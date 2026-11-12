"""
Load cell weight reading via HX711 (GPIO 5 = DOUT, GPIO 6 = SCK).

The load cell sits on the shuttle's tilt frame under the cradle
(cad/shuttle.scad). The card is weighed AT REST on the cradle in the
shuttle's HOLD pose, after it has left the belt:
  - empty  (~0 g)       card lost between the belt end and the cradle
  - single (~1.75 g)    one raw Riftbound card
  - double (>2.8 g)     two cards stuck together (picked as one)
  - unknown             anything else (partial / bent / leaning on the lip)

Tare with the EMPTY cradle in HOLD (main.py tares at the end of every cycle,
right after shuttle.route() has proved the cradle empty), so the weigh pose
and the tare pose are the same.

Requires: hx711 (gandalf15/HX711, PyPI "hx711")
Calibrate with `python main.py --calibrate`; the scale factor is saved to
config/loadcell_calibration.json and loaded by init().
"""

import json
import os
import statistics
from pathlib import Path

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"

try:
    from hx711 import HX711
except ImportError:
    HX711 = None

DOUT_PIN = 5
SCK_PIN  = 6

_CALIBRATION_FILE = Path(__file__).parent.parent / "config" / "loadcell_calibration.json"

# Calibration — `python main.py --calibrate` writes SCALE_FACTOR to the file above
SCALE_FACTOR = 420.0     # raw ADC counts per gram (default until calibrated)

# Thresholds (grams, relative to the empty-cradle tare)
WEIGHT_EMPTY_MAX    = 0.5   # below this = no card
WEIGHT_SINGLE_MIN   = 1.3
WEIGHT_SINGLE_MAX   = 2.3
WEIGHT_DOUBLE_MIN   = 2.8   # above this = double pick

MOCK_CARD_G = 1.75          # simulated single card

_hx = None


class LoadCellError(RuntimeError):
    """The HX711 returned no data (wiring, power, or timing problem)."""


# ── MOCK world ───────────────────────────────────────────────────────────────
# read_grams() returns (load on the cradle − tare). The simulated card leaves
# the cradle when it is tipped, i.e. whenever the shuttle carriage is away from
# home at the time of a reading (shuttle.route() only reads after a tip).
_mock_load_g = 0.0
_mock_tare_g = 0.0


def mock_set_load(grams: float) -> None:
    """MOCK only: put `grams` on the simulated cradle (0 = empty)."""
    global _mock_load_g
    _mock_load_g = float(grams)


def _mock_read() -> float:
    global _mock_load_g
    try:
        from hardware import shuttle
        target, tilt, _ = shuttle.state()
        if target not in (None, "home"):
            _mock_load_g = 0.0          # card was tipped off at a column
    except Exception:
        pass
    return _mock_load_g - _mock_tare_g


# ── Hardware ─────────────────────────────────────────────────────────────────
def _load_calibration() -> None:
    global SCALE_FACTOR
    if not _CALIBRATION_FILE.exists():
        return
    try:
        cal = json.loads(_CALIBRATION_FILE.read_text())
        SCALE_FACTOR = float(cal["scale_factor"])
        print(f"[loadcell] Loaded SCALE_FACTOR={SCALE_FACTOR:.2f} from {_CALIBRATION_FILE}")
    except Exception as exc:
        print(f"[loadcell] Warning: could not read {_CALIBRATION_FILE}: {exc}")


def save_calibration(factor: float) -> None:
    """Persist the scale factor so the next init() uses it."""
    global SCALE_FACTOR
    SCALE_FACTOR = float(factor)
    _CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CALIBRATION_FILE.write_text(json.dumps({"scale_factor": SCALE_FACTOR}, indent=2))
    if _hx is not None:
        _hx.set_scale_ratio(SCALE_FACTOR)
    print(f"[loadcell] Saved SCALE_FACTOR={SCALE_FACTOR:.2f} to {_CALIBRATION_FILE}")


def _zero() -> None:
    """Zero the HX711. gandalf15/HX711 calls this zero() (returns False on
    success); some forks call it tare(). Support both."""
    if hasattr(_hx, "zero"):
        failed = _hx.zero()
        if failed:
            raise LoadCellError("HX711 zero() failed (no valid readings)")
    else:
        _hx.tare()


def init():
    """Open the HX711 and zero it. The cradle should be empty: main.py
    re-tares with the empty cradle in HOLD before the first card anyway."""
    global _hx
    _load_calibration()
    if _MOCK:
        print("[loadcell] MOCK mode — simulated cradle (mock_set_load())")
        return
    if HX711 is None:
        raise ImportError("Install hx711: pip install hx711")
    _hx = HX711(dout_pin=DOUT_PIN, pd_sck_pin=SCK_PIN)
    _hx.set_scale_ratio(SCALE_FACTOR)
    _zero()
    print(f"[loadcell] HX711 initialized (DOUT={DOUT_PIN}, SCK={SCK_PIN})")


def read_grams(samples=5) -> float:
    """Return average weight in grams over N samples (relative to the last tare).

    Raises LoadCellError if the HX711 returns no data: the library reports a
    failed read as False, which would otherwise look like 0 g = "empty".
    """
    if _MOCK:
        return _mock_read()
    readings = []
    for _ in range(samples):
        raw = _hx.get_weight_mean(1)
        if raw is False or raw is None:
            raise LoadCellError("HX711 read failed")
        readings.append(float(raw))
    return statistics.mean(readings)


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


def tare():
    """Zero the scale. Call ONLY with the cradle empty and in HOLD."""
    global _mock_tare_g
    if _MOCK:
        _mock_tare_g = _mock_load_g
        return
    _zero()


def calibrate(known_weight_g: float):
    """
    Return (and print) the scale factor for a known weight on the cradle.
    Call tare() first with the empty cradle in HOLD, then place the known
    weight and call this.

    B-22 fix: uses only get_data_mean(), which already subtracts the tare
    offset, so the result is ADC counts per gram.
    """
    if _MOCK:
        print(f"[loadcell] MOCK calibrate: keeping SCALE_FACTOR = {SCALE_FACTOR:.2f}")
        return SCALE_FACTOR
    net_counts = _hx.get_data_mean(20)   # tare-subtracted counts ∝ weight
    if net_counts is False or net_counts is None:
        raise LoadCellError("HX711 read failed during calibration")
    factor = net_counts / known_weight_g
    print(f"[loadcell] Calibration: SCALE_FACTOR = {factor:.2f} for {known_weight_g}g")
    return factor
