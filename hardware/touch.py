"""
Option B cup touch contact (cad_b/README.md rounds 2-3).

The cup hangs on a gravity-loaded slider. A 608 bearing ring on the slider
rests on three M3 button heads; two of them are wired as a switch:
  one head → GND, the other → PIN (input, internal pull-up)
  resting (cup hanging free) → contact CLOSED → PIN reads LOW
  cup touching a card / stack / the bed → slider lifts → contact OPEN → HIGH
A broken wire reads OPEN ("touching"): lowering stops at once and the
start-up / pre-descent checks refuse a contact that is open with the cup
hanging free, so the fault is caught, never driven through.

is_open() needs DEBOUNCE_READS consecutive open reads (arm vibration can
chatter the contact for a moment); is_closed() needs as many closed reads.
"""

import os
import sys
import time

from hardware import machine_config

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

PIN = 16                 # BCM, header pin 36 (cad_b/README.md "Pin map (option B)")
DEBOUNCE_READS = 3
DEBOUNCE_S = 0.002

machine_config.apply(sys.modules[__name__], "touch", ("PIN", "DEBOUNCE_READS", "DEBOUNCE_S"))

_GPIO = None
_initialized = False


def init():
    global _GPIO, _initialized
    if _MOCK:
        _initialized = True
        return
    import RPi.GPIO as GPIO
    _GPIO = GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    _initialized = True
    print(f"[touch] cup contact on GPIO {PIN} (closed = resting, open = touching)")


def raw_open() -> bool:
    if _MOCK:
        from hardware import b_mock
        return b_mock.WORLD.touch_open()
    return _GPIO.input(PIN) == _GPIO.HIGH


def _all(want_open: bool) -> bool:
    for i in range(DEBOUNCE_READS):
        if raw_open() != want_open:
            return False
        if i + 1 < DEBOUNCE_READS and DEBOUNCE_S and not _MOCK:
            time.sleep(DEBOUNCE_S)
    return True


def is_open() -> bool:
    """Touching (debounced): the cup / card rests on something."""
    return _all(True)


def is_closed() -> bool:
    """Hanging free (debounced)."""
    return _all(False)


def deinit():
    global _initialized
    if not _MOCK and _initialized and _GPIO is not None:
        try:
            _GPIO.cleanup([PIN])
        except Exception as exc:
            print(f"[touch] GPIO cleanup failed: {exc!r}")
    _initialized = False
