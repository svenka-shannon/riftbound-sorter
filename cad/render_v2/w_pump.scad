// v3 assembly video: pump bracket, pump, vent-valve clip and valve (step 11, §14.6).
// openscad --backend=manifold -D 'part="v3_pb_base"' -o pb_base.stl w_pump.scad
include <../pump_bracket.scad>
include <hw_common.scad>
part = "v3_pb_base";
P = part;
module base_screws() for (h = holes) at_screw([h[0], h[1], bt + base_t]) shcs(20);
module cap_screws() for (s = [-1, 1]) at_screw([sad_x0 + sad_w / 2, pump_y + s * ear_y, pump_z + gap / 2 + ear_t]) shcs(10);
module clip_screws() for (h = vc_holes) at_screw([h[0], h[1], bt + vc_t]) shcs(20);
module valve_foam() translate([vv_x - 7, vv_y0 + 2, vc_floor]) cube([14, 16, vfoam]);
// 1N5819 across the pump terminals (rear end of the can)
module pump_diode() translate([can_x0 - 3, pump_y, pump_z]) rotate([90, 0, 0]) {
    cylinder(d = 2.7, h = 5.2, center = true, $fn = 16);
    for (s = [-1, 1]) translate([0, 0, s * 4.5]) cylinder(d = 0.8, h = 4, center = true, $fn = 8);
}

if (P == "v3_pb_base") bracket_base();
if (P == "v3_pb_basescr") base_screws();
if (P == "v3_pb_sleeve") bracket_sleeve();
if (P == "v3_pb_pad") bracket_pad();
if (P == "v3_pb_pump") hw_pump();
if (P == "v3_pb_cap") bracket_cap();
if (P == "v3_pb_capscr") cap_screws();
if (P == "v3_pb_diode") pump_diode();
if (P == "v3_pb_clip") valve_clip();
if (P == "v3_pb_clipscr") clip_screws();
if (P == "v3_pb_foam") valve_foam();
if (P == "v3_pb_valve") hw_valve();
if (P == "v3_pb_tee") hw_tee();
