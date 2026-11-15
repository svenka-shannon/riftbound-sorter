"""
Riftbound Card Sorter — option B (turntable picker, cad_b/) sort cycle
=====================================================================

main.py is still the program (`python main.py`, same CLI, same systemd unit,
same web UI and JSON API). With "machine": "b" in config/machine.json it calls
install() below, which swaps in the machine-specific functions listed in
HOOKS. Everything else is main.py's, unchanged: the state machine
(running / paused / stopped / jam / hopper_empty / error / needs_confirm),
pause / stop at card boundaries, the second-signal Shutdown deferred while a
card is on the cup (_no_shutdown), the clean / unclean record + "Machine
clear", bin counts and limits, the rules engine, the web endpoints.

One card (cards are raw and valuable: when in doubt reject it or stop, and
NEVER drop a card mid-swing):
  1. yaw to the hopper (approached from below) and CHECK the home switch reads
     released — pressed = lost steps → stop (never re-zeroed during a run)
  2. lower until touch. The hopper floor has a Ø32 hole under the cup (cad
     029e479): with no card left the cup drops through and never touches, so
     no touch with the cup below the floor level = HOPPER EMPTY, a clean stop
     (nothing was picked). The descent is bounded HOPPER_BOUND_MM below the
     previous stack top; no touch by that bound while still above the floor =
     a contact fault → stop. On touch: pump on, SEAL_OVERTRAVEL_MM, SEAL_S, lift
  3. yaw to the scan bed; lower until touch, PLACE_OVERTRAVEL_MM; pump off,
     BLEED_S (pin-hole bleed, no vent valve), slow peel, lift to full
  4. yaw clear of the camera (clear_yaw, default the hopper angle); weigh the
     bed (weight MUST have appeared: else the pick failed → stop; a touch at
     floor height that delivered nothing = the last card was not picked →
     stop), capture, identify, decide the bin (double / unknown weight /
     unidentified → reject) — a full target bin PAUSES here with the card
     waiting FLAT ON THE BED
  5. yaw back to the bed; touch-down, pump, seal, lift; the bed must read ~0 g
     again (else the card is put back down on the bed and the machine stops)
  6. yaw to the target bin; lower until touch, bounded by where the bin's pile
     can be (its card count); an empty bin: the floor stops it; release, lift
  7. count the card, re-tare the (proven empty) bed, yaw back to the hopper
Steps 2-3 and 5-6 (card on the cup) run inside main._no_shutdown(): a second
stop signal waits until the card is down.

Every yaw move goes through hardware/yaw.py, which refuses to move unless the
lift is at full height with the cup hanging free (lift.yaw_permitted), keeps
the hard limits [-64, 175] and approaches stations from below.

One hardware lock (_hw_lock, re-entrant): every hook that moves anything —
the cycle, prepare, make-safe, idle park, re-assert, teardown, --calibrate —
holds it, and every manual (web) command tries to take it WITHOUT waiting and
is refused as busy (ManualBusy) if the sorter holds it. Nothing is ever moved
by two threads at once.

A card held on the cup is NEVER let go except over the bed or a bin:
  * resting on a station (contact open, lift low): let go right there
    (hopper → back on the stack, bed → on the bed, bin → in the bin uncounted);
  * at full lift over a known station: lower until touch there and let go;
  * anywhere else (yaw position lost, mid-move error) or if lowering fails: the
    card stays HELD (pump ON), with NO time limit on B (the R385 is a diaphragm
    pump: against a sealed cup + pin-hole bleed it draws less than at free
    flow, so a long hold is wear and noise, not a heat hazard), and the
    operator is told where it would fall. The record says "pump_hold": the
    relay is driven through pigpiod, so the pump keeps holding across a crash
    or service stop, scripts/safe_outputs.py leaves it on, and the next start
    keeps it on until "Machine clear" (the operator took the card off).
The yaw never moves in make-safe.

Rest pose (clean record rest_pose "parked"): no card in the machine; the arm is
parked at park_yaw (inside the home cam, nothing under the cup) when paused /
stopped / shut down. Only then does the lift go limp at exit; after any other
stop the PCA9685 keeps driving, so the lift holds its height. The next start
re-asserts full lift with one write (upward is always clear) and homes.
After an unclean stop nothing moves until "Machine clear".

Start-up (prepare_machine): lift to full; contact must read closed; write the
TMC2209 config; home the yaw (bounded by the saved position hint, at the
homing current) or, if still homed from the previous run in this process,
verify the edge; empty-bed check against the stored reference, tare; touch
self-test on the empty bed; yaw to the hopper.

Manual / calibration API (status(), home(), jog_yaw(), goto_station(),
set_lift(), lift_full(), probe_touch(), pump(), motor_off(),
declare_position(), save_*()): for the web UI (web/app.py /api/b/...). Every
refusal raises ManualRefused (→ 409): run in progress (including paused),
sorter busy (ManualBusy), not homed, interlock, limits, pump on while asking
for yaw, pump off away from a station. The first manual command marks the
machine NOT clean, so sorting needs "Machine clear" afterwards.
"""

from __future__ import annotations

import functools
import sys
import threading
import time

import main as M
from hardware import b_calibration as cal
from hardware import b_geometry as geo
from hardware import camera, instance, lift, loadcell, machine_config, touch, vacuum, yaw
from hardware.lift import LiftError, TouchFault
from hardware.loadcell import LoadCellError

_MOCK = M.MOCK_HARDWARE

# ── Timing / tuning (config/machine.json "b_sort") ───────────────────────────
SEAL_S = 0.3                 # pump on, cup on the card → seal before lifting
SEAL_OVERTRAVEL_MM = 3.0     # after touch-down when picking (presses the bellows)
PLACE_OVERTRAVEL_MM = 2.0    # after touch-down when setting a card down
# Overtravel is measured from the last height at which the contact still read
# closed (lift.lower_until_touch), and one PCA9685 count moves the cup ~1.7 mm,
# so the real slider compression is overtravel − (0..1.7) mm: keep it ≥ 2 mm
# wherever the cup must actually rest (seal, place, self-test).
BLEED_S = 0.8                # pump off → the pin-hole bleed lets go of the card
PEEL_MM = 6.0                # first lift after a release, slowly
PEEL_S = 0.5
WEIGH_SETTLE_S = 0.3
TARE_SETTLE_S = 0.3
RESUME_DELAY_S = 2.0
CALIBRATION_MASS_G = 5.0
TOUCH_SELFTEST = True        # start-up: lower onto the empty bed, check touch + scale
SELFTEST_MIN_G = 5.0         # the bed must feel at least this with the cup resting on it
SELFTEST_WINDOW_DEG = 1.0    # touch within this of the calibrated scan touch_th (~3.8 mm)
SELFTEST_OVERTRAVEL_MM = 2.5 # the empty cup must REST on the bed for the scale check
EDGE_CHECK_EVERY = 20        # cards between home-edge checks (0: only at parks)
MANUAL_PUMP_MAX_S = 60.0     # manual pump-on: switched off after this IF the cup rests at a station
HOPPER_BOUND_MM = 5.0        # next hopper touch must come within this below the previous one
BIN_BOUND_MM = 3.0           # bin pile top expected at floor + count·0.33 mm; descent bound below it
BIN_BOUND_FRAC = 0.10        # ... plus this fraction of the pile height (card thickness spread)
FLOOR_TOUCH_TOL_DEG = 0.5    # a hopper touch this close to floor_th = the last card
FLOOR_PASS_MM = 1.5          # cup lip this far below the hopper floor top = through the hole

machine_config.apply(sys.modules[__name__], "b_sort", (
    "SEAL_S", "SEAL_OVERTRAVEL_MM", "PLACE_OVERTRAVEL_MM", "BLEED_S", "PEEL_MM", "PEEL_S",
    "WEIGH_SETTLE_S", "TARE_SETTLE_S", "RESUME_DELAY_S", "CALIBRATION_MASS_G",
    "TOUCH_SELFTEST", "SELFTEST_MIN_G", "EDGE_CHECK_EVERY", "MANUAL_PUMP_MAX_S",
    "HOPPER_BOUND_MM", "BIN_BOUND_MM", "BIN_BOUND_FRAC"))

REST_POSE = "parked"
RELEASE_ZONES = ("scan",) + tuple(f"bin{n}" for n in geo.BIN_NUMS) + ("reject",)  # bed or a bin
CARD_PLACES = {"cup": "on the cup", "bed": "on the scan bed",
               "bin": "in a bin but NOT counted (add it to that bin's count by hand)",
               "unknown": "somewhere unknown (nothing arrived on the bed: on the cup, back in "
                          "the hopper or dropped)"}


# ── Outcomes (main.py's classes, so its loop handles them unchanged) ─────────
class YawFault(M.StopMachine):
    """Yaw refused / failed (interlock, limit, homing, pigpio)."""
    state = "error"


class LostStepsStop(M.StopMachine):
    state = "error"


class LiftFault(M.StopMachine):
    """Lift or touch contact misbehaved."""
    state = "error"


class PickFailed(M.Jam):
    """A card did not arrive where the scale says it must be."""


class LastCardNotPicked(PickFailed):
    """Touch at the hopper floor height (the last card) and nothing arrived on
    the bed. A fault, not "empty" (an empty hopper never touches: floor hole)."""


class BedNotEmpty(M.Jam):
    pass


# ── state ────────────────────────────────────────────────────────────────────
_hw_lock = threading.RLock()     # held by every hook that moves hardware (see the docstring)
_cards_since_edge = 0
_fault = None                    # reason the machine must not be called clean (lost steps at park)
_manual_used = False
_pump_timer = None
_last_hopper_closed = None       # th just above the previous hopper touch (descent bound)


def _hw(fn):
    """Run fn holding the hardware lock (re-entrant: hooks call each other)."""
    @functools.wraps(fn)
    def wrapper(*a, **k):
        with _hw_lock:
            return fn(*a, **k)
    return wrapper


def _status_pose():
    M._status["yaw_deg"] = None if yaw.position_deg() is None else round(yaw.position_deg(), 3)
    M._status["lift_th"] = None if lift.th() is None else round(lift.th(), 2)
    M._status["station"] = cal.station_at(yaw.position_deg())


# ── motion helpers (driver errors → main's stop classes) ─────────────────────
def _goto_yaw(deg: float, approach: bool, what: str):
    try:
        yaw.move_to(deg, approach=approach, tick=M._beat)
    except yaw.YawInterlockError as exc:
        raise YawFault(f"yaw to {what} refused: {exc}") from exc
    except yaw.YawLimitError as exc:
        raise YawFault(f"yaw to {what}: {exc} — check config/b_calibration.json") from exc
    except yaw.YawNotHomed as exc:
        raise YawFault(f"yaw to {what}: {exc}") from exc
    except Exception as exc:              # YawError, pigpio socket errors, ...
        raise YawFault(f"yaw to {what} failed: {exc!r} — yaw position no longer trusted") from exc
    finally:
        _status_pose()


def _goto(name: str):
    _goto_yaw(cal.station_yaw(name), True, name)


def _goto_clear():
    _goto_yaw(cal.clear_yaw(), False, "the camera-clear pose")


def _lower(name: str, overtravel_mm: float, limit_th: float | None = None) -> lift.TouchResult:
    st = cal.station(name)
    limit = st["limit_th"] if limit_th is None else max(st["limit_th"], limit_th)
    limit = min(limit, st["approach_th"] - 1e-3)
    try:
        return lift.lower_until_touch(st["approach_th"], limit, overtravel_mm, tick=M._beat)
    except TouchFault as exc:
        raise LiftFault(f"at {name}: {exc}") from exc
    except LiftError as exc:
        raise LiftFault(f"lowering at {name} failed: {exc}") from exc
    finally:
        _status_pose()


def _lift_full(peel: bool = False):
    try:
        if peel:
            lift.raise_by_mm(PEEL_MM, PEEL_S)
        lift.to_full()
    except LiftError as exc:
        raise LiftFault(f"lift to full height failed: {exc}") from exc
    finally:
        _status_pose()


def _release_card(where: str):
    vacuum.release(bleed_s=BLEED_S)
    M._set_card_at(where)


def _hopper_check():
    try:
        yaw.check_released("the hopper")
    except yaw.LostSteps as exc:
        raise LostStepsStop(f"{exc} — the arm may not be where it should; check it, then confirm "
                            "(it re-homes on the next start)") from exc


def _edge_check():
    try:
        yaw.verify_edge(tick=M._beat)
    except yaw.LostSteps as exc:
        raise LostStepsStop(f"home edge check: {exc} — check the arm, then confirm") from exc
    except yaw.YawError as exc:
        raise YawFault(f"home edge check failed: {exc}") from exc
    finally:
        _status_pose()


def _park():
    """Edge check on the way down, then park_yaw (switch must read pressed there)."""
    _edge_check()
    _goto_yaw(cal.park_yaw(), False, "park")
    if not yaw.home_pressed():
        yaw.disable(distrust=True)
        raise LostStepsStop(f"home switch released at the park pose ({cal.park_yaw():g} deg): "
                            "steps were lost")


def _cards_estimate(th_touch: float) -> int:
    return max(0, round((geo.lip_z(th_touch) - geo.FLOOR_Z_MM) / geo.CARD_T_MM))


def _floor_th():
    return cal.station("hopper").get("floor_th")


def _touch_at_floor(res) -> bool:
    floor = _floor_th()
    return floor is not None and res.th_touch is not None and res.th_touch <= floor + FLOOR_TOUCH_TOL_DEG


def _hopper_limit() -> float | None:
    """Descent bound at the hopper: HOPPER_BOUND_MM below the previous touch."""
    if _last_hopper_closed is None:
        return None
    try:
        return geo.th_below(_last_hopper_closed, HOPPER_BOUND_MM)
    except ValueError:
        return None


def _went_through_floor(res) -> bool:
    """No touch and the cup lip got below the hopper floor top: it is in the hole."""
    floor = _floor_th()
    if floor is None:
        return True                       # no floor height calibrated: any no-touch = empty
    return geo.lip_z(res.th_end) <= geo.lip_z(floor) - FLOOR_PASS_MM


def _bin_limit(station: str, bin_num: int) -> float | None:
    """Descent bound at a bin: below where its pile of `count` cards must be."""
    n = M._bins.count(bin_num)
    if n <= 0:
        return None
    pile = n * geo.CARD_T_MM
    try:
        return geo.th_for_lip(geo.FLOOR_Z_MM + pile - BIN_BOUND_MM - BIN_BOUND_FRAC * pile)
    except ValueError:
        return None


# ── bed (scale) ──────────────────────────────────────────────────────────────
def _tare_bed(first: bool = False, anchored: bool = False):
    """Empty bed (arm off it) → check empty → tare; same persistence rule as v2."""
    time.sleep(TARE_SETTLE_S)
    if first:
        persist = False
    else:
        anchored = loadcell.tare_anchored()
        persist = anchored
        w = M._weigh("checking the bed is empty")
        if not loadcell.is_empty(w):
            raise BedNotEmpty(f"bed not empty before tare ({w:.2f} g) — remove the card")
    try:
        loadcell.tare(anchored=anchored, persist=persist)
    except LoadCellError as exc:
        raise M.LoadCellFault(f"load cell tare failed: {exc}") from exc


def _startup_bed_check(confirmed: bool):
    """Like main._startup_cradle_check: compare with the stored empty-bed reference
    BEFORE taring (a card left on the bed is never tared away)."""
    time.sleep(TARE_SETTLE_S)
    try:
        w = loadcell.grams_vs_empty_reference()
    except LoadCellError as exc:
        raise M.LoadCellFault(f"load cell failed at start-up: {exc}") from exc
    if w is None:
        if not confirmed:
            raise M.NeedsConfirm("no stored empty-bed reference (first start or old calibration) — "
                                 "run `main.py --calibrate`, or check the bed is EMPTY and confirm")
        print("[b] WARNING: no stored empty-bed reference — taring on the operator's word; run "
              "`main.py --calibrate`")
        _tare_bed(first=True, anchored=False)
        return
    if w > loadcell.STARTUP_EMPTY_MAX_G:
        raise M.NeedsConfirm(f"card on the scan bed — remove it ({w:.2f} g above the empty-bed "
                             "reference), then confirm")
    if w < -loadcell.STARTUP_EMPTY_MAX_G:
        raise M.LoadCellFault(f"bed reads {w:.2f} g BELOW the stored empty reference — load cell "
                              "fault or drift; check it, then re-run `main.py --calibrate`")
    _tare_bed(first=True, anchored=True)


def _touch_selftest():
    """Lower the empty cup onto the empty bed: touch near touch_th, the scale
    feels the slider, and reads ~0 again once lifted."""
    st = cal.station("scan")
    _goto("scan")
    res = _lower("scan", SELFTEST_OVERTRAVEL_MM)
    try:
        if not res.touched:
            raise LiftFault(f"touch self-test: the contact never opened on the empty bed down to th "
                            f"{st['limit_th']:g} — contact wire / slider, or scan calibration")
        if abs(res.th_touch - st["touch_th"]) > SELFTEST_WINDOW_DEG:
            raise LiftFault(f"touch self-test: touched the bed at th {res.th_touch:.2f}, calibrated "
                            f"{st['touch_th']:.2f} (±{SELFTEST_WINDOW_DEG:g}) — re-calibrate the lift "
                            "(servo map / scan touch_th) or check the bed")
        time.sleep(WEIGH_SETTLE_S)
        w = M._weigh("touch self-test (cup resting on the bed)")
        if w < SELFTEST_MIN_G:
            raise M.LoadCellFault(f"touch self-test: the bed felt only {w:.2f} g with the cup resting "
                                  f"on it (expected ≥ {SELFTEST_MIN_G:g} g) — load cell / HX711 wiring")
    finally:
        _lift_full()
    time.sleep(WEIGH_SETTLE_S)
    w = M._weigh("touch self-test (cup lifted)")
    if not loadcell.is_empty(w):
        raise M.LoadCellFault(f"touch self-test: bed reads {w:.2f} g after the cup lifted — the bed "
                              "does not return to zero (friction / cable on the bed?)")


# ── the cycle ────────────────────────────────────────────────────────────────
@_hw
def sort_one_card(engine, dry_run: bool = False) -> int:
    """One card, hopper → bed → bin (see the module docstring). Returns the bin.
    Raises like main.sort_one_card: HopperEmpty / Jam / StopRequested / errors
    (stop), BinFull (pause, card waiting on the bed), Shutdown. On ANY
    exception _make_safe() runs first."""
    global _cards_since_edge, _last_hopper_closed
    try:
        if EDGE_CHECK_EVERY and _cards_since_edge >= EDGE_CHECK_EVERY:
            _edge_check()
            _cards_since_edge = 0
        # 1. hopper + lost-step check
        _goto("hopper")
        _hopper_check()
        # 2. pick
        res = _lower("hopper", SEAL_OVERTRAVEL_MM, _hopper_limit())
        if not res.touched:
            _lift_full()
            if _went_through_floor(res):
                _last_hopper_closed = None
                if M._stop_wanted():
                    raise M.StopRequested("stop requested")
                raise M.HopperEmpty("hopper empty (the cup went through the floor hole without a "
                                    "touch) — refill and resume")
            raise LiftFault(f"no touch at the hopper within {HOPPER_BOUND_MM:g} mm below the previous "
                            "stack top, and the cup is still above the floor — touch contact fault, or "
                            "cards were taken out while running. Check, then confirm")
        _last_hopper_closed = res.th_closed
        at_floor = _touch_at_floor(res)
        M._status["cards_remaining_estimate"] = _cards_estimate(res.th_touch)
        with M._no_shutdown():
            vacuum.pump_on()
            M._set_card_at("cup")
            time.sleep(SEAL_S)
            _lift_full()
            # 3. set it down on the bed
            _goto("scan")
            placed = _lower("scan", PLACE_OVERTRAVEL_MM)
            _release_card("bed")          # touched, or at the limit just above / on the bed
            _lift_full(peel=True)
        if not placed.touched:
            raise LiftFault("the touch contact did not open on the bed — card released at the bed "
                            "limit; check the contact")
        # 4. clear the camera, weigh, look
        _goto_clear()
        time.sleep(WEIGH_SETTLE_S)
        weight_g = M._weigh("weighing the card on the bed")
        weight_class = loadcell.classify(weight_g)
        M._status["last_weight_g"] = round(weight_g, 2)
        if weight_class == "empty":
            M._set_card_at("unknown")
            if at_floor:
                raise LastCardNotPicked(
                    f"the cup touched at the hopper floor height (the last card) but nothing arrived "
                    f"on the bed ({weight_g:.2f} g) — check the cup, the hopper and the bins, then "
                    "confirm")
            raise PickFailed(f"no card arrived on the bed ({weight_g:.2f} g) — the pick at the hopper "
                             "failed, or the card is still on the cup / was dropped. Check the cup, "
                             "hopper and bins, then confirm")
        try:
            jpeg = camera.capture_card_jpeg()
        except camera.CameraTimeout as exc:
            raise M.CameraFault(f"{exc} — the card is on the scan bed; remove it, then confirm") from exc
        card_id, confidence, card = M._identify(jpeg)
        if weight_class == "double":
            M._stats["double_picks"] += 1
        elif weight_class == "unknown":
            M._stats["weight_unknown"] += 1
        elif card_id is None or card is None:
            M._stats["unknowns"] += 1
        pending = M._decide(engine, card_id, confidence, card, weight_g, weight_class, dry_run)
        print(f"[b] {pending.card_name} ({confidence:.0%}, {weight_g:.2f} g) → bin {pending.bin_num} "
              f"[{engine.describe_bin(pending.bin_num)}; {pending.reason}]")
        return _route_from_bed(pending)
    except M.BinFull:
        _make_safe()
        raise
    except BaseException:
        _make_safe()
        raise


@_hw
def _route_pending(p) -> int:
    """A card that waited on the bed for its bin to be emptied."""
    try:
        return _route_from_bed(p)
    except BaseException:
        _make_safe()
        raise


def _put_back_on_bed():
    """Whatever the cup holds goes back down onto the bed."""
    res = _lower("scan", PLACE_OVERTRAVEL_MM)
    _release_card("bed")
    _lift_full(peel=True)
    return res


def _route_from_bed(p) -> int:
    """Steps 5-7: re-pick from the bed, verify by weight, place in the bin, count."""
    global _cards_since_edge
    if M._bins.is_full(p.bin_num):
        raise M.BinFull(p)
    station = geo.bin_station(p.bin_num)
    _goto("scan")
    res = _lower("scan", SEAL_OVERTRAVEL_MM)
    if not res.touched:
        _lift_full()
        raise LiftFault("no touch on the card on the bed down to the scan limit — contact fault; the "
                        "card is on the bed")
    with M._no_shutdown():
        vacuum.pump_on()
        M._set_card_at("cup")
        time.sleep(SEAL_S)
        _lift_full()
        time.sleep(WEIGH_SETTLE_S)
        w = M._weigh("checking the card left the bed")
        if not loadcell.is_empty(w):
            # not picked (or only partly): put it back flat on the bed, then stop
            _put_back_on_bed()
            raise PickFailed(f"re-pick from the bed failed ({w:.2f} g still on the bed) — the card "
                             "was put back on the bed; check the cup seal, then confirm")
        _goto(station)
        bound = _bin_limit(station, p.bin_num)
        placed = _lower(station, PLACE_OVERTRAVEL_MM, bound)
        _release_card("bin")              # over its bin: touched, or at the bound / floor limit
        _lift_full(peel=True)
    M._set_card_at(None)
    M._count_and_record(p)
    _tare_bed()
    if not placed.touched:
        where = (f"where bin {p.bin_num}'s pile of {M._bins.count(p.bin_num) - 1} cards should be — was "
                 "the bin emptied without resetting its count, or is the touch contact faulty?"
                 if bound is not None else f"at {station}'s floor — check the touch contact")
        raise LiftFault(f"no touch {where} The card was released over the bin and counted; check, "
                        "then confirm")
    _cards_since_edge += 1
    _goto("hopper")
    return p.bin_num


# ── make-safe / rest / teardown (main.py hooks) ──────────────────────────────
def _held_card_landing(angle=None) -> tuple[str, str]:
    y = yaw.position_deg() if angle is None else angle
    if y is None:
        return "unknown", "arm position unknown — it may fall anywhere along the arm's swing"
    name = cal.station_near(y)
    th = lift.th()
    lip = geo.lip_z(th) if th is not None else None
    if name is None:
        return "between", (f"arm at yaw {y:.1f} deg, between pockets: it would fall across a pocket "
                           "wall and may be bent — take it off the cup by hand")
    base = geo.BED_TOP_Z_MM if name == "scan" else geo.FLOOR_Z_MM
    drop = "" if lip is None else f" from up to {max(0.0, lip - base):.0f} mm"
    return name, f"arm at yaw {y:.1f} deg over {name}: it would fall{drop} into / onto {name}"


def _station_here():
    return cal.station_at(yaw.position_deg()) if yaw.homed() else None


def _secure_cup():
    """A card on the cup is put down at the station the arm is at, or held."""
    if M._card_at != "cup":
        vacuum.pump_off()
        return
    st = _station_here()
    where = {"hopper": None, "scan": "bed"}.get(st, "bin")
    last = None
    with M._no_shutdown():
        if st is not None:
            for _ in range(2):
                try:
                    resting = lift.th() is not None and not lift.at_full_lift() and touch.is_open()
                    if not resting:
                        if not lift.at_full_lift():
                            lift.to_full()
                        _lower(st, PLACE_OVERTRAVEL_MM)
                    _release_card(where)
                    lift.to_full()
                    print(f"[b] card on the cup put down at {st}")
                    return
                except Exception as exc:
                    last = exc
                    print(f"[b] putting the card down at {st} failed: {exc!r}")
        if M._cup_hold_since is None:
            M._cup_hold_since = time.monotonic()
        try:      # the record says "pump_hold" BEFORE anything else can happen to the process
            M._write_machine_state(clean=False, confirmed=False,
                                   reason=f"card held on the cup: {_held_card_landing()[1]}")
        except Exception as exc:
            print(f"[b] could not record the held card: {exc!r}")
        raise M.CupNotSecured(f"card held on the cup ({_held_card_landing()[1]}); pump left ON so it "
                              f"is not dropped (no time limit). {M.CUP_HELD_MSG}") from last


@_hw
def _make_safe(hold_cradle: bool = True):
    """Card on the cup put down or held, pump off otherwise, lift up. The yaw never moves."""
    with M._no_shutdown():
        M._try(_secure_cup)
        if M._card_at != "cup":
            M._try(vacuum.pump_off)
            if lift.th() is not None and not lift.at_full_lift():
                M._try(lift.to_full)


def _cup_hold_watch():
    """Operator wait with a card held on the cup: say so. B never switches the
    pump off on a timer (see the docstring); "Machine clear" does, once the
    operator has taken the card off."""
    if M._card_at != "cup" or not vacuum.pump_is_on():
        M._cup_hold_since = None
        return
    if M._cup_hold_since is None:
        M._cup_hold_since = time.monotonic()
    state = M._status.get("state")
    if state not in M.CONFIRM_STATES:
        state = "needs_confirm"
    msg = (f"{M.CUP_HELD_MSG}: {_held_card_landing()[1]}. The pump keeps holding it (no time limit). "
           "Take it off the cup by hand, then press 'Machine clear' (the pump then stops)")
    if M._status.get("message") != msg or M._status.get("state") != state:
        M._set_state(state, msg)


def _write_machine_state(**fields):
    """main._write_machine_state + "pump_hold" (card held on the cup with the pump on),
    read by scripts/safe_outputs.py and by the next start's init_hardware()."""
    fields.setdefault("pump_hold", bool(M._card_at == "cup" and vacuum.pump_is_on()))
    data = instance.write_state(M.MACHINE_STATE_FILE, **fields)
    M._status["machine_state"] = data


def _pose_at_rest() -> bool:
    return (lift.at_full_lift() and yaw.homed()
            and abs(yaw.position_deg() - cal.park_yaw()) < 0.05)


@_hw
def _release_idle():
    """Idle at rest with no card: park the arm (hopper free for refilling). Never raises."""
    global _fault
    if M._card_at is not None or not yaw.homed() or not lift.at_full_lift() or _pose_at_rest():
        return
    try:
        _park()
        _status_pose()
    except Exception as exc:
        _fault = str(exc)
        M._control["stop"] = True
        M._set_state("error", f"parking failed: {exc}")
        try:
            M._write_machine_state(clean=False, confirmed=False, reason=f"parking failed: {exc}")
        except Exception:
            pass


@_hw
def _reassert_rest_pose():
    global _last_hopper_closed
    _last_hopper_closed = None            # the operator may have changed the hopper while paused
    if _fault or not yaw.homed():
        raise LostStepsStop(_fault or "yaw position no longer trusted — check the arm, then confirm")
    if not lift.at_full_lift():
        _lift_full()


def _on_confirmed_start():
    """Machine clear: any held card has been taken off the cup — the pump stops."""
    global _fault, _manual_used, _last_hopper_closed
    if vacuum.pump_is_on():
        vacuum.release(bleed_s=BLEED_S)
    M._set_card_at(None)
    M._cup_hold_since = None
    _fault = None
    _manual_used = False
    _last_hopper_closed = None


def _assess_clean() -> tuple[bool, str]:
    if M._card_at is not None:
        return False, f"a card was left {CARD_PLACES.get(M._card_at, M._card_at)}"
    if M._status.get("state") in ("jam", "error"):
        return False, f"stopped on {M._status['state']}: {M._status.get('message', '')}"
    if _fault:
        return False, _fault
    if _manual_used:
        return False, "manual control (calibration API) was used"
    if vacuum.pump_is_on():
        return False, "vacuum pump still on"
    if not lift.at_full_lift():
        return False, f"lift not at full height (th {'unknown' if lift.th() is None else format(lift.th(), '.2f')})"
    try:
        w = loadcell.read_grams()
    except Exception as exc:
        return False, f"could not verify the bed is empty: {exc}"
    if not loadcell.is_empty(w):
        return False, f"scan bed not empty ({w:.2f} g)"
    return True, "clean shutdown: no card in the machine, lift up, bed empty"


@_hw
def init_hardware(assume_rest: bool = False):
    """Pump off first — unless the record says a card is held on the cup, then
    the pump stays ON. Calibration validated before anything moves. Nothing
    moves here except, after a clean stop, ONE write of full lift."""
    M._hw_initialised = True
    held = bool(M.read_machine_state().get("pump_hold"))
    if _MOCK:
        from hardware import b_mock
        b_mock.attach()
    vacuum.init(hold=held)
    if held:
        M._set_card_at("cup")
        M._cup_hold_since = time.monotonic()
        print("[b] the last record says a card is HELD on the cup — pump kept ON until 'Machine clear'")
    cal.load(lift.ACTUATION_RANGE)
    touch.init()
    lift.init(assume_full=assume_rest and not held)
    yaw.init()
    yaw.set_interlock(lift.yaw_permitted)
    loadcell.init()
    camera.init()
    _status_pose()


@_hw
def prepare_machine(confirmed: bool = False):
    global _last_hopper_closed
    with M._machine_active():
        M._set_state("starting", "checking the machine")
        _last_hopper_closed = None
        vacuum.pump_off()
        if lift.th() is None and not confirmed:
            raise M.NeedsConfirm("arm pose unknown (lift never commanded) — check the arm, bins and "
                                 "bed are clear, then confirm; the arm then lifts straight to full "
                                 "height and homes")
        _lift_full()
        if not touch.is_closed():
            raise LiftFault("touch contact OPEN with the arm at full lift — cup resting on something, "
                            "slider stuck or contact wire broken")
        try:
            yaw.configure_driver()
        except Exception as exc:
            raise YawFault(f"TMC2209 UART config failed: {exc!r}") from exc
        if yaw.homed():
            _edge_check()
        else:
            print("[b] homing the yaw axis...")
            try:
                yaw.home(tick=M._beat)
            except yaw.YawInterlockError as exc:
                raise YawFault(f"homing refused: {exc}") from exc
            except yaw.YawError as exc:
                raise YawFault(f"homing failed: {exc}") from exc
            finally:
                _status_pose()
        print("[b] checking the scan bed is EMPTY, then taring")
        _startup_bed_check(confirmed)
        if TOUCH_SELFTEST:
            _touch_selftest()
        _goto("hopper")


@_hw
def teardown():
    """Once, from main()'s finally: card put down / held, park if clean, record,
    release. A held card is let go only over the bed or a bin; elsewhere the
    pump stays ON after exit (pigpiod keeps the relay pin) and the record says so.
    The lift goes limp only when parked."""
    if M._tearing_down:
        return
    M._tearing_down = True
    print("\n[b] Shutting down...")
    _make_safe()
    was_held = M._card_at == "cup"
    if was_held:
        zone, text = _held_card_landing()
        if zone in RELEASE_ZONES:
            print(f"[b] releasing the card held on the cup over the bed / a bin: {text}")
            M._try(vacuum.release, None, BLEED_S)
            M._set_card_at("bed" if zone == "scan" else "bin")
    held = M._card_at == "cup"
    if not held and M._card_at is None and yaw.homed() and lift.at_full_lift() and not _pose_at_rest():
        try:
            _park()
        except Exception as exc:
            print(f"[b] could not park: {exc!r}")
    parked = _pose_at_rest() and M._card_at is None
    if M._marker_armed or was_held:
        try:
            clean, reason = _assess_clean()
            M._write_machine_state(clean=clean, confirmed=False, reason=reason,
                                   rest_pose=REST_POSE if clean and parked else None)
            print(f"[b] {'clean' if clean else 'UNCLEAN'} stop: {reason}")
        except Exception as exc:
            print(f"[b] could not record the machine state: {exc!r}")
    if held:
        print(f"[b] card HELD on the cup — the pump stays ON after exit: {_held_card_landing()[1]}")
    M._try(yaw.deinit)
    M._try(lift.deinit, parked)
    M._try(vacuum.deinit, held)
    for fn in (touch.deinit, loadcell.deinit, camera.deinit):
        M._try(fn)


@_hw
def calibrate_loadcell(mass_g: float | None = None):
    """Scale factor from a known mass on the bed; stores the empty-bed reference.
    Marks the machine not clean first (like main.calibrate_loadcell)."""
    M._marker_armed = False
    M._write_machine_state(clean=False, confirmed=False,
                           reason=instance.TOOL_REASON.format(tool=M.CALIBRATE_TOOL_NAME),
                           tool=M.CALIBRATE_TOOL_NAME)
    mass_g = float(mass_g or CALIBRATION_MASS_G)
    input("The arm lifts straight to full height. Check nothing is on the cup, then press Enter...")
    lift.to_full()
    input("Make sure the scan bed is EMPTY and the cup is not touching it, then press Enter to tare...")
    loadcell.tare(calibration=True)
    input(f"Place the {mass_g:.3f} g reference mass (default: a US nickel) in the middle of the bed, "
          "then press Enter...")
    time.sleep(WEIGH_SETTLE_S)
    factor = loadcell.calibrate(known_weight_g=mass_g)
    loadcell.save_calibration(factor)
    print(f"[b] Check: reference reads {loadcell.read_grams():.3f} g (should be {mass_g:.3f} g)")
    input("Remove the reference mass, then press Enter...")
    time.sleep(TARE_SETTLE_S)
    w = loadcell.read_grams_unchecked()
    print(f"[b] Empty bed reads {w:.3f} g ({loadcell.classify(w)})")
    if loadcell.is_empty(w):
        loadcell.tare(calibration=True)
    else:
        print("[b] WARNING: the bed did not return to its empty reading — re-run the calibration")


def _mock_cradle_receives_card():
    """v2 MOCK hook; B's mock world moves the cards itself."""


# ── install into main.py ─────────────────────────────────────────────────────
HOOKS = ("sort_one_card", "_route_pending", "prepare_machine", "init_hardware", "_assess_clean",
         "teardown", "_make_safe", "_release_idle", "_reassert_rest_pose", "_held_card_landing",
         "calibrate_loadcell", "_pose_at_rest", "_on_confirmed_start", "_mock_cradle_receives_card",
         "_cup_hold_watch", "_write_machine_state")


def install(m, setter=setattr):
    """Make main.py (module m) drive machine B. setter: tests pass
    monkeypatch.setattr so everything is restored afterwards."""
    me = sys.modules[__name__]
    for name in HOOKS:
        setter(m, name, getattr(me, name))
    setter(m, "MACHINE", "b")
    setter(m, "SORT_BINS", m.B_SORT_BINS)
    setter(m, "DEFAULT_BIN_LIMITS", m.B_DEFAULT_BIN_LIMITS)
    setter(m, "BIN_LIMIT_MAX", m.B_BIN_LIMIT_MAX)
    setter(m, "REST_POSE", REST_POSE)
    setter(m, "HOLD_PLACE", "bed")
    setter(m, "HW_CONFIG_ERRORS", (cal.BCalibrationError, lift.LiftLimitError))
    setter(m, "RESUME_DELAY_S", RESUME_DELAY_S)
    if set(m._bins.limits) != set(m.B_DEFAULT_BIN_LIMITS):
        setter(m, "_bins", m.BinCounts(m._bins.counts_file, m._bins.limits_file, m.B_DEFAULT_BIN_LIMITS))
    m._status["machine"] = "b"


# ── manual / calibration API (web UI) ────────────────────────────────────────
class ManualRefused(RuntimeError):
    """Not now / not allowed (→ HTTP 409): run in progress, sorter busy, not
    homed, interlock, limits, pump rules. The machine has not moved."""


class ManualBusy(ManualRefused):
    """The sorter holds the hardware lock right now (e.g. parking): try again."""


def _mark_manual():
    global _manual_used
    if not _manual_used:
        _manual_used = True
        M._write_machine_state(clean=False, confirmed=False,
                               reason="manual control (calibration API) was used — check the "
                                      "machine, then confirm")
        if M._status.get("state") not in ("needs_confirm", "jam", "error"):
            M._set_state("needs_confirm", "manual control used — check the machine, then press "
                                          "'Machine clear' before sorting")


def _manual(fn, *args, moves: bool = True):
    """Run a manual command holding the hardware lock — never waiting for it."""
    if not _hw_lock.acquire(blocking=False):
        raise ManualBusy("the sorter is moving the machine right now (busy) — try again in a moment")
    try:
        if M.run_in_progress():
            raise ManualRefused(f"a run is in progress (machine {M._status.get('state')}) — stop it first")
        if M._card_at == "cup":
            raise ManualRefused("the sorter holds a card on the cup — take it off and press "
                                "'Machine clear' first")
        if moves:
            _mark_manual()
        try:
            return fn(*args)
        except (yaw.YawInterlockError, yaw.YawLimitError, yaw.YawNotHomed, lift.LiftLimitError,
                TouchFault) as exc:
            raise ManualRefused(str(exc)) from exc
        except (yaw.YawError, LiftError) as exc:
            raise ManualRefused(f"{type(exc).__name__}: {exc}") from exc
    finally:
        _hw_lock.release()
        _status_pose()


def _no_pump_for_yaw():
    if vacuum.pump_is_on():
        raise ManualRefused("the pump is on (the cup may hold a card): yaw moves are refused — put "
                            "the card down at this station first, or take it off and switch the pump off")


def _busy() -> bool:
    """Another thread (the sorter) holds the hardware lock right now."""
    if _hw_lock.acquire(blocking=False):
        _hw_lock.release()
        return False
    return True


def status() -> dict:
    """Read-only snapshot for the calibration UI."""
    out = {"machine": M.MACHINE, "homed": yaw.homed(), "yaw_deg": yaw.position_deg(),
           "lift_th": lift.th(), "at_full_lift": lift.at_full_lift(),
           "station": cal.station_at(yaw.position_deg()), "pump": vacuum.pump_is_on(),
           "run_in_progress": M.run_in_progress(), "state": M._status.get("state"),
           "busy": _busy(),
           "position_hint": yaw.load_hint(), "calibration": cal.get(), "stations": list(geo.STATIONS),
           "limits": [yaw.LIMIT_MIN_DEG, yaw.LIMIT_MAX_DEG], "th_range": [geo.TH_MIN, geo.TH_FULL]}
    try:
        out["home_pressed"] = yaw.home_pressed() if yaw.backend() else None
        out["touch_open"] = touch.raw_open()
    except Exception as exc:
        out["sensor_error"] = repr(exc)
    return out


def _do_home():
    _no_pump_for_yaw()
    lift.to_full()
    yaw.home()
    return status()


def home():
    return _manual(_do_home)


def _do_jog(deg):
    _no_pump_for_yaw()
    if not yaw.homed():
        raise ManualRefused("yaw not homed — home first")
    yaw.move_by(deg)
    return status()


def jog_yaw(deg: float):
    deg = float(deg)
    if not -30.0 <= deg <= 30.0:
        raise ValueError("jog must be within ±30 deg (use goto for stations)")
    return _manual(_do_jog, deg)


def _do_goto(name):
    _no_pump_for_yaw()
    if not yaw.homed():
        raise ManualRefused("yaw not homed — home first")
    if name == "park":
        yaw.move_to(cal.park_yaw())
    elif name == "clear":
        yaw.move_to(cal.clear_yaw())
    else:
        yaw.move_to(cal.station_yaw(name), approach=True)
    return status()


def goto_station(name: str):
    if name not in geo.STATIONS + ("park", "clear"):
        raise ValueError(f"unknown station {name!r} (valid: {', '.join(geo.STATIONS)}, park, clear)")
    return _manual(_do_goto, name)


def _do_lift(th):
    cur = lift.th()
    if cur is None:
        raise ManualRefused("lift pose unknown — use 'lift to full' first")
    out = {}
    if th < cur:
        res = lift.lower_watching(th)          # small steps, stops on the first contact
        out = {"touched": res.touched, "th_touch": res.th_touch}
    else:
        lift.move_to(th)
    return {**status(), **out}


def set_lift(th: float):
    """Downward moves step with the touch contact watched and stop on contact."""
    th = float(th)
    if not geo.TH_MIN <= th <= geo.TH_FULL:
        raise ValueError(f"th must be within [{geo.TH_MIN:g}, {geo.TH_FULL:g}]")
    return _manual(_do_lift, th)


def _do_full():
    lift.to_full()
    return status()


def lift_full():
    return _manual(_do_full)


def _do_probe(limit_th):
    if lift.th() is None:
        raise ManualRefused("lift pose unknown — lift to full first")
    res = None
    if lift.th() > limit_th:
        res = lift.lower_until_touch(lift.th(), limit_th, 0.0)   # steps from where it is
    out = status()
    out["touched"] = bool(res and res.touched)
    out["th_touch"] = res.th_touch if res else None
    out["th_closed"] = res.th_closed if res else None
    return out


def probe_touch(limit_th: float | None = None):
    """Step down from the current th until the contact opens (or limit_th);
    the lift stays there so the value can be saved."""
    limit_th = geo.TH_MIN if limit_th is None else float(limit_th)
    if not geo.TH_MIN <= limit_th <= geo.TH_FULL:
        raise ValueError("limit_th outside the lift range")
    return _manual(_do_probe, limit_th)


def _resting_at_station() -> str | None:
    """Station name if the cup rests on something there (safe to let go), else None."""
    st = _station_here()
    if st is None or lift.th() is None or lift.at_full_lift():
        return None
    return st if touch.is_open() else None


def _pump_auto_off():
    """Manual pump time-out: let go ONLY if the cup rests at a station; otherwise keep holding."""
    global _pump_timer
    _pump_timer = None
    if not _hw_lock.acquire(blocking=False):
        _arm_pump_timer(5.0)                    # the sorter is busy: look again shortly
        return
    try:
        if not vacuum.pump_is_on() or M.run_in_progress() or M._card_at == "cup":
            return
        if _resting_at_station():
            vacuum.release(bleed_s=BLEED_S)
            print(f"[b] manual pump switched off after {MANUAL_PUMP_MAX_S:.0f} s (cup resting at a station)")
        else:
            print("[b] manual pump time-out: the cup is not resting at a station — KEEPING the pump "
                  "on (it may hold a card). Lower it onto a station or take the card off by hand.")
    finally:
        _hw_lock.release()


def _arm_pump_timer(seconds: float):
    global _pump_timer
    if _pump_timer is not None:
        _pump_timer.cancel()
    _pump_timer = threading.Timer(seconds, _pump_auto_off)
    _pump_timer.daemon = True
    _pump_timer.start()


def _do_pump(on, card_removed):
    global _pump_timer
    if on:
        vacuum.pump_on()
        _arm_pump_timer(MANUAL_PUMP_MAX_S)
        return status()
    if not vacuum.pump_is_on():
        return status()
    if not card_removed and _resting_at_station() is None:
        raise ManualRefused("the cup may hold a card and is not resting at a station — lower it onto a "
                            "station first (the lift stops on contact), or take the card off by hand "
                            "and send card_removed=true. The pump stays on")
    if _pump_timer is not None:
        _pump_timer.cancel()
        _pump_timer = None
    vacuum.release(bleed_s=BLEED_S)
    return status()


def pump(on: bool, card_removed: bool = False):
    """Pump on; or off — only with the cup resting at a station, or after the
    operator took the card off by hand (card_removed=True)."""
    return _manual(_do_pump, bool(on), bool(card_removed))


def _do_motor_off():
    _no_pump_for_yaw()
    yaw.disable(distrust=True)
    return status()


def motor_off():
    """Yaw motor off so the arm can be turned by hand; the saved position is
    no longer trusted (declare_position after placing the arm)."""
    return _manual(_do_motor_off)


def _do_declare(deg):
    if yaw.homed():
        raise ManualRefused("the yaw is homed — its position is known; nothing to declare")
    yaw.save_hint(deg - yaw.HINT_MARGIN_DEG, deg + yaw.HINT_MARGIN_DEG, True)
    return status()


def declare_position(yaw_deg: float | None = None):
    """Operator: the arm is at about yaw_deg (default the park pose) — placed
    there by hand with the motor off. Bounds the next homing search."""
    deg = cal.park_yaw() if yaw_deg is None else float(yaw_deg)
    if not geo.LIMIT_MIN_DEG <= deg <= geo.LIMIT_MAX_DEG:
        raise ValueError(f"yaw must be within [{geo.LIMIT_MIN_DEG:g}, {geo.LIMIT_MAX_DEG:g}]")
    return _manual(_do_declare, deg)


def save_station_yaw(name: str):
    def do():
        if not yaw.homed():
            raise ManualRefused("yaw not homed — home first")
        cal.set_station_value(name, "yaw", yaw.position_deg(), lift.ACTUATION_RANGE)
        return status()
    return _manual(do, moves=False)


def save_station_th(name: str, key: str):
    def do():
        if lift.th() is None:
            raise ManualRefused("lift th unknown")
        cal.set_station_value(name, key, lift.th(), lift.ACTUATION_RANGE)
        return status()
    return _manual(do, moves=False)


def save_pose(key: str):
    """key "park_yaw" or "clear_yaw": the current yaw."""
    if key not in ("park_yaw", "clear_yaw"):
        raise ValueError("key must be park_yaw or clear_yaw")

    def do():
        if not yaw.homed():
            raise ManualRefused("yaw not homed — home first")
        cal.set_top_value(key, round(yaw.position_deg(), 4), lift.ACTUATION_RANGE)
        return status()
    return _manual(do, moves=False)


def set_servo_raw(angle: float):
    """Servo-map calibration: command a raw servo angle (measure th with a gauge)."""
    return _manual(lambda: (lift.write_raw_servo(float(angle)), status())[1])


def save_servo_map(points):
    """New [th, servo] map: the commanded th no longer describes the arm, so it
    is forgotten (yaw refused until 'lift to full' re-commands the height)."""
    def do():
        cal.set_top_value("servo_map", [[float(a), float(b)] for a, b in points], lift.ACTUATION_RANGE)
        lift.invalidate()
        return status()
    return _manual(do)
