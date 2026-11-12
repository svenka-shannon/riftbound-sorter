// =============================================
// Riftbound Card Sorter — Conveyor Roller / Round-Belt Pulley
// =============================================
// Print 2× (one per 8mm rod: near x=-140 + far x=+60, both driven).
// Drive: N20 → 3mm-to-8mm set-screw coupling (motor_mount.scad) → 8mm rod
//        → this roller (D-bore keyed to the rod flat + M3 grub screw).
// The rollers are the pulleys of a 4-strand ROUND-BELT conveyor: four
// 135 × 3mm NBR O-rings run in the grooves and carry the card across the
// 200mm span between the rollers (slide_bed.scad sits under the top span).
// Material: PLA/PETG, 4 perimeters, 60% infill
//
// Local frame: roller axis = +Z, z = 0 at the front (-Y, motor-side) end.
// In assembly.scad: translate([x, -roller_w/2, 19]) rotate([-90,0,0]),
// so machine Y = z - 44.
// =============================================
//
// ── ROUND BELT (O-ring) MATH ────────────────────────────────────────────
//   Belt: NBR 70A O-ring, ID 135 × CS 3.0 (OD 141), 4 per machine.
//   Free centreline length  = π·(ID + CS) = π·138       = 433.5 mm
//   Stretched CS ≈ 3/√1.074 = 2.89 → cord centre rests at r = 10.45
//   Pitch dia Dp            = 2·10.45                    = 20.9 mm
//   Belt path (open, equal pulleys, C = 200) = 2C + π·Dp = 465.6 mm
//   Stretch                 = 465.6 / 433.5 − 1          = 7.4 %
//   Static tension ≈ E·ε·A ≈ 6 MPa·0.074·6.6 mm² ≈ 2.9 N per strand
//   Sag at mid-span: self weight (8.5 g/m) 0.14 mm + 1.8 g card 0.08 mm
//   → < 0.25 mm, irrelevant optically; slide bed added for robustness.
//   Belt top (card face) r = 10.45 + 1.45 = 11.9 → 0.9 mm above the
//   roller body, so the card only ever touches the belts.
// ────────────────────────────────────────────────────────────────────────

roller_dia  = 22;
roller_w    = 88;    // 90mm rail gap − 2 × 1.0mm running clearance
shaft_bore  = 8.2;   // clearance for 8mm steel rod (ream with 8mm bit)

// Round-belt grooves: U-groove, R1.6 bottom, straight walls to the OD
belt_cs      = 3.0;                 // O-ring cross-section (free)
belt_y       = [-25.5, -8.5, 8.5, 25.5];   // strand centres, machine Y (17mm pitch)
groove_r     = 1.6;                 // bottom radius (free cord r 1.5 + 0.1)
groove_c     = 10.6;                // groove-circle centre radius → bottom at r 9.0
belt_pitch_r = 10.45;               // stretched cord centre radius (see math)
belt_top_r   = 11.9;                // card face radius

rod_dia      = 8;
motor_flat_w = 4;    // width of the flat ground along the 8mm rod
flat_clr     = 0.15; // radial clearance roller flat → rod flat
// distance from axis to the roller's flat face (3.61mm for a 4mm-wide flat)
flat_off     = sqrt(pow(rod_dia / 2, 2) - pow(motor_flat_w / 2, 2)) + flat_clr;

// Axial location: M3 heat-set insert (radial, mid-roller, on the flat side)
// + M3 × 6 cup-point grub screw onto the rod flat. Keeps the roller centred
// with 1.0mm to each rail inner face. (Rod itself is located by the two
// collars outside the bearings — see motor_mount.scad.)
grub_z       = roller_w / 2;   // between the two inner belts (±8.5)
grub_insert_d = 4.0;
grub_insert_l = 6.0;           // from the surface inward (insert 5.7 long)
grub_d       = 3.2;            // through to the flat

// 608 inner-race spacer: sits between each bearing's inner ring and the
// rod collar so the collar can never touch the (stationary) ZZ shield.
spacer_id    = 8.3;
spacer_od    = 11.0;           // < 608 inner-ring land Ø12.1
spacer_t     = 1.0;

function roller_width()        = roller_w;
function roller_belt_y()       = belt_y;
function roller_belt_pitch_r() = belt_pitch_r;
function roller_belt_top_r()   = belt_top_r;
function roller_belt_cs()      = 2 * (belt_top_r - belt_pitch_r);  // stretched CS 2.9
function race_spacer_t()       = spacer_t;

// D-shaped bore: round bore minus the key (material left on the flat side)
module d_bore(h)
    difference() {
        cylinder(d = shaft_bore, h = h, $fn = 48);
        translate([-shaft_bore, flat_off, -1])
            cube([2 * shaft_bore, shaft_bore, h + 2]);
    }

module roller() {
    difference() {
        cylinder(d = roller_dia, h = roller_w, $fn = 96);

        // D-bore keyed to the rod flat (flat face at +y = flat_off)
        translate([0, 0, -0.1]) d_bore(roller_w + 0.2);

        // Round-belt grooves (U profile: R1.6 circle + straight walls)
        for (y = belt_y)
            translate([0, 0, y + roller_w / 2])
                rotate_extrude($fn = 96) {
                    translate([groove_c, 0]) circle(r = groove_r, $fn = 32);
                    translate([groove_c, -groove_r]) square([roller_dia, 2 * groove_r]);
                }

        // Grub-screw insert hole (radial, through the flat side) + screw hole
        translate([0, roller_dia / 2 + 0.1, grub_z]) rotate([90, 0, 0]) {
            cylinder(d = grub_insert_d, h = grub_insert_l + 0.1, $fn = 24);
            cylinder(d = grub_d, h = roller_dia / 2, $fn = 24);
        }
    }
}

module race_spacer()
    difference() {
        cylinder(d = spacer_od, h = spacer_t, $fn = 48);
        translate([0, 0, -0.1]) cylinder(d = spacer_id, h = spacer_t + 0.2, $fn = 32);
    }

// Reference solid: one stretched O-ring strand (round cord) running over
// two pulleys c apart, in the XZ plane (x along travel, z up, y = 0 on the
// strand), pulley axes along Y at x = 0 and x = c.
module belt_strand(c = 200) {
    cr = roller_belt_cs() / 2;
    // full torus in each groove (the inner half coincides with the groove,
    // so it adds no false contact; bed ends are 13mm from the axes)
    for (x = [0, c])
        translate([x, 0, 0]) rotate([90, 0, 0])
            rotate_extrude($fn = 64)
                translate([belt_pitch_r, 0]) circle(r = cr, $fn = 24);
    for (z = [-belt_pitch_r, belt_pitch_r])
        translate([0, 0, z]) rotate([0, 90, 0])
            cylinder(r = cr, h = c, $fn = 24);
}

roller();
// translate([20, 0, 0]) race_spacer();   // print 4

// =============================================
// PRINT ORIENTATION: axis vertical (on end); spacer flat
// SUPPORTS: none (groove tops are ≤0.5mm curved overhangs; Ø4 radial hole bridges)
// POST-PROCESS: ream bore with an 8mm drill bit (keep the flat),
//   heat-set one M3 insert into the radial hole, flush with the surface.
// ROD: full-length flat, ~0.5mm deep / 4mm wide (or buy 8mm D-shaft) —
//   keys this roller and seats the coupling set screw.
// ASSEMBLY: slide roller on, centre it (1.0mm gap to each rail face),
//   tighten the M3 × 6 grub onto the flat. Fit 4 O-rings across both
//   rollers before the second rod goes in (or roll them on over the end).
// =============================================
