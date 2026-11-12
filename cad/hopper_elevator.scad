// =============================================
// Riftbound Card Sorter — Hopper elevator in MACHINE coordinates
// =============================================
// Wraps cad/hopper.scad (parts are modelled in a local frame whose axes match
// the machine frame; origin = cavity centre, Z 0 = hopper base underside).
// For assembly.scad:   use <hopper_elevator.scad>   then   asm_hopper_elevator();
//
// Placement (machine_frame.scad is the single source of truth):
//   cavity centre        X = frame_hopper_x() = -215, Y = 0 (card 88 along X, 63 along Y)
//   hopper base          Z = frame_base_top() = 4 (stands on the baseplate)
//   pick height          Z = frame_card_z()   = 90.9 (pick_z 86.9 local)
//   +X outer wall        X = -166.5            (belt starts at -165)
//   footprint            X -263.5 .. -166.5, Y -65.6 .. +74 (motor wire cover;
//                        tower back wall +70; flag cheeks / top switch on the
//                        -Y wall down to -65.6) — inside the baseplate
//                        (frame_base_x/y = ±285 / ±270), asserted below
//   heights              rim Z 94.4, tower cap Z 135.1, motor top Z 154.1
// Nothing is above the cavity: X -260.5..-169.5, Y -33..33 is clear from Z 94.4
// upward, except the feeler flag on the -Y wall at X -245 (≤ Z ~101 at full lift,
// within 8 mm of that wall) — keep the suction-arm links off that spot.
// =============================================

use <machine_frame.scad>
use <hopper.scad>

/* [Preview] */
plate_z_in = -1;    // plate top, LOCAL Z (-1 = bottom of travel)

function hopper_machine_origin() = [frame_hopper_x(), 0, frame_base_top()];

// footprint must stay on the baseplate
let(o = hopper_machine_origin(), b = hopper_outer(), bx = frame_base_x(), by = frame_base_y())
    assert(o[0] + b[0][0] >= bx[0] && o[0] + b[1][0] <= bx[1] &&
           o[1] + b[0][1] >= by[0] && o[1] + b[1][1] <= by[1],
           "hopper footprint leaves the baseplate");

// plate_z: plate top in LOCAL Z (hopper_zp_min() .. hopper_zp_max()), -1 = bottom
module asm_hopper_elevator(plate_z = -1, flag_phi = -1, cards = true)
    translate(hopper_machine_origin())
        hopper_elevator_local(plate_z >= 0 ? plate_z : hopper_zp_min(), flag_phi, cards);

asm_hopper_elevator(plate_z_in);
