"""
Option B calibration store: config/b_calibration.json (MOCK runs:
config/b_calibration.mock.json, so a mock never overwrites the real values).

Measured per machine, written by the calibration API (sorter_b.py manual
functions / web/app.py /api/b/... endpoints), read at start-up:

  {"stations": {
      "hopper": {"yaw": 10.0, "approach_th": 4.69, "limit_th": -5.48, "floor_th": -3.91},
      "scan":   {"yaw": 30.0, "approach_th": 4.17, "limit_th": 2.34, "touch_th": 3.13},
      "bin0":   {"yaw": 50.0, "approach_th": 4.43, "limit_th": -4.17},
      ... bin1 .. bin5 (70 .. 150), "reject": {"yaw": 170.0, ...}},
   "park_yaw": -10.0,
   "clear_yaw": null,
   "servo_map": [[-6.0, 84.0], [10.0, 100.0]]}

  yaw          station ray (deg from the home edge), approached from BELOW
  approach_th  fast descent ends here (above any surface the cup can meet there);
               the slow, touch-watching descent starts from it
  limit_th     lowest th the descent may reach: no touch by then means
                 hopper → empty (the floor has a Ø32 hole under the cup, cad
                          029e479: with no card the cup drops through it; the
                          default is the lip 6 mm under the floor top, in the hole);
                 scan → contact fault;  bin → released at the floor
  floor_th     hopper only: th at which the cup lip is level with the hopper floor
               top (the last card is 0.33 mm higher). A touch at or below it = the
               last card; no touch with the lip FLOOR_PASS_MM below it = the cup is
               in the hole = empty. null: any no-touch counts as empty
  touch_th     scan only: th at which the empty cup meets the empty bed (start-up
               touch self-test window)
  park_yaw     rest pose: inside the home cam (switch pressed), nothing below the
               cup; the arm parks here when paused / stopped / shut down
  clear_yaw    where the arm waits while the camera looks at the bed (null = the
               hopper's yaw)
  servo_map    two [th, servo angle] points: the MG996R angle for a link angle
               (linear between / beyond them); measure th with an angle gauge

Every key is optional (defaults from the CAD, hardware/b_geometry.py).
Validation (like config/machine.json): unknown keys, non-numbers, NaN, values
outside the lift / yaw range, station yaws more than STATION_WINDOW_DEG from
the design angle, stations out of order, inconsistent heights or a servo map
with an implausible gain are ALL listed and refused (BCalibrationError →
main.py exits 78). Saves validate the whole file first and are atomic.
"""

import json
import math
import os
import tempfile
from pathlib import Path

from hardware import b_geometry as geo
from hardware import instance

_MOCK = os.environ.get("MOCK_HARDWARE", "0") == "1"
CAL_FILE = Path(__file__).resolve().parent.parent / "config" / (
    "b_calibration.mock.json" if _MOCK else "b_calibration.json")

STATION_WINDOW_DEG = 8.0          # calibrated yaw within this of the design angle
HOPPER_MIN_YAW = 5.0              # the home switch must read released at the hopper
PARK_RANGE = (-55.0, -2.0)        # park inside the home cam (switch pressed), above LIMIT_MIN + undershoot
CLEAR_MIN_FROM_SCAN_DEG = 15.0    # the clear pose must be out of the camera's view
SERVO_GAIN_RANGE = (0.7, 1.4)     # |Δservo / Δth|: direct drive, MG996R gain spread
STATION_KEYS = {"hopper": ("yaw", "approach_th", "limit_th", "floor_th"),
                "scan": ("yaw", "approach_th", "limit_th", "touch_th")}
TOP_KEYS = ("stations", "park_yaw", "clear_yaw", "servo_map")


class BCalibrationError(ValueError):
    """config/b_calibration.json is invalid; .problems lists every bad key."""

    def __init__(self, path, problems):
        self.path = Path(path)
        self.problems = list(problems)
        lines = "\n".join(f"  - {p}" for p in self.problems)
        super().__init__(f"invalid option B calibration {self.path} — refusing to start:\n{lines}\n"
                         "Fix these keys (or delete them to use the CAD defaults) and re-calibrate.")


def _keys(name: str) -> tuple:
    return STATION_KEYS.get(name, ("yaw", "approach_th", "limit_th"))


def defaults() -> dict:
    """CAD-derived calibration (hardware/b_geometry.py)."""
    th = geo.th_for_lip
    wall_th = round(th(geo.WALL_TOP_Z_MM + 1.0), 2)
    st = {"hopper": {"yaw": geo.NOMINAL_YAW["hopper"], "approach_th": wall_th,
                     "limit_th": round(th(geo.FLOOR_Z_MM - 6.0), 2),       # in the floor hole
                     "floor_th": round(th(geo.FLOOR_Z_MM), 2)},
          "scan": {"yaw": geo.NOMINAL_YAW["scan"],
                   "approach_th": round(th(geo.BED_TOP_Z_MM + 4.0), 2),
                   "limit_th": round(th(geo.BED_TOP_Z_MM - 3.0), 2),
                   "touch_th": round(th(geo.BED_TOP_Z_MM), 2)}}
    for name in geo.STATIONS[2:]:
        st[name] = {"yaw": geo.NOMINAL_YAW[name], "approach_th": wall_th,
                    "limit_th": round(th(geo.FLOOR_Z_MM - 1.0), 2)}
    return {"stations": st, "park_yaw": -10.0, "clear_yaw": None,
            "servo_map": [[geo.TH_MIN, 90.0 + geo.TH_MIN], [geo.TH_FULL, 90.0 + geo.TH_FULL]]}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate(data, actuation_range: int = 180) -> tuple[dict, list[str]]:
    """(calibration merged onto the defaults, problems). Pure."""
    cal = defaults()
    problems = []
    if not isinstance(data, dict):
        return cal, [f"top level must be a JSON object, got {type(data).__name__}"]
    for k in data:
        if not str(k).startswith("_") and k not in TOP_KEYS:
            problems.append(f"{k}: unknown key (valid: {', '.join(TOP_KEYS)})")
    sts = data.get("stations", {})
    if not isinstance(sts, dict):
        problems.append("stations: must be an object of station → {yaw, approach_th, ...}")
        sts = {}
    for name, body in sts.items():
        if str(name).startswith("_"):
            continue
        if name not in geo.STATIONS:
            problems.append(f"stations.{name}: unknown station (valid: {', '.join(geo.STATIONS)})")
            continue
        if not isinstance(body, dict):
            problems.append(f"stations.{name}: must be an object")
            continue
        for k, v in body.items():
            if str(k).startswith("_"):
                continue
            where = f"stations.{name}.{k}"
            if k not in _keys(name):
                problems.append(f"{where}: unknown key (valid: {', '.join(_keys(name))})")
            elif v is None and k == "floor_th":
                cal["stations"][name][k] = None
            elif not _num(v):
                problems.append(f"{where}: must be a finite number, got {json.dumps(v)}")
            else:
                cal["stations"][name][k] = float(v)
    for k in ("park_yaw", "clear_yaw"):
        if k in data:
            v = data[k]
            if v is None and k == "clear_yaw":
                cal[k] = None
            elif not _num(v):
                problems.append(f"{k}: must be a finite number{' or null' if k == 'clear_yaw' else ''}, "
                                f"got {json.dumps(v)}")
            else:
                cal[k] = float(v)
    if "servo_map" in data:
        sm = data["servo_map"]
        if (not isinstance(sm, list) or len(sm) != 2 or
                not all(isinstance(p, list) and len(p) == 2 and all(_num(x) for x in p) for p in sm)):
            problems.append(f"servo_map: must be [[th, servo], [th, servo]] (finite numbers), got "
                            f"{json.dumps(sm)}")
        else:
            cal["servo_map"] = [[float(a), float(b)] for a, b in sm]
    if problems:
        return cal, problems
    return cal, rule_problems(cal, actuation_range)


def rule_problems(cal: dict, actuation_range: int = 180) -> list[str]:
    """The rules between the values (each already a finite number)."""
    out = []
    lo_th, hi_th = geo.TH_MIN, geo.TH_FULL
    prev = None
    for name in geo.STATIONS:
        s = cal["stations"][name]
        y = s["yaw"]
        nom = geo.NOMINAL_YAW[name]
        if abs(y - nom) > STATION_WINDOW_DEG:
            out.append(f"stations.{name}.yaw: {y:g} is more than {STATION_WINDOW_DEG:g} deg from the "
                       f"design angle {nom:g} — a typo? (stations are 20 deg apart)")
        if not geo.LIMIT_MIN_DEG <= y <= geo.LIMIT_MAX_DEG:
            out.append(f"stations.{name}.yaw: {y:g} is outside the yaw limits "
                       f"[{geo.LIMIT_MIN_DEG:g}, {geo.LIMIT_MAX_DEG:g}]")
        if prev is not None and y <= cal["stations"][prev]["yaw"]:
            out.append(f"stations.{name}.yaw ({y:g}) must be above stations.{prev}.yaw "
                       f"({cal['stations'][prev]['yaw']:g}): stations run hopper, scan, bin0..bin5, reject")
        prev = name
        for k in _keys(name)[1:]:
            v = s.get(k)
            if v is not None and not lo_th <= v <= hi_th:
                out.append(f"stations.{name}.{k}: {v:g} is outside the lift range [{lo_th:g}, {hi_th:g}]")
        if s["limit_th"] >= s["approach_th"]:
            out.append(f"stations.{name}: limit_th ({s['limit_th']:g}) must be below approach_th "
                       f"({s['approach_th']:g})")
        for k in ("touch_th", "floor_th"):
            v = s.get(k)
            if v is not None and not s["limit_th"] <= v < s["approach_th"]:
                out.append(f"stations.{name}.{k}: {v:g} must lie between limit_th ({s['limit_th']:g}) "
                           f"and approach_th ({s['approach_th']:g})")
    hop = cal["stations"]["hopper"]["yaw"]
    if hop < HOPPER_MIN_YAW:
        out.append(f"stations.hopper.yaw: {hop:g} is below {HOPPER_MIN_YAW:g} — the home switch must "
                   "read released at the hopper (lost-step check)")
    p = cal["park_yaw"]
    if not PARK_RANGE[0] <= p <= PARK_RANGE[1]:
        out.append(f"park_yaw: {p:g} must lie in [{PARK_RANGE[0]:g}, {PARK_RANGE[1]:g}] (inside the home "
                   "cam, where the switch reads pressed and nothing is under the cup)")
    c = cal["clear_yaw"]
    if c is not None:
        if not geo.LIMIT_MIN_DEG <= c <= geo.LIMIT_MAX_DEG:
            out.append(f"clear_yaw: {c:g} is outside the yaw limits")
        if abs(c - cal["stations"]["scan"]["yaw"]) < CLEAR_MIN_FROM_SCAN_DEG:
            out.append(f"clear_yaw: {c:g} is within {CLEAR_MIN_FROM_SCAN_DEG:g} deg of the scan station "
                       "— the arm would block the camera")
    (t0, s0), (t1, s1) = cal["servo_map"]
    if abs(t1 - t0) < 4.0:
        out.append("servo_map: the two points must be at least 4 deg of th apart")
    else:
        gain = abs((s1 - s0) / (t1 - t0))
        if not SERVO_GAIN_RANGE[0] <= gain <= SERVO_GAIN_RANGE[1]:
            out.append(f"servo_map: {gain:.2f} servo deg per link deg is outside "
                       f"{SERVO_GAIN_RANGE[0]}..{SERVO_GAIN_RANGE[1]} (direct drive: ~1)")
    for t, sv in cal["servo_map"]:
        if not 0.0 <= sv <= float(actuation_range):
            out.append(f"servo_map: servo angle {sv:g} is outside 0..{actuation_range}")
    return out


# ── the loaded calibration ───────────────────────────────────────────────────
_cal = None


def _reject_constant(token):
    raise ValueError(f"{token} is not a valid JSON number")


def load(actuation_range: int = 180) -> dict:
    """Read + validate CAL_FILE (defaults if absent). Raises BCalibrationError."""
    global _cal
    data = {}
    if CAL_FILE.exists():
        try:
            data = json.loads(CAL_FILE.read_text(), parse_constant=_reject_constant)
        except (OSError, ValueError) as exc:
            raise BCalibrationError(CAL_FILE, [f"not valid JSON: {exc}"]) from exc
    cal, problems = validate(data, actuation_range)
    if problems:
        raise BCalibrationError(CAL_FILE, problems)
    _cal = cal
    return cal


def get() -> dict:
    return _cal if _cal is not None else load()


def station(name: str) -> dict:
    if name not in geo.STATIONS:
        raise ValueError(f"unknown station {name!r} (valid: {', '.join(geo.STATIONS)})")
    return dict(get()["stations"][name])


def station_yaw(name: str) -> float:
    return station(name)["yaw"]


def park_yaw() -> float:
    return get()["park_yaw"]


def clear_yaw() -> float:
    c = get()["clear_yaw"]
    return station_yaw("hopper") if c is None else c


def servo_map() -> list:
    return [list(p) for p in get()["servo_map"]]


def station_at(yaw_deg, tol_deg: float = 0.2):
    """Name of the station whose calibrated yaw is within tol_deg of yaw_deg."""
    if yaw_deg is None:
        return None
    for name in geo.STATIONS:
        if abs(get()["stations"][name]["yaw"] - yaw_deg) <= tol_deg:
            return name
    return None


def station_near(yaw_deg):
    """Station whose pocket lies under the cup at yaw_deg (±STATION_HALF_WIDTH_DEG)."""
    if yaw_deg is None:
        return None
    best = min(geo.STATIONS, key=lambda n: abs(get()["stations"][n]["yaw"] - yaw_deg))
    if abs(get()["stations"][best]["yaw"] - yaw_deg) <= geo.STATION_HALF_WIDTH_DEG:
        return best
    return None


def _file_data() -> dict:
    if not CAL_FILE.exists():
        return {}
    return json.loads(CAL_FILE.read_text(), parse_constant=_reject_constant)


def _save(data: dict, actuation_range: int = 180) -> dict:
    """Validate the WHOLE file content, then write it atomically and reload."""
    global _cal
    cal, problems = validate(data, actuation_range)
    if problems:
        raise BCalibrationError(CAL_FILE, problems)
    CAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{CAL_FILE.name}.", suffix=".tmp", dir=CAL_FILE.parent)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(data, indent=2) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o644)
        instance._match_parent_owner(tmp)
        os.replace(tmp, CAL_FILE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    instance.fsync_dir(CAL_FILE.parent)
    _cal = cal
    return cal


def set_station_value(name: str, key: str, value, actuation_range: int = 180) -> dict:
    if name not in geo.STATIONS:
        raise ValueError(f"unknown station {name!r} (valid: {', '.join(geo.STATIONS)})")
    if key not in _keys(name):
        raise ValueError(f"{name} has no {key!r} (valid: {', '.join(_keys(name))})")
    data = _file_data()
    data.setdefault("stations", {}).setdefault(name, {})[key] = (
        None if value is None else round(float(value), 4))
    return _save(data, actuation_range)


def set_top_value(key: str, value, actuation_range: int = 180) -> dict:
    if key not in TOP_KEYS or key == "stations":
        raise ValueError(f"unknown calibration key {key!r}")
    data = _file_data()
    data[key] = value
    return _save(data, actuation_range)
