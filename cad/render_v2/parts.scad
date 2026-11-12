// Riftbound Card Sorter - per-material part exports for the v2 (Blender) assembly video.
// Uses the asm_* modules from ../assembly.scad (already at assembled positions, Nov 11
// redesign: riser, raised conveyor, hopper elevator, single-servo pick arm, scan station,
// cradle shuttle) and adds visual-only hardware (PCBs, standoffs, MDF board, screws) so
// each part can get its own material. Export: openscad -D 'part="rails"' -o rails.stl parts.scad
// Every part is posed at the machine's HOME pose (arm parked, hopper plate at the bottom
// with a full stack, shuttle at home/level).
// Vacuum / wiring parts: pump (R385 solid), pump_bracket (base + cap + sleeve + head pad +
// vent-valve clip), valve (12 V NC vent valve), tee (barbed tee), tube (hose runs only),
// harness, ribbon, cell_lead (load-cell trailing loop at the home pose).
// NOTE: several part files define the same helper names (mg996r, xz, …); `use`
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
use <../pump_bracket.scad>
part = "baseplate";
idx = 0;  // tile index for part="tile"
base_top = 4;
$fn = 48;

module screw_head(d = 5.5, h = 3) { cylinder(d = d, h = h); }
module pcb(x0, y0, w, d) translate([x0, y0, 0]) cube([w, d, 1.6]);

// Electronics tray at world (-150, 80, base_top), floor 2.5. Board layout =
// electronics_tray.scad (tray-local x = machine X + 150, y = machine Y - 80;
// keep in sync): the posts / blocks / pockets are printed with the tray, so
// "standoffs" is now the brass-coloured board screws on top of them.
tray_o = [-150, 80, base_top + 2.5];     // floor top
post_h = 5; pol_h = 4; foam = 1;
//          [x0, y0], [w, d], height above the floor top
b_pi  = [[107, 5],    [65, 30],       post_h];   // Pi Zero 2 W, CSI end to +X
b_pca = [[108, 44],   [62.23, 25.4],  post_h];   // PCA9685 (blue)
b_rly = [[5, 42],     [50, 38.5],     post_h];   // 2-ch relay (blue)
b_uln = [[62, 42],    [35, 32],       post_h];   // ULN2003
b_hx  = [[62.3, 82.3],[34, 21],       foam];     // HX711 (pocket, foam tape)
b_l91 = [[38.3, 5.3], [29, 23],       foam];     // L9110S (pocket, foam tape)
b_d22 = [[40, 125],   [17.8, 17.8],   pol_h];    // Pololu D24V22F5
b_d50 = [[62, 125],   [17.8, 20.3],   pol_h];    // Pololu D24V50F5
b_d36 = [[104, 125],  [17.8, 20.3],   pol_h];    // Pololu D36V28F5
module board(b) translate(tray_o + [b[0][0], b[0][1], b[2]]) cube([b[1][0], b[1][1], 1.6]);
module boards_green() for (b = [b_pi, b_uln, b_hx, b_l91, b_d22, b_d50, b_d36]) board(b);
module boards_blue()  for (b = [b_pca, b_rly]) board(b);
// board screws (heads on the PCB top at the tray's post / block positions)
module board_screws() {
    hs = [for (h = [[3.5, 3.5], [61.5, 3.5], [3.5, 26.5], [61.5, 26.5]]) [b_pi, h],
          for (x = [3.175, 59.055], y = [3.175, 22.225]) [b_pca, [x, y]],
          for (x = [-1, 1], y = [-1, 1]) [b_rly, [25 + x * 22.15, 19.25 + y * 16.4]],
          for (x = [-1, 1], y = [-1, 1]) [b_uln, [17.5 + x * 15, 16 + y * 13.25]],
          for (h = [[2.3, 15.5], [15.5, 2.3]]) [b_d22, h],
          for (h = [[2.2, 2.2], [15.7, 18.2]]) [b_d50, h],
          for (h = [[2.2, 2.2], [15.7, 18.2]]) [b_d36, h]];
    for (e = hs) let(b = e[0], h = e[1])
        translate(tray_o + [b[0][0] + h[0], b[0][1] + h[1], b[2] + 1.6]) cylinder(d = 4.2, h = 1.8, $fn = 12);
}
module chips() {
    at = function(b, x, y) tray_o + [b[0][0] + x, b[0][1] + y, b[2] + 1.6];
    translate(at(b_pi, 28, 9))   cube([12, 12, 1.2]);         // Pi SoC (RP3A0)
    translate(at(b_pi, 61, 9.5)) cube([4.5, 11, 3]);          // CSI connector (+X end)
    translate(at(b_pca, 26, 8))  cube([10, 10, 1.4]);         // PCA9685
    translate(at(b_pca, 4, 2))   cube([2.5, 21, 8.5]);        // header row
    for (y = [3, 20.5]) translate(at(b_rly, 18, y)) cube([19, 15.5, 15.5]);   // 2 Songle relays
    translate(at(b_uln, 7, 9))   cube([20, 7, 3]);            // ULN2003 DIP
    translate(at(b_hx, 12, 7))   cube([7, 5, 1.4]);           // HX711 chip
    translate(at(b_l91, 8, 8))   cube([5, 4, 1.4]);           // L9110S chips
    for (b = [b_d22, b_d50, b_d36]) translate(at(b, 5, 5)) cube([6, 6, 2]);   // regulator ICs / inductors
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
module sh_hw() difference() { shuttle_fixed(); sh_printed(); }      // rod, REX tilt shaft, ch1 + ch2 servos
// servos: ch2 hangs at X 70..90, ch1 sits at Y < -168; rod and REX shaft are at X > 95, Y >= -168
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
if (part == "pcb_green") boards_green();
if (part == "pcb_blue") boards_blue();
if (part == "standoffs") board_screws();
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
if (part == "pump") hw_pump();                                   // R385 reference solid
if (part == "pump_bracket") { bracket_base(); bracket_cap(); bracket_sleeve(); bracket_pad(); valve_clip(); }
if (part == "valve") hw_valve();                                 // 12 V NC vent valve
if (part == "tee") hw_tee();                                     // 1/8" barbed tee
if (part == "tube") asm_vac_hose();
if (part == "cell_lead") asm_cell_lead(sh_y);                    // load-cell trailing loop, home pose
if (part == "harness") asm_harness();
if (part == "ribbon") asm_ribbon();
