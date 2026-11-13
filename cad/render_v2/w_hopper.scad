// v3 assembly video: hopper-elevator parts in machine coordinates (step 7), at the
// home pose (carriage at the bottom, flag resting on its stop, no cards).
// openscad --backend=manifold -D 'part="v3_hop_body"' -o hop_body.stl w_hopper.scad
include <../hopper.scad>
include <hw_common.scad>
part = "v3_hop_body";
P = part;
module M() translate([frame_hopper_x(), 0, frame_base_top()]) children();
z = zp_min;
fl_top = car_z0(z) + car_h - t8_len + t8_fl_t;     // T8 flange top (local)
module m2(L) shcs(L, d = 2, hd = 3.8, hh = 1.5);
module m2nut() hexnut(d = 2, af = 4, h = 1.6);

module base_screws() for (h = base_holes) at_screw([h[0], h[1], base_t]) csk(20);
module bsw_screws() for (x = sw_hole_x) {
    at_screw([bsw_x0 + x, bsw_y0, base_t + sw_hole_z], [0, 1, 0]) m2(12);
    translate([bsw_x0 + x, tower_y1, base_t + sw_hole_z]) rotate([-90, 0, 0]) m2nut();
}
module t8_screws() for (sx = [-1, 1]) at_screw([sx * t8_pcd / 2, rod_y, fl_top]) shcs(14);
module plate_screws() for (p = plate_screw) at_screw([p[0], p[1], z]) csk(10);
module cap_screws() for (p = tower_ins) at_screw([p[0], p[1], cap_z0 + cap_t]) shcs(10);
module motor_screws() for (sx = [-1, 1]) at_screw([sx * motor_ear / 2, rod_y + motor_off, motor_face_z + 0.8]) shcs(8);
module flag_axle() at_flag() {
    at_screw([piv[0], cheek_in + cheek_t, piv[1]], [0, -1, 0]) shcs(20);
    translate([piv[0], -cheek_in - cheek_t, piv[1]]) rotate([90, 0, 0]) hexnut(h = 4);
}
module tsw_screws() at_flag() for (x = sw_hole_x) {
    at_screw([tsw_x0 + x, cheek_in + cheek_t, tsw_z0 + sw_hole_z], [0, -1, 0]) m2(12);
    translate([tsw_x0 + x, -sw_t / 2, tsw_z0 + sw_hole_z]) rotate([90, 0, 0]) m2nut();
}

M() {
    if (P == "v3_hop_body") hopper_body();
    if (P == "v3_hop_base_scr") base_screws();
    if (P == "v3_hop_bsw") { hw_sw_bottom_body(); hw_sw_bottom_roller(); }
    if (P == "v3_hop_bsw_scr") bsw_screws();
    if (P == "v3_hop_rods") hw_rods();
    if (P == "v3_hop_lm8uu") hw_bushings(z);
    if (P == "v3_hop_carriage") hopper_carriage(z);
    if (P == "v3_hop_t8nut") hw_nut(z);
    if (P == "v3_hop_t8scr") t8_screws();
    if (P == "v3_hop_lead") hw_screw();
    if (P == "v3_hop_plate") hopper_plate(z);
    if (P == "v3_hop_plate_scr") plate_screws();
    if (P == "v3_hop_coupler") hw_coupler();
    if (P == "v3_hop_cap") hopper_cap();
    if (P == "v3_hop_cap_scr") cap_screws();
    if (P == "v3_hop_motor") hw_motor();
    if (P == "v3_hop_motor_scr") motor_screws();
    if (P == "v3_hop_flag") hopper_flag(phi_rest);
    if (P == "v3_hop_axle") flag_axle();
    if (P == "v3_hop_tsw") { hw_sw_top_body(); hw_sw_top_roller(); }
    if (P == "v3_hop_tsw_scr") tsw_screws();
}
