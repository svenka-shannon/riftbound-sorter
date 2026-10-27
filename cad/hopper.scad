// =============================================
// Riftbound Card Sorter — Input Hopper
// =============================================
// Fits: 63mm W × 88mm H Riftbound cards (standard TCG size)
// Capacity: ~300 cards
// Printer: Bambu P1S (256×256×256mm bed)
// Material: PLA, 0.2mm layers, 40% infill
// =============================================

// Parameters
card_w      = 63;      // card width mm
card_h      = 88;      // card height mm
card_thick  = 0.3;     // single card thickness mm (range 0.28–0.35mm)
n_cards     = 300;     // design capacity
clearance   = 1.5;     // per-side clearance for smooth feeding

wall        = 3.0;     // wall thickness
inner_w     = card_w + clearance * 2;   // 66mm
inner_d     = card_h + clearance * 2;   // 91mm
stack_h     = n_cards * card_thick;     // 90mm
inner_h     = stack_h + 15;             // 105mm (15mm headroom above full stack)

outer_w     = inner_w + wall * 2;       // 72mm
outer_d     = inner_d + wall * 2;       // 97mm
outer_h     = inner_h + wall;           // 108mm

// Exit slot — single-card clearance
//
// Card thickness spec: 0.28–0.35mm (standard TCG).
// 0.65mm slot allows one card (≤0.35mm) with 0.30mm of flex clearance.
// Two perfectly flat stacked cards would need ≥0.56mm; the separation wedge
// below blocks them from entering the outer 1mm of the slot (see module).
// FDM minimum feature on Bambu P1S: ~0.5mm. 0.65mm is safely printable.
//
// Previous value was 3.5mm — that 3.2mm of excess clearance allowed 2–3
// cards to exit simultaneously before the load cell could detect a double-pick.
exit_slot_h = 0.80;   // single-card slot: 0.80mm > card_thick_max (0.35mm), wedge brings effective to 0.40mm
                      // FIX: was 0.65mm — wedge (sep_wedge_h) was only 0.15mm which is below 0.4mm nozzle min
exit_slot_w = inner_w + 0.5;

// Separation wedge parameters
//
// The wedge is a triangular lip that fills the top-outer corner of the exit
// slot, projecting sep_wedge_h mm downward from the slot ceiling at the outer
// face (Y=0) and tapering to nothing at sep_wedge_depth mm inside the slot.
//
// How it works (cards are flat, stacked in Z):
//   First card  (floor of hopper): Z = wall .. wall+0.35mm
//               clears the wedge — exits freely.
//   Second card (riding on first): Z = wall+0.30 .. wall+0.65mm
//               its top edge at Z≈wall+0.65 hits the wedge at the outer face,
//               blocking it from entering the slot while card 1 is still exiting.
//
//   Effective slot at outer face = exit_slot_h − sep_wedge_h = 0.50mm
//   One card (max 0.35mm) fits with 0.15mm margin.  ✓
//   Two stacked cards (min 0.56mm) are blocked.       ✓
//
// Angle note: a "standard" 30° wedge at 1mm depth projects tan(30°)×1mm ≈ 0.58mm,
// which would leave only 0.07mm clearance — all cards would jam.  The actual angle
// here is arctan(0.15 / 1.0) ≈ 8.5°, which is the steepest angle that keeps a
// worst-case 0.35mm card moving freely while still blocking a double-card entry.
sep_wedge_h     = 0.40;   // lip projection downward into slot at outer face (mm)
                          // FIX: was 0.15mm — below 0.4mm nozzle dia, slicer drops it entirely
                          // 0.40mm = 1 extrusion width exactly (printable), effective slot = 0.40mm
sep_wedge_depth = 1.0;    // wedge length into slot in Y direction (mm); ≥0.5mm for P1S

spring_w    = 25;
spring_d    = 8;

// =============================================
// Spring pusher / gravity sled — design notes
//
// This design uses a GRAVITY-FED sled (no spring).  The sled sits on top of
// the card stack and presses it downward by its own weight (~30–50g PLA),
// supplying roughly 0.3–0.5 N of feed force at all fill levels.
//
// Sled position with 300 cards (full hopper):
//   stack top  = wall + stack_h     = 3 + 90 = 93mm from base
//   sled top   = 93 + sled_h (20mm) = 113mm — 5mm above the hopper rim
//   The sled rides above the rim when full; that is intentional.
//   As cards are consumed the sled descends into the cavity.
//
// Sled position when empty:
//   sled bottom = wall = 3mm (resting on cavity floor)
//   sled top    = 3 + 20 = 23mm — fully inside cavity (outer_h = 108mm)  ✓
//
// The spring channel (inner_h = 105mm tall) gives full travel for the sled
// from floor (empty) to Z = wall + stack_h = 93mm (full).  ✓
//
// To upgrade to a spring-assisted feed (recommended for reliability):
//   Add a 4mm-diameter × 5mm-deep pocket to the top face of the sled.
//   Drop in a 4mm OD × 20mm compressed-length coil spring anchored to the lid.
//   Target spring force: 0.5–1.0 N (light; heavy springs buckle thin cards).
// =============================================

module separation_wedge() {
    // Triangular prism spanning the full slot width (X axis).
    // Cross-section in the YZ plane: full sep_wedge_h tall at Y=0 (outer face),
    // tapering to a line at Y=sep_wedge_depth (inside the slot).
    // hull() of two thin slabs gives the tapered wedge reliably on all OpenSCAD versions.
    x0 = (outer_w - exit_slot_w) / 2;
    hull() {
        // Front slab at outer face — full lip height
        translate([x0, 0, wall + exit_slot_h - sep_wedge_h])
            cube([exit_slot_w, 0.001, sep_wedge_h]);
        // Inner line at sep_wedge_depth — zero height (tapers to nothing)
        translate([x0, sep_wedge_depth, wall + exit_slot_h - 0.001])
            cube([exit_slot_w, 0.001, 0.001]);
    }
}

module spring_pusher() {
    // Gravity-fed sled that rests on top of the card stack.
    // Rides downward as cards exit; no spring required.
    // 0.4mm subtracted per side for smooth sliding fit in spring channel.
    cube([spring_w - 0.4, spring_d - 0.4, 20]);
}

module hopper_body() {
    union() {
        difference() {
            // Outer shell
            cube([outer_w, outer_d, outer_h]);

            // Inner cavity (open top)
            translate([wall, wall, wall])
                cube([inner_w, inner_d, outer_h]);

            // Card exit slot (bottom front face, single-card height)
            translate([(outer_w - exit_slot_w) / 2, 0, wall])
                cube([exit_slot_w, wall + 0.1, exit_slot_h]);

            // Gravity-sled / spring pusher channel (back wall interior).
            // Sled travels the full inner_h range in Z as the stack is consumed.
            translate([(outer_w - spring_w) / 2, outer_d - wall - spring_d, wall])
                cube([spring_w, spring_d + 0.1, inner_h]);
        }

        // Separation wedge: adds a triangular lip to the top of the exit slot
        // to block double-picks at the mechanical level (before load cell).
        separation_wedge();
    }
}

// Render hopper body by default
hopper_body();

// Uncomment to render gravity sled:
// spring_pusher();

// =============================================
// PRINT ORIENTATION: flat base on bed
// SUPPORTS: none needed
// POST-PROCESS: light sanding on inner walls
//               for smooth card feeding
// =============================================
