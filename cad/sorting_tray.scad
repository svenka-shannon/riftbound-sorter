// ============================================================
// Riftbound Card Sorter — 2-Floor Sorting Tray
// ============================================================
// Replaces single-row 9-slot tray.
// TWO stacked floors of 4 slots each = 8 sort slots.
// Sort gate routes cards to floor + column position.
//
// COMPACT FOOTPRINT:
//   Single-row tray: 9 × 65mm = 585mm wide ✗ (too wide)
//   2-floor tray:    2 sections × 137mm = 274mm wide ✓  (saves 311mm)
//
// CARD FLOW:
//   Gate deflects card to Z column (0-3) AND floor (lower/upper).
//   Lower floor: slots 0–3 (Champion, Spell, Follower, Equipment)
//   Upper floor: slots 4–7 (Legendary, Epic/Rare, Common, Basic)
//   Reject: a separate small tray at end of lower floor.
//   Cards lie flat and enter through the OPEN BACK (Y = tray_depth),
//   which faces the belt exit — nothing may obstruct the back.
//
// PRINT (per tray): 6 pieces, every one fits the P1S 256mm bed
//   Section A  lower floor, slots 0–1  137 × 98 × 65   (pin on right face)
//   Section B  lower floor, slots 2–3  137 × 98 × 65   (pin hole on left face)
//   Section C  upper floor, slots 4–5  137 × 98 × 65   (pin on right face)
//   Section D  upper floor, slots 6–7  137 × 98 × 65   (pin hole on left face)
//   Shelf half ×2 (identical)          137 × 98 × 3
//   Lower sections (A, B) carry the stacking bosses + baseplate screw
//   holes; upper sections (C, D) carry countersunk stacking holes.
//   Material: PLA, 0.2mm, 40% infill
//   Orientation: flat on bed (open top facing up); shelf halves flat.
//
// FASTENING (all M3):
//   Lower section → baseplate: 4× M3 countersunk per section, from inside
//     the slots (fit BEFORE the shelf). Holes land coaxially on the
//     baseplate_tile 30mm mounting grid at the assembly.scad position.
//   Upper section → shelf → lower section: 4× M3 × 12 countersunk per
//     section, from inside the upper slots' front corners, through the
//     upper floor (2.5) + shelf half (3) into a Ø2.5 pilot in the lower
//     section's front-corner boss (6.5mm thread engagement).
//   Shelf halves need no joint of their own: each half is clamped to its
//     own lower/upper section pair by those 4 screws, and the section pairs
//     are aligned to each other by the side alignment pin.
// ============================================================

// ── Card dimensions (Riftbound standard) ───────────────────
card_w   = 63;
card_h   = 88;
card_clr = 2;      // 1mm clearance per side

// ── Slot geometry ───────────────────────────────────────────
slot_w      = card_w + card_clr;     // 65mm per slot
n_slots     = 4;                     // 4 slots per floor
n_floors    = 2;                     // 2 stacked floors

// ── Tray body ───────────────────────────────────────────────
tray_wall   = 2.5;
divider_t   = 2.0;
floor_h     = 65;                    // height per floor (card stack height)
tray_depth  = card_h + 10;          // 98mm

// ── Section split (2 slots per printed section) ─────────────
// Width of 2-slot section: 2×65 + 1 divider + 2 walls = 137mm ✓ P1S
n_slots_per_section = 2;
section_w = slot_w * n_slots_per_section
          + divider_t * (n_slots_per_section - 1)
          + tray_wall * 2;
// section_w = 2×65 + 1×2 + 2×2.5 = 137mm

// ── Full tray width (both sections joined) ──────────────────
// Each printed section keeps BOTH of its 2.5mm side walls, and the
// sections butt face-to-face, so the join is a 5mm double wall (not a
// shared single wall). Assembled width is therefore simply
//   n_sections × section_w = 2 × 137 = 274mm
n_sections  = n_slots / n_slots_per_section;   // 2 sections per floor
full_tray_w = n_sections * section_w;          // 274mm
// Exposed for other files (`use <sorting_tray.scad>` does not import variables)
function sorting_tray_width() = full_tray_w;
function sorting_tray_depth() = tray_depth;

// ── Floor gap / shelf between floors ────────────────────────
shelf_h = 3;           // thin shelf separating floors
floor_gap = shelf_h;   // visual gap = shelf thickness

// ── Label windows on front face ─────────────────────────────
label_h      = 18;
label_margin = 3;
label_inset  = 0.5;

// ── Alignment pin — 3mm, same as conveyor_rail.scad ─────────
// Pin is rooted in the section's own right wall and sticks out of its right
// face into a through-hole in the next section's left wall. Both lengths are
// kept < tray_wall (2.5mm) so the pin never pokes into a card slot.
pin_dia     = 3.2;     // hole
pin_dia_pin = 3.0;     // pin
pin_h_protr = 2.0;     // protrusion past the right face (into neighbour's 2.5mm wall)
pin_embed   = 2.0;     // length rooted inside own right wall (overlaps for union)
pin_z       = floor_h / 2;

// ── M3 hardware ─────────────────────────────────────────────
m3_dia      = 3.4;     // clearance
m3_pilot    = 2.5;     // self-tapping pilot in PLA
m3_pilot_h  = 12;      // pilot depth from boss top
csk_d       = 6.0;     // ISO 10642 M3 countersunk head Ø

// ── Stacking bosses (lower floor only) ──────────────────────
// Solid blocks fused into the FRONT corners of every lower-floor slot
// (the back is the card entry, so it must stay clear). A card lying flat
// stops against the bosses: 95.5 − 6 = 89.5mm free for an 88mm card.
boss_w      = 7.0;     // along X (into the slot from the side wall/divider)
boss_d      = 6.0;     // along Y (back from the front wall)
boss_cx     = 3.5;     // screw axis, X offset from the slot side face
boss_cy     = 3.1;     // screw axis, Y offset from the front-wall inner face
                       // (keeps the upper floor's Ø6 countersink 0.1mm off the wall)

// ── Baseplate screw holes (lower floor only), section-local [x, y] ──
// Tray back (open) face at world X 178 (cradle-shuttle sorter, shuttle_geom.scad
// sg_tray_x0): assembly places it at world X = 276 − y, Y = −137 + x_global.
// baseplate_tile grid: world X ∈ {200, 230, 260}, world Y ≡ 15 (mod 30).
//   → local y ∈ {76, 46, 16};  global x ∈ {2, 32, 62, … 272}
// Chosen holes sit in the slot floors, clear of walls/dividers/bosses:
base_holes_A = [[32, 16], [32, 76], [92, 16], [92, 76]];   // global x 32, 92
base_holes_B = [[45, 16], [45, 76], [105, 16], [105, 76]]; // global x 182, 242

// ── Lead-in chamfers cut into the top inner edges ───────────
chamfer_wall = 1.5;    // outer walls (2.5mm) → 1.0mm flat land remains
chamfer_div  = 0.75;   // divider (2.0mm), both faces → 0.5mm flat land remains

// ── Derived per-section positions ───────────────────────────
function slot_x(i) = tray_wall + i * (slot_w + divider_t);   // slot i inner left face
// Screw axes of the 2 front-corner bosses of each slot (section-local)
function stack_points() = [
    for (i = [0 : n_slots_per_section - 1])
        for (cx = [slot_x(i) + boss_cx, slot_x(i) + slot_w - boss_cx])
            [cx, tray_wall + boss_cy]
];

// 45° wedge cutter along an edge running in Y at (x, z=floor_h)
module chamfer_cut_y(x, c, y0, y1)
    translate([x, (y0 + y1) / 2, floor_h])
        rotate([0, 45, 0])
            cube([c * sqrt(2), y1 - y0, c * sqrt(2)], center = true);

// 45° wedge cutter along an edge running in X at (y, z=floor_h)
module chamfer_cut_x(y, c, x0, x1)
    translate([(x0 + x1) / 2, y, floor_h])
        rotate([45, 0, 0])
            cube([x1 - x0, c * sqrt(2), c * sqrt(2)], center = true);

// Countersunk M3 through a floor of thickness t (head flush at z = t)
module csk_hole(t) {
    translate([0, 0, -0.1]) cylinder(d = m3_dia, h = t + 0.2, $fn = 24);
    cone_h = (csk_d - m3_dia) / 2;                       // 90° head
    translate([0, 0, t - cone_h])
        cylinder(d1 = m3_dia, d2 = csk_d + 0.02, h = cone_h + 0.01, $fn = 32);
}

// ============================================================
// MODULE: tray_floor_section
//   One floor, one 2-slot section (printable piece).
//   start_slot 0/2 = lower floor (A/B), 4/6 = upper floor (C/D).
//   is_first / is_last control which face gets the alignment pin
//   (right face, !is_last) and which gets the pin hole (left, !is_first).
// ============================================================
module tray_floor_section(start_slot=0, is_first=true, is_last=false) {
    n = n_slots_per_section;
    sec_w = section_w;
    lower = start_slot < n_slots;
    c_y0  = lower ? tray_wall + boss_d : tray_wall;   // side chamfers stop at bosses

    difference() {
        union() {
            difference() {
                cube([sec_w, tray_depth, floor_h]);
                // Slot voids (open top and open back)
                for (i = [0 : n - 1])
                    translate([slot_x(i), tray_wall, tray_wall])
                        cube([slot_w, tray_depth - tray_wall + 0.1, floor_h]);
            }
            // Front-corner stacking bosses, fused to floor + walls, flush at floor_h
            if (lower)
                for (i = [0 : n - 1])
                    for (bx = [slot_x(i), slot_x(i) + slot_w - boss_w])
                        // 0.01 overlap into the wall/divider/floor so the union fuses
                        translate([bx - 0.01, tray_wall - 0.01, tray_wall - 0.01])
                            cube([boss_w + 0.02, boss_d + 0.01, floor_h - tray_wall + 0.01]);
        }

        // Lead-in chamfers on every top inner edge (top stays flat at floor_h)
        for (i = [0 : n - 1]) {
            cl = (i == 0)     ? chamfer_wall : chamfer_div;
            cr = (i == n - 1) ? chamfer_wall : chamfer_div;
            chamfer_cut_y(slot_x(i),          cl, c_y0, tray_depth + 1);
            chamfer_cut_y(slot_x(i) + slot_w, cr, c_y0, tray_depth + 1);
            // front wall inner edge (between the bosses on the lower floor)
            chamfer_cut_x(tray_wall, chamfer_wall,
                          slot_x(i) + (lower ? boss_w : 0),
                          slot_x(i) + slot_w - (lower ? boss_w : 0));
        }

        // Label windows (front face, Y=0) — kept clear of the bosses
        for (i = [0 : n - 1]) {
            m  = lower ? boss_w + label_inset : label_inset;
            translate([slot_x(i) + m, -0.1, label_margin])
                cube([slot_w - 2 * m, tray_wall + 0.2, label_h]);
        }

        if (lower) {
            // Baseplate screws: countersunk through the slot floors
            for (p = is_first ? base_holes_A : base_holes_B)
                translate([p[0], p[1], 0]) csk_hole(tray_wall);
            // Stacking pilots in the boss tops
            for (p = stack_points())
                translate([p[0], p[1], floor_h - m3_pilot_h])
                    cylinder(d = m3_pilot, h = m3_pilot_h + 0.1, $fn = 20);
        } else {
            // Stacking screws: countersunk through the upper floor, coaxial
            // with the shelf holes and the lower bosses' pilots
            for (p = stack_points())
                translate([p[0], p[1], 0]) csk_hole(tray_wall);
        }

        // Alignment pin hole on left face (receives pin from section to left).
        // Through the 2.5mm wall (2.6mm deep incl. 0.1 overcut); the 2.0mm
        // pin bottoms out 0.5mm short of the slot interior.
        if (!is_first)
            translate([-0.1, tray_depth/2, pin_z])
                rotate([0, 90, 0])
                cylinder(d=pin_dia, h=tray_wall+0.2, $fn=24);
        // (No hole on the right face — that face carries the pin.)
    }

    // Alignment pin on right face (mates with next section's left-face hole).
    // Unioned AFTER the difference() so it is not cut away.
    // Spans x = sec_w − pin_embed .. sec_w + pin_h_protr (135 .. 139).
    if (!is_last)
        translate([sec_w - pin_embed, tray_depth/2, pin_z])
            rotate([0, 90, 0])
            cylinder(d=pin_dia_pin, h=pin_embed + pin_h_protr, $fn=24);
}

// ============================================================
// MODULE: floor_shelf_half
//   One half of the separator shelf between the floors, covering exactly
//   one section (137 × 98 × 3 → fits the 256mm bed). Both halves are
//   IDENTICAL — PRINT 2× PER TRAY. `side` (0 = left over A/C, 1 = right
//   over B/D) only positions it for the assembly preview; print side=0.
//   Seam at x = 137 coincides with the section seam. No joint between the
//   halves: each is clamped by its 4 stacking screws to the section pair
//   below/above, and the section pairs are aligned by the side pin.
// ============================================================
module floor_shelf_half(side=0) {
    translate([side * section_w, 0, 0])
        difference() {
            cube([section_w, tray_depth, shelf_h]);
            for (p = stack_points())
                translate([p[0], p[1], -0.1])
                    cylinder(d=m3_dia, h=shelf_h+0.2, $fn=24);
        }
}

// Full shelf (preview only — 274mm, too wide to print in one piece)
module floor_shelf() {
    for (s = [0 : n_sections - 1]) floor_shelf_half(s);
}

// ============================================================
// MODULE: full_2floor_assembly (preview only — not for printing)
// ============================================================
module full_2floor_assembly() {
    sec_w = section_w;
    // Lower floor — Section A (slots 0–1)
    color("SteelBlue")  tray_floor_section(0, true, false);
    // Lower floor — Section B (slots 2–3)
    translate([sec_w, 0, 0])
    color("CornflowerBlue") tray_floor_section(2, false, true);

    // Shelf between floors (2 identical halves)
    translate([0, 0, floor_h])
    color("LightGray", 0.5) floor_shelf();

    // Upper floor — Section C (slots 4–5)
    translate([0, 0, floor_h + shelf_h])
    color("SlateBlue") tray_floor_section(4, true, false);
    // Upper floor — Section D (slots 6–7)
    translate([sec_w, 0, floor_h + shelf_h])
    color("MediumPurple") tray_floor_section(6, false, true);
}

// ============================================================
// DEFAULT RENDER: Lower floor, Section A (slots 0–1)
// Uncomment the desired piece below to print it.
// ============================================================
tray_floor_section(start_slot=0, is_first=true, is_last=false);

// Lower floor, Section B (slots 2–3):
// tray_floor_section(start_slot=2, is_first=false, is_last=true);

// Separator shelf half (print 2× per tray):
// floor_shelf_half();

// Upper floor, Section C (slots 4–5):
// tray_floor_section(start_slot=4, is_first=true, is_last=false);

// Upper floor, Section D (slots 6–7):
// tray_floor_section(start_slot=6, is_first=false, is_last=true);

// Full assembly preview (NOT for printing):
// full_2floor_assembly();

// ============================================================
// DIMENSIONS SUMMARY:
//   One section:  137mm × 98mm × 65mm (+2mm pin on A/C) ← fits P1S 256mm ✓
//                 top face flat at z = 65 (chamfers cut in, nothing above)
//   Shelf half:   137mm × 98mm × 3mm, 4× Ø3.4 — print 2× per tray ✓
//   Full tray W:  2 × 137 = 274mm (was 585mm) ← saves 311mm ✓
//                 (5mm double wall at the A|B join; world Y in assembly.scad)
//   Full tray H:  65+3+65 = 133mm tall    ← adds height, not footprint
//   Machine footprint: ~540mm X × ~300mm Z (well under 2ft×2ft ✓)
//
//   Stacking screw axes (section-local, same on all 4 sections + shelf):
//     x = 6, 64, 73, 131   y = 5.6
//   Baseplate screw axes (lower floor):
//     A: x = 32, 92   B: x = 45, 105   y = 16, 76  (tray back face at world X 178)
//
// SLOT ASSIGNMENTS (lower → upper, left → right):
//   Floor 0 slot 0: Champions     Floor 1 slot 4: Legendary
//   Floor 0 slot 1: Spells        Floor 1 slot 5: Epic/Rare
//   Floor 0 slot 2: Followers     Floor 1 slot 6: Common
//   Floor 0 slot 3: Equipment     Floor 1 slot 7: Basic/Default
//
// REJECT SLOT: Small 1-slot section (tray_floor_section n=1) at end.
// ============================================================
