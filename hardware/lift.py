"""
Option B lift: one MG996R on PCA9685 channel CHANNEL (0) drives the
parallelogram (cad_b/). Everything here is in LINK ANGLE th (deg, + = up):
TH_MIN -6 (lowest, reaches an empty bin floor) .. TH_FULL +10 (full lift: the
card bottom is 21 mm over every wall — the only height at which yaw may move).
Lip height z = 17 + 220·sin(th) mm (hardware/b_geometry.py).

Servo mapping: two calibrated [th, servo angle] points (config/b_calibration.json
"servo_map"), linear. Commands outside [TH_MIN, TH_FULL] are refused
(LiftLimitError), never clamped silently.

Full-lift interlock: at_full_lift() is True only when the last command was
TH_FULL, the move finished and SETTLE_S passed (the arm rings), and the servo
is powered. yaw_permitted() (registered with hardware/yaw.py) also wants the
touch contact CLOSED — the cup hanging free, not resting on a pile. Hobby
servos have no feedback: "at full lift" means "commanded and settled".

Touch-down (lower_until_touch):
  1. the contact must read CLOSED first (else TouchFault: wire, stuck slider);
  2. down to approach_th in frames of at most DESCENT_STEP_DEG (any move that
     watches the contact uses these small frames, never the 1.5 deg fast
     ones), the contact read after every frame — an unexpected surface
     (overfull bin) stops it within one frame (~1.7 mm);
  3. single DESCENT_STEP_DEG steps (~one PCA9685 count) with the contact read
     after each, until it OPENS or limit_th is reached;
  4. on contact: back UP to the last th at which the contact still read
     closed (the surface is between it and the step that opened), then at
     most `overtravel_mm` (<= MAX_OVERTRAVEL_MM, slider travel 10 mm) below
     THAT, and never any further. So the slider compression is at most
     overtravel_mm, whatever the step size.
  The caller bounds limit_th by where the surface can be (sorter_b: the last
  hopper touch, a bin's card count), so a contact stuck CLOSED cannot drive
  the cup through a full stack to the floor.
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass

from hardware import b_calibration as cal
from hardware import b_geometry as geo
from hardware import machine_config, touch

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

CHANNEL = 0
ACTUATION_RANGE = 180        # MG996R at 500-2500 us
MAX_STEP_DEG = 1.5           # th change per 50 Hz frame in a ramp (75 deg/s)
FULL_MOVE_S = 0.5            # ramp time for the whole TH_MIN..TH_FULL range
DESCENT_STEP_DEG = 0.44      # one PCA9685 count at 50 Hz ≈ 0.44 servo deg ≈ 1.7 mm at the cup
DESCENT_STEP_S = 0.04        # per descent step: two PWM frames for the servo to get there
SETTLE_S = 0.25              # after reaching full lift: the arm's vertical ringing dies down
MAX_OVERTRAVEL_MM = 5.0      # after touch-down, never more than this (slider travel 10 mm)
UPDATE_S = 0.02

machine_config.apply(sys.modules[__name__], "lift", (
    "CHANNEL", "ACTUATION_RANGE", "MAX_STEP_DEG", "FULL_MOVE_S", "DESCENT_STEP_DEG",
    "DESCENT_STEP_S", "SETTLE_S", "MAX_OVERTRAVEL_MM"))


class LiftError(RuntimeError):
    """The lift could not do what was asked."""


class LiftLimitError(LiftError):
    """A th outside [TH_MIN, TH_FULL] was commanded (refused)."""


class TouchFault(LiftError):
    """The touch contact reads something it cannot (open with the cup hanging free)."""


@dataclass
class TouchResult:
    touched: bool
    th_touch: float | None      # th at which the contact first read open
    th_end: float               # th after the overtravel (or the limit if no touch)
    th_closed: float | None = None   # last th with the contact closed (surface is below it)


_pca = None
_servo = None
_th = None                  # last commanded th (None: unknown, never written since init)
_settled = False            # at TH_FULL, move finished, SETTLE_S waited
_released = False           # channel off (limp)


def servo_angle_for(th: float) -> float:
    (t0, s0), (t1, s1) = cal.servo_map()
    return s0 + (s1 - s0) * (float(th) - t0) / (t1 - t0)


def th() -> float | None:
    return _th


def init(assume_full: bool = False):
    """PCA9685 up. assume_full (clean stop, rest pose recorded): ONE write to
    TH_FULL (a limp arm snaps back up — upward is always clear). Otherwise
    nothing is written until the first command."""
    global _pca, _servo, _th, _settled, _released
    cal.get()                                 # BCalibrationError before anything moves
    _th, _settled, _released = None, False, False
    if not _MOCK:
        import board
        import busio
        from adafruit_motor import servo as adafruit_servo
        from adafruit_pca9685 import PCA9685
        _pca = PCA9685(busio.I2C(board.SCL, board.SDA), address=0x40)
        _pca.frequency = 50
        _servo = adafruit_servo.Servo(_pca.channels[CHANNEL], actuation_range=ACTUATION_RANGE,
                                      min_pulse=500, max_pulse=2500)
        print(f"[lift] PCA9685 ch{CHANNEL}, servo map {cal.servo_map()}")
    if assume_full:
        _write(geo.TH_FULL)


def _write(t: float) -> None:
    global _th, _settled, _released
    if not geo.TH_MIN - 1e-9 <= t <= geo.TH_FULL + 1e-9:
        raise LiftLimitError(f"lift th {t:.2f} is outside [{geo.TH_MIN:g}, {geo.TH_FULL:g}]")
    angle = servo_angle_for(t)
    if not 0.0 <= angle <= ACTUATION_RANGE:
        raise LiftLimitError(f"th {t:.2f} maps to servo {angle:.1f}, outside 0..{ACTUATION_RANGE}")
    if _MOCK:
        from hardware import b_mock
        b_mock.WORLD.set_th(t)
    else:
        _servo.angle = angle
    _th, _settled, _released = float(t), False, False


def write_raw_servo(angle: float) -> None:
    """Calibration only: command a raw servo angle (th unknown afterwards)."""
    global _th, _settled, _released
    if not 0.0 <= angle <= ACTUATION_RANGE:
        raise LiftLimitError(f"servo angle {angle} outside 0..{ACTUATION_RANGE}")
    if not _MOCK:
        _servo.angle = float(angle)
    _th, _settled, _released = None, False, False


_last_closed = None         # last th at which a watched move read the contact closed


def move_to(target: float, duration_s: float | None = None, watch_touch: bool = False) -> bool:
    """Cosine ramp to target (refused outside the range); the target is
    always written, also for a zero-length move. watch_touch (pose must be
    known): frames of at most DESCENT_STEP_DEG, contact read after each;
    stop at the first open reading and return True."""
    global _last_closed
    if not geo.TH_MIN - 1e-9 <= target <= geo.TH_FULL + 1e-9:
        raise LiftLimitError(f"lift th {target:.2f} is outside [{geo.TH_MIN:g}, {geo.TH_FULL:g}]")
    start = _th
    if start is None:
        if watch_touch:
            raise LiftError("lift pose unknown — a watched move needs a known start (lift to full first)")
        _write(target)
        time.sleep(0.3)
        return False
    delta = target - start
    if abs(delta) < 1e-9:
        _write(target)
        return watch_touch and touch.is_open()
    if duration_s is None:
        duration_s = max(0.1, FULL_MOVE_S * abs(delta) / (geo.TH_FULL - geo.TH_MIN))
    frame = DESCENT_STEP_DEG if watch_touch else MAX_STEP_DEG
    n = max(1, round(duration_s / UPDATE_S), math.ceil(math.pi * abs(delta) / (2 * frame)))
    if watch_touch:
        _last_closed = start
    for i in range(1, n + 1):
        _write(start + delta * (1 - math.cos(math.pi * i / n)) / 2)
        time.sleep(UPDATE_S)
        if watch_touch:
            if touch.is_open():
                return True
            _last_closed = _th
    _write(target)
    return False


def invalidate() -> None:
    """The servo map changed: the commanded th no longer says where the arm is."""
    global _th, _settled
    _th, _settled = None, False


def to_full() -> None:
    """Up to TH_FULL (direct if the pose is unknown), ALWAYS ending with a write
    of TH_FULL (so a changed servo map is applied), then settle."""
    global _settled
    if _th is None or _released:
        _write(geo.TH_FULL)
        time.sleep(0.3)
    else:
        move_to(geo.TH_FULL)              # always ends with a write of TH_FULL
    time.sleep(SETTLE_S)
    _settled = True


def raise_by_mm(mm: float, duration_s: float) -> None:
    """Slow first lift after a release (a card still stuck to the cup peels off)."""
    if _th is None or mm <= 0:
        return
    target = min(geo.TH_FULL, geo.th_for_lip(geo.lip_z(_th) + mm))
    move_to(target, duration_s=duration_s)


def at_full_lift() -> bool:
    return _th is not None and abs(_th - geo.TH_FULL) < 1e-9 and _settled and not _released


def yaw_permitted() -> tuple[bool, str]:
    """The yaw interlock (hardware/yaw.set_interlock)."""
    if not at_full_lift():
        return False, (f"lift not at full height (th {'unknown' if _th is None else format(_th, '.2f')}{'' if _settled else ', still moving'}) — yaw only moves "
                       "with the card 21 mm over every wall")
    if not touch.is_closed():
        return False, ("touch contact OPEN at full lift: the cup rests on something (overfull pile?), "
                       "the slider sticks or the contact wire is broken")
    return True, ""


def lower_until_touch(approach_th: float, limit_th: float, overtravel_mm: float = 0.0,
                      tick=None) -> TouchResult:
    """See the module docstring. Raises TouchFault if the contact is already open."""
    if _th is None:
        raise LiftError("lift pose unknown — lift to full first")
    if limit_th < geo.TH_MIN - 1e-9 or approach_th > geo.TH_FULL + 1e-9 or limit_th >= approach_th:
        raise LiftLimitError(f"bad descent window approach {approach_th} / limit {limit_th}")
    if not touch.is_closed():
        raise TouchFault("touch contact open BEFORE lowering (cup not hanging free): wire broken, "
                         "slider stuck, or the cup already rests on something")
    touched, th_touch, closed = False, None, _th
    if _th > approach_th:
        if move_to(approach_th, watch_touch=True):
            touched, th_touch, closed = True, _th, _last_closed
        else:
            closed = _th
    while not touched:
        if tick:
            tick()
        nxt = _th - DESCENT_STEP_DEG
        if nxt < limit_th - 1e-9:
            if _th > limit_th + 1e-9:
                nxt = limit_th
            else:
                break
        _write(nxt)
        time.sleep(DESCENT_STEP_S)
        if touch.is_open():
            touched, th_touch = True, _th
        else:
            closed = _th
    if touched:
        mm = min(max(float(overtravel_mm), 0.0), MAX_OVERTRAVEL_MM)
        target = max(geo.TH_MIN, geo.th_below(closed, mm))
        if target > _th:                    # the opening step already went deeper: back up
            _write(target)
            time.sleep(DESCENT_STEP_S)
        while _th - target > 1e-9:          # bounded; no contact checks: it is open
            _write(max(target, _th - DESCENT_STEP_DEG))
            time.sleep(DESCENT_STEP_S)
    return TouchResult(touched, th_touch, _th, closed)


def lower_watching(target: float) -> TouchResult:
    """Manual: step down to target in DESCENT_STEP_DEG steps with the contact
    read after every step; stop AT the first open reading (the cup then rests
    there, at most one step of slider compression). Pose must be known."""
    if _th is None:
        raise LiftError("lift pose unknown — lift to full first")
    if not geo.TH_MIN - 1e-9 <= target < _th:
        raise LiftLimitError("lower_watching only goes down, within the lift range")
    if not touch.is_closed():
        raise TouchFault("touch contact open before lowering — the cup already rests on something")
    closed = _th
    while _th - target > 1e-9:
        _write(max(target, _th - DESCENT_STEP_DEG))
        time.sleep(DESCENT_STEP_S)
        if touch.is_open():
            return TouchResult(True, _th, _th, closed)
        closed = _th
    return TouchResult(False, None, _th, closed)


def release() -> None:
    """Channel off: the arm goes limp (sags). th stays tracked as unknown-ish."""
    global _released, _settled
    if not _MOCK and _pca is not None:
        _pca.channels[CHANNEL].duty_cycle = 0
    _released, _settled = True, False


def deinit(release_servo: bool = False) -> None:
    """Forget the PCA9685. release_servo=True (only when parked, nothing under
    the cup): all channels off + sleep — the arm goes limp. Otherwise the chip
    is left running: it keeps sending the last pulse without the host, so the
    lift HOLDS its height instead of sagging onto a stack, the bed or a wall."""
    global _pca, _servo
    if _MOCK or _pca is None:
        _pca = _servo = None
        return
    pca, _pca, _servo = _pca, None, None
    if release_servo:
        from hardware.servos import release_pca
        release_pca(pca)
