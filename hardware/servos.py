"""
Servo control via PCA9685 (I2C address 0x40, 50Hz PWM).
Channels (the only servos this code drives):
  0 - Pickup arm    single-servo parallelogram arm (cad/suction_arm.scad):
                    ARM_PICK = cup on the top card in the hopper,
                    ARM_DROP = card 3 mm above the belt at X -95,
                    ARM_PARK = crank straight up (servo 90°)
  1 - Deflect gate  — floor select: left=lower floor (bins 0-3),
                      right=upper floor (bins 4-7), center=reject (bin 9)
  2 - Bin select    — column select: same 4 angles on both floors + reject
  3-15 - unused
Sort-gate levers (cad/sort_gate_lever.scad): 2 — one each on ch1 and ch2.

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

# PCA9685 channel map (keep in sync with scripts/calibrate_servos.py,
# scripts/test_hardware.py and cad/sort_gate_lever.scad header)
CH_PICKUP_ARM   = 0
CH_DEFLECT_GATE = 1
CH_BIN_SELECT   = 2
SERVO_CHANNELS  = (CH_PICKUP_ARM, CH_DEFLECT_GATE, CH_BIN_SELECT)

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
ARM_ACTUATION_RANGE = 180   # MG996R at 500–2500 µs; set 270 for a DS3218MG-270 drop-in
ARM_MAX_STEP_DEG = 4.0      # largest angle change per PWM update (≤200°/s peak; card sees <1 m/s²)
ARM_UPDATE_S = 0.02         # one update per 50 Hz PWM frame
ARM_FULL_MOVE_S = 1.2       # default time for the full pick↔drop arc (~170°)

# Legacy names (scripts/test_hardware.py, scripts/calibrate_servos.py): UP = park, DOWN = pick
PICKUP_ARM_UP    = ARM_PARK
PICKUP_ARM_DOWN  = ARM_PICK

GATE_LEFT  = 30          # route to bin group A (bins 0-3)
GATE_RIGHT = 150         # route to bin group B (bins 4-7)
GATE_CENTER = 90         # card passes straight (scanner feed)

# Bin select (ch2) positions for 8 bins: 2 floors × 4 columns.
# Lower floor (gate left):  bins 0,1,2,3 → angles 20,55,90,125
# Upper floor (gate right): bins 4,5,6,7 → same 4 angles, SAME ch2 servo
# (the deflect gate on ch1 picks the floor; ch2 only picks the column)
BIN_SELECT_ANGLES = {
    0: 20, 1: 55, 2: 90, 3: 125,   # bins 0-3 (row A)
    4: 20, 5: 55, 6: 90, 7: 125,   # bins 4-7 (row B, same angles)
    9: 160,                          # reject bin
}

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
    global GATE_LEFT, GATE_CENTER, GATE_RIGHT
    global BIN_SELECT_ANGLES

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

    gate = cal.get("gate", {})
    if "GATE_LEFT" in gate:
        GATE_LEFT = gate["GATE_LEFT"]
    if "GATE_CENTER" in gate:
        GATE_CENTER = gate["GATE_CENTER"]
    if "GATE_RIGHT" in gate:
        GATE_RIGHT = gate["GATE_RIGHT"]

    bin_sel = cal.get("bin_select", {})
    for raw_key, angle in bin_sel.items():
        # Keys are stored as "BIN_0" → map to integer 0, "BIN_9_REJECT" → 9
        label = raw_key  # e.g. "BIN_3" or "BIN_9_REJECT"
        if label.startswith("BIN_"):
            suffix = label[4:]
            try:
                bin_num = int(suffix.split("_")[0])  # handles "9_REJECT" → 9
                BIN_SELECT_ANGLES[bin_num] = angle
            except ValueError:
                pass

    print(f"[servos] Loaded calibration from {_CALIBRATION_FILE}")


def init():
    """Initialize PCA9685 and attach servo objects."""
    global _pca, _servos

    # Apply calibration overrides before any hardware move
    _load_calibration()

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


def route_card(bin_number: int, settle_s=0.3):
    """
    Set gate and bin-select servo positions for target bin.
    Call before card reaches the sort gate.
    """
    if bin_number not in BIN_SELECT_ANGLES:
        raise ValueError(f"Unknown bin: {bin_number}. Valid: {list(BIN_SELECT_ANGLES)}")

    if _MOCK:
        print(f"[servos] MOCK route_card → bin {bin_number}")
        time.sleep(settle_s)
        return

    # Gate direction
    if bin_number <= 3:
        _servos[CH_DEFLECT_GATE].angle = GATE_LEFT
    elif bin_number == 9:
        _servos[CH_DEFLECT_GATE].angle = GATE_CENTER  # reject chute
    else:
        _servos[CH_DEFLECT_GATE].angle = GATE_RIGHT

    # Bin select position
    _servos[CH_BIN_SELECT].angle = BIN_SELECT_ANGLES[bin_number]
    time.sleep(settle_s)


def reset_all():
    """Return all servos to neutral/home positions."""
    arm_park()
    if _MOCK:
        return
    _servos[CH_DEFLECT_GATE].angle = GATE_CENTER
    _servos[CH_BIN_SELECT].angle = 90
    time.sleep(0.5)


def deinit():
    """Release PCA9685."""
    if _MOCK or not _pca:
        return
    _pca.deinit()
