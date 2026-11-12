#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "trimesh", "manifold3d", "python-fcl", "scipy", "pymunk", "rtree"]
# ///
"""Validate the cradle-shuttle sorter (cad/shuttle*.scad, lower_ramp, reject_bin, riser).

  collide  — STRICT trimesh/FCL collision + clearance sweep. EVERY part of the
             shuttle (printed parts AND the modelled hardware: LM8UU, 688ZZ,
             rod, REX shaft, F pins, pin A, dowels, cheek / cell / pivot / rod
             set screws, every ch1/ch2 screw, insert, servo, horn and coupler)
             is tested against EVERY other part, including parts of the same
             rigid group (sled ↔ cheeks, crank ↔ pivot screw, TF ↔ pins …), and
             against the tray, rails, riser, motor mounts, card guides, rollers
             and electronics tray, through every target (4 columns + reject +
             home) × every tilt state (incl. intermediate angles) and the whole
             Y travel in HOLD. Touching or overlapping fails unless the pair is
             on WHITELIST (reason + overlap-volume cap). Design rules: cradle↔TF
             > 0.5 (weighing gap), TF↔carriage ≥ 0.6, ch1 crank↔carriage ≥ 0.6
             (running clearance in the sled pocket), crank↔LM8UU ≥ 0.6, link↔TF
             ≥ 0.4, ch2 crank↔link and link↔carriage ≥ 0.8, pivot screw / nylock
             ≥ 0.5, sled wall crank pocket ↔ LM8UU pocket ≥ 1.2, everything of
             ch2 ≥ 3 mm above the tiles.
  assembly — insertion / access paths: ch1 crank↔link pivot (screw length past
             the nylock, key + nut driver on the bench), crank + link slid into
             the sled pocket and turned through its range, the REX shaft through
             posts, sled and crank bore, pin A dowel path, ch2 pivot screws from
             above, riser front-tie screws from the front, end-post holes on the
             30 mm baseplate grid (probe).
  slide    — 2-D rigid-card simulation (penalty contacts, Coulomb friction):
             the cradle tips from HOLD to UPPER/LOWER over the firmware ramp
             time and the card slides off; reports where it comes to rest.

Constants are read from shuttle_geom.scad via an OpenSCAD echo, so this file
never drifts from the CAD.

    cad/shuttle_check.py collide
    cad/shuttle_check.py slide
    cad/shuttle_check.py assembly
    cad/shuttle_check.py all          (default)
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import trimesh

CAD = Path(__file__).resolve().parent
OPENSCAD = os.environ.get("OPENSCAD", "openscad")
WORK = Path(tempfile.gettempdir()) / "shuttle_check"
WORK.mkdir(exist_ok=True)


# ---------------------------------------------------------------- constants
def read_geom():
    names = ["sg_F()", "sg_S0()", "sg_SJ()", "sg_th_hold()", "sg_th_upper()", "sg_dl_lower()",
             "sg_D()", "sg_A()", "sg_crank_r()", "sg_link_l()", "sg_c2_pivot()", "sg_c2_r()",
             "sg_c2_l()", "sg_c2_pin_dy()", "sg_col_y()", "sg_reject_y()", "sg_tray_x0()",
             "sg_lip()", "sg_bed_z()", "sg_bed_x0()", "sg_bend_x()", "sg_kick_a()", "sg_kick_l()",
             "sg_ramp_profile()", "sg_card_z()", "sg_bed_t()", "sg_c2_link_z()", "sg_c2_z()",
             "sg_c2_arm_z()", "sg_c2_sh()", "sg_c2_roof_z()", "sg_base_top()"]
    src = f"use <{CAD}/shuttle_geom.scad>\n" + "".join(
        f'echo(str("SG|{n}|", {n}));\n' for n in names) + "cube(1);\n"
    f = WORK / "geom_echo.scad"
    f.write_text(src)
    out = subprocess.run([OPENSCAD, "-o", str(WORK / "geom_echo.stl"), str(f)],
                         capture_output=True, text=True).stderr
    g = {}
    for m in re.finditer(r'ECHO: "SG\|(\w+)\(\)\|(.*)"', out):
        g[m.group(1)] = json.loads(m.group(2))
    return g


G = read_geom()
F = np.array(G["sg_F"], float); S0 = np.array(G["sg_S0"], float); SJ = np.array(G["sg_SJ"], float)
TH_H, TH_U, DL = G["sg_th_hold"], G["sg_th_upper"], G["sg_dl_lower"]
D = np.array(G["sg_D"], float); A = np.array(G["sg_A"], float)
CR, LL = G["sg_crank_r"], G["sg_link_l"]
C2P = np.array(G["sg_c2_pivot"], float); C2R, C2L, C2DY = G["sg_c2_r"], G["sg_c2_l"], G["sg_c2_pin_dy"]
TARGETS = {"home": 0.0, **{str(i): float(y) for i, y in enumerate(G["sg_col_y"])}, "reject": float(G["sg_reject_y"])}
XT = G["sg_tray_x0"]


def rot2(p, c, a):  # front-down rotation (= OpenSCAD rotate([0,a,0])) in XZ
    a = math.radians(a); x, z = p[0] - c[0], p[1] - c[1]
    return np.array([c[0] + x * math.cos(a) + z * math.sin(a), c[1] - x * math.sin(a) + z * math.cos(a)])


def ry(a, c):        # 4x4: rotate about the Y axis through (c[0], *, c[1]) by a (OpenSCAD sense)
    a = math.radians(a); ca, sa = math.cos(a), math.sin(a)
    T = np.eye(4); T[0, 3], T[2, 3] = -c[0], -c[1]
    R = np.array([[ca, 0, sa, 0], [0, 1, 0, 0], [-sa, 0, ca, 0], [0, 0, 0, 1]])
    B = np.eye(4); B[0, 3], B[2, 3] = c[0], c[1]
    return B @ R @ T


def tf_matrix(mode, a):
    """mode 'F': about F by a (level=0, hold=TH_H, upper=TH_U); mode 'S': hold then about SJ by a."""
    if mode == "F":
        return ry(a, F)
    return ry(a, SJ) @ ry(TH_H, F)


def pose_pt(p, mode, a):
    if mode == "F":
        return rot2(p, F, a)
    return rot2(rot2(p, F, TH_H), SJ, a)


def crank_phi(mode, a):
    Ap = pose_pt(A, mode, a); v = Ap - D; d = np.linalg.norm(v)
    g = math.acos((CR * CR + d * d - LL * LL) / (2 * CR * d))
    return math.degrees(math.atan2(v[1], v[0]) - g)


def c2_psi(yc):
    y = yc + C2DY - C2P[1]
    cs = (y * y + C2R * C2R - C2L * C2L) / (2 * C2R * y)
    return math.degrees(math.acos(max(-1, min(1, cs))))


def trans(x=0, y=0, z=0):
    T = np.eye(4); T[:3, 3] = [x, y, z]; return T


def rz(a):
    a = math.radians(a); T = np.eye(4)
    T[0, 0], T[0, 1], T[1, 0], T[1, 1] = math.cos(a), -math.sin(a), math.sin(a), math.cos(a)
    return T


# ---------------------------------------------------------------- meshes
SCENE_OBJS = {
    # moving, exported un-posed (level frame, carriage at Y 0)
    "carriage": "carriage();",                 # assembled sled + cheeks (assembly mode only)
    "sled": "sled();", "cheek_neg": "cheek(-1);", "cheek_pos": "cheek(1);",
    "lm8uu": "sh_lm8uu();",                    # carriage frame
    "cheek_screws": "sh_cheek_screws();",      # carriage frame
    "cheek_dowels": "sh_cheek_dowels();",      # carriage frame
    "cell_screws": "sh_cell_screws();",        # TF frame
    "cradle": "cradle();",
    "tf": "tilt_frame();",
    "fpins": "f_pins();",
    "pin_a": "pin_a();",
    "cell": "load_cell();",
    "card": "card_on_bed();",
    "tilt_crank": "tilt_crank();",
    "tilt_link": "tilt_link();",
    "tilt_pivot": "tilt_pivot_hw();",           # crank frame: M3 × 16 SHCS + nylock (crank ↔ link)
    "c2_crank": "c2_crank();",
    "c2_link": "c2_link();",
    "c2_horn_screws": "c2_horn_screws();",     # crank frame
    "c2_tip_pin": "c2_tip_pin();",             # crank frame (axisymmetric; turns with the link)
    "c2_drive_pin": "c2_drive_pin();",         # carriage frame
    # fixed
    "rbar": "rbar_neg(); rbar_pos();",
    "end_posts": "end_post_neg(); end_post_pos();",
    "rod": "rod8(sg_rod(), sh_rod_y()[0], sh_rod_y()[1]);",
    "rex_shaft": "rex_shaft();",                           # 8 mm REX shaft, Y −175.2..241.8
    "bearings_688": "sh_688zz();",
    "rod_grubs": "sh_rod_grub_screws();",
    "servo_ch1": "c1_servo();",
    "ch1_coupler": "c1_coupler(swept = true);",            # goBILDA 4001-0025-4008, boss swept over its range
    "c1_ear_screws": "c1_ear_screws();",
    "servo_ch2": "c2_servo();",
    "c2_horn": "c2_horn();",
    "c2_ear_screws": "c2_ear_screws();",
    "lower_ramp": "ramp_neg(); ramp_pos();",
    "reject_bin": "reject_bin();",
    "riser": "riser_a(); riser_b();",
    "tray": "translate([sg_tray_x0() + sorting_tray_depth(), -sorting_tray_width() / 2, 4]) rotate([0, 0, 90]) full_2floor_assembly();",
    "rails": "for (side = [-1, 1]) translate([-165, side * 45, 64]) mirror([0, side < 0 ? 1 : 0, 0]) { rail_half(add_shaft_far = false, motor_mount = (side < 0)); translate([125, 0, 0]) rail_half(add_shaft_far = true, motor_mount = (side < 0)); }",
    "motor_mounts": "for (x = [-140, 60]) translate([x, -45, 64]) mirror([0, 1, 0]) translate([0, rail_boss_face_y(), 0]) { motor_mount(); motor_mount_n20(); motor_mount_coupling(); }",
    "rollers": "for (x = [-140, 60]) translate([x, -roller_width() / 2, 79]) rotate([-90, 0, 0]) roller();",
    "card_guides": "card_guides();",
    "etray": "translate([-150, 80, 4]) electronics_tray();",
}
USES = ["shuttle_geom", "shuttle", "lower_ramp", "reject_bin", "riser", "sorting_tray", "conveyor_rail",
        "motor_mount", "conveyor_roller", "card_guide", "electronics_tray"]


# cut volumes (not parts) for the wall-thickness rules in collide
WALL_OBJS = {"crank_pocket": "sled_crank_pocket();", "lm8uu_pockets": "sled_lm8uu_pockets();"}
# minimum material between two cuts of the same print: (cut, cut) → (min mm, why)
WALL_RULES = {("crank_pocket", "lm8uu_pockets"): (1.2, "sled wall between the crank pocket and the +Y LM8UU pocket")}
# extra objects for the assembly-order mode (exported on demand)
ASM_OBJS = {
    "c1_coupler_up": "c1_coupler(90);",                    # boss up: how it passes the cage opening
    "end_post_neg": "end_post_neg();",
    "c2_ear_screws_rear": "c2_ear_screws_at(sg_c2_ear_y()[1]);",
    "c2_ear_screws_front": "c2_ear_screws_at(sg_c2_ear_y()[0]);",
    "ramp_neg": "ramp_neg();", "ramp_pos": "ramp_pos();",
    # coupler (not swept) at HOLD for each of the three hex indexings (−30 / 0 / +30°)
    **{f"c1_coupler_hold{k:+d}": f'c1_coupler(sg_crank_phi("hold") + {k});' for k in (-30, 0, 30)},
}


def export(name):
    stl = WORK / f"{name}.stl"
    scad = WORK / f"{name}.scad"
    src = "".join(f"use <{CAD}/{u}.scad>\n" for u in USES)
    src += "module cyl_y(p, d, y0, y1, fn = 40) translate([p[0], y0, p[1]]) rotate([-90, 0, 0]) cylinder(d = d, h = y1 - y0, $fn = fn);\n"
    src += {**SCENE_OBJS, **ASM_OBJS, **WALL_OBJS}[name] + "\n"
    # cache key: wrapper source + modification times of every CAD file it can reach
    src += "// " + " ".join(f"{p.name}:{p.stat().st_mtime_ns}" for p in sorted(CAD.glob("*.scad"))) + "\n"
    if (not stl.exists()) or (not scad.exists()) or scad.read_text() != src:
        scad.write_text(src)
        for _ in range(2):            # one retry: openscad occasionally exits non-zero with no message
            r = subprocess.run([OPENSCAD, "--backend=manifold", "--export-format", "binstl", "-o", str(stl), str(scad)],
                               capture_output=True, text=True)
            if r.returncode == 0 and stl.exists():
                break
        if r.returncode != 0 or not stl.exists():
            stl.unlink(missing_ok=True); scad.unlink(missing_ok=True)
            sys.exit(f"openscad failed for {name}:\n{r.stderr}")
    return trimesh.load(stl, force="mesh")


def load_all():
    return {n: export(n) for n in SCENE_OBJS}


# ---------------------------------------------------------------- collide
# EVERY part of the shuttle is tested against EVERY other part (and against the
# conveyor / tray parts around it) in every pose, including parts of the same rigid
# subassembly (sled ↔ cheeks, crank ↔ pivot screw, TF ↔ pins, …). Each part lives in
# one FRAME; parts in the same frame never move relative to each other and are tested
# once, every other pair in every pose. Touching or overlapping is a FAILURE unless the
# pair is on WHITELIST (below), with the reason and a cap on the overlap volume.
FRAMES = {
    # frame: parts (OWN = shuttle parts; ENV = neighbours, only tested against OWN parts)
    "fixed":    ["rbar", "end_posts", "rod", "bearings_688", "rod_grubs", "servo_ch1", "ch1_coupler", "c1_ear_screws",
                 "servo_ch2", "c2_horn", "c2_ear_screws", "lower_ramp", "reject_bin", "riser",
                 "tray", "rails", "motor_mounts", "rollers", "card_guides", "etray"],
    "carriage": ["sled", "cheek_neg", "cheek_pos", "lm8uu", "cheek_screws", "cheek_dowels", "c2_drive_pin"],
    "crank":    ["tilt_crank", "tilt_pivot"],          # carriage Y + crank angle φ about D
    "shaft":    ["rex_shaft"],                         # turns with the crank (φ about D), does not slide
    "link":     ["tilt_link"],
    "tf":       ["tf", "cradle", "cell", "card", "fpins", "pin_a", "cell_screws"],
    "c2crank":  ["c2_crank", "c2_horn_screws", "c2_tip_pin"],
    "c2link":   ["c2_link"],
}
ENV = {"tray", "rails", "motor_mounts", "rollers", "card_guides", "etray"}
FRAME_OF = {p: f for f, ps in FRAMES.items() for p in ps}
COLLIDE_PARTS = list(FRAME_OF)
CARRIAGE = ["sled", "cheek_neg", "cheek_pos"]
TF_GROUP = ["cradle", "tf", "cell", "card", "fpins", "pin_a"]          # (assembly mode)
C2_HW = ["c2_horn_screws", "c2_tip_pin", "c2_drive_pin"]
FIXED = FRAMES["fixed"] + ["rex_shaft"]          # assembly mode: everything that stays put
OWN = [p for p in COLLIDE_PARTS if p not in ENV]

# WHITELIST: the ONLY pairs that may touch or overlap, each with the largest overlap
# volume (mm³) allowed in any pose and why. Caps are the modelled interference (press
# fits, threads in pilots, bores not modelled in bought parts) plus a small margin;
# anything larger — or any pair not listed — fails.
WHITELIST = {frozenset(k): v for k, v in {
    # -- carriage --
    ("lm8uu", "rod"):            (2.0,  "rod in the LM8UU bore (line-to-line, 24-gon rod)"),
    ("cheek_dowels", "sled"):    (14.0, "Ø3 dowels pressed 6 deep into the sled's Ø2.9 holes"),
    ("sled", "cheek_neg"):       (0.5, "cheek root bolted flat against the sled side face"),
    ("sled", "cheek_pos"):       (0.5, "cheek root bolted flat against the sled side face"),
    ("c2_drive_pin", "sled"):    (0.5, "ch2 drive-pin shoulder screw head seated on the sled's arm"),
    ("c2_drive_pin", "c2_link"): (2.0, "drive-pin M3 × 4 insert pressed into the link's Ø4.0 hole"),
    # -- ch1 tilt drive --
    ("tilt_pivot", "tilt_crank"): (0.5, "M3 × 16 head on the crank face, shank in the Ø3.2 hole"),
    ("tilt_pivot", "tilt_link"):  (0.5, "nylock on the link face, shank in the Ø3.2 hole"),
    ("pin_a", "tf"):             (7.0, "pin A pressed into the TF's Ø2.9 bores, ≈ 14.5 mm engaged (ream Ø2.95)"),
    ("rex_shaft", "bearings_688"): (2.0, "REX round lands in the 688ZZ bores (line-to-line)"),
    ("rex_shaft", "ch1_coupler"): (500.0, "shaft end 9 mm in the coupler's REX bore (bore not modelled: π·4²·9 ≈ 452)"),
    ("ch1_coupler", "servo_ch1"): (120.0, "coupler on the MG996R spline (spline bore not modelled)"),
    ("c1_ear_screws", "servo_ch1"): (75.0, "4 × M3 through the servo ears (ear holes not modelled: 4·π·1.5²·2.5 ≈ 71), washers on the ears"),
    ("servo_ch1", "end_posts"):  (1.0, "ch1 ears seated on the cage's −Y face"),
    ("bearings_688", "end_posts"): (0.5, "688ZZ seated on its pocket shoulder"),
    # -- tilt frame / load cell / cradle --
    ("fpins", "tf"):             (6.0, "F pins pressed into the TF's Ø3.9 bores (ream Ø3.9)"),
    ("cell", "tf"):              (0.5, "cell's tapped end clamped on the TF pad"),
    ("cell", "cradle"):          (0.5, "cradle boss clamped on the cell's free end"),
    ("cell_screws", "cell"):     (12.0, "M3 screws in the cell's threaded holes (modelled Ø3, 12-gon)"),
    ("cell_screws", "tf"):       (0.5, "M3 × 12 heads seated in the TF counterbores"),
    ("tf", "rbar"):              (1.0, "rear skid resting on the R-bar (LOWER) / home ledge (LEVEL)"),
    # -- fixed --
    ("rod_grubs", "rod"):        (0.5, "set-screw tips on the rod"),
    ("tray", "lower_ramp"):      (0.5, "ramp hooked into the tray (face contact; hook fit checked in lower_ramp.scad)"),
    ("riser", "etray"):          (1.0, "riser foot beside the electronics tray"),
    ("rails", "riser"):          (0.5, "rails bolted onto the riser (face contact)"),
    ("motor_mounts", "riser"):   (0.5, "motor mounts bolted onto the riser (face contact)"),
    # -- ch2 --
    ("c2_crank", "c2_horn"):     (1.0, "horn disc against the crank top"),
    ("c2_horn", "servo_ch2"):    (120.0, "25T spline inside the horn hub (horn bore not modelled)"),
    ("c2_horn_screws", "c2_crank"): (3.0, "horn screws in the crank's countersunk holes"),
    ("c2_horn_screws", "c2_horn"):  (80.0, "4 × M2 self-tappers + centre M3 through the horn (no holes modelled)"),
    ("c2_horn_screws", "servo_ch2"): (45.0, "centre M3 × 12 threaded 4.9 into the spline"),
    ("c2_tip_pin", "c2_crank"):  (0.5, "tip shoulder screw head seated on the crank top"),
    ("c2_tip_pin", "c2_link"):   (2.0, "tip M3 × 4 insert pressed into the link's Ø4.0 hole"),
    ("c2_ear_screws", "servo_ch2"): (60.0, "ear screws through the servo ears (ear holes not modelled)"),
    ("c2_ear_screws", "riser"):  (18.0, "2 × M2.5 self-threading ≈ 5 deep into riser_b's Ø2.1 pilots"),
    ("c2_ear_screws", "end_posts"): (20.0, "2 × M2.5 self-threading 5.6 deep into the end-post shelf + boss Ø2.1 pilots (2·π·(1.25²−1.05²)·5.6 ≈ 16)"),
}.items()}
# design-rule minimum clearances; "carriage" = sled + both cheeks
RULES = {("cradle", "tf"): (0.5, "weighing gap: cradle must never touch the tilt frame"),
         ("tf", "carriage"): (0.6, "TF body ↔ carriage"),
         ("tilt_crank", "carriage"): (0.6, "ch1 crank (hub + arm) running clearance in the sled pocket"),
         ("tilt_crank", "lm8uu"): (0.6, "ch1 crank ↔ +Y LM8UU"),
         ("tilt_crank", "rex_shaft"): (0.05, "REX bore fit (+0.15 on the hex and round)"),
         ("tilt_link", "carriage"): (0.6, "ch1 link ↔ carriage"),
         ("tilt_link", "tf"): (0.4, "ch1 link in the TF slot"),
         ("rex_shaft", "carriage"): (0.1, "shaft in the sled bushings / cheek holes"),
         ("c2_crank", "c2_link"): (0.8, "ch2 crank over link (horn screws flush)"),
         ("c2_link", "carriage"): (0.8, "ch2 link under the drive-pin arm"),
         ("c2_horn_screws", "c2_link"): (0.8, "horn screw heads over the link at column 0"),
         ("tilt_pivot", "carriage"): (0.5, "ch1 crank-link M3 × 16 head / nylock ↔ sled + cheeks"),
         ("tilt_pivot", "tf"): (0.5, "ch1 crank-link M3 × 16 head / nylock ↔ tilt frame"),
         ("tilt_pivot", "cell"): (0.5, "ch1 crank-link nylock ↔ load cell (weighing path)"),
         ("ch1_coupler", "end_posts"): (1.0, "ch1 coupler (swept) ↔ end post / cage / ch2 gusset"),
         ("rex_shaft", "servo_ch1"): (1.0, "shaft end ↔ ch1 spline (shaft bottoms in the coupler, not on the servo)")}
ALIAS = {"carriage": CARRIAGE}
TILE_LIP = 3.0     # everything of the ch2 linkage stays ≥ 3 mm above the tiles (seam lips)
BASE = np.array([[-285.0, -270.0, 4.0], [285.0, 270.0, 1e9]])   # baseplate top / extents
REPORT = 3.0       # print every pair that comes closer than this


def overlap_volume(a, b):
    try:
        v = a.intersection(b, engine="manifold").volume
    except Exception:
        v = float("nan")
    return v


def frame_transforms(yc, mode, a):
    """4×4 transform of every frame at carriage Y yc and tilt pose (mode, a)."""
    T_y = trans(y=yc)
    phi = crank_phi(mode, a)
    tip = D + CR * np.array([math.cos(math.radians(phi)), math.sin(math.radians(phi))])
    Ap = pose_pt(A, mode, a)
    lang = math.degrees(math.atan2(Ap[1] - tip[1], Ap[0] - tip[0]))
    psi = c2_psi(yc)
    c2tip = np.array([C2P[0] - C2R * math.sin(math.radians(psi)), C2P[1] + C2R * math.cos(math.radians(psi))])
    pin = np.array([C2P[0], yc + C2DY])
    return {"fixed": np.eye(4), "carriage": T_y, "crank": T_y @ ry(-phi, D), "shaft": ry(-phi, D),
            "link": T_y @ trans(tip[0], 0, tip[1]) @ ry(-lang, (0, 0)), "tf": T_y @ tf_matrix(mode, a),
            "c2crank": trans(C2P[0], C2P[1]) @ rz(psi),
            "c2link": trans(c2tip[0], c2tip[1]) @ rz(math.degrees(math.atan2(pin[1] - c2tip[1], pin[0] - c2tip[0])) - 90)}


def collide_poses():
    cases = []
    for tgt, yc in TARGETS.items():
        if tgt == "home":
            for a in np.linspace(0, TH_H, 4):
                cases.append((tgt, yc, "F", float(a), "level" if a == 0 else ("hold" if a == TH_H else "level→hold")))
            continue
        for a in np.linspace(TH_H, TH_U, 6):
            cases.append((tgt, yc, "F", float(a), "hold" if a == TH_H else ("upper" if a == TH_U else "hold→upper")))
        for a in np.linspace(0, DL, 7)[1:]:
            cases.append((tgt, yc, "S", float(a), "lower" if a == DL else "hold→lower"))
    for yc in np.arange(min(TARGETS.values()), max(TARGETS.values()) + 0.1, 6.0):   # Y travel in HOLD
        cases.append(("travel", float(yc), "F", TH_H, "hold"))
    return cases


def _box(m, T):
    """World AABB of mesh m under transform T (from its 8 local corners)."""
    lo, hi = m.bounds
    c = np.array([[x, y, z, 1.0] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]) @ T.T
    return c[:, :3].min(0), c[:, :3].max(0)


def run_collide(meshes, verbose=False):
    import fcl  # noqa: F401  (trimesh uses it)
    mgr = {}
    for n in COLLIDE_PARTS:                      # one BVH per part, moved with set_transform
        mgr[n] = trimesh.collision.CollisionManager(); mgr[n].add_object(n, meshes[n])
    pairs = [(a, b) for i, a in enumerate(COLLIDE_PARTS) for b in COLLIDE_PARTS[i + 1:]
             if not (a in ENV and b in ENV)]
    static = [p for p in pairs if FRAME_OF[p[0]] == FRAME_OF[p[1]]]
    dynamic = [p for p in pairs if FRAME_OF[p[0]] != FRAME_OF[p[1]]]
    worst = {}       # pair → (min clearance (neg = −overlap mm³), max overlap mm³, case label)
    fails = []

    ruled = {frozenset((x, y)) for n1, n2 in RULES for x in ALIAS.get(n1, [n1]) for y in ALIAS.get(n2, [n2])}

    def test(a, b, Ta, Tb, label):
        ba, bb = _box(meshes[a], Ta), _box(meshes[b], Tb)
        if frozenset((a, b)) not in ruled and (np.any(ba[0] > bb[1] + REPORT) or np.any(bb[0] > ba[1] + REPORT)):
            return
        mgr[a].set_transform(a, Ta); mgr[b].set_transform(b, Tb)
        d = mgr[a].min_distance_other(mgr[b])
        vol = 0.0
        if d <= 1e-6:
            vol = overlap_volume(meshes[a].copy().apply_transform(Ta), meshes[b].copy().apply_transform(Tb))
            vol = float("inf") if math.isnan(vol) else max(vol, 0.0)
            d = 0.0
        key = frozenset((a, b))
        w = worst.get(key)
        if w is None:
            worst[key] = [d if vol == 0 else -vol, vol, label, (a, b)]
        else:
            if (d if vol == 0 else -vol) < w[0]:
                w[0], w[2] = (d if vol == 0 else -vol), label
            w[1] = max(w[1], vol)

    for a, b in static:                          # same frame: once, in model coordinates
        test(a, b, np.eye(4), np.eye(4), "any pose (same rigid part group)")
    cases = collide_poses()
    env = {}
    for tgt, yc, mode, a, label in cases:
        T = frame_transforms(yc, mode, a)
        for n in OWN:
            lo, hi = _box(meshes[n], T[FRAME_OF[n]])
            env[n] = (lo, hi) if n not in env else (np.minimum(env[n][0], lo), np.maximum(env[n][1], hi))
        for p, q in dynamic:
            test(p, q, T[FRAME_OF[p]], T[FRAME_OF[q]], f"{tgt}/{label} {a:.1f}°")

    print(f"\nCOLLISION SWEEP (strict): {len(COLLIDE_PARTS)} parts in {len(FRAMES)} rigid groups, "
          f"{len(static)} same-group pairs once + {len(dynamic)} pairs × {len(cases)} poses "
          f"({len(TARGETS) - 1} targets × hold/upper/lower incl. intermediate angles, home level→hold, "
          f"Y travel every 6 mm in HOLD)")
    print(f"Every pair closer than {REPORT} mm (clearance mm; touching/overlap shown as −mm³):")
    print(f"  {'part':14s} {'vs':14s} {'min':>9s}  {'max ovl':>8s}  verdict / worst case")
    for key, (d, vol, label, (a, b)) in sorted(worst.items(), key=lambda kv: kv[1][0]):
        if d >= REPORT:
            continue
        wl = WHITELIST.get(key)
        if d > 0:
            verdict = ""
        elif wl is None:
            verdict = "FAIL: touches/overlaps, not whitelisted"
        elif vol > wl[0]:
            verdict = f"FAIL: {vol:.2f} mm³ > cap {wl[0]:g} ({wl[1]})"
        else:
            verdict = f"whitelisted ≤ {wl[0]:g} mm³ ({wl[1]})"
        if verdict.startswith("FAIL"):
            fails.append((a, b, label, verdict))
        print(f"  {a:14s} {b:14s} {d:9.2f}  {vol:8.2f}  {verdict}   [{label}]")
    unused = [tuple(sorted(k)) for k in WHITELIST
              if k not in worst or worst[k][0] > 0]
    if unused:
        print("  (whitelist entries that never touched: " + ", ".join("↔".join(u) for u in unused) + ")")

    print("\nDESIGN RULES (min clearance over every pose):")

    def members(n):
        return ALIAS.get(n, [n])
    for (n1, n2), (lim, why) in RULES.items():
        ds = [worst[frozenset((x, y))][0] for x in members(n1) for y in members(n2) if frozenset((x, y)) in worst]
        d = min(ds) if ds else float("inf")
        strict = (n1, n2) == ("cradle", "tf")
        ok = d > lim if strict else d >= lim
        print(f"  {n1:14s} {n2:14s} {d:7.2f}  {'>' if strict else '≥'} {lim}  {'ok' if ok else 'FAIL'}   {why}")
        if not ok:
            fails.append((n1, n2, "rule", why))
    print("\nWALLS (material between two cuts of one print):")
    for (c1, c2), (lim, why) in WALL_RULES.items():
        m1, m2 = export(c1), export(c2)
        w = trimesh.collision.CollisionManager(); w.add_object(c2, m2)
        d = w.min_distance_single(m1)
        ok = d >= lim
        print(f"  {c1:14s} {c2:14s} {d:7.2f}  ≥ {lim}  {'ok' if ok else 'FAIL'}   {why}")
        if not ok:
            fails.append((c1, c2, "wall", why))
    print("\nBASEPLATE ENVELOPE (every pose; baseplate X ±285, Y ±270, top Z 4):")
    for n in OWN:
        lo, hi = env[n]
        inside = np.all(lo[:2] >= BASE[0][:2] - 1e-6) and np.all(hi[:2] <= BASE[1][:2] + 1e-6) and lo[2] >= BASE[0][2] - 1e-6
        print(f"  {n:14s} X {lo[0]:7.1f}..{hi[0]:6.1f}  Y {lo[1]:7.1f}..{hi[1]:6.1f}  Z {lo[2]:5.1f}..{hi[2]:6.1f}  "
              f"{'ok' if inside else 'OUTSIDE BASEPLATE'}")
        if not inside:
            fails.append((n, "baseplate", "envelope", ""))
    lows = {n: env[n][0][2] - BASE[0][2] for n in ["c2_link", "c2_crank", *C2_HW]}
    lo_n = min(lows, key=lows.get)
    print(f"\nch2 linkage lowest point: {lo_n} {lows[lo_n]:.1f} mm above the tiles (rule ≥ {TILE_LIP}: "
          f"{'ok' if lows[lo_n] >= TILE_LIP else 'FAIL'})")
    if lows[lo_n] < TILE_LIP:
        fails.append((lo_n, "tiles", "lip", ""))
    if fails:
        print(f"\n{len(fails)} FAILURES:")
        for f in fails:
            print("   ", f)
    else:
        print("\nNo unintended contact or overlap; every whitelisted overlap within its cap.")
    return not fails


# ---------------------------------------------------------------- assembly / access
def echo_vals(exprs, uses):
    src = "".join(f"use <{CAD}/{u}.scad>\n" for u in uses) + "".join(
        f'echo(str("AV|{k}|", {e}));\n' for k, e in exprs.items()) + "cube(1);\n"
    f = WORK / "asm_echo.scad"; f.write_text(src)
    out = subprocess.run([OPENSCAD, "-o", str(WORK / "asm_echo.stl"), str(f)], capture_output=True, text=True).stderr
    return {m.group(1): json.loads(m.group(2)) for m in re.finditer(r'ECHO: "AV\|(\w+)\|(.*)"', out)}


def cyl_between(p0, p1, r):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    v = p1 - p0; h = np.linalg.norm(v)
    c = trimesh.creation.cylinder(radius=r, height=h, sections=24)
    z = np.array([0, 0, 1.0]); a = v / h
    T = trimesh.geometry.align_vectors(z, a); T[:3, 3] = (p0 + p1) / 2
    return c.apply_transform(T)


def place_moving(meshes, yc, mode="F", a=0.0, psi=None):
    """Carriage + TF group + tilt drive at carriage Y yc and tilt pose (mode, a); ch2 crank,
    horn screws at crank angle psi (default: the angle that goes with yc)."""
    T_y = trans(y=yc)
    phi = crank_phi(mode, a)
    tip = D + CR * np.array([math.cos(math.radians(phi)), math.sin(math.radians(phi))])
    Ap = pose_pt(A, mode, a)
    lang = math.degrees(math.atan2(Ap[1] - tip[1], Ap[0] - tip[0]))
    psi = c2_psi(yc) if psi is None else psi
    out = {"carriage": meshes["carriage"].copy().apply_transform(T_y),
           "tilt_crank": meshes["tilt_crank"].copy().apply_transform(T_y @ ry(-phi, D)),
           "tilt_pivot": meshes["tilt_pivot"].copy().apply_transform(T_y @ ry(-phi, D)),
           "tilt_link": meshes["tilt_link"].copy().apply_transform(T_y @ trans(tip[0], 0, tip[1]) @ ry(-lang, (0, 0))),
           "c2_crank": meshes["c2_crank"].copy().apply_transform(trans(C2P[0], C2P[1]) @ rz(psi)),
           "c2_horn_screws": meshes["c2_horn_screws"].copy().apply_transform(trans(C2P[0], C2P[1]) @ rz(psi))}
    for n in TF_GROUP:
        out[n] = meshes[n].copy().apply_transform(T_y @ tf_matrix(mode, a))
    return out


def hits(group, against, allow=()):
    """Overlap volumes (mm³) of every group part with every `against` part; pairs in `allow`
    may touch (≤ 1 mm³)."""
    import fcl  # noqa: F401
    res = []
    for n, m in group.items():
        for k, f in against.items():
            if np.any(m.bounds[0] > f.bounds[1]) or np.any(f.bounds[0] > m.bounds[1]):
                continue
            mgr = trimesh.collision.CollisionManager(); mgr.add_object(k, f)
            if not mgr.in_collision_single(m):
                continue
            v = overlap_volume(m, f)
            v = 1e-3 if math.isnan(v) else v
            if v > 0.05 and not ((n, k) in allow and v < 1.0):
                res.append(f"{n}↔{k} {v:.2f} mm³")
    return res


def sweep(label, group, against, steps, allow=()):
    """Move `group` (dict of meshes in their FINAL pose) through the list of 4×4 offsets
    `steps` (last one = identity) and report the first collision."""
    for i, T in enumerate(steps):
        g = {n: m.copy().apply_transform(T) for n, m in group.items()}
        h = hits(g, against, allow if i == len(steps) - 1 else ())
        if h:
            off = np.round(T[:3, 3], 1)
            print(f"  FAIL {label}: at offset {off.tolist()}: " + ", ".join(h))
            return False
    print(f"  ok   {label} ({len(steps)} steps)")
    return True


def run_assembly(meshes):
    """Install order, step by step: every insertion is swept along its path against what is
    already installed, every screw gets a tool path (hex key) from its head outward."""
    V = echo_vals({"tie": "riser_tie_screws()", "fy": "riser_front_y()", "holes": "sh_end_post_holes()",
                   "pina": "sh_pin_a_y()", "pivot": "sh_tilt_pivot_hw()", "crank_y": "sg_crank_y()", "link_y": "sg_link_y()", "c1e": "sh_c1_ear_holes()", "c1y": "sg_c1_face_y()",
                   "grub": "sh_rod_grubs()", "rear": "sg_c2_ear_y()", "face": "sg_c2_face_z()",
                   "riser_ear": "riser_ear_screws()", "hold": 'sg_crank_phi("hold")', "ear_x": "sg_c2_ear_x()",
                   "grub_len": "sh_rod_grub_len()",
                   "clamp_m": 'sh_c1_clamp(sg_crank_phi("hold") - 30)', "clamp_0": 'sh_c1_clamp(sg_crank_phi("hold"))',
                   "clamp_p": 'sh_c1_clamp(sg_crank_phi("hold") + 30)'},
                  ["riser", "shuttle", "shuttle_geom"])
    for n in ASM_OBJS:
        meshes.setdefault(n, export(n))
    ok = True
    fixed = {n: meshes[n] for n in FIXED}
    conveyor = {n: meshes[n] for n in ["riser", "tray", "rails", "motor_mounts", "rollers", "card_guides", "etray"]}

    def clear(tool, against, label, quiet=False):
        hits_ = []
        for n, m in against.items():
            if np.any(tool.bounds[0] > m.bounds[1]) or np.any(m.bounds[0] > tool.bounds[1]):
                continue
            v = overlap_volume(tool, m)
            if math.isnan(v):                      # boolean failed: fall back to FCL distance
                mgr = trimesh.collision.CollisionManager(); mgr.add_object(n, m)
                v = 0.0 if mgr.min_distance_single(tool) > 1e-6 else float("inf")
            if not (v < 0.05):
                hits_.append(f"{n} {v:.2f} mm³")
        if not quiet:
            print(f"  {'ok  ' if not hits_ else 'FAIL'} {label}" + ("" if not hits_ else "  blocked by: " + ", ".join(hits_)))
        return not hits_

    def key_swing(x, y, zb, against, label, need=60):
        """L-key, short arm (14) up into the socket, long arm (45) swinging horizontally at
        its bottom: largest contiguous free arc (15° steps) must be ≥ need."""
        ok_ = clear(cyl_between([x, y, zb - 0.1], [x, y, zb - 14], 1.25), against, label + ": 1.5 mm L-key short arm (14) up")
        free = [clear(cyl_between([x, y, zb - 14], [x + 45 * math.cos(math.radians(t)), y + 45 * math.sin(math.radians(t)), zb - 14], 1.25),
                      against, "", quiet=True) for t in range(0, 360, 15)]
        best = run_ = 0
        for f in free + free:                     # wrap around
            run_ = run_ + 1 if f else 0
            best = max(best, min(run_, 24))
        arc = (best - 1) * 15 if best else 0
        print(f"  {'ok  ' if arc >= need else 'FAIL'}    … long arm (45) free swing at Z {zb - 14:.1f}: {arc}° contiguous (need ≥ {need}°)")
        return ok_ and arc >= need

    print("\nASSEMBLY ORDER / INSERTION AND DRIVING PATHS (tool = hex key / driver envelope)")
    PSI_PARK = 100.0          # ch2 crank parked pointing −X/−Y, outside the riser footprint
    Y_PARK = 102.0            # carriage parked at column 3: its drive-pin arm is beyond the riser (Y > 80)

    # ---- 0. riser (bolted down before the conveyor, riser.scad) -- riser front tie
    print(" 0. riser_a + riser_b on the baseplate")
    for x, z in V["tie"]:
        ok &= clear(cyl_between([x, V["fy"] - 0.2, z], [x, -300, z], 3.5), fixed,
                    f"riser front-tie M3 × 10 countersunk from the front (X {x}, Z {z}), Ø7 driver")

    # ---- 1. bench: ch1 servo + coupler into the −Y end post's cage
    print(" 1. bench: ch1 MG996R + goBILDA 4001 coupler (screwed to the spline, boss UP) into the −Y cage from −Y")
    grp = {"servo_ch1": meshes["servo_ch1"], "coupler": meshes["c1_coupler_up"]}
    ok &= sweep("ch1 servo + coupler slid along +Y through the cage opening (60 mm)", grp,
                {"end_post_neg": meshes["end_post_neg"]},
                [trans(y=-d) for d in np.arange(60, -0.01, -1.0)], allow={("servo_ch1", "end_post_neg")})
    yf = V["c1y"]; ye = yf - 10.6
    for x, z in V["c1e"]:
        ok &= clear(cyl_between([x, ye - 3.6, z], [x, -300, z], 2.0),
                    {**fixed, "end_post_neg": meshes["end_post_neg"]},
                    f"ch1 ear M3 × 10 SHCS + washer, along +Y from behind the servo (X {x}, Z {z}): 2.5 mm hex driver to Y −300")
    # ---- 2. bench: module (posts, rod, carriage, shaft, R-bar)
    print(" 2. bench: rod, carriage, shaft (REX, from +Y into the coupler), R-bar; coupler clamp; rod grubs")
    # ch1 crank ↔ link pivot (§13.2, bench, before pin A and the shaft): M3 × 16 SHCS + nylock.
    # Length: grip (crank + gap + link) + nylock + ≥ 1 mm of thread past the nylon ring.
    hd, hh, nd, nh, ln = V["pivot"]; cy, ly = V["crank_y"], V["link_y"]
    grip = cy[1] - ly[0]; past = ln - grip - nh
    good = past >= 1.0
    ok &= good
    print(f"  {'ok  ' if good else 'FAIL'} crank-link pivot M3 × {ln:.0f} + nylock: grip {grip:.1f} (crank + gap + link) + nut {nh:.1f}, "
          f"{past:.1f} mm of thread past the nut (need ≥ 1)")
    # tools on the bench (crank + link joined at their HOLD angle, nothing else fitted yet):
    # 2.5 mm hex key along +Y from the head, Ø10 nut driver (5.5 mm) along −Y from the nylock
    fin = place_moving(meshes, 0.0, "F", TH_H)
    phi_h = math.radians(crank_phi("F", TH_H)); tp = D + CR * np.array([math.cos(phi_h), math.sin(phi_h)])
    bench = {n: fin[n] for n in ("tilt_crank", "tilt_link")}
    ok &= clear(cyl_between([tp[0], cy[1] + hh + 0.2, tp[1]], [tp[0], cy[1] + hh + 80, tp[1]], 1.25), bench,
                f"crank-link pivot: 2.5 mm hex key along +Y on the M3 × {ln:.0f} head (bench)")
    ok &= clear(cyl_between([tp[0], ly[0] - 0.2, tp[1]], [tp[0], ly[0] - 80, tp[1]], 5.0), bench,
                "crank-link pivot: Ø10 nut driver (5.5 mm) along −Y on the nylock (bench)")
    # crank + link (joined) into the sled pocket (§13.2: LM8UUs already pressed in; no cheeks,
    # TF or shaft yet): crank pointing +X (φ 0), hub first along −X through the insertion
    # channel until its bore is on the shaft axis; then it turns freely on that axis
    sled_lm = {"sled": meshes["sled"], "lm8uu": meshes["lm8uu"]}
    tip0 = D + np.array([CR, 0.0]); Ah = pose_pt(A, "F", 0.0)
    lang = math.degrees(math.atan2(Ah[1] - tip0[1], Ah[0] - tip0[0]))      # link hanging toward pin A
    grp = {"tilt_crank": meshes["tilt_crank"], "tilt_pivot": meshes["tilt_pivot"],
           "tilt_link": meshes["tilt_link"].copy().apply_transform(trans(tip0[0], 0, tip0[1]) @ ry(-lang, (0, 0)))}
    ok &= sweep("§13.2 crank + link (joined, crank pointing +X) slid hub-first along −X into the sled pocket (40 mm)",
                grp, sled_lm, [trans(x=d) for d in np.arange(40, -0.01, -1.0)])
    ok &= sweep("§13.2 crank turned on the shaft axis through φ −50..30 (operating −48.5..22.2 + margin)",
                {n: grp[n] for n in ("tilt_crank", "tilt_pivot")}, sled_lm, [ry(-a, D) for a in range(-50, 31, 2)] + [np.eye(4)])
    # the shaft goes through the crank's REX bore (crank turned so its hex matches: φ 0)
    shaft_against = {"end_posts": meshes["end_posts"], "servo_ch1": meshes["servo_ch1"],
                     "carriage": meshes["carriage"], "lm8uu": meshes["lm8uu"], "tilt_crank": meshes["tilt_crank"]}
    ok &= sweep("shaft slid along −Y from +440 mm (through post +Y, sled bushings, crank bore, post −Y 688ZZ) into the coupler",
                {"rex_shaft": meshes["rex_shaft"]}, shaft_against, [trans(y=d) for d in np.arange(440, -0.01, -4.0)])
    for k, key, off in (("clamp_m", "−30°", -30), ("clamp_0", "0°", 0), ("clamp_p", "+30°", 30)):
        p0, u = (np.array(v, float) for v in V[k])
        pa = p0 + 7.05 * u         # head top (screw 14 long centred on the axis point)
        against = {**{n: m for n, m in fixed.items() if n != "ch1_coupler"}, "coupler": meshes[f"c1_coupler_hold{off:+d}"]}
        ok &= clear(cyl_between(pa, pa + 120 * u, 1.75), against,
                    f"coupler M4 clamp screw at HOLD, hex-index offset {key} (boss {V['hold'] + off:.0f}°): 3 mm key from the head out 120 mm")
    for x, y, z in V["grub"]:
        for yc in (TARGETS["0"], TARGETS["reject"]):
            others = {**fixed, "carriage": meshes["carriage"].copy().apply_transform(trans(y=yc))}
            ok &= clear(cyl_between([x + 0.2, y, z], [x + 150, y, z], 1.5), others,
                        f"rod M3 × {V['grub_len']:.0f} set screw along −X into the insert (Y {y}, Z {z}), 1.5 mm key, carriage at Y {yc:.0f}")
    # ---- 3. bench: ch2 servo (horn + crank + hub screw fitted, crank at ψ_park) hung under the shelf
    print(f" 3. bench: ch2 MG996R with horn, crank, hub screw; crank parked at ψ {PSI_PARK:.0f}°; lifted under the −Y shelf")
    c2 = {"servo_ch2": meshes["servo_ch2"], "c2_horn": meshes["c2_horn"],
          "c2_crank": meshes["c2_crank"].copy().apply_transform(trans(C2P[0], C2P[1]) @ rz(PSI_PARK)),
          "c2_horn_screws": meshes["c2_horn_screws"].copy().apply_transform(trans(C2P[0], C2P[1]) @ rz(PSI_PARK))}
    ok &= sweep("ch2 servo + crank lifted straight up 40 mm, rear ear under the end-post shelf", c2,
                {"end_posts": meshes["end_posts"]}, [trans(z=-d) for d in np.arange(40, -0.01, -1.0)],
                allow={("servo_ch2", "end_posts")})
    face = V["face"]; zb = face + 8.1 - 1.8          # screw head bottom
    for x in V["ear_x"]:
        ok &= key_swing(x, V["rear"][1], zb, {"end_posts": meshes["end_posts"], **c2},
                        f"ch2 REAR ear M2.5 button head from below (X {x}, Y {V['rear'][1]})")
    # ---- 4. module set down 10 mm in front of its place, then slid +Y 10 mm (front ear into the riser pocket)
    print(f" 4. module (step 1–3, carriage parked at Y {Y_PARK:.0f}, TF level) set down at Y −10 and slid +Y into place;"
          " ch2 rear-ear screws 1 turn loose (servo hangs 0.5 low)")
    module = {n: meshes[n] for n in ["end_posts", "rbar", "rod", "rex_shaft", "servo_ch1", "ch1_coupler", "c1_ear_screws"]}
    module.update({n: m for n, m in place_moving(meshes, Y_PARK, "F", 0.0).items() if n not in ("c2_crank", "c2_horn_screws")})
    module.update({n: m.copy().apply_transform(trans(z=-0.5)) for n, m in {**c2, "c2_ear_screws_rear": meshes["c2_ear_screws_rear"]}.items()})
    steps = [trans(y=-10, z=dz) for dz in np.arange(80, 0, -2.0)] + [trans(y=-d) for d in np.arange(10, -0.01, -0.5)]
    ok &= sweep("module lowered 80 mm at Y −10, then slid +10 mm along +Y", module, conveyor, steps)
    # ---- 5. front ear screws from below, through the tunnel
    print(" 5. ch2 FRONT ear: tighten the rear screws (servo up 0.5), drive the front screws up through the tunnel")
    inst = {**{n: meshes[n] for n in ["riser", "end_posts", "servo_ch2", "c2_horn", "rbar", "rod"]},
            "c2_crank": c2["c2_crank"], "c2_horn_screws": c2["c2_horn_screws"]}
    for x, y, zc in V["riser_ear"]:
        ok &= key_swing(x, y, zb, inst, f"ch2 FRONT ear M2.5 button head from below through the tunnel (X {x}, Y {y})")
    for x, y in V["holes"]:
        bt = G["sg_base_top"]
        others = {**fixed, **{k: v for k, v in place_moving(meshes, Y_PARK).items()}}
        if not clear(cyl_between([x, y, bt + 7.2], [x, y, 200], 1.5), others, "", quiet=True):
            d = np.array([1, 0, 1]) / math.sqrt(2)      # rod/shaft overhead: ball-end key tilted toward +X
            ok &= clear(cyl_between([x, y, bt + 7.2], np.array([x, y, bt + 7.2]) + 120 * d, 1.5), others,
                        f"end-post anchor M3 × 20 at ({x}, {y}): rod overhead, 2.5 mm BALL-END key at 45° from +X")
        else:
            print(f"  ok   end-post anchor M3 × 20 at ({x}, {y}): 2.5 mm key straight down")
    # ---- 6. ch2 link, pivots (existing order), then ramp + reject bin
    print(" 6. ch2 link + pivot screws (crank-tip screw at column 0, drive-pin screw at reject)")
    sh = G["sg_c2_sh"]
    tip = np.array([C2P[0] - C2R * math.sin(math.radians(c2_psi(TARGETS["0"]))),
                    C2P[1] + C2R * math.cos(math.radians(c2_psi(TARGETS["0"])))])
    z_tip = G["sg_c2_z"][1] + sh[2]
    others = {**fixed, "carriage@col0": meshes["carriage"].copy().apply_transform(trans(y=TARGETS["0"]))}
    ok &= clear(cyl_between([tip[0], tip[1], z_tip + 0.2], [tip[0], tip[1], 250], 4.5), others,
                f"ch2 crank-tip shoulder screw from above at column 0 (X {tip[0]:.0f}, Y {tip[1]:.0f}, head top Z {z_tip:.0f})")
    yr = TARGETS["reject"]; pin = [C2P[0], yr + C2DY]
    z_pin = G["sg_c2_arm_z"][1] + sh[2]
    others = {**fixed, "carriage@reject": meshes["carriage"].copy().apply_transform(trans(y=yr))}
    ok &= clear(cyl_between([pin[0], pin[1], z_pin + 0.2], [pin[0], pin[1], 250], 4.5), others,
                f"ch2 drive-pin shoulder screw from above at reject (X {pin[0]:.0f}, Y {pin[1]:.0f}, head top Z {z_pin:.0f})")
    # pin A: Ø3 dowel pushed in along −Y from outside the +Y TF plate (bench, before the +Y cheek)
    y0 = V["pina"][0]
    tool = cyl_between([A[0], y0 + 0.3, A[1]], [A[0], 80.0, A[1]], 1.4)
    ok &= clear(tool, {"tf": meshes["tf"], "cell": meshes["cell"], "cradle": meshes["cradle"], "tilt_link": meshes["tilt_link"]},
                f"pin A dowel path (X {A[0]:.0f}, Z {A[1]:.0f}) from Y 80 to its seat at Y {y0} (bench, before the +Y cheek)")
    ray = meshes["tf"].ray.intersects_location([[A[0] + 1.2, 80.0, A[1]]], [[0, -1.0, 0]], multiple_hits=True)[0]
    first = max(ray[:, 1]) if len(ray) else None
    print(f"       ray along −Y 1.2 off the pin-A axis: first TF surface at Y {first if first is not None else float('nan'):.2f} "
          f"(the Ø2.9→Ø2 seat shoulder at Y {y0}); knock-out from −Y through the Ø2")
    ok &= first is not None and first <= y0 + 0.01
    print(" 7. lower ramp + reject bin lowered onto the baseplate; the carriage (TF level) is parked clear of each")
    base = {n: meshes[n] for n in ["end_posts", "rbar", "rod", "rex_shaft", "riser", "tray"]}
    for part, yc in (("ramp_neg", TARGETS["3"]), ("ramp_pos", TARGETS["0"]), ("reject_bin", TARGETS["0"])):
        ok &= sweep(f"{part} lowered 120 mm (carriage at Y {yc:.0f})", {part: meshes[part]}, {**base, **place_moving(meshes, yc, "F", 0.0)},
                    [trans(z=d) for d in np.arange(120, -0.01, -3.0)], allow={(part, "tray")})
    # end-post holes on the baseplate grid (probe): grid membership, hole open, plate all round, head clear
    gx = sorted({-285 + 190 * c + 15 + 30 * k for c in range(3) for k in range(6)})
    gy = sorted({-270 + 180 * r + 15 + 30 * k for r in range(3) for k in range(6)})
    ep = meshes["end_posts"]; bt = G["sg_base_top"]
    for x, y in V["holes"]:
        on = x in gx and y in gy
        hit = ep.ray.intersects_location([[x, y, bt + 30]], [[0, 0, -1.0]], multiple_hits=True)[0]
        open_ = not any(bt - 0.01 <= h[2] <= bt + 4.01 for h in hit)
        rim = ep.contains([[x + 3.0 * math.cos(t), y + 3.0 * math.sin(t), bt + 2] for t in np.linspace(0, 2 * math.pi, 8, endpoint=False)]).all()
        head = cyl_between([x, y, bt + 4.05], [x, y, bt + 4 + 3.0], 2.75 + 0.5)
        head_ok = all(not (overlap_volume(head, m) > 0.05) for n, m in fixed.items()
                      if not (np.any(head.bounds[0] > m.bounds[1]) or np.any(m.bounds[0] > head.bounds[1])))
        good = on and open_ and rim and head_ok
        ok &= good
        print(f"  {'ok  ' if good else 'FAIL'} end-post hole ({x}, {y}): on grid {on}, open through the plate {open_}, "
              f"plate all round {rim}, head clear (0.5) {head_ok}")
    # ch2 direction (geometry convention the firmware relies on)
    t0 = np.array([C2P[0] - C2R * math.sin(math.radians(c2_psi(TARGETS["reject"]))), C2P[1] + C2R * math.cos(math.radians(c2_psi(TARGETS["reject"])))])
    t1 = np.array([C2P[0] - C2R * math.sin(math.radians(90)), C2P[1]])
    assert abs(c2_psi(TARGETS["reject"])) < 3 and abs(c2_psi(TARGETS["0"]) - 180) < 3 and t1[0] < C2P[0] and t0[1] > C2P[1], \
        "ch2 convention broken: ψ 0 must point +Y (reject), 90 −X, 180 −Y (column 0)"
    print("  note ch2 DIRECTION: increasing servo angle must swing the crank +Y → −X → −Y, i.e. COUNTER-CLOCKWISE seen\n"
          "       from ABOVE (clockwise looking at the spline of the upside-down servo). Check it on the bench (calibrate_servos.py d + t)\n"
          "       BEFORE the horn/crank go on; a reversed servo drives the crank into the end post (shuttle.scad).")
    print("  " + ("Install order and every driving path clear." if ok else "ASSEMBLY FAILURES above."))
    return ok


# ---------------------------------------------------------------- slide
CARD_L, CARD_M = 88.0, 1.75e-3      # mm, kg (raw card, owner-confirmed)


def cradle_surface_level():
    """Card-contact polyline of the cradle (bed + fillet + kick) in the level frame, mm."""
    bz, bx0, bend, ka, kl = G["sg_bed_z"], G["sg_bed_x0"], G["sg_bend_x"], G["sg_kick_a"], G["sg_kick_l"]
    fr = 20.0; t = fr * math.tan(math.radians(ka / 2))
    fc = (bend - t, bz + fr)
    pts = [(bx0 + 4 - 4 * math.cos(math.radians(30)), bz - 2.0), (bx0 + 4, bz)]
    pts += [(fc[0] + fr * math.cos(math.radians(-90 + ka * i / 6)), fc[1] + fr * math.sin(math.radians(-90 + ka * i / 6))) for i in range(7)]
    pts.append(tuple(G["sg_lip"]))
    return np.array(pts)


def run_slide(target_floor, mu, front_x=152.0, stack=0.0, t_tip=0.5, t_end=2.0, th_u=None, dl=None, mu_cradle=None):
    """2-D rigid-body run (pymunk/Chipmunk, mm-g-s units). The card starts at rest on the cradle
    in HOLD (front edge at front_x, level frame). The cradle (kinematic body) turns to UPPER
    (about F) or LOWER (about the skid on the R-bar) with the cosine ramp shuttle.py uses,
    the card slides off. Returns where the card comes to rest and whether it is inside the slot."""
    import pymunk
    space = pymunk.Space()
    space.gravity = (0, -9810.0)
    space.iterations = 60
    space.collision_slop = 0.005
    R_S = 0.25                                      # segment half-thickness (surfaces offset down by it)
    level = cradle_surface_level()
    mu_c = mu if mu_cradle is None else mu_cradle   # card-on-cradle (bed may carry PTFE tape)
    th_u = TH_U if th_u is None else th_u
    dl = DL if dl is None else dl
    if target_floor == "upper":
        pivot, a_end = F, th_u - TH_H
        local = np.array([rot2(p, F, TH_H) for p in level]) - F    # hold pose, about F
    else:
        pivot, a_end = SJ, dl
        local = np.array([rot2(p, F, TH_H) for p in level]) - SJ   # hold pose, about the skid
    cradle = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    cradle.position = tuple(pivot)
    space.add(cradle)
    for p0, p1 in zip(local[:-1], local[1:]):
        sh = pymunk.Segment(cradle, tuple(p0 + (0, -R_S)), tuple(p1 + (0, -R_S)), R_S)
        sh.friction = mu_c; space.add(sh)
    lipc = pymunk.Circle(cradle, 1.0, tuple(local[-1] + (0, -1.0))); lipc.friction = mu_c; space.add(lipc)
    xt = XT
    statics = []
    if target_floor == "upper":
        floor_z = 74.5 + stack; front = xt + 95.5             # upper slot: front wall inner face
        statics += [((xt, 60.0), (xt, floor_z)), ((xt, floor_z), (front, floor_z)), ((front, floor_z), (front, 140.0))]
    else:
        floor_z = 6.5 + stack; front = xt + 89.5              # lower slot: front-corner bosses (89.5 free)
        ramp = [tuple(p) for p in G["sg_ramp_profile"]]
        statics += list(zip(ramp[:-1], ramp[1:]))
        statics += [((ramp[0][0], ramp[0][1] - 3), ramp[0]), (ramp[-1], (xt, floor_z)), ((xt, floor_z), (front, floor_z)),
                    ((front, floor_z), (front, 69.0)), ((xt, 69.0), (front, 69.0)), ((xt, 69.0), (xt, 140.0))]
    for p0, p1 in statics:
        sh = pymunk.Segment(space.static_body, p0, p1, 0.5); sh.friction = mu; space.add(sh)
    # card: 88 × 0.33 box with 0.15 rounding
    th0 = math.radians(TH_H)
    p_front = rot2(np.array([front_x, G["sg_bed_z"] + 0.3]), F, TH_H)
    u0 = np.array([math.cos(th0), -math.sin(th0)])
    com = p_front - u0 * CARD_L / 2
    mass = CARD_M * 1000.0                                  # g
    card = pymunk.Body(mass, pymunk.moment_for_box(mass, (CARD_L, 0.33)))
    card.position = tuple(com); card.angle = -th0
    cs = pymunk.Poly.create_box(card, (CARD_L, 0.33), 0.15); cs.friction = 1.0     # pair μ = surface μ
    space.add(card, cs)
    dt = 1 / 20000.0
    n = int(t_end / dt)
    peak = 0.0
    a_prev = 0.0
    area = 63.0 * 88.0                                      # mm²
    for i in range(n):
        t = i * dt
        s_ = min(1.0, t / t_tip); a = (0.5 - 0.5 * math.cos(math.pi * s_)) * a_end
        cradle.angle = -math.radians(a)
        cradle.angular_velocity = -math.radians(a - a_prev) / dt
        a_prev = a
        # air drag on the card face (Cd 1.2, rho 1.2e-9 g/mm³)
        nv = pymunk.Vec2d(0, 1).rotated(card.angle)
        vn = card.velocity.dot(nv)
        card.apply_force_at_world_point(tuple(-0.5 * 1.2e-9 * 1.2 * area * vn * abs(vn) * nv), card.position)
        space.step(dt)
        peak = max(peak, card.velocity.length)
    u = np.array([math.cos(card.angle), math.sin(card.angle)])
    c = np.array(card.position)
    tail = c - u * CARD_L / 2; head = c + u * CARD_L / 2
    xs = sorted([tail[0], head[0]]); zs = sorted([tail[1], head[1]])
    inside = xs[0] >= xt - 0.5 and xs[1] <= front + 0.5 and zs[0] >= floor_z - 1.5 and zs[1] <= floor_z + 4
    resting = card.velocity.length < 20.0                   # mm/s
    return dict(floor=target_floor, mu=mu, mu_c=mu_c, front0=front_x, stack=stack, tail_x=round(float(xs[0]), 1),
                head_x=round(float(xs[1]), 1), z=(round(float(zs[0]), 1), round(float(zs[1]), 1)),
                tilt_deg=round(math.degrees(card.angle), 1), speed=round(card.velocity.length / 1000, 3),
                peak_speed=round(peak / 1000, 2), ok=bool(inside and resting))


def slide_suite():
    print("\nCARD SLIDE SIMULATION (pymunk 2-D rigid card 88 × 0.33 mm, 1.75 g; cosine tilt ramp 0.5 s; air drag)")
    print(f"  slots: upper X {XT}..{XT + 95.5}, floor 74.5 + stack; lower X {XT}..{XT + 89.5} (front bosses), floor 6.5 + stack")
    print("  μ = card on PLA (tray floor, lower ramp); cradle bed with PTFE tape μc = 0.15 (design) or bare PLA (μc = μ)")
    print("  IN  = card flat in the slot, tail past the back face;  SHORT = flat on the floor but tail ≤ 6 mm behind")
    print("        the back face (under every cradle path; the next card pushes it home);  JAM = still on the cradle/ramp")
    all_ok = True
    rows = []
    for floor, stacks in (("upper", (0.0, 4.0, 8.0)), ("lower", (0.0, 10.0, 18.0))):
        for muc in (0.15, None):
            for mu in (0.25, 0.35, 0.45):
                cells = []
                for st in stacks:
                    verdicts = []
                    for fx in (148.0, 156.0):
                        r = run_slide(floor, mu, fx, st, mu_cradle=muc)
                        flat = (r["z"][1] - r["z"][0]) < 1.0
                        v = "IN" if r["ok"] else ("SHORT" if flat and r["tail_x"] > XT - 6 else "JAM")
                        verdicts.append(v); rows.append((floor, muc, mu, st, fx, v, r))
                        if muc == 0.15 and mu <= 0.35 and v == "JAM":
                            all_ok = False
                    worst = "JAM" if "JAM" in verdicts else ("SHORT" if "SHORT" in verdicts else "IN")
                    cells.append(f"stack {st:4.1f}: {worst:5s}")
                tag = f"μc {0.15 if muc else mu:.2f}"
                print(f"  {floor:5s} {tag}  μ {mu:.2f} | " + " | ".join(cells))
    return all_ok, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", nargs="?", default="all", choices=["all", "collide", "slide", "assembly", "geom"])
    args = ap.parse_args()
    ok = True
    if args.what == "geom":
        print(json.dumps(G, indent=1))
        return
    meshes = load_all() if args.what in ("all", "collide", "assembly") else None
    if args.what in ("all", "collide"):
        ok &= run_collide(meshes)
    if args.what in ("all", "assembly"):
        ok &= run_assembly(meshes)
    if args.what in ("all", "slide"):
        s_ok, _ = slide_suite()
        ok &= s_ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
