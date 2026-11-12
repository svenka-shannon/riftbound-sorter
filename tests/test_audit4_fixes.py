"""
Regression tests for the fourth audit (MJ1 calibration windows, minors m1-m9)
and the follow-up "every config error exits 78 in every tool". Ported from the
audit's scratch probes (/tmp/rb_audit4/tests4/test_probe4.py) — every probe
now asserts instead of printing. The operate-loop sweep is in
tests/test_audit4_operate_sweep.py.

Run:
  uv run --python 3.11 --with pytest --with pillow --with numpy --with requests \
         --with flask --with imagehash pytest -q tests/
"""

import importlib.util
import json
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import main
import test_audit2_sweep as TS
from conftest import ROOT
from hardware import elevator, instance, loadcell, servos, shuttle, vacuum


def _load_script(name):
    spec = importlib.util.spec_from_file_location(f"_audit4_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def cs():
    mod = _load_script("calibrate_servos")
    mod.load_modules(mock=True)
    yield mod
    if mod._lock not in (None, True):
        mod._lock.close()


# ══ MJ1: calibration sanity windows tight enough to catch swapped digits ═════
# Every swapped-digit / transposed-pose typo the audit found accepted.
SWAPPED_TILT = {
    "hold_79": {"hold": 79.0},                       # 97 → 79
    "hold_107": {"hold": 107.0},                     # 97 → 107 (stray digit)
    "level_103": {"level": 103.0},                   # 93.1 → 103
    "hold_93.2_level_93.1": {"hold": 93.2, "level": 93.1},   # hold typed as level
    "level_96.9": {"level": 96.9},                   # level ≈ hold
    "upper_98": {"upper": 98.0},                     # 112.2 → 98
    "level_70": {"level": 70.0, "lower": 41.5},
    "lower_14.5": {"lower": 14.5},                   # 41.5 → 14.5
    "level_above_hold": {"level": 95.0, "hold": 94.0},
    "upper_near_hold": {"hold": 104.0, "upper": 105.0, "level": 97.0},
}
SWAPPED_SHUTTLE = {
    "col1_78.3": {"1": 78.3},                        # 87.3 → 78.3
    "home_64_col2_63": {"home": 64.0, "2": 63.0},
    "home_100": {"home": 100.0},
    "col3_20_reject_19": {"3": 20.0, "reject": 19.0},
    "col0_153": {"0": 153.0},
    "col3_54": {"3": 54.0},                          # 45 → 54
    "col2_56.2": {"2": 56.2},                        # 65.2 → 56.2
    "home_too_close_to_col1": {"home": 83.0},        # inside its ±12° but < 5° from column 1
}
SWAPPED_ARM = {
    "pick_157": {"ARM_PICK": 157},                   # 175 → 157
    "drop_50": {"ARM_DROP": 50},                     # 05 → 50
    "park_9": {"ARM_PARK": 9},                       # 90 → 9
    "park_109": {"ARM_PARK": 109},
}


@pytest.mark.parametrize("case", list(SWAPPED_TILT))
def test_swapped_digit_tilt_rejected(case):
    _, problems = shuttle.validate_calibration({"tilt": SWAPPED_TILT[case]})
    assert problems, case


@pytest.mark.parametrize("case", list(SWAPPED_SHUTTLE))
def test_swapped_digit_shuttle_rejected(case):
    _, problems = shuttle.validate_calibration({"shuttle": SWAPPED_SHUTTLE[case]})
    assert problems, case


@pytest.mark.parametrize("case", list(SWAPPED_ARM))
def test_swapped_digit_arm_rejected(case):
    _, problems, _ = servos.validate_calibration({"pickup_arm": SWAPPED_ARM[case]})
    assert problems, case


def test_swapped_digit_file_refused_at_init_nothing_written():
    (shuttle._CALIBRATION_FILE).write_text(json.dumps({"tilt": {"hold": 93.2, "level": 93.1}}))
    writes = []
    orig = shuttle._write
    shuttle._write = lambda ch, a: (writes.append((ch, a)), orig(ch, a))
    try:
        with pytest.raises(shuttle.ShuttleConfigError) as ei:
            shuttle.init(assume_rest=True)
    finally:
        shuttle._write = orig
    assert "tilt.hold − tilt.level = 0.1° must be 2–8°" in str(ei.value)
    assert writes == []


def test_window_sizes():
    # audit 5: carriage ±12° (MJ-B), arm widened towards PARK only (MJ-A); tilt unchanged
    assert shuttle.SANITY_WINDOW_DEG == {"tilt": 8.0, "shuttle": 12.0}
    assert servos.SANITY_WINDOW_DEG == 10.0 and servos.SANITY_WINDOW_TOWARD_PARK_DEG == 20.0
    assert servos.ARM_SYMMETRY_MAX_DEG == 10.0
    assert shuttle.SHUTTLE_MIN_GAP_DEG == 5.0 and shuttle.SHUTTLE_PAIR_GAPS == ((3, 2, 12.0),)
    assert shuttle.TILT_GAPS == (("lower", "level", 30.0, None), ("level", "hold", 2.0, 8.0),
                                 ("hold", "upper", 8.0, None))
    assert servos.sanity_windows("ARM_PICK") == [(0.0, 25.0), (155.0, 180.0)]
    assert servos.sanity_windows("ARM_DROP") == [(0.0, 25.0), (155.0, 180.0)]
    assert servos.sanity_windows("ARM_PARK") == [(80.0, 100.0)]


# Valid calibrations: nominal, the CAD-derived geometric angles (φ + 90°), the
# documented example (docs/ASSEMBLY.md §16.4), the coupler residual (≤ 1.2°, all
# ch1 poses together) and a crank re-fit on a neighbouring spline tooth's
# half-way point (ch2, all poses together), plus per-pose trims.
VALID_SHUTTLE = {
    "nominal": {},
    "cad_geometric_level": {"tilt": {"level": 93.6, "hold": 97.0, "upper": 112.2, "lower": 41.5}},
    "assembly_md_example": {"tilt": {"hold": 97.0, "level": 93.1, "upper": 112.2, "lower": 41.5},
                            "shuttle": {"home": 75.5, "0": 178.0, "1": 87.3, "2": 65.2, "3": 45.0,
                                        "reject": 2.0},
                            "actuation_range": {"2": 270}},
    "coupler_plus_0.6": {"tilt": {k: v + 0.6 for k, v in shuttle.NOMINAL_TILT_ANGLES.items()}},
    "coupler_minus_0.6": {"tilt": {k: v - 0.6 for k, v in shuttle.NOMINAL_TILT_ANGLES.items()}},
    "coupler_plus_1.2": {"tilt": {k: v + 1.2 for k, v in shuttle.NOMINAL_TILT_ANGLES.items()}},
    "coupler_minus_1.2": {"tilt": {k: v - 1.2 for k, v in shuttle.NOMINAL_TILT_ANGLES.items()}},
    "level_preload_1.5": {"tilt": {"level": 92.1}},
    "tilt_trims": {"tilt": {"level": 94.5, "hold": 99.0, "upper": 118.0, "lower": 36.0}},
    "crank_plus_2": {"shuttle": {str(k): v + 2 for k, v in shuttle.NOMINAL_SHUTTLE_ANGLES.items()
                                 if k != 0}},
    "crank_minus_2": {"shuttle": {str(k): v - 2 for k, v in shuttle.NOMINAL_SHUTTLE_ANGLES.items()
                                  if k != "reject"}},
    "column_trims": {"shuttle": {"3": 41.0, "2": 69.0, "home": 76.5, "1": 84.0}},
}


@pytest.mark.parametrize("case", list(VALID_SHUTTLE))
def test_documented_calibrations_accepted(case):
    _, problems = shuttle.validate_calibration(VALID_SHUTTLE[case])
    assert problems == [], problems


@pytest.mark.parametrize("arm", [{}, {"ARM_PICK": 172, "ARM_DROP": 8, "ARM_PARK": 92},
                                 {"ARM_PICK": 5, "ARM_DROP": 175},          # mirrored servo
                                 {"ARM_PICK": 167.5, "ARM_DROP": 12.5, "ARM_PARK": 88},     # +10 % gain
                                 {"ARM_PICK": 172, "ARM_DROP": 9, "ARM_PARK": 86.5}])     # PARK jogged vertical
def test_arm_calibrations_accepted(arm):
    _, problems, _ = servos.validate_calibration({"pickup_arm": arm})
    assert problems == [], problems


def test_nominals_well_inside_windows_and_gaps():
    for k, n in shuttle.NOMINAL_TILT_ANGLES.items():
        assert shuttle.sanity_window("tilt", k) == (pytest.approx(n - 8), pytest.approx(n + 8))
    for k, n in shuttle.NOMINAL_SHUTTLE_ANGLES.items():
        lo, hi = shuttle.sanity_window("shuttle", k)
        assert (lo, hi) == (pytest.approx(max(0.0, n - 12)), pytest.approx(min(180.0, n + 12)))
    t = shuttle.NOMINAL_TILT_ANGLES
    for a, b, gmin, gmax in shuttle.TILT_GAPS:
        assert t[b] - t[a] >= gmin + 1.5 and (gmax is None or t[b] - t[a] <= gmax - 1.5)
    c, order = shuttle.NOMINAL_SHUTTLE_ANGLES, shuttle._SHUTTLE_ORDER
    assert all(c[b] - c[a] >= shuttle._shuttle_min_gap(a, b) + 5 for a, b in zip(order, order[1:]))
    for k, n in servos.NOMINAL_ARM.items():
        assert any(lo + 5 <= n <= hi - 5 for lo, hi in servos.sanity_windows(k)), k


def _section_value(section, key, v):
    return {section: {str(key): round(v, 6)}}


@pytest.mark.parametrize("section,key", [("tilt", k) for k in shuttle.NOMINAL_TILT_ANGLES]
                         + [("shuttle", k) for k in shuttle._SHUTTLE_ORDER])
def test_allowed_range_is_exactly_what_validation_accepts(section, key):
    nominal = (shuttle.NOMINAL_TILT_ANGLES if section == "tilt" else shuttle.NOMINAL_SHUTTLE_ANGLES)[key]
    lo, hi = shuttle.allowed_range(section, key)
    assert lo <= nominal <= hi
    for v in (lo, hi, (lo + hi) / 2):
        assert shuttle.validate_calibration(_section_value(section, key, v))[1] == [], v
    for v in (lo - 0.05, hi + 0.05):
        if 0.0 <= v <= 180.0:
            assert shuttle.validate_calibration(_section_value(section, key, v))[1], v


def test_allowed_range_follows_the_other_poses():
    cur = dict(shuttle.NOMINAL_TILT_ANGLES, level=91.0)
    assert shuttle.allowed_range("tilt", "hold", cur) == (pytest.approx(93.0), pytest.approx(99.0))
    cur = {**shuttle.NOMINAL_SHUTTLE_ANGLES, 1: 82.0}
    assert shuttle.allowed_range("shuttle", "home", cur)[1] == pytest.approx(77.0)


def test_calibrate_tool_jogs_inside_the_module_limits(cs, monkeypatch):
    """section_tilt / section_columns / section_arm hand jog() exactly the
    module's per-pose sanity window (audit 5 minor 3: no longer narrowed by
    the order / gap rules against the other poses — those are checked when
    saving)."""
    seen = {}
    monkeypatch.setattr(cs, "ask", lambda prompt="": "n")
    monkeypatch.setattr(time, "sleep", lambda s: None)

    def jog(title, *, lo, hi, **k):
        seen[title] = (lo, hi)
        return None
    monkeypatch.setattr(cs, "jog", jog)
    cs.init_base()
    cs.section_arm()
    cs.section_tilt()
    cs.section_columns()
    for pose in shuttle.NOMINAL_TILT_ANGLES:
        assert seen[f"tilt {pose}"] == pytest.approx(shuttle.sanity_window("tilt", pose)), pose
    for key in ("home", 0, 1, 2, 3, "reject"):
        lo, hi = shuttle.sanity_window("shuttle", key)
        lo, hi = max(lo, cs.CARRIAGE_LIMITS[0]), min(hi, cs.CARRIAGE_LIMITS[1])
        assert seen[f"carriage {key}"] == pytest.approx((lo, hi)), key
    assert seen["ARM_PICK"] == (155.0, 180.0) and seen["ARM_DROP"] == (0.0, 25.0)
    assert seen["ARM_PARK"] == (80.0, 100.0)
    for (lo, hi) in seen.values():
        assert hi - lo <= 25.0


def test_calibrate_window_pins_when_no_room(cs):
    assert cs.window(97.0, 180, (99.0, 98.0)) == (97.0, 97.0)
    assert cs.window(97.0, 180, (89.0, 105.0)) == (89.0, 105.0)


def test_calibrate_save_never_writes_swapped_value(cs):
    # audit 5 minor 3: a value inside its own window that breaks a rule between
    # poses is HELD (not written); unresolved at the end of the menu it is dropped
    assert cs.save_shuttle("tilt", "hold", 93.2) is True           # 0.1° above level 93.1: held
    assert cs._held["tilt"] == {"hold": 93.2} and not shuttle._CALIBRATION_FILE.exists()
    cs.finish_held("tilt")
    assert shuttle.TILT_ANGLES["hold"] == 97.0 and not shuttle._CALIBRATION_FILE.exists()
    assert cs.save_shuttle("shuttle", 1, 78.3) is True             # < 5° above home: held
    cs.finish_held("shuttle")
    assert shuttle.SHUTTLE_ANGLES[1] == 87.3 and not shuttle._CALIBRATION_FILE.exists()
    assert cs.save_arm("ARM_PICK", 157.0) is True                  # breaks the symmetry: held
    cs.finish_held("arm")
    assert servos.ARM_PICK == 175 and not servos._CALIBRATION_FILE.exists()
    assert cs.save_shuttle("shuttle", 1, 60.0) is False            # outside its own window: refused
    assert cs.save_arm("ARM_PICK", 150.0) is False


# ══ m1: --calibrate records the machine NOT clean (tool marker) ══════════════
def _calibrate_inputs(monkeypatch, interrupt_at=None):
    n = {"i": 0}

    def fake_input(prompt):
        n["i"] += 1
        if "Place the" in prompt:
            loadcell.mock_set_load(5.0)
        if "Remove the reference" in prompt:
            loadcell.mock_set_load(0.0)
        if interrupt_at is not None and n["i"] == interrupt_at:
            main._signals = 1
            main._on_signal()                     # 2nd signal → Shutdown
        return ""
    monkeypatch.setattr("builtins.input", fake_input)


def test_calibrate_interrupted_marks_unclean(monkeypatch, tmp_path):
    TS.setup_rig(monkeypatch, tmp_path)
    main._write_machine_state(clean=True, confirmed=False, reason="prev", rest_pose="home_level")
    _calibrate_inputs(monkeypatch, interrupt_at=2)        # nickel placed, then Ctrl-C twice
    with pytest.raises(main.Shutdown):
        try:
            main.calibrate_loadcell()
        finally:
            main.teardown()
    ms = main.read_machine_state()
    assert ms["clean"] is False and ms.get("rest_pose") is None
    assert ms["tool"] == main.CALIBRATE_TOOL_NAME and "main.py --calibrate" in ms["reason"]


def test_calibrate_completed_still_unclean(monkeypatch, tmp_path):
    TS.setup_rig(monkeypatch, tmp_path)
    main._write_machine_state(clean=True, confirmed=False, reason="prev", rest_pose="home_level")
    _calibrate_inputs(monkeypatch)
    main.calibrate_loadcell()
    main.teardown()
    ms = main.read_machine_state()
    assert ms["clean"] is False and ms["tool"] == "main.py --calibrate"
    assert main._marker_armed is False


def test_calibrate_marks_before_anything_moves(monkeypatch, tmp_path):
    TS.setup_rig(monkeypatch, tmp_path)
    main._write_machine_state(clean=True, confirmed=False, reason="prev", rest_pose="home_level")
    first = []
    orig = shuttle._write
    monkeypatch.setattr(shuttle, "_write", lambda ch, a: (
        first.append(main.read_machine_state()["clean"]) if not first else None, orig(ch, a)))
    _calibrate_inputs(monkeypatch)
    main.calibrate_loadcell()
    assert first == [False]


# ══ m2: unusable lock file → clean refusal, exit 78 ══════════════════════════
def test_lock_released_after_sigkill(tmp_path):
    lf = tmp_path / "sorter.lock"
    code = (f"import sys; sys.path.insert(0,{str(ROOT)!r}); from hardware import instance; "
            f"import time; fh=instance.acquire_lock({str(lf)!r},'x'); print('got', fh is not None, "
            "flush=True); time.sleep(60)")
    p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True,
                         env=dict(os.environ, MOCK_HARDWARE="1"))
    try:
        assert p.stdout.readline().strip() == "got True"
        assert instance.lock_held(lf) is True
        assert instance.acquire_lock(lf, "me") is None
    finally:
        p.send_signal(signal.SIGKILL)
        p.wait()
    fh = instance.acquire_lock(lf, "me")
    assert fh is not None and instance.lock_holder(lf).endswith(" me")
    fh.close()


@pytest.fixture
def readonly_lock(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root ignores file modes")
    lf = tmp_path / "sorter.lock"
    lf.write_text("0 root\n")
    os.chmod(lf, 0o444)
    yield lf
    os.chmod(lf, 0o644)


def test_acquire_lock_on_readonly_file_raises_clear_error(readonly_lock):
    with pytest.raises(instance.LockFileError) as ei:
        instance.acquire_lock(readonly_lock, "main.py")
    msg = str(ei.value)
    assert str(readonly_lock) in msg and "sudo chown -R" in msg and "never run" in msg
    assert instance.lock_held(readonly_lock) is False          # read-only open still answers


def test_main_refuses_unusable_lock_with_78(readonly_lock, monkeypatch, capsys):
    monkeypatch.setattr(main, "INSTANCE_LOCK_FILE", readonly_lock)
    with pytest.raises(SystemExit) as ei:
        main._claim_instance_or_exit()
    assert ei.value.code == 78
    err = capsys.readouterr().err
    assert str(readonly_lock) in err and "chown" in err and "refusing to start" in err


def test_unit_does_not_restart_on_78():
    unit = (ROOT / "scripts" / "riftbound-sorter.service").read_text()
    assert "RestartPreventExitStatus=78" in unit and instance.EX_CONFIG == 78


def test_main_refuses_unwritable_data_dir(tmp_path, monkeypatch, capsys):
    if os.geteuid() == 0:
        pytest.skip("root ignores file modes")
    d = tmp_path / "data"
    d.mkdir()
    os.chmod(d, 0o555)
    try:
        monkeypatch.setattr(main, "INSTANCE_LOCK_FILE", d / "sorter.lock")
        assert instance.data_dir_problems(d / "sorter.lock")
        with pytest.raises(SystemExit) as ei:
            main._claim_instance_or_exit()
        assert ei.value.code == 78
        assert f"sudo chown -R" in capsys.readouterr().err
    finally:
        os.chmod(d, 0o755)


def test_cli_with_unreadable_lock_exits_78(tmp_path, monkeypatch):
    if os.geteuid() == 0:
        pytest.skip("root ignores file modes")
    lf = tmp_path / "sorter.lock"
    lf.write_text("")
    os.chmod(lf, 0)
    try:
        monkeypatch.setattr(main, "INSTANCE_LOCK_FILE", lf)
        monkeypatch.setattr(sys, "argv", ["main.py", "--confirm-clear"])
        with pytest.raises(SystemExit) as ei:
            main.main()
        assert ei.value.code == 78
    finally:
        os.chmod(lf, 0o644)


def test_tools_exit_78_on_unusable_lock(cs, monkeypatch):
    if os.geteuid() == 0:
        pytest.skip("root ignores file modes")
    lf = instance.lock_file(True)
    lf.parent.mkdir(parents=True, exist_ok=True)
    lf.write_text("0 root\n")
    os.chmod(lf, 0o444)
    try:
        with pytest.raises(SystemExit) as ei:
            cs.claim_machine()
        assert ei.value.code == 78
        th = _load_script("test_hardware")
        with pytest.raises(SystemExit) as ei:
            th.claim_machine(True)
        assert ei.value.code == 78
        cc = _load_script("calibrate_camera")
        monkeypatch.setattr(sys, "argv", ["calibrate_camera.py"])
        with pytest.raises(SystemExit) as ei:
            cc.main()
        assert ei.value.code == 78
    finally:
        os.chmod(lf, 0o644)


def test_root_created_files_go_to_the_data_dir_owner(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(os, "chown", lambda p, u, g: calls.append((Path(p).name, u, g)))
    real_stat = Path.stat

    def fake_stat(self, *a, **k):
        st = real_stat(self, *a, **k)
        if self == tmp_path:
            return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, 1000, 1000,
                                   st.st_size, st.st_atime, st.st_mtime, st.st_ctime))
        return st
    monkeypatch.setattr(Path, "stat", fake_stat)
    fh = instance.acquire_lock(tmp_path / "sorter.lock", "tool")
    instance.write_state(tmp_path / "machine_state.json", clean=False, reason="x")
    fh.close()
    assert ("sorter.lock", 1000, 1000) in calls
    assert any(n.startswith(".machine_state.json.") and u == 1000 for n, u, g in calls)


# ══ every config error exits 78 in every tool (coordinator follow-up) ════════
BAD_MACHINE_JSON = {"servos": {"ARM_ACTUATION_RANGE": "x"}}


@pytest.mark.parametrize("tool", ["test_hardware.py", "calibrate_servos.py", "calibrate_camera.py"])
def test_tool_exits_78_on_bad_machine_json(tool, tmp_path):
    cfg = tmp_path / "machine.json"
    cfg.write_text(json.dumps(BAD_MACHINE_JSON))
    env = dict(os.environ, MOCK_HARDWARE="1", RIFTBOUND_MACHINE_CONFIG=str(cfg))
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / tool)], cwd=tmp_path, env=env,
                       capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    assert r.returncode == 78, (r.returncode, r.stdout[-500:], r.stderr[-2000:])
    assert "invalid machine config" in r.stderr


def test_calibrate_servos_unreadable_file_mid_session_is_78(cs):
    shuttle._CALIBRATION_FILE.write_text("{oops")
    with pytest.raises(SystemExit) as ei:
        cs.read_json(shuttle._CALIBRATION_FILE)
    assert ei.value.code == 78


# ══ m3: idle release of ch1 ONLY, and only with no card in the machine ═══════
def _at_rest(monkeypatch, tmp_path):
    TS.setup_rig(monkeypatch, tmp_path)
    assert main._pose_at_rest()


def test_idle_release_only_ch1(monkeypatch, tmp_path):
    _at_rest(monkeypatch, tmp_path)
    main._release_idle()
    assert shuttle.released(shuttle.CH_TILT) is True
    assert shuttle.released(shuttle.CH_SHUTTLE) is False and servos.arm_released() is False


@pytest.mark.parametrize("where", ["belt", "cradle", "cup"])
def test_idle_release_never_with_a_card(monkeypatch, tmp_path, where):
    _at_rest(monkeypatch, tmp_path)
    main._set_card_at(where)
    main._release_idle()
    assert not shuttle.released() and not servos.arm_released()


def test_reassert_writes_ch1_back_without_touching_the_arm(monkeypatch, tmp_path):
    _at_rest(monkeypatch, tmp_path)
    main._release_idle()
    log = []
    o_sw, o_aw = shuttle._write, servos._arm_write
    monkeypatch.setattr(shuttle, "_write", lambda ch, a: (log.append((ch, a)), o_sw(ch, a)))
    monkeypatch.setattr(servos, "_arm_write", lambda a: (log.append((0, a)), o_aw(a)))
    main._reassert_rest_pose()
    assert (shuttle.CH_TILT, shuttle.TILT_ANGLES["level"]) in log
    assert all(ch != 0 for ch, _ in log)                          # arm kept holding
    assert all(a == shuttle.SHUTTLE_ANGLES["home"] for ch, a in log if ch == shuttle.CH_SHUTTLE)
    assert not shuttle.released()


def test_teardown_still_releases_both_shuttle_channels(monkeypatch, tmp_path):
    _at_rest(monkeypatch, tmp_path)
    shuttle.release_channels()
    assert shuttle.released(shuttle.CH_TILT) and shuttle.released(shuttle.CH_SHUTTLE)


# ══ m4: a card held on the cup is never parked over the hopper rim ═══════════
@pytest.fixture
def held_card(monkeypatch):
    """Plain MOCK machine (real mock vacuum), arm moved to a pose, card on the
    cup, every carry to DROP failing (e.g. I2C)."""
    monkeypatch.setattr(time, "sleep", lambda s: None)
    vacuum.init()
    servos.init()
    servos.arm_park()
    shuttle.init()
    shuttle.home()

    def setup(angle):
        servos.move_arm_smooth(angle)
        vacuum.pump_on()
        main._set_card_at("cup")
        orig = servos.move_arm_smooth

        def flaky(target, *a, **k):
            if target == servos.ARM_DROP:
                raise OSError("I2C")
            return orig(target, *a, **k)
        monkeypatch.setattr(servos, "move_arm_smooth", flaky)
    return setup


@pytest.mark.parametrize("angle,zone", [(120.0, "rim"), (90.0, "rim"), (160.0, "rim"),
                                        (168.0, "stack"), (40.0, "belt"), (15.0, "belt")])
def test_failed_carry_keeps_the_arm_where_it_is(held_card, angle, zone):
    held_card(angle)
    main._make_safe()
    assert servos.arm_angle() == angle                     # NOT parked
    assert vacuum.pump_is_on() and main._card_at == "cup"  # still held
    assert main._held_card_landing()[0] == zone
    main._release_idle()
    assert not servos.arm_released() and not shuttle.released()


def test_card_near_pick_goes_back_on_the_stack(held_card):
    held_card(174.0)
    main._make_safe()
    assert main._card_at is None and not vacuum.pump_is_on()
    assert servos.arm_angle() == servos.ARM_PARK            # empty cup: parked as before


def test_landing_zones_follow_a_mirrored_arm(monkeypatch):
    monkeypatch.setattr(servos, "ARM_PICK", 5.0)
    monkeypatch.setattr(servos, "ARM_DROP", 175.0)
    assert main._held_card_landing(10.0)[0] == "stack"
    assert main._held_card_landing(150.0)[0] == "belt"
    assert main._held_card_landing(90.0)[0] == "rim"
    assert main._held_card_landing(None)[0] in ("unknown", "rim", "stack", "belt")


def test_cup_hold_limit_drops_from_the_kept_pose(held_card, monkeypatch):
    held_card(40.0)
    main._make_safe()
    main._set_state("needs_confirm", "x")
    monkeypatch.setattr(main, "_cup_hold_since", time.monotonic() - main.CUP_HOLD_MAX_S - 1)
    main._cup_hold_watch()
    assert not vacuum.pump_is_on()
    assert servos.arm_angle() == 40.0
    assert "flat onto the belt" in main._status["message"]
    assert main.CUP_HOLD_MAX_S == 600.0


def test_cup_hold_message_says_where_it_will_land(held_card):
    held_card(120.0)
    main._make_safe()
    main._set_state("needs_confirm", "x")
    main._cup_hold_watch()
    msg = main._status["message"]
    assert msg.startswith(main.CUP_HELD_MSG) and "hopper rim" in msg


def test_teardown_lets_go_before_the_arm_goes_limp(held_card, monkeypatch):
    held_card(40.0)
    order = []
    o_rel, o_deinit = vacuum.release, servos.deinit
    monkeypatch.setattr(vacuum, "release", lambda *a, **k: (order.append(("release",
                                                                         servos.arm_angle())),
                                                            o_rel(*a, **k)))
    monkeypatch.setattr(servos, "deinit", lambda: (order.append(("servos.deinit", None)), o_deinit()))
    main.teardown()
    assert order[0] == ("release", 40.0) and ("servos.deinit", None) in order
    assert order.index(("release", 40.0)) < order.index(("servos.deinit", None))


# ══ m6: bin counts fsynced like instance.write_state ═════════════════════════
def test_bin_count_write_is_fsynced(tmp_path, monkeypatch):
    events = []
    real_fsync, real_replace = os.fsync, os.replace
    monkeypatch.setattr(os, "fsync", lambda fd: (events.append(
        "fsync_dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "fsync_file"), real_fsync(fd))[1])
    monkeypatch.setattr(os, "replace", lambda a, b: (events.append("replace"), real_replace(a, b))[1])
    b = main.BinCounts(tmp_path / "c.json", tmp_path / "l.json", main.DEFAULT_BIN_LIMITS)
    events.clear()
    b.increment(4)
    assert events == ["fsync_file", "replace", "fsync_dir"]
    assert json.loads((tmp_path / "c.json").read_text())["counts"]["4"] == 1


# ══ m7: upper-floor cap 15, default 12 ═══════════════════════════════════════
def test_upper_floor_cap_15(tmp_path):
    assert all(main.BIN_LIMIT_MAX[b] == 15 for b in (4, 5, 6, 7))
    assert all(main.DEFAULT_BIN_LIMITS[b] == 12 for b in (4, 5, 6, 7))
    limits, problems = main.validate_bin_limits({"4": 15, "7": 15}, main.DEFAULT_BIN_LIMITS)
    assert problems == [] and limits[4] == 15
    _, problems = main.validate_bin_limits({"5": 16}, main.DEFAULT_BIN_LIMITS)
    assert problems and "5: 16 is outside 1..15" in problems[0]
    # the format example in the error message must itself be valid
    assert '{"0": 45, "4": 14}' in str(main.BinLimitsError(tmp_path / "x", ["p"]))


# ══ m9: relay inputs pulled up at boot via config.txt ════════════════════════
def test_config_txt_line_idempotent(tmp_path):
    ct = _load_script("config_txt_line")
    f = tmp_path / "config.txt"
    f.write_text("dtparam=audio=on\n[cm4]\notg_mode=1\n")
    line = "gpio=17,27=ip,pu"
    assert ct.ensure_line(f, line, "riftbound") is True
    text = f.read_text()
    assert text.endswith("\n[all]\n# riftbound\ngpio=17,27=ip,pu\n")
    assert text.startswith("dtparam=audio=on\n[cm4]\notg_mode=1\n")
    assert ct.ensure_line(f, line, "riftbound") is False
    assert f.read_text().count(line) == 1
    assert (tmp_path / "config.txt.riftbound.bak").read_text() == "dtparam=audio=on\n[cm4]\notg_mode=1\n"


def test_config_txt_line_not_fooled_by_filters_or_comments(tmp_path):
    ct = _load_script("config_txt_line")
    line = "gpio=17,27=ip,pu"
    assert ct.has_line(f"{line}\n[pi4]\nx=1\n", line)                 # before any filter
    assert ct.has_line(f"[pi4]\nx=1\n[all]\n{line}\n", line)
    assert not ct.has_line(f"[pi4]\n{line}\n", line)                   # only for one model
    assert not ct.has_line(f"# {line}\n", line)
    stub = tmp_path / "stub.txt"
    stub.write_text("DO NOT EDIT THIS FILE\n")
    real = tmp_path / "config.txt"
    real.write_text("")
    assert ct.find_config((stub, real)) == real
    assert ct.main([line, "--file", str(real)]) == 0 and line in real.read_text()


def test_setup_adds_the_pull_up_and_owns_data():
    sh = (ROOT / "scripts" / "setup.sh").read_text()
    assert 'config_txt_line.py" "gpio=17,27=ip,pu"' in sh
    assert 'sudo chown -R "$RUN_USER": cache data config' in sh
    r = subprocess.run(["bash", "-n", str(ROOT / "scripts" / "setup.sh")], capture_output=True)
    assert r.returncode == 0, r.stderr


def test_config_txt_line_stdlib_only():
    src = (ROOT / "scripts" / "config_txt_line.py").read_text()
    for mod in ("hardware", "main", "flask", "numpy"):
        assert f"import {mod}" not in src and f"from {mod}" not in src
