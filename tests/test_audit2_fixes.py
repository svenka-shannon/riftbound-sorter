"""
Tests for the second audit's findings (B-N1, M1-M10, minors), one block per item.

Run:
  uv run --python 3.11 --with pytest --with pillow --with numpy --with requests \
         --with flask --with imagehash pytest -q tests/
"""

import io
import json
import os
import re
import signal
import socket
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main
from hardware import (camera, card_detect, conveyor, elevator, loadcell, machine_config, servos,
                      shuttle, vacuum)
import test_audit2_sweep as TS
import fakegpio as G

ROOT = Path(__file__).resolve().parent.parent
AUTH = {"X-Auth-Token": "t"}


@pytest.fixture
def rig(monkeypatch, tmp_path):
    return TS.setup_rig(monkeypatch, tmp_path)


@pytest.fixture
def client(rig):
    from web.app import create_app
    app = create_app(token="t")
    app.testing = True
    return app.test_client()


# ══ B-N1: dependency pinning ═════════════════════════════════════════════════
APT_PROVIDED = ("numpy", "pillow", "scipy", "pywavelets")


def _lock_entries():
    text = (ROOT / "requirements.lock").read_text()
    entries = {}
    for block in re.split(r"\n(?=[a-z0-9])", text):
        m = re.match(r"([a-z0-9][a-z0-9._-]*)==([^\s\\]+)", block)
        if m:
            entries[m.group(1)] = (m.group(2), block.count("--hash=sha256:"))
    return entries


def test_lock_pins_blinka_below_10_with_hashes():
    e = _lock_entries()
    v = e["adafruit-blinka"][0]
    assert int(v.split(".")[0]) == 9, v                 # 10.x needs gpiod>=2.2.2,<3
    assert "gpiod" not in e
    for name, (ver, hashes) in e.items():
        assert hashes >= 1, f"{name} has no hash"
        assert re.fullmatch(r"[0-9][0-9a-z.]*", ver), (name, ver)
    for name in APT_PROVIDED:                           # never replace apt's numpy-ABI set
        assert name not in e, name
    for needed in ("adafruit-circuitpython-pca9685", "adafruit-circuitpython-motor", "flask",
                   "imagehash", "requests", "sysv-ipc", "adafruit-platformdetect"):
        assert needed in e, needed
    req = (ROOT / "requirements.txt").read_text()
    assert re.search(r"^adafruit-blinka>=9\.2,<10$", req, re.M)


def test_setup_installs_from_lock_and_checks_blinka():
    sh = (ROOT / "scripts" / "setup.sh").read_text()
    assert "pip install --no-deps --require-hashes -r requirements.lock" in sh
    assert "install -r requirements.txt" not in sh
    assert "import board, busio, adafruit_pca9685" in sh


# ══ M1: empty-cradle reference ═══════════════════════════════════════════════
def _stored():
    return json.loads(loadcell._CALIBRATION_FILE.read_text()) if loadcell._CALIBRATION_FILE.exists() else {}


def test_plain_and_unverified_tares_never_persist(monkeypatch):
    loadcell.mock_set_load(0.0)
    loadcell.tare()
    assert "empty_offset" not in _stored() and not loadcell.tare_anchored()
    loadcell.tare(anchored=False, persist=True)          # persist without anchor: ignored
    assert "empty_offset" not in _stored()
    loadcell.tare(anchored=True, persist=True)           # no calibration baseline: ignored
    assert "empty_offset" not in _stored()


def test_calibration_persists_and_anchors():
    loadcell.mock_set_load(0.0)
    loadcell.tare(calibration=True)
    d = _stored()
    assert d["empty_offset"] == d["calibrated_empty_offset"] and loadcell.tare_anchored()


def test_route_proven_tare_persists_only_in_an_anchored_chain(rig, monkeypatch):
    # rig = calibrated machine (anchored). Shift the zero a little (drift) → a
    # route-proven tare refreshes the stored reference.
    writes = []
    orig = loadcell._persist_empty_offset
    monkeypatch.setattr(loadcell, "_persist_empty_offset",
                        lambda off, calibration=False: writes.append(off) or orig(off, calibration))
    orig_raw = loadcell._mock_raw
    drift = 0.2 * loadcell.SCALE_FACTOR                   # 0.2 g of zero drift
    monkeypatch.setattr(loadcell, "_mock_raw", lambda: orig_raw() + drift)
    assert main.sort_one_card(TS.Eng()) == 2
    assert writes and loadcell.tare_anchored()
    assert _stored()["empty_offset"] == pytest.approx(0.2 * loadcell.SCALE_FACTOR)
    # Unanchored chain (e.g. confirmed start-up without a reference): the next
    # route-proven tare must NOT be stored.
    writes.clear()
    loadcell.tare()                                       # unanchored zero
    drift = 0.3 * loadcell.SCALE_FACTOR
    main.mark_running()
    shuttle.level()
    assert main.sort_one_card(TS.Eng()) == 2
    assert writes == [] and not loadcell.tare_anchored()


def test_reference_drift_beyond_limit_not_persisted(rig):
    cal = loadcell._cal_empty_offset
    far = cal + (loadcell.REFERENCE_MAX_DRIFT_G + 0.2) * loadcell.SCALE_FACTOR
    assert loadcell._persist_empty_offset(far) is False
    assert _stored()["empty_offset"] == cal


def test_negative_weight_is_a_fault_not_empty(rig):
    assert loadcell.is_empty(0.0) and loadcell.is_empty(-0.4)
    assert not loadcell.is_empty(-0.6) and loadcell.classify(-0.6) == "fault"
    loadcell.mock_set_load(-1.0)                          # something lifted / zero drift
    with pytest.raises(loadcell.LoadCellError, match="BELOW"):
        loadcell.read_grams()
    assert loadcell.read_grams_unchecked() == pytest.approx(-1.0)


def test_startup_below_reference_is_a_fault(rig):
    loadcell.mock_set_load(-1.5)
    with pytest.raises(main.LoadCellFault, match="BELOW"):
        main._startup_cradle_check(confirmed=True)


def test_confirmed_startup_still_checks_the_reference(rig):
    loadcell.mock_set_load(1.75)
    with pytest.raises(main.NeedsConfirm, match="card on cradle"):
        main._startup_cradle_check(confirmed=True)
    loadcell.mock_set_load(0.0)
    main._startup_cradle_check(confirmed=True)
    assert loadcell.tare_anchored()                       # anchored to the reference, not stored


def test_route_with_negative_reading_latches_and_stops(rig, monkeypatch):
    orig = loadcell._mock_raw

    def raw():
        v = orig()
        return v - 2.0 * loadcell.SCALE_FACTOR if shuttle.state()[0] not in (None, "home") else v
    monkeypatch.setattr(loadcell, "_mock_raw", raw)       # cradle reads -2 g after the tip
    assert main.run_sorter(engine=TS.Eng(), max_cycles=1) == "error"
    assert shuttle.jammed() and "BELOW" in main._status["message"]


# ══ M2: web state machine ════════════════════════════════════════════════════
def _post(c, url):
    return c.post(url, headers=AUTH).status_code


@pytest.mark.parametrize("state,expect", [
    # state:          pause resume stop confirm empty-all
    ("running",       (200, 409, 200, 409, 409)),
    ("starting",      (200, 409, 200, 409, 409)),
    ("paused",        (200, 200, 200, 409, 200)),
    ("stopped",       (409, 200, 409, 200, 200)),
    ("hopper_empty",  (409, 200, 409, 409, 200)),
    ("jam",           (409, 409, 409, 200, 200)),
    ("error",         (409, 409, 409, 200, 200)),
    ("needs_confirm", (409, 409, 409, 200, 200)),
])
def test_endpoint_gating_by_state(client, state, expect):
    got = []
    for url in ("/api/pause", "/api/resume", "/api/stop", "/api/confirm-clear",
                "/api/bins/empty-all"):
        main._control.update(pause=False, stop=False)
        main._set_state(state, "x")
        got.append(_post(client, url))
    assert tuple(got) == expect


def test_resume_cancels_pending_stop_while_running(client):
    main._set_state("running")
    assert _post(client, "/api/stop") == 200
    assert _post(client, "/api/resume") == 200 and main._control["stop"] is False


def test_confirm_refused_while_a_run_is_in_progress(client):
    main._set_state("stopped")
    with main._machine_active():
        assert _post(client, "/api/confirm-clear") == 409
    assert _post(client, "/api/confirm-clear") == 200


def test_operate_sets_starting_before_prepare(monkeypatch, tmp_path):
    seen = {}

    def prep(confirmed):
        seen["state"] = main._status["state"]
        main._running = False
        raise main.StopRequested("x")
    monkeypatch.setattr(main, "prepare_machine", prep)
    main._write_machine_state(clean=True, confirmed=False, reason="", rest_pose="home_level")
    main._operate(False)
    assert seen["state"] == "starting"


# ══ M3: bin-full wait honours pause / stop; never moves while paused ═════════
def test_bin_full_wait_stop_returns_without_moving(rig, monkeypatch):
    main._bins.limits[2] = 0
    n = {"i": 0}
    orig = main._bins.is_full

    def is_full(b):
        n["i"] += 1
        if n["i"] == 3:
            main.request_stop()
        return orig(b)
    monkeypatch.setattr(main._bins, "is_full", is_full)
    assert main.run_sorter(engine=TS.Eng(), max_cycles=1) == "stopped"
    assert shuttle.state()[:2] == ("home", "hold") and main._bins.count(2) == 0


def test_bin_emptied_while_operator_paused_needs_resume(rig, monkeypatch):
    main._bins.limits[2] = 0
    moved = []
    orig_w = shuttle._write
    phase = {"p": "before"}

    def w(ch, a):
        if phase["p"] == "paused" and ch == shuttle.CH_SHUTTLE:
            moved.append(a)
        orig_w(ch, a)
    monkeypatch.setattr(shuttle, "_write", w)
    polls = {"n": 0}
    orig_full = main._bins.is_full

    def is_full(b):
        polls["n"] += 1
        if polls["n"] == 2:
            main.request_pause()                          # operator presses Pause
            phase["p"] = "paused"
        if polls["n"] == 4:
            main._bins.limits[2] = 40                     # ... then empties the bin
        if polls["n"] == 12:
            assert main._status["state"] == "paused" and "press Resume" in main._status["message"]
            assert moved == []                            # nothing moved while paused
            phase["p"] = "resumed"
            main.request_resume()
        return orig_full(b)
    monkeypatch.setattr(main._bins, "is_full", is_full)
    assert main.run_sorter(engine=TS.Eng(), max_cycles=1) == "stopped"
    assert polls["n"] >= 12 and main._bins.count(2) == 1  # routed only after Resume


# ══ M4: HX711 plausibility + set_offset slot ═════════════════════════════════
def test_implausible_readings_rejected(rig, monkeypatch):
    vals = iter([500.0] * 3 + [1.75] * 7)                  # 500 g: no real load on a 50 g cell
    monkeypatch.setattr(loadcell, "_mock_raw", lambda: next(vals) * loadcell.SCALE_FACTOR)
    assert loadcell.read_grams() == pytest.approx(1.75)
    monkeypatch.setattr(loadcell, "_mock_raw", lambda: 500.0 * loadcell.SCALE_FACTOR)
    with pytest.raises(loadcell.LoadCellError):
        loadcell.read_grams()


def test_init_sets_offset_in_channel_a_gain_128(monkeypatch):
    rpi = types.ModuleType("RPi"); rpi.GPIO = G
    monkeypatch.setitem(sys.modules, "RPi", rpi); monkeypatch.setitem(sys.modules, "RPi.GPIO", G)
    G.reset(); G.input_value[loadcell.DOUT_PIN] = 0
    monkeypatch.setattr(time, "sleep", lambda s: None)
    sys.modules.pop("hardware.vendor.hx711", None)
    monkeypatch.setattr(loadcell, "_MOCK", False)
    loadcell._CALIBRATION_FILE.write_text(json.dumps({"empty_offset": 123456}))
    loadcell.init()
    try:
        assert loadcell._hx._offset_A_128 == 123456
    finally:
        loadcell._hx = None


def test_vendored_read_timeout_fixed():
    src = (ROOT / "hardware" / "vendor" / "hx711.py").read_text()
    assert "if ready_counter == 50" not in src and "RIFTBOUND LOCAL EDIT" in src


# ══ M5: camera timeouts + systemd watchdog ═══════════════════════════════════
class _FakeCam:
    def __init__(self, exc=None):
        self.calls, self.exc = [], exc

    def capture_array(self, name="main", wait=None, signal_function=None):
        self.calls.append((name, wait))
        if self.exc:
            raise self.exc
        return np.zeros((270, 320), np.uint8)


def test_lores_capture_uses_a_timeout(monkeypatch):
    cam = _FakeCam()
    monkeypatch.setattr(camera, "_MOCK", False)
    monkeypatch.setattr(camera, "_cam", cam)
    camera.capture_lores_luma()
    assert cam.calls == [("lores", camera.LORES_TIMEOUT_S)] and camera.LORES_TIMEOUT_S == 0.2
    monkeypatch.setattr(camera, "_cam", _FakeCam(TimeoutError("timed out")))
    with pytest.raises(camera.CameraTimeout):
        camera.capture_lores_luma()


def test_camera_timeout_brakes_and_is_a_camera_fault(monkeypatch):
    ev = []

    def grab():
        raise camera.CameraTimeout("no lores frame")
    src = card_detect.CameraSource()
    monkeypatch.setattr(src, "grab", grab)
    r = card_detect.centre_card(np.zeros((180, 320), np.uint8), lambda: ev.append("run"),
                                lambda: ev.append("brake"), lambda: ev.append("stop"), source=src)
    assert r.reason == "camera" and r.jam and ev == ["run", "brake"]


def test_camera_fault_stops_the_machine(rig, monkeypatch):
    monkeypatch.setattr(card_detect, "centre_card", lambda *a, **k: card_detect.CentreResult(
        False, "camera", None, None, 3, 0.1))
    assert main.run_sorter(engine=TS.Eng(), max_cycles=1) == "error"
    assert "camera" in main._status["message"] and main._card_at == "belt"


def test_sd_notify_watchdog_ping(monkeypatch):
    d = tempfile.mkdtemp(prefix="rbn", dir="/tmp")
    path = os.path.join(d, "n.sock")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    srv.bind(path)
    srv.settimeout(2)
    try:
        monkeypatch.setenv("NOTIFY_SOCKET", path)
        monkeypatch.setattr(main, "_last_ping", 0.0)
        main._beat()
        assert srv.recv(64) == b"WATCHDOG=1"
        main._beat()                                       # rate-limited: no second datagram
        srv.settimeout(0.2)
        with pytest.raises(socket.timeout):
            srv.recv(64)
    finally:
        srv.close()
        os.unlink(path)
        os.rmdir(d)
    monkeypatch.delenv("NOTIFY_SOCKET")
    assert main._sd_notify("WATCHDOG=1") is False


def test_service_unit_has_watchdog_and_safe_outputs():
    unit = (ROOT / "scripts" / "riftbound-sorter.service").read_text()
    assert re.search(r"^WatchdogSec=\d+", unit, re.M)
    assert re.search(r"^NotifyAccess=main$", unit, re.M)
    assert re.search(r"^ExecStopPost=\+/usr/bin/python3 /opt/riftbound-sorter/scripts/safe_outputs.py$",
                     unit, re.M)
    assert re.search(r"^RestartPreventExitStatus=78$", unit, re.M)


# ══ M6: machine config schema ════════════════════════════════════════════════
def test_example_config_validates_and_matches_defaults():
    ex = json.loads((ROOT / "config" / "machine.example.json").read_text())
    cfg, problems = machine_config.validate(ex)
    assert problems == []
    assert set(cfg) == set(machine_config.SCHEMA)
    for sec in cfg:
        assert set(cfg[sec]) == set(machine_config.SCHEMA[sec]), sec
    mods = {"card_detect": card_detect, "camera": camera, "sort": main, "elevator": elevator,
            "servos": servos}
    for sec, mod in mods.items():
        for k, v in cfg[sec].items():
            cur = getattr(mod, k)
            assert (cur == pytest.approx(v)) if isinstance(v, float) else cur == v, (sec, k)


@pytest.mark.parametrize("data,bad", [
    ({"card_detect": {"BELT_SPEED_MM_S": 0}}, "card_detect.BELT_SPEED_MM_S"),
    ({"card_detect": {"BELT_SPEED_MM_S": float("nan")}}, "card_detect.BELT_SPEED_MM_S"),
    ({"card_detect": {"BELT_SPEED_MM_S": float("inf")}}, "card_detect.BELT_SPEED_MM_S"),
    ({"card_detect": {"BELT_SPEED_MM_S": "150"}}, "card_detect.BELT_SPEED_MM_S"),
    ({"card_detect": {"BELT_SPEED_MM_S": True}}, "card_detect.BELT_SPEED_MM_S"),
    ({"card_detect": {"TRAVEL_SIGN": 0}}, "card_detect.TRAVEL_SIGN"),
    ({"card_detect": {"PIXEL_DIFF": 30.5}}, "card_detect.PIXEL_DIFF"),
    ({"camera": {"LOCK_AE_AWB": "false"}}, "camera.LOCK_AE_AWB"),
    ({"camera": {"LOCK_AE_AWB": 0}}, "camera.LOCK_AE_AWB"),
    ({"camera": {"AF_MODE": "auto"}}, "camera.AF_MODE"),
    ({"camera": {"COLOUR_GAINS": [1.5]}}, "camera.COLOUR_GAINS"),
    ({"camera": {"CARD_ROTATE": 45}}, "camera.CARD_ROTATE"),
    ({"sort": {"EXIT_MAX_S": None}}, "sort.EXIT_MAX_S"),
    ({"sort": {"SEAL_S": -5}}, "sort.SEAL_S"),
    ({"sort": {"EXIT_MIN_S": 2.0, "EXIT_MAX_S": 1.0}}, "sort.EXIT_MIN_S"),
    ({"elevator": {"TOP_SWITCH_NC": "yes"}}, "elevator.TOP_SWITCH_NC"),
    ({"servos": {"ARM_ACTUATION_RANGE": 200}}, "servos.ARM_ACTUATION_RANGE"),
    ({"card_detect": [1, 2]}, "card_detect: must be a JSON object"),
    ({"card_detect": {"BELT_SPEED_MMS": 90}}, "card_detect.BELT_SPEED_MMS: unknown key"),
    ({"cardetect": {}}, "cardetect: unknown section"),
])
def test_schema_rejects(data, bad):
    _, problems = machine_config.validate(data)
    assert any(bad in p for p in problems), problems


def test_schema_accepts_and_normalises():
    cfg, problems = machine_config.validate({
        "_comment": "x", "card_detect": {"_note": 1, "BELT_SPEED_MM_S": 120, "TRAVEL_SIGN": -1},
        "camera": {"LOCK_AE_AWB": False, "EXPOSURE_TIME_US": None, "COLOUR_GAINS": [1.5, 2]},
        "elevator": {"TOP_SWITCH_NC": False}})
    assert problems == []
    assert cfg["card_detect"] == {"BELT_SPEED_MM_S": 120.0, "TRAVEL_SIGN": -1}
    assert cfg["camera"]["LOCK_AE_AWB"] is False and cfg["camera"]["COLOUR_GAINS"] == [1.5, 2.0]


def test_load_raises_listing_every_bad_key(tmp_path, monkeypatch):
    f = tmp_path / "machine.json"
    f.write_text(json.dumps({"card_detect": {"BELT_SPEED_MM_S": 0, "TRAVEL_SIGN": 0}}))
    monkeypatch.setattr(machine_config, "CONFIG_FILE", f)
    monkeypatch.setattr(machine_config, "_cache", None)
    with pytest.raises(machine_config.MachineConfigError) as ei:
        machine_config.load()
    assert len(ei.value.problems) == 2
    f.write_text("{oops")
    with pytest.raises(machine_config.MachineConfigError, match="not valid JSON"):
        machine_config.load()
    monkeypatch.setattr(machine_config, "_cache", None)


# ══ M7: nothing on ch0-ch2 moves before confirmation after an unclean stop ═══
def _spy_servo_writes(monkeypatch):
    log = []
    o_sw, o_aw = shuttle._write, servos._arm_write
    monkeypatch.setattr(shuttle, "_write", lambda ch, a: (log.append((ch, a)), o_sw(ch, a)))
    monkeypatch.setattr(servos, "_arm_write", lambda a: (log.append((0, a)), o_aw(a)))
    return log


def test_unclean_start_commands_no_servo_until_confirmed(monkeypatch):
    log = _spy_servo_writes(monkeypatch)
    main.init_hardware(assume_rest=False)
    assert log == [] and servos.arm_angle() is None and not shuttle.pose_known()
    main._make_safe()                                     # e.g. after a NeedsConfirm: still nothing
    assert log == []
    with pytest.raises(main.NeedsConfirm, match="pose not known"):
        main.prepare_machine(confirmed=False)
    assert log == []
    main.prepare_machine(confirmed=True)                  # operator confirmed: now it moves
    assert log and shuttle.state()[:2] == ("home", "level")
    assert servos.arm_angle() == servos.ARM_PARK


def test_clean_start_reasserts_rest_once_then_ramps(monkeypatch):
    log = _spy_servo_writes(monkeypatch)
    main.init_hardware(assume_rest=True)
    assert sorted(ch for ch, _ in log) == [shuttle.CH_TILT, shuttle.CH_SHUTTLE]   # one write each
    assert servos.arm_angle() == servos.ARM_PARK and shuttle.at_rest()
    log.clear()
    shuttle.hold()                                        # ramps from level
    tilts = [a for ch, a in log if ch == shuttle.CH_TILT]
    assert len(tilts) > 3 and abs(tilts[0] - shuttle.TILT_ANGLES["level"]) < 1.0


def test_shuttle_init_never_homes():
    shuttle.init()
    assert shuttle.state()[:2] == (None, None) and not shuttle.pose_known()


def test_teardown_pose_unclean_unless_arm_parked(rig):
    main.mark_running()
    servos.move_arm_smooth(servos.ARM_PARK + 20)
    main.teardown()
    ms = main.read_machine_state()
    assert ms["clean"] is True and ms["rest_pose"] == "home_level"   # parked by teardown
    main._tearing_down = False
    servos._arm_angle = None                              # arm pose lost (never commanded)
    clean, reason = main._assess_clean()
    assert not clean and "arm" in reason


# ══ M8: elevator top / bottom switch faults ══════════════════════════════════
def test_raise_after_first_is_capped_and_stops_on_missing_switch(monkeypatch):
    monkeypatch.setattr(elevator, "TOP_SWITCH_NC", False)       # NO wiring: broken wire = never pressed
    elevator.init()
    elevator.mock_set_cards(150)
    assert elevator.home()
    assert elevator.raise_to_pick() is True                       # first raise: uncapped
    start = elevator.position_mm()
    elevator._mock_wire_broken["top"] = True
    elevator.mock_set_cards(149)
    with pytest.raises(elevator.ElevatorError, match="top switch not detected"):
        elevator.raise_to_pick()
    assert elevator.position_mm() - start <= elevator.RAISE_CAP_MM + 0.01


def test_nc_top_switch_broken_wire_reads_pressed():
    elevator._mock_wire_broken["top"] = True
    assert elevator.TOP_SWITCH_NC is True
    assert elevator._top_pressed() is True                       # floor never rises into the arm


def test_nc_bottom_switch_broken_wire_fails_home():
    elevator.init()
    elevator._mock_wire_broken["bottom"] = True
    with pytest.raises(elevator.ElevatorError, match="bottom"):
        elevator.home()


def test_pressed_levels_for_nc_and_no():
    assert elevator.pressed_level(True) == 1 and elevator.pressed_level(False) == 0


def test_hopper_empty_still_detected_with_the_cap():
    elevator.init()
    elevator.mock_set_cards(2)
    assert elevator.home()
    assert elevator.raise_to_pick()
    for _ in range(2):
        elevator.mock_set_cards(elevator._mock_cards - 1)
        r = elevator.raise_to_pick()
    assert r is False                                              # empty → top limit, not an error


def test_top_switch_fault_stops_the_sorter(rig, monkeypatch):
    monkeypatch.setattr(elevator, "TOP_SWITCH_NC", False)
    elevator._raised_since_home = True
    elevator._mock_wire_broken["top"] = True
    assert main.run_sorter(engine=TS.Eng(), max_cycles=1) == "error"
    assert "top switch not detected" in main._status["message"]


def test_real_gpio_switch_levels(monkeypatch):
    monkeypatch.setattr(elevator, "_MOCK", False)
    monkeypatch.setattr(elevator, "GPIO", G, raising=False)
    G.reset()
    G.input_value[elevator.TOP_SWITCH_PIN] = 1
    assert elevator._top_pressed() is True                         # NC: open contact = HIGH = pressed
    monkeypatch.setattr(elevator, "TOP_SWITCH_NC", False)
    assert elevator._top_pressed() is False


# ══ M9: safe outputs after the process dies ══════════════════════════════════
def _load_script(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_safe_outputs_levels_match_the_drivers():
    so = _load_script("safe_outputs")
    off = lambda active_low: 1 if active_low else 0
    assert so.SAFE_LEVELS[vacuum.RELAY_PIN] == off(vacuum.RELAY_ACTIVE_LOW)
    assert so.SAFE_LEVELS[vacuum.VENT_PIN] == off(vacuum.VENT_ACTIVE_LOW)
    for p in (conveyor.MOTOR_A_FWD, conveyor.MOTOR_A_REV, conveyor.MOTOR_B_FWD, conveyor.MOTOR_B_REV,
              *elevator.STEPPER_PINS):
        assert so.SAFE_LEVELS[p] == 0
    assert set(so.ORDER) == set(so.SAFE_LEVELS) and so.ORDER[0] == vacuum.RELAY_PIN
    cmds = so.gpio_commands("pinctrl")
    assert cmds[0] == ["pinctrl", "set", "17", "op", "dh"]
    assert ["pinctrl", "set", "23", "op", "dl"] in cmds
    assert so.pca_writes() == [bytes([0xFD, 0x10]), bytes([0x00, servos.PCA_SLEEP])]
    assert so.main(["--dry-run"]) == 0


def test_safe_outputs_never_imports_the_project():
    src = (ROOT / "scripts" / "safe_outputs.py").read_text()
    assert "from hardware" not in src and "import main" not in src


def test_cmdline_param_idempotent(tmp_path):
    cp = _load_script("cmdline_param")
    f = tmp_path / "cmdline.txt"
    f.write_text("console=serial0,115200 root=PARTUUID=abc rootwait quiet\n")
    param = "pinctrl_bcm2835.persist_gpio_outputs=0"
    assert cp.ensure_param(f, param) is True
    assert cp.ensure_param(f, param) is False
    text = f.read_text()
    assert text.count("persist_gpio_outputs") == 1 and text.endswith(param + "\n")
    assert "\n" not in text[:-1] and text.startswith("console=serial0,115200 root=PARTUUID=abc")
    f.write_text(text.replace("=0", "=1"))
    assert cp.ensure_param(f, param) is True and "persist_gpio_outputs=0" in f.read_text()
    assert (tmp_path / "cmdline.txt.riftbound.bak").exists()
    stub = tmp_path / "stub.txt"
    stub.write_text("DO NOT EDIT THIS FILE\n\nThe file you are looking for has moved\n")
    assert cp.find_cmdline((stub, f)) == f


def test_setup_sets_the_kernel_param():
    sh = (ROOT / "scripts" / "setup.sh").read_text()
    assert "cmdline_param.py\" pinctrl_bcm2835.persist_gpio_outputs=0" in sh


# ══ M10: identification ══════════════════════════════════════════════════════
def _jpeg(seed):
    rng = np.random.default_rng(seed)
    img = Image.fromarray((rng.random((64, 48, 3)) * 255).astype("uint8")).resize((300, 420))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue(), img


def _flip(h, n, start=0):
    import imagehash
    arr = h.hash.copy().flatten()
    arr[start:start + n] = ~arr[start:start + n]
    return imagehash.ImageHash(arr.reshape(h.hash.shape))


@pytest.fixture
def idm(monkeypatch):
    from vision import identify as m
    for k in ("MIN_CONF", "MIN_MARGIN_BITS", "FALLBACK", "FALLBACK_MIN_PHASH_CONF",
              "MAX_MISSING_FRACTION", "_hash_db", "_hash_db_ahash", "_hash_db_dhash", "_card_names"):
        monkeypatch.setattr(m, k, getattr(m, k))
    monkeypatch.setattr(m, "HASH_DB_FILE", Path(tempfile.mkdtemp()) / "hash_db.json")
    return m


def _hashes(m, jpeg):
    import imagehash
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    return (imagehash.phash(img, hash_size=m.HASH_SIZE), imagehash.average_hash(img, hash_size=m.HASH_SIZE),
            imagehash.dhash(img, hash_size=m.HASH_SIZE))


def test_ambiguous_phash_rejected_even_if_fallbacks_agree(idm):
    jpeg, _ = _jpeg(1)
    ph, ah, dh = _hashes(idm, jpeg)
    idm._hash_db = {"a": str(ph), "b": str(_flip(ph, 4))}            # pHash ambiguous
    idm._hash_db_ahash = {"a": str(ah), "b": str(_flip(ah, 120))}     # ahash: clearly "a"
    idm._hash_db_dhash = {"a": str(dh), "b": str(_flip(dh, 120))}
    r = idm.identify_with_details(jpeg)
    assert r["card_id"] is None and r["ambiguous"] and r["method"] == "phash"


def test_low_phash_needs_all_three_methods_to_agree(idm):
    jpeg, _ = _jpeg(2)
    ph, ah, dh = _hashes(idm, jpeg)
    weak = _flip(ph, 60)                                  # conf 0.766: below MIN_CONF 0.80, above 0.70
    idm._hash_db = {"a": str(weak), "b": str(_flip(ph, 120, 100))}
    idm._hash_db_ahash = {"a": str(ah), "b": str(_flip(ah, 120))}
    idm._hash_db_dhash = {"a": str(dh), "b": str(_flip(dh, 120))}
    r = idm.identify_with_details(jpeg)
    assert r["card_id"] == "a" and r["method"] == "phash+ahash+dhash"
    # dhash points at another card → disagreement → reject
    idm._hash_db_dhash = {"a": str(_flip(dh, 120)), "b": str(dh)}
    assert idm.identify_with_details(jpeg)["card_id"] is None
    # fallback switched off → reject
    idm._hash_db_dhash = {"a": str(dh), "b": str(_flip(dh, 120))}
    idm.FALLBACK = False
    assert idm.identify_with_details(jpeg)["card_id"] is None


def test_weaker_hash_can_never_override_phash(idm):
    jpeg, _ = _jpeg(3)
    ph, ah, dh = _hashes(idm, jpeg)
    idm._hash_db = {"a": str(_flip(ph, 60)), "b": str(_flip(ph, 120, 100))}   # pHash leans "a"
    idm._hash_db_ahash = {"b": str(ah), "a": str(_flip(ah, 120))}             # ahash says "b"
    idm._hash_db_dhash = {"b": str(dh), "a": str(_flip(dh, 120))}
    assert idm.identify_with_details(jpeg)["card_id"] is None


def test_build_hash_db_reports_missing(idm, monkeypatch):
    jpeg, img = _jpeg(4)

    def dl(cid, url, name):
        if cid == "bad":
            raise OSError("404")
        return (cid, *[str(h) for h in _hashes(idm, jpeg)], name)
    monkeypatch.setattr(idm, "_download_and_hash", dl)
    cards = {"a": {"image_url": "u", "name": "A"}, "bad": {"image_url": "u2"}, "noimg": {}}
    r = idm.build_hash_db(cards, force=True)
    assert r["missing"] == ["bad", "noimg"] and r["no_image"] == ["noimg"]
    assert r["total"] == 3 and r["hashed"] == 1 and r["ok"] is False
    idm.MAX_MISSING_FRACTION = 0.7
    assert idm.completeness(cards)["ok"] is True


def test_sorting_refused_while_hash_db_incomplete(monkeypatch):
    reports = iter([{"total": 100, "hashed": 90, "missing": list(range(10)), "no_image": [],
                     "missing_fraction": 0.1, "ok": False},
                    {"total": 100, "hashed": 100, "missing": [], "no_image": [],
                     "missing_fraction": 0.0, "ok": True}])
    states = []
    monkeypatch.setattr(main, "build_hash_db", lambda cards, force=False, progress=None: next(reports))
    monkeypatch.setattr(main, "_wait_interruptible", lambda s: states.append(main._status["state"]))
    assert main._ensure_hash_db({}, dry_run=False) is True
    assert states == ["error"]


# ══ minors ═══════════════════════════════════════════════════════════════════
def test_carry_retries_after_an_error_and_keeps_pump_on_if_it_cannot(rig, monkeypatch):
    main._set_card_at("cup")
    servos.move_arm_smooth(100)
    calls = {"n": 0}
    orig = servos.move_arm_smooth

    def flaky(target, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("I2C")
        orig(target, *a, **k)
    monkeypatch.setattr(servos, "move_arm_smooth", flaky)
    main._make_safe()
    assert main._card_at == "belt" and servos.arm_angle() == servos.ARM_PARK
    # an arm that never gets there: card stays held (pump ON), never released mid-arc
    main._set_card_at("cup")
    rig.pump = True
    monkeypatch.setattr(servos, "move_arm_smooth", lambda *a, **k: (_ for _ in ()).throw(OSError("I2C")))
    main._make_safe()
    assert main._card_at == "cup" and rig.pump is True and not rig.violations


def test_sighup_handled_like_sigterm(monkeypatch):
    seen = {}
    monkeypatch.setattr(main, "_main", lambda args: seen.update(
        {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}))
    monkeypatch.setattr(sys, "argv", ["main.py", "--dry-run"])
    old = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        main.main()
    finally:
        for s, h in old.items():
            signal.signal(s, h)
        if main._instance_lock_fh:
            main._instance_lock_fh.close()
            main._instance_lock_fh = None
    assert all(h is main._on_signal for h in seen.values())


def test_resume_click_while_halting_is_not_lost():
    main._set_state("stopped")
    main.request_resume()                                 # clicked before the wait loop starts
    assert main._await_operator(needs_confirm=False) is True
    assert not main._resume_event.is_set()


def test_cli_empty_bin_goes_through_the_running_sorter(monkeypatch, capsys):
    import fcntl
    main._bins.increment(3)
    calls = []
    monkeypatch.setattr(main, "_web_post", lambda path: calls.append(path) or (
        409, {"error": "machine is running: pause or stop it"}))
    main.INSTANCE_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(main.INSTANCE_LOCK_FILE, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)                    # a sorter process is running
        assert main.sorter_running()
        assert main.cli_empty_bins([3], False) == 1
        assert main.cli_confirm_clear() == 1
    assert calls == ["/api/bins/3/empty", "/api/confirm-clear"]
    assert main._bins.count(3) == 1 and "refused" in capsys.readouterr().out
    assert not main.sorter_running()                      # no sorter: direct reset
    assert main.cli_empty_bins([3], False) == 0 and main._bins.count(3) == 0
    assert main.cli_empty_bins([8], False) == 2


def test_web_token_not_printed_on_generation(capsys):
    tok = main.load_or_create_web_token()
    out = capsys.readouterr().out
    assert tok not in out and "--web-token" in out


def test_vacuum_docstring_corrected():
    doc = vacuum.__doc__
    assert "§14.2" in doc and "§3d" not in doc
    assert "persist_gpio_outputs" in doc and "flyback" in doc.lower()
    assert "pigpio" not in conveyor.__doc__.replace("no pigpio", "")
