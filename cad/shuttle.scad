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
// PRINTED PARTS (export with -D 'part="..."'; all fit the 256 mm bed):
//   cradle        1×  PLA, 0.12 mm layers, 3 walls, 15 %, IRON the top; ≈17 g
//                     printed (≈19 g with tape + inserts; target ≤ 35 g).
//                     Print bed-top UP; the kick is an 18° slope whose layer
//                     steps face downhill for an exiting card. Then cover bed +
//                     kick with 0.1 mm skived-PTFE tape (wrap 2 mm over the lip),
//                     this is REQUIRED: shuttle_check.py slide shows bare PLA
//                     (μ ≈ 0.35-0.45) jams the upper-floor transfer.
//   tilt_frame    1×  PETG, 0.2, 4 walls, 40 %, upright (crossbar down), tree
//                     supports under the plate bottom edges + skid nubs; ream
//                     the F-pin holes Ø3.9 and press Ø4 × 8 dowels from inside.
//   carriage      1×  PETG, 0.2, 4 walls, 40 %, on its −y face (sled + cheek
//                     outer faces are flush); LM8UU pockets and the D-shaft
//                     bushings then print as vertical holes. Ream D bushings Ø8.3.
//   tilt_crank / tilt_link  1× each, PETG 100 %, flat
//   c2_crank      1×  PETG, 0.2, 5 walls, 50 %, flat (155 mm)
//   c2_link       1×  PETG, flat (173 mm)
//   rbar_neg / rbar_pos  1× each, PLA, on the −X face, 4 walls; sand the top
//   end_post_neg / end_post_pos  1× each, PETG/PLA, 4 walls, 40 %, upright
// HARDWARE: see the BOM block at the end of this file.
// =============================================

use <shuttle_geom.scad>
use <lower_ramp.scad>
use <reject_bin.scad>

/* [Export] */
part = "assembly";   // assembly | cradle | tilt_frame | carriage | tilt_crank | tilt_link | c2_crank | c2_link | rbar_neg | rbar_pos | end_post_neg | end_post_pos
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
module cradle() {
    difference() {
        union() {
            xz(-sg_cradle_hw(), sg_cradle_hw()) bed_profile_2d();
            for (s = [-1, 1]) cradle_guide(s);
            // longitudinal ribs (clear of the cell at |y| ≤ 6)
            for (y = [-27, -15, 15, 27])
                translate([bx0 + 6, y - 0.8, bz - bt - 3]) cube([bend - bx0 - 9, 1.6, 3 + eps]);
            // transverse ribs either side of the boss
            for (x = [104.5, 113])
                translate([x, -28, bz - bt - 3]) cube([1.6, 56, 3 + eps]);
            // boss on the cell's free (rear) pad: X 106..113
            translate([cxc - 23.5, -6, czt]) cube([7, 12, bz - bt - czt + eps]);
        }
        // 2× M3 heat-set inserts (Ø4.0 × 5.7) from below, on the cell's Ø3.2 holes
        for (y = [-3, 3]) translate([cxc - 20, y, czt - 0.1]) cylinder(d = 4.0, h = 6.0, $fn = 24);
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
            // F pin bosses (outer side, to |y| 40)
            for (s = [-1, 1]) cyl_y(F, 10, s > 0 ? tfy[1] - eps : -40, s > 0 ? 40 : -tfy[1] + eps, 40);
            // crossbar
            translate([140, -tfy[1], 64]) cube([18, 2 * tfy[1], 73.9 - 64]);
            // cell fixed-end pad (tapped end of the TAL221)
            translate([cxc + 16.5, -6, 73.9 - eps]) cube([7, 12, czt - 6 - 73.9 + eps]);
        }
        // F pin holes Ø3.9 (press Ø4 dowel)
        for (s = [-1, 1]) cyl_y(F, 3.9, -41, 41, 24);
        // cell screws into the tapped end: M3 clearance + head counterbore from below
        for (y = [-3, 3]) translate([cxc + 20, y, 60]) {
            cylinder(d = 3.4, h = 30, $fn = 20);
            cylinder(d = 6.2, h = 64 + 6.5 - 60, $fn = 24);
        }
        // link slot (open below) + pin A (M3 shoulder screw / Ø3 pin)
        translate([138, ly[0] - 0.5, 63]) cube([12.5, ly[1] - ly[0] + 1, 13]);
        cyl_y(A, 3.2, ly[0] - 6, ly[1] + 6, 20);
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
module cheek_2d()
    polygon([[111, 13], [148, 13], [156, 26], [156, 50], [164, 62], [164, 97],
             [150, 97], [138, 84], [118, 58], [111, 58]]);
// F pin path in LOWER mode (arc about the skid) → channel in the cheek
function f_path() = [for (i = [0 : 12]) sg_rot(sg_F(), sg_SJ(), sg_dl_lower() * i / 12)];
module carriage() {
    cy = sg_crank_y(); ly = sg_link_y();
    difference() {
        union() {
            translate([91, -hw, 13]) cube([118 - 91, 2 * hw, 54 - 13]);   // sled
            xz_sym(chy[0], chy[1]) cheek_2d();                              // cheeks
            translate([76, sg_c2_pin_dy() - 6, 10]) cube([91 - 76 + 1, 12, 6]);  // ch2 drive-pin arm
        }
        // rear-bottom notch: the ch2 horn (Ø25, Z 13.5..20.4, X ≤ 92.5) passes under the
        // sled at column 0; kept solid around the drive-pin arm (y −8..10)
        for (yy = [[-hw - 1, -8], [10, hw + 1]]) translate([90, yy[0], 12]) cube([4.6, yy[1] - yy[0], 10]);
        // front-top chamfer: the TF plates swing past it in LOWER
        xz(-hw - 1, hw + 1) polygon([[107.5, 54.1], [118.1, 54.1], [118.1, 41.5]]);
        // rod: Ø8.4 through, LM8UU Ø15.1 × 24.1 pockets at both ends
        cyl_y(rod, 8.4, -hw - 1, hw + 1);
        for (s = [-1, 1]) cyl_y(rod, 15.1, s > 0 ? hw - 24.1 : -hw - 1, s > 0 ? hw + 1 : -hw + 24.1, 48);
        // D-shaft: Ø8.3 bushing bores at both ends, Ø10 relief in between
        cyl_y(D, 8.3, -hw - 1, hw + 1);
        cyl_y(D, 10, -hw + 8, hw - 8);
        // crank + link swing pocket (sector about D, −62°..45°)
        translate([0, ly[0] - 0.8, 0]) xz(0, cy[1] - ly[0] + 1.6)
            polygon(concat([D], [for (a = [-62 : 6 : 45]) D + 41 * [cos(a), sin(a)]]));
        // F hook + lower-mode channel, 3.8 deep in each cheek's inner face
        for (s = [-1, 1]) for (i = [0 : len(f_path()) - 2]) hull() for (p = [f_path()[i], f_path()[i + 1]])
            cyl_y(p, 4.5, s > 0 ? chy[0] - 1 : -44.3, s > 0 ? 44.3 : -chy[0] + 1, 24);
        // ch2 drive pin Ø3.2 (M3 shoulder bolt from below through the link)
        translate([sg_c2_pivot()[0], sg_c2_pin_dy(), 5]) cylinder(d = 3.2, h = 20, $fn = 20);
        // cable clip slot for the load-cell lead (zip tie) on the −y cheek
        translate([150, -chy[1] - 1, 70]) cube([4, chy[1] - chy[0] + 2, 2.5]);
    }
}

// =====================================================================
// ch1 tilt crank (on the D-shaft) and link
// =====================================================================
module d_bore(h) difference() { cylinder(d = 8.15, h = h, $fn = 40); translate([3.55, -5, -1]) cube([5, 10, h + 2]); }
module tilt_crank() {      // modelled pointing +X from D, in the crank slab
    cy = sg_crank_y();
    translate([D[0], cy[1], D[1]]) rotate([90, 0, 0]) difference() {
        hull() { cylinder(d = 16, h = cy[1] - cy[0]); translate([sg_crank_r(), 0, 0]) cylinder(d = 9, h = cy[1] - cy[0]); }
        translate([0, 0, -1]) d_bore(cy[1] - cy[0] + 2);
        translate([sg_crank_r(), 0, -1]) cylinder(d = 3.2, h = 10, $fn = 20);
        // M3 grub screw onto the shaft flat
        translate([0, 0, (cy[1] - cy[0]) / 2]) rotate([0, 90, 0]) cylinder(d = 2.6, h = 10, $fn = 16);
    }
}
module tilt_link() {       // modelled from the origin along +X, in the link slab
    ly = sg_link_y();
    translate([0, ly[1], 0]) rotate([90, 0, 0]) difference() {
        hull() { cylinder(d = 7, h = ly[1] - ly[0]); translate([sg_link_l(), 0, 0]) cylinder(d = 7, h = ly[1] - ly[0]); }
        for (x = [0, sg_link_l()]) translate([x, 0, -1]) cylinder(d = 3.2, h = 10, $fn = 20);
    }
}

// =====================================================================
// ch2 shuttle crank (servo horn) and link — XY plane under the deck
// =====================================================================
module c2_crank() {        // modelled pointing +Y from the pivot (psi = 0)
    z = sg_c2_z(); r = sg_c2_r();
    translate([0, 0, z[0]]) difference() {
        union() {
            hull() { cylinder(d = 20, h = z[1] - z[0]); translate([0, r, 0]) cylinder(d = 12, h = z[1] - z[0]); }
        }
        // MG996R round horn (Ø25 disc, 4 × Ø1.5 screws on Ø14): screw holes + hub relief
        for (a = [45 : 90 : 315]) rotate(a) translate([7, 0, -1]) cylinder(d = 1.8, h = 10, $fn = 12);
        translate([0, 0, -1]) cylinder(d = 3.2, h = 10, $fn = 20);
        translate([0, r, -1]) cylinder(d = 3.2, h = 10, $fn = 20);
        // lightening slots
        for (t = [30, 70, 105]) hull() for (dy = [0, 22]) translate([0, t + dy, -1]) cylinder(d = 5, h = 10);
    }
}
module c2_link() {         // modelled from the origin along +Y
    z = sg_c2_link_z(); l = sg_c2_l();
    translate([0, 0, z[0]]) difference() {
        hull() { cylinder(d = 11, h = z[1] - z[0]); translate([0, l, 0]) cylinder(d = 11, h = z[1] - z[0]); }
        for (y = [0, l]) translate([0, y, -1]) cylinder(d = 3.2, h = 10, $fn = 20);
        for (t = [25, 75, 120]) hull() for (dy = [0, 18]) translate([0, t + dy, -1]) cylinder(d = 4.5, h = 10);
    }
}

// =====================================================================
// R-BAR (fixed lower-mode fulcrum) + riser brackets + end posts
// =====================================================================
nb = sg_rbar_notch_y();
// The bar spans end post to end post (Y −150..232). 7 × 17 PLA: mid-span sag
// under the 0.3 N skid load ≈ 0.04 mm, so no intermediate supports (nothing
// fixed may stand inside the carriage's travel envelope anyway).
// Two prints joined by a 20 mm lap splice at Y 0 (lower half-depth from the
// −Y half, upper from the +Y half: the contact top stays one piece there),
// 2× M3 × 16 down through the splice into heat-set inserts.
rb_split_z = 64.5;
module rbar_raw(y0, y1) {
    xb = sg_rbar_x(); zt = sg_SJ()[1] - sg_skid_r() - 0.3;   // skid hovers 0.3 above the bar in HOLD
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
module rbar_neg() difference() {          // Y −150..10, lower half only over Y −10..10
    rbar_raw(sg_rbar_y()[0], 10);
    translate([90, -10, rb_split_z]) cube([20, 21, 20]);
    for (y = [-5, 5]) translate([100.5, y, rb_split_z - 7]) cylinder(d = 4.0, h = 8, $fn = 20);
}
module rbar_pos() difference() {          // Y −10..232, upper half only over Y −10..10
    rbar_raw(-10, sg_rbar_y()[1]);
    translate([90, -11, 40]) cube([20, 21, rb_split_z - 40]);
    for (y = [-5, 5]) translate([100.5, y, rb_split_z - 1]) {
        cylinder(d = 3.4, h = 20, $fn = 16);
        translate([0, 0, sg_SJ()[1] - sg_skid_r() - 0.3 - rb_split_z - 1.9]) cylinder(d = 6.2, h = 5, $fn = 24);
    }
}

// −Y end block: rod / D-shaft (688ZZ) / R-bar post + ch1 servo cage + ch2 rear ear shelf.
// Everything at X < 90 stays above Z 16 (ch2 crank sweeps below); everything at
// Y > −150 stays at X < 91 (carriage at column 0 reaches Y −148).
module end_post_neg() {
    y0 = sg_rod_y()[0];       // −160: post Y −160..−150
    difference() {
        union() {
            translate([96, y0, 4]) cube([20, 10, sg_SJ()[1] - 4]);          // post
            translate([90, -190, 4]) cube([30, 190 + y0 + 10, 4]);          // floor plate
            translate([90, -185.6, 4]) cube([30, 6.9, 62]);                 // ch1 cage (ear plane)
            translate([90, -175, 4]) cube([4, 25, 54]);                     // ch2 wall
            translate([68, sg_c2_ear_end_y()[1] - 0.5, sg_c2_shelf_z()])
                cube([26, 7.0, 3.4]);                                       // ch2 rear ear shelf (0.5 off the case)
            translate([90, -175, 4]) cube([6, 25, 4]);
        }
        cyl_y(rod, 8.05, y0 - 1, y0 + 11);                                   // rod end (M3 clamp screw from top)
        translate([rod[0], y0 + 5, rod[1]]) cylinder(d = 2.6, h = 40, $fn = 16);
        cyl_y(D, 10, y0 - 1, y0 + 11);                                       // D-shaft through
        cyl_y(D, 16.05, y0 + 5, y0 + 11, 48);                                // 688ZZ pocket (inner side)
        translate([95.15, -186, 13.3]) cube([19.7, 8, 41.1]);                // ch1 servo body opening
        for (z = [9.5, 58.5]) translate([105, -190, z]) rotate([-90, 0, 0]) cylinder(d = 2.6, h = 15, $fn = 16);
        for (x = [100, 110]) translate([x, -170, 0]) cylinder(d = 3.4, h = 20, $fn = 16);   // to baseplate (X 110 grid)
        for (x = [75, 85]) translate([x, sg_c2_ear_y()[1], sg_c2_shelf_z() - 4.2])
            cylinder(d = 2.2, h = 10, $fn = 16);                              // ear screws (M2.5 self-tap)
        translate([sg_rbar_x()[0] - 0.1, y0 + 6, sg_rbar_z0() - 0.1]) cube([sg_rbar_x()[1] - sg_rbar_x()[0] + 0.2, 5, 30]); // R-bar end seat
    }
}
module end_post_pos() {
    y1 = sg_rod_y()[1];       // 232: post Y 232..242
    difference() {
        union() {
            translate([96, y1, 4]) cube([20, 10, sg_SJ()[1] - 4]);
            translate([90, y1, 4]) cube([32, 22, 4]);
        }
        cyl_y(rod, 8.05, y1 - 1, y1 + 11);
        translate([rod[0], y1 + 5, rod[1]]) cylinder(d = 2.6, h = 40, $fn = 16);
        cyl_y(D, 10, y1 - 1, y1 + 11);
        cyl_y(D, 16.05, y1 - 1, y1 + 5, 48);                                 // 688ZZ pocket (inner side)
        translate([sg_rbar_x()[0] - 0.1, y1 - 1, sg_rbar_z0() - 0.1]) cube([sg_rbar_x()[1] - sg_rbar_x()[0] + 0.2, 5, 30]);
        for (x = [98, 114]) translate([x, y1 + 17, 0]) cylinder(d = 3.4, h = 20, $fn = 16);
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
    color("Orange") translate([P[0], P[1], 0]) rotate(psi) c2_crank();
    color("Gold") translate([T[0], T[1], 0]) rotate(atan2(pin[1] - T[1], pin[0] - T[0]) - 90) c2_link();
}

// Moving shuttle group at carriage Y = yc (cradle + card + TF + cell + carriage + crank/link)
module shuttle_moving(yc, st, show_card = true) translate([0, yc, 0]) {
    color("SteelBlue") carriage();
    color("Tomato") tilt_drive_posed(st);
    tf_pose(st) {
        color("MediumSeaGreen") tilt_frame();
        load_cell();
        color("Khaki") cradle();
        if (show_card) card_on_bed();
        for (s = [-1, 1]) color("LightSteelBlue") cyl_y(F, 4, s > 0 ? tfy[0] : -44, s > 0 ? 44 : -tfy[0], 16);
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
if (part == "assembly")     asm_sorter_end(show_col, show_state);
if (part == "cradle")       cradle();
if (part == "tilt_frame")   tilt_frame();
if (part == "carriage")     carriage();
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
//  1  0.1 mm skived PTFE tape, silicone adhesive, ≥ 75 mm wide (cradle bed + kick)
//  2  M3 × 10 SHCS (TF crossbar → cell tapped end)
//  2  M3 × 10 SHCS + 2 M3 × 5.7 heat-set inserts (cell free end → cradle boss)
//  4  M3 × 16 SHCS + nylock as pivots (crank–link, link–pin A, c2 crank–link,
//       c2 link–carriage drive pin)
//  1  M3 × 4 set screw (tilt crank onto the D flat)
//  4  M2.5 × 10 self-tapping (MG996R ears, ch1) + 4 (ch2, up into the shelves)
//  1  MG996R Ø25 round 25T horn (in the servo bag) between the ch2 crank and the servo
//  2  M3 × 16 + 2 M3 × 5.7 inserts (R-bar lap splice), 2 M3 × 10 (rod clamps)
//  4  M3 × 25 + nuts/washers (end posts → baseplate)
// =============================================
