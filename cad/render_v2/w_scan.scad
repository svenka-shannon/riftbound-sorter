// v3 assembly video: scan-station parts (machine coordinates), step 6.
// openscad --backend=manifold -D 'part="v3_hood"' -o hood.stl w_scan.scad
include <../scanner_hood.scad>
include <hw_common.scad>
part = "v3_hood";
P = part;

// LED strips: the 0.8 mm recess bands in the two long walls (Z 100.9..110.9, X cx ± 44)
module led_strips() intersection() {
    difference() {
        hull() { slab_c(in_hx + led_d, rail_in + led_d, rail_top - 0.01); slab_c(top_in + led_d, top_in + led_d, roof_bot); }
        hull() { slab_c(in_hx - 0.01, rail_in - 0.01, rail_top - 0.02); slab_c(top_in - 0.01, top_in - 0.01, roof_bot + 0.01); }
    }
    translate([cx - led_hx, -100, zc + led_h[0]]) cube([2 * led_hx, 200, led_h[1] - led_h[0]]);
    union() for (s = [-1, 1]) translate([cx - 100, s > 0 ? 25 : -125, 0]) cube([200, 100, 300]);
}
cam_holes = [for (u = [2.0, 23.0]) for (v = [2.0, 14.5]) [u - 12.5, -(v - 14.4)]];
module cam_screws() for (h = cam_holes) at_screw([cx + h[0], h[1], zc + 106.98], [0, 0, 1]) shcs(10, d = 2, hd = 3.8, hh = 1.3);
module bracket_screws() for (x = [-20, 10]) at_screw([x, -75, 74], [0, 0, -1]) shcs(16);
module foam_ring() translate([cx, 0, roof_top]) difference() { cylinder(d = 21, h = 2.9, $fn = 40); translate([0, 0, -1]) cylinder(d = 8.5, h = 5, $fn = 32); }
// FPC connector on the PCB back (+Z) at the −Y edge, for a recognisable camera
module camera() {
    camera_ghost_placed();
    translate([cx - 8, -(23.862 - 14.4) - 0.5, zc + 106.98 + 1.12]) cube([16, 5.5, 3.2]);
}

if (P == "v3_guide_back") guide_back();
if (P == "v3_guide_front") guide_front();
if (P == "v3_clips") for (x = guide_clip_x()) { clip_back(x); mirror([0, 1, 0]) clip_back(x); }
if (P == "v3_hood") scanner_hood();
if (P == "v3_leds") led_strips();
if (P == "v3_cam_bracket") camera_bracket_placed();
if (P == "v3_camera") camera();
if (P == "v3_cam_screws") cam_screws();
if (P == "v3_bracket_screws") bracket_screws();
if (P == "v3_foam_ring") foam_ring();
