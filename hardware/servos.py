"""
Servo control via PCA9685 (I2C address 0x40, 50Hz PWM).
Channels:
  0 - Pickup arm    (down=pickup, up=rest)
  1 - Deflect gate  (left=bin_A, right=bin_B)
  2 - Bin select    (rotates to target bin position)

Requires: adafruit-circuitpython-pca9685, adafruit-circuitpython-motor
"""

import os
import time

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

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

# Bin select positions for 8 bins in 2 rows of 4
# Row A (gate left): bins 0,1,2,3  →  angles 20,50,80,110
# Row B (gate right): bins 4,5,6,7 →  angles 20,50,80,110 (second servo)
BIN_SELECT_ANGLES = {
    0: 20, 1: 55, 2: 90, 3: 125,   # bins 0-3 (row A)
    4: 20, 5: 55, 6: 90, 7: 125,   # bins 4-7 (row B, same angles)
    9: 160,                          # reject bin
}

_pca = None
_servos = {}


def init():
    """Initialize PCA9685 and attach servo objects."""
    global _pca, _servos
    if _MOCK:
        print("[servos] MOCK mode — no hardware")
        return
    i2c = busio.I2C(board.SCL, board.SDA)
    _pca = PCA9685(i2c, address=0x40)
    _pca.frequency = 50
    _servos[0] = adafruit_servo.Servo(_pca.channels[0], min_pulse=500, max_pulse=2500)
    _servos[1] = adafruit_servo.Servo(_pca.channels[1], min_pulse=500, max_pulse=2500)
    _servos[2] = adafruit_servo.Servo(_pca.channels[2], min_pulse=500, max_pulse=2500)
    print("[servos] PCA9685 initialized on I2C 0x40")


def pickup_arm_down(settle_s=0.4):
    """Lower suction arm to card surface."""
    if _MOCK:
        time.sleep(settle_s); return
    _servos[0].angle = PICKUP_ARM_DOWN
    time.sleep(settle_s)


def pickup_arm_up(settle_s=0.4):
    """Raise suction arm to resting position."""
    if _MOCK:
        time.sleep(settle_s); return
    _servos[0].angle = PICKUP_ARM_UP
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
        _servos[1].angle = GATE_LEFT
    elif bin_number == 9:
        _servos[1].angle = GATE_CENTER  # reject chute
    else:
        _servos[1].angle = GATE_RIGHT

    # Bin select position
    _servos[2].angle = BIN_SELECT_ANGLES[bin_number]
    time.sleep(settle_s)


def reset_all():
    """Return all servos to neutral/home positions."""
    if _MOCK:
        return
    _servos[0].angle = PICKUP_ARM_UP
    _servos[1].angle = GATE_CENTER
    _servos[2].angle = 90
    time.sleep(0.5)


def deinit():
    """Release PCA9685."""
    if _MOCK or not _pca:
        return
    _pca.deinit()
