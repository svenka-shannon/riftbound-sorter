"""
Per-machine calibration values in config/machine.json, so tuning the machine
never means editing code. Every key is optional; the code constants are the
defaults. See config/machine.example.json for the full list.

  {"card_detect": {"TRAVEL_SIGN": 1, "CENTRE_OFFSET_MM": 0.0, "BELT_SPEED_MM_S": 150.0, ...},
   "camera":      {"CARD_ROTATE": 90, "LENS_POSITION": 10.0, "AF_MODE": "manual", ...},
   "sort":        {"EXIT_TRAVEL_MM": 144.0, "EXIT_TIME_MARGIN": 1.25, ...},
   "elevator":    {"TOP_SWITCH_NC": true, "BOTTOM_SWITCH_NC": true, "RAISE_CAP_MM": 3.0, ...},
                  (TOP_SWITCH_NC must be true: NO wiring of the top switch is refused)
   "servos":      {"ARM_ACTUATION_RANGE": 180}}

Validation (audit M6): the WHOLE file is checked against SCHEMA the first
time any module reads it. Every value must have the right JSON type (a bool
is true/false, never the string "false"; a number is a JSON number, never a
string, NaN or Infinity), lie inside its range / enum, and every section must
be an object. Unknown sections and unknown keys (typos) are errors. Keys
starting with "_" are comments and ignored. Invalid JSON is an error too —
the machine never silently falls back to the code defaults.

Any problem raises MachineConfigError listing EVERY bad key; main.py turns
that into a clear message and exit status 78 (EX_CONFIG), which the systemd
unit does not restart (RestartPreventExitStatus=78).

Each module applies its own section at import time with apply().
"""

import json
import math
import os
from pathlib import Path

CONFIG_FILE = Path(os.environ.get("RIFTBOUND_MACHINE_CONFIG",
                                  Path(__file__).parent.parent / "config" / "machine.json"))

EX_CONFIG = 78          # sysexits.h: configuration error


class MachineConfigError(ValueError):
    """config/machine.json is invalid; .problems lists every bad key."""

    def __init__(self, path, problems):
        self.path = Path(path)
        self.problems = list(problems)
        lines = "\n".join(f"  - {p}" for p in self.problems)
        super().__init__(f"invalid machine config {self.path} — refusing to start:\n{lines}\n"
                         "Fix these keys (see config/machine.example.json for every key, its "
                         "default and type), or delete the file to use the code defaults.")


# ── Schema ───────────────────────────────────────────────────────────────────
# kind: "float" (any finite JSON number), "int" (integral JSON number),
#       "bool", "enum" (one of `values`), "gains" ([red, blue] or null)
def _f(lo, hi, nullable=False):
    return {"kind": "float", "min": lo, "max": hi, "nullable": nullable}


def _i(lo, hi, nullable=False):
    return {"kind": "int", "min": lo, "max": hi, "nullable": nullable}


def _e(*values, why=None):
    return {"kind": "enum", "values": values, "nullable": False, "why": why}


_B = {"kind": "bool", "nullable": False}

SCHEMA = {
    "card_detect": {
        "TRAVEL_SIGN": _e(1, -1),
        "CENTRE_OFFSET_MM": _f(-20.0, 20.0),
        "BELT_SPEED_MM_S": _f(30.0, 600.0),
        "BRAKE_COAST_MM": _f(0.0, 20.0),
        "STOP_LATENCY_S": _f(0.0, 0.5),
        "CENTER_TOL_MM": _f(0.1, 20.0),
        "MAX_CAPTURE_OFFSET_MM": _f(0.5, 30.0),
        "PIXEL_DIFF": _i(1, 254),
        "COL_FRAC": _f(0.01, 1.0),
        "VIEW_HALF_MM": _f(10.0, 64.0),
        "SEEK_MAX_TRAVEL_MM": _f(20.0, 170.0),
        "SEEK_HARD_LIMIT_FACTOR": _f(1.0, 10.0),
        "FRAME_TIMEOUT_S": _f(0.05, 5.0),
    },
    "camera": {
        "LENS_POSITION": _f(0.0, 32.0),
        "AF_MODE": _e("manual", "continuous"),
        "LOCK_AE_AWB": _B,
        "EXPOSURE_TIME_US": _i(10, 100_000, nullable=True),
        "ANALOGUE_GAIN": _f(1.0, 16.0, nullable=True),
        "COLOUR_GAINS": {"kind": "gains", "min": 0.1, "max": 8.0, "nullable": True},
        "CARD_ROTATE": _e(0, 90, 180, 270),
        "STABILIZE_DELAY_S": _f(0.0, 2.0),
        "WARMUP_S": _f(0.0, 10.0),
        "SWAP_RB": _B,
        "LORES_TIMEOUT_S": _f(0.05, 5.0),
    },
    "sort": {
        "EXIT_TRAVEL_MM": _f(50.0, 400.0),
        "EXIT_TIME_MARGIN": _f(1.0, 3.0),
        "EXIT_MIN_S": _f(0.05, 5.0),
        "EXIT_MAX_S": _f(0.1, 10.0),
        "EXIT_EXTRA_S": _f(0.0, 3.0),
        "SEAL_S": _f(0.0, 3.0),
        "DROP_SETTLE_S": _f(0.0, 3.0),
        "ARM_LIFT_DEG": _f(0.0, 45.0),
        "ARM_LIFT_S": _f(0.05, 5.0),
        "WEIGH_SETTLE_S": _f(0.0, 5.0),
        "TARE_SETTLE_S": _f(0.0, 5.0),
        "RESUME_DELAY_S": _f(0.0, 30.0),
        "CALIBRATION_MASS_G": _f(0.5, 500.0),
        "CUP_HOLD_MAX_S": _f(10.0, 3600.0),
    },
    "elevator": {
        # Audit 3: normally-open wiring of the TOP switch is not supported. A broken
        # NO wire reads "never pressed", and the first raise after homing (which
        # must be allowed the full travel: the stack height is unknown) would push
        # the stack into the arm. With NC a broken wire reads pressed: no rise.
        "TOP_SWITCH_NC": _e(True, why="normally-open wiring of the top-of-stack switch is not "
                                      "supported — a broken NO wire reads 'never pressed' and "
                                      "the first raise after homing would push the stack into "
                                      "the arm. Wire it normally-closed (C → GND, NC → GPIO 12)"),
        "BOTTOM_SWITCH_NC": _B,
        "RAISE_CAP_MM": _f(0.5, 10.0),
        "UP_DIRECTION": _e(1, -1),
        "TRIP_EXTRA_STEPS": _i(0, 2000),
        "HOME_BACKOFF_MM": _f(0.1, 5.0),
    },
    "servos": {
        "ARM_ACTUATION_RANGE": _e(180, 270),
    },
}

# Cross-key rules: (section, low key, high key) → low ≤ high when both are set
_ORDERED = (("sort", "EXIT_MIN_S", "EXIT_MAX_S"),)

_cache = None


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_value(where: str, spec: dict, v):
    """Return (problem | None, normalised value)."""
    if v is None:
        return (None, None) if spec["nullable"] else (f"{where}: null is not allowed", None)
    kind = spec["kind"]
    if kind == "bool":
        if not isinstance(v, bool):
            return f"{where}: must be true or false (a JSON boolean, not {json.dumps(v)})", None
        return None, v
    if kind == "enum":
        ok = any(v == x and type(v) is type(x) for x in spec["values"])
        if not ok:
            if len(spec["values"]) == 1:
                msg = f"{where}: must be {json.dumps(spec['values'][0])}, got {json.dumps(v)}"
            else:
                msg = f"{where}: must be one of {list(spec['values'])}, got {json.dumps(v)}"
            if spec.get("why"):
                msg += f" — {spec['why']}"
            return msg, None
        return None, v
    if kind == "gains":
        if (not isinstance(v, list) or len(v) != 2 or not all(_is_number(x) for x in v)
                or not all(math.isfinite(x) and spec["min"] <= x <= spec["max"] for x in v)):
            return (f"{where}: must be null or [red, blue] with two finite numbers in "
                    f"[{spec['min']}, {spec['max']}], got {json.dumps(v)}"), None
        return None, [float(x) for x in v]
    # float / int
    if not _is_number(v):
        return f"{where}: must be a number, got {json.dumps(v)}", None
    if not math.isfinite(v):
        return f"{where}: must be a finite number, got {v}", None
    if kind == "int":
        if float(v) != int(v):
            return f"{where}: must be a whole number, got {v}", None
        v = int(v)
    else:
        v = float(v)
    if not spec["min"] <= v <= spec["max"]:
        return f"{where}: {v} is outside [{spec['min']}, {spec['max']}]", None
    return None, v


def validate(data) -> tuple[dict, list[str]]:
    """(normalised config, problems). Pure: does not touch the cache."""
    problems = []
    out = {}
    if not isinstance(data, dict):
        return {}, [f"top level must be a JSON object, got {type(data).__name__}"]
    for sec, body in data.items():
        if str(sec).startswith("_"):
            continue
        if sec not in SCHEMA:
            problems.append(f"{sec}: unknown section (valid: {', '.join(SCHEMA)})")
            continue
        if not isinstance(body, dict):
            problems.append(f"{sec}: must be a JSON object of KEY: value, got {type(body).__name__}")
            continue
        clean = {}
        for key, v in body.items():
            if str(key).startswith("_"):
                continue
            where = f"{sec}.{key}"
            spec = SCHEMA[sec].get(key)
            if spec is None:
                problems.append(f"{where}: unknown key (valid: {', '.join(SCHEMA[sec])})")
                continue
            problem, nv = _check_value(where, spec, v)
            if problem:
                problems.append(problem)
            else:
                clean[key] = nv
        out[sec] = clean
    for sec, lo, hi in _ORDERED:
        s = out.get(sec, {})
        if s.get(lo) is not None and s.get(hi) is not None and s[lo] > s[hi]:
            problems.append(f"{sec}.{lo} ({s[lo]}) must not exceed {sec}.{hi} ({s[hi]})")
    return out, problems


def _reject_constant(token):
    raise ValueError(f"{token} is not a valid JSON number")


def load() -> dict:
    """Validated config (cached). Raises MachineConfigError on ANY problem."""
    global _cache
    if _cache is None:
        if not CONFIG_FILE.exists():
            _cache = {}
            return _cache
        try:
            # NaN / Infinity are not JSON; Python's parser accepts them unless told not to
            data = json.loads(CONFIG_FILE.read_text(), parse_constant=_reject_constant)
        except (OSError, ValueError) as exc:
            raise MachineConfigError(CONFIG_FILE, [f"not valid JSON: {exc}"]) from exc
        cfg, problems = validate(data)
        if problems:
            raise MachineConfigError(CONFIG_FILE, problems)
        _cache = cfg
        print(f"[config] Loaded {CONFIG_FILE}")
    return _cache


def section(name: str) -> dict:
    return load().get(name, {})


def apply(module, name: str, keys) -> dict:
    """Set module.KEY = config[name][KEY] for each KEY present (already
    validated and normalised by load()). Returns the applied overrides."""
    sec = section(name)
    applied = {}
    for key in keys:
        if key not in sec:
            continue
        value = sec[key]
        if isinstance(value, list):
            value = tuple(value)
        setattr(module, key, value)
        applied[key] = value
    if applied:
        print(f"[config] {name}: {applied}")
    return applied
