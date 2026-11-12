// Riftbound Card Sorter - per-material part exports for the v2 (Blender) assembly video.
// Uses the asm_* modules from ../assembly.scad (already at assembled positions, Nov 11
// redesign: riser, raised conveyor, hopper elevator, single-servo pick arm, scan station,
// cradle shuttle) and adds visual-only hardware (PCBs, standoffs, MDF board, screws) so
// each part can get its own material. Export: openscad -D 'part="rails"' -o rails.stl parts.scad
// Every part is posed at the machine's HOME pose (arm parked, hopper plate at the bottom
// with a full stack, shuttle at home/level).
// NOTE: several part files define the same helper names (mg996r, xz, d_bore); `use`
// resolves those to the LAST file, so only call unique module names here.
use <../assembly.scad>
use <../baseplate_tile.scad>
use <../riser.scad>
use <../scanner_hood.scad>
use <../card_guide.scad>
use <../camera_bracket.scad>
use <../hopper.scad>
use <../hopper_elevator.scad>
use <../suction_arm.scad>
use <../shuttle_geom.scad>
use <../shuttle.scad>
use <../lower_ramp.scad>
use <../reject_bin.scad>
part = "baseplate";
idx = 0;  // tile index for part="tile"
base_top = 4;
$fn = 48;

module screw_head(d = 5.5, h = 3) { cylinder(d = d, h = h); }
module pcb(x0, y0, w, d) translate([x0, y0, 0]) cube([w, d, 1.6]);

// electronics tray at world (-150, 80, base_top); floor 2.5 thick; standoffs 5 high
tray_o = [-150, 80, base_top + 2.5];
module boards_pi()  translate(tray_o + [0, 0, 5]) pcb(5, 5, 85, 56);
module boards_pca() translate(tray_o + [0, 0, 5]) pcb(94, 6, 37, 68);
module boards_hx()  translate(tray_o + [0, 0, 5]) pcb(145, 74, 30, 22);
module standoffs() translate(tray_o) {
    for (x = [10, 68]) for (y = [10, 33]) translate([x + 5, y + 5, 0]) cylinder(d = 5, h = 5, $fn = 6);
    for (x = [100, 125]) for (y = [10, 70]) translate([x, y, 0]) cylinder(d = 5, h = 5, $fn = 6);
    for (x = [150, 170]) for (y = [78, 92]) translate([x, y, 0]) cylinder(d = 5, h = 5, $fn = 6);
}
module chips() translate(tray_o + [0, 0, 6.6]) {
    translate([30, 20, 0]) cube([14, 14, 1.4]);          // Pi SoC
    translate([60, 35, 0]) cube([18, 8, 1]);              // Pi RAM
    translate([72, 10, 0]) cube([17, 14, 8]);             // USB block
    translate([72, 30, 0]) cube([17, 14, 13]);            // RJ45
    translate([106, 30, 0]) cube([10, 10, 1.4]);          // PCA9685 chip
    translate([96, 64, 0]) cube([33, 5, 9]);              // header row
    translate([155, 80, 0]) cube([7, 5, 1.4]);            // HX711 chip
}
// MDF backing board under the 3x3 tiles
module mdf() translate([-295, -280, -12]) cube([590, 560, 12]);

// ── hopper elevator (local parts at the machine origin), home: plate at the bottom ──
module hop() translate(hopper_machine_origin()) children();
module hopper_printed() hop() {
    hopper_body(); hopper_cap(); hopper_carriage(hopper_zp_min()); hopper_plate(hopper_zp_min());
    hopper_flag(hopper_phi_trip());
}
module hopper_steel() hop() { hw_rods(); hw_screw(); hw_coupler(); hw_nut(hopper_zp_min()); hw_bushings(hopper_zp_min()); }

// ── pick arm, parked (servo 90) ──
module arm_head_placed() translate([pick_arm_pivot()[0], 0, pick_arm_pivot()[1]]) head();
// servo + ground pins = the fixed group minus the printed tower and head
module arm_servo() difference() { pick_arm_fixed(); tower(); arm_head_placed(); }
module arm_moving() pick_arm_moving_theta(pick_arm_theta(pick_arm_servo_park()), false);
// 4 × M3 head → column bolts (positions = suction_arm.scad hd_bolts, heads on the head floor)
module arm_bolts() for (b = [[-5, -134], [5, -134], [-5, -126], [5, -126]])
    translate([pick_arm_pivot()[0] + b[0], b[1], pick_arm_pivot()[1] - 44]) screw_head(5.5, 3);

// ── cradle shuttle at home / level ──
sh_y = sg_target_y("home");
module sh_printed() { rbar_neg(); rbar_pos(); end_post_neg(); end_post_pos(); }
module sh_hw() difference() { shuttle_fixed(); sh_printed(); }      // rod, D-shaft, ch1 + ch2 servos
// servos: ch2 hangs at X 70..90, ch1 sits at Y < -168; rod and D-shaft are at X > 95, Y >= -168
module sh_servo_zone() union() {
    translate([-1000, -1000, -1000]) cube([1095, 2000, 2000]);
    translate([-1000, -1000, -1000]) cube([2000, 832, 2000]);
}
module sh_carriage() translate([0, sh_y, 0]) { carriage(); tilt_drive_posed("level"); }
module sh_cradle() translate([0, sh_y, 0]) tf_pose("level") { tilt_frame(); cradle(); }
module sh_loadcell() translate([0, sh_y, 0]) tf_pose("level") load_cell();

if (part == "baseplate") asm_baseplate();
if (part == "tile") translate([floor(idx / 3) * 190 - 285, (idx % 3) * 180 - 270, 0]) baseplate_tile();
if (part == "mdf") mdf();
// electronics
if (part == "etray") asm_electronics_tray();
if (part == "pcb_green") { boards_pi(); boards_hx(); }
if (part == "pcb_blue") boards_pca();
if (part == "standoffs") standoffs();
if (part == "chips") chips();
// riser
if (part == "riser") asm_riser();
// conveyor (on the riser deck)
if (part == "rails") asm_rails();
if (part == "bearings") asm_bearings();
if (part == "motor_mounts") asm_motor_mounts();
if (part == "motors") asm_motors();
if (part == "slidebed") asm_slide_bed();
if (part == "rollers") asm_rollers();
if (part == "rods") asm_rods();
if (part == "belts") asm_belts();
if (part == "collars") asm_collars();
// scan station
if (part == "guides") card_guides();
if (part == "hood") scanner_hood();
if (part == "cam_bracket") camera_bracket_placed();
if (part == "camera") camera_ghost_placed();
// hopper elevator
if (part == "hopper") hopper_printed();
if (part == "hopper_steel") hopper_steel();
if (part == "hopper_motor") hop() hw_motor();
if (part == "hopper_switches") hop() { hw_sw_bottom_body(); hw_sw_top_body(); hw_sw_bottom_roller(); hw_sw_top_roller(); }
if (part == "cards") hop() hw_cards(hopper_zp_min());
// pick arm
if (part == "arm_tower") tower();
if (part == "arm_head") arm_head_placed();
if (part == "arm_servo") arm_servo();
if (part == "arm") arm_moving();
if (part == "arm_bolts") arm_bolts();
// sorting tray
if (part == "sorttray") asm_sorting_tray();
// cradle shuttle, lower ramp, reject bin
if (part == "sh_frame") sh_printed();
if (part == "sh_steel") difference() { sh_hw(); sh_servo_zone(); }
if (part == "sh_servos") intersection() { sh_hw(); sh_servo_zone(); }
if (part == "sh_carriage") sh_carriage();
if (part == "sh_cradle") sh_cradle();
if (part == "loadcell") sh_loadcell();
if (part == "c2_drive") c2_posed(sh_y);
if (part == "ramp") asm_lower_ramp();
if (part == "reject") asm_reject_bin();
// wiring + vacuum (rough routing)
if (part == "pump") asm_pump();
if (part == "tube") asm_vac_tube();
if (part == "harness") asm_harness();
if (part == "ribbon") asm_ribbon();
