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
// Round 5 (2026-11-14): yaw axis is a NEMA 17 pancake stepper on a lazy-susan bearing.
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

// ---- yaw stage (round 5, 2026-11-14): NEMA 17 pancake stepper + 4" lazy-susan bearing ----
// The turntable rides on a 4" square lazy-susan bearing (carries the arm's
// weight and tipping moment). A NEMA 17 pancake stepper (no gearbox, so no
// backlash; TMC2209, 1/16 microsteps = 0.1125 deg) hangs under a separate
// printed deck, shaft up on the yaw axis, and turns the turntable through a
// set-screw hub. Round 4's 28BYJ-48 was dropped: 1-3 deg gearbox backlash.
tt_z0 = 46.4;                            // turntable underside (unchanged: arm geometry identical)
tt_t  = 5;  tt_d = 104;
tt_top = tt_z0 + tt_t;                   // 51.4
ls_sq = 102; ls_t = 7.9;                 // 4" square lazy susan, 5/16" thick
ls_hole = 55;                            // centre hole (2.16")
ls_pitch_bot = 80.8;                     // bottom plate holes, square pitch (3.18"): MEASURE before printing the deck
ls_pitch_top = 88.9;                     // top plate holes (3.5" per one seller): MEASURE before printing the turntable
ls_z0 = tt_z0 - ls_t;                    // 38.5: bottom plate underside = deck pocket floor
ls_pocket = 1.0;                         // bottom plate sits 1 mm deep in a square pocket in the deck
deck_t = 5;                              // deck (separate part), pocket floor at ls_z0
deck_top = ls_z0 + ls_pocket;            // 39.5
deck_z0 = deck_top - deck_t;             // 34.5 = motor mounting face = pedestal tube top
deck_r = 80;
ped_r = 80; ped_wall = 2.4;              // pedestal tube (separate part), Z 0 .. deck_z0
deck_screw_r = 72;                       // 4 x M3 x 10 deck -> tube bosses, at 0/90/180/270 (outside the bearing's square)
// NEMA 17 pancake (STEPPERONLINE 17HS08-1004S class): 42.3 square x 23, boss 22 x 2,
// M3 holes on a 31 mm square, shaft 5 mm with a D flat, ~24 mm above the face. CHECK on arrival.
nm_sq = 42.3; nm_h = 23; nm_boss_d = 22; nm_boss_h = 2; nm_hole = 31;
nm_shaft_d = 5; nm_shaft_l = 24; nm_flat_l = 15;   // listings say 20-24 mm; the collar works with either
// drive collar on TOP of the turntable (always reachable): Ø16 x 8, M3 x 6 set screw onto the
// shaft's flat (+Y side, clear of the mast wall), 2 x M3 x 10 down into the turntable through Ø4 float holes.
col_d = 16; col_h = 8; col_sink = 3;                    // collar sits 3 mm down in a recess in the turntable top
col_z0 = tt_top - col_sink;                              // 48.4
col_ss_z = col_z0 + 3.5;                                 // set screw Z 51.9: works for a 20 or a 24 mm shaft
col_ears = [[-11, 0], [0, 11]];
// home switch: KW12-3 roller lever (20 x 10.5 x 6.5) lying flat in a press-fit cradle at az 270
// (behind the axis: the arm works at 0..170 and its links would hit anything at 170..190);
// an adjustable trip block on a turntable tab at local 270 deg presses its roller. HOME = arm at az 0.
sw_az = 270;
tab_w = 20; tab_r1 = 92;                 // turntable tab
trip_r_nom = 96;                         // trip block nose radius (radial slot: 91..99)
ms_l = 20; ms_w = 10.5; ms_h = 6.5;      // body length (tangential), depth (radial), thickness (Z)
ms_r0 = 99;                              // switch inner (lever) face radius
ms_z0 = 51;                              // switch underside: roller ~Z 54, centred on the trip block (Z 51.4..57.4)

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
