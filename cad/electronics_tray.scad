// =============================================
// Riftbound Card Sorter — Electronics Tray
// =============================================
// One open-top box on the baseplate behind the riser. Holds every board of
// the control electronics, each on its REAL hole pattern (or, where the
// clone boards disagree, in a locating pocket):
//
//   board                         pattern / mount                       source
//   Pi Zero 2 W  65 × 30          58 × 23, M2.5 pilots on Ø6 × 5 posts   RPi mechanical drawing
//   PCA9685 16-ch (generic blue)  55.88 × 19.05 (2.2" × 0.75"), M2.5     Adafruit #815 rev C .brd
//     62.2 × 25.4                 pilots on Ø6 × 5 posts. The generic     (clones copy this layout;
//                                 blue board copies the #815 outline.     listings say "56 × 19/20")
//   2-ch 5 V relay (Songle)       44.3 × 32.8 nominal, M2.5 into Ø3.1    vendor listings 44..44.5 ×
//     ≈ 50 × 38.5                 board holes, on 8 × 8 corner blocks     32.5..33 (±0.3 mm absorbed)
//   ULN2003 board (28BYJ-48 kit)  30 × 26.5, M2.5 into Ø3 board holes,   vendor listing; 40 × 21
//     ≈ 35 × 32                   on 8 × 8 corner blocks                  variant: drill the blocks
//   Pololu D24V22F5  17.8 × 17.8  13.2 × 13.2 diagonal (TL/BR), M2       Pololu dim. drawing 0J1031
//   Pololu D24V50F5  17.8 × 20.3  13.5 × 16.0 diagonal (BL/TR), M2       pololu.com/product/2851
//   Pololu D36V28F5  17.8 × 20.3  13.5 × 16.0 diagonal (BL/TR), M2       Pololu dim. drawing 0J1659
//   HX711 (green)    ≈ 34 × 21    no agreed hole pattern between clones → corner-stop pocket + foam tape
//   L9110S           ≈ 29 × 23    no agreed hole pattern (28×21..29×23.5) → corner-stop pocket + foam tape
//   Panel DC jack 5.5 × 2.1       Ø8.2 hole in the +Y (back) wall, for the M8 × 0.75-thread
//                                 DC-022 type (11 mm-thread types: drill out to Ø11.2)
//
// Pilots: M2.5 Ø2.15 (thread-forming / self-tapping M2.5 × 6..8), M2 Ø1.7
// (M2 × 5..6). All pilots are blind: they stop 1 mm above the underside.
// The corner blocks under the relay / ULN2003 are solid 8 × 8 so a board
// whose holes are up to ±2.5 mm off the nominal pattern can be drilled
// Ø2.15 in place. Board undersides sit 5 mm (Pololu 4 mm) above the floor,
// clear of their through-hole solder tails.
//
// SIZE / PLACEMENT: 185 × 150 × 45 (was 185 × 125: everything above plus
// 4 Wago bars, 3 × 1000 µF and the jack did not fit with wiring room).
// Placed by assembly.scad at translate([-150, 80, 4]) → machine
// X −150..35, Y 80..230. The front face touches the riser's back face (Y 80).
// The 4 mounting holes are REAL baseplate grid holes (30 mm pitch, 15 mm in
// from each 190 × 180 tile edge, so the X grid restarts on every tile column:
// X −270..−120 | −80..70 | 110..260; Y −255+30j): machine (−120, 105),
// (−50, 105), (−120, 195), (10, 195),
// M3 × 18 SHCS into the board's tee-nuts (baseplate_tile.scad): floor 2.5 +
// tile 4 + 6 mm board = 12.5 clamp, so the tip runs through all 5.9 mm of
// tee-nut thread and ends 5.5 mm below the board underside (4.6 below the
// tee-nut flange; M3 × 20 poked out 7.5). Fallback without tee-nuts: washer +
// nut under the board (0.5 + 2.4, 2.6 mm of thread past the nut).
//
// LAYOUT (tray-local, x = machine X + 150, y = machine Y − 80):
//   front strip  Pi Zero 2 W x 107..172, y 5..35, CSI connector to +X
//                (machine X ≈ 22, Y ≈ 100: 80 mm closer to the camera-ribbon
//                entry at X 5, Y 88 than before); L9110S pocket x 38..67
//   middle       relay x 5..55 y 42..80.5 | ULN2003 x 62..97 y 42..74 |
//                PCA9685 x 108..170 y 44..69 | HX711 pocket x 62..97 y 82..104
//                free: x 5..55 y 85..108, x 105..180 y 75..110 (Wago / caps)
//   back strip   D24V22F5 x 40..58, D24V50F5 x 62..80, jack at x 92,
//                D36V28F5 x 104..122 (all y 125..145); Wago bank x 126..180
//
// Print: floor down, no supports (cable slots are 10 mm bridges, the jack
// hole is Ø8.2 in a vertical wall). PLA 0.2 mm, 3 walls, 25 % infill.
// =============================================

/* [Export] */
show_boards = false;   // true: draw board outlines (reference, not printed)

outer_w   = 185;
outer_d   = 150;
outer_h   = 45;
wall      = 2.5;
floor_t   = 2.5;
tray_org  = [-150, 80];        // machine X/Y of the tray corner (assembly.scad)

$fn = 24;

// ── Baseplate grid (baseplate_tile.scad: 3 × 3 tiles of 190 × 180 from machine
//    X −285, Y −270; holes every 30 mm, 15 mm in from each tile edge) ────────
function on_grid1(v, x0, tile, n) =
    let(t = floor((v - x0) / tile), r = (v - x0) - t * tile - 15)
    t >= 0 && t < n && r >= -1e-6 && abs(r / 30 - round(r / 30)) < 1e-6 && r <= tile - 30 + 1e-6;
function on_grid(p) = on_grid1(p[0], -285, 190, 3) && on_grid1(p[1], -270, 180, 3);
mount_m = [[-120, 105], [-50, 105], [-120, 195], [10, 195]];    // machine X/Y
mount_l = [for (p = mount_m) p - tray_org];                      // tray-local
for (p = mount_m) assert(on_grid(p), str("tray mounting hole ", p, " is off the baseplate grid"));

// ── Fasteners ───────────────────────────────────────────────────────────────
m25_pilot = 2.15;
m2_pilot  = 1.7;
post_h    = 5;         // board underside above the floor top
post_d    = 6;
pol_h     = 4;         // Pololu posts (1.1 mm parts underneath)
pol_d     = 4.5;
blk       = 8;         // corner block size (relay / ULN2003)

// ── Boards: [x0, y0] lower-left corner of the PCB (tray-local), size, holes
//    relative to that corner ─────────────────────────────────────────────────
pi_at   = [107, 5];   pi_sz  = [65, 30];
pi_h    = [[3.5, 3.5], [61.5, 3.5], [3.5, 26.5], [61.5, 26.5]];

pca_at  = [108, 44];  pca_sz = [62.23, 25.4];
pca_h   = [for (x = [3.175, 3.175 + 55.88]) for (y = [3.175, 3.175 + 19.05]) [x, y]];

rly_at  = [5, 42];    rly_sz = [50, 38.5];
rly_h   = [for (x = [-1, 1]) for (y = [-1, 1]) rly_sz / 2 + [x * 44.3 / 2, y * 32.8 / 2]];

uln_at  = [62, 42];   uln_sz = [35, 32];
uln_h   = [for (x = [-1, 1]) for (y = [-1, 1]) uln_sz / 2 + [x * 30 / 2, y * 26.5 / 2]];

// Pololu: pin row along the board's y0 edge (toward the tray middle)
d22_at  = [40, 125];  d22_sz = [17.8, 17.8];  d22_h = [[2.3, 15.5], [15.5, 2.3]];
d50_at  = [62, 125];  d50_sz = [17.8, 20.3];  d50_h = [[2.2, 2.2], [15.7, 18.2]];
d36_at  = [104, 125]; d36_sz = [17.8, 20.3];  d36_h = [[2.2, 2.2], [15.7, 18.2]];

// Pockets for boards without an agreed hole pattern (inner size, board + 0.3/side)
hx_at   = [62, 82];   hx_sz  = [34.6, 21.6];   // green HX711 ≈ 34 × 21
l91_at  = [38, 5];    l91_sz = [29.6, 23.6];   // L9110S 28 × 21 .. 29 × 23.5

jack_x  = 92;  jack_z = 18;  jack_d = 8.2;

slot_w = 10;  slot_h = 6;     // cable slots (both X walls)

echo(str("ETRAY: ", outer_w, " x ", outer_d, " x ", outer_h, " at machine X ", tray_org[0], "..", tray_org[0] + outer_w,
         " Y ", tray_org[1], "..", tray_org[1] + outer_d, "; grid mounting holes (machine) ", mount_m));

// ── Interference self-check (board footprints vs each other / mount heads) ──
boards = [[pi_at, pi_sz], [pca_at, pca_sz], [rly_at, rly_sz], [uln_at, uln_sz],
          [d22_at, d22_sz], [d50_at, d50_sz], [d36_at, d36_sz],
          [hx_at - [1.6, 1.6], hx_sz + [3.2, 3.2]], [l91_at - [1.6, 1.6], l91_sz + [3.2, 3.2]],
          [[jack_x - 8, outer_d - wall - 16], [16, 16]]];
function _ov(a, b, g) = a[0][0] < b[0][0] + b[1][0] + g && b[0][0] < a[0][0] + a[1][0] + g &&
                        a[0][1] < b[0][1] + b[1][1] + g && b[0][1] < a[0][1] + a[1][1] + g;
for (i = [0 : len(boards) - 1]) {
    b = boards[i];
    assert(b[0][0] >= wall && b[0][1] >= wall && b[0][0] + b[1][0] <= outer_w - wall &&
           b[0][1] + b[1][1] <= outer_d - wall, str("board ", i, " outside the tray"));
    for (j = [i + 1 : 1 : len(boards) - 1])
        assert(!_ov(b, boards[j], 3), str("boards ", i, " and ", j, " closer than 3 mm"));
    for (m = mount_l)   // M3 head + washer Ø7 + 1 mm
        assert(!_ov(b, [m - [4.5, 4.5], [9, 9]], 0), str("board ", i, " over mounting hole ", m));
}

// =========================================================================
module post(p, d, h, pilot)       // standoff with a blind pilot (stops 1 mm above the underside)
    translate([p[0], p[1], 0]) difference() {
        cylinder(d = d, h = floor_t + h, $fn = 32);
        translate([0, 0, 1]) cylinder(d = pilot, h = floor_t + h, $fn = 16);
    }

module block(p, h)                // solid corner block, pilot at the nominal hole
    translate([p[0], p[1], 0]) difference() {
        translate([-blk / 2, -blk / 2, 0]) cube([blk, blk, floor_t + h]);
        translate([0, 0, 1]) cylinder(d = m25_pilot, h = floor_t + h, $fn = 16);
    }

// Corner stops: L-shaped, 1.6 wide, 6 mm legs, 4 mm above the floor; the
// board edges between them stay open for the header / screw-terminal wires.
module pocket(at, sz, h = 4, leg = 6, t = 1.6)
    for (cx = [0, 1], cy = [0, 1])
        translate([at[0] + cx * sz[0], at[1] + cy * sz[1], 0])
            mirror([cx, 0, 0]) mirror([0, cy, 0]) {
                translate([-t, -t, 0]) cube([leg + t, t, floor_t + h]);
                translate([-t, -t, 0]) cube([t, leg + t, floor_t + h]);
            }

module electronics_tray() {
    difference() {
        cube([outer_w, outer_d, outer_h]);

        // Interior
        translate([wall, wall, floor_t])
            cube([outer_w - wall * 2, outer_d - wall * 2, outer_h]);

        // Cable slots (3× on the +X wall)
        for (i = [0:2])
            translate([outer_w - wall - 0.1, 20 + i * 30, outer_h - slot_h - wall])
                cube([wall + 0.2, slot_w, slot_h]);

        // Cable slots (3× on the LEFT / machine −X wall, same Y/Z as the right
        // side). The front harness comes round the hopper's −X side; entering
        // here instead of the +X slots saves ≈ 0.3 m of harness (machine
        // X −150, Y 100..110 / 130..140 / 160..170, Z 40.5..46.5). Top 2.5 mm
        // of the wall stays closed (10 mm bridge); nothing mounts on this wall.
        for (i = [0:2])
            translate([-0.1, 20 + i * 30, outer_h - slot_h - wall])
                cube([wall + 0.2, slot_w, slot_h]);

        // M3 baseplate mounting holes, on real grid holes
        for (p = mount_l)
            translate([p[0], p[1], -0.1])
                cylinder(d = 3.4, h = floor_t + 0.2, $fn = 20);

        // Panel DC jack in the +Y (back) wall
        translate([jack_x, outer_d - wall - 0.1, jack_z]) rotate([-90, 0, 0])
            cylinder(d = jack_d, h = wall + 0.2, $fn = 40);
    }

    // Pi Zero 2 W, PCA9685: M2.5 posts
    for (h = pi_h)  post(pi_at + h, post_d, post_h, m25_pilot);
    for (h = pca_h) post(pca_at + h, post_d, post_h, m25_pilot);
    // relay, ULN2003: 8 × 8 corner blocks (drill in place if your clone differs)
    for (h = rly_h) block(rly_at + h, post_h);
    for (h = uln_h) block(uln_at + h, post_h);
    // Pololu regulators: M2 posts on the diagonal
    for (h = d22_h) post(d22_at + h, pol_d, pol_h, m2_pilot);
    for (h = d50_h) post(d50_at + h, pol_d, pol_h, m2_pilot);
    for (h = d36_h) post(d36_at + h, pol_d, pol_h, m2_pilot);
    // HX711, L9110S: corner-stop pockets (board on 1 mm foam tape)
    pocket(hx_at, hx_sz);
    pocket(l91_at, l91_sz);
}

// Reference board outlines (not printed)
module tray_boards() color("ForestGreen", 0.6) {
    for (b = [[pi_at, pi_sz, post_h], [pca_at, pca_sz, post_h], [rly_at, rly_sz, post_h],
              [uln_at, uln_sz, post_h], [d22_at, d22_sz, pol_h], [d50_at, d50_sz, pol_h],
              [d36_at, d36_sz, pol_h], [hx_at + [0.3, 0.3], hx_sz - [0.6, 0.6], 1],
              [l91_at + [0.3, 0.3], l91_sz - [0.6, 0.6], 1]])
        translate([b[0][0], b[0][1], floor_t + b[2]]) cube([b[1][0], b[1][1], 1.6]);
}

electronics_tray();
if (show_boards) %tray_boards();
