"""
Audit 4 (ported from /tmp/rb_audit4/tests4/test_operate_sweep.py): a 1- and
2-signal sweep plus a SIGKILL-marker sweep across the FULL operate loop:
start (prepare, assert rest) -> 2 cards -> hopper empty -> idle release ->
operator resume -> prepare (re-assert) -> 2 cards -> hopper empty -> operator
stops. Mimics main(): try: _operate() [finally _shutdown_raises=False] except
Shutdown; finally teardown(). Invariants after every run: no blind move of a
released servo, no move with a card on the cup while released, no clean marker
with a card in the machine or the shuttle off its rest pose, pump / vent / belt
off, teardown ran; and (audit 4 m3) while waiting for the operator only ch1 is
ever released, and never with a card in the machine.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import main
import test_audit2_sweep as TS
from hardware import card_detect, elevator, loadcell, servos, shuttle, vacuum


def rig(monkeypatch, tmp_path):
    rec = TS.setup_rig(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "RulesEngine", lambda f: TS.Eng())
    main._write_machine_state(clean=True, confirmed=False, reason="prev", rest_pose="home_level")
    elevator.mock_set_cards(2)
    rec.waits = 0
    po = vacuum.pump_on

    def pump_on_pick():
        if main._card_at is None:          # a pick: one card leaves the stack
            elevator.mock_set_cards(max(0, elevator._mock_cards - 1))
        po()
    monkeypatch.setattr(vacuum, "pump_on", pump_on_pick)
    rec.released_moves = []

    rec.idle = []

    def await_op(needs_confirm):
        rec.waits += 1
        rec.idle.append((servos.arm_released(), shuttle.released(shuttle.CH_TILT),
                         shuttle.released(shuttle.CH_SHUTTLE), main._card_at))
        rec.events.append(f"await{rec.waits}:{main._status['state']}:nc={needs_confirm}")
        if rec.waits == 1 and main._running:
            elevator.mock_set_cards(2)
            return True
        main._running = False
        return False
    monkeypatch.setattr(main, "_await_operator", await_op)
    # a write while released that changes the pose = a blind move from limp
    sw, aw = shuttle._write, servos._arm_write

    def sw2(ch, a):
        if shuttle._released and shuttle._pos[ch] is not None and abs(a - shuttle._pos[ch]) > 1e-6:
            rec.released_moves.append(("sh", ch, shuttle._pos[ch], a))
        sw(ch, a)

    def aw2(a):
        if servos._arm_released and servos._arm_angle is not None and abs(a - servos._arm_angle) > 1e-6:
            rec.released_moves.append(("arm", servos._arm_angle, a))
        if main._card_at == "cup" and (servos._arm_released or shuttle._released):
            rec.released_moves.append(("arm moved with card on cup while released", a))
        aw(a)
    monkeypatch.setattr(shuttle, "_write", sw2)
    monkeypatch.setattr(servos, "_arm_write", aw2)
    return rec


def run(monkeypatch, tmp_path, fire_at, nsig, marker_check=False):
    rec = rig(monkeypatch, tmp_path)
    rec.n = 0; rec.fire_at = fire_at; rec.nsig = nsig
    rec.marker_bad = []
    if marker_check:
        def check(ev):
            ms = main.read_machine_state()
            if not (ms.get("clean") and ms.get("rest_pose") == "home_level"):
                return
            t, tilt, _ = shuttle.state()
            card = (main._card_at is not None or loadcell._mock_load_g > 0.5
                    or card_detect.MOCK_SCENE.card_x_mm is not None)
            if (t, tilt) != ("home", "level") or card or servos.arm_angle() != servos.ARM_PARK \
                    or vacuum.pump_is_on():
                rec.marker_bad.append((ev, t, tilt, card, servos.arm_angle(), main._status["state"]))
        for mod, name in ((shuttle, "_write"), (servos, "_arm_write")):
            f = getattr(mod, name)
            monkeypatch.setattr(mod, name, lambda *a, f=f, name=name: (f(*a), check(name))[0])
        prev = time.sleep
        monkeypatch.setattr(time, "sleep", lambda x, prev=prev: (prev(x), check("sleep"))[0])
    outcome = None
    main._shutdown_raises = True
    try:
        try:
            try:
                main._operate(False)
                outcome = "returned"
            finally:
                main._shutdown_raises = False
        except main.Shutdown:
            outcome = "Shutdown"
    finally:
        main.teardown()
    ms = main.read_machine_state()
    v = list(rec.violations) + [f"released-move {m}" for m in rec.released_moves]
    if ms.get("clean") and (loadcell._mock_load_g > 0.5 or main._card_at
                            or card_detect.MOCK_SCENE.card_x_mm is not None):
        v.append(f"CLEAN marker with card at={main._card_at}")
    if ms.get("clean") and ms.get("rest_pose") == "home_level" and not shuttle.at_rest():
        v.append(f"CLEAN marker, shuttle not at rest {shuttle.state()[:2]}")
    if rec.pump: v.append("pump left on")
    if rec.vent: v.append("vent left open")
    if rec.belt: v.append("belt left running")
    if not main._tearing_down: v.append("teardown did not run")
    v += [f"marker {b}" for b in rec.marker_bad]
    for arm_rel, ch1_rel, ch2_rel, card in rec.idle:
        if arm_rel or ch2_rel:
            v.append(f"arm / carriage released while waiting ({arm_rel}, {ch2_rel})")
        if ch1_rel and card is not None:
            v.append(f"ch1 released with a card at {card}")
    return rec, outcome, ms, v


def reset():
    main._signals = 0; main._running = True; main._tearing_down = False
    main._marker_armed = False; main._card_at = None; main._cup_hold_since = None
    main._defer_depth = 0; main._shutdown_pending = False
    main._control.update(pause=False, stop=False, resume=False, reload_rules=False)


@pytest.mark.parametrize("nsig", [1, 2])
def test_operate_signal_sweep(monkeypatch, tmp_path, nsig):
    reset()
    rec, outcome, ms, v = run(monkeypatch, tmp_path, None, nsig)
    total = rec.n
    print(f"\nundisturbed: {total} events, outcome {outcome}, waits {rec.waits}, clean={ms['clean']}, viol {v}")
    assert rec.waits == 2 and not v
    assert [r[:3] for r in rec.idle] == [(False, True, False)] * 2      # hopper empty: ch1 only
    bad, outcomes = {}, {}
    for k in range(1, total + 1):
        reset()
        r, outcome, ms, v = run(monkeypatch, tmp_path, k, nsig)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        if v:
            bad[k] = (r.events[k - 1] if k - 1 < len(r.events) else "?", v[:3])
    print(f"nsig={nsig}: {total} points, outcomes {outcomes}, bad {len(bad)}")
    for k, x in list(bad.items())[:15]:
        print("  ", k, x)
    assert not bad


def test_operate_sigkill_marker(monkeypatch, tmp_path):
    reset()
    rec, outcome, ms, v = run(monkeypatch, tmp_path, None, 1, marker_check=True)
    print(f"\nevents {rec.n}, marker-unsafe instants {len(rec.marker_bad)}")
    for b in rec.marker_bad[:10]:
        print("  ", b)
    assert not v
