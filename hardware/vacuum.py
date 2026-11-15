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

HARDWARE REQUIREMENTS (docs/ASSEMBLY.md §14.2):
  * 10 kΩ pull-up from GPIO 17 to 3.3 V, and the same on GPIO 27 (vent).
    GPIO 17 / 27 reset to INPUTS with the SoC's default pull-DOWN, which an
    active-LOW relay board reads as ON. That is the state at power-up / boot
    (before init()), and — with the kernel parameter
    pinctrl_bcm2835.persist_gpio_outputs=0 that scripts/setup.sh adds to
    cmdline.txt — after the process exits or deinit()'s GPIO.cleanup()
    releases the line. The pull-up makes such a released pin read HIGH = OFF.
  * A flyback diode across EACH coil: the 12 V pump motor and the 12 V vent
    solenoid (1N5819 or 1N4007), mounted at the device. The relay switches
    the + side (COM = 12 V, NO → device +; device − → GND), so each diode
    goes cathode (stripe) to the device's + terminal and anode to its −
    (GND) (docs/ASSEMBLY.md §14.1, §14.6). The relay modules' own diodes only protect
    their relay coils, not the loads the contacts switch; without these the
    inductive kick arcs the relay contacts and couples spikes into the Pi.

What happens when the process dies (corrected, audit M9): Raspberry Pi
kernels default to persist_gpio_outputs=1, i.e. a line that was an OUTPUT
STAYS DRIVEN at its last level when the process holding it exits or is
killed — a pump left ON stays ON; the pull-up cannot help. Two layers fix
that: setup.sh sets persist_gpio_outputs=0 (freed lines revert to inputs →
pull-ups → OFF), and the systemd unit's ExecStopPost runs
scripts/safe_outputs.py, which drives the pump / vent / belt / stepper pins
to their safe levels and puts the PCA9685 to sleep after ANY exit (clean,
crash, SIGKILL, watchdog). Power loss is safe by itself (relay NO contacts
open: pump off, valve closed).

Option B (cad_b/, machine "b" in config/machine.json): ONE relay, a KY-019
module, which is ACTIVE-HIGH (transistor driver: IN high = relay on), and NO
vent valve — a pin-hole bleed in the airline tee releases the card ~0.5-1 s
after the pump stops. So on B the defaults are RELAY_ACTIVE_LOW = False,
VENT_PIN = None and release() waits RELEASE_FALLBACK_S (the bleed time,
default 0.8 s; config "vacuum.RELEASE_FALLBACK_S" or sorter_b's BLEED_S).
GPIO 17 resets to an input with the SoC's pull-DOWN, which an active-high
relay reads as OFF, so B needs no external resistor; scripts/setup.sh adds
"gpio=17=ip,pd" to config.txt to make that explicit (cad_b/README.md,
"Pin map (option B)"). Every value can be overridden in the "vacuum" section
of config/machine.json on either machine.

Option B drives the relay through pigpiod (USE_PIGPIO), not RPi.GPIO: a pin
pigpiod drives KEEPS its level after the sorter process exits (the daemon owns
it; persist_gpio_outputs does not apply). B never lets go of a card except over
the bed or a bin (sorter_b.py), so a card held on the cup elsewhere must stay
held across a crash or a service stop: teardown calls deinit(keep_on=True),
scripts/safe_outputs.py leaves the relay alone while the machine record says
"pump_hold", and the next start's init(hold=True) keeps it on.
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

import sys as _sys
from hardware import machine_config as _machine_config

if _machine_config.machine() == "b":
    # option B: KY-019 active-HIGH relay, pin-hole bleed instead of a vent valve
    RELAY_ACTIVE_LOW = False
    VENT_PIN = None
    RELEASE_FALLBACK_S = 0.8
_machine_config.apply(_sys.modules[__name__], "vacuum", (
    "RELAY_PIN", "RELAY_ACTIVE_LOW", "VENT_PIN", "VENT_ACTIVE_LOW", "VENT_S", "RELEASE_FALLBACK_S"))

# MOCK only: called with the new pump state on every pump_on()/pump_off(), so
# a simulated machine (hardware/b_mock.py) can attach / drop the card.
_mock_listener = None

USE_PIGPIO = _machine_config.machine() == "b"
_pi = None              # pigpio connection (option B)
_pump = False           # last commanded state (also tracked in MOCK)
_vent = False
_initialized = False


def _level(on: bool, active_low: bool) -> int:
    if active_low:
        return GPIO.LOW if on else GPIO.HIGH
    return GPIO.HIGH if on else GPIO.LOW


def _relay_write(on: bool) -> None:
    if _pi is not None:
        high = on != RELAY_ACTIVE_LOW
        _pi.write(RELAY_PIN, 1 if high else 0)
    else:
        GPIO.output(RELAY_PIN, _level(on, RELAY_ACTIVE_LOW))


def init(hold: bool = False):
    """Pump OFF — or, hold=True (option B: the machine record says a card is
    held on the cup), pump kept ON so the card is not dropped."""
    global _initialized, _pump, _vent, _pi
    _pump, _vent = bool(hold), False
    if _MOCK:
        _initialized = True
        print("[vacuum] MOCK mode — no hardware" + (" (pump kept ON: card held)" if hold else ""))
        if hold and _mock_listener is not None:
            _mock_listener(True)
        return
    if USE_PIGPIO:
        import pigpio
        _pi = pigpio.pi()
        if not _pi.connected:
            _pi = None
            raise RuntimeError("cannot reach pigpiod for the pump relay — sudo systemctl enable --now pigpiod")
        _relay_write(bool(hold))
        _initialized = True
        print(f"[vacuum] pump relay on GPIO {RELAY_PIN} via pigpiod"
              + (" — kept ON (card held on the cup)" if hold else ""))
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
        if _mock_listener is not None:
            _mock_listener(True)
        return
    _relay_write(True)


def pump_off():
    """Deactivate vacuum pump (relay opens)."""
    global _pump
    _pump = False
    if _MOCK:
        if _mock_listener is not None:
            _mock_listener(False)
        return
    _relay_write(False)


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


def release(vent_s: float | None = None, bleed_s: float | None = None):
    """Drop the card: pump off, vent the line to atmosphere for vent_s, close
    the vent. Without a vent valve (option B: pin-hole bleed), just wait
    bleed_s (default RELEASE_FALLBACK_S). The vent is closed again even if the
    wait is interrupted."""
    pump_off()
    if VENT_PIN is None:
        time.sleep(RELEASE_FALLBACK_S if bleed_s is None else bleed_s)
        return
    if vent_s is None:
        vent_s = VENT_S
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


def deinit(keep_on: bool = False):
    """Pump off, vent closed, pins freed. Idempotent. keep_on (option B, card
    held): leave the pump running — pigpiod keeps the relay pin driven."""
    global _initialized, _pi
    if _MOCK:
        _initialized = False
        return
    if not _initialized:
        return
    if _pi is not None:
        try:
            if not keep_on:
                _relay_write(False)
        finally:
            _initialized = False
            pi, _pi = _pi, None
            pi.stop()
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
