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
  * the carriage only moves in HOLD (card tail up, cradle clear of everything).
    The tilt state is None ("unknown") from the first step of every tilt ramp
    until the ramp has finished, so an interrupted tip (exception, shutdown
    signal) can never be mistaken for HOLD: to_column() refuses to move
    unless the tilt is known to be HOLD.
  * level only at home; upper/lower never at home
  * route() can verify with the load cell that the cradle emptied before it
    moves again (a card hanging on the lip would be dragged sideways)
  * jam latch: a card that will not leave the cradle (or a failed emptiness
    check) latches _jammed; the carriage then refuses every move until
    clear_jam() is called (operator confirmed the cradle clear). init() clears it.

Shutdown (deinit) does NOT home: the shuttle stays where it is and every
PCA9685 channel it drives is switched fully OFF (no pulses = de-energized,
limp; scripts/safe_outputs.py also sleeps the PCA9685 when the service stops).
init() never moves anything by itself (audit M7):
  * clean stop (rest pose home + level, from main.py's machine state file):
    init(assume_rest=True) re-asserts that rest pose with ONE write per
    channel — the servos were limp, so they may have sagged a little and snap
    back by that much, never more — and every later move ramps from it.
  * unclean stop: init() commands nothing; the pose is unknown (state() is
    (None, None, ...)). main.py waits for the operator's "Machine clear" and
    only then calls home(), whose first command is necessarily a full-speed
    jump (hobby servos have no position feedback).

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

# Servo actuation range per channel (degrees covered by 500–2500 µs). MG996R: 180.
# ch2 needs ~176° of crank travel (reject 2° … column 0 178°), right at an
# MG996R's limit; a DS3218MG-270 is the drop-in fallback — set 270 here or in
# config/shuttle_calibration.json {"actuation_range": {"2": 270}}. All angles
# in this file are SERVO degrees within that range (Adafruit's Servo scales
# angle / actuation_range onto the pulse width), so after changing a servo's
# range its angles must be re-calibrated (scripts/calibrate_servos.py).
SHUTTLE_ACTUATION_RANGE = {CH_TILT: 180, CH_SHUTTLE: 180}

if not _MOCK:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
    from adafruit_motor import servo as adafruit_servo

# --- Nominal angles from cad/shuttle_geom.scad (calibrate on the machine) -----
# ch1: servo angle = 90° + crank angle φ (horn horizontal toward +X at 90°).
#   φ: level 3.6, hold 7.0, upper 22.2, lower -48.5  (shuttle_check.py geom)
#   level is set 0.5° past the geometric value (93.6) so the skids sit on the
#   home ledges (hard stop), which fixes the bed height for the incoming card.
#   Keep the preload small: past the hard stop the MG996R stalls against the
#   ledge for as long as the cradle waits level (heat, current, gear wear).
TILT_ANGLES = {
    "level": 93.1,
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
# "Empty cradle" threshold: hardware.loadcell.WEIGHT_EMPTY_MAX (one value for the
# whole machine; see loadcell.is_empty()).
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
_tilt_state = None                         # None = unknown (never set, or mid-ramp)
_target = None                             # 0..3, "reject", "home"
_jammed = None                             # None, or why the carriage is locked


class ShuttleError(RuntimeError):
    """Raised for an illegal move or a card that did not leave the cradle."""


def jammed():
    """None, or the reason the carriage is locked (see clear_jam())."""
    return _jammed


def set_jammed(reason: str) -> None:
    """Lock the carriage: no to_column() until clear_jam()."""
    global _jammed
    _jammed = reason or "jammed"


def clear_jam() -> None:
    """Operator has confirmed the cradle is clear: allow carriage moves again."""
    global _jammed
    _jammed = None


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
    for k, v in cal.get("actuation_range", {}).items():
        if str(k).isdigit() and int(k) in SHUTTLE_ACTUATION_RANGE:
            SHUTTLE_ACTUATION_RANGE[int(k)] = int(v)
    print(f"[shuttle] Loaded calibration from {_CALIBRATION_FILE}")


def _shared_pca():
    """Reuse the PCA9685 that hardware/servos.py opened, if any."""
    try:
        from hardware import servos
    except Exception:
        return None
    return getattr(servos, "_pca", None)


def init(pca=None, assume_rest: bool = False):
    """Attach ch1/ch2. Pass a PCA9685 object, or call after servos.init() to
    share its instance; otherwise this module opens its own on 0x40.
    Never homes (audit M7) — call home() explicitly once it is safe.

    assume_rest=True: the previous run stopped cleanly with the shuttle at
    home + level (main.py's machine state file), and deinit() left it there
    de-energized. The rest pose is written once (at most a small snap back by
    whatever the limp servos sagged) and every later move ramps from it.
    assume_rest=False: pose unknown; NOTHING is commanded (no pulses on ch1 /
    ch2). home() later goes tilt straight to HOLD, then carriage straight to
    HOME — two full-speed jumps, in that order so nothing drags."""
    global _pca, _own_pca, _tilt_state, _target, _jammed
    _load_calibration()
    _tilt_state, _target, _jammed = None, None, None
    _pos[CH_TILT] = _pos[CH_SHUTTLE] = None
    if _MOCK:
        print("[shuttle] MOCK mode — no hardware")
    else:
        _pca = pca or _shared_pca()
        _own_pca = False
        if _pca is None:
            i2c = busio.I2C(board.SCL, board.SDA)
            _pca = PCA9685(i2c, address=0x40)
            _pca.frequency = 50
            _own_pca = True
        for ch in (CH_TILT, CH_SHUTTLE):
            _servos[ch] = adafruit_servo.Servo(_pca.channels[ch],
                                               actuation_range=SHUTTLE_ACTUATION_RANGE[ch],
                                               min_pulse=500, max_pulse=2500)
        print("[shuttle] ch1 tilt + ch2 shuttle attached")
    if assume_rest:
        _write(CH_SHUTTLE, SHUTTLE_ANGLES["home"])
        _write(CH_TILT, TILT_ANGLES["level"])
        _sleep(0.3)
        _target, _tilt_state = "home", "level"


def pose_known() -> bool:
    """Both channels have been commanded since init() (positions tracked)."""
    return _pos[CH_TILT] is not None and _pos[CH_SHUTTLE] is not None


def at_rest() -> bool:
    """Carriage at home and the cradle level (the receive / rest pose)."""
    return (_target, _tilt_state) == ("home", "level")


# --- low-level ramped motion ---------------------------------------------------
def _write(ch, angle):
    angle = max(0.0, min(float(SHUTTLE_ACTUATION_RANGE[ch]), float(angle)))
    _pos[ch] = angle
    if not _MOCK:
        _servos[ch].angle = angle


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
    """Ramp the cradle to `state`. The tilt is UNKNOWN (None) from before the
    first step until the ramp has completed: an exception or shutdown signal
    mid-ramp leaves _tilt_state None, never the old (stale) pose."""
    global _tilt_state
    _tilt_state = None
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
    """Move the carriage to column 0..3, 'reject' or 'home'.
    Refuses (ShuttleError) unless the tilt is KNOWN to be HOLD — callers put
    it in hold first — and while the jam latch is set.
    Every move ends approaching from the same side (−ψ → +ψ) to take up gear/link
    backlash, so the slot alignment repeats to the servo's resolution."""
    global _target
    key = col if col in ("reject", "home") else int(col)
    if key not in SHUTTLE_ANGLES:
        raise ValueError(f"Unknown column {col!r}. Valid: 0-3, 'reject', 'home'")
    if _jammed:
        raise ShuttleError(f"carriage locked ({_jammed}) — clear the cradle and confirm (clear_jam())")
    if _tilt_state != "hold":
        raise ShuttleError(f"carriage moves only in HOLD (tilt is {_tilt_state or 'unknown'})")
    target = SHUTTLE_ANGLES[key]
    cur = _pos[CH_SHUTTLE]
    _target = None                       # in transit: position unknown until the move completes
    if cur is not None and target < cur and target - 3.0 >= 0.0:
        _ramp(CH_SHUTTLE, target - 3.0, TIMING["shuttle_s_per_deg"], TIMING["shuttle_min_s"])
    _ramp(CH_SHUTTLE, target, TIMING["shuttle_s_per_deg"], TIMING["shuttle_min_s"])
    _target = key


def home():
    """Hold, shuttle to the belt axis, then level to receive the next card."""
    global _tilt_state
    if _pos[CH_TILT] is None:                 # never commanded: tilt first so nothing drags
        _write(CH_TILT, TILT_ANGLES["hold"])
        _sleep(0.6)
        _tilt_state = "hold"
    else:
        hold()                                # ramps from the last commanded angle
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
    from hardware import loadcell
    _sleep(TIMING["weigh_settle_s"])
    return loadcell.is_empty(read_grams())


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
        while True:
            try:
                empty = _cradle_empty(read_grams)
            except Exception as exc:
                set_jammed(f"emptiness check failed at {col!r}: {exc}")
                raise
            if empty:
                break
            if tries >= NUDGE_TRIES:
                set_jammed(f"card stuck on the cradle at column {col!r}")
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


def make_safe() -> None:
    """After an interruption: if the tilt is unknown (mid-ramp) or tipped,
    ramp it back to HOLD. Never moves the carriage; never commands a channel
    whose position is unknown."""
    if _pos[CH_TILT] is not None and _tilt_state not in ("hold", "level"):
        hold()


def hold_if_known() -> None:
    """hold(), but only if the tilt position is tracked (no blind jump)."""
    if _pos[CH_TILT] is not None:
        hold()


def _pca_usable() -> bool:
    """False once the shared PCA9685 has been released by servos.deinit():
    after Adafruit's deinit() (MODE1 = 0, auto-increment off) a 4-byte
    channel write would land in the wrong registers."""
    if _pca is None:
        return False
    if _own_pca:
        return True
    return _shared_pca() is _pca


def release_channels() -> None:
    """Switch ch1 and ch2 fully OFF (no pulses): the servos go limp where they are."""
    if _MOCK or not _pca_usable():
        return
    for ch in (CH_TILT, CH_SHUTTLE):
        _pca.channels[ch].duty_cycle = 0          # < 0x10 → FULL_OFF bit


def deinit():
    """Leave the shuttle WHERE IT IS (no homing), de-energized: ch1/ch2 fully
    OFF. Releases the PCA9685 only if this module opened it (then every
    channel is switched off first, see servos.release_pca). Idempotent."""
    global _pca, _own_pca
    if _MOCK:
        return
    try:
        release_channels()
    finally:
        if _own_pca and _pca is not None:
            from hardware import servos
            servos.release_pca(_pca)
        _pca, _own_pca = None, False
        _servos.clear()
