// =========================================================================
// Option B ("turntable picker"): shared geometry. Keep in sync with b_check.py.
//
// World frame: origin = yaw axis on the board top, Z up. The arm points at
// azimuth = yaw angle s (deg, from +X, counter-clockwise). Stations sit on
// a circle of radius R at s = 10, 30, ..., 170: hopper, scan/weigh platform,
// bins 1-6, reject. Electronics, pump and the cable post live behind (-Y).
//
// Arm-local frame (turntable, mast, links, hand): +X along the arm, +Y
// tangential (counter-clockwise), Z up. The cup axis is the plane Y = 0; the
// parallelogram links run in the plane Y = 9..19.
// Round 2 (2026-11-13): review fixes, see CHANGES in cad_b/README.md.
// Round 4 (2026-11-14): yaw axis is a 28BYJ-48 stepper on a lazy-susan bearing.
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

// ---- MG996R (lift servo) ----
sv_l = 40.7; sv_w = 19.7; sv_case_h = 37.0; sv_h = 42.9;   // bottom -> spline top
sv_tab_z0 = 26.8; sv_tab_t = 2.5; sv_tab_span = 54.0;
sv_hole_p = 49.5; sv_hole_dx = 10;
sv_shaft_off = 10.2;                     // spline centre from the near case end
horn_d = 21; horn_t = 3; horn_gap = 1.4; // owned round disc horn: 21 mm

// ---- yaw stage (round 4, 2026-11-14): 28BYJ-48 stepper + 4" lazy-susan bearing ----
// The turntable rides on a 4" square lazy-susan bearing (carries the arm's
// weight and tipping moment); the stepper sits under it, shaft up on the yaw
// axis, and only turns it through a press-fit double-D hub.
tt_z0 = 46.4;                            // turntable underside (unchanged from round 3: arm geometry identical)
tt_t  = 5;  tt_d = 104;
tt_top = tt_z0 + tt_t;                   // 51.4
ls_sq = 102; ls_t = 7.9;                 // 4" square lazy susan, 5/16" thick
ls_hole = 55;                            // centre hole (2.16"), clear for hub + nuts
ls_pitch = 80.8;                         // mounting holes 3.18" on centre (CHECK on the bearing you get)
ls_z0 = tt_z0 - ls_t;                    // 38.5: bottom plate underside = deck pocket floor
ls_pocket = 1.0;                         // both plates sit 1 mm deep in square pockets (registers them)
deck_t = 5;                              // pedestal deck, pocket floor at ls_z0
deck_top = ls_z0 + ls_pocket;            // 39.5
deck_z0 = deck_top - deck_t;             // 34.5 = stepper mounting face
ped_r = 80;                              // pedestal tube outer radius
ped_wall = 2.4;
// 28BYJ-48 (generic): body 28 x 19, ears 35 apart (4.2 holes, 0.8 thick, 7 wide),
// shaft 8 mm off the body centre, boss 9 x 1.5, shaft 5 dia double-D 3.0 across
// flats, 10 mm above the mounting face (flats on the top 6). CHECK on arrival.
st_d = 28; st_h = 19; st_ear_span = 35; st_ear_hole = 4.2; st_ear_w = 7; st_ear_t = 0.8;
st_off = 8; st_boss_d = 9; st_boss_h = 1.5; st_shaft_d = 5; st_flat = 3.0; st_shaft_l = 10; st_flat_l = 6;
st_xy = [0, -st_off];                    // body centre (shaft on the axis, body toward -Y, ears along X)
hub_d = 14; hub_z0 = deck_z0 + st_boss_h + 0.5;   // separate printed hub, screwed under the turntable, to just over the boss
hub_fl_d = 32; hub_fl_t = 3;             // hub flange (inside the bearing's centre hole, clear of the ear screw heads)
// home switch: generic roller-lever microswitch (20 x 6.4 x 10.2, M2 holes 9.5 apart)
// lying flat on a bracket at az 180, its lever tripped by the end of a tab on the
// turntable at arm-local 180 deg. HOME = arm at az 0 (10 deg before the hopper).
home_az = 0;
flag_r1 = 92; flag_w = 12;               // tab end radius, tab width (turntable plate level, Z 46.4..51.4)
ms_l = 20; ms_w = 6.4; ms_h = 10.2; ms_hole_p = 9.5;
ms_r0 = 96;                              // switch body inner face radius (lever reaches in to the tab end)
ms_z0 = 44;                              // switch underside = bracket top (2.4 under the tab)

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
contact_r = 11.5;                        // M3 button-head contacts under the 608 ring, 3 points at 120 deg (clear of the bore)

// ---- camera tower ----
tower_xy    = [330, 60];                 // post centre, scan-station frame (off the ray: stays on a 2 ft board, clear of bin 1)
cam_dist    = 188;                       // lens -> bed: middle of the +5 D range on a 1.5 m-inf camera (176..200)
cam_lens_z  = bed_top + cam_dist;        // 217
ring_side   = 22;                        // WS2812 ring beside the post toward the station ray, off-axis: no foil hot spot
ring_z      = bed_top + 50;

// ---- board ----
board_x = 610; board_y = 610; board_t = 12;
board_y0 = -290;                         // board spans Y -290..320 (yaw axis at 0,0)
cable_post_xy = [0, -160];               // fixed post the tube/wire loop hangs from

// ---- helpers ----
module at_station(i, z = 0) translate([R * cos(st_angle(i)), R * sin(st_angle(i)), z]) rotate([0, 0, st_angle(i)]) children();
function H1z(th) = z_p1 + L * sin(th);
function cup_lip_z(th) = H1z(th) - hand_drop;
