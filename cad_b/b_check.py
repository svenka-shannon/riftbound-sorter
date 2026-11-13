#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Option B geometry check: station layout, pocket clearances against a real
error stack-up, lift range, swing clearance with sag, camera clearance and
focus, load cell. Numbers mirror cad_b/b_params.scad (round 2).
Exits non-zero if any check fails.
"""
import math, sys

# ---- shared parameters (keep in sync with b_params.scad) ----
R = 260.0
S0, PITCH, N = 10.0, 20.0, 9
CARD_W, CARD_L, CARD_T = 63.0, 88.0, 0.33
HOP_IN_W, HOP_IN_L, WALL = 65.0, 90.0, 2.4
BIN_R_IN, BIN_R_OUT, HALF_WALL, DIVIDER_R0 = R - 50, R + 50, 1.2, 236.0
FLOOR = 2.0
WALL_TOP = FLOOR + 32.0
BED_TOP = 8 + 12.7 + 5 + 3.3
L, R_P1, Z_P1, D_LINK, H_OFF = 220.0, 25.0, 70.0, 40.0, 15.0
TH_MIN, TH_MAX = -6.0, 10.0
SLIDER_BELOW, CUP_H = 22.0, 23.0
HAND_DROP = 8 + SLIDER_BELOW + CUP_H
SLIDER_TRAVEL = 10.0
HAND_TOP_ABOVE_H2 = 10.0
RING_STACK = 3 + 7 + 2.5 + 3          # screw heads + 608 + cap + M3 head
CAM_DIST = 176.0
CAM_LENS_Z = BED_TOP + CAM_DIST
STEP_DEG = 180.0 / 410                 # PCA9685 12-bit, 500..2500 us at 50 Hz

# error budget (yaw), degrees and mm
YAW_REPEAT_DEG = 0.6                   # same-direction approach: deadband + residual backlash
YAW_SETPOINT_DEG = STEP_DEG / 2
CUP_ON_CARD_MM = 1.5                   # re-pick from the bed, aimed with the camera's measured card centre
CARD_ROT_DEG = math.degrees(math.atan((HOP_IN_W - CARD_W) / CARD_L))   # rotation allowed by the hopper
# vertical budget for the swing (mm)
SAG_MM = 4.4 + 1.2                      # roller-gap tilt (reviewer: 3.1-4.4) + link A sag
CARD_TILT_MM = 2.6                      # 3 deg bellows tilt at the card corner

fails = []
def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        fails.append(msg)

stations = [S0 + i * PITCH for i in range(N)]
names = ["hopper", "scan/weigh"] + [f"bin {i}" for i in range(1, 7)] + ["reject"]
print("stations: " + ", ".join(f"{n} {s:.0f}" for s, n in zip(stations, names)))
check(stations[-1] - stations[0] <= 160, f"yaw span {stations[0]:.0f}..{stations[-1]:.0f}: needs +/-80 deg (bench-test the servo first)")

# hopper fits its slot
hop_ow = HOP_IN_W + 2 * WALL
r_hop_in = R - HOP_IN_L / 2 - WALL
chord = 2 * r_hop_in * math.sin(math.radians(PITCH / 2))
check(chord >= hop_ow + 1.0, f"hopper fits its 20 deg slot: chord {chord:.1f} vs {hop_ow:.1f} (+1)")

# yaw error stack at a radius r (mm), worst case linear sum
def yaw_err(r):
    return r * math.radians(YAW_REPEAT_DEG + YAW_SETPOINT_DEG) + CUP_ON_CARD_MM
corner_rot = (CARD_L / 2) * math.radians(CARD_ROT_DEG)     # tangential corner shift from card rotation
def wedge_room(r):
    return (2 * r * math.sin(math.radians(PITCH / 2)) - 2 * HALF_WALL - CARD_W) / 2
r_c_in = R - CARD_L / 2
need_div = yaw_err(DIVIDER_R0) + corner_rot
check(wedge_room(DIVIDER_R0) >= need_div, f"bin divider (starts r {DIVIDER_R0:.0f}): room {wedge_room(DIVIDER_R0):.1f} mm vs error stack {need_div:.1f}")
gap_cards = 2 * r_c_in * math.sin(math.radians(PITCH / 2)) - CARD_W     # neighbouring cards' inner corners, nominal
need_gap = 2 * (yaw_err(r_c_in) + corner_rot)
check(gap_cards >= need_gap * 0.5 + 0.5, f"inner zone (no divider): neighbours' corners {gap_cards:.1f} mm apart nominal; one card's error {need_gap/2:.1f}")
rad_room = (BIN_R_OUT - BIN_R_IN - CARD_L) / 2
check(rad_room >= 2 + 2, f"bin radial room {rad_room:.1f} mm each end vs hopper offset 1 + cup 1.5 + lift 1.5")
hop_room = (HOP_IN_W - CARD_W) / 2
check(R * math.radians(YAW_REPEAT_DEG + 1.0) + 27 / 2 <= CARD_W / 2, "hopper pick: the 27 mm cup stays on the card even with a 1.6 deg error")
print(f"  card rotation in the hopper <= {CARD_ROT_DEG:.2f} deg; 1 deg at the cup = {R*math.radians(1):.1f} mm")

# lift
h1 = lambda th: Z_P1 + L * math.sin(math.radians(th))
lip = lambda th: h1(th) - HAND_DROP
check(lip(TH_MIN) <= FLOOR - 6, f"lowest lip {lip(TH_MIN):.1f}: reaches an empty bin floor ({FLOOR}) with >= 6 mm of slider overtravel")
swing = lip(TH_MAX) - WALL_TOP
check(swing >= SAG_MM + CARD_TILT_MM + 5, f"swing: card bottom {lip(TH_MAX):.1f}, {swing:.1f} mm over the walls vs sag {SAG_MM} + tilt {CARD_TILT_MM} + 5")
dr = L * (1 - math.cos(math.radians(max(abs(TH_MIN), TH_MAX))))
check(dr <= 3.5, f"cup radius change over the lift range {dr:.2f} mm")
step_mm = L * math.radians(STEP_DEG)
check(3 * step_mm < SLIDER_TRAVEL - 2, f"lift: 3 steps ({3*step_mm:.1f} mm) of overshoot after touch-down stay inside the {SLIDER_TRAVEL} mm slider travel")

# camera
hand_top = h1(TH_MAX) + D_LINK + HAND_TOP_ABOVE_H2 + RING_STACK
check(hand_top + 20 <= CAM_LENS_Z, f"arm top at full lift {hand_top:.0f} vs lens {CAM_LENS_Z:.0f} (>= 20 clear)")
fov_w = 2 * CAM_DIST * math.tan(math.radians(33)); fov_h = 2 * CAM_DIST * math.tan(math.radians(20.5))
check(fov_w >= CARD_L + 20 and fov_h >= CARD_W + 20, f"FOV at the bed {fov_w:.0f} x {fov_h:.0f} mm; card long side ~{2304*CARD_L/fov_w:.0f} px")
for D in (4.0, 5.0, 6.0):
    near, far = 1 / (D + 1 / 1.5), 1 / D
    print(f"  +{D:.0f} D close-up lens on a 1.5 m-inf camera focuses at {near*1000:.0f}..{far*1000:.0f} mm")
check(1 / (5 + 1 / 1.5) * 1000 - 5 <= CAM_DIST <= 1 / 5 * 1000 + 5, f"lens at {CAM_DIST:.0f} mm is in focus with a +5 D lens (boom height adjustable +/-20)")

# load cell: owned 5 kg bar (not a 50 g TAL221)
check(30 + 40 + 2 * 1.75 < 5000, "platform load (slider 30 g + bed 40 g + 2 cards) well inside the 5 kg cell")

print()
print("FAILED: " + "; ".join(fails) if fails else "ALL CHECKS PASS")
sys.exit(1 if fails else 0)
