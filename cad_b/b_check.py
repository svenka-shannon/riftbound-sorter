#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Option B geometry check: station layout, pocket clearances against a real
error stack-up, lift range, swing clearance with sag, camera clearance and
focus, load cell, yaw stage. Numbers mirror cad_b/b_params.scad (round 5: the yaw axis
is a NEMA 17 pancake stepper, direct drive, on a 4" lazy-susan bearing).
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
YAW_STEP_DEG = 1.8 / 16                # NEMA 17, TMC2209 at 1/16 microsteps, direct drive (no gearbox)

# error budget (yaw), degrees and mm
YAW_REPEAT_DEG = 0.15                  # same target from the same direction: microstep repeatability + load
                                       # deflection (10 mN m against ~170 mN m holding: ~0.03 deg) + hub set screw.
                                       # No gearbox, so no backlash term. Assumed; bench-check with a 260 mm pointer.
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
CAM_A0, CAM_A1, CAM_RAMP, SW_AZ, POST_CRASH = 262, 350, 8, 270, -90
press_lo, press_hi = SW_AZ - (CAM_A1 - CAM_RAMP), SW_AZ - (CAM_A0 + CAM_RAMP)
check(press_hi == 0 and press_lo > POST_CRASH and SW_AZ - CAM_A0 < stations[0], f"home cam holds the switch for arm {press_lo}..{press_hi} deg (ramps to {SW_AZ-CAM_A1}/{SW_AZ-CAM_A0}); released over the working range from {stations[0]}; cable post hit at ~{POST_CRASH}")

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

# yaw stage (round 5)
DECK_Z0, DECK_TOP, TT_Z0, TT_T, LS_HOLE = 34.5, 39.5, 46.4, 5.0, 55.0
NM_H, NM_SHAFT_L, NM_FLAT_L, NM_HOLE = 23.0, 24.0, 15.0, 31.0
COL_SS_Z = TT_Z0 + TT_T - 3 + 3.5
check(DECK_Z0 - NM_H >= 4, f"motor body bottom Z {DECK_Z0-NM_H:.1f}: inside the pedestal, above the board")
shaft_top = DECK_Z0 + NM_SHAFT_L
for sl in (20.0, NM_SHAFT_L):
    check(DECK_Z0 + sl >= COL_SS_Z + 2.0, f"{sl:.0f} mm shaft (top Z {DECK_Z0+sl:.1f}) reaches past the collar's set screw (Z {COL_SS_Z:.1f})")
check(shaft_top - NM_FLAT_L <= COL_SS_Z - 2, f"set screw at Z {COL_SS_Z:.1f} lands on the flat (flat from Z {shaft_top-NM_FLAT_L:.1f})")
r_head_in = NM_HOLE / math.sqrt(2) - 2.75
check(NM_HOLE / math.sqrt(2) + 2.75 <= LS_HOLE / 2, f"motor screw heads r {r_head_in:.1f}..{NM_HOLE/math.sqrt(2)+2.75:.1f}: inside the bearing hole (r {LS_HOLE/2:.1f})")
# torque / time: arm inertia about the yaw axis (rough masses, PETG ~40 % infill)
I = 0.055 * 0.03**2 + 0.066 * 0.22**2 / 3 + 0.06 * 0.245**2 + 0.15 * 0.05**2   # lift servo, links (2 x 33 g, 100 % infill), hand+slider+cup+tube, turntable+cam sector
T_hold = 0.17                                        # 17 N cm holding (pancake, 1 A)
T_avail = 0.25 * T_hold                              # at 30 rpm on 12 V a pancake keeps well over half; use a quarter
alpha_cmd = math.radians(300)                        # commanded accel/decel: gentle on the 220 mm links
w_max = math.radians(120)                            # 120 deg/s (20 rpm)
T_need = I * alpha_cmd + 0.003 + 0.004               # + bearing drag + cable loop
check(T_need <= T_avail, f"yaw torque: need {T_need*1000:.0f} mN m (I ~{I*1e4:.0f} kg cm2 at {math.degrees(alpha_cmd):.0f} deg/s2 + drag + cable) vs ~{T_avail*1000:.0f} available")
def move_t(deg):
    ang = math.radians(deg); t_acc = w_max / alpha_cmd
    return 2 * t_acc + (ang - alpha_cmd * t_acc**2) / w_max if alpha_cmd * t_acc**2 < ang else 2 * math.sqrt(ang / alpha_cmd)
check(move_t(160) <= 2.0, f"yaw: 160 deg in {move_t(160):.1f} s, 20 deg hop {move_t(20):.2f} s")
stiff_defl = math.degrees(math.asin(0.010 / (0.5 * T_hold))) * (7.2 / 360)   # 10 mN m disturbance at the TMC2209's default 50 % standstill current
check(stiff_defl <= YAW_REPEAT_DEG, f"yaw stiffness: a 10 mN m disturbance (tilted board, cable) moves the arm {stiff_defl:.3f} deg")

# load cell: owned 5 kg bar (not a 50 g TAL221)
check(30 + 40 + 2 * 1.75 < 5000, "platform load (slider 30 g + bed 40 g + 2 cards) well inside the 5 kg cell")

print()
print("FAILED: " + "; ".join(fails) if fails else "ALL CHECKS PASS")
sys.exit(1 if fails else 0)
