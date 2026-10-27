// Riftbound Card Sorter — Assembly View
// All 9 parts positioned at machine coordinates

use </tmp/riftbound-sorter/cad/hopper.scad>
use </tmp/riftbound-sorter/cad/conveyor_rail.scad>
use </tmp/riftbound-sorter/cad/conveyor_roller.scad>
use </tmp/riftbound-sorter/cad/scanner_hood.scad>
use </tmp/riftbound-sorter/cad/suction_arm.scad>
use </tmp/riftbound-sorter/cad/sort_gate_lever.scad>
use </tmp/riftbound-sorter/cad/output_bin.scad>
use </tmp/riftbound-sorter/cad/electronics_tray.scad>
use </tmp/riftbound-sorter/cad/baseplate_tile.scad>

// ── Baseplate (3×3 grid of 190×180mm tiles) ─────────────────────────────
for (col = [0:2]) for (row = [0:2])
    translate([col * 190 - 190, 0, row * 180 - 180])
        baseplate_tile();

// ── Electronics Tray (centered under conveyor area) ──────────────────────
translate([10, 10, 20])
    electronics_tray();

// ── Hopper (left side, on baseplate) ────────────────────────────────────
translate([-230, 10, -20])
    hopper_body();

// ── Conveyor Rail × 2 (left+right, back+front, split 2×190) ─────────────
// Back rail
translate([-160, 10, -53]) {
    rail_half(add_shaft_far=false);
    translate([190, 0, 0]) rail_half(add_shaft_far=true);
}
// Front rail
translate([-160, 10, 50]) {
    rail_half(add_shaft_far=false);
    translate([190, 0, 0]) rail_half(add_shaft_far=true);
}

// ── Conveyor Rollers (at each shaft position) ───────────────────────────
translate([-130, 25, 0]) rotate([90,0,0]) roller();
translate([20,  25, 0]) rotate([90,0,0]) roller();

// ── Scanner Hood (above conveyor center) ─────────────────────────────────
translate([-15, 45, -47])
    scanner_hood();

// ── Suction Arm (above hopper, vertical) ─────────────────────────────────
translate([-192, 155, -15]) rotate([0,0,-90])
    suction_arm();

// ── Sort Gate Levers × 3 (at end of conveyor) ───────────────────────────
for (i = [-1, 0, 1])
    translate([195, 80, i * 32]) rotate([90,0,0])
        gate_lever();

// ── Output Bins (2 cols × 4 rows) ───────────────────────────────────────
for (col = [0:1]) for (row = [0:3])
    translate([225 + col * 87, 10, row * 133 - 195])
        output_bin();

// Reject bin
translate([225 + 2 * 87, 10, 0])
    output_bin();
