# Option B: turntable picker (concept, 2026-11-13)

Budget rebuild: $100 cap on new parts, built mostly from parts already owned.

- `b_params.scad`: all shared geometry (stations, heights, servo, arm).
- `b_parts.scad`: printed parts (`-D 'part="bin"'` etc.) + reference solids.
- `b_assembly.scad`: whole machine, `-D yaw=<servo deg> -D th=<link deg>`.
- `b_check.py`: numeric checks (pocket spacing, yaw tolerance, lift range, FOV, camera clearance).
- `b_interfere.scad` + `b_sweep.sh`: collision sweep of the moving arm against every fixed part.

Card path: hopper (station 0, s=10) -> cup lifts top card -> scan/weigh bed (s=30, camera above, owned 5 kg bar cell under) -> released, photographed, weighed -> re-picked -> one of 6 bins or reject (s=50..170, 20 deg pitch, fan-shaped pockets).
Touch-down sensing: the cup slider rests on the hand under gravity; an M3 screw pair is a contact that opens when the cup touches anything.

## Round 2 changes (review fixes, 2026-11-13)

- Turntable: horn screw holes actually cut at the plate (were at Z 0); lift servo flipped to lie outboard of P1, so the yaw horn screw and the 4 M2.5 horn screws are reachable from above at any time.
- Tube + leads: zip-tied at the mast top, free loop back to a fixed `cable_post` behind the axis (no route through the yaw joint).
- Pivots: printed sleeves on M3 x 16 into inserts (no M3 x 25/35, no nylocks); servo tabs through-bolted with nuts in hex pockets.
- Accuracy: hopper 65 x 90 with a lead-in chamfer; bins 100 mm radially; bin dividers start at r 236 so nothing can catch the card's inner corners; b_check now has a yaw error stack-up.
- Swing clearance: lift range -6..+10 deg (card 21 mm over the walls); roller axles in slots to set the sag-stop gap.
- Arm stiffness: links 10 x 12 (was 5 x 12); full-height mast wall, rear gussets, gusset under the P2 boss.
- Touch sensing: 608 bearing ring on the slider (12 g of weight) rests on two M3 head-up screws + a printed bump (3-point); no wire on the moving slider.
- Slider Ø12 solid with an airline tee pocket at the bottom (stem into the cup neck, one leg to the tube, one to the pin-hole bleed).
- Camera: +5 D close-up lens, lens 176 mm over the bed, boom clamps to the post at any height; WS2812 ring on its own clamp beside the post.
- Bed boss 5 mm (4 mm under the M4 heads). Bin/hopper ears inboard only.
- `export_b.py` exports all print STLs (print orientation) + PRINT_LIST.md + zip.

## Round 3 changes (second review, 2026-11-13)

- Slider and bore are D-profiles (flat 3.5 mm off-axis, 0.1 clearance): the cup can no longer swivel the card.
- Touch contact: three M3 button heads at 120 deg on r 11.5 (two wired, one plain) under the 608 ring; inserts 3 mm from the bore; hand flange kept out of the link plane.
- Tee snaps into a slot 0.8 mm narrower than its seat.
- Camera tower moved off the station ray to (330, 60): it stays on a 2 ft board and clear of bin 1. Boom and ring holder clamp with an M3 into a 10 mm boss; camera turned so the sensor's long axis is along the card; new `lens_frame` holds the popped-out +5 D glasses lens; lens 188 mm over the bed (middle of the +5 D range).
- Hopper/bin ears overlap their walls; hand zip-tie slot moved between the pivots; mast zip-tie holes moved to x 50/60; mast wall widened to x 0..70 with the gussets outside the nut path (washer + nut on the flat back, no pockets); full-width gusset under the P2 boss; horn slots are +/-8 deg arcs; yaw-base tab holes and the slider stub use self-tap pilots (no heat-set in thin walls); cap screw M3 x 8.
- Print orientations fixed in export_b.py (post upright, boom and lens frame upside down, hand flange-down, brims on the slider and sleeves).
- b_check: slider swivel and radial bed offset in the error budget; the inner-zone check is now the honest two-card worst case (margin 0 mm, RSS 4.5 mm), which REQUIRES the firmware to approach every station from the same direction. Fallback if the bench repeatability test fails: 5 bins + reject at 22.9 deg pitch.
