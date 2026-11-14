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
bin_ear_r = bin_r_in - wall - 4.5;          // ears overlap the inner wall by 1.5
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
    ex = R - ol / 2 - 4;                        // ears overlap the wall by 2 (were only touching)
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
// PEDESTAL (print 1, PETG, flange down; round 4 replaces the servo yaw base +
// rollers). Tube r 80 with a 5 mm deck at Z 34.5..39.5. The lazy susan's
// bottom plate sits in a 1 mm square pocket on the deck (M3 x 8 self-tapped
// into Ø2.5 pilots at its corner holes). The 28BYJ-48 hangs under the deck,
// shaft up on the yaw axis, ears on M3 x 8 down through Ø5 float holes (washer
// + nut under each ear): leave them loose, turn the arm by hand a full sweep so
// the stepper centres itself on the bearing axis, then tighten. Lead exits
// through a slot toward -Y. Home-switch bracket at az 180 (+home_az).
// =========================================================================
ped_flange = 150;                        // board screws at (+/-75, +/-75), r 106
ears = [for (s = [-1, 1]) [st_xy[0] + s * st_ear_span / 2, st_xy[1]]];
module stepper_ref() color("RoyalBlue") {
    translate([st_xy[0], st_xy[1], deck_z0 - st_h]) cylinder(d = st_d, h = st_h);
    translate([st_xy[0] - 8.5, st_xy[1] - st_d / 2 - 3, deck_z0 - 16]) cube([17, 6, 16]);   // lead housing
    hull() for (e = ears) translate([e[0], e[1], deck_z0 - st_ear_t]) cylinder(d = st_ear_w, h = st_ear_t);
    translate([0, 0, deck_z0]) cylinder(d = st_boss_d, h = st_boss_h);
    color("Silver") translate([0, 0, deck_z0]) cylinder(d = st_shaft_d, h = st_shaft_l);
}
module lazy_susan_ref() color("Silver") translate([0, 0, ls_z0]) difference() {
    translate([-ls_sq / 2, -ls_sq / 2, 0]) cube([ls_sq, ls_sq, ls_t]);
    translate([0, 0, -1]) cylinder(d = ls_hole, h = ls_t + 2);
}
module ls_pilots(z0, h) for (x = [-1, 1], y = [-1, 1]) translate([x * ls_pitch / 2, y * ls_pitch / 2, z0]) cylinder(d = 2.5, h = h);
ms_xc = -(ms_r0 + 10.2 / 2);             // switch body centre (radial), world frame at home_az = 0
module switch_ref() color("Black") rotate([0, 0, home_az]) translate([ms_xc - ms_h / 2, -ms_l / 2, ms_z0]) cube([ms_h, ms_l, ms_w]);
module switch_bracket() rotate([0, 0, home_az]) difference() {
    translate([-110, -12, 0]) cube([110 - ped_r + ped_wall, 24, ms_z0]);
    translate([-107, -9, -1]) cube([107 - ped_r - 1, 18, ms_z0 - 5 + 1]);             // hollow: nut access from below
    for (y = [-ms_hole_p / 2, ms_hole_p / 2]) hull() for (dx = [-3, 3]) translate([ms_xc + dx, y, ms_z0 - 10]) cylinder(d = 2.4, h = 20);   // M2 slots: set the lever to the tab
}
module pedestal() difference() {
    union() {
        for (a = [45, 135, 225, 315]) rotate([0, 0, a]) hull() { translate([ped_r - 10, -9, 0]) cube([1, 18, 4]); translate([ped_flange / sqrt(2) - 0.1, 0, 0]) cylinder(d = 18, h = 4); }   // 4 board tabs
        cylinder(r = ped_r, h = deck_top, $fn = 120);
        switch_bracket();
    }
    translate([0, 0, -1]) cylinder(r = ped_r - ped_wall, h = deck_z0 + 1, $fn = 120);  // hollow tube
    translate([-ls_sq / 2 - 0.3, -ls_sq / 2 - 0.3, deck_top - ls_pocket]) cube([ls_sq + 0.6, ls_sq + 0.6, 5]);
    translate([0, 0, deck_z0 - 1]) cylinder(d = 16, h = 10);                          // boss + hub clearance
    for (e = ears) translate([e[0], e[1], deck_z0 - 1]) cylinder(d = 5, h = 10);      // float holes
    ls_pilots(deck_z0 - 1, 10);                                                       // through: M3 x 6 may poke out below
    translate([-8, -ped_r - 1, 4]) cube([16, 10, 14]);                                // stepper lead exit (-Y)
    for (a = [45, 135, 225, 315]) rotate([0, 0, a]) translate([ped_flange / sqrt(2) - 0.1, 0, -1]) m3_clear(10);   // to the board
}

// =========================================================================
// TURNTABLE + MAST (print 1, PETG, plate down; the P2 boss has a gusset under
// it, no supports). Arm-local frame. Round 4: the lazy susan's top plate is
// screwed to the plate's underside (M3 x 8 self-tapped up into Ø2.5 pilots);
// the separate hub (below) screws into three more pilots. Ø8 access holes at
// local 90/180/270 deg, r 57: rotate the arm 45 deg off the deck's square and
// drive the bearing's bottom-plate screws through them. The tab at local 180
// deg trips the home switch with its end. The lift MG996R lies along
// +X with its spline at P1 = (25, Y, 70); its tabs bolt through the mast wall
// (M3 x 12, washer + nut on the flat back face). P2 boss carries link B.
// =========================================================================
lsv_spline_y = link_y0 - horn_gap;
lsv_bot_y = lsv_spline_y - sv_h;
lsv_tab_y = lsv_bot_y + sv_tab_z0;
lsv_xc = r_p1 + (sv_l / 2 - sv_shaft_off);      // case centre X (35.15): case runs outboard of P1
lsv_x0 = lsv_xc - sv_l / 2; lsv_x1 = lsv_xc + sv_l / 2;
mast_y0 = lsv_tab_y - 7; mast_y1 = lsv_tab_y;
mast_x0 = 0; mast_x1 = 70;
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
    // arc slots (+/-8 deg absorbs the 14.4 deg spline steps); through-slot and counterbore hulled separately
    for (a = [45, 135, 225, 315]) {
        hull() for (da = [-8, 8], r = [5.5, 8.5]) rotate([0, 0, a + da]) translate([r, 0, z_face - 30]) cylinder(d = 2.8, h = 60);
        hull() for (da = [-8, 8], r = [5.5, 8.5]) rotate([0, 0, a + da]) translate([r, 0, z_face + cb_from_top]) cylinder(d = 5.2, h = 30);
    }
}
module turntable() {
    hx = [for (s = [-1, 1]) lsv_xc + s * sv_hole_p / 2];   // 10.4, 59.9
    difference() {
        union() {
            translate([0, 0, tt_z0]) hull() { cylinder(d = tt_d, h = tt_t, $fn = 120); translate([0, -42, 0]) cube([70, 62, tt_t]);
                                              translate([-54, -54, 0]) cube([108, 108, tt_t]); }
            translate([-flag_r1, -flag_w / 2, tt_z0]) cube([flag_r1, flag_w, tt_t]);   // home tab
            translate([mast_x0, mast_y0, tt_top - eps]) cube([mast_x1 - mast_x0, mast_y1 - mast_y0, mast_top - tt_top]);
            for (x = [mast_x0, mast_x1 - 4]) hull() {                     // rear gussets
                translate([x, mast_y0 - eps, tt_top - eps]) cube([4, eps, mast_top - tt_top - 10]);
                translate([x, mast_y0 - 18, tt_top - eps]) cube([4, 18, 3]);
            }
            translate([r_p1, 0, z_p2]) ycyl(14, mast_y1 - eps, link_y0);   // P2 boss
            hull() {                                                       // gusset under the boss (full boss width)
                translate([r_p1 - 7, mast_y1 - eps, z_p2 - 1]) cube([14, link_y0 - 1.5 - mast_y1, 1]);
                translate([r_p1 - 7, mast_y1 - eps, 84]) cube([14, 1, 1]);
            }
        }
        ls_pilots(tt_z0 - 1, tt_t + 2);                                          // bearing top plate (through, M3 x 6)
        for (a = [0, 120, 240]) rotate([0, 0, a]) translate([12, 0, tt_z0 - 1]) cylinder(d = 2.5, h = tt_t + 2);   // hub flange (through, M3 x 8)
        for (a = [90, 180, 270]) rotate([0, 0, a]) translate([ls_pitch / sqrt(2), 0, tt_z0 - 1]) cylinder(d = 8, h = 20);   // bottom-plate screw access
        translate([lsv_x0 - 0.4, mast_y0 - 1, tt_top - 1]) cube([sv_l + 0.8, 20, z_p1 + sv_w / 2 + 0.4 - tt_top + 1]);
        for (x = hx, dz = [-sv_hole_dx / 2, sv_hole_dx / 2]) translate([x, 0, z_p1 + dz]) {
            ycyl(3.4, mast_y0 - 1, mast_y1 + 1);
        }
        translate([r_p1, link_y0 + eps, z_p2]) rotate([90, 0, 0]) insert_hole();   // P2 pivot insert
        for (x = [50, 60]) translate([x, 0, mast_top - 5]) ycyl(4, mast_y0 - 1, mast_y1 + 1);   // zip-tie slots: tube + leads
    }
}

// HUB (print 1, PETG, flange down, 100 % infill): presses onto the stepper's
// double-D shaft and screws up into the turntable (3 x M3 x 8, heads under the
// flange). Round Ø5.2 over the shaft's round root, then double-D 2.95 across
// the flats (press fit; if it is loose, a drop of CA). Turntable frame.
module hub() difference() {
    union() {
        translate([0, 0, hub_z0]) cylinder(d = hub_d, h = tt_z0 - hub_z0);
        translate([0, 0, tt_z0 - hub_fl_t]) cylinder(d = hub_fl_d, h = hub_fl_t);
    }
    translate([0, 0, hub_z0 - 1]) cylinder(d = st_shaft_d + 0.2, h = deck_z0 + st_shaft_l - st_flat_l - hub_z0 + 1);
    intersection() {
        translate([0, 0, deck_z0 + st_shaft_l - st_flat_l - eps]) cylinder(d = st_shaft_d + 0.05, h = st_flat_l + 1);
        translate([-(st_flat - 0.05) / 2, -5, 0]) cube([st_flat - 0.05, 10, 100]);
    }
    for (a = [0, 120, 240]) rotate([0, 0, a]) translate([12, 0, tt_z0 - hub_fl_t - 1]) m3_clear(10);
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
hand_zb = z_p1 - 8; hand_zt = z_p2 + 14;
flange_t = 8;                                     // top flange carries the 3 rest points
contact_pts = [for (a = [270, 150]) [R + contact_r * cos(a), contact_r * sin(a)]];
bump_pt = [R + contact_r * cos(30), contact_r * sin(30)];
// D-profile shared by the slider and its bore: anti-rotation flat on +X
flat_x = 3.5;
module d2d(d, fx) intersection() { circle(d = d); translate([-d, -d]) square([d + fx, 2 * d]); }
module hand() difference() {
    union() {
        translate([hand_x0, hand_y0, hand_zb]) cube([hand_x1 - hand_x0, link_y0 - hand_y0, hand_zt - hand_zb]);
        translate([0, 0, hand_zt - flange_t]) linear_extrude(flange_t) intersection() {   // flange stays out of the link plane (Y < 9)
            translate([R, 0]) circle(d = 2 * contact_r + 9);
            translate([R - 50, -50]) square([100, 50 + link_y0]);
        }
    }
    translate([R, 0, hand_zb - 1]) linear_extrude(hand_zt - hand_zb + 2) d2d(slider_bore, flat_x + 0.1);
    for (z = [z_p1, z_p2]) translate([hx_piv, link_y0 + eps, z]) rotate([90, 0, 0]) insert_hole();
    for (p = concat(contact_pts, [bump_pt])) translate([p[0], p[1], hand_zt - 6.5 + eps]) insert_hole();   // 2 wired contacts + 1 plain rest screw
    translate([hand_x0 + 3, hand_y0 - 1, z_p1 + 18]) cube([4, 30, 3]);             // zip-tie slot: tube clamp, between the pivots
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
ring_z0   = hand_zt + 1.65;                // 608 underside resting on three M3 button heads (two wired)
module slider() difference() {
    union() {
        translate([R, 0, slider_z0]) linear_extrude(ring_z0 - slider_z0) d2d(slider_d, flat_x);
        translate([R, 0, ring_z0 - eps]) cylinder(d = 7.95, h = 7);
    }
    translate([R, 0, ring_z0 + 0.5]) cylinder(d = 2.5, h = 10);                    // M3 x 8 self-taps (no heat-set in the thin stub)
    translate([R, 0, slider_z0 + 5]) ycyl(tee_d, -10, 10);
    translate([R - (tee_d - 0.8) / 2, -10, slider_z0 - 1]) cube([tee_d - 0.8, 20, 6]);   // 0.8 narrower: the tee snaps in
}
module cap() translate([R, 0, ring_z0 + 7]) difference() { cylinder(d = 12, h = 2.5); translate([0, 0, -1]) m3_clear(5); }   // PRINT 1, M3 x 8
module ring608_ref() color("Silver") translate([R, 0, ring_z0]) difference() { cylinder(d = 22, h = 7); translate([0, 0, -1]) cylinder(d = 8, h = 9); }
module cup_ref(lip_z) color("Orange") translate([R, 0, lip_z]) { cylinder(d1 = 27, d2 = cup_d, h = 15); translate([0, 0, 15]) cylinder(d = 10, h = cup_h - 15); }
module tee_ref() color("White") translate([R, 0, slider_z0 + 5]) { ycyl(5, -14, 14); translate([0, 0, -12]) cylinder(d = 5, h = 12); }

// =========================================================================
// CAMERA TOWER (station-local frame). Post at tower_xy (off the station ray,
// so it stays on a 2 ft board and clear of bin 1): print 1, PLA, UPRIGHT on
// its base. Boom (print 1, upside down) and ring holder (print 1) each clamp
// on the post at any height: M3 x 10 into an insert in a 10 mm boss presses
// on the post. Camera face-down under the boom end, sensor long axis radial
// (along the card); lens_frame holds the +5 D close-up lens under it; the Pi
// Zero sits on the boom top.
// =========================================================================
post_w = 24; post_h = 250; sleeve_t = 4; sleeve_h = 30;
boom_t = 10; boom_w = 34;
cam_board_t = 11.5;                       // board + lens, Arducam B0308
boom_z0 = cam_lens_z + cam_board_t;
tx = tower_xy[0]; ty = tower_xy[1];
boom_ang = atan2(ty, tx - R);             // boom direction, camera -> post
module tower_post() difference() {
    union() {
        translate([tx - post_w / 2, ty - post_w / 2, 0]) cube([post_w, post_w, post_h]);
        translate([tx - 22, ty - 22, 0]) cube([44, 44, 5]);
    }
    for (dx = [-16, 16], dy = [-16, 16]) translate([tx + dx, ty + dy, -1]) m3_clear(10);
}
module post_clamp(z0, h) difference() {
    union() {
        translate([tx - post_w / 2 - sleeve_t, ty - post_w / 2 - sleeve_t, z0]) cube([post_w + 2 * sleeve_t, post_w + 2 * sleeve_t, h]);
        translate([tx + post_w / 2 + sleeve_t - eps, ty - 6, z0 + h / 2 - 6]) cube([6, 12, 12]);   // clamp boss (+X face)
    }
    translate([tx - post_w / 2 - 0.3, ty - post_w / 2 - 0.3, z0 - 1]) cube([post_w + 0.6, post_w + 0.6, h + 2]);
    translate([tx + post_w / 2 + sleeve_t + 6 + eps, ty, z0 + h / 2]) rotate([0, -90, 0]) { insert_hole(6.5); m3_clear(20); }
}
module boom() difference() {
    union() {
        post_clamp(boom_z0 + boom_t - sleeve_h, sleeve_h);
        hull() {
            translate([R - 17, -17, boom_z0]) cube([34, 34, boom_t]);
            translate([tx, ty, boom_z0]) rotate([0, 0, boom_ang]) translate([-post_w / 2 - sleeve_t - 1, -boom_w / 2, 0]) cube([1, boom_w, boom_t]);
        }
    }
    translate([tx - post_w / 2 - 0.3, ty - post_w / 2 - 0.3, 0]) cube([post_w + 0.6, post_w + 0.6, 400]);   // keep the post bore clear
    for (dx = [-10.5, 10.5], dy = [-6.25, 6.25]) translate([R + dx, dy, boom_z0 - 1]) cylinder(d = 1.8, h = 8);   // camera M2 pilots, 21 along X
    translate([R, 0, boom_z0 - 1]) cylinder(d = 10, h = 2);
    translate([R - 9, 13, boom_z0 - 1]) cube([18, 3, boom_t + 2]);                                          // ribbon slot (+Y edge)
    for (dx = [-29, 29], dy = [-11.5, 11.5]) translate([(R + tx) / 2, ty / 2, boom_z0 + 2]) rotate([0, 0, boom_ang]) translate([dx, dy, 0]) cylinder(d = 2.2, h = 10);   // Pi Zero 58 x 23
    for (dx = [-14, 14]) translate([R + dx, -11, boom_z0 - 1]) insert_hole();                                // lens frame screws
}
// close-up lens frame: box round the camera board, pocket for the popped-out glasses lens at the bottom
gl_w = 52; gl_h = 32; gl_t = 3;           // MEASURE the lens, adjust
module lens_frame() difference() {
    translate([R - 30, -20, cam_lens_z - 4]) cube([60, 40, boom_z0 - cam_lens_z + 4]);
    translate([R - 15, -15, cam_lens_z - 1]) cube([30, 31, 50]);                                           // camera board + ribbon
    translate([R - gl_w / 2, -gl_h / 2, cam_lens_z - 4 + 1]) cube([gl_w, gl_h, gl_t]);                     // lens pocket (slides in from -X)
    translate([R - 31, -gl_h / 2, cam_lens_z - 4 + 1]) cube([10, gl_h, gl_t]);
    translate([R, 0, cam_lens_z - 10]) cylinder(d = 16, h = 10);                                          // window
    for (dx = [-14, 14]) translate([R + dx, -11, boom_z0 - 10]) m3_clear(20);
}
// WS2812 ring: clamp sleeve + arm toward the station ray, cradle aimed at the bed centre
ring_c = [tx, ty - post_w / 2 - sleeve_t - ring_side, ring_z];
ring_aim = [R, 0, bed_top] - ring_c;
module ring_holder() {
    post_clamp(ring_z - 15, 30);
    hull() {
        translate([tx - 6, ty - post_w / 2 - sleeve_t - 1, ring_z - 15]) cube([12, 1, 30]);
        translate(ring_c) cylinder(d = 10, h = 2, center = true);
    }
    translate(ring_c) rotate([0, 0, atan2(ring_aim[1], ring_aim[0])]) rotate([0, 90 + atan2(-ring_aim[2], norm([ring_aim[0], ring_aim[1]])), 0]) difference() {
        cylinder(d = 44, h = 4);
        translate([0, 0, 2]) cylinder(d = 38, h = 5);       // ring recess: glue the ring in
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
if (part == "pedestal") pedestal();
if (part == "turntable") turntable();
if (part == "hub") hub();
if (part == "link_a") link_a();
if (part == "link_b") link_b();
if (part == "sleeve") sleeve();
if (part == "hand") hand();
if (part == "slider") slider();
if (part == "cap") cap();
if (part == "tower_post") tower_post();
if (part == "boom") boom();
if (part == "lens_frame") lens_frame();
if (part == "ring_holder") ring_holder();
if (part == "cable_post") cable_post();
if (part == "foot") foot();
