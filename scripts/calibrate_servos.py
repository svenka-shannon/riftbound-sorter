#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]   # hardware/__init__ imports camera + card_detect
# ///
"""
Interactive servo jog / calibration tool for the Riftbound card sorter.

Drives the servos through the SAME modules the sorter uses, so the motion
limits, ramps and interlocks are the real ones:
  ch0  pickup arm        hardware/servos.py   → config/servo_calibration.json
         {"pickup_arm": {"ARM_PICK": .., "ARM_DROP": .., "ARM_PARK": ..}}
  ch1  cradle tilt       hardware/shuttle.py  → config/shuttle_calibration.json
         {"tilt": {"hold": .., "level": .., "upper": .., "lower": ..}}
  ch2  shuttle carriage  hardware/shuttle.py  → config/shuttle_calibration.json
         {"shuttle": {"home": .., "0": .., "1": .., "2": .., "3": .., "reject": ..}}
Only the poses you save are written; everything else in the files (other
sections, "timing", …) is kept. Unsaved poses keep the module defaults.

Usage:
    uv run scripts/calibrate_servos.py                  # MOCK (nothing moves), anywhere
    venv/bin/python scripts/calibrate_servos.py --no-mock          # real hardware (Pi venv)
    venv/bin/python scripts/calibrate_servos.py --no-mock --verify # cycle saved poses slowly
        --dwell S   seconds to rest at each pose in --verify (default 1.5)
        --step      --verify waits for Enter at every pose instead

Jog commands (at every pose):
    +  -      ±0.5°        ++  --   ±2°        +++  ---   ±5°
    +1.5 -3   any step up to ±5°
    s  save this pose and go on      n  skip (keep the stored value)
    r  back to the stored value      q  quit (machine is parked safely)
    Enter     show the readout again ?  help

Safety: every move is a ramped move of the owning module (servos.move_arm_smooth,
shuttle hold/level/tip/to_column). The carriage only moves with the cradle in
HOLD, and always finishes towards +ψ like shuttle.to_column() (backlash).
Jogging is limited to ±25° around the value stored at the start of the
session; if you need more, save at the edge and re-run the tool (or re-seat
the horn — one MG996R spline tooth is 14.4°).
"""

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

JOG_STEPS = (0.5, 2.0, 5.0)     # +, ++, +++
JOG_MAX_DEG = 5.0               # largest single jog
WINDOW_DEG = 25.0               # jog window around the value stored at session start
APPROACH_MARGIN_DEG = 8.0       # arm starts PICK/DROP this far short, towards PARK
VERIFY_SLOWDOWN = 2.0           # --verify ramps this many times slower than normal
DEFAULT_TILT_COLUMN = 1         # where upper/lower are calibrated (any column works)
CARRIAGE_LIMITS = (2.0, 178.0)  # ch2: stay 2° inside the servo stops (reject / column 0 dead centres)

# Populated by load_modules() — MOCK_HARDWARE must be set before import.
servos = shuttle = vacuum = elevator = None
_MOCK = True
NOMINAL: dict = {}              # module defaults, before any calibration file
_arm_ready = False
_shuttle_ready = False
_elevator_ready = False
_pump_on = False


class Quit(Exception):
    """User asked to quit (q, Ctrl-D)."""


# ---------------------------------------------------------------------------
# Setup / teardown
# ---------------------------------------------------------------------------

def load_modules(mock: bool) -> None:
    global servos, shuttle, vacuum, elevator, _MOCK
    _MOCK = mock
    os.environ["MOCK_HARDWARE"] = "1" if mock else "0"
    sys.path.insert(0, str(ROOT))
    from hardware import servos as _s, shuttle as _sh, vacuum as _v, elevator as _e
    servos, shuttle, vacuum, elevator = _s, _sh, _v, _e
    # Module defaults (calibration files are only applied by init())
    NOMINAL["arm"] = {k: float(getattr(servos, k)) for k in ("ARM_PICK", "ARM_DROP", "ARM_PARK")}
    NOMINAL["tilt"] = dict(shuttle.TILT_ANGLES)
    NOMINAL["shuttle"] = dict(shuttle.SHUTTLE_ANGLES)


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        print()
        raise Quit


def init_base() -> None:
    """Pump relay off, PCA9685 open. Nothing moves yet."""
    vacuum.init()
    vacuum.pump_off()
    servos.init()           # loads servo_calibration.json


def ensure_arm() -> None:
    global _arm_ready
    if _arm_ready:
        return
    print("\n  The arm's position is unknown at power-up, so its FIRST move goes straight")
    print(f"  to PARK ({servos.ARM_PARK:.1f}°) without a ramp. Cup empty, hands clear.")
    ask("  Enter to park the arm... ")
    servos.arm_park()
    _arm_ready = True


def ensure_shuttle() -> None:
    global _shuttle_ready
    if _shuttle_ready:
        return
    print("\n  Homing the cradle: tilt straight to HOLD, carriage straight to HOME (positions")
    print("  unknown at power-up), then ramps to LEVEL. Cradle empty, hands clear.")
    ask("  Enter to home the shuttle... ")
    shuttle.init()          # loads shuttle_calibration.json; never moves anything
    shuttle.home()          # the explicit, confirmed homing
    _shuttle_ready = True


def set_pump(on: bool) -> None:
    global _pump_on
    (vacuum.pump_on if on else vacuum.pump_off)()
    _pump_on = on
    print(f"  pump {'ON — suction' if on else 'OFF — released'}{' [MOCK]' if _MOCK else ''}")


def shutdown() -> None:
    print("\n[calibrate] Parking: pump off, arm PARK, cradle home + level.")
    steps = [("pump off", vacuum.pump_off)]
    if _arm_ready:
        steps.append(("arm park", servos.arm_park))
    if _shuttle_ready:
        steps.append(("shuttle home", shuttle.home))     # hold → home → level
        steps.append(("shuttle off", shuttle.deinit))    # deinit no longer homes; before servos.deinit
    if _elevator_ready:
        steps.append(("elevator", elevator.deinit))
    steps += [("servos", servos.deinit), ("vacuum", vacuum.deinit)]
    for name, fn in steps:
        try:
            fn()
        except Exception as exc:
            print(f"  [calibrate] {name}: {exc!r}")


# ---------------------------------------------------------------------------
# Calibration files (exact formats the modules load)
# ---------------------------------------------------------------------------

def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        sys.exit(f"[calibrate] {path} is not valid JSON ({exc}) — fix or move it, then re-run")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)


def save_arm(key: str, angle: float) -> None:
    path = servos._CALIBRATION_FILE
    data = read_json(path)
    arm = data.setdefault("pickup_arm", {})
    arm[key] = round(angle, 2)
    legacy = {"ARM_PICK": "ARM_DOWN", "ARM_PARK": "ARM_UP"}.get(key)
    if legacy:
        arm.pop(legacy, None)       # superseded by the new key
    write_json(path, data)
    setattr(servos, key, angle)
    servos.PICKUP_ARM_UP, servos.PICKUP_ARM_DOWN = servos.ARM_PARK, servos.ARM_PICK
    print(f"  saved pickup_arm.{key} = {arm[key]} → {path}")


def save_shuttle(section: str, key, angle: float) -> None:
    path = shuttle._CALIBRATION_FILE
    data = read_json(path)
    data.setdefault(section, {})[str(key)] = round(angle, 2)
    write_json(path, data)
    (shuttle.TILT_ANGLES if section == "tilt" else shuttle.SHUTTLE_ANGLES)[key] = angle
    print(f"  saved {section}.{key} = {round(angle, 2)} → {path}")


# ---------------------------------------------------------------------------
# Generic jog loop
# ---------------------------------------------------------------------------

JOG_HELP = ("  +/- ±0.5°   ++/-- ±2°   +++/--- ±5°   +N/-N (≤5°)   "
            "s save   n skip   r stored value   q quit   Enter readout")


def parse_jog(cmd: str):
    """Jog delta in degrees, 0.0 for a rejected jog, None if not a jog command."""
    if cmd and len(cmd) <= 3 and set(cmd) == {"+"}:
        return JOG_STEPS[len(cmd) - 1]
    if cmd and len(cmd) <= 3 and set(cmd) == {"-"}:
        return -JOG_STEPS[len(cmd) - 1]
    if cmd[:1] in ("+", "-"):
        try:
            d = float(cmd)
        except ValueError:
            return None
        if abs(d) > JOG_MAX_DEG:
            print(f"  max jog is ±{JOG_MAX_DEG:g}° — repeat smaller steps")
            return 0.0
        return d
    return None


def jog(title: str, *, start: float, stored: float, nominal: float, lo: float, hi: float,
        pulse_range: float, move, save, extra=None, extra_help: str = ""):
    """Jog one pose. move(angle) does the module's ramped move to `angle`.
    Returns the saved angle, or None if skipped. The servo is at `start` on entry."""
    cur = start

    def readout():
        us = 500 + 2000 * cur / pulse_range
        tag = "" if abs(cur - stored) < 1e-9 else "   * unsaved"
        print(f"  ▸ {title}: {cur:6.1f}°  ({us:4.0f} µs)   stored {stored:.1f}°  Δ {cur - stored:+.1f}°"
              f"   nominal {nominal:.1f}°   window {lo:.1f}–{hi:.1f}°{' [MOCK]' if _MOCK else ''}{tag}")

    print(JOG_HELP)
    if extra_help:
        print(extra_help)
    readout()
    while True:
        cmd = ask(f"  [{title}] > ")
        if not cmd:
            readout()
            continue
        d = parse_jog(cmd)
        if d is not None:
            if d == 0.0:
                continue
            new = round(min(hi, max(lo, cur + d)), 2)
            if new != round(cur + d, 2):
                print(f"  at the window edge ({lo:.1f}–{hi:.1f}°): save here and re-run the tool "
                      "to go further, or check the horn is on the right spline tooth")
            if new == cur:
                continue
            move(new)
            cur = new
            readout()
            continue
        c = cmd.lower()
        if c == "s":
            save(cur)
            return cur
        if c == "n":
            if abs(cur - stored) > 1e-9:
                print(f"  not saved — {title} stays {stored:.1f}°")
            return None
        if c == "r":
            move(stored)
            cur = stored
            readout()
            continue
        if c == "q":
            raise Quit
        if extra is not None and extra(cmd):
            continue
        print(JOG_HELP)
        if extra_help:
            print(extra_help)


def window(stored: float, top: float):
    return max(0.0, stored - WINDOW_DEG), min(float(top), stored + WINDOW_DEG)


# ---------------------------------------------------------------------------
# Section 1 — pickup arm (ch0)
# ---------------------------------------------------------------------------

ARM_STEPS = (
    ("ARM_PICK", [
        "PICK — cup on the top card in the hopper.",
        "  Put a KNOWN-FLAT card on top of the stack (a curled card moves the touch-down point).",
        "  Jog towards the stack until the cup lip sits on the card AND the spring slider is",
        "  compressed about 3 mm. Too little: no seal. Too much: the slider bottoms out and the",
        "  arm presses on the stack. When it is right: 'v' (suction on), then 's' — the arm",
        "  carries the card over to DROP.",
    ]),
    ("ARM_DROP", [
        "DROP — card held 3 mm above the belt at X -95.",
        "  With the card on the cup (suction on), jog until the card UNDERSIDE is about 3 mm above",
        "  the belt (slide a 3 mm drill shank / hex key under it as a gauge) and the card clears",
        "  the side guides. The card is released onto the belt when you leave this pose.",
    ]),
    ("ARM_PARK", [
        "PARK — crank straight up (rest / refill pose).",
        "  Jog until the crank is vertical (check with a small square). Hopper and belt both clear.",
    ]),
)


def raise_stack() -> None:
    """Bring the top card to pick height with the hopper elevator (arm must be parked)."""
    global _elevator_ready
    if not _elevator_ready:
        elevator.init()
        _elevator_ready = True
    if elevator.raise_to_pick():
        print("  stack at pick height (top-of-stack switch closed)")
        return
    if math.isnan(elevator.position_mm()):                      # not homed yet
        print("  homing the elevator first (floor goes all the way down, up to 90 s)...")
        if not elevator.home():
            print("  elevator did not home — set the stack height by hand (feeler flag just tripped)")
            return
        if elevator.raise_to_pick():
            print("  stack at pick height (top-of-stack switch closed)")
            return
    print("  elevator could not reach pick height — hopper empty? Set the stack by hand.")


def section_arm() -> None:
    ensure_arm()
    print("\n=== Pickup arm (ch0) — ARM_PICK, ARM_DROP, ARM_PARK ===")
    print("  Use a SACRIFICIAL BULK CARD for this: it may get creased or marked.")
    print(f"  PICK and DROP start {APPROACH_MARGIN_DEG:g}° short of the stored value (towards PARK),")
    print("  so jog the last few degrees in yourself.")
    print(f"  Moves use servos.move_arm_smooth (cosine ramp, ≤{servos.ARM_MAX_STEP_DEG:g}° per 20 ms frame).")
    if ask("\n  Raise the stack to pick height with the elevator first? [y/N] ").lower() in ("y", "yes"):
        raise_stack()

    def arm_extra(cmd: str) -> bool:
        if cmd.lower() == "v":
            set_pump(not _pump_on)
            return True
        return False

    top = float(servos.ARM_ACTUATION_RANGE)
    for key, advice in ARM_STEPS:
        print("\n  " + "\n  ".join(advice))
        stored = float(getattr(servos, key))
        lo, hi = window(stored, top)
        start = stored
        if key != "ARM_PARK":
            toward = 1.0 if stored > servos.ARM_PARK else -1.0
            start = min(hi, max(lo, stored - toward * APPROACH_MARGIN_DEG))
        servos.move_arm_smooth(start)
        jog(key, start=start, stored=stored, nominal=NOMINAL["arm"][key], lo=lo, hi=hi,
            pulse_range=top, move=servos.move_arm_smooth,
            save=lambda a, k=key: save_arm(k, a),
            extra=arm_extra, extra_help="  v  suction on/off")
        if key == "ARM_DROP" and _pump_on:
            set_pump(False)           # same order as the sort cycle: release at DROP, then park
            time.sleep(0.3)
    if _pump_on:
        set_pump(False)
    servos.arm_park()
    print("  arm parked")


# ---------------------------------------------------------------------------
# Section 2 / 3 — shuttle (ch1 tilt, ch2 carriage)
# ---------------------------------------------------------------------------

def carriage_to(key) -> None:
    """Move the carriage with the module's to_column() — only ever in HOLD."""
    shuttle.hold()
    target, tilt, _ = shuttle.state()
    if tilt != "hold":
        raise RuntimeError(f"interlock: cradle is {tilt!r}, not hold — carriage not moved")
    shuttle.to_column(key)


def tilt_to(pose: str) -> None:
    """Ramp the cradle to TILT_ANGLES[pose] through the module's public moves
    (which enforce: level only at home, upper/lower only at a column, tips via hold).
    A fine jog inside upper/lower ramps straight from the current angle."""
    _, tilt, _ = shuttle.state()
    if pose == "hold":
        shuttle.hold()
    elif pose == "level":
        shuttle.level()
    elif pose == tilt:
        shuttle._tilt(pose)            # already tipped: small ramp, no detour via hold
    else:
        (shuttle.tip_upper if pose == "upper" else shuttle.tip_lower)()


TILT_STEPS = (
    ("hold", "home", [
        "HOLD — 10° nose-down about the front pin (carriage at HOME).",
        "  The card tail must be lifted clear of the rails and side guides, so the cradle can",
        "  travel without dragging; this is also the weighing pose (cradle at rest, no contact).",
    ]),
    ("level", "home", [
        "LEVEL — receive pose, home only.",
        "  Jog until the skids sit firmly on the home ledges and the bed is ~0.7 mm under the",
        "  belt (a card slides on without catching). Keep ~1.5° of preload past first contact,",
        "  but back off 0.5° if the servo hums/stalls against the ledges.",
    ]),
    ("upper", "column", [
        "UPPER — 35° about the front pin: card slides off the lip into the UPPER slot.",
        "  Jog until a card on the cradle slides off cleanly and the lip clears the upper slot",
        "  edge. (Try it: 'c N' to change column; drop a sacrificial card on in HOLD.)",
    ]),
    ("lower", "column", [
        "LOWER — the other way from hold: rear skids land on the R-bar, cradle swings to ~58°,",
        "  card goes down the fixed lower ramp. Jog until the skids sit on the R-bar without the",
        "  servo stalling, and a card slides down the ramp.",
    ]),
)


def section_tilt() -> None:
    ensure_shuttle()
    print("\n=== Cradle tilt (ch1) — hold, level, upper, lower ===")
    print("  Cradle EMPTY unless the step asks for a card. HOLD and LEVEL are set at HOME;")
    print(f"  UPPER and LOWER at a column (default {DEFAULT_TILT_COLUMN}; calibrate the columns first if a")
    print("  tip clips the tray). The carriage only ever moves in HOLD.")
    col_state = {"col": DEFAULT_TILT_COLUMN}

    for pose, where, advice in TILT_STEPS:
        print("\n  " + "\n  ".join(advice))
        target = shuttle.state()[0]
        if where == "home" and target != "home":
            carriage_to("home")
        elif where == "column" and target in (None, "home"):
            carriage_to(col_state["col"])
        stored = float(shuttle.TILT_ANGLES[pose])
        lo, hi = window(stored, 180)

        def move(a, p=pose):
            shuttle.TILT_ANGLES[p] = a
            tilt_to(p)

        def extra(cmd: str, p=pose, w=where) -> bool:
            parts = cmd.split()
            if w != "column" or len(parts) != 2 or parts[0].lower() != "c":
                return False
            key = parts[1].lower()
            key = int(key) if key in ("0", "1", "2", "3") else key
            if key not in shuttle.COLUMNS and key != "reject":
                print("  c 0|1|2|3|reject")
                return True
            carriage_to(key)                 # back to hold, travel, …
            col_state["col"] = key
            tilt_to(p)                       # … and tip again with the current angle
            print(f"  carriage at {key!r}, cradle {p}")
            return True

        move(stored)
        got = jog(f"tilt {pose}", start=stored, stored=stored, nominal=NOMINAL["tilt"][pose],
                  lo=lo, hi=hi, pulse_range=180, move=move,
                  save=lambda a, p=pose: save_shuttle("tilt", p, a),
                  extra=extra, extra_help="  c N  move to column N (0-3, reject) and tip again" if where == "column" else "")
        if got is None:
            move(stored)                     # unsaved: back to the stored angle (and dict value)
    shuttle.home()
    print("  cradle home + level")


COLUMN_STEPS = (
    ("home", "HOME — belt axis: centre the cradle on the belt so the card runs straight on."),
    (0, "COLUMN 0 — centre the cradle on tray slot 0."),
    (1, "COLUMN 1 — centre the cradle on tray slot 1."),
    (2, "COLUMN 2 — centre the cradle on tray slot 2."),
    (3, "COLUMN 3 — centre the cradle on tray slot 3."),
    ("reject", "REJECT — centre the cradle over the reject bin opening."),
)


def section_columns() -> None:
    ensure_shuttle()
    print("\n=== Shuttle carriage (ch2) — home, columns 0-3, reject ===")
    print("  Centre the cradle on each tray slot by eye, or drop a 65 mm card gauge into the")
    print("  slot and line the cradle up with it. The cradle is in HOLD for every move.")
    print("  Backlash: like shuttle.to_column(), every move ENDS travelling towards +ψ")
    print("  (increasing angle); a '-' jog dips 3° below the target and comes back up.")
    for key, advice in COLUMN_STEPS:
        print(f"\n  {advice}")
        stored = float(shuttle.SHUTTLE_ANGLES[key])
        lo, hi = window(stored, 180)
        lo, hi = max(lo, CARRIAGE_LIMITS[0]), min(hi, CARRIAGE_LIMITS[1])

        def move(a, k=key):
            shuttle.SHUTTLE_ANGLES[k] = a
            carriage_to(k)

        move(stored)
        got = jog(f"carriage {key}", start=stored, stored=stored, nominal=NOMINAL["shuttle"][key],
                  lo=lo, hi=hi, pulse_range=180, move=move,
                  save=lambda a, k=key: save_shuttle("shuttle", k, a))
        if got is None:
            shuttle.SHUTTLE_ANGLES[key] = stored      # carriage moves on from here anyway
    shuttle.home()
    print("  cradle home + level")


# ---------------------------------------------------------------------------
# Verify — slow cycle through every saved pose
# ---------------------------------------------------------------------------

def print_values() -> None:
    def src(path: Path) -> str:
        return str(path) if path.exists() else f"{path} (absent → module defaults)"
    print(f"\n  ch0 arm      [{src(servos._CALIBRATION_FILE)}]")
    for k in ("ARM_PICK", "ARM_DROP", "ARM_PARK"):
        print(f"    {k:9s} {float(getattr(servos, k)):6.1f}°   nominal {NOMINAL['arm'][k]:6.1f}°")
    print(f"  ch1 tilt     [{src(shuttle._CALIBRATION_FILE)}]")
    for k, v in shuttle.TILT_ANGLES.items():
        print(f"    {k:9s} {v:6.1f}°   nominal {NOMINAL['tilt'][k]:6.1f}°")
    print("  ch2 carriage")
    for k in ("home", 0, 1, 2, 3, "reject"):
        print(f"    {str(k):9s} {shuttle.SHUTTLE_ANGLES[k]:6.1f}°   nominal {NOMINAL['shuttle'][k]:6.1f}°")


def verify(dwell: float, step: bool) -> None:
    ensure_arm()
    ensure_shuttle()
    print_values()
    print("\n=== Verify: every saved pose, ramps "
          f"{VERIFY_SLOWDOWN:g}× slower than normal ===")
    print("  Cup EMPTY (pump stays off), cradle EMPTY. The cup touches the stack at PICK.")
    ask("  Enter to start... ")

    def pose(label: str) -> None:
        print(f"  ● {label}")
        if step:
            ask("    Enter for the next pose... ")
        elif not _MOCK:
            time.sleep(dwell)

    old_arm = servos.ARM_FULL_MOVE_S
    old_timing = dict(shuttle.TIMING)
    servos.ARM_FULL_MOVE_S = old_arm * VERIFY_SLOWDOWN
    for k in ("tilt_s_per_deg", "tilt_min_s", "shuttle_s_per_deg", "shuttle_min_s"):
        shuttle.TIMING[k] = old_timing[k] * VERIFY_SLOWDOWN
    try:
        print("\n  ch0 pickup arm")
        for name, fn in (("ARM_PARK", servos.arm_park), ("ARM_PICK", servos.arm_to_pick),
                         ("ARM_PARK", servos.arm_park), ("ARM_DROP", servos.arm_to_drop),
                         ("ARM_PARK", servos.arm_park)):
            fn()
            pose(f"arm {name} {float(getattr(servos, name)):.1f}°")

        T, S = shuttle.TILT_ANGLES, shuttle.SHUTTLE_ANGLES
        print("\n  ch1/ch2 shuttle")
        shuttle.home()
        pose(f"home {S['home']:.1f}° + level {T['level']:.1f}°")
        shuttle.hold()
        pose(f"home + hold {T['hold']:.1f}°")
        for col in (0, 1, 2, 3, "reject"):
            carriage_to(col)
            pose(f"column {col} {S[col]:.1f}° in hold")
            shuttle.tip_lower()
            pose(f"column {col} lower {T['lower']:.1f}°")
            shuttle.hold()
            if col != "reject":
                shuttle.tip_upper()
                pose(f"column {col} upper {T['upper']:.1f}°")
                shuttle.hold()
        shuttle.home()
        pose(f"home {S['home']:.1f}° + level {T['level']:.1f}°")
        print("\n  verify complete")
    finally:
        servos.ARM_FULL_MOVE_S = old_arm
        shuttle.TIMING.update(old_timing)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

MENU = """
=== Servo calibration ({mode}) ===
  1  Pickup arm (ch0)        ARM_PICK / ARM_DROP / ARM_PARK
  2  Cradle tilt (ch1)       hold / level / upper / lower
  3  Shuttle carriage (ch2)  home / columns 0-3 / reject
  v  Verify: cycle every saved pose slowly
  p  Print current values
  q  Quit (parks everything)"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Jog and save servo poses (arm, cradle tilt, shuttle carriage)")
    parser.add_argument("--no-mock", action="store_true",
                        help="drive the real PCA9685 (default: MOCK_HARDWARE=1, nothing moves)")
    parser.add_argument("--verify", action="store_true", help="cycle through all saved poses slowly, then exit")
    parser.add_argument("--dwell", type=float, default=1.5, help="--verify: seconds at each pose (default 1.5)")
    parser.add_argument("--step", action="store_true", help="--verify: wait for Enter at each pose")
    args = parser.parse_args()

    load_modules(mock=not args.no_mock)
    mode = "MOCK — nothing moves" if _MOCK else "REAL hardware"
    print(f"[calibrate] {mode}")
    if _MOCK:
        print("[calibrate] Saved values ARE written to config/ — use --no-mock on the Pi.")
    init_base()
    try:
        if args.verify:
            verify(args.dwell, args.step)
            return
        while True:
            print(MENU.format(mode=mode))
            choice = ask("Choose: ").lower()
            if choice == "q":
                break
            elif choice == "1":
                section_arm()
            elif choice == "2":
                section_tilt()
            elif choice == "3":
                section_columns()
            elif choice == "v":
                verify(args.dwell, args.step)
            elif choice == "p":
                print_values()
            elif choice:
                print("  ?")
    except Quit:
        pass
    except KeyboardInterrupt:
        print("\n[calibrate] interrupted")
    finally:
        shutdown()
        for path in (servos._CALIBRATION_FILE, shuttle._CALIBRATION_FILE):
            if path.exists():
                print(f"\n{path}:\n{path.read_text().rstrip()}")


if __name__ == "__main__":
    main()
