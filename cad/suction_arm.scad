// =============================================
// Riftbound Card Sorter — Suction Pickup Arm
// =============================================
// Servo (CH0) pivots arm over hopper → down → pick card → up
// Suction cup attaches at tip via 4mm barbed fitting
// Material: PETG (stress-bearing), 0.2mm layers, 60% infill
// =============================================

arm_len     = 130;
arm_w       = 18;
arm_thick   = 10;

pivot_dia   = 5.2;    // pivot rod hole
pivot_x     = 10;
pivot_z     = arm_thick / 2;

cup_dia     = 13.2;   // suction cup barbed fitting OD
cup_x       = arm_len - 10;

// 25T servo horn pattern (standard, 4× M3 at 15mm PCD)
horn_pcd    = 15;
horn_hole_d = 3.2;
horn_center_d = 5.2;

module suction_arm() {
    difference() {
        // Main arm body (slightly tapered for aesthetics)
        hull() {
            cube([arm_thick, arm_w, arm_thick]);
            translate([arm_len - arm_thick, arm_w * 0.3, 0])
                cube([arm_thick, arm_w * 0.4, arm_thick]);
        }

        // Pivot hole at base
        translate([pivot_x, arm_w / 2, -0.1])
            cylinder(d = pivot_dia, h = arm_thick + 0.2, $fn = 24);

        // Suction cup mount at tip
        translate([cup_x, arm_w / 2, -0.1])
            cylinder(d = cup_dia, h = arm_thick + 0.2, $fn = 32);

        // Servo horn center hole
        translate([pivot_x, arm_w / 2, -0.1])
            cylinder(d = horn_center_d, h = arm_thick + 0.2, $fn = 24);

        // Servo horn mounting holes (25T, 4× M3)
        for (a = [0, 90, 180, 270]) {
            translate([
                pivot_x + cos(a) * horn_pcd / 2,
                arm_w / 2 + sin(a) * horn_pcd / 2,
                -0.1
            ])
                cylinder(d = horn_hole_d, h = arm_thick + 0.2, $fn = 16);
        }

        // Vacuum tube channel (4mm bore along top face of arm)
        translate([pivot_x + 5, arm_w / 2, arm_thick - 3])
            cylinder(d = 4.5, h = cup_x - pivot_x, $fn = 16);
    }
}

suction_arm();

// =============================================
// PRINT ORIENTATION: flat on bed (wide face down)
// SUPPORTS: minimal around cup mount hole
// NOTE: run vacuum tube in channel, secure with
//       M2 screws or cable ties at 3 points
// =============================================
