// v3 assembly video: individual parts (machine coordinates) for steps 1-5 and 9:
// backing board, tiles, keys, tee-nuts, feet, electronics tray + boards, riser,
// rails, bearings, conveyor, sorting tray, and their fasteners.
// Export one part:  openscad --backend=manifold -D 'part="v3_tile3"' -o tile3.stl w_base.scad
// (the "v3_" prefix keeps the used part files' own `part` selectors inert).
use <../assembly.scad>
use <../machine_frame.scad>
use <../baseplate_tile.scad>
use <../riser.scad>
use <../conveyor_rail.scad>
use <../conveyor_roller.scad>
use <../motor_mount.scad>
use <../slide_bed.scad>
use <../sorting_tray.scad>
use <../electronics_tray.scad>
include <hw_common.scad>

part = "v3_board";
P = part;
base_top = 4;
board_t = 6;
deck_z = 64;
belt_x0 = -165;
rail_in = 45;
roller_x = [-140, 60];
shaft_z = 79;

// ── Step 1: board, tiles, keys, tee-nuts, feet ──────────────────────────────
module board() translate([-290, -275, -board_t]) cube([580, 550, board_t]);
module tile(i) translate([floor(i / 3) * 190 - 285, (i % 3) * 180 - 270, 0]) baseplate_tile();
key_z = base_top - 0.1 - 2.3;
module keys() {
    for (x = [-95, 95], r = [0 : 2], ky = [30, 150])          // seams at X = const (key spans X)
        translate([x, -270 + 180 * r + ky, key_z]) baseplate_key();
    for (y = [-90, 90], c = [0 : 2], kx = [30, 150])          // seams at Y = const
        translate([-285 + 190 * c + kx, y, key_z]) rotate(90) baseplate_key();
}
// the 49 board holes (ASSEMBLY.md §4 table)
holes = [[-120, 105], [-50, 105], [-120, 195], [10, 195],                         // electronics tray
         [-150, -105], [-150, 75], [-80, -15], [-20, 75], [-20, 45],             // riser anchors
         [-80, -75], [-120, 75], [-80, 75], [10, 75],                            // rail through-feet
         [-240, -15], [-240, 15], [-180, -15], [-180, 15],                       // hopper
         [-180, -165], [-120, -165], [-180, -135], [-120, -135],                 // arm tower
         for (x = [200, 260], y = [-105, -45, 45, 105]) [x, y],                  // sorting tray
         [110, -225], [140, -195], [140, -165], [110, 225], [110, 255], [140, 255],   // end posts
         for (y = [-105, -45, 45, 105]) [140, y],                                // lower ramp
         for (x = [200, 230], y = [165, 195]) [x, y],                            // reject bin
         for (x = [-270, -240], y = [-225, -195]) [x, y],                        // pump bracket
         [-180, -255], [-150, -255]];                                            // vent-valve clip
echo(str("V3 board holes: ", len(holes)));
module hole_marks() for (h = holes) translate([h[0], h[1], base_top]) cylinder(d = 7, h = 0.4, $fn = 24);
module teenuts() for (h = holes) teenut(h, -board_t);
feet_xy = [for (x = [-268, 268], y = [-255, 0, 255]) [x, y], [0, -255], [0, 255]];
module feet() for (f = feet_xy) translate([f[0], f[1], -board_t - 10]) cylinder(d = 20, h = 10, $fn = 32);

// ── Step 2: electronics tray + boards ───────────────────────────────────────
tray_o = [-150, 80, base_top + 2.5];     // floor top
post_h = 5; pol_h = 4; foam = 1;
b_pi  = [[107, 5],    [65, 30],       post_h];
b_pca = [[108, 44],   [62.23, 25.4],  post_h];
b_rly = [[5, 42],     [50, 38.5],     post_h];
b_uln = [[62, 42],    [35, 32],       post_h];
b_hx  = [[62.3, 82.3],[34, 21],       foam];
b_l91 = [[38.3, 5.3], [29, 23],       foam];
b_d22 = [[40, 125],   [17.8, 17.8],   pol_h];
b_d50 = [[62, 125],   [17.8, 20.3],   pol_h];
b_d36 = [[104, 125],  [17.8, 20.3],   pol_h];
function at(b, x, y) = tray_o + [b[0][0] + x, b[0][1] + y, b[2] + 1.6];
module pcb(b) translate(tray_o + [b[0][0], b[0][1], b[2]]) cube([b[1][0], b[1][1], 1.6]);
module bscrews(b, hs, d = 2.5) for (h = hs) translate(at(b, h[0], h[1])) cylinder(d = d * 1.8, h = 1.6, $fn = 14);
pi_h  = [[3.5, 3.5], [61.5, 3.5], [3.5, 26.5], [61.5, 26.5]];
pca_h = [for (x = [3.175, 59.055], y = [3.175, 22.225]) [x, y]];
rly_h = [for (x = [-1, 1], y = [-1, 1]) [25 + x * 22.15, 19.25 + y * 16.4]];
uln_h = [for (x = [-1, 1], y = [-1, 1]) [17.5 + x * 15, 16 + y * 13.25]];
module pi_chips()  { translate(at(b_pi, 28, 9)) cube([12, 12, 1.2]); translate(at(b_pi, 61, 9.5)) cube([4.5, 11, 3]);
                     translate(at(b_pi, 8, 24)) cube([51, 5, 8.5]); }                       // SoC, CSI (+X), GPIO header
module pca_chips() { translate(at(b_pca, 26, 8)) cube([10, 10, 1.4]); translate(at(b_pca, 4, 2)) cube([2.5, 21, 8.5]);
                     for (i = [0 : 3]) translate(at(b_pca, 14 + i * 9, 18)) cube([8, 6, 8]); }  // servo header blocks
module rly_chips() { for (y = [3, 20.5]) translate(at(b_rly, 18, y)) cube([19, 15.5, 15.5]);
                     for (y = [5, 22]) translate(at(b_rly, 40, y)) cube([8, 11, 9]); }   // relays + terminals
module uln_chips() { translate(at(b_uln, 7, 9)) cube([20, 7, 3]); translate(at(b_uln, 4, 24)) cube([12, 6, 6]); }
module hx_chips()  { translate(at(b_hx, 12, 7)) cube([7, 5, 1.4]); translate(at(b_l91, 8, 8)) cube([5, 4, 1.4]);
                     translate(at(b_l91, 1, 14)) cube([7, 8, 8]); }
module pol_chips() for (b = [b_d22, b_d50, b_d36]) translate(at(b, 5, 5)) cube([7, 7, 3]);
module foam_tape() for (b = [b_hx, b_l91]) translate(tray_o + [b[0][0] + 2, b[0][1] + 2, 0]) cube([b[1][0] - 4, b[1][1] - 4, 1]);
// tray → board: 4 × M3 × 18 SHCS, head on the floor top
module tray_screws() for (h = [[-120, 105], [-50, 105], [-120, 195], [10, 195]]) at_screw([h[0], h[1], base_top + 2.5]) shcs(18);
// panel barrel jack in the +Y wall (tray-local x 92, 18 up): body inside, nut outside
module jack() translate([-150 + 92, 80 + 150, base_top + 18]) rotate([90, 0, 0]) {
    translate([0, 0, -3]) cylinder(d = 8, h = 3 + 2.5 + 2, $fn = 24);          // M8 thread through the wall
    translate([0, 0, -2.5]) cylinder(d = 12, h = 2.5, $fn = 6);                 // nut outside
    translate([0, 0, 2.5]) cylinder(d = 11, h = 14, $fn = 24);                  // body inside
}
// Wago 221 bank (5 levers) + 3 × 1000 µF on the free floor
module wago() for (i = [0 : 4]) translate(tray_o + [128 + i * 10.5, 128, 0]) cube([8.5, 18.5, 8]);
module wago_levers() for (i = [0 : 4]) for (j = [0 : 2]) translate(tray_o + [129 + i * 10.5, 129.5 + j * 5.8, 8]) cube([6.5, 4, 3]);
module caps() for (p = [[16, 96], [32, 96], [118, 92]]) translate(tray_o + [p[0], p[1], 0]) cylinder(d = 10, h = 16, $fn = 24);

// ── Step 3: riser ───────────────────────────────────────────────────────────
module riser_joint_screws() for (p = [[-30, 40], [30, 30], [65, 30]]) at_screw([-43, p[0], p[1]], [1, 0, 0]) shcs(12);
module riser_joint_nuts() for (p = [[-30, 40], [30, 30], [65, 30]]) translate([-37.4, p[0], p[1]]) rotate([0, 90, 0]) hexnut();
module riser_tie_screws() for (z = [37, 56]) at_screw([-30.5, -113, z], [0, 1, 0]) csk(10);
module riser_anchors() for (h = [[-150, -105], [-150, 75], [-80, -15], [-20, 75], [-20, 45]]) at_screw([h[0], h[1], 10]) shcs(20);

// ── Step 4: rails + bearings ────────────────────────────────────────────────
module rail_piece(side, k)
    translate([belt_x0, side * rail_in, deck_z]) mirror([0, side < 0 ? 1 : 0, 0])
        if (k == 0) rail_half(add_shaft_far = false, motor_mount = (side < 0));
        else translate([125, 0, 0]) rail_half(add_shaft_far = true, motor_mount = (side < 0));
module bearings(side) for (x = roller_x) translate([x, side * (rail_in + 3), shaft_z]) rotate([side > 0 ? -90 : 90, 0, 0])
    difference() { cylinder(d = 22, h = 7, $fn = 48); translate([0, 0, -0.1]) cylinder(d = 8, h = 7.2, $fn = 32); }
module collars(side) for (x = roller_x) translate([x, side * (rail_in + rail_boss_face_y()), deck_z])
    mirror([0, side < 0 ? 1 : 0, 0]) motor_mount_collar();
module rail_through() for (h = [[-80, -75], [-120, 75], [-80, 75], [10, 75]]) at_screw([h[0], h[1], deck_z + 4]) shcs(80);
module rail_insert_screws() for (h = [[-50, -75], [40, 75]]) at_screw([h[0], h[1], deck_z + 4]) shcs(10);

// ── Step 5: conveyor ────────────────────────────────────────────────────────
module mm_at(x) translate([x, -rail_in, deck_z]) mirror([0, 1, 0]) translate([0, rail_boss_face_y(), 0]) children();
module mm_screws() for (x = roller_x, dx = [-15, 15]) at_screw([x + dx, -(rail_in + rail_boss_face_y() + 4), deck_z + 24], [0, 1, 0]) bhcs(10);

// ── Step 9: sorting tray (tray-local → machine: X = 276 − y, Y = −137 + x) ──
sec_w = 137; floor_h = 65; shelf_h = 3;
module tray_T() translate([276, -137, base_top]) rotate(90) children();
module tray_lower_screws() for (x = [200, 260], y = [-105, -45, 45, 105]) at_screw([x, y, base_top + 2.5]) csk(18);
module tray_stack_screws() tray_T() for (s = [0, 1], i = [0, 1], cx = [2.5 + i * 67 + 3.5, 2.5 + i * 67 + 65 - 3.5])
    at_screw([s * sec_w + cx, 5.6, floor_h + shelf_h + 2.5]) csk(12);

// ── selector ────────────────────────────────────────────────────────────────
if (P == "v3_board") board();
for (i = [0 : 8]) if (P == str("v3_tile", i)) tile(i);
if (P == "v3_keys") keys();
if (P == "v3_holemarks") hole_marks();
if (P == "v3_teenuts") teenuts();
if (P == "v3_feet") feet();
if (P == "v3_etray") asm_electronics_tray();
if (P == "v3_etray_screws") tray_screws();
if (P == "v3_jack") jack();
if (P == "v3_pi") pcb(b_pi);
if (P == "v3_pi_chips") pi_chips();
if (P == "v3_pi_scr") bscrews(b_pi, pi_h);
if (P == "v3_pca") pcb(b_pca);
if (P == "v3_pca_chips") pca_chips();
if (P == "v3_pca_scr") bscrews(b_pca, pca_h);
if (P == "v3_rly") pcb(b_rly);
if (P == "v3_rly_chips") rly_chips();
if (P == "v3_rly_scr") bscrews(b_rly, rly_h);
if (P == "v3_uln") pcb(b_uln);
if (P == "v3_uln_chips") uln_chips();
if (P == "v3_uln_scr") bscrews(b_uln, uln_h);
if (P == "v3_hxl9") { pcb(b_hx); pcb(b_l91); }
if (P == "v3_hxl9_chips") hx_chips();
if (P == "v3_foam") foam_tape();
if (P == "v3_pol") { pcb(b_d22); pcb(b_d50); pcb(b_d36); }
if (P == "v3_pol_chips") pol_chips();
if (P == "v3_pol_scr") { bscrews(b_d22, [[2.3, 15.5], [15.5, 2.3]], 2); bscrews(b_d50, [[2.2, 2.2], [15.7, 18.2]], 2); bscrews(b_d36, [[2.2, 2.2], [15.7, 18.2]], 2); }
if (P == "v3_wago") wago();
if (P == "v3_wago_lev") wago_levers();
if (P == "v3_caps") caps();
if (P == "v3_riser_a") riser_a();
if (P == "v3_riser_b") riser_b();
if (P == "v3_riser_joint") { riser_joint_screws(); riser_joint_nuts(); }
if (P == "v3_riser_tie") riser_tie_screws();
if (P == "v3_riser_anchors") riser_anchors();
if (P == "v3_rail_back1") rail_piece(1, 0);
if (P == "v3_rail_back2") rail_piece(1, 1);
if (P == "v3_rail_front1") rail_piece(-1, 0);
if (P == "v3_rail_front2") rail_piece(-1, 1);
if (P == "v3_bearings_f") bearings(-1);
if (P == "v3_bearings_b") bearings(1);
if (P == "v3_rail_through") rail_through();
if (P == "v3_rail_inserts") rail_insert_screws();
for (k = [0, 1]) {
    if (P == str("v3_mm", k)) mm_at(roller_x[k]) motor_mount();
    if (P == str("v3_n20_", k)) mm_at(roller_x[k]) motor_mount_n20();
    if (P == str("v3_cpl", k)) mm_at(roller_x[k]) motor_mount_coupling();
}
if (P == "v3_slidebed") asm_slide_bed();
if (P == "v3_belts") asm_belts();
if (P == "v3_rollers") asm_rollers();
if (P == "v3_rods") asm_rods();
if (P == "v3_collars_f") collars(-1);
if (P == "v3_collars_b") collars(1);
if (P == "v3_mm_screws") mm_screws();
if (P == "v3_tray_a") tray_T() tray_floor_section(0, true, false);
if (P == "v3_tray_b") tray_T() translate([sec_w, 0, 0]) tray_floor_section(2, false, true);
if (P == "v3_tray_lscr") tray_lower_screws();
if (P == "v3_shelf") tray_T() translate([0, 0, floor_h]) { floor_shelf_half(0); floor_shelf_half(1); }
if (P == "v3_tray_c") tray_T() translate([0, 0, floor_h + shelf_h]) tray_floor_section(4, true, false);
if (P == "v3_tray_d") tray_T() translate([sec_w, 0, floor_h + shelf_h]) tray_floor_section(6, false, true);
if (P == "v3_tray_sscr") tray_stack_screws();
