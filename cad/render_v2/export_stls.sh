#!/bin/bash
# Export every material group of parts.scad to STL: export_stls.sh OUTDIR
set -e
cd "$(dirname "$0")"
out="${1:-/tmp/rv2/stl}"; mkdir -p "$out"
parts="lc_mount baseplate mdf etray pcb_green pcb_blue standoffs chips rails rollers rods orings hopper armpost arm arm_bolts cup hood loadcell lc_bolts sorttray levers lever_screws"
for p in $parts; do
  openscad --backend=manifold -D "part=\"$p\"" -o "$out/$p.stl" parts.scad >/dev/null 2>"$out/$p.log" &
done
for i in 0 1 2 3 4 5 6 7 8; do
  openscad --backend=manifold -D "part=\"tile\"" -D "idx=$i" -o "$out/tile$i.stl" parts.scad >/dev/null 2>"$out/tile$i.log" &
done
wait
for p in $parts; do [ -s "$out/$p.stl" ] && echo "ok $p $(wc -c < "$out/$p.stl")" || { echo "FAIL $p"; cat "$out/$p.log"; }; done
