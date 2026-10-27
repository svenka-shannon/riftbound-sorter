// =============================================
// Riftbound Card Sorter — Baseplate Tile
// =============================================
// Machine baseplate split into 3×3 grid of tiles
// Each tile: 190×180mm (fits P1S 256×256mm bed)
// Total assembled: 570×540mm
// Tiles connect via 3mm alignment pins
// Material: PLA, 0.2mm, 40% infill, 4 perimeters
// =============================================

tile_w    = 190;
tile_d    = 180;
tile_h    = 4;
pin_dia   = 3.0;   // male pin
hole_dia  = 3.2;   // female hole (clearance)
pin_h     = 6;

// M3 component mounting holes (grid pattern every 30mm)
mount_hole_d = 3.4;
mount_inset  = 15;
mount_step   = 30;

module baseplate_tile(
    pin_top    = false,   // pin on top edge
    pin_right  = false,   // pin on right edge
    hole_top   = false,   // hole on top edge
    hole_right = false    // hole on right edge
) {
    difference() {
        cube([tile_w, tile_d, tile_h]);

        // Component mounting holes grid
        for (x = [mount_inset : mount_step : tile_w - mount_inset])
            for (y = [mount_inset : mount_step : tile_d - mount_inset])
                translate([x, y, -0.1])
                    cylinder(d = mount_hole_d, h = tile_h + 0.2, $fn = 16);

        // Alignment holes
        if (hole_top)
            for (x = [30, tile_w - 30])
                translate([x, tile_d - 2, tile_h / 2])
                    rotate([90, 0, 0])
                    cylinder(d = hole_dia, h = 8, $fn = 16);

        if (hole_right)
            for (y = [30, tile_d - 30])
                translate([tile_w - 2, y, tile_h / 2])
                    rotate([0, 90, 0])
                    cylinder(d = hole_dia, h = 8, $fn = 16);
    }

    // Alignment pins
    if (pin_top)
        for (x = [30, tile_w - 30])
            translate([x, tile_d, tile_h / 2])
                rotate([90, 0, 0])
                cylinder(d = pin_dia, h = pin_h, $fn = 16);

    if (pin_right)
        for (y = [30, tile_d - 30])
            translate([tile_w, y, tile_h / 2])
                rotate([0, -90, 0])
                cylinder(d = pin_dia, h = pin_h, $fn = 16);
}

// Default: interior tile with pins on top + right
baseplate_tile(pin_top = true, pin_right = true);

// Edge tiles: set holes where adjacent tiles attach
// Corner tile: baseplate_tile(pin_top=false, pin_right=false)
