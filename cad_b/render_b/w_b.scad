// Option B assembly video: every part and fastener in machine (world) coordinates.
// openscad --backend=manifold -D 'part="v3_pedestal"' -o pedestal.stl w_b.scad
// Arm shown at yaw_v (pointing at bin 4) with the links level (th_v = 0).
include <../b_parts.scad>
include <hw_common.scad>
part = "v3_none";
P = part;
yaw_v = 110; th_v = 0;
module ARM() rotate([0, 0, yaw_v]) children();
module LA() ARM() translate([r_p1, 0, z_p1]) rotate([0, -th_v, 0]) translate([-r_p1, 0, -z_p1]) children();
module LB() ARM() translate([r_p1, 0, z_p2]) rotate([0, -th_v, 0]) translate([-r_p1, 0, -z_p2]) children();
module HND() ARM() translate([L * cos(th_v) - L, 0, L * sin(th_v)]) children();
module ST(i) rotate([0, 0, st_angle(i)]) children();
feet_xy = [for (x = [-280, 280], y = [board_y0 + 25, board_y0 + board_y - 25]) [x, y]];
fb = -board_t;                                      // board underside
ls_top_plate_z = tt_z0;                             // bearing top face
// electronics stand-ins (no mounts designed yet): name, centre, size
el = [["pump", [-215, -240], [40, 90, 36]], ["relay", [-150, -240], [26, 34, 18]], ["pca", [-85, -245], [62, 25, 12]],
      ["tmc", [60, -240], [15, 20, 14]], ["hx711", [105, -240], [21, 34, 5]], ["drok", [170, -240], [26, 45, 14]]];
module elbox(n) for (e = el) if (e[0] == n) translate([e[1][0] - e[2][0] / 2, e[1][1] - e[2][1] / 2, 0]) cube(e[2]);

// ── base ──
if (P == "v3_board") translate([-board_x / 2, board_y0, -board_t]) cube([board_x, board_y, board_t]);
if (P == "v3_feet") for (f = feet_xy) translate([f[0], f[1], fb - 14]) foot();
if (P == "v3_feet_scr") for (f = feet_xy) at_screw([f[0], f[1], fb - 12], [0, 0, 1]) shcs(16);
// ── yaw base ──
if (P == "v3_pedestal") pedestal();
if (P == "v3_ped_scr") for (a = [45, 135, 225, 315]) rotate([0, 0, a]) at_screw([106, 0, 4]) shcs(12);
if (P == "v3_motor") color("DimGray") translate([-nm_sq / 2, -nm_sq / 2, deck_z0 - nm_h]) cube([nm_sq, nm_sq, nm_h]);
if (P == "v3_motor_shaft") { translate([0, 0, deck_z0]) cylinder(d = nm_boss_d, h = nm_boss_h); translate([0, 0, deck_z0]) cylinder(d = nm_shaft_d, h = nm_shaft_l); }
if (P == "v3_deck") deck();
if (P == "v3_motor_scr") for (x = [-1, 1], y = [-1, 1]) at_screw([x * nm_hole / 2, y * nm_hole / 2, deck_top]) shcs(8);
if (P == "v3_deck_scr") for (a = [0, 90, 180, 270]) rotate([0, 0, a + 22.5]) at_screw([deck_screw_r, 0, deck_top - 3]) shcs(10);
if (P == "v3_bearing") lazy_susan_ref();
if (P == "v3_bear_top_scr") ARM() for (x = [-1, 1], y = [-1, 1]) at_screw([x * ls_pitch_top / 2, y * ls_pitch_top / 2, tt_z0 - 1.2], [0, 0, 1]) shcs(6);
if (P == "v3_bear_bot_scr") for (x = [-1, 1], y = [-1, 1]) translate([x * ls_pitch_bot / 2, y * ls_pitch_bot / 2, tt_z0 - 2]) { washer(); translate([0, 0, 0.5]) shcs(6); }   // drawn on the slab top: the bearing is one block here
if (P == "v3_turntable") ARM() turntable();
if (P == "v3_collar") ARM() collar();
if (P == "v3_collar_ss") ARM() { at_screw([col_d / 2 + 0.5, 0, col_ss_z], [-1, 0, 0]) shcs(6); translate([4.3, 0, col_ss_z]) rotate([0, 90, 0]) rotate([0, 0, 30]) hexnut(); }
if (P == "v3_collar_scr") ARM() for (e = col_ears) at_screw([e[0], e[1], col_z0 + col_h]) shcs(10);
if (P == "v3_cradle") switch_cradle();
if (P == "v3_switch") switch_ref();
if (P == "v3_cradle_scr") rotate([0, 0, sw_az - 180]) for (y = [-10, 10]) translate([-(ms_r0 + ms_w + 3 + 7), y, 4]) { washer(); translate([0, 0, 0.5]) shcs(12); }
// ── lift arm ──
if (P == "v3_servo") ARM() { translate([lsv_x0, lsv_bot_y, z_p1 - sv_w / 2]) cube([sv_l, sv_case_h, sv_w]);
                            translate([lsv_xc - sv_tab_span / 2, lsv_tab_y, z_p1 - sv_w / 2]) cube([sv_tab_span, sv_tab_t, sv_w]);
                            translate([r_p1, 0, z_p1]) ycyl(12, lsv_bot_y, lsv_spline_y); }
if (P == "v3_servo_scr") ARM() for (x = [lsv_xc - sv_hole_p / 2, lsv_xc + sv_hole_p / 2], dz = [-sv_hole_dx / 2, sv_hole_dx / 2]) {
    at_screw([x, lsv_tab_y + sv_tab_t, z_p1 + dz], [0, -1, 0]) shcs(12);
    translate([x, mast_y0, z_p1 + dz]) rotate([90, 0, 0]) hexnut(); }
if (P == "v3_horn") ARM() translate([r_p1, 0, z_p1]) ycyl(horn_d, link_y0 - horn_t, link_y0);
if (P == "v3_link_a") LA() link_a();
if (P == "v3_horn_scr") LA() for (a = [45, 135, 225, 315]) at_screw([r_p1 + 7 * cos(a), link_y0 + 3, z_p1 + 7 * sin(a)], [0, -1, 0]) shcs(6, d = 2.5, hd = 4.5, hh = 2.5);
if (P == "v3_link_b") LB() link_b();
if (P == "v3_p2_pin") ARM() { translate([r_p1, link_y0, z_p2]) ycyl(6, 0, link_t + 0.3); at_screw([r_p1, link_y0 + link_t + 0.3, z_p2], [0, -1, 0]) shcs(16); }
if (P == "v3_hand") HND() hand();
if (P == "v3_hand_pins") HND() for (z = [z_p1, z_p2]) { translate([hx_piv, link_y0, z]) ycyl(6, 0, link_t + 0.3); at_screw([hx_piv, link_y0 + link_t + 0.3, z], [0, -1, 0]) shcs(16); }
if (P == "v3_contacts") HND() for (p = concat(contact_pts, [bump_pt])) translate([p[0], p[1], hand_zt]) bhcs(6);
if (P == "v3_slider") HND() slider();
if (P == "v3_tee") HND() tee_ref();
if (P == "v3_cup") HND() cup_ref(cup_lip_z(0));
if (P == "v3_ring608") HND() ring608_ref();
if (P == "v3_cap") HND() cap();
if (P == "v3_cap_scr") HND() at_screw([R, 0, ring_z0 + 9.5]) shcs(8);
// ── stations ──
if (P == "v3_hopper") ST(st_hopper) hopper();
if (P == "v3_hopper_scr") ST(st_hopper) for (s = [-1, 1]) at_screw([R - (hop_in_l + 2 * wall) / 2 - 4, s * 20, 4]) shcs(12);
for (i = [2 : n_st - 1]) if (P == str("v3_bin", i - 1)) ST(i) bin();
for (i = [2 : n_st - 1]) if (P == str("v3_bin", i - 1, "_scr")) ST(i) for (s = [-1, 1]) at_screw([bin_ear_r, s * 22, 4]) shcs(12);
// ── scan / weigh ──
if (P == "v3_cell_block") ST(st_scan) cell_block();
if (P == "v3_cellblk_scr") ST(st_scan) for (y = [-9, 9]) at_screw([cell_x0 - 14 + 6, y, cell_z0 - 2]) shcs(12);
if (P == "v3_cell_scr_up") ST(st_scan) for (x = [cell_holes_x[0], cell_holes_x[1]]) at_screw([x, 0, 4], [0, 0, 1]) shcs(10, d = 4, hd = 7, hh = 4);
if (P == "v3_cell") ST(st_scan) cell_ref();
if (P == "v3_bed") ST(st_scan) bed();
if (P == "v3_bed_scr") ST(st_scan) for (x = [cell_holes_x[2], cell_holes_x[3]]) at_screw([x, 0, bed_top - 4.3], [0, 0, -1]) shcs(10, d = 4, hd = 7, hh = 4);
// ── camera tower ──
if (P == "v3_post") ST(st_scan) tower_post();
if (P == "v3_post_scr") ST(st_scan) for (dx = [-16, 16], dy = [-16, 16]) at_screw([tx + dx, ty + dy, 5]) shcs(12);
if (P == "v3_boom") ST(st_scan) boom();
if (P == "v3_boom_scr") ST(st_scan) at_screw([tx + post_w / 2 + sleeve_t + 6, ty, boom_z0 + boom_t - sleeve_h / 2], [-1, 0, 0]) shcs(10);
if (P == "v3_camera") ST(st_scan) { translate([R - 12.5, -12, boom_z0 - 1.6]) cube([25, 24, 1.6]); translate([R - 4, -4, cam_lens_z + 2]) cube([8, 8, boom_z0 - 1.6 - cam_lens_z - 2]); translate([R, 0, cam_lens_z]) cylinder(d = 6, h = 2); }
if (P == "v3_cam_scr") ST(st_scan) for (dx = [-10.5, 10.5], dy = [-6.25, 6.25]) at_screw([R + dx, dy, boom_z0 - 2.6], [0, 0, 1]) shcs(5, d = 2, hd = 3.8, hh = 1.6);
if (P == "v3_lens_frame") ST(st_scan) lens_frame();
if (P == "v3_lens") ST(st_scan) translate([R - gl_w / 2 + 1, -gl_h / 2 + 1, cam_lens_z - 4 + 1.2]) cube([gl_w - 2, gl_h - 2, 2.2]);
if (P == "v3_lens_scr") ST(st_scan) for (dx = [-14, 14]) at_screw([R + dx, -11, cam_lens_z - 4], [0, 0, 1]) shcs(16);
if (P == "v3_pi") ST(st_scan) translate([(R + tx) / 2, ty / 2, boom_z0 + boom_t + 3]) rotate([0, 0, boom_ang]) translate([-32.5, -15, 0]) cube([65, 30, 1.6]);
if (P == "v3_pi_scr") ST(st_scan) for (dx = [-29, 29], dy = [-11.5, 11.5]) translate([(R + tx) / 2, ty / 2, boom_z0 + boom_t + 4.6]) rotate([0, 0, boom_ang]) translate([dx, dy, 0]) shcs(8, d = 2.5, hd = 4.5, hh = 2);
if (P == "v3_pi_standoffs") ST(st_scan) for (dx = [-29, 29], dy = [-11.5, 11.5]) translate([(R + tx) / 2, ty / 2, boom_z0 + boom_t]) rotate([0, 0, boom_ang]) translate([dx, dy, 0]) cylinder(d = 4.5, h = 3, $fn = 6);
if (P == "v3_ring_holder") ST(st_scan) ring_holder();
if (P == "v3_ring_scr") ST(st_scan) at_screw([tx + post_w / 2 + sleeve_t + 6, ty, ring_z], [-1, 0, 0]) shcs(10);
if (P == "v3_led_ring") ST(st_scan) translate(ring_c) rotate([0, 0, atan2(ring_aim[1], ring_aim[0])]) rotate([0, 90 + atan2(-ring_aim[2], norm([ring_aim[0], ring_aim[1]])), 0]) translate([0, 0, 2]) difference() { cylinder(d = 37.5, h = 1.6); translate([0, 0, -1]) cylinder(d = 23, h = 4); }
// ── cable post, tube, electronics ──
if (P == "v3_cable_post") cable_post();
if (P == "v3_cpost_scr") for (x = [-18, 18], y = [-18, 18]) at_screw([cable_post_xy[0] + x, cable_post_xy[1] + y, 5]) shcs(12);
mt = [for (x = [50, 60]) [x * cos(yaw_v), x * sin(yaw_v)]];                 // mast-top zip-tie slots (world xy)
hand_tee = [R * cos(yaw_v), R * sin(yaw_v)];
if (P == "v3_tube") chain([[hand_tee[0] + 14 * cos(yaw_v + 90), hand_tee[1] + 14 * sin(yaw_v + 90), slider_z0 + 5], [hand_tee[0] * 0.92, hand_tee[1] * 0.92, 95],
                          [mt[1][0], mt[1][1], mast_top + 4], [mt[0][0] * 0.5, mt[0][1] * 0.5 - 40, mast_top + 30], [0, -150, 152], [6, -172, 140], [6, -172, 20], [-60, -210, 8], [-215, -240, 30]], 4);
if (P == "v3_leads") chain([[mt[0][0], mt[0][1], mast_top + 2], [mt[0][0] * 0.4, mt[0][1] * 0.4 - 50, mast_top + 26], [-4, -152, 150], [-6, -172, 138], [-6, -172, 18], [-40, -200, 6], [-85, -235, 12]], 3);
if (P == "v3_zipties") { for (m = mt) translate([m[0], m[1], mast_top - 4]) rotate([0, 0, yaw_v]) difference() { cube([4, 12, 10], center = true); cube([2, 8.5, 12], center = true); }
                        translate([0, -144, 144.5]) difference() { cube([26, 4, 6], center = true); cube([22, 6, 3], center = true); } }
for (e = el) if (P == str("v3_el_", e[0])) elbox(e[0]);
