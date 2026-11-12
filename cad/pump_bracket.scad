// =============================================
// Riftbound Card Sorter — Vacuum pump bracket (R385 12 V diaphragm pump)
// =============================================
// Holds the R385 pump (vacuum source for the pick-arm cup) on the baseplate,
// front-left, with a TPU sleeve between the motor can and the printed clamp so
// the diaphragm buzz does not reach the baseplate / pick arm.
//
// PUMP (typical R385 / "385" aquarium diaphragm pump, e.g. Gikfun; measure yours):
//   motor RS-385 can Ø27.6 × 38 (rear boss + solder tabs ≈ 4 more),
//   pump head ≈ 40 wide × 36 tall × 32 long on the shaft end, two Ø8.5 nozzles
//   ≈ 15 long on the head end face. Overall ≈ 90 × 40 × 36.
//   Axis along machine X, head/nozzles toward +X (toward the arm tower,
//   where the 4 mm vacuum tube goes up the column).
//
// PLACEMENT (machine coords, bolts on 4 real baseplate grid holes):
//   axis Y −210, Z 28; can X −268..−230, head X −230..−198, nozzles to X ≈ −183.
//   Bracket X −276..−234, Y −234..−186, Z 4..47.
//   Grid holes (tile 0,0: X −270..−120, Y −255..−105 every 30): (−270, −225), (−270, −195),
//   (−240, −225), (−240, −195): 4 × M3 × 20 SHCS + washer + nut
//   (base 5 + tile 4 + 6 mm board = 15 clamp, + 4 → 19 → M3 × 20).
//   Clear of: arm-tower foot (X −188..−112, Y −173..−122: ≥ 13 mm in Y),
//   hopper (Y ≥ −65.6), riser (X ≥ −165), the arm sweep (all ≥ Y −152 and
//   Z ≥ 60 at this X) and the shuttle (X ≥ 92).
//
// ISOLATION: a TPU 95A sleeve (part="sleeve") on the can; the clamp halves
//   close a 1.0 mm gap onto it (≈ 0.5 mm radial squeeze of the 1.7 mm wall),
//   so the preload is set by geometry, not by screw torque. The sleeve's end
//   flanges keep it (and the pump) from walking axially. No TPU? Wrap the can
//   in 1.5 mm neoprene / EPDM strip, 18 mm wide, instead.
//
// PARTS (`part`, print orientation):
//   base    base flange + lower saddle (2 × M3 heat-set inserts)  upright, no supports
//   cap     clamp strap                                             on its end face, no supports
//   sleeve  TPU isolation sleeve                                    upright, no supports
// HARDWARE: 4 × M3 × 20 SHCS + washer + nut (base → baseplate),
//   2 × M3 × 10 SHCS + 2 × M3 heat-set inserts (Ø4.0 × 5.7) (cap → base).
// =============================================

use <machine_frame.scad>

/* [Export] */
part = "base";        // base | cap | sleeve | assembly

$fn = 64;
bt = frame_base_top();                 // 4

// ── Pump ────────────────────────────────────────────────────────────────────
can_d   = 27.6;   can_l  = 38;
head_w  = 40;     head_h = 36;  head_l = 32;   head_dz = -1;   // head centre below the axis
noz_d   = 8.5;    noz_l  = 15;  noz_dy = 9;
pump_y  = -210;   pump_z = bt + 24;            // axis: Y −210, Z 28
can_x0  = -268;                                 // motor rear (can end)

// ── Sleeve / clamp ──────────────────────────────────────────────────────────
slv_id  = 27.2;  slv_t = 1.7;  slv_od = slv_id + 2 * slv_t;   // 30.6
slv_fl  = 2;     slv_fl_od = slv_od + 4;                       // end flanges
sad_w   = 18;                         // saddle / cap width along X
sad_x0  = -264;                       // saddle X −264..−246 (washers at −266.5 / −243.5 clear)
gap     = 1.0;                        // clamp gap (closes on the sleeve)
r_in    = slv_od / 2;                 // cradle radius 15.3
cap_r   = r_in + 2.5;                 // cap ring outer radius 17.8
ear_y   = 20.5;                       // cap screws / inserts at Y = axis ± 20.5
sad_hy  = 24;                         // saddle half-width (Y)
ear_t   = 5;                          // cap ear thickness
ins_d   = 4.0;  ins_l = 5.7;

// ── Base flange ─────────────────────────────────────────────────────────────
base_t  = 5;
base_x  = [-276, -234];  base_y = [-234, -186];
// baseplate grid: 3 × 3 tiles of 190 × 180 from X −285, Y −270, holes every
// 30 mm starting 15 mm in from each tile edge (X restarts per tile column)
function on_grid1(v, x0, tile, n) =
    let(t = floor((v - x0) / tile), r = (v - x0) - t * tile - 15)
    t >= 0 && t < n && r >= -1e-6 && abs(r / 30 - round(r / 30)) < 1e-6 && r <= tile - 30 + 1e-6;
function on_grid(p) = on_grid1(p[0], -285, 190, 3) && on_grid1(p[1], -270, 180, 3);
holes   = [[-270, -225], [-270, -195], [-240, -225], [-240, -195]];
for (h = holes) assert(on_grid(h), str("pump bracket hole ", h, " off the baseplate grid"));
assert(pump_z + head_dz - head_h / 2 > bt + 2, "pump head too close to the baseplate");
assert(pump_z - r_in - (bt + base_t) >= 3, "too little material under the cradle");
for (h = holes) assert(h[0] + 3.5 <= sad_x0 || h[0] - 3.5 >= sad_x0 + sad_w, "washer hits the saddle");

echo(str("PUMP BRACKET: axis Y ", pump_y, " Z ", pump_z, "; can X ", can_x0, "..", can_x0 + can_l,
         "; head to X ", can_x0 + can_l + head_l, "; nozzle tips X ", can_x0 + can_l + head_l + noz_l,
         "; grid holes ", holes));

// =========================================================================
module xcyl(r, x0, x1, fn = 64) translate([x0, 0, 0]) rotate([0, 90, 0]) cylinder(r = r, h = x1 - x0, $fn = fn);

// Everything below in a pump-local frame: Y/Z relative to the axis, X machine.
module at_axis() translate([0, pump_y, pump_z]) children();

module bracket_base() {
    difference() {
        union() {
            translate([base_x[0], base_y[0], bt]) cube([base_x[1] - base_x[0], base_y[1] - base_y[0], base_t]);
            at_axis() translate([sad_x0, -sad_hy, bt + base_t - pump_z - 0.01])
                cube([sad_w, 2 * sad_hy, pump_z - gap / 2 - (bt + base_t) + 0.01]);
        }
        at_axis() {
            xcyl(r_in, sad_x0 - 1, sad_x0 + sad_w + 1);
            for (s = [-1, 1]) translate([sad_x0 + sad_w / 2, s * ear_y, -gap / 2 - ins_l - 0.5])
                cylinder(d = ins_d, h = ins_l + 1, $fn = 24);
        }
        for (h = holes) translate([h[0], h[1], bt - 0.1]) cylinder(d = 3.4, h = base_t + 0.2, $fn = 24);
    }
}

module bracket_cap() {
    at_axis() difference() {
        union() {
            intersection() {
                xcyl(cap_r, sad_x0, sad_x0 + sad_w);
                translate([sad_x0 - 1, -cap_r - 1, gap / 2]) cube([sad_w + 2, 2 * cap_r + 2, cap_r + 1]);
            }
            translate([sad_x0, -sad_hy, gap / 2]) cube([sad_w, 2 * sad_hy, ear_t]);
        }
        xcyl(r_in, sad_x0 - 1, sad_x0 + sad_w + 1);
        for (s = [-1, 1]) translate([sad_x0 + sad_w / 2, s * ear_y, 0])
            cylinder(d = 3.4, h = cap_r + 2, $fn = 24);
    }
}

module sleeve_local()   // along +Z, z = 0 at the −X flange outer face
    difference() {
        union() {
            cylinder(d = slv_fl_od, h = slv_fl);
            cylinder(d = slv_od, h = 2 * slv_fl + sad_w + 0.4);
            translate([0, 0, slv_fl + sad_w + 0.4]) cylinder(d1 = slv_od, d2 = slv_fl_od, h = slv_fl);
        }
        translate([0, 0, -1]) cylinder(d = slv_id, h = 2 * slv_fl + sad_w + 3);
    }
module bracket_sleeve()
    at_axis() translate([sad_x0 - 0.2 - slv_fl, 0, 0]) rotate([0, 90, 0]) sleeve_local();

// Pump reference solid (not printed)
module hw_pump() color("DimGray") at_axis() {
    xcyl(can_d / 2, can_x0, can_x0 + can_l);
    xcyl(5, can_x0 - 4, can_x0);                                     // rear boss + tabs
    translate([can_x0 + can_l, -head_w / 2, head_dz - head_h / 2]) cube([head_l, head_w, head_h]);
    for (s = [-1, 1]) translate([0, s * noz_dy, 0])
        xcyl(noz_d / 2, can_x0 + can_l + head_l - 0.01, can_x0 + can_l + head_l + noz_l, 32);
}

// Machine-coordinate placement for assembly.scad (replaces the asm_pump stand-in)
module asm_pump_bracket(show_pump = true) {
    color("SlateGray") { bracket_base(); bracket_cap(); }
    color("Black") bracket_sleeve();
    if (show_pump) hw_pump();
}
function pump_nozzle_tip() = [can_x0 + can_l + head_l + noz_l, pump_y, pump_z];   // vacuum tube start

// =========================================================================
if (part == "base")     translate([0, 0, -bt]) bracket_base();
if (part == "cap")      translate([0, 0, sad_x0 + sad_w]) rotate([0, 90, 0]) bracket_cap();   // end face down
if (part == "sleeve")   sleeve_local();
if (part == "assembly") asm_pump_bracket();
