// v3 assembly video: pick-arm parts in machine coordinates (step 8), parked (servo 90°).
// openscad --backend=manifold -D 'part="v3_arm_head"' -o arm_head.stl w_arm.scad
include <../suction_arm.scad>
include <hw_common.scad>
part = "v3_arm_head";
P = part;
th = pa_theta(s_park);
H  = [R * cos(th), 0, R * sin(th)];          // hand origin A' (A-local)
module A() translate([px, 0, pz]) children();
module HAND() A() translate(H) children();
module LIP() HAND() translate([0, 0, -h_cup]) children();   // lip frame (z 0 = free cup lip)

module gdowels() for (g = [[gB, lb_y1], [gC, lc_y1]]) at_xz(g[0]) ycyl(dowel_d / 2, gp_y0, g[1] + 1, 16);
module gsleeves() { at_xz(gB) ycyl(slv_d / 2, gp_y1 - eps, lb_y0 - slv_gap, 24); at_xz(gC) ycyl(slv_d / 2, gp_y1 - eps, lc_y0 - slv_gap, 24); }
module tab_screws() for (h = sv_holes) at_screw([h[0], gp_y0 - sv_tab_t, h[1]], [0, 1, 0]) shcs(8);
module horn_screws() rotate([0, -th, 0]) for (a = [0, 90, 180, 270]) rotate([0, -a - 45, 0])
    at_screw([8, cr_y1 - 3, 0], [0, -1, 0]) shcs(6);
module washers() {
    for (g = [[gB, lb_y1], [gC, lc_y1]]) at_xz(g[0]) ycyl(4.5, g[1], g[1] + 0.5, 20);          // ground pin ends
    translate(H) {
        at_xz(gB) ycyl(4.5, lb_y0 - 0.5, lb_y0, 20);                                         // B' end
        at_xz(gC) ycyl(4.5, lc_y0 - 0.5, lc_y0, 20);                                         // C' end
        ycyl(6.5, cr_y0 - 1.5, cr_y0 - 1.0, 24);                                             // A' tube end (Ø8)
    }
}
module springs() for (s = [-1, 1]) translate([s * rod_dx, 0, sl_z1]) difference() {
    cylinder(d = 5, h = beam_z[0] + h_cup - sl_z1, $fn = 16); translate([0, 0, -1]) cylinder(d = 4.2, h = 40, $fn = 12);
}
module tower_bolts() for (h = foot_holes) at_screw([h[0], h[1], frame_base_top() + foot_t]) shcs(20);
module head_bolts() for (b = hd_bolts) at_screw([px + b[0], b[1], pz + hd_floor[1]]) shcs(12);
// vacuum tube on the arm: barb → loop → through the A' tube → spoke → anchor → down the column
module arm_tube() let(h = [px, 0, pz] + H, bz = h[2] - h_cup + pad_top + web_t + 12)
    chain([[h[0], 0, bz], [h[0] + 9, -8, h[2] - 14], [h[0] + 9, -28, h[2] - 6], [h[0], -34, h[2]],
           [h[0], cr_y0 - 1.5, h[2]], [px, anc_y[1], pz], [px, anc_y[0] - 1, pz], [px, -160, pz],
           [px + 8, -160, pz - 8], [px + 8, -160, 18]], 4);
module zip_ties() for (z = [55, 80]) translate([px, (col_y[0] + 2.5 + 1.1), z + 2]) difference() {
    cube([2 * col_hx + 3, 9, 2.5], center = true); cube([2 * col_hx + 0.6, 6.6, 4], center = true);
}

if (P == "v3_arm_head") A() head();
if (P == "v3_arm_dowels") A() gdowels();
if (P == "v3_arm_servo") A() mg996r();
if (P == "v3_arm_tabscr") A() tab_screws();
if (P == "v3_arm_horn") A() rotate([0, -th, 0]) horn();
if (P == "v3_arm_crank") A() rotate([0, -th, 0]) crank();
if (P == "v3_arm_hornscr") A() horn_screws();
if (P == "v3_arm_gsleeves") A() gsleeves();
if (P == "v3_arm_linkc") A() at_xz(gC) rotate([0, -th, 0]) link(lc_y0);
if (P == "v3_arm_linkb") A() at_xz(gB) rotate([0, -th, 0]) link(lb_y0);
if (P == "v3_arm_hand") HAND() hand();
if (P == "v3_arm_handpins") HAND() hand_pins();
if (P == "v3_arm_washers") A() washers();
if (P == "v3_arm_sled") LIP() sled();
if (P == "v3_arm_pad") LIP() bellows_pad();
if (P == "v3_arm_barb") LIP() barb_fitting();
if (P == "v3_arm_springs") LIP() springs();
if (P == "v3_arm_guidescr") HAND() guide_screws();
if (P == "v3_arm_tower") tower();
if (P == "v3_arm_headbolts") head_bolts();
if (P == "v3_arm_towerbolts") tower_bolts();
if (P == "v3_arm_tube") arm_tube();
if (P == "v3_arm_zipties") zip_ties();
