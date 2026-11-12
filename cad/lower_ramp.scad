// =============================================
// Riftbound Card Sorter — Lower Ramp + Upper Lead-in (fixed, belt end)
// =============================================
// Sits on the baseplate directly behind the sorting tray's open back
// (tray back face X 178). Two identical-in-function halves (Y −137..0 and
// 0..137), one per tray section, each with two card lanes.
//
// LOWER LANES: the cradle's kick, tipped to −40° in the LOWER pose, ends
// 1 mm before the ramp entry and 1.5 mm above it. The ramp continues the
// −40° line, then curves (R 20) to −8° and releases the card at the tray
// back face, ~20 mm above the lower slot floor (Z 6.5). Profile comes from
// shuttle_geom.scad (sg_ramp_profile), so it follows any pose change.
// Dividers line up with the tray's walls/dividers; their tops are 0.6 mm
// ridges with 1 mm rounds so a card edge that lands on one slides off.
//
// UPPER LEAD-IN: in the last 4 mm before the tray (X 174..178) the dividers
// carry on up to Z 104 as fins that taper from knife edges (X 174) to the
// tray wall thickness (X 175): a ±2 mm funnel for the card leaving the
// cradle lip (Z ≈ 85) for the upper slot (floor 74.5). A top bar at
// Z 100..104 (above every cradle pose and card path) ties the fins.
//
// PRINT: 2 parts (ramp_neg, ramp_pos), 15 × 137 × 100 mm, standing on the
//   −X (rear) face so the lane surface is a vertical wall and the layer lines
//   run along the card's slide direction. PLA, 0.16 mm, 3 walls, 15 %.
//   Sand the lane surface lightly with 600 grit; no supports.
// FASTEN: 2× M3 per half through the rear floor tabs into the baseplate grid
//   (X 140; Y ±45, ±105) + nut under the board.
// =============================================

use <shuttle_geom.scad>

/* [Export] */
part = "assembly";   // assembly | ramp_neg | ramp_pos

$fn = 32;
eps = 0.01;
xt  = sg_tray_x0();               // 175
prof = sg_ramp_profile();
x0  = sg_ramp_x0() - 1;           // rear face
fin_x0 = xt - 4;                 // fin knife edge X 171 (cradle lip ≤ 172.5 in every pose)
bar_z  = [100, 104];
div_h  = 8;                       // divider height above the lane surface

function ramp_z_at(x) =           // lane surface height at X (linear interp of the profile)
    x <= prof[0][0] ? prof[0][1] :
    let(i = max([for (k = [0 : len(prof) - 2]) if (prof[k][0] <= x) k]))
    i >= len(prof) - 1 ? prof[len(prof) - 1][1] :
    prof[i][1] + (prof[i + 1][1] - prof[i][1]) * (x - prof[i][0]) / (prof[i + 1][0] - prof[i][0]);

module xz(y0, y1) translate([0, y1, 0]) rotate([90, 0, 0]) linear_extrude(y1 - y0) children();

module ramp_body_2d()
    polygon(concat([[x0, sg_base_top()], [x0, prof[0][1] - 1.0 * tan(sg_kick_lower_a())]],
                   prof, [[xt, prof[len(prof) - 1][1]], [xt, sg_base_top()]]));

// one divider/fin over the wall band [ya, yb]
module divider(ya, yb) {
    yc = (ya + yb) / 2; w = yb - ya;
    // low divider along the lane (ridge top)
    for (i = [0 : len(prof) - 2]) hull() for (p = [prof[i], prof[i + 1]]) {
        translate([p[0], ya, p[1] - 1]) cube([eps, w, 1 + div_h - 1.6]);
        translate([p[0], yc, p[1] + div_h - 0.8]) rotate([0, 90, 0]) cylinder(d = 1.6, h = eps, $fn = 12);
    }
    // upper fin: wedge in plan (knife at X 170 → full band at X 175), up to the top bar
    hull() {
        translate([fin_x0, yc - 0.3, ramp_z_at(fin_x0)]) cube([eps, 0.6, bar_z[1] - ramp_z_at(fin_x0)]);
        translate([xt - eps, ya, ramp_z_at(xt)]) cube([eps, w, bar_z[1] - ramp_z_at(xt)]);
    }
}

module ramp_half(s) {             // s = −1: Y −137..0, +1: Y 0..137
    ylo = s < 0 ? -137 : 0; yhi = s < 0 ? 0 : 137;
    walls = [for (b = sg_tray_walls()) if (b[1] > ylo + 0.1 && b[0] < yhi - 0.1) [max(b[0], ylo), min(b[1], yhi)]];
    difference() {
        union() {
            xz(ylo, yhi) ramp_body_2d();
            for (b = walls) divider(b[0], b[1]);
            translate([fin_x0, ylo, bar_z[0]]) cube([xt - fin_x0, yhi - ylo, bar_z[1] - bar_z[0]]);
            // rear floor tabs to the baseplate grid at X 140
            for (y = s < 0 ? [-105, -45] : [45, 105])
                translate([136, y - 6, sg_base_top()]) cube([x0 - 136 + 1, 12, 4]);
        }
        for (y = s < 0 ? [-105, -45] : [45, 105])
            translate([140, y, 0]) cylinder(d = 3.4, h = 20, $fn = 16);
        // keep the tray's back face plane clean
        translate([xt, ylo - 1, 0]) cube([10, yhi - ylo + 2, 120]);
    }
}
module ramp_neg() ramp_half(-1);
module ramp_pos() ramp_half(1);

module asm_lower_ramp() { color("Plum") { ramp_neg(); ramp_pos(); } }

echo(str("LOWER RAMP: entry X ", sg_ramp_x0(), " Z ", sg_ramp_z0(), " at −", sg_kick_lower_a(),
         "°, R", sg_ramp_R(), " run-out to −", sg_ramp_exit_a(), "°, exit X ", xt, " Z ", sg_ramp_exit_z(),
         " (", sg_ramp_exit_z() - frame_tray_lower(), " mm above the lower slot floor)"));
function frame_tray_lower() = 6.5;

if (part == "assembly") asm_lower_ramp();
if (part == "ramp_neg") ramp_neg();
if (part == "ramp_pos") ramp_pos();
