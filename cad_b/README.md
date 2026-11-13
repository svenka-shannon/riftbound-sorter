# Option B: turntable picker (concept, 2026-11-13)

Budget rebuild: $100 cap on new parts, built mostly from parts already owned.

- `b_params.scad`: all shared geometry (stations, heights, servo, arm).
- `b_parts.scad`: printed parts (`-D 'part="bin"'` etc.) + reference solids.
- `b_assembly.scad`: whole machine, `-D yaw=<servo deg> -D th=<link deg>`.
- `b_check.py`: numeric checks (pocket spacing, yaw tolerance, lift range, FOV, camera clearance).
- `b_interfere.scad` + `b_sweep.sh`: collision sweep of the moving arm against every fixed part.

Card path: hopper (station 0, s=10) -> cup lifts top card -> scan/weigh bed (s=30, camera above, owned 5 kg bar cell under) -> released, photographed, weighed -> re-picked -> one of 6 bins or reject (s=50..170, 20 deg pitch, fan-shaped pockets).
Touch-down sensing: the cup slider rests on the hand under gravity; an M3 screw pair is a contact that opens when the cup touches anything.
