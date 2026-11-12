"""
Cradle-shuttle sorter at the belt exit (cad/shuttle.scad, cad/shuttle_geom.scad).

Two MG996R servos on the shared PCA9685 (I2C 0x40, 50 Hz):
  ch1 (CH_TILT)    turns an 8 mm REX tilt shaft (goBILDA 2106-4008-4320, cut to
                   417 mm) along Y through a goBILDA clamping coupler; a
                   crank + link on the carriage tips the tilt frame that carries the load cell and
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
                   carriage along Y on an 8 mm rod + the REX tilt shaft:
                     home (Y 0, belt), columns 0..3 (Y -102, -35, 35, 102),
                     reject (Y 176, beside the tray).

Bins: 0-3 lower floor (column = bin), 4-7 upper floor (column = bin - 4),
9 reject. All angles live in TILT_ANGLES / SHUTTLE_ANGLES and can be overridden
from config/shuttle_calibration.json (same idea as servos.py), which is
validated strictly (validate_calibration(): known keys, finite numbers inside
the servo range AND a ±8° sanity window around the nominal pose, pose order
and minimum / maximum gaps between poses; any problem → ShuttleConfigError,
nothing applied, main.py exits 78). They are always
GEOMETRIC angles (crank φ + 90° / crank ψ); a servo that turns the wrong way
is handled by the per-channel "invert" option (SHUTTLE_INVERT) at the PWM write.

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

# Per-channel direction invert, config/shuttle_calibration.json
#   {"invert": {"1": false, "2": false}}   (JSON booleans only; channels "1"/"2" only)
# An inverted channel gets (actuation_range − a) on the PWM write for every
# commanded angle a, so every angle in this file / the calibration file keeps
# its geometric meaning (φ + 90°, ψ) whichever way the servo turns. Everything
# above the write (_pos, state(), ramps, interlocks, backlash approach) works in
# those geometric angles. Expected direction for BOTH channels: increasing angle
# turns the spline CLOCKWISE looking straight at the spline face (ch2: = counter-
# clockwise seen from above, cad/shuttle.scad "ch2 DIRECTION"; ch1: φ grows from
# +X up toward +Z, shuttle_geom.scad sg_crank_tip). If a bare servo turns the
# other way, set its invert (scripts/calibrate_servos.py direction check) — never
# fit the crank / shaft to a servo that has not been checked.
_INVERT_DEFAULT = {CH_TILT: False, CH_SHUTTLE: False}
SHUTTLE_INVERT = dict(_INVERT_DEFAULT)

if not _MOCK:
    import board
    import busio
    from adafruit_pca9685 import PCA9685
    from adafruit_motor import servo as adafruit_servo

# --- Nominal angles from cad/shuttle_geom.scad (calibrate on the machine) -----
# ch1: servo angle = 90° + crank angle φ, φ = tilt-crank arm direction in the XZ
#   plane (0 = horizontal toward +X, positive = up toward +Z; shuttle_geom.scad).
#   There is NO horn on ch1: the MG996R spline drives the 8 mm REX shaft through
#   a goBILDA 4001-0025-4008 clamping coupler (25T spline → REX bore), and the
#   tilt crank is keyed on the shaft by its REX bore (two hex flats parallel to
#   the crank arm). The angle ↔ φ relation is therefore set at ASSEMBLY, at HOLD:
#   with ch1 powered to HOLD (97°) the coupler is pressed onto the spline at the
#   tooth that puts two flats of its hex bore 7° up from horizontal toward +X
#   (φ_hold = 7°), and its M4 clamp is tightened with the cradle 10° nose-down
#   (cad/shuttle.scad header + INSTALL ORDER steps 1-2). 25T × hex indexing
#   leaves ≤ 0.6° residual: trim it with scripts/calibrate_servos.py.
#   φ: level 3.6, hold 7.0, upper 22.2, lower -48.5  (shuttle_check.py geom)
#   level is set 0.5° past the geometric value (93.6) so the skids sit on the
#   home ledges (hard stop), which fixes the bed height for the incoming card.
#   Keep the preload at ~0.5°: past the hard stop the MG996R stalls against the
#   ledge for as long as the cradle waits level (heat, current, gear wear), so
#   main.py also switches ch1/ch2 off while the machine idles at rest.
TILT_ANGLES = {
    "level": 93.1,
    "hold":  97.0,
    "upper": 112.2,
    "lower": 41.5,
}
# ch2: servo angle = crank angle ψ (0° = crank pointing +Y = reject end, 90° = −X,
#   180° = −Y = column 0; direction: see SHUTTLE_INVERT and cad/shuttle.scad).
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
_released = set()                          # channels switched off since their last write (limp)


class ShuttleError(RuntimeError):
    """Raised for an illegal move or a card that did not leave the cradle."""


class ShuttleConfigError(ShuttleError):
    """config/shuttle_calibration.json is unusable; init() refuses to attach.
    .problems lists every bad key (empty for an unreadable file)."""

    def __init__(self, message, problems=()):
        super().__init__(message)
        self.problems = list(problems)


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


# --- calibration file (config/shuttle_calibration.json) -------------------------
# Validated as strictly as config/machine.json (audit 3 M1): every problem is
# collected and reported at once, and NOTHING is applied unless the whole file
# is good (ShuttleConfigError → main.py exits 78, systemd does not restart).
#   sections        tilt, shuttle, timing, actuation_range, invert (keys "_…" = comments)
#   actuation_range {"1"|"2": 180 | 270}
#   tilt / shuttle  finite JSON numbers in [0, actuation_range] AND inside the
#                   sanity window: within SANITY_WINDOW_DEG (±8°) of the nominal
#                   pose below — the calibrate tool's jog window is clamped to
#                   the same limits (allowed_range()). Why ±8° (audit 4 MJ1):
#                     ch1: the coupler is indexed at HOLD on the 25T spline, so
#                          the residual is ≤ 0.6° (25T × hex indexing, see the
#                          TILT_ANGLES note) — every tilt pose shares that offset;
#                     ch2: the crank horn is fitted at a commanded pose; a 25T
#                          spline tooth is 14.4°, so the nearest tooth is always
#                          within ±7.2° of nominal.
#                   ±8° covers both with margin, and is tight enough that a
#                   swapped-digit typo of any nominal (79 / 107 for hold 97,
#                   103 for level 93.1, 98 for upper 112.2, 78.3 for column 1
#                   87.3, …) or a sign slip lands outside. Angles are geometric
#                   (see "invert"), so the window holds for a 270° servo too.
#                   Order + gaps (geometry; TILT_GAPS / SHUTTLE_MIN_GAP_DEG):
#                     tilt  lower < level < hold < upper with
#                           2° ≤ hold − level ≤ 8°   (nominal 3.9°: hold must lift
#                                                    the tail, level must not be
#                                                    a second hold)
#                           upper − hold ≥ 8°        (nominal 15.2°)
#                           level − lower ≥ 30°      (nominal 51.6°)
#                     carriage reject < 3 < 2 < home < 1 < 0, neighbours ≥ 5°
#                           apart (nominal gaps 43 / 20.2 / 10.3 / 11.8 / 90.7°)
#                   A window alone cannot catch two poses typed into each
#                   other's place (hold 93.2 with level 93.1): the gaps do.
#   timing          finite numbers inside TIMING_LIMITS (all ≥ 0)
#   invert          JSON booleans, channels "1" / "2"
SANITY_WINDOW_DEG = 8.0
# (lower pose, upper pose, min gap °, max gap ° or None): TILT[b] − TILT[a] in [min, max]
TILT_GAPS = (
    ("lower", "level", 30.0, None),
    ("level", "hold", 2.0, 8.0),
    ("hold", "upper", 8.0, None),
)
SHUTTLE_MIN_GAP_DEG = 5.0
VALID_ACTUATION_RANGES = (180, 270)
TIMING_LIMITS = {
    "tilt_s_per_deg": (0.0, 0.2),
    "tilt_min_s": (0.0, 10.0),
    "shuttle_s_per_deg": (0.0, 0.2),
    "shuttle_min_s": (0.0, 10.0),
    "update_hz": (1.0, 200.0),
    "settle_s": (0.0, 10.0),
    "dump_dwell_s": (0.0, 10.0),
    "weigh_settle_s": (0.0, 10.0),
}
CAL_SECTIONS = ("tilt", "shuttle", "timing", "actuation_range", "invert")
# Module defaults = the nominal poses the sanity window is centred on.
NOMINAL_TILT_ANGLES = dict(TILT_ANGLES)
NOMINAL_SHUTTLE_ANGLES = dict(SHUTTLE_ANGLES)
NOMINAL_TIMING = dict(TIMING)
NOMINAL_ACTUATION_RANGE = dict(SHUTTLE_ACTUATION_RANGE)
_TILT_ORDER = ("lower", "level", "hold", "upper")      # increasing servo angle
_SHUTTLE_ORDER = ("reject", 3, 2, "home", 1, 0)          # increasing crank angle ψ


def _shuttle_key(k):
    """JSON key of the "shuttle" section → SHUTTLE_ANGLES key (None if unknown)."""
    if k in ("home", "reject"):
        return k
    if k in ("0", "1", "2", "3"):
        return int(k)
    return None


def sanity_window(section: str, key, actuation_range: int | None = None) -> tuple[float, float]:
    """(lo, hi) allowed for tilt.<key> / shuttle.<key>: nominal ± SANITY_WINDOW_DEG,
    clipped to [0, actuation_range]."""
    nominal = (NOMINAL_TILT_ANGLES if section == "tilt" else NOMINAL_SHUTTLE_ANGLES)[key]
    ch = CH_TILT if section == "tilt" else CH_SHUTTLE
    rng = actuation_range if actuation_range is not None else SHUTTLE_ACTUATION_RANGE[ch]
    return max(0.0, nominal - SANITY_WINDOW_DEG), min(float(rng), nominal + SANITY_WINDOW_DEG)


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_calibration(cal) -> tuple[dict, list[str]]:
    """Check a parsed shuttle_calibration.json. Returns (effective, problems):
    effective = {"tilt", "shuttle", "timing", "actuation_range", "invert"}, each
    the nominal defaults overridden by the file (only meaningful if problems is
    empty). Pure: changes nothing."""
    problems: list[str] = []
    eff = {"tilt": dict(NOMINAL_TILT_ANGLES), "shuttle": dict(NOMINAL_SHUTTLE_ANGLES),
           "timing": dict(NOMINAL_TIMING), "actuation_range": dict(NOMINAL_ACTUATION_RANGE),
           "invert": dict(_INVERT_DEFAULT)}
    if not isinstance(cal, dict):
        return eff, [f"must be a JSON object, got {type(cal).__name__}"]
    for sec in cal:
        if not str(sec).startswith("_") and sec not in CAL_SECTIONS:
            problems.append(f"{sec}: unknown section (valid: {', '.join(CAL_SECTIONS)})")

    def body(name):
        b = cal.get(name, {})
        if name == "invert" and not isinstance(b, dict):
            problems.append(f'"invert" must be an object like {{"1": false, "2": false}}, got {b!r}')
            return {}
        if not isinstance(b, dict):
            problems.append(f"{name}: must be a JSON object of KEY: value, got {json.dumps(b)}")
            return {}
        return {k: v for k, v in b.items() if not str(k).startswith("_")}

    # actuation_range first: the angle limits depend on it
    for k, v in body("actuation_range").items():
        if k not in ("1", "2"):
            problems.append(f"actuation_range.{k}: unknown channel (only \"1\" tilt and \"2\" shuttle)")
        elif not (_is_number(v) and math.isfinite(v) and float(v).is_integer()
                  and int(v) in VALID_ACTUATION_RANGES):
            problems.append(f"actuation_range.{k}: must be 180 (MG996R) or 270 (DS3218MG-270), "
                            f"got {json.dumps(v)}")
        else:
            eff["actuation_range"][int(k)] = int(v)

    for k, v in body("invert").items():
        if k not in ("1", "2"):
            problems.append(f"invert.{k}: unknown channel (only \"1\" tilt and \"2\" shuttle)")
        elif not isinstance(v, bool):
            problems.append(f"invert.{k}: must be true or false (a JSON boolean), got {v!r}")
        else:
            eff["invert"][int(k)] = v

    bad_angle = set()
    for sec, ch in (("tilt", CH_TILT), ("shuttle", CH_SHUTTLE)):
        rng = eff["actuation_range"][ch]
        for k, v in body(sec).items():
            key = k if sec == "tilt" and k in NOMINAL_TILT_ANGLES else (
                _shuttle_key(k) if sec == "shuttle" else None)
            where = f"{sec}.{k}"
            if key is None:
                valid = (NOMINAL_TILT_ANGLES if sec == "tilt" else ("home", "reject", "0", "1", "2", "3"))
                problems.append(f"{where}: unknown key (valid: {', '.join(map(str, valid))})")
                continue
            bad_angle.add((sec, key))
            if not _is_number(v):
                problems.append(f"{where}: must be a number (degrees), got {json.dumps(v)}")
                continue
            if not math.isfinite(v):
                problems.append(f"{where}: must be a finite number, got {v}")
                continue
            v = float(v)
            if not 0.0 <= v <= rng:
                problems.append(f"{where}: {v:g}° is outside the servo range [0, {rng}] (ch{ch})")
                continue
            lo, hi = sanity_window(sec, key, rng)
            nominal = (NOMINAL_TILT_ANGLES if sec == "tilt" else NOMINAL_SHUTTLE_ANGLES)[key]
            if not lo <= v <= hi:
                problems.append(f"{where}: {v:g}° is more than {SANITY_WINDOW_DEG:g}° from the nominal "
                                f"{nominal:g}° (allowed {lo:g}–{hi:g}°) — a typo? Re-calibrate with "
                                "scripts/calibrate_servos.py (re-seat the horn / coupler if the "
                                "pose really is that far off)")
                continue
            bad_angle.discard((sec, key))
            eff[sec][key] = v

    for k, v in body("timing").items():
        where = f"timing.{k}"
        if k not in TIMING_LIMITS:
            problems.append(f"{where}: unknown key (valid: {', '.join(TIMING_LIMITS)})")
            continue
        lo, hi = TIMING_LIMITS[k]
        if not _is_number(v) or not math.isfinite(v):
            problems.append(f"{where}: must be a finite number, got {json.dumps(v)}")
        elif not lo <= v <= hi:
            problems.append(f"{where}: {v:g} is outside [{lo:g}, {hi:g}]")
        else:
            eff["timing"][k] = float(v)

    # Geometric order + gaps (only between values that passed their own checks)
    t = eff["tilt"]
    for a, b, gmin, gmax in TILT_GAPS:
        if ("tilt", a) in bad_angle or ("tilt", b) in bad_angle:
            continue
        gap = t[b] - t[a]
        if gap <= 0:
            problems.append(f"tilt.{a} ({t[a]:g}°) must be below tilt.{b} ({t[b]:g}°) — "
                            "the order is lower < level < hold < upper")
        elif gap < gmin or (gmax is not None and gap > gmax):
            want = f"{gmin:g}–{gmax:g}°" if gmax is not None else f"at least {gmin:g}°"
            problems.append(f"tilt.{b} − tilt.{a} = {gap:g}° must be {want} (nominal "
                            f"{NOMINAL_TILT_ANGLES[b] - NOMINAL_TILT_ANGLES[a]:.1f}°) — two poses "
                            "swapped or mistyped?")
    c = eff["shuttle"]
    for a, b in zip(_SHUTTLE_ORDER, _SHUTTLE_ORDER[1:]):
        if ("shuttle", a) in bad_angle or ("shuttle", b) in bad_angle:
            continue
        if not c[a] < c[b]:
            problems.append(f"shuttle.{a} ({c[a]:g}°) must be below shuttle.{b} ({c[b]:g}°) — the "
                            "carriage order is reject < 3 < 2 < home < 1 < 0 (crank angle ψ)")
        elif c[b] - c[a] < SHUTTLE_MIN_GAP_DEG:
            problems.append(f"shuttle.{b} − shuttle.{a} = {c[b] - c[a]:g}° must be at least "
                            f"{SHUTTLE_MIN_GAP_DEG:g}° (neighbouring stops; nominal "
                            f"{NOMINAL_SHUTTLE_ANGLES[b] - NOMINAL_SHUTTLE_ANGLES[a]:.1f}°)")
    return eff, problems


def allowed_range(section: str, key, current: dict | None = None,
                  actuation_range: int | None = None) -> tuple[float, float]:
    """(lo, hi) a single pose may take with every OTHER pose of its section at
    `current` (default: the live TILT_ANGLES / SHUTTLE_ANGLES): the sanity
    window intersected with the order / gap rules of validate_calibration().
    scripts/calibrate_servos.py clamps its jog window to this, so a jog can
    never reach a value the save (and the sorter) would refuse. If the other
    poses leave no room, lo > hi (the caller pins the jog to the stored value)."""
    lo, hi = sanity_window(section, key, actuation_range)
    if section == "tilt":
        cur = TILT_ANGLES if current is None else current
        for a, b, gmin, gmax in TILT_GAPS:
            if b == key:          # key above a
                lo = max(lo, cur[a] + gmin)
                if gmax is not None:
                    hi = min(hi, cur[a] + gmax)
            elif a == key:        # key below b
                hi = min(hi, cur[b] - gmin)
                if gmax is not None:
                    lo = max(lo, cur[b] - gmax)
    else:
        cur = SHUTTLE_ANGLES if current is None else current
        i = _SHUTTLE_ORDER.index(key)
        if i > 0:
            lo = max(lo, cur[_SHUTTLE_ORDER[i - 1]] + SHUTTLE_MIN_GAP_DEG)
        if i < len(_SHUTTLE_ORDER) - 1:
            hi = min(hi, cur[_SHUTTLE_ORDER[i + 1]] - SHUTTLE_MIN_GAP_DEG)
    return lo, hi


def _reject_constant(token):
    raise ValueError(f"{token} is not a valid JSON number")


def read_calibration_file(path=None) -> dict | None:
    """Parsed calibration file (None if absent). NaN / Infinity are rejected
    like config/machine.json. Raises ShuttleConfigError if unreadable."""
    path = Path(path) if path is not None else _CALIBRATION_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(), parse_constant=_reject_constant)
    except Exception as exc:
        raise ShuttleConfigError(f"could not read {path} ({exc}) — fix or move it, then restart") from exc


def _load_calibration() -> None:
    """Apply config/shuttle_calibration.json. The WHOLE file is validated
    first (validate_calibration): any problem raises ShuttleConfigError
    listing every bad key, and nothing changes (no silent fall-back to
    defaults — a dropped invert or a typo would drive a crank the wrong way
    or to a wild pose). Keys absent from the file get their nominal value."""
    cal = read_calibration_file()
    eff, problems = validate_calibration({} if cal is None else cal)
    if problems:
        if not isinstance(cal, dict):
            raise ShuttleConfigError(f"{_CALIBRATION_FILE} must be a JSON object — refusing to start",
                                     problems)
        lines = "\n".join(f"  - {p}" for p in problems)
        raise ShuttleConfigError(f"invalid {_CALIBRATION_FILE} — refusing to start:\n{lines}\n"
                                 "Fix these keys (or delete them to use the nominal values) and "
                                 "re-check with scripts/calibrate_servos.py --verify", problems)
    TILT_ANGLES.clear()
    TILT_ANGLES.update(eff["tilt"])
    SHUTTLE_ANGLES.clear()
    SHUTTLE_ANGLES.update(eff["shuttle"])
    TIMING.clear()
    TIMING.update(eff["timing"])
    SHUTTLE_ACTUATION_RANGE.update(eff["actuation_range"])
    SHUTTLE_INVERT.update(eff["invert"])
    if cal is None:
        return
    inverted = [f"ch{ch}" for ch, on in sorted(SHUTTLE_INVERT.items()) if on]
    print(f"[shuttle] Loaded calibration from {_CALIBRATION_FILE}"
          + (f" (inverted: {', '.join(inverted)})" if inverted else ""))


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
    Raises ShuttleConfigError (before touching anything) if
    config/shuttle_calibration.json is unreadable or fails validation
    (validate_calibration: types, ranges, sanity window, order, invert).

    assume_rest=True: the previous run stopped cleanly with the shuttle at
    home + level (main.py's machine state file), and deinit() left it there
    de-energized. The rest pose is written once (at most a small snap back by
    whatever the limp servos sagged) and every later move ramps from it.
    assume_rest=False: pose unknown; NOTHING is commanded (no pulses on ch1 /
    ch2). home() later goes tilt straight to HOLD, then carriage straight to
    HOME — two full-speed jumps, in that order so nothing drags."""
    global _pca, _own_pca, _tilt_state, _target, _jammed, _released
    _load_calibration()
    _tilt_state, _target, _jammed, _released = None, None, None, set()
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
        _target, _tilt_state = "home", "level"
        assert_rest()


def assert_rest() -> None:
    """Re-assert the rest pose (home + level) with ONE write per channel —
    after a clean stop (init(assume_rest=True)) or after release_channels()
    while idle at rest: the limp servos may have sagged a little and snap
    back by that much, never more. Only when the pose is known to be at rest."""
    if not at_rest():
        raise ShuttleError(f"rest pose not known ({_target!r}, {_tilt_state!r}) — not re-asserting")
    _write(CH_SHUTTLE, SHUTTLE_ANGLES["home"])
    _write(CH_TILT, TILT_ANGLES["level"])
    _sleep(0.3)


def released(ch=None) -> bool:
    """Channel `ch` (default: either of ch1 / ch2) switched off (limp) since its
    last command."""
    return bool(_released) if ch is None else ch in _released


def pose_known() -> bool:
    """Both channels have been commanded since init() (positions tracked)."""
    return _pos[CH_TILT] is not None and _pos[CH_SHUTTLE] is not None


def at_rest() -> bool:
    """Carriage at home and the cradle level (the receive / rest pose)."""
    return (_target, _tilt_state) == ("home", "level")


# --- low-level ramped motion ---------------------------------------------------
def _clamp(ch, angle) -> float:
    return max(0.0, min(float(SHUTTLE_ACTUATION_RANGE[ch]), float(angle)))


def pwm_angle(ch, angle) -> float:
    """Angle actually written to the servo for the geometric angle `angle`
    (clamped to 0..actuation_range): actuation_range − angle on an inverted channel."""
    a = _clamp(ch, angle)
    return float(SHUTTLE_ACTUATION_RANGE[ch]) - a if SHUTTLE_INVERT[ch] else a


def pulse_us(ch, angle) -> float:
    """Pulse width (µs, 500–2500) the servo gets for the geometric angle `angle`."""
    return 500.0 + 2000.0 * pwm_angle(ch, angle) / float(SHUTTLE_ACTUATION_RANGE[ch])


def _write(ch, angle):
    """Command the geometric `angle`; _pos keeps it, the PWM gets pwm_angle()."""
    angle = _clamp(ch, angle)
    _pos[ch] = angle
    _released.discard(ch)
    if not _MOCK:
        _servos[ch].angle = pwm_angle(ch, angle)


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


def release_channels(channels=(CH_TILT, CH_SHUTTLE)) -> None:
    """Switch `channels` (default ch1 and ch2) fully OFF (no pulses): those
    servos go limp where they are. The commanded pose stays tracked
    (assert_rest() re-asserts a rest pose)."""
    _released.update(channels)
    if _MOCK or not _pca_usable():
        return
    for ch in channels:
        _pca.channels[ch].duty_cycle = 0          # < 0x10 → FULL_OFF bit


def release_tilt() -> None:
    """Idle at rest (main._release_idle, audit 4 m3): switch ONLY ch1 off. At
    LEVEL the skids sit on the home ledges with ~0.5° of preload, i.e. ch1
    stalls against them for as long as it is powered; limp, the cradle simply
    rests on the ledges. ch2 keeps holding the carriage at home."""
    release_channels((CH_TILT,))


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
