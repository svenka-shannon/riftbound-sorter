"""
Targeted tests from the second audit (/tmp/rb_audit2/tests/test_targeted.py),
ported. Where the audit's scratch test encoded the OLD behaviour as its
expectation, the assertion now states the fixed behaviour (noted per test).
"""

import json
import os
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main
from hardware import card_detect, elevator, loadcell, servos, shuttle
import test_audit2_sweep as TS
import fakegpio as G

ROOT = Path(__file__).resolve().parent.parent
_real_sleep = time.sleep


def rig(monkeypatch, tmp_path):
    return TS.setup_rig(monkeypatch, tmp_path)


def _client():
    from web.app import create_app
    app = create_app(token="t")
    app.testing = True
    return app.test_client()


AUTH = {"X-Auth-Token": "t"}


# ── minor: _secure_cup — exception mid-arc, then a stop signal during the carry ──
def test_exception_then_signal_during_secure_cup_never_drops_card_mid_arc(monkeypatch, tmp_path):
    rec = rig(monkeypatch, tmp_path)
    state = {"raised": False, "sig": False}
    inner = servos._arm_write

    def aw(a):
        if main._card_at == "cup" and not state["raised"] and a < 120:
            state["raised"] = True
            main._on_signal()                      # operator: Ctrl-C (finish card)
            raise OSError("I2C remote I/O error")  # transient PCA9685 error mid-arc
        if state["raised"] and not state["sig"] and a < 100:
            state["sig"] = True
            main._on_signal()                      # Ctrl-C again (stop now) DURING the carry
        inner(a)
    monkeypatch.setattr(servos, "_arm_write", aw)
    with pytest.raises(main.Shutdown):             # the deferred second signal, after the carry
        main.sort_one_card(TS.Eng())
    assert state["sig"], "second signal never delivered during the carry"
    assert not rec.violations
    assert main._card_at == "belt" and not rec.pump


# ── M2/M1: web stop during a bin-full pause, then 'Machine clear' with the card held ──
def test_stop_during_binfull_then_confirm_does_not_tare_card_away(monkeypatch, tmp_path):
    """Audit: the confirmed start-up tared the held card away (and its weak
    assertion passed because the stored reference had been overwritten too).
    Now: confirmed start-up still compares with the stored reference."""
    rig(monkeypatch, tmp_path)
    c = _client()
    main._bins.limits[2] = 0
    main.mark_running()
    polls = {"n": 0, "stop": None}
    orig_full = main._bins.is_full

    def is_full(b):
        polls["n"] += 1
        if polls["n"] == 3:                        # while paused on the full bin
            polls["stop"] = c.post("/api/stop", headers=AUTH).status_code
        return orig_full(b)
    monkeypatch.setattr(main._bins, "is_full", is_full)
    assert main.run_sorter(engine=TS.Eng(), max_cycles=1) == "stopped"
    assert polls["stop"] == 200                    # Stop is allowed while paused
    assert loadcell.read_grams() == pytest.approx(loadcell.MOCK_CARD_G)
    clean, reason = main._assess_clean()
    assert not clean and "cradle" in reason
    main._write_machine_state(clean=clean, confirmed=False, reason=reason)
    ref_before = loadcell.empty_offset()
    assert c.post("/api/confirm-clear", headers=AUTH).status_code == 200   # halted: allowed
    ms = main.read_machine_state()
    main._control["stop"] = False
    shuttle.clear_jam(); main._set_card_at(None)
    main._bins.limits[2] = 40
    with pytest.raises(main.NeedsConfirm, match="card on cradle"):
        main.prepare_machine(confirmed=bool(ms.get("confirmed")))
    assert loadcell.empty_offset() == ref_before                       # reference untouched
    assert loadcell.grams_vs_empty_reference() == pytest.approx(loadcell.MOCK_CARD_G)


def test_confirm_clear_refused_while_paused_on_full_bin(monkeypatch, tmp_path):
    rig(monkeypatch, tmp_path)
    c = _client()
    main._bins.limits[2] = 0
    main.mark_running()
    polls = {"n": 0, "code": None}
    orig_full = main._bins.is_full

    def is_full(b):
        polls["n"] += 1
        if polls["n"] == 3:
            polls["code"] = c.post("/api/confirm-clear", headers=AUTH).status_code
            main._running = False                  # ...then power cut / SIGKILL: no teardown
        return orig_full(b)
    monkeypatch.setattr(main._bins, "is_full", is_full)
    main.run_sorter(engine=TS.Eng(), max_cycles=1)
    assert polls["code"] == 409
    assert not main.read_machine_state().get("confirmed")


def test_starting_state_blocks_empty_all_and_confirm_while_moving(monkeypatch, tmp_path):
    rig(monkeypatch, tmp_path)
    c = _client()
    main._set_state("stopped", "stopped by operator")
    seen = {}
    orig_home = elevator.home

    def home(*a, **k):
        seen["state"] = main._status["state"]
        seen["empty_all"] = c.post("/api/bins/empty-all", headers=AUTH).status_code
        seen["empty_1"] = c.post("/api/bins/1/empty", headers=AUTH).status_code
        seen["confirm"] = c.post("/api/confirm-clear", headers=AUTH).status_code
        seen["resume"] = c.post("/api/resume", headers=AUTH).status_code
        return orig_home(*a, **k)
    monkeypatch.setattr(elevator, "home", home)
    main.prepare_machine(confirmed=False)
    assert seen == {"state": "starting", "empty_all": 409, "empty_1": 409, "confirm": 409,
                    "resume": 409}


# ── M6: corrupt / bad config/machine.json → refuse to start, listing the keys ──
CASES = {
    "invalid_json": ("{ not json", "not valid JSON"),
    "speed_zero": (json.dumps({"card_detect": {"BELT_SPEED_MM_S": 0}}), "card_detect.BELT_SPEED_MM_S"),
    "speed_nan": ('{"card_detect": {"BELT_SPEED_MM_S": NaN}}', "not valid JSON"),
    "speed_inf": ('{"card_detect": {"BELT_SPEED_MM_S": Infinity}}', "not valid JSON"),
    "speed_str_nan": (json.dumps({"card_detect": {"BELT_SPEED_MM_S": "nan"}}), "card_detect.BELT_SPEED_MM_S"),
    "travel_sign_0": (json.dumps({"card_detect": {"TRAVEL_SIGN": 0}}), "card_detect.TRAVEL_SIGN"),
    "lock_false_str": (json.dumps({"camera": {"LOCK_AE_AWB": "false"}}), "camera.LOCK_AE_AWB"),
    "exit_max_null": (json.dumps({"sort": {"EXIT_MAX_S": None}}), "sort.EXIT_MAX_S"),
    "seal_negative": (json.dumps({"sort": {"SEAL_S": -5}}), "sort.SEAL_S"),
    "section_list": (json.dumps({"card_detect": [1, 2]}), "card_detect: must be a JSON object"),
    "typo_key": (json.dumps({"card_detect": {"BELT_SPEED_MMS": 90}}), "card_detect.BELT_SPEED_MMS: unknown key"),
    "unknown_section": (json.dumps({"cardetect": {}}), "cardetect: unknown section"),
    "top_level_list": ("[1]", "top level must be a JSON object"),
}
PROBE = r'''
import os, sys
os.environ["MOCK_HARDWARE"] = "1"
sys.path.insert(0, %r)
try:
    import main
    print("RESULT started")
except Exception as e:
    print("RESULT refused", type(e).__name__)
    print(e)
''' % str(ROOT)


@pytest.mark.parametrize("case", list(CASES))
def test_bad_machine_config_refuses_to_start(tmp_path, case):
    text, expect = CASES[case]
    cfg = tmp_path / "machine.json"
    cfg.write_text(text)
    env = dict(os.environ, RIFTBOUND_MACHINE_CONFIG=str(cfg), MOCK_HARDWARE="1")
    p = subprocess.run([sys.executable, "-c", PROBE], env=env, capture_output=True, text=True,
                       cwd=tmp_path)
    out = p.stdout + p.stderr
    assert "RESULT refused MachineConfigError" in out, out
    assert expect in out, out


def test_bad_machine_config_lists_every_bad_key_and_exits_78(tmp_path):
    cfg = tmp_path / "machine.json"
    cfg.write_text(json.dumps({"card_detect": {"BELT_SPEED_MM_S": 0, "TRAVEL_SIGN": 0},
                               "camera": {"LOCK_AE_AWB": "false"}, "sort": {"SEAL_S": -1}}))
    env = dict(os.environ, RIFTBOUND_MACHINE_CONFIG=str(cfg), MOCK_HARDWARE="1")
    p = subprocess.run([sys.executable, str(ROOT / "main.py"), "--web-token"], env=env,
                       capture_output=True, text=True, cwd=tmp_path)
    assert p.returncode == 78
    for key in ("card_detect.BELT_SPEED_MM_S", "card_detect.TRAVEL_SIGN", "camera.LOCK_AE_AWB",
                "sort.SEAL_S"):
        assert key in p.stderr, p.stderr
    assert "Traceback" not in p.stderr


# ── M4: HX711 never ready (DOUT stuck HIGH) through the REAL vendored lib ─────
@pytest.fixture
def real_hx(monkeypatch):
    rpi = types.ModuleType("RPi"); rpi.GPIO = G
    monkeypatch.setitem(sys.modules, "RPi", rpi); monkeypatch.setitem(sys.modules, "RPi.GPIO", G)
    G.reset()
    monkeypatch.setattr(time, "sleep", lambda s: None)
    sys.modules.pop("hardware.vendor.hx711", None)
    monkeypatch.setattr(loadcell, "_MOCK", False)
    G.input_value[loadcell.DOUT_PIN] = 0
    loadcell.init()
    yield loadcell._hx
    loadcell._hx = None


def test_hx711_not_ready_is_a_fault_not_empty(real_hx):
    """Audit: a dead HX711 read as raw -1 → -238 g → "empty". Now the vendored
    _read gives up (False) and read_grams() raises LoadCellError."""
    real_hx.set_offset(100_000, channel='A', gain_A=128)
    G.input_value[loadcell.DOUT_PIN] = 1             # HX711 unpowered / not ready: DOUT stays high
    assert real_hx._read() is False
    with pytest.raises(loadcell.LoadCellError):
        loadcell.read_grams()


def test_raw_minus_one_rejected_even_without_the_vendored_fix(real_hx, monkeypatch):
    real_hx.set_offset(100_000, channel='A', gain_A=128)
    monkeypatch.setattr(loadcell, "_offset_valid", True)
    monkeypatch.setattr(real_hx, "get_raw_data_mean", lambda n=1: -1)
    with pytest.raises(loadcell.LoadCellError):
        loadcell.read_grams()
    assert not loadcell.is_empty(-238.1)


# ── load cell failing intermittently during a run ───────────────────────────
@pytest.mark.parametrize("fail_after", [1, 3, 5, 8, 12, 20, 30])
def test_intermittent_loadcell(monkeypatch, tmp_path, fail_after):
    rec = rig(monkeypatch, tmp_path)
    n = {"r": 0}
    orig = loadcell._mock_raw

    def raw():
        n["r"] += 1
        if fail_after <= n["r"] < fail_after + 7:      # a burst of 7 bad reads (> MAX_READ_FAILURES)
            return None
        return orig()
    monkeypatch.setattr(loadcell, "_mock_raw", raw)
    main.mark_running()
    main.run_sorter(engine=TS.Eng(), max_cycles=2)
    main.teardown()
    assert not rec.violations and not rec.pump and not rec.belt


# ── camera never sees the card / camera stalls mid-seek ─────────────────────
def test_camera_never_sees_card(monkeypatch, tmp_path):
    rec = rig(monkeypatch, tmp_path)
    card_detect.MOCK_SCENE.visible = False
    st = main.run_sorter(engine=TS.Eng(), max_cycles=1)
    assert st == "jam" and not rec.belt


def test_camera_stall_brakes_the_belt(monkeypatch):
    """Audit: the belt kept running while capture_lores_luma() blocked. The
    grab watchdog now brakes it after FRAME_TIMEOUT_S."""
    belt = {"on": False}
    gate = threading.Event()
    src = card_detect.CameraSource()
    monkeypatch.setattr(card_detect.camera, "capture_lores_luma", lambda: (gate.wait(), None)[1])
    ref = np.zeros((180, 320), "uint8")
    out = {}
    t = threading.Thread(target=lambda: out.update(r=card_detect.centre_card(
        ref, lambda: belt.update(on=True), lambda: belt.update(on=False),
        lambda: belt.update(on=False), source=src)), daemon=True)
    t.start()
    _real_sleep(card_detect.FRAME_TIMEOUT_S + 0.5)
    on = belt["on"]
    gate.set()
    t.join(2.0)
    assert not on, "belt keeps running while capture_lores_luma() blocks"
    assert out["r"].reason == "camera" and out["r"].jam


# ── config/identify.json: validated like machine.json (exit 78, every bad key) ─
_IDM_KEYS = ("MIN_CONF", "MIN_MARGIN_BITS", "FALLBACK", "FALLBACK_MIN_PHASH_CONF", "MAX_MISSING_FRACTION")


@pytest.fixture
def idm_cfg(monkeypatch, tmp_path):
    from vision import identify as m
    for k in _IDM_KEYS:
        monkeypatch.setattr(m, k, getattr(m, k))
    cfg = tmp_path / "identify.json"
    monkeypatch.setattr(m, "CONFIG_FILE", cfg)
    return m, cfg


def test_identify_config_applies_every_key_normalised(idm_cfg):
    m, cfg = idm_cfg
    cfg.write_text(json.dumps({"_comment": "x", "min_conf": 0.9, "min_margin_bits": 12.0, "fallback": False,
                               "fallback_min_phash_conf": 0.75, "max_missing_fraction": 0}))
    applied = m.load_config()
    assert applied == {"min_conf": 0.9, "min_margin_bits": 12, "fallback": False,
                       "fallback_min_phash_conf": 0.75, "max_missing_fraction": 0.0}
    assert m.MIN_CONF == 0.9 and m.MIN_MARGIN_BITS == 12 and isinstance(m.MIN_MARGIN_BITS, int)
    assert m.FALLBACK is False and m.FALLBACK_MIN_PHASH_CONF == 0.75
    assert m.MAX_MISSING_FRACTION == 0.0 and isinstance(m.MAX_MISSING_FRACTION, float)


def test_identify_config_missing_file_keeps_defaults(idm_cfg):
    m, _ = idm_cfg
    before = {k: getattr(m, k) for k in _IDM_KEYS}
    assert m.load_config() == {}
    assert {k: getattr(m, k) for k in _IDM_KEYS} == before


def test_identify_config_lists_every_bad_key_and_applies_nothing(idm_cfg):
    m, cfg = idm_cfg
    before = {k: getattr(m, k) for k in _IDM_KEYS}
    cfg.write_text(json.dumps({"min_conf": "0.9", "min_margin_bits": 3.5, "fallback": "false",
                               "fallback_min_phash_conf": 1.5, "max_missing_fraction": -0.1,
                               "min_cof": 0.8}))
    with pytest.raises(m.IdentifyConfigError) as ei:
        m.load_config()
    probs = ei.value.problems
    assert len(probs) == 6, probs
    for key in ("min_conf", "min_margin_bits", "fallback", "fallback_min_phash_conf",
                "max_missing_fraction", "min_cof"):
        assert any(p.startswith(f"{key}:") for p in probs), (key, probs)
    assert "refusing to start" in str(ei.value)
    assert {k: getattr(m, k) for k in _IDM_KEYS} == before        # all or nothing


@pytest.mark.parametrize("text, expect", [
    ("{oops", "not valid JSON"),
    ('{"min_conf": NaN}', "not valid JSON"),
    ('[0.8]', "top level must be a JSON object"),
    ('{"min_conf": true}', "min_conf: must be a number"),
    ('{"min_margin_bits": 257}', "min_margin_bits: 257 is outside [0, 256]"),
    ('{"min_conf": 0.4}', "min_conf: 0.4 is outside [0.5, 1.0]"),
    ('{"min_conf": 0.75, "fallback_min_phash_conf": 0.8}', "must not exceed min_conf"),
])
def test_identify_config_rejects(idm_cfg, text, expect):
    m, cfg = idm_cfg
    cfg.write_text(text)
    with pytest.raises(m.IdentifyConfigError) as ei:
        m.load_config()
    assert any(expect in p for p in ei.value.problems), ei.value.problems


def test_bad_identify_config_lists_every_bad_key_and_exits_78(tmp_path):
    cfg = tmp_path / "identify.json"
    cfg.write_text(json.dumps({"min_conf": 2, "fallback": "no", "min_margin_bit": 10}))
    env = dict(os.environ, RIFTBOUND_IDENTIFY_CONFIG=str(cfg), MOCK_HARDWARE="1")
    env.pop("RIFTBOUND_MACHINE_CONFIG", None)
    p = subprocess.run([sys.executable, str(ROOT / "main.py"), "--web-token"], env=env,
                       capture_output=True, text=True, cwd=tmp_path)
    assert p.returncode == 78, p.stdout + p.stderr
    assert "identify.json" in p.stderr and "refusing to start" in p.stderr
    for key in ("min_conf:", "fallback:", "min_margin_bit:"):
        assert key in p.stderr, p.stderr
    assert "Traceback" not in p.stderr
