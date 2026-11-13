// v3 assembly video: cradle-shuttle parts in machine coordinates (step 10).
// Home pose (carriage Y 0, tilt frame level) unless a part name says _col3 / _col0.
// openscad --backend=manifold -D 'part="v3_sh_sled"' -o sh_sled.stl w_shuttle.scad
include <../shuttle.scad>
include <hw_common.scad>
part = "v3_sh_sled";
P = part;
base_top = sg_base_top();

module c2_crank_posed(yc) { Pv = sg_c2_pivot(); translate([Pv[0], Pv[1], 0]) rotate(sg_c2_psi(yc)) c2_crank(); }
module c2_hornscr_posed(yc) { Pv = sg_c2_pivot(); translate([Pv[0], Pv[1], 0]) rotate(sg_c2_psi(yc)) c2_horn_screws(); }
module c2_tip_posed(yc) { Pv = sg_c2_pivot(); translate([Pv[0], Pv[1], 0]) rotate(sg_c2_psi(yc)) c2_tip_pin(); }
module c2_link_posed(yc) {
    T = sg_c2_tip(yc); pin = [sg_c2_pivot()[0], yc + sg_c2_pin_dy()];
    translate([T[0], T[1], 0]) rotate(atan2(pin[1] - T[1], pin[0] - T[0]) - 90) c2_link();
}
module cell_scr_tf() for (y = [-3, 3]) translate([cxc + 20, y, 65]) { cylinder(d = 5.5, h = 3, $fn = 24); cylinder(d = 3, h = 15, $fn = 16); }
module cell_scr_cr() for (y = [-3, 3]) translate([cxc - 20, y, czt - 9]) { cylinder(d = 5.5, h = 3, $fn = 24); cylinder(d = 3, h = 13, $fn = 16); }
module ptfe() {   // 0.1 mm skived PTFE on the bed + 18° kick (drawn 0.25 thick)
    translate([bx0 + 0.5, -sg_guide_hw() + 0.3, bz]) cube([bend - bx0 - 0.5, 2 * sg_guide_hw() - 0.6, 0.25]);
    translate([bend, -sg_guide_hw() + 0.3, bz]) rotate([0, -sg_kick_a(), 0]) cube([sg_kick_l(), 2 * sg_guide_hw() - 0.6, 0.25]);
}
module rbar_screws() for (s = [-1, 1]) at_screw([99.5, s * 10, rb_top() - 3.3]) shcs(10);
module post_anchors() for (h = sh_end_post_holes()) at_screw([h[0], h[1], base_top + 4]) shcs(20);
module ramp_screws() for (y = [-105, -45, 45, 105]) at_screw([140, y, base_top + 4]) shcs(20);
module reject_screws() for (x = [200, 230], y = [165, 195]) at_screw([x, y, base_top + 2.5]) csk(18);

// moving group, per material, at carriage Y = yc (tilt frame level)
module mv_carriage(yc) translate([0, yc, 0]) { carriage(); tilt_drive_posed("level"); }
module mv_tf(yc) translate([0, yc, 0]) tilt_frame();
module mv_cradle(yc) translate([0, yc, 0]) { cradle(); ptfe(); }
module mv_steel(yc) { translate([0, yc, 0]) { sh_lm8uu(); sh_cheek_screws(); sh_cheek_dowels(); load_cell(); sh_cell_screws(); f_pins(); pin_a(); } }
module mv_c2crank(yc) { c2_crank_posed(yc); c2_hornscr_posed(yc); }
module mv_c2pins(yc) { c2_tip_posed(yc); translate([0, yc, 0]) c2_drive_pin(); }

// bench order
if (P == "v3_sh_tf") tilt_frame();
if (P == "v3_sh_fpins") f_pins();
if (P == "v3_sh_ptfe") ptfe();
if (P == "v3_sh_cradle") cradle();
if (P == "v3_sh_cell") load_cell();
if (P == "v3_sh_cellscr_tf") cell_scr_tf();
if (P == "v3_sh_cellscr_cr") cell_scr_cr();
if (P == "v3_sh_sled") sled();
if (P == "v3_sh_lm8uu") sh_lm8uu();
if (P == "v3_sh_dowels") sh_cheek_dowels();
if (P == "v3_sh_tdrive") tilt_drive_posed("level");
if (P == "v3_sh_pina") pin_a();
if (P == "v3_sh_cheek_neg") cheek(-1);
if (P == "v3_sh_cheek_pos") cheek(1);
if (P == "v3_sh_cheekscr") sh_cheek_screws();
if (P == "v3_sh_post_neg") end_post_neg();
if (P == "v3_sh_post_pos") end_post_pos();
if (P == "v3_sh_c1servo") c1_servo();
if (P == "v3_sh_c1cpl") c1_coupler(sg_crank_phi("hold"));
if (P == "v3_sh_c1scr") c1_ear_screws();
if (P == "v3_sh_688") sh_688zz();
if (P == "v3_sh_rod") rod8(rod, sh_rod_y()[0], sh_rod_y()[1]);
if (P == "v3_sh_rex") rex_shaft();
if (P == "v3_sh_rodscr") sh_rod_grub_screws();
if (P == "v3_sh_rbar_neg") rbar_neg();
if (P == "v3_sh_rbar_pos") rbar_pos();
if (P == "v3_sh_rbarscr") rbar_screws();
if (P == "v3_sh_c2servo") c2_servo();
if (P == "v3_sh_c2horn") c2_horn();
if (P == "v3_sh_c2crank") c2_crank_posed(0);
if (P == "v3_sh_c2hornscr") c2_hornscr_posed(0);
// crank parked at psi ≈ 100° (§13.5 step 6) while the module goes in, before the link is fitted
if (P == "v3_sh_c2crank_park") translate([sg_c2_pivot()[0], sg_c2_pivot()[1], 0]) rotate(100) c2_crank();
if (P == "v3_sh_c2hornscr_park") translate([sg_c2_pivot()[0], sg_c2_pivot()[1], 0]) rotate(100) c2_horn_screws();
if (P == "v3_sh_c2ear_rear") c2_ear_screws_at(sg_c2_ear_y()[1]);
if (P == "v3_sh_c2ear_front") c2_ear_screws_at(sg_c2_ear_y()[0]);
if (P == "v3_sh_anchors") post_anchors();
if (P == "v3_sh_c2link") c2_link_posed(0);
if (P == "v3_sh_c2tip") c2_tip_posed(0);
if (P == "v3_sh_c2drive") c2_drive_pin();
if (P == "v3_sh_ramp_neg") ramp_neg();
if (P == "v3_sh_ramp_pos") ramp_pos();
if (P == "v3_sh_rampscr") ramp_screws();
if (P == "v3_sh_reject") reject_bin();
if (P == "v3_sh_rejectscr") reject_screws();
// pose variants for the ramp / reject-bin segments (carriage at column 3 / column 0)
for (c = [["col3", 3], ["col0", 0]]) let(yc = sg_target_y(c[1])) {
    if (P == str("v3_var_", c[0], "_carriage")) mv_carriage(yc);
    if (P == str("v3_var_", c[0], "_tf")) mv_tf(yc);
    if (P == str("v3_var_", c[0], "_cradle")) mv_cradle(yc);
    if (P == str("v3_var_", c[0], "_steel")) mv_steel(yc);
    if (P == str("v3_var_", c[0], "_c2crank")) mv_c2crank(yc);
    if (P == str("v3_var_", c[0], "_c2link")) c2_link_posed(yc);
    if (P == str("v3_var_", c[0], "_c2pins")) mv_c2pins(yc);
}
