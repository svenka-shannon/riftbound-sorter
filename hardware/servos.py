"""
Servo control via PCA9685 (I2C address 0x40, 50Hz PWM).
Channels:
  0 - Pickup arm    single-servo parallelogram arm (cad/suction_arm.scad):
                    ARM_PICK = cup on the top card in the hopper,
                    ARM_DROP = card 3 mm above the belt at X -95,
                    ARM_PARK = top of the arc (servo 90° = crank 93°, th_mid)
  1, 2 - cradle tilt + shuttle carriage: hardware/shuttle.py (shares this PCA9685)
  3-15 - unused

Shutdown (deinit / release_pca): every channel is set fully OFF (no pulses,
servos limp) BEFORE Adafruit's PCA9685.deinit(), which only writes MODE1 = 0 —
that leaves the oscillator running and the last pulses going, and turns
register auto-increment off (so later 4-byte channel writes would be garbage).
The chip is then put to sleep (MODE1 SLEEP bit). Call shuttle.deinit() first.

Requires: adafruit-circuitpython-pca9685, adafruit-circuitpython-motor
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

_CALIBRATION_FILE = Path(__file__).parent.parent / "config" / "servo_calibration.json"

# PCA9685 channel map. This module owns ONLY ch0 (pickup arm).
# ch1 (cradle tilt) and ch2 (shuttle carriage) belong to hardware/shuttle.py,
# which replaced the old flat gate levers in the Nov 2026 redesign.
CH_PICKUP_ARM   = 0
SERVO_CHANNELS  = (CH_PICKUP_ARM,)

if not _MOCK:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
    from adafruit_motor import servo as adafruit_servo

# ── Pickup arm (ch0) ──────────────────────────────────────────────────────
# Parallelogram arm, cad/suction_arm.scad: the cup stays vertical and moves on
# a 60.3 mm-radius arc about the servo axis (X -154.7, Z 151.8). Servo 90° =
# crank th_mid = 93.0° (3° past vertical toward the hopper: the middle of the
# pick 178° … drop 8° arc), which is how the crank is fitted (docs/ASSEMBLY.md
# §11 step 3: 25T spline × 4 horn slots = 3.6° steps, so within 1.8° of 93°);
# increasing angle swings the cup towards the hopper. The working arc is
# symmetric about 90°, so if your servo turns the other way just swap ARM_PICK
# and ARM_DROP (calibration file) — it never leaves the safe arc.
ARM_PICK = 175   # crank 178°: cup lip 3 mm below the top card (Z 90.9), spring slider takes it
ARM_DROP = 5     # crank 8°: card underside 3 mm above the belt, card centre X -95
ARM_PARK = 90    # crank 93° (th_mid): hand over X ≈ -158 at the top of the arc (rest / refill)
ARM_ACTUATION_RANGE = 180   # MG996R at 500–2500 µs; 270 for a DS3218MG-270 drop-in:
                            # config/machine.json {"servos": {"ARM_ACTUATION_RANGE": 270}}
                            # (then re-calibrate the arm angles). Every arm angle is GEOMETRIC
                            # (crank − 3°) on either range: a 270° servo gets the CENTRING
                            # OFFSET (centring_offset(), 45°) added at the PWM write only, so
                            # the 0–180° working arc sits in the middle of its travel
                            # (0° → 833 µs, 90° → 1500 µs, 180° → 2167 µs) and neither end
                            # is at a pulse limit.
ARM_MAX_STEP_DEG = 4.0      # largest angle change per PWM update (≤200°/s peak; card sees <1 m/s²)
ARM_UPDATE_S = 0.02         # one update per 50 Hz PWM frame
ARM_FULL_MOVE_S = 1.2       # default time for the full pick↔drop arc (~170°)

# Legacy names (scripts/test_hardware.py, scripts/calibrate_servos.py): UP = park, DOWN = pick
PICKUP_ARM_UP    = ARM_PARK
PICKUP_ARM_DOWN  = ARM_PICK

import sys as _sys
from hardware import machine_config as _machine_config
_machine_config.apply(_sys.modules[__name__], "servos", ("ARM_ACTUATION_RANGE",))


# ── Geometric angle → PWM (centring offset) ──────────────────────────────
# Every angle in this module, in config/servo_calibration.json and in the
# calibration tool is GEOMETRIC: 0–180° is the arm's working arc, 90° the
# PARK pose the crank is fitted at. On a 180° servo that is the whole pulse
# range (0° = 500 µs). On a 270° servo the geometric arc is centred in the
# servo's travel: the PWM gets angle + centring_offset(270) = angle + 45°, so
# geometric 0 / 90 / 180 = 833 / 1500 / 2167 µs and both ends keep 45° of
# servo travel spare (a DS3218 that turns only ~255° over 500–2500 µs still
# reaches them). The builder never sees the offset: they command the
# geometric pose (PARK 90°) and fit the crank there. hardware/shuttle.py
# applies the same offset to ch1 / ch2 (shuttle.pwm_angle()).
def centring_offset(actuation_range) -> float:
    """PWM angle of geometric 0°: (actuation_range − 180) / 2 — 0 for a
    180° servo, 45° for a 270° one. Derived from the range, never configured."""
    return (float(actuation_range) - 180.0) / 2.0


def geometric_limits(actuation_range) -> tuple[float, float]:
    """Geometric angles a servo of this range can be commanded to:
    [−offset, range − offset] (0–180 on a 180° servo, −45–225 on a 270° one)."""
    off = centring_offset(actuation_range)
    return 0.0 - off, float(actuation_range) - off      # (0.0 - 0.0 = +0.0, not -0.0)


def arm_pwm_angle(angle: float) -> float:
    """Angle written to the ch0 servo (0..ARM_ACTUATION_RANGE) for the
    geometric arm angle `angle` (clamped to geometric_limits first)."""
    lo, hi = geometric_limits(ARM_ACTUATION_RANGE)
    return max(lo, min(hi, float(angle))) + centring_offset(ARM_ACTUATION_RANGE)


def arm_pulse_us(angle: float) -> float:
    """Pulse width (µs, 500–2500) ch0 gets for the geometric arm angle `angle`."""
    return 500.0 + 2000.0 * arm_pwm_angle(angle) / float(ARM_ACTUATION_RANGE)

_pca = None
_servos = {}
_arm_angle = None   # last commanded ch0 angle (None until the first move)
_arm_released = False   # ch0 switched off (limp) since the last write; _arm_angle still tracked


# ── Calibration file (config/servo_calibration.json) ─────────────────────
# Validated strictly (audit 3 M1), like config/machine.json: every problem is
# reported at once and NOTHING is applied unless the whole file is good
# (ServoConfigError → main.py exits 78, systemd does not restart).
#   sections   "pickup_arm" (keys ARM_PICK, ARM_DROP, ARM_PARK; legacy ARM_DOWN /
#              ARM_UP, see below); legacy "gate" / "bin_select" (ignored: those
#              servos are now the shuttle's); keys "_…" are comments.
#   values     finite JSON numbers (GEOMETRIC degrees) within the servo's reach
#              geometric_limits(ARM_ACTUATION_RANGE) (0–180; −45–225 on a 270°
#              servo, whose PWM gets the 45° centring offset), each inside its
#              sanity window round the nominal pose — or round the MIRRORED pose
#              (180° − nominal: a servo that turns the other way swaps PICK and
#              DROP, the arc is symmetric about PARK 90°):
#                PICK 155–180 (mirror 0–25)    DROP 0–25 (mirror 155–180)
#                PARK 80–100
#              (on a 270° servo the reach clips them at −45 / 225 instead of
#              0 / 180: PICK 155–185, DROP −5–25, mirrors alike)
#              i.e. SANITY_WINDOW_DEG (10°) away from PARK / either side of PARK,
#              SANITY_WINDOW_TOWARD_PARK_DEG (20°) towards PARK (clipped to the
#              servo's reach). Plus two rules between the poses:
#                PICK and DROP on opposite sides of PARK;
#                symmetry |(PICK − PARK) − (PARK − DROP)| ≤ ARM_SYMMETRY_MAX_DEG
#                (10°) — both ends sit 85°/(1 + gain) from PARK on a crank
#                fitted as documented, whatever the servo's gain.
#              So a typo (ARM_DROP 400, a string, NaN, 120 for 12, 157 for 175)
#              can never swing the arm into the hopper.
#              Why these numbers (audit 5 MJ-A): the crank is fitted within
#              1.8° of th_mid (3.6° spline × slot lattice), the rest is trim
#              (PICK slider compression, DROP height) and MG996R GAIN: a servo
#              that turns 10 % more than commanded needs PICK ≈ 167 / DROP ≈ 13
#              — so the windows open towards PARK only; away from PARK the arm
#              would go past the hopper / belt. Every build with gain −10…+10 %
#              whose poses the servo can reach passes (tests/test_audit5_fixes.py
#              models it), while 157 for 175 breaks the symmetry rule by 18°.
#              calibrate_servos.py clamps its jog to the per-pose window and
#              checks the symmetry / side rules when it saves.
#   legacy     ARM_DOWN → ARM_PICK, ARM_UP → ARM_PARK, only when the new key is
#              absent (with a warning; checked like the key it stands in for).
#              Superseded legacy keys are ignored.
SANITY_WINDOW_DEG = 10.0                # PARK ±; PICK / DROP away from PARK
SANITY_WINDOW_TOWARD_PARK_DEG = 20.0    # PICK / DROP towards PARK (servo gain, audit 5 MJ-A)
ARM_SYMMETRY_MAX_DEG = 10.0             # |(PICK − PARK) − (PARK − DROP)|
NOMINAL_ARM = {"ARM_PICK": float(ARM_PICK), "ARM_DROP": float(ARM_DROP), "ARM_PARK": float(ARM_PARK)}
_ARM_KEYS = ("ARM_PICK", "ARM_DROP", "ARM_PARK")
_LEGACY_ARM = {"ARM_DOWN": "ARM_PICK", "ARM_UP": "ARM_PARK"}
_LEGACY_SECTIONS = ("gate", "bin_select")


class ServoConfigError(ValueError):
    """config/servo_calibration.json is unusable; .problems lists every bad key."""

    def __init__(self, message, problems=()):
        super().__init__(message)
        self.problems = list(problems)


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def sanity_windows(key: str, actuation_range: int | None = None) -> list[tuple[float, float]]:
    """Allowed (lo, hi) windows for ARM_PICK / ARM_DROP / ARM_PARK: around the
    nominal pose and around its mirror (180° − nominal), clipped to the servo's
    geometric reach (geometric_limits: 0–180, or −45–225 on a 270° servo). PARK: ±SANITY_WINDOW_DEG. PICK / DROP: SANITY_WINDOW_TOWARD_PARK_DEG on the
    side towards PARK 90° (a servo with more gain than nominal needs less
    command), SANITY_WINDOW_DEG on the side away from it."""
    reach_lo, reach_hi = geometric_limits(actuation_range if actuation_range is not None
                                          else ARM_ACTUATION_RANGE)
    out = []
    for c in sorted({NOMINAL_ARM[key], 180.0 - NOMINAL_ARM[key]}):
        below = above = SANITY_WINDOW_DEG
        if c > 90.0:
            below = SANITY_WINDOW_TOWARD_PARK_DEG
        elif c < 90.0:
            above = SANITY_WINDOW_TOWARD_PARK_DEG
        out.append((max(reach_lo, c - below), min(reach_hi, c + above)))
    return out


def sanity_window(key: str, value: float, actuation_range: int | None = None) -> tuple[float, float]:
    """The window that contains `value` (else the one nearest to it)."""
    wins = sanity_windows(key, actuation_range)
    for lo, hi in wins:
        if lo <= value <= hi:
            return lo, hi
    return min(wins, key=lambda w: min(abs(value - w[0]), abs(value - w[1])))


def validate_calibration(cal, actuation_range: int | None = None) -> tuple[dict, list[str], list[str]]:
    """Check a parsed servo_calibration.json. Returns (values, problems, notes):
    values = {ARM_PICK, ARM_DROP, ARM_PARK} (nominal where the file has none;
    only meaningful without problems), notes = warnings (legacy keys). Pure."""
    rng = actuation_range if actuation_range is not None else ARM_ACTUATION_RANGE
    problems, notes = [], []
    values = dict(NOMINAL_ARM)
    if not isinstance(cal, dict):
        return values, [f"must be a JSON object, got {type(cal).__name__}"], notes
    for sec in cal:
        if str(sec).startswith("_") or sec == "pickup_arm":
            continue
        if sec in _LEGACY_SECTIONS:
            notes.append(f'old "{sec}" section ignored (those servos are now the shuttle\'s: '
                         "config/shuttle_calibration.json)")
            continue
        problems.append(f"{sec}: unknown section (valid: pickup_arm)")
    arm = cal.get("pickup_arm", {})
    if not isinstance(arm, dict):
        return values, problems + [f"pickup_arm: must be a JSON object of KEY: value, got {json.dumps(arm)}"], notes
    arm = {k: v for k, v in arm.items() if not str(k).startswith("_")}
    for k in arm:
        if k not in _ARM_KEYS and k not in _LEGACY_ARM:
            problems.append(f"pickup_arm.{k}: unknown key (valid: {', '.join(_ARM_KEYS)})")
    source = {}
    for key in _ARM_KEYS:
        if key in arm:
            source[key] = key
        else:
            legacy = next((lk for lk, nk in _LEGACY_ARM.items() if nk == key and lk in arm), None)
            if legacy:
                source[key] = legacy
                notes.append(f"using legacy {legacy} as {key} — re-calibrate ch0 "
                             "(ARM_PICK/ARM_DROP/ARM_PARK)")
    good = set()
    for key, src in source.items():
        v = arm[src]
        where = f"pickup_arm.{src}" + (f" (legacy, used as {key})" if src != key else "")
        if not _is_number(v):
            problems.append(f"{where}: must be a number (degrees), got {json.dumps(v)}")
            continue
        if not math.isfinite(v):
            problems.append(f"{where}: must be a finite number, got {v}")
            continue
        v = float(v)
        reach_lo, reach_hi = geometric_limits(rng)
        if not reach_lo <= v <= reach_hi:
            problems.append(f"{where}: {v:g}° is outside the servo range [{reach_lo:g}, {reach_hi:g}] "
                            f"(geometric degrees, ARM_ACTUATION_RANGE {rng})")
            continue
        wins = sanity_windows(key, rng)
        if not any(lo <= v <= hi for lo, hi in wins):
            allowed = " or ".join(f"{lo:g}–{hi:g}°" for lo, hi in wins)
            mirror = (f" (or its mirror {180 - NOMINAL_ARM[key]:g}°)"
                      if NOMINAL_ARM[key] != 90.0 else "")
            problems.append(f"{where}: {v:g}° is outside the sanity window round the nominal "
                            f"{NOMINAL_ARM[key]:g}°{mirror}; allowed {allowed} — a typo? Re-calibrate with "
                            "scripts/calibrate_servos.py (re-fit the crank, docs/ASSEMBLY.md §11, "
                            "if the pose really is that far off)")
            continue
        values[key] = v
        good.add(key)
    if {"ARM_PICK", "ARM_DROP", "ARM_PARK"} <= good | (set(_ARM_KEYS) - set(source)):
        problems.extend(pose_rule_problems(values))
    return values, problems, notes


def pose_rule_problems(values: dict) -> list[str]:
    """The rules BETWEEN the three arm poses (each already inside its own
    window): PICK and DROP on opposite sides of PARK, and the two half-arcs
    within ARM_SYMMETRY_MAX_DEG of each other. Pure; used by
    validate_calibration() and by calibrate_servos.py when it saves."""
    pk, dr, pa = (float(values[k]) for k in _ARM_KEYS)
    if not (pk - pa) * (dr - pa) < 0:
        return [f"pickup_arm: ARM_PICK ({pk:g}°) and ARM_DROP ({dr:g}°) must lie on "
                f"opposite sides of ARM_PARK ({pa:g}°) — swap BOTH for a servo that "
                "turns the other way"]
    asym = (pk - pa) - (pa - dr)
    if abs(asym) > ARM_SYMMETRY_MAX_DEG + 1e-9:
        return [f"pickup_arm: ARM_PICK − ARM_PARK ({pk - pa:+g}°) and ARM_PARK − ARM_DROP "
                f"({pa - dr:+g}°) differ by {abs(asym):g}°, more than {ARM_SYMMETRY_MAX_DEG:g}° — "
                "the arc is symmetric about PARK (a typo such as 157 for 175?). Re-calibrate "
                "with scripts/calibrate_servos.py; if the poses really are that lopsided, the "
                "crank is not on the 93° fit (docs/ASSEMBLY.md §11 step 3)"]
    return []


def _reject_constant(token):
    raise ValueError(f"{token} is not a valid JSON number")


def read_calibration_file(path=None):
    """Parsed calibration file (None if absent); NaN / Infinity rejected.
    Raises ServoConfigError if unreadable."""
    path = Path(path) if path is not None else _CALIBRATION_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(), parse_constant=_reject_constant)
    except Exception as exc:
        raise ServoConfigError(f"could not read {path} ({exc}) — fix or move it, then restart",
                               [f"not valid JSON: {exc}"]) from exc


def _load_calibration() -> None:
    """Apply config/servo_calibration.json (validate_calibration first: any
    problem raises ServoConfigError listing every bad key and NOTHING is
    applied). Keys absent from the file get their nominal value."""
    global ARM_PICK, ARM_DROP, ARM_PARK, PICKUP_ARM_UP, PICKUP_ARM_DOWN

    cal = read_calibration_file()
    values, problems, notes = validate_calibration({} if cal is None else cal)
    if problems:
        lines = "\n".join(f"  - {p}" for p in problems)
        raise ServoConfigError(f"invalid {_CALIBRATION_FILE} — refusing to start:\n{lines}\n"
                               "Fix these keys (or delete them to use the nominal values) and "
                               "re-check with scripts/calibrate_servos.py --verify", problems)
    for n in notes:
        print(f"[servos] Warning: {n}")
    ARM_PICK, ARM_DROP, ARM_PARK = values["ARM_PICK"], values["ARM_DROP"], values["ARM_PARK"]
    PICKUP_ARM_UP, PICKUP_ARM_DOWN = ARM_PARK, ARM_PICK


def init(assume_parked: bool = False):
    """Initialize PCA9685 and attach servo objects.

    assume_parked: the last stop was clean (main.py's machine state file), so
    the arm rests at ARM_PARK (the calibrated value), limp. ARM_PARK is
    written once (a small snap back by whatever the limp arm sagged) and the
    first move ramps from there. If the arm is really somewhere else, that
    write still makes it jump at full speed — hobby servos have no position
    feedback, so a slow first move cannot be guaranteed.
    assume_parked=False: NOTHING is written to ch0 (audit M7); the first
    move_arm_smooth() — main.py only makes it after the operator confirmed
    the machine clear — goes straight to its target.
    Raises ServoConfigError (before touching anything) if
    config/servo_calibration.json is unreadable or fails validation."""
    global _pca, _servos, _arm_angle, _arm_released

    # Apply calibration overrides before any hardware move
    _load_calibration()
    _arm_angle = float(ARM_PARK) if assume_parked else None
    _arm_released = False

    if _MOCK:
        print("[servos] MOCK mode — no hardware")
        return
    i2c = busio.I2C(board.SCL, board.SDA)
    _pca = PCA9685(i2c, address=0x40)
    _pca.frequency = 50
    for ch in SERVO_CHANNELS:
        rng = ARM_ACTUATION_RANGE if ch == CH_PICKUP_ARM else 180
        _servos[ch] = adafruit_servo.Servo(_pca.channels[ch], actuation_range=rng,
                                           min_pulse=500, max_pulse=2500)
    if _arm_angle is not None:
        _servos[CH_PICKUP_ARM].angle = arm_pwm_angle(_arm_angle)   # hold the assumed rest pose
    print("[servos] PCA9685 initialized on I2C 0x40")


def _arm_write(angle: float) -> None:
    """Command the geometric `angle`; _arm_angle keeps it, the PWM gets arm_pwm_angle()."""
    global _arm_angle, _arm_released
    if not _MOCK:
        _servos[CH_PICKUP_ARM].angle = arm_pwm_angle(angle)
    _arm_angle = angle
    _arm_released = False


def release_arm(forget: bool = False) -> None:
    """Switch ch0 fully OFF (no pulses): the arm goes limp where it is, and
    stops drawing holding current. The commanded angle stays tracked, so
    assert_park() can re-assert the park pose with one write later.
    forget=True: the pose is no longer tracked either (someone may turn the
    spline by hand, e.g. after the calibration tool's bare-servo travel
    test), so the next move goes straight to its target like the first
    move after init()."""
    global _arm_released, _arm_angle
    if not _MOCK and _pca is not None:
        _pca.channels[CH_PICKUP_ARM].duty_cycle = 0       # < 0x10 → FULL_OFF bit
    _arm_released = True
    if forget:
        _arm_angle = None


def arm_released() -> bool:
    """ch0 is switched off (limp) since the last command."""
    return _arm_released


def assert_park() -> None:
    """Re-assert ARM_PARK with ONE write (the limp arm may have sagged a
    little and snaps back by that much) — only if the arm is known to be
    parked (same rest-pose logic as init(assume_parked=True))."""
    if _arm_angle is None or float(_arm_angle) != float(ARM_PARK):
        raise RuntimeError(f"arm not known to be parked ({_arm_angle!r}) — not re-asserting")
    _arm_write(float(ARM_PARK))


def move_arm_smooth(target: float, duration_s: float | None = None, settle_s: float = 0.15) -> None:
    """Ramp the pickup arm (ch0) to `target` degrees without flinging the card.

    Cosine (ease-in / ease-out) profile: zero speed at both ends, so the cup
    touches down on the stack and lifts the card off it slowly, and the card
    is never jerked sideways. One update per 50 Hz PWM frame, never more than
    ARM_MAX_STEP_DEG per update (duration is stretched if needed).

    duration_s: total ramp time; default scales with distance
                (ARM_FULL_MOVE_S for the whole pick↔drop arc, min 0.15 s).
    If the arm position is unknown (first move after init) it is commanded
    directly — call arm_park() once at start-up while the cup is empty.
    """
    lo, hi = geometric_limits(ARM_ACTUATION_RANGE)
    target = max(lo, min(hi, float(target)))
    start = _arm_angle
    if start is None:
        print(f"[servos] arm position unknown — moving straight to {target:.1f}°")
        _arm_write(target)
        time.sleep(0.6 + settle_s)       # MG996R: ~0.17 s/60° unloaded, worst case ~180°
        return
    delta = target - start
    if abs(delta) < 1e-6:
        time.sleep(settle_s)
        return
    full_arc = max(1.0, abs(ARM_PICK - ARM_DROP))
    if duration_s is None:
        duration_s = max(0.15, ARM_FULL_MOVE_S * abs(delta) / full_arc)
    # peak step of a cosine ramp over n steps = |delta|·π/(2n)
    n = max(1, round(duration_s / ARM_UPDATE_S),
            math.ceil(math.pi * abs(delta) / (2 * ARM_MAX_STEP_DEG)))
    dt = max(ARM_UPDATE_S, duration_s / n)
    for i in range(1, n + 1):
        _arm_write(start + delta * (1 - math.cos(math.pi * i / n)) / 2)
        time.sleep(dt)
    _arm_write(target)
    time.sleep(settle_s)


def arm_to_pick(duration_s: float | None = None, settle_s: float = 0.15) -> None:
    """Cup down onto the top card in the hopper (spring slider absorbs ~3 mm)."""
    move_arm_smooth(ARM_PICK, duration_s, settle_s)


def arm_to_drop(duration_s: float | None = None, settle_s: float = 0.15) -> None:
    """Carry the card over the arc and hold it 3 mm above the belt at X -95."""
    move_arm_smooth(ARM_DROP, duration_s, settle_s)


def arm_park(duration_s: float | None = None, settle_s: float = 0.15) -> None:
    """Top of the arc (crank 93°, 3° past vertical): hopper and belt both clear (rest / refill)."""
    move_arm_smooth(ARM_PARK, duration_s, settle_s)


def arm_angle() -> float | None:
    """Last commanded ch0 angle (None before the first move)."""
    return _arm_angle


def pickup_arm_down(settle_s=0.4):
    """Legacy wrapper: arm_to_pick()."""
    arm_to_pick(settle_s=settle_s)


def pickup_arm_up(settle_s=0.4):
    """Legacy wrapper: arm_park(). NOTE: with the parallelogram arm the card is
    released at the BELT, so the pick cycle must call arm_to_drop() before
    vacuum.pump_off(); parking with a held card just lifts it to the top."""
    arm_park(settle_s=settle_s)


def reset_all():
    """Park the pickup arm (the only servo this module owns)."""
    arm_park()


PCA_SLEEP = 0x10       # MODE1 SLEEP bit: oscillator off, all outputs off


def release_pca(pca) -> None:
    """All 16 channels fully OFF, then deinit, then sleep. Each step is tried
    even if an earlier one failed (I2C error)."""
    errors = []
    for ch in range(16):
        try:
            pca.channels[ch].duty_cycle = 0       # < 0x10 → LEDn_OFF full-off bit
        except Exception as exc:
            errors.append(f"ch{ch}: {exc!r}")
    try:
        pca.deinit()                              # MODE1 = 0 (auto-increment off)
    except Exception as exc:
        errors.append(f"deinit: {exc!r}")
    try:
        pca.mode1_reg = PCA_SLEEP                 # 1-byte write, unaffected by auto-increment
    except Exception as exc:
        errors.append(f"sleep: {exc!r}")
    if errors:
        print(f"[servos] PCA9685 release problems: {'; '.join(errors)}")


def deinit():
    """Switch every channel off and release the PCA9685 (call shuttle.deinit()
    first). Idempotent: a second call does nothing."""
    global _pca
    if _MOCK or not _pca:
        return
    pca, _pca = _pca, None
    _servos.clear()
    release_pca(pca)
