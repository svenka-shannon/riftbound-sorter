"""
Option B (turntable picker, cad_b/) geometry shared by the B drivers, the
calibration defaults and the MOCK machine. Numbers mirror cad_b/b_params.scad
and cad_b/b_check.py — keep them in sync.

Yaw: the arm points at azimuth s (deg, CCW from +X). Stations sit on R = 260 mm
at s = 10 + 20·i: hopper (i 0), scan/weigh bed (1), bins 0-5 (2..7; the rules
engine's bin numbers 0-5), reject (8; rules bin 9). These are DESIGN angles:
the real ones are calibrated per machine (config/b_calibration.json).

Lift: one MG996R drives a parallelogram; link angle th (deg, + = up) from
TH_MIN -6 (lowest: the cup reaches an empty bin floor) to TH_FULL +10 (full
lift: the card bottom is 21 mm over every wall — the ONLY height at which yaw
may move). Cup lip height z = PIVOT_Z + LINK·sin(th) − HAND_DROP = 17 + 220·sin(th).
"""

import math
import sys

from hardware import machine_config

# ── stations ─────────────────────────────────────────────────────────────────
R_MM = 260.0
ST0_DEG, PITCH_DEG = 10.0, 20.0
BIN_NUMS = (0, 1, 2, 3, 4, 5)       # rules-engine bins on B
REJECT_BIN = 9                       # rules-engine reject bin (same as v2)
STATIONS = ("hopper", "scan") + tuple(f"bin{n}" for n in BIN_NUMS) + ("reject",)
NOMINAL_YAW = {name: ST0_DEG + PITCH_DEG * i for i, name in enumerate(STATIONS)}
STATION_HALF_WIDTH_DEG = 8.0         # a pocket spans about ±8 deg around its station ray


def bin_station(bin_num: int) -> str:
    """Station name for a rules-engine bin number (0-5 → bin0-bin5, 9 → reject)."""
    if bin_num == REJECT_BIN:
        return "reject"
    if bin_num in BIN_NUMS:
        return f"bin{bin_num}"
    raise ValueError(f"no station for bin {bin_num!r} on machine B (bins {BIN_NUMS} + reject 9)")


# ── heights (mm, board top = 0) ──────────────────────────────────────────────
CARD_T_MM = 0.33
FLOOR_Z_MM = 2.0                     # bin / hopper floor top (floor_t)
WALL_TOP_Z_MM = 34.0                 # every pocket wall top (pocket_h)
BED_TOP_Z_MM = 29.0                  # scan bed top (cell_z0 + cell_s + bed_boss + bed_t)
SLIDER_TRAVEL_MM = 10.0              # gravity slider travel above its resting contacts
HOPPER_CAPACITY = 80                 # 26.4 mm of cards under the 34 mm wall

# ── lift (parallelogram) ─────────────────────────────────────────────────────
LINK_MM = 220.0
PIVOT_Z_MM = 70.0
HAND_DROP_MM = 53.0                  # H1 → cup lip with the slider resting
TH_MIN = -6.0
TH_FULL = 10.0

# ── yaw stage / home cam ─────────────────────────────────────────────────────
LIMIT_MIN_DEG = -80.0                # software limits (the cable post is hit at about -90)
LIMIT_MAX_DEG = 175.0
HOME_CAM_LOW_DEG = -72.0             # switch held pressed for arm angles HOME..-72
CABLE_POST_DEG = -90.0
RELEASED_FROM_DEG = 8.0              # switch released over the whole working range from ~+8

machine_config.apply(sys.modules[__name__], "lift",
                     ("LINK_MM", "PIVOT_Z_MM", "HAND_DROP_MM", "TH_MIN", "TH_FULL"))


def lip_z(th: float) -> float:
    """Cup lip height (mm over the board top) at link angle th (deg), slider resting."""
    return PIVOT_Z_MM + LINK_MM * math.sin(math.radians(th)) - HAND_DROP_MM


def th_for_lip(z: float) -> float:
    """Link angle (deg) that puts the cup lip at height z (mm)."""
    s = (z - PIVOT_Z_MM + HAND_DROP_MM) / LINK_MM
    if not -1.0 <= s <= 1.0:
        raise ValueError(f"lip height {z} mm is out of the lift's reach")
    return math.degrees(math.asin(s))


def th_below(th: float, mm: float) -> float:
    """Link angle that puts the lip `mm` lower than at th."""
    return th_for_lip(lip_z(th) - mm)
