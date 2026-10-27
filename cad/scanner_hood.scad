// =============================================
// Riftbound Card Sorter — Scanner Hood
// =============================================
// Encloses Pi Camera + LED ring over the conveyor
// Blocks ambient light for consistent card imaging
// Material: PLA, 0.1mm layers (detail), 40% infill
// =============================================

card_w       = 63 + 3;   // card + clearance
card_pass_h  = 3.5;      // card pass-through slot height
wall         = 3.0;
outer_w      = 95;
outer_d      = 75;
outer_h      = 65;

cam_mount_sq = 25;        // camera board mount square
led_ring_dia = 52;        // LED ring OD
led_ring_dep = 5;         // LED ring recess depth

module scanner_hood() {
    difference() {
        // Outer shell
        cube([outer_w, outer_d, outer_h]);

        // Interior cavity (open bottom — faces conveyor)
        translate([wall, wall, wall])
            cube([outer_w - wall*2, outer_d - wall*2, outer_h]);

        // Camera mount square (top center)
        translate([(outer_w - cam_mount_sq) / 2,
                   (outer_d - cam_mount_sq) / 2,
                   outer_h - wall - 0.1])
            cube([cam_mount_sq, cam_mount_sq, wall + 0.2]);

        // LED ring recess (inner top face)
        translate([outer_w / 2, outer_d / 2, outer_h - wall - led_ring_dep])
            cylinder(d = led_ring_dia, h = led_ring_dep + 0.1, $fn = 64);

        // Card entry slot (front face) — z=0 so card passes at conveyor height
        translate([(outer_w - card_w) / 2, -0.1, -0.1])
            cube([card_w, wall + 0.2, card_pass_h + 0.1]);

        // Card exit slot (back face) — z=0 so card passes at conveyor height
        translate([(outer_w - card_w) / 2, outer_d - wall, -0.1])
            cube([card_w, wall + 0.2, card_pass_h + 0.1]);

        // Camera cable slot (side)
        translate([outer_w - wall, outer_d / 2 - 5, outer_h - 20])
            cube([wall + 0.1, 10, 15]);
    }
}

scanner_hood();

// =============================================
// PRINT ORIENTATION: open bottom facing up (bridge)
// SUPPORTS: yes — for camera mount cutout
// TIP: print in black PLA for best light control
// =============================================
