"""
Vacuum pump control via GPIO relay.
Relay module: active LOW (GPIO LOW = pump ON).
GPIO 17 → relay IN pin.
"""

import time
import RPi.GPIO as GPIO

RELAY_PIN = 17  # BCM numbering

def init():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.HIGH)  # HIGH = pump OFF
    print(f"[vacuum] Relay initialized on GPIO {RELAY_PIN}")


def pump_on():
    """Activate vacuum pump (relay closes)."""
    GPIO.output(RELAY_PIN, GPIO.LOW)


def pump_off():
    """Deactivate vacuum pump (relay opens)."""
    GPIO.output(RELAY_PIN, GPIO.HIGH)


def pulse(duration_s=0.3):
    """Short pump burst (e.g. to release card)."""
    pump_on()
    time.sleep(duration_s)
    pump_off()


def deinit():
    pump_off()
    GPIO.cleanup(RELAY_PIN)
