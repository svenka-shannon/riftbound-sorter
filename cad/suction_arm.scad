// =============================================
// Riftbound Card Sorter — Pick Arm (single-servo parallelogram, suction cup)
// =============================================
// Replaces the old vertical-axis swing arm. ONE MG996R (PCA9685 ch0) with its
// axis along machine Y swings a crank in the XZ plane. A parallelogram keeps
// the "hand" (cup carrier) in pure TRANSLATION, so the cup always points
// straight down and the card stays flat: it is lifted straight up off the
// stack, carried over the top of a ~170° arc and lowered onto the belt.
//
// ── KINEMATICS (machine coords, see machine_frame.scad) ─────────────────────
//   Crank angle th is measured in the XZ plane from +X towards +Z about the
//   servo axis A. Every hand point moves on a circle of radius R.
//   Pick: th_p = 178° (2° above horizontal → lift is vertical to within 2°;
//         first 5 mm of lift moves the card 0.4 mm in X). The cup lip is
//         commanded pick_over = 3 mm BELOW the top card; the spring slider and
//         the bellows take that up, so height errors never press hard.
//   Drop: th_d ≈ 8° — card underside frame_drop_clear() above the belt.
//   Chord pick→drop = 120 mm → R ≈ 60.3; pivot A ≈ (X -154.7, Z 151.8).
//   All numbers are DERIVED below from the frame and echoed ("PICK ARM: ...").
//
// ── WHY THREE PARALLEL LINKS (not one) ──────────────────────────────────────
//   A plain parallelogram has a change point where the crank is collinear with
//   the ground link; any sweep near 180° must pass it, and there the hand can
//   flip into the anti-parallelogram. So the hand rides on the crank PLUS two
//   followers whose ground offsets are 90° apart ("quartered", like locomotive
//   side rods): whenever one follower is at its change point (th 25.5° for C,
//   115.5° for B) the other is exactly 90° away from its own. The three
//   ground pivots A (servo), B, C sit BELOW A at 295.5° / 205.5°, 45 mm out,
//   so no pin ever crosses another link inside the working arc (the
//   pin-crossing directions 205.5°, 295.5°, 340.5° all lie outside
//   th 8..178, ≥ 27.5° margin; the full servo range 0..180° is still safe).
//   Both plates carry the SAME pivot pattern and all links are the same
//   length; print both plates flat and both followers together, so print
//   scaling errors cancel (the mechanism stays a true triple parallelogram).
//
// ── LAYERS ALONG Y (the card side is +Y) ────────────────────────────────────
//   hand plate  Y -42..-36   (card edge at |Y| ≤ 33 incl. hopper play)
//   link B      Y -48..-43   ┐ the two followers are the same printed part
//   link C      Y -56.5..-51.5┘ (3.5 / 2.5 mm gaps: pin ends must not reach
//   crank       Y -65..-59      the next layer) — crank on a 25T aluminium disc horn
//   ground plate Y -80..-72, MG996R behind it (tabs on the plate's back)
//   tower       column Y -152..-122 → clear of the motor bracket (Y ≥ -113.5)
//               and the riser (Y ≥ -113); foot on the baseplate grid
//               (X -180/-120, Y -165/-135).
//
// ── VACUUM TUBE (4 mm OD) ───────────────────────────────────────────────────
//   cup → M5 barb → loop → straight along the A' axis INTO the hollow A' pin
//   (8×6 mm tube, fixed in the hand) → out behind the crank → free "spoke" of
//   constant length to an anchor/strain-relief bell ON THE SERVO AXIS behind
//   the servo (tower post, Y -142). Because the hand point A' always stays R
//   from the axis, that spoke never stretches; it only whirls (no twist, no
//   rubbing), and it never meets a link (it is behind them all).
//
// ── PARTS (print orientation via `part`, all PETG 0.2 mm, 4 walls, 40 %) ───
//   head   ground plate + servo cradle + floor  front face DOWN, no supports
//   tower  foot + column + tube anchor post      upright, no supports
//   crank                                        flat, no supports
//   link   ×2 (B and C — print together)         flat, no supports
//   hand   hand plate + slider beams             back face DOWN (beams up)
//   sled   cup carrier                           upright (hex pocket down)
//   sleeves 4 spacer sleeves                     upright
//
// See the PRINT/HARDWARE notes at the bottom.
// =============================================

use <machine_frame.scad>

/* [Export] */
part        = "assembly";  // assembly | head | tower | crank | link | hand | sled | sleeves
                           // ref_fixed | ref_crank | ref_link_b | ref_link_c | ref_hand | ref_sled | ref_card
servo_angle = 90;          // for "assembly": PCA9685 ch0 angle (ARM_PICK/ARM_DROP/ARM_PARK)
show_card   = true;

$fn = 48;
eps = 0.01;

// ── Card / frame (single source: machine_frame.scad) ───────────────────────
card_l = 88;  card_w = 63;  card_t = 0.33;      // = machine_frame card_* (raw cards)
card_z = frame_card_z();                        // 90.9: top card in hopper = belt face
pick_x = frame_hopper_x();                      // -215
drop_x = frame_drop_x();                        // -95
card_dy_max = 1.5;                              // card Y play in the hopper cavity (66 - 63)/2

// ── Arc design inputs ───────────────────────────────────────────────────────
pick_over = 3;      // cup lip nominal BELOW the top card at ARM_PICK (slider + bellows absorb)
th_p      = 178;    // crank angle at pick
h_cup     = 66;     // free cup lip → hand pivot A' (vertical). Sets pivot height; chosen so
                    // the hand plate / links stay ≥ 5 mm above the rail top (Z 99) and the
                    // hopper rim/flag (Z 94.4 / ~101).

lip_pick = card_z - pick_over;                          // 87.9
lip_drop = card_z + frame_drop_clear() + card_t;        // 94.23 (card underside 93.9)

function _thd(r) = asin((lip_drop - lip_pick) / r + sin(th_p));
function _rr(r)  = (drop_x - pick_x) / (cos(_thd(r)) - cos(th_p));
R      = _rr(_rr(_rr(60)));                             // crank = link length
th_d   = _thd(R);                                       // crank angle at drop
px     = pick_x - R * cos(th_p);                        // servo axis A, machine X
pz     = lip_pick + h_cup - R * sin(th_p);              // servo axis A, machine Z
th_mid = (th_p + th_d) / 2;                             // crank angle at servo 90°

// Servo ↔ crank mapping: servo 90° = th_mid (crank ~vertical, arm parked on top).
// Increasing servo angle = increasing th (CW seen from the spline side). If your
// servo turns the other way, swap ARM_PICK/ARM_DROP in hardware/servos.py — the
// arc is symmetric about 90°, so a reversed servo still only visits the safe arc.
function pa_theta(s) = th_mid + (s - 90);
function pa_servo(th) = 90 + (th - th_mid);
s_pick = pa_servo(th_p);    // ≈ 175
s_drop = pa_servo(th_d);    // ≈ 5
s_park = 90;

// ── Parallelogram pivot pattern (same on ground plate and hand plate) ──────
Lg   = 45;
phiB = 295.5;
phiC = 205.5;
gB   = Lg * [cos(phiB), sin(phiB)];      // [19.4, -40.6]
gC   = Lg * [cos(phiC), sin(phiC)];      // [-40.6, -19.4]

// ── Y layers ────────────────────────────────────────────────────────────────
hp_t  = 6;   hp_y1 = -36;            hp_y0 = hp_y1 - hp_t;          // hand plate
lk_t  = 5;
lb_y1 = hp_y0 - 1;                   lb_y0 = lb_y1 - lk_t;          // link B
// Pin ends stick 1 mm out of their links (push-on retaining washers) into the
// GAPS. Coupler pin C' must never reach the crank layer (the crank sweeps over
// C' at th 25.5°), B' and the C ground pin must never reach the C/B layer
// (th 160.5°), so those two gaps are 2.5 / 3.5 mm.
lc_y1 = lb_y0 - 3.5;                 lc_y0 = lc_y1 - lk_t;          // link C
cr_t  = 6;
cr_y1 = lc_y0 - 2.5;                 cr_y0 = cr_y1 - cr_t;          // crank

// ── MG996R (TowerPro datasheet 40.7 × 19.7 × 42.9). Tab-hole pattern from the
//    shared frame_mg996r_hole_pitch() × frame_mg996r_hole_dx() (49.5 × 10,
//    machine_frame.scad), the same value the shuttle's ch1 / ch2 mounts use.
//    A real MG996R's tab holes are Ø4.5+ (grommet holes), so an M3 still finds
//    its insert for a pitch within about ±0.7 mm of this. Tab height / shaft
//    offset are typical values — MEASURE YOUR SERVO and adjust sv_tab_z0 /
//    horn_gap; a printed shim under the tabs is fine.
sv_l = 40.7;  sv_w = 19.7;  sv_case_h = 37.0;  sv_h = 42.9;   // bottom → spline top
sv_tab_z0 = 26.8;  sv_tab_t = 2.5;  sv_tab_span = 54.0;
sv_hole_p = frame_mg996r_hole_pitch();  sv_hole_dx = frame_mg996r_hole_dx();
sv_shaft_off = 10.2;                  // spline centre from case end
sv_spline_d = 5.9;
// 25T aluminium DISC horn (Ø25, 4× M3 tapped holes on 14–18 mm PCD)
horn_d = 25;  horn_t = 3;  horn_hub_d = 10;
horn_gap = 1.4;                       // horn front face above the spline top
spline_y = cr_y0 - horn_gap;          // spline top (crank sits on the horn face)
sv_y0    = spline_y - sv_h;           // servo bottom face
gp_y0    = sv_y0 + sv_tab_z0 + sv_tab_t;   // ground plate BACK face = tab top face
gp_t     = 8;
gp_y1    = gp_y0 + gp_t;
sv_zc    = (sv_shaft_off - (sv_l - sv_shaft_off)) / 2;  // case centre Z rel. A (-10.15)
sv_holes = [for (sz = [-1, 1]) for (sx = [-1, 1]) [sx * sv_hole_dx / 2, sv_zc + sz * sv_hole_p / 2]];

// ── Pins / bores ────────────────────────────────────────────────────────────
dowel_d = 4;  dowel_press = 3.95;  dowel_run = 4.15;
ap_od = 8;    ap_id = 6;  ap_press = 7.95;  ap_run = 8.15;     // hollow A' pin (8×6 tube)
ins_d = 4.1;  ins_l = 5.7;                                      // M3 heat-set insert
m3_clr = 3.4;
slv_d = 10;   slv_bore = 4.3;   slv_ap_d = 14;  slv_ap_bore = 8.3;
slv_gap = 0.3;                        // link ↔ sleeve end running gap

// ── Crank / links ───────────────────────────────────────────────────────────
cr_hub_r = 17;   cr_end_r = 9;   cr_w = 12;
lk_end_r = 7;    lk_w = 10;
horn_slot = [6.5, 9.5];               // radial slots for horn screws (PCD 13–19)

// ── Hand (hand-local: origin = A' in XZ, Y machine) ─────────────────────────
hp_ap_r = 10;  hp_pin_r = 7;
// Guide screws at X ±14.5: their Ø5.5 heads (fixed to the hand, lip-relative
// Z 21..24) have their inner edge at r 11.75, 1.25 outside the Ø21 bellows
// pad, which rides up with the sled into the heads' height band whenever the
// slider compresses (at rod_dx 12 the pad hit both heads at every pick).
beam_x  = [10.5, 18.5];               // |X| of the two slider beams (rel. A'), centred on the screws
beam_z  = [56, 64] - [h_cup, h_cup];  // beam Z rel. A' (lip-relative 56..64)
beam_y1 = 7;
rod_dx  = 14.5;                       // guide screws at X ±14.5, Y 0
gs_head_d = 5.5;  gs_head_h = 3;      // M3 SHCS head
// Sled (cup carrier), lip-relative Z, at rest (fully extended)
sl_z0 = 24;  sl_z1 = 38;  sl_hx = 19;  sl_hy = 7;
pad_hex_af = 8.0;  pad_top = 29;  web_t = 1.6;
sl_stroke = 10;
// SMC ZPT16BS-B5: Ø16 silicone bellows, M5 female, 29 tall, Ø21 max, hex 8 AF
pad_d = 21;  pad_lip_d = 18;
assert(rod_dx - gs_head_d / 2 - pad_d / 2 >= 1.0, "guide-screw heads within 1 mm of the bellows pad");
assert(sl_hx - rod_dx - m3_clr / 2 >= 2.5, "sled wall outside the guide bores too thin");
assert(min(beam_x[1] - rod_dx, rod_dx - beam_x[0]) - ins_d / 2 >= 1.9, "beam wall round the guide-screw insert too thin");

// ── Tower / column / anchor ─────────────────────────────────────────────────
hd_wall_x = [10.6, 14.6];   // head side walls |X| rel A (servo case ±9.85)
hd_floor  = [-50, -44];     // head floor Z rel A
hd_wall_top = -6;           // nothing of the head above A.z - 6 behind the plate (tube cone)
col_y   = [-152, -122];
col_hx  = 15;
hd_y0   = -138;             // head floor back end (overlaps column top by 16)
anc_y   = [-152, -142];     // anchor post (tube enters on the servo axis at Y -142)
bp_hole = function(i, j) [frame_base_x()[0] + 15 + 30 * i, frame_base_y()[0] + 15 + 30 * j];
foot_holes = [bp_hole(3, 3), bp_hole(5, 3), bp_hole(3, 4), bp_hole(5, 4)];  // X -180/-120, Y -165/-135
foot_x  = [-188, -112];  foot_y = [-173, col_y[1]];  foot_t = 6;
col_top = pz + hd_floor[0];
hd_bolts = [[-5, -134], [5, -134], [-5, -126], [5, -126]];   // [dX rel A, Y]

// ── Public API for assembly.scad ───────────────────────────────────────────
function pick_arm_pivot()       = [px, pz];          // servo axis (X, Z); axis along Y
function pick_arm_radius()      = R;
function pick_arm_theta(s)      = pa_theta(s);
function pick_arm_servo_pick()  = s_pick;
function pick_arm_servo_drop()  = s_drop;
function pick_arm_servo_park()  = s_park;
function pick_arm_lip_z(s)      = pz + R * sin(pa_theta(s)) - h_cup;   // free cup lip
function pick_arm_cup_x(s)      = px + R * cos(pa_theta(s));

echo(str("PICK ARM: R ", R, "  pivot A X ", px, " Z ", pz, "  th_pick ", th_p, "  th_drop ", th_d,
         "  sweep ", th_p - th_d, "  servo pick ", s_pick, " drop ", s_drop, " park ", s_park,
         "  lip pick ", lip_pick, " (card ", card_z, ") lip drop ", lip_drop,
         "  cup X pick ", px + R * cos(th_p), " drop ", px + R * cos(th_d)));
echo(str("PICK ARM: Y layers hand ", hp_y0, "..", hp_y1, "  B ", lb_y0, "..", lb_y1,
         "  C ", lc_y0, "..", lc_y1, "  crank ", cr_y0, "..", cr_y1, "  ground plate ", gp_y0, "..", gp_y1,
         "  servo bottom ", sv_y0, "  spline top ", spline_y));

echo(str("PICK ARM: pin lengths (1 mm proud at the free end) — B ground ", (lb_y1 + 1) - gp_y0,
         "  C ground ", (lc_y1 + 1) - gp_y0, "  B' ", hp_y1 - (lb_y0 - 1), "  C' ", hp_y1 - (lc_y0 - 1),
         "  A' tube ", hp_y1 - (cr_y0 - 1.5), "  sleeves ", [for (s = slv_list()) s[2]],
         "  tube spoke ", norm([R, (cr_y0 - 1.5) - anc_y[1]]),
         "  column top Z ", col_top, "  head floor Z ", pz + hd_floor[0]));
// machine-readable copy for cad/pick_arm_check.py
echo(str("PICK_ARM_JSON {\"R\":", R, ",\"px\":", px, ",\"pz\":", pz, ",\"th_p\":", th_p, ",\"th_d\":", th_d,
         ",\"th_mid\":", th_mid, ",\"h_cup\":", h_cup, ",\"gB\":[", gB[0], ",", gB[1], "],\"gC\":[", gC[0], ",", gC[1],
         "],\"card_z\":", card_z, ",\"card_t\":", card_t, ",\"pick_x\":", pick_x, ",\"drop_x\":", drop_x,
         ",\"tube_y0\":", cr_y0 - 1.5, ",\"tube_y1\":", anc_y[1], ",\"sl_stroke\":", sl_stroke,
         ",\"s_pick\":", s_pick, ",\"s_drop\":", s_drop, ",\"s_park\":", s_park, "}"));

// ── Sanity asserts (the full swept-volume check is cad/pick_arm_check.py) ──
assert(abs(px + R * cos(th_d) - drop_x) < 0.05, "drop X not hit");
assert(abs(px + R * cos(th_p) - pick_x) < 0.05, "pick X not hit");
assert(s_pick <= 180 && s_drop >= 0, "arc exceeds the servo range");
assert(hp_y1 <= -(card_w / 2 + card_dy_max + 2.5), "hand plate too close to the card edge");
for (d = [phiB, phiC, (gB - gC)[1] < 0 ? 360 + atan2((gB - gC)[1], (gB - gC)[0]) : atan2((gB - gC)[1], (gB - gC)[0])])
    assert(d > th_p + 20 && d < th_d + 360 - 20, str("pin-crossing direction ", d, " inside the arc"));
assert(norm(gB - gC) > R, "follower C link could reach pin B'");
assert(gp_y1 < cr_y0 - horn_t, "ground plate hits the horn");
assert(sv_y0 + sv_case_h <= gp_y1 + 0.01 && sv_y0 + sv_case_h > gp_y0, "servo case top not inside the plate cut-out");
assert(abs(gB[0]) - dowel_d / 2 - (sv_w / 2 + 0.25) > 5, "pin B too close to the servo cut-out");
for (h = foot_holes) assert(h[0] < px - col_hx - 4 || h[0] > px + col_hx + 4, "foot hole under the column");

// =========================================================================
// Geometry helpers
// =========================================================================
module yslab(y0, y1) translate([0, y1, 0]) rotate([90, 0, 0]) linear_extrude(y1 - y0) children();
// 2D in XZ: point [x, z] → yslab maps 2D x→X, 2D y→Z
module ycyl(r, y0, y1, fn = 48) translate([0, y1, 0]) rotate([90, 0, 0]) cylinder(r = r, h = y1 - y0, $fn = fn);
module at_xz(p) translate([p[0], 0, p[1]]) children();
module rounded_sq(x0, x1, y0, y1, r)
    hull() for (x = [x0 + r, x1 - r]) for (y = [y0 + r, y1 - r]) translate([x, y]) circle(r = r);
function hex_r(af) = af / sqrt(3);

// =========================================================================
// Purchased parts (reference solids, used by the assembly and the sweep)
// =========================================================================
module mg996r() color("RoyalBlue") {   // A-local: spline on the A axis, top face +Y
    translate([-sv_w / 2, sv_y0, -(sv_l - sv_shaft_off)]) cube([sv_w, sv_case_h, sv_l]);
    translate([-sv_w / 2, sv_y0 + sv_tab_z0, -(sv_l - sv_shaft_off) - (sv_tab_span - sv_l) / 2])
        cube([sv_w, sv_tab_t, sv_tab_span]);
    ycyl(sv_spline_d / 2 + 4, sv_y0 + sv_case_h, spline_y - 1.5);   // gear boss
    ycyl(sv_spline_d / 2, sv_y0, spline_y);
}
module horn() color("Silver") {
    ycyl(horn_d / 2, cr_y0 - horn_t, cr_y0);
    ycyl(horn_hub_d / 2, spline_y - 4, cr_y0 - horn_t + eps);
}
module bellows_pad() color("WhiteSmoke") {   // lip at z = 0 (hand-local lip frame)
    cylinder(d1 = pad_lip_d, d2 = pad_d, h = 4);
    translate([0, 0, 4]) cylinder(d = pad_d, h = 16);
    translate([0, 0, 20]) cylinder(d = 12, h = 4);
    translate([0, 0, 24]) cylinder(r = hex_r(pad_hex_af), h = pad_top - 24, $fn = 6);
}
module barb_fitting() color("Gold") {        // Festo CN-M5-PK-3 (M5 male, barb for 4 mm OD tube)
    translate([0, 0, pad_top + web_t]) cylinder(r = hex_r(8), h = 4, $fn = 6);
    translate([0, 0, pad_top + web_t + 4]) cylinder(d = 4.2, h = 8);
}

// =========================================================================
// FIXED SIDE
// =========================================================================
// Ground plate outline (A-local XZ)
// The plate also runs down to the head floor (Z −50) across the floor width,
// so in the print (front face down) the floor, side walls and web stand on the
// plate instead of overhanging its lower edge by up to 9.7 mm.
module gp_outline_2d()
    union() {
        hull() {
            translate([-16, -40]) square([32, 62]);
            translate(gB) circle(r = 8);
            translate(gC) circle(r = 8);
        }
        translate([-16, hd_floor[0]]) square([32, -40 - hd_floor[0] + 1]);   // ±16: no edge coincident with the floor's ±14.6
    }

module head() {   // A-local (translate by [px, 0, pz])
    difference() {
        union() {
            yslab(gp_y0, gp_y1) gp_outline_2d();
            // side walls (stay below A.z - 6: the tube spoke whirls above)
            for (s = [-1, 1])
                translate([s > 0 ? hd_wall_x[0] : -hd_wall_x[1], hd_y0, hd_floor[0]])
                    cube([hd_wall_x[1] - hd_wall_x[0], gp_y0 - hd_y0 + eps, hd_wall_top - hd_floor[0]]);
            // floor
            translate([-hd_wall_x[1], hd_y0, hd_floor[0]])
                cube([2 * hd_wall_x[1], gp_y0 - hd_y0 + eps, hd_floor[1] - hd_floor[0]]);
            // diagonal web plate↔floor under the servo (stiffens the 60 mm cantilever)
            translate([-hd_wall_x[1], gp_y0 - 22, hd_floor[0]])
                cube([2 * hd_wall_x[1], 22 + eps, 4]);
        }
        // servo case cut-out (case top sits flush in the plate)
        translate([-sv_w / 2 - 0.25, gp_y0 - 1, -(sv_l - sv_shaft_off) - 0.25])
            cube([sv_w + 0.5, gp_t + 2, sv_l + 0.5]);
        // tab inserts, blind from the back face
        for (h = sv_holes) at_xz(h) ycyl(ins_d / 2, gp_y0 - 0.1, gp_y0 + ins_l + 0.5, 24);
        // B and C dowels: press-fit through holes
        for (g = [gB, gC]) at_xz(g) ycyl(dowel_press / 2, gp_y0 - 1, gp_y1 + 1, 24);
        // floor → column bolts (M3 clearance)
        for (b = hd_bolts) translate([b[0], b[1], hd_floor[0] - 1]) cylinder(d = m3_clr, h = 10, $fn = 24);
        // servo cable slot in the floor
        translate([-4, gp_y0 - 34, hd_floor[0] - 1]) cube([8, 12, 10]);
    }
}

module tower() {   // MACHINE coords
    bt = frame_base_top();
    difference() {
        union() {
            translate([foot_x[0], foot_y[0], bt]) cube([foot_x[1] - foot_x[0], foot_y[1] - foot_y[0], foot_t]);
            translate([px - col_hx, col_y[0], bt]) cube([2 * col_hx, col_y[1] - col_y[0], col_top - bt]);
            // gussets: ±X faces at Y -150 and -124 (between the foot bolts), back face at X px
            for (s = [-1, 1]) for (gy = [-150, -124])
                translate([px + s * col_hx, gy, bt + foot_t - eps])
                    rotate([90, 0, 0]) linear_extrude(4, center = true)
                        polygon([[0, 0], [s * 16, 0], [0, 40]]);
            translate([px, col_y[0], bt + foot_t - eps]) rotate([90, 0, 90]) linear_extrude(4, center = true)
                polygon([[0, 0], [-(col_y[0] - foot_y[0]), 0], [0, 40]]);
            // tube anchor post on the servo axis
            translate([px - 6, anc_y[0], col_top - eps]) cube([12, anc_y[1] - anc_y[0], pz + 7 - col_top]);
        }
        for (h = foot_holes) translate([h[0], h[1], bt - 1]) cylinder(d = m3_clr, h = foot_t + 2, $fn = 24);
        for (b = hd_bolts) translate([px + b[0], b[1], col_top - ins_l - 0.5]) cylinder(d = ins_d, h = ins_l + 1, $fn = 24);
        // anchor: Ø4.6 bore on the A axis + strain-relief bell (Ø4.6 → Ø13) facing the arm
        translate([px, 0, pz]) {
            ycyl(2.3, anc_y[0] - 1, anc_y[1] + 1, 24);
            translate([0, anc_y[1] + eps, 0]) rotate([90, 0, 0]) cylinder(d1 = 13, d2 = 4.6, h = 5, $fn = 48);
        }
        // zip-tie channels (tube + servo cable down the back of the column):
        // 4 × 2.2 tunnels 2.5 mm behind the back face, open through BOTH ±X
        // side faces, so a tie threads in one side and out the other around
        // the 2.5 mm back strip. Z 55 / 80: above the gussets (they end at
        // Z 50), so the tunnel ends are not blocked.
        for (z = [55, 80]) translate([px - col_hx - 1, col_y[0] + 2.5, z]) cube([2 * col_hx + 2, 2.2, 4]);
        translate([px - 7, anc_y[0] + 2.5, pz - 9]) cube([14, 2.2, 4]);
    }
}

// =========================================================================
// MOVING PARTS (reference pose th = 0; pivots at their ground points)
// =========================================================================
module crank_2d()
    union() {
        circle(r = cr_hub_r);
        translate([R, 0]) circle(r = cr_end_r);
        translate([0, -cr_w / 2]) square([R, cr_w]);
    }

module crank() {   // A-local, pointing +X
    difference() {
        yslab(cr_y0, cr_y1) crank_2d();
        ycyl(3.75, cr_y0 - 1, cr_y1 + 1);                              // horn centre screw access
        for (a = [0, 90, 180, 270]) rotate([0, -a - 45, 0]) {
            hull() for (r = horn_slot) translate([r, 0, 0]) ycyl(m3_clr / 2, cr_y0 - 1, cr_y1 + 1, 16);
            hull() for (r = horn_slot) translate([r, 0, 0]) ycyl(3.3, cr_y1 - 3, cr_y1 + 1, 24);   // head recess
        }
        translate([R, 0, 0]) ycyl(ap_run / 2, cr_y0 - 1, cr_y1 + 1);
    }
}

module link_2d()
    union() {
        circle(r = lk_end_r);
        translate([R, 0]) circle(r = lk_end_r);
        translate([0, -lk_w / 2]) square([R, lk_w]);
    }
module link(y0) {   // pivot-local, pointing +X
    difference() {
        yslab(y0, y0 + lk_t) link_2d();
        for (x = [0, R]) translate([x, 0, 0]) ycyl(dowel_run / 2, y0 - 1, y0 + lk_t + 1, 24);
    }
}

// Hand plate + beams, hand-local (origin A')
module hand_plate_2d()
    union() {
        hull() {
            circle(r = hp_ap_r);
            translate(gB) circle(r = hp_pin_r);
            translate(gC) circle(r = hp_pin_r);
        }
        translate([-beam_x[1], beam_z[0] - 2]) square([2 * beam_x[1], -beam_z[0] + 2 + 4]);
    }
module hand() {
    difference() {
        union() {
            yslab(hp_y0, hp_y1) hand_plate_2d();
            for (s = [-1, 1])
                translate([s > 0 ? beam_x[0] : -beam_x[1], hp_y1 - eps, beam_z[0]])
                    cube([beam_x[1] - beam_x[0], beam_y1 - hp_y1 + eps, beam_z[1] - beam_z[0]]);
        }
        ycyl(ap_press / 2, hp_y0 - 1, hp_y1 + 1);                       // hollow A' pin, pressed
        for (g = [gB, gC]) at_xz(g) ycyl(dowel_press / 2, hp_y0 - 1, hp_y1 + 1, 24);
        // guide-screw inserts (from the beam top)
        for (s = [-1, 1]) translate([s * rod_dx, 0, beam_z[1] - ins_l - 0.5]) cylinder(d = ins_d, h = ins_l + 1, $fn = 24);
        for (s = [-1, 1]) translate([s * rod_dx, 0, beam_z[0] - 1]) cylinder(d = 2.6, h = 4, $fn = 16);
    }
}

// Cup carrier (sled), lip frame (z = 0 at the free cup lip)
module sled() {
    difference() {
        translate([-sl_hx, -sl_hy, sl_z0]) cube([2 * sl_hx, 2 * sl_hy, sl_z1 - sl_z0]);
        // pad hex pocket (from below) + web + recess for the barb fitting
        translate([0, 0, sl_z0 - 1]) cylinder(r = hex_r(pad_hex_af + 0.15), h = pad_top - sl_z0 + 1, $fn = 6);
        translate([0, 0, pad_top - 1]) cylinder(d = 5.3, h = web_t + 2);
        translate([0, 0, pad_top + web_t]) cylinder(d = 11, h = sl_z1);
        // guide bores
        for (s = [-1, 1]) translate([s * rod_dx, 0, sl_z0 - 1]) cylinder(d = m3_clr, h = 40, $fn = 24);
    }
}

// Sleeves (spacers on the pins)
function slv_list() = [   // [od, bore, length, label]
    [slv_d, slv_bore, (lb_y0 - slv_gap) - gp_y1, "B ground"],
    [slv_d, slv_bore, (lc_y0 - slv_gap) - gp_y1, "C ground"],
    [slv_d, slv_bore, hp_y0 - (lc_y1 + slv_gap), "C' hand"],
    [slv_ap_d, slv_ap_bore, hp_y0 - (cr_y1 + slv_gap), "A' hand"]];
module sleeve(s) difference() { cylinder(d = s[0], h = s[2]); translate([0, 0, -1]) cylinder(d = s[1], h = s[2] + 2); }

// Pins + sleeves as they sit in the machine (for assembly / sweep)
module ground_pins() color("Silver") {   // A-local
    at_xz(gB) { ycyl(slv_d / 2, gp_y1 - eps, lb_y0 - slv_gap); ycyl(dowel_d / 2, gp_y0, lb_y1 + 1); }
    at_xz(gC) { ycyl(slv_d / 2, gp_y1 - eps, lc_y0 - slv_gap); ycyl(dowel_d / 2, gp_y0, lc_y1 + 1); }
}
module hand_pins() color("Silver") {     // hand-local
    ycyl(slv_ap_d / 2, cr_y1 + slv_gap, hp_y0 + eps);
    ycyl(ap_od / 2, cr_y0 - 1.5, hp_y1);
    at_xz(gC) { ycyl(slv_d / 2, lc_y1 + slv_gap, hp_y0 + eps); ycyl(dowel_d / 2, lc_y0 - 1, hp_y1); }
    at_xz(gB) ycyl(dowel_d / 2, lb_y0 - 1, hp_y1);
}
// Guide screws (M3 × 40, heads down) — fixed to the hand
module guide_screw_heads() color("DimGray")
    for (s = [-1, 1]) translate([s * rod_dx, 0, sl_z0 - h_cup - gs_head_h]) cylinder(d = gs_head_d, h = gs_head_h);
module guide_screw_shanks() color("DimGray")
    for (s = [-1, 1]) translate([s * rod_dx, 0, sl_z0 - h_cup]) cylinder(d = 3, h = 40);
module guide_screws() { guide_screw_heads(); guide_screw_shanks(); }
// Sled group in hand-local coords, raised by `comp` (slider compression)
module sled_group(comp = 0)
    translate([0, 0, comp - h_cup]) {
        color("Orange") sled();
        bellows_pad();
        barb_fitting();
    }
module held_card(comp = 0)
    color("Khaki", 0.8) translate([-card_l / 2, -card_w / 2, comp - h_cup - card_t]) cube([card_l, card_w, card_t]);

// =========================================================================
// Assembly in machine coordinates
// =========================================================================
// slider compression from the stack / belt contact (only if the servo drives past)
function _comp(th, card) =
    let(lip = pz + R * sin(th) - h_cup, cx = px + R * cos(th))
    abs(cx - pick_x) < 5 ? max(0, card_z - lip)
  : (card && abs(cx - drop_x) < 5) ? max(0, card_z + card_t - lip) : 0;

module pick_arm_fixed() {
    translate([px, 0, pz]) {
        color("SteelBlue") head();
        ground_pins();
        mg996r();
    }
    color("SteelBlue") tower();
}

module pick_arm_moving_theta(th, card = false) {
    c = _comp(th, card);
    translate([px, 0, pz]) {
        rotate([0, -th, 0]) { color("Tomato") crank(); horn(); }
        at_xz(gB) rotate([0, -th, 0]) color("Coral") link(lb_y0);
        at_xz(gC) rotate([0, -th, 0]) color("Coral") link(lc_y0);
        translate([R * cos(th), 0, R * sin(th)]) {
            color("Tomato") hand();
            hand_pins();
            guide_screws();
            sled_group(min(c, sl_stroke));
            if (card) held_card(min(c, sl_stroke));
        }
    }
}

// THE integration module: servo angle in degrees (same numbers as hardware/servos.py)
module asm_pick_arm(angle = 90, card = false) {
    pick_arm_fixed();
    pick_arm_moving_theta(pa_theta(angle), card);
}
module asm_pick_arm_theta(th, card = false) { pick_arm_fixed(); pick_arm_moving_theta(th, card); }

// Legacy name kept so an old `use <suction_arm.scad>` still renders something;
// it is the parked arm IN MACHINE COORDS (do not translate it).
module suction_arm() asm_pick_arm(s_park);

// =========================================================================
// Export selector
// =========================================================================
if (part == "assembly") asm_pick_arm(servo_angle, show_card);

// print orientations
if (part == "head")  translate([0, 0, gp_y1]) rotate([-90, 0, 0]) head();               // plate front face down
if (part == "tower") translate([-px, -(col_y[0] + col_y[1]) / 2, -frame_base_top()]) tower();
if (part == "crank") translate([0, 0, cr_y1]) rotate([-90, 0, 0]) crank();
if (part == "link")  for (i = [0, 1]) translate([0, i * 20, lb_y1]) rotate([-90, 0, 0]) link(lb_y0);   // print B and C together
if (part == "hand")  translate([0, 0, -hp_y0]) rotate([90, 0, 0]) hand();               // back face down, beams up
if (part == "sled")  translate([0, 0, -sl_z0]) sled();
if (part == "sleeves") for (i = [0 : 3]) translate([i * 18, 0, 0]) sleeve(slv_list()[i]);

// reference poses for cad/pick_arm_check.py (machine coords, th = 0, comp = 0)
if (part == "ref_fixed")  pick_arm_fixed();
if (part == "ref_head")   translate([px, 0, pz]) head();
if (part == "ref_tower")  tower();
if (part == "ref_servo")  translate([px, 0, pz]) mg996r();
if (part == "ref_gpin_b") translate([px, 0, pz]) at_xz(gB) { ycyl(slv_d / 2, gp_y1 - eps, lb_y0 - slv_gap); ycyl(dowel_d / 2, gp_y0, lb_y1 + 1); }
if (part == "ref_gpin_c") translate([px, 0, pz]) at_xz(gC) { ycyl(slv_d / 2, gp_y1 - eps, lc_y0 - slv_gap); ycyl(dowel_d / 2, gp_y0, lc_y1 + 1); }
if (part == "ref_crank")  translate([px, 0, pz]) { crank(); horn(); }
if (part == "ref_link_b") translate([px + gB[0], 0, pz + gB[1]]) link(lb_y0);
if (part == "ref_link_c") translate([px + gC[0], 0, pz + gC[1]]) link(lc_y0);
if (part == "ref_hand")   translate([px + R, 0, pz]) hand();
if (part == "ref_gs_head")  translate([px + R, 0, pz]) guide_screw_heads();    // fixed to the hand
if (part == "ref_gs_shank") translate([px + R, 0, pz]) guide_screw_shanks();
if (part == "ref_hpin_a") translate([px + R, 0, pz]) { ycyl(slv_ap_d / 2, cr_y1 + slv_gap, hp_y0 + eps); ycyl(ap_od / 2, cr_y0 - 1.5, hp_y1); }
if (part == "ref_hpin_b") translate([px + R, 0, pz]) at_xz(gB) ycyl(dowel_d / 2, lb_y0 - 1, hp_y1);
if (part == "ref_hpin_c") translate([px + R, 0, pz]) at_xz(gC) { ycyl(slv_d / 2, lc_y1 + slv_gap, hp_y0 + eps); ycyl(dowel_d / 2, lc_y0 - 1, hp_y1); }
if (part == "ref_sled")   translate([px + R, 0, pz - h_cup]) sled();            // printed carrier only
if (part == "ref_pad")    translate([px + R, 0, pz - h_cup]) { bellows_pad(); barb_fitting(); }
if (part == "ref_card")   translate([px + R, 0, pz]) held_card(0);

// =============================================
// PRINT NOTES (PETG, 0.2 mm, 4 walls, 40 % gyroid unless noted)
//   head    plate front face on the bed; walls + floor grow up 62 mm. Pin and
//           insert holes print vertical (accurate pattern). No supports.
//   tower   upright on the foot (≈154 mm tall). Anchor bore Ø4.6 prints
//           horizontal (bridge 4.6 mm). No supports. 30 % infill is plenty.
//   crank   flat (6 mm), 100 % infill around the hub is worth it (5 walls).
//   link    ×2 in ONE print (B and C must be the same length). 5 walls.
//   hand    hand-plate back face on the bed; the two beams stand 43 mm up.
//           The guide-screw insert holes are then horizontal — fine for M3 inserts.
//   sled    upright, hex pocket on the bed side (8 mm bridge over it).
//   sleeves upright; or use 10×4.3 / 14×8.3 nylon spacers cut to length.
// Check XY scaling with a 50 mm test before printing head/hand: only the
// SAME pattern on both plates matters, not the absolute 45 mm.
//
// HARDWARE
//   1× MG996R + 25T aluminium disc horn (Ø25, 4× M3); 4× M3×6 horn screws;
//      4× M3×8 SHCS + 4× M3 heat-set inserts (tabs → plate back face): 2.5 tab
//      + 5.5 into the 5.7 insert, tip 0.7 short of the 6.2 hole bottom (an M3×10
//      would bottom out: 7.5 > 6.2, and the 8 mm plate leaves no room to deepen)
//   1× 8×6 mm brass/aluminium tube, 30.5 mm (hollow A' pin) + 8 mm flat push-on washer
//   4 mm silver-steel rod (or h6 dowels) cut to the echoed lengths, ends
//      chamfered: B ground 38, C ground 29.5, B' 13, C' 21.5 mm. Each sticks
//      1 mm out of its link: + 4× 4 mm FLAT push-on retaining washers (≤0.5 mm;
//      domed caps are too tall for the 1 mm gaps)
//   2× M3×40 SHCS (guide screws, heads down) + 2 M3 heat-set inserts
//   2× compression spring ~0.3 wire × 5 OD × 18 free (≤0.1 N/mm) on the guide screws
//   1× SMC ZPT16BS-B5 bellows pad (Ø16 silicone, M5 female)
//   1× Festo CN-M5-PK-3 barb (M5 male, 4 mm OD tube) — or any M5 × 4 mm barb
//   ~400 mm 4 mm OD vacuum tube (soft PU PUN-H-4×0.75 or silicone 2×4)
//   Tower: 4× M3×20 through foot (6) + tile (4) + 6 mm backing board = 16 mm
//      clamp into the board's tee-nuts (fallback washer + nut: +0.5 washer +
//      2.4 nut + ≥1 thread → still M3×20);
//      head→tower 4× M3×12 into 4 heat-set inserts in the column top.
// ASSEMBLY ORDER
//   1. Inserts. Press B/C dowels into the plate (from the front, flush at the back).
//   2. Servo into the head from behind, tabs on the plate's back face, 4 screws.
//   3. Power the servo at ARM_PARK (90°), fit the disc horn so its screw slots
//      roughly align, bolt the crank on pointing straight UP (±7° spline step;
//      trim with the calibration offsets).
//   4. Sleeves on B/C, C link (on C), B link (on B). Hand: press A' tube + B'/C'
//      dowels, A' sleeve + C' sleeve on. Slide the hand on (A' into the crank,
//      B' into link B, C' into link C) — it only goes on when all three links
//      are parallel. Starlocks on every free pin end.
//   5. Pad hex into the sled, barb through the web into the pad (gasket).
//      Springs + sled onto the M3×40 screws, screw into the beam inserts.
//   6. Tube: barb → loop → through the A' tube → spoke → anchor bell → down
//      the column (zip ties). Leave ~10 mm slack in the hand loop.
//   7. Head onto the tower (4× M3×12), tower onto the baseplate.
// =============================================
