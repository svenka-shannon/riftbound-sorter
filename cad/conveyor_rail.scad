// =============================================
// Riftbound Card Sorter — Conveyor Side Rail
// =============================================
// Print 2× (mirror for left/right)
// 250mm total → split into 2×125mm for P1S
// Each piece has alignment pins/holes for joining
// Material: PLA, 0.2mm layers, 40% infill
// =============================================

// Parameters
rail_len    = 125;    // half-length (split for P1S bed); total = 250mm
rail_h      = 35;
wall        = 3.0;
card_h      = 88;     // Riftbound card height

// Card guide groove (card rides in this channel)
groove_depth = 2.5;
groove_w     = 1.5;   // just enough to keep card upright

// Roller shaft holes
shaft_dia    = 8.2;   // 8mm rod + clearance
shaft_y      = 15;    // height from base
shaft_x1     = 25;    // near end
shaft_x2     = 100;   // far end (only in second half piece)

// Alignment pin (M3 pin = 3mm dia)
pin_dia  = 3.2;
pin_h    = 5;
pin_x    = rail_len - 5;

module rail_half(add_shaft_far = false) {
    difference() {
        // Rail body
        cube([rail_len, wall, rail_h]);

        // Card guide groove (inner face, top)
        translate([-0.1, -0.1, rail_h - groove_depth])
            cube([rail_len + 0.2, groove_depth + 0.1, groove_depth + 0.1]);

        // Near roller shaft hole
        translate([shaft_x1, wall / 2, shaft_y])
            rotate([90, 0, 0])
            cylinder(d = shaft_dia, h = wall + 0.2, center = true, $fn = 32);

        // Far roller shaft hole (only in second piece)
        if (add_shaft_far)
            translate([shaft_x2 - rail_len, wall / 2, shaft_y])
                rotate([90, 0, 0])
                cylinder(d = shaft_dia, h = wall + 0.2, center = true, $fn = 32);

        // Alignment hole at join end
        translate([pin_x, wall / 2, rail_h / 2])
            rotate([90, 0, 0])
            cylinder(d = pin_dia, h = wall + 0.2, center = true, $fn = 24);
    }

    // Alignment pin at start end (protruding)
    translate([5, wall / 2, rail_h / 2])
        rotate([90, 0, 0])
        cylinder(d = pin_dia - 0.2, h = pin_h + wall, center = true, $fn = 24);
}

// Render first half (has near shaft hole + outgoing pin)
rail_half(add_shaft_far = false);

// Uncomment for second half:
// rail_half(add_shaft_far = true);

// =============================================
// PRINT ORIENTATION: wide face on bed
// SUPPORTS: minimal (shaft holes only if rotated)
// =============================================
