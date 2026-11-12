// =============================================
// Riftbound Card Sorter — Hopper elevator in MACHINE coordinates
// =============================================
// Wraps cad/hopper.scad (parts are modelled in a local frame whose axes match
// the machine frame; origin = cavity centre, Z 0 = hopper base underside).
// For assembly.scad:   use <hopper_elevator.scad>   then   asm_hopper_elevator();
//
// Placement (coordinator, 2026-11-11; see machine_frame.scad):
//   cavity centre        machine X = -215, Y = 0      (card 88 along X, 63 along Y)
//   hopper base          machine Z = frame_base_top() = 4 (stands on the baseplate)
//   pick height          machine Z = frame_card_z()   = 90.9 (pick_z 86.9 local)
//   +X outer wall        machine X = -166.5            (belt starts at -165)
//   drive tower          machine Y +36 .. +70, motor on top to Z 157.6
//   flag cheeks / switch machine X -263.5 .. -293.1 (overhangs the -285 baseplate edge by ~8)
// Nothing is above the cavity: the space over X -260.5..-169.5, Y -33..33 is clear
// from Z 94.4 (rim) upward, except the feeler flag (≤ Z ~101 at full lift, -X end,
// 39-55 mm from the cavity centre) — keep the suction-arm links off that corner.
// =============================================

use <machine_frame.scad>
use <hopper.scad>

hopper_cx = -215;   // cavity centre (not in machine_frame.scad yet)

/* [Preview] */
plate_z_in = -1;    // plate top, LOCAL Z (-1 = bottom of travel)

function hopper_machine_origin() = [hopper_cx, 0, frame_base_top()];

// plate_z: plate top in LOCAL Z (hopper_zp_min() .. hopper_zp_max()), -1 = bottom
module asm_hopper_elevator(plate_z = -1, flag_phi = -1, cards = true)
    translate(hopper_machine_origin())
        hopper_elevator_local(plate_z >= 0 ? plate_z : hopper_zp_min(), flag_phi, cards);

asm_hopper_elevator(plate_z_in);
