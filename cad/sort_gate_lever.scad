// =============================================
// Riftbound Card Sorter — Sort Gate Lever
// =============================================
// Print 2× (primary deflect gate + secondary bin select)
// Servo horn drives the lever to route cards left/right
// Material: PETG (flex-resistant), 0.2mm, 60% infill
// =============================================

lever_len    = 70;
lever_w      = 12;
lever_thick  = 6;
pivot_x      = 10;
pivot_dia    = 5.2;

// Servo horn (25T standard)
horn_pcd     = 15;
horn_hole_d  = 3.2;
horn_ctr_d   = 5.2;

// Paddle at tip (deflects cards)
paddle_l     = 40;
paddle_angle = 15;  // degrees, angled to guide card smoothly

module gate_lever() {
    difference() {
        union() {
            // Main lever body
            cube([lever_len, lever_w, lever_thick]);

            // Paddle (angled deflector at tip)
            translate([lever_len - paddle_l, 0, 0])
                rotate([0, 0, paddle_angle])
                cube([paddle_l, lever_w, lever_thick]);
        }

        // Pivot hole
        translate([pivot_x, lever_w / 2, -0.1])
            cylinder(d = pivot_dia, h = lever_thick + 0.2, $fn = 24);

        // Servo horn center + 4× M3 holes
        translate([pivot_x, lever_w / 2, -0.1])
            cylinder(d = horn_ctr_d, h = lever_thick + 0.2, $fn = 24);

        for (a = [0, 90, 180, 270])
            translate([
                pivot_x + cos(a) * horn_pcd / 2,
                lever_w / 2 + sin(a) * horn_pcd / 2,
                -0.1
            ])
                cylinder(d = horn_hole_d, h = lever_thick + 0.2, $fn = 16);
    }
}

gate_lever();

// =============================================
// PRINT ORIENTATION: flat face down
// SUPPORTS: none needed
// PRINT 2× (mirror in slicer for second lever)
// =============================================
