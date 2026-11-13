#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy-stl"]
# ///
"""Export every option B printed part as an STL in print orientation, check it
fits a 256 mm bed, report volume, and zip them with a print list.

    cad_b/export_b.py [OUTDIR]     (default /tmp/option-b-stl)
"""
import subprocess, sys, zipfile
from pathlib import Path
from stl import mesh

HERE = Path(__file__).resolve().parent
# part: (qty, material, rotation [x,y,z] for printing, note)
PARTS = {
    "bin":           (7, "PLA",  [0, 0, 0],   "floor down"),
    "hopper":        (1, "PLA",  [0, 0, 0],   "floor down"),
    "cell_block":    (1, "PLA",  [0, 0, 0],   ""),
    "bed":           (1, "PLA",  [180, 0, 0], "top face down"),
    "yaw_base":      (1, "PETG", [0, 0, 0],   "plate down"),
    "roller_sleeve": (4, "PETG", [0, 0, 0],   ""),
    "turntable":     (1, "PETG", [0, 0, 0],   "plate down, no supports"),
    "link_a":        (1, "PETG", [90, 0, 0],  "100 % infill, flat"),
    "link_b":        (1, "PETG", [90, 0, 0],  "100 % infill, flat"),
    "sleeve":        (3, "PETG", [0, 0, 0],   ""),
    "hand":          (1, "PETG", [90, 0, 0],  "pivot face down"),
    "slider":        (1, "PETG", [0, 0, 0],   "upright"),
    "cap":           (1, "PETG", [0, 0, 0],   ""),
    "tower_post":    (1, "PLA",  [0, 90, 0],  "lying on a side face"),
    "boom":          (1, "PLA",  [0, 0, 0],   "boom bottom down, sleeve up"),
    "ring_holder":   (1, "PLA",  [0, 0, 0],   "may need supports under the ring cradle"),
    "cable_post":    (1, "PLA",  [0, 0, 0],   ""),
    "foot":          (4, "PLA",  [0, 0, 0],   ""),
}

def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/option-b-stl"); out.mkdir(parents=True, exist_ok=True)
    rows, bad, grams = [], 0, 0.0
    for name, (qty, mat, rot, note) in PARTS.items():
        stl = out / f"b_{name}.stl"
        wrapper = out / f"_{name}.scad"
        wrapper.write_text(f'use <{HERE}/b_parts.scad>\ninclude <{HERE}/b_params.scad>\npart="none";\n'
                           f'rotate({rot}) {name}();\n')
        r = subprocess.run(["openscad", "--backend=manifold", "-o", str(stl), str(wrapper)], capture_output=True, text=True)
        wrapper.unlink()
        if r.returncode or not stl.exists():
            print(f"FAIL {name}: {r.stderr.strip()}"); bad += 1; continue
        m = mesh.Mesh.from_file(str(stl))
        m.translate(-m.min_); m.save(str(stl))              # on Z = 0, at the origin
        ext = m.max_ - m.min_
        vol = m.get_mass_properties()[0] / 1000
        fits = ext[0] <= 256 and ext[1] <= 256 and ext[2] <= 256
        if not fits: bad += 1
        grams += vol * 1.24 * qty
        rows.append(f"| {name} | {qty} | {mat} | {ext[0]:.0f} x {ext[1]:.0f} x {ext[2]:.0f} | {vol:.1f} | {note} |")
        print(f"{'OK  ' if fits else 'BIG '}{name:14s} x{qty} {mat:4s} {ext[0]:.0f}x{ext[1]:.0f}x{ext[2]:.0f} mm {vol:.1f} cm3")
    guide = out / "PRINT_LIST.md"
    guide.write_text("# Option B print list\n\n| Part | Qty | Material | Size (mm) | Solid cm3 | Note |\n|---|---|---|---|---|---|\n"
                     + "\n".join(rows) + f"\n\nSolid total ~{grams:.0f} g (printed with infill: less).\n")
    z = out / "option-b-stl.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(out.glob("b_*.stl")): zf.write(f, f.name)
        zf.write(guide, guide.name)
    print(f"solid total ~{grams:.0f} g; zip: {z}")
    sys.exit(1 if bad else 0)

main()
