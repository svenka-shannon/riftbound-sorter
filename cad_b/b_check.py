#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Option B geometry check: station layout, pocket clearances against a real
error stack-up, lift range, swing clearance with sag, camera clearance and
focus, load cell, yaw stage. Numbers mirror cad_b/b_params.scad (round 4: the yaw axis
is a 28BYJ-48 stepper on a 4" lazy-susan bearing).
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
HAND_TOP_ABOVE_H2 = 14.0
RING_STACK = 1.65 + 7 + 2.5 + 3        # button heads + 608 + cap + M3 head
CAM_DIST = 188.0
CAM_LENS_Z = BED_TOP + CAM_DIST
STEP_DEG = 180.0 / 410                 # lift servo: PCA9685 12-bit, 500..2500 us at 50 Hz
YAW_STEP_DEG = 360.0 / 4076            # 28BYJ-48 half-step through its 63.68:1 gearbox

# error budget (yaw), degrees and mm
YAW_REPEAT_DEG = 0.25                  # stepper, same-direction approach (gearbox backlash taken up in one
                                       # direction, held by the bearing's drag): coupling + gear compliance.
                                       # Assumed, not measured; the servo version needed 0.6 and had 0 mm margin.
YAW_SETPOINT_DEG = YAW_STEP_DEG / 2
CUP_ON_CARD_MM = 1.0                   # tangential only: the camera measures the card on the bed and the re-pick yaw is
                                       # corrected to +/- half a yaw step (radial offset can NOT be corrected: no radial axis)
SLIDER_ROT_DEG = math.degrees(0.1 / math.sqrt(6.0**2 - 3.5**2))   # D-flat play: 0.1 mm clearance at the flat corners
RADIAL_ON_BED_MM = 2.0                 # card position error on the bed (radial), carried into the bin
CARD_ROT_DEG = math.degrees(math.atan((HOP_IN_W - CARD_W) / CARD_L)) + SLIDER_ROT_DEG   # hopper slop + slider swivel
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
check(stations[-1] - stations[0] + stations[0] <= 180, f"yaw span home 0 .. {stations[-1]:.0f}: inside the half turn the cable loop allows (stepper: no travel limit of its own)")

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
per_card = yaw_err(r_c_in) + corner_rot
rss_card = math.hypot(math.hypot(r_c_in * math.radians(YAW_REPEAT_DEG + YAW_SETPOINT_DEG), CUP_ON_CARD_MM), corner_rot)
check(gap_cards >= 2 * per_card - 0.5, f"inner zone (no divider): corners {gap_cards:.1f} mm apart vs two worst-case cards {2*per_card:.1f} (RSS {2*rss_card:.1f}); margin {gap_cards-2*per_card:+.1f} -- firmware approaches every station from the same direction")
rad_room = (BIN_R_OUT - BIN_R_IN - CARD_L) / 2
check(rad_room >= RADIAL_ON_BED_MM + 3.34 / 2 + 1, f"bin radial room {rad_room:.1f} mm each end vs bed offset {RADIAL_ON_BED_MM} + lift arc 1.7 + 1")
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
check(1 / (5 + 1 / 1.5) * 1000 <= CAM_DIST <= 1 / 5 * 1000, f"lens at {CAM_DIST:.0f} mm sits inside the +5 D focus range (boom slides on the post to focus)")

# yaw stage (round 4)
DECK_Z0, DECK_TOP, TT_Z0, LS_HOLE = 34.5, 39.5, 46.4, 55.0
ST_SHAFT_L, ST_FLAT_L, ST_BOSS_H = 10.0, 6.0, 1.5
HUB_Z0, HUB_FL_D, HUB_FL_T = DECK_Z0 + ST_BOSS_H + 0.5, 32.0, 3.0
EAR_R = math.hypot(35 / 2, 8)                       # ear screws from the axis
d_engage = (DECK_Z0 + ST_SHAFT_L) - max(HUB_Z0, DECK_Z0 + ST_SHAFT_L - ST_FLAT_L)
check(d_engage >= 5, f"hub: double-D engages {d_engage:.1f} mm of the shaft's flats")
check(DECK_TOP + 3 + 0.5 <= TT_Z0 - HUB_FL_T, f"ear screw heads top {DECK_TOP+3:.1f} under the hub flange {TT_Z0-HUB_FL_T:.1f}")
check(HUB_FL_D / 2 + 3 <= LS_HOLE / 2 and HUB_FL_D / 2 < EAR_R - 2.75, f"hub flange r {HUB_FL_D/2:.0f}: inside the bearing hole r {LS_HOLE/2:.1f}, clear of the ear heads r {EAR_R-2.75:.1f}")
# torque / time: arm inertia about the yaw axis (rough masses, PETG ~40 % infill)
I = 0.055 * 0.03**2 + 0.05 * 0.22**2 / 3 + 0.06 * 0.245**2 + 0.08 * 0.04**2   # lift servo, links, hand+slider+cup+tube, turntable
T_avail = 0.5 * 0.034                                # half the 28BYJ-48's ~34 mN m pull-in torque, rest for drag + cable loop
w_max = 12 * 2 * math.pi / 60                        # 12 rpm: a safe 5 V half-step rate (~800 steps/s)
alpha = T_avail / I
t_acc = w_max / alpha
ang = math.radians(160)
t_move = 2 * t_acc + (ang - alpha * t_acc**2) / w_max if alpha * t_acc**2 < ang else 2 * math.sqrt(ang / alpha)
check(t_move <= 3.0, f"yaw: I ~{I*1e4:.0f} kg cm2, accel {math.degrees(alpha):.0f} deg/s2, 160 deg in {t_move:.1f} s at 12 rpm (20 deg hop {2*math.sqrt(math.radians(20)/alpha) if math.radians(20) < alpha*t_acc**2 else 2*t_acc + (math.radians(20)-alpha*t_acc**2)/w_max:.1f} s)")

# load cell: owned 5 kg bar (not a 50 g TAL221)
check(30 + 40 + 2 * 1.75 < 5000, "platform load (slider 30 g + bed 40 g + 2 cards) well inside the 5 kg cell")

print()
print("FAILED: " + "; ".join(fails) if fails else "ALL CHECKS PASS")
sys.exit(1 if fails else 0)
