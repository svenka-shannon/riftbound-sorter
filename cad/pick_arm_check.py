#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["trimesh", "numpy", "python-fcl", "scipy"]
# ///
"""
Swept-volume collision check for the pick arm (cad/suction_arm.scad).

Exports the arm's reference-pose parts and the REAL neighbouring parts
(asm_hopper_elevator, asm_riser, rails + motor mounts on the deck,
asm_scan_station, electronics tray) with OpenSCAD, then steps the arm through
its arc and reports the minimum clearance of every moving body (crank, two
follower links, hand, cup sled + pad, held card, vacuum-tube spoke) to every
fixed body and to the other moving bodies. Pin-in-bore joints are excluded by
design (they are bearings); everything else must stay > 0.

Usage:
  cad/pick_arm_check.py                 # pick→drop, servo step 10° + ends + fine lift
  cad/pick_arm_check.py --step 5 --full # also sweep the full servo range 0..180
  cad/pick_arm_check.py --verbose       # per-pose table

Card-offset cases (always run): the card has ±1.5 mm play in X and Y in the
91 × 66 hopper cavity, so the held card is also swept shifted +X/−X/+Y/−Y by
--card-play (default 1.5) relative to the cup, finely around the lift off the
stack. It must clear the hopper by ≥ --card-clear (default 0.3 mm) at every
pose and touch nothing else (the feeler flag is a designed light touch).
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import trimesh
from trimesh.collision import CollisionManager

CAD = Path(__file__).resolve().parent
ARM = CAD / "suction_arm.scad"

OBST_SCAD = """
use <{cad}/machine_frame.scad>
use <{cad}/hopper.scad>
use <{cad}/hopper_elevator.scad>
use <{cad}/riser.scad>
use <{cad}/conveyor_rail.scad>
use <{cad}/motor_mount.scad>
use <{cad}/scanner_hood.scad>
use <{cad}/electronics_tray.scad>
obst = "hopper";
zp = hopper_zp_max() - 10;   // plate well below; the top card is the card_stack stand-in
if (obst == "hopper") translate(hopper_machine_origin()) {{
    hopper_body(); hopper_cap(); hopper_carriage(zp); hopper_plate(zp);
    hw_rods(); hw_screw(); hw_coupler(); hw_nut(zp); hw_bushings(zp); hw_motor();
    hw_sw_bottom_body(); hw_sw_top_body(); hw_sw_bottom_roller(); hw_sw_top_roller();
}}
if (obst == "flag") translate(hopper_machine_origin()) hopper_flag(hopper_phi_rest());
if (obst == "riser") asm_riser();
if (obst == "rails")
    for (side = [-1, 1]) translate([frame_belt_x0(), side * frame_rail_in(), frame_deck_z()])
        mirror([0, side < 0 ? 1 : 0, 0]) {{
            rail_half(add_shaft_far = false, motor_mount = (side < 0));
            translate([125, 0, 0]) rail_half(add_shaft_far = true, motor_mount = (side < 0));
        }}
if (obst == "motor_mounts")
    for (x = frame_roller_x()) translate([x, -frame_rail_in(), frame_deck_z()]) mirror([0, 1, 0])
        translate([0, rail_boss_face_y(), 0]) {{ motor_mount(); motor_mount_coupling(); motor_mount_n20(); }}
if (obst == "scan_station") asm_scan_station();
if (obst == "etray") translate([-150, 80, frame_base_top()]) electronics_tray();
"""

ARM_PARTS = ["head", "tower", "servo", "gpin_b", "gpin_c", "crank", "link_b", "link_c",
             "hand", "hpin_a", "hpin_b", "hpin_c", "sled", "card"]
OBSTACLES = ["hopper", "flag", "riser", "rails", "motor_mounts", "scan_station", "etray"]


def run_scad(src: Path, out: Path, defs: dict) -> str:
    cmd = ["openscad", "--backend=manifold", "--export-format", "stl", "-o", str(out)]
    for k, v in defs.items():
        cmd += ["-D", f'{k}="{v}"']
    cmd.append(str(src))
    r = subprocess.run(cmd, capture_output=True, text=True)
    log = r.stdout + r.stderr
    if r.returncode != 0 or not out.exists():
        sys.exit(f"OpenSCAD failed for {src.name} {defs}:\n{log}")
    return log


def capsule_chain(pts: np.ndarray, r: float) -> trimesh.Trimesh:
    parts = []
    for a, b in zip(pts[:-1], pts[1:]):
        seg = trimesh.creation.cylinder(radius=r, segment=[a, b], sections=12)
        parts.append(seg)
        parts.append(trimesh.creation.icosphere(subdivisions=1, radius=r).apply_translation(b))
    return trimesh.util.concatenate(parts)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--step", type=float, default=10.0, help="servo-angle step in degrees (default 10)")
    ap.add_argument("--full", action="store_true", help="also sweep the full servo range 0..180")
    ap.add_argument("--verbose", action="store_true", help="print the per-pose table")
    ap.add_argument("--top", type=int, default=14, help="how many closest pairs to list (default 14)")
    ap.add_argument("--workdir", type=Path, default=None, help="keep STLs here (default: temp dir)")
    ap.add_argument("--card-play", type=float, default=1.5, help="card X/Y play in the hopper cavity (default 1.5)")
    ap.add_argument("--card-clear", type=float, default=0.3, help="min card-to-hopper clearance (default 0.3)")
    args = ap.parse_args()

    work = args.workdir or Path(tempfile.mkdtemp(prefix="pick_arm_check_"))
    work.mkdir(parents=True, exist_ok=True)

    # ---- export arm parts (also grabs the derived geometry) ----
    meshes = {}
    geo = None
    for p in ARM_PARTS:
        out = work / f"arm_{p}.stl"
        log = run_scad(ARM, out, {"part": f"ref_{p}"})
        m = re.search(r"PICK_ARM_JSON (\{.*\})", log)
        if m and geo is None:
            geo = json.loads(m.group(1))
        meshes[p] = trimesh.load(out)
    obst_src = work / "obstacles.scad"
    obst_src.write_text(OBST_SCAD.format(cad=CAD))
    for o in OBSTACLES:
        out = work / f"obst_{o}.stl"
        run_scad(obst_src, out, {"obst": o})
        meshes[o] = trimesh.load(out)
    g = geo
    R, px, pz, h = g["R"], g["px"], g["pz"], g["h_cup"]
    card_z, card_t = g["card_z"], g["card_t"]

    # simple stand-ins for things that are not separate parts
    meshes["belt_top"] = trimesh.creation.box(bounds=[[-165, -30, card_z - 2.0], [85, 30, card_z]])
    meshes["card_stack"] = trimesh.creation.box(bounds=[[g["pick_x"] - 44, -31.5, card_z - 6], [g["pick_x"] + 44, 31.5, card_z]])
    meshes["baseplate"] = trimesh.creation.box(bounds=[[-285, -270, 0], [285, 270, 4]])
    static_obst = OBSTACLES + ["belt_top", "card_stack", "baseplate"]
    fixed_arm = ["head", "tower", "servo", "gpin_b", "gpin_c"]

    mgr = {}
    for name in fixed_arm + static_obst:
        cm = CollisionManager()
        cm.add_object(name, meshes[name])
        mgr[name] = cm

    # ---- static check: fixed arm parts vs the machine ----
    print("=" * 78)
    print(f"PICK ARM sweep check   R {R:.2f}  pivot X {px:.2f} Z {pz:.2f}   h_cup {h}")
    print(f"servo pick {g['s_pick']:.2f}  drop {g['s_drop']:.2f}  park {g['s_park']}   STLs in {work}")
    print("=" * 78)
    print("STATIC (fixed arm parts vs machine), min clearance mm:")
    static_res = {}
    for f in fixed_arm:
        for o in static_obst:
            if o == "baseplate" and f == "tower":
                continue            # the foot stands on it
            if o in ("card_stack", "belt_top"):
                continue
            d = mgr[o].min_distance_single(meshes[f])
            static_res[(f, o)] = d
    for (f, o), d in sorted(static_res.items(), key=lambda kv: kv[1])[:8]:
        print(f"  {f:8s} vs {o:14s} {d:8.2f}")

    # ---- moving bodies at a servo angle ----
    def theta(s):
        return g["th_mid"] + (s - 90.0)

    def comp_for(th, card):
        lip = pz + R * np.sin(np.radians(th)) - h
        cx = px + R * np.cos(np.radians(th))
        if abs(cx - g["pick_x"]) < 5:
            return max(0.0, card_z - lip)
        if card and abs(cx - g["drop_x"]) < 5:
            return max(0.0, card_z + card_t - lip)
        return 0.0

    def rot(th, pivot):
        return trimesh.transformations.rotation_matrix(np.radians(-th), [0, 1, 0], pivot)

    def poses(s):
        th = theta(s)
        c = min(comp_for(th, True), g["sl_stroke"])
        T = {}
        T["crank"] = rot(th, [px, 0, pz])
        T["link_b"] = rot(th, [px + g["gB"][0], 0, pz + g["gB"][1]])
        T["link_c"] = rot(th, [px + g["gC"][0], 0, pz + g["gC"][1]])
        hand = trimesh.transformations.translation_matrix([R * np.cos(np.radians(th)) - R, 0, R * np.sin(np.radians(th))])
        for k in ("hand", "hpin_a", "hpin_b", "hpin_c"):
            T[k] = hand
        T["sled"] = trimesh.transformations.translation_matrix([R * np.cos(np.radians(th)) - R, 0, R * np.sin(np.radians(th)) + c])
        T["card"] = T["sled"]
        # vacuum tube spoke: hollow A' pin back end → anchor on the servo axis
        a_prime = np.array([px + R * np.cos(np.radians(th)), pz + R * np.sin(np.radians(th))])
        A = np.array([px, pz])
        t = np.linspace(0.03, 0.95, 32)
        s3 = 3 * t**2 - 2 * t**3
        xz = A + np.outer(1 - s3, a_prime - A)
        y = g["tube_y0"] + (g["tube_y1"] - g["tube_y0"]) * t
        pts = np.column_stack([xz[:, 0], y, xz[:, 1]])
        return th, c, T, capsule_chain(pts, 2.0)

    moving = ["crank", "link_b", "link_c", "hand", "hpin_a", "hpin_b", "hpin_c", "sled", "card", "tube"]
    # pairs that are bearings / intended contact (excluded)
    joint = {("crank", "servo"), ("crank", "hpin_a"), ("link_b", "gpin_b"), ("link_b", "hpin_b"),
             ("link_c", "gpin_c"), ("link_c", "hpin_c"), ("hand", "hpin_a"), ("hand", "hpin_b"),
             ("hand", "hpin_c"), ("hpin_a", "hpin_b"), ("hpin_a", "hpin_c"), ("hpin_b", "hpin_c"),
             ("hand", "sled"), ("hand", "card"), ("sled", "card"), ("hpin_a", "tube"),
             ("hpin_a", "sled"), ("hpin_a", "card"), ("hpin_b", "sled"), ("hpin_c", "sled"),
             ("hpin_b", "card"), ("hpin_c", "card")}

    def excluded(a, b, c, th):
        if (a, b) in joint or (b, a) in joint:
            return True
        # cup on the card on the stack at pick (intended contact)
        if {a, b} & {"card_stack"} and {a, b} & {"sled", "card"} and abs(th - g["th_p"]) < 6:
            return True
        # flag: designed light touch — it rests on the held card's -Y margin and is
        # pushed up/out by the card (reported separately below). Cup, sled, hand
        # and links are still checked against it.
        if {a, b} == {"flag", "card"}:
            return True
        return False

    def sweep(angles, label):
        worst = {}
        rows = []
        for s in angles:
            th, c, T, tube = poses(s)
            bodies = {k: (meshes[k], T[k]) for k in moving if k != "tube"}
            bodies["tube"] = (tube, np.eye(4))
            row_min = (1e9, "")
            for i, a in enumerate(moving):
                ma, Ta = bodies[a]
                # vs fixed + static
                for o in fixed_arm + static_obst:
                    if excluded(a, o, c, th):
                        continue
                    if a == "tube" and o in ("tower",):
                        continue    # the tube ends in the anchor bore
                    d = mgr[o].min_distance_single(ma, transform=Ta)
                    key = (a, o)
                    if key not in worst or d < worst[key][0]:
                        worst[key] = (d, s)
                    if d < row_min[0]:
                        row_min = (d, f"{a}/{o}")
                # vs other moving
                for b in moving[i + 1:]:
                    if excluded(a, b, c, th):
                        continue
                    mb, Tb = bodies[b]
                    cm = CollisionManager()
                    cm.add_object(b, mb, transform=Tb)
                    d = cm.min_distance_single(ma, transform=Ta)
                    key = (a, b)
                    if key not in worst or d < worst[key][0]:
                        worst[key] = (d, s)
                    if d < row_min[0]:
                        row_min = (d, f"{a}/{b}")
            lip = pz + R * np.sin(np.radians(th)) - h + c
            cup_x = px + R * np.cos(np.radians(th))
            rows.append((s, th, cup_x, lip, c, row_min))
        print(f"\n{label}: {len(angles)} poses")
        if args.verbose:
            print("  servo   theta   cup X    lip Z   comp   min gap  (pair)")
            for s, th, cx, lip, c, (d, pr) in rows:
                print(f"  {s:6.2f} {th:7.2f} {cx:8.2f} {lip:8.2f} {c:5.2f} {d:8.2f}  {pr}")
        hits = [(k, v) for k, v in worst.items() if v[0] <= 0.0]
        print("  closest pairs over the sweep (mm, at servo angle):")
        for (a, b), (d, s) in sorted(worst.items(), key=lambda kv: kv[1][0])[:args.top]:
            print(f"    {a:7s} vs {b:14s} {d:8.2f}  @ {s:6.2f}")
        if hits:
            print("  COLLISIONS:")
            for (a, b), (d, s) in hits:
                print(f"    {a} vs {b} @ servo {s:.2f}")
        else:
            print("  no collisions")
        return worst, hits

    s_lo, s_hi = g["s_drop"], g["s_pick"]
    angles = sorted(set([s_lo, s_hi, 90.0] + list(np.arange(np.ceil(s_lo / args.step) * args.step, s_hi, args.step))
                        + list(np.linspace(s_hi - 8, s_hi, 9)) + list(np.linspace(s_lo, s_lo + 6, 4))))
    worst, hits = sweep(angles, "WORKING ARC (pick ↔ drop)")
    if args.full:
        _, hits_full = sweep(sorted(set(list(np.arange(0, 181, args.step)) + [180.0])), "FULL SERVO RANGE 0..180")
        hits = hits + hits_full

    # ---- held card offset in the hopper (±play in X and Y) ----
    # The card is picked wherever it lies in the cavity, so relative to the cup
    # it can sit ±play off-centre. The lift is 2° off vertical (+X drift), so the
    # +X case is the critical one. Fine steps over the lift off the stack, plus
    # the whole working arc, vs every static obstacle.
    lift = sorted(set(list(np.arange(s_hi, s_hi - 20, -0.25)) + angles))
    play = args.card_play
    print(f"\nHELD CARD OFFSET in the hopper (play ±{play}), {len(lift)} poses, need ≥ {args.card_clear} mm to the hopper:")
    off_fail = []
    for dx, dy in [(0.0, 0.0), (play, 0.0), (-play, 0.0), (0.0, play), (0.0, -play)]:
        Toff = trimesh.transformations.translation_matrix([dx, dy, 0.0])
        best = {}
        for s in lift:
            th, c, T, _ = poses(s)
            Tc = T["card"] @ Toff
            for o in static_obst + fixed_arm:
                if excluded("card", o, c, th) or o == "flag":
                    continue
                d = mgr[o].min_distance_single(meshes["card"], transform=Tc)
                if o not in best or d < best[o][0]:
                    best[o] = (d, s)
        hd, hs = best["hopper"]
        others = sorted(((d, o, s) for o, (d, s) in best.items() if o != "hopper"))[:2]
        ok = hd >= args.card_clear - 1e-6 and all(d > 0 for d, _, _ in others)
        lab = f"X{dx:+.1f} Y{dy:+.1f}"
        print(f"  {'OK ' if ok else 'BAD'} card {lab}: hopper min {hd:5.2f} @ servo {hs:6.2f}; next closest "
              + ", ".join(f"{o} {d:.2f} @ {s:.2f}" for d, o, s in others))
        if not ok:
            off_fail.append(lab)
    if off_fail:
        print("  CARD-OFFSET FAILURES:", off_fail)

    # flag (intended contact) report
    print("\nheld card vs hopper feeler flag (intended light touch near pick):")
    for s in np.linspace(s_hi - 6, s_hi, 7):
        th, c, T, _ = poses(s)
        d = mgr["flag"].min_distance_single(meshes["card"], transform=T["card"])
        lip = pz + R * np.sin(np.radians(th)) - h + c
        print(f"  servo {s:6.2f}  card top Z {lip:7.2f}  card-flag {d:6.2f}")
    sys.exit(1 if hits or off_fail else 0)


if __name__ == "__main__":
    main()
