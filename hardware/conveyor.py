"""
Conveyor belt control via L9110S dual motor driver.
Two N20 gear motors (6V, 200rpm) drive the card transport rollers.

L9110S wiring:
  A-1A → GPIO 23 (Motor A forward)
  A-1B → GPIO 24 (Motor A reverse / brake)
  B-1A → GPIO 25 (Motor B forward)
  B-1B → GPIO 26 (Motor B reverse / brake)
  VCC  → 5V
  GND  → GND

Both motors run the same direction (card moves left→right).
Speed is controlled by software PWM (pigpio for accurate PWM on Pi Zero).
"""

from __future__ import annotations

import os
import time

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

if not _MOCK:
    import RPi.GPIO as GPIO

# GPIO BCM pin assignments
MOTOR_A_FWD = 23
MOTOR_A_REV = 24
MOTOR_B_FWD = 25
MOTOR_B_REV = 26

# Speed 0–100 (%)
DEFAULT_SPEED = 75   # enough to move cards reliably without flipping
PWM_FREQ_HZ  = 1000

_pwm_a: GPIO.PWM | None = None
_pwm_b: GPIO.PWM | None = None


def init():
    global _pwm_a, _pwm_b
    if _MOCK:
        print("[conveyor] MOCK mode — no hardware")
        return
    GPIO.setmode(GPIO.BCM)
    for pin in (MOTOR_A_FWD, MOTOR_A_REV, MOTOR_B_FWD, MOTOR_B_REV):
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

    _pwm_a = GPIO.PWM(MOTOR_A_FWD, PWM_FREQ_HZ)
    _pwm_b = GPIO.PWM(MOTOR_B_FWD, PWM_FREQ_HZ)
    _pwm_a.start(0)
    _pwm_b.start(0)
    print(f"[conveyor] L9110S initialized (A: GPIO{MOTOR_A_FWD}/{MOTOR_A_REV}, "
          f"B: GPIO{MOTOR_B_FWD}/{MOTOR_B_REV})")


def _coast() -> None:
    """All four inputs LOW = coast. REV pins first: if we are interrupted
    between the writes the bridge is left at IA=H,IB=L (forward, harmless)
    or all LOW — never IA=L,IB=H (reverse)."""
    GPIO.output(MOTOR_A_REV, GPIO.LOW)
    GPIO.output(MOTOR_B_REV, GPIO.LOW)
    _pwm_a.ChangeDutyCycle(0)
    _pwm_b.ChangeDutyCycle(0)


def run(speed: int = DEFAULT_SPEED):
    """Start conveyor moving cards forward."""
    if _MOCK:
        return
    speed = max(0, min(100, speed))
    GPIO.output(MOTOR_A_REV, GPIO.LOW)
    GPIO.output(MOTOR_B_REV, GPIO.LOW)
    _pwm_a.ChangeDutyCycle(speed)
    _pwm_b.ChangeDutyCycle(speed)


def stop():
    """Stop conveyor (coast): FWD and REV inputs all LOW."""
    if _MOCK:
        return
    _coast()


def brake():
    """Active brake: short the motor terminals briefly, then coast.

    L9110S truth table: IA=H, IB=H -> brake; IA=L, IB=L -> coast;
    IA=L, IB=H -> REVERSE. Order matters, because each write is separate:
      engage:  FWD 100 % first (IA=H,IB=L = forward), then REV HIGH (brake)
      release: REV LOW first (IA=H,IB=L = forward), then FWD 0 (coast)
    so no intermediate state is ever reverse. The release runs in a finally,
    so an exception during the 50 ms brake (e.g. a shutdown signal) still
    leaves the bridge coasting instead of half-way.
    """
    if _MOCK:
        return
    try:
        _pwm_a.ChangeDutyCycle(100)      # FWD input HIGH
        _pwm_b.ChangeDutyCycle(100)
        GPIO.output(MOTOR_A_REV, GPIO.HIGH)  # REV input HIGH -> both HIGH = brake
        GPIO.output(MOTOR_B_REV, GPIO.HIGH)
        time.sleep(0.05)
    finally:
        _coast()


def transport_card(travel_time_s: float = 1.2, speed: int = DEFAULT_SPEED):
    """
    Run conveyor for a fixed duration to move card from pickup to scanner.
    Adjust travel_time_s after physical calibration.
    """
    run(speed)
    time.sleep(travel_time_s)
    brake()


def deinit():
    """Coast (all inputs LOW), stop the soft PWM, free the pins. Idempotent."""
    global _pwm_a, _pwm_b
    if _MOCK or _pwm_a is None:
        return
    try:
        stop()
    finally:
        _pwm_a.stop()
        _pwm_b.stop()
        _pwm_a = _pwm_b = None
        GPIO.cleanup([MOTOR_A_FWD, MOTOR_A_REV, MOTOR_B_FWD, MOTOR_B_REV])
