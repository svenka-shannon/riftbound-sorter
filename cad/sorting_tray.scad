// ============================================================
// Riftbound Card Sorter — Sorting Tray
// ============================================================
// Replaces 9 individual output bins with a single unified tray
// styled like a desktop letter-sorter / magazine rack.
// Cards fall in VERTICALLY (top-open slots, card face forward).
//
// CARD FLOW:
//   Sort gate lever deflects card → flies off conveyor end
//   → drops down into the appropriate tray slot
//   Cards stand upright, readable from above/front.
//
// ASSEMBLY ORIENTATION (top view):
//   Conveyor → [Section A: slots 0-2] [Section B: slots 3-5] [Section C: slots 6-8]
//   Section C rightmost slot = reject slot (slot index 8)
//   Sections join on the X axis (width direction).
//   Alignment pins on mating faces, identical to conveyor_rail.scad.
//
// PRINT NOTES:
//   Each 3-slot section: ~204mm × 103mm × 65mm → fits P1S 256×256mm straight.
//   Print 3 sections total.
//   Material: PLA or PETG, 0.2mm layers, 40% infill.
//   Orientation: flat on bed (large face down, open top facing up).
//   Supports: none needed.
// ============================================================

// ── Card dimensions (Riftbound standard) ───────────────────
card_w   = 63;     // card width  (mm)
card_h   = 88;     // card height (mm)
card_clr = 2;      // lateral clearance per slot (1mm each side)

// ── Slot geometry ───────────────────────────────────────────
slot_w      = card_w + card_clr;   // 65mm per slot
n_slots_per_section = 3;           // 3 slots per printed section
n_sections  = 3;                   // 3 sections = 9 slots total
n_slots     = n_slots_per_section * n_sections;  // 9 (8 sorted + 1 reject)

// ── Tray body ───────────────────────────────────────────────
tray_wall    = 2.5;   // perimeter wall thickness
divider_t    = 2.0;   // thickness of internal dividers
tray_height  = 65;    // wall height — keeps cards upright
tray_depth   = card_h + 10;  // 98mm front-to-back (10mm headroom above card)

// ── Label window (front face cutout per slot) ───────────────
label_h      = 18;    // label holder window height
label_margin = 3;     // distance from tray floor to bottom of label window
label_inset  = 0.5;   // wall material left at sides of label window

// ── Alignment pins — matches conveyor_rail.scad ─────────────
pin_dia      = 3.2;   // M3 pin hole diameter
pin_dia_pin  = 3.0;   // pin protrusion diameter (slight interference)
pin_h_protr  = 5.0;   // protrusion length beyond face
pin_z        = tray_height / 2;  // vertical centre of pin

// ── M3 mounting holes at tray base ──────────────────────────
m3_dia       = 3.4;   // M3 clearance
m3_inset     = 5;     // from corner edges

// ── Chamfer on divider tops to guide card entry ─────────────
chamfer      = 1.5;   // 45° chamfer height/width on divider top edges

// ── Computed section width ──────────────────────────────────
// 3 slots × 65mm + 2 internal dividers + 2 perimeter walls
// = 195 + 4 + 5 = 204mm  → fits 256mm P1S bed straight ✓
section_w = slot_w * n_slots_per_section
          + divider_t * (n_slots_per_section - 1)
          + tray_wall * 2;
// section_w ≈ 204mm

// ============================================================
// MODULE: single_slot_cell
//   Produces the void (positive geometry) of one card slot.
//   Origin at slot interior bottom-left-front corner.
// ============================================================
module single_slot_cell() {
    cube([slot_w, tray_depth, tray_height]);
}

// ============================================================
// MODULE: tray_section(n, start_label)
//   n           — number of slots in this section (default 3)
//   start_label — slot index of leftmost slot (0, 3, or 6)
//   is_first    — true = left end is a closed perimeter wall
//                 false = left face is a mating/pin face
//   is_last     — true = right end is a closed perimeter wall
//                 false = right face is a mating/pin face
// ============================================================
module tray_section(n = 3, start_label = 0, is_first = true, is_last = false) {

    // Derived widths for this section
    sec_w = slot_w * n
          + divider_t * (n - 1)
          + tray_wall * 2;

    difference() {
        // ── Solid tray body ───────────────────────────────
        cube([sec_w, tray_depth, tray_height]);

        // ── Slot voids (card pockets) ─────────────────────
        for (i = [0 : n - 1]) {
            slot_x = tray_wall + i * (slot_w + divider_t);
            // Remove material from floor up, leaving tray_wall on floor
            translate([slot_x, tray_wall, tray_wall])
                cube([slot_w, tray_depth - tray_wall, tray_height]);
            // Note: top is fully open — no lid. Cards drop straight in.
        }

        // ── Label windows on front face ───────────────────
        for (i = [0 : n - 1]) {
            slot_x = tray_wall + i * (slot_w + divider_t);
            label_w = slot_w - label_inset * 2;
            translate([slot_x + label_inset, -0.1, label_margin])
                cube([label_w, tray_wall + 0.2, label_h]);
        }

        // ── M3 mounting holes (bottom face, 4 corners) ────
        // Front-left
        translate([m3_inset, m3_inset, -0.1])
            cylinder(d = m3_dia, h = tray_wall + 0.2, $fn = 24);
        // Front-right
        translate([sec_w - m3_inset, m3_inset, -0.1])
            cylinder(d = m3_dia, h = tray_wall + 0.2, $fn = 24);
        // Rear-left
        translate([m3_inset, tray_depth - m3_inset, -0.1])
            cylinder(d = m3_dia, h = tray_wall + 0.2, $fn = 24);
        // Rear-right
        translate([sec_w - m3_inset, tray_depth - m3_inset, -0.1])
            cylinder(d = m3_dia, h = tray_wall + 0.2, $fn = 24);

        // ── Alignment pin HOLES on mating faces ──────────
        // Left face hole (receives pin from section to the left)
        if (!is_first)
            translate([-0.1, tray_depth / 2, pin_z])
                rotate([0, 90, 0])
                cylinder(d = pin_dia, h = tray_wall + 0.2, $fn = 24);

        // Right face hole (receives pin from section to the right)
        if (!is_last)
            translate([sec_w - tray_wall - 0.1, tray_depth / 2, pin_z])
                rotate([0, 90, 0])
                cylinder(d = pin_dia, h = tray_wall + 0.2, $fn = 24);
    }

    // ── Alignment pin PROTRUSIONS on mating faces ─────────
    // Right face pin (protrudes → mates with left hole of next section)
    if (!is_last)
        translate([sec_w + pin_h_protr / 2, tray_depth / 2, pin_z])
            rotate([0, 90, 0])
            cylinder(d = pin_dia_pin, h = pin_h_protr, center = true, $fn = 24);

    // ── Divider top chamfers (guide card entry) ────────────
    // Chamfer each divider's top edge on both faces (front edge of opening)
    for (i = [1 : n - 1]) {
        div_x = tray_wall + i * (slot_w + divider_t) - divider_t;
        // 45° prism along depth axis, sitting on divider top corner
        translate([div_x, tray_wall, tray_height])
            rotate([0, -45, 0])
            cube([chamfer * sqrt(2), tray_depth - tray_wall, chamfer * sqrt(2)]);
    }

    // Chamfer on left perimeter wall top inner edge
    translate([tray_wall, tray_wall, tray_height])
        rotate([0, -45, 0])
        cube([chamfer * sqrt(2), tray_depth - tray_wall, chamfer * sqrt(2)]);

    // Chamfer on right perimeter wall top inner edge
    translate([sec_w - tray_wall - chamfer * sqrt(2), tray_wall, tray_height])
        rotate([0, -45, 0])
        cube([chamfer * sqrt(2), tray_depth - tray_wall, chamfer * sqrt(2)]);
}

// ============================================================
// MODULE: full_tray_assembly
//   Places all 3 sections side by side for preview only.
//   NOT for printing — print each section separately.
// ============================================================
module full_tray_assembly() {
    // Section A: slots 0–2 (leftmost, first section)
    sec_w_A = slot_w * 3 + divider_t * 2 + tray_wall * 2;
    color("SteelBlue")
        tray_section(n = 3, start_label = 0, is_first = true,  is_last = false);

    // Section B: slots 3–5 (middle)
    translate([sec_w_A + pin_h_protr, 0, 0])
    color("CornflowerBlue")
        tray_section(n = 3, start_label = 3, is_first = false, is_last = false);

    // Section C: slots 6–8 (rightmost; slot 8 = reject slot)
    translate([(sec_w_A + pin_h_protr) * 2, 0, 0])
    color("SlateBlue")
        tray_section(n = 3, start_label = 6, is_first = false, is_last = true);
}

// ============================================================
// DEFAULT RENDER — Section A (slots 0–2)
// To print other sections, comment this and uncomment below.
// ============================================================
tray_section(n = 3, start_label = 0, is_first = true, is_last = false);

// Section B (slots 3–5):
// tray_section(n = 3, start_label = 3, is_first = false, is_last = false);

// Section C (slots 6–8, rightmost slot = reject):
// tray_section(n = 3, start_label = 6, is_first = false, is_last = true);

// Full assembly preview (all 3 sections together, not for printing):
// full_tray_assembly();

// ============================================================
// SECTION DIMENSIONS (for reference):
//   Width:  3×65 + 2×2 + 2×2.5 = 204mm  ✓ fits P1S 256mm bed
//   Depth:  98mm
//   Height: 65mm
//
// SLOT LABELS (front label windows):
//   Slot 0–7: sorted card categories (per software config)
//   Slot 8:   reject / unsorted / error cards
//
// ASSEMBLY ORDER:
//   1. Print 3 sections (A, B, C)
//   2. Press M3×10 pins (or 3mm steel rod) into Section A & B right-face holes
//   3. Slide Section B and C onto pins until faces are flush
//   4. Optional: apply thin bead of CA glue at mating faces for permanent join
//   5. Mount to baseplate using M3 screws through corner holes (4 per section)
//
// CARD FLOW DIRECTION:
//   Conveyor runs left → right (or right → left depending on install).
//   Cards exit conveyor end and arc down into tray slots.
//   Tray front face (label side) faces the operator.
//   Tray open top faces the conveyor discharge end.
// ============================================================
