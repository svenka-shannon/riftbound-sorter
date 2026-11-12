// =============================================
// Riftbound Card Sorter — Conveyor Slide Bed
// =============================================
// Print 1×. Sits between the rails, between the two rollers, INSIDE the
// four O-ring belt loops (upper span above it, return span below it).
// The belts carry the card; this bed is a flat datum under the top span:
//   - each belt runs in a 5mm channel, 0.6mm above the channel floor
//     (never touches in normal running; catches a sagging/pressed belt)
//   - lands between the channels are 1.0mm below the card plane, so a
//     bowed card can dip at most 1.0mm — flat zone for the scanner
//     (camera axis X = -40, hood X -77.5..-2.5).
// Belt sag without the bed is already < 0.25mm (see conveyor_roller.scad);
// the bed is cheap insurance against O-ring stress relaxation and cards
// being pressed down by the suction arm.
//
// Shape: inverted U — top plate + two side skirts standing on the
// baseplate just inside the rails (|Y| 41.5..44.5, outside every belt),
// plus 4 cross ribs that stop 6mm above the return span. Open at both
// ends, so the O-rings slip over it lengthwise.
// Captured, no screws: rails ±0.5mm in Y, rollers ±2mm in X, belts above.
//
// Frame: x = 0 at machine X = -127 (13mm past the near roller axis),
// y = 0 on the belt axis, z = 0 on the baseplate top (machine Z = 4).
// Place: translate([-127, 0, base_top]) slide_bed();
// Material: PLA/PETG, 0.2mm, 3 walls, 20% infill
// =============================================

use <conveyor_rail.scad>
use <conveyor_roller.scad>

roller_c      = 200;                      // roller centre distance
end_clr       = 13;                       // bed end → roller axis
bed_len       = roller_c - 2 * end_clr;   // 174
bed_hw        = 44.5;                     // rail inner faces at ±45

shaft_z       = rail_shaft_y();           // 15
belt_y        = roller_belt_y();          // [-25.5, -8.5, 8.5, 25.5]
belt_cs       = roller_belt_cs();         // 2.9 (stretched)
card_z        = shaft_z + roller_belt_top_r();          // 26.9 (machine 30.9)
belt_bot_z    = card_z - belt_cs;                       // 24.0
return_top_z  = shaft_z - roller_belt_pitch_r() + belt_cs / 2;  // 6.0

land_drop     = 1.0;    // lands below the card plane
chan_clr      = 0.6;    // channel floor below the belt
chan_w        = 5.0;
land_z        = card_z - land_drop;                     // 25.9
chan_floor_z  = belt_bot_z - chan_clr;                  // 23.4
plate_z0      = chan_floor_z - 1.9;                     // 21.5
skirt_t       = 3.0;
rib_t         = 2.4;
rib_z0        = return_top_z + 6;                       // 12.0
rib_x         = [20, 65, 110, 155];

function slide_bed_x0()     = -127;                     // machine X of local x = 0
function slide_bed_card_z() = card_z;

echo(str("SLIDE BED: ", bed_len, " × ", 2 * bed_hw, " × ", land_z,
         " mm; card plane z=", card_z, " (machine ", card_z + 4, "); land z=", land_z,
         "; channel floor z=", chan_floor_z, "; belt bottom z=", belt_bot_z,
         "; return-span top z=", return_top_z, "; rib bottom z=", rib_z0));
assert(rib_z0 - return_top_z >= 3, "ribs too close to the return span");

module slide_bed() {
    difference() {
        union() {
            // Top plate
            translate([0, -bed_hw, plate_z0]) cube([bed_len, 2 * bed_hw, land_z - plate_z0]);
            // Side skirts (outside all belts, inside the rails)
            for (s = [-1, 1])
                translate([0, s > 0 ? bed_hw - skirt_t : -bed_hw, 0])
                    cube([bed_len, skirt_t, plate_z0 + 1]);
            // Cross ribs (stiffness), clear of the return span
            for (x = rib_x)
                translate([x - rib_t / 2, -bed_hw, rib_z0]) cube([rib_t, 2 * bed_hw, plate_z0 - rib_z0 + 1]);
        }
        // Belt channels, open at both ends
        for (y = belt_y)
            translate([-0.1, y - chan_w / 2, chan_floor_z]) cube([bed_len + 0.2, chan_w, 10]);
        // Chamfer the plate's top edges at both ends so a card edge can't catch
        for (x = [0, bed_len])
            translate([x, 0, land_z]) rotate([90, 0, 0])
                linear_extrude(2 * bed_hw + 1, center = true)
                    polygon([[-1.5, 0.01], [1.5, 0.01], [0, -1.5]]);
    }
}

slide_bed();

// =============================================
// PRINT ORIENTATION: upside down (lands on the bed) — gives the flattest
//   top surface; skirts and ribs point up. Footprint 174 × 89mm.
// SUPPORTS: none
// INSTALL: lay the bed between the rails, loop the 4 O-rings lengthwise
//   around it (one per channel), put both rollers inside the loop ends,
//   lift them to the bearing height and push the rods through.
// =============================================
