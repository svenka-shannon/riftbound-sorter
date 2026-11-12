"""
Regression tests for the third audit (M1 calibration validation, M2 stale
clean marker after the hardware tools, minors 1-9). Ported from the audit's
scratch tests (/tmp/rb_audit3/tests: test_new_cfg.py, test_sigkill_marker.py,
test_elevator_cap.py, test_ui_state.py, test_sweep_binfull.py) — every one
now asserts instead of printing.

Run:
  uv run --python 3.11 --with pytest --with pillow --with numpy --with requests \
         --with flask --with imagehash pytest -q tests/
"""

import importlib.util
import json
import math
import os
import stat
import subprocess
import sys
import time
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import main
import test_audit2_sweep as TS
from conftest import ROOT
from hardware import (card_detect, elevator, instance, loadcell, machine_config, servos, shuttle,
                      vacuum)
import fakegpio as G


def _load_script(name):
    spec = importlib.util.spec_from_file_location(f"_audit3_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(path: Path, data):
    path.write_text(data if isinstance(data, str) else json.dumps(data))


# ══ M1: shuttle_calibration.json validated strictly ══════════════════════════
SHUTTLE_BAD = {
    "tilt_str": ({"tilt": {"level": "abc"}}, "tilt.level: must be a number"),
    "tilt_nan": ('{"tilt": {"upper": NaN}}', "NaN is not a valid JSON number"),
    "tilt_typo_1122": ({"tilt": {"upper": 1122}}, "tilt.upper: 1122° is outside the servo range"),
    "tilt_neg": ({"tilt": {"lower": -40}}, "tilt.lower: -40° is outside the servo range"),
    "tilt_list": ({"tilt": [1, 2]}, "tilt: must be a JSON object"),
    "tilt_bool": ({"tilt": {"level": True}}, "tilt.level: must be a number"),
    "tilt_out_of_window": ({"tilt": {"upper": 140}}, "tilt.upper: 140° is more than 8° from the nominal"),
    # audit 4 MJ1: the windows are ±8°, so an order slip is now tested inside them
    "tilt_order": ({"tilt": {"level": 95, "hold": 94}}, "tilt.level (95°) must be below tilt.hold (94°)"),
    "tilt_unknown_key": ({"tilt": {"levle": 93}}, "tilt.levle: unknown key"),
    "shuttle_null": ({"shuttle": {"0": None}}, "shuttle.0: must be a number"),
    "shuttle_key_00": ({"shuttle": {"00": 175}}, "shuttle.00: unknown key"),
    "shuttle_swapped": ({"shuttle": {"home": 80, "1": 79.5}}, "shuttle.home (80°) must be below shuttle.1"),
    "timing_neg": ({"timing": {"dump_dwell_s": -1}}, "timing.dump_dwell_s: -1 is outside"),
    "timing_str": ({"timing": {"settle_s": "0.2"}}, "timing.settle_s: must be a finite number"),
    "timing_unknown": ({"timing": {"dwell": 1}}, "timing.dwell: unknown key"),
    "range_zero": ({"actuation_range": {"2": 0}}, "actuation_range.2: must be 180"),
    "range_1000": ({"actuation_range": {"1": 1000}}, "actuation_range.1: must be 180"),
    "range_270_5": ({"actuation_range": {"2": 270.5}}, "actuation_range.2: must be 180"),
    "range_channel": ({"actuation_range": {"3": 180}}, "actuation_range.3: unknown channel"),
    "unknown_section": ({"tlit": {"level": 90}}, "tlit: unknown section"),
    "invert_str": ({"invert": {"2": "true"}}, "invert.2: must be true or false"),
    "over_180": ({"shuttle": {"0": 195}}, "shuttle.0: 195° is outside the servo range [0, 180]"),
}


@pytest.mark.parametrize("case", list(SHUTTLE_BAD))
def test_shuttle_calibration_rejected_and_nothing_applied(case):
    data, needle = SHUTTLE_BAD[case]
    _write(shuttle._CALIBRATION_FILE, data)
    before = (dict(shuttle.TILT_ANGLES), dict(shuttle.SHUTTLE_ANGLES), dict(shuttle.TIMING),
              dict(shuttle.SHUTTLE_ACTUATION_RANGE), dict(shuttle.SHUTTLE_INVERT))
    writes = []
    orig = shuttle._write
    shuttle._write = lambda ch, a: (writes.append((ch, a)), orig(ch, a))
    try:
        with pytest.raises(shuttle.ShuttleConfigError) as ei:
            shuttle.init(assume_rest=True)
    finally:
        shuttle._write = orig
    assert needle in str(ei.value), str(ei.value)
    assert writes == []                                         # nothing commanded
    after = (dict(shuttle.TILT_ANGLES), dict(shuttle.SHUTTLE_ANGLES), dict(shuttle.TIMING),
             dict(shuttle.SHUTTLE_ACTUATION_RANGE), dict(shuttle.SHUTTLE_INVERT))
    assert after == before                                      # nothing applied


def test_shuttle_calibration_lists_every_problem():
    _write(shuttle._CALIBRATION_FILE, {"tilt": {"upper": 1122, "level": "x"}, "timing": {"settle_s": -1},
                                       "bogus": 1, "invert": {"1": 1}})
    with pytest.raises(shuttle.ShuttleConfigError) as ei:
        shuttle._load_calibration()
    assert len(ei.value.problems) == 5
    for key in ("tilt.upper", "tilt.level", "timing.settle_s", "bogus", "invert.1"):
        assert key in str(ei.value)


def test_shuttle_calibration_valid_file_applied_and_absent_keys_reset():
    _write(shuttle._CALIBRATION_FILE, {
        "_note": "x", "tilt": {"level": 92.6, "upper": 115, "_c": 1},
        "shuttle": {"home": 76, "0": 177}, "timing": {"dump_dwell_s": 0.8},
        "actuation_range": {"2": 270}, "invert": {"2": True}})
    shuttle._load_calibration()
    assert shuttle.TILT_ANGLES["level"] == 92.6 and shuttle.TILT_ANGLES["upper"] == 115.0
    assert shuttle.SHUTTLE_ANGLES["home"] == 76.0 and shuttle.SHUTTLE_ANGLES[0] == 177.0
    assert shuttle.TIMING["dump_dwell_s"] == 0.8
    assert shuttle.SHUTTLE_ACTUATION_RANGE[2] == 270 and shuttle.SHUTTLE_INVERT[2] is True
    _write(shuttle._CALIBRATION_FILE, {"tilt": {"hold": 96.5}})       # keys removed from the file
    shuttle._load_calibration()
    assert shuttle.TILT_ANGLES == {**shuttle.NOMINAL_TILT_ANGLES, "hold": 96.5}
    assert shuttle.SHUTTLE_ANGLES == shuttle.NOMINAL_SHUTTLE_ANGLES
    assert shuttle.TIMING == shuttle.NOMINAL_TIMING
    assert shuttle.SHUTTLE_ACTUATION_RANGE == shuttle.NOMINAL_ACTUATION_RANGE


def test_shuttle_sanity_window_matches_calibrate_tool():
    # audit 4 MJ1: ±8° (was ±25°); audit 5 MJ-B: carriage ±12°. The tool's jog
    # window IS the module's per-pose window
    cs = _load_script("calibrate_servos")
    assert shuttle.SANITY_WINDOW_DEG == {"tilt": 8.0, "shuttle": 12.0} and not hasattr(cs, "WINDOW_DEG")
    lo, hi = shuttle.sanity_window("tilt", "upper")
    assert (lo, hi) == (pytest.approx(104.2), pytest.approx(120.2))
    assert shuttle.sanity_window("shuttle", 0) == (pytest.approx(166.0), 180.0)   # clipped to the range


# ══ M1: servo_calibration.json validated strictly ════════════════════════════
SERVO_BAD = {
    "park_str": ({"pickup_arm": {"ARM_PARK": "90"}}, "pickup_arm.ARM_PARK: must be a number"),
    "pick_nan": ('{"pickup_arm": {"ARM_PICK": NaN}}', "NaN is not a valid JSON number"),
    "drop_400": ({"pickup_arm": {"ARM_DROP": 400}}, "pickup_arm.ARM_DROP: 400° is outside the servo range"),
    "arm_list": ({"pickup_arm": []}, "pickup_arm: must be a JSON object"),
    "drop_120": ({"pickup_arm": {"ARM_DROP": 120}}, "pickup_arm.ARM_DROP: 120° is outside the sanity window"),
    "same_side": ({"pickup_arm": {"ARM_PICK": 175, "ARM_DROP": 170}}, "opposite sides of ARM_PARK"),
    "unknown_key": ({"pickup_arm": {"ARM_PIKC": 170}}, "pickup_arm.ARM_PIKC: unknown key"),
    "unknown_section": ({"pickup": {"ARM_PICK": 170}}, "pickup: unknown section"),
    "legacy_out_of_window": ({"pickup_arm": {"ARM_DOWN": 60}},
                             "pickup_arm.ARM_DOWN (legacy, used as ARM_PICK)"),
    "top_level_list": ("[1]", "must be a JSON object"),
}


@pytest.mark.parametrize("case", list(SERVO_BAD))
def test_servo_calibration_rejected_and_nothing_applied(case, monkeypatch):
    data, needle = SERVO_BAD[case]
    _write(servos._CALIBRATION_FILE, data)
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))
    writes = []
    orig = servos._arm_write
    monkeypatch.setattr(servos, "_arm_write", lambda a: (writes.append(a), orig(a)))
    before = (servos.ARM_PICK, servos.ARM_DROP, servos.ARM_PARK)
    with pytest.raises(servos.ServoConfigError) as ei:
        servos.init(assume_parked=True)
    assert needle in str(ei.value), str(ei.value)
    assert (servos.ARM_PICK, servos.ARM_DROP, servos.ARM_PARK) == before
    assert writes == [] and slept == []


def test_servo_calibration_mirrored_legacy_and_old_sections_accepted(capsys):
    _write(servos._CALIBRATION_FILE, {"pickup_arm": {"ARM_PICK": 6, "ARM_DROP": 174, "ARM_PARK": 91}})
    servos.init()
    assert (servos.ARM_PICK, servos.ARM_DROP, servos.ARM_PARK) == (6.0, 174.0, 91.0)
    _write(servos._CALIBRATION_FILE, {"gate": {"GATE_LEFT": 30}, "pickup_arm": {"ARM_DOWN": 172, "ARM_UP": 88}})
    servos.init()
    assert (servos.ARM_PICK, servos.ARM_PARK) == (172.0, 88.0) and servos.ARM_DROP == servos.NOMINAL_ARM["ARM_DROP"]
    out = capsys.readouterr().out
    assert "legacy ARM_DOWN as ARM_PICK" in out and '"gate" section ignored' in out
    _write(servos._CALIBRATION_FILE, {"pickup_arm": {"ARM_PICK": 170, "ARM_DOWN": 60}})   # superseded
    servos.init()
    assert servos.ARM_PICK == 170.0
    servos._CALIBRATION_FILE.unlink()                                  # absent → nominal again
    servos.init()
    assert {k: getattr(servos, k) for k in servos.NOMINAL_ARM} == servos.NOMINAL_ARM


@pytest.mark.parametrize("which", ["servo", "shuttle"])
def test_main_exits_78_on_bad_calibration(which, monkeypatch):
    if which == "servo":
        _write(servos._CALIBRATION_FILE, {"pickup_arm": {"ARM_DROP": 400}})
    else:
        _write(shuttle._CALIBRATION_FILE, {"tilt": {"upper": 1122}})
    monkeypatch.setattr(main, "_hw_initialised", False)
    args = Namespace(build_db=False, calibrate=False, web_only=False, dry_run=False, mass=None)
    with pytest.raises(SystemExit) as ei:
        main._main(args)
    assert ei.value.code == machine_config.EX_CONFIG == 78
    assert not vacuum.pump_is_on()


# ══ M1: the calibrate tool refuses to save invalid values ════════════════════
@pytest.fixture
def cs():
    mod = _load_script("calibrate_servos")
    mod.load_modules(mock=True)
    assert mod.shuttle is shuttle and mod.servos is servos
    yield mod
    if mod._lock not in (None, True):
        mod._lock.close()


def test_calibrate_refuses_invalid_saves(cs):
    assert cs.save_arm("ARM_DROP", 120.0) is False
    assert not servos._CALIBRATION_FILE.exists()
    assert cs.save_shuttle("tilt", "upper", 140.0) is False             # outside the sanity window
    assert cs.save_shuttle("tilt", "hold", 113.0) is False              # hold above upper (112.2)
    assert not shuttle._CALIBRATION_FILE.exists()
    assert shuttle.TILT_ANGLES["hold"] == 97.0
    assert cs.save_shuttle("tilt", "level", 92.6) is True
    assert cs.save_arm("ARM_DROP", 7.5) is True
    _, problems = shuttle.validate_calibration(json.loads(shuttle._CALIBRATION_FILE.read_text()))
    assert problems == []
    shuttle._load_calibration()
    servos.init()
    assert shuttle.TILT_ANGLES["level"] == 92.6 and servos.ARM_DROP == 7.5


def test_calibrate_jog_refused_save_keeps_jogging(cs, monkeypatch):
    answers = iter(["s", "-", "s"])
    monkeypatch.setattr(cs, "ask", lambda prompt="": next(answers))
    saves = []
    got = cs.jog("x", start=113.0, stored=113.0, nominal=97.0, lo=100.0, hi=120.0, pulse_range=180,
                 move=lambda a: None, save=lambda a: (saves.append(a), len(saves) > 1)[1])
    assert saves == [113.0, 112.5] and got == 112.5


def test_calibrate_jog_window_inside_sanity_window(cs):
    # audit 4 MJ1 / audit 5: the jog window is exactly the module's per-pose window
    assert cs.window(112.2, 180, shuttle.sanity_window("tilt", "upper")) == (pytest.approx(104.2),
                                                                           pytest.approx(120.2))
    assert cs.window(170.0, 180, servos.sanity_window("ARM_PICK", 170.0)) == (155.0, 180.0)
    assert cs.window(10.0, 180, servos.sanity_window("ARM_PICK", 10.0)) == (0.0, 25.0)   # mirrored


def test_calibrate_tool_exits_78_on_invalid_file_before_claiming(cs, monkeypatch):
    _write(shuttle._CALIBRATION_FILE, {"tilt": {"upper": 1122}})
    monkeypatch.setattr(sys, "argv", ["calibrate_servos.py"])
    monkeypatch.setattr(cs, "ask", lambda prompt="": "q")
    with pytest.raises(SystemExit) as ei:
        cs.main()
    assert ei.value.code == 78
    assert not instance.state_file(True).exists()                      # nothing claimed / moved


# ══ M1: bin_limits.json validated (positive ints ≤ the geometric maximum) ═══
def test_bin_limit_caps_cover_defaults():
    for b, d in main.DEFAULT_BIN_LIMITS.items():
        assert 1 <= d <= main.BIN_LIMIT_MAX[b]
    assert main.BIN_LIMIT_MAX[0] == 54 and main.BIN_LIMIT_MAX[4] == 15 and main.BIN_LIMIT_MAX[9] == 52


def test_bin_limits_valid_file(tmp_path):
    f = tmp_path / "limits.json"
    _write(f, {"_c": "x", "0": 45, "4": 14, "9": 52.0})
    b = main.BinCounts(tmp_path / "c.json", f, main.DEFAULT_BIN_LIMITS)
    assert b.limits[0] == 45 and b.limits[4] == 14 and b.limits[9] == 52 and b.limits[1] == 40


def test_bin_limits_every_problem_listed(tmp_path):
    f = tmp_path / "limits.json"
    _write(f, {"0": "45", "1": 0, "2": 55, "4": 16, "9": 53, "8": 10, "5": 12.5, "6": True, "3": -4})
    with pytest.raises(main.BinLimitsError) as ei:
        main.BinCounts(tmp_path / "c.json", f, main.DEFAULT_BIN_LIMITS)
    assert len(ei.value.problems) == 9
    msg = str(ei.value)
    assert "2: 55 is outside 1..54 (lower floor: default 40, geometric maximum 54)" in msg
    assert "4: 16 is outside 1..15 (upper floor" in msg and "9: 53 is outside 1..52 (reject" in msg
    assert "8: unknown bin" in msg


@pytest.mark.parametrize("text", ['{"0": NaN}', "[40]", "{oops"])
def test_bin_limits_bad_json(tmp_path, text):
    f = tmp_path / "limits.json"
    f.write_text(text)
    with pytest.raises(main.BinLimitsError):
        main.BinCounts(tmp_path / "c.json", f, main.DEFAULT_BIN_LIMITS)


def test_bad_bin_limits_exit_78_before_anything(tmp_path):
    f = tmp_path / "limits.json"
    _write(f, {"4": 400})
    env = dict(os.environ, MOCK_HARDWARE="1", RIFTBOUND_BIN_LIMITS=str(f))
    r = subprocess.run([sys.executable, str(ROOT / "main.py"), "--web-token"], cwd=tmp_path, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 78, r.stderr
    assert "invalid bin limits" in r.stderr and "4: 400 is outside 1..15" in r.stderr


# ══ M2: hardware tools take the lock and invalidate the clean marker ═════════
@pytest.fixture
def shared_paths(monkeypatch):
    """main's lock / marker = the ones the tools use (mock files in tmp)."""
    monkeypatch.setattr(main, "INSTANCE_LOCK_FILE", instance.lock_file(True))
    monkeypatch.setattr(main, "MACHINE_STATE_FILE", instance.state_file(True))
    monkeypatch.setattr(main, "_instance_lock_fh", None)
    yield
    if main._instance_lock_fh not in (None, True):
        main._instance_lock_fh.close()


def test_tool_claim_marks_unclean_and_excludes_the_sorter(shared_paths):
    main._write_machine_state(clean=True, confirmed=False, reason="clean", rest_pose="home_level")
    fh = instance.claim_for_tool("scripts/test_hardware.py", True)
    ms = main.read_machine_state()
    assert ms["clean"] is False and ms["reason"].startswith("tool ran: scripts/test_hardware.py")
    assert "rest_pose" not in ms
    assert main.sorter_running() is True and main.acquire_instance_lock() is False
    fh.close()
    assert main.acquire_instance_lock() is True                         # sorter now running …
    with pytest.raises(instance.LockBusy, match="main.py"):             # … so a tool refuses
        instance.claim_for_tool("scripts/calibrate_servos.py", True)


def test_stale_clean_marker_after_tool(shared_paths, monkeypatch):
    """Audit test_new_cfg.test_stale_clean_marker_after_tool: a clean stop, then a tool
    leaves the carriage at column 2 with the cradle tipped LOWER and dies. The next
    start must NOT trust the old record (no blind full-speed carriage jump)."""
    main._write_machine_state(clean=True, confirmed=False, reason="clean", rest_pose="home_level")
    lock = instance.claim_for_tool("scripts/calibrate_servos.py", True)
    shuttle.init(); shuttle.home(); shuttle.hold(); shuttle.to_column(2); shuttle.tip_lower()   # died here
    lock.close()                                                        # process gone
    writes = []
    orig = shuttle._write
    monkeypatch.setattr(shuttle, "_write", lambda ch, a: (writes.append((ch, a)), orig(ch, a)))
    ms = main.read_machine_state()
    assume = bool(ms.get("clean")) and ms.get("rest_pose") == "home_level"
    assert assume is False
    shuttle.init(assume_rest=assume)
    assert writes == []                                                 # nothing moves until confirmed


def test_test_hardware_claims_before_moving(shared_paths, monkeypatch):
    th = _load_script("test_hardware")
    order = []
    real_claim = instance.claim_for_tool
    monkeypatch.setattr(instance, "claim_for_tool", lambda t, m: (order.append("claim"), real_claim(t, m))[1])
    real_init = vacuum.init
    monkeypatch.setattr(vacuum, "init", lambda: (order.append("vacuum.init"), real_init())[1])
    main._write_machine_state(clean=True, confirmed=False, reason="clean", rest_pose="home_level")
    th.init_hardware(mock=True)
    try:
        assert order[:2] == ["claim", "vacuum.init"]
        ms = main.read_machine_state()
        assert ms["clean"] is False and "tool ran: scripts/test_hardware.py" in ms["reason"]
        assert main.acquire_instance_lock() is False
    finally:
        th._lock.close()


def test_test_hardware_exits_78_on_bad_calibration(shared_paths):
    th = _load_script("test_hardware")
    _write(servos._CALIBRATION_FILE, {"pickup_arm": {"ARM_DROP": 400}})
    try:
        with pytest.raises(SystemExit) as ei:
            th.init_hardware(mock=True)
        assert ei.value.code == 78
    finally:
        if th._lock not in (None, True):
            th._lock.close()


def test_test_hardware_refuses_while_sorter_runs(shared_paths):
    th = _load_script("test_hardware")
    assert main.acquire_instance_lock() is True
    with pytest.raises(SystemExit, match="sorter or another tool is running"):
        th.init_hardware(mock=True)


def test_calibrate_servos_quit_leaves_marker_unclean(cs, shared_paths, monkeypatch):
    main._write_machine_state(clean=True, confirmed=False, reason="clean", rest_pose="home_level")
    monkeypatch.setattr(sys, "argv", ["calibrate_servos.py"])
    monkeypatch.setattr(cs, "ask", lambda prompt="": "q")
    cs.main()                                                          # quit at once: parked
    ms = main.read_machine_state()
    assert ms["clean"] is False and "tool ran: scripts/calibrate_servos.py" in ms["reason"]
    assert main.sorter_running() is True                               # lock held until exit


def test_calibrate_camera_takes_lock_and_marks_unclean(shared_paths, monkeypatch):
    cc = _load_script("calibrate_camera")
    main._write_machine_state(clean=True, confirmed=False, reason="clean", rest_pose="home_level")
    monkeypatch.setattr(sys, "argv", ["calibrate_camera.py"])
    answers = iter(["n", "", "q"])
    monkeypatch.setattr(cc, "ask", lambda prompt="": next(answers))
    try:
        cc.main()
        ms = main.read_machine_state()
        assert ms["clean"] is False and "calibrate_camera.py" in ms["reason"]
        assert main.acquire_instance_lock() is False
    finally:
        if cc._lock not in (None, True):
            cc._lock.close()


def test_marker_write_is_fsynced(tmp_path, monkeypatch):
    synced = []
    real = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (synced.append(stat.S_ISDIR(os.fstat(fd).st_mode)),
                                                 real(fd))[1])
    instance.write_state(tmp_path / "ms.json", clean=False, reason="x")
    assert synced[0] is False and True in synced                        # the file, then the directory
    assert json.loads((tmp_path / "ms.json").read_text())["reason"] == "x"


# ══ Minor 1 + 2: elevator caps (ported test_elevator_cap.py) ═════════════════
def _reset_elevator(monkeypatch, cards, top_nc=True, broken=False, trip_offset=0.0):
    monkeypatch.setattr(elevator, "TOP_SWITCH_NC", top_nc)
    monkeypatch.setitem(elevator._mock_wire_broken, "top", broken)
    monkeypatch.setattr(elevator, "PICK_Z_MM", elevator.PICK_Z_MM + trip_offset)
    elevator.init()
    elevator.mock_set_cards(cards)
    elevator._mock_plate_mm = 40.0
    assert elevator.home()


def test_no_wiring_broken_wire_first_raise_never_pushes_the_stack(monkeypatch):
    _reset_elevator(monkeypatch, 150, top_nc=False, broken=True)
    start = elevator.position_mm()
    with pytest.raises(elevator.ElevatorError, match="top switch not detected"):
        elevator.raise_to_pick()
    assert elevator.position_mm() - start <= elevator.RAISE_CAP_MM + 0.01
    top = elevator.PLATE_Z_ZERO_MM + elevator.position_mm() + 150 * elevator.CARD_THICKNESS_MM
    assert top < elevator.PICK_Z_MM                                     # stack never reaches the arm


def test_nc_broken_wire_reads_pressed_no_rise(monkeypatch):
    _reset_elevator(monkeypatch, 150, top_nc=True, broken=True)
    assert elevator.raise_to_pick() is True
    assert elevator.position_mm() == 0.0


@pytest.mark.parametrize("off", [0.0, -2.0, -3.5, -5.5])
def test_run_to_empty_is_hopper_empty_not_wiring_fault(monkeypatch, off):
    """The real top switch trips `off` mm below the CAD pick height."""
    _reset_elevator(monkeypatch, 5, trip_offset=off)
    out = []
    for _ in range(8):
        r = elevator.raise_to_pick()                                    # never ElevatorError
        out.append(r)
        if not r:
            break
        elevator.mock_set_cards(elevator._mock_cards - 1)               # one card picked
    assert out == [True] * 5 + [False]


def test_mid_stack_no_trip_is_still_a_wiring_fault(monkeypatch):
    _reset_elevator(monkeypatch, 150)
    assert elevator.raise_to_pick() is True
    monkeypatch.setattr(elevator, "_top_pressed", lambda: False)
    with pytest.raises(elevator.ElevatorError, match="check wiring"):
        elevator.raise_to_pick()


def test_last_card_with_low_trip_stops_as_hopper_empty(monkeypatch, tmp_path):
    TS.setup_rig(monkeypatch, tmp_path)
    monkeypatch.setattr(elevator, "PICK_Z_MM", elevator.PICK_Z_MM - 3.5)
    elevator.mock_set_cards(1)
    assert elevator.raise_to_pick() is True
    elevator.mock_set_cards(0)                                          # the last card was picked
    with pytest.raises(main.HopperEmpty):
        main.sort_one_card(TS.Eng())


# ══ Minor 3: stopped on a full bin with a card held → needs_confirm, Resume 409 ═
def test_unclean_stop_shows_needs_confirm_and_resume_409(monkeypatch, tmp_path):
    """Ported test_ui_state.py."""
    TS.setup_rig(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "_beat", lambda: None)
    from web.app import create_app
    app = create_app(token="t")
    app.testing = True
    c = app.test_client()
    main._bins.limits[2] = 0
    monkeypatch.setattr(main, "RulesEngine", lambda f: TS.Eng())
    main._write_machine_state(clean=True, confirmed=False, reason="", rest_pose="home_level")
    polls = {"n": 0}
    orig_full = main._bins.is_full

    def is_full(b):
        polls["n"] += 1
        if polls["n"] == 3:
            c.post("/api/stop", headers={"X-Auth-Token": "t"})
        return orig_full(b)
    monkeypatch.setattr(main._bins, "is_full", is_full)
    seen = {}

    def await_op(needs_confirm):
        seen.update(needs_confirm=needs_confirm, card_at=main._card_at, state=main._status["state"],
                    msg=main._status["message"], ms=main.read_machine_state())
        r = c.post("/api/resume", headers={"X-Auth-Token": "t"})
        seen["resume"] = (r.status_code, r.get_json())
        return False
    monkeypatch.setattr(main, "_await_operator", await_op)
    main._operate(dry_run=False)
    assert seen["needs_confirm"] is True and seen["card_at"] == "cradle"
    assert seen["state"] == "needs_confirm" and "card held on the cradle" in seen["msg"]
    assert seen["ms"]["clean"] is False
    code, body = seen["resume"]
    assert code == 409 and "Machine clear" in body["error"]


# ══ Minor 4: the marker is unclean BEFORE prepare_machine() moves anything ═══
def test_mark_running_before_prepare(monkeypatch):
    main._write_machine_state(clean=True, confirmed=False, reason="x", rest_pose="home_level")
    seen = {}

    def prep(confirmed):
        seen["ms"] = main.read_machine_state()
        raise main.StopRequested("stop")
    monkeypatch.setattr(main, "prepare_machine", prep)
    with pytest.raises(main.StopRequested):
        main.start_and_run(confirmed=False)
    assert seen["ms"]["clean"] is False and main._marker_armed


def test_sigkill_marker_sweep(monkeypatch, tmp_path):
    """Ported test_sigkill_marker.py: at EVERY hardware event of start-up + 2 cards +
    teardown, the on-disk marker never says clean + home_level while the machine is
    not at rest (or a card is inside)."""
    TS.setup_rig(monkeypatch, tmp_path)
    main._write_machine_state(clean=True, confirmed=False, reason="prev clean stop", rest_pose="home_level")
    bad = []

    def check(ev):
        ms = main.read_machine_state()
        if not (ms.get("clean") and ms.get("rest_pose") == "home_level"):
            return
        t, tilt, _ = shuttle.state()
        card = (main._card_at is not None or loadcell._mock_load_g > 0.5
                or card_detect.MOCK_SCENE.card_x_mm is not None)
        if (t, tilt) != ("home", "level") or card or servos.arm_angle() != servos.ARM_PARK:
            bad.append((ev, t, tilt, card, servos.arm_angle(), main._status["state"]))
    for mod, name in ((shuttle, "_write"), (servos, "_arm_write")):
        f = getattr(mod, name)

        def wrap(*a, f=f, name=name):
            r = f(*a)
            check(name)
            return r
        monkeypatch.setattr(mod, name, wrap)
    s = time.sleep
    monkeypatch.setattr(time, "sleep", lambda x: (s(x), check("sleep")))
    assert main.start_and_run(confirmed=False, engine=TS.Eng(), max_cycles=2) == "stopped"
    main._running = False
    main.teardown()
    assert bad == []
    ms = main.read_machine_state()
    assert ms["clean"] is True and ms["rest_pose"] == "home_level"     # a real clean stop after all


# ══ Minor 5: servos released while idle at rest, rest pose re-asserted ═══════
# Audit 4 m3: ONLY ch1 (tilt, stalling on the level ledges) is released; ch0
# (arm) and ch2 (carriage) keep holding while the operator works in the machine.
def _released3():
    return (servos.arm_released(), shuttle.released(shuttle.CH_TILT),
            shuttle.released(shuttle.CH_SHUTTLE))


def test_idle_release_and_reassert(monkeypatch, tmp_path):
    TS.setup_rig(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "RulesEngine", lambda f: TS.Eng())
    main._write_machine_state(clean=True, confirmed=False, reason="", rest_pose="home_level")
    elevator.mock_set_cards(0)                                         # → hopper empty at once
    seen = []

    def await_op(needs_confirm):
        seen.append((main._status["state"], needs_confirm) + _released3())
        return False
    monkeypatch.setattr(main, "_await_operator", await_op)
    main._operate(dry_run=False)
    assert seen == [("hopper_empty", False, False, True, False)]
    assert main.read_machine_state()["clean"] is True
    # resume: the rest pose is re-asserted (one write per channel) before the elevator moves
    log = []
    o_sw, o_aw, o_home = shuttle._write, servos._arm_write, elevator.home
    monkeypatch.setattr(shuttle, "_write", lambda ch, a: (log.append((ch, a)), o_sw(ch, a)))
    monkeypatch.setattr(servos, "_arm_write", lambda a: (log.append((0, a)), o_aw(a)))
    monkeypatch.setattr(elevator, "home", lambda **k: (log.append("elevator.home"), o_home(**k))[1])
    with pytest.raises(main.HopperEmpty):
        main.prepare_machine(confirmed=False)
        main.sort_one_card(TS.Eng())
    assert log[:4] == [(0, servos.ARM_PARK), (shuttle.CH_SHUTTLE, shuttle.SHUTTLE_ANGLES["home"]),
                       (shuttle.CH_TILT, shuttle.TILT_ANGLES["level"]), "elevator.home"]
    assert not servos.arm_released() and not shuttle.released()


def test_operator_pause_releases_and_reasserts(monkeypatch, tmp_path):
    TS.setup_rig(monkeypatch, tmp_path)
    main._control["pause"] = True
    seen = []

    def sleep(_):
        seen.append(_released3())
        main._control["pause"] = False
    monkeypatch.setattr(time, "sleep", sleep)
    assert main._wait_while_paused() is True
    assert seen == [(False, True, False)]
    assert not servos.arm_released() and not shuttle.released() and shuttle.at_rest()


def test_held_card_keeps_servos_powered(monkeypatch, tmp_path):
    TS.setup_rig(monkeypatch, tmp_path)
    shuttle.hold()                                                     # card held in HOLD: not at rest
    main._release_idle()
    assert not servos.arm_released() and not shuttle.released()


def test_level_preload_advice_is_half_a_degree():
    cs = _load_script("calibrate_servos")
    level = " ".join(next(a for p, _, a in cs.TILT_STEPS if p == "level"))
    assert "0.5°" in level and "1.5°" not in level
    assert shuttle.NOMINAL_TILT_ANGLES["level"] == pytest.approx(93.6 - 0.5)


# ══ Minor 6: card held on the cup — clear message, pump-on time limit ════════
def _cup_held(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    servos.init()
    servos.arm_park()
    vacuum.init()
    main._set_card_at("cup")
    monkeypatch.setattr(servos, "move_arm_smooth", lambda *a, **k: (_ for _ in ()).throw(OSError("I2C")))
    vacuum.pump_on()
    with pytest.raises(main.CupNotSecured, match="card held on cup"):
        main._secure_cup()
    assert vacuum.pump_is_on() and main._cup_hold_since is not None


def test_cup_hold_message_then_pump_off_after_limit(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["t"])
    _cup_held(monkeypatch)
    main._set_state("error", "unexpected error")
    main._cup_hold_watch()
    assert main._status["message"].startswith(main.CUP_HELD_MSG)
    assert main._status["message"].startswith("card held on cup — remove it by hand before stopping the service")
    assert vacuum.pump_is_on()
    clock["t"] += main.CUP_HOLD_MAX_S - 1
    main._cup_hold_watch()
    assert vacuum.pump_is_on() and "1 s more" in main._status["message"]
    clock["t"] += 2
    main._cup_hold_watch()
    assert not vacuum.pump_is_on()
    assert main._status["state"] == "error" and "switched off" in main._status["message"]


def test_cup_hold_limit_inside_operator_wait(monkeypatch):
    clock = {"t": 0.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["t"])
    _cup_held(monkeypatch)
    main._set_state("needs_confirm", "x")
    msgs = []

    def sleep(_):
        msgs.append(main._status["message"])
        clock["t"] += 60.0
        if not vacuum.pump_is_on():
            main._running = False
    monkeypatch.setattr(time, "sleep", sleep)
    assert main._await_operator(needs_confirm=True) is False
    assert msgs[0].startswith(main.CUP_HELD_MSG)
    assert not vacuum.pump_is_on()
    assert len(msgs) == math.ceil(main.CUP_HOLD_MAX_S / 60.0) + 1


def test_cup_hold_limit_configurable():
    assert machine_config.SCHEMA["sort"]["CUP_HOLD_MAX_S"]["min"] == 10.0
    ex = json.loads((ROOT / "config" / "machine.example.json").read_text())
    assert ex["sort"]["CUP_HOLD_MAX_S"] == main.CUP_HOLD_MAX_S


# ══ Minor 7: cmdline_param fsyncs the temp file and the directory ════════════
def test_cmdline_param_fsyncs_before_and_after_rename(tmp_path, monkeypatch):
    cp = _load_script("cmdline_param")
    f = tmp_path / "cmdline.txt"
    f.write_text("console=tty1 root=PARTUUID=1 rootwait\n")
    events = []
    real_fsync, real_replace = os.fsync, os.replace
    monkeypatch.setattr(os, "fsync", lambda fd: (events.append(
        ("fsync_dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "fsync_file")), real_fsync(fd))[1])
    monkeypatch.setattr(os, "replace", lambda a, b: (events.append(("replace", Path(b).name)),
                                                     real_replace(a, b))[1])
    assert cp.ensure_param(f, "pinctrl_bcm2835.persist_gpio_outputs=0") is True
    i = events.index(("replace", "cmdline.txt"))
    assert events[i - 1] == "fsync_file" and events[i + 1] == "fsync_dir"
    j = events.index(("replace", "cmdline.txt.riftbound.bak"))
    assert events[j - 1] == "fsync_file" and j < i
    assert f.read_text().split()[-1] == "pinctrl_bcm2835.persist_gpio_outputs=0"
    assert (tmp_path / "cmdline.txt.riftbound.bak").read_text() == "console=tty1 root=PARTUUID=1 rootwait\n"
    assert not (tmp_path / "cmdline.txt.tmp").exists()


# ══ Minor 8: a second signal between _main returning and teardown() ══════════
@pytest.fixture
def main_entry(monkeypatch):
    monkeypatch.setattr(main.signal, "signal", lambda *a: None)
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setattr(main, "_hw_initialised", False)
    monkeypatch.setattr(main, "_instance_lock_fh", None)
    yield
    if main._instance_lock_fh not in (None, True):
        main._instance_lock_fh.close()


def test_second_signal_in_teardown_window_still_tears_down(main_entry, monkeypatch):
    calls = []
    real_teardown = main.teardown

    def fake_main(args):
        main._hw_initialised = True
        main._on_signal()                         # 1st signal: finish, then return

    def teardown_with_signal_first():
        main._on_signal()                         # 2nd signal lands before teardown sets its flag
        calls.append("teardown")
        real_teardown()
    monkeypatch.setattr(main, "_main", fake_main)
    monkeypatch.setattr(main, "teardown", teardown_with_signal_first)
    main.main()                                   # no Shutdown escapes
    assert calls == ["teardown"] and main._tearing_down is True
    assert main._signals == 2


def test_shutdown_raised_in_main_still_tears_down(main_entry, monkeypatch):
    calls = []
    real_teardown = main.teardown

    def fake_main(args):
        main._hw_initialised = True
        main._on_signal()
        main._on_signal()                         # raises Shutdown inside _main
        raise AssertionError("not reached")

    def td():
        main._on_signal()                         # a third one during teardown: ignored
        calls.append("teardown")
        real_teardown()
    monkeypatch.setattr(main, "_main", fake_main)
    monkeypatch.setattr(main, "teardown", td)
    main.main()
    assert calls == ["teardown"] and main._shutdown_raises is False


# ══ Ported test_sweep_binfull.py: signals at every event of a bin-full run ═══
@pytest.mark.parametrize("nsig", [1, 2])
def test_sweep_binfull(monkeypatch, tmp_path, nsig):
    bad, outcomes = {}, {}
    for k in range(1, 260):
        main._signals = 0; main._running = True; main._tearing_down = False
        main._marker_armed = False; main._card_at = None
        main._control.update(pause=False, stop=False, resume=False, reload_rules=False)
        r, outcome, ms = TS.run_once(monkeypatch, tmp_path, k, nsig, bin_full_after=True)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        if not r.fired:
            bad[k] = ("never fired",)
        if r.violations:
            bad[k] = (r.events[k - 1] if k - 1 < len(r.events) else "?", r.violations[:3])
        if loadcell._mock_load_g > 0.5 and ms.get("clean"):
            bad[k] = ("clean marker with card on cradle",)
    assert not bad, list(bad.items())[:8]
    assert sum(outcomes.values()) == 259
