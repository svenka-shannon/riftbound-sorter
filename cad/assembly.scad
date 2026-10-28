// Riftbound Card Sorter — Assembly View
// All parts positioned at machine coordinates
// Updated for 250mm conveyor + 2-floor sorting tray

use </tmp/riftbound-sorter/cad/hopper.scad>
use </tmp/riftbound-sorter/cad/conveyor_rail.scad>
use </tmp/riftbound-sorter/cad/conveyor_roller.scad>
use </tmp/riftbound-sorter/cad/scanner_hood.scad>
use </tmp/riftbound-sorter/cad/suction_arm.scad>
use </tmp/riftbound-sorter/cad/sort_gate_lever.scad>
use </tmp/riftbound-sorter/cad/sorting_tray.scad>
use </tmp/riftbound-sorter/cad/electronics_tray.scad>
use </tmp/riftbound-sorter/cad/baseplate_tile.scad>

// ── Machine layout (X axis = card travel direction) ──────────────────────
//   Hopper right wall:     X ≈ -158
//   Belt start:            X = -165
//   Belt end / Tray start: X =  85   (250mm belt)
//   Tray end:              X = 170   (85mm deep tray)
//   Total X footprint:     ~480mm
//   Z footprint:           ~300mm (271mm tray + walls)

// ── Baseplate (3×3 grid of 190×180mm tiles, centred under machine) ────────
for (col = [0:2]) for (row = [0:2])
    translate([col * 190 - 285, 0, row * 180 - 180])
        baseplate_tile();

// ── Electronics Tray (centred under conveyor) ─────────────────────────────
translate([-40, 5, 20])
    electronics_tray();

// ── Hopper (left side, on baseplate) ──────────────────────────────────────
translate([-230, 10, -20])
    hopper_body();

// ── Suction Arm (above hopper) ────────────────────────────────────────────
translate([-192, 155, -15]) rotate([0,0,-90])
    suction_arm();

// ── Conveyor Rails × 2 (back + front, each split into 2×125mm) ───────────
//   rail_len = 125, total = 250mm, starts at X=-165
//   Back rail (Z = -53)
translate([-165, 10, -53]) {
    rail_half(add_shaft_far=false);
    translate([125, 0, 0]) rail_half(add_shaft_far=true);
}
//   Front rail (Z = +50)
translate([-165, 10, 50]) {
    rail_half(add_shaft_far=false);
    translate([125, 0, 0]) rail_half(add_shaft_far=true);
}

// ── Conveyor Rollers (shaft positions from rail params) ───────────────────
//   Roller 1: -165 + shaft_x1(25) = -140
//   Roller 2: -165 + 125 + shaft_x2(100) = 60
translate([-140, 25, 0]) rotate([90,0,0]) roller();
translate([  60, 25, 0]) rotate([90,0,0]) roller();

// ── Scanner Hood (centred above belt, ~100mm from left end) ───────────────
//   Belt centre X = -40; scanner_hood module origin at its corner → offset -40
translate([-80, 45, -50])
    scanner_hood();

// ── Sort Gate Levers × 3 (at X=60, near belt right end) ──────────────────
for (i = [-1, 0, 1])
    translate([60, 80, i * 32]) rotate([90,0,0])
        gate_lever();

// ── 2-Floor Sorting Tray ──────────────────────────────────────────────────
//   Tray starts at X=85 (belt exit), full width Z=271mm centred at Z=0
//   Lower floor — Section A (slots 0-1, Z = -135.5..0)
translate([85, 10, -135.5])
    color("SteelBlue") tray_floor_section(start_slot=0, is_first=true, is_last=false);

//   Lower floor — Section B (slots 2-3, Z = 0..+135.5)
//   Account for section_w + alignment pin protrusion (5mm)
translate([85, 10, 0])
    color("CornflowerBlue") tray_floor_section(start_slot=2, is_first=false, is_last=true);

//   Separator shelf between floors
translate([85, 10 + 65, -135.5])
    color("LightGray", 0.5) floor_shelf();

//   Upper floor — Section C (slots 4-5, Z = -135.5..0)
translate([85, 10 + 65 + 3, -135.5])
    color("SlateBlue") tray_floor_section(start_slot=4, is_first=true, is_last=false);

//   Upper floor — Section D (slots 6-7, Z = 0..+135.5)
translate([85, 10 + 65 + 3, 0])
    color("MediumPurple") tray_floor_section(start_slot=6, is_first=false, is_last=true);
