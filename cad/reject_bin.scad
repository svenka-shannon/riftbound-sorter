// =============================================
// Riftbound Card Sorter — Reject Bin (bin 9)
// =============================================
// Open box beside the sorting tray at the shuttle's reject position
// (carriage Y 176; tray ends at Y 137). The shuttle tips the card in the
// LOWER pose; a lane with the same −40° → −8° ramp profile as the lower
// ramp (shuttle_geom.scad) slides it into the box. Box inner 66 × 94 mm,
// floor Z 6.5, walls to Z 60, open top for emptying.
//
// PRINT: 1 piece, 115 × 75 × 56 mm (X 159.4..274, Y 138.4..213.6, Z 4..60),
//   upright as modelled, PLA 0.2 mm, 3 walls, 15 %; ≈ 8100 mm² on the bed, no
//   overhangs. The lane surface prints as a 40°→8° slope (layer steps face downhill).
// FASTEN: 4× M3 countersunk through the box floor into the baseplate grid
//   (X 200, 230; Y 165, 195), nut under the board.
// =============================================

use <shuttle_geom.scad>

/* [Export] */
part = "assembly";   // assembly | reject_bin

$fn = 32;
eps = 0.01;
yc   = sg_reject_y();          // 176
xt   = sg_tray_x0();           // 178 — lane exit = box rear inner face
prof = sg_ramp_profile();
x0   = sg_ramp_x0() - 1;
wall = 2;
in_hw = 33;                    // box inner half-width (66)
lane_hw = 35.6;                // lane entry half-width (cradle is ±35.2)
box_x1 = xt + 94;              // inner front face
floor_z = sg_base_top() + 2.5; // 6.5
top_z  = 60;

module xz(y0, y1) translate([0, y1, 0]) rotate([90, 0, 0]) linear_extrude(y1 - y0) children();
module lane_2d()
    polygon(concat([[x0, sg_base_top()], [x0, prof[0][1] - 1.0 * tan(sg_kick_lower_a())]],
                   prof, [[xt, sg_base_top()]]));          // prof ends at (xt, exit Z)

module reject_bin() {
    difference() {
        union() {
            // lane body
            xz(yc - lane_hw - wall, yc + lane_hw + wall) lane_2d();
            // lane side walls (funnel 71.2 → 66), from X 165 so the tipped cradle's corners clear them
            for (s = [-1, 1]) hull() {
                translate([165, yc + s * (lane_hw + wall / 2) - wall / 2, sg_base_top()]) cube([eps, wall, 48 - sg_base_top()]);
                translate([xt, yc + s * (in_hw + wall / 2) - wall / 2, sg_base_top()]) cube([eps, wall, 48 - sg_base_top()]);
            }
            // box
            translate([xt, yc - in_hw - wall, sg_base_top()]) cube([box_x1 + wall - xt, 2 * (in_hw + wall), top_z - sg_base_top()]);
        }
        // box cavity
        translate([xt - eps, yc - in_hw, floor_z]) cube([box_x1 - xt + eps, 2 * in_hw, top_z]);
        // lane cavity above the surface between the walls (funnel)
        hull() {
            translate([x0 - 1, yc - lane_hw - wall - 1, prof[0][1] - 0.5]) cube([165 - x0 + 1, 2 * (lane_hw + wall + 1), 60]);
        }
        hull() {
            translate([165, yc - lane_hw, prof[0][1] - 0.5]) cube([eps, 2 * lane_hw, 60]);
            translate([xt, yc - in_hw, prof[len(prof) - 1][1] - 0.5]) cube([eps, 2 * in_hw, 60]);
        }
        // countersunk M3 to the baseplate
        for (x = [200, 230]) for (y = [165, 195]) translate([x, y, 0]) {
            cylinder(d = 3.4, h = 20, $fn = 16);
            translate([0, 0, floor_z - 1.3]) cylinder(d1 = 3.4, d2 = 6.2, h = 1.31, $fn = 24);
        }
        // finger notch on the front wall for emptying
        translate([box_x1 - 1, yc, top_z]) rotate([0, 90, 0]) cylinder(d = 30, h = wall + 2, $fn = 48);
    }
    // restore the lane surface inside the funnel cut
    intersection() {
        xz(yc - lane_hw, yc + lane_hw) lane_2d();
        union() {
            translate([x0 - 1, yc - lane_hw - wall, 0]) cube([165 - x0 + 1 + eps, 2 * (lane_hw + wall), 60]);
            hull() {
                translate([165, yc - lane_hw, 0]) cube([eps, 2 * lane_hw, 60]);
                translate([xt, yc - in_hw, 0]) cube([eps, 2 * in_hw, 60]);
            }
        }
    }
}

module asm_reject_bin() color("IndianRed") reject_bin();

if (part == "assembly" || part == "reject_bin") reject_bin();
