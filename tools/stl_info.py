#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["trimesh", "numpy", "networkx", "scipy"]
# ///
import sys, glob, os, trimesh
for p in sorted(glob.glob(os.path.join(sys.argv[1], "*.stl"))):
    m = trimesh.load(p)
    b = m.bounds; d = b[1]-b[0]
    bodies = len(m.split(only_watertight=False))
    print(f"{os.path.basename(p):24s} {d[0]:6.1f} x {d[1]:6.1f} x {d[2]:6.1f}  zmin={b[0][2]:5.2f} bodies={bodies:3d} vol={m.volume/1000:7.1f}cm3")
