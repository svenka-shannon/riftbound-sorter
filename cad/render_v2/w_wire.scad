// v3 assembly video: wiring and vacuum-line runs (step 11). Rough routing, as in
// assembly.scad asm_harness() / asm_vac_hose() / asm_ribbon() / asm_cell_lead(),
// split so each run can be shown on its own.
// openscad --backend=manifold -D 'part="v3_harness"' -o harness.stl w_wire.scad
use <../assembly.scad>
use <../pump_bracket.scad>
use <../suction_arm.scad>
include <hw_common.scad>
part = "v3_harness";
P = part;
ax = pick_arm_pivot()[0]; az = pick_arm_pivot()[1];
roller_x = [-140, 60];

module harness_main() {
    chain([[66, -117.5, 52], [60, -117.5, 45], [-277, -117.5, 45], [-277, -117.5, 12],
           [-277, 135, 12], [-160, 135, 12]], 7);
    for (y = [105, 135, 165]) chain([[-160, 135, 12], [-160, y, 43.5], [-145, y, 43.5]], 5);
    for (x = roller_x) chain([[x, -116, 66], [x, -117.5, 45]], 5);                       // N20 drops
    chain([[ax, -108, 99], [ax, -117.5, 99], [ax, -117.5, 45]], 5);                      // arm servo lead
    chain([[-215, 80, 150], [-215, 82, 12], [-277, 82, 12]], 5);                         // hopper motor + switches
}
module leads_12v() {
    let(v = vent_valve_leads())
        chain([[v[0], v[1] - 2.5, v[2]], [v[0], v[1] - 2.5, 12], [-280, v[1] - 2.5, 12],
               [-280, -117.5, 12], [-277, -117.5, 12]], 4);
    let(pr = pump_rear()) chain([[pr[0] - 2.5, pr[1], pr[2]], [-280, pr[1], pr[2]], [-280, pr[1], 12]], 4);
}
// vacuum tube, pump side: nozzle → tee → along Y −205 → to the foot of the arm column
module tube_pump() chain([pump_nozzle_tip(), vent_tee_pos(), [ax + 8, -205, 28], [ax + 8, -205, 18], [ax + 8, -160, 18]], 4);
module tube_branch() chain([vent_tee_pos() + [0, -5, 0], vent_valve_root()], 4);

if (P == "v3_harness") harness_main();
if (P == "v3_leads12") leads_12v();
if (P == "v3_ribbon") asm_ribbon();
if (P == "v3_cell_lead") asm_cell_lead(0);
if (P == "v3_tube_pump") tube_pump();
if (P == "v3_tube_branch") tube_branch();
