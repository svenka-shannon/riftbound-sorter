"""
Regression tests for the audit fixes (B1-B5, M1-M7, minors) and the
mechanical-audit additions (exit run, bin limits, vent valve).

Run:
  uv run --python 3.11 --with pytest --with pillow --with numpy --with requests \
         --with flask --with imagehash pytest -q tests/
"""

import importlib
import io
import json
import os
import sys
import time
import types
import urllib.error
from pathlib import Path
from types import SimpleNamespace

os.environ["MOCK_HARDWARE"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from PIL import Image

import main
from hardware import (camera, card_detect, conveyor, elevator, loadcell, machine_config, servos,
                      shuttle, vacuum)
from api import riftcodex
import fakegpio as G


class Eng:
    reject_bin = 9
    reloads = 0

    def __init__(self, bin_num=2):
        self.bin_num = bin_num

    def assign_bin(self, card):
        return self.bin_num

    def describe_bin(self, b):
        return f"Bin {b}"

    def load(self):
        Eng.reloads += 1


@pytest.fixture
def rig(monkeypatch, tmp_path):
    rec = SimpleNamespace(events=[], recorded=[], pump=False, belt=False, sleep_hook=None)

    def fake_sleep(s):
        if rec.sleep_hook:
            rec.sleep_hook()
    monkeypatch.setattr(time, "sleep", fake_sleep)
    monkeypatch.setattr(main, "_bins", main.BinCounts(tmp_path / "c.json", tmp_path / "l.json",
                                                      main.DEFAULT_BIN_LIMITS))
    monkeypatch.setattr(main, "identify", lambda j: ("rb_001", 0.95))
    monkeypatch.setattr(main.riftcodex, "get_card", lambda cid: {"name": "Jinx"})
    monkeypatch.setattr(main.inventory, "record_scan", lambda *a: rec.recorded.append(a))

    def belt(state, name):
        def f(*a, **k):
            rec.belt = state
            rec.events.append(name)
        return f
    monkeypatch.setattr(conveyor, "run", belt(True, "run"))
    monkeypatch.setattr(conveyor, "brake", belt(False, "brake"))
    monkeypatch.setattr(conveyor, "stop", belt(False, "stop"))

    def pump(state):
        def f():
            rec.pump = state
            rec.events.append("pump_on" if state else "pump_off")
        return f
    monkeypatch.setattr(vacuum, "pump_on", pump(True))
    monkeypatch.setattr(vacuum, "pump_off", pump(False))

    monkeypatch.setattr(loadcell, "MOCK_CARD_G", 1.75)
    loadcell.mock_set_load(0.0)
    s = card_detect.MOCK_SCENE
    s.card_x_mm, s.auto_card, s.visible, s.running = None, True, True, False
    s.speed_mm_s = card_detect.BELT_SPEED_MM_S * 1.1
    elevator.mock_set_cards(150)
    servos.init()
    servos.arm_park()
    shuttle.init()
    shuttle.home()                          # init() never homes (audit M7)
    elevator.init()
    assert elevator.home()
    loadcell.tare(calibration=True)         # calibrated machine: stores the empty reference
    shuttle.level()
    main._set_state("running")
    for k in main._stats:
        main._stats[k] = 0
    rec.events.clear()
    yield rec


def _assert_safe(rec):
    assert rec.pump is False, "pump left on"
    assert rec.belt is False, "belt left running"
    assert servos.arm_angle() == servos.ARM_PARK, "arm not parked"


# ── B4: shutdown signals ─────────────────────────────────────────────────────
def _tip_spy(monkeypatch, n_signals):
    """Deliver n_signals stop signals while the cradle is part-way through
    tip_lower at column 2. Returns the write trace."""
    orig = shuttle._write
    trace, fired = [], {}

    def spy(ch, a):
        trace.append((ch, round(a, 1), shuttle._tilt_state, shuttle._target))
        if ch == shuttle.CH_TILT and shuttle._target == 2 and a < 70 and not fired:
            fired["i"] = len(trace) - 1
            for _ in range(n_signals):
                main._on_signal()
        orig(ch, a)
    monkeypatch.setattr(shuttle, "_write", spy)
    return trace, fired


def test_single_sigterm_mid_tip_finishes_card_then_stops(rig, monkeypatch):
    trace, fired = _tip_spy(monkeypatch, 1)
    assert main.run_sorter(engine=Eng(), max_cycles=5) == "stopped"
    assert fired, "tip never reached"
    assert main._stats["total"] == 1 and main._bins.count(2) == 1     # card finished, no 2nd card
    hold = shuttle.TILT_ANGLES["hold"]
    last_tilt = None
    for ch, a, tilt_state, _ in trace:
        if ch == shuttle.CH_TILT:
            last_tilt = a
        else:   # every carriage step happened with the cradle at HOLD
            assert tilt_state == "hold" and abs(last_tilt - hold) < 0.5
    assert shuttle.state()[:2] == ("home", "level")


def test_second_sigterm_mid_tip_never_moves_carriage(rig, monkeypatch):
    trace, fired = _tip_spy(monkeypatch, 2)
    main.mark_running()
    with pytest.raises(main.Shutdown):
        main.sort_one_card(Eng())
    after = trace[fired["i"] + 1:]
    assert after, "cradle was not brought back"
    assert not [t for t in after if t[0] == shuttle.CH_SHUTTLE], "carriage moved after the signal"
    assert shuttle.state()[:2] == (2, "hold")        # tilt back to hold, carriage left at column 2
    n = len(trace)
    main.teardown()
    assert not [t for t in trace[n:] if t[0] == shuttle.CH_SHUTTLE], "teardown moved the carriage"
    assert shuttle.state()[0] == 2                   # deinit does NOT home
    ms = main.read_machine_state()
    assert ms["clean"] is False and "cradle" in ms["reason"]


def test_tilt_unknown_mid_ramp_and_to_column_refuses(rig, monkeypatch):
    orig = shuttle._write
    seen = []

    def spy(ch, a):
        if ch == shuttle.CH_TILT:
            seen.append(shuttle._tilt_state)
        orig(ch, a)
    monkeypatch.setattr(shuttle, "_write", spy)
    shuttle.hold()
    assert seen and all(s is None for s in seen)       # unknown while ramping
    assert shuttle.state()[1] == "hold"
    shuttle._tilt_state = None
    with pytest.raises(shuttle.ShuttleError, match="only in HOLD"):
        shuttle.to_column(1)
    shuttle.hold()
    shuttle.set_jammed("test")
    with pytest.raises(shuttle.ShuttleError, match="locked"):
        shuttle.to_column(1)
    shuttle.clear_jam()
    shuttle.to_column(1)
    assert shuttle.state()[0] == 1


def test_stuck_card_latches_carriage(rig, monkeypatch):
    monkeypatch.setattr(loadcell, "read_grams", lambda samples=7: 1.75)
    assert main.run_sorter(engine=Eng(), max_cycles=1) == "jam"
    assert shuttle.jammed()
    with pytest.raises(shuttle.ShuttleError):
        shuttle.to_column("home")


def test_first_signal_during_elevator_raise_stops_cleanly(rig, monkeypatch):
    elevator.mock_set_cards(10)                 # long raise
    elevator.home()
    n = {"i": 0}
    orig = elevator._write_phase

    def wp(idx):
        n["i"] += 1
        if n["i"] == 50:
            main._on_signal()
        orig(idx)
    monkeypatch.setattr(elevator, "_write_phase", wp)
    assert main.run_sorter(engine=Eng(), max_cycles=1) == "stopped"
    assert "pump_on" not in rig.events
    assert main._status["state"] == "stopped"


def test_signal_during_teardown_is_ignored(rig):
    main._tearing_down = True
    main._on_signal(); main._on_signal(); main._on_signal()   # never raises


def test_second_signal_on_arm_mid_arc_carries_card_to_belt(rig, monkeypatch):
    orig = servos._arm_write
    fired = {}
    orig_off = vacuum.pump_off
    off_at = []

    def off():
        off_at.append(servos.arm_angle())
        orig_off()
    monkeypatch.setattr(vacuum, "pump_off", off)

    def spy(a):
        orig(a)
        if main._card_at == "cup" and abs(a - servos.ARM_PICK) > 40 and not fired:
            fired[1] = a
            main._on_signal(); main._on_signal()
    monkeypatch.setattr(servos, "_arm_write", spy)
    main.mark_running()
    with pytest.raises(main.Shutdown):
        main.sort_one_card(Eng())
    assert fired, "signal never delivered mid-arc"
    ev = rig.events
    assert ev.count("pump_on") == 1 and "pump_off" in ev and rig.pump is False
    # the pump stayed on until the arm had reached the drop pose
    assert off_at and off_at[0] == pytest.approx(servos.ARM_DROP)
    assert main._card_at == "belt"                     # carried on, released at the drop pose
    assert servos.arm_angle() == servos.ARM_PARK
    main.teardown()
    ms = main.read_machine_state()
    assert ms["clean"] is False and "belt" in ms["reason"]


def test_signal_while_sealing_leaves_card_on_stack(rig, monkeypatch):
    calls = {"n": 0}

    def sleep(s):
        if main._card_at == "cup" and servos.arm_angle() == servos.ARM_PICK and not calls["n"]:
            calls["n"] = 1
            main._on_signal(); main._on_signal()
    monkeypatch.setattr(time, "sleep", sleep)
    with pytest.raises(main.Shutdown):
        main.sort_one_card(Eng())
    assert calls["n"] == 1, "signal never delivered while sealing"
    assert main._card_at is None                       # released at the pick pose
    _assert_safe(rig)


def test_graceful_stop_writes_clean_marker_and_restart_assumes_rest(rig):
    main.mark_running()
    main._on_signal()                                  # finish, then stop
    assert main.run_sorter(engine=Eng(), max_cycles=3) == "stopped"
    main.teardown()
    ms = main.read_machine_state()
    assert ms["clean"] is True and ms["rest_pose"] == "home_level"
    # restart ramps from the assumed rest pose (no jump: first tilt move starts at level)
    shuttle.init(assume_rest=True)
    assert shuttle.state()[:2] == ("home", "level")


# ── M6: PCA9685 release ──────────────────────────────────────────────────────
class FakeChannel:
    def __init__(self, log, i):
        self.log, self.i, self._d = log, i, 0x1234

    @property
    def duty_cycle(self):
        return self._d

    @duty_cycle.setter
    def duty_cycle(self, v):
        self._d = v
        self.log.append(("duty", self.i, v))


class FakePCA:
    def __init__(self):
        self.log = []
        self.channels = [FakeChannel(self.log, i) for i in range(16)]
        self._mode1 = 0xA0

    def deinit(self):
        self.log.append(("deinit",))
        self._mode1 = 0

    @property
    def mode1_reg(self):
        return self._mode1

    @mode1_reg.setter
    def mode1_reg(self, v):
        self._mode1 = v
        self.log.append(("mode1", v))


def test_pca_channels_off_before_deinit_shared(monkeypatch):
    pca = FakePCA()
    monkeypatch.setattr(servos, "_MOCK", False)
    monkeypatch.setattr(shuttle, "_MOCK", False)
    monkeypatch.setattr(servos, "_pca", pca)
    monkeypatch.setattr(shuttle, "_pca", pca)
    monkeypatch.setattr(shuttle, "_own_pca", False)
    shuttle.deinit()
    assert pca.log == [("duty", 1, 0), ("duty", 2, 0)]       # its channels off, chip kept
    servos.deinit()
    duties = [e for e in pca.log[2:] if e[0] == "duty"]
    assert sorted(e[1] for e in duties) == list(range(16)) and all(e[2] == 0 for e in duties)
    i_deinit = pca.log.index(("deinit",))
    assert all(pca.log.index(d) < i_deinit for d in duties)  # every channel off BEFORE deinit
    assert pca.log[-1] == ("mode1", servos.PCA_SLEEP)
    n = len(pca.log)
    servos.deinit()                                          # idempotent
    shuttle.deinit()                                         # chip released: no writes
    assert len(pca.log) == n


def test_pca_owned_by_shuttle(monkeypatch):
    pca = FakePCA()
    monkeypatch.setattr(shuttle, "_MOCK", False)
    monkeypatch.setattr(servos, "_pca", None)
    monkeypatch.setattr(shuttle, "_pca", pca)
    monkeypatch.setattr(shuttle, "_own_pca", True)
    shuttle.deinit()
    assert ("deinit",) in pca.log
    assert pca.log.index(("deinit",)) > max(i for i, e in enumerate(pca.log) if e[0] == "duty")
    assert shuttle._pca is None


def test_level_preload_and_actuation_range(monkeypatch):
    geometric_level = 90 + 3.6
    assert geometric_level - shuttle.TILT_ANGLES["level"] == pytest.approx(0.5, abs=0.05)
    monkeypatch.setitem(shuttle.SHUTTLE_ACTUATION_RANGE, shuttle.CH_SHUTTLE, 270)
    shuttle._write(shuttle.CH_SHUTTLE, 250.0)
    assert shuttle._pos[shuttle.CH_SHUTTLE] == 250.0
    monkeypatch.setitem(shuttle.SHUTTLE_ACTUATION_RANGE, shuttle.CH_SHUTTLE, 180)
    shuttle._write(shuttle.CH_SHUTTLE, 250.0)
    assert shuttle._pos[shuttle.CH_SHUTTLE] == 180.0


# ── B5 + elevator minors ─────────────────────────────────────────────────────
def test_raise_timeout_is_distance_based():
    full = int(elevator.MAX_POS_MM * elevator.STEPS_PER_MM)
    t = elevator.raise_timeout_s(full)
    nominal = full * elevator.RAISE_STEP_S
    assert nominal > 30.0                                  # the old fixed timeout was too short
    assert t >= nominal * elevator.RAISE_TIMEOUT_FACTOR
    assert t <= nominal * elevator.RAISE_TIMEOUT_FACTOR + elevator.RAISE_TIMEOUT_MARGIN_S + 1.0
    assert elevator.raise_timeout_s(100) < 5.0


def test_nearly_empty_hopper_reaches_pick_after_homing(monkeypatch):
    """Simulated clock: one RAISE_STEP_S per step. The old 30 s limit failed here."""
    clock = {"t": 0.0}
    monkeypatch.setattr(elevator.time, "perf_counter", lambda: clock["t"])
    orig = elevator._write_phase

    def wp(idx):
        clock["t"] += elevator.RAISE_STEP_S
        orig(idx)
    monkeypatch.setattr(elevator, "_write_phase", wp)
    elevator.init()
    elevator.mock_set_cards(3)
    assert elevator.home()
    assert elevator.raise_to_pick() is True
    assert clock["t"] > 30.0


def test_step_pacing_never_bursts_after_a_hiccup(monkeypatch):
    clock = {"t": 0.0}
    writes = []
    monkeypatch.setattr(elevator, "_MOCK", False)
    monkeypatch.setattr(elevator, "GPIO", G, raising=False)
    G.reset()
    monkeypatch.setattr(elevator, "_initialized", True)
    for p in elevator.STEPPER_PINS:
        G.setup(p, G.OUT, initial=0)
    monkeypatch.setattr(elevator.time, "perf_counter", lambda: clock["t"])

    def wait_until(t):
        clock["t"] = max(clock["t"], t)
    monkeypatch.setattr(elevator, "_wait_until", wait_until)
    orig = elevator._write_phase

    def wp(idx):
        writes.append(clock["t"])
        if len(writes) in (150, 151, 300):
            clock["t"] += 0.0019                             # scheduler hiccups
        orig(idx)
    monkeypatch.setattr(elevator, "_write_phase", wp)
    elevator._move(+1, 400, elevator.RAISE_STEP_S)
    gaps = [b - a for a, b in zip(writes, writes[1:])]
    assert min(gaps) >= elevator.RAISE_STEP_S - 1e-9


def test_elevator_release_after_deinit_does_not_raise(monkeypatch):
    monkeypatch.setattr(elevator, "_MOCK", False)
    monkeypatch.setattr(elevator, "GPIO", G, raising=False)
    G.reset()
    elevator.init()
    elevator.deinit()
    elevator._release()                                     # pins cleaned up: no RuntimeError
    elevator.deinit()                                       # idempotent


# ── M1: card left on the cradle at restart ───────────────────────────────────
def test_card_on_cradle_at_startup_refuses(rig):
    main._bins.limits[2] = 0
    main.mark_running()
    with pytest.raises(main.BinFull):
        main.sort_one_card(Eng())                            # card held on the cradle
    main.teardown()
    ms = main.read_machine_state()
    assert ms["clean"] is False and "cradle" in ms["reason"]
    # --- restart (new process): the load cell is NOT tared at init, nothing moves ---
    loadcell.init()
    servos.init()
    shuttle.init()
    assert servos.arm_angle() is None and shuttle.state()[:2] == (None, None)
    with pytest.raises(main.NeedsConfirm, match="pose not known"):
        main.prepare_machine(confirmed=False)
    assert servos.arm_angle() is None and shuttle.state()[:2] == (None, None)   # M7: no command
    # operator presses "Machine clear" WITHOUT removing the card: still refused (M1)
    main.confirm_clear("test")
    with pytest.raises(main.NeedsConfirm, match="card on cradle"):
        main.prepare_machine(confirmed=True)
    assert loadcell.grams_vs_empty_reference() == pytest.approx(1.75)    # NOT tared away
    # operator removes the card and confirms again
    loadcell.mock_set_load(0.0)
    main.confirm_clear("test")
    assert main.read_machine_state()["confirmed"] is True
    main.prepare_machine(confirmed=True)
    assert shuttle.state()[:2] == ("home", "level")
    assert abs(loadcell.read_grams()) < 0.01


def test_startup_without_reference_needs_confirmation(rig, monkeypatch):
    monkeypatch.setattr(loadcell, "_empty_offset", None)
    with pytest.raises(main.NeedsConfirm, match="no stored empty-cradle reference"):
        main._startup_cradle_check(confirmed=False)


def test_startup_empty_cradle_passes_without_confirmation(rig):
    loadcell.init()                                          # reloads the stored offset
    main._startup_cradle_check(confirmed=False)
    assert shuttle.state()[:2] == ("home", "level")


def test_empty_offset_persisted_on_verified_tare(rig):
    data = json.loads(loadcell._CALIBRATION_FILE.read_text())
    assert "empty_offset" in data


def test_missing_marker_means_unclean():
    ms = main.read_machine_state()
    assert ms["clean"] is False and ms["confirmed"] is False


# ── M2: load cell robustness ────────────────────────────────────────────────
def test_transient_read_failures_are_reread(rig):
    loadcell.mock_set_load(1.75)
    loadcell.mock_fail_next_reads(3)
    assert loadcell.read_grams() == pytest.approx(1.75)
    loadcell.mock_fail_next_reads(loadcell.MAX_READ_FAILURES + 1)
    with pytest.raises(loadcell.LoadCellError):
        loadcell.read_grams()


def test_transient_failure_mid_cycle_does_not_stop(rig, monkeypatch):
    orig = main._mock_cradle_receives_card

    def receive():
        orig()
        loadcell.mock_fail_next_reads(2)
    monkeypatch.setattr(main, "_mock_cradle_receives_card", receive)
    assert main.sort_one_card(Eng()) == 2


def test_persistent_load_cell_failure_stops(rig, monkeypatch):
    orig = main._mock_cradle_receives_card

    def receive():
        orig()
        loadcell.mock_fail_next_reads(1000)
    monkeypatch.setattr(main, "_mock_cradle_receives_card", receive)
    assert main.run_sorter(engine=Eng(), max_cycles=1) == "error"
    assert "load cell" in main._status["message"]


def test_median_rejects_a_spike(rig, monkeypatch):
    vals = iter([1.75, 1.75, 60.0, 1.75, 1.75, 1.74, 1.76])   # plausible (< 100 g) outlier
    monkeypatch.setattr(loadcell, "_mock_raw", lambda: next(vals) * loadcell.SCALE_FACTOR)
    assert loadcell.read_grams() == pytest.approx(1.75, abs=0.02)


@pytest.fixture
def vendored_hx(monkeypatch):
    """The real vendored gandalf15 HX711 class on a fake RPi.GPIO, with _read scripted."""
    rpi = types.ModuleType("RPi")
    rpi.GPIO = G
    monkeypatch.setitem(sys.modules, "RPi", rpi)
    monkeypatch.setitem(sys.modules, "RPi.GPIO", G)
    G.reset()
    G.input_value[loadcell.DOUT_PIN] = 0
    monkeypatch.setattr(time, "sleep", lambda s: None)
    sys.modules.pop("hardware.vendor.hx711", None)
    hx_mod = importlib.import_module("hardware.vendor.hx711")
    monkeypatch.setattr(loadcell, "_MOCK", False)
    loadcell.init()                                         # GPIO.setmode + HX711(...)
    script = []
    monkeypatch.setattr(loadcell._hx, "_read", lambda: script.pop(0) if script else 100_000)
    yield SimpleNamespace(hx=loadcell._hx, script=script, mod=hx_mod)
    loadcell._hx = None


def test_vendored_hx711_api(vendored_hx):
    assert isinstance(vendored_hx.hx, vendored_hx.mod.HX711)
    s = vendored_hx.script
    s.extend([100_000] * 10)                                 # zero(10)
    loadcell.tare(calibration=True)
    assert vendored_hx.hx.get_current_offset() == 100_000
    assert json.loads(loadcell._CALIBRATION_FILE.read_text())["empty_offset"] == 100_000
    card = 100_000 + int(1.75 * loadcell.SCALE_FACTOR)
    s.extend([False, card, 0, card, card, False, card, card, card, card])   # 3 failed reads
    assert loadcell.read_grams() == pytest.approx(1.75, abs=0.01)
    s.extend([False] * (loadcell.MAX_READ_FAILURES + 1))
    with pytest.raises(loadcell.LoadCellError):
        loadcell.read_grams()
    s.clear()
    s.extend([card] * 7)
    assert loadcell.grams_vs_empty_reference() == pytest.approx(1.75, abs=0.01)


# ── M4: conveyor pins ────────────────────────────────────────────────────────
def _no_reverse_ever(log):
    lv = {}
    for e in log:
        if e[0] in ("out", "setup_out"):
            lv[e[1]] = e[2]
        elif e[0] == "pwm":
            lv[e[1]] = 1 if e[2] >= 100 else (0 if e[2] <= 0 else "pwm")
        for fwd, rev in ((conveyor.MOTOR_A_FWD, conveyor.MOTOR_A_REV),
                         (conveyor.MOTOR_B_FWD, conveyor.MOTOR_B_REV)):
            if lv.get(rev) == 1 and lv.get(fwd) in (0, "pwm"):
                return False
    return True


@pytest.fixture
def gpio_conveyor(monkeypatch):
    monkeypatch.setattr(conveyor, "_MOCK", False)
    monkeypatch.setattr(conveyor, "GPIO", G, raising=False)
    G.reset()
    conveyor.init()
    yield
    conveyor.deinit()


def test_stop_drives_all_pins_low(gpio_conveyor):
    conveyor.run()
    G.output(conveyor.MOTOR_A_REV, 1)          # whatever state an earlier path left
    G.output(conveyor.MOTOR_B_REV, 1)
    conveyor.stop()
    for pin in (conveyor.MOTOR_A_FWD, conveyor.MOTOR_A_REV, conveyor.MOTOR_B_FWD, conveyor.MOTOR_B_REV):
        assert G.level[pin] == 0, f"GPIO {pin} not LOW after stop()"


def test_brake_never_reverses_and_never_drives_rev_high(gpio_conveyor, monkeypatch):
    """Audit minor: brake = all inputs LOW, REV pins first; nothing ever drives
    a REV input HIGH, so IA=L, IB=H (reverse) is impossible on every path."""
    for seq in (("run", "brake"), ("run", "stop"), ("brake",), ("run", "run", "brake", "stop")):
        G.log.clear()
        for name in seq:
            getattr(conveyor, name)()
        assert _no_reverse_ever(G.log), seq
        assert not [e for e in G.log if e[0] == "out" and e[1] in (conveyor.MOTOR_A_REV,
                                                                 conveyor.MOTOR_B_REV) and e[2]]
        assert all(G.level[p] == 0 for p in (23, 24, 25, 26)), seq
    # REV pins are written before the FWD duty drops
    G.log.clear()
    conveyor.run()
    conveyor.brake()
    i_rev = max(i for i, e in enumerate(G.log) if e[0] == "out")
    i_fwd = min(i for i, e in enumerate(G.log) if e[0] == "pwm" and e[2] == 0)
    assert i_rev < i_fwd


# ── Vent valve ───────────────────────────────────────────────────────────────
def test_vent_release_sequence(monkeypatch):
    monkeypatch.setattr(vacuum, "_MOCK", False)
    monkeypatch.setattr(vacuum, "GPIO", G, raising=False)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    G.reset()
    vacuum.init()
    assert G.level[vacuum.RELAY_PIN] == 1 and G.level[vacuum.VENT_PIN] == 1   # active LOW: both off
    vacuum.pump_on()
    assert G.level[vacuum.RELAY_PIN] == 0 and G.level[vacuum.VENT_PIN] == 1
    G.log.clear()
    vacuum.release()
    outs = [(e[1], e[2]) for e in G.log if e[0] == "out"]
    assert outs == [(vacuum.RELAY_PIN, 1), (vacuum.VENT_PIN, 0), (vacuum.VENT_PIN, 1)]
    assert not vacuum.vent_is_open() and not vacuum.pump_is_on()
    vacuum.deinit()
    assert vacuum.RELAY_PIN not in G.mode and vacuum.VENT_PIN not in G.mode
    vacuum.deinit()                            # idempotent


def test_vent_pin_is_free():
    used = {conveyor.MOTOR_A_FWD, conveyor.MOTOR_A_REV, conveyor.MOTOR_B_FWD, conveyor.MOTOR_B_REV,
            loadcell.DOUT_PIN, loadcell.SCK_PIN, elevator.TOP_SWITCH_PIN, elevator.BOTTOM_SWITCH_PIN,
            vacuum.RELAY_PIN, 2, 3, *elevator.STEPPER_PINS}
    assert vacuum.VENT_PIN == 27 and vacuum.VENT_PIN not in used


def test_release_then_slow_lift_before_park(rig, monkeypatch):
    moves = []
    orig = servos.move_arm_smooth

    def spy(target, duration_s=None, settle_s=0.15):
        moves.append((round(target, 1), duration_s))
        orig(target, duration_s, settle_s)
    monkeypatch.setattr(servos, "move_arm_smooth", spy)
    main.sort_one_card(Eng())
    lift = servos.ARM_DROP + (main.ARM_LIFT_DEG if servos.ARM_PARK >= servos.ARM_DROP else -main.ARM_LIFT_DEG)
    i_drop = moves.index((servos.ARM_DROP, None))
    assert moves[i_drop + 1] == (round(lift, 1), main.ARM_LIFT_S)
    assert moves[i_drop + 2][0] == servos.ARM_PARK


def test_card_never_seen_blames_the_cup(rig):
    card_detect.MOCK_SCENE.auto_card = False
    assert main.run_sorter(engine=Eng(), max_cycles=1) == "jam"
    assert "still be on the cup" in main._status["message"]
    _assert_safe(rig)


# ── Exit run onto the cradle ─────────────────────────────────────────────────
def test_exit_run_uses_measured_speed():
    nominal = card_detect.BELT_SPEED_MM_S
    assert main.exit_run_s(nominal) == pytest.approx(main.EXIT_TRAVEL_MM / nominal * main.EXIT_TIME_MARGIN)
    assert main.exit_run_s(115.0) > main.exit_run_s(nominal)            # slow N20 → longer run
    assert main.exit_run_s(115.0) * 115.0 >= 144.0                      # covers the 144 mm
    assert main.exit_run_s(500.0) == main.exit_run_s(nominal)           # never assumed faster
    assert main.exit_run_s(20.0) == main.EXIT_MAX_S                     # capped
    assert main.exit_run_s(None) == main.exit_run_s(nominal)


def test_card_partly_on_cradle_is_not_tipped(rig, monkeypatch):
    monkeypatch.setattr(main, "_mock_cradle_receives_card", lambda: loadcell.mock_set_load(0.9))
    assert main.run_sorter(engine=Eng(), max_cycles=1) == "jam"
    assert "not fully on the cradle" in main._status["message"]
    assert shuttle.state()[:2] == ("home", "level")                     # NOT tipped to hold
    assert rig.events.count("run") >= 3                                 # centre, exit, extra burst
    _assert_safe(rig)


def test_bin_limit_defaults_conservative():
    assert all(main.DEFAULT_BIN_LIMITS[b] == 40 for b in range(4))
    assert all(main.DEFAULT_BIN_LIMITS[b] == 12 for b in range(4, 8))


# ── M5: offline card cache ──────────────────────────────────────────────────
def _offline(monkeypatch):
    def boom(endpoint):
        raise urllib.error.URLError("no network")
    monkeypatch.setattr(riftcodex, "_fetch", boom)


def test_stale_cache_used_when_offline(monkeypatch):
    riftcodex.CACHE_FILE.write_text(json.dumps({"rb_001": {"riftbound_id": "rb_001", "name": "Jinx"}}))
    old = time.time() - 10 * riftcodex.CACHE_TTL
    os.utime(riftcodex.CACHE_FILE, (old, old))
    _offline(monkeypatch)
    cards = riftcodex.fetch_all_cards()
    assert cards["rb_001"]["name"] == "Jinx"
    assert riftcodex.get_card("rb_001")["name"] == "Jinx"


def test_no_cache_offline_raises_clearly(monkeypatch):
    _offline(monkeypatch)
    with pytest.raises(riftcodex.CardDataUnavailable, match="no card cache"):
        riftcodex.fetch_all_cards()


def test_corrupt_cache_and_offline(monkeypatch):
    riftcodex.CACHE_FILE.write_text("{not json")
    _offline(monkeypatch)
    with pytest.raises(riftcodex.CardDataUnavailable):
        riftcodex.fetch_all_cards()


def test_main_waits_for_card_data_instead_of_exiting(monkeypatch):
    calls = {"n": 0}

    def fetch(force=False):
        calls["n"] += 1
        if calls["n"] < 3:
            raise riftcodex.CardDataUnavailable("offline")
        return {"rb_001": {}}
    monkeypatch.setattr(riftcodex, "fetch_all_cards", fetch)
    monkeypatch.setattr(main, "_wait_interruptible", lambda s: None)
    assert main._load_cards_with_retry() == {"rb_001": {}}
    assert calls["n"] == 3


def test_fresh_fetch_writes_cache(monkeypatch):
    monkeypatch.setattr(riftcodex, "_fetch", lambda e: [{"riftbound_id": "x1", "name": "X"}])
    assert "x1" in riftcodex.fetch_all_cards(force=True)
    assert "x1" in json.loads(riftcodex.CACHE_FILE.read_text())


# ── M7: web UI controls, auth, gating, XSS, rules ────────────────────────────
@pytest.fixture
def client(rig, monkeypatch, tmp_path):
    from web import app as webapp
    rules = tmp_path / "rules.json"
    rules.write_text((ROOT / "config" / "rules.json").read_text())
    monkeypatch.setattr(webapp, "RULES_FILE", rules)
    monkeypatch.setattr(webapp, "get_inventory_with_bins", lambda limit=1000: [
        {"card_id": "rb_<b>", "card_name": "</script><script>alert(1)</script>", "count": 1,
         "primary_bin": 2}])
    monkeypatch.setattr(webapp, "get_distinct_bins", lambda: [2])
    c = webapp.create_app(token="s3cret").test_client()
    c.auth = {"X-Auth-Token": "s3cret"}
    c.rules = rules
    return c


def test_mutating_endpoints_need_token(client):
    main._set_state("stopped")
    for url in ("/api/bins/1/empty", "/api/bins/empty-all", "/api/pause", "/api/resume",
                "/api/stop", "/api/confirm-clear"):
        assert client.post(url).status_code == 401, url
        assert client.post(url, headers={"X-Auth-Token": "nope"}).status_code == 401, url
    assert client.post("/rules", data={"rules_json": "{}"}).status_code == 401
    assert client.get("/api/status").status_code == 200        # reads stay open


def test_empty_bin_gated_on_pause(client):
    main._set_state("running")
    main._bins.increment(1)
    r = client.post("/api/bins/1/empty", headers=client.auth)
    assert r.status_code == 409 and main._bins.count(1) == 1
    assert client.post("/api/bins/empty-all", headers=client.auth).status_code == 409
    # the bin the machine is paused on may be emptied, others only when paused/stopped
    main._status["state"] = "paused"
    main._status["paused_bin"] = 1
    assert client.post("/api/bins/1/empty", headers=client.auth).status_code == 200
    main._set_state("running")
    main._status["paused_bin"] = 3
    main._bins.increment(3)
    assert client.post("/api/bins/3/empty", headers=client.auth).status_code == 200
    main._set_state("paused", "operator")
    assert client.post("/api/bins/empty-all", headers=client.auth).status_code == 200


def test_pause_resume_stop_between_cards(client, rig):
    assert client.post("/api/pause", headers=client.auth).status_code == 200
    seen = {}

    def hook():
        if main._status["state"] == "paused" and "p" not in seen:
            seen["p"] = main._stats["total"]
            client.post("/api/stop", headers=client.auth)
    rig.sleep_hook = hook
    assert main.run_sorter(engine=Eng(), max_cycles=5) == "stopped"
    assert seen["p"] == 0 and main._stats["total"] == 0          # paused before the first card
    assert "operator" in main._status["message"]
    client.post("/api/resume", headers=client.auth)
    assert main._control["stop"] is False and main._control["pause"] is False
    assert main.run_sorter(engine=Eng(), max_cycles=1) == "stopped"
    assert main._stats["total"] == 1


def test_stop_mid_card_finishes_the_card(client, rig, monkeypatch):
    orig = main._exit_to_cradle

    def exit_and_stop(speed):
        client.post("/api/stop", headers=client.auth)
        orig(speed)
    monkeypatch.setattr(main, "_exit_to_cradle", exit_and_stop)
    assert main.run_sorter(engine=Eng(), max_cycles=5) == "stopped"
    assert main._stats["total"] == 1 and shuttle.state()[:2] == ("home", "level")


def test_confirm_clear_endpoint(client):
    main._set_state("running")
    assert client.post("/api/confirm-clear", headers=client.auth).status_code == 409
    main._set_state("needs_confirm", "x")
    assert client.post("/api/confirm-clear", headers=client.auth).status_code == 200
    assert main.read_machine_state()["confirmed"] is True


def test_inventory_and_rules_are_escaped(client):
    html = client.get("/inventory").get_data(as_text=True)
    assert "</script><script>alert(1)" not in html
    assert "esc(c.name)" in html
    client.rules.write_text('{"rules": [], "x": "</textarea><script>alert(2)</script>"}')
    html = client.get("/rules").get_data(as_text=True)
    assert "</textarea><script>alert(2)" not in html and "&lt;/textarea&gt;" in html


def test_rules_validated_before_save_and_engine_reloads(client):
    before = client.rules.read_text()
    bad = json.dumps({"rules": [{"name": "x", "match": {"type": "Spell"}, "bin": 8}]})
    r = client.post("/rules", data={"rules_json": bad, "token": "s3cret"})
    assert r.status_code == 400 and "bin must be 0-7 or 9" in r.get_data(as_text=True)
    assert client.rules.read_text() == before
    r = client.post("/rules", data={"rules_json": "{oops", "token": "s3cret"})
    assert r.status_code == 400 and client.rules.read_text() == before
    good = json.dumps({"_reject_bin": 9, "rules": [{"name": "All", "match": {"default": True}, "bin": 3}]})
    r = client.post("/rules", data={"rules_json": good, "token": "s3cret"})
    assert r.status_code == 200 and json.loads(client.rules.read_text())["rules"][0]["bin"] == 3
    assert main._control["reload_rules"] is True
    Eng.reloads = 0
    main.run_sorter(engine=Eng(), max_cycles=1)
    assert Eng.reloads == 1 and main._control["reload_rules"] is False


def test_validate_rules_accepts_shipped_rules():
    from web.app import validate_rules
    for f in ("rules.json", "rules.example.json"):
        assert validate_rules(json.loads((ROOT / "config" / f).read_text())) == [], f


def test_web_token_generated_once():
    t1 = main.load_or_create_web_token()
    t2 = main.load_or_create_web_token()
    assert t1 == t2 and len(t1) >= 12
    assert main.check_web_token(t1, t1) and not main.check_web_token("", t1)


# ── identify margin ──────────────────────────────────────────────────────────
def _img_jpeg(seed):
    import numpy as np
    rng = np.random.default_rng(seed)
    arr = (rng.random((64, 48, 3)) * 255).astype("uint8")
    img = Image.fromarray(arr).resize((300, 420))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue(), img


def _flip_bits(h, n):
    import imagehash
    arr = h.hash.copy().flatten()
    arr[:n] = ~arr[:n]
    return imagehash.ImageHash(arr.reshape(h.hash.shape))


def test_identify_rejects_ambiguous_match(monkeypatch):
    import imagehash
    from vision import identify as idm
    jpeg, _ = _img_jpeg(1)
    h = imagehash.phash(Image.open(io.BytesIO(jpeg)).convert("RGB"), hash_size=idm.HASH_SIZE)
    monkeypatch.setattr(idm, "_hash_db_ahash", {})
    monkeypatch.setattr(idm, "_hash_db_dhash", {})
    monkeypatch.setattr(idm, "_card_names", {"a": "A", "b": "B"})
    monkeypatch.setattr(idm, "MIN_MARGIN_BITS", 10)
    # runner-up only 4 bits further away → ambiguous → reject
    monkeypatch.setattr(idm, "_hash_db", {"a": str(h), "b": str(_flip_bits(h, 4))})
    r = idm.identify_with_details(jpeg)
    assert r["card_id"] is None and r["ambiguous"] is True and r["margin"] == 4
    assert r["confidence"] >= idm.MIN_CONF
    # runner-up far away → accepted
    monkeypatch.setattr(idm, "_hash_db", {"a": str(h), "b": str(_flip_bits(h, 60))})
    r = idm.identify_with_details(jpeg)
    assert r["card_id"] == "a" and r["ambiguous"] is False and r["margin"] >= 10
    # margin check disabled
    monkeypatch.setattr(idm, "MIN_MARGIN_BITS", 0)
    monkeypatch.setattr(idm, "_hash_db", {"a": str(h), "b": str(_flip_bits(h, 4))})
    assert idm.identify_with_details(jpeg)["card_id"] == "a"


def test_identify_margin_configurable(monkeypatch, tmp_path):
    from vision import identify as idm
    cfg = tmp_path / "identify.json"
    cfg.write_text('{"min_margin_bits": 17, "min_conf": 0.9}')
    monkeypatch.setattr(idm, "CONFIG_FILE", cfg)
    monkeypatch.setattr(idm, "MIN_MARGIN_BITS", idm.MIN_MARGIN_BITS)
    monkeypatch.setattr(idm, "MIN_CONF", idm.MIN_CONF)
    idm.load_config()
    assert idm.MIN_MARGIN_BITS == 17 and idm.MIN_CONF == 0.9


# ── minors ───────────────────────────────────────────────────────────────────
def test_dry_run_records_nothing(rig):
    assert main.sort_one_card(Eng(), dry_run=True) == main.REJECT_BIN
    assert rig.recorded == []


def test_empty_threshold_is_unified():
    w = (loadcell.WEIGHT_EMPTY_MAX + loadcell.WEIGHT_SINGLE_MIN) / 2 - 0.3   # just above empty
    assert loadcell.classify(w) != "empty" and not loadcell.is_empty(w)
    w = loadcell.WEIGHT_EMPTY_MAX
    assert loadcell.classify(w) == "empty" and loadcell.is_empty(w)
    assert not hasattr(shuttle, "EMPTY_MAX_G")
    assert shuttle._cradle_empty(lambda: loadcell.WEIGHT_EMPTY_MAX - 0.01)
    assert not shuttle._cradle_empty(lambda: loadcell.WEIGHT_EMPTY_MAX + 0.01)


def test_bin_counts_detect_change_with_same_mtime(tmp_path):
    a = main.BinCounts(tmp_path / "c.json", tmp_path / "l.json", main.DEFAULT_BIN_LIMITS)
    b = main.BinCounts(tmp_path / "c.json", tmp_path / "l.json", main.DEFAULT_BIN_LIMITS)
    a.increment(2)
    st = (tmp_path / "c.json").stat()
    assert b.count(2) == 1
    b.empty(2)
    os.utime(tmp_path / "c.json", ns=(st.st_atime_ns, st.st_mtime_ns))   # same mtime as before
    assert a.count(2) == 0                                    # content hash, not mtime
    assert a.version == b.version == 2
    assert not list(tmp_path.glob("*.tmp"))                   # unique tmp files cleaned up


def test_calibration_uses_reference_mass(rig, monkeypatch):
    assert main.CALIBRATION_MASS_G == 5.0
    prompts = []
    monkeypatch.setattr("builtins.input", lambda p="": prompts.append(p) or "")
    seen = {}
    monkeypatch.setattr(loadcell, "calibrate", lambda known_weight_g: seen.setdefault("m", known_weight_g) and 420.0)
    main.calibrate_loadcell()
    assert seen["m"] == 5.0 and any("5.000 g" in p for p in prompts)
    seen.clear()
    main.calibrate_loadcell(12.5)
    assert seen["m"] == 12.5


# ── B2 / config ──────────────────────────────────────────────────────────────
def test_fov_derived_from_scaler_crop(monkeypatch):
    monkeypatch.setattr(camera, "FOV_X_MM", camera.FOV_X_MM)
    monkeypatch.setattr(camera, "FOV_Y_MM", camera.FOV_Y_MM)
    monkeypatch.setattr(camera, "CARD_CROP", camera.CARD_CROP)
    monkeypatch.setattr(camera, "_crop_calibrated", False)
    full = camera.apply_field_of_view((0, 0, 4608, 2592), (4608, 2592))
    assert full == 1.0 and camera.FOV_X_MM == pytest.approx(129.9)
    full_crop = camera.CARD_CROP
    frac = camera.apply_field_of_view((768, 432, 3072, 1728), (4608, 2592))   # 1536×864 mode
    assert frac == pytest.approx(2 / 3) and camera.FOV_X_MM == pytest.approx(86.6, abs=0.1)
    l, t, r, b = camera.CARD_CROP
    assert r - l > full_crop[2] - full_crop[0]                # card covers more pixels
    assert card_detect._view_half_mm() < card_detect.VIEW_HALF_MM


def test_camera_constants():
    assert camera.SENSOR_MODE == (2304, 1296) and camera.DETECT_FPS == 50
    assert camera.LENS_POSITION == pytest.approx(10.0)
    assert card_detect.STOP_LATENCY_S >= 1.5 / camera.DETECT_FPS


def test_machine_config_applies(tmp_path, monkeypatch):
    f = tmp_path / "machine.json"
    f.write_text(json.dumps({"card_detect": {"TRAVEL_SIGN": -1, "BELT_SPEED_MM_S": 120},
                             "camera": {"LENS_POSITION": 9.5}}))
    monkeypatch.setattr(machine_config, "CONFIG_FILE", f)
    monkeypatch.setattr(machine_config, "_cache", None)
    mod = types.SimpleNamespace(TRAVEL_SIGN=1, BELT_SPEED_MM_S=150.0, OTHER=3)
    applied = machine_config.apply(mod, "card_detect", ("TRAVEL_SIGN", "BELT_SPEED_MM_S", "OTHER"))
    assert mod.TRAVEL_SIGN == -1 and mod.BELT_SPEED_MM_S == 120.0 and isinstance(mod.BELT_SPEED_MM_S, float)
    assert mod.OTHER == 3 and set(applied) == {"TRAVEL_SIGN", "BELT_SPEED_MM_S"}
    monkeypatch.setattr(machine_config, "_cache", None)


def test_example_machine_config_matches_code_defaults():
    ex = json.loads((ROOT / "config" / "machine.example.json").read_text())
    for k, v in ex["card_detect"].items():
        assert getattr(card_detect, k) == pytest.approx(v), k
    for k, v in ex["sort"].items():
        assert getattr(main, k) == pytest.approx(v), k
    for k, v in ex["camera"].items():
        assert getattr(camera, k) == v, k
