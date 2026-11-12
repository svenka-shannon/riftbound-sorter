"""
Load cell weight reading via HX711 (GPIO 5 = DOUT, GPIO 6 = SCK).

The load cell sits on the shuttle's tilt frame under the cradle
(cad/shuttle.scad). The card is weighed AT REST on the cradle in the
shuttle's HOLD pose, after it has left the belt:
  - empty  (<= WEIGHT_EMPTY_MAX)   card lost between the belt end and the cradle
  - single (~1.75 g)               one raw Riftbound card
  - double (>= WEIGHT_DOUBLE_MIN)  two cards stuck together (picked as one)
  - unknown                        anything else (partial / bent / leaning on the lip)
WEIGHT_EMPTY_MAX is THE empty threshold for the whole machine: classify(),
is_empty(), shuttle.route()'s "did the card leave" check and main.py's
"cradle empty before tare" check all use it.

Tare with the EMPTY cradle in HOLD (main.py tares at the end of every cycle,
right after shuttle.route() has proved the cradle empty), so the weigh pose
and the tare pose are the same.

Empty-cradle reference (audit M1): every verified-empty tare (and the
calibration) stores the absolute raw HX711 offset of the EMPTY cradle in
config/loadcell_calibration.json ("empty_offset"). At start-up main.py
compares the raw reading against it BEFORE taring, so a card left on the
cradle by a stop / crash is detected instead of being tared away.

Library: gandalf15/HX711, vendored as hardware/vendor/hx711.py (the PyPI
package called "hx711" is a different library with another API). Calls used,
exactly as that file defines them:
  HX711(dout_pin=, pd_sck_pin=)        gain 128, channel A (defaults)
  get_raw_data_mean(1) -> int | 0/False one raw 24-bit reading (0 = failed read)
  zero(readings) -> bool               True on ERROR; readings 1..99
  get_current_offset() -> int          offset set by zero()/set_offset()
  set_offset(int)                      int only (TypeError otherwise)
The library never calls GPIO.setmode(); init() sets BCM first.

Robustness (audit M2): one weight = median of READ_SAMPLES raw readings; a
failed raw read is simply re-read, and LoadCellError is raised only after
MAX_READ_FAILURES failures in one measurement (main.py then stops the machine).

Calibrate with `python main.py --calibrate`; the scale factor and the empty
offset are saved to config/loadcell_calibration.json and loaded by init().
"""

import json
import os
import statistics
import time
from pathlib import Path

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

DOUT_PIN = 5
SCK_PIN  = 6

_CALIBRATION_FILE = Path(__file__).parent.parent / "config" / "loadcell_calibration.json"
if _MOCK:
    # MOCK runs (dev machine, or test_hardware.py's default mode ON the Pi) must
    # never overwrite the real scale factor / empty-cradle reference.
    _CALIBRATION_FILE = _CALIBRATION_FILE.with_name("loadcell_calibration.mock.json")

# Calibration — `python main.py --calibrate` writes SCALE_FACTOR to the file above
SCALE_FACTOR = 420.0     # raw ADC counts per gram (default until calibrated)

# Thresholds (grams, relative to the empty-cradle tare)
WEIGHT_EMPTY_MAX    = 0.5   # at or below this = no card (single machine-wide threshold)
WEIGHT_SINGLE_MIN   = 1.3
WEIGHT_SINGLE_MAX   = 2.3
WEIGHT_DOUBLE_MIN   = 2.8   # above this = double pick
# Start-up check against the stored empty offset (no tare yet, so allow for
# zero drift since the last run). Any card (>= WEIGHT_SINGLE_MIN) still trips it.
STARTUP_EMPTY_MAX_G = 0.8

# Reading
READ_SAMPLES        = 7     # median of this many raw readings per weight
MAX_READ_FAILURES   = 6     # failed raw reads tolerated in one measurement
TARE_READINGS       = 10    # zero(10): ~1 s at the HX711's 10 SPS
TARE_ATTEMPTS       = 3
CALIBRATE_SAMPLES   = 15
OFFSET_PERSIST_DELTA_G = 0.05   # rewrite the stored empty offset only if it moved this much

MOCK_CARD_G = 1.75          # simulated single card

_hx = None
_empty_offset = None        # absolute raw counts of the EMPTY cradle (persisted)
_offset = 0                 # MOCK: current tare offset in raw counts


class LoadCellError(RuntimeError):
    """The HX711 returned no data (wiring, power, or timing problem)."""


# ── MOCK world ───────────────────────────────────────────────────────────────
# The simulated cradle holds _mock_load_g grams; raw counts = grams × SCALE_FACTOR.
# The simulated card leaves the cradle when it is tipped, i.e. whenever the
# shuttle carriage is away from home at the time of a reading
# (shuttle.route() only reads after a tip).
_mock_load_g = 0.0
_mock_fail_reads = 0        # MOCK: the next N raw reads fail (tests)


def mock_set_load(grams: float) -> None:
    """MOCK only: put `grams` on the simulated cradle (0 = empty)."""
    global _mock_load_g
    _mock_load_g = float(grams)


def mock_fail_next_reads(n: int) -> None:
    """MOCK only: make the next `n` raw readings fail (HX711 returned no data)."""
    global _mock_fail_reads
    _mock_fail_reads = int(n)


def _mock_raw():
    global _mock_load_g, _mock_fail_reads
    if _mock_fail_reads > 0:
        _mock_fail_reads -= 1
        return None
    try:
        from hardware import shuttle
        target, _tilt, _ = shuttle.state()
        if target not in (None, "home"):
            _mock_load_g = 0.0          # card was tipped off at a column
    except Exception:
        pass
    return _mock_load_g * SCALE_FACTOR


# ── Calibration file ─────────────────────────────────────────────────────────
def _read_file() -> dict:
    if not _CALIBRATION_FILE.exists():
        return {}
    try:
        return json.loads(_CALIBRATION_FILE.read_text())
    except Exception as exc:
        print(f"[loadcell] Warning: could not read {_CALIBRATION_FILE}: {exc}")
        return {}


def _write_file(data: dict) -> None:
    _CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CALIBRATION_FILE.with_name(f".{_CALIBRATION_FILE.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, _CALIBRATION_FILE)


def _load_calibration() -> None:
    global SCALE_FACTOR, _empty_offset
    cal = _read_file()
    if "scale_factor" in cal:
        try:
            SCALE_FACTOR = float(cal["scale_factor"])
            print(f"[loadcell] Loaded SCALE_FACTOR={SCALE_FACTOR:.2f} from {_CALIBRATION_FILE}")
        except (TypeError, ValueError) as exc:
            print(f"[loadcell] Warning: bad scale_factor in {_CALIBRATION_FILE}: {exc}")
    eo = cal.get("empty_offset")
    _empty_offset = int(eo) if isinstance(eo, (int, float)) else None


def save_calibration(factor: float) -> None:
    """Persist the scale factor (and the current empty offset) for the next init()."""
    global SCALE_FACTOR
    SCALE_FACTOR = float(factor)
    data = _read_file()
    data["scale_factor"] = SCALE_FACTOR
    if _empty_offset is not None:
        data["empty_offset"] = int(_empty_offset)
    _write_file(data)
    print(f"[loadcell] Saved SCALE_FACTOR={SCALE_FACTOR:.2f} to {_CALIBRATION_FILE}")


def _persist_empty_offset(offset: int, force: bool = False) -> None:
    """Store the absolute raw offset of the verified-EMPTY cradle."""
    global _empty_offset
    offset = int(offset)
    if (not force and _empty_offset is not None
            and abs(offset - _empty_offset) < OFFSET_PERSIST_DELTA_G * SCALE_FACTOR):
        return                                   # unchanged: spare the SD card
    _empty_offset = offset
    data = _read_file()
    data["empty_offset"] = offset
    data.setdefault("scale_factor", SCALE_FACTOR)
    data["empty_offset_saved"] = time.time()
    try:
        _write_file(data)
    except OSError as exc:
        print(f"[loadcell] Warning: could not save the empty offset: {exc}")


def empty_offset():
    """Stored absolute raw offset of the empty cradle (None if never saved)."""
    return _empty_offset


# ── Hardware ─────────────────────────────────────────────────────────────────
def init():
    """Open the HX711. Does NOT tare: whatever is on the cradle stays visible
    until main.py has checked it against the stored empty offset."""
    global _hx, _offset
    _load_calibration()
    if _MOCK:
        _offset = _empty_offset if _empty_offset is not None else 0
        print("[loadcell] MOCK mode — simulated cradle (mock_set_load())")
        return
    import RPi.GPIO as GPIO
    from hardware.vendor.hx711 import HX711
    GPIO.setmode(GPIO.BCM)                       # gandalf15 HX711 never sets the mode
    _hx = HX711(dout_pin=DOUT_PIN, pd_sck_pin=SCK_PIN)
    if _empty_offset is not None:
        _hx.set_offset(int(_empty_offset))
    print(f"[loadcell] HX711 initialized (DOUT={DOUT_PIN}, SCK={SCK_PIN})")


def _read_raw_once():
    """One raw reading, or None if the HX711 returned no data."""
    if _MOCK:
        return _mock_raw()
    v = _hx.get_raw_data_mean(1)
    # gandalf15: a failed read comes back as int(mean([False])) == 0 (or False)
    if v is None or v is False or v == 0:
        return None
    return v


def read_raw(samples: int = READ_SAMPLES) -> float:
    """Median of `samples` raw readings. Failed reads are re-read; raises
    LoadCellError after MAX_READ_FAILURES failures."""
    vals = []
    failures = 0
    while len(vals) < samples:
        v = _read_raw_once()
        if v is None:
            failures += 1
            if failures > MAX_READ_FAILURES:
                raise LoadCellError(f"HX711 read failed {failures}× ({len(vals)}/{samples} good readings)")
            continue
        vals.append(float(v))
    if failures:
        print(f"[loadcell] {failures} failed read(s) re-read")
    return statistics.median(vals)


def _current_offset() -> float:
    if _MOCK:
        return _offset
    return _hx.get_current_offset()


def read_grams(samples: int = READ_SAMPLES) -> float:
    """Weight in grams relative to the last tare (median of `samples` readings).
    Raises LoadCellError only after repeated failed reads (see read_raw)."""
    return (read_raw(samples) - _current_offset()) / SCALE_FACTOR


def grams_vs_empty_reference(samples: int = READ_SAMPLES):
    """Load on the cradle relative to the STORED empty offset (no tare), or
    None if no empty offset has ever been stored. Start-up card check (M1)."""
    if _empty_offset is None:
        return None
    return (read_raw(samples) - _empty_offset) / SCALE_FACTOR


def classify(weight_g: float) -> str:
    """
    Returns: 'empty', 'single', 'double', or 'unknown'
    """
    if weight_g <= WEIGHT_EMPTY_MAX:
        return "empty"
    elif WEIGHT_SINGLE_MIN <= weight_g <= WEIGHT_SINGLE_MAX:
        return "single"
    elif weight_g >= WEIGHT_DOUBLE_MIN:
        return "double"
    else:
        return "unknown"


def is_empty(weight_g: float) -> bool:
    """The machine-wide 'cradle is empty' test (same threshold as classify)."""
    return weight_g <= WEIGHT_EMPTY_MAX


def tare(verified_empty: bool = True):
    """Zero the scale. Call ONLY with the cradle empty and in HOLD.
    verified_empty=True (the default — every caller in main.py has proved the
    cradle empty first) also stores the offset as the empty-cradle reference."""
    global _offset
    if _MOCK:
        raw = None
        for _ in range(TARE_ATTEMPTS):
            try:
                raw = read_raw(TARE_READINGS)
                break
            except LoadCellError:
                continue
        if raw is None:
            raise LoadCellError("HX711 zero() failed (no valid readings)")
        _offset = raw
    else:
        for attempt in range(1, TARE_ATTEMPTS + 1):
            try:
                failed = _hx.zero(TARE_READINGS)
            except statistics.StatisticsError:   # outliers_filter with < 2 good readings
                failed = True
            if not failed:
                break
            print(f"[loadcell] zero() failed (attempt {attempt}/{TARE_ATTEMPTS})")
        else:
            raise LoadCellError("HX711 zero() failed (no valid readings)")
        _offset = _hx.get_current_offset()
    if verified_empty:
        _persist_empty_offset(_offset)


def calibrate(known_weight_g: float):
    """
    Return (and print) the scale factor for a known weight on the cradle.
    Call tare() first with the empty cradle in HOLD (that also stores the
    empty-cradle reference), then place the known weight and call this.
    """
    net_counts = read_raw(CALIBRATE_SAMPLES) - _current_offset()
    if _MOCK:
        print(f"[loadcell] MOCK calibrate: keeping SCALE_FACTOR = {SCALE_FACTOR:.2f}")
        return SCALE_FACTOR
    factor = net_counts / known_weight_g
    if factor == 0:
        raise LoadCellError("calibration weight reads 0 counts — is the card on the cradle?")
    print(f"[loadcell] Calibration: SCALE_FACTOR = {factor:.2f} for {known_weight_g}g")
    return factor


def deinit():
    """Forget the HX711 and free its two pins."""
    global _hx
    if _hx is not None and not _MOCK:
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup([DOUT_PIN, SCK_PIN])
        except Exception as exc:
            print(f"[loadcell] GPIO cleanup failed: {exc!r}")
    _hx = None
