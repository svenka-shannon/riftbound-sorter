// =============================================
// Riftbound Card Sorter — Conveyor Riser (60 mm)
// =============================================
// Lifts the whole conveyor (rails, L-feet, slide bed, motor mounts, rollers,
// rods, card guides, hood, camera bracket) by frame_riser_h() = 60 mm, so
// every part that used to stand on the baseplate (Z 4) now stands on the
// riser deck (Z 64 = frame_deck_z()). Nothing on the conveyor changes.
//
// TWO PRINTS (riser_a 125 × 193 + a 16 mm tie tab, riser_b 129 × 193; both
// 60 mm tall, fit the 256 mm bed):
//   riser_a  X −165..−40   (under rail halves 1)
//   riser_b  X  −40.. 85   (under rail halves 2, motor mount 2, belt exit)
// Both are a closed-top box: 4 mm deck, 3 mm skin, 2.4 mm ribs at ≈31 mm
// pitch. Footprint Y −113..80: covers the front-rail motor brackets (sleeve to
// Y −111.5), the slide-bed skirts, all 8 rail L-feet (|Y| 48..79) and stops at
// the electronics tray (Y 80).
//
// TUNNEL: the ch2 shuttle crank (shuttle.scad, Ø278 half-disc about X 80,
// Y −124, Z 15..19, tip-screw head to Z 23) and its 162 mm link (Z 9..14) sweep
// under the deck. Below Z 26 (sg_c2_roof_z) the riser is open over that swept
// area (+8 mm) and along the front strip X ≥ 72 (carriage drive-pin arm, head to
// Z 24); a 3 mm roof at Z 26..29 closes the box there. riser_b is therefore a
// 38 mm deep box beam standing on its back-left corner (behind the link sweep)
// and tied to riser_a — far stiffer than the rails it carries.
//
// FASTENING (all M3; the baseplate is 4 mm tiles on a 6 mm board):
//   Rail L-feet → riser → baseplate, ONE bolt per foot where possible:
//     through-bolt feet (M3 × 80 SHCS into the board's tee-nut; or 85 mm M3
//     threaded rod with nut + washer at the top and the tee-nut / a washer +
//     nut under the board as the fallback): front X −80; back X −120, −80, 10.
//   The other feet use M3 × 5.7 heat-set inserts in the deck with a 14 mm Ø3.4
//     relief below, so a 6 mm longer screw still fits: front X −50, −20, 10
//     (over the tunnel) and back X 40. The camera bracket stands on the front feet at
//     X −20 and +10 and shares those screws (M3 × 16 instead of M3 × 10).
//   riser_a ↔ riser_b:
//     back/middle: 3 × M3 × 12 + nut through the joint walls at X −40
//       (Y −30 / 30 / 65), nut and head reached from the open bottom;
//     FRONT TIE (the joint's front is tunnel, its cells sealed by the roof):
//       riser_a's front skin carries on past the joint as a 16 × 3 tab
//       (X −40..−24, Z 30..64) that sits flush in a recess in riser_b's front
//       face; 2 × M3 × 10 countersunk from the front (heads flush, clear of the
//       Z 45 harness) into M3 × 5.7 inserts in riser_b's internal front wall
//       (insert Y −109.8..−104.1, Ø3.2 relief on to Y −102.2: the screw tip at
//       Y −103.0 has 0.8 mm to spare, 1.2 mm of wall behind).
//   Riser → baseplate: 5 anchors, head down a Ø6.8 well from the deck top onto
//     the 6 mm floor of the boss (head at Z 10), into the board's tee-nut
//     (baseplate_tile.scad; washer + nut under the board is the fallback).
//     Grip 6 + tile 4 + board 6 = 16 (+ washer 0.5 + nut 2.4 for the fallback) → M3 × 20
//     (use a long-arm 2.5 mm hex key down the 54 mm well). Fit the riser BEFORE
//     the conveyor: the slide bed covers two of the wells.
//   ch2 servo front ear: pocket in riser_b's front face (X 69..86, Y −113..−105.8,
//     Z 25..37.0). Over it a SOLID block (X 69..85, Y −113..−105, Z 37..64, i.e.
//     up to the deck, so it prints as a column) plus the lug on riser_b's +X face
//     (X 84.5..89): the pocket ceiling is real material over the whole ear. The ear
//     screws (2 × M2.5 × 10 button-head, X 75 and 85, Y −109.4: shared MG996R
//     pitch, machine_frame.scad) go up into Ø2.1
//     pilots 9 mm deep in the block/lug, driven from below through the tunnel
//     (1.5 mm L-key, short arm up). The block's front-bottom edge has a 1 mm 45°
//     lead-in: the ear slides in from −Y when the shuttle module is set down
//     (shuttle.scad, install order).
// PRINT: upside down (deck on the bed), PLA/PETG 0.24 mm, 3 walls, 15 % gyroid
//   (ribs carry the load). No supports: the tunnel roof is the last layer over
//   ≤ 29 mm cells (bridges); the tab, lug and ear block stand on the bed.
// NO SLIVERS: below the roof the tunnel edge is oblique to the ribs and skins; each
//   rib/skin row it touches is cut square across the rib (square_cut_2d), and the
//   insert-foot bosses start at the roof, so no knife-edge tips are left.
// =============================================

use <machine_frame.scad>
use <shuttle_geom.scad>

/* [Export] */
part = "assembly";   // assembly | riser_a | riser_b

$fn = 32;
eps = 0.01;
bt  = frame_base_top();        // 4
dz  = frame_deck_z();          // 64
Y0  = -113;  Y1 = 80;
XJ  = -40;                     // joint
XA  = [-165, XJ];  XB = [XJ, frame_belt_x1()];
skin = 3;  deck = 4;  rib = 2.4;
tun_z = sg_c2_roof_z();        // 26: tunnel roof underside (heads ≤ Z 24 below it)
roof_t = 3;

feet_through = [[-80, -75], [-120, 75], [-80, 75], [10, 75]];
feet_insert  = [[-50, -75], [-20, -75], [10, -75], [40, 75]];
// riser → baseplate anchors (counterbored from the deck top; fit BEFORE the
// conveyor goes on): M3 × 20 into the board tee-nuts (washer/nut fallback)
anchors      = [[-150, -105], [-150, 75], [-80, -15], [-20, 75], [-20, 45]];
joint_bolts  = [[-30, 40], [30, 30], [65, 30]];            // (Y, Z) through the X −40 walls
// front tie: tab on riser_a, inserts in riser_b
tie_x  = [XJ, XJ + 16];   tie_z = [30, dz];
tie_screws = [[XJ + 9.5, 37], [XJ + 9.5, 56]];             // (X, Z)
// ch2 front-ear lug beyond riser_b's +X face
lug_x  = [frame_belt_x1() - 0.5, 89];
ear_x  = sg_c2_ear_x();                                    // ch2 front-ear screws (X 75 / 85)
ear_blk = [69, -105];                                      // solid block over the front-ear pocket: X 69..x1, Y Y0..−105, Z 37..deck

// ch2 crank + link swept area (+8 mm margin), from shuttle_geom.scad
c2p = sg_c2_pivot(); c2r = sg_c2_r(); c2l = sg_c2_l();
function c2_tip(psi) = [c2p[0] - c2r * sin(psi), c2p[1] + c2r * cos(psi)];
function c2_pin(psi) = [c2p[0], c2p[1] + c2r * cos(psi) + sqrt(c2l * c2l - pow(c2r * sin(psi), 2))];
module c2_sweep_2d(m = 8) {
    intersection() {                                      // crank half-disc (toward −X)
        translate(c2p) circle(r = c2r + m, $fn = 120);
        translate([c2p[0] + m + 2 - 400, -400]) square([400, 800]);
    }
    for (i = [0 : 5 : 175]) hull() for (p = [i, i + 5]) {  // link
        translate(c2_tip(p)) circle(r = m, $fn = 16);
        translate(c2_pin(p)) circle(r = m, $fn = 16);
    }
    translate([72, Y0 - 1]) square([50, Y1 - Y0 + 2]);    // carriage drive-pin arm strip
}

// Square-ended tunnel cut: below the roof, every rib or skin ROW (strips along Y) or
// COLUMN (strips along X) that the tunnel touches is removed across the whole strip
// width, so the tunnel never leaves an oblique knife-edge tip on a rib or skin
// (strip ∩ minkowski(tunnel ∩ strip, segment across the strip)).
module square_cut_2d(x0, x1, xs, ys) {
    module sq(strip_xy, w, along_y) intersection() {
        translate(strip_xy) square(along_y ? [w, Y1 - Y0] : [x1 - x0, w]);
        minkowski() {
            intersection() { c2_sweep_2d(); translate(strip_xy) square(along_y ? [w, Y1 - Y0] : [x1 - x0, w]); }
            square(along_y ? [2 * w + 0.2, 0.01] : [0.01, 2 * w + 0.2], center = true);
        }
    }
    for (x = xs) sq([x - rib / 2, Y0], rib, true);
    sq([x0, Y0], skin, true); sq([x1 - skin, Y0], skin, true);
    for (y = ys) sq([x0, y - rib / 2], rib, false);
    sq([x0, Y0], skin, false); sq([x0, Y1 - skin], skin, false);
}
module riser_piece(x0, x1) {
    xs = [for (x = [x0 + 31 : 31 : x1 - 10]) x];
    ys = [-80, -45, -15, 15, 45];
    // everything is clipped to the piece box at the end (one cut, no coplanar seams)
    intersection() {
        difference() {
            union() {
                difference() {
                    union() {
                        difference() {
                            translate([x0, Y0, bt]) cube([x1 - x0, Y1 - Y0, dz - bt]);
                            translate([x0 + skin, Y0 + skin, bt - 1]) cube([x1 - x0 - 2 * skin, Y1 - Y0 - 2 * skin, dz - deck - bt + 1]);
                        }
                        for (x = xs) translate([x - rib / 2, Y0 + 1, bt]) cube([rib, Y1 - Y0 - 2, dz - bt]);
                        for (y = ys) translate([x0 + 1, y - rib / 2, bt]) cube([x1 - x0 - 2, rib, dz - bt]);
                        for (p = feet_through) if (p[0] > x0 && p[0] < x1)
                            translate([p[0], p[1], bt]) cylinder(d = 9, h = dz - bt);
                        // insert feet only need the deck + relief: from the roof up (no
                        // crescent left where the tunnel clips them)
                        for (p = feet_insert) if (p[0] > x0 && p[0] < x1)
                            translate([p[0], p[1], tun_z + 1]) cylinder(d = 9, h = dz - tun_z - 1);   // from inside the roof slab (no coplanar faces)
                        for (p = anchors) if (p[0] > x0 && p[0] < x1)
                            translate([p[0], p[1], bt]) cylinder(d = 10.4, h = dz - bt);
                        // riser_b: internal front wall behind the tie recess (insert bosses)
                        if (x0 == XJ) translate([x0 + 1, Y0 + 1, tun_z]) cube([tie_x[1] - x0 + 2, 11, dz - tun_z - 1]);
                    }
                    // tunnel (open below the roof) + the knife-edge tips it leaves
                    translate([0, 0, bt - 1]) linear_extrude(tun_z - bt + 1) {
                        c2_sweep_2d();
                        square_cut_2d(x0, x1, xs, ys);
                    }
                }
                // tunnel roof plate
                translate([0, 0, tun_z]) linear_extrude(roof_t) c2_sweep_2d();
                // riser_b: solid block over the ch2 front-ear pocket, up to the deck
                if (x1 > 80) translate([ear_blk[0], Y0, sg_c2_shelf_z()]) cube([x1 - ear_blk[0] + 1, ear_blk[1] - Y0, dz - sg_c2_shelf_z()]);
            }
            // through-bolt holes (rail foot → riser → baseplate)
            for (p = feet_through) translate([p[0], p[1], 0]) cylinder(d = 3.6, h = 100, $fn = 20);
            // heat-set inserts + relief for longer screws
            for (p = feet_insert) translate([p[0], p[1], 0]) {
                translate([0, 0, dz - 6]) cylinder(d = 4.0, h = 7, $fn = 24);
                translate([0, 0, dz - 20]) cylinder(d = 3.4, h = 21, $fn = 20);
            }
            // joint bolts at X −40, nut/head reached from the open bottom
            for (b = joint_bolts) translate([XJ - 8, b[0], b[1]]) rotate([0, 90, 0]) cylinder(d = 3.4, h = 16, $fn = 20);
            // baseplate anchors: Ø3.6 through, Ø6.8 head well from the deck top down to Z 10
            for (p = anchors) translate([p[0], p[1], 0]) {
                cylinder(d = 3.6, h = 100, $fn = 20);
                translate([0, 0, 10]) cylinder(d = 6.8, h = 100, $fn = 24);
            }
            // riser_b: recess for riser_a's tie tab (0.2 clearance) + inserts behind it
            if (x0 == XJ) {
                translate([x0 - 1, Y0 - 1, tie_z[0] - 0.2]) cube([tie_x[1] - x0 + 1.2, skin + 1.2, 50]);
                for (p = tie_screws) translate([p[0], Y0 + skin + 0.2 - eps, p[1]]) rotate([-90, 0, 0]) {
                    cylinder(d = 4.0, h = 5.7 + eps, $fn = 24);             // insert Y −109.8..−104.1
                    cylinder(d = 3.2, h = 7.6, $fn = 16);                   // relief to Y −102.2 (M3 × 10 tip −103.0)
                }
            }
            // ch2 servo front-ear pocket in riser_b's front face (ear Z 34.4..36.9,
            // pocket up to the block at Z 37.0) + 1 mm 45° lead-in on the block's
            // front-bottom edge + M2.5 pilots up into the block / lug
            if (x1 > 80) {
                translate([69, Y0 - 1, tun_z - 1]) cube([x1 - 69 + 1, sg_c2_ear_end_y()[0] + 1 - Y0 + 1, sg_c2_shelf_z() - tun_z + 1]);
                lead_in(69, x1 + 1);
                for (x = ear_x) translate([x, sg_c2_ear_y()[0], sg_c2_shelf_z() - 0.5]) cylinder(d = 2.1, h = 9.5, $fn = 16);
            }
            // cable pass for the motor/servo wiring along the deck underside
            translate([x0 - 1, 60, 44]) rotate([0, 90, 0]) cylinder(d = 12, h = x1 - x0 + 2);   // above the roof
        }
        translate([x0, Y0, bt]) cube([x1 - x0, Y1 - Y0, dz - bt]);
    }
}
module tie_tab() difference() {          // on riser_a: front-skin extension, flush with the front face
    translate([tie_x[0] - 1, Y0, tie_z[0]]) cube([tie_x[1] - tie_x[0] + 1, skin, tie_z[1] - tie_z[0]]);
    for (p = tie_screws) translate([p[0], Y0 - 1, p[1]]) rotate([-90, 0, 0]) {
        cylinder(d = 3.4, h = skin + 2, $fn = 20);
        translate([0, 0, 1 - eps]) cylinder(d1 = 7.0, d2 = 3.4, h = 1.8, $fn = 24);   // countersink, flush
    }
}
module ear_lug() difference() {          // on riser_b: carries the X 85 front-ear screw
    translate([lug_x[0], Y0, sg_c2_shelf_z()]) cube([lug_x[1] - lug_x[0], sg_c2_ear_end_y()[0] + 2 - Y0, dz - sg_c2_shelf_z()]);
    translate([ear_x[1], sg_c2_ear_y()[0], sg_c2_shelf_z() - 1]) cylinder(d = 2.1, h = 10, $fn = 16);
    lead_in(lug_x[0] - 1, lug_x[1] + 1);
}
// 1 × 1 mm 45° lead-in along the front-bottom edge (Y0, ceiling Z 37) from X a to b
module lead_in(a, b) translate([a, Y0, sg_c2_shelf_z()]) rotate([90, 0, 90]) linear_extrude(b - a)
    polygon([[-1, -1], [1, -1], [-1, 1]]);
function riser_ear_screws() = [for (x = ear_x) [x, sg_c2_ear_y()[0], sg_c2_shelf_z()]];   // (X, Y, ceiling Z)
function riser_tie_screws() = tie_screws;     // (X, Z) of the front-tie screws (Y = Y0 face)
function riser_front_y() = Y0;
module riser_a() { riser_piece(XA[0], XA[1]); tie_tab(); }
module riser_b() { riser_piece(XB[0], XB[1]); ear_lug(); }

// ==== PUBLIC: machine coordinates ====
module asm_riser() color("LightSlateGray") { riser_a(); riser_b(); }

if (part == "assembly") asm_riser();
if (part == "riser_a")  riser_a();
if (part == "riser_b")  riser_b();
