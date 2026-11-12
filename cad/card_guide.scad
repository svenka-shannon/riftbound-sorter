// =============================================
// Riftbound Card Sorter — Card Side Guides (+ retaining clips)
// =============================================
// Two long guide bars that hang in the conveyor rails' top grooves and
// narrow the card channel from the 90 mm rail gap to 66.4 mm (63 mm card +
// 1.7 mm each side), from upstream of the drop zone to the belt exit. They
// keep the card square and centred under the camera (camera Y margin is only
// ±5.9 mm at 100 mm lens height, rail-to-rail play would be ±13.5 mm).
//
// Print: 1× guide_back, 1× guide_front (mirror image), 2-4× clip.
// Material: PETG (low friction on card edges, tougher than PLA), 0.2 mm,
//   3 walls, 20 % infill. Black if you can (less stray light under the hood).
//
// COORDINATES: machine frame (see machine_frame.scad). Every module here
// is already in machine coordinates; no placement transform is needed.
//
// CROSS-SECTION (back guide, +Y side; front guide is the mirror image)
//
//      z 99 ─ rail top ─────────── ┌──────────┬─┐ ← groove fill sits on the
//                      45° funnel  /          │ │   rail groove floor (z 96.5);
//                                 /           │ └─┐  rail fin |Y| 46.8..48 (1.2)
//      z 93.8   R3 rounded top  (             │   │  rail wall |Y| 45..48
//      z 92.6  vertical contact │             │   │
//              face, |Y| 33.2   │             │   │
//      z 90.4  ─ guide bottom ─ └─────────────┘   │
//      card face z 90.9 (sleeved card top 91.4)   │
//      slide-bed lands z 89.9, roller tops z 90.0 │
//                               |Y| 33.2    44.9  45
//
//  - Card edge sees only the smooth vertical face (layer lines run along X,
//    i.e. along the card's travel) and the R3 round above it. No corners.
//  - Guide bottom (z 90.4) is 0.5 mm below the card underside, 0.5 mm above
//    the slide-bed lands and 0.4 mm above the roller bodies, so a card cannot
//    slip under it and nothing rotating touches it. Closest belt cord is at
//    |Y| 26.95, 6.25 mm inboard of the guide face.
//  - The 45° funnel above the R3 round catches a card that the suction arm
//    lowers up to 4.9 mm off-centre (edge at |Y| ≤ 38.4 when it passes the
//    rail-top plane) and steers it into the channel as it is lowered; it must
//    be released ≤ 1.7 mm off-centre (it then falls clear of the round).
//  - Upstream end: 22.4 mm long 15° plan-view flare (channel 78.4 → 66.4 mm)
//    so a card dropped long, or nudged backwards, still enters smoothly.
//  - Nothing rises above the rail top (z 99) except the clips, which sit just
//    outside each end of the hood, downstream of the suction cup and arm.
//
// RETENTION: the groove fill rests on the rail groove floor and the guide
//   body bears against the rail inner face (its centre of mass is inboard of
//   the ledge, so it leans into the rail on its own). The hood stands on the
//   rails' 1.2 mm top fins just outboard of the guides (0.4 mm clear of them),
//   and a clip at each end of the hood snaps over the rail wall: bridge on
//   the guide top + fin top, inner leg in a pocket in the guide top, outer jaw
//   on the rail's outer face (fin + full wall). No screws, no holes in the rails.
// =============================================

use <machine_frame.scad>

/* [Export] */
part = "assembly";   // assembly | guide_back | guide_front | clip

$fn = 48;

// --- From the frame / rail (single sources of truth) ---
card_z     = frame_card_z();         // 90.9 card face (belt top)
deck_z     = frame_deck_z();         // 64   rail base
rail_in    = frame_rail_in();        // 45   rail inner face |Y|
cam_x      = frame_cam_x();          // lens axis X
drop_x     = frame_drop_x();         // card centre at release
belt_x1    = frame_belt_x1();        // 85   belt / rail end
rail_h     = 35;                     // conveyor_rail.scad rail_h
rail_wall  = 3;                      // conveyor_rail.scad wall
groove     = 2.5;                    // conveyor_rail.scad groove_depth (groove height)
groove_y   = 1.8;                    // conveyor_rail.scad groove_y (depth into the wall;
                                     //   leaves a 1.2 mm fin at |Y| 46.8..48)
rail_top   = deck_z + rail_h;        // 99
groove_fl  = rail_top - groove;      // 96.5 groove floor = guide seat

// --- Card ---
card_w     = 63;
card_l     = 88;
card_t_max = 0.6;                    // sleeved card

// --- Guide section ---
side_clr   = 1.7;                    // per side: 63 + 2×1.7 = 66.4 channel
ch_hw      = card_w / 2 + side_clr;  // 33.2 contact face |Y|
g_z0       = card_z - 0.5;           // 90.4 guide underside
v_top      = card_z + card_t_max + 1.1;   // 92.6 top of the vertical face
fil_r      = 3;                      // round between face and funnel
fun_a      = 45;                     // funnel slope from horizontal
fit        = 0.1;                    // clearance to rail faces
g_out      = rail_in - fit;          // 44.9 bears on the rail inner face
fill_out   = rail_in + groove_y - fit; // 46.7 groove fill outer face (rail fin at 46.8)

fil_td     = fil_r / tan((90 + fun_a) / 2);   // 1.24 tangent length
z_corner   = v_top + fil_td;                  // 93.84 virtual corner
y_fun_top  = ch_hw + (rail_top - z_corner) / tan(fun_a);  // 38.36

// --- Length / plan view ---
g_x0       = drop_x - card_l / 2 - 16;  // -155: 16 mm upstream of a dropped card
g_x1       = belt_x1;                    //   85: belt exit
flare_d    = 6;                          // plan-view flare depth at the mouth
flare_a    = 15;
flare_len  = flare_d / tan(flare_a);     // 22.4 mm

// --- Hood interface (scanner_hood.scad reads these) ---
hood_hl    = 54;                         // hood outer half-length along X
function scan_hood_half_len() = hood_hl;

// --- Clips ---
clip_l     = 10;                         // along X
clip_t     = 2.0;                        // bridge thickness above the rail top
clip_leg_y = [41.2, 42.8];               // inner leg (in the guide-top pocket)
clip_jaw_y = [rail_in + rail_wall + 0.05, rail_in + rail_wall + 2.6];  // 48.05..50.6
clip_jaw_z0 = groove_fl - 2;             // 94.5 (608 bosses top out at z 93.5)
pocket_y   = [41.0, 43.0];
pocket_d   = 2.0;
// One clip per side at each end of the hood, 8 mm clear of it:
//  - upstream: only if it stays downstream of the suction cup (drop_x + 15);
//    the arm sweeps over the rails from about drop_x upstream, so nothing
//    above the rail top may sit there (cam_x = 5: X -62, span -67..-57);
//  - downstream: midway between the hood and the belt exit (cam_x = 5: X 72).
// Both sit at |Y| 41..51, Z 94.5..101: outside the card path and outside the
// funnel's catch range (|Y| <= 38.4) of a card being lowered.
hood_gap   = 8;
function guide_clip_x() =
    let(up = cam_x - hood_hl - hood_gap - clip_l / 2,
        dn = (cam_x + hood_hl + g_x1) / 2)
    concat(up - clip_l / 2 >= drop_x + 15 ? [up] : [],
           dn - clip_l / 2 >= cam_x + hood_hl + 2 && dn + clip_l / 2 <= g_x1 - 1 ? [dn] : []);

// ── Functions for other parts / checks ──
function guide_channel_hw() = ch_hw;
function guide_z0()         = g_z0;
function guide_x_range()    = [g_x0, g_x1];
function guide_rail_top()   = rail_top;

echo(str("CARD GUIDE: channel ", 2 * ch_hw, " mm (|Y| ", ch_hw, "), X ", g_x0, "..", g_x1,
         ", bottom z ", g_z0, ", vertical face to z ", v_top, ", funnel top |Y| ", y_fun_top,
         ", flare ", flare_len, " mm @ ", flare_a, "°, clips at X ", guide_clip_x()));
assert(ch_hw - (25.5 + 1.45) > 5, "guide face too close to the outer belt");
assert(g_z0 < card_z - 0.3, "card could slip under the guide");
assert(y_fun_top < g_out, "funnel wider than the guide body");

// Arc points of the R3 round, from the funnel tangent down to the face tangent
function fillet_pts(s) =
    let(cy = ch_hw + fil_r + s, cz = v_top)
    [for (a = [180 - (90 - fun_a) : 5 : 180]) [cy + fil_r * cos(a), cz + fil_r * sin(a)]];

// Convex main body (2D, x = |Y|, y = Z), inner face shifted outward by s
module prof_main(s = 0)
    polygon(concat(
        [[ch_hw + s, g_z0], [g_out, g_z0], [g_out, rail_top], [y_fun_top + s, rail_top]],
        fillet_pts(s)
    ));

// Groove fill: rests on the groove floor inside the rail top notch
module prof_fill()
    translate([g_out - 0.01, groove_fl]) square([fill_out - g_out + 0.01, groove]);

module prof_full() union() { prof_main(0); prof_fill(); }

// 2D (|Y|, Z) → machine (X, Y, Z), extruded along +X
module along_x(x0, len) translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(len) children();

// Back (+Y) guide in machine coordinates
module guide_back() {
    difference() {
        union() {
            // Straight section. The flare hull below carries on 1 mm past the
            // flare end with the straight profile, and the straight section starts
            // 0.5 mm inside that prismatic stub: the two bodies overlap in volume
            // with identical faces (a 0.01 mm overlap at the seam left degenerate
            // sliver faces, STL not watertight) and the contact face has no step.
            along_x(g_x0 + flare_len + 0.5, g_x1 - g_x0 - flare_len - 0.5) prof_main(0);
            // Upstream flare: linear sweep of the convex body (hull of end slices),
            // clipped to the guide envelope next to the rail
            intersection() {
                hull() {
                    along_x(g_x0, 0.01) prof_main(flare_d);
                    along_x(g_x0 + flare_len, 1) prof_main(0);
                }
                translate([g_x0, 0, g_z0 - 1]) cube([flare_len + 1, g_out, rail_top - g_z0 + 2]);
            }
            // Groove fill, full length
            along_x(g_x0, g_x1 - g_x0) prof_fill();
        }
        // Clip pockets in the guide top
        for (x = guide_clip_x())
            translate([x - clip_l / 2 - 0.2, pocket_y[0], rail_top - pocket_d])
                cube([clip_l + 0.4, pocket_y[1] - pocket_y[0], pocket_d + 1]);
        // 1.5 mm chamfers on the two exposed end corners of the contact face.
        // Upstream: the face there runs at the 15° flare, so the cut goes from
        // 1.5 along the end face to 1.5 along the flare face (a 45°-turned cube
        // left its tip exactly on the funnel surface → non-manifold edge).
        let(c = [g_x0, ch_hw + flare_d], a = c + [0, 1.5], b = c + 1.5 * [cos(flare_a), -sin(flare_a)])
            translate([0, 0, g_z0 - 1]) linear_extrude(rail_top - g_z0 + 2)
                polygon([a, b, [b[0], c[1] - 3], [c[0] - 2, c[1] - 3], [c[0] - 2, a[1]]]);
        translate([g_x1, ch_hw, (g_z0 + rail_top) / 2]) rotate([0, 0, 45])
            cube([1.5 * sqrt(2), 1.5 * sqrt(2), rail_top - g_z0 + 2], center = true);
    }
}

module guide_front() mirror([0, 1, 0]) guide_back();

// Clip profile (2D, x = |Y|, y = Z)
// One closed outline (no overlapping pieces, so the mesh is cleanly manifold):
// inner leg down into the guide pocket, bridge over the rail top, outer jaw
// down the rail's outer face with a 0.8 × 1.2 lead-in chamfer at its tip.
module prof_clip() {
    leg_z0 = rail_top - pocket_d + 0.2;   // 97.2, 0.2 above the pocket floor
    top    = rail_top + clip_t;           // 101
    polygon([
        [clip_leg_y[0], leg_z0],
        [clip_leg_y[1], leg_z0],
        [clip_leg_y[1], rail_top],
        [clip_jaw_y[0], rail_top],
        [clip_jaw_y[0], clip_jaw_z0 + 1.2],
        [clip_jaw_y[0] + 0.8, clip_jaw_z0],
        [clip_jaw_y[1], clip_jaw_z0],
        [clip_jaw_y[1], top - 0.8],          // 0.8 chamfer on the outer top edge
        [clip_jaw_y[1] - 0.8, top],          //   (the one a hand runs along)
        [clip_leg_y[0], top],
    ]);
}

// One clip on the back (+Y) rail at machine X = x
module clip_back(x) translate([x - clip_l / 2, 0, 0]) rotate([90, 0, 90]) clip_print();

// Both guides + all clips, machine coordinates
module card_guides() {
    guide_back();
    guide_front();
    for (x = guide_clip_x()) {
        clip_back(x);
        mirror([0, 1, 0]) clip_back(x);
    }
}

// Keep-out solid for parts that pass over the guides (the hood end walls):
// the straight guide section offset by clr, both sides, X x0..x1
module card_guide_envelope(x0, x1, clr = 0.4)
    for (m = [0, 1]) mirror([0, m, 0])
        along_x(x0, x1 - x0) offset(delta = clr) prof_full();

// ── Export ──
// Guides print upside down: the flat z = 99 top on the bed; the 45° funnel,
// the R3 round and the groove-fill step are all ≤ 45° → no supports.
// Clips print lying on their profile (10 mm tall). Front guide = mirror.
if (part == "assembly") card_guides();
if (part == "guide_back")  translate([-g_x0, 0, rail_top]) rotate([180, 0, 0]) guide_back();
if (part == "guide_front") translate([-g_x0, 0, rail_top]) rotate([180, 0, 0]) guide_front();
if (part == "clip") clip_print();

// Clip in print orientation (profile on the bed). The 0.8 mm chamfer on the
// jaw's outer top edge is part of the 2D profile (a rotated-cube cutter left
// zero-area slivers → non-manifold STL).
module clip_print() linear_extrude(clip_l) prof_clip();

// =============================================
// INSTALL: drop each guide into its rail's top groove from above (groove
//   fill down, flat face against the rail inner face), then press the
//   clip(s) over the rail wall so the inner leg seats in the guide's pocket.
//   Fit the guides before the hood; the hood stands on the rails' top fins,
//   0.4 mm clear of the guides (it does not rest on them).
// CHECK: slide a sleeved card along the channel by hand — it should move
//   freely with ~1.7 mm play each side and never touch the clip or hood.
// =============================================
