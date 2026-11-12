"""
Servo control via PCA9685 (I2C address 0x40, 50Hz PWM).
Channels:
  0 - Pickup arm    single-servo parallelogram arm (cad/suction_arm.scad):
                    ARM_PICK = cup on the top card in the hopper,
                    ARM_DROP = card 3 mm above the belt at X -95,
                    ARM_PARK = crank straight up (servo 90°)
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
# crank straight up; increasing angle swings the cup towards the hopper. The
# working arc is symmetric about 90°, so if your servo turns the other way just
# swap ARM_PICK and ARM_DROP (calibration file) — it never leaves the safe arc.
ARM_PICK = 175   # crank 178°: cup lip 3 mm below the top card (Z 90.9), spring slider takes it
ARM_DROP = 5     # crank 8°: card underside 3 mm above the belt, card centre X -95
ARM_PARK = 90    # crank vertical: hand over X -155 at the top of the arc (rest / refill)
ARM_ACTUATION_RANGE = 180   # MG996R at 500–2500 µs; 270 for a DS3218MG-270 drop-in:
                            # config/machine.json {"servos": {"ARM_ACTUATION_RANGE": 270}}
                            # (then re-calibrate the arm angles)
ARM_MAX_STEP_DEG = 4.0      # largest angle change per PWM update (≤200°/s peak; card sees <1 m/s²)
ARM_UPDATE_S = 0.02         # one update per 50 Hz PWM frame
ARM_FULL_MOVE_S = 1.2       # default time for the full pick↔drop arc (~170°)

# Legacy names (scripts/test_hardware.py, scripts/calibrate_servos.py): UP = park, DOWN = pick
PICKUP_ARM_UP    = ARM_PARK
PICKUP_ARM_DOWN  = ARM_PICK

import sys as _sys
from hardware import machine_config as _machine_config
_machine_config.apply(_sys.modules[__name__], "servos", ("ARM_ACTUATION_RANGE",))

_pca = None
_servos = {}
_arm_angle = None   # last commanded ch0 angle (None until the first move)


def _load_calibration() -> None:
    """Override module-level angle constants from servo_calibration.json if present.

    Pickup arm keys (section "pickup_arm"): ARM_PICK, ARM_DROP, ARM_PARK.
    Legacy keys from older calibrations are still honoured when the new key is
    absent: ARM_DOWN → ARM_PICK, ARM_UP → ARM_PARK. (An old ARM_DOWN was taken
    with the previous swing arm and is wrong for the parallelogram arm —
    re-calibrate with the new labels.)
    """
    global ARM_PICK, ARM_DROP, ARM_PARK, PICKUP_ARM_UP, PICKUP_ARM_DOWN

    if not _CALIBRATION_FILE.exists():
        return

    try:
        with open(_CALIBRATION_FILE) as f:
            cal = json.load(f)
    except Exception as exc:
        print(f"[servos] Warning: could not read calibration file: {exc}")
        return

    arm = cal.get("pickup_arm", {})
    if "ARM_PICK" in arm:
        ARM_PICK = arm["ARM_PICK"]
    elif "ARM_DOWN" in arm:
        ARM_PICK = arm["ARM_DOWN"]
        print("[servos] Warning: using legacy ARM_DOWN as ARM_PICK — re-calibrate ch0 (ARM_PICK/ARM_DROP/ARM_PARK)")
    if "ARM_DROP" in arm:
        ARM_DROP = arm["ARM_DROP"]
    if "ARM_PARK" in arm:
        ARM_PARK = arm["ARM_PARK"]
    elif "ARM_UP" in arm:
        ARM_PARK = arm["ARM_UP"]
    PICKUP_ARM_UP, PICKUP_ARM_DOWN = ARM_PARK, ARM_PICK
    # (old "gate"/"bin_select" sections are ignored: those servos are now the
    #  shuttle's, calibrated in config/shuttle_calibration.json)


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
    the machine clear — goes straight to its target."""
    global _pca, _servos, _arm_angle

    # Apply calibration overrides before any hardware move
    _load_calibration()
    _arm_angle = float(ARM_PARK) if assume_parked else None

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
        _servos[CH_PICKUP_ARM].angle = _arm_angle   # hold the assumed rest pose (no motion if there)
    print("[servos] PCA9685 initialized on I2C 0x40")


def _arm_write(angle: float) -> None:
    global _arm_angle
    if not _MOCK:
        _servos[CH_PICKUP_ARM].angle = angle
    _arm_angle = angle


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
    target = max(0.0, min(float(ARM_ACTUATION_RANGE), float(target)))
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
    """Crank straight up: hopper and belt both clear (rest / refill position)."""
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
