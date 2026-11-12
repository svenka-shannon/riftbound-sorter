"""Adversarial sweep (ported from the second audit's scratch tests): deliver 1
or 2 stop signals at EVERY hardware event of a 2-card run, mimic main():
run_sorter in try/except Shutdown, finally teardown(). Check invariants after
each run. Port changes: the rig homes the shuttle explicitly (shuttle.init()
never homes, audit M7) and tares as a calibrated machine (the only tare that
stores the empty reference besides route-proven ones, audit M1)."""
import os, sys, time
from pathlib import Path
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
import main
from hardware import card_detect, conveyor, elevator, loadcell, servos, shuttle, vacuum
ORIG_SW = shuttle._write
ORIG_AW = servos._arm_write


class Eng:
    reject_bin = 9
    def __init__(self, b=2): self.b = b
    def assign_bin(self, card): return self.b
    def describe_bin(self, b): return f"Bin {b}"
    def load(self): pass


def setup_rig(monkeypatch, tmp_path):
    rec = SimpleNamespace(events=[], pump=False, vent=False, belt=False, n=0, fire_at=None,
                          nsig=1, violations=[], fired=False)
    monkeypatch.setattr(main, "_bins", main.BinCounts(tmp_path / "c.json", tmp_path / "l.json",
                                                      main.DEFAULT_BIN_LIMITS))
    monkeypatch.setattr(main, "identify", lambda j: ("rb_001", 0.95))
    monkeypatch.setattr(main.riftcodex, "get_card", lambda cid: {"name": "Jinx"})
    monkeypatch.setattr(main.inventory, "record_scan", lambda *a: None)

    def tick(what):
        rec.n += 1
        rec.events.append(what)
        if rec.fire_at is not None and rec.n == rec.fire_at and not rec.fired:
            rec.fired = True
            for _ in range(rec.nsig):
                main._on_signal()

    monkeypatch.setattr(time, "sleep", lambda s: tick("sleep"))
    def belt(state, name):
        def f(*a, **k):
            rec.belt = state; tick(name)
        return f
    monkeypatch.setattr(conveyor, "run", belt(True, "run"))
    monkeypatch.setattr(conveyor, "brake", belt(False, "brake"))
    monkeypatch.setattr(conveyor, "stop", belt(False, "stop"))

    def pump(state):
        def f():
            if not state and rec.pump and main._card_at == "cup":
                a = servos.arm_angle()
                if not (abs(a - servos.ARM_PICK) <= 2 or abs(a - servos.ARM_DROP) <= 2):
                    rec.violations.append(f"pump off with card on cup mid-arc at {a:.1f} deg")
            rec.pump = state; tick("pump_on" if state else "pump_off")
        return f
    monkeypatch.setattr(vacuum, "pump_on", pump(True))
    monkeypatch.setattr(vacuum, "pump_off", pump(False))
    def vent(state):
        def f():
            rec.vent = state; tick("vent")
        return f
    monkeypatch.setattr(vacuum, "vent_open", vent(True))
    monkeypatch.setattr(vacuum, "vent_close", vent(False))

    orig_w = ORIG_SW
    def sw(ch, a):
        if ch == shuttle.CH_SHUTTLE and shuttle._pos[ch] is not None and abs(a - shuttle._pos[ch]) > 1e-6:
            if shuttle._tilt_state != "hold" or abs(shuttle._pos[shuttle.CH_TILT] - shuttle.TILT_ANGLES["hold"]) > 0.5:
                rec.violations.append(f"carriage moved with tilt {shuttle._tilt_state} @ {shuttle._pos[shuttle.CH_TILT]}")
        orig_w(ch, a); tick("shuttle")
    monkeypatch.setattr(shuttle, "_write", sw)
    orig_a = ORIG_AW
    def aw(a):
        orig_a(a); tick("arm")
    monkeypatch.setattr(servos, "_arm_write", aw)

    def landed():
        loadcell.mock_set_load(loadcell.MOCK_CARD_G + loadcell._mock_load_g)
        card_detect.MOCK_SCENE.card_x_mm = None      # card left the belt
    monkeypatch.setattr(main, "_mock_cradle_receives_card", landed)
    loadcell.mock_set_load(0.0)
    s = card_detect.MOCK_SCENE
    s.card_x_mm, s.auto_card, s.visible, s.running = None, True, True, False
    s.speed_mm_s = card_detect.BELT_SPEED_MM_S * 1.1
    elevator.mock_set_cards(150)
    servos.init(); servos.arm_park(); shuttle.init(); shuttle.home()
    elevator.init(); assert elevator.home()
    loadcell.tare(calibration=True); shuttle.level()
    for k in main._stats: main._stats[k] = 0
    main._set_state("running")
    return rec


def run_once(monkeypatch, tmp_path, fire_at, nsig, bin_full_after=None):
    rec = setup_rig(monkeypatch, tmp_path)
    if bin_full_after:
        main._bins.limits[2] = 1          # 2nd card pauses on a full bin
    rec.n = 0; rec.fire_at = fire_at; rec.nsig = nsig
    main.mark_running()
    outcome = None
    try:
        try:
            outcome = main.run_sorter(engine=Eng(), max_cycles=2)
        except main.Shutdown:
            outcome = "Shutdown"
    finally:
        # bin-full pause would wait forever: run_sorter only leaves it on stop; ensure stop
        main.teardown()
    ms = main.read_machine_state()
    card_on_cradle = loadcell._mock_load_g > 0.5
    card_on_belt = card_detect.MOCK_SCENE.card_x_mm is not None and card_detect.MOCK_SCENE.card_x_mm < card_detect.BELT_END_X_MM
    if ms.get("clean") and (card_on_cradle or card_on_belt or main._card_at):
        rec.violations.append(f"CLEAN marker with card cradle={card_on_cradle} belt={card_on_belt} at={main._card_at}")
    if rec.pump: rec.violations.append("pump left on")
    if rec.vent: rec.violations.append("vent left open")
    if rec.belt: rec.violations.append("belt left running")
    return rec, outcome, ms


@pytest.mark.parametrize("nsig", [1, 2])
def test_signal_sweep(monkeypatch, tmp_path, nsig):
    # count events of an undisturbed run first
    rec, _, _ = run_once(monkeypatch, tmp_path, None, nsig)
    total = rec.n
    bad = {}
    outcomes = {}
    for k in range(1, total + 1):
        main._signals = 0; main._running = True; main._tearing_down = False
        main._marker_armed = False; main._card_at = None
        main._control.update(pause=False, stop=False, resume=False, reload_rules=False)
        r, outcome, ms = run_once(monkeypatch, tmp_path, k, nsig)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        if r.violations:
            bad[k] = (r.events[k - 1] if k - 1 < len(r.events) else "?", r.violations[:3])
    print(f"\nnsig={nsig}: {total} injection points, outcomes {outcomes}, violations at {len(bad)} points")
    for k, v in list(bad.items())[:12]:
        print("  ", k, v)
    assert not bad
