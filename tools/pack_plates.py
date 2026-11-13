#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["trimesh", "numpy", "networkx", "scipy", "rectpack", "lxml", "pillow"]
# ///
"""Pack the Riftbound sorter STLs into ready-to-print build plates (one 3MF per plate).

Usage: pack_plates.py STL_DIR OUT_DIR [--bed 256] [--margin 4] [--gap 6]

Parts are grouped by material + print settings (GROUPS below), so every object on a
plate prints with one profile. Within a group, parts are bin-packed (90-degree
rotation allowed) into as few plates as possible. Writes plate_NN_<group>.3mf,
plate_NN_<group>.png (top view) and PLATES.md (what to load, settings, what's on it).
"""
import argparse, os, sys
from collections import Counter
import numpy as np
import trimesh
from rectpack import newPacker, MaxRectsBssf, MaxRectsBl, MaxRectsBaf, MaxRectsBlsf, SkylineBlWm, SkylineMwfl, GuillotineBssfSas
from PIL import Image, ImageDraw

# (key, title, filament, settings, [(stl, qty), ...] [, times to print the plate])
GROUPS = [
    ("tile", "PLA, baseplate tile", "PLA",
     "0.20 mm layers, 4 walls, 40 % infill, flat with the key pockets facing up. No supports.",
     [("baseplate_tile", 1)], 9),
    ("pla_structural", "PLA, structural", "PLA",
     "0.20 mm layers, 4 walls, 40 % infill. No supports.",
     [("baseplate_keys", 1), ("rail_back1", 1), ("rail_back2", 1),
      ("rail_front1", 1), ("rail_front2", 1), ("tray_A", 1), ("tray_B", 1), ("tray_C", 1),
      ("tray_D", 1), ("tray_shelf", 2), ("sh_rbar_neg", 1), ("sh_rbar_pos", 1),
      ("cam_bracket", 1), ("hopper_body", 1), ("hopper_cap", 1), ("hopper_carriage", 1),
      ("hopper_plate", 1), ("hopper_flag", 1)]),
    ("pla_light", "PLA, light", "PLA",
     "0.20 mm layers, 3 walls, 25 % infill. No supports.",
     [("electronics_tray", 1), ("slide_bed", 1), ("reject_bin", 1)]),
    ("pla_riser", "PLA, riser", "PLA (or PETG)",
     "0.24 mm layers, 3 walls, 15 % gyroid. Printed upside down as exported. No supports.",
     [("riser_a", 1), ("riser_b", 1)]),
    ("pla_ramp", "PLA, lower ramp", "PLA",
     "**0.16 mm layers**, 3 walls, 15 % infill, bridge fan 100 %. Upright as exported. Sand the lanes with 600 grit.",
     [("ramp_neg", 1), ("ramp_pos", 1)]),
    ("pla_cradle", "PLA, cradle", "PLA",
     "**0.12 mm layers**, 3 walls, 15 % infill, ironing on top surface, **brim on**.",
     [("sh_cradle", 1)]),
    ("petg_general", "PETG, mechanism", "PETG",
     "0.20 mm layers, 4 walls, 40 % infill. No supports.",
     [("arm_head", 1), ("arm_tower", 1), ("arm_hand", 1), ("arm_sled", 1), ("arm_sleeves", 1),
      ("motor_mount", 2), ("sh_tilt_frame", 1), ("sh_sled", 1), ("sh_cheek_neg", 1),
      ("sh_cheek_pos", 1), ("sh_end_post_neg", 1), ("sh_end_post_pos", 1), ("cg_clip", 4),
      ("pump_base", 1), ("pump_cap", 1), ("pump_valve_clip", 1)]),
    ("petg_strong", "PETG, cranks/links/rollers", "PETG",
     "0.20 mm layers, 5 walls, **100 % infill**. No supports.",
     [("arm_crank", 1), ("arm_link", 1), ("sh_tilt_crank", 1), ("sh_tilt_link", 1),
      ("sh_c2_crank", 1), ("sh_c2_link", 1), ("roller", 2), ("race_spacer", 4)]),
    ("black", "Black, scanner hood + card guides", "**Black** PETG or PLA",
     "0.20 mm layers, 3 walls, 20 % infill, **8-10 mm brim** (the hood is 101 mm tall on a small roof), outer walls <= 60 mm/s.",
     [("hood", 1), ("cg_guide_back", 1), ("cg_guide_front", 1)]),
    ("tpu", "TPU (optional)", "TPU 95A",
     "Optional: skip this plate if you use a neoprene strip instead. Default TPU profile.",
     [("pump_sleeve", 1), ("pump_pad", 1)]),
]

COLORS = ["#E2742B", "#2E78C9", "#3A9E95", "#C73A3F", "#F0BE2A", "#7A5BC4", "#5C6B7A", "#B07A45"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stl_dir"); ap.add_argument("out_dir")
    ap.add_argument("--bed", type=float, default=256.0)
    ap.add_argument("--margin", type=float, default=4.0, help="keep-out at the bed edge, mm")
    ap.add_argument("--gap", type=float, default=6.0, help="space between parts, mm")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    listed = {s for g in GROUPS for s, _ in g[4]}
    on_disk = {f[:-4] for f in os.listdir(a.stl_dir) if f.endswith(".stl")}
    if on_disk - listed or listed - on_disk:
        sys.exit(f"STL set mismatch. Not grouped: {sorted(on_disk - listed)}  Missing: {sorted(listed - on_disk)}")

    usable = a.bed - 2 * a.margin
    plates, plate_no = [], 0
    for key, title, filament, settings, items, *rep in GROUPS:
        repeat = rep[0] if rep else 1
        meshes, rects = {}, []
        for stl, qty in items:
            m = trimesh.load(os.path.join(a.stl_dir, stl + ".stl"))
            m.apply_translation(-m.bounds[0])           # bbox min at origin, keeps Z=0 on bed
            meshes[stl] = m
            dx, dy = m.extents[0], m.extents[1]
            if min(dx, dy) > usable or max(dx, dy) > usable:
                sys.exit(f"{stl} ({dx:.0f} x {dy:.0f}) does not fit a {usable:.0f} mm usable bed")
            for i in range(qty):
                rects.append((dx + a.gap, dy + a.gap, (stl, i)))
        packed = best_pack(rects, usable + a.gap)
        if len(packed) != len(rects):
            sys.exit(f"{key}: packed {len(packed)} of {len(rects)}")
        by_bin = {}
        for b, x, y, w, h, rid in packed:
            by_bin.setdefault(b, []).append((x, y, w, h, rid))
        for b in sorted(by_bin):
            plate_no += 1
            scene = trimesh.Scene()
            placed = []
            for x, y, w, h, (stl, i) in by_bin[b]:
                m = meshes[stl].copy()
                dx, dy = m.extents[0], m.extents[1]
                if abs((w - a.gap) - dx) > 1e-6 or abs((h - a.gap) - dy) > 1e-6:   # rotated 90
                    m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 0, 1]))
                    m.apply_translation(-m.bounds[0])
                m.apply_translation([a.margin + x, a.margin + y, 0])
                assert m.bounds[1][0] <= a.bed - a.margin + 1e-6 and m.bounds[1][1] <= a.bed - a.margin + 1e-6
                scene.add_geometry(m, node_name=f"{stl}_{i + 1}", geom_name=f"{stl}_{i + 1}")
                placed.append((stl, m))
            base = f"plate_{plate_no:02d}_{key}"
            scene.export(os.path.join(a.out_dir, base + ".3mf"))
            draw_preview(placed, a.bed, os.path.join(a.out_dir, base + ".png"), f"Plate {plate_no}: {title}")
            hmax = max(m.bounds[1][2] for _, m in placed)
            plates.append((plate_no, base, title, filament, settings, Counter(s for s, _ in placed), hmax, repeat))

    write_md(plates, a)
    print(f"{len(plates)} plates written to {a.out_dir}")
    for n, base, title, _f, _s, cnt, h, rep in plates:
        times = f" PRINT x{rep}" if rep > 1 else ""
        print(f"  {n:2d} {title:32s} {sum(cnt.values()):3d} objects, max height {h:5.1f}{times}  {dict(cnt)}")


def best_pack(rects, side):
    """Try several packers and sort orders; keep the one with the fewest plates, then the
    fullest last plate is NOT preferred: ties go to the most even split (less risk per plate)."""
    best = None
    orders = [lambda r: -r[0] * r[1], lambda r: -max(r[0], r[1]), lambda r: -(r[0] + r[1])]
    for algo in (MaxRectsBssf, MaxRectsBl, MaxRectsBaf, MaxRectsBlsf, SkylineBlWm, SkylineMwfl, GuillotineBssfSas):
        for order in orders:
            pk = newPacker(pack_algo=algo, rotation=True)
            for w, h, rid in sorted(rects, key=order):
                pk.add_rect(w, h, rid)
            for _ in rects:
                pk.add_bin(side, side)
            pk.pack()
            res = pk.rect_list()
            if len(res) != len(rects):
                continue
            counts = Counter(r[0] for r in res)
            score = (len(counts), -min(counts.values()))
            if best is None or score < best[0]:
                best = (score, res)
    return best[1] if best else []


def draw_preview(placed, bed, path, label):
    s = 3
    img = Image.new("RGB", (int(bed * s), int(bed * s) + 40), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 40, bed * s - 1, bed * s + 39], outline="black", width=2)
    d.text((8, 12), label, fill="black")
    names = sorted({stl for stl, _ in placed})
    for stl, m in placed:
        col = COLORS[names.index(stl) % len(COLORS)]
        b = m.bounds
        x0, y0, x1, y1 = b[0][0] * s, (bed - b[1][1]) * s + 40, b[1][0] * s, (bed - b[0][1]) * s + 40
        d.rectangle([x0, y0, x1, y1], outline=col, width=2)
        # footprint silhouette: project faces touching the bed
        d.text((x0 + 4, y0 + 4), stl, fill=col)
    img.save(path)


def write_md(plates, a):
    lines = [
        "# Riftbound sorter - build plates",
        "",
        f"Every printed part, packed onto {len(plates)} build plates for a {a.bed:.0f} x {a.bed:.0f} mm bed "
        "(Bambu P1S / X1 / A1, Prusa MK4, any 256 mm bed). Each plate holds parts that share one "
        "material and one set of print settings, so you load one file, pick the filament and the settings "
        "below, slice and print. Parts are already in their print orientation; don't rotate them in Z.",
        "",
        "How to use: open the `.3mf` in Bambu Studio / OrcaSlicer / PrusaSlicer (if asked, load geometry only). "
        "The parts are already arranged; you can re-run auto-arrange if you like. The `.png` next to each "
        "file is a top view of the plate.",
        "",
        "| Plate | File | Print | Filament | Settings | Contents |",
        "|---|---|---|---|---|---|",
    ]
    for n, base, title, filament, settings, cnt, h, rep in plates:
        contents = ", ".join(f"{s} x{c}" if c > 1 else s for s, c in sorted(cnt.items()))
        times = f"**{rep} times**" if rep > 1 else "once"
        lines.append(f"| {n} | `{base}.3mf` | {times} | {filament} | {settings} | {contents} (tallest {h:.0f} mm) |")
    total = sum(p[7] for p in plates)
    lines += ["", f"That is {len(plates)} plate files and **{total} print jobs** in all."]
    lines += ["", "Notes:",
              "- `sh_end_post_neg` comes with a built-in break-away support ladder under its ledge: snap it out after printing.",
              "- The 9 tiles are optional: BOM.md (cost-down option 1) shows how to drill the backing board from a template instead. That saves about 1.1 kg of PLA and about 30 h of printing.",
              "- Full per-part notes (orientation, inserts, sanding) are in PRINT_GUIDE.md.",
              "", "Totals: 9 baseplate tiles, 24 tile keys (one part), and every other part at the quantity "
              "in PRINT_GUIDE.md. The 2 arm links and the 4 arm sleeves are each one file.", ""]
    open(os.path.join(a.out_dir, "PLATES.md"), "w").write("\n".join(lines))


if __name__ == "__main__":
    main()
