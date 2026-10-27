// =============================================
// Riftbound Card Sorter — Output Bin
// =============================================
// Print N bins (default 8 + 1 reject)
// Stacks in 2×4 grid within 2ft×2ft footprint
// Front label slot for printed card labels
// Material: PLA, 0.2mm layers, 20% infill (non-structural)
// =============================================

bin_inner_w  = 78;
bin_inner_d  = 125;
bin_inner_h  = 65;
wall         = 2.0;
label_h      = 15;   // front label slot height

outer_w = bin_inner_w + wall * 2;
outer_d = bin_inner_d + wall * 2;
outer_h = bin_inner_h + wall;

module output_bin() {
    difference() {
        cube([outer_w, outer_d, outer_h]);

        // Inner cavity (open top)
        translate([wall, wall, wall])
            cube([bin_inner_w, bin_inner_d, outer_h]);

        // Front label window
        translate([(outer_w - bin_inner_w) / 2, 0, wall])
            cube([bin_inner_w, wall + 0.1, label_h]);

        // Card entry slot (top back, angled) — optional
        // Cards fall in from top, no slot needed
    }
}

output_bin();

// =============================================
// PRINT ORIENTATION: open top facing up
// SUPPORTS: none needed
// PRINT 9× total (8 sort bins + 1 reject)
// EST: ~45 min per bin at 0.3mm draft quality
// =============================================
