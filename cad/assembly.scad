// Riftbound Card Sorter — Assembly View (Nov 11 redesign)
// Every part at machine coordinates; cad/machine_frame.scad is the single
// source of truth for the card path.
//
// Coordinate frame (matches machine_frame.scad and every part file):
//   X = card travel (hopper → belt → shuttle → sorting tray)
//   Y = across the belt (+Y = back of machine, electronics side)
//   Z = up; Z = 0 underside of the baseplate tiles, baseplate top Z = 4
//
// Each asm_* module below is one build step (cad/assembly-steps.yaml and
// cad/render_v2/parts.scad use them; `use` is not transitive, so the part
// files' own asm_* modules are wrapped here under distinct names).
//
// ── Machine layout ──────────────────────────────────────────────────────────
//   Baseplate        3 × 3 tiles, X −285..285, Y −270..270, top Z 4
//   Electronics tray X −150..35, Y 80..205, on the baseplate
//   Riser            X −165..85, Y −113..80, Z 4..64 (deck = rail base)
//   Conveyor         belt X −165..85, rollers X −140 / 60, rod axis Z 79,
//                    card face Z 90.9, slide bed X −127..47, rail top Z 99
//   Scan station     hood X −49..59 over the rails, camera on X 5, Z ≈ 191
//   Hopper elevator  cavity centre X −215, Y 0; tower +Y, motor top Z ≈ 158
//   Pick arm         servo axis X ≈ −154.7, Z ≈ 151.8; tower on the front
//                    (−Y) side at Y −173..−122; pick X −215 → drop X −95
//   Shuttle          cradle at X 92..169, carriage rod X 106, travel Y −102..176
//   Sorting tray     X 178..276, Y −137..137 (back/open face at X 178)
//   Reject bin       beside the tray at the shuttle's reject Y 176
//
// ── Pose ────────────────────────────────────────────────────────────────────
//   pose = "running" (default) | "home" | "pick" | "drop" | "custom"
//   "custom" uses arm_angle / elev_plate_z / shuttle_col / shuttle_tilt.

use <machine_frame.scad>
use <baseplate_tile.scad>
use <electronics_tray.scad>
use <riser.scad>
use <conveyor_rail.scad>
use <conveyor_roller.scad>
use <motor_mount.scad>
use <slide_bed.scad>
use <scanner_hood.scad>
use <hopper.scad>
use <hopper_elevator.scad>
use <suction_arm.scad>
use <sorting_tray.scad>
use <shuttle_geom.scad>
use <shuttle.scad>
use <pump_bracket.scad>

/* [Pose] */
pose         = "running"; // [running, home, pick, drop, custom]
arm_angle    = 120;       // PCA9685 ch0 servo angle (custom pose); pick ≈ 175, park 90, drop ≈ 5
elev_plate_z = 55;        // hopper floor-plate top, MACHINE Z (custom); travel 19..90.6
shuttle_col  = 1;         // 0..3, "reject" or "home" (custom)
shuttle_tilt = "hold";    // level | hold | upper | lower (custom)
show_cards   = true;      // card on the arm / in the cradle

// ── Frame values (functions: `use` does not import variables) ──────────────
base_top = frame_base_top();       // 4
deck_z   = frame_deck_z();         // 64  rail base on the riser
belt_x0  = frame_belt_x0();        // −165
rail_in  = frame_rail_in();        // 45
roller_x = frame_roller_x();       // [−140, 60]
shaft_z  = deck_z + 15;            // 79  rod axis
card_z   = frame_card_z();         // 90.9 card face (belt top)
rod_len  = 150;                    // 8 mm rod, centred on Y = 0
assert(abs(shaft_z + roller_belt_top_r() - card_z) < 0.05, "belt top is not at frame_card_z()");

// ── Pose resolution ─────────────────────────────────────────────────────────
// hopper plate: local Z = machine Z − base_top (hopper_elevator.scad API)
function _plate_local(zm) = max(hopper_zp_min(), min(hopper_zp_max(), zm - base_top));
pose_arm   = pose == "home" ? pick_arm_servo_park()
           : pose == "pick" ? pick_arm_servo_pick()
           : pose == "drop" ? pick_arm_servo_drop()
           : pose == "running" ? 120 : arm_angle;
pose_plate = pose == "home" ? hopper_zp_min()
           : pose == "pick" ? hopper_zp_max() - 20
           : pose == "drop" ? hopper_zp_max() - 20
           : pose == "running" ? _plate_local(55) : _plate_local(elev_plate_z);
pose_col   = pose == "running" ? 1 : pose == "custom" ? shuttle_col : "home";
pose_tilt  = pose == "running" ? "hold" : pose == "custom" ? shuttle_tilt : "level";
pose_arm_card = show_cards && (pose == "running" || pose == "drop" || pose == "custom");
pose_cradle_card = show_cards && pose != "home";

// ── Step 1 — Baseplate: 3 × 3 grid of 190 × 180 tiles ─────────────────────
module asm_baseplate()
    for (col = [0:2]) for (row = [0:2])
        translate([col * 190 - 285, row * 180 - 270, 0]) baseplate_tile();

// ── Step 2 — Electronics tray (185 × 150 × 45) on the baseplate, behind the riser
module asm_electronics_tray()
    translate([-150, 80, base_top]) electronics_tray();

// ── Step 3 — Conveyor riser (2 prints, 60 mm), anchored to the baseplate ───
module asm_deck_riser() asm_riser();

// ── Step 4 — Conveyor on the riser deck (geometry unchanged, lifted 60 mm) ─
// Rails × 2 (each 2 × 125), groove faces inward; front (−Y) = motor side.
module asm_rails() {
    for (side = [-1, 1])
        translate([belt_x0, side * rail_in, deck_z])
            mirror([0, side < 0 ? 1 : 0, 0]) {
                rail_half(add_shaft_far = false, motor_mount = (side < 0));
                translate([125, 0, 0]) rail_half(add_shaft_far = true, motor_mount = (side < 0));
            }
}
// 608ZZ bearings in the 4 rail pockets (|Y| 48..55)
module asm_bearings()
    for (x = roller_x) for (side = [-1, 1])
        translate([x, side * (rail_in + 3), shaft_z])
            rotate([side > 0 ? -90 : 90, 0, 0])
            difference() {
                cylinder(d = 22, h = 7, $fn = 48);
                translate([0, 0, -0.1]) cylinder(d = 8, h = 7.2, $fn = 32);
            }
// Slide bed between the rails (inside the belt loops)
module asm_slide_bed()
    translate([slide_bed_x0(), 0, deck_z]) slide_bed();
// Rollers (88 mm, 1 mm to each rail face) on the 8 mm rods
module asm_rollers()
    for (x = roller_x)
        translate([x, -roller_width() / 2, shaft_z]) rotate([-90, 0, 0]) roller();
module asm_rods()   // flat (4 mm wide, 0.54 deep) faces −Z, like the roller D-bore
    for (x = roller_x)
        translate([x, -rod_len / 2, shaft_z]) rotate([-90, 0, 0])
            difference() {
                cylinder(d = 8, h = rod_len, $fn = 32);
                translate([-5, sqrt(16 - 4), -1]) cube([10, 5, rod_len + 2]);
            }
// Race spacer + 8 mm collar outside each bearing
module asm_collars()
    for (x = roller_x) for (side = [-1, 1])
        translate([x, side * (rail_in + rail_boss_face_y()), deck_z])
            mirror([0, side < 0 ? 1 : 0, 0]) motor_mount_collar();
// Round belts: 4 × O-ring 135 × 3, stretched over the rollers
module asm_belts()
    for (y = roller_belt_y())
        translate([roller_x[0], y, shaft_z]) belt_strand(roller_x[1] - roller_x[0]);
// N20 motor brackets on the front rail (+ coupling and N20 reference solids)
module asm_motor_mounts()
    for (x = roller_x)
        translate([x, -rail_in, deck_z]) mirror([0, 1, 0])
            translate([0, rail_boss_face_y(), 0]) motor_mount();
module asm_motors()
    for (x = roller_x)
        translate([x, -rail_in, deck_z]) mirror([0, 1, 0])
            translate([0, rail_boss_face_y(), 0]) {
                motor_mount_coupling();
                motor_mount_n20();
            }
module asm_conveyor() {
    asm_rails(); asm_bearings(); asm_slide_bed(); asm_rollers(); asm_rods();
    asm_collars(); asm_belts(); asm_motor_mounts(); asm_motors();
}

// ── Step 5 — Scan station: card guides + clips, light hood, camera bracket ─
module asm_scan() asm_scan_station();

// ── Step 6 — Hopper elevator (motor-raised floor), plate_z = LOCAL plate top
// The flag is shown riding on the top card (phi_trip): the stack always
// reaches pick height in the assembly (hopper.scad hw_cards fills to pick_z).
module asm_hopper_lift(plate_z = -1) asm_hopper_elevator(plate_z, hopper_phi_trip());

// ── Step 7 — Pick arm: tower + head + MG996R (ch0) + triple parallelogram
module asm_arm(angle = 90, card = false) asm_pick_arm(angle, card);

// ── Step 8 — 2-floor sorting tray, open back face at X 178 (shuttle_geom) ──
module asm_sorting_tray()
    translate([shuttle_tray_x0() + sorting_tray_depth(), -sorting_tray_width() / 2, base_top])
        rotate([0, 0, 90]) full_2floor_assembly();

// ── Step 9 — Cradle shuttle (ch1 tilt, ch2 shuttle), load cell, lower ramp,
//             reject bin
module asm_sorter(col = "home", tilt = "level", card = false) asm_sorter_end(col, tilt, card);

// ── Step 10 — Wiring + vacuum (rough routing reference, not printed) ──────
// Cable bundles are hulls of spheres along a polyline. Routes:
//   vacuum tube Ø4: pump (front-left corner, X −265..−205) → along Y −205 →
//     up behind the arm column (X A+8, Y −160) → into the tube anchor on the
//     servo axis from behind (Y −152). The free spoke anchor → A' pin moves
//     with the arm and is checked by cad/pick_arm_check.py.
//   front harness Ø7: N20 ×2, ch1/ch2 servo, arm servo; clipped to the riser's
//     front face at Z 45 (above the ch2 crank, Z 5..13.5), round the −X end in
//     front of the arm column, down to Z 12 at X −277 (outside the hopper),
//     along the −X edge to Y 135, then in through the tray's −X wall cable
//     slots (X −150, Y 100..170, Z 40.5..46.5). The riser has no front→back
//     pass, so this is the only route that stays clear of the crank sweep.
//   arm servo Ø5: head-floor slot (Y ≈ −108) → under the head → down in front
//     of the column (Y −117.5) onto the harness.
//   hopper drop Ø5: 28BYJ-48 + 2 switches, down the tower back (Y 80).
//   camera FFC (16 mm, two Ø1.2 strands): connector → out of the bracket's
//     −Y plate slot → up the plate, over the gusset and arm top → down behind
//     the hood and back rail → into the tray from above at X 5, Y 88 (≈ 0.5 m).
//   load-cell cable: trailing service loop from the carriage (moves, not modelled).
// Pump: R385 in its isolated bracket (cad/pump_bracket.scad), nozzles at pump_nozzle_tip()
module asm_pump() asm_pump_bracket();
module cable(pts, d = 6) for (i = [0 : len(pts) - 2])
    hull() for (p = [pts[i], pts[i + 1]]) translate(p) sphere(d = d, $fn = 12);
function _ax() = pick_arm_pivot()[0];
function _az() = pick_arm_pivot()[1];
module asm_vac_tube()   // vacuum tube (4 mm OD, PU)
    color("SkyBlue") cable([pump_nozzle_tip(), [_ax() + 8, -205, 28], [_ax() + 8, -205, 18], [_ax() + 8, -160, 18],
                            [_ax() + 8, -160, _az()], [_ax(), -160, _az()], [_ax(), -152.5, _az()]], 4);
module asm_harness() {
    color("Black") {
        // main front harness (Ø7)
        cable([[66, -117.5, 52], [60, -117.5, 45], [-277, -117.5, 45], [-277, -117.5, 12],
               [-277, 135, 12], [-160, 135, 12]], 7);
        // fans out into the tray's three −X wall cable slots (10 × 6, Z 40.5..46.5, X −150)
        for (y = [105, 135, 165]) cable([[-160, 135, 12], [-160, y, 43.5], [-145, y, 43.5]], 5);
        // N20 drops onto the harness
        for (x = roller_x) cable([[x, -116, 66], [x, -117.5, 45]], 5);
        // arm servo cable: head floor slot → under the head → down in front of the column
        cable([[_ax(), -108, 99], [_ax(), -117.5, 99], [_ax(), -117.5, 45]], 5);
        // hopper motor + switches, down the tower back to the harness
        cable([[-215, 80, 150], [-215, 82, 12], [-277, 82, 12]], 5);
    }
}
module asm_ribbon()   // camera FFC, rough (two strands at the ribbon edges)
    color("Wheat") for (s = [-1, 1]) let(x = frame_cam_x() + s * 6)
        cable([[x, -9.5, 200.6], [x, -68.8, 200.6], [x, -68.8, 233.9], [x, -61, 233.9], [x, -41, 213.9],
               [x, 16.7, 213.9], [x, 62, 104], [x, 62, 84], [x, 88, 84], [x, 88, 30]], 1.2);
module asm_wiring() { asm_pump(); asm_vac_tube(); asm_harness(); asm_ribbon(); }

// ── Full assembly (default "running" pose) ─────────────────────────────────
asm_baseplate();
asm_electronics_tray();
asm_deck_riser();
asm_conveyor();
asm_scan();
asm_hopper_lift(pose_plate);
asm_arm(pose_arm, pose_arm_card);
asm_sorting_tray();
asm_sorter(pose_col, pose_tilt, pose_cradle_card);
asm_wiring();
