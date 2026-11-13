// =========================================================================
// Option B ("turntable picker"): shared geometry. Keep in sync with b_check.py.
//
// World frame: origin = yaw axis on the board top, Z up. The arm points at
// azimuth = servo angle s (deg, from +X, counter-clockwise). Stations sit on
// a circle of radius R at s = 10, 30, ..., 170: hopper, scan/weigh platform,
// bins 1-6, reject. Electronics, pump and the cable post live behind (-Y).
//
// Arm-local frame (turntable, mast, links, hand): +X along the arm, +Y
// tangential (counter-clockwise), Z up. The cup axis is the plane Y = 0; the
// parallelogram links run in the plane Y = 9..19.
// Round 2 (2026-11-13): review fixes, see CHANGES in cad_b/README.md.
// =========================================================================
$fn = 48;
eps = 0.01;

// ---- card + stations ----
card_w = 63; card_l = 88; card_t = 0.33;
R      = 260;                 // cup-centre radius at every station
st0    = 10; pitch = 20; n_st = 9;
function st_angle(i) = st0 + i * pitch;
st_hopper = 0; st_scan = 1;   // bins: i = 2..7, reject: i = 8

// ---- pockets ----
floor_t   = 2;
wall      = 2.4;
pocket_h  = floor_t + 32;     // wall top Z 34 (80 cards = 26.4 mm)
hop_in_w  = 65; hop_in_l = 90;           // hopper: 1 mm room each side, 2 mm lead-in chamfer
hop_chamfer = 2;
bin_r_in  = R - 50; bin_r_out = R + 50;  // bin wedge, inside faces (radial): 6 mm room each end
half_wall = 1.2;                         // each bin's own radial wall ...
divider_r0 = 236;                        // ... which starts here: no divider where the wedge is narrow

// ---- scan / weigh platform ----
cell_l = 75; cell_s = 12.7;              // owned 5 kg bar cell, 4 x M4
cell_hole_outer = 64; cell_hole_inner = 44;
cell_z0  = 8;                            // cell underside (on the cell block)
bed_boss = 5;                            // bed boss on the free end (M4 head recess leaves 4 mm)
bed_t    = 3.3;
bed_top  = cell_z0 + cell_s + bed_boss + bed_t;   // 29.0
bed_w = 70; bed_l = 96;

// ---- MG996R (both servos) ----
sv_l = 40.7; sv_w = 19.7; sv_case_h = 37.0; sv_h = 42.9;   // bottom -> spline top
sv_tab_z0 = 26.8; sv_tab_t = 2.5; sv_tab_span = 54.0;
sv_hole_p = 49.5; sv_hole_dx = 10;
sv_shaft_off = 10.2;                     // spline centre from the near case end
horn_d = 21; horn_t = 3; horn_gap = 1.4; // owned round disc horn: 21 mm

// ---- yaw stage ----
yaw_spline_z = 45;                       // spline top
yaw_sv_bot   = yaw_spline_z - sv_h;      // 2.1
tt_z0 = yaw_spline_z + horn_gap;         // turntable underside = horn front face (46.4)
tt_t  = 5;  tt_d = 104;
tt_top = tt_z0 + tt_t;                   // 51.4
roller_r = 42;                           // 608ZZ sag stop under the rim
roller_gap = 0.5;                        // nominal; axle slots give +/-1.5 to set it with a paper shim

// ---- lift stage (parallelogram) ----
L      = 220;                            // link pivot-to-pivot
r_p1   = 25;                             // P1 = lift servo spline, radius from the yaw axis
z_p1   = 70;
d_link = 40;                             // P2 = P1 + [0, 0, d_link]
h_off  = 15;                             // hand: link pivots -> cup axis (radial)
link_y0 = 9; link_t = 10; link_hgt = 12; // links in the plane Y = 9..19
th_min = -6; th_max = 10;                // link swing (deg, + = up)

// ---- hand + slider + cup ----
slider_below = 22;                       // slider below the hand bottom (tee + tube clear at full lift)
cup_h = 23; cup_d = 28;                  // owned PATIKIL 27 mm bellows cup (rubber neck, 4 mm bore)
hand_drop   = 8 + slider_below + cup_h;  // H1 -> cup lip with the slider resting (53)
slider_d = 12; slider_bore = 12.6;
slider_travel = 10;
contact_r = 9.6;                         // M3 head-up contact screws under the 608 ring (clear of the bore)

// ---- camera tower ----
cam_r_tower = 345;                       // tower post centre radius
cam_dist    = 176;                       // lens -> bed: +5 D close-up lens on a 1.5 m-inf camera
cam_lens_z  = bed_top + cam_dist;        // 205
ring_side   = 22;                        // WS2812 ring beside the post (+Y), off-axis: no foil hot spot
ring_z      = bed_top + 50;

// ---- board ----
board_x = 610; board_y = 610; board_t = 12;
board_y0 = -290;                         // board spans Y -290..320 (yaw axis at 0,0)
cable_post_xy = [0, -160];               // fixed post the tube/wire loop hangs from

// ---- helpers ----
module at_station(i, z = 0) translate([R * cos(st_angle(i)), R * sin(st_angle(i)), z]) rotate([0, 0, st_angle(i)]) children();
function H1z(th) = z_p1 + L * sin(th);
function cup_lip_z(th) = H1z(th) - hand_drop;
