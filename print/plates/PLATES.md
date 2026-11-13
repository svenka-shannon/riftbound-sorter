# Riftbound sorter - build plates

Every printed part, packed onto 16 build plates for a 256 x 256 mm bed (Bambu P1S / X1 / A1, Prusa MK4, any 256 mm bed). Each plate holds parts that share one material and one set of print settings, so you load one file, pick the filament and the settings below, slice and print. Parts are already in their print orientation; don't rotate them in Z.

How to use: open the `.3mf` in Bambu Studio / OrcaSlicer / PrusaSlicer (if asked, load geometry only). The parts are already arranged; you can re-run auto-arrange if you like. The `.png` next to each file is a top view of the plate.

| Plate | File | Print | Filament | Settings | Contents |
|---|---|---|---|---|---|
| 1 | `plate_01_tile.3mf` | **9 times** | PLA | 0.20 mm layers, 4 walls, 40 % infill, flat with the key pockets facing up. No supports. | baseplate_tile (tallest 4 mm) |
| 2 | `plate_02_pla_structural.3mf` | once | PLA | 0.20 mm layers, 4 walls, 40 % infill. No supports. | cam_bracket, hopper_plate, rail_back2, tray_A, tray_C (tallest 65 mm) |
| 3 | `plate_03_pla_structural.3mf` | once | PLA | 0.20 mm layers, 4 walls, 40 % infill. No supports. | rail_front1, tray_B, tray_D, tray_shelf (tallest 65 mm) |
| 4 | `plate_04_pla_structural.3mf` | once | PLA | 0.20 mm layers, 4 walls, 40 % infill. No supports. | baseplate_keys, hopper_body, hopper_flag, rail_back1, sh_rbar_pos, tray_shelf (tallest 126 mm) |
| 5 | `plate_05_pla_structural.3mf` | once | PLA | 0.20 mm layers, 4 walls, 40 % infill. No supports. | hopper_cap, hopper_carriage, rail_front2, sh_rbar_neg (tallest 34 mm) |
| 6 | `plate_06_pla_light.3mf` | once | PLA | 0.20 mm layers, 3 walls, 25 % infill. No supports. | electronics_tray, slide_bed (tallest 45 mm) |
| 7 | `plate_07_pla_light.3mf` | once | PLA | 0.20 mm layers, 3 walls, 25 % infill. No supports. | reject_bin (tallest 56 mm) |
| 8 | `plate_08_pla_riser.3mf` | once | PLA (or PETG) | 0.24 mm layers, 3 walls, 15 % gyroid. Printed upside down as exported. No supports. | riser_a (tallest 60 mm) |
| 9 | `plate_09_pla_riser.3mf` | once | PLA (or PETG) | 0.24 mm layers, 3 walls, 15 % gyroid. Printed upside down as exported. No supports. | riser_b (tallest 60 mm) |
| 10 | `plate_10_pla_ramp.3mf` | once | PLA | **0.16 mm layers**, 3 walls, 15 % infill, bridge fan 100 %. Upright as exported. Sand the lanes with 600 grit. | ramp_neg, ramp_pos (tallest 100 mm) |
| 11 | `plate_11_pla_cradle.3mf` | once | PLA | **0.12 mm layers**, 3 walls, 15 % infill, ironing on top surface, **brim on**. | sh_cradle (tallest 13 mm) |
| 12 | `plate_12_petg_general.3mf` | once | PETG | 0.20 mm layers, 4 walls, 40 % infill. No supports. | arm_hand, arm_head, arm_tower, motor_mount x2, pump_base, sh_cheek_neg, sh_cheek_pos, sh_end_post_neg, sh_end_post_pos, sh_tilt_frame (tallest 155 mm) |
| 13 | `plate_13_petg_general.3mf` | once | PETG | 0.20 mm layers, 4 walls, 40 % infill. No supports. | arm_sled, arm_sleeves, cg_clip x4, pump_cap, pump_valve_clip, sh_sled (tallest 81 mm) |
| 14 | `plate_14_petg_strong.3mf` | once | PETG | 0.20 mm layers, 5 walls, **100 % infill**. No supports. | arm_crank, arm_link, race_spacer x4, roller x2, sh_c2_crank, sh_c2_link, sh_tilt_crank, sh_tilt_link (tallest 88 mm) |
| 15 | `plate_15_black.3mf` | once | **Black** PETG or PLA | 0.20 mm layers, 3 walls, 20 % infill, **8-10 mm brim** (the hood is 101 mm tall on a small roof), outer walls <= 60 mm/s. | cg_guide_back, cg_guide_front, hood (tallest 101 mm) |
| 16 | `plate_16_tpu.3mf` | once | TPU 95A | Optional: skip this plate if you use a neoprene strip instead. Default TPU profile. | pump_pad, pump_sleeve (tallest 22 mm) |

That is 16 plate files and **24 print jobs** in all.

Notes:
- `sh_end_post_neg` comes with a built-in break-away support ladder under its ledge: snap it out after printing.
- The 9 tiles are optional: BOM.md (cost-down option 1) shows how to drill the backing board from a template instead. That saves about 1.1 kg of PLA and about 30 h of printing.
- Full per-part notes (orientation, inserts, sanding) are in PRINT_GUIDE.md.

Totals: 9 baseplate tiles, 24 tile keys (one part), and every other part at the quantity in PRINT_GUIDE.md. The 2 arm links and the 4 arm sleeves are each one file.
