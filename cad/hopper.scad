// =============================================
// Riftbound Card Sorter — Input Hopper (motor-raised floor, top pick)
// =============================================
// Replaces the bottom-feed hopper. A 28BYJ-48 stepper turns a T8 lead screw
// that lifts a carriage + floor plate, so the TOP card of the stack always
// sits at a fixed pick height `pick_z`. A suction cup comes straight down onto
// the card centre and lifts it straight up (owner decision 2026-11-11: no
// friction roller, the cards are valuable).
//
// Material: PLA or PETG, 0.2 mm layers, 3-4 walls, 25-40 % infill.
//
// LOCAL FRAME (everything in this file):
//   origin = cavity centre in X/Y, Z = 0 = underside of the hopper base
//   X = card LENGTH (88 mm), Y = card WIDTH (63 mm), Z up.
//   Identical axes to machine coords: hopper_elevator.scad only translates
//   by [frame_hopper_x(), 0, frame_base_top()] (no rotation).
//
// LAYOUT (top view)
//      +Y  ┌──────────────┐     +Y side: drive tower (rods, screw, motor on top)
//          │ tower        │     -Y side: finger slot (machine front) + feeler
//          ├──┐slot┌──────┤              flag / top switch at X -30
//          │   cavity     │     +X end: faces the belt (outer wall X = +48.5,
//          │   91 x 66    │             i.e. machine X = -166.5 <= -166)
//          └─flag─finger──┘
//             ▼ cheeks + switch hang out to Y -65.6
//
// PARTS (`part` selector at the bottom, exported in PRINT orientation):
//   body     hopper shell + drive tower + flag cheeks   upright, no supports
//   cap      tower cap / motor plate                    upside down, no supports
//   carriage carriage (2× LM8UU, T8 nut, plate shelf)   upright, no supports
//   plate    floor plate                                card face DOWN, no supports
//   flag     top-of-stack feeler flag                   flat on its side, no supports
//
// HEIGHT CHAIN (all derived below, numbers for the default pick_z = 86.9):
//   plate top travel    zp_min 15.0 .. zp_max 86.6  -> 71.6 mm stack
//                       = ~217 raw cards @ 0.33 mm (205 @ 0.35 mm)
//   carriage            = plate - 11 .. +16 (shelf 7 + plate 4 below the top)
//   T8 nut (inverted)   flange on the floor of a pocket 15 deep in the carriage
//                       top, body pointing UP, nut top flush with the carriage
//                       top: 102.6 at the top of travel
//   lead screw T8 x 100 12.5 .. 112.5
//   coupler 5->8 D19L25 104.1 .. 129.1
//   cap (motor plate)   126.1 .. 131.1, 28BYJ-48 body on top -> 150.1
//   guide rods 8 x 150  0.6 .. 150.6 (stick 19.5 mm out of the cap)
//   cavity walls        to pick_z + 3.5 = 90.4; from pick_z - 1 = 85.9 up the
//                       cavity steps out (lift relief: +X 1.0, other walls 0.5)
//
// TOP-OF-STACK SENSING (why a flag, not the bare switch lever):
//   A microswitch lever resting on the card would be dragged up with the card
//   when the cup lifts it, and an SS-type switch only has ~0.8 mm overtravel.
//   So a light printed flag (≈1.2 g) rests on the top card's -Y long-edge margin
//   (5 mm in from the cavity wall) with a rounded, edge-chamfered Ø5 tip. Its
//   pivot is outside the wall and BELOW the tip, so when the card is lifted the
//   tip rises AND swings outward and slides off the card edge after ≤5.7 mm of
//   lift; then it falls back onto the next card. The arm is cranked (elbow
//   above the wall) so the tip is always the lowest point over the cavity.
//   A conjugate cam on the flag hub drives the switch roller: rising stack ->
//   ramp -> switch closes exactly at pick_z -> peak 0.4 mm into overtravel ->
//   slow descent (switch spring returns the flag; never over-travels).
//   Force on the card: flag weight ≈ 0.006 N; while the roller is on the ramp
//   (the elevator has just stopped) ≈ 0.1 N with an SS-5GL2-F (16 gf) switch,
//   ≈ 0.05 N with an SS-01GL2-E (8 gf); while the card is being lifted ≈ 0.015 N.
//   The floor plate has a notch under the flag, so an EMPTY plate passes the
//   flag without closing the switch; the soft top limit then reports empty.
// =============================================

use <machine_frame.scad>

/* [Export] */
part = "body";   // body | cap | carriage | plate | flag | assembly | pos_* (see bottom)
zp   = -1;       // plate-top Z for "assembly"/"pos_*" (-1 = bottom of travel)
flag_phi_in = -1;// flag angle for "assembly"/"pos_flag" (-1 = resting on the stop)
card_dy  = 0;     // shift the checked card stack in Y (±1.5 = against a long wall)

$fn = 64;

// ── Card & cavity ──────────────────────────────────────────────────────────
card_l   = 88;  card_w = 63;  card_t = 0.33;  card_t_max = 0.35;
clr      = 1.5;                 // per side
cav_x    = card_l + 2 * clr;    // 91
cav_y    = card_w + 2 * clr;    // 66
hx = cav_x / 2;  hy = cav_y / 2;
wall     = 3;
ox = hx + wall;  oy = hy + wall;   // 48.5, 36
base_t   = 3;

// Pick height (top of the card stack, above the hopper base). Single source:
// machine_frame.scad card_z (belt top = suction-arm arc low point).
pick_z   = frame_card_z() - frame_base_top();   // 86.9
lip      = 3.5;                 // walls rise this far above pick_z (guides the top cards)
wall_top = pick_z + lip;        // 90.4
corner_r = 1.2;                 // vertical corner relief (centred on the cavity corner;
                                //   leaves 1.8 mm of the 3 mm wall, cards have r ≈ 3 corners)
// LIFT RELIEF (audit 2026-11-11). The arm's arc is 2° off vertical at pick, so
// a lifted card drifts +X: 0.18 mm while the slider is still compressed (card
// underside Z 90.57 machine), 0.42 at Z 92.9, 0.63 at the rim (Z 94.4). With
// the card's ±1.5 mm X play against the +X wall that scraped its short edge.
// Above relief_z the cavity steps out (+X by relief_px, the other three walls by
// relief_p): a card sitting against any wall then clears it by ≥ 0.3 mm over
// the whole lift (cad/pick_arm_check.py, card-offset cases ±1.5 X / ±1.5 Y).
// relief_z is 1 mm below the top card's top face, so the top card's underside
// (0.33 below) starts 0.67 mm above the step edge. Only the top ~3 cards are
// in the relief zone; the stack below is still guided by the 91 x 66 walls.
relief_z  = pick_z - 1.0;       // 85.9 local = machine Z 89.9
relief_px = 1.0;                // +X (belt-side) wall: drift side
relief_p  = 0.5;                // -X, +Y, -Y walls
top_ch   = 0.8;                 // 45° chamfer on the (relieved) cavity rim; rim land ≥ 1.2
edge_ch  = 0.6;                 // chamfer on slot edges that cards slide past

// Slots (all open to the top, so no card edge can catch while rising)
slot_w      = 34;               // carriage shelf passage in the +Y wall
finger_w    = 24;  finger_z0 = 14;   // loading/finger slot in the -Y wall
air_w       = 2.5; air_h     = 12;   // air-separation slots, top 12 mm of walls
air_x       = [-33, 33];

// ── Floor plate & carriage ────────────────────────────────────────────────
plate_t   = 4;   plate_gap = 1.0;    // 1 mm per side to the cavity walls
plate_rib = 5;                       // stiffening ribs under the plate
shelf_t   = 7;   shelf_w = 30;  shelf_y0 = 20;
plate_screw = [[-9, 26.5], [9, 26.5]];   // M3 countersunk into shelf inserts
car_gap_floor = 1;
zp_min    = base_t + car_gap_floor + shelf_t + plate_t;  // 15
zp_max    = pick_z - 0.3;            // soft top: one card below pick height
function car_z0(z) = z - plate_t - shelf_t;

rod_d  = 8;  rod_len = 150;  rod_dx = 28;  rod_y = 48.5;  rod_sock = 2.4;
lm_d   = 15; lm_l = 24; lm_lip = 1.5;    // LM8UU 8 x 15 x 24
car_y0 = 38; car_y1 = 59; car_h = 27; car_hx = rod_dx + lm_d / 2 + 3;  // 38.5

// ── Lead screw, nut, coupler, motor ───────────────────────────────────────
nut_style  = "t8";          // "t8" = T8 brass flange nut (default) | "m8" = M8 hex nut on M8 rod
// T8 brass flange nut (the common 3D-printer Z nut): flange Ø22 × 3.5, body
// Ø10.2, 15 long overall, 4 × Ø3.5 flange holes on a 16 mm PCD (measure yours).
// The PCD-16 holes are only 1.15 mm outside the body, so a fastener at PCD 16
// beside a Ø10.8 body bore leaves 0.6 mm of plastic (an insert there would
// crack / distort the bore). So the nut is mounted INVERTED: flange down on the
// floor of a Ø22.6 pocket 15 deep in the carriage top, body pointing up inside
// the pocket (free, no bore around it). Below the floor the carriage only needs
// the lead-screw clearance bore Ø8.8; 2 flange screws at PCD 16 run down
// through it into 2 M3 inserts pressed into the carriage BOTTOM, which keep
// 16/2 - 2.0 - 4.4 = 1.6 mm of wall to the bore (≥ 1.5). The lift load goes
// flange -> pocket floor in compression; the screws only stop the nut turning.
t8_fl_d = 22; t8_fl_t = 3.5; t8_body_d = 10.2; t8_len = 15; t8_pcd = 16;
t8_pocket_d = t8_fl_d + 0.6;                 // Ø22.6 pocket (the flange locates in it)
t8_slot_hw  = 7;                             // square through-slot where the pocket meets the ±Y faces
t8_screw_bore = 8.8;                         // lead-screw clearance below the pocket floor
m8_af   = 13; m8_h   = 6.5;
screw_d = 8; screw_len = 100;
screw_z0   = car_z0(zp_min) + car_h - t8_len - 3.5;                  // 12.5 (3.5 below the nut at zp_min)
coupler_d  = 19; coupler_l = 25;
coupler_z0 = car_z0(zp_max) + car_h + 1.5;                           // 104.1 (1.5 above the nut top)
motor_face_z = coupler_z0 + coupler_l + 2;                           // 131.1
motor_off  = 8;             // 28BYJ-48: body centre is 8 mm from the shaft (+Y here)
motor_ear  = 35;            // ear hole spacing (Ø4.2 holes)
cap_t   = 5;
cap_z0  = motor_face_z - cap_t;                                      // 126.1
tower_y1 = 70; tower_wall = 8; back_t = 3;
tower_ins = [[-44.5, 41], [44.5, 41], [-44.5, 64.5], [44.5, 64.5]];  // M3 inserts, cap screws

// ── Switches (Omron SS footprint: 19.8 x 6.4 x 10.2, Ø2.35 holes 9.5 apart) ─
sw_l = 19.8; sw_t = 6.4; sw_h = 10.2;
sw_hole_x = [5.1, 14.6]; sw_hole_z = 2.9;
sw_roll_x = 19.6;            // roller centre from the hole-end of the body
sw_op     = 14.5;            // roller top at Operating Position, above the hole line
sw_roll_d = 4.8; sw_roll_w = 3.2;
// bottom (home) switch: on the tower floor against the back wall
bsw_x0 = -3.6;  bsw_y0 = tower_y1 - back_t - sw_t;   // body X -3.6..16.2, Y 60.6..67
bsw_op_z = base_t + sw_hole_z + sw_op;                // 20.4: roller top at OP
lug_dz = bsw_op_z - (base_t + car_gap_floor) - 0.3;  // carriage lug 0.3 mm past OP at zp_min
lug_x  = [10, 22];
// The lug's underside is ONE 45° plane falling toward +X (along the roller's
// rolling direction, i.e. a cam ramp in the lever's plane), so the lug prints
// without support and has no flat ledge. It is placed tangent to the Ø4.8
// roller with the roller 0.3 past OP at zp_min (the same trip point as the old
// flat face): the carriage still pushes the roller down 1:1, the extra force on
// the roller points along the lever toward its hinge.
lug_xr = bsw_x0 + sw_roll_x;                                   // roller centre X (16.0)
lug_zr = bsw_op_z - 0.3 - sw_roll_d / 2;                       // roller centre Z at zp_min
function lug_u(x) = lug_zr + sw_roll_d / 2 * sqrt(2) - (x - lug_xr) - car_z0(zp_min);   // underside, carriage-relative
lug_top = lug_dz + 8;                                          // carriage-relative top of the lug

// ── Feeler flag + cam (top switch) ────────────────────────────────────────
// The flag sits on the -Y long wall (machine front; the tower is on +Y) and
// rests on the card's LONG-edge margin. Everything below (flag, cheeks, top
// switch, wall notch, plate notch) is defined in a FLAG FRAME (fx, fy, z):
// fx = horizontal toward the cavity, the flag wall's cavity face at fx = -fwd,
// fy = along the wall, flag plane fy = 0. at_flag() places that frame in the
// local frame: flag frame -X -> local -Y, flag plane at local X = flag_x.
flag_x   = -30;    // flag plane along the -Y wall (clear of the finger slot, the
                   // plate ribs and the +X side where the suction arm comes down)
fwd = hy;  fwo = hy + wall;   // flag wall: cavity face / outer face distance (33 / 36)
module at_flag() translate([flag_x, 0, 0]) rotate([0, 0, 90]) children();
flag_d   = 10.5;   // pivot outboard of the cavity face
flag_hp  = 6;      // pivot below pick_z
flag_e   = 5;      // tip contact inboard of the cavity face (card long-edge margin)
flag_rt  = 2.5;    // tip radius
flag_t   = 5.4;    // hub / tip thickness (fy); arm is 4
flag_w   = 4;      // arm width in its plane
rest_drop = 5;     // with no card at pick height the tip rests at pick_z - 5
piv   = [-fwd - flag_d, pick_z - flag_hp];          // [fx, Z] = [-43.5, 80.9]
tip_t = [-fwd + flag_e, pick_z + flag_rt];          // tip centre at trip
flag_L   = norm(tip_t - piv);                        // ≈17.5
phi_trip = atan2(tip_t[1] - piv[1], tip_t[0] - piv[0]);              // ≈29°
phi_rest = asin((pick_z - rest_drop + flag_rt - piv[1]) / flag_L);   // ≈15°
cam_ds   = 6.5;    // pivot -> switch roller top at OP
cam_R1   = cam_ds + 0.4;   // peak radius: 0.4 mm into overtravel (OT min 0.8)
cam_R0   = cam_ds - 1.8;   // base radius: clears the roller even at FP (PT max 1.2)
cam_ramp = 12;             // deg of flag rotation for the ramp
cam_lead = 2.2;            // deg: the Ø4.8 roller lags the ideal ramp (measured, sweep of the conjugate cam)
phi_a    = phi_trip - cam_ramp * (cam_ds - cam_R0) / (cam_R1 - cam_R0) - cam_lead;
phi_b    = phi_a + cam_ramp;
cheek_t  = 4;  cheek_in = flag_t / 2 + 0.5;          // cheek inner faces at ±3.2
// The arm is CRANKED: pivot -> elbow (above the wall) -> tip. A straight arm
// from a pivot below pick_z would slope up toward the tip, so its underside
// would hit the card edge before the tip; with the elbow the rounded tip is
// always the lowest point of the flag over the cavity.
elbow_t  = [-fwd - 2, pick_z + 5.5];                 // elbow centre at trip [fx, Z]
pe_off   = atan2(elbow_t[1] - piv[1], elbow_t[0] - piv[0]) - phi_trip;  // P->E vs P->T, ≈22°
pe_len   = norm(elbow_t - piv);
elbow_f  = pe_len * [cos(pe_off), sin(pe_off)];      // elbow in the flag frame (P->T = +u)
phi_stop = 80;                                       // flag upper stop
stop_r   = 9;
stop_ang = phi_stop + pe_off + asin((flag_w / 2 + 2) / stop_r);   // stop pin Ø4 on the P->E segment
notch_hw = 3.7;                                        // flag-wall notch half-width
// lowest P->E underside over the wall (outer face fx = -fwo) at rest = notch floor
notch_z  = let(a = phi_rest + pe_off)
           piv[1] + (-fwo - piv[0]) * tan(a) - (flag_w / 2) / cos(a);
// top switch: roller centre straight below the pivot, body runs outward (-fx)
tsw_roll_top = piv[1] - cam_ds;
tsw_z0   = tsw_roll_top - sw_hole_z - sw_op;
tsw_x0   = piv[0] - sw_roll_x;
// plate notch under the flag tip/arm (empty plate passes the flag)
pnotch_x1 = piv[0] + flag_L * cos(phi_rest) + flag_rt + 1.5;
pnotch_hw = 4;

// Baseplate M3 grid holes that land inside the footprint (machine grid 30 mm,
// see baseplate_tile.scad; hopper centre X=-215 -> local X -25 / +35)
base_holes = [[-25, -15], [-25, 15], [35, -15], [35, 15]];

// ── Sanity checks ─────────────────────────────────────────────────────────
assert(ox <= 48.5 + 1e-6, "outer +X wall must stay at machine X <= -166");
assert(screw_z0 + screw_len - coupler_z0 >= 7, "lead screw too short for the coupler");
assert(phi_a > phi_rest + 2, "cam ramp starts before the flag rest angle");
assert(car_hx + 2 <= ox - tower_wall, "carriage too wide for the tower");
assert(t8_pcd / 2 - 4.0 / 2 - t8_screw_bore / 2 >= 1.5, "T8 flange inserts too close to the screw bore");
assert(t8_pocket_d / 2 + 1.5 <= rod_dx - lm_d / 2, "T8 pocket too close to the LM8UU bores");
assert(car_h - t8_len >= 5.7 + 4, "too little carriage under the T8 pocket for the inserts");
// wall left between the T8 pocket and a ±Y face at the slot edge (|X| = t8_slot_hw)
assert(min(rod_y - car_y0, car_y1 - rod_y) - sqrt(pow(t8_pocket_d / 2, 2) - pow(t8_slot_hw, 2)) >= 1.5,
       "T8 pocket leaves a thin flap beside the slot");
assert(lug_u(lug_x[1]) > 0 && lug_u(lug_x[0]) < lug_top, "bottom-switch lug ramp out of range");
assert(rod_y - (coupler_d + 3.6) / 2 - oy >= 1.2 - 0.01, "cap wall in front of the coupler hole < 1.2");

// =========================================================================
// Helpers
// =========================================================================
module vch(x, y, z0, h, c = edge_ch)      // vertical 45° edge-chamfer cutter
    translate([x, y, z0]) rotate([0, 0, 45]) cube([c * sqrt(2), c * sqrt(2), h], center = false);

module vch_c(x, y, z0, h, c = edge_ch)
    translate([x, y, z0 + h / 2]) rotate([0, 0, 45]) cube([c * sqrt(2), c * sqrt(2), h], center = true);

// Slot through a wall: profile in the wall plane (s along the wall, z up),
// flat bottom with 45° bottom corners, open to the top.
module slot_profile(w, z0, ztop, c0 = 1.5)
    let(c = min(c0, w / 2 - 0.3))
    polygon([[-w / 2, z0 + c], [-w / 2 + c, z0], [w / 2 - c, z0], [w / 2, z0 + c],
             [w / 2, ztop], [-w / 2, ztop]]);

module slot_y(xc, y_in, y_out, w, z0, ztop)   // through a wall normal to Y
    translate([xc, (y_in + y_out) / 2, 0]) rotate([90, 0, 0])
        linear_extrude(height = abs(y_out - y_in) + 0.2, center = true) slot_profile(w, z0, ztop);

module slot_x(yc, x_in, x_out, w, z0, ztop)   // through a wall normal to X
    translate([(x_in + x_out) / 2, yc, 0]) rotate([90, 0, 90])
        linear_extrude(height = abs(x_out - x_in) + 0.2, center = true) slot_profile(w, z0, ztop);

module insert_hole(h = 6)  cylinder(d = 4.0, h = h, $fn = 24);     // M3 heat-set (Ø4.0-4.2 pilot)

// =========================================================================
// BODY: hopper shell + drive tower + flag cheeks (one print, upright)
// =========================================================================
module tower_shell()
    difference() {
        translate([-ox, oy - 0.01, 0]) cube([2 * ox, tower_y1 - oy + 0.01, cap_z0]);
        translate([-ox + tower_wall, oy - 1, base_t])
            cube([2 * (ox - tower_wall), tower_y1 - back_t - oy + 1, cap_z0]);
        // back access window, pointed top (prints without a bridge)
        translate([0, tower_y1 - back_t / 2, 0]) rotate([90, 0, 0])
            linear_extrude(height = back_t + 1, center = true)
                polygon([[-26, 30], [26, 30], [26, cap_z0 - 29.6], [0, cap_z0 - 3.6], [-26, cap_z0 - 29.6]]);
    }

// Cheek profiles in the XZ plane (attached to the -X wall outer face)
module cheek_pos_2d()     // +Y cheek: pivot, flag stop, top switch
    let(xf = tsw_x0 - 2.5, zb = tsw_z0 - 3, zl = zb - (-fwo - xf))
    polygon([[-fwo + 0.01, zl], [xf, zb], [xf, piv[1] + 4], [piv[0] - 8.5, piv[1] + 13],
             [-fwo + 0.01, piv[1] + 13]]);
module cheek_neg_2d()     // -Y cheek: pivot and flag stop only
    let(xf = piv[0] - 8.5, zb = piv[1] - 7, zl = zb - (-fwo - xf))
    polygon([[-fwo + 0.01, zl], [xf, zb], [xf, piv[1] + 13], [-fwo + 0.01, piv[1] + 13]]);

module flag_cheeks() {
    translate([0, cheek_in + cheek_t, 0]) rotate([90, 0, 0])
        linear_extrude(height = cheek_t) cheek_pos_2d();
    translate([0, -cheek_in, 0]) rotate([90, 0, 0])
        linear_extrude(height = cheek_t) cheek_neg_2d();
    // upper stop pin bridging the cheeks (flag stops at ≈80°)
    translate([piv[0] + stop_r * cos(stop_ang), 0, piv[1] + stop_r * sin(stop_ang)])
        rotate([90, 0, 0]) cylinder(d = 4, h = 2 * cheek_in + 2, center = true, $fn = 24);
}

module hopper_body() {
    difference() {
        union() {
            translate([-ox, -oy, 0]) cube([2 * ox, 2 * oy, wall_top]);
            tower_shell();
            at_flag() flag_cheeks();
        }
        // cavity, corner reliefs, lift relief, rim chamfer
        translate([-hx, -hy, base_t]) cube([cav_x, cav_y, wall_top]);
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * hx, sy * hy, base_t]) cylinder(r = corner_r, h = wall_top, $fn = 32);
        translate([-hx - relief_p, -hy - relief_p, relief_z])
            cube([cav_x + relief_p + relief_px, cav_y + 2 * relief_p, wall_top]);
        hull() {
            translate([-hx - relief_p, -hy - relief_p, wall_top - top_ch])
                cube([cav_x + relief_p + relief_px, cav_y + 2 * relief_p, 0.01]);
            translate([-hx - relief_p - top_ch, -hy - relief_p - top_ch, wall_top])
                cube([cav_x + relief_p + relief_px + 2 * top_ch, cav_y + 2 * relief_p + 2 * top_ch, 0.01]);
        }
        // carriage shelf passage through the +Y wall (open to the top)
        translate([-slot_w / 2, hy - 0.1, base_t]) cube([slot_w, wall + 0.2, cap_z0]);
        for (sx = [-1, 1]) vch_c(sx * slot_w / 2, hy, base_t, wall_top);
        // finger slot in the -Y wall
        slot_y(0, -hy, -oy, finger_w, finger_z0, wall_top + 1);
        for (sx = [-1, 1]) vch_c(sx * finger_w / 2, -hy, finger_z0 + 1.6, wall_top);
        // air-separation slots: +Y wall at X ±33, -Y wall at X +33 (the flag
        // notch at X -30 is the second one there), both end walls at Y 0
        for (xs = [[air_x[0], 1], [air_x[1], 1], [air_x[1], -1]]) let(x = xs[0], s = xs[1]) {
            slot_y(x, s * hy, s * oy, air_w, wall_top - air_h, wall_top + 1);
            for (sx = [-1, 1]) vch_c(x + sx * air_w / 2, s * hy, wall_top - air_h + 1.2, air_h, 0.4);
        }
        for (s = [-1, 1]) {
            slot_x(0, s * hx, s * ox, air_w, wall_top - air_h, wall_top + 1);
            for (sy = [-1, 1]) vch_c(s * hx, sy * air_w / 2, wall_top - air_h + 1.2, air_h, 0.4);
        }
        // flag notch in the -Y wall (flag frame)
        at_flag() {
            slot_x(0, -fwd, -fwo, 2 * notch_hw, notch_z, wall_top + 1);
            for (sy = [-1, 1]) vch_c(-fwd, sy * notch_hw, notch_z + 1.6, wall_top);
        }
        // guide-rod sockets
        for (sx = [-1, 1]) translate([sx * rod_dx, rod_y, base_t - rod_sock])
            cylinder(d = rod_d + 0.15, h = rod_sock + 0.1);
        // cap screw inserts in the tower walls
        for (p = tower_ins) translate([p[0], p[1], cap_z0 - 6]) insert_hole(6.1);
        // baseplate screws (M3 countersunk, flush with the cavity floor)
        for (p = base_holes) translate([p[0], p[1], -0.1]) {
            cylinder(d = 3.4, h = base_t + 0.2, $fn = 20);
            translate([0, 0, base_t - 1.6 + 0.1]) cylinder(d1 = 3.4, d2 = 6.6, h = 1.6, $fn = 24);
        }
        // bottom switch: M2 through the back wall
        for (hx_ = sw_hole_x) translate([bsw_x0 + hx_, tower_y1 - back_t - 0.1, base_t + sw_hole_z])
            rotate([-90, 0, 0]) cylinder(d = 2.2, h = back_t + 0.2, $fn = 16);
        at_flag() {
            // flag pivot (M3 axle through both cheeks)
            translate([piv[0], 0, piv[1]]) rotate([90, 0, 0])
                cylinder(d = 3.4, h = 2 * (cheek_in + cheek_t) + 1, center = true, $fn = 24);
            // top switch: M2 slots (±1.2 mm along the actuation axis, to set the trip height)
            for (hx_ = sw_hole_x) translate([tsw_x0 + hx_, cheek_in + cheek_t / 2, tsw_z0 + sw_hole_z])
                hull() for (dz = [-1.2, 1.2]) translate([0, 0, dz]) rotate([90, 0, 0])
                    cylinder(d = 2.4, h = cheek_t + 1, center = true, $fn = 16);
        }
    }
}

// =========================================================================
// CAP: tower cap / motor plate (screws onto the 4 tower inserts)
// =========================================================================
module hopper_cap() {
    difference() {
        union() {
            translate([-ox, oy, cap_z0]) cube([2 * ox, tower_y1 - oy, cap_t]);
            // bosses under the motor-ear inserts
            for (sx = [-1, 1]) translate([sx * motor_ear / 2, rod_y + motor_off, cap_z0 - 2.5])
                cylinder(r = 4, h = 2.6, $fn = 32);
        }
        for (sx = [-1, 1]) translate([sx * rod_dx, rod_y, cap_z0 - 1]) cylinder(d = rod_d + 0.15, h = cap_t + 2);
        // coupler pass Ø22.6 (1.8 radial play): leaves 1.2 of cap wall at its −Y edge (oy)
        translate([0, rod_y, cap_z0 - 1]) cylinder(d = coupler_d + 3.6, h = cap_t + 2);
        for (sx = [-1, 1]) translate([sx * motor_ear / 2, rod_y + motor_off, cap_z0 - 2.6]) insert_hole(cap_t + 3);
        for (p = tower_ins) translate([p[0], p[1], cap_z0 - 1]) cylinder(d = 3.4, h = cap_t + 2, $fn = 20);
    }
}

// =========================================================================
// CARRIAGE (z = plate-top position `z`)
// =========================================================================
module hopper_carriage(z = zp_min) {
    c0 = car_z0(z);
    difference() {
        union() {
            translate([-car_hx, car_y0, c0]) cube([2 * car_hx, car_y1 - car_y0, car_h]);
            // shelf that reaches through the +Y wall slot under the floor plate
            translate([-shelf_w / 2, shelf_y0, c0]) cube([shelf_w, car_y0 - shelf_y0 + 0.01, shelf_t]);
            // lug that presses the bottom (home) switch roller (Y 62.2..65.4):
            // 45° ramp underside falling toward +X (see lug_u), out to Y 66.4
            translate([0, bsw_y0 + sw_t - 0.6, c0]) rotate([90, 0, 0])
                linear_extrude(height = bsw_y0 + sw_t - 0.6 - (car_y1 - 0.01))
                    polygon([[lug_x[0], lug_u(lug_x[0])], [lug_x[1], lug_u(lug_x[1])],
                             [lug_x[1], lug_top], [lug_x[0], lug_top]]);
        }
        // LM8UU bores (press fit from the top onto a 1.5 mm lip)
        for (sx = [-1, 1]) translate([sx * rod_dx, rod_y, c0]) {
            translate([0, 0, lm_lip]) cylinder(d = lm_d, h = car_h);
            translate([0, 0, -1]) cylinder(d = rod_d + 2, h = car_h + 2);
        }
        if (nut_style == "t8") {
            // inverted T8 nut: Ø22.6 pocket from the top. The carriage is only
            // 21 deep in Y, so the pocket would break out of both ±Y faces at
            // |X| < 4.2 and leave 0..0.75 mm knife-edge flaps beside the
            // break-outs; instead a square slot (|X| ≤ t8_slot_hw, pocket
            // height) is cut cleanly through both faces, leaving ≥ 1.6 mm of
            // wall at its edges. The flange still locates on the pocket arcs
            // at |X| 7..11.3. Screw bore below. 2 flange screws at PCD 16 (along X): Ø3.4 from the pocket
            // floor down, into M3 inserts pressed in FROM THE CARRIAGE BOTTOM
            // (flush with it: free iron access, no reaching 15 mm down the
            // pocket beside the wall)
            translate([0, rod_y, c0 + car_h - t8_len]) cylinder(d = t8_pocket_d, h = t8_len + 1);
            translate([-t8_slot_hw, car_y0 - 1, c0 + car_h - t8_len]) cube([2 * t8_slot_hw, car_y1 - car_y0 + 2, t8_len + 1]);
            translate([0, rod_y, c0 - 1]) cylinder(d = t8_screw_bore, h = car_h + 2);
            for (sx = [-1, 1]) translate([sx * t8_pcd / 2, rod_y, c0 - 0.1]) {
                insert_hole(5.8);
                cylinder(d = 3.4, h = car_h - t8_len + 0.2, $fn = 20);
            }
        } else {
            // M8 hex nut, captive in a side pocket entered from +Y (carriage rests on it)
            translate([0, rod_y, c0 - 1]) cylinder(d = screw_d + 0.8, h = car_h + 2);
            translate([0, rod_y, c0 + car_h - 12]) {
                cylinder(d = (m8_af + 0.3) / cos(30), h = m8_h + 0.3, $fn = 6);
                translate([-(m8_af + 0.3) / 2, 0, 0]) cube([m8_af + 0.3, car_y1 - rod_y + 1, m8_h + 0.3]);
            }
        }
        // plate screw inserts in the shelf
        for (p = plate_screw) translate([p[0], p[1], c0 - 0.1]) insert_hole(shelf_t + 0.2);
    }
}

// =========================================================================
// FLOOR PLATE (z = plate-top position)
// =========================================================================
module hopper_plate(z = zp_min) {
    px = hx - plate_gap;  py = hy - plate_gap;
    difference() {
        union() {
            // top edge chamfered 0.8, corners rounded r 2.5
            hull() for (sx = [-1, 1], sy = [-1, 1])
                translate([sx * (px - 2.5), sy * (py - 2.5), z - plate_t]) {
                    cylinder(r = 2.5, h = plate_t - 0.8, $fn = 24);
                    cylinder(r = 1.7, h = plate_t, $fn = 24);
                }
            // ribs underneath (clear of the shelf, the flag notch and the base screws)
            for (sx = [-1, 1]) translate([sx * 20 - 1.5, -py + 3, z - plate_t - plate_rib]) cube([3, 2 * py - 6, plate_rib + 0.01]);
            translate([-px + 3, -15 - 1.5, z - plate_t - plate_rib]) cube([2 * px - 6, 3, plate_rib + 0.01]);
        }
        // notch so the empty plate passes under the resting flag
        at_flag() translate([-fwd - 1, -pnotch_hw, z - plate_t - plate_rib - 1]) cube([pnotch_x1 + fwd + 1, 2 * pnotch_hw, plate_t + plate_rib + 2]);
        // M3 countersunk screws into the shelf
        for (p = plate_screw) translate([p[0], p[1], z - plate_t - 0.1]) {
            cylinder(d = 3.4, h = plate_t + 0.2, $fn = 20);
            translate([0, 0, plate_t - 1.6 + 0.1]) cylinder(d1 = 3.4, d2 = 6.6, h = 1.6 + 0.01, $fn = 24);
        }
    }
}

// =========================================================================
// FEELER FLAG (flag-local: pivot at origin, arm along +X, thickness along Y)
// =========================================================================
// Cam radius under the roller vs flag angle: base (no contact) -> ramp (switch
// closes at phi_trip) -> peak R1 (0.4 mm overtravel) -> slow descent to below FP
// at the stop. The descent makes the switch spring push the flag back DOWN
// (≈0.15-0.2 N·mm), which beats pivot friction (a constant-radius dwell would
// give zero return torque and the 1.2 g flag could hang up). Extra force on
// the card while it is being lifted: ≈0.015 N.
cam_Rend = cam_ds - 0.8;
cam_hold = 12;     // deg of plateau at R1 after the ramp (a round roller shaves a sharp peak)
function cam_r(phi) = phi <= phi_a ? cam_R0
                    : phi <= phi_b ? cam_R0 + (cam_R1 - cam_R0) * (phi - phi_a) / (phi_b - phi_a)
                    : phi <= phi_b + cam_hold ? cam_R1
                    : cam_R1 - (cam_R1 - cam_Rend) * min(1, (phi - phi_b - cam_hold) / (phi_stop - phi_b - cam_hold));
// Conjugate cam: the roller (Ø4.8, straight below the pivot) must have its top
// at distance cam_r(phi) from the pivot at flag angle phi. In the flag frame the
// roller sits at rotate(-phi) of that position; the cam is a Ø(2·R1) disc minus
// the roller swept over the whole flag travel (round-roller flank contact included).
module cam_2d()
    union() {
        circle(r = cam_R0);
        difference() {
            circle(r = cam_R1);
            for (p = [phi_rest - 3 : 0.5 : phi_stop + 3])
                rotate(-p) translate([0, -(cam_r(p) + sw_roll_d / 2)]) circle(d = sw_roll_d, $fn = 32);
        }
    }

module flag_local() {
    difference() {
        union() {
            rotate([90, 0, 0]) linear_extrude(height = flag_t, center = true)
                cam_2d();
            rotate([90, 0, 0]) linear_extrude(height = 4, center = true) {
                hull() { circle(r = flag_w / 2); translate(elbow_f) circle(r = flag_w / 2); }
                hull() { translate(elbow_f) circle(r = flag_w / 2); translate([flag_L, 0]) circle(r = flag_w / 2); }
            }
            // rounded, edge-chamfered Ø5 tip
            translate([flag_L, 0, 0]) rotate([90, 0, 0]) hull() {
                cylinder(r = flag_rt, h = flag_t - 1.2, center = true);
                cylinder(r = flag_rt - 0.6, h = flag_t, center = true);
            }
        }
        rotate([90, 0, 0]) cylinder(d = 3.4, h = flag_t + 2, center = true, $fn = 24);
    }
}
module hopper_flag(phi = phi_rest) at_flag()
    translate([piv[0], 0, piv[1]]) rotate([0, -phi, 0]) flag_local();

// =========================================================================
// Reference hardware (not printed) — for the assembly view and collision checks
// =========================================================================
module hw_rods()     for (sx = [-1, 1]) translate([sx * rod_dx, rod_y, base_t - rod_sock + 0.01]) cylinder(d = rod_d, h = rod_len);
module hw_bushings(z = zp_min)
    for (sx = [-1, 1]) translate([sx * rod_dx, rod_y, car_z0(z) + lm_lip + 0.01])
        difference() { cylinder(d = lm_d - 0.05, h = lm_l); translate([0, 0, -1]) cylinder(d = rod_d + 0.05, h = lm_l + 2); }
module hw_screw()    translate([0, rod_y, screw_z0]) cylinder(d = screw_d, h = screw_len);
module hw_nut(z = zp_min) {    // inverted: flange on the pocket floor, body up
    fl = car_z0(z) + car_h - t8_len;
    translate([0, rod_y, 0]) difference() {
        union() {
            translate([0, 0, fl + 0.01]) cylinder(d = t8_fl_d, h = t8_fl_t);
            translate([0, 0, fl + t8_fl_t]) cylinder(d = t8_body_d, h = t8_len - t8_fl_t - 0.02);
        }
        translate([0, 0, fl - 1]) cylinder(d = screw_d + 0.05, h = t8_len + 2);
    }
}
module hw_coupler()  translate([0, rod_y, coupler_z0]) difference() {
    cylinder(d = coupler_d, h = coupler_l);
    translate([0, 0, -1]) cylinder(d = screw_d + 0.05, h = coupler_l / 2 + 1);
    translate([0, 0, coupler_l / 2]) cylinder(d = 5.05, h = coupler_l);
}
module hw_motor() {   // 28BYJ-48 (Fulling drawing), mounted shaft-DOWN on the cap
    mz = motor_face_z + 0.01;
    translate([0, rod_y + motor_off, mz]) {
        cylinder(d = 28, h = 19);
        hull() for (sx = [-1, 1]) translate([sx * motor_ear / 2, 0, 0]) cylinder(r = 3.5, h = 0.8);
        translate([-7.25, 0, 2.7]) cube([14.5, 17.5, 19 - 2.7]);   // wire cover (side opposite the shaft)
    }
    translate([0, rod_y, mz - 1.5]) cylinder(d = 9, h = 1.5);       // boss
    translate([0, rod_y, mz - 10]) intersection() {                // Ø5 shaft, 3 mm across flats
        cylinder(d = 5, h = 8.5);
        translate([-2.5, -1.5, 0]) cube([5, 3, 8.5]);
    }
}
module sw_body() cube([sw_l, sw_t, sw_h]);
module sw_roller() rotate([90, 0, 0]) cylinder(d = sw_roll_d, h = sw_roll_w, center = true, $fn = 24);
// switch drawn at its Operating Position (roller top at sw_op above the hole line)
module hw_sw_bottom_body()   translate([bsw_x0, bsw_y0, base_t]) sw_body();
module hw_sw_bottom_roller() translate([bsw_x0 + sw_roll_x, bsw_y0 + sw_t / 2, base_t + sw_hole_z + sw_op - sw_roll_d / 2]) sw_roller();
module hw_sw_top_body()      at_flag() translate([tsw_x0, -sw_t / 2, tsw_z0]) sw_body();
module hw_sw_top_roller()    at_flag() translate([piv[0], 0, tsw_roll_top - sw_roll_d / 2]) sw_roller();
module hw_cards(z = zp_min, n = 0)    // n cards on the plate (default: fill to pick_z)
    let(nn = n > 0 ? n : floor((pick_z - z) / card_t))
    translate([-card_l / 2, -card_w / 2, z]) cube([card_l, card_w, nn * card_t]);

// Assembled hopper in LOCAL coords. plate_z = plate top; flag_phi -1 = resting
// on the top card if the stack reaches pick_z, otherwise on its stop.
module hopper_elevator_local(plate_z = zp_min, flag_phi = -1, cards = true) {
    hopper_body();
    hopper_cap();
    hopper_carriage(plate_z);
    hopper_plate(plate_z);
    hopper_flag(flag_phi >= 0 ? flag_phi : (cards ? phi_trip : phi_rest));   // per header: rests on the top card when loaded
    color("silver") { hw_rods(); hw_screw(); hw_coupler(); hw_nut(plate_z); hw_bushings(plate_z); }
    color("gold") hw_motor();
    color("dimgray") { hw_sw_bottom_body(); hw_sw_top_body(); }
    color("white") { hw_sw_bottom_roller(); hw_sw_top_roller(); }
    if (cards) %hw_cards(plate_z);
}

// Exported for hopper_elevator.scad / assembly
function hopper_pick_z()   = pick_z;
function hopper_zp_min()   = zp_min;
function hopper_zp_max()   = zp_max;
function hopper_phi_rest() = phi_rest;
function hopper_phi_trip() = phi_trip;
function hopper_outer()    = [[-ox, tsw_x0 - 2.5], [ox, tower_y1]];   // footprint incl. flag cheeks (excl. motor wire cover)

// =========================================================================
// Export selector
// =========================================================================
_zp  = zp >= 0 ? zp : zp_min;
_phi = flag_phi_in >= 0 ? flag_phi_in : phi_rest;

if (part == "body")     hopper_body();
if (part == "cap")      translate([0, 0, cap_z0 + cap_t]) mirror([0, 0, 1]) hopper_cap();   // top face on the bed
if (part == "carriage") translate([0, 0, -car_z0(zp_min)]) hopper_carriage(zp_min);
if (part == "plate")    translate([0, 0, zp_min]) mirror([0, 0, 1]) hopper_plate(zp_min); // card face on the bed
if (part == "flag")     translate([0, 0, flag_t / 2]) rotate([-90, 0, 0]) flag_local();   // lies flat
if (part == "assembly") hopper_elevator_local(_zp, _phi);
// positioned single parts (local coords) for collision checks
if (part == "pos_body")      hopper_body();
if (part == "pos_cap")       hopper_cap();
if (part == "pos_carriage")  hopper_carriage(_zp);
if (part == "pos_plate")     hopper_plate(_zp);
if (part == "pos_flag")      hopper_flag(_phi);
if (part == "pos_rods")      hw_rods();
if (part == "pos_bushings")  hw_bushings(_zp);
if (part == "pos_screw")     hw_screw();
if (part == "pos_nut")       hw_nut(_zp);
if (part == "pos_coupler")   hw_coupler();
if (part == "pos_motor")     hw_motor();
if (part == "pos_swb_body")  hw_sw_bottom_body();
if (part == "pos_swb_roll")  hw_sw_bottom_roller();
if (part == "pos_swt_body")  hw_sw_top_body();
if (part == "pos_swt_roll")  hw_sw_top_roller();
if (part == "pos_cards")     hw_cards(_zp);
// stack whose top is exactly at pick_z (what the flag sees at trip)
if (part == "pos_cards_pick") translate([-card_l / 2, card_dy - card_w / 2, _zp]) cube([card_l, card_w, pick_z - _zp]);

// =============================================
// PRINT ORIENTATION / SUPPORTS
//   body     upright as modelled (base on bed). No supports: every slot is
//            open to the top, the tower window has a 45° pointed top, the
//            flag cheeks have 45° undersides, horizontal holes are ≤ Ø3.4.
//            97 x 135.6 x 126.1 mm (Y -65.6 .. +70 incl. the flag cheeks).
//   cap      top face down (part="cap" is already flipped). No supports.
//   carriage upright (shelf on the bed). No supports (the lug underside is
//            one 45° ramp; the T8 pocket and its square through-slot open
//            upward).
// HARDWARE (carriage): 2 × M3 heat-set inserts pressed into the carriage
//   BOTTOM at local (±8, 48.5), flush; T8 nut dropped into the top pocket
//   flange-first, body up, flange holes on the X axis; 2 × M3 × 14 SHCS down
//   through the flange (3.5) and the 12 mm under the pocket floor into the
//   inserts (≈ 4.2 mm engagement, tip 1.5 above the bottom face).
//   plate    card face down on the PEI (part="plate" is flipped) -> smooth
//            card face, ribs up. No supports.
//   flag     on its side (part="flag"). No supports.
// =============================================
