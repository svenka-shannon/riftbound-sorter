#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Option B geometry check: station layout, bin spacing, arm reach and heights.

Numbers here mirror cad_b/b_params.scad. Run:  cad_b/b_check.py
Exits non-zero if any check fails.
"""
import math, sys

# ---- shared parameters (keep in sync with b_params.scad) ----
R = 260.0            # cup-centre radius at every station
S0, PITCH, N = 10.0, 20.0, 9   # servo angles of the stations: 10..170
CARD_W, CARD_L = 63.0, 88.0
BIN_IN_W, BIN_IN_L, WALL = 69.0, 94.0, 2.4
FLOOR = 2.0
BIN_WALL_TOP = FLOOR + 32.0        # 80 cards * 0.33 = 26.4 + margin
SWING_CLEAR = 6.0                  # card bottom above the highest wall when swinging
PLATFORM_BED = 26.0                # scan/weigh bed top
L = 220.0            # parallelogram link length (pivot to pivot)
R_P1 = 25.0          # lift pivot radius from the yaw axis
H_OFF = 15.0         # hand: link pivot to cup axis, radial
D_LINK = 40.0        # vertical spacing of the two parallelogram pivots
HAND_DROP = 47.0     # lower hand pivot H1 -> cup lip (slider resting)
SLIDER_TRAVEL = 10.0
OVERTRAVEL = 8.0     # max planned slider lift after touch-down
CAM_Z = PLATFORM_BED + 150.0       # lens height above the board
HAND_TOP_ABOVE_H2 = 6.0
SERVO_DEG_PER_STEP = 180.0 / 410   # PCA9685 12-bit, 500..2500 us at 50 Hz

fails = []
def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok: fails.append(msg)

stations = [S0 + i * PITCH for i in range(N)]
names = ["hopper", "scan/weigh"] + [f"bin {i}" for i in range(1, 7)] + ["reject"]
print("stations (servo angle -> role):")
for s, n in zip(stations, names):
    print(f"  {s:5.1f} deg  {n}")
check(stations[0] >= 5 and stations[-1] <= 175, f"yaw span {stations[0]}..{stations[-1]} needs +/-{(stations[-1]-stations[0])/2:.0f} deg of servo travel (MG996R: test first)")

# Hopper: tight rectangular pocket (card centred +/-3 mm for the pick).
# Bins: fan-shaped (wedge) pockets that share the 20 deg pitch, with 1.2 mm
# half-walls on each radial side, so the tangential room grows outward.
HOP_IN_W, HOP_IN_L = 67.0, 92.0   # 2 mm room each side: keeps the stack centred under the cup
hop_outer_w = HOP_IN_W + 2 * WALL
r_hop_in = R - HOP_IN_L / 2 - WALL
chord = 2 * r_hop_in * math.sin(math.radians(PITCH / 2))
check(chord >= hop_outer_w + 1.0, f"hopper pocket fits its 20 deg slot: chord {chord:.1f} vs width {hop_outer_w:.1f} (+1)")
HALF_WALL = 1.2
r_card_in, r_card_out = R - CARD_L / 2, R + CARD_L / 2
def wedge_clear(r):  # free room each side of a centred card, at radius r
    return (2 * r * math.sin(math.radians(PITCH / 2)) - 2 * HALF_WALL - CARD_W) / 2
c_in, c_out = wedge_clear(r_card_in), wedge_clear(r_card_out)
print(f"  bin wedge: tangential room per side {c_in:.1f} mm at the card inner edge, {c_out:.1f} at the outer edge")
mm_per_deg = R * math.radians(1)
print(f"  1 deg of yaw = {mm_per_deg:.1f} mm at the cup centre, {r_card_in*math.radians(1):.1f} at the card inner edge; 1 PCA9685 step = {mm_per_deg*SERVO_DEG_PER_STEP:.1f} mm")
check(r_card_in * math.radians(1.0) <= c_in, "a 1 deg yaw error still lowers the card into a bin wedge without touching a wall")
check(R * math.radians(1.0) + 27 / 2 <= CARD_W / 2, "hopper: a 1 deg yaw error keeps the 27 mm cup on the card")

# footprint (rectangle approximation of every pocket)
pts = []
for s in stations:
    a = math.radians(s)
    for dr in (-(BIN_IN_L/2+WALL), BIN_IN_L/2+WALL):
        for dt in (-(hop_outer_w/2), hop_outer_w/2):
            r = R + dr
            pts.append((r*math.cos(a) - dt*math.sin(a), r*math.sin(a) + dt*math.cos(a)))
xs, ys = [p[0] for p in pts], [p[1] for p in pts]
print(f"  pockets span X {min(xs):.0f}..{max(xs):.0f}, Y {min(ys):.0f}..{max(ys):.0f} (yaw axis at 0,0)")

# heights: card bottom = cup lip (card hangs flat under the cup)
lip_min = FLOOR - OVERTRAVEL                   # empty bin, slider fully lifted by the overtravel
lip_max = BIN_WALL_TOP + SWING_CLEAR
h1_min, h1_max = lip_min + HAND_DROP, lip_max + HAND_DROP
z_p1 = (h1_min + h1_max) / 2
th = math.degrees(math.asin((h1_max - z_p1) / L))
print(f"  P1 (lift servo spline) at Z {z_p1:.1f}; links swing +/-{th:.2f} deg; H1 Z {h1_min:.0f}..{h1_max:.0f}")
dr = L * (1 - math.cos(math.radians(th)))
check(dr <= 2.0, f"cup radius change over the lift range {dr:.2f} mm (<= 2)")
step_mm = L * math.radians(SERVO_DEG_PER_STEP)
check(step_mm < SLIDER_TRAVEL - OVERTRAVEL + 2, f"lift resolution {step_mm:.2f} mm per PCA9685 step")
check(step_mm * 3 < OVERTRAVEL, f"3 steps + deadband ({step_mm*3:.1f} mm) fit inside the {OVERTRAVEL} mm overtravel")
hand_top_max = h1_max + D_LINK + HAND_TOP_ABOVE_H2
check(hand_top_max + 25 <= CAM_Z, f"hand top max Z {hand_top_max:.0f} vs camera lens Z {CAM_Z:.0f} (>= 25 clear)")

# camera field of view at the platform (IMX708 standard lens 66 x 41 deg)
dist = CAM_Z - PLATFORM_BED
fov_w = 2 * dist * math.tan(math.radians(33)); fov_h = 2 * dist * math.tan(math.radians(20.5))
check(fov_w >= CARD_L + 20 and fov_h >= CARD_W + 20, f"FOV at the bed {fov_w:.0f} x {fov_h:.0f} mm covers the card + 10 mm each side")
print(f"  card across the frame: {2304*CARD_L/fov_w:.0f} px long side in the 2304 x 1296 mode")

# load cell: worst-case force on the platform = slider weight + card (slider never bottoms out there)
# owned cell is a 5 kg bar (75 x 12.7 x 12.7, M4), not a 50 g TAL221: no overload risk.
# HX711 noise on a 5 kg / 1 mV/V bridge is ~50 mg rms: 1 card (1.75 g) vs 2 (3.5 g) is easy with averaging.
slider_g, bed_g, card_g = 12.0, 40.0, 1.75
check(slider_g + bed_g + 2 * card_g <= 5000, "platform load well inside the 5 kg cell")

print()
print("FAILED: " + "; ".join(fails) if fails else "ALL CHECKS PASS")
sys.exit(1 if fails else 0)
