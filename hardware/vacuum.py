"""
Vacuum pump + vent valve control via a 2-channel relay module (active LOW).

  GPIO 17 [header pin 11] → relay IN1 → 12 V vacuum pump
  GPIO 27 [header pin 13] → relay IN2 → 12 V normally-CLOSED mini solenoid
                            vent valve, teed into the vacuum line between the
                            pump and the cup; energised = OPEN to atmosphere

Why the vent: the relay only cuts the pump, and the cup + hose stay evacuated
for a while, so the card may still hang on the cup when the arm lifts away.
release() = pump off, vent open VENT_S, vent closed. A normally-closed valve
is closed (sealed) without power, so a dead relay/valve never leaks the vacuum
during a pick; only the active vent pulse opens it.

Relay semantics are configurable (RELAY_ACTIVE_LOW / VENT_ACTIVE_LOW): most
5 V opto relay boards switch ON when IN is pulled LOW. Set VENT_PIN = None to
run without a vent valve (falls back to waiting RELEASE_FALLBACK_S).

HARDWARE REQUIREMENT (docs/ASSEMBLY.md §3d, audit B-14): a 10 kΩ pull-up
from GPIO 17 to 3.3 V — and the same on GPIO 27 for the vent channel.
Whenever this module is NOT driving a pin — during boot, after deinit()'s
GPIO.cleanup() (pin reverts to an input), or if the process dies — the pin
floats with the SoC's default pull-DOWN, which an active-LOW relay reads as ON.
The external pull-up makes "floating" mean HIGH = OFF. (A floating vent is
harmless — it only opens the line — but the pull-up keeps the coil cold.)
Power loss is already safe (relay NO contacts open: pump off, valve closed).
"""

import os
import time

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

if not _MOCK:
    import RPi.GPIO as GPIO

RELAY_PIN = 17          # BCM numbering — pump relay
VENT_PIN = 27           # BCM numbering — vent valve relay (None = no vent valve fitted)
RELAY_ACTIVE_LOW = True
VENT_ACTIVE_LOW = True
VENT_S = 0.4            # vent open time during release()
RELEASE_FALLBACK_S = 0.3  # no vent valve: wait for the cup to leak down

_pump = False           # last commanded state (also tracked in MOCK)
_vent = False
_initialized = False


def _level(on: bool, active_low: bool) -> int:
    if active_low:
        return GPIO.LOW if on else GPIO.HIGH
    return GPIO.HIGH if on else GPIO.LOW


def init():
    global _initialized, _pump, _vent
    _pump = _vent = False
    if _MOCK:
        _initialized = True
        print("[vacuum] MOCK mode — no hardware")
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_PIN, GPIO.OUT, initial=_level(False, RELAY_ACTIVE_LOW))   # pump OFF
    if VENT_PIN is not None:
        GPIO.setup(VENT_PIN, GPIO.OUT, initial=_level(False, VENT_ACTIVE_LOW))  # vent CLOSED
    _initialized = True
    print(f"[vacuum] pump relay on GPIO {RELAY_PIN}, vent valve "
          f"{'GPIO ' + str(VENT_PIN) if VENT_PIN is not None else 'not fitted'}")


def pump_on():
    """Activate vacuum pump (relay closes). Closes the vent first."""
    global _pump
    vent_close()
    _pump = True
    if _MOCK:
        return
    GPIO.output(RELAY_PIN, _level(True, RELAY_ACTIVE_LOW))


def pump_off():
    """Deactivate vacuum pump (relay opens)."""
    global _pump
    _pump = False
    if _MOCK:
        return
    GPIO.output(RELAY_PIN, _level(False, RELAY_ACTIVE_LOW))


def vent_open():
    global _vent
    if VENT_PIN is None:
        return
    _vent = True
    if not _MOCK:
        GPIO.output(VENT_PIN, _level(True, VENT_ACTIVE_LOW))


def vent_close():
    global _vent
    if VENT_PIN is None:
        return
    _vent = False
    if not _MOCK:
        GPIO.output(VENT_PIN, _level(False, VENT_ACTIVE_LOW))


def release(vent_s: float = VENT_S):
    """Drop the card: pump off, vent the line to atmosphere for vent_s, close
    the vent. Without a vent valve, just wait RELEASE_FALLBACK_S. The vent is
    closed again even if the wait is interrupted."""
    pump_off()
    if VENT_PIN is None:
        time.sleep(RELEASE_FALLBACK_S)
        return
    try:
        vent_open()
        time.sleep(vent_s)
    finally:
        vent_close()


def vent():
    """Alias of release()."""
    release()


def pump_is_on() -> bool:
    return _pump


def vent_is_open() -> bool:
    return _vent


def pulse(duration_s=0.3):
    """Short pump burst. NOTE: this turns suction ON — it grabs, it does not release a card."""
    pump_on()
    time.sleep(duration_s)
    pump_off()


def deinit():
    """Pump off, vent closed, pins freed. Idempotent."""
    global _initialized
    if _MOCK:
        _initialized = False
        return
    if not _initialized:
        return
    try:
        pump_off()
        vent_close()
    finally:
        _initialized = False
        # cleanup() returns the pins to inputs; only the external 10 kΩ pull-ups
        # to 3.3 V keep the active-LOW relays off after this point.
        pins = [RELAY_PIN] + ([VENT_PIN] if VENT_PIN is not None else [])
        GPIO.cleanup(pins)
