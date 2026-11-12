// =============================================
// Riftbound Card Sorter — cradle-shuttle sorter: shared geometry + kinematics
// =============================================
// Functions only (no geometry). Used by shuttle.scad, lower_ramp.scad,
// reject_bin.scad and riser.scad, and mirrored 1:1 in cad/shuttle_check.py.
// Machine coordinates (see machine_frame.scad): X = card travel, Y = across
// (+Y back), Z = up. Shuttle parts are modelled in the LEVEL (receive) pose
// with y measured from the carriage centre; asm_sorter_end() places them.
//
// HOW IT WORKS (side view, X → right):
//
//   belt end ─┐ card (Z 90.9)                       tray back face X 178
//   roller 60 ●══════════▶  ┌─ bed (Z 90.2) ──────┐╱ kick 18°, lip
//                           │  cradle (≤35 g)      │   upper slot floor Z 74.5
//                  rear R   └── load cell ─ F pin ─┘
//                  skid ●        tilt frame (TF)       ● = pivots
//                  R-bar (fixed, along Y)              lower ramp → lower slot
//
//  - The cradle sits on the free end of a TAL221 beam whose other end is
//    screwed to the TILT FRAME (TF). The TF hangs in the carriage cheeks by
//    two Ø4 pins at F (front). ch1 (MG996R) turns an 8 mm shaft along Y (axis D;
//    called "D-shaft" throughout, but it is an 8 mm REX = round ∩ 7 mm hex shaft);
//    a crank on that shaft + a short link lift/lower the TF.
//  - RECEIVE (level, home Y=0 only): bed 0.7 below the belt; the belt pushes
//    the card on until its tail leaves the roller.
//  - HOLD (TF rotated 10° front-down about F): card tail rises above the
//    rails, guide clips and guide tops, so the shuttle may move in Y.
//    The card rests at a 10° slope against the 18° kick; it is weighed here,
//    at rest, on the cradle alone.
//  - UPPER (further about F to 35°): the lip stays high (F is right under the
//    bend), the kick turns downhill (−17°) and the card slides off the lip
//    into the upper slot (lip Z ≈ 86.7, slot floor 74.5).
//  - The bed + kick carry 0.1 mm PTFE (skived, self-adhesive) tape: card μ
//    ≈ 0.15 instead of ≈ 0.3–0.45 on PLA. shuttle_check.py slide shows this
//    is what makes the upper/lower transfer reliable.
//  - LOWER (from HOLD, ch1 the other way): at every column/reject position
//    the TF's rear skids land on the fixed R-bar, so the TF now rotates
//    about the skid, front down, to 58°: the kick becomes a −40° chute
//    straight onto the fixed lower ramp, which curves the card into the lower
//    slot. At HOME the R-bar has notches under the skids, so the same ch1
//    motion brings the cradle back to LEVEL instead (skids land on a ledge).
// =============================================

use <machine_frame.scad>

// ---------- frame ----------
function sg_base_top()  = frame_base_top();            // 4
function sg_card_z()    = frame_card_z();              // 90.9
function sg_deck_z()    = frame_deck_z();              // 64
function sg_belt_x1()   = frame_belt_x1();             // 85

// ---------- tray (moved) ----------
function sg_tray_x0()   = 178;      // tray back (open) face; tray spans X 178..276
function sg_tray_depth()= 98;
function sg_col_y()     = [-102, -35, 35, 102];
function sg_reject_y()  = 176;
function sg_home_y()    = 0;
// carriage-centre Y for a target ("home", "reject", or 0..3)
function sg_target_y(col) = col == "home" ? 0 : col == "reject" ? sg_reject_y() : sg_col_y()[col];
// tray wall/divider Y bands (machine), used for ramp dividers and upper fins
function sg_tray_walls() = [[-137, -134.5], [-69.5, -67.5], [-2.5, 2.5], [67.5, 69.5], [134.5, 137]];

// ---------- cradle (level frame, machine X/Z) ----------
function sg_bed_z()     = 90.2;     // bed top, 0.7 below the card face
function sg_bed_t()     = 2.0;
function sg_bed_x0()    = 92;       // rear edge (rail end 85, guide-rail tenon 90)
function sg_bend_x()    = 157;      // bed → kick bend (directly over pivot F)
function sg_kick_a()    = 18;       // kick angle up from the bed
function sg_kick_l()    = 12;
function sg_lip()       = [sg_bend_x() + sg_kick_l() * cos(sg_kick_a()),
                           sg_bed_z()  + sg_kick_l() * sin(sg_kick_a())];
function sg_guide_hw()  = 32.25;    // card guide inner face |y| (64.5 channel, card 63)
function sg_mouth_hw()  = 33.7;     // flared mouth at the rear edge (67.4; belt guides 66.4)
function sg_guide_t()   = 1.5;
function sg_guide_top() = sg_bed_z() + 3.8;
function sg_cradle_hw() = sg_mouth_hw() + sg_guide_t();   // 35.2

// ---------- load cell TAL221 (47 × 12 × 6, holes ±20 along X, ±3 across) ----------
function sg_cell_xc()   = 129.5;    // fixed (tapped, cable) end at the FRONT
function sg_cell_ztop() = sg_bed_z() - sg_bed_t() - 6.8;   // 81.4 (cradle boss 6.8)
function sg_cell_l()    = 47;
function sg_cell_w()    = 12;
function sg_cell_h()    = 6;

// ---------- tilt frame pivots ----------
function sg_F()         = [157, 90.2];   // front pin (Ø4), |y| 36..44
function sg_S0()        = [106, 65.8];   // rear skid nub CENTRE (Ø4 nub, bottom Z 63.8), level pose
function sg_skid_r()    = 2;
function sg_th_hold()   = 10;            // hold: front-down about F
function sg_th_upper()  = 35;            // total bed angle, upper dump (about F) → kick −17°
function sg_dl_lower()  = 48;            // extra rotation about the skid (bed 58°)
function sg_tf_y()      = [36, 39];      // TF side plates |y|
function sg_cheek_y()   = [40.5, 45.5];  // carriage cheeks |y|

// ---------- ch1 tilt drive (crank on D-shaft + link) ----------
function sg_D()         = [105, 44];     // D-shaft axis (X, Z)
function sg_crank_r()   = 32;
function sg_link_l()    = 25;
function sg_A()         = [144, 70];     // link pin on the TF (level frame)
function sg_crank_y()   = [13.5, 18];    // crank slab (y)
function sg_link_y()    = [8, 12.5];     // link slab (y); TF slot 7.5..13 leaves 1.4 to the cell-screw counterbore
// ch1 servo + coupler at the −Y end (machine Y). The "D-shaft" is an 8 mm REX shaft
// (Ø8 round ∩ 7 mm hex: goBILDA 2106-4008-4320, 432 mm, cut to 417), coupled to
// the MG996R by ONE bought part: goBILDA 4001-0025-4008 clamping servo-to-shaft
// coupler (25T spline → 8 mm REX bore, Ø13.8 × 17, clamp boss to r 11.9, M4
// clamp screw; dimensions from goBILDA's STEP file). Stack along +Y from the
// servo case face Yf: spline 0..4, coupler Yf+0.8..Yf+17.8, shaft end at
// Yf+9.8 (8 mm in the REX bore), 7.2 mm air to the end post's outer face (−160).
function sg_c1_face_y() = -185;          // MG996R case face (spline side), body toward −Y
function sg_c1_cpl()    = [0.8, 17.0, 6.9, 11.87, 9.0];  // coupler: start (from face), length, body r, boss r, shaft end (from coupler start)
function sg_c1_cpl_y()  = [sg_c1_face_y() + sg_c1_cpl()[0], sg_c1_face_y() + sg_c1_cpl()[0] + sg_c1_cpl()[1]];
function sg_dshaft_y()  = [sg_c1_cpl_y()[0] + sg_c1_cpl()[4], sg_c1_cpl_y()[0] + sg_c1_cpl()[4] + 417];   // −175.2..241.8

// ---------- carriage / rods ----------
function sg_rod()       = [106, 24];     // smooth rod (LM8UU ×2)
function sg_rod_y()     = [-160, 232];   // 400 mm rod, ends in the end posts
function sg_carr_hw()   = 45.5;          // carriage half-width (y) = cheek outer faces; the sled is ±40.5

// ---------- fixed R-bar (lower-mode fulcrum) ----------
function sg_rbar_x()    = [95, 104];    // 9 wide: 1.4 walls round the splice counterbores
function sg_rbar_z0()   = 56;
function sg_rbar_y()    = [-150, 232];
function sg_rbar_notch_y() = [29, 45];   // |Y| band notched at home (skids pass)

// ---------- ch2 shuttle drive (in-line slider-crank, XY plane, under the deck) ----------
// Pivot Y −124: the crank tip boss (r 6) at column 0 (ψ 180°) reaches Y −269,
// inside the baseplate (±270). The servo's front ear then sits 6 mm inside the
// riser footprint; riser_b has a pocket for it (its ceiling is the ear shelf).
function sg_c2_pivot()  = [80, -124];    // servo output axis (X, Y), servo hangs above
function sg_c2_r()      = 139;
function sg_c2_l()      = 162;
function sg_c2_pin_dy() = 1;             // drive pin Y relative to carriage centre
function sg_c2_tip_r()  = 6;             // crank tip boss radius
// Z stack, bottom to top. NOTHING hangs below the link: both link pivots are
// 4 mm-shoulder screws dropped in from ABOVE, their M3 × 4 thread in an M3 × 4
// heat-set insert pressed into the link top; the link hangs on the screw heads.
//   tiles Z 4 | 5 air (tile-seam lips) | link 9..14 | 1 | crank 15..19 and
//   carriage drive-pin arm 15..20 | tip-screw head 19..23, drive-pin head 20..24
//   | 2 | riser tunnel roof from Z 26.
//   The horn screws (4 × M2 on Ø14 + the centre M3) are countersunk flush in the
//   crank bottom, so the link may pass 1 mm under the crank hub at column 0.
// MG996R hanging upside down above the crank, with the 25T round horn between:
//   crank top 19 | horn disc Ø25 × 1.4 | horn hub up to the spline | case face
//   Z 26.3 (horn stack 1.4 + 5.9) | case to Z 62.9; ears (2.5 thick) 8.1..10.6
//   above the case face → Z 34.4..36.9; ear shelves above them from Z 37.0.
// The crank angles (hardware/shuttle.py SHUTTLE_ANGLES) depend only on the XY
// values above, so raising the stack does not change them.
function sg_c2_link_z() = [9, 14];       // link slab Z
function sg_c2_z()      = [15, 19];      // crank slab Z
function sg_c2_arm_z()  = [15, 20];      // carriage drive-pin arm Z
function sg_c2_sh()     = [4, 8, 4];     // shoulder screw envelope: shoulder Ø, head Ø, head height
function sg_c2_sh_l()   = [5, 6];        // shoulder length: crank tip (crank 4 + 1), drive pin (arm 5 + 1)
function sg_c2_roof_z() = 26;            // riser tunnel roof underside
function sg_c2_face_z() = sg_c2_z()[1] + 1.4 + 5.9;          // 26.3
function sg_c2_shelf_z()= sg_c2_face_z() + 10.7;             // 37.0
function sg_c2_ear_y()  = [sg_c2_pivot()[1] + 14.2, sg_c2_pivot()[1] - 34.5];  // ear hole Ys (front, rear)
function sg_c2_body_y() = [sg_c2_pivot()[1] + 10.2, sg_c2_pivot()[1] - 30.5];  // case Y extent
function sg_c2_ear_end_y() = [sg_c2_pivot()[1] + 17.2, sg_c2_pivot()[1] - 37.5];

// ---------- 2D kinematics (XZ), rotation = front-down by a (= rotate([0,a,0])) ----------
function sg_rot(p, c, a) = [c[0] + (p[0]-c[0])*cos(a) + (p[1]-c[1])*sin(a),
                            c[1] - (p[0]-c[0])*sin(a) + (p[1]-c[1])*cos(a)];
function sg_SJ() = sg_rot(sg_S0(), sg_F(), sg_th_hold());   // skid in HOLD = R-bar top
// pose of a level-frame point
function sg_pose(p, st) =
    st == "level" ? p :
    st == "hold"  ? sg_rot(p, sg_F(), sg_th_hold()) :
    st == "upper" ? sg_rot(p, sg_F(), sg_th_upper()) :
    st == "lower" ? sg_rot(sg_rot(p, sg_F(), sg_th_hold()), sg_SJ(), sg_dl_lower()) : p;
function sg_bed_angle(st) =
    st == "level" ? 0 : st == "hold" ? sg_th_hold() : st == "upper" ? sg_th_upper()
                  : sg_th_hold() + sg_dl_lower();
// crank tip for a TF pose (circle-circle intersection, branch −1)
function sg_crank_phi(st) =
    let(D = sg_D(), A = sg_pose(sg_A(), st), v = A - D, d = norm(v),
        c = sg_crank_r(), l = sg_link_l(),
        base = atan2(v[1], v[0]), g = acos((c*c + d*d - l*l) / (2*c*d)))
    base - g;
function sg_crank_tip(st) = sg_D() + sg_crank_r() * [cos(sg_crank_phi(st)), sin(sg_crank_phi(st))];
// ch2: crank angle psi (0 = pointing +Y, 90 = pointing −X) for a carriage Y
function sg_c2_psi(yc) =
    let(y = yc + sg_c2_pin_dy() - sg_c2_pivot()[1], r = sg_c2_r(), l = sg_c2_l(),
        cs = (y*y + r*r - l*l) / (2*r*y))
    acos(max(-1, min(1, cs)));
function sg_c2_tip(yc) = let(p = sg_c2_psi(yc))
    [sg_c2_pivot()[0] - sg_c2_r() * sin(p), sg_c2_pivot()[1] + sg_c2_r() * cos(p)];

// ---------- lower ramp profile (machine XZ), derived from the lower-pose lip ----------
function sg_lip_lower()   = sg_pose(sg_lip(), "lower");
function sg_kick_lower_a()= sg_bed_angle("lower") - sg_kick_a();    // downhill angle of kick
function sg_ramp_x0()     = sg_lip_lower()[0] + 1.0;
function sg_ramp_z0()     = sg_lip_lower()[1] - 1.5 - (1.0 * tan(sg_kick_lower_a()));
function sg_ramp_exit_a() = 8;      // exit angle below horizontal
function sg_ramp_R()      = 20;     // run-out radius
function sg_ramp_profile() =
    let(a0 = sg_kick_lower_a(), a1 = sg_ramp_exit_a(), R = sg_ramp_R(),
        hx = R * (sin(a0) - sin(a1)), hz = R * (cos(a1) - cos(a0)),
        sx = sg_tray_x0() - sg_ramp_x0() - hx,             // straight part, horizontal
        p1 = [sg_ramp_x0() + sx, sg_ramp_z0() - sx * tan(a0)],
        cc = [p1[0] + R * sin(a0), p1[1] + R * cos(a0)])  // arc centre (above)
    concat([[sg_ramp_x0(), sg_ramp_z0()]],
           [for (i = [0 : 12]) let(a = a0 - (a0 - a1) * i / 12) [cc[0] - R * sin(a), cc[1] - R * cos(a)]]);
function sg_ramp_exit_z() = let(p = sg_ramp_profile()) p[len(p) - 1][1];
