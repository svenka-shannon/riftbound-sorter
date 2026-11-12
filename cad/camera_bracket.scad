// =============================================
// Riftbound Card Sorter — Camera Bracket
// =============================================
// Hangs a Pi Camera Module 3 (standard, 66°×41° FOV) LENS-DOWN under a
// cantilever arm, ~100 mm above the card on the conveyor, centred over the
// scanner hood (the camera looks down through the hood's top cutout).
//
// Shape (side profile, extruded along X):
//
//           gusset |\
//   arm  ==========| |          ← arm, PCB hangs under its tip on 4 standoffs
//     [PCB]        |=|  ← CSI ribbon slot through plate
//      \lens/      | |
//                  | |  ← vertical plate, outside the back (+Y) conveyor rail
//                  | |\
//                  |_|_\______  ← foot, 2× M3 into the baseplate M3 grid
//
// Material: PLA or PETG, 0.2 mm layers, 4 walls, 30–40 % infill
// =============================================
//
// COORDINATE FRAME (machine-aligned, same axes as assembly.scad):
//   X = card travel (hopper → sorting tray), Y = across belt (+Y = back /
//   electronics side), Z = up.
//   ORIGIN = camera optical axis on the card surface, i.e. machine
//   (cam_mx, cam_my, card_z) = (-40, 0, 30). Place in assembly with
//     translate([-40, 0, 30]) camera_bracket();
//
// ---------------------------------------------
// CARD SURFACE HEIGHT  (machine Z)
//   baseplate top           base_top        =  4   (baseplate_tile tile_h)
//   roller shaft centre     + shaft_y       = 19   (conveyor_rail shaft_y = 15)
//   roller top / belt face  + roller_dia/2  = 30   (conveyor_roller dia 22)
//   → card face  card_z = 30 (+ belt_t if a flat belt is run over the rollers)
//   Bracket foot sits on the baseplate top: foot underside = 4 − 30 = −26 local.
//
// LENS HEIGHT
//   lens tip              z = lens_h                 = 100.00  (≥ 10 cm min focus)
//   PCB front (lens side) z = lens_h + lens_proj     = 106.98  (lens tip is 6.98 mm
//                                                       proud of PCB, RPi drawing)
//   PCB back              z = + pcb_t (1.12)         = 108.10
//   standoff tips         z = PCB back               = 108.10
//   arm underside         z = + so_h (6)             = 114.10  (FPC connector is 3.2 mm
//                                                       tall on PCB back → 2.8 mm clear)
//   arm top               z = + arm_h (8)            = 122.10
//   → plate height foot-underside → arm top = 26 + 122.1 = 148.1 mm
//     (machine Z 4 → 152.1; gusset adds 20 mm above that)
//
// FIELD OF VIEW at 100 mm (Pi Cam 3 standard: 66° H × 41° V)
//   H: 2·100·tan(33°)   = 129.9 mm   → along X (card travel)
//   V: 2·100·tan(20.5°) =  74.8 mm   → along Y (across belt)
//
// CARD ORIENTATION → PCB ORIENTATION
//   Cards travel along +X with the 88 mm length ALONG X and the 63 mm width
//   across Y: the hopper's 91 mm inner depth (card_h + clearance) is rotated
//   onto machine X in assembly.scad (rotate 90°), and both the hopper exit
//   slot (66.5 mm) and the scanner-hood card slots (card_w = 63 + 3) span Y.
//   So the image's long (66°/130 mm) axis must lie along X.
//   Per the RPi drawing the 66° axis is parallel to the 25 mm PCB edge (the
//   FPC-connector edge and the 21 mm hole spacing); the 41° axis is along
//   the 23.862 mm PCB height (the 12.5 mm hole spacing).
//   ⇒ 21 mm hole spacing along X, 12.5 mm spacing along Y,
//     FPC connector edge facing +Y (toward the plate's ribbon slot and the
//     Pi on the electronics tray).
//   Coverage: 88 mm card in 129.9 mm (±21 mm margin on X),
//             63 mm card in  74.8 mm (±5.9 mm margin on Y).
//
// PI CAMERA MODULE 3 (standard) — official RPi mechanical drawing
// RP-008153-DS-1 (pip.raspberrypi.com, design files):
//   PCB 25 × 23.862 × 1.12 mm, 4× ø2.2 holes (ø4.75 pad keep-out).
//   Holes 2.0 mm from left/right edges → 21.0 mm apart.
//   Hole row A 2.0 mm from the edge AWAY from the FPC connector;
//   row B 14.5 mm from that edge → 12.5 mm apart (9.362 mm from FPC edge).
//   Lens centred left/right, 14.4 mm from the non-FPC edge (0.1 mm off row B).
//   FPC connector on PCB back along the FPC edge: 19.61 × 5.71, ~3.2 mm tall.
//
//   PCB-frame → local: X = u − 12.5,  Y = v − 14.4   (u along 25 mm edge,
//   v from non-FPC edge toward FPC edge), so the lens lands on X = Y = 0:
//     holes  (−10.5, −12.4) (+10.5, −12.4)   row A, non-FPC side (−Y)
//            (−10.5,  +0.1) (+10.5,  +0.1)   row B, FPC side
//     PCB outline X −12.5..+12.5, Y −14.4..+9.462 (FPC edge at +Y)
// ---------------------------------------------

// --- Optics / placement ---
lens_h      = 100;     // lens tip above card face
lens_proj   = 6.98;    // lens tip in front of PCB front face (RPi drawing)
pcb_t       = 1.12;    // PCB thickness
belt_t      = 0;       // flat-belt thickness if used (raises card face; set e.g. 1.5)
card_z      = 4 + 15 + 22 / 2 + belt_t;  // card face, machine Z (= 30)
base_top    = 4;       // baseplate top, machine Z

// --- Pi Cam 3 hole pattern (local XY, lens at origin) ---
cam_u       = [2.0, 23.0];               // hole u (along 25 mm edge)
cam_v       = [2.0, 14.5];               // hole v (from non-FPC edge)
lens_u      = 12.5;
lens_v      = 14.4;
pcb_w       = 25;
pcb_hgt     = 23.862;
m2_pilot    = 1.8;     // M2 self-tapping pilot (or tap M2); drill 2.3 + nut if preferred
so_od       = 4.4;     // standoff OD (fits inside ø4.75 pad keep-out)
so_h        = 6;       // standoff height: clears 3.2 mm FPC connector on PCB back

// --- Structure (local Y/Z) ---
bw          = 50;      // bracket width (X), whole profile is extruded over this
bx0         = -25;     // bracket X start  → machine X −65..−15
arm_h       = 8;       // arm thickness
arm_tip_pad = 2.1;     // arm runs past the outer standoff edge by this much
plate_t     = 8;       // vertical plate thickness (Y)
plate_y     = 57;      // plate inner face; back rail outer face is Y 48 and its
                       // 608 bearing bosses reach Y 55.2 (at machine X −15)
foot_t      = 6;       // foot thickness (Z)
foot_y1     = 79;      // foot end; electronics tray starts at machine Y 80
gus_arm     = 20;      // gusset above arm/plate joint (legs, mm)
gus_foot_y  = 6;       // foot gusset legs (Y × Z)
gus_foot_z  = 12;

// --- Frame attachment: 2× M3 down into the baseplate's M3 component grid ---
// baseplate_tile: ø3.4 holes every 30 mm from 15 mm inset; tiles placed at
// col·190 − 285 / row·180 − 270 → machine grid X … −80, −50, −20, 10 …
// and Y … 45, 75, 105 …  Use (−50, 75) and (−20, 75) → local (−10, 75), (20, 75).
mount_d     = 3.4;     // M3 clearance
mount_pts   = [[-10, 75], [20, 75]];

// --- CSI ribbon exit slot (through plate, in line with the FPC edge) ---
csl_w       = 20;      // X  (15-pin FPC is 16 mm wide)
csl_z0      = 105;     // slot bottom  (connector spans z 108.1..111.3)
csl_z1      = 112;     // slot top     (2.1 mm below arm underside)

// --- Derived ---
pcb_front_z = lens_h + lens_proj;        // 106.98
pcb_back_z  = pcb_front_z + pcb_t;       // 108.10
arm_bot     = pcb_back_z + so_h;         // 114.10
arm_top     = arm_bot + arm_h;           // 122.10
foot_z0     = base_top - card_z;         // −26
holes       = [for (u = cam_u) for (v = cam_v) [u - lens_u, v - lens_v]];
arm_y0      = (cam_v[0] - lens_v) - so_od / 2 - arm_tip_pad;   // −16.7

print_orient = false;  // true → lay on the −X face for slicing

// Side profile in (Y, Z); extruded along X.
module side_profile() {
    polygon([
        [plate_y,                      foot_z0],
        [foot_y1,                      foot_z0],
        [foot_y1,                      foot_z0 + foot_t],
        [plate_y + plate_t + gus_foot_y, foot_z0 + foot_t],
        [plate_y + plate_t,            foot_z0 + foot_t + gus_foot_z],
        [plate_y + plate_t,            arm_top + gus_arm],
        [plate_y,                      arm_top + gus_arm],
        [plate_y - gus_arm,            arm_top],
        [arm_y0,                       arm_top],
        [arm_y0,                       arm_bot],
        [plate_y,                      arm_bot],
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
                    linear_extrude(bw) side_profile();

            // 4× standoffs hanging from arm underside
            for (h = holes)
                translate([h[0], h[1], pcb_back_z])
                    linear_extrude(so_h + 0.01) standoff_2d();
        }

        // M2 pilot holes through standoffs and arm
        for (h = holes)
            translate([h[0], h[1], pcb_back_z - 0.1])
                cylinder(d = m2_pilot, h = so_h + arm_h + 0.2, $fn = 16);

        // 2× M3 baseplate holes through foot
        for (p = mount_pts)
            translate([p[0], p[1], foot_z0 - 0.1])
                cylinder(d = mount_d, h = foot_t + 0.2, $fn = 24);

        // CSI ribbon slot through plate, centred on the lens X
        translate([-csl_w / 2, plate_y - 0.1, csl_z0])
            cube([csl_w, plate_t + 0.2, csl_z1 - csl_z0]);
    }
}

// Ghost of the camera PCB + view cone for checking (not exported: % modifier)
module camera_ghost() {
    %translate([-lens_u, -lens_v, pcb_front_z])
        cube([pcb_w, pcb_hgt, pcb_t]);
    %translate([0, 0, lens_h])
        cylinder(d = 5.75, h = lens_proj);
}

if (print_orient)
    rotate([0, -90, 0]) translate([-bx0, 0, 0]) camera_bracket();  // −X face → bed (local +X → +Z)
else {
    camera_bracket();
    camera_ghost();
}

// =============================================
// HARDWARE: 4× M2×10 self-tapping (or machine screw into tapped hole), heads
//           on the lens side of the PCB; 2× M3×12 + nut/washer into the
//           baseplate grid holes at machine (−50, 75) and (−20, 75).
// ASSEMBLY: connect the ribbon to the camera, feed it through the plate slot
//           (FPC edge toward the plate), then screw the PCB on lens-down.
// PRINT ORIENTATION: on its SIDE — the −X face (the flat 50 mm-wide side
//   showing the full L/Z profile) on the bed, i.e. the profile lies flat and
//   the 50 mm width becomes print height (set print_orient = true to export
//   it pre-rotated). Footprint ≈ 96 × 168 mm, 50 mm tall.
//   Everything is a straight extrusion along print-Z except: standoffs
//   (teardrop, pointing down → ≤45° overhang, tip truncated to a 1.5 mm
//   flat), the ø1.8/ø3.4 horizontal holes (self-bridging), and the CSI slot
//   (7 mm bridge). Layers run across the bending plane → strongest choice.
// SUPPORTS: none.
// =============================================
