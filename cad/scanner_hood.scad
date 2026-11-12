// =============================================
// Riftbound Card Sorter — Scanner Hood (+ asm_scan_station)
// =============================================
// Light-tight box over the scan zone. Straddles both conveyor rails, rests
// on the rail tops + the card guides' groove fills (z 99), skirts overlap
// the rails' outer faces by 5 mm. The camera (camera_bracket.scad) hangs
// above it with the lens through the roof port, so no room light reaches
// the card except through the two low card slots.
//
// Print 1×, roof down (part = "hood"). Black PLA/PETG, 0.2 mm, 3 walls,
// 15 % infill. No supports: walls lean ≤ 23° from vertical, everything else
// opens upward in print orientation.
//
// COORDINATES: machine frame (machine_frame.scad); scanner_hood() is already
// placed. asm_scan_station() places hood + guides + clips + camera bracket.
//
// ---------------------------------------------
// GEOMETRY (cam_x = frame_cam_x(), card face zc = 90.9, rail top 99)
//   Inner length along X 100 (cam_x ± 50), end walls 4 → outer cam_x ± 54
//   Inner width over the rails |Y| 45, skirts |Y| 48.3..51.3 down to z 94
//   Card slots: |Y| ≤ 34.0, ceiling zc + 4.0 = 94.9 (3.5 mm over a 0.5 mm
//     sleeved card), ceiling edge a full R2 bullnose. Beyond |Y| 34 the end
//     wall follows the card-guide profile with 0.4 mm clearance.
//   Walls taper from (±50, ±45) at z 99 to (±10, ±10) under the roof
//   Roof 2.5 mm, top at PCB front − 2.9 = z 195.0; lens port 15 × 15
//
// VIEW-CONE MATH (Pi Cam 3 standard, apex at the lens tip, h = height
// above the card face, lens tip at h = 100):
//   full FOV half-widths at h:  X (100 − h)·tan 33°   = 0.649·(100 − h)
//                               Y (100 − h)·tan 20.5° = 0.374·(100 − h)
//     at the card (h = 0): X ±64.9, Y ±37.4
//   needed region = card + 5 mm: X ±(44 + 5) = ±49
//                                Y ±(31.5 + 1.7 play + 5) = ±38.2 → capped by
//                                the sensor at ±37.4
//   needed half-widths at h:  X 49·(1 − h/100), Y 38.2·(1 − h/100)
//   hood interior at h (z = 90.9 + h), for z ≥ 99:
//     X 50 − 40·(z − 99)/93.5,  Y 45 − 35·(z − 99)/93.5
//     at z  99 (h  8.1): interior X ±50.0 / Y ±45.0 vs needed ±45.0 / ±35.1
//     at z 150 (h 59.1): interior X ±28.2 / Y ±25.9 vs needed ±20.0 / ±15.6
//     at z 190.9 (lens):  interior X ±10.7 / Y ±10.6 vs needed 0
//   below z 99 the interior is the rail channel |Y| < 45 and the end walls'
//   inner faces at X ±50, which the cone passes at ±47.0 at the slot ceiling
//   (h = 4). → No hood or guide surface is inside the card + 5 mm cone.
//   The roof is ABOVE the lens tip, so the "window" is just a port for the
//   lens body: the cone starts below the roof and the port never clips it.
//
// LIGHTING: the old ø52 LED-ring recess is dropped — a ring around the lens
//   puts a specular hotspot in the middle of glossy/foil cards. Instead the
//   two long inner side walls carry a 10 mm band (0.8 mm recess) at
//   h = 10..20 mm for 8 mm LED strip (≈ 88 mm per side, wires through the
//   ø4 holes). Mirror glare of a strip at (Y_L, h_L) lands on the card plane
//   at y = Y_L·100/(100 + h_L): strip centre (42.4, 15) → 36.9, strip top
//   edge (40.5, 20) → 33.8, both outside the card even at 1.7 mm play (33.2).
//   Strips must stay below h ≈ 21 for that to hold.
// ---------------------------------------------

use <machine_frame.scad>
use <card_guide.scad>
use <camera_bracket.scad>

/* [Export] */
part = "assembly";   // assembly (hood in place) | hood (print orientation) | station

$fn = 48;

cx        = frame_cam_x();
zc        = frame_card_z();
rail_in   = frame_rail_in();          // 45
rail_top  = guide_rail_top();         // 99
ch_hw     = guide_channel_hw();       // 33.2

// --- Shell ---
out_hx    = scan_hood_half_len();     // 54 (card_guide.scad keeps clips clear of it)
end_t     = 4;
in_hx     = out_hx - end_t;           // 50 → inner length 100
sk_in     = rail_in + 3 + 0.3;        // 48.3 (rail outer face 48)
sk_out    = sk_in + 3;                // 51.3
sk_bot    = rail_top - 5;             // 94 (5 mm overlap on the rail outer face)
z_lb      = rail_top + 2;             // top of the vertical lower band
roof_t    = 2.5;
roof_top  = zc + cam_pcb_front_rel() - 2.9;   // 195.0: M2 heads clear by ≥ 0.9
roof_bot  = roof_top - roof_t;
top_out   = 13;                       // outer half-size at the roof
top_in    = 10;                       // inner half-size under the roof
port      = 15;                       // lens-body port (lens holder ≤ ~12 mm)

// --- Card slots ---
slot_hw   = 34.0;                     // guide envelope meets the slot ceiling here
slot_top  = zc + 4.0;                 // 94.9
lip_r     = end_t / 2;                // full bullnose on the slot ceiling

// --- LED bands ---
led_h     = [10, 20];                 // above the card face
led_d     = 0.8;
led_hx    = 44;
wire_d    = 4;

// --- View cone check values ---
lens_z    = zc + cam_lens_h();
need_hx   = 88 / 2 + 5;
need_hy   = min(63 / 2 + (ch_hw - 63 / 2) + 5, cam_lens_h() * tan(20.5));
function need_x(z) = need_hx * (lens_z - z) / (lens_z - zc);
function need_y(z) = need_hy * (lens_z - z) / (lens_z - zc);
function cav_x(z)  = in_hx - (in_hx - top_in) * (z - rail_top) / (roof_bot - rail_top);
function cav_y(z)  = rail_in - (rail_in - top_in) * (z - rail_top) / (roof_bot - rail_top);

echo(str("HOOD: X ", cx - out_hx, "..", cx + out_hx, " (inner ", 2 * in_hx, "), roof top z ", roof_top,
         ", slot |Y|≤", slot_hw, " ceiling z ", slot_top, " (", slot_top - zc, " over card face)"));
echo(str("HOOD VIEW CONE: needed card+5 at card plane X ±", need_hx, " Y ±", need_hy,
         "; at z99 cavity ±", cav_x(99), "/±", cav_y(99), " vs ±", need_x(99), "/±", need_y(99),
         "; at slot ceiling needed X ±", need_x(slot_top), " vs end wall ", in_hx));
for (z = [rail_top : 10 : roof_bot])
    assert(cav_x(z) >= need_x(z) + 3 && cav_y(z) >= need_y(z) + 3, str("hood wall in view cone at z ", z));
assert(need_x(slot_top) + 2 < in_hx, "end wall in view cone");

module slab(x0, x1, y, z) translate([x0, -y, z]) cube([x1 - x0, 2 * y, 0.01]);
module slab_c(hx, hy, z)  translate([cx - hx, -hy, z]) cube([2 * hx, 2 * hy, 0.01]);

module hood_outer() {
    // vertical lower band: skirts + rest-on-rail band
    translate([cx - out_hx, -sk_out, sk_bot]) cube([2 * out_hx, 2 * sk_out, z_lb - sk_bot]);
    // end walls down into the rail channel (trimmed by the keep-out)
    for (x = [cx - out_hx, cx + in_hx])
        translate([x, -sk_in, zc - 0.4]) cube([end_t, 2 * sk_in, z_lb - zc + 0.4]);
    // tapered body
    hull() {
        slab(cx - out_hx, cx + out_hx, sk_out, z_lb - 0.01);
        slab_c(top_out, top_out, roof_top - 0.01);
    }
}

module hood_cavity() {
    // rail channel + rails below the rest plane
    translate([cx - in_hx, -sk_in, zc - 20]) cube([2 * in_hx, 2 * sk_in, rail_top - zc + 20]);
    // tapered interior
    hull() {
        slab_c(in_hx, rail_in, rail_top - 0.01);
        slab_c(top_in, top_in, roof_bot);
    }
    // lens port
    translate([cx - port / 2, -port / 2, roof_bot - 1]) cube([port, port, roof_t + 2]);
    // LED strip bands on the two long side walls
    intersection() {
        hull() {
            slab_c(in_hx + led_d, rail_in + led_d, rail_top - 0.01);
            slab_c(top_in + led_d, top_in + led_d, roof_bot);
        }
        translate([cx - led_hx, -100, zc + led_h[0]]) cube([2 * led_hx, 200, led_h[1] - led_h[0]]);
        union() for (s = [-1, 1]) translate([cx - 100, s > 0 ? 25 : -125, 0]) cube([200, 100, 300]);
    }
    // LED wire holes, one per side at the downstream end of the band
    translate([cx + led_hx - 4, 0, zc + (led_h[0] + led_h[1]) / 2])
        rotate([90, 0, 0]) cylinder(d = wire_d, h = 2 * sk_out + 10, center = true);
}

// Everything the hood must stay clear of below the rest plane
module hood_keepout() {
    xa = cx - out_hx - 1; xb = cx + out_hx + 1;
    card_guide_envelope(xa, xb, 0.4);
    // rail walls + groove fills (rest plane z 99 stays)
    for (s = [-1, 1])
        translate([xa, s > 0 ? rail_in - 0.4 : -sk_in, zc - 30]) cube([xb - xa, sk_in - rail_in + 0.4, rail_top - zc + 30]);
    // card slots with an R2 bullnose ceiling at both end walls
    for (x = [cx - out_hx, cx + in_hx])
        difference() {
            translate([x - 1, -slot_hw, zc - 30]) cube([end_t + 2, 2 * slot_hw, slot_top + lip_r - zc + 30]);
            translate([x + end_t / 2, 0, slot_top + lip_r]) rotate([90, 0, 0])
                cylinder(r = lip_r, h = 2 * slot_hw + 2, center = true);
        }
    // belts / bed / rollers: nothing below the guide underside inside the rails
    translate([xa, -rail_in, zc - 30]) cube([xb - xa, 2 * rail_in, 30 - 0.5]);
}

module scanner_hood()
    difference() {
        hood_outer();
        hood_cavity();
        hood_keepout();
    }

// Print orientation: roof on the bed
module scanner_hood_print() translate([0, 0, roof_top]) rotate([180, 0, 0]) translate([-cx, 0, 0]) scanner_hood();

// ── Scan station: hood + guides + clips + camera bracket, machine coords ──
module asm_scan_station() {
    scanner_hood();
    card_guides();
    camera_bracket_placed();
    %camera_ghost_placed();
}

if (part == "assembly") scanner_hood();
if (part == "hood")     scanner_hood_print();
if (part == "station")  asm_scan_station();

// =============================================
// INSTALL: guides first, then lower the hood straight down over the rails
//   (skirts outside, end walls straddling the guides), then lower the camera
//   bracket so the lens drops into the roof port. To lift the hood, remove
//   the bracket (2 M3) first. Jams: reverse the belt; cards leave through
//   either slot.
// LIGHT: the only openings are the two 68 × 4 mm card slots (plus 0.4 mm
//   gaps around the guides) and the 2.9 mm gap between roof and camera PCB;
//   a 2-3 mm black foam ring around the lens on the roof closes the latter.
// =============================================
