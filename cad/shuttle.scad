// =============================================
// Riftbound Card Sorter — Cradle Shuttle (belt-end sorter)
// =============================================
// Replaces the two flat sort-gate levers. One card at a time:
//   belt → CRADLE (weighed alone, at rest, on a TAL221 beam) → shuttle sideways
//   (ch2) to one of 4 tray columns or the reject bin → tip (ch1) into the
//   UPPER slot (forward about the front pin F) or onto the fixed LOWER RAMP
//   (forward about the rear skid on the fixed R-bar).
// Geometry, kinematics and the full story: shuttle_geom.scad (single source
// of truth, mirrored in shuttle_check.py). Firmware: hardware/shuttle.py.
//
// PRINTED PARTS (export with -D 'part="..."', assembly pose; all fit the
// 256 mm bed; "bed" = contact area in the stated orientation):
//   cradle        1×  PLA, 0.12 mm layers, 3 walls, 15 %, IRON the top;
//                     13.6 cm³ solid ≈ 17 g (≈ 19 g with tape + inserts; target
//                     ≤ 35 g). Print bed-top UP, NO supports: the boss and every
//                     rib (skirts, |y| 10 / 22, rear rib) stand on one flat plane
//                     (bed ≈ 600 mm²; use a brim), the bed panels bridge ≤ 19 mm
//                     between ribs, the kick underside bridges between 45° rib
//                     noses. The card faces (bed, kick, guide insides) are all
//                     up-facing or vertical. The kick is an 18° slope whose layer
//                     steps face downhill for an exiting card. Then cover bed +
//                     kick with 0.1 mm skived-PTFE tape (wrap 2 mm over the lip),
//                     this is REQUIRED: shuttle_check.py slide shows bare PLA
//                     (μ ≈ 0.35-0.45) jams the upper-floor transfer.
//   tilt_frame    1×  PETG, 0.2, 4 walls, 40 %, upright (crossbar down), NO
//                     supports: crossbar, plate bottoms and the skid-nub tangents
//                     are one flat plane at Z 63.8 (bed ≈ 1420 mm²); the plate
//                     tails rest on the nubs, window tops are 12 mm bridges, the
//                     link slot (open below, 5.5 wide) has a flat bridged ceiling
//                     then a 45° one, the block over it ties the crossbar halves, the
//                     rear window edge and the plate step are 45°, the bores are
//                     small horizontal holes. Ream the F-pin holes Ø3.9 and press
//                     Ø4 × 8 dowels from inside; ream the pin-A bore Ø2.95.
//   sled          1×  PETG, 0.2, 4 walls, 40 %, on its +y face (bed ≈ 720 mm²):
//                     LM8UU pockets, shaft bushings and insert holes print as vertical
//                     holes, the ch2 arm has a 45° flank, the crank pocket closes
//                     with 45° roofs (only ≤ 0.5 mm ledges at their edges and tips);
//                     the only other flat overhangs are the round LM8UU pocket ends
//                     (bridged) and the 3.6 mm notch roof. Ream the shaft bushings Ø8.3 and the
//                     drive-pin journal Ø4.0+. 6 × M3 × 5.7 inserts (cheeks).
//   cheek_neg / cheek_pos  1× each, PETG, 0.2, 4 walls, 40 %, flat on the outer
//                     face (bed ≈ 3560 mm², no overhangs; countersinks on the bed
//                     side are 45° cones). Bolt to the sled with 3 × M3 × 10
//                     countersunk + 2 × Ø3 × 8 dowels each.
//   tilt_crank / tilt_link  1× each, PETG 100 %, flat; the crank bore is REX
//                     (Ø8.15 ∩ 7.15 hex) for the goBILDA REX shaft. Crank arm: straight
//                     lower edge 2.5 under the axis (keeps it off the +Y LM8UU).
//   c2_crank      1×  PETG, 0.2, 5 walls, 50 %, flat (155 mm), countersinks down
//   c2_link       1×  PETG, flat (173 mm); press the 2 × M3 × 4 inserts flush
//                     from the top
//   rbar_neg / rbar_pos  1× each, PLA, on the −X face, 4 walls; sand the top
//   end_post_neg  1×  PETG, 0.2, 4 walls, 40 %, upright (floor plate down, bed
//                     ≈ 3500 mm²), 78 × 79 × 81. The export includes a separate
//                     break-away support ladder (0.8 walls, 4 cells) under the ch2
//                     rear-ear ledge (X 70.5..89.5, Y −161.5..−155.5, up to 0.2 below
//                     the ledge): that ledge sits over the servo ear and the crank
//                     sweeps everything below Z 21 at X < 90, so no printable gusset
//                     can reach it; snap the ladder out with pliers. Everything else
//                     is support-free: the cage opening top is a 20 mm bridge, the
//                     gusset is 45°, the holes are small horizontal bores.
//   end_post_pos  1×  PETG/PLA, 4 walls, 40 %, upright, no supports
// HARDWARE: see the BOM block at the end of this file.
// =============================================

use <shuttle_geom.scad>
use <lower_ramp.scad>
use <reject_bin.scad>

/* [Export] */
part = "assembly";   // assembly | cradle | tilt_frame | carriage_preview (NOT a print) | sled | cheek_neg | cheek_pos | tilt_crank | tilt_link | c2_crank | c2_link | rbar_neg | rbar_pos | end_post_neg | end_post_pos
show_col   = 1;        // assembly preview: 0..3, "reject", "home"
show_state = "hold";   // level | hold | upper | lower

$fn = 40;
eps = 0.01;

// ---------- shorthands ----------
bz   = sg_bed_z();  bt = sg_bed_t();  bx0 = sg_bed_x0();  bend = sg_bend_x();
F    = sg_F();      S0 = sg_S0();     D   = sg_D();       A   = sg_A();
cxc  = sg_cell_xc(); czt = sg_cell_ztop();
tfy  = sg_tf_y();   chy = sg_cheek_y();
rod  = sg_rod();    hw  = sg_carr_hw();
pinA_y = [1.5, 21.5];   // tilt-link pin A dowel (Ø3 × 20) span in y

// XZ-profile helper: 2D (x = machine X, y = machine Z) → 3D slab y0..y1
module xz(y0, y1) translate([0, y1, 0]) rotate([90, 0, 0]) linear_extrude(y1 - y0) children();
module xz_sym(a, b) { xz(a, b) children(); xz(-b, -a) children(); }
// cylinder along Y
module cyl_y(p, d, y0, y1, fn = 40) translate([p[0], y0, p[1]]) rotate([-90, 0, 0]) cylinder(d = d, h = y1 - y0, $fn = fn);

// =====================================================================
// CRADLE — on the load-cell free end. Level frame, y about the carriage.
// =====================================================================
function lead_in_pts() = [for (a = [150 : -10 : 90]) [bx0 + 4 + 4 * cos(a), bz - 4 + 4 * sin(a)]];
module bed_profile_2d() {
    ka = sg_kick_a(); kl = sg_kick_l(); fr = 20;            // concave fillet radius at the bend
    t  = fr * tan(ka / 2);                                  // tangent length
    fc = [bend - t, bz + fr];                               // fillet centre (above)
    fil = [for (i = [0 : 6]) let(a = -90 + ka * i / 6) [fc[0] + fr * cos(a), fc[1] + fr * sin(a)]];
    lipt = sg_lip();
    nrm = [sin(ka), -cos(ka)];                              // kick downward normal
    top = concat(lead_in_pts(), fil, [lipt]);
    bot = [lipt + bt * nrm, [bend + bt * tan(ka / 2), bz - bt], [bx0 + 0.6, bz - bt]];
    union() {
        polygon(concat(top, bot));
        translate(lipt + (bt / 2) * nrm) circle(d = bt, $fn = 24);   // rounded lip
    }
}
function guide_in(x) = x <= bx0 + 2 ? sg_mouth_hw()
                     : x >= bx0 + 14 ? sg_guide_hw()
                     : sg_mouth_hw() - (sg_mouth_hw() - sg_guide_hw()) * (x - bx0 - 2) / 12;
module cradle_guide(s) {            // s = +1 / −1
    gt = sg_guide_t(); gz = sg_guide_top(); x1 = bend - 1.5;
    xs = [bx0 + 1, bx0 + 2, bx0 + 14, x1];
    difference() {
        union() for (i = [0 : len(xs) - 2]) hull() for (x = [xs[i], xs[i + 1]])
            translate([x, s > 0 ? guide_in(x) : -guide_in(x) - gt, bz - 0.5])
                cube([0.01, gt, gz - bz + 0.5]);
        // 1 mm chamfer on the inner top edge + rounded ends
        for (i = [0 : len(xs) - 2]) hull() for (x = [xs[i], xs[i + 1]])
            translate([x, s * guide_in(x), gz]) rotate([45, 0, 0]) cube([0.02, 1.42, 1.42], center = true);
    }
}
// Underside = one flat print plane at the boss bottom (Z czt = 81.4): the cradle
// prints bed-top UP with every rib standing on the plate, and the bed between
// the ribs is a short bridge (≤ 19 mm). Ribs 1.2 thick, full depth (6.8):
//   skirts at |y| 34.0..35.2 (0.8 inside the TF plates, as the bed edge was),
//   |y| 10 (3.4 beside the 12-wide cell) and |y| 22, a rear rib at X 93;
//   under the kick each rib ends in a 45° nose, so the kick underside is a
//   short sloped bridge between ribs (no supports). To stay inside the mass
//   budget the bed panels between ribs are 1.4 thick (0.6 pockets from below).
cr_rib = 1.2;
cr_ribs_y = [-34.6, -22, -10, 10, 22, 34.6];
cr_nose = [bend + bt * tan(sg_kick_a() / 2), bz - bt];     // bed underside at the bend (157.3, 88.2)
function cr_nose_x() = let(k = tan(sg_kick_a()), x0 = 155.2)   // 45° from (x0, czt) meets the kick underside
    (cr_nose[1] - k * cr_nose[0] - czt + x0) / (1 - k);
module cradle_nose_2d() let(xn = cr_nose_x())    // rib nose under the kick (45° from the plate)
    polygon([[155.2, czt + 0.05], [xn, czt + xn - 155.2 + 0.05],
             [xn, cr_nose[1] + (xn - cr_nose[0]) * tan(sg_kick_a()) + 0.5],
             [cr_nose[0], cr_nose[1] + 0.5], [154, bz - bt + 0.5], [154, czt + 0.5]]);
// plan of everything standing on the print plane (one extrusion: no coplanar seams)
module cradle_floor_2d(bw) {
    h = sg_cradle_hw() - 0.01;                              // 0.01 inside the bed edge (no coplanar faces)
    for (y = cr_ribs_y) translate([bx0 + 1, max(y - cr_rib / 2, -h)])
        square([155.4 - bx0 - 1, min(y + cr_rib / 2, h) - max(y - cr_rib / 2, -h)]);
    translate([bx0 + 1, -h]) square([cr_rib, 2 * h]);          // rear rib
    translate([cxc - 23.5, -bw]) square([7, 2 * bw]);                                    // boss on the cell free pad (X 106..113)
}
module cradle() {
    bw = 7;                                                 // boss half-width: 2.0 walls round the inserts
    difference() {
        union() {
            xz(-sg_cradle_hw(), sg_cradle_hw()) bed_profile_2d();
            for (s = [-1, 1]) cradle_guide(s);
            translate([0, 0, czt]) linear_extrude(bz - bt - czt + 0.5) cradle_floor_2d(bw);
            for (y = cr_ribs_y) xz(max(y - cr_rib / 2 + 0.01, -sg_cradle_hw() + 0.03), min(y + cr_rib / 2 - 0.01, sg_cradle_hw() - 0.03)) cradle_nose_2d();
        }
        // 2× M3 heat-set inserts (Ø4.0 × 5.7) from below, on the cell's Ø3.2 holes
        for (y = [-3, 3]) translate([cxc - 20, y, czt - 0.1]) cylinder(d = 4.0, h = 6.0, $fn = 24);
        // 0.6 pockets under the bed panels (bed 1.4 there), clear of ribs, boss and bend
        ys = [for (y = cr_ribs_y) each [y - cr_rib / 2, y + cr_rib / 2]];
        for (i = [1 : 2 : len(ys) - 3]) let(a = ys[i] + 0.05, b = ys[i + 1] - 0.05)
            for (xr = (a < 0 && b > 0) ? [[bx0 + 3.2, cxc - 25.5], [cxc - 14.5, bend - 3]] : [[bx0 + 3.2, bend - 3]])
                translate([xr[0], a, bz - bt - 1]) cube([xr[1] - xr[0], b - a, 1.6]);
    }
}

// =====================================================================
// TILT FRAME — two side plates + front crossbar (cell fixed end, link pin A)
// =====================================================================
// The plate bottom is FLAT at Z 63.8 from X 112.8 to 160 (the skid nub's bottom
// tangent, the crossbar bottom): printed upright (crossbar down) the part stands on
// that plane (≈ 1480 mm²) and needs no supports; the 45° step at X 110..112.8 and
// the 53° rear edge are self-supporting, the nub carries the plate tail. Behind
// X 112.5 the bottom must stay ≥ 0.6 above what swings into the R-bar in LOWER
// (about the skid): 66.0 at X 107.5, 66.6 at X 110 (needs 65.9 / 66.0).
tf_bot = sg_S0()[1] - sg_skid_r();     // 63.8
// The link turns about pin A relative to the TF from −106° (LEVEL) to −32° (LOWER),
// −55° in UPPER (0° = +X, TF frame; shuttle_check.py prints the range). Its slot is
// that sector ± 6° about A, widened by the link half-width 3.5 + 0.6 running clearance.
lk_rng = [-112, -26];
lk_c = 0.6;
// Printed crossbar-down, so the slot's ceiling must be flat (a 5.5 mm bridge across the
// slot) or ≥ 45°: flat at the top of the link end's clearance (Z 74.1) from behind A to X 152, then
// 45° down to the front face, above the shallow −26° edge of the swept sector.
module link_slot_2d() {
    r = sg_link_w() / 2 + lk_c; top = A[1] + r;
    offset(r = r) polygon(concat([A], [for (a = [lk_rng[0] : 2 : lk_rng[1]]) A + 30 * [cos(a), sin(a)]]));
    polygon([[A[0] - r - 0.5, top], [152, top], [182, top - 30], [A[0] - r - 0.5, top - 30]]);
}
tf_bridge_y = [sg_link_y()[0] - 1.5, sg_link_y()[1] + 1.5];   // 6.5..14
tf_bridge_z = 79.5;
module tf_plate_2d()
    polygon([[103, 68], [104.5, 66], [107.5, 66], [110, 66.6], [110 + 66.6 - tf_bot, tf_bot], [160, tf_bot],
             [163, 68], [163, 93], [160, 96], [154, 96], [150, 93], [118, 80], [106, 76.5], [103, 74]]);
module tilt_frame() {
    ly = sg_link_y();
    difference() {
        union() {
            xz_sym(tfy[0], tfy[1]) tf_plate_2d();
            // rounded skid nub (contact r 2 at S0)
            for (s = [-1, 1]) cyl_y(S0, 2 * sg_skid_r(), s > 0 ? tfy[0] : -tfy[1], s > 0 ? tfy[1] : -tfy[0], 32);
            // F pin bosses (outer side, to |y| 39.8: 0.7 to the cheek inner face)
            for (s = [-1, 1]) cyl_y(F, 10, s > 0 ? tfy[1] - eps : -39.8, s > 0 ? 39.8 : -tfy[1] + eps, 40);
            // crossbar
            translate([140, -tfy[1], tf_bot]) cube([18, 2 * tfy[1], 73.9 - tf_bot]);
            // cell fixed-end pad (tapped end of the TAL221)
            translate([cxc + 16.5, -6, 73.9 - eps]) cube([7, 12, czt - 6 - 73.9 + eps]);
            // bridge over the link slot: the slot cuts the crossbar right through in its
            // y band, so this block (y 6.5..14, Z 73.9..79.5) ties the two halves together
            // above the link (0.6 over its end at A, 0.5 beside the cell, 1.9 under the cradle)
            translate([140, tf_bridge_y[0], 73.9 - eps]) cube([158 - 140, tf_bridge_y[1] - tf_bridge_y[0], tf_bridge_z - 73.9 + eps]);
        }
        // F pin holes Ø3.9 (press Ø4 dowel)
        for (s = [-1, 1]) cyl_y(F, 3.9, -41, 41, 24);
        // cell screws into the tapped end: M3 × 12, clearance + head counterbore from
        // below (counterbore top Z 68: 1.7 below pin A's bore)
        for (y = [-3, 3]) translate([cxc + 20, y, 60]) {
            cylinder(d = 3.4, h = 30, $fn = 20);
            cylinder(d = 6.2, h = 68 - 60, $fn = 24);
        }
        // link slot (open below, y 7.5..13: 1.4 wall to the cell-screw counterbores):
        // the link's whole swing about A relative to the TF + 0.6 (link_slot_2d)
        xz(ly[0] - 0.5, ly[1] + 0.5) link_slot_2d();
        // pin A = Ø3 × 20 dowel at Y pinA_y, pushed in from the +Y plate through the
        // Ø3.3 entry bore until it bottoms at Y 1.5; firm fit in the Ø2.9 bore on both
        // sides of the link (ream Ø2.95). Ø2 knock-out from the −Y plate.
        cyl_y(A, 2.9, pinA_y[0], pinA_y[1] + 0.5, 20);
        cyl_y(A, 3.3, pinA_y[1], tfy[1] + 1, 20);
        cyl_y(A, 2.0, -tfy[1] - 1, pinA_y[0] + eps, 16);
        // cell cable exit notch in the crossbar front
        translate([155, -3, 72]) cube([4, 6, 3]);
        // lightening windows in the plates
        for (s = [-1, 1]) xz(s > 0 ? tfy[0] - 1 : -tfy[1] - 1, s > 0 ? tfy[1] + 1 : -tfy[0] + 1)
            polygon([[118, 71], [136, 67.5], [136, 76], [123, 76]]);   // 45° upper rear edge (support-free)
    }
}

// =====================================================================
// CARRIAGE — sled (rod + REX tilt shaft) and two cheeks with the F hooks
// =====================================================================
// Three prints: the SLED (rod + REX shaft + ch1 crank pocket + ch2 drive-pin arm,
// |y| ≤ 40.5) and two bolt-on CHEEKS (|y| 40.5..45.5, printed flat on the outer
// face). Each cheek's root laps the whole sled side (X 91..118, sled profile) and
// is held by 3 × M3 countersunk screws into heat-set inserts in the sled, located
// by 2 × Ø3 × 8 dowels. Both LM8UU sit wholly in the sled (pockets |y| 16.4..40.5);
// the cheek root closes each pocket mouth (Ø10 rod hole) and retains the bearing.
sled_hw = chy[0];                                           // 40.5
cheek_screws = [[112.5, 39], [97, 50], [114.5, 16.5]];      // (X, Z) M3 + insert (Ø4.0 × 6.5)
cheek_dowels = [[94, 42], [115, 31]];                       // (X, Z) Ø3 × 8 dowel: Ø2.9 press in the sled, Ø3.1 in the cheek
// sled side profile; the rear-bottom notch (X < 94.6, Z < 23) lets the ch2 horn and
// crank pass the carriage during travel, so the cheek root keeps it too
module sled_side_2d() polygon([[94.7, 13], [118, 13], [118, 41.5], [107.5, 54], [91, 54], [91, 23.1], [94.7, 23.1]]);
module cheek_2d() union() {
    // front edge at X 158 over Z 40..52: ≥ 2.4 round the lower-mode F channel
    polygon([[111, 13], [148, 13], [156, 26], [156, 40], [158, 43], [158, 52], [164, 61], [164, 97],
             [150, 97], [138, 84], [118, 58], [111, 58]]);
    sled_side_2d();                                         // root, lapping the whole sled side
}
// F pin path in LOWER mode (arc about the skid) → channel in the cheek
function f_path() = [for (i = [0 : 12]) sg_rot(sg_F(), sg_SJ(), sg_dl_lower() * i / 12)];
// ch2 drive-pin arm (XY), modelled in carriage coordinates. The 45° flank on its
// +y side keeps it self-supporting when the sled prints on its +y face.
module c2_arm_2d() hull() {
    translate([sg_c2_pivot()[0], sg_c2_pin_dy()]) circle(r = 6, $fn = 48);
    translate([86, sg_c2_pin_dy() - 6]) square([92 - 86, 21.5 - sg_c2_pin_dy() + 6]);
}
// ch1 crank pocket (XZ, machine coordinates), cut through the crank slab ± pk_c:
//  - the crank (tilt_crank_2d) swept about D over φ pk_rng, + pk_c running clearance.
//    φ runs −48.5 (LOWER) .. 22.2 (UPPER); below LOWER the cradle meets the lower
//    ramp within ≈ 1°, so 1.5° margin there; 30° on top is free air.
//  - the insertion channel: the Ø16 hub (+ pk_c) slides in along −X from the sled's
//    front face with the crank pointing +X (φ 0), §13.2.
// The +Y LM8UU pocket (|y| ≥ 16.4) overlaps the slab only near the rod: the crank's
// lower arm edge (crank_low) keeps ≥ 1.3 of wall between the two pockets at φ −50.
pk_rng = [-50, 30];
pk_c = 0.7;
module crank_pocket_2d() offset(r = pk_c, $fn = 24) translate(D) union() {
    hull() { circle(d = 16); translate([25, 0]) circle(d = 16); }   // hub + insertion channel
    for (a = [pk_rng[0] : 2 : pk_rng[1]]) rotate(a) tilt_crank_arm_2d();
}
// crank pocket (crank_pocket_2d) over the crank slab ± pk_c (y 12.8..18.7). The link
// (y 8..12.5) only ever moves at X ≥ 122.7, outside the sled, so toward −y the pocket
// closes with a 45° roof (printed on the +y face this roof is the only overhang). The
// pocket outline is a union of convex pieces (hub + channel; per swept angle the arm
// and the tip boss); under each piece a 45° frustum (the piece inset by k at depth k),
// started 0.3 inside the slab so it meets the slab bottom 0.35 inside the outline
// (a 0.35 ledge, less than one extrusion width).
module pocket_roof(k) {
    y0 = sg_crank_y()[0] - pk_c;
    hull() { xz(y0 + 0.3, y0 + 0.3 + eps) offset(delta = -0.05) children(); xz(y0 - k, y0 - k + eps) offset(delta = -k - 0.35) children(); }
}
module sled_crank_pocket() {
    cy = sg_crank_y();
    xz(cy[0] - pk_c, cy[1] + pk_c) crank_pocket_2d();
    pocket_roof(8 + pk_c - 0.6) translate(D) offset(r = pk_c, $fn = 24) hull() { circle(d = 16); translate([25, 0]) circle(d = 16); }
    for (a = [pk_rng[0] : 2 : pk_rng[1]]) {
        pocket_roof(4.5 + pk_c - 0.6) translate(D) rotate(a) translate([sg_crank_r(), 0]) offset(r = pk_c, $fn = 24) circle(d = 9);
        pocket_roof(3.6) translate(D) rotate(a) offset(r = pk_c, $fn = 24) tilt_crank_arm_hull_2d();
    }
}
// LM8UU pockets Ø15.1 × 24.1 at both ends (the cheek roots close the mouths)
module sled_lm8uu_pockets() for (s = [-1, 1])
    cyl_y(rod, 15.1, s > 0 ? sled_hw - 24.1 : -sled_hw - 1, s > 0 ? sled_hw + 1 : -sled_hw + 24.1, 48);
module sled() {
    cy = sg_crank_y(); ly = sg_link_y(); az = sg_c2_arm_z();
    difference() {
        union() {
            translate([91, -sled_hw, 13]) cube([118 - 91, 2 * sled_hw, 54 - 13]);
            translate([0, 0, az[0]]) linear_extrude(az[1] - az[0]) c2_arm_2d();
        }
        // rear-bottom notch: the ch2 horn disc (Ø25, Z 19..20.4, X ≤ 92.5) passes the
        // sled at column 0; kept solid around the drive-pin arm (y −8..23)
        for (yy = [[-sled_hw - 1, -8], [23, sled_hw + 1]]) translate([90, yy[0], 12]) cube([4.6, yy[1] - yy[0], 11]);
        // front-top chamfer: the TF plates swing past it in LOWER
        xz(-sled_hw - 1, sled_hw + 1) polygon([[107.5, 54.1], [118.1, 54.1], [118.1, 41.5]]);
        // rod: Ø8.4 through, LM8UU Ø15.1 × 24.1 pockets at both ends
        cyl_y(rod, 8.4, -sled_hw - 1, sled_hw + 1);
        sled_lm8uu_pockets();
        // REX tilt shaft: Ø8.3 bushing bores at both ends (8 long, on the round lands), Ø10 relief in between
        cyl_y(D, 8.3, -sled_hw - 1, sled_hw + 1);
        cyl_y(D, 10, -sled_hw + 8, sled_hw - 8);
        sled_crank_pocket();
        // ch2 drive pin: Ø4.1 journal for the 4 mm shoulder (ream Ø4.0 + slip)
        translate([sg_c2_pivot()[0], sg_c2_pin_dy(), az[0] - 1]) cylinder(d = 4.1, h = az[1] - az[0] + 2, $fn = 24);
        // cheek fixings: inserts + dowel holes in both side faces
        for (s = [-1, 1]) {
            for (p = cheek_screws) cyl_y([p[0], p[1]], 4.0, s > 0 ? sled_hw - 6.5 : -sled_hw - 1, s > 0 ? sled_hw + 1 : -sled_hw + 6.5, 24);
            for (p = cheek_dowels) cyl_y([p[0], p[1]], 2.9, s > 0 ? sled_hw - 6 : -sled_hw - 1, s > 0 ? sled_hw + 1 : -sled_hw + 6, 20);
        }
    }
}
module cheek(s) {          // s = +1: +y cheek, −1: −y cheek (assembly position)
    y0 = s > 0 ? chy[0] : -chy[1]; y1 = s > 0 ? chy[1] : -chy[0];
    yo = s > 0 ? chy[1] : -chy[1];                          // outer face
    difference() {
        xz(y0, y1) cheek_2d();
        // F hook + lower-mode channel, 3.8 deep in the inner face
        for (i = [0 : len(f_path()) - 2]) hull() for (p = [f_path()[i], f_path()[i + 1]])
            cyl_y(p, 4.5, s > 0 ? chy[0] - 1 : -44.3, s > 0 ? 44.3 : -chy[0] + 1, 24);
        // rod and REX-shaft clearance (the root closes the LM8UU pocket: Ø10 < Ø15)
        cyl_y(rod, 10, y0 - 1, y1 + 1, 40);
        cyl_y(D, 9.5, y0 - 1, y1 + 1, 40);
        // M3 countersunk screws (head flush with the outer face), dowels
        for (p = cheek_screws) {
            cyl_y([p[0], p[1]], 3.4, y0 - 1, y1 + 1, 20);
            translate([p[0], yo, p[1]]) rotate([s > 0 ? -90 : 90, 0, 0]) translate([0, 0, -1.8])
                cylinder(d1 = 3.4, d2 = 7.0, h = 1.8 + eps, $fn = 24);
        }
        for (p = cheek_dowels) cyl_y([p[0], p[1]], 3.1, y0 - 1, y1 + 1, 20);
        // cable clip slot for the load-cell lead (zip tie) on the −y cheek
        if (s < 0) translate([150, -chy[1] - 1, 70]) cube([4, chy[1] - chy[0] + 2, 2.5]);
    }
}
// assembled carriage (preview + checks): cheeks sunk 0.01 into the sled so the union is
// one valid solid instead of two face-touching ones
module carriage() { sled(); for (s = [-1, 1]) translate([0, -s * 0.01, 0]) cheek(s); }

// =====================================================================
// ch1 tilt crank (on the REX shaft) and link
// =====================================================================
// The crank is captured in the sled's swing pocket and SLIDES along the fixed
// shaft with the carriage, so it is keyed by its bore only (no set screw).
// The tilt shaft (axis D) is an 8 mm REX shaft (Ø8 round ∩ 7 mm across-flats hex,
// goBILDA 2106-4008-4320, cut to 417 mm):
// the round lands run in the 688ZZ and the sled bushings, the hex drives the crank
// and the bought ch1 coupler. Crank bore = REX + 0.15 (Ø8.15 ∩ 7.15 hex).
module rex_2d(d = 8, af = 7) intersection() { circle(d = d, $fn = 48); circle(r = af / 2 / cos(30), $fn = 6); }
module rex_bore(h) linear_extrude(h) rex_2d(8.15, 7.15);   // flats parallel to the crank arm
// Crank outline (crank frame: D at the origin, pointing +X): Ø16 hub, Ø9 tip boss, and
// an arm whose LOWER edge is a straight line crank_low below the axis (the upper edge is
// the hub-to-tip tangent). In LOWER (φ −48.5) the rod and the +Y LM8UU are on the lower
// side, 12.5 off the arm axis: the lower edge then clears the LM8UU by 2.5 (a full
// hub-to-tip hull reached into it).
crank_low = 2.5;
// arm + tip boss; its hub end (Ø14) lies well inside the Ø16 hub, so the swept pocket
// has no coincident arcs
module tilt_crank_arm_hull_2d() hull() {
    intersection() { circle(d = 14); translate([-10, -crank_low]) square([20, 20]); }
    translate([sg_crank_r(), 0]) intersection() { circle(d = 9); translate([-6, -crank_low]) square([12, 12]); }
}
module tilt_crank_arm_2d() { translate([sg_crank_r(), 0]) circle(d = 9); tilt_crank_arm_hull_2d(); }
module tilt_crank_2d() { circle(d = 16); tilt_crank_arm_2d(); }
module tilt_crank() {      // modelled pointing +X from D, in the crank slab
    cy = sg_crank_y();
    translate([D[0], cy[1], D[1]]) rotate([90, 0, 0]) difference() {
        linear_extrude(cy[1] - cy[0]) tilt_crank_2d();
        translate([0, 0, -1]) rex_bore(cy[1] - cy[0] + 2);
        translate([sg_crank_r(), 0, -1]) cylinder(d = 3.2, h = 10, $fn = 20);
    }
}
module tilt_link() {       // modelled from the origin along +X, in the link slab
    ly = sg_link_y();
    translate([0, ly[1], 0]) rotate([90, 0, 0]) difference() {
        hull() { cylinder(d = sg_link_w(), h = ly[1] - ly[0]); translate([sg_link_l(), 0, 0]) cylinder(d = sg_link_w(), h = ly[1] - ly[0]); }
        translate([0, 0, -1]) cylinder(d = 3.2, h = 10, $fn = 20);
        translate([sg_link_l(), 0, -1]) cylinder(d = 3.1, h = 10, $fn = 20);   // on the Ø3 pin-A dowel
    }
}
// Crank ↔ link pivot: M3 × 16 SHCS + M3 nylock (DIN 985, 5.5 AF × 4), modelled in the
// crank frame (crank pointing +X from D, like tilt_crank()). Head (Ø5.5 × 3) on the
// crank's +y face, nylock on the link's −y face: grip = crank 4.5 + 1.0 gap + link 4.5
// = 10, nut 4, 2 mm of thread past the nut. The nut is a round Ø6.4 envelope (across
// corners) so the check holds at any nut rotation. Assembled on the bench before the
// crank goes into the sled pocket (§13.2); `shuttle_check.py` sweeps it through every
// pose (≥ 0.5 to carriage, TF and cell) and checks its length and bench tool access.
pivot_hw = [5.5, 3.0, 6.4, 4.0, 16];   // head Ø, head h, nut Ø (corners), nut h, screw length
module tilt_pivot_hw() color("DimGray") {
    cy = sg_crank_y(); ly = sg_link_y(); T = [D[0] + sg_crank_r(), D[1]];
    cyl_y(T, pivot_hw[0], cy[1], cy[1] + pivot_hw[1], 24);              // SHCS head
    cyl_y(T, 3.0, cy[1] - pivot_hw[4], cy[1], 16);                      // shank, y 2..18
    cyl_y(T, pivot_hw[2], ly[0] - pivot_hw[3], ly[0], 24);              // nylock, y 4..8
}

// =====================================================================
// ch2 shuttle crank (servo horn) and link — XY plane under the deck
// =====================================================================
// Joints (see shuttle_geom.scad for the Z stack): both link pivots are a 4 mm
// shoulder screw (M3 × 4 thread, head ≤ Ø8 × 4) dropped in from above: the
// shoulder journals in the upper member (crank tip Ø4.1 / carriage arm Ø4.1),
// the thread goes into an M3 × 4 heat-set insert pressed into the link top
// (Ø4.0 through, flush). Nothing protrudes below the link (Z 9).
// Horn: 4 × M2 × 6 countersunk self-tappers up into the horn disc + the centre
// M3 × 12 countersunk into the spline (4.9 mm engagement), all flush with the crank bottom.
//
// !! ch2 DIRECTION — CHECK BEFORE THE CRANK GOES ON !!
// The firmware (hardware/shuttle.py SHUTTLE_ANGLES) assumes servo angle = crank angle
// ψ, with ψ 0 = crank pointing +Y (reject), 90 = −X, 180 = −Y (column 0): increasing
// angle must turn the crank COUNTER-CLOCKWISE SEEN FROM ABOVE (= clockwise looking at
// the spline of the upside-down servo). MG996R clones differ. On the bench, with only
// the bare horn on, command 2°, 90°, 178° (calibrate_servos.py) and watch the horn; if
// it turns the other way, do NOT fit the crank: set "invert": {"2": true} in
// config/shuttle_calibration.json (hardware/shuttle.py then writes actuation_range − ψ;
// calibrate_servos.py menu item d does this check and writes it). A reversed servo
// without invert drives the crank into the end post.
assert(abs(sg_c2_psi(sg_target_y("reject"))) < 3 && abs(sg_c2_psi(sg_target_y(0)) - 180) < 3
       && sg_c2_tip(sg_target_y(1))[0] < sg_c2_pivot()[0],
       "ch2 convention changed: psi 0 must point +Y (reject), 180 −Y (column 0), the crank must swing through −X");
c2_horn_holes = [for (a = [45 : 90 : 315]) 7 * [cos(a), sin(a)]];
module c2_crank() {        // modelled pointing +Y from the pivot (psi = 0)
    z = sg_c2_z(); r = sg_c2_r();
    translate([0, 0, z[0]]) difference() {
        hull() { cylinder(d = 20, h = z[1] - z[0]); translate([0, r, 0]) cylinder(d = 12, h = z[1] - z[0]); }
        // horn screws: M2 countersunk (Ø3.8 head) + centre M3 countersunk (Ø6 head)
        for (p = c2_horn_holes) translate(p) {
            translate([0, 0, -1]) cylinder(d = 2.0, h = 10, $fn = 16);
            translate([0, 0, -eps]) cylinder(d1 = 4.2, d2 = 1.8, h = 1.2, $fn = 20);
        }
        translate([0, 0, -1]) cylinder(d = 3.3, h = 10, $fn = 20);
        translate([0, 0, -eps]) cylinder(d1 = 6.6, d2 = 3.0, h = 1.8, $fn = 24);
        // tip: Ø4.1 journal for the shoulder screw
        translate([0, r, -1]) cylinder(d = 4.1, h = 10, $fn = 24);
        // lightening slots
        for (t = [30, 70, 105]) hull() for (dy = [0, 22]) translate([0, t + dy, -1]) cylinder(d = 5, h = 10);
    }
}
module c2_link() {         // modelled from the origin along +Y
    z = sg_c2_link_z(); l = sg_c2_l();
    translate([0, 0, z[0]]) difference() {
        hull() { cylinder(d = 11, h = z[1] - z[0]); translate([0, l, 0]) cylinder(d = 11, h = z[1] - z[0]); }
        for (y = [0, l]) translate([0, y, -1]) cylinder(d = 4.0, h = 10, $fn = 24);   // M3 × 4 inserts from the top
        for (t = [25, 75, 120]) hull() for (dy = [0, 18]) translate([0, t + dy, -1]) cylinder(d = 4.5, h = 10);
    }
}
// ---- ch2 hardware (modelled for the collision sweep) ----
// shoulder screw standing on a member top at Z zt: head above, shoulder of length sl
// below, M3 × 4 thread + insert in the link under it
module c2_shoulder_screw(zt, sl) {
    sh = sg_c2_sh();
    color("DarkGray") {
        translate([0, 0, zt]) cylinder(d = sh[1], h = sh[2], $fn = 24);
        translate([0, 0, zt - sl]) cylinder(d = sh[0], h = sl + eps, $fn = 20);
        translate([0, 0, zt - sl - 4]) cylinder(d = 3, h = 4 + eps, $fn = 16);
    }
    color("Goldenrod") translate([0, 0, zt - sl - 4]) difference() {
        cylinder(d = 4.0, h = 4, $fn = 20); translate([0, 0, -1]) cylinder(d = 3, h = 6, $fn = 16);
    }
}
// horn screws, crank frame (countersunk heads 0.2 below the crank bottom face)
module c2_horn_screws() color("DarkGray") translate([0, 0, sg_c2_z()[0] + 0.2]) {
    for (p = c2_horn_holes) translate(p) { cylinder(d1 = 3.8, d2 = 2, h = 0.9, $fn = 16); cylinder(d = 2, h = 6, $fn = 12); }
    cylinder(d1 = 6.0, d2 = 3, h = 1.5, $fn = 20); cylinder(d = 3, h = 12, $fn = 16);   // M3 × 12: 4.9 into the spline
}
// tip pivot, crank frame
module c2_tip_pin() translate([0, sg_c2_r(), 0]) c2_shoulder_screw(sg_c2_z()[1], sg_c2_sh_l()[0]);
// drive-pin pivot, carriage frame
module c2_drive_pin() translate([sg_c2_pivot()[0], sg_c2_pin_dy(), 0]) c2_shoulder_screw(sg_c2_arm_z()[1], sg_c2_sh_l()[1]);
// ch2 servo ear screws: M2.5 × 10 button-head hex socket (ISO 7380, head Ø4.7 × 1.5,
// modelled Ø4.5 × 1.8), self-threading up into Ø2.1 pilots: front ear into the solid
// block / lug of riser_b, rear ear into the end-post shelf. Driven from BELOW with a
// 1.5 mm L-key, short arm up (rear: on the bench; front: through the riser tunnel,
// crank parked at ψ ≈ 100°) — see the install order at the end of this file.
module c2_ear_screws_at(y) color("DarkGray")
    for (x = [75, 85]) translate([x, y, sg_c2_face_z() + 8.1 - 1.8]) {
        cylinder(d = 4.5, h = 1.8, $fn = 16); cylinder(d = 2.5, h = 10, $fn = 12);
    }
module c2_ear_screws() for (y = sg_c2_ear_y()) c2_ear_screws_at(y);


// =====================================================================
// R-BAR (fixed lower-mode fulcrum) + end posts
// =====================================================================
nb = sg_rbar_notch_y();
// The bar spans end post to end post (Y −150..232). 9 × 17 PLA: mid-span sag
// under the 0.3 N skid load ≈ 0.04 mm, so no intermediate supports (nothing
// fixed may stand inside the carriage's travel envelope anyway).
// Two prints joined by a 32 mm lap splice at Y −16..16 (lower half-depth from
// the −Y half, upper from the +Y half: the contact top stays one piece there).
// The bar is 9 wide (X 95..104: 1.4 walls round the counterbores); 2 × M3 × 10
// SHCS at Y ±10, heads 0.3 below the top, down into M3 × 5.7 heat-set inserts. The skids land on the bar at Y ±(1..4)
// (columns 1/2), clear of the counterbores (|Y| ≥ 6.9).
rb_split_z = 64.5;
rb_lap = 16;
rb_bolt = [99.5, 10];        // splice bolts at (X, ±Y)
function rb_top() = sg_SJ()[1] - sg_skid_r() - 0.3;          // skid hovers 0.3 above the bar in HOLD
module rbar_raw(y0, y1) {
    xb = sg_rbar_x(); zt = rb_top();
    difference() {
        union() {
            translate([xb[0], y0, sg_rbar_z0()]) cube([xb[1] - xb[0], y1 - y0, zt - sg_rbar_z0()]);
            // home ledges under the skids (LEVEL hard stop)
            for (s = [-1, 1]) let(a = max(y0, s > 0 ? nb[0] : -nb[1]), b = min(y1, s > 0 ? nb[1] : -nb[0]))
                if (b > a) translate([xb[1] - eps, a, 59]) cube([110 - xb[1], b - a, S0[1] - sg_skid_r() - 59]);
        }
        // home notches: skids and plate tails pass down to LEVEL
        for (s = [-1, 1]) translate([xb[0] - 1, s > 0 ? nb[0] : -nb[1], S0[1] - sg_skid_r() - 1])
            cube([xb[1] - xb[0] + 2, nb[1] - nb[0], 20]);
        // round the front-top (fulcrum) edge R1
        translate([xb[1] - 1, y0 - 1, zt - 1]) difference() {
            cube([2, y1 - y0 + 2, 2]);
            rotate([-90, 0, 0]) cylinder(r = 1, h = y1 - y0 + 2, $fn = 16);
        }
    }
}
module rbar_neg() difference() {          // Y −150..16, lower half only over the lap
    rbar_raw(sg_rbar_y()[0], rb_lap);
    translate([90, -rb_lap, rb_split_z]) cube([20, 2 * rb_lap + 1, 20]);
    for (s = [-1, 1]) translate([rb_bolt[0], s * rb_bolt[1], rb_split_z - 7]) cylinder(d = 4.0, h = 8, $fn = 20);
}
module rbar_pos() difference() {          // Y −16..232, upper half only over the lap
    rbar_raw(-rb_lap, sg_rbar_y()[1]);
    translate([90, -rb_lap - 1, 40]) cube([20, 2 * rb_lap + 1, rb_split_z - 40]);
    for (s = [-1, 1]) translate([rb_bolt[0], s * rb_bolt[1], rb_split_z - 1]) {
        cylinder(d = 3.4, h = 20, $fn = 16);
        translate([0, 0, rb_top() - 3.3 - rb_split_z + 1]) cylinder(d = 6.2, h = 5, $fn = 24);
    }
}

// End posts → baseplate: M3 SHCS down through the floor plate on the 30 mm
// baseplate grid, washer + nut under the board: plate 4 + tile 4 + 6 mm board +
// washer + nut → M3 × 20. −Y post: (110, −225) behind the ch1 servo, (140, −195),
// (140, −165); +Y post: (110, 225), (110, 255), (140, 255).
ep_neg_holes = [[110, -225], [140, -195], [140, -165]];
ep_pos_holes = [[110, 225], [110, 255], [140, 255]];
function sh_end_post_holes() = concat(ep_neg_holes, ep_pos_holes);
function sh_pin_a_y() = pinA_y;
function sh_tilt_pivot_hw() = pivot_hw;   // ch1 crank-link M3 × 16 + nylock: head Ø, head h, nut Ø, nut h, length
// Rod: 400 mm, Y −160..240 (through the −Y post, 8 mm into the +Y post). Each post
// holds it with a SIDE grub screw: M3 × 5.7 heat-set insert pressed into the post's
// +X face (X 116 → 110.3) on the rod's centre height, M3 × 6 flat-point set screw
// through it onto the rod (tip on the rod at X 110, end flush with the face),
// driven along −X with a 1.5 mm hex key from the open +X side.
function sh_rod_y() = [sg_rod_y()[0], sg_rod_y()[1] + 8];
function sh_rod_grubs() = [[116, sg_rod_y()[0] + 5, rod[1]], [116, sg_rod_y()[1] + 5, rod[1]]];   // insert mouth (X, Y, Z)
module rod_grub_hole(y) translate([116 + 1, y, rod[1]]) rotate([0, -90, 0]) {
    cylinder(d = 4.0, h = 1 + 5.7, $fn = 24);              // M3 × 5.7 insert from the +X face
    cylinder(d = 3.2, h = 1 + 116 - rod[0], $fn = 16);     // set-screw clearance into the rod bore
}
// −Y end block: rod / shaft (688ZZ) / R-bar post + ch1 servo cage + ch2 rear ear shelf.
// Everything at X < 90 stays above Z 21 (ch2 crank + tip screw sweep below Z 23
// only along |X − 80| ≤ 10); everything at Y > −150 stays at X < 91 (carriage
// at column 0 reaches Y −147.5).
// ch1 (see c1_servo): cage Y −193.1..−185.1 with the servo's ears on its −Y face;
// the bought coupler sits in the open bay Y −184.2..−167.2 between the cage and the
// post (7.2 mm to the post's outer face, 1.2 to the ch2 gusset), its clamp screw
// reached from ABOVE (nothing over the bay). The bay is closed at the sides by the
// ch2 wall (X 91..94, to Z 58) and a low rib (X 116..120, to Z 30, under the
// coupler's swept boss which never comes below Z 32).
// print_aid = true adds a free-standing break-away support ladder under the ch2
// rear-ear ledge (see the header); the assembly and the checks use print_aid = false.
module end_post_neg(print_aid = false) {
    y0 = sg_rod_y()[0];       // −160: post Y −160..−150
    yc = [c1_yf - 8.1, c1_yf - 0.1];                                        // cage Y −193.1..−185.1
    sz = sg_c2_shelf_z(); sy = [sg_c2_ear_end_y()[1] - 4.5, sg_c2_body_y()[1] - 0.5];   // shelf Y −166..−155
    difference() {
        union() {
            translate([93, y0, 4]) cube([23, 10, sg_SJ()[1] - 4]);          // post
            translate([90, -229, 4]) cube([30, 229 + y0 + 10, 4]);          // floor plate Y −229..−150
            translate([119.9, -201, 4]) cube([26.1, 43, 4]);                // tongue to the X 140 holes
            translate([90, yc[0], 4]) cube([30, yc[1] - yc[0], 81]);        // ch1 cage, to Z 85
            translate([91, yc[0], 4]) cube([3, y0 + 10 - yc[0], 54]);       // ch2 wall (1.75 off the crank), cage → post
            translate([116 - eps, yc[1] - eps, 4]) cube([4 + eps, y0 - yc[1], 26]);   // +X rib, cage → post (Z ≤ 30)
            translate([68, sy[0], sz]) cube([26, sy[1] - sy[0], 3.4]);     // ch2 rear ear shelf (0.5 off the case)
            // gusset web beside the ear (Y −166..−162): 45° underside from the wall
            // (prints without support; ≥ 2.1 above the crank body, which is the only
            // thing sweeping under it: the tip screw never reaches Y −166..−162),
            // tapering top back to the wall at Z 58
            xz(sy[0], sg_c2_ear_end_y()[1] - 0.5) polygon([[94, 16], [94, 58], [69, sz + 3], [69, sz + 0.5], [94 - (sz + 0.5 - 16), sz + 0.5]]);
        }
        cyl_y(rod, 8.05, y0 - 1, y0 + 11);                                   // rod end
        rod_grub_hole(y0 + 5);
        cyl_y(D, 10, y0 - 1, y0 + 11);                                       // shaft through
        cyl_y(D, 16.05, y0 + 5, y0 + 11, 48);                                // 688ZZ pocket (inner side)
        // ch1: opening for the case nose (19.7 × 40.7 + 0.3 all round) and 4 inserts
        // pressed into the cage's −Y (ear) face, Ø3.2 relief beyond (blind, 0.5 from the face)
        translate([D[0] - 10.15, yc[0] - 1, D[1] - 10.5]) cube([20.3, yc[1] - yc[0] + 2, 41.3]);
        for (p = c1_ear_holes) { cyl_y(p, 4.0, yc[0] - 1, yc[0] + 6, 24); cyl_y(p, 3.2, yc[0] + 5.9, yc[1] - 0.5, 16); }
        for (p = ep_neg_holes) translate([p[0], p[1], 0]) cylinder(d = 3.4, h = 20, $fn = 16);
        for (x = [75, 85]) translate([x, sg_c2_ear_y()[1], sz - 4.2])
            cylinder(d = 2.1, h = 10, $fn = 16);                              // ch2 ear screws (M2.5)
        translate([sg_rbar_x()[0] - 0.1, y0 + 6, sg_rbar_z0() - 0.1]) cube([sg_rbar_x()[1] - sg_rbar_x()[0] + 0.2, 5, 30]); // R-bar end seat
    }
    // break-away ladder under the rear-ear ledge (print only): 0.8 walls, 0.2 gap
    // under the ledge (one 0.2 layer), stands on the bed beside the post
    if (print_aid) translate([0, 0, 4]) linear_extrude(sz - 0.2 - 4) difference() {
        translate([70.5, sy[0] + 4.5]) square([19, 6]);                    // X 70.5..89.5, Y −161.5..−155.5 (0.5 off the floor plate)
        for (i = [0 : 3]) translate([71.3 + 4.55 * i, sy[0] + 5.3]) square([3.75, 4.4]);
    }
}
module end_post_pos() {
    y1 = sg_rod_y()[1];       // 232: post Y 232..242
    difference() {
        union() {
            translate([93, y1, 4]) cube([23, 10, sg_SJ()[1] - 4]);
            translate([104, 219, 4]) cube([18, y1 - 219 + eps, 4]);          // tongue to the Y 225 hole (under the carriage path, Z ≤ 8)
            translate([90, y1, 4]) cube([32, 261 - y1, 4]);
            translate([121.9, 249, 4]) cube([24.1, 12, 4]);                  // tongue to the X 140 hole
        }
        cyl_y(rod, 8.05, y1 - 1, y1 + 11);
        rod_grub_hole(y1 + 5);
        cyl_y(D, 10, y1 - 1, y1 + 11);
        cyl_y(D, 16.05, y1 - 1, y1 + 5, 48);                                 // 688ZZ pocket (inner side)
        translate([sg_rbar_x()[0] - 0.1, y1 - 1, sg_rbar_z0() - 0.1]) cube([sg_rbar_x()[1] - sg_rbar_x()[0] + 0.2, 5, 30]);
        for (p = ep_pos_holes) translate([p[0], p[1], 0]) cylinder(d = 3.4, h = 20, $fn = 16);
    }
}


// =====================================================================
// Reference (bought) parts
// =====================================================================
module load_cell() color("Silver") translate([cxc - 23.5, -6, czt - 6]) difference() {
    cube([47, 12, 6]);
    for (x = [3.5, 43.5]) for (y = [3, 9]) translate([x, y, -1]) cylinder(d = 3, h = 8, $fn = 12);
}
// ---- bought hardware, modelled so shuttle_check.py can test every part against every other ----
// LM8UU (Ø8 / Ø15 × 24), carriage frame: one per sled pocket, 0.05 off the pocket floor
module sh_lm8uu() color("Silver") for (s = [-1, 1]) {
    y0 = s > 0 ? sled_hw - 24.05 : -sled_hw + 0.05;
    difference() { cyl_y(rod, 15, y0, y0 + 24, 48); cyl_y(rod, 8, y0 - 1, y0 + 25, 24); }
}
// 688ZZ (Ø8 / Ø16 × 5), fixed: one per end post, seated on its pocket shoulder
module sh_688zz() color("Silver") for (y0 = [sg_rod_y()[0] + 5, sg_rod_y()[1]])
    difference() { cyl_y(D, 16, y0, y0 + 5, 48); cyl_y(D, 8, y0 - 1, y0 + 6, 48); }
// cheek → sled: M3 × 10 countersunk (ISO 10642: Ø6.7 × 1.85 head, 90°) from each outer
// face, and the Ø3 × 8 dowels bottomed in the sled's Ø2.9 holes (6 deep), carriage frame
module sh_cheek_screws() color("DarkGray") for (s = [-1, 1], p = cheek_screws) {
    yo = s > 0 ? chy[1] : -chy[1];
    translate([p[0], yo, p[1]]) rotate([s > 0 ? -90 : 90, 0, 0]) translate([0, 0, -1.85])
        cylinder(d1 = 3.0, d2 = 6.7, h = 1.85, $fn = 24);
    cyl_y(p, 3.0, s > 0 ? chy[1] - 10 : -chy[1], s > 0 ? chy[1] : -chy[1] + 10, 16);
}
module sh_cheek_dowels() color("LightSteelBlue") for (s = [-1, 1], p = cheek_dowels)
    cyl_y(p, 3.0, s > 0 ? sled_hw - 6 : -sled_hw - 2, s > 0 ? sled_hw + 2 : -sled_hw + 6, 16);
// load-cell screws, TF frame: 2 × M3 × 12 SHCS up through the TF crossbar into the cell's
// tapped end (head in the Ø6.2 counterbore, top at Z 68), 2 × M3 × 10 SHCS up through the
// cell's free end into the cradle's inserts (head under the cell)
module sh_cell_screws() color("DarkGray") for (y = [-3, 3]) {
    translate([cxc + 20, y, 65]) { cylinder(d = 5.5, h = 3, $fn = 24); cylinder(d = 3, h = 3 + 12, $fn = 16); }
    translate([cxc - 20, y, czt - 9]) { cylinder(d = 5.5, h = 3, $fn = 24); cylinder(d = 3, h = 3 + 10, $fn = 16); }
}
// rod set screws, fixed: M3 × 6 flat point in each end post's +X-face insert, tip on the rod
module sh_rod_grub_screws() color("DarkGray") for (g = sh_rod_grubs())
    translate([rod[0] + 4, g[1], g[2]]) rotate([0, 90, 0]) cylinder(d = 3, h = 6, $fn = 16);
module mg996r() color("DimGray") {    // origin = output spline axis at the top face, body below (−Z)
    translate([-10.2, -9.85, -36.6]) cube([40.7, 19.7, 36.6]);
    translate([-17.2, -9.85, -10.6]) cube([54.7, 19.7, 2.5]);   // ears
    cylinder(d = 6, h = 4);
}
// ---- ch1 tilt servo + coupler (−Y end; numbers in shuttle_geom.scad) ----
// MG996R spline on the shaft axis, case face at Yf = −185, body toward −Y, mounted
// LONG SIDE UP (rotated 180° about its own output axis: body Z 33.8..74.5, ears
// Z 26.8..81.5, ear holes at X 100/110, Z 29.5/78.5), so nothing is near the floor
// plate. Its ears sit on the −Y face of the cage (Y −193.1..−185.1) and are held by
// 4 × M3 × 10 SHCS + washers driven along +Y from BEHIND the servo into M3 × 5.7
// heat-set inserts in the cage. The case nose (Yf−8.1..Yf) sits in the cage opening.
c1_yf = sg_c1_face_y();
c1_ear_holes = [for (x = [100, 110], z = [29.5, 78.5]) [x, z]];
c1_rng = [-80, 55];        // coupler boss direction range (shaft φ −48.5..22.2 ± 30° hex indexing)
module c1_servo() translate([D[0], c1_yf, D[1]]) rotate([0, 180, 0]) rotate([-90, 0, 0]) rotate(90) mg996r();
// goBILDA 4001-0025-4008 clamping servo-to-shaft coupler (25T → 8 mm REX), simplified
// from the goBILDA STEP: Ø13.8 × 17 body + clamp boss (to 9.7 from the axis, ±6.9,
// last 8.5 mm) that carries the M4 clamp screw tangentially (6.2 off the axis).
// a = boss direction in the XZ plane (same sense as the crank angle φ).
// swept = true: envelope over every boss direction in c1_rng (for collision checks).
module c1_boss_2d(a) rotate(a) translate([0, -6.9]) square([9.66, 13.8]);
module c1_coupler(a = 0, swept = false) color("Silver") {
    c = sg_c1_cpl(); y0 = sg_c1_cpl_y()[0];
    cyl_y(D, 2 * c[2], y0, y0 + c[1], 40);
    translate([D[0], y0 + c[1], D[1]]) rotate([90, 0, 0]) linear_extrude(8.5)
        if (swept) for (b = [c1_rng[0] : 5 : c1_rng[1] - 5]) hull() { c1_boss_2d(b); c1_boss_2d(b + 5); }
        else c1_boss_2d(a);
}
// clamp-screw axis for boss direction a: point on the axis (X, Y, Z) and unit direction
// toward the head (head side = +90° from the boss direction)
function sh_c1_clamp(a) = [[D[0] + 6.16 * cos(a), sg_c1_cpl_y()[0] + 13, D[1] + 6.16 * sin(a)], [-sin(a), 0, cos(a)]];
// ch1 ear screws: M3 × 10 SHCS (head Ø5.5 × 3) + M3 washer (Ø7 × 0.5) on the ear's −Y face
module c1_ear_screws() color("DarkGray") for (p = c1_ear_holes) {
    ye = c1_yf - 10.6;                                     // ear −Y face
    cyl_y(p, 7, ye - 0.5, ye, 20); cyl_y(p, 5.5, ye - 3.5, ye - 0.5, 20); cyl_y(p, 3, ye - 0.5, ye - 0.5 + 10, 12);
}
function sh_c1_ear_holes() = c1_ear_holes;
// ch2 servo hanging upside down, case face at sg_c2_face_z(), body toward −Y
module c2_servo() translate([sg_c2_pivot()[0], sg_c2_pivot()[1], sg_c2_face_z()]) rotate([180, 0, 0]) rotate(90) mg996r();
// MG996R 25T round horn (Ø25 × 1.4 disc + Ø10 spline hub) between crank and case;
// the crank bolts to the disc (4 × M2 on Ø14) and the horn screw goes through the crank hub
module c2_horn() color("WhiteSmoke") translate([sg_c2_pivot()[0], sg_c2_pivot()[1], sg_c2_z()[1]]) {
    cylinder(d = 25, h = 1.4, $fn = 48);
    cylinder(d = 10, h = sg_c2_face_z() - sg_c2_z()[1] - 0.4, $fn = 32);
}
module rod8(p, y0, y1) color("LightSteelBlue") cyl_y(p, 8, y0, y1, 24);
// ch1 tilt shaft: 8 mm REX (goBILDA 2106-4008-4320) cut to 417 mm, Y −175.2..241.8
module rex_shaft(y0 = sg_rex_shaft_y()[0], y1 = sg_rex_shaft_y()[1]) color("LightSteelBlue")
    translate([D[0], y0, D[1]]) rotate([-90, 0, 0]) linear_extrude(y1 - y0) rex_2d();
module card_on_bed(front_x = 154) color("Ivory", 0.9)
    translate([front_x - 88, -31.5, bz + 0.02]) cube([88, 63, 0.33]);

// =====================================================================
// Posing
// =====================================================================
module tf_pose(st) {
    if (st == "level") children();
    else if (st == "hold" || st == "upper")
        translate([F[0], 0, F[1]]) rotate([0, sg_bed_angle(st), 0]) translate([-F[0], 0, -F[1]]) children();
    else {   // lower: hold about F, then about the skid
        S = sg_SJ();
        translate([S[0], 0, S[1]]) rotate([0, sg_dl_lower(), 0]) translate([-S[0], 0, -S[1]])
        translate([F[0], 0, F[1]]) rotate([0, sg_th_hold(), 0]) translate([-F[0], 0, -F[1]]) children();
    }
}
module tilt_drive_posed(st) {
    phi = sg_crank_phi(st); T = sg_crank_tip(st); Ap = sg_pose(A, st);
    translate([D[0], 0, D[1]]) rotate([0, -phi, 0]) translate([-D[0], 0, -D[1]]) { tilt_crank(); tilt_pivot_hw(); }
    translate([T[0], 0, T[1]]) rotate([0, -atan2(Ap[1] - T[1], Ap[0] - T[0]), 0]) tilt_link();
}
module c2_posed(yc) {
    P = sg_c2_pivot(); psi = sg_c2_psi(yc); T = sg_c2_tip(yc);
    pin = [P[0], yc + sg_c2_pin_dy()];
    translate([P[0], P[1], 0]) rotate(psi) { color("Orange") c2_crank(); c2_horn_screws(); c2_tip_pin(); }
    color("Gold") translate([T[0], T[1], 0]) rotate(atan2(pin[1] - T[1], pin[0] - T[0]) - 90) c2_link();
    translate([0, yc, 0]) c2_drive_pin();
}

// Moving shuttle group at carriage Y = yc (cradle + card + TF + cell + carriage + crank/link)
module f_pins() for (s = [-1, 1]) color("LightSteelBlue") cyl_y(F, 4, s > 0 ? tfy[0] : -44, s > 0 ? 44 : -tfy[0], 16);
module pin_a() color("LightSteelBlue") cyl_y(A, 3, pinA_y[0], pinA_y[1], 16);
module shuttle_moving(yc, st, show_card = true) translate([0, yc, 0]) {
    color("SteelBlue") carriage();
    sh_lm8uu(); sh_cheek_screws(); sh_cheek_dowels();
    color("Tomato") tilt_drive_posed(st);
    tf_pose(st) {
        color("MediumSeaGreen") tilt_frame();
        load_cell(); sh_cell_screws();
        color("Khaki") cradle();
        if (show_card) card_on_bed();
        f_pins(); pin_a();
    }
}
module shuttle_fixed() {
    color("Peru") { rbar_neg(); rbar_pos(); }
    color("SandyBrown") { end_post_neg(); end_post_pos(); }
    rod8(rod, sh_rod_y()[0], sh_rod_y()[1]);
    rex_shaft();
    sh_688zz(); sh_rod_grub_screws();
    // ch1: servo (case face Y −185, long side up), bought coupler (boss at HOLD), ear screws
    c1_servo();
    c1_coupler(sg_crank_phi("hold"));
    c1_ear_screws();
    c2_servo();
    c2_horn();
    c2_ear_screws();
}

// ==== PUBLIC: everything at the belt end, machine coordinates ====
//   col: 0..3, "reject" or "home";  floor_state: "level" | "hold" | "upper" | "lower"
//   (at a column, "level" is not reachable — the R-bar turns it into "lower";
//    at home, "lower" is not reachable — the notches turn it into "level")
module asm_sorter_end(col = "home", floor_state = "hold", show_card = true) {
    yc = sg_target_y(col);
    if (col != "home" && floor_state == "level") echo("WARNING: level is only reachable at home");
    if (col == "home" && floor_state == "lower") echo("WARNING: lower is only reachable at a column");
    shuttle_moving(yc, floor_state, show_card);
    shuttle_fixed();
    c2_posed(yc);
    asm_lower_ramp();
    asm_reject_bin();
}
function shuttle_tray_x0() = sg_tray_x0();   // tray open back face → translate([178 + 98, -137, 4]) rotate(90)

// ---------- export / preview ----------
// Every part exports in its assembly pose; the print orientation is in the header.
if (part == "assembly")     asm_sorter_end(show_col, show_state);
if (part == "cradle")       cradle();
if (part == "tilt_frame")   tilt_frame();
// "carriage" is NOT a print: the carriage is 3 prints (sled, cheek_neg, cheek_pos).
assert(part != "carriage", "part=\"carriage\" is the assembled preview, not a print: export sled, cheek_neg and cheek_pos (or carriage_preview to look at it)");
if (part == "carriage_preview") carriage();
if (part == "sled")         sled();
if (part == "cheek_neg")    cheek(-1);
if (part == "cheek_pos")    cheek(1);
if (part == "tilt_crank")   tilt_crank();
if (part == "tilt_link")    tilt_link();
if (part == "c2_crank")     c2_crank();
if (part == "c2_link")      c2_link();
if (part == "rbar_neg")     rbar_neg();
if (part == "rbar_pos")     rbar_pos();
if (part == "end_post_neg") end_post_neg(print_aid = true);   // incl. the break-away ledge support
if (part == "end_post_pos") end_post_pos();

// =============================================
// BOM (shuttle)
//  1  TAL221 mini load cell, 47 × 12 × 6, 4× M3 (±20 / ±3), cable end tapped
//       (owner's 50 g unit; SparkFun 100 g SEN-14727 is a drop-in)
//  1  8 mm smooth (h6, hardened) rod × 400 mm, e.g. Thomson 8MMSMAE L400MM
//       (Y −160..240: through the −Y post, 8 mm into the +Y post)
//  2  LM8UU (8 × 15 × 24), e.g. Adafruit 1181
//  1  8 mm REX shaft (Ø8 round ∩ 7 mm hex), goBILDA 2106-4008-4320 (432 mm,
//       stainless, E-clip not used), CUT TO 417 mm (Y −175.2..241.8; a hacksaw /
//       cut-off disc, deburr, chamfer 0.5):
//       https://www.gobilda.com/8mm-rex-shaft-with-e-clip-stainless-steel-432mm-length/
//  2  688ZZ (8 × 16 × 5), one per end post (shaft; the REX round lands run in them)
//  1  ch1 coupler: goBILDA 4001-0025-4008 "4001 Series Clamping Servo to Shaft
//       Coupler (25 Tooth Spline to 8mm REX Bore)", aluminium, Ø13.8 × 17, clamp
//       boss to r 11.9, M4 clamp screw included:
//       https://www.gobilda.com/4001-series-clamping-servo-to-shaft-coupler-25-tooth-spline-to-8mm-rex-bore/
//       + 1 M3 × 6 SHCS (coupler → MG996R spline, driven down the REX bore on the bench)
//       (replaces the earlier "25T disc horn + 8 mm flange coupling": no horn on ch1)
//  2  MG996R (ch1 tilt, ch2 shuttle; the two scrapped gate servos)
//  2  Ø4 × 8 mm steel dowel pins (F pins)
//  1  Ø3 × 20 mm steel dowel pin (tilt link pin A)
//  4  Ø3 × 8 mm steel dowel pins (cheek ↔ sled alignment)
//  1  0.1 mm skived PTFE tape, silicone adhesive, ≥ 75 mm wide (cradle bed + kick)
//  2  M3 × 12 SHCS (TF crossbar → cell tapped end)
//  2  M3 × 10 SHCS + 2 M3 × 5.7 heat-set inserts (cell free end → cradle boss)
//  6  M3 × 10 countersunk (ISO 10642) + 6 M3 × 5.7 heat-set inserts (cheeks → sled)
//  1  M3 × 16 SHCS + M3 nylock (ch1 crank–link pivot, made up on the bench; tilt_pivot_hw(),
//       swept through every pose and checked for length / tool access by shuttle_check.py)
//  2  shoulder screw, 4 mm shoulder, M3 × 4 thread, head ≤ Ø8 × 4: shoulder
//       5 mm (ch2 crank tip) and 6 mm (ch2 drive pin), e.g. ISO 7379-style
//       4 mm / M3 shoulder screws (MISUMI MSB4, McMaster 4 mm-shoulder M3)
//  2  M3 × 4 short heat-set inserts (≤ Ø4.6 OD), pressed flush into the ch2 link top
//  4  M2 × 6 countersunk self-tapping (c2 crank → horn disc, flush from below)
//  1  M3 × 12 countersunk (c2 crank hub → servo spline, ≈ 4.9 mm engagement)
//  (the tilt crank needs NO set screw: it slides along the shaft, keyed by its REX bore)
//  4  M3 × 10 SHCS + 4 M3 washers + 4 M3 × 5.7 heat-set inserts (ch1 MG996R ears →
//       −Y cage, driven along +Y from behind the servo; ear grommets removed)
//  4  M2.5 × 10 button-head hex socket (ISO 7380), self-threading into Ø2.1 pilots
//       (ch2 ears: 2 into the end-post shelf, 2 into riser_b's ear block / lug)
//  1  MG996R Ø25 round 25T horn (in the servo bag) between the ch2 crank and the servo
//  2  M3 × 10 SHCS + 2 M3 × 5.7 inserts (R-bar lap splice)
//  2  M3 × 6 flat-point set screws + 2 M3 × 5.7 heat-set inserts (rod grub screws,
//       one in each end post's +X face)
//  6  M3 × 20 SHCS + washers + nuts (end posts → baseplate, 3 per post)
// =============================================
//
// INSTALL ORDER (every insertion and driving path is checked by
// `cad/shuttle_check.py assembly`, step numbers as printed there):
//  0. Riser (riser.scad) bolted down, BEFORE the conveyor.
//  1. Bench, −Y end post: press the 4 cage inserts (−Y face) and the rod-grub
//     insert. Power ch1 to HOLD = 97° and press the goBILDA coupler onto the spline
//     at the tooth that puts two flats of its hex bore parallel to the crank arm at
//     HOLD, i.e. 7° up from horizontal toward +X (the tilt crank's REX bore has its
//     flats parallel to the arm); 25T × hex gives ≤ 0.6° error. M3 × 6 down its bore.
//     Turn the clamp boss UP (servo off, by hand) and push servo + coupler nose-first along
//     +Y through the cage opening; ears on the cage's −Y face; 4 × M3 × 10 + washers
//     along +Y from behind the servo (2.5 mm hex driver).
//  2. Bench, module: 688ZZ in both posts; rod through post −Y, carriage (LM8UU),
//     post +Y; tilt crank in the sled pocket (§13.2, on the bench before the TF and
//     cheeks: crank + link joined, crank pointing +X, slid hub-first along −X through
//     the pocket's front channel until the bore is on the shaft axis, then turned to
//     HOLD; the hex is turned to match the shaft); slide the REX shaft in from the +Y end
//     through post +Y, sled, crank, sled, post −Y into the coupler (8 mm deep).
//     Power ch1 to HOLD (97°), set the cradle 10° nose-down, tighten the coupler's
//     M4 clamp from ABOVE (3 mm key; the boss sits ±30° of horizontal-+X at HOLD
//     depending on the hex indexing, the screw head up). Residual ≤ 0.6° (25T ×
//     hex): trim in calibration. Rod set screws along −X from the +X side (1.5 mm
//     key). R-bar into its seats.
//  3. Bench, ch2: check the servo DIRECTION (see the ch2 section) first; horn →
//     crank (4 × M2), set ψ = 75.5° at home, hub screw M3 × 12. Then command / turn
//     the crank to ψ ≈ 100° (pointing −X, clear of the riser) and lift the servo
//     straight up under the −Y shelf; 2 rear-ear screws from below (1.5 mm L-key,
//     short arm up), left ONE TURN LOOSE.
//  4. Park the carriage at column 3 (Y ≈ 102: its drive-pin arm beyond the riser),
//     TF level. Set the whole module down 10 mm toward −Y of its place, then slide
//     it +Y: the ch2 front ear slides under riser_b's ear block (1 mm lead-in).
//  5. Tighten the rear-ear screws (servo up 0.5 onto both ceilings); front-ear
//     screws from below through the tunnel (1.5 mm L-key, ≥ 195° free swing).
//     End-post anchors 6 × M3 × 20 (the one at (110, 225) is under the rod: ball-end
//     key at 45° from +X).
//  6. ch2 link + the two shoulder-screw pivots (as before: crank tip at column 0,
//     drive pin at reject).
//  7. ramp_neg with the carriage at column 3, ramp_pos and the reject bin with the
//     carriage at column 0 (each lowered from above).
// =============================================
