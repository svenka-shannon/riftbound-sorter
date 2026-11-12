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
use <motor_mount.scad>
use <slide_bed.scad>
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
//   Rollers / rods:        X = -140 and +60 (200mm centres), rod axis Z = 19
//   Round belts:           4 × NBR O-ring 135 × 3 at Y = ±8.5, ±25.5
//   Card face (belt top):  Z = 30.9; slide bed X = -127 .. 47
//   Motors:                front (-Y) rail, brackets reach Y = -113.5
//   Sorting tray:          X =   85 .. 183  (98mm deep), Y = -137 .. 137 (274mm wide)
//   Electronics tray:      behind the belt, Y = 80 .. 205
base_top  = 4;     // baseplate_tile tile_h
belt_x0   = -165;  // belt start
rail_in   = 45;    // inner face of each rail (|Y|); roller_w = 88 (1mm each side)
rail_top  = base_top + 35;  // rail_h = 35
roller_x  = [belt_x0 + 25, belt_x0 + 225];   // [-140, 60]
shaft_z   = base_top + 15;                   // 19 — rod axis
card_z    = shaft_z + 11.9;                  // 30.9 — belt top = card face
rod_len   = 150;                             // 8mm rod, centred on Y = 0

// Step 1 — Baseplate: 3 × 3 grid of 190 × 180mm tiles, centred under machine
module asm_baseplate()
    for (col = [0:2]) for (row = [0:2])
        translate([col * 190 - 285, row * 180 - 270, 0])
            baseplate_tile();

// Step 2 — Electronics tray (185 × 125 × 45), behind the conveyor
module asm_electronics_tray()
    translate([-150, 80, base_top]) electronics_tray();

// Step 3 — Conveyor rails × 2 (each split into 2 × 125mm), groove faces inward.
// Front (-Y) rail = motor side: insert pads for the motor brackets.
// Each rail line has 4 L-feet → M3 into the baseplate grid row |Y| = 75.
module asm_rails() {
    for (side = [-1, 1])
        translate([belt_x0, side * rail_in, base_top])
            mirror([0, side < 0 ? 1 : 0, 0]) {
                rail_half(add_shaft_far = false, motor_mount = (side < 0));
                translate([125, 0, 0]) rail_half(add_shaft_far = true, motor_mount = (side < 0));
            }
}

// Step 3a — 608ZZ bearings pressed into the 4 rail pockets (|Y| 48..55)
module asm_bearings()
    for (x = roller_x) for (side = [-1, 1])
        translate([x, side * (rail_in + 3), shaft_z])
            rotate([side > 0 ? -90 : 90, 0, 0])
            difference() {
                cylinder(d = 22, h = 7, $fn = 48);
                translate([0, 0, -0.1]) cylinder(d = 8, h = 7.2, $fn = 32);
            }

// Step 3b — Slide bed between the rails (inside the belt loops)
module asm_slide_bed()
    translate([slide_bed_x0(), 0, base_top]) slide_bed();

// Step 3c — Rollers (88mm, centred, 1mm to each rail face) on 8mm × 150 rods
module asm_rollers() {
    for (x = roller_x)
        translate([x, -roller_width() / 2, shaft_z]) rotate([-90, 0, 0]) roller();
}
module asm_rods()   // full-length flat (4mm wide, 0.54 deep) faces -Z, like the roller D-bore
    for (x = roller_x)
        translate([x, -rod_len / 2, shaft_z]) rotate([-90, 0, 0])
            difference() {
                cylinder(d = 8, h = rod_len, $fn = 32);
                translate([-5, sqrt(16 - 4), -1]) cube([10, 5, rod_len + 2]);
            }
// Race spacer + 8mm collar outside each bearing (front ones live inside the
// motor bracket's flange hole); locates the rod axially.
module asm_collars()
    for (x = roller_x) for (side = [-1, 1])
        translate([x, side * (rail_in + rail_boss_face_y()), base_top])
            mirror([0, side < 0 ? 1 : 0, 0]) motor_mount_collar();

// Step 3d — Round belts: 4 × O-ring 135 × 3 per conveyor, stretched 7.4 %
module asm_belts()
    for (y = roller_belt_y())
        translate([roller_x[0], y, shaft_z]) belt_strand(roller_x[1] - roller_x[0]);

// Step 3e — N20 motor brackets on the front rail, one per rod, with the
// 3→8mm coupling and N20 shown as reference solids
module asm_motor_mounts()
    for (x = roller_x)
        translate([x, -rail_in, base_top]) mirror([0, 1, 0])
            translate([0, rail_boss_face_y(), 0]) motor_mount();
module asm_motors()
    for (x = roller_x)
        translate([x, -rail_in, base_top]) mirror([0, 1, 0])
            translate([0, rail_boss_face_y(), 0]) {
                motor_mount_coupling();
                motor_mount_n20();
            }

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

// Step 8 — 2-floor sorting tray at the belt exit, label windows facing +X.
// Centred on the belt axis: width comes from sorting_tray.scad (2 × 137 = 274mm).
module asm_sorting_tray()
    translate([85 + sorting_tray_depth(), -sorting_tray_width() / 2, base_top])
        rotate([0, 0, 90]) full_2floor_assembly();

// Step 8b — Sort gate levers × 2 on the back rail near the belt exit.
// Matches hardware/servos.py: PCA9685 ch1 = deflect gate (floor select),
// ch2 = bin select (column). ch0 is the pickup arm, not a gate.
function gate_lever_x() = [30, 65];   // [deflect gate (ch1), bin select (ch2)]
module asm_gate_levers()
    for (x = gate_lever_x())
        translate([x, rail_in + 3, rail_top]) rotate([0, 0, -90]) gate_lever();

// ── Full assembly ─────────────────────────────────────────────────────────
asm_baseplate();
asm_electronics_tray();
asm_rails();
asm_bearings();
asm_slide_bed();
asm_rollers();
asm_rods();
asm_collars();
asm_belts();
asm_motor_mounts();
%asm_motors();
asm_hopper();
asm_arm_post();
asm_suction_arm();
asm_scanner_hood();
asm_load_cell();
asm_sorting_tray();
asm_gate_levers();
