"""
Cradle-shuttle sorter at the belt exit (cad/shuttle.scad, cad/shuttle_geom.scad).

Two MG996R servos on the shared PCA9685 (I2C 0x40, 50 Hz):
  ch1 (CH_TILT)    turns an 8 mm D-shaft along Y; a crank + link on the
                   carriage tips the tilt frame that carries the load cell and
                   the cradle. Poses:
                     level  - home only: bed 0.7 mm under the belt, card rides on
                     hold   - 10° nose-down about the front pin: card tail lifted
                              clear of rails/guides, card weighed here (at rest)
                     upper  - 35° about the front pin: card slides off the lip
                              into the UPPER slot (bins 4-7)
                     lower  - from hold the other way: the rear skids land on the
                              fixed R-bar and the cradle swings to 58°; card goes
                              down the fixed lower ramp into the LOWER slot
                              (bins 0-3) or, at the reject position, the reject bin
                   "lower" and "level" are the SAME ch1 direction: the R-bar has
                   notches only at home, so home gives level, every column lower.
  ch2 (CH_SHUTTLE) in-line slider-crank (139 mm crank, 162 mm link) moving the
                   carriage along Y on an 8 mm rod + the D-shaft:
                     home (Y 0, belt), columns 0..3 (Y -102, -35, 35, 102),
                     reject (Y 176, beside the tray).

Bins: 0-3 lower floor (column = bin), 4-7 upper floor (column = bin - 4),
9 reject. All angles live in TILT_ANGLES / SHUTTLE_ANGLES and can be overridden
from config/shuttle_calibration.json (same idea as servos.py).

Motion is ramped (cosine ease, ~50 Hz updates) so a card never gets jerked:
tilts take 0.4-0.6 s, shuttle moves ~0.5-1.2 s. Interlocks:
  * the carriage only moves in HOLD (card tail up, cradle clear of everything)
  * level only at home; upper/lower never at home
  * route() can verify with the load cell that the cradle emptied before it
    moves again (a card hanging on the lip would be dragged sideways)

Requires: adafruit-circuitpython-pca9685, adafruit-circuitpython-motor
"""

import json
import math
import os
import time
from pathlib import Path

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

_CALIBRATION_FILE = Path(__file__).parent.parent / "config" / "shuttle_calibration.json"

CH_TILT = 1
CH_SHUTTLE = 2

if not _MOCK:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
    from adafruit_motor import servo as adafruit_servo

# --- Nominal angles from cad/shuttle_geom.scad (calibrate on the machine) -----
# ch1: servo angle = 90° + crank angle φ (horn horizontal toward +X at 90°).
#   φ: level 3.6, hold 7.0, upper 22.2, lower -48.5  (shuttle_check.py geom)
#   level is set 1.5° past the geometric value so the skids sit firmly on the
#   home ledges (hard stop), which fixes the bed height for the incoming card.
TILT_ANGLES = {
    "level": 92.1,
    "hold":  97.0,
    "upper": 112.2,
    "lower": 41.5,
}
# ch2: servo angle = crank angle ψ (0° = crank pointing +Y = reject end).
SHUTTLE_ANGLES = {
    "reject": 2.0,      # geometric 0° (dead centre); stay 2° inside the servo stop
    3: 45.0,
    2: 65.2,
    "home": 75.5,
    1: 87.3,
    0: 178.0,           # geometric 180° (dead centre)
}
TIMING = {
    "tilt_s_per_deg": 0.012,    # ramp duration per degree of servo travel
    "tilt_min_s": 0.35,
    "shuttle_s_per_deg": 0.007,
    "shuttle_min_s": 0.4,
    "update_hz": 50,
    "settle_s": 0.15,           # after a move, before anything else
    "dump_dwell_s": 0.6,        # time the card needs to leave the cradle
    "weigh_settle_s": 0.3,      # cradle at rest before a weight reading
}
EMPTY_MAX_G = 0.4               # cradle reads below this (tared in HOLD) → empty
NUDGE_TRIES = 2

COLUMNS = (0, 1, 2, 3)
REJECT_BIN = 9

def _sleep(seconds):
    """Real delay on hardware; instant in MOCK mode (positions are still tracked)."""
    if not _MOCK:
        time.sleep(seconds)


_pca = None
_own_pca = False
_servos = {}
_pos = {CH_TILT: None, CH_SHUTTLE: None}   # last commanded angle per channel
_tilt_state = None
_target = None                             # 0..3, "reject", "home"


class ShuttleError(RuntimeError):
    """Raised for an illegal move or a card that did not leave the cradle."""


def _load_calibration() -> None:
    if not _CALIBRATION_FILE.exists():
        return
    try:
        cal = json.loads(_CALIBRATION_FILE.read_text())
    except Exception as exc:
        print(f"[shuttle] Warning: could not read calibration file: {exc}")
        return
    for k, v in cal.get("tilt", {}).items():
        if k in TILT_ANGLES:
            TILT_ANGLES[k] = float(v)
    for k, v in cal.get("shuttle", {}).items():
        key = int(k) if str(k).isdigit() else k
        if key in SHUTTLE_ANGLES:
            SHUTTLE_ANGLES[key] = float(v)
    for k, v in cal.get("timing", {}).items():
        if k in TIMING:
            TIMING[k] = float(v)
    print(f"[shuttle] Loaded calibration from {_CALIBRATION_FILE}")


def _shared_pca():
    """Reuse the PCA9685 that hardware/servos.py opened, if any."""
    try:
        from hardware import servos
    except Exception:
        return None
    return getattr(servos, "_pca", None)


def init(pca=None):
    """Attach ch1/ch2. Pass a PCA9685 object, or call after servos.init() to
    share its instance; otherwise this module opens its own on 0x40."""
    global _pca, _own_pca
    _load_calibration()
    if _MOCK:
        print("[shuttle] MOCK mode — no hardware")
    else:
        _pca = pca or _shared_pca()
        if _pca is None:
            i2c = busio.I2C(board.SCL, board.SDA)
            _pca = PCA9685(i2c, address=0x40)
            _pca.frequency = 50
            _own_pca = True
        for ch in (CH_TILT, CH_SHUTTLE):
            _servos[ch] = adafruit_servo.Servo(_pca.channels[ch], min_pulse=500, max_pulse=2500)
        print("[shuttle] ch1 tilt + ch2 shuttle attached")
    home()


# --- low-level ramped motion ---------------------------------------------------
def _write(ch, angle):
    _pos[ch] = angle
    if not _MOCK:
        _servos[ch].angle = max(0.0, min(180.0, angle))


def _ramp(ch, target, s_per_deg, min_s):
    """Cosine-eased move from the last commanded angle to `target`."""
    start = _pos[ch]
    if start is None:                         # unknown position: go there slowly in one step
        _write(ch, target)
        _sleep(1.0)
        return
    delta = target - start
    if abs(delta) < 0.05:
        return
    duration = max(min_s, abs(delta) * s_per_deg)
    steps = max(2, int(duration * TIMING["update_hz"]))
    for i in range(1, steps + 1):
        s = 0.5 - 0.5 * math.cos(math.pi * i / steps)
        _write(ch, start + delta * s)
        _sleep(duration / steps)
    _sleep(TIMING["settle_s"])


def _tilt(state):
    global _tilt_state
    _ramp(CH_TILT, TILT_ANGLES[state], TIMING["tilt_s_per_deg"], TIMING["tilt_min_s"])
    _tilt_state = state


# --- public API -----------------------------------------------------------------
def hold():
    """Cradle 10° nose-down: card tail clear, ready to move or weigh."""
    _tilt("hold")


def level():
    """Receive pose (home only): bed just under the belt, skids on the home ledges."""
    if _target != "home":
        raise ShuttleError(f"level() only at home (carriage at {_target!r}); at a column this pose is 'lower'")
    _tilt("level")


def tip_upper():
    """Slide the card into the UPPER slot of the current column."""
    if _target in (None, "home"):
        raise ShuttleError("tip_upper() needs the carriage at a column (0-3) or reject")
    if _tilt_state != "hold":
        hold()
    _tilt("upper")


def tip_lower():
    """Swing the cradle down onto the lower ramp (lower slot / reject bin)."""
    if _target in (None, "home"):
        raise ShuttleError("tip_lower() is not possible at home (R-bar notches); move to a column first")
    if _tilt_state != "hold":
        hold()
    _tilt("lower")


def to_column(col):
    """Move the carriage to column 0..3, 'reject' or 'home'. Always travels in HOLD.
    Every move ends approaching from the same side (−ψ → +ψ) to take up gear/link
    backlash, so the slot alignment repeats to the servo's resolution."""
    global _target
    key = col if col in ("reject", "home") else int(col)
    if key not in SHUTTLE_ANGLES:
        raise ValueError(f"Unknown column {col!r}. Valid: 0-3, 'reject', 'home'")
    if _tilt_state != "hold":
        hold()
    target = SHUTTLE_ANGLES[key]
    cur = _pos[CH_SHUTTLE]
    if cur is not None and target < cur and target - 3.0 >= 0.0:
        _ramp(CH_SHUTTLE, target - 3.0, TIMING["shuttle_s_per_deg"], TIMING["shuttle_min_s"])
    _ramp(CH_SHUTTLE, target, TIMING["shuttle_s_per_deg"], TIMING["shuttle_min_s"])
    _target = key


def home():
    """Hold, shuttle to the belt axis, then level to receive the next card."""
    global _tilt_state
    if _tilt_state is None:                   # first call: tilt first so nothing drags
        _write(CH_TILT, TILT_ANGLES["hold"])
        _sleep(0.6)
        _tilt_state = "hold"
    to_column("home")
    level()


def bin_to_target(bin_num: int):
    """bin → (column or 'reject', 'upper' | 'lower')."""
    if bin_num == REJECT_BIN:
        return "reject", "lower"
    if 0 <= bin_num <= 3:
        return bin_num, "lower"
    if 4 <= bin_num <= 7:
        return bin_num - 4, "upper"
    raise ValueError(f"Unknown bin {bin_num}. Valid: 0-7, {REJECT_BIN}")


def _cradle_empty(read_grams):
    _sleep(TIMING["weigh_settle_s"])
    return read_grams() < EMPTY_MAX_G


def route(bin_num: int, read_grams=None):
    """Full sort move for the card resting on the cradle:
       hold → shuttle to the column → tip (upper/lower) → dwell → hold →
       [verify empty with read_grams(), nudge + retry if not] → home → level.
    read_grams: optional callable returning the cradle load in grams, tared
    with an EMPTY cradle in HOLD (e.g. hardware.loadcell.read_grams). Without
    it the move is open-loop. Raises ShuttleError if the card will not leave."""
    col, floor = bin_to_target(bin_num)
    hold()
    to_column(col)
    tip = tip_upper if floor == "upper" else tip_lower
    tip()
    _sleep(TIMING["dump_dwell_s"])
    hold()
    if read_grams is not None:
        tries = 0
        while not _cradle_empty(read_grams):
            if tries >= NUDGE_TRIES:
                raise ShuttleError(f"card still on the cradle at {col!r} after {tries} nudges — "
                                   "not moving (it would be dragged); clear it by hand")
            tries += 1
            # nudge: tip again, with a short back-and-forth at the end of the stroke
            tip()
            end = _pos[CH_TILT]
            back = -6.0 if floor == "upper" else 6.0
            for _ in range(2):
                _ramp(CH_TILT, end + back, 0.01, 0.12)
                _ramp(CH_TILT, end, 0.01, 0.12)
            _sleep(TIMING["dump_dwell_s"])
            hold()
    to_column("home")
    level()


def state():
    """(target, tilt_state, {ch: angle})."""
    return _target, _tilt_state, dict(_pos)


def deinit():
    """Leave the cradle level at home; release our own PCA9685 if we opened it."""
    if _target is not None:
        try:
            home()
        except ShuttleError:
            pass
    if not _MOCK and _own_pca and _pca is not None:
        _pca.deinit()
