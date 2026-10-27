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
card_thick  = 0.3;     // single card thickness mm
n_cards     = 300;     // design capacity
clearance   = 1.5;     // per-side clearance for smooth feeding

wall        = 3.0;     // wall thickness
inner_w     = card_w + clearance * 2;   // 66mm
inner_d     = card_h + clearance * 2;   // 91mm
stack_h     = n_cards * card_thick;     // 90mm
inner_h     = stack_h + 15;             // 105mm (extra headroom)

outer_w     = inner_w + wall * 2;       // 72mm
outer_d     = inner_d + wall * 2;       // 97mm
outer_h     = inner_h + wall;           // 108mm

exit_slot_h = 3.5;    // card exit slot height (slightly more than 1 card)
exit_slot_w = inner_w + 0.5;

spring_w    = 25;
spring_d    = 8;

module hopper_body() {
    difference() {
        // Outer shell
        cube([outer_w, outer_d, outer_h]);

        // Inner cavity (open top)
        translate([wall, wall, wall])
            cube([inner_w, inner_d, outer_h]);

        // Card exit slot (bottom front face)
        translate([(outer_w - exit_slot_w) / 2, 0, wall])
            cube([exit_slot_w, wall + 0.1, exit_slot_h]);

        // Spring pusher channel (back wall interior)
        translate([(outer_w - spring_w) / 2, outer_d - wall - spring_d, wall])
            cube([spring_w, spring_d + 0.1, inner_h]);
    }
}

module spring_pusher() {
    // Sled that rides in the spring channel to push cards forward
    translate([0, 0, 0])
        cube([spring_w - 0.4, spring_d - 0.4, 20]);
}

// Render hopper body by default
hopper_body();

// Uncomment to render spring pusher:
// spring_pusher();

// =============================================
// PRINT ORIENTATION: flat base on bed
// SUPPORTS: none needed
// POST-PROCESS: light sanding on inner walls
//               for smooth card feeding
// =============================================
