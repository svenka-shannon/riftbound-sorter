// =============================================
// Riftbound Card Sorter — Electronics Tray
// =============================================
// Mounts: Pi Zero 2W, PCA9685, HX711, relay module
// Sits on baseplate, recessed 10mm below top surface
// Material: PLA, 0.2mm, 40% infill
// =============================================

outer_w   = 185;
outer_d   = 125;
outer_h   = 45;
wall      = 2.5;

// Pi Zero 2W mounting holes (58mm × 23mm pattern, M2.5)
pi_hole_x = [10, 68];
pi_hole_y = [10, 33];
pi_hole_d = 2.7;
pi_standoff_h = 5;
pi_standoff_d = 6;

// PCA9685 mounting holes (25mm × 60mm, M2.5)
pca_x = [100, 125];
pca_y = [10, 70];
pca_hole_d = 2.7;

// HX711 load cell amplifier board (20mm × 15mm, M2.5 holes at corners)
hx711_x      = 150;   // position from left edge of tray
hx711_y      = 75;    // position from front edge
hx711_hole_d = 2.7;   // M2.5 clearance
hx711_hole_dx = 20;   // spacing X
hx711_hole_dy = 15;   // spacing Y

// Load cell beam recess (60mm × 12mm × 3mm pocket for TAL221 50g beam)
lcell_x      = 140;
lcell_y      = 60;
lcell_len    = 60;
lcell_w      = 12;
lcell_dep    = 3;

// Cable management slots
slot_w = 10;
slot_h = 6;

module electronics_tray() {
    difference() {
        cube([outer_w, outer_d, outer_h]);

        // Interior
        translate([wall, wall, wall])
            cube([outer_w - wall*2, outer_d - wall*2, outer_h]);

        // Cable slots (3× on right side)
        for (i = [0:2])
            translate([outer_w - wall - 0.1, 20 + i * 30, outer_h - slot_h - wall])
                cube([wall + 0.2, slot_w, slot_h]);

        // M3 baseplate mounting holes (corners)
        for (x = [8, outer_w - 8]) for (y = [8, outer_d - 8])
            translate([x, y, -0.1])
                cylinder(d = 3.4, h = wall + 0.2, $fn = 16);

        // Load cell beam recess (sits flush in pocket, beam end overhangs hopper side)
        translate([lcell_x, lcell_y, outer_h - lcell_dep])
            cube([lcell_len, lcell_w, lcell_dep + 0.1]);

        // HX711 board mount holes (M2.5, 4× at 20×15mm pattern)
        for (dx = [0, hx711_hole_dx]) for (dy = [0, hx711_hole_dy])
            translate([hx711_x + dx, hx711_y + dy, -0.1])
                cylinder(d = hx711_hole_d, h = wall + 0.2, $fn = 16);
    }

    // HX711 standoffs (4×, like Pi standoffs)
    for (dx = [0, hx711_hole_dx]) for (dy = [0, hx711_hole_dy])
        translate([hx711_x + dx, hx711_y + dy, wall])
            difference() {
                cylinder(d = pi_standoff_d, h = pi_standoff_h, $fn = 16);
                translate([0, 0, -0.1])
                    cylinder(d = hx711_hole_d, h = pi_standoff_h + 0.2, $fn = 16);
            }

    // Pi Zero 2W standoffs
    for (x = pi_hole_x) for (y = pi_hole_y)
        translate([x, y, wall])
            difference() {
                cylinder(d = pi_standoff_d, h = pi_standoff_h, $fn = 16);
                translate([0, 0, -0.1])
                    cylinder(d = pi_hole_d, h = pi_standoff_h + 0.2, $fn = 16);
            }

    // PCA9685 standoffs
    for (x = pca_x) for (y = pca_y)
        translate([x, y, wall])
            difference() {
                cylinder(d = pi_standoff_d, h = pi_standoff_h, $fn = 16);
                translate([0, 0, -0.1])
                    cylinder(d = pca_hole_d, h = pi_standoff_h + 0.2, $fn = 16);
            }
}

electronics_tray();
