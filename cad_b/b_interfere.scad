// Interference probe: intersection of the moving arm with every fixed part.
// -D yaw=.. -D th=.. -D with_cup=true|false. Empty result = no collision.
include <b_params.scad>
use <b_parts.scad>
part = "none";
yaw = 30; th = 10; with_cup = true;
module card() translate([-card_l / 2, -card_w / 2, 0]) cube([card_l, card_w, card_t]);
module fixed() {
    rotate([0, 0, st_angle(st_hopper)]) hopper();
    at_station(st_hopper, floor_t) translate([-card_l / 2, -card_w / 2, 0]) cube([card_l, card_w, 40 * card_t]);
    for (i = [2 : n_st - 1]) rotate([0, 0, st_angle(i)]) bin();
    rotate([0, 0, st_angle(st_scan)]) { cell_block(); bed(); tower_post(); boom(); ring_holder(); }
    yaw_base(); cable_post();
}
module arm() rotate([0, 0, yaw]) {
    turntable();
    translate([r_p1, 0, z_p1]) rotate([0, -th, 0]) translate([-r_p1, 0, -z_p1]) link_a();
    translate([r_p1, 0, z_p1 + d_link]) rotate([0, -th, 0]) translate([-r_p1, 0, -(z_p1 + d_link)]) link_b();
    translate([L * cos(th) - L, 0, L * sin(th)]) {
        hand();
        if (with_cup) { slider(); cap(); ring608_ref(); tee_ref(); cup_ref(cup_lip_z(0)); translate([R, 0, cup_lip_z(0) - card_t]) card(); }
    }
}
intersection() { fixed(); arm(); }
