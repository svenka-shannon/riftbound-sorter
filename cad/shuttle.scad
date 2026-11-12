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
//   tilt_frame    1×  PETG, 0.2, 4 walls, 40 %, upright (crossbar down), tree
//                     supports under the plate bottom edges + skid nubs; ream
//                     the F-pin holes Ø3.9 and press Ø4 × 8 dowels from inside;
//                     ream the pin-A bore Ø2.95 (see tilt_frame()).
//   sled          1×  PETG, 0.2, 4 walls, 40 %, on its +y face (bed ≈ 720 mm²):
//                     LM8UU pockets, D bushings and insert holes print as vertical
//                     holes, the ch2 arm has a 45° flank. Ream D bushings Ø8.3 and
//                     the drive-pin journal Ø4.0+. 6 × M3 × 5.7 inserts (cheeks).
//   cheek_neg / cheek_pos  1× each, PETG, 0.2, 4 walls, 40 %, flat on the outer
//                     face (bed ≈ 3560 mm², no overhangs; countersinks on the bed
//                     side are 45° cones). Bolt to the sled with 3 × M3 × 10
//                     countersunk + 2 × Ø3 × 8 dowels each.
//   tilt_crank / tilt_link  1× each, PETG 100 %, flat
//   c2_crank      1×  PETG, 0.2, 5 walls, 50 %, flat (155 mm), countersinks down
//   c2_link       1×  PETG, flat (173 mm); press the 2 × M3 × 4 inserts flush
//                     from the top
//   rbar_neg / rbar_pos  1× each, PLA, on the −X face, 4 walls; sand the top
//   end_post_neg / end_post_pos  1× each, PETG/PLA, 4 walls, 40 %, upright, no
//                     supports (ear shelf: 45° gusset web; 5 mm tip and a 7 mm
//                     side ledge print as short overhangs)
// HARDWARE: see the BOM block at the end of this file.
// =============================================

use <shuttle_geom.scad>
use <lower_ramp.scad>
use <reject_bin.scad>

/* [Export] */
part = "assembly";   // assembly | cradle | tilt_frame | carriage (preview) | sled | cheek_neg | cheek_pos | tilt_crank | tilt_link | c2_crank | c2_link | rbar_neg | rbar_pos | end_post_neg | end_post_pos
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
module tf_plate_2d()
    polygon([[103, 68], [104.5, 66], [107.5, 66], [112, 68.5], [140, 64], [160, 64],
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
            translate([140, -tfy[1], 64]) cube([18, 2 * tfy[1], 73.9 - 64]);
            // cell fixed-end pad (tapped end of the TAL221)
            translate([cxc + 16.5, -6, 73.9 - eps]) cube([7, 12, czt - 6 - 73.9 + eps]);
        }
        // F pin holes Ø3.9 (press Ø4 dowel)
        for (s = [-1, 1]) cyl_y(F, 3.9, -41, 41, 24);
        // cell screws into the tapped end: M3 × 12, clearance + head counterbore from
        // below (counterbore top Z 68: 1.7 below pin A's bore)
        for (y = [-3, 3]) translate([cxc + 20, y, 60]) {
            cylinder(d = 3.4, h = 30, $fn = 20);
            cylinder(d = 6.2, h = 68 - 60, $fn = 24);
        }
        // link slot (open below): 1.4 wall to the cell-screw counterbores
        translate([138, ly[0] - 0.5, 63]) cube([12.5, ly[1] - ly[0] + 1, 13]);
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
            polygon([[118, 71], [136, 67.5], [136, 76], [124, 76]]);
    }
}

// =====================================================================
// CARRIAGE — sled (rod + D-shaft) and two cheeks with the F hooks
// =====================================================================
// Three prints: the SLED (rod + D-shaft + ch1 crank pocket + ch2 drive-pin arm,
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
        for (s = [-1, 1]) cyl_y(rod, 15.1, s > 0 ? sled_hw - 24.1 : -sled_hw - 1, s > 0 ? sled_hw + 1 : -sled_hw + 24.1, 48);
        // D-shaft: Ø8.3 bushing bores at both ends (8 long), Ø10 relief in between
        cyl_y(D, 8.3, -sled_hw - 1, sled_hw + 1);
        cyl_y(D, 10, -sled_hw + 8, sled_hw - 8);
        // crank + link swing pocket (sector about D, −62°..45°)
        translate([0, ly[0] - 0.8, 0]) xz(0, cy[1] - ly[0] + 1.6)
            polygon(concat([D], [for (a = [-62 : 6 : 45]) D + 41 * [cos(a), sin(a)]]));
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
        // rod and D-shaft clearance (the root closes the LM8UU pocket: Ø10 < Ø15)
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
// ch1 tilt crank (on the D-shaft) and link
// =====================================================================
// The crank is captured in the sled's swing pocket and SLIDES along the fixed
// D-shaft with the carriage, so it is keyed by the D-bore only (no set screw).
module d_bore(h) difference() { cylinder(d = 8.15, h = h, $fn = 40); translate([3.55, -5, -1]) cube([5, 10, h + 2]); }
module tilt_crank() {      // modelled pointing +X from D, in the crank slab
    cy = sg_crank_y();
    translate([D[0], cy[1], D[1]]) rotate([90, 0, 0]) difference() {
        hull() { cylinder(d = 16, h = cy[1] - cy[0]); translate([sg_crank_r(), 0, 0]) cylinder(d = 9, h = cy[1] - cy[0]); }
        translate([0, 0, -1]) d_bore(cy[1] - cy[0] + 2);
        translate([sg_crank_r(), 0, -1]) cylinder(d = 3.2, h = 10, $fn = 20);
    }
}
module tilt_link() {       // modelled from the origin along +X, in the link slab
    ly = sg_link_y();
    translate([0, ly[1], 0]) rotate([90, 0, 0]) difference() {
        hull() { cylinder(d = 7, h = ly[1] - ly[0]); translate([sg_link_l(), 0, 0]) cylinder(d = 7, h = ly[1] - ly[0]); }
        translate([0, 0, -1]) cylinder(d = 3.2, h = 10, $fn = 20);
        translate([sg_link_l(), 0, -1]) cylinder(d = 3.1, h = 10, $fn = 20);   // on the Ø3 pin-A dowel
    }
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
// ch2 servo ear screws: M2.5 × 10 self-tappers, pan head Ø4.5 × 1.8 under the ears,
// up into the riser pocket ceiling (front ear) and the end-post shelf (rear ear)
module c2_ear_screws() color("DarkGray")
    for (y = sg_c2_ear_y()) for (x = [75, 85]) translate([x, y, sg_c2_face_z() + 8.1 - 1.8]) {
        cylinder(d = 4.5, h = 1.8, $fn = 16); cylinder(d = 2.5, h = 10, $fn = 12);
    }


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
// baseplate grid (X 110/140; Y −165/−195 and 225/255), washer + nut under the
// board: plate 4 + tile 4 + 6 mm board + washer + nut → M3 × 20.
ep_neg_holes = [[110, -165], [110, -195], [140, -165]];
ep_pos_holes = [[110, 225], [110, 255], [140, 255]];
function sh_end_post_holes() = concat(ep_neg_holes, ep_pos_holes);
function sh_pin_a_y() = pinA_y;
// −Y end block: rod / D-shaft (688ZZ) / R-bar post + ch1 servo cage + ch2 rear ear shelf.
// Everything at X < 90 stays above Z 21 (ch2 crank + tip screw sweep below Z 23
// only along |X − 80| ≤ 10); everything at Y > −150 stays at X < 91 (carriage
// at column 0 reaches Y −147.5).
module end_post_neg() {
    y0 = sg_rod_y()[0];       // −160: post Y −160..−150
    sz = sg_c2_shelf_z(); sy = [sg_c2_ear_end_y()[1] - 4.5, sg_c2_body_y()[1] - 0.5];   // shelf Y −166..−155
    difference() {
        union() {
            translate([93, y0, 4]) cube([23, 10, sg_SJ()[1] - 4]);          // post
            translate([90, -201, 4]) cube([30, 201 + y0 + 10, 4]);          // floor plate
            translate([119.9, -172, 4]) cube([26.1, 14, 4]);                // tongue to the X 140 hole
            translate([90, -185.6, 4]) cube([30, 6.9, 62]);                 // ch1 cage (ear plane)
            translate([91, -175, 4]) cube([3, 25, 54]);                     // ch2 wall (1.75 off the crank)
            translate([68, sy[0], sz]) cube([26, sy[1] - sy[0], 3.4]);     // ch2 rear ear shelf (0.5 off the case)
            // gusset web beside the ear (Y −166..−162): 45° underside from the wall
            // (prints without support; ≥ 2.1 above the crank body, which is the only
            // thing sweeping under it: the tip screw never reaches Y −166..−162),
            // tapering top back to the wall at Z 58
            xz(sy[0], sg_c2_ear_end_y()[1] - 0.5) polygon([[94, 16], [94, 58], [69, sz + 3], [69, sz + 0.5], [94 - (sz + 0.5 - 16), sz + 0.5]]);
            translate([90, -175, 4]) cube([6, 25, 4]);
        }
        cyl_y(rod, 8.05, y0 - 1, y0 + 11);                                   // rod end (M3 clamp screw from top)
        translate([rod[0], y0 + 5, rod[1]]) cylinder(d = 2.6, h = 40, $fn = 16);
        cyl_y(D, 10, y0 - 1, y0 + 11);                                       // D-shaft through
        cyl_y(D, 16.05, y0 + 5, y0 + 11, 48);                                // 688ZZ pocket (inner side)
        translate([95.15, -186, 13.3]) cube([19.7, 8, 41.1]);                // ch1 servo body opening
        translate([94.5, -179.1, 6]) cube([21, 3.5, 3]);                     // ch1 lower ear tip (Z 6.5) clears the plate
        for (x = [100, 110], z = [9.5, 58.5]) translate([x, -190, z]) rotate([-90, 0, 0])
            cylinder(d = 2.1, h = 15, $fn = 16);                              // ch1 ear screws, 4 × M2.5 self-tap
        for (p = ep_neg_holes) translate([p[0], p[1], 0]) cylinder(d = 3.4, h = 20, $fn = 16);
        for (x = [75, 85]) translate([x, sg_c2_ear_y()[1], sz - 4.2])
            cylinder(d = 2.1, h = 10, $fn = 16);                              // ch2 ear screws (M2.5 self-tap)
        translate([sg_rbar_x()[0] - 0.1, y0 + 6, sg_rbar_z0() - 0.1]) cube([sg_rbar_x()[1] - sg_rbar_x()[0] + 0.2, 5, 30]); // R-bar end seat
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
        translate([rod[0], y1 + 5, rod[1]]) cylinder(d = 2.6, h = 40, $fn = 16);
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
module mg996r() color("DimGray") {    // origin = output spline axis at the top face, body below (−Z)
    translate([-10.2, -9.85, -36.6]) cube([40.7, 19.7, 36.6]);
    translate([-17.2, -9.85, -10.6]) cube([54.7, 19.7, 2.5]);   // ears
    cylinder(d = 6, h = 4);
}
// ch2 servo hanging upside down, case face at sg_c2_face_z(), body toward −Y
module c2_servo() translate([sg_c2_pivot()[0], sg_c2_pivot()[1], sg_c2_face_z()]) rotate([180, 0, 0]) rotate(90) mg996r();
// MG996R 25T round horn (Ø25 × 1.4 disc + Ø10 spline hub) between crank and case;
// the crank bolts to the disc (4 × M2 on Ø14) and the horn screw goes through the crank hub
module c2_horn() color("WhiteSmoke") translate([sg_c2_pivot()[0], sg_c2_pivot()[1], sg_c2_z()[1]]) {
    cylinder(d = 25, h = 1.4, $fn = 48);
    cylinder(d = 10, h = sg_c2_face_z() - sg_c2_z()[1] - 0.4, $fn = 32);
}
module rod8(p, y0, y1) color("LightSteelBlue") cyl_y(p, 8, y0, y1, 24);
module dshaft(y0, y1) color("LightSteelBlue") translate([D[0], y0, D[1]]) rotate([-90, 0, 0]) d_bore(y1 - y0);
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
    translate([D[0], 0, D[1]]) rotate([0, -phi, 0]) translate([-D[0], 0, -D[1]]) tilt_crank();
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
    color("Tomato") tilt_drive_posed(st);
    tf_pose(st) {
        color("MediumSeaGreen") tilt_frame();
        load_cell();
        color("Khaki") cradle();
        if (show_card) card_on_bed();
        f_pins(); pin_a();
    }
}
module shuttle_fixed() {
    color("Peru") { rbar_neg(); rbar_pos(); }
    color("SandyBrown") { end_post_neg(); end_post_pos(); }
    rod8(rod, sg_rod_y()[0], sg_rod_y()[1]);
    dshaft(sg_rod_y()[0] - 8, sg_rod_y()[1]);
    // ch1 servo: spline on the D-shaft axis at Y −168, body toward −Y
    translate([D[0], -168, D[1]]) rotate([-90, 0, 0]) rotate(90) mg996r();
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
if (part == "carriage")     carriage();                 // preview only (3 prints)
if (part == "sled")         sled();
if (part == "cheek_neg")    cheek(-1);
if (part == "cheek_pos")    cheek(1);
if (part == "tilt_crank")   tilt_crank();
if (part == "tilt_link")    tilt_link();
if (part == "c2_crank")     c2_crank();
if (part == "c2_link")      c2_link();
if (part == "rbar_neg")     rbar_neg();
if (part == "rbar_pos")     rbar_pos();
if (part == "end_post_neg") end_post_neg();
if (part == "end_post_pos") end_post_pos();

// =============================================
// BOM (shuttle)
//  1  TAL221 mini load cell, 47 × 12 × 6, 4× M3 (±20 / ±3), cable end tapped
//       (owner's 50 g unit; SparkFun 100 g SEN-14727 is a drop-in)
//  1  8 mm smooth (h6, hardened) rod × 400 mm, e.g. Thomson 8MMSMAE L400MM
//  2  LM8UU (8 × 15 × 24), e.g. Adafruit 1181
//  1  8 mm D-shaft × 400 mm (≈7.5 mm across the flat), e.g. Ondrives GSM8000-400
//       or MISUMI D-cut rotary shaft; check d_bore() flat vs your shaft
//  2  688ZZ (8 × 16 × 5), one per end post (D-shaft)
//  1  D-shaft → MG996R 25T spline coupler: metal round horn + 8 mm D-hub
//  2  MG996R (ch1 tilt, ch2 shuttle; the two scrapped gate servos)
//  2  Ø4 × 8 mm steel dowel pins (F pins)
//  1  Ø3 × 20 mm steel dowel pin (tilt link pin A)
//  4  Ø3 × 8 mm steel dowel pins (cheek ↔ sled alignment)
//  1  0.1 mm skived PTFE tape, silicone adhesive, ≥ 75 mm wide (cradle bed + kick)
//  2  M3 × 12 SHCS (TF crossbar → cell tapped end)
//  2  M3 × 10 SHCS + 2 M3 × 5.7 heat-set inserts (cell free end → cradle boss)
//  6  M3 × 10 countersunk (ISO 10642) + 6 M3 × 5.7 heat-set inserts (cheeks → sled)
//  1  M3 × 16 SHCS + nylock (ch1 crank–link pivot)
//  2  shoulder screw, 4 mm shoulder, M3 × 4 thread, head ≤ Ø8 × 4: shoulder
//       5 mm (ch2 crank tip) and 6 mm (ch2 drive pin), e.g. ISO 7379-style
//       4 mm / M3 shoulder screws (MISUMI MSB4, McMaster 4 mm-shoulder M3)
//  2  M3 × 4 short heat-set inserts (≤ Ø4.6 OD), pressed flush into the ch2 link top
//  4  M2 × 6 countersunk self-tapping (c2 crank → horn disc, flush from below)
//  1  M3 × 12 countersunk (c2 crank hub → servo spline, ≈ 4.9 mm engagement)
//  (the tilt crank needs NO set screw: it slides along the D-shaft, keyed by its D-bore)
//  4  M2.5 × 10 self-tapping (MG996R ears, ch1) + 4 (ch2, up into the shelves)
//  1  MG996R Ø25 round 25T horn (in the servo bag) between the ch2 crank and the servo
//  2  M3 × 10 SHCS + 2 M3 × 5.7 inserts (R-bar lap splice), 2 M3 × 10 (rod clamps)
//  6  M3 × 20 SHCS + washers + nuts (end posts → baseplate, 3 per post)
// =============================================
