// =============================================
// Riftbound Card Sorter — Conveyor Side Rail
// =============================================
// 4 prints: 2 rail lines (front -Y = motor side, back +Y = plain), each
// split into 2 × 125mm halves for the P1S bed. Halves join by tenon/mortise.
// Material: PLA, 0.2mm layers, 40% infill, 4 walls
//
// Local frame (as modelled): x = along the rail (belt travel), y = 0 on the
// INNER face, +y outward, z = 0 on the baseplate. In assembly.scad the back
// rail is placed as-is at Y = +45, the front rail mirrored in Y at Y = -45.
// Export the front halves with `part = "front1"/"front2"` (already mirrored).
//
// Drivetrain (see motor_mount.scad):
//   Two 8mm rods, one per roller: near shaft (half 1, x=25) and far shaft
//   (half 2, x=100). BOTH are driven — one N20 per rod, L9110S ch A/B
//   (hardware/conveyor.py). Both motors sit on the front (-Y) rail, so only
//   that rail's halves are printed with motor_mount = true.
//
// 608ZZ bearing housing (one per shaft station, 4 total):
//   boss Ø29 × 7.0 on the outer face, with a Ø22.15 × 7.0 press-fit pocket
//   OPEN TO THE OUTSIDE. The 3mm rail wall is the pocket floor = shoulder:
//   its through-hole is Ø15, i.e. bigger than the 608 inner-ring land
//   (≈Ø12.1, so the rotating inner ring never touches plastic) and smaller
//   than the outer-ring land (≈Ø19.5, so the outer ring is fully backed and
//   cannot be pushed through to the card side). The bearing sits flush with
//   the boss face; it is retained from outside by the motor-mount flange
//   (front) and by the rod collars (both sides, via the inner ring).
//
//   inner face │ 3.0 wall (shoulder, Ø15 hole) │ 7.0 pocket = 608ZZ │ boss face
//   y = 0                                  y = 3                     y = 10
// =============================================

/* [Export] */
part = "back1";   // back1 | back2 | front1 | front2

// Parameters
rail_len    = 125;    // half-length (split for P1S bed); total = 250mm
rail_h      = 35;
wall        = 3.0;
card_h      = 88;     // Riftbound card length (along X)

// Card-guide seat groove (top of the inner face). card_guide.scad hangs its
// groove fill in it (fill rests on the groove floor, local Z 32.5 = machine
// 96.5). The groove is 2.5 tall but only 1.8 deep into the 3 mm wall, so the
// fin left along the rail top is 1.2 mm thick (was 0.5 × 2.5 with a 2.5 deep
// groove: one perimeter, and the hood seat + clip jaws bear on it).
groove_depth = 2.5;          // vertical (Z) height of the groove
groove_y     = 1.8;          // horizontal depth into the wall → fin wall - groove_y = 1.2
assert(wall - groove_y >= 1.2 - 1e-6, "rail-top fin thinner than 1.2 mm");

// Roller shafts
shaft_y      = 15;    // rod axis height above the rail base
shaft_x1     = 25;    // near shaft (first half piece)
shaft_x2     = 100;   // far shaft (second half piece)

// 608ZZ: d 8 × D 22 × B 7. Inner-ring land ≈ Ø12.1, outer-ring land ≈ Ø19.5
brg_od       = 22.0;
brg_w        = 7.0;
pocket_d     = 22.15; // press fit in PLA/PETG; tune ±0.05 to your printer
pocket_depth = 7.0;   // = bearing width → bearing flush with boss face
pocket_chamf = 0.4;   // lead-in chamfer at the pocket mouth
shoulder_d   = 15.0;  // through-hole in the wall (shoulder ID)
boss_d       = 29.0;  // housing OD → 3.4mm radial wall around the pocket
boss_h       = pocket_depth;   // boss protrudes 7.0 past the 3mm wall

// Motor-mount fastening (front rail only). 2× M3 brass heat-set inserts per
// shaft in Ø9 pads, coplanar with the boss face (pads merge into the boss).
// Hole Ø4.1 for M3 inserts (Ruthex/CNC Kitchen M3×5.7 → Ø4.0, generic
// M3×5×4.5 → Ø4.2); blind, stops 1mm short of the inner (card) face.
// Insert centres sit 17.5mm from the shaft: hole edge r 15.45 is 0.95mm
// outside the Ø29 boss outline and leaves 4.4mm of plastic to the pocket.
mm_screw_dx     = 15.0;   // ± X from shaft centre
mm_screw_dz     = 9.0;    // + Z above shaft centre
mm_pad_d        = 9.0;
mm_insert_d     = 4.1;
mm_insert_depth = wall + boss_h - 1.0;   // 9.0mm blind, from pad face

// Riser-deck fastening — L-feet on the OUTER face, M3 through the foot into
// the riser (see FEET at the bottom for lengths). The tile M3 grid
// (baseplate_tile.scad, 30mm pitch) has a row at |Y| = 75 (and at 45, which
// is exactly the rail inner face, so unusable); feet reach out to it.
foot_t       = 4.0;          // foot plate thickness (Z)
foot_w       = 10.0;         // along X
foot_hole_y  = 75 - 45;      // 30: grid row |Y|=75 minus rail_in
foot_len     = foot_hole_y + 4;   // foot ends at |Y| = 79 (electronics tray at 80)
foot_hole_d  = 3.4;
foot_gusset  = 12.0;         // gusset legs (y and z), centre web 2.5 thick
// Foot positions in local x (machine X = local + -165 for half 1, + -40 for
// half 2), chosen on the 30mm grid and clear of: motor brackets (front, X
// -161..-119 and 39..81), camera-bracket foot (back, X -65..-15), collars.
//   front: X -80, -50 | -20, 10      back: X -120, -80 | 10, 40
function rail_feet_x(far, front) =
    front ? (far ? [20, 50] : [85, 115])
          : (far ? [50, 80] : [45, 85]);

// ── Shared geometry for other parts (motor_mount / slide_bed `use` these) ──
function rail_wall()            = wall;
function rail_boss_h()          = boss_h;
function rail_boss_d()          = boss_d;
function rail_boss_face_y()     = wall + boss_h;          // 10.0 from inner face
function rail_pocket_d()        = pocket_d;
function rail_shoulder_d()      = shoulder_d;
function rail_shaft_y()         = shaft_y;
function rail_shaft_x(far)      = far ? shaft_x2 : shaft_x1;
function rail_mm_screw_offsets() = [[-mm_screw_dx, mm_screw_dz],
                                    [ mm_screw_dx, mm_screw_dz]];
function rail_foot_hole_y()     = foot_hole_y;
function rail_groove()          = [groove_y, groove_depth];   // [depth into wall, height]

echo(str("RAIL: 608 pocket Ø", pocket_d, " × ", pocket_depth, ", boss Ø", boss_d,
         ", shoulder hole Ø", shoulder_d, "; insert hole edge r = ",
         norm([mm_screw_dx, mm_screw_dz]) - mm_insert_d / 2,
         " (boss r ", boss_d / 2, ", pocket r ", pocket_d / 2, ")"));
assert(norm([mm_screw_dx, mm_screw_dz]) - mm_insert_d / 2 > boss_d / 2,
       "insert hole breaks into the boss outline");
assert(shoulder_d > 12.5 && shoulder_d < 19, "shoulder must clear inner ring, back outer ring");
assert(shaft_y - boss_d / 2 >= 0, "boss below the baseplate");

// One bearing boss (+ optional motor-mount insert pads) at x = sx
module shaft_station_add(sx, motor_mount) {
    translate([sx, wall - 0.01, shaft_y])
        rotate([-90, 0, 0])
        cylinder(d = boss_d, h = boss_h + 0.01, $fn = 64);
    if (motor_mount)
        for (o = rail_mm_screw_offsets())
            translate([sx + o[0], wall - 0.01, shaft_y + o[1]])
                rotate([-90, 0, 0])
                cylinder(d = mm_pad_d, h = boss_h + 0.01, $fn = 32);
}

module shaft_station_cut(sx, motor_mount) {
    // Shoulder through-hole in the wall
    translate([sx, -0.1, shaft_y])
        rotate([-90, 0, 0])
        cylinder(d = shoulder_d, h = wall + 0.2, $fn = 48);
    // 608ZZ pocket, open to the outside
    translate([sx, wall, shaft_y])
        rotate([-90, 0, 0])
        cylinder(d = pocket_d, h = pocket_depth + 0.1, $fn = 96);
    // Lead-in chamfer at the mouth
    translate([sx, wall + boss_h - pocket_chamf, shaft_y])
        rotate([-90, 0, 0])
        cylinder(d1 = pocket_d, d2 = pocket_d + 2 * pocket_chamf + 0.2,
                 h = pocket_chamf + 0.1, $fn = 96);
    // M3 heat-set insert holes, blind from the pad face toward the inner face
    if (motor_mount)
        for (o = rail_mm_screw_offsets())
            translate([sx + o[0], wall + boss_h + 0.1, shaft_y + o[1]])
                rotate([90, 0, 0])
                cylinder(d = mm_insert_d, h = mm_insert_depth + 0.1, $fn = 24);
}

module rail_foot(fx) {
    translate([fx - foot_w / 2, wall - 0.01, 0])
        cube([foot_w, foot_len - wall + 0.01, foot_t]);
    // centre gusset web (stops short of the screw head)
    translate([fx - 1.25, wall - 0.01, foot_t - 0.01])
        rotate([90, 0, 90])
        linear_extrude(2.5)
        polygon([[0, 0], [foot_gusset, 0], [0, foot_gusset]]);
}

module rail_foot_cut(fx)
    translate([fx, foot_hole_y, -0.1])
        cylinder(d = foot_hole_d, h = foot_t + 0.2, $fn = 24);

// add_shaft_near defaults to !add_shaft_far: half 1 carries only the near
// shaft (x=25), half 2 only the far shaft (x=100).
// motor_mount = true → front-rail variant: insert pads + front foot layout.
module rail_half(add_shaft_far = false, add_shaft_near = undef, motor_mount = false,
                 feet = undef) {
    near  = is_undef(add_shaft_near) ? !add_shaft_far : add_shaft_near;
    feetx = is_undef(feet) ? rail_feet_x(add_shaft_far, motor_mount) : feet;
    difference() {
        union() {
            // Rail body
            cube([rail_len, wall, rail_h]);

            // 608ZZ housing(s) on the outer face
            if (near)          shaft_station_add(shaft_x1, motor_mount);
            if (add_shaft_far) shaft_station_add(shaft_x2, motor_mount);

            // Baseplate feet
            for (fx = feetx) rail_foot(fx);

            // Tenon protruding 5mm from right face, mates with next piece's mortise
            translate([rail_len, 0, rail_h / 2 - 6])
                cube([5, wall, 12]);
        }

        // Card guide groove (inner face, top)
        translate([-0.1, -0.1, rail_h - groove_depth])
            cube([rail_len + 0.2, groove_y + 0.1, groove_depth + 0.1]);

        if (near)          shaft_station_cut(shaft_x1, motor_mount);
        if (add_shaft_far) shaft_station_cut(shaft_x2, motor_mount);

        for (fx = feetx) rail_foot_cut(fx);

        // Mortise at left face (x=0), 0.2mm clearance all sides
        translate([-0.1, -0.2, rail_h / 2 - 6.2])
            cube([5.1, wall + 0.4, 12.4]);
    }
}

if (part == "back1")  rail_half(add_shaft_far = false);
if (part == "back2")  rail_half(add_shaft_far = true);
if (part == "front1") mirror([0, 1, 0]) rail_half(add_shaft_far = false, motor_mount = true);
if (part == "front2") mirror([0, 1, 0]) rail_half(add_shaft_far = true,  motor_mount = true);

// =============================================
// PRINT ORIENTATION: inner face on the bed (bosses and feet pointing up),
//   so each 608 pocket is a vertical blind hole open at the top.
//   front1/front2 are exported pre-mirrored — do NOT mirror in the slicer.
// SUPPORTS: none (foot holes Ø3.4 and insert holes Ø4.1 print horizontal)
// BEARINGS: press the 608ZZ in with a vise/flat block on the OUTER ring
//   only, until it seats on the shoulder (flush with the boss face).
// HEAT-SET INSERTS (front rail only): 4× M3, pressed in from the pad face
//   with a soldering iron at ~220°C, flush with the pad face.
// FEET: 8 total (4 per rail line). The rails stand on the riser deck
//   (riser.scad), not on the baseplate, so a foot screw either goes through
//   the whole riser or into a deck insert:
//   - through-feet front X −80, back X −120 / −80 / +10: clamp = foot 4 +
//     riser 60 + tile 4 + 6 mm backing board = 74 → M3 × 80 (or 85 mm M3
//     threaded rod) into the board's tee-nut (washer + nut under the board is
//     the fallback: 6 mm left for 0.5 washer + 2.4 nut + thread).
//   - insert feet front X −50, back X +40: M3 × 10 into the deck's M3 × 5.7
//     heat-set insert. Front X −20 / +10 also carry the camera bracket foot
//     (6 mm): M3 × 16 there (the insert has a 14 mm relief below).
// =============================================
