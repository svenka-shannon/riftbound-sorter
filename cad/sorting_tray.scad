// ============================================================
// Riftbound Card Sorter — 2-Floor Sorting Tray
// ============================================================
// Replaces single-row 9-slot tray.
// TWO stacked floors of 4 slots each = 8 sort slots.
// Sort gate routes cards to floor + column position.
//
// COMPACT FOOTPRINT:
//   Single-row tray: 9 × 65mm = 585mm wide ✗ (too wide)
//   2-floor tray:    4 × 65mm = 260mm wide ✓  (saves 325mm)
//
// CARD FLOW:
//   Gate deflects card to Z column (0-3) AND floor (lower/upper).
//   Lower floor: slots 0–3 (Champion, Spell, Follower, Equipment)
//   Upper floor: slots 4–7 (Legendary, Epic/Rare, Common, Basic)
//   Reject: a separate small tray at end of lower floor.
//
// PRINT: 4 pieces total (2 sections per floor × 2 floors)
//   Each section: ~137mm × 103mm × 65mm → fits P1S 256mm bed ✓
//   Material: PLA, 0.2mm, 40% infill
//   Orientation: flat on bed (open top facing up)
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
floor_h     = 65;                    // height per floor (keeps card upright)
tray_depth  = card_h + 10;          // 98mm (10mm headroom above card)

// ── Section split (2 slots per printed section) ─────────────
// Width of 2-slot section: 2×65 + 1 divider + 2 walls = 137mm ✓ P1S
n_slots_per_section = 2;
section_w = slot_w * n_slots_per_section
          + divider_t * (n_slots_per_section - 1)
          + tray_wall * 2;
// section_w = 2×65 + 1×2 + 2×2.5 = 137mm

// ── Full tray width (both sections joined) ──────────────────
// = 2 × section_w − tray_wall (shared wall at join becomes one wall)
// = 2×137 − 2.5 = 271.5mm  ← 271mm footprint in Z ✓
full_tray_w = slot_w * n_slots + divider_t * (n_slots - 1) + tray_wall * 2;
// = 4×65 + 3×2 + 2×2.5 = 271mm

// ── Floor gap / shelf between floors ────────────────────────
shelf_h = 3;           // thin shelf separating floors
floor_gap = shelf_h;   // visual gap = shelf thickness

// ── Label windows on front face ─────────────────────────────
label_h      = 18;
label_margin = 3;
label_inset  = 0.5;

// ── Alignment pin — 3mm, same as conveyor_rail.scad ─────────
pin_dia     = 3.2;
pin_dia_pin = 3.0;
pin_h_protr = 5.0;
pin_z       = floor_h / 2;

// ── M3 baseplate mounting holes ─────────────────────────────
m3_dia  = 3.4;
m3_inset = 5;

// ── Divider top chamfer to guide card entry ──────────────────
chamfer = 1.5;

// ============================================================
// MODULE: tray_floor_section
//   One floor, one 2-slot section (printable piece).
//   is_first / is_last control which face gets perimeter wall
//   vs alignment pin on the joining face.
// ============================================================
module tray_floor_section(start_slot=0, is_first=true, is_last=false) {
    n = n_slots_per_section;
    sec_w = section_w;

    difference() {
        cube([sec_w, tray_depth, floor_h]);

        // Slot voids
        for (i = [0 : n - 1]) {
            sx = tray_wall + i * (slot_w + divider_t);
            translate([sx, tray_wall, tray_wall])
                cube([slot_w, tray_depth - tray_wall, floor_h]);
        }

        // Label windows (front face, Y=0)
        for (i = [0 : n - 1]) {
            sx = tray_wall + i * (slot_w + divider_t);
            lw = slot_w - label_inset * 2;
            translate([sx + label_inset, -0.1, label_margin])
                cube([lw, tray_wall + 0.2, label_h]);
        }

        // M3 corner holes (base)
        for (cx = [m3_inset, sec_w - m3_inset])
            for (cy = [m3_inset, tray_depth - m3_inset])
                translate([cx, cy, -0.1])
                    cylinder(d=m3_dia, h=tray_wall+0.2, $fn=24);

        // Alignment pin hole on left face (receives pin from section to left)
        if (!is_first)
            translate([-0.1, tray_depth/2, pin_z])
                rotate([0, 90, 0])
                cylinder(d=pin_dia, h=tray_wall+0.2, $fn=24);

        // Alignment pin hole on right face (receives pin from right)
        if (!is_last)
            translate([sec_w - tray_wall - 0.1, tray_depth/2, pin_z])
                rotate([0, 90, 0])
                cylinder(d=pin_dia, h=tray_wall+0.2, $fn=24);
    }

    // Alignment pin protrusion on right face (mates with next section)
    if (!is_last)
        translate([sec_w + pin_h_protr/2, tray_depth/2, pin_z])
            rotate([0, 90, 0])
            cylinder(d=pin_dia_pin, h=pin_h_protr, center=true, $fn=24);

    // Divider top chamfers
    for (i = [1 : n - 1]) {
        dx = tray_wall + i * (slot_w + divider_t) - divider_t;
        translate([dx, tray_wall, floor_h])
            rotate([0, -45, 0])
            cube([chamfer*sqrt(2), tray_depth-tray_wall, chamfer*sqrt(2)]);
    }
    // Left wall chamfer
    translate([tray_wall, tray_wall, floor_h])
        rotate([0, -45, 0])
        cube([chamfer*sqrt(2), tray_depth-tray_wall, chamfer*sqrt(2)]);
    // Right wall chamfer
    translate([sec_w - tray_wall - chamfer*sqrt(2), tray_wall, floor_h])
        rotate([0, -45, 0])
        cube([chamfer*sqrt(2), tray_depth-tray_wall, chamfer*sqrt(2)]);
}

// ============================================================
// MODULE: floor_shelf
//   Thin separator shelf that sits on top of the lower floor.
//   Cards drop THROUGH the open upper floor into lower slots
//   OR land on top of shelf for upper floor.
//   In practice: upper floor tray section sits on top, shelf
//   provides separation — separate printed piece.
// ============================================================
module floor_shelf() {
    difference() {
        cube([full_tray_w, tray_depth, shelf_h]);
        // Open holes above each lower slot so lower-floor cards can pass
        // (lower floor has its own walls, so no holes needed — shelf is solid)
        // M3 screw holes at corners to stack floors
        for (cx = [m3_inset, full_tray_w - m3_inset])
            for (cy = [m3_inset, tray_depth - m3_inset])
                translate([cx, cy, -0.1])
                    cylinder(d=m3_dia, h=shelf_h+0.2, $fn=24);
    }
}

// ============================================================
// MODULE: full_2floor_assembly (preview only — not for printing)
// ============================================================
module full_2floor_assembly() {
    sec_w = section_w;
    // Lower floor — Section A (slots 0–1)
    color("SteelBlue")  tray_floor_section(0, true, false);
    // Lower floor — Section B (slots 2–3)
    translate([sec_w + pin_h_protr, 0, 0])
    color("CornflowerBlue") tray_floor_section(2, false, true);

    // Shelf between floors
    translate([0, 0, floor_h])
    color("LightGray", 0.5) floor_shelf();

    // Upper floor — Section C (slots 4–5)
    translate([0, 0, floor_h + shelf_h])
    color("SlateBlue") tray_floor_section(4, true, false);
    // Upper floor — Section D (slots 6–7)
    translate([sec_w + pin_h_protr, 0, floor_h + shelf_h])
    color("MediumPurple") tray_floor_section(6, false, true);
}

// ============================================================
// DEFAULT RENDER: Lower floor, Section A (slots 0–1)
// Uncomment the desired section below to print it.
// ============================================================
tray_floor_section(start_slot=0, is_first=true, is_last=false);

// Lower floor, Section B (slots 2–3):
// translate([section_w + pin_h_protr, 0, 0])
// tray_floor_section(start_slot=2, is_first=false, is_last=true);

// Separator shelf (between floors):
// floor_shelf();

// Upper floor, Section C (slots 4–5):
// tray_floor_section(start_slot=4, is_first=true, is_last=false);

// Upper floor, Section D (slots 6–7):
// translate([section_w + pin_h_protr, 0, 0])
// tray_floor_section(start_slot=6, is_first=false, is_last=true);

// Full assembly preview (NOT for printing):
// full_2floor_assembly();

// ============================================================
// DIMENSIONS SUMMARY:
//   One section:  137mm × 98mm × 65mm    ← fits P1S 256mm ✓
//   Full tray Z:  271mm (was 585mm)       ← saves 314mm ✓
//   Full tray H:  65+3+65 = 133mm tall    ← adds height, not footprint
//   Machine footprint: ~540mm X × ~300mm Z (well under 2ft×2ft ✓)
//
// SLOT ASSIGNMENTS (lower → upper, left → right):
//   Floor 0 slot 0: Champions     Floor 1 slot 4: Legendary
//   Floor 0 slot 1: Spells        Floor 1 slot 5: Epic/Rare
//   Floor 0 slot 2: Followers     Floor 1 slot 6: Common
//   Floor 0 slot 3: Equipment     Floor 1 slot 7: Basic/Default
//
// REJECT SLOT: Small 1-slot section (tray_floor_section n=1) at end.
// ============================================================
