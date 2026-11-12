"""
Servo control via PCA9685 (I2C address 0x40, 50Hz PWM).
Channels (the only servos this code drives):
  0 - Pickup arm    (down=pickup, up=rest)
  1 - Deflect gate  — floor select: left=lower floor (bins 0-3),
                      right=upper floor (bins 4-7), center=reject (bin 9)
  2 - Bin select    — column select: same 4 angles on both floors + reject
  3-15 - unused
Sort-gate levers (cad/sort_gate_lever.scad): 2 — one each on ch1 and ch2.

Requires: adafruit-circuitpython-pca9685, adafruit-circuitpython-motor
"""

import json
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

# Servo angle presets (degrees)
PICKUP_ARM_UP    = 90    # resting position
PICKUP_ARM_DOWN  = 10    # card pickup position

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


def _load_calibration() -> None:
    """Override module-level angle constants from servo_calibration.json if present."""
    global PICKUP_ARM_UP, PICKUP_ARM_DOWN
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
    if "ARM_UP" in arm:
        PICKUP_ARM_UP = arm["ARM_UP"]
    if "ARM_DOWN" in arm:
        PICKUP_ARM_DOWN = arm["ARM_DOWN"]

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
        _servos[ch] = adafruit_servo.Servo(_pca.channels[ch], min_pulse=500, max_pulse=2500)
    print("[servos] PCA9685 initialized on I2C 0x40")


def pickup_arm_down(settle_s=0.4):
    """Lower suction arm to card surface."""
    if _MOCK:
        time.sleep(settle_s); return
    _servos[CH_PICKUP_ARM].angle = PICKUP_ARM_DOWN
    time.sleep(settle_s)


def pickup_arm_up(settle_s=0.4):
    """Raise suction arm to resting position."""
    if _MOCK:
        time.sleep(settle_s); return
    _servos[CH_PICKUP_ARM].angle = PICKUP_ARM_UP
    time.sleep(settle_s)


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
    if _MOCK:
        return
    _servos[CH_PICKUP_ARM].angle = PICKUP_ARM_UP
    _servos[CH_DEFLECT_GATE].angle = GATE_CENTER
    _servos[CH_BIN_SELECT].angle = 90
    time.sleep(0.5)


def deinit():
    """Release PCA9685."""
    if _MOCK or not _pca:
        return
    _pca.deinit()
