// =============================================
// Riftbound Card Sorter — Conveyor Riser (60 mm)
// =============================================
// Lifts the whole conveyor (rails, L-feet, slide bed, motor mounts, rollers,
// rods, card guides, hood, camera bracket) by frame_riser_h() = 60 mm, so
// every part that used to stand on the baseplate (Z 4) now stands on the
// riser deck (Z 64 = frame_deck_z()). Nothing on the conveyor changes.
//
// TWO PRINTS (each 125 × 193 × 60 mm, fits the 256 mm bed):
//   riser_a  X −165..−40   (under rail halves 1)
//   riser_b  X  −40.. 85   (under rail halves 2, motor mount 2, belt exit)
// Both are a closed-top box: 4 mm deck, 3 mm skin, 2.4 mm ribs at ≈31 mm
// pitch. Footprint Y −113..80: covers the front-rail motor brackets (sleeve to
// Y −111.5), the slide-bed skirts, all 8 rail L-feet (|Y| 48..79) and stops at
// the electronics tray (Y 80).
//
// TUNNEL: the ch2 shuttle crank (shuttle.scad, Ø278 half-disc about X 80,
// Y −131, at Z 5..13.5) and its 162 mm link sweep under the deck. Below Z 18
// the riser is open over that swept area (+8 mm) and along the front strip
// X ≥ 72 (carriage drive-pin arm); a 3 mm roof at Z 18 closes the box there.
// riser_b is therefore a 46 mm deep box beam standing on its back-left corner
// (behind the link sweep) and bolted to riser_a — far stiffer than the rails
// it carries, so a running belt cannot excite it.
//
// FASTENING (all M3):
//   Rail L-feet → riser → baseplate, ONE bolt per foot where possible:
//     through-bolt feet (M3 threaded rod 85 mm, or M3 × 80 + board ≤ 12 mm,
//     nut + washer both ends): front X −80; back X −120, −80, 10, 40.
//   Feet over the tunnel use M3 × 5.7 heat-set inserts in the deck with a
//     14 mm Ø3.4 relief below, so a 6 mm longer screw still fits:
//     front X −50, −20, 10. The camera bracket stands on the front feet at
//     X −20 and +10 and shares those screws (M3 × 16 instead of M3 × 10).
//   riser_a ↔ riser_b: 4× M3 × 12 + nut through the joint walls at X −40.
//   Riser → baseplate: 5 anchors (M3 × 80 or threaded rod, head down a Ø6.8
//     well from the deck top, nut + washer under the board) — fit the riser
//     BEFORE the conveyor, the slide bed covers two of the wells.
//   ch2 servo front ear shelf is part of riser_b (2× M2.5/M3 self-tap).
// PRINT: upside down (deck on the bed), PLA/PETG 0.24 mm, 3 walls, 15 % gyroid
//   (ribs carry the load). No supports (the tunnel floor bridges 31 mm cells).
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
tun_z = 18;                    // tunnel roof (crank Z ≤ 13.5, pin arm Z ≤ 16)

feet_through = [[-80, -75], [-120, 75], [-80, 75], [10, 75]];
feet_insert  = [[-50, -75], [-20, -75], [10, -75], [40, 75]];
// riser → baseplate anchors (counterbored from the deck top; fit BEFORE the
// conveyor goes on): M3 × 80 (or threaded rod) + nut/washer under the board
anchors      = [[-150, -105], [-150, 75], [-80, -15], [-20, 75], [-20, 45]];

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
function in_tunnel_dummy() = 0;

module tunnel_2d(x0, x1)
    intersection() {
        translate([x0 - 1, Y0 - 1]) square([x1 - x0 + 2, Y1 - Y0 + 2]);
        c2_sweep_2d();
    }

module riser_piece(x0, x1) {
    xs = [for (x = [x0 + 31 : 31 : x1 - 10]) x];
    ys = [-80, -45, -15, 15, 45];
    difference() {
        union() {
            difference() {
                union() {
                    difference() {
                        translate([x0, Y0, bt]) cube([x1 - x0, Y1 - Y0, dz - bt]);
                        translate([x0 + skin, Y0 + skin, bt - 1]) cube([x1 - x0 - 2 * skin, Y1 - Y0 - 2 * skin, dz - deck - bt + 1]);
                    }
                    for (x = xs) translate([x - rib / 2, Y0, bt]) cube([rib, Y1 - Y0, dz - bt]);
                    for (y = ys) translate([x0, y - rib / 2, bt]) cube([x1 - x0, rib, dz - bt]);
                    for (p = concat(feet_through, feet_insert)) if (p[0] > x0 && p[0] < x1)
                        translate([p[0], p[1], bt]) cylinder(d = 9, h = dz - bt);
                    for (p = anchors) if (p[0] > x0 && p[0] < x1)
                        translate([p[0], p[1], bt]) cylinder(d = 10, h = dz - bt);
                }
                // tunnel (open below tun_z)
                translate([0, 0, bt - 1]) linear_extrude(tun_z - bt + 1) tunnel_2d(x0, x1);
            }
            // tunnel roof plate
            translate([0, 0, tun_z]) linear_extrude(3) intersection() {
                tunnel_2d(x0, x1);
                translate([x0, Y0]) square([x1 - x0, Y1 - Y0]);
            }
            // ch2 servo front ear shelf (riser_b, front face)
            if (x1 > 80) {
                translate([68, -120.6, 24.2]) cube([17, 7.6 + eps, 3.4]);
                translate([68, -114, 24.2]) cube([17, 1.01, 10]);
            }
        }
        // through-bolt holes (rail foot → riser → baseplate)
        for (p = feet_through) if (p[0] > x0 && p[0] < x1)
            translate([p[0], p[1], 0]) cylinder(d = 3.6, h = 100, $fn = 20);
        // heat-set inserts + relief for longer screws
        for (p = feet_insert) if (p[0] > x0 && p[0] < x1) translate([p[0], p[1], 0]) {
            translate([0, 0, dz - 6]) cylinder(d = 4.0, h = 7, $fn = 24);
            translate([0, 0, dz - 20]) cylinder(d = 3.4, h = 21, $fn = 20);
        }
        // joint bolts at X −40 (4×), with nut access from the open bottom
        for (y = [-95, -30, 30, 65]) translate([XJ - 8, y, (y <= 14 ? 40 : 30)])
            rotate([0, 90, 0]) cylinder(d = 3.4, h = 16, $fn = 20);
        // baseplate anchors: Ø3.6 through, Ø6.8 head well from the deck top down to Z 10
        for (p = anchors) if (p[0] > x0 && p[0] < x1) translate([p[0], p[1], 0]) {
            cylinder(d = 3.6, h = 100, $fn = 20);
            translate([0, 0, 10]) cylinder(d = 6.8, h = 100, $fn = 24);
        }
        // ch2 shelf ear-screw pilots
        if (x1 > 80) for (x = [75, 85 - 0.5]) translate([min(x, 83), -116.8, 20]) cylinder(d = 2.2, h = 10, $fn = 16);
        // cable pass for the motor/servo wiring along the deck underside
        translate([x0 - 1, 60, 30]) rotate([0, 90, 0]) cylinder(d = 12, h = x1 - x0 + 2);
    }
}
module riser_a() riser_piece(XA[0], XA[1]);
module riser_b() riser_piece(XB[0], XB[1]);

// ==== PUBLIC: machine coordinates ====
module asm_riser() color("LightSlateGray") { riser_a(); riser_b(); }

if (part == "assembly") asm_riser();
if (part == "riser_a")  riser_a();
if (part == "riser_b")  riser_b();
