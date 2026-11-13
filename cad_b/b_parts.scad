// =========================================================================
// Option B printed parts + reference solids for purchased parts.
//   openscad --backend=manifold -D 'part="bin"' -o bin.stl b_parts.scad
// Parts are modelled in their installed frame; export_b.py places them for
// printing (orientation per module's PRINT note).
// Fasteners: every pivot is an M3 x 16 SHCS + washer through a printed sleeve
// into a heat-set insert (no nylocks, nothing longer than the owned 6-20 kit).
// =========================================================================
include <b_params.scad>

part = "bin";

// ---------- helpers ----------
module ycyl(d, y0, y1) translate([0, y0, 0]) rotate([-90, 0, 0]) cylinder(d = d, h = y1 - y0);
module xcyl(d, x0, x1) translate([x0, 0, 0]) rotate([0, 90, 0]) cylinder(d = d, h = x1 - x0);
module insert_hole(depth = 6.5) cylinder(d = 4.1, h = depth);       // M3 x 5.7 heat-set, from Z = 0 up
module m3_clear(h) cylinder(d = 3.4, h = h);
module hex_pocket(depth) cylinder(d = 5.6 / cos(30), h = depth, $fn = 6);   // M3 nut, 5.5 AF + 0.1
module annulus2d(r0, r1) difference() { circle(r = r1, $fn = 360); circle(r = r0, $fn = 360); }
module wedge2d(a, d, rmax = 400)       // between lines at +/-a through the origin, each moved inward by d
    intersection() {
        rotate(a) translate([-rmax, -2 * rmax - d]) square([2 * rmax, 2 * rmax]);
        rotate(-a) translate([-rmax, d]) square([2 * rmax, 2 * rmax]);
    }
module ear(x, y, t = 4) translate([x, y, 0]) cylinder(d = 12, h = t);
module ear_hole(x, y) translate([x, y, -1]) m3_clear(10);

// =========================================================================
// BIN (print 7, PLA, floor down): fan-shaped pocket, station-local frame (yaw
// axis at the origin, station on +X). Each bin owns a 1.2 mm radial half-wall;
// the half-walls only start at r = divider_r0, so where the wedge is narrow
// (card inner corners) nothing can catch a slightly mis-aimed card.
// Two ears on the inner arc only (the outer edge may overhang a 2 x 2 ft board).
// =========================================================================
bin_ear_r = bin_r_in - wall - 6;
module bin() {
    a = pitch / 2;
    difference() {
        union() {
            linear_extrude(pocket_h) intersection() { annulus2d(bin_r_in - wall, bin_r_out + wall); wedge2d(a, 0); }
            for (s = [-1, 1]) ear(bin_ear_r, s * 22);
        }
        translate([0, 0, floor_t]) linear_extrude(pocket_h) intersection() {
            annulus2d(bin_r_in, bin_r_out);
            union() { wedge2d(a, half_wall); circle(r = divider_r0, $fn = 360); }
        }
        // the inner zone has no divider: trim the pocket there to this bin's own wedge only
        translate([bin_r_out - 1, -17, 12]) cube([wall + 2, 34, pocket_h]);     // thumb notch
        for (s = [-1, 1]) ear_hole(bin_ear_r, s * 22);
    }
}

// =========================================================================
// HOPPER (print 1, PLA, floor down): 65 x 90 pocket (1 mm room each side),
// 2 mm lead-in chamfer, finger notches in both short walls, ears inboard.
// =========================================================================
module hopper() {
    ow = hop_in_w + 2 * wall; ol = hop_in_l + 2 * wall;
    ex = R - ol / 2 - 6;
    difference() {
        union() {
            translate([R - ol / 2, -ow / 2, 0]) cube([ol, ow, pocket_h]);
            for (s = [-1, 1]) ear(ex, s * 20);
        }
        translate([R - hop_in_l / 2, -hop_in_w / 2, floor_t]) cube([hop_in_l, hop_in_w, pocket_h]);
        translate([R, 0, pocket_h - hop_chamfer]) linear_extrude(hop_chamfer + eps, scale = [(hop_in_l + 2 * hop_chamfer) / hop_in_l, (hop_in_w + 2 * hop_chamfer) / hop_in_w]) square([hop_in_l, hop_in_w], center = true);
        for (s = [-1, 1]) translate([R + s * (hop_in_l / 2 + wall / 2) - wall, -15, 10]) cube([2 * wall, 30, pocket_h]);
        for (s = [-1, 1]) ear_hole(ex, s * 20);
    }
}

// =========================================================================
// SCAN / WEIGH PLATFORM: owned 5 kg bar cell, radial, fixed end inboard.
// cell_block (PLA) holds the fixed end 8 mm up; bed (PLA) sits on the free
// end on a 5 mm boss. M4 x 10 x 4 (2 up through the block, 2 down through the
// bed with the heads recessed 4.3, leaving 4 mm of boss under them).
// =========================================================================
cell_x0 = R - cell_l / 2;
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
bed_z0 = bed_top - bed_t;
module bed() {
    boss_x0 = cell_holes_x[2] - 7; boss_x1 = cell_x0 + cell_l;
    difference() {
        union() {
            translate([R - bed_l / 2, -bed_w / 2, bed_z0]) cube([bed_l, bed_w, bed_t]);
            translate([boss_x0, -cell_s / 2, cell_z0 + cell_s]) cube([boss_x1 - boss_x0, cell_s, bed_boss + eps]);
        }
        for (x = [cell_holes_x[2], cell_holes_x[3]]) translate([x, 0, 0]) { cylinder(d = 4.5, h = 40); translate([0, 0, bed_top - 4.3]) cylinder(d = 7.6, h = 10); }
    }
}

// =========================================================================
// YAW BASE (print 1, PETG, plate down): yaw MG996R spline-up at the origin,
// case toward -Y; tabs on two end blocks (M3 x 10 + washer into inserts).
// Four 608ZZ rollers 0.5 mm under the turntable rim (sag stop); their axles
// sit in vertical slots so the gap can be set with a paper shim.
// =========================================================================
yb_t = 4;
sv_yc = -(sv_l / 2 - sv_shaft_off);
yaw_tab_z = yaw_sv_bot + sv_tab_z0;
module yaw_servo_ref() color("RoyalBlue") {
    translate([-sv_w / 2, sv_yc - sv_l / 2, yaw_sv_bot]) cube([sv_w, sv_l, sv_case_h]);
    translate([-sv_w / 2, sv_yc - sv_tab_span / 2, yaw_tab_z]) cube([sv_w, sv_tab_span, sv_tab_t]);
    translate([0, 0, yaw_sv_bot]) cylinder(d = 12, h = sv_h);
    color("Silver") translate([0, 0, tt_z0 - horn_t]) cylinder(d = horn_d, h = horn_t);
}
roller_cz = tt_z0 - roller_gap - 11;
module roller_post(az) rotate([0, 0, az]) difference() {
    union() for (r = [roller_r - 3.5 - 0.4 - 4, roller_r + 3.5 + 0.4]) translate([r, -8, 0]) cube([4, 16, roller_cz + 7]);
    hull() for (dz = [-1.5, 1.5]) translate([0, 0, roller_cz + dz]) xcyl(3.4, roller_r - 15, roller_r + 15);
}
module roller_ref(az) color("Silver") rotate([0, 0, az]) translate([0, 0, roller_cz]) difference() { xcyl(22, roller_r - 3.5, roller_r + 3.5); xcyl(8, roller_r - 5, roller_r + 5); }
module yaw_base() {
    hy = [for (s = [-1, 1]) sv_yc + s * sv_hole_p / 2];
    difference() {
        union() {
            translate([-60, -60, 0]) cube([120, 120, yb_t]);
            for (y = hy) translate([-12, y - 4, 0]) cube([24, 8, yaw_tab_z]);
            for (s = [-1, 1]) translate([s * (sv_w / 2 + 0.4) + (s < 0 ? -3 : 0), sv_yc - 15, 0]) cube([3, 30, 20]);
            for (az = [45, 135, 225, 315]) roller_post(az);
        }
        translate([-sv_w / 2 - 0.4, sv_yc - sv_l / 2 - 0.4, yaw_sv_bot]) cube([sv_w + 0.8, sv_l + 0.8, 50]);
        translate([0, 0, -1]) cylinder(d = 14, h = 10);
        translate([-5, sv_yc - sv_l / 2 - 10, yaw_sv_bot]) cube([10, 12, 8]);       // lead exit
        for (y = hy, x = [-sv_hole_dx / 2, sv_hole_dx / 2]) translate([x, y, yaw_tab_z - 6.5]) insert_hole();
        for (x = [-52, 52], y = [-52, 52]) translate([x, y, -1]) m3_clear(10);
    }
}
module roller_sleeve() difference() { cylinder(d = 7.9, h = 7.0); translate([0, 0, -1]) cylinder(d = 3.4, h = 10); }   // PRINT 4

// =========================================================================
// TURNTABLE + MAST (print 1, PETG, plate down; the P2 boss has a gusset under
// it, no supports). Arm-local frame. The plate screws to the yaw horn from
// above: 4 x M2.5 x 6 (standoff kit) through counterbored slots, centre hole
// for the horn screw (the area above it is clear). The lift MG996R lies along
// +X with its spline at P1 = (25, Y, 70); its tabs bolt through the mast wall
// (M3 x 12, nuts in hex pockets on the back). P2 boss carries link B.
// =========================================================================
lsv_spline_y = link_y0 - horn_gap;
lsv_bot_y = lsv_spline_y - sv_h;
lsv_tab_y = lsv_bot_y + sv_tab_z0;
lsv_xc = r_p1 + (sv_l / 2 - sv_shaft_off);      // case centre X (35.15): case runs outboard of P1
lsv_x0 = lsv_xc - sv_l / 2; lsv_x1 = lsv_xc + sv_l / 2;
mast_y0 = lsv_tab_y - 7; mast_y1 = lsv_tab_y;
mast_x0 = 4; mast_x1 = 66;
z_p2 = z_p1 + d_link;
mast_top = z_p2 + 7;
module lift_servo_ref() color("RoyalBlue") {
    translate([lsv_x0, lsv_bot_y, z_p1 - sv_w / 2]) cube([sv_l, sv_case_h, sv_w]);
    translate([lsv_xc - sv_tab_span / 2, lsv_tab_y, z_p1 - sv_w / 2]) cube([sv_tab_span, sv_tab_t, sv_w]);
    translate([r_p1, 0, z_p1]) ycyl(12, lsv_bot_y, lsv_spline_y);
    color("Silver") translate([r_p1, 0, z_p1]) ycyl(horn_d, link_y0 - horn_t, link_y0);
}
module horn_screws(z_face, cb_from_top) {   // M2.5 into the horn's holes: slots PCD 11..17 + centre access
    translate([0, 0, z_face - 30]) cylinder(d = 7, h = 60);
    for (a = [45, 135, 225, 315]) rotate([0, 0, a]) hull() for (r = [5.5, 8.5]) translate([r, 0, 0]) {
        translate([0, 0, z_face - 30]) cylinder(d = 2.8, h = 60);
        translate([0, 0, z_face + cb_from_top]) cylinder(d = 5.2, h = 30);
    }
}
module turntable() {
    hx = [for (s = [-1, 1]) lsv_xc + s * sv_hole_p / 2];   // 10.4, 59.9
    difference() {
        union() {
            translate([0, 0, tt_z0]) hull() { cylinder(d = tt_d, h = tt_t, $fn = 120); translate([0, -42, 0]) cube([70, 62, tt_t]); }
            translate([mast_x0, mast_y0, tt_top - eps]) cube([mast_x1 - mast_x0, mast_y1 - mast_y0, mast_top - tt_top]);
            for (x = [mast_x0, mast_x1 - 4]) hull() {                     // rear gussets
                translate([x, mast_y0 - eps, tt_top - eps]) cube([4, eps, mast_top - tt_top - 10]);
                translate([x, mast_y0 - 18, tt_top - eps]) cube([4, 18, 3]);
            }
            translate([r_p1, 0, z_p2]) ycyl(14, mast_y1 - eps, link_y0);   // P2 boss
            hull() {                                                       // gusset under the boss
                translate([r_p1 - 4, mast_y1 - eps, z_p2 - 1]) cube([8, link_y0 - 1.5 - mast_y1, 1]);
                translate([r_p1 - 4, mast_y1 - eps, 84]) cube([8, 1, 1]);
            }
        }
        horn_screws(tt_z0, 2);
        translate([lsv_x0 - 0.4, mast_y0 - 1, tt_top - 1]) cube([sv_l + 0.8, 20, z_p1 + sv_w / 2 + 0.4 - tt_top + 1]);
        for (x = hx, dz = [-sv_hole_dx / 2, sv_hole_dx / 2]) translate([x, 0, z_p1 + dz]) {
            ycyl(3.4, mast_y0 - 1, mast_y1 + 1);
            translate([0, mast_y0 - eps, 0]) rotate([-90, 0, 0]) hex_pocket(2.6);
        }
        translate([r_p1, link_y0 + eps, z_p2]) rotate([90, 0, 0]) insert_hole();   // P2 pivot insert
        for (x = [10, 20]) translate([x, 0, mast_top - 5]) ycyl(4, mast_y0 - 1, mast_y1 + 1);   // zip-tie slots: tube + leads
    }
}

// =========================================================================
// LINKS (print 1 each, PETG, 100 % infill, lying on the Y face): 10 x 12
// section. A is bolted to the lift horn at P1 (4 x M2.5 x 6 in counterbores);
// every other pivot is a printed sleeve (sleeve()) on an M3 x 16 into an insert.
// Modelled at th = 0.
// =========================================================================
pivot_hole = 6.3;
module link_body(hub0) {
    hull() { translate([r_p1, 0, 0]) ycyl(hub0, link_y0, link_y0 + link_t); translate([r_p1 + 22, link_y0, -link_hgt / 2]) cube([1, link_t, link_hgt]); }
    translate([r_p1 + 15, link_y0, -link_hgt / 2]) cube([L - 30, link_t, link_hgt]);
    hull() { translate([r_p1 + L, 0, 0]) ycyl(15, link_y0, link_y0 + link_t); translate([r_p1 + L - 20, link_y0, -link_hgt / 2]) cube([1, link_t, link_hgt]); }
}
module link_a() translate([0, 0, z_p1]) difference() {
    link_body(26);
    translate([r_p1, 0, 0]) rotate([-90, 0, 0]) horn_screws(link_y0, 3);
    translate([r_p1 + L, 0, 0]) ycyl(pivot_hole, 0, 30);
}
module link_b() translate([0, 0, z_p2]) difference() {
    link_body(16);
    for (x = [r_p1, r_p1 + L]) translate([x, 0, 0]) ycyl(pivot_hole, 0, 30);
}
module sleeve() difference() { cylinder(d = 6.0, h = link_t + 0.3); translate([0, 0, -1]) cylinder(d = 3.4, h = 20); }   // PRINT 3

// =========================================================================
// HAND (print 1, PETG): distal pivot inserts H1, H2 in its +Y face; vertical
// slider bore on the cup axis. Top face: two M3 x 6 head-up contact screws
// (inserts) + one printed bump of the same height = 3-point rest for the 608
// ring on the slider. Ring resting = circuit closed through the bearing.
// Modelled at th = 0.
// =========================================================================
hx_piv = r_p1 + L;
hand_x0 = hx_piv - 8; hand_x1 = R + 14;
hand_y0 = -10;
hand_zb = z_p1 - 8; hand_zt = z_p2 + 10;
contact_pts = [for (a = [150, 210]) [R + contact_r * cos(a), contact_r * sin(a)]];
module hand() difference() {
    union() {
        translate([hand_x0, hand_y0, hand_zb]) cube([hand_x1 - hand_x0, link_y0 - hand_y0, hand_zt - hand_zb]);
        translate([R + contact_r, 0, hand_zt - eps]) cylinder(d = 4, h = 3);          // third rest point
    }
    translate([R, 0, hand_zb - 1]) cylinder(d = slider_bore, h = hand_zt - hand_zb + 2);
    for (z = [z_p1, z_p2]) translate([hx_piv, link_y0 + eps, z]) rotate([90, 0, 0]) insert_hole();
    for (p = contact_pts) translate([p[0], p[1], hand_zt - 6.5 + eps]) insert_hole();
    translate([hand_x0 + 3, hand_y0 - 1, hand_zb + 6]) cube([4, 30, 3]);           // zip-tie slot: tube clamp
}

// =========================================================================
// SLIDER (print 1, PETG, upright): solid Ø12 rod. Top: Ø7.95 stub for a 608ZZ
// (12 g of weight + the conductive contact ring), clamped by cap() with an
// M3 x 10 into an insert in the stub. Bottom: a pocket for an airline TEE:
// run along Y (one leg to the tube, the other to the pin-hole bleed), stem
// down into the cup's rubber neck (clamped with the cup's own ring).
// Modelled resting, at th = 0.
// =========================================================================
tee_d = 6.2;                               // AQUANEAT 3/16" tee body: measure, adjust
slider_z0 = hand_zb - slider_below;        // slider bottom when resting
ring_z0   = hand_zt + 3;                   // 608 underside resting on the screw heads
module slider() difference() {
    union() {
        translate([R, 0, slider_z0]) cylinder(d = slider_d, h = ring_z0 - slider_z0);
        translate([R, 0, ring_z0 - eps]) cylinder(d = 7.95, h = 7);
    }
    translate([R, 0, ring_z0 + 7 - 6.5 + eps]) insert_hole();
    translate([R, 0, slider_z0 + 5]) ycyl(tee_d, -10, 10);
    translate([R - tee_d / 2, -10, slider_z0 - 1]) cube([tee_d, 20, 6]);
}
module cap() translate([R, 0, ring_z0 + 7]) difference() { cylinder(d = 12, h = 2.5); translate([0, 0, -1]) m3_clear(5); }   // PRINT 1
module ring608_ref() color("Silver") translate([R, 0, ring_z0]) difference() { cylinder(d = 22, h = 7); translate([0, 0, -1]) cylinder(d = 8, h = 9); }
module cup_ref(lip_z) color("Orange") translate([R, 0, lip_z]) { cylinder(d1 = 27, d2 = cup_d, h = 15); translate([0, 0, 15]) cylinder(d = 10, h = cup_h - 15); }
module tee_ref() color("White") translate([R, 0, slider_z0 + 5]) { ycyl(5, -14, 14); translate([0, 0, -12]) cylinder(d = 5, h = 12); }

// =========================================================================
// CAMERA TOWER: post (print 1, PLA, lying flat, 250 long) + boom (print 1)
// that clamps on the post at any height (M3 x 10 into an insert presses a
// printed pad on the post). Camera face-down under the boom end; Pi Zero on
// top. Station-local frame.
// =========================================================================
post_w = 24; post_h = 250; sleeve_t = 4; sleeve_h = 30;
boom_t = 10; boom_w = 34;
cam_board_t = 11.5;
boom_z0 = cam_lens_z + cam_board_t;
module tower_post() difference() {
    union() {
        translate([cam_r_tower - post_w / 2, -post_w / 2, 0]) cube([post_w, post_w, post_h]);
        translate([cam_r_tower - post_w / 2 - 14, -post_w / 2 - 14, 0]) cube([post_w + 28, post_w + 28, 5]);
    }
    for (x = [cam_r_tower - post_w / 2 - 7, cam_r_tower + post_w / 2 + 7], y = [-post_w / 2 - 7, post_w / 2 + 7]) translate([x, y, -1]) m3_clear(10);
}
module post_clamp(z0, h) difference() {          // sleeve round the post with a clamp screw on the outer face
    translate([cam_r_tower - post_w / 2 - sleeve_t, -post_w / 2 - sleeve_t, z0]) cube([post_w + 2 * sleeve_t, post_w + 2 * sleeve_t, h]);
    translate([cam_r_tower - post_w / 2 - 0.3, -post_w / 2 - 0.3, z0 - 1]) cube([post_w + 0.6, post_w + 0.6, h + 2]);
    translate([cam_r_tower + post_w / 2 - eps, 0, z0 + h / 2]) rotate([0, 90, 0]) translate([0, 0, -2]) insert_hole(sleeve_t + 3);
}
module boom() difference() {
    union() {
        post_clamp(boom_z0 + boom_t - sleeve_h, sleeve_h);
        translate([R - 16, -boom_w / 2, boom_z0]) cube([cam_r_tower - post_w / 2 - R + 16 + eps, boom_w, boom_t]);
    }
    for (dx = [-6.25, 6.25], dy = [-10.5, 10.5]) translate([R + dx, dy, boom_z0 - 1]) cylinder(d = 1.8, h = 8);   // camera M2 pilots (21 x 12.5)
    translate([R, 0, boom_z0 - 1]) cylinder(d = 10, h = 2);
    translate([R + 13, -9, boom_z0 - 1]) cube([3, 18, boom_t + 2]);                                         // ribbon slot
    for (dx = [0, 58], dy = [-11.5, 11.5]) translate([R + 22 + dx, dy, boom_z0 + 2]) cylinder(d = 2.2, h = 10);   // Pi Zero M2.5 pilots
}
// WS2812 ring: clamp sleeve + arm to the post's +Y side, cradle aimed at the bed centre
ring_c = [cam_r_tower, post_w / 2 + sleeve_t + ring_side, ring_z];
ring_aim = [R, 0, bed_top] - ring_c;
module ring_holder() {
    post_clamp(ring_z - 15, 30);
    hull() {
        translate([cam_r_tower - 6, post_w / 2 + sleeve_t - eps, ring_z - 15]) cube([12, 1, 30]);
        translate(ring_c) cylinder(d = 10, h = 2, center = true);
    }
    translate(ring_c) rotate([0, 0, atan2(ring_aim[1], ring_aim[0])]) rotate([0, 90 + atan2(-ring_aim[2], norm([ring_aim[0], ring_aim[1]])), 0]) difference() {
        cylinder(d = 44, h = 4);
        translate([0, 0, 2]) cylinder(d = 38, h = 5);
        translate([0, 0, -1]) cylinder(d = 22, h = 10);
    }
}

// =========================================================================
// CABLE POST (print 1, PLA): fixed post behind the yaw axis; the tube and the
// arm's leads run from the mast-top zip ties to its hook in a free loop that
// only twists (the arm never points into -Y). World frame.
// =========================================================================
module cable_post() translate([cable_post_xy[0], cable_post_xy[1], 0]) difference() {
    union() {
        translate([-10, -10, 0]) cube([20, 20, 150]);
        translate([-24, -24, 0]) cube([48, 48, 5]);
        translate([-10, -10, 140]) cube([20, 34, 10]);                  // hook arm toward the axis
    }
    translate([-11, 14, 143]) cube([22, 4, 3]);                         // zip-tie slot
    for (x = [-18, 18], y = [-18, 18]) translate([x, y, -1]) m3_clear(10);
}

module foot() difference() { cylinder(d = 24, h = 14); translate([0, 0, 2]) cylinder(d = 14, h = 20); translate([0, 0, -1]) m3_clear(10); }   // PRINT 4

if (part == "bin") bin();
if (part == "hopper") hopper();
if (part == "bed") bed();
if (part == "cell_block") cell_block();
if (part == "yaw_base") yaw_base();
if (part == "roller_sleeve") roller_sleeve();
if (part == "turntable") turntable();
if (part == "link_a") link_a();
if (part == "link_b") link_b();
if (part == "sleeve") sleeve();
if (part == "hand") hand();
if (part == "slider") slider();
if (part == "cap") cap();
if (part == "tower_post") tower_post();
if (part == "boom") boom();
if (part == "ring_holder") ring_holder();
if (part == "cable_post") cable_post();
if (part == "foot") foot();
