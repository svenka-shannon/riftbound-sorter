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
  ch1/ch2 direction check (bare servos, bench) → config/shuttle_calibration.json
         {"invert": {"1": false, "2": false}}
Only the poses you save are written; everything else in the files (other
sections, "timing", …) is kept. Unsaved poses keep the module defaults.

Direction check (menu 'd', and offered before sections 2 / 3 until the shuttle
has been homed): with the servo BARE — ch1: no REX shaft in the coupler (best
before the coupler is indexed at HOLD); ch2: no crank, horn alone at most —
the servo goes to 80° (straight there: its position is unknown at power-up)
and then ramps slowly to 100°. Increasing angle must turn the spline CLOCKWISE
looking straight at the spline face (cad/shuttle.scad "ch2 DIRECTION": ψ grows
counter-clockwise seen from above; ch1: φ grows from +X up toward +Z). If it
turned the other way, the tool flips that channel's "invert" in the file
(hardware/shuttle.py then writes actuation_range − offset − angle), so every stored
angle keeps its geometric meaning. Fit the crank / shaft only after a check
that passed.

Travel test (menu 't', docs/ASSEMBLY.md §19.1 item 1): ch0, ch1 or ch2, with
the servo BARE (a horn to mark, nothing else) and refused once the arm or the
shuttle has been homed this session, like 'd'. The servo goes straight to 90°,
then ramps slowly to 0°, 180° and back to 90°; mark the horn at 90°, 0° and
180°, measure from the 90° mark to each end and type the two angles in. The
tool compares them with what the channel needs: arm ≥ 87° each side (174° in
all), ch2 ≥ 88° each side (176°), ch1 the nominal tilt range plus its ±8°
window (56.5° below 90°, 30.2° above). On a 270° servo a short end still passes
if the command that would reach it is one calibration accepts (see below).

Angles are GEOMETRIC everywhere in this tool (readout, windows, files): arm
0–180° with PARK 90°, ch1 φ + 90°, ch2 ψ. On a 270° servo (ARM_ACTUATION_RANGE /
"actuation_range" 270) the modules add a centring offset of 45° at the PWM write
only (hardware/servos.py centring_offset), so geometric 0 / 90 / 180 are 833 /
1500 / 2167 µs and the servo keeps 45° of travel spare at each end; the pulse
in the readout includes it. Command the geometric pose and fit there (arm PARK
90°, ch2 ψ 90, ch1 HOLD): the offset is invisible.

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
Jogging is clamped to each pose's own sanity window (the same window the
sorter checks the file against): arm PICK 155–180 / DROP 0–25 / PARK 80–100
(or the mirror, 180° − angle, for a servo that turns the other way), tilt ±8°
and carriage ±12° round the nominal pose, all clipped to the servo's geometric
reach (0–180°; −45–225° on a 270° servo, e.g. arm PICK up to 185, DROP down to
−5), and the carriage to 2° inside that reach (2–178° on a 180° servo). If you need more, the horn / crank /
coupler is on the wrong spline tooth: re-fit it (docs/ASSEMBLY.md §11, §13).

Saving: the rules BETWEEN poses (arm PICK / DROP either side of PARK and
symmetric about it within 10°; tilt lower < level < hold < upper with 2–8°
from level to hold, ≥ 8° from hold to upper, ≥ 30° from lower to level;
carriage reject < 3 < 2 < home < 1 < 0, stops ≥ 5° apart, 2 − 3 ≥ 12°) are
checked when you save, against the other poses as they stand. A pose that is
fine on its own but breaks one of them only because poses still to come in
this menu have their old values is HELD (the tool says which rule): it is
written, together with the held poses, by the first later save that makes the
whole file valid — so a build whose every pose sits ~8° off nominal is done in
one pass (audit 5 minor 3). Whatever is still held at the end of the menu (or
at 'q') is NOT written, and the tool says so. The file on disk always passes
the module's validation (hardware/servos.py / hardware/shuttle.py
validate_calibration). An invalid file at start
stops the tool (exit 78) with the list of bad keys — fix or delete them. Every
config error exits 78 (EX_CONFIG): config/machine.json, an unreadable
calibration file, and an instance lock / data/ this user cannot open (left
root-owned by a run with sudo — never run the tools with sudo; the message
names the file and the chown fix).

Sorter interlock (audit 3 M2): the tool takes the sorter's instance lock
(data/sorter.lock; refuses while the sorter service or another tool runs —
`sudo systemctl stop riftbound-sorter` first) and records the machine NOT
clean in data/machine_state.json before anything moves ("tool ran: ...").
It never records it clean again, even after a normal quit with everything
parked: the next sorter start always asks for "Machine clear". MOCK runs use
the mock files (machine_state.mock.json, sorter.mock.lock).
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
APPROACH_MARGIN_DEG = 8.0       # arm starts PICK/DROP this far short, towards PARK
VERIFY_SLOWDOWN = 2.0           # --verify ramps this many times slower than normal
DEFAULT_TILT_COLUMN = 1         # where upper/lower are calibrated (any column works)
CARRIAGE_STOP_MARGIN_DEG = 2.0  # ch2 jog stays this far inside the servo's reach (geometric ψ): 2–178 on a
                                # 180° servo (reject / column 0 sit at the dead centres, right at its pulse
                                # limits); on a 270° servo the reach is −45…225 (centring offset), so the
                                # ±12° pose windows are the limit. Invert / offset apply only at the PWM write.

# Populated by load_modules() — MOCK_HARDWARE must be set before import.
servos = shuttle = vacuum = elevator = None
_MOCK = True
NOMINAL: dict = {}              # module defaults, before any calibration file
_arm_ready = False
_shuttle_ready = False
_elevator_ready = False
_pump_on = False
_lock = None                    # instance lock handle, held for the life of the tool
EX_CONFIG = 78
# Poses saved in the current menu that are fine on their own but not written
# yet: they break a rule between poses (order / gap / arm symmetry) against
# poses still to come. Written with the first save that makes the file valid.
_held: dict = {"arm": {}, "tilt": {}, "shuttle": {}}


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
    try:
        from hardware import servos as _s, shuttle as _sh, vacuum as _v, elevator as _e
    except Exception as exc:
        # config/machine.json is applied at import (hardware/__init__ imports every
        # module, so even hardware.machine_config cannot be imported first): exit 78
        # like every config error
        if type(exc).__name__ == "MachineConfigError":
            print(f"[calibrate] ERROR: {exc}", file=sys.stderr)
            sys.exit(EX_CONFIG)
        raise
    servos, shuttle, vacuum, elevator = _s, _sh, _v, _e
    # Module nominal poses (the centre of their sanity windows)
    NOMINAL["arm"] = dict(servos.NOMINAL_ARM)
    NOMINAL["tilt"] = dict(shuttle.NOMINAL_TILT_ANGLES)
    NOMINAL["shuttle"] = dict(shuttle.NOMINAL_SHUTTLE_ANGLES)


def claim_machine() -> None:
    """Instance lock + "not clean" marker before anything moves (audit 3 M2).
    Exits 1 if the sorter (or another tool) is running."""
    global _lock
    from hardware import instance
    try:
        _lock = instance.claim_for_tool("scripts/calibrate_servos.py", _MOCK)
    except instance.LockBusy as exc:
        sys.exit(f"[calibrate] ERROR: {exc}")
    except instance.LockFileError as exc:          # root-owned lock / data/ (sudo run)
        print(f"[calibrate] ERROR: {exc}", file=sys.stderr)
        sys.exit(EX_CONFIG)
    print(f"[calibrate] machine recorded as NOT clean ({instance.state_file(_MOCK)}): the next "
          "sorter start asks for 'Machine clear'")


def check_files() -> None:
    """Both calibration files must pass the modules' validation before anything
    moves (the same check the sorter makes). Exit 78 listing every bad key."""
    bad = []
    try:
        cal = servos.read_calibration_file()
        if cal is not None:
            _, problems, _ = servos.validate_calibration(cal)
            bad += [f"{servos._CALIBRATION_FILE}: {p}" for p in problems]
    except servos.ServoConfigError as exc:
        bad.append(str(exc))
    try:
        cal = shuttle.read_calibration_file()
        if cal is not None:
            _, problems = shuttle.validate_calibration(cal)
            bad += [f"{shuttle._CALIBRATION_FILE}: {p}" for p in problems]
    except shuttle.ShuttleConfigError as exc:
        bad.append(str(exc))
    if bad:
        print("[calibrate] ERROR: invalid calibration file(s) — nothing moved:", file=sys.stderr)
        for b in bad:
            print(f"  - {b}", file=sys.stderr)
        print("  Fix or delete those keys (deleted keys use the nominal values), then re-run.",
              file=sys.stderr)
        sys.exit(EX_CONFIG)


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
        data = json.loads(path.read_text())
    except Exception as exc:
        print(f"[calibrate] {path} is not valid JSON ({exc}) — fix or move it, then re-run",
              file=sys.stderr)
        sys.exit(EX_CONFIG)
    if not isinstance(data, dict):
        print(f"[calibrate] {path} must be a JSON object — fix or move it, then re-run",
              file=sys.stderr)
        sys.exit(EX_CONFIG)
    return data


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w") as fh:
        fh.write(json.dumps(data, indent=2) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _refuse(what: str, problems) -> bool:
    print(f"  NOT saved — {what} would make the calibration file invalid:")
    for p in problems:
        print(f"    - {p}")
    return False


def _hold(kind: str, what: str, key, value: float, rule_problems) -> bool:
    """A pose fine on its own that breaks a rule between poses: keep it (not
    written) until a later save in this menu makes the whole file valid."""
    _held[kind][key] = value
    print(f"  HELD, not written yet — {what} is inside its window, but against the other "
          "poses as they are now:")
    for p in rule_problems:
        print(f"    - {p}")
    print("    It is written together with the next pose you save that puts this right "
          "(set the other poses of this menu next).")
    return True


def finish_held(kind: str) -> None:
    """End of a menu (or quit): poses still held are dropped — the file keeps
    its old values, and so does the module."""
    held, _held[kind] = _held[kind], {}
    if not held:
        return
    names = ", ".join(f"{k} {v:g}°" for k, v in held.items())
    if kind == "arm":
        values, problems, _ = servos.validate_calibration(read_json(servos._CALIBRATION_FILE))
        if not problems:
            for k in held:
                setattr(servos, k, values[k])
            servos.PICKUP_ARM_UP, servos.PICKUP_ARM_DOWN = servos.ARM_PARK, servos.ARM_PICK
        path = servos._CALIBRATION_FILE
    else:
        eff, problems = shuttle.validate_calibration(read_json(shuttle._CALIBRATION_FILE))
        if not problems:
            live = shuttle.TILT_ANGLES if kind == "tilt" else shuttle.SHUTTLE_ANGLES
            for k in held:
                live[k] = eff[kind][k]
        path = shuttle._CALIBRATION_FILE
    print(f"  NOT saved: {names} — still held at the end of the menu (the rules between "
          f"poses are not met yet; {path} keeps the old values). Re-run this menu and set "
          "every pose.")


def save_arm(key: str, angle: float) -> bool:
    """Write pickup_arm.<key> (plus any poses held earlier in this menu) if
    the resulting file passes servos.validate_calibration(). A value that only
    breaks the rules between the poses (side of PARK, symmetry) is held
    (_hold); one that fails its own checks is refused: returns False, file
    untouched."""
    path = servos._CALIBRATION_FILE
    data = read_json(path)
    arm = data.get("pickup_arm")
    if not isinstance(arm, dict):
        arm = data["pickup_arm"] = {}
    staged = {**_held["arm"], key: round(angle, 2)}
    for k, v in staged.items():
        arm[k] = v
        legacy = {"ARM_PICK": "ARM_DOWN", "ARM_PARK": "ARM_UP"}.get(k)
        if legacy:
            arm.pop(legacy, None)       # superseded by the new key
    values, problems, _ = servos.validate_calibration(data)
    if problems:
        rules = servos.pose_rule_problems(values)
        if any(p not in rules for p in problems):
            return _refuse(f"pickup_arm.{key} = {arm[key]}", problems)
        setattr(servos, key, angle)          # the moves in this menu use it
        servos.PICKUP_ARM_UP, servos.PICKUP_ARM_DOWN = servos.ARM_PARK, servos.ARM_PICK
        return _hold("arm", f"pickup_arm.{key} = {arm[key]}", key, round(angle, 2), problems)
    write_json(path, data)
    _held["arm"] = {}
    for k, v in staged.items():
        setattr(servos, k, angle if k == key else v)
        print(f"  saved pickup_arm.{k} = {v}{'' if k == key else ' (held)'} → {path}")
    servos.PICKUP_ARM_UP, servos.PICKUP_ARM_DOWN = servos.ARM_PARK, servos.ARM_PICK
    return True


def save_invert(ch: int, value: bool) -> bool:
    """Write {"invert": {"<ch>": value}} into shuttle_calibration.json (rest of
    the file kept) and apply it to the loaded module — if the file stays valid."""
    path = shuttle._CALIBRATION_FILE
    data = read_json(path)
    inv = data.get("invert")
    if not isinstance(inv, dict):
        inv = data["invert"] = {}
    inv[str(ch)] = bool(value)
    _, problems = shuttle.validate_calibration(data)
    if problems:
        return _refuse(f"invert.{ch} = {'true' if value else 'false'}", problems)
    write_json(path, data)
    shuttle.SHUTTLE_INVERT[ch] = bool(value)
    print(f"  saved invert.{ch} = {'true' if value else 'false'} → {path}")
    return True


def save_shuttle(section: str, key, angle: float) -> bool:
    """Write <section>.<key> (plus any poses held earlier in this menu) if the
    resulting file passes shuttle.validate_calibration(). A value that only
    breaks the order / gap rules against the other poses is held (_hold); one
    that fails its own checks (range, sanity window) is refused: returns
    False, file untouched."""
    path = shuttle._CALIBRATION_FILE
    data = read_json(path)
    sec = data.get(section)
    if not isinstance(sec, dict):
        sec = data[section] = {}
    staged = {**_held[section], key: round(angle, 2)}
    for k, v in staged.items():
        sec[str(k)] = v
    eff, problems = shuttle.validate_calibration(data)
    live = shuttle.TILT_ANGLES if section == "tilt" else shuttle.SHUTTLE_ANGLES
    if problems:
        rules = shuttle.pose_rule_problems(eff["tilt"], eff["shuttle"])
        if any(p not in rules for p in problems):
            return _refuse(f"{section}.{key} = {round(angle, 2)}", problems)
        live[key] = angle                    # the moves in this menu use it
        return _hold(section, f"{section}.{key} = {round(angle, 2)}", key, round(angle, 2), problems)
    write_json(path, data)
    _held[section] = {}
    for k, v in staged.items():
        live[k] = angle if k == key else v
        print(f"  saved {section}.{k} = {v}{'' if k == key else ' (held)'} → {path}")
    return True


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
        pulse_range: float, move, save, extra=None, extra_help: str = "", pulse_us=None):
    """Jog one pose. move(angle) does the module's ramped move to `angle`.
    Returns the saved angle, or None if skipped. The servo is at `start` on entry.
    Every angle here is GEOMETRIC; pulse_us(angle) gives the real pulse width
    (servos.arm_pulse_us / shuttle.pulse_us: centring offset and invert
    applied). Without it: 500–2500 µs over pulse_range with the centring offset."""
    cur = start

    def readout():
        us = (pulse_us(cur) if pulse_us else
              500 + 2000 * (cur + servos.centring_offset(pulse_range)) / pulse_range)
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
                print(f"  at the edge of this pose's sanity window ({lo:.1f}–{hi:.1f}°): if the "
                      "pose is still not right, the horn / crank / coupler is on the wrong "
                      "spline tooth — re-fit it (docs/ASSEMBLY.md §11, §13)")
            if new == cur:
                continue
            move(new)
            cur = new
            readout()
            continue
        c = cmd.lower()
        if c == "s":
            if save(cur) is False:
                continue                     # refused (reason printed): jog on, or 'n' / 'r'
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


def window(stored: float, top: float, sanity=None):
    """Jog window: the geometric reach of a servo whose actuation range is
    `top` (servos.geometric_limits: 0–180, or −45–225 on a 270° servo with its
    centring offset) clamped to `sanity` = (lo, hi), the pose's own sanity
    window (servos.sanity_window / shuttle.sanity_window: the same per-pose
    limits the sorter checks the file against). The rules between poses are
    checked at save time (save_arm / save_shuttle), not here (audit 5 minor
    3). If (lo, hi) is empty the jog is pinned to the stored value."""
    lo, hi = servos.geometric_limits(top)
    if sanity is not None:
        lo, hi = max(lo, sanity[0]), min(hi, sanity[1])
    if lo > hi:
        lo = hi = stored
    return lo, hi


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
        "PARK — top of the arc (rest / refill pose): the crank 3° past vertical towards the",
        "  hopper (93°), the pose it was fitted at (docs/ASSEMBLY.md §11 step 3). The default",
        "  90° is right for a crank fitted that way: 'n' keeps it. Only jog if the hopper and",
        "  the belt are not both clear of the cup.",
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
    try:
        _arm_steps(top, arm_extra)
    finally:
        finish_held("arm")
    if _pump_on:
        set_pump(False)
    servos.arm_park()
    print("  arm parked")


def _arm_steps(top: float, arm_extra) -> None:
    for key, advice in ARM_STEPS:
        print("\n  " + "\n  ".join(advice))
        stored = float(getattr(servos, key))
        lo, hi = window(stored, top, servos.sanity_window(key, stored))
        start = stored
        if key != "ARM_PARK":
            toward = 1.0 if stored > servos.ARM_PARK else -1.0
            start = min(hi, max(lo, stored - toward * APPROACH_MARGIN_DEG))
        servos.move_arm_smooth(start)
        jog(key, start=start, stored=stored, nominal=NOMINAL["arm"][key], lo=lo, hi=hi,
            pulse_range=top, move=servos.move_arm_smooth, pulse_us=servos.arm_pulse_us,
            save=lambda a, k=key: save_arm(k, a),
            extra=arm_extra, extra_help="  v  suction on/off")
        if key == "ARM_DROP" and _pump_on:
            set_pump(False)           # same order as the sort cycle: release at DROP, then park
            time.sleep(0.3)


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
        "  belt (a card slides on without catching). Then go ~0.5° past first contact (no more:",
        "  past the ledges the servo stalls for as long as the cradle waits level) — back off",
        "  if the servo hums.",
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
    offer_direction_check(shuttle.CH_TILT)
    ensure_shuttle()
    print("\n=== Cradle tilt (ch1) — hold, level, upper, lower ===")
    print("  Cradle EMPTY unless the step asks for a card. HOLD and LEVEL are set at HOME;")
    print(f"  UPPER and LOWER at a column (default {DEFAULT_TILT_COLUMN}; calibrate the columns first if a")
    print("  tip clips the tray). The carriage only ever moves in HOLD.")
    try:
        _tilt_steps()
    finally:
        finish_held("tilt")
    shuttle.home()
    print("  cradle home + level")


def _tilt_steps() -> None:
    col_state = {"col": DEFAULT_TILT_COLUMN}
    for pose, where, advice in TILT_STEPS:
        print("\n  " + "\n  ".join(advice))
        target = shuttle.state()[0]
        if where == "home" and target != "home":
            carriage_to("home")
        elif where == "column" and target in (None, "home"):
            carriage_to(col_state["col"])
        stored = float(shuttle.TILT_ANGLES[pose])
        lo, hi = window(stored, shuttle.SHUTTLE_ACTUATION_RANGE[shuttle.CH_TILT],
                        shuttle.sanity_window("tilt", pose))

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
                  lo=lo, hi=hi, pulse_range=shuttle.SHUTTLE_ACTUATION_RANGE[shuttle.CH_TILT], move=move,
                  pulse_us=lambda a: shuttle.pulse_us(shuttle.CH_TILT, a),
                  save=lambda a, p=pose: save_shuttle("tilt", p, a),
                  extra=extra, extra_help="  c N  move to column N (0-3, reject) and tip again" if where == "column" else "")
        if got is None:
            move(stored)                     # unsaved: back to the stored angle (and dict value)


COLUMN_STEPS = (
    ("home", "HOME — belt axis: centre the cradle on the belt so the card runs straight on."),
    (0, "COLUMN 0 — centre the cradle on tray slot 0."),
    (1, "COLUMN 1 — centre the cradle on tray slot 1."),
    (2, "COLUMN 2 — centre the cradle on tray slot 2."),
    (3, "COLUMN 3 — centre the cradle on tray slot 3."),
    ("reject", "REJECT — centre the cradle over the reject bin opening."),
)


def section_columns() -> None:
    offer_direction_check(shuttle.CH_SHUTTLE)
    ensure_shuttle()
    print("\n=== Shuttle carriage (ch2) — home, columns 0-3, reject ===")
    print("  Centre the cradle on each tray slot by eye, or drop a 65 mm card gauge into the")
    print("  slot and line the cradle up with it. The cradle is in HOLD for every move.")
    print("  Backlash: like shuttle.to_column(), every move ENDS travelling towards +ψ")
    print("  (increasing angle); a '-' jog dips 3° below the target and comes back up.")
    try:
        _column_steps()
    finally:
        finish_held("shuttle")
    shuttle.home()
    print("  cradle home + level")


def carriage_limits(actuation_range=None) -> tuple[float, float]:
    """ch2 jog limits (geometric ψ): CARRIAGE_STOP_MARGIN_DEG inside the
    servo's reach — 2–178 on a 180° servo, −43–223 on a 270° one (there the
    ±12° pose windows are the real limit)."""
    rng = shuttle.SHUTTLE_ACTUATION_RANGE[shuttle.CH_SHUTTLE] if actuation_range is None else actuation_range
    lo, hi = servos.geometric_limits(rng)
    return lo + CARRIAGE_STOP_MARGIN_DEG, hi - CARRIAGE_STOP_MARGIN_DEG


def _column_steps() -> None:
    for key, advice in COLUMN_STEPS:
        print(f"\n  {advice}")
        stored = float(shuttle.SHUTTLE_ANGLES[key])
        lo, hi = window(stored, shuttle.SHUTTLE_ACTUATION_RANGE[shuttle.CH_SHUTTLE],
                        shuttle.sanity_window("shuttle", key))
        c_lo, c_hi = carriage_limits()
        lo, hi = max(lo, c_lo), min(hi, c_hi)

        def move(a, k=key):
            shuttle.SHUTTLE_ANGLES[k] = a
            carriage_to(k)

        move(stored)
        got = jog(f"carriage {key}", start=stored, stored=stored, nominal=NOMINAL["shuttle"][key],
                  lo=lo, hi=hi, pulse_range=shuttle.SHUTTLE_ACTUATION_RANGE[shuttle.CH_SHUTTLE], move=move,
                  pulse_us=lambda a: shuttle.pulse_us(shuttle.CH_SHUTTLE, a),
                  save=lambda a, k=key: save_shuttle("shuttle", k, a))
        if got is None:
            shuttle.SHUTTLE_ANGLES[key] = stored      # carriage moves on from here anyway


# ---------------------------------------------------------------------------
# Direction check — bare ch1 / ch2 servo, before the crank / shaft goes on
# ---------------------------------------------------------------------------

DIRECTION_SWEEP = (80.0, 100.0)     # geometric degrees; mid-range on every servo
DIRECTION_S_PER_DEG = 0.1           # 20° in 2 s: slow enough to see the sense
DIRECTION_MIN_S = 2.0

DIRECTION_INFO = {
    1: ("ch1 cradle tilt",
        "NO REX shaft in the coupler (bench, install step 1 — best BEFORE the coupler is\n"
        "  indexed at HOLD; a bare spline or the loose coupler alone is fine to watch)",
        "CLOCKWISE looking straight at the spline face (from the shaft side, +Y)",
        "the crank angle φ grows from horizontal +X up toward +Z"),
    2: ("ch2 shuttle carriage",
        "NO crank fitted (bare spline, or the round horn alone)",
        "CLOCKWISE looking straight at the spline (from below the upside-down servo)",
        "= COUNTER-CLOCKWISE seen from above: ψ 0 (+Y, reject) → 90 (−X) → 180 (−Y, column 0)"),
}


def offer_direction_check(ch: int) -> None:
    """Before calibrating ch1 / ch2: offer the bare-servo direction check
    (not once the shuttle has been homed — then the mechanism is attached)."""
    if _shuttle_ready:
        return
    name = DIRECTION_INFO[ch][0]
    if ask(f"\n  Run the DIRECTION CHECK for {name} first (bare servo, nothing fitted)? [y/N] "
           ).lower() in ("y", "yes"):
        direction_check(ch)


def direction_check(ch: int) -> bool:
    """Sweep the bare servo 80° → 100° slowly and ask whether the spline turned
    the documented way; if not, flip invert.<ch> in shuttle_calibration.json.
    Returns True if the final answer was "right direction"."""
    name, bare, expect, why = DIRECTION_INFO[ch]
    lo, hi = DIRECTION_SWEEP
    print(f"\n=== Direction check — {name} (ch{ch}) ===")
    if _shuttle_ready:
        print("  The shuttle has been homed this session, so the mechanism is attached: the direction")
        print("  check is for a BARE servo on the bench. Re-run the tool before fitting anything.")
        return False
    while True:
        shuttle.init()                      # (re)loads shuttle_calibration.json; moves nothing
        inv = shuttle.SHUTTLE_INVERT[ch]
        print(f"  Servo must be BARE: {bare}.")
        print(f"  Current invert.{ch} = {'true' if inv else 'false'}. The servo goes STRAIGHT to {lo:g}°")
        print(f"  (position unknown at power-up), then ramps slowly to {hi:g}° and back.")
        print(f"  Expected for increasing angle: {expect},\n  {why}.")
        if ask(f"  Nothing fitted to ch{ch}, hands clear — Enter to move, 'n' to skip: ").lower() in ("n", "no"):
            return False
        try:
            shuttle._ramp(ch, lo, DIRECTION_S_PER_DEG, DIRECTION_MIN_S)    # unknown → one step
            while True:
                ask(f"  At {lo:g}°. Watch the spline — Enter to ramp to {hi:g}°... ")
                shuttle._ramp(ch, hi, DIRECTION_S_PER_DEG, DIRECTION_MIN_S)
                ans = ask(f"  Did it turn {expect}? [y/n, a = again] ").lower()
                shuttle._ramp(ch, lo, DIRECTION_S_PER_DEG, DIRECTION_MIN_S)
                if ans in ("y", "yes", "n", "no"):
                    break
        finally:
            shuttle.deinit()                # ch1/ch2 fully off: limp, nothing tracked
        if ans in ("y", "yes"):
            print(f"  ch{ch} direction OK (invert.{ch} stays {'true' if inv else 'false'}).")
            return True
        if not save_invert(ch, not inv):
            return False
        print(f"  ch{ch} now writes {'the mirror (actuation_range − offset − angle)' if not inv else 'angle + offset'}"
              " (offset: 45° on a 270° servo, else 0); every stored angle keeps its meaning.")
        if ask("  Run the check again to confirm? [Y/n] ").lower() in ("n", "no"):
            return False


# ---------------------------------------------------------------------------
# Travel test — bare ch0 / ch1 / ch2 servo, before anything is fitted (§19.1)
# ---------------------------------------------------------------------------

TRAVEL_SEQUENCE = (90.0, 0.0, 180.0, 90.0)   # geometric; the last move just parks it mid-range
TRAVEL_MARKS = (90.0, 0.0, 180.0)            # stops where the builder marks the horn
TRAVEL_S_PER_DEG = 0.05                       # 90° in 4.5 s: slow enough to watch
TRAVEL_MIN_S = 2.0
TRAVEL_MAX_DEG = 270.0                        # a typed measurement above this is a typo
# Physical degrees each side of geometric 90° the servo must turn at commanded 0° / 180°:
ARM_TRAVEL_SIDE_DEG = 87.0    # crank 85° each side of PARK (pick 178 / drop 8 about 93) + the
                              # 1.8° crank-fit tolerance (§11 step 3): ≥ 174° in all
TRAVEL_INFO = {
    0: ("ch0 pickup arm",
        "NO arm crank on the spline (bare spline, or a horn alone to mark), arm not assembled"),
    1: ("ch1 cradle tilt",
        "NO REX shaft in the coupler (bare spline, a horn, or the loose coupler alone)"),
    2: ("ch2 shuttle carriage",
        "NO crank fitted (bare spline, or the round horn alone)"),
}


def travel_required(ch: int) -> tuple[float, float]:
    """(below, above): physical degrees the bare servo must turn from geometric
    90° to commanded 0° and to commanded 180°.
      ch0: ARM_TRAVEL_SIDE_DEG each side (≥ 174° in all).
      ch2: 90 − reject (2) and column 0 (178) − 90 = 88° each side (≥ 176°),
           from shuttle.NOMINAL_SHUTTLE_ANGLES.
      ch1: the nominal tilt poses (lower 41.5 … upper 112.2) plus the ±8° tilt
           window (shuttle.SANITY_WINDOW_DEG): 56.5° below, 30.2° above (86.7°)."""
    if ch == servos.CH_PICKUP_ARM:
        return ARM_TRAVEL_SIDE_DEG, ARM_TRAVEL_SIDE_DEG
    if ch == shuttle.CH_SHUTTLE:
        nom = shuttle.NOMINAL_SHUTTLE_ANGLES
        return 90.0 - nom["reject"], nom[0] - 90.0
    nom, m = shuttle.NOMINAL_TILT_ANGLES, shuttle.SANITY_WINDOW_DEG["tilt"]
    return 90.0 - (min(nom.values()) - m), max(nom.values()) + m - 90.0


def travel_range(ch: int) -> int:
    return (servos.ARM_ACTUATION_RANGE if ch == servos.CH_PICKUP_ARM
            else shuttle.SHUTTLE_ACTUATION_RANGE[ch])


def travel_command_limits(ch: int) -> tuple[float, float]:
    """The furthest geometric commands calibration accepts at each end of the
    channel's travel: the union of its pose windows (clipped to the servo's
    reach), and for ch2 also the tool's carriage jog limits. Past 0° / 180°
    only on a 270° servo (centring offset)."""
    rng = travel_range(ch)
    if ch == servos.CH_PICKUP_ARM:
        wins = [w for k in servos.NOMINAL_ARM for w in servos.sanity_windows(k, rng)]
    elif ch == shuttle.CH_TILT:
        wins = [shuttle.sanity_window("tilt", k, rng) for k in shuttle.NOMINAL_TILT_ANGLES]
    else:
        wins = [shuttle.sanity_window("shuttle", k, rng) for k in shuttle.NOMINAL_SHUTTLE_ANGLES]
    lo, hi = min(w[0] for w in wins), max(w[1] for w in wins)
    if ch == shuttle.CH_SHUTTLE:
        c_lo, c_hi = carriage_limits(rng)
        lo, hi = max(lo, c_lo), min(hi, c_hi)
    return lo, hi


def travel_verdict(ch: int, below: float, above: float) -> tuple[bool, list[str]]:
    """Judge the measured turn from the 90° mark to the 0° mark (`below`) and to
    the 180° mark (`above`). An end passes if it turned at least
    travel_required(); on a 270° servo a short end still passes if the command
    that WOULD reach it (90 ∓ required × 90 / measured) is one calibration
    accepts (travel_command_limits): the centring offset leaves 45° of servo
    travel past each end. Returns (passed, report lines). Pure."""
    req_b, req_a = travel_required(ch)
    rng = travel_range(ch)
    lim_lo, lim_hi = travel_command_limits(ch)
    lines, ok = [], True
    for label, meas, req, sign, limit in (("0° side  ", below, req_b, -1.0, lim_lo),
                                          ("180° side", above, req_a, +1.0, lim_hi)):
        line = f"{label}: {meas:6.1f}° measured, needs ≥ {req:.1f}°"
        if meas >= req - 1e-9:
            line += "   ok"
        else:
            need = 90.0 + sign * req * 90.0 / meas if meas > 0 else math.copysign(math.inf, sign)
            reachable = servos.centring_offset(rng) > 0 and (need >= limit if sign < 0 else need <= limit)
            line += f"   SHORT by {req - meas:.1f}°"
            if servos.centring_offset(rng) > 0:
                line += (f" — reaching it takes ≈ {need:.1f}° commanded; calibration allows "
                         f"{'down to' if sign < 0 else 'up to'} {limit:g}° on this {rng}° servo: "
                         + ("OK (calibrate that end past " + ("0°)" if sign < 0 else "180°)")
                            if reachable else "NOT reachable"))
            ok = ok and reachable
        lines.append(line)
    total, req_t = below + above, req_b + req_a
    lines.append(f"total    : {total:6.1f}° measured, needs ≥ {req_t:.1f}° between commanded 0° and 180°"
                 + ("   ok" if total >= req_t - 1e-9 else "   short"))
    return ok, lines


def _ask_measured(prompt: str):
    """A measured angle in degrees (0 < x ≤ TRAVEL_MAX_DEG); None if left empty."""
    while True:
        txt = ask(prompt)
        if not txt:
            return None
        try:
            v = float(txt)
        except ValueError:
            v = math.nan
        if math.isfinite(v) and 0.0 < v <= TRAVEL_MAX_DEG:
            return v
        print(f"  a number of degrees, 0–{TRAVEL_MAX_DEG:g} (Enter to skip the result)")


def _travel_move(ch: int, angle: float, *, first: bool) -> None:
    """Slow ramp of the bare servo to the geometric `angle` (the first move
    goes straight there: the position is unknown at power-up)."""
    if ch == servos.CH_PICKUP_ARM:
        cur = servos.arm_angle()
        dur = None if first or cur is None else max(TRAVEL_MIN_S, abs(angle - cur) * TRAVEL_S_PER_DEG)
        servos.move_arm_smooth(angle, duration_s=dur)
    else:
        shuttle._ramp(ch, angle, TRAVEL_S_PER_DEG, TRAVEL_MIN_S)


def travel_test(ch: int):
    """Bare-servo travel test (§19.1 item 1): sweep slowly to the geometric 0°,
    90° and 180° (the PWM gets the centring offset on a 270° servo), have the
    builder mark the horn at each, then judge the measured turn against
    travel_required(). Refused once the arm or the shuttle has been homed this
    session (the mechanism may be on) — same rule as the direction check.
    Returns True / False (passed / failed), None if skipped or refused."""
    name, bare = TRAVEL_INFO[ch]
    rng = travel_range(ch)
    off = servos.centring_offset(rng)
    req_b, req_a = travel_required(ch)
    print(f"\n=== Travel test — {name} (ch{ch}) ===")
    if _arm_ready or _shuttle_ready:
        homed = " and ".join(n for n, f in (("the arm", _arm_ready), ("the shuttle", _shuttle_ready)) if f)
        print(f"  {homed[0].upper() + homed[1:]} has been homed this session, so a mechanism may be attached:")
        print("  the travel test is for a BARE servo on the bench. Re-run the tool before fitting anything.")
        return None
    print(f"  Servo must be BARE: {bare}.")
    print(f"  Actuation range {rng}°" + (f" (centring offset {off:g}°: geometric 0 / 90 / 180 = "
                                          f"{500 + 2000 * off / rng:.0f} / 1500 / "
                                          f"{500 + 2000 * (180 + off) / rng:.0f} µs)" if off else
                                          " (geometric 0 / 90 / 180 = 500 / 1500 / 2500 µs)") + ".")
    print("  Put a horn on the spline (any tooth) and a sheet of paper or a protractor under it. The")
    print("  servo goes STRAIGHT to 90° (position unknown at power-up), then ramps slowly to 0°, to")
    print("  180° and back to 90°. Mark the horn's pointer at each stop (90°, 0°, 180°).")
    print(f"  Needed: ≥ {req_b:.1f}° from the 90° mark to the 0° mark, ≥ {req_a:.1f}° from the 90° mark")
    print(f"  to the 180° mark (≥ {req_b + req_a:.1f}° in all).")
    if ask(f"  Nothing fitted to ch{ch} but the horn, hands clear — Enter to move, 'n' to skip: "
           ).lower() in ("n", "no"):
        return None
    if ch != servos.CH_PICKUP_ARM:
        shuttle.init()                      # (re)loads shuttle_calibration.json; moves nothing
    try:
        for i, a in enumerate(TRAVEL_SEQUENCE):
            _travel_move(ch, a, first=(i == 0))
            if i < len(TRAVEL_MARKS):
                ask(f"  At {a:g}°. Mark the horn — Enter for the next stop... ")
    finally:
        if ch == servos.CH_PICKUP_ARM:
            servos.release_arm(forget=True)   # ch0 off: limp, position no longer tracked
        else:
            shuttle.deinit()                # ch1/ch2 fully off: limp (the next shuttle.init() forgets the pose)
    below = _ask_measured("  Measured angle from the 90° mark to the 0° mark (degrees, Enter to skip): ")
    if below is None:
        return None
    above = _ask_measured("  Measured angle from the 90° mark to the 180° mark (degrees, Enter to skip): ")
    if above is None:
        return None
    ok, lines = travel_verdict(ch, below, above)
    for line in lines:
        print(f"    {line}")
    if ok:
        print(f"  ch{ch} travel OK: this servo can reach both ends of {name}.")
    elif off:
        print(f"  ch{ch} travel FAILED: even with its spare travel this {rng}° servo can't reach both ends")
        print("  inside the calibration windows. Try another unit (docs/ASSEMBLY.md §19.1 item 1).")
    else:
        print(f"  ch{ch} travel FAILED: this servo can't reach both ends of {name}. Use a DS3218MG-270")
        print("  (actuation range 270, docs/ASSEMBLY.md §19.1 item 1) or another unit.")
    return ok


# ---------------------------------------------------------------------------
# Verify — slow cycle through every saved pose
# ---------------------------------------------------------------------------

def print_values() -> None:
    def src(path: Path) -> str:
        return str(path) if path.exists() else f"{path} (absent → module defaults)"
    print(f"\n  ch0 arm      [{src(servos._CALIBRATION_FILE)}]  ARM_ACTUATION_RANGE "
          f"{servos.ARM_ACTUATION_RANGE}° (centring offset {servos.centring_offset(servos.ARM_ACTUATION_RANGE):g}°)")
    for k in ("ARM_PICK", "ARM_DROP", "ARM_PARK"):
        print(f"    {k:9s} {float(getattr(servos, k)):6.1f}°   nominal {NOMINAL['arm'][k]:6.1f}°")
    rng, inv = shuttle.SHUTTLE_ACTUATION_RANGE, shuttle.SHUTTLE_INVERT
    print(f"  ch1/ch2      [{src(shuttle._CALIBRATION_FILE)}]")
    for ch in (shuttle.CH_TILT, shuttle.CH_SHUTTLE):
        print(f"    ch{ch}: actuation_range {rng[ch]}° (centring offset "
              f"{servos.centring_offset(rng[ch]):g}°), invert {'true' if inv[ch] else 'false'}")
    print("  ch1 tilt")
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
  d  Direction check (ch1/ch2, bare servos on the bench) → invert
  t  Travel test (ch0/ch1/ch2, bare servo on the bench): 0° / 90° / 180°
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
    check_files()             # invalid calibration → exit 78, nothing moved
    claim_machine()           # instance lock + "not clean" marker, before anything moves
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
            elif choice == "d":
                c = ask("  Channel 1 (tilt) or 2 (shuttle)? ")
                if c in ("1", "2"):
                    direction_check(int(c))
                else:
                    print("  1 or 2")
            elif choice == "t":
                c = ask("  Channel 0 (arm), 1 (tilt) or 2 (shuttle)? ")
                if c in ("0", "1", "2"):
                    travel_test(int(c))
                else:
                    print("  0, 1 or 2")
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
