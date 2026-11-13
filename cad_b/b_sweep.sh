#!/bin/bash
# Collision sweep for option B: swing height over the whole yaw range, lowest
# pose at every station (hand + links only), and three sanity cases that MUST hit.
cd "$(dirname "$0")"
probe() { rm -f /tmp/b_int.stl; if openscad --backend=manifold -D yaw=$1 -D th=$2 -D with_cup=$3 -o /tmp/b_int.stl b_interfere.scad 2>&1 | grep -q "object is empty"; then echo clear; else echo HIT; fi; }
bad=0
for y in $(seq 5 5 175); do [ "$(probe $y 6 true)" = HIT ] && { echo "HIT swing yaw=$y"; bad=$((bad+1)); }; done
for i in 0 1 2 3 4 5 6 7 8; do s=$((10+20*i)); [ "$(probe $s -6 false)" = HIT ] && { echo "HIT low station yaw=$s"; bad=$((bad+1)); }; done
for c in "30 -9 true" "90 -9 true"; do [ "$(probe $c)" = clear ] && { echo "SANITY FAIL: $c should hit"; bad=$((bad+1)); }; done
echo "problems: $bad"; exit $bad
