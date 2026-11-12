"""
Per-machine calibration values in config/machine.json, so tuning the machine
never means editing code. Every key is optional; the code constants are the
defaults. See config/machine.example.json for the full list.

  {"card_detect": {"TRAVEL_SIGN": 1, "CENTRE_OFFSET_MM": 0.0, "BELT_SPEED_MM_S": 150.0,
                   "BRAKE_COAST_MM": 1.5, "STOP_LATENCY_S": 0.040, ...},
   "camera":      {"CARD_ROTATE": 90, "LENS_POSITION": 10.0, "AF_MODE": "manual",
                   "LOCK_AE_AWB": true, "EXPOSURE_TIME_US": null, ...},
   "sort":        {"EXIT_TRAVEL_MM": 144.0, "EXIT_TIME_MARGIN": 1.25, ...}}

Each module applies its own section at import time with apply().
"""

import json
import os
from pathlib import Path

CONFIG_FILE = Path(os.environ.get("RIFTBOUND_MACHINE_CONFIG",
                                  Path(__file__).parent.parent / "config" / "machine.json"))

_cache = None


def load() -> dict:
    global _cache
    if _cache is None:
        _cache = {}
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                if isinstance(data, dict):
                    _cache = data
                    print(f"[config] Loaded {CONFIG_FILE}")
            except Exception as exc:
                print(f"[config] Warning: could not read {CONFIG_FILE}: {exc} — using code defaults")
    return _cache


def section(name: str) -> dict:
    sec = load().get(name, {})
    return sec if isinstance(sec, dict) else {}


def apply(module, name: str, keys) -> dict:
    """Set module.KEY = config[name][KEY] for each KEY present, coerced to the
    type of the code default (None defaults accept any value). Returns the
    applied overrides."""
    sec = section(name)
    applied = {}
    for key in keys:
        if key not in sec:
            continue
        default = getattr(module, key, None)
        value = sec[key]
        try:
            if value is not None and isinstance(default, bool):
                value = bool(value)
            elif value is not None and isinstance(default, (int, float)) and not isinstance(default, bool):
                value = type(default)(value)
            elif value is not None and isinstance(default, tuple):
                value = tuple(value)
        except (TypeError, ValueError) as exc:
            print(f"[config] Warning: {name}.{key}={value!r} ignored ({exc})")
            continue
        setattr(module, key, value)
        applied[key] = value
    if applied:
        print(f"[config] {name}: {applied}")
    return applied
