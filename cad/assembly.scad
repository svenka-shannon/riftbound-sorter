// Riftbound Card Sorter — Assembly View
// All parts positioned at machine coordinates
// Updated for 250mm conveyor + 2-floor sorting tray
//
// Coordinate frame (matches every part file's print orientation, Z up):
//   X = card travel direction (hopper → conveyor → sorting tray)
//   Y = across the belt (+Y = back of machine, electronics side)
//   Z = up; baseplate top surface at Z = 4
//
// Each asm_* module below is one step of docs/ASSEMBLY.md §4 and is used by
// cad/assembly-steps.yaml to render the assembly video (docs/assembly-video.mp4).

use <hopper.scad>
use <conveyor_rail.scad>
use <conveyor_roller.scad>
use <scanner_hood.scad>
use <suction_arm.scad>
use <sort_gate_lever.scad>
use <sorting_tray.scad>
use <electronics_tray.scad>
use <baseplate_tile.scad>

// ── Machine layout ────────────────────────────────────────────────────────
//   Arm post:              X = -270
//   Hopper:                X = -262 .. -165
//   Belt start / end:      X = -165 .. 85   (250mm belt, 2 × 125mm rails)
//   Sorting tray:          X =   85 .. 183  (98mm deep, 271mm wide in Y)
//   Electronics tray:      behind the belt, Y = 80 .. 205
base_top  = 4;     // baseplate_tile tile_h
belt_x0   = -165;  // belt start
rail_in   = 45;    // inner face of each rail (|Y|); roller_w = 90
rail_top  = base_top + 35;  // rail_h = 35

// Step 1 — Baseplate: 3 × 3 grid of 190 × 180mm tiles, centred under machine
module asm_baseplate()
    for (col = [0:2]) for (row = [0:2])
        translate([col * 190 - 285, row * 180 - 270, 0])
            baseplate_tile();

// Step 2 — Electronics tray (185 × 125 × 45), behind the conveyor
module asm_electronics_tray()
    translate([-150, 80, base_top]) electronics_tray();

// Step 3 — Conveyor rails × 2 (each split into 2 × 125mm), groove faces inward
module asm_rails() {
    for (side = [-1, 1])
        translate([belt_x0, side * rail_in, base_top])
            mirror([0, side < 0 ? 1 : 0, 0]) {
                rail_half(add_shaft_far = false);
                translate([125, 0, 0]) rail_half(add_shaft_far = true);
            }
}

// Step 3b — Rollers on 8mm shafts (shaft_x1 = 25 from belt start, drive roller 25 from end)
module asm_rollers()
    for (x = [belt_x0 + 25, belt_x0 + 225])
        translate([x, -rail_in, base_top + 15]) rotate([-90, 0, 0]) roller();

// Step 4 — Hopper at the belt inlet, exit slot facing +X (down the belt)
module asm_hopper()
    translate([belt_x0, -36, base_top]) rotate([0, 0, 90]) hopper_body();

// Step 5 — Suction arm on its baseplate post (post is a 12mm stand-in, not a printed part)
module asm_arm_post()
    translate([-270, 0, base_top]) cylinder(d = 12, h = 121, $fn = 32);
module asm_suction_arm()
    translate([-280, -10, base_top + 121]) suction_arm();

// Step 6 — Scanner hood, straddling the rails over the scan zone
module asm_scanner_hood()
    translate([-2.5, -47.5, rail_top]) rotate([0, 0, 90]) scanner_hood();

// Step 7 — Load cell (TAL221 50g beam stand-in) seated in the tray's beam pocket
module asm_load_cell()
    translate([-150 + 140, 80 + 60, base_top + 45 - 3]) cube([60, 12, 8]);

// Step 8 — 2-floor sorting tray at the belt exit, label windows facing +X
module asm_sorting_tray()
    translate([85 + 98, -138, base_top]) rotate([0, 0, 90]) full_2floor_assembly();

// Step 8b — Sort gate levers × 3 on the back rail near the belt exit
module asm_gate_levers()
    for (x = [20, 45, 70])
        translate([x, rail_in + 3, rail_top]) rotate([0, 0, -90]) gate_lever();

// ── Full assembly ─────────────────────────────────────────────────────────
asm_baseplate();
asm_electronics_tray();
asm_rails();
asm_rollers();
asm_hopper();
asm_arm_post();
asm_suction_arm();
asm_scanner_hood();
asm_load_cell();
asm_sorting_tray();
asm_gate_levers();
