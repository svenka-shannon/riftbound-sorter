// =========================================================================
// Option B printed parts + reference solids for purchased parts.
//   openscad -D 'part="bin"' -o bin.stl b_parts.scad
// part = bin | hopper | bed | cell_block | yaw_base | roller_sleeve |
//        turntable | link_a | link_b | hand | slider | tower | ring_holder | foot
// Every part is modelled in its installed frame; "print" placement is done by
// export_b.py (rotations listed in PRINT notes per module).
// =========================================================================
include <b_params.scad>

part = "bin";

// ---------- small helpers ----------
module ycyl(d, y0, y1) translate([0, y0, 0]) rotate([-90, 0, 0]) cylinder(d = d, h = y1 - y0);
module xcyl(d, x0, x1) translate([x0, 0, 0]) rotate([0, 90, 0]) cylinder(d = d, h = x1 - x0);
module insert_hole(depth = 6.5) cylinder(d = 4.1, h = depth);       // M3 x 5.7 heat-set
module m3_clear(h) cylinder(d = 3.4, h = h);
module annulus2d(r0, r1) difference() { circle(r = r1, $fn = 360); circle(r = r0, $fn = 360); }
// points between two lines through the origin at +/-a, each moved inward by d
module wedge2d(a, d, rmax = 400)
    intersection() {
        rotate(a) translate([-rmax, -2 * rmax - d]) square([2 * rmax, 2 * rmax]);   // below the +a edge
        rotate(-a) translate([-rmax, d]) square([2 * rmax, 2 * rmax]);              // above the -a edge
    }
// mounting ear: flange with an M3 clearance hole, centred at [x, y]
module ear(x, y, t = 4) translate([x, y, 0]) difference() { cylinder(d = 12, h = t); translate([0, 0, -1]) m3_clear(t + 2); }
module ear_hole(x, y) translate([x, y, -1]) m3_clear(10);

// =========================================================================
// BIN (print 7): fan-shaped pocket, station-local frame (yaw axis at origin,
// station on +X). Shares the 20 deg slot with its neighbours: each bin owns a
// 1.2 mm radial half-wall, so two neighbours make a 2.4 mm divider.
// PRINT: as modelled (floor down), no supports.
// =========================================================================
ear_in_x = bin_r_in - wall - 6; ear_out_x = bin_r_out + wall + 6;
module bin() {
    a = pitch / 2;
    difference() {
        union() {
            linear_extrude(pocket_h) intersection() { annulus2d(bin_r_in - wall, bin_r_out + wall); wedge2d(a, 0); }
            ear(ear_in_x, 0); ear(ear_out_x, 0);
        }
        // pocket
        translate([0, 0, floor_t]) linear_extrude(pocket_h) intersection() { annulus2d(bin_r_in, bin_r_out); wedge2d(a, half_wall); }
        // thumb notch in the outer wall, to lift the stack out
        translate([bin_r_out - 1, -17, 12]) cube([wall + 2, 34, pocket_h]);
        ear_hole(ear_in_x, 0); ear_hole(ear_out_x, 0);
    }
}

// =========================================================================
// HOPPER (print 1): rectangular pocket, 2 mm room each side so the stack stays
// centred under the cup. Same mounting as a bin. PRINT: floor down.
// =========================================================================
module hopper() {
    ow = hop_in_w + 2 * wall; ol = hop_in_l + 2 * wall;
    difference() {
        union() {
            translate([R - ol / 2, -ow / 2, 0]) cube([ol, ow, pocket_h]);
            ear(R - ol / 2 - 6, 0); ear(R + ol / 2 + 6, 0);
        }
        translate([R - hop_in_l / 2, -hop_in_w / 2, floor_t]) cube([hop_in_l, hop_in_w, pocket_h]);
        // notches in both short walls: load and unload with fingers
        for (s = [-1, 1]) translate([R + s * (hop_in_l / 2 + wall / 2) - wall, -15, 10]) cube([2 * wall, 30, pocket_h]);
        ear_hole(R - ol / 2 - 6, 0); ear_hole(R + ol / 2 + 6, 0);
    }
}

// =========================================================================
// SCAN / WEIGH PLATFORM: the owned 5 kg bar cell, radial, fixed end inboard.
// cell_block (print 1) holds the fixed end 8 mm up; bed (print 1) sits on the
// free end on a 2 mm boss. M4 x 10 SHCS x 4 (2 up through the block, 2 down
// through the bed, heads recessed below the bed top).
// =========================================================================
cell_x0 = R - cell_l / 2;              // 222.5
cell_z0 = 8;
cell_holes_x = [R - cell_hole_outer / 2, R - cell_hole_inner / 2, R + cell_hole_inner / 2, R + cell_hole_outer / 2];
module cell_ref() color("Silver") difference() {
    translate([cell_x0, -cell_s / 2, cell_z0]) cube([cell_l, cell_s, cell_s]);
    for (x = cell_holes_x) translate([x, 0, cell_z0 - 1]) cylinder(d = 4, h = cell_s + 2);
}
module cell_block() {
    bx0 = cell_x0 - 14; bx1 = cell_holes_x[1] + 7;
    difference() {
        translate([bx0, -14, 0]) cube([bx1 - bx0, 28, cell_z0]);
        for (x = [cell_holes_x[0], cell_holes_x[1]]) translate([x, 0, -1]) { cylinder(d = 4.5, h = 20); cylinder(d = 7.6, h = 1 + 4); }
        for (y = [-9, 9]) translate([bx0 + 6, y, -1]) { m3_clear(20); translate([0, 0, cell_z0 - 2]) cylinder(d = 6.2, h = 10); }
    }
}
bed_z0 = bed_top - bed_t;               // 22.7
module bed() {
    boss_x0 = cell_holes_x[2] - 7; boss_x1 = cell_x0 + cell_l;
    difference() {
        union() {
            translate([R - bed_l / 2, -bed_w / 2, bed_z0]) cube([bed_l, bed_w, bed_t]);
            translate([boss_x0, -cell_s / 2, cell_z0 + cell_s]) cube([boss_x1 - boss_x0, cell_s, bed_z0 - cell_z0 - cell_s + eps]);
        }
        for (x = [cell_holes_x[2], cell_holes_x[3]]) translate([x, 0, 0]) { cylinder(d = 4.5, h = 40); translate([0, 0, bed_top - 4.3]) cylinder(d = 7.6, h = 10); }
    }
}

// =========================================================================
// YAW BASE (print 1, PETG): holds the yaw MG996R spline-up at the origin (case
// toward -Y) and four 608ZZ rollers that catch the turntable rim if it sags.
// Servo tabs rest on the two end blocks (Z 28.9), M3 x 10 + washer into inserts.
// =========================================================================
yb_t = 4;
sv_yc = -(sv_l / 2 - sv_shaft_off);              // case centre Y (-10.15)
yaw_tab_z = yaw_sv_bot + sv_tab_z0;              // 28.9
module yaw_servo_ref() color("RoyalBlue") {
    translate([-sv_w / 2, sv_yc - sv_l / 2, yaw_sv_bot]) cube([sv_w, sv_l, sv_case_h]);
    translate([-sv_w / 2, sv_yc - sv_tab_span / 2, yaw_tab_z]) cube([sv_w, sv_tab_span, sv_tab_t]);
    translate([0, 0, yaw_sv_bot]) cylinder(d = 12, h = sv_h);
    color("Silver") translate([0, 0, tt_z0 - horn_t]) cylinder(d = horn_d, h = horn_t);
}
roller_cz = tt_z0 - roller_gap - 11;             // 608: OD 22
module roller_post(az) rotate([0, 0, az]) difference() {
    union() for (r = [roller_r - 3.5 - 0.4 - 4, roller_r + 3.5 + 0.4]) translate([r, -8, 0]) cube([4, 16, roller_cz + 7]);
    translate([0, 0, roller_cz]) xcyl(3.4, roller_r - 15, roller_r + 15);
}
module roller_ref(az) color("Silver") rotate([0, 0, az]) translate([0, 0, roller_cz]) difference() { xcyl(22, roller_r - 3.5, roller_r + 3.5); xcyl(8, roller_r - 5, roller_r + 5); }
module yaw_base() {
    hy = [for (s = [-1, 1]) sv_yc + s * sv_hole_p / 2];   // 14.6, -34.9
    difference() {
        union() {
            translate([-60, -60, 0]) cube([120, 120, yb_t]);
            // tab blocks
            for (y = hy) translate([-12, y - 4, 0]) cube([24, 8, yaw_tab_z]);
            // side cheeks (locate the case)
            for (s = [-1, 1]) translate([s * (sv_w / 2 + 0.4) + (s < 0 ? -3 : 0), sv_yc - 15, 0]) cube([3, 30, 20]);
            for (az = [45, 135, 225, 315]) roller_post(az);
        }
        // servo recess: 2 mm into the plate
        translate([-sv_w / 2 - 0.4, sv_yc - sv_l / 2 - 0.4, yaw_sv_bot]) cube([sv_w + 0.8, sv_l + 0.8, 50]);
        translate([0, 0, -1]) cylinder(d = 14, h = 10);                     // spline boss / cable
        // lead slot out of the -Y end
        translate([-5, sv_yc - sv_l / 2 - 10, yaw_sv_bot]) cube([10, 12, 8]);
        for (y = hy, x = [-sv_hole_dx / 2, sv_hole_dx / 2]) translate([x, y, yaw_tab_z - 6.5]) insert_hole();
        for (x = [-52, 52], y = [-52, 52]) translate([x, y, -1]) m3_clear(10);
    }
}
// PRINT 4: 7.0 long sleeve, OD 7.9 (fits the 608 bore), M3 axle through it
module roller_sleeve() difference() { cylinder(d = 7.9, h = 7.0); translate([0, 0, -1]) cylinder(d = 3.4, h = 10); }

// =========================================================================
// TURNTABLE + MAST (print 1, PETG): arm-local frame. Plate screws to the yaw
// horn from above (4 x M2 self-tap through radial slots + centre access hole).
// The mast wall carries the lift MG996R on its +Y face (axis along Y, case
// lying along X under P1) and the P2 boss for link B.
// =========================================================================
lsv_spline_y = link_y0 - horn_gap;              // 6.6
lsv_bot_y = lsv_spline_y - sv_h;                // -36.3
lsv_tab_y = lsv_bot_y + sv_tab_z0;              // -9.5 (tab underside)
lsv_xc = r_p1 - (sv_l / 2 - sv_shaft_off);      // case centre X 14.85
mast_y0 = lsv_tab_y - 7; mast_y1 = lsv_tab_y;
z_p2 = z_p1 + d_link;
module lift_servo_ref() color("RoyalBlue") {
    translate([lsv_xc - sv_l / 2, lsv_bot_y, z_p1 - sv_w / 2]) cube([sv_l, sv_case_h, sv_w]);
    translate([lsv_xc - sv_tab_span / 2, lsv_tab_y, z_p1 - sv_w / 2]) cube([sv_tab_span, sv_tab_t, sv_w]);
    translate([r_p1, 0, z_p1]) ycyl(12, lsv_bot_y, lsv_spline_y);
    color("Silver") translate([r_p1, 0, z_p1]) ycyl(horn_d, link_y0 - horn_t, link_y0);
}
module horn_screw_pattern() {          // 4 radial slots (PCD 11..17) + centre access
    cylinder(d = 7, h = 50, center = true);
    for (a = [0, 90, 180, 270]) rotate([0, 0, a + 45]) hull() for (r = [5.5, 8.5]) translate([r, 0, 0]) cylinder(d = 2.4, h = 50, center = true);
}
module turntable() {
    hx = [for (s = [-1, 1]) lsv_xc + s * sv_hole_p / 2];   // -9.9, 39.6
    difference() {
        union() {
            translate([0, 0, tt_z0]) cylinder(d = tt_d, h = tt_t, $fn = 120);
            // mast wall
            translate([-16, mast_y0, tt_top - eps]) cube([62, mast_y1 - mast_y0, z_p1 + 16 - tt_top]);
            translate([r_p1 - 9, mast_y0, tt_top - eps]) cube([18, mast_y1 - mast_y0, z_p2 + 7 - tt_top]);
            // P2 boss
            translate([r_p1, 0, z_p2]) ycyl(14, mast_y0, link_y0);
        }
        horn_screw_pattern();
        // lift servo case passes through the wall
        translate([lsv_xc - sv_l / 2 - 0.4, mast_y0 - 1, tt_top - 1]) cube([sv_l + 0.8, 20, z_p1 + sv_w / 2 + 0.4 - tt_top + 1]);
        for (x = hx, dz = [-sv_hole_dx / 2, sv_hole_dx / 2]) translate([x, mast_y1 + eps, z_p1 + dz]) rotate([90, 0, 0]) insert_hole();
        // P2 pivot: through-bolt, nylock on the back face
        translate([r_p1, 0, z_p2]) ycyl(3.4, mast_y0 - 1, link_y0 + 1);
        translate([r_p1, 0, z_p2]) ycyl(6.4, mast_y0 - 1, mast_y0 + 2.5);
        // tube + lead hole down through the plate behind the mast
        translate([-25, -5, 0]) cylinder(d = 10, h = 100);
    }
}

// =========================================================================
// LINKS (print 1 each, PETG, 100 % infill, flat): A is driven (bolted to the
// lift horn at P1), B idles on the P2 boss. Both 220 mm pivot to pivot, in the
// plane Y = 8..13. Modelled at th = 0 (horizontal).
// =========================================================================
module link_body(hub_d) {
    hull() { translate([r_p1, 0, 0]) ycyl(hub_d, link_y0, link_y0 + link_t); translate([r_p1 + 20, link_y0, -link_hgt / 2]) cube([1, link_t, link_hgt]); }
    translate([r_p1 + 15, link_y0, -link_hgt / 2]) cube([L - 30, link_t, link_hgt]);
    hull() { translate([r_p1 + L, 0, 0]) ycyl(12, link_y0, link_y0 + link_t); translate([r_p1 + L - 20, link_y0, -link_hgt / 2]) cube([1, link_t, link_hgt]); }
}
module link_a() translate([0, 0, z_p1]) difference() {
    link_body(24);
    translate([r_p1, 0, 0]) rotate([90, 0, 0]) horn_screw_pattern();
    translate([r_p1 + L, 0, 0]) ycyl(3.4, 0, 20);
}
module link_b() translate([0, 0, z_p2]) difference() {
    link_body(14);
    for (x = [r_p1, r_p1 + L]) translate([x, 0, 0]) ycyl(3.4, 0, 20);
}

// =========================================================================
// HAND (print 1, PETG): carries both distal pivots (H1, H2) on its +Y face and
// the vertical slider bore on the cup axis (X = R at th = 0). Contact pad: an
// M3 screw head-up in an insert on the top face, 10 mm inboard of the bore.
// Modelled at th = 0.
// =========================================================================
hx_piv = r_p1 + L;                       // 245
h1_z0 = z_p1;                            // H1 at th = 0
hand_x0 = hx_piv - 8; hand_x1 = R + 12;
hand_zb = h1_z0 - 8; hand_zt = h1_z0 + d_link + 6;
module hand() difference() {
    translate([hand_x0, -8, hand_zb]) cube([hand_x1 - hand_x0, 8 + link_y0, hand_zt - hand_zb]);
    // slider bore with a flat (anti-rotation, keeps the contact screws aligned)
    translate([R, 0, hand_zb - 1]) linear_extrude(hand_zt - hand_zb + 2) d_profile(slider_bore);
    for (z = [h1_z0, h1_z0 + d_link]) { translate([hx_piv, 0, z]) ycyl(3.4, -10, 20); translate([hx_piv, 0, z]) ycyl(6.4, -10, -8 + 2.5); }
    translate([R - 10, 0, hand_zt - 6.5 + eps]) insert_hole();
}
module d_profile(d) intersection() { circle(d = d); translate([-d / 2 + 1.2, -d / 2]) square([d, d]); }

// =========================================================================
// SLIDER (print 1, PETG, upright): hollow D-rod (6.5 bore for the 6 mm OD
// tube) with a collar that rests on the hand top under gravity. Contact: an
// M3 x 10 down through an insert in the collar touches the hand's screw head
// when resting (circuit closed = cup free; open = cup touching).
// =========================================================================
slider_below = 16;
slider_len = slider_below + (hand_zt - hand_zb);
module slider() translate([R, 0, hand_zb - slider_below]) difference() {
    union() {
        linear_extrude(slider_len) d_profile(slider_d);
        translate([0, 0, slider_len]) cylinder(d = 26, h = 6);
    }
    translate([0, 0, -1]) cylinder(d = 6.5, h = slider_len + 10);
    translate([-10, 0, slider_len - 1]) insert_hole(8);
}
module cup_ref(lip_z) color("Orange") translate([R, 0, lip_z]) { cylinder(d1 = 27, d2 = cup_d, h = 15); translate([0, 0, 15]) cylinder(d = 10, h = cup_h - 15); }

// =========================================================================
// CAMERA TOWER (print 1, PLA): post at radius 345 on the scan station's ray,
// boom over the bed. Camera board face-down under the boom end (lens at Z 172),
// Pi Zero on the boom top (150 mm ribbon reaches). Station-local frame.
// PRINT: on its side (Y face down), no supports.
// =========================================================================
post_w = 24; boom_t = 10; boom_w = 34;
cam_board_t = 11.5;
boom_z0 = cam_lens_z + cam_board_t;      // board + lens stack above the lens tip
module tower() difference() {
    union() {
        translate([cam_r_tower - post_w / 2, -post_w / 2, 0]) cube([post_w, post_w, boom_z0 + boom_t]);
        translate([cam_r_tower - post_w / 2 - 14, -post_w / 2 - 14, 0]) cube([post_w + 28, post_w + 28, 5]);
        translate([R - 16, -boom_w / 2, boom_z0]) cube([cam_r_tower - R + 16, boom_w, boom_t]);
    }
    // camera: 21 x 12.5 hole pattern, M2 self-tap pilots; lens window
    for (dx = [-6.25, 6.25], dy = [-10.5, 10.5]) translate([R + dx, dy, boom_z0 - 1]) cylinder(d = 1.8, h = 8);
    translate([R, 0, boom_z0 - 1]) cylinder(d = 10, h = 2);
    // ribbon slot next to the camera
    translate([R + 13, -9, boom_z0 - 1]) cube([3, 18, boom_t + 2]);
    // Pi Zero 2 W on the boom top: holes 58 x 23, M2.5 self-tap pilots
    for (dx = [0, 58], dy = [-11.5, 11.5]) translate([R + 22 + dx, dy, boom_z0 + 2]) cylinder(d = 2.2, h = 10);
    for (x = [cam_r_tower - post_w / 2 - 7, cam_r_tower + post_w / 2 + 7], y = [-post_w / 2 - 7, post_w / 2 + 7]) translate([x, y, -1]) m3_clear(10);
}
// WS2812 ring holder: angled cradle on the post's inner face, aimed at the bed centre
ring_tilt = atan2(ring_z - bed_top, ring_r - R);   // ~33.7 deg below horizontal
module ring_holder() translate([ring_r, 0, ring_z]) rotate([0, -(90 - ring_tilt), 0]) difference() {
    union() { cylinder(d = 44, h = 4); translate([-6, -10, -12]) cube([12, 20, 12]); }
    translate([0, 0, 2]) cylinder(d = 38, h = 5);       // ring recess (37 OD)
    translate([0, 0, -1]) cylinder(d = 22, h = 10);     // ring centre open
}

// PRINT 4: board feet, so the nuts under the board clear the table
module foot() difference() { cylinder(d = 24, h = 14); translate([0, 0, 2]) cylinder(d = 14, h = 20); translate([0, 0, -1]) m3_clear(10); }

if (part == "bin") bin();
if (part == "hopper") hopper();
if (part == "bed") bed();
if (part == "cell_block") cell_block();
if (part == "yaw_base") yaw_base();
if (part == "roller_sleeve") roller_sleeve();
if (part == "turntable") turntable();
if (part == "link_a") link_a();
if (part == "link_b") link_b();
if (part == "hand") hand();
if (part == "slider") slider();
if (part == "tower") tower();
if (part == "ring_holder") ring_holder();
if (part == "foot") foot();
