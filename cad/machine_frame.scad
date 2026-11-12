// =============================================
// Riftbound Card Sorter — shared machine frame
// =============================================
// Single source of truth for the card path after the Nov 11 redesign
// (suction pick from a motor-raised hopper, raised transport line,
// cradle shuttle sorter). Machine coords as in assembly.scad:
//   X = card travel (hopper -> belt -> tray), Y = across belt (+Y = back,
//   electronics side), Z = up, Z=0 bottom of baseplate tiles.
// `use <machine_frame.scad>` does not import variables, so read these via
// the functions at the bottom.
// =============================================

base_top   = 4;      // top of baseplate tiles
riser_h    = 60;     // conveyor deck raised so cards can FALL into both tray floors
deck_z     = base_top + riser_h;          // rail base / hopper deck reference = 64

// Conveyor (geometry unchanged, just lifted by riser_h)
belt_x0    = -165;   // belt start
belt_x1    = 85;     // belt end
roller_x   = [-140, 60];
rail_in    = 45;     // |Y| of rail inner faces
shaft_z    = deck_z + 15;
card_z     = deck_z + 15 + 11.9;          // top of round belts = card face = 90.9
scan_flat  = [-127, 47];                  // slide-bed backed flat zone (X)

// Scanner
cam_x      = 5;      // lens axis; card centred here for capture (moved from -40 so the hood clears the arm drop zone at X -139..-51)

// Hopper (motor-raised floor keeps top card at card_z)
hopper_x   = -215;   // cavity centre X (Y = 0)

// Baseplate extents (3x3 tiles of 190x180)
base_x     = [-285, 285];
base_y     = [-270, 270];

// Pick & place hand-off
drop_x     = -95;    // card CENTRE when the suction arm releases it onto the belt
                     // (card spans -139..-51: on belts, clear of hopper wall)
drop_clear = 3;      // card underside this far above belt at release (low drop)

// Sorting tray (bottom on baseplate); owner of tray placement may move it in X
tray_floor_lower_z = base_top + 2.5;      // lower slot floor
tray_floor_upper_z = base_top + 65 + 3 + 2.5;  // = 74.5 upper slot floor

// Card
card_w = 63; card_l = 88; card_t = 0.33;  // RAW cards (owner confirmed 2026-11-11: no sleeves), ~1.75 g

// MG996R mounting-tab holes (all three servos: pick arm ch0, shuttle ch1 / ch2).
// ONE value for every mount: hole-centre pitch along the case (49.5, TowerPro
// MG996R drawing) × across it (10), symmetric about the case centre. Clones
// vary (48.5..50 seen); the servo's own tab holes are Ø4.5+ grommet holes, so
// an M3 / M2.5 still lands for ±0.7 mm. MEASURE YOUR SERVO; if it is further
// off, change it here and re-export the arm head and the shuttle end post / riser.
mg996r_hole_pitch = 49.5;
mg996r_hole_dx    = 10;

function frame_base_top()  = base_top;
function frame_riser_h()   = riser_h;
function frame_deck_z()    = deck_z;
function frame_belt_x0()   = belt_x0;
function frame_belt_x1()   = belt_x1;
function frame_roller_x()  = roller_x;
function frame_rail_in()   = rail_in;
function frame_card_z()    = card_z;
function frame_scan_flat() = scan_flat;
function frame_cam_x()     = cam_x;
function frame_hopper_x()  = hopper_x;
function frame_base_x()    = base_x;
function frame_base_y()    = base_y;
function frame_drop_x()    = drop_x;
function frame_drop_clear()= drop_clear;
function frame_tray_floor_lower_z() = tray_floor_lower_z;
function frame_tray_floor_upper_z() = tray_floor_upper_z;
function frame_mg996r_hole_pitch() = mg996r_hole_pitch;
function frame_mg996r_hole_dx()    = mg996r_hole_dx;
