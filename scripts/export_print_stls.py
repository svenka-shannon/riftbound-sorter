#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "trimesh", "manifold3d", "scipy", "networkx", "rtree"]
# ///
"""Export every printable part as a binary STL already in its print orientation,
sitting on Z=0, and zip them with BOM.md's printed-parts table as PRINT_GUIDE.md.

    scripts/export_print_stls.py [OUTDIR]        (default /tmp/riftbound-v2-stl)

Fails (non-zero) if any part does not export with Status NoError or is not
watertight. Orientation list mirrors the audit print checker.
"""
import concurrent.futures as cf, subprocess, sys, zipfile, re
from pathlib import Path
import numpy as np, trimesh
from trimesh.transformations import rotation_matrix as R

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "cad"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/riftbound-v2-stl")
OUT.mkdir(parents=True, exist_ok=True)
W = OUT / "_wrappers"; W.mkdir(exist_ok=True)
X, Y = [1, 0, 0], [0, 1, 0]; d = np.pi / 2
JOBS = {}
def job(name, args, ori=None): JOBS[name] = (args, ori)
def wrap(name, body, uses):
    f = W / f"w_{name}.scad"
    f.write_text("".join(f"use <{C}/{u}.scad>\n" for u in uses) + body + "\n")
    return [str(f)]
job("baseplate_tile", [f"{C}/baseplate_tile.scad"])
job("baseplate_keys", ["-D", 'part="keys"', f"{C}/baseplate_tile.scad"])
job("electronics_tray", [f"{C}/electronics_tray.scad"])
for p in ("riser_a", "riser_b"): job(p, ["-D", f'part="{p}"', f"{C}/riser.scad"], R(np.pi, X))
for p, o in (("back1", R(d, X)), ("back2", R(d, X)), ("front1", R(-d, X)), ("front2", R(-d, X))):
    job("rail_" + p, ["-D", f'part="{p}"', f"{C}/conveyor_rail.scad"], o)
job("roller", [f"{C}/conveyor_roller.scad"])
job("race_spacer", wrap("race_spacer", "race_spacer();", ["conveyor_roller"]))
job("motor_mount", [f"{C}/motor_mount.scad"])
job("slide_bed", [f"{C}/slide_bed.scad"], R(np.pi, X))
for p in ("guide_back", "guide_front", "clip"): job("cg_" + p, ["-D", f'part="{p}"', f"{C}/card_guide.scad"])
job("hood", ["-D", 'part="hood"', f"{C}/scanner_hood.scad"])
job("cam_bracket", ["-D", "print_orient=true", f"{C}/camera_bracket.scad"])
for p in ("body", "cap", "carriage", "plate", "flag"): job("hopper_" + p, ["-D", f'part="{p}"', f"{C}/hopper.scad"])
for p in ("base", "cap", "sleeve", "pad", "valve_clip"): job("pump_" + p, ["-D", f'part="{p}"', f"{C}/pump_bracket.scad"])
for p in ("head", "tower", "crank", "link", "hand", "sled", "sleeves"): job("arm_" + p, ["-D", f'part="{p}"', f"{C}/suction_arm.scad"])
for n, b in (("tray_A", "tray_floor_section(0, true, false);"), ("tray_B", "tray_floor_section(2, false, true);"),
             ("tray_C", "tray_floor_section(4, true, false);"), ("tray_D", "tray_floor_section(6, false, true);"),
             ("tray_shelf", "floor_shelf_half();")):
    job(n, wrap(n, b, ["sorting_tray"]))
SHO = {"sled": R(-d, X), "cheek_pos": R(-d, X), "cheek_neg": R(d, X), "tilt_crank": R(d, X), "tilt_link": R(d, X),
       "rbar_neg": R(-d, Y), "rbar_pos": R(-d, Y)}
for p in ("cradle", "tilt_frame", "sled", "cheek_neg", "cheek_pos", "tilt_crank", "tilt_link", "c2_crank", "c2_link",
          "rbar_neg", "rbar_pos", "end_post_neg", "end_post_pos"):
    job("sh_" + p, ["-D", f'part="{p}"', f"{C}/shuttle.scad"], SHO.get(p))
for p in ("ramp_neg", "ramp_pos"): job(p, ["-D", f'part="{p}"', f"{C}/lower_ramp.scad"])
job("reject_bin", ["-D", 'part="reject_bin"', f"{C}/reject_bin.scad"])

def run(name):
    args, ori = JOBS[name]
    raw = W / f"{name}.raw.stl"
    r = subprocess.run(["openscad", "--backend=manifold", "--export-format", "binstl", "-o", str(raw)] + args,
                       capture_output=True, text=True)
    ok = r.returncode == 0 and ("Status:     NoError" in r.stderr or "PolySet" in r.stderr or "Status" not in r.stderr)
    if not ok or "ERROR" in r.stderr:
        return name, False, r.stderr[-400:]
    m = trimesh.load(raw, force="mesh")
    if ori is not None: m.apply_transform(ori)
    m.apply_translation(-m.bounds[0])
    ext = m.bounds[1]
    m.export(OUT / f"{name}.stl")
    raw.unlink()
    wt = m.is_watertight
    fits = bool((ext <= 256).all())
    return name, wt and fits, f"{ext[0]:.0f}x{ext[1]:.0f}x{ext[2]:.0f} mm, watertight={wt}, fits_bed={fits}"

if __name__ == "__main__":
    bad = []
    with cf.ThreadPoolExecutor(6) as ex:
        for name, ok, info in ex.map(run, sorted(JOBS)):
            print(("OK  " if ok else "BAD ") + f"{name:22s} {info}")
            if not ok: bad.append(name)
    bom = (ROOT / "BOM.md").read_text()
    m = re.search(r"## Printed parts.*?(?=\n## )", bom, re.S)
    (OUT / "PRINT_GUIDE.md").write_text(
        "# Riftbound Card Sorter v2 — print files\n\nEvery STL is already in its print orientation, on Z=0.\n"
        "Quantities, materials and supports: table below (from BOM.md). Full build: docs/ASSEMBLY.md.\n\n"
        + (m.group(0) if m else "(see BOM.md)") + "\n")
    z = OUT.parent / f"{OUT.name}.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUT.glob("*.stl")) + [OUT / "PRINT_GUIDE.md"]:
            zf.write(f, f.name)
    print(f"\n{len(JOBS) - len(bad)}/{len(JOBS)} parts OK -> {z} ({z.stat().st_size // 1024} KB)")
    sys.exit(1 if bad else 0)
