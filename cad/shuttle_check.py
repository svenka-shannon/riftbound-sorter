#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "trimesh", "manifold3d", "python-fcl", "scipy", "pymunk", "rtree"]
# ///
"""Validate the cradle-shuttle sorter (cad/shuttle*.scad, lower_ramp, reject_bin, riser).

  collide  — trimesh/FCL collision + clearance sweep: carriage, tilt frame,
             cradle, load cell, card, F pins, pin A and both drive linkages
             (incl. every ch2 screw, insert and pin: horn screws, the two
             shoulder-screw pivots, the servo ear screws) through every
             target (4 columns + reject + home) × every tilt state (incl.
             intermediate angles) and the whole Y travel in HOLD, against the
             tray, lower ramp, reject bin, rails, riser, motor mounts, card
             guides, rollers, electronics tray, R-bar, end posts and servos.
             Design rules: cradle↔TF > 0.5 (weighing gap), TF body↔carriage
             ≥ 0.6, ch2 crank↔link and link↔carriage ≥ 0.8 (no hardware between
             them), everything of ch2 ≥ 3 mm above the tiles.
  assembly — insertion / access paths: pin A dowel path, ch2 pivot screws from
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
    "carriage": "carriage();",
    "cradle": "cradle();",
    "tf": "tilt_frame();",
    "fpins": "f_pins();",
    "pin_a": "pin_a();",
    "cell": "load_cell();",
    "card": "card_on_bed();",
    "tilt_crank": "tilt_crank();",
    "tilt_link": "tilt_link();",
    "c2_crank": "c2_crank();",
    "c2_link": "c2_link();",
    "c2_horn_screws": "c2_horn_screws();",     # crank frame
    "c2_tip_pin": "c2_tip_pin();",             # crank frame (axisymmetric; turns with the link)
    "c2_drive_pin": "c2_drive_pin();",         # carriage frame
    # fixed
    "rbar": "rbar_neg(); rbar_pos();",
    "end_posts": "end_post_neg(); end_post_pos();",
    "rod": "rod8(sg_rod(), sg_rod_y()[0], sg_rod_y()[1]);",
    "dshaft": "dshaft(sg_rod_y()[0] - 8, sg_rod_y()[1]);",
    "servo_ch1": "translate([sg_D()[0], -168, sg_D()[1]]) rotate([-90, 0, 0]) rotate(90) mg996r();",
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


def export(name):
    stl = WORK / f"{name}.stl"
    scad = WORK / f"{name}.scad"
    src = "".join(f"use <{CAD}/{u}.scad>\n" for u in USES)
    src += "module cyl_y(p, d, y0, y1, fn = 40) translate([p[0], y0, p[1]]) rotate([-90, 0, 0]) cylinder(d = d, h = y1 - y0, $fn = fn);\n"
    src += SCENE_OBJS[name] + "\n"
    # cache key: wrapper source + modification times of every CAD file it can reach
    src += "// " + " ".join(f"{p.name}:{p.stat().st_mtime_ns}" for p in sorted(CAD.glob("*.scad"))) + "\n"
    if (not stl.exists()) or (not scad.exists()) or scad.read_text() != src:
        scad.write_text(src)
        r = subprocess.run([OPENSCAD, "--backend=manifold", "--export-format", "binstl", "-o", str(stl), str(scad)],
                           capture_output=True, text=True)
        if "NoError" not in r.stderr and not stl.exists():
            sys.exit(f"openscad failed for {name}:\n{r.stderr}")
    return trimesh.load(stl, force="mesh")


def load_all():
    return {n: export(n) for n in SCENE_OBJS}


# ---------------------------------------------------------------- collide
TF_GROUP = ["cradle", "tf", "cell", "card", "fpins", "pin_a"]
C2_HW = ["c2_horn_screws", "c2_tip_pin", "c2_drive_pin"]
MOVING = ["carriage", "tilt_crank", "tilt_link", *TF_GROUP]
FIXED = ["rbar", "end_posts", "rod", "dshaft", "servo_ch1", "servo_ch2", "c2_horn", "c2_ear_screws", "lower_ramp", "reject_bin", "riser",
         "tray", "rails", "motor_mounts", "rollers", "card_guides", "etray"]
# JOINED: parts fastened/journalled together (bearings, pins, bolted) — not checked.
JOINED = {frozenset(p) for p in [
    ("carriage", "rod"), ("carriage", "dshaft"), ("tilt_crank", "dshaft"), ("tilt_crank", "tilt_link"),
    ("tilt_link", "tf"), ("tf", "cell"), ("cradle", "cell"), ("card", "cradle"),
    ("fpins", "tf"), ("pin_a", "tf"), ("pin_a", "tilt_link"),
    # ch2: crank↔link and link↔carriage are NOT joined (1 mm apart in Z, checked);
    # only the hardware that actually connects them is
    ("c2_crank", "c2_horn"), ("c2_horn", "servo_ch2"),
    ("c2_horn_screws", "c2_crank"), ("c2_horn_screws", "c2_horn"),
    ("c2_horn_screws", "servo_ch2"),      # centre screw threads into the output spline
    ("c2_tip_pin", "c2_crank"), ("c2_tip_pin", "c2_link"),
    ("c2_drive_pin", "carriage"), ("c2_drive_pin", "c2_link"),
    ("c2_ear_screws", "servo_ch2"), ("c2_ear_screws", "riser"), ("c2_ear_screws", "end_posts"),
    ("dshaft", "end_posts"),
    ("rod", "end_posts"), ("rbar", "end_posts"), ("dshaft", "servo_ch1"),
    ("rails", "riser"), ("motor_mounts", "riser"),
    ("motor_mounts", "rails"), ("card_guides", "rails"), ("rollers", "rails"), ("tray", "lower_ramp"),
    ("reject_bin", "tray"), ("lower_ramp", "reject_bin")]}
# CONTACT: may touch (≤ 1 mm³ numerical overlap) but must not interpenetrate:
#   fpins–carriage = F pins seated in the cheek hooks; tf–rbar = skid on the R-bar;
#   servo ears seated under their shelves / against the ch1 cage.
CONTACT = {frozenset(p) for p in [("fpins", "carriage"), ("tf", "rbar"), ("servo_ch2", "riser"),
                                   ("servo_ch2", "end_posts"), ("servo_ch1", "end_posts")]}
OWN = ["carriage", "tilt_crank", "tilt_link", "cradle", "tf", "cell", "card", "c2_crank", "c2_link", *C2_HW, "c2_horn", "c2_ear_screws",
       "servo_ch2", "servo_ch1", "rbar", "end_posts", "rod", "dshaft", "lower_ramp", "reject_bin", "riser"]
# design-rule minimum clearances (moving pairs): name pair → (min mm, why)
RULES = {("cradle", "tf"): (0.5, "weighing gap: cradle must never touch the tilt frame"),
         ("tf", "carriage"): (0.6, "TF body ↔ carriage"),
         ("c2_crank", "c2_link"): (0.8, "ch2 crank over link (horn screws flush)"),
         ("c2_link", "carriage"): (0.8, "ch2 link under the drive-pin arm"),
         ("c2_horn_screws", "c2_link"): (0.8, "horn screw heads over the link at column 0")}
TILE_LIP = 3.0     # everything of the ch2 linkage stays ≥ 3 mm above the tiles (seam lips)
BASE = np.array([[-285.0, -270.0, 4.0], [285.0, 270.0, 1e9]])   # baseplate top / extents
ALLOWED = JOINED | CONTACT


def overlap_volume(a, b):
    try:
        v = a.intersection(b, engine="manifold").volume
    except Exception:
        v = float("nan")
    return v


def run_collide(meshes, verbose=False):
    import fcl  # noqa: F401  (trimesh uses it)
    fixed = {n: meshes[n] for n in FIXED}
    mgr_fixed = trimesh.collision.CollisionManager()
    for n, m in fixed.items():
        mgr_fixed.add_object(n, m)

    def moving_set(yc, mode, a):
        T_y = trans(y=yc)
        T_tf = T_y @ tf_matrix(mode, a)
        phi = crank_phi(mode, a)
        tip = D + CR * np.array([math.cos(math.radians(phi)), math.sin(math.radians(phi))])
        Ap = pose_pt(A, mode, a)
        T_crank = T_y @ ry(-phi, D)
        lang = math.degrees(math.atan2(Ap[1] - tip[1], Ap[0] - tip[0]))
        T_link = T_y @ trans(tip[0], 0, tip[1]) @ ry(-lang, (0, 0))
        psi = c2_psi(yc)
        c2tip = np.array([C2P[0] - C2R * math.sin(math.radians(psi)), C2P[1] + C2R * math.cos(math.radians(psi))])
        pin = np.array([C2P[0], yc + C2DY])
        out = {
            "carriage": meshes["carriage"].copy().apply_transform(T_y),
            "tilt_crank": meshes["tilt_crank"].copy().apply_transform(T_crank),
            "tilt_link": meshes["tilt_link"].copy().apply_transform(T_link),
            "c2_crank": meshes["c2_crank"].copy().apply_transform(trans(C2P[0], C2P[1]) @ rz(psi)),
            "c2_horn_screws": meshes["c2_horn_screws"].copy().apply_transform(trans(C2P[0], C2P[1]) @ rz(psi)),
            "c2_tip_pin": meshes["c2_tip_pin"].copy().apply_transform(trans(C2P[0], C2P[1]) @ rz(psi)),
            "c2_drive_pin": meshes["c2_drive_pin"].copy().apply_transform(T_y),
            "c2_link": meshes["c2_link"].copy().apply_transform(
                trans(c2tip[0], c2tip[1]) @ rz(math.degrees(math.atan2(pin[1] - c2tip[1], pin[0] - c2tip[0])) - 90)),
        }
        for n in TF_GROUP:
            out[n] = meshes[n].copy().apply_transform(T_tf)
        return out

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
    # Y travel in HOLD (every 6 mm across the full stroke)
    for yc in np.arange(min(TARGETS.values()), max(TARGETS.values()) + 0.1, 6.0):
        cases.append((f"travel", float(yc), "F", TH_H, "hold"))

    worst = {}
    fails = []
    env = {n: fixed[n].bounds.copy() for n in OWN if n in fixed}
    for tgt, yc, mode, a, label in cases:
        mv = moving_set(yc, mode, a)
        for n, m in mv.items():
            b = m.bounds
            env[n] = b.copy() if n not in env else np.array([np.minimum(env[n][0], b[0]), np.maximum(env[n][1], b[1])])
        names = list(mv)
        # moving vs fixed
        for n in names:
            for fn, fm in fixed.items():
                pair = frozenset((n, fn))
                if pair in JOINED:
                    continue
                key = (n, fn)
                m1 = mv[n]
                if not m1.bounds is None and (np.any(m1.bounds[0] > fm.bounds[1] + 20) or np.any(fm.bounds[0] > m1.bounds[1] + 20)):
                    continue
                mgr = trimesh.collision.CollisionManager(); mgr.add_object(fn, fm)
                d = mgr.min_distance_single(m1)
                if d <= 1e-6:
                    vol = overlap_volume(m1, fm)
                    if pair in ALLOWED and (vol < 1.0 or math.isnan(vol)):
                        d = 0.0
                    elif pair in ALLOWED:
                        d = -vol
                    else:
                        d = -max(vol, 1e-3) if not math.isnan(vol) else -1e-3
                if key not in worst or d < worst[key][0]:
                    worst[key] = (d, tgt, label, round(a, 1))
                if d < 0 and not (pair in ALLOWED and d > -1.0):
                    fails.append((n, fn, tgt, round(yc, 1), label, round(a, 1), round(d, 3)))
        # moving vs moving (relative motion between TF group and carriage/drive)
        for n1, n2 in [("cradle", "tf"), ("cradle", "carriage"), ("cradle", "tilt_crank"), ("cradle", "tilt_link"),
                       ("cell", "carriage"), ("cell", "tilt_link"), ("cell", "tilt_crank"), ("tf", "tilt_crank"),
                       ("tf", "carriage"), ("card", "carriage"), ("card", "tf"),
                       ("tilt_link", "carriage"), ("c2_crank", "carriage"), ("c2_link", "carriage"),
                       ("fpins", "carriage"), ("pin_a", "carriage"), ("pin_a", "cradle"), ("pin_a", "cell"),
                       ("pin_a", "tilt_crank"), ("fpins", "tilt_crank"),
                       # ch2: links and every screw / pin against everything else that moves
                       ("c2_crank", "c2_link"), ("c2_horn_screws", "c2_link"), ("c2_horn_screws", "carriage"),
                       ("c2_tip_pin", "carriage"), ("c2_tip_pin", "c2_drive_pin"), ("c2_drive_pin", "c2_crank"),
                       ("c2_drive_pin", "c2_horn_screws")]:
            pair = frozenset((n1, n2))
            if pair in JOINED:
                continue
            mgr = trimesh.collision.CollisionManager(); mgr.add_object(n2, mv[n2])
            d = mgr.min_distance_single(mv[n1])
            if d <= 1e-6:
                vol = overlap_volume(mv[n1], mv[n2])
                d = 0.0 if (pair in ALLOWED and (vol < 1.0 or math.isnan(vol))) else -(vol if not math.isnan(vol) else 1e-3)
            key = (n1, n2)
            if key not in worst or d < worst[key][0]:
                worst[key] = (d, tgt, label, round(a, 1))
            if d < 0:
                fails.append((n1, n2, tgt, round(yc, 1), label, round(a, 1), round(d, 3)))
    print(f"\nCOLLISION SWEEP: {len(cases)} poses ({len(TARGETS) - 1} targets × hold/upper/lower incl. "
          f"intermediate angles, home level→hold, Y travel every 6 mm in HOLD)")
    print(f"{'part':12s} {'vs':14s} {'min clearance mm':>17s}   worst case")
    for (n, fn), (d, tgt, label, a) in sorted(worst.items(), key=lambda kv: kv[1][0]):
        if d < 15:
            tag = "OVERLAP" if d < 0 else ("contact (by design)" if d == 0 else "")
            print(f"{n:12s} {fn:14s} {d:17.2f}   {tgt}/{label} {a}°  {tag}")
    print("\nDESIGN RULES (min clearance over every pose):")
    for (n1, n2), (lim, why) in RULES.items():
        d = worst.get((n1, n2), worst.get((n2, n1), (float("nan"),)))[0]
        ok = d > lim if (n1, n2) == ("cradle", "tf") else d >= lim
        print(f"  {n1:14s} {n2:14s} {d:6.2f}  {'>' if (n1, n2) == ('cradle', 'tf') else '≥'} {lim}  {'ok' if ok else 'FAIL'}   {why}")
        if not ok:
            fails.append((n1, n2, "rule", 0, why, 0, round(d, 3)))
    print("\nBASEPLATE ENVELOPE (every pose; baseplate X ±285, Y ±270, top Z 4):")
    for n in OWN:
        if n not in env:
            continue
        lo, hi = env[n]
        inside = np.all(lo[:2] >= BASE[0][:2] - 1e-6) and np.all(hi[:2] <= BASE[1][:2] + 1e-6) and lo[2] >= BASE[0][2] - 1e-6
        print(f"  {n:12s} X {lo[0]:7.1f}..{hi[0]:6.1f}  Y {lo[1]:7.1f}..{hi[1]:6.1f}  Z {lo[2]:5.1f}..{hi[2]:6.1f}  "
              f"{'ok' if inside else 'OUTSIDE BASEPLATE'}")
        if not inside:
            fails.append((n, "baseplate", "envelope", 0, "", 0, 0))
    lows = {n: env[n][0][2] - BASE[0][2] for n in ["c2_link", "c2_crank", *C2_HW] if n in env}
    lo_n = min(lows, key=lows.get)
    print(f"\nch2 linkage lowest point: {lo_n} {lows[lo_n]:.1f} mm above the tiles (rule ≥ {TILE_LIP}: "
          f"{'ok' if lows[lo_n] >= TILE_LIP else 'FAIL'})")
    if lows[lo_n] < TILE_LIP:
        fails.append((lo_n, "tiles", "lip", 0, "", 0, round(lows[lo_n], 2)))
    if fails:
        print(f"\n{len(fails)} FAILURES (overlap where none is allowed):")
        seen = set()
        for f in fails:
            k = f[:2]
            if k in seen:
                continue
            seen.add(k)
            print("   ", f)
    else:
        print("\nNo unintended overlaps.")
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


def run_assembly(meshes):
    """Insertion / access paths that the collision sweep cannot see."""
    V = echo_vals({"tie": "riser_tie_screws()", "fy": "riser_front_y()", "holes": "sh_end_post_holes()",
                   "pina": "sh_pin_a_y()"}, ["riser", "shuttle"])
    ok = True
    print("\nASSEMBLY / ACCESS PATHS")

    def clear(tool, against, label):
        hits = []
        for n, m in against.items():
            if np.any(tool.bounds[0] > m.bounds[1]) or np.any(m.bounds[0] > tool.bounds[1]):
                continue
            v = overlap_volume(tool, m)
            if math.isnan(v):                      # boolean failed: fall back to FCL distance
                mgr = trimesh.collision.CollisionManager(); mgr.add_object(n, m)
                v = 0.0 if mgr.min_distance_single(tool) > 1e-6 else float("inf")
            if not (v < 0.05):
                hits.append(f"{n} {v:.2f} mm³")
        print(f"  {'ok  ' if not hits else 'FAIL'} {label}" + ("" if not hits else "  blocked by: " + ", ".join(hits)))
        return not hits

    # 1. pin A: Ø3 dowel pushed in along −Y from outside the +Y plate to its seat
    #    (TF hung on the sled, cheeks not yet fitted); tool Ø2.8 from the seat out
    y0 = V["pina"][0]
    tool = cyl_between([A[0], y0 + 0.3, A[1]], [A[0], 80.0, A[1]], 1.4)
    ok &= clear(tool, {"tf": meshes["tf"], "cell": meshes["cell"], "cradle": meshes["cradle"],
                       "tilt_link": meshes["tilt_link"]},
                f"pin A dowel path (X {A[0]:.0f}, Z {A[1]:.0f}) from Y 80 to its seat at Y {y0} (before the +Y cheek)")
    ray = meshes["tf"].ray.intersects_location([[A[0] + 1.2, 80.0, A[1]]], [[0, -1.0, 0]], multiple_hits=True)[0]
    first = max(ray[:, 1]) if len(ray) else None
    print(f"       ray along −Y 1.2 off the pin-A axis: first TF surface at Y {first if first is not None else float('nan'):.2f} "
          f"(the Ø2.9→Ø2 seat shoulder at Y {y0}); knock-out from −Y through the Ø2")
    ok &= first is not None and first <= y0 + 0.01
    # the cheek closes the path once fitted (the dowel is a firm fit; cheek off to service)
    # 2. ch2 pivot screws from above: crank-tip screw at column 0 (tip at Y −263, outside the
    #    riser), drive-pin screw at the reject position (Y 177, outside the riser); hex-key
    #    shank Ø9 (head Ø8) straight up from the head to Z 250
    sh = G["sg_c2_sh"]
    fixed = {n: meshes[n] for n in FIXED}
    tip = np.array([C2P[0] - C2R * math.sin(math.radians(c2_psi(TARGETS["0"]))),
                    C2P[1] + C2R * math.cos(math.radians(c2_psi(TARGETS["0"])))])
    z_tip = G["sg_c2_z"][1] + sh[2]
    yc0 = TARGETS["0"]
    others = {**fixed, "carriage@col0": meshes["carriage"].copy().apply_transform(trans(y=yc0))}
    ok &= clear(cyl_between([tip[0], tip[1], z_tip + 0.2], [tip[0], tip[1], 250], 4.5), others,
                f"ch2 crank-tip shoulder screw from above at column 0 (X {tip[0]:.0f}, Y {tip[1]:.0f}, head top Z {z_tip:.0f})")
    yr = TARGETS["reject"]; pin = [C2P[0], yr + C2DY]
    z_pin = G["sg_c2_arm_z"][1] + sh[2]
    others = {**fixed, "carriage@reject": meshes["carriage"].copy().apply_transform(trans(y=yr))}
    ok &= clear(cyl_between([pin[0], pin[1], z_pin + 0.2], [pin[0], pin[1], 250], 4.5), others,
                f"ch2 drive-pin shoulder screw from above at reject (X {pin[0]:.0f}, Y {pin[1]:.0f}, head top Z {z_pin:.0f})")
    # 3. riser front tie: countersunk M3 driven along +Y from the front (Ø7 driver)
    for x, z in V["tie"]:
        ok &= clear(cyl_between([x, V["fy"] - 0.2, z], [x, -300, z], 3.5), fixed,
                    f"riser front-tie screw from the front (X {x}, Z {z})")
    # 4. end-post holes on the baseplate grid (probe): grid membership, hole open through
    #    the floor plate, plate material all round, SHCS head (Ø5.5 × 3) clear above
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
    print("  " + ("All access paths clear." if ok else "ACCESS FAILURES above."))
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
