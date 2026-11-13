// =========================================================================
// Option B ("turntable picker"): shared geometry. Keep in sync with b_check.py.
//
// World frame: origin = yaw axis on the board top, Z up. The arm points at
// azimuth = servo angle s (deg, from +X, counter-clockwise). Stations sit on
// a circle of radius R at s = 10, 30, ..., 170: hopper, scan/weigh platform,
// bins 1-6, reject. Electronics and pump live behind the axis (-Y).
//
// Arm-local frame (used by the turntable, mast, links and hand): +X along the
// arm, +Y tangential (counter-clockwise), Z up. The cup axis is the plane Y=0;
// the parallelogram links run in the plane Y = 8..13.
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
hop_in_w  = 67; hop_in_l = 92;           // hopper: 2 mm room each side
bin_r_in  = R - 47; bin_r_out = R + 47;  // bin wedge, inside faces (radial)
half_wall = 1.2;                         // each bin's own radial wall

// ---- scan / weigh platform ----
bed_top   = 26;                         // cell 8..20.7, 2 mm boss, 3.3 bed
bed_w = 70; bed_l = 96; bed_t = 3.3;
cell_l = 75; cell_s = 12.7;              // owned 5 kg bar cell, 4 x M4
cell_hole_outer = 64; cell_hole_inner = 44;   // hole spacing (each end pair 10 apart)

// ---- MG996R (both servos) ----
sv_l = 40.7; sv_w = 19.7; sv_case_h = 37.0; sv_h = 42.9;   // bottom -> spline top
sv_tab_z0 = 26.8; sv_tab_t = 2.5; sv_tab_span = 54.0;
sv_hole_p = 49.5; sv_hole_dx = 10;
sv_shaft_off = 10.2;                     // spline centre from the case end
horn_d = 21; horn_t = 3; horn_gap = 1.4; // owned round disc horn is 21 mm

// ---- yaw stage ----
yaw_spline_z = 45;                       // spline top
yaw_sv_bot   = yaw_spline_z - sv_h;      // 2.1
tt_z0 = yaw_spline_z + horn_gap;         // turntable underside = horn front face (46.4)
tt_t  = 5;  tt_d = 104;
tt_top = tt_z0 + tt_t;                   // 51.4
roller_r = 42;                           // 608ZZ support rollers under the rim
roller_gap = 0.5;                        // rollers sit 0.5 below the plate: a sag stop

// ---- lift stage (parallelogram) ----
L      = 220;                            // link pivot-to-pivot
r_p1   = 25;                             // P1 = lift servo spline, radius from the yaw axis
z_p1   = 64;
d_link = 40;                             // P2 = P1 + [0, 0, d_link]
h_off  = 15;                             // hand: link pivots -> cup axis (radial)
link_y0 = 8; link_t = 5; link_hgt = 12;  // links in the plane Y = 8..13
lift_range = 6;                          // +/- deg of link swing

// ---- hand + slider ----
hand_drop   = 47;                        // H1 -> cup lip with the slider resting
cup_h = 23; cup_d = 28;                  // owned PATIKIL 27 mm bellows cup
slider_d = 10; slider_bore = 10.6;
slider_travel = 10;

// ---- camera tower ----
cam_r_tower = 345;                       // tower post centre radius
cam_lens_z  = bed_top + 150;             // 172
ring_r = R + 75; ring_z = bed_top + 50;  // WS2812 ring, off-axis (no foil hot spot)

// ---- board ----
board_x = 610; board_y = 610; board_t = 12;
board_y0 = -290;                         // board spans Y -290..320 (yaw axis at 0,0)

// ---- helpers ----
function polar(r, a) = [r * cos(a), r * sin(a)];
module at_station(i, z = 0) translate([R * cos(st_angle(i)), R * sin(st_angle(i)), z]) rotate([0, 0, st_angle(i)]) children();
// hand pose: link angle th (deg, + = up). Returns the lower hand pivot H1 in the arm frame.
function H1(th) = [r_p1 + L * cos(th), link_y0, z_p1 + L * sin(th)];
function cup_xy(th) = r_p1 + L * cos(th) + h_off;
function cup_lip_z(th) = z_p1 + L * sin(th) - hand_drop;
