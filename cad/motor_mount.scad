// =============================================
// Riftbound Card Sorter — N20 Motor Standoff Bracket
// =============================================
// Holds one N20 gear motor coaxial with an 8mm roller rod, on the OUTER
// side of the front (-Y) conveyor rail, joined by a 3mm→8mm shaft coupling.
// Print 2× — one per driven roller (both rollers are driven: L9110S ch A
// and ch B, hardware/conveyor.py).
//
// Drive train, outward from the rail (axis = Y below, 0 = boss face):
//   rail inner face │ 3mm wall/shoulder │ 608ZZ in Ø22.15×7 pocket │ y=0 boss face
//   │ FLANGE 0..4 (Ø18 hole) — race spacer 0..1, 8mm collar 1..9 inside it
//   │ gap │ COUPLING 10..35 (Ø19×25) │ gap │ FACE PLATE │ N20 → motor body
//
//   - The flange seats on the boss face + both insert pads and covers the
//     608 OUTER ring (Ø18..22 annulus; bearing is flush with the boss face),
//     so it retains the bearing outward. Its Ø18 hole clears the inner ring
//     (land Ø12.1, 2.95mm radial), the rod, the Ø11 race spacer and the
//     Ø16 shaft collar (1.0mm radial) — it never touches anything rotating.
//   - Race spacer (conveyor_roller.scad, 8.3/11 × 1) + 8mm collar ride on
//     the rod against the inner ring: with the matching collar on the back
//     rail they locate the rod axially. Tighten the collar BEFORE fitting
//     the bracket (its set screw is behind the flange afterwards).
//   - 8mm rod sticks out rod_protrusion (20) past the boss face and enters
//     the coupling's 8mm bore by cpl_rod_engage (10mm).
//   - N20 3mm D-shaft (10mm long) passes the face plate and enters the
//     coupling's 3mm bore by n20_engage (6.5mm, covers the set screw).
//   - The coupling bay is an open-top U-channel (side walls only up to the
//     shaft centreline) so both coupling set screws can be reached from above.
//
// Coupling: aluminium 3mm×8mm bore, D19 × L25, 2× M3 set screws
//   (e.g. https://kitsguru.com/products/19mm-outer-diameter-x-25mm-length-3mm-x-8mm-inner-diameter-rb-aluminium-flexible-shaft-coupling
//    — same D19L25 3×8 helical coupling is sold widely on Amazon/AliExpress).
// Collar: 8mm bore × Ø16 × 8 wide, M4 set screw (e.g. Climax GMC-08, RS PRO
//   122-3450, Stafford 34LM008). A Ø18 collar fits too (0mm margin — avoid).
//
// Frame (assembled): X = along rail (shaft at X=0), Y = 0 on the bearing
// boss face, +Y away from the rail, Z = 0 on the rail base / baseplate.
// Place onto a rail_half(): translate([shaft_x, rail_boss_face_y(), 0]).
//
// Material: PETG or PLA, 0.2mm, 4 walls, 40% infill
// =============================================

use <conveyor_rail.scad>
use <conveyor_roller.scad>

// --- From the rail / roller (single source of truth) ---
shaft_y      = rail_shaft_y();            // 15 — rod axis height
boss_d       = rail_boss_d();             // 29
pocket_d     = rail_pocket_d();           // 22.15
screw_offs   = rail_mm_screw_offsets();   // [[±15, +9]] rel. to shaft (17.5mm)
spacer_t     = race_spacer_t();           // 1.0

// --- 608ZZ ---
brg_inner_land_d = 12.1;   // inner-ring OD land (rotating)
brg_od           = 22.0;

// --- N20 micro gear motor ---
motor_w      = 10.0;   // body width  (X)
motor_h      = 12.0;   // body height (Z)
motor_l      = 20.0;   // gearbox + can length (Y)
n20_shaft_l  = 10.0;   // 3mm D-shaft length from gearbox face
n20_bush_d   =  5.0;   // clearance for the gearbox-face bushing
n20_hole_spc =  9.0;   // 2× M1.6 tapped holes in gearbox face, along the 12mm side (Z)
n20_hole_d   =  1.9;   // M1.6 clearance
n20_head_d   =  3.6;   // M1.6 pan head counterbore
n20_head_h   =  1.2;   // counterbore depth (keeps heads clear of the coupling)
motor_clr    =  0.2;   // pocket clearance per side (snug slide fit)

// --- Rod collar (8mm bore) ---
collar_od     = 16.0;
collar_w      =  8.0;

// --- Shaft coupling (3mm ↔ 8mm) ---
cpl_od        = 19.0;
cpl_len       = 25.0;
cpl_clr       =  1.5;  // radial clearance to bay walls / floor
cpl_rod_engage = 10.0; // 8mm rod depth into coupling (≤ half length)

// --- Bracket ---
flange_t     =  4.0;   // back flange, seats on boss face + insert pads
flange_hw    = 21.0;   // flange half-width (X)
flange_top   = 31.0;   // flange top Z: covers the Ø29 boss (top 29.5); rail top 35
flange_hole_d = 18.0;  // centre hole: collar Ø16 + 1mm, < 608 OD so the
                       //   flange still bears on the outer ring
gap_collar_cpl = 1.0;  // collar → coupling end
gap_cpl_face   = 1.0;  // coupling end → face plate
face_t       =  2.5;   // face plate the gearbox screws to
wall_t       =  3.0;   // bay side walls
floor_t      =  3.0;
sleeve_wall  =  2.5;
sleeve_len   = 18.0;   // covers 18 of the 20mm body; rear + tabs exposed
m3_clear_d   =  3.4;

// ---- Derived ---------------------------------------------------
collar_y0  = spacer_t;                            //  1.0
collar_y1  = collar_y0 + collar_w;                //  9.0
cpl_y0     = collar_y1 + gap_collar_cpl;          // 10.0 coupling start
cpl_y1     = cpl_y0 + cpl_len;                    // 35.0 coupling end
face_y0    = cpl_y1 + gap_cpl_face;               // 36.0
motor_y0   = face_y0 + face_t;                    // 38.5 gearbox face
sleeve_y1  = motor_y0 + sleeve_len;               // 56.5
motor_y1   = motor_y0 + motor_l;                  // 58.5 motor rear

bay_hw     = cpl_od / 2 + cpl_clr;                // 11.0 bay inner half-width
pocket_w   = motor_w + 2 * motor_clr;             // 10.4
pocket_h   = motor_h + 2 * motor_clr;             // 12.4
sleeve_hw  = pocket_w / 2 + sleeve_wall;          //  7.7
sleeve_top = shaft_y + pocket_h / 2 + sleeve_wall; // 23.7

rod_protrusion = cpl_y0 + cpl_rod_engage;         // 20.0 past boss face
n20_engage     = n20_shaft_l - face_t - gap_cpl_face; // 6.5 into coupling

function mm_rod_protrusion() = rod_protrusion;
function mm_collar_od()      = collar_od;
function mm_collar_w()       = collar_w;

echo(str("MOTOR MOUNT: rod protrusion past boss face = ", rod_protrusion,
         " mm; N20 shaft engagement = ", n20_engage,
         " mm; rod-end to N20-shaft-tip gap = ",
         (motor_y0 - n20_shaft_l) - rod_protrusion, " mm; overall depth = ",
         motor_y1, " mm; flange hole Ø", flange_hole_d,
         " (inner-ring radial clr ", (flange_hole_d - brg_inner_land_d) / 2,
         ", collar radial clr ", (flange_hole_d - collar_od) / 2, ")"));

assert(cpl_rod_engage <= cpl_len / 2, "rod would run past coupling centre");
assert(rod_protrusion < motor_y0 - n20_shaft_l, "rod end hits N20 shaft tip");
assert(n20_engage >= 5, "N20 shaft barely reaches the coupling set screw");
assert(shaft_y - cpl_od / 2 - cpl_clr >= floor_t, "coupling rubs the floor");
assert(flange_hole_d > collar_od + 1, "collar rubs the flange");
assert(flange_hole_d > brg_inner_land_d + 2, "flange too close to the 608 inner ring");
assert(flange_hole_d < brg_od - 2, "flange no longer covers the 608 outer ring");
assert(collar_od / 2 < bay_hw, "collar rubs the bay walls");
assert(flange_top >= shaft_y + boss_d / 2, "flange does not cover the boss");
for (o = screw_offs)
    assert(norm(o) >= 15, "mount screw inside 15mm of shaft centre");

// Flat-topped teardrop: prints the Ø18 horizontal hole without supports
module teardrop_y(d, h)
    rotate([-90, 0, 0]) linear_extrude(h)
        intersection() {
            union() {
                circle(d = d, $fn = 64);
                rotate(-135) square(d / 2);   // point → 2D -y → machine +Z
            }
            translate([-d, -d / 2]) square([2 * d, d]);   // flat cap at Z = +r
        }

module motor_mount() {
    difference() {
        union() {
            // Back flange — seats on boss face + both insert pads
            translate([-flange_hw, 0, 0])
                cube([2 * flange_hw, flange_t, flange_top]);

            // Coupling bay: floor + two side walls up to the shaft centreline
            // (open top = set-screw access window)
            translate([-bay_hw - wall_t, 0, 0])
                cube([2 * (bay_hw + wall_t), face_y0, floor_t]);
            for (s = [-1, 1])
                translate([s > 0 ? bay_hw : -bay_hw - wall_t, 0, 0])
                    cube([wall_t, face_y0, shaft_y]);

            // Face plate — N20 gearbox face screws to its back side
            translate([-bay_hw - wall_t, face_y0, 0])
                cube([2 * (bay_hw + wall_t), face_t, sleeve_top]);

            // Motor sleeve (solid down to the floor for a flat print base)
            translate([-sleeve_hw, motor_y0 - 0.01, 0])
                cube([2 * sleeve_hw, sleeve_len + 0.01, sleeve_top]);
        }

        // Flange centre hole (rod, 608 inner ring, spacer, collar, driver access)
        translate([0, -0.1, shaft_y]) teardrop_y(flange_hole_d, flange_t + 0.2);

        // M3 clearance holes → heat-set inserts in the rail pads
        for (o = screw_offs)
            translate([o[0], -0.1, shaft_y + o[1]])
                rotate([-90, 0, 0])
                cylinder(d = m3_clear_d, h = flange_t + 0.2, $fn = 24);

        // Face plate: gearbox bushing + 2× M1.6 screws with counterbores
        translate([0, face_y0 - 0.1, shaft_y])
            rotate([-90, 0, 0])
            cylinder(d = n20_bush_d, h = face_t + 0.2, $fn = 32);
        for (dz = [-n20_hole_spc / 2, n20_hole_spc / 2]) {
            translate([0, face_y0 - 0.1, shaft_y + dz])
                rotate([-90, 0, 0])
                cylinder(d = n20_hole_d, h = face_t + 0.2, $fn = 16);
            translate([0, face_y0 - 0.1, shaft_y + dz])
                rotate([-90, 0, 0])
                cylinder(d = n20_head_d, h = n20_head_h + 0.1, $fn = 24);
        }

        // Motor pocket — open at the rear for the motor tabs / wires
        translate([-pocket_w / 2, motor_y0, shaft_y - pocket_h / 2])
            cube([pocket_w, sleeve_len + 0.1, pocket_h]);
    }
}

// Reference solids (for assembly / collision checks, not printed)
module motor_mount_coupling()
    translate([0, cpl_y0, shaft_y]) rotate([-90, 0, 0])
        cylinder(d = cpl_od, h = cpl_len, $fn = 48);
module motor_mount_collar()     // collar + race spacer, outside the bearing
    translate([0, 0, shaft_y]) rotate([-90, 0, 0]) {
        race_spacer();
        translate([0, 0, collar_y0]) difference() {
            cylinder(d = collar_od, h = collar_w, $fn = 48);
            translate([0, 0, -0.1]) cylinder(d = 8, h = collar_w + 0.2, $fn = 32);
        }
    }
module motor_mount_n20()
    union() {
        translate([-motor_w / 2, motor_y0, shaft_y - motor_h / 2])
            cube([motor_w, motor_l, motor_h]);
        translate([0, motor_y0 - n20_shaft_l, shaft_y]) rotate([-90, 0, 0])
            cylinder(d = 3, h = n20_shaft_l, $fn = 16);
    }
module motor_mount_rod_stub()   // rod portion past the boss face
    translate([0, -0.01, shaft_y]) rotate([-90, 0, 0])
        cylinder(d = 8, h = rod_protrusion + 0.01, $fn = 32);

motor_mount();

// =============================================
// PRINT ORIENTATION: floor (Z=0) on the bed, as modelled
// SUPPORTS: none (flange hole is a flat-topped teardrop, 7.5mm bridge;
//           motor pocket roof is a short bridge)
// FASTENERS: 2× M3×10 BHCS → M3 heat-set inserts in the rail pads
//            2× M1.6×4 pan head → N20 gearbox-face tapped holes
// ASSEMBLY ORDER:
//   1. Slide N20 into the sleeve from the rear, screw its face to the
//      face plate (driver through the flange hole).
//   2. Push the coupling's 3mm bore onto the N20 shaft (set screw on the
//      D-flat), leave it loose.
//   3. Rod (150mm) through both bearings + roller, 20mm past the front boss
//      face. On each side slide on a race spacer + 8mm collar, push both
//      collars against the bearings (no end play) and tighten them.
//   4. Offer the bracket up (flange hole passes over the collar), slide the
//      coupling onto the rod, 2× M3×10 into the inserts, then tighten the
//      coupling's 8mm set screw from above onto the rod flat.
// =============================================
