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
//   Bracket X −276..−200, Y −234..−186, Z 4..47 (saddle + cap at X −264..−246,
//   head cradle at X −232..−200).
//   Grid holes (tile 0,0: X −270..−120, Y −255..−105 every 30): (−270, −225), (−270, −195),
//   (−240, −225), (−240, −195): 4 × M3 × 20 SHCS into the board's tee-nuts
//   (base 5 + tile 4 + 6 mm board = 15 clamp, + 4 → 19 → M3 × 20; washer + nut
//   under the board is the fallback).
//   Clear of: arm-tower foot (X −188..−112, Y −173..−122: ≥ 13 mm in Y),
//   hopper (Y ≥ −65.6), riser (X ≥ −165), the arm sweep (all ≥ Y −152 and
//   Z ≥ 60 at this X) and the shuttle (X ≥ 92).
//
// ASSEMBLY ORDER — BASE BEFORE PUMP: the grid fixes the X −240 bolts at
//   Y −210 ± 15, and the can (r 13.8) leaves only 1.2 mm outside its outline: a
//   2.5 mm hex key (r 1.25) on those bolts is 0.05 mm inside the can's plan
//   outline, so they cannot be driven with the pump in place. Bolt the base
//   to the board first (all 4), then lay the pad, sleeve + pump and the cap.
//   To remove the base later, take the cap and pump off first.
//
// HEAD CRADLE: the head (≈ 32 long, ≈ 60 g with the diaphragm) used to
//   cantilever 50 mm from the 18 mm clamp. The base now runs on under the head
//   as a shallow cradle: a pocket (floor Z 7.5) holding a 1.5 mm TPU pad
//   (part="pad", or cut from the same neoprene strip) that the head bottom
//   (Z 9) rests on, and two 6 mm cheeks 1 mm off the head sides that stop it
//   rocking in Y. The pad keeps the head isolated like the can sleeve. Real
//   R385 heads vary: if the pad does not touch, shim it; it must not lift the
//   can off the saddle.
//
// VENT VALVE (part="valve_clip", a separate small bracket on 2 grid holes):
//   uxcell 2-way NORMALLY CLOSED mini air solenoid valve, DC 12 V 0.2 A (2.2 W),
//   0–350 mmHg, Ø3 mm barbs, 15 × 14 × 34 mm overall incl. the axial barb,
//   11 cm leads out of the coil end (listing: walmart.com/ip/809112545, the
//   common "0520-size" mini valve body). Measure yours: the
//   model below (coil 15 × 14 × 22, head Ø10 × 6, axial barb Ø3 × 6, side vent
//   barb Ø3 × 5) is a reference envelope, not a vendor drawing.
//   It lies along Y with the axial (line) barb toward +Y and the side barb up
//   (open to air = the vent). Clip on grid holes (−180, −255), (−150, −255):
//   2 × M3 × 20 SHCS into tee-nuts (plate 5 + tile 4 + board 6 = 15, as the
//   base; washer + nut fallback). The valve snaps down between two lipped walls onto a strip of 1 mm
//   foam tape (floor Z 19.5, valve axis Z 28 = the vacuum line height).
//   TEE: a 1/8" (3.2 mm) barbed plastic tee (≈ 22 × 11, Ø3 barbs) hangs in
//   the tube at X −165, Y −210, Z 28, 18 mm past the pump nozzle; its branch
//   (−Y) goes to the valve's axial barb with a 20 mm piece of 2 × 4 silicone
//   (PU 4 × 2.5 is a tight push onto a Ø3 barb: warm it). Valve clip X −186..−144,
//   Y −264..−246, Z 4..37.7; clear of the arm tower foot (Y ≥ −173: 73 mm), the
//   arm sweep (Y ≥ −152), the hopper (Y ≥ −65.6) and the pump base (X ≤ −200).
//
// ISOLATION: a TPU 95A sleeve (part="sleeve") on the can; the clamp halves
//   close a 1.0 mm gap onto it (≈ 0.5 mm radial squeeze of the 1.7 mm wall),
//   so the preload is set by geometry, not by screw torque. The sleeve's end
//   flanges keep it (and the pump) from walking axially. No TPU? Wrap the can
//   in 1.5 mm neoprene / EPDM strip, 18 mm wide, instead.
//
// PARTS (`part`, print orientation):
//   base        base flange + lower saddle + head cradle (2 × M3 inserts)  upright, no supports
//   cap         clamp strap                                    on its end face, no supports
//   sleeve      TPU isolation sleeve                           upright, no supports
//   pad         TPU head pad 30 × 40 × 1.5                     flat, no supports
//   valve_clip  vent-valve clip                                upright, no supports (lips 45°)
// HARDWARE: 4 × M3 × 20 SHCS into board tee-nuts (base → baseplate; washer + nut fallback),
//   2 × M3 × 10 SHCS + 2 × M3 heat-set inserts (Ø4.0 × 5.7) (cap → base),
//   2 × M3 × 20 SHCS into board tee-nuts (valve clip → baseplate; washer + nut fallback),
//   1 × 12 V NC mini solenoid valve, 1 × 1/8" barbed tee, 20 mm 2 × 4 silicone tube,
//   1 mm foam tape 14 × 16 (valve seat).
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
base_x  = [-276, -200];  base_y = [-234, -186];
// ── Head cradle (under the pump head, X −230..−198) ─────────────────────────
pad_t   = 1.5;                        // TPU / neoprene pad
crd_x   = [-232, -200];               // cradle pocket + cheeks along X
crd_gap = 1.0;                        // cheek ↔ head side
crd_h   = 6;                          // cheek height above the flange top
head_z0 = pump_z + head_dz - head_h / 2;          // 9: head underside
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
for (h = holes) assert(h[0] + 3.5 <= crd_x[0], "washer hits the head cradle");
assert(head_z0 - pad_t > bt + 2, "head cradle floor too thin");
assert(head_w / 2 + crd_gap + 3 <= sad_hy, "cradle cheeks leave the base");

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
            // head-cradle cheeks (1 mm off the head sides)
            for (s = [-1, 1]) translate([crd_x[0], pump_y + (s > 0 ? head_w / 2 + crd_gap : -head_w / 2 - crd_gap - 3), bt + base_t - 0.01])
                cube([crd_x[1] - crd_x[0] - 2, 3, crd_h + 0.01]);
        }
        // head-cradle pocket for the pad (floor = head underside − pad)
        translate([crd_x[0], pump_y - head_w / 2 - crd_gap, head_z0 - pad_t])
            cube([crd_x[1] - crd_x[0] + 1, head_w + 2 * crd_gap, base_t]);
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

module head_pad_local() cube([crd_x[1] - crd_x[0] - 2, head_w, pad_t]);
module bracket_pad() translate([crd_x[0] + 1, pump_y - head_w / 2, head_z0 - pad_t]) head_pad_local();

// =========================================================================
// VENT VALVE + TEE (reference envelopes) and the valve clip
// =========================================================================
// valve-local frame: coil end (leads) at z 0, axis +z, side (vent) barb +x
vv_w = 15; vv_d = 14; vv_coil = 22;          // coil body 15 (x) × 14 (y) × 22
vv_head_d = 10; vv_head_l = 6;               // valve head
vv_barb_d = 3; vv_barb_l = 6;                // axial (line) barb → total 34
vv_side_l = 5; vv_side_z = vv_coil + 3;      // side (vent) barb
vv_len = vv_coil + vv_head_l + vv_barb_l;    // 34
// placement: axis along +Y at X −165, Z 28 (line height), coil end at Y −264
vv_x = -165; vv_z = pump_z; vv_y0 = -264;
tee_c = [-165, pump_y, pump_z];              // tee centre (run along X, branch −Y)
tee_run = 22; tee_br = 11; tee_d = 6;        // 1/8" barbed tee envelope
vfoam = 1.0;                                 // foam tape under the valve
vc_holes = [[-180, -255], [-150, -255]];
vc_x = [-186, -144]; vc_y = [-264, -246]; vc_t = 5;
vc_wall = 2; vc_clr = 0.2; vc_lip = 0.8; vc_lip_h = 2.0;
vc_floor = vv_z - vv_w / 2 - vfoam;          // 19.5
vc_top = vv_z + vv_w / 2 + vc_clr + vc_lip_h; // 37.7
for (h = vc_holes) assert(on_grid(h), str("valve clip hole ", h, " off the baseplate grid"));
for (h = vc_holes) assert(abs(h[0] - vv_x) - 3.5 >= vv_d / 2 + vc_clr + vc_wall + 1.5, "valve clip washer hits a wall");
assert(vv_y0 >= frame_base_y()[0] + 4, "valve leads leave the baseplate");
let(g = (tee_c[1] - tee_br) - (vv_y0 + vv_len))   // free tube between the two barb tips
    assert(g >= 5 && g <= 15, str("tee branch ↔ valve barb gap ", g, " (20 mm tube wants 5..15)"));

module valve_local() {
    translate([-vv_w / 2, -vv_d / 2, 0]) cube([vv_w, vv_d, vv_coil]);
    translate([0, 0, vv_coil - 0.01]) cylinder(d = vv_head_d, h = vv_head_l + 0.01, $fn = 32);
    translate([0, 0, vv_coil + vv_head_l - 0.01]) cylinder(d = vv_barb_d, h = vv_barb_l + 0.01, $fn = 24);
    translate([0, 0, vv_side_z]) rotate([0, 90, 0]) cylinder(d = vv_barb_d, h = vv_head_d / 2 + vv_side_l, $fn = 24);
}
// local z → +Y, local x → +Z, local y → −X
module hw_valve() color("RoyalBlue")
    translate([vv_x, vv_y0, vv_z]) rotate([0, 0, 90]) rotate([0, 90, 0]) rotate([0, 0, 180]) valve_local();
module hw_tee() color("WhiteSmoke") translate(tee_c) {
    rotate([0, 90, 0]) cylinder(d = tee_d, h = 10, center = true, $fn = 24);
    rotate([90, 0, 0]) cylinder(d = tee_d, h = 5, $fn = 24);
    for (s = [-1, 1]) translate([s * 5, 0, 0]) rotate([0, s * 90, 0]) cylinder(d1 = 3.6, d2 = 2.6, h = tee_run / 2 - 5, $fn = 24);
    translate([0, -5, 0]) rotate([90, 0, 0]) cylinder(d1 = 3.6, d2 = 2.6, h = tee_br - 5, $fn = 24);
}
function vent_tee_pos()     = tee_c;                                  // tee centre
function vent_tee_branch()  = [tee_c[0], tee_c[1] - tee_br, tee_c[2]];// branch barb tip
function vent_valve_port()  = [vv_x, vv_y0 + vv_len, vv_z];           // valve axial barb tip
function vent_valve_root()  = [vv_x, vv_y0 + vv_coil + vv_head_l, vv_z];
function vent_valve_leads() = [vv_x, vv_y0, vv_z];                    // coil end (11 cm leads)
function pump_rear()        = [can_x0 - 4, pump_y, pump_z];           // pump terminals end

module valve_clip() {
    ix = vv_d / 2 + vc_clr;                       // channel half-width (X)
    difference() {
        union() {
            translate([vc_x[0], vc_y[0], bt]) cube([vc_x[1] - vc_x[0], vc_y[1] - vc_y[0], vc_t]);
            translate([vv_x - ix - vc_wall, vc_y[0], bt + vc_t - 0.01])
                cube([2 * (ix + vc_wall), vc_y[1] - vc_y[0], vc_top - bt - vc_t + 0.01]);
        }
        // channel down to the floor (open on top and at both ends)
        translate([vv_x - ix, vc_y[0] - 1, vc_floor]) cube([2 * ix, vc_y[1] - vc_y[0] + 2, vc_top]);
        for (h = vc_holes) translate([h[0], h[1], bt - 0.1]) cylinder(d = 3.4, h = vc_t + 0.2, $fn = 24);
    }
    // snap lips: 45° underside + 45° lead-in on top (prints without supports)
    for (s = [-1, 1]) translate([vv_x + s * ix, vc_y[0], 0]) rotate([90, 0, 0]) mirror([0, 0, 1])
        linear_extrude(vc_y[1] - vc_y[0])
            polygon([[s * 0.3, vv_z + vv_w / 2 + vc_clr - 0.3], [-s * vc_lip, vv_z + vv_w / 2 + vc_clr + vc_lip],
                     [-s * vc_lip, vc_top - vc_lip], [s * 0.3, vc_top - 0.01]]);   // 0.3 into the wall
}

// Machine-coordinate placement for assembly.scad (replaces the asm_pump stand-in)
module asm_pump_bracket(show_pump = true) {
    color("SlateGray") { bracket_base(); bracket_cap(); valve_clip(); }
    color("Black") { bracket_sleeve(); bracket_pad(); }
    if (show_pump) hw_pump();
}
// vent valve + tee: drawn with the vacuum tube (they are part of the line)
module asm_vent_valve() { hw_valve(); hw_tee(); }
function pump_nozzle_tip() = [can_x0 + can_l + head_l + noz_l, pump_y, pump_z];   // vacuum tube start

// =========================================================================
if (part == "base")     translate([0, 0, -bt]) bracket_base();
if (part == "cap")      translate([0, 0, sad_x0 + sad_w]) rotate([0, 90, 0]) bracket_cap();   // end face down
if (part == "sleeve")   sleeve_local();
if (part == "pad")      head_pad_local();
if (part == "valve_clip") translate([0, 0, -bt]) valve_clip();
if (part == "assembly") { asm_pump_bracket(); asm_vent_valve(); }
