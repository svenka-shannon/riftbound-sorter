// Option B assembly. -D yaw=<arm deg> -D th=<link deg> -D show_board=true
include <b_params.scad>
use <b_parts.scad>
part = "none";

yaw = 30;        // arm azimuth (deg)
th  = -4;        // link angle (+ up)
stack = 40;      // cards in the hopper
show_board = true;
holding = true;  // card on the cup

module card() color("Gold") translate([-card_l / 2, -card_w / 2, 0]) cube([card_l, card_w, card_t]);
module at_station_raw(i) rotate([0, 0, st_angle(i)]) children();

if (show_board) color("BurlyWood", 0.6) translate([-board_x / 2, board_y0, -board_t]) cube([board_x, board_y, board_t]);
color("Wheat") cable_post();

color("LightSteelBlue") at_station_raw(st_hopper) hopper();
at_station(st_hopper, floor_t) for (k = [0 : stack - 1]) translate([0, 0, k * card_t]) card();
for (i = [2 : n_st - 1]) color("LightSteelBlue") at_station_raw(i) bin();   // one colour: touching bins merge in the render
at_station_raw(st_scan) { color("DarkSeaGreen") cell_block(); cell_ref(); color("DarkSeaGreen") bed(); color("Wheat") tower_post(); color("Tan") boom(); color("Tan") lens_frame(); color("Tan") ring_holder(); }

color("DarkSeaGreen") pedestal(); color("MediumSeaGreen") deck();
stepper_ref(); switch_ref();
rotate([0, 0, yaw]) lazy_susan_ref();

rotate([0, 0, yaw]) {
    color("SteelBlue") turntable();
    color("White") collar(); color("White") trip();
    lift_servo_ref();
    color("Coral") translate([r_p1, 0, z_p1]) rotate([0, -th, 0]) translate([-r_p1, 0, -z_p1]) link_a();
    color("Coral") translate([r_p1, 0, z_p1 + d_link]) rotate([0, -th, 0]) translate([-r_p1, 0, -(z_p1 + d_link)]) link_b();
    translate([L * cos(th) - L, 0, L * sin(th)]) {
        color("SteelBlue") hand();
        color("White") slider(); color("White") cap(); ring608_ref(); tee_ref();
        cup_ref(cup_lip_z(0));
        if (holding) translate([R, 0, cup_lip_z(0) - card_t]) card();
    }
}
