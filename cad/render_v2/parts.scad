// Riftbound Card Sorter - per-material part exports for the v2 (Blender) assembly video.
// Uses the asm_* modules from ../assembly.scad (already at assembled positions) and adds
// visual-only hardware (steel rods, O-rings, screws, PCBs, standoffs, MDF board, suction cup)
// so each part can get its own material. Export: openscad -D 'part="rails"' -o rails.stl parts.scad
use <../assembly.scad>
use <../baseplate_tile.scad>
part = "baseplate";
idx = 0;  // tile index for part="tile"
base_top = 4;
$fn = 48;

module screw_head(d = 5.5, h = 3) { cylinder(d = d, h = h); }
module pcb(x0, y0, w, d) translate([x0, y0, 0]) cube([w, d, 1.6]);

// electronics tray at world (-150, 80, base_top); floor 2.5 thick; standoffs 5 high
tray_o = [-150, 80, base_top + 2.5];
module boards_pi()  translate(tray_o + [0, 0, 5]) pcb(5, 5, 85, 56);
module boards_pca() translate(tray_o + [0, 0, 5]) pcb(94, 6, 37, 68);
module boards_hx()  translate(tray_o + [0, 0, 5]) pcb(145, 74, 30, 22);
module standoffs() translate(tray_o) {
    for (x = [10, 68]) for (y = [10, 33]) translate([x + 5, y + 5, 0]) cylinder(d = 5, h = 5, $fn = 6);
    for (x = [100, 125]) for (y = [10, 70]) translate([x, y, 0]) cylinder(d = 5, h = 5, $fn = 6);
    for (x = [150, 170]) for (y = [78, 92]) translate([x, y, 0]) cylinder(d = 5, h = 5, $fn = 6);
}
module chips() translate(tray_o + [0, 0, 6.6]) {
    translate([30, 20, 0]) cube([14, 14, 1.4]);          // Pi SoC
    translate([60, 35, 0]) cube([18, 8, 1]);              // Pi RAM
    translate([72, 10, 0]) cube([17, 14, 8]);             // USB block
    translate([72, 30, 0]) cube([17, 14, 13]);            // RJ45
    translate([106, 30, 0]) cube([10, 10, 1.4]);          // PCA9685 chip
    translate([96, 64, 0]) cube([33, 5, 9]);              // header row
    translate([155, 80, 0]) cube([7, 5, 1.4]);            // HX711 chip
}

// rollers: x = -140 / 60, axis along Y, centre z = base_top + 15
roller_x = [-140, 60];
module rods() for (x = roller_x) translate([x, -58, base_top + 15]) rotate([-90, 0, 0]) cylinder(d = 8, h = 116);
module orings() for (x = roller_x) for (k = [1:4])
    translate([x, -45 + 18 * k, base_top + 15]) rotate([90, 0, 0])
        rotate_extrude($fn = 48) translate([10.4, 0]) circle(r = 1.05, $fn = 16);

// suction arm hardware: bolts either side of the pivot, suction cup under the tip
module arm_bolts() for (dx = [-7.5, 7.5]) translate([-270 + dx, 0, base_top + 131]) screw_head();
module cup() translate([-160, 0, base_top + 121]) mirror([0, 0, 1]) {
    cylinder(d = 8, h = 8);
    translate([0, 0, 8]) cylinder(d1 = 8, d2 = 16, h = 6);
}
// load cell lower mounting block (to the tray floor) + spacer + upper weigh platform
module lc_mount() {
    translate([-10, 140, base_top + 2.5]) cube([15, 12, 39.5]);
    translate([35, 140, base_top + 50]) cube([15, 12, 3]);
    translate([20.5, 124, base_top + 53]) cube([44, 44, 2.5]);
}
// load cell bolts
module lc_bolts() for (x = [-2, 42]) translate([x, 146, base_top + 49]) screw_head(5, 2.5);
// gate lever pivot screws
module lever_screws() for (x = [20, 45, 70]) translate([x, 38, base_top + 35 + 6]) screw_head(5.5, 2.5);
// MDF backing board under the 3x3 tiles
module mdf() translate([-295, -280, -12]) cube([590, 560, 12]);

if (part == "baseplate") asm_baseplate();
if (part == "tile") translate([floor(idx / 3) * 190 - 285, (idx % 3) * 180 - 270, 0]) baseplate_tile();
if (part == "mdf") mdf();
if (part == "etray") asm_electronics_tray();
if (part == "pcb_green") { boards_pi(); boards_hx(); }
if (part == "pcb_blue") boards_pca();
if (part == "standoffs") standoffs();
if (part == "chips") chips();
if (part == "rails") asm_rails();
if (part == "rollers") asm_rollers();
if (part == "rods") rods();
if (part == "orings") orings();
if (part == "hopper") asm_hopper();
if (part == "armpost") asm_arm_post();
if (part == "arm") asm_suction_arm();
if (part == "arm_bolts") arm_bolts();
if (part == "cup") cup();
if (part == "hood") asm_scanner_hood();
if (part == "loadcell") asm_load_cell();
if (part == "lc_bolts") lc_bolts();
if (part == "lc_mount") lc_mount();
if (part == "sorttray") asm_sorting_tray();
if (part == "levers") asm_gate_levers();
if (part == "lever_screws") lever_screws();
