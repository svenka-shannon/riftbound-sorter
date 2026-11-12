// =============================================
// Riftbound Card Sorter — Camera Bracket
// =============================================
// Hangs a Pi Camera Module 3 (standard, 66°×41° FOV) LENS-DOWN under a
// cantilever arm, 100 mm above the card face, its lens poking into the
// scanner hood's roof port. The bracket stands on the two FRONT (-Y) rail
// L-feet nearest the camera axis and shares their M3 screws.
//
// Shape (side profile in Y/Z, extruded along X):
//
//                gusset /|
//          arm =======/ |             ← PCB hangs under the arm tip on
//              [PCB]   |=|  ← CSI      4 standoffs, lens down
//               \lens/ | |    ribbon
//          ┌─hood roof─┐| |    slot     vertical plate, outside the front
//          │           │| |              (-Y) rail and its foot gussets
//   ===rail top===     │|_|\__
//                      ─────┘  ← foot on the 2 front rail L-feet (M3 shared)
//
// Material: PLA or PETG, 0.2 mm layers, 4 walls, 30–40 % infill
// =============================================
//
// COORDINATE FRAME (machine axes, as assembly.scad / machine_frame.scad):
//   X = card travel, Y = across belt (+Y = back / electronics side), Z = up.
//   ORIGIN = camera optical axis on the card face, i.e. machine
//   (frame_cam_x(), 0, frame_card_z()) = (5, 0, 90.9).
//   camera_bracket_placed() applies that translation.
//
// ---------------------------------------------
// CARD FACE / MOUNT HEIGHTS (machine Z, from machine_frame.scad)
//   baseplate top 4 → riser 60 → rail base (deck_z)          = 64
//   rail L-foot plate 4 mm thick → foot top                    = 68  ← bracket foot underside
//   roller axis deck_z + 15 = 79, belt top + 11.9 → card face  = 90.9
//   → foot underside local z = 68 − 90.9 = −22.9
//
// LENS HEIGHT (local z above the card face)
//   lens tip              z = lens_h                 = 100.00  (Pi Cam 3 min focus ~10 cm)
//   PCB front (lens side) z = lens_h + lens_proj     = 106.98  (RPi drawing: lens tip
//                                                       6.98 mm proud of the PCB)
//   PCB back              z = + pcb_t (1.12)         = 108.10
//   arm underside         z = + so_h (6)             = 114.10  (FPC connector 3.2 mm tall
//                                                       on the PCB back → 2.8 mm clear)
//   arm top               z = + arm_h (8)            = 122.10  (machine 213.0)
//   plate: foot underside → gusset top = 22.9 + 122.1 + 20 = 165 mm
//
// FIELD OF VIEW at 100 mm (Pi Cam 3 standard: 66° H × 41° V, apex at the lens tip)
//   along X: 2·100·tan(33°)   = 129.9 mm  vs card 88 → ±20.9 mm margin
//   along Y: 2·100·tan(20.5°) =  74.8 mm  vs card 63 → ±5.9 mm centred,
//            4.2 mm worst case with the card against a guide (±1.7 mm play).
//   (lens_h = 102 would give ≥ 5.0 mm worst case; kept at 100 per spec.)
//
// CARD ORIENTATION → PCB ORIENTATION
//   Cards travel along X with the 88 mm length along X, so the image's long
//   (66°) axis must lie along X. Per the RPi drawing the 66° axis is parallel
//   to the 25 mm PCB edge (FPC-connector edge, 21 mm hole spacing); the 41°
//   axis runs along the 23.862 mm PCB height (12.5 mm hole spacing).
//   ⇒ 21 mm hole spacing along X, 12.5 mm along Y, FPC edge facing −Y
//     (toward the plate and its ribbon slot). NOTE: this is the old bracket
//     turned 180° about Z, so set the camera transform to rotate 180°
//     (Picamera2: Transform(hflip=1, vflip=1)) if image orientation matters.
//
// PI CAMERA MODULE 3 (standard) — RPi mechanical drawing RP-008153-DS-1:
//   PCB 25 × 23.862 × 1.12 mm, 4× ø2.2 holes (ø4.75 pad keep-out).
//   Holes 2.0 mm from left/right edges → 21.0 mm apart.
//   Hole row A 2.0 mm from the edge AWAY from the FPC connector,
//   row B 14.5 mm from that edge → 12.5 mm apart (9.362 mm from FPC edge).
//   Lens centred left/right, 14.4 mm from the non-FPC edge.
//   FPC connector on the PCB back along the FPC edge: 19.61 × 5.71, ~3.2 tall.
//
//   PCB (u along the 25 mm edge, v from the non-FPC edge) → local:
//     X = u − 12.5,  Y = −(v − 14.4)   (lens at X = Y = 0, FPC edge at −Y)
//     holes  (−10.5, +12.4) (+10.5, +12.4)   row A, non-FPC side (+Y)
//            (−10.5,  −0.1) (+10.5,  −0.1)   row B, FPC side
//     PCB outline X −12.5..+12.5, Y −9.462..+14.4
// ---------------------------------------------

use <machine_frame.scad>
use <conveyor_rail.scad>

/* [Export] */
print_orient = false;  // true → lay on the −X face for slicing

// --- Frame ---
cam_x       = frame_cam_x();           // 5
card_z      = frame_card_z();          // 90.9
deck_z      = frame_deck_z();          // 64
rail_in     = frame_rail_in();         // 45
belt_x0     = frame_belt_x0();         // −165
rail_foot_t = 4;                       // conveyor_rail.scad foot_t
rail_wall   = rail_wall();             // 3
rail_gus    = 12;                      // conveyor_rail.scad foot_gusset (legs, mm)

// --- Optics / placement ---
lens_h      = 100;     // lens tip above card face
lens_proj   = 6.98;    // lens tip in front of PCB front face (RPi drawing)
pcb_t       = 1.12;    // PCB thickness

// --- Pi Cam 3 hole pattern (local XY, lens at origin) ---
cam_u       = [2.0, 23.0];               // hole u (along 25 mm edge)
cam_v       = [2.0, 14.5];               // hole v (from non-FPC edge)
lens_u      = 12.5;
lens_v      = 14.4;
pcb_w       = 25;
pcb_hgt     = 23.862;
m2_pilot    = 1.8;     // M2 self-tapping pilot (or tap M2)
so_od       = 4.4;     // standoff OD (fits inside ø4.75 pad keep-out)
so_h        = 6;       // standoff height: clears 3.2 mm FPC connector on PCB back

// --- Mount: the two front-rail L-feet either side of the camera axis ---
// Front rail feet (machine X): half 1 at belt_x0 + rail_feet_x(false, true),
// half 2 at belt_x0 + 125 + rail_feet_x(true, true) → −80, −50, −20, 10.
feet_all    = concat([for (f = rail_feet_x(false, true)) belt_x0 + f],
                     [for (f = rail_feet_x(true,  true)) belt_x0 + 125 + f]);
foot_lo     = max([for (f = feet_all) if (f <= cam_x) f]);   // −20 (for cam_x = 5)
foot_hi     = min([for (f = feet_all) if (f >  cam_x) f]);   // 10
hole_y      = -(rail_in + rail_foot_hole_y());               // −75
mount_d     = 3.4;     // M3 clearance (same as the rail feet)
mount_pts   = [[foot_lo - cam_x, hole_y], [foot_hi - cam_x, hole_y]];

// --- Structure (local Y/Z) ---
arm_h       = 8;       // arm thickness
arm_tip_pad = 2.1;     // arm runs past the outer standoff edge by this much
plate_t     = 7;       // vertical plate thickness (Y)
plate_y     = -(rail_in + rail_wall + rail_gus + 1);   // −61: inner face, 1 mm past
                                                        // the rail-foot gusset webs
foot_t      = 6;       // foot thickness (Z)
foot_y1     = hole_y - 4;                               // −79 (rail foot ends at |Y| 79)
gus_arm     = 20;      // gusset above arm/plate joint (legs, mm)
gus_foot_y  = 3;       // foot gusset legs (Y × Z) — stops 1.25 mm short of the
gus_foot_z  = 8;       //   M3 head (ø5.5 at Y −75)
bw_half     = 25;      // half-width of the bracket about the lens axis (X)
bx0         = min(-bw_half, mount_pts[0][0] - 6);
bx1         = max( bw_half, mount_pts[1][0] + 6);

// --- CSI ribbon exit slot (through plate, in line with the FPC edge) ---
csl_w       = 20;      // X  (15-pin FPC is 16 mm wide)
csl_z0      = 105;     // slot bottom  (connector spans z 108.1..111.3)
csl_z1      = 112;     // slot top     (2.1 mm below arm underside)

// --- Derived ---
pcb_front_z = lens_h + lens_proj;        // 106.98
pcb_back_z  = pcb_front_z + pcb_t;       // 108.10
arm_bot     = pcb_back_z + so_h;         // 114.10
arm_top     = arm_bot + arm_h;           // 122.10
foot_z0     = deck_z + rail_foot_t - card_z;   // −22.9
holes       = [for (u = cam_u) for (v = cam_v) [u - lens_u, -(v - lens_v)]];
arm_y1      = -(cam_v[0] - lens_v) + so_od / 2 + arm_tip_pad;   // +16.7

// ── Shared values for the hood / checks ──
function cam_lens_h()        = lens_h;
function cam_pcb_front_rel() = pcb_front_z;   // PCB front face above the card face
function cam_holes()         = holes;
function cam_mount_xy()      = [for (p = mount_pts) [p[0] + cam_x, p[1]]];  // machine

echo(str("CAMERA BRACKET: lens tip machine Z ", card_z + lens_h, ", PCB front ", card_z + pcb_front_z,
         ", arm top ", card_z + arm_top, "; foot on front rail feet X ", foot_lo, " & ", foot_hi,
         " (M3 at Y ", hole_y, ", Z ", deck_z + rail_foot_t, "); bracket X ", cam_x + bx0, "..", cam_x + bx1));
assert(arm_bot - pcb_back_z >= 3.2 + 2, "standoffs too short for the FPC connector");
assert(plate_y - plate_t - gus_foot_y > hole_y + 5.5 / 2, "foot gusset hits the M3 head");
// The foot must land on two real front-rail L-feet: one each side of the lens,
// both fully under the bracket (rail foot pads are 10 mm wide along X).
assert(!is_undef(foot_lo) && !is_undef(foot_hi), "no front rail foot on one side of cam_x");
assert(bx0 <= foot_lo - cam_x - 5 && bx1 >= foot_hi - cam_x + 5, "bracket foot does not cover both rail feet");
assert(foot_hi - foot_lo <= 60, "rail feet too far apart for a stiff foot");

// Side profile in (Y, Z); extruded along X.
module side_profile() {
    polygon([
        [plate_y,                         foot_z0],
        [foot_y1,                         foot_z0],
        [foot_y1,                         foot_z0 + foot_t],
        [plate_y - plate_t - gus_foot_y,  foot_z0 + foot_t],
        [plate_y - plate_t,               foot_z0 + foot_t + gus_foot_z],
        [plate_y - plate_t,               arm_top + gus_arm],
        [plate_y,                         arm_top + gus_arm],
        [plate_y + gus_arm,               arm_top],
        [arm_y1,                          arm_top],
        [arm_y1,                          arm_bot],
        [plate_y,                         arm_bot],
    ]);
}

// Standoff section: teardrop pointing −X (down when printed on the −X face),
// truncated at the ø4.75 pad radius so it never touches PCB parts.
module standoff_2d() {
    intersection() {
        hull() {
            circle(d = so_od, $fn = 32);
            translate([-so_od / 2 * sqrt(2), 0]) square(0.01, center = true);
        }
        translate([-4.75 / 2, -so_od]) square([so_od * 2, so_od * 2]);
    }
}

module camera_bracket() {
    difference() {
        union() {
            // Body: foot + plate + arm + gussets
            translate([bx0, 0, 0])
                rotate([90, 0, 90])
                    linear_extrude(bx1 - bx0) side_profile();

            // 4× standoffs hanging from arm underside
            for (h = holes)
                translate([h[0], h[1], pcb_back_z])
                    linear_extrude(so_h + 0.01) standoff_2d();
        }

        // M2 pilot holes through standoffs and arm
        for (h = holes)
            translate([h[0], h[1], pcb_back_z - 0.1])
                cylinder(d = m2_pilot, h = so_h + arm_h + 0.2, $fn = 16);

        // 2× M3 through the foot, coaxial with the rail-foot holes
        for (p = mount_pts)
            translate([p[0], p[1], foot_z0 - 0.1])
                cylinder(d = mount_d, h = foot_t + 0.2, $fn = 24);

        // CSI ribbon slot through plate, centred on the lens X
        translate([-csl_w / 2, plate_y - plate_t - 0.1, csl_z0])
            cube([csl_w, plate_t + 0.2, csl_z1 - csl_z0]);
    }
}

// Ghost of the camera PCB + lens for checking (local frame)
module camera_ghost() {
    translate([-lens_u, -(pcb_hgt - lens_v), pcb_front_z]) cube([pcb_w, pcb_hgt, pcb_t]);
    translate([0, 0, lens_h]) cylinder(d = 5.75, h = lens_proj, $fn = 32);
}

// Machine-coordinate placement (used by scanner_hood.scad asm_scan_station())
module camera_bracket_placed() translate([cam_x, 0, card_z]) camera_bracket();
module camera_ghost_placed()   translate([cam_x, 0, card_z]) camera_ghost();

if (print_orient)
    rotate([0, -90, 0]) translate([-bx0, 0, 0]) camera_bracket();  // −X face → bed (local +X → +Z)
else {
    camera_bracket();
    %camera_ghost();
}

// =============================================
// HARDWARE: 4× M2×10 self-tapping (or machine screw into a tapped hole),
//   heads on the lens side of the PCB (they stay ≥ 0.9 mm above the hood
//   roof); 2× M3 shared with the two front rail L-feet either side of cam_x,
//   i.e. machine (−20, −75) and (10, −75) for cam_x = 5: use screws 6 mm longer than the rail-foot screws.
// RIBBON: Pi Zero 2 W (22-pin 0.5 mm "mini") ↔ Cam 3 (15-pin 1 mm "standard"):
//   Raspberry Pi Camera Cable Standard–Mini 500 mm, part SC1130.
//   Route: through the plate slot, turn +X round the plate's downstream edge
//   (X ≈ cam_x + 25), drape over the hood's downstream shoulder, down behind
//   the back rail and over the electronics-tray wall to the Pi. Estimated
//   ≈ 420 mm with the Pi's camera connector facing +X (≈ 480 mm facing −X),
//   so mount the Pi with its CSI end toward +X.
// ASSEMBLY: fit the hood first. Connect the ribbon to the camera, feed it
//   through the plate slot, screw the PCB on lens-down, then lower the
//   bracket straight down (lens into the hood roof port) onto the rail feet.
// PRINT ORIENTATION: on its SIDE — the −X face (the flat face showing the
//   full L/Z profile) on the bed (print_orient = true exports it rotated).
//   Footprint ≈ 96 × 165 mm, 51 mm tall. Straight extrusion along print-Z
//   except the teardrop standoffs (≤ 45°, tip truncated), the self-bridging
//   ø1.8/ø3.4 horizontal holes and the 7 mm CSI slot bridge.
// SUPPORTS: none.
// =============================================
