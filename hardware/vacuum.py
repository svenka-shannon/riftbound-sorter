"""
Vacuum pump control via GPIO relay.
Relay module: active LOW (GPIO LOW = pump ON).
GPIO 17 → relay IN pin.

HARDWARE REQUIREMENT (docs/ASSEMBLY.md §3d, audit B-14): a 10 kΩ pull-up
from GPIO 17 to 3.3 V. Whenever this module is NOT driving the pin — during
boot, after deinit()'s GPIO.cleanup() (pin reverts to an input), or if the
process dies — GPIO 17 floats with the SoC's default pull-DOWN, which this
active-LOW relay reads as pump ON. The external pull-up makes "floating" mean
HIGH = pump OFF. Power loss is already safe (relay NO contact opens).
"""

import os
import time

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

if not _MOCK:
    import RPi.GPIO as GPIO

RELAY_PIN = 17  # BCM numbering

def init():
    if _MOCK:
        print("[vacuum] MOCK mode — no hardware")
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.HIGH)  # HIGH = pump OFF
    print(f"[vacuum] Relay initialized on GPIO {RELAY_PIN}")


def pump_on():
    """Activate vacuum pump (relay closes)."""
    if _MOCK:
        return
    GPIO.output(RELAY_PIN, GPIO.LOW)


def pump_off():
    """Deactivate vacuum pump (relay opens)."""
    if _MOCK:
        return
    GPIO.output(RELAY_PIN, GPIO.HIGH)


def pulse(duration_s=0.3):
    """Short pump burst. NOTE: this turns suction ON — it grabs, it does not release a card."""
    pump_on()
    time.sleep(duration_s)
    pump_off()


def deinit():
    if _MOCK:
        return
    pump_off()
    # cleanup() returns the pin to an input; only the external 10 kΩ pull-up
    # to 3.3 V keeps the relay (active LOW) off after this point.
    GPIO.cleanup(RELAY_PIN)
