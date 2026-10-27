// =============================================
// Riftbound Card Sorter — Conveyor Roller
// =============================================
// Print 2× (one per shaft end)
// Driven by N20 gear motor via friction coupling
// O-ring grooves grip card underside
// Material: PLA, 4 perimeters, 60% infill (strength)
// =============================================

roller_dia  = 22;
roller_w    = 75;
shaft_bore  = 8.2;   // clearance for 8mm steel rod

oring_w     = 2.2;   // O-ring cross-section width
oring_depth = 1.6;   // groove depth
n_orings    = 4;

motor_flat_w = 4;    // flat on shaft for motor grub screw

module roller() {
    difference() {
        // Main cylinder
        cylinder(d = roller_dia, h = roller_w, $fn = 64);

        // Shaft bore (centered)
        translate([0, 0, -0.1])
            cylinder(d = shaft_bore, h = roller_w + 0.2, $fn = 32);

        // O-ring grooves (evenly spaced)
        for (i = [0 : n_orings - 1]) {
            z = (roller_w / (n_orings + 1)) * (i + 1);
            translate([0, 0, z])
                rotate_extrude($fn = 64)
                translate([roller_dia / 2 - oring_depth, 0, 0])
                square([oring_depth + 0.1, oring_w], center = true);
        }

        // Motor shaft flat (D-shaft style) — one side
        translate([shaft_bore / 2 - motor_flat_w + shaft_bore / 2,
                   -shaft_bore, -0.1])
            cube([motor_flat_w, shaft_bore * 2, roller_w + 0.2]);
    }
}

roller();

// =============================================
// PRINT ORIENTATION: axis vertical (on end)
// SUPPORTS: none needed
// POST-PROCESS: ream bore with 8mm drill bit
// O-RINGS: 16mm ID × 2mm cross-section (#010)
// =============================================
