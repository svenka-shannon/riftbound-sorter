// =============================================
// Riftbound Card Sorter — Baseplate Tile (+ bow-tie alignment key)
// =============================================
// Machine baseplate = 3 × 3 grid of IDENTICAL tiles, 190 × 180 × 4 mm
// (fits the P1S 256 × 256 bed), assembled 570 × 540, on a 6 mm backing board.
// Material: PLA, 0.2 mm, 40 % infill, 4 perimeters.
//
// ALIGNMENT: printed BOW-TIE (butterfly) KEYS across every tile-to-tile seam.
//   Each tile edge has 2 dovetail half-pockets, open to the top, 2.4 deep;
//   two butting tiles form one full bow-tie pocket, and a printed key (2.3
//   thick, 0.15 mm clearance per side) pressed in from above locks the seam
//   in X and Y and pulls the tiles together (the 1:3 dovetail flare).
//   Vertical flushness comes from the backing board underneath. The key sits
//   0.1 mm below the tile top, so parts bolted across a seam still sit flat.
//   (The old 3 mm horizontal pins pointed INTO the tile and could never
//   engage; a Ø3 pin in a 4 mm plate would also leave 0.5 mm walls.)
//   Pockets sit midway between grid holes (tile-local X 30 / 150 on the
//   front/back edges, Y 30 / 150 on the left/right edges); a pocket reaches
//   8.15 mm in from the edge, the first hole row starts at 13.3 (≥ 5.15 mm
//   of solid tile between). All tiles are the same, so matching pockets
//   always face each other; the unused half-pockets on the outer border are
//   harmless.
//   Keys needed: 12 interior seams × 2 = 24 (`part = "keys"` prints 24).
//
// M3 GRID: Ø3.4 through holes every 30 mm, 15 mm in from each tile edge,
//   6 × 6 per tile. In machine coordinates (tiles at X −285 + 190·c,
//   Y −270 + 180·r, assembly.scad asm_baseplate):
//     X RESTARTS per tile column (190 is not a multiple of 30):
//       c 0: X −270, −240, −210, −180, −150, −120
//       c 1: X  −80,  −50,  −20,   10,   40,   70
//       c 2: X  110,  140,  170,  200,  230,  260
//     Y is one continuous grid (180 = 6 × 30): Y = −255 + 30·j, j 0..17
//       (−255 .. 255).
//   Every part's bolt holes must land on these (pump_bracket.scad has an
//   on_grid() check).
//   Underside: each hole has a Ø5.2 × 1.5 counterbore so the barrel of a
//   board tee-nut longer than the board (see BOARD FASTENING) has room.
//
// BOARD FASTENING (recommendation, see INSTALL below): M3 four-prong
//   TEE-NUTS (zinc steel, barrel Ø4.5 × 5, flange Ø13 × 0.9, e.g. FastenRight
//   FF01 M3) hammered into the 6 mm board FROM BELOW, once, at every grid hole
//   a part uses, before anything is assembled. Then every baseplate screw goes
//   in from above and nothing ever has to be reached under the loaded board.
//   Screw lengths stay as listed in the part files (clamp + 4): the screw tip
//   passes through the 5.9 mm of tee-nut thread and pokes ≤ 7 mm out below
//   the flange (rubber feet ≥ 10 mm). The barrel stops 1 mm below the board
//   top (Ø4.5 < board 6); the counterbore above takes barrels up to 7.5 mm.
//   Rejected: screw-in / press-in threaded inserts for wood. M3 ones are
//   typically 8–10 mm long (longer than the 6 mm board), and they hold only
//   by their outer thread in MDF, which strips easily; the tee-nut's flange
//   bears on the board underside, so tightening pulls it INTO the board.
//
// part = "tile" (default) | "key" | "keys" (24 keys on a 6 × 4 grid)
// =============================================

/* [Export] */
part = "tile";

tile_w    = 190;
tile_d    = 180;
tile_h    = 4;

// M3 component mounting holes (grid pattern every 30mm)
mount_hole_d = 3.4;
mount_inset  = 15;
mount_step   = 30;
cb_d         = 5.2;  // underside counterbore (tee-nut barrel Ø4.5 + clearance)
cb_h         = 1.5;

// Bow-tie key (dimensions of the KEY; pockets are 0.15 larger per side)
key_half   = 8;      // length on each side of the seam
key_neck   = 6;      // width at the seam
key_end    = 11.3;   // width at the far ends (flare 1:3 per side)
key_t      = 2.3;    // thickness
key_clr    = 0.15;   // per side, in the pocket
pocket_d   = 2.4;    // pocket depth from the tile top (1.6 mm floor left)
key_pos_x  = [30, 150];   // along the front (y = 0) / back (y = tile_d) edges
key_pos_y  = [30, 150];   // along the left (x = 0) / right (x = tile_w) edges

function baseplate_tile_size() = [tile_w, tile_d, tile_h];

// half bow-tie on one side of the seam: 2D, seam on x = 0, pointing +x
module key_half_2d(c = 0)
    polygon([[-0.01, -(key_neck / 2 + c)], [key_half + c, -(key_end / 2 + c)],
             [key_half + c, key_end / 2 + c], [-0.01, key_neck / 2 + c]]);

module key_2d(c = 0) union() { key_half_2d(c); mirror([1, 0]) key_half_2d(c); }

// one half-pocket on the tile edge: (ex, ey) on the edge, a = inward direction
module key_pocket(ex, ey, a)
    translate([ex, ey, tile_h - pocket_d]) rotate([0, 0, a])
        linear_extrude(pocket_d + 0.1) key_half_2d(key_clr);

module baseplate_tile() {
    difference() {
        cube([tile_w, tile_d, tile_h]);

        // Component mounting holes grid
        for (x = [mount_inset : mount_step : tile_w - mount_inset])
            for (y = [mount_inset : mount_step : tile_d - mount_inset])
                translate([x, y, -0.1])
                    cylinder(d = mount_hole_d, h = tile_h + 0.2, $fn = 16);
        // underside counterbore for a tee-nut barrel (prints on the bed: a
        // 0.9 mm annular step at Z 1.5, no supports)
        for (x = [mount_inset : mount_step : tile_w - mount_inset])
            for (y = [mount_inset : mount_step : tile_d - mount_inset])
                translate([x, y, -0.1])
                    cylinder(d = cb_d, h = cb_h + 0.1, $fn = 24);

        // Bow-tie half-pockets on all four edges
        for (x = key_pos_x) {
            key_pocket(x, 0, 90);           // front edge, pocket points +Y
            key_pocket(x, tile_d, -90);     // back edge, points -Y
        }
        for (y = key_pos_y) {
            key_pocket(0, y, 0);            // left edge, points +X
            key_pocket(tile_w, y, 180);     // right edge, points -X
        }
    }
}

// Key in print orientation (flat), 0.4 × 45° chamfer on the bottom edges
// as a lead-in so it presses into the pocket.
// (each half is convex, so hull the halves separately: a hull of the whole
// bow-tie would fill in its waist)
module baseplate_key()
    for (m = [0, 1]) mirror([m, 0, 0]) hull() {
        translate([0, 0, 0.4]) linear_extrude(key_t - 0.4) key_half_2d();
        linear_extrude(0.41) offset(delta = -0.4) key_half_2d();
    }

if (part == "tile") baseplate_tile();
if (part == "key")  baseplate_key();
if (part == "keys") for (i = [0 : 5], j = [0 : 3]) translate([i * 22, j * 16, 0]) baseplate_key();

assert(tile_h - cb_h >= 2.5, "counterbore leaves too thin a tile");
// Sanity: a pocket reaches key_half + key_clr = 8.15 in from the edge, the
// first grid-hole row starts at 15 - 1.7 = 13.3 → ≥ 5.15 mm of tile between.
assert(mount_inset - mount_hole_d / 2 - (key_half + key_clr) >= 1.2, "key pocket too close to a grid hole");
assert(key_pos_x[1] + key_end / 2 + key_clr < tile_w - key_half - key_clr - 1.2 &&
       key_pos_y[1] + key_end / 2 + key_clr < tile_d - key_half - key_clr - 1.2, "key pockets meet at a corner");

// =============================================
// PRINT: tile flat, top up (pockets open upward: no bridges). Keys flat.
// INSTALL: lay the 9 tiles on the board in a 3 × 3 grid, all the same way
//   round (pockets facing pockets), press a key into every seam pocket
//   (24, flush −0.1 mm; a light tap with a mallet).
//   TEE-NUTS (recommended, do this before any part goes on): with the tiles
//   clamped in place, drill Ø3.4 down through every grid hole a part uses
//   (the hole tables in docs/ASSEMBLY.md), lift the tiles off, open those
//   board holes to Ø4.5 from below, and tap an M3 tee-nut into each from
//   below (prongs into the board, flange flush). Lay the tiles back on.
//   Then bolt the parts from above. Without tee-nuts: washer + nut under the
//   board on every screw (the parts' BOM lines), which means lifting the
//   loaded machine for every later bolt.
//   Optional: 2 × M3 × 16 per tile at free grid holes (tile 4 + board 6 = 10
//   clamp; into a tee-nut, or washer + nut) to hold the tiles to the board.
// =============================================
