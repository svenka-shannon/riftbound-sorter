"""
Load cell weight reading via HX711.
GPIO 5 = DOUT, GPIO 6 = SCK

Used to detect:
  - No card picked up (weight ~0g)
  - Single card (~1.7-1.9g)
  - Double pick (>2.5g)

Requires: hx711 (pip install hx711)
Calibrate SCALE_FACTOR on first run using calibrate() function.
"""

import time
import statistics

try:
    from hx711 import HX711
except ImportError:
    HX711 = None

DOUT_PIN = 5
SCK_PIN  = 6

# Calibration — run calibrate() with a known weight to find this
SCALE_FACTOR = 420.0     # raw units per gram (adjust after calibration)
TARE_OFFSET  = 0         # set by tare()

# Thresholds (grams)
WEIGHT_EMPTY_MAX    = 0.5   # below this = no card
WEIGHT_SINGLE_MIN   = 1.3
WEIGHT_SINGLE_MAX   = 2.3
WEIGHT_DOUBLE_MIN   = 2.8   # above this = double pick

_hx = None


def init():
    global _hx
    if HX711 is None:
        raise ImportError("Install hx711: pip install hx711")
    _hx = HX711(dout_pin=DOUT_PIN, pd_sck_pin=SCK_PIN)
    _hx.set_scale_ratio(SCALE_FACTOR)
    _hx.tare()
    print(f"[loadcell] HX711 initialized (DOUT={DOUT_PIN}, SCK={SCK_PIN})")


def read_grams(samples=5) -> float:
    """Return average weight in grams over N samples."""
    readings = []
    for _ in range(samples):
        raw = _hx.get_weight_mean(1)
        readings.append(raw)
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
    """Zero the scale (call with no card/suction cup resting on sensor)."""
    _hx.tare()
    print("[loadcell] Tared.")


def calibrate(known_weight_g: float):
    """
    Print scale factor for a known weight.
    Place a card of known weight on the sensor, then call this.
    """
    raw = _hx.get_raw_data_mean(20)
    factor = (raw - _hx.get_data_mean(20)) / known_weight_g
    print(f"[loadcell] Calibration: set SCALE_FACTOR = {factor:.2f} for {known_weight_g}g")
    return factor
