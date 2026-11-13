// Visual-only hardware for the v3 assembly video (render_v2/w_*.scad). Not printed.
// Screws are drawn with the origin at the underside of the head (the bearing face)
// and the tip along `dir` (default straight down). Lengths are nominal (mm).

// rotate so that local -Z points along v
module point_tip(v = [0, 0, -1]) {
    n = norm(v); u = v / n;
    if (u[2] < -0.9999) children();
    else if (u[2] > 0.9999) rotate([180, 0, 0]) children();
    else rotate(a = acos(-u[2]), v = cross([0, 0, -1], u)) children();
}

// socket head cap screw: head Ø5.5 × 3 above the origin, shank down
module shcs(L, d = 3, hd = 5.5, hh = 3) {
    cylinder(d = hd, h = hh, $fn = 20);
    translate([0, 0, -L]) cylinder(d = d, h = L + 0.01, $fn = 12);
}
// button head (ISO 7380)
module bhcs(L, d = 3, hd = 5.7, hh = 1.65) {
    cylinder(d1 = hd, d2 = hd * 0.75, h = hh, $fn = 20);
    translate([0, 0, -L]) cylinder(d = d, h = L + 0.01, $fn = 12);
}
// countersunk (ISO 10642): head top at the origin, cone below it
module csk(L, d = 3, hd = 6) {
    translate([0, 0, -(hd - d) / 2]) cylinder(d1 = d, d2 = hd, h = (hd - d) / 2, $fn = 20);
    translate([0, 0, -L]) cylinder(d = d, h = L, $fn = 12);
}
// set screw (no head), top at the origin
module setscrew(L, d = 3) translate([0, 0, -L]) cylinder(d = d, h = L, $fn = 12);
module hexnut(d = 3, af = 5.5, h = 2.4) difference() {
    cylinder(d = af / cos(30), h = h, $fn = 6);
    translate([0, 0, -1]) cylinder(d = d, h = h + 2, $fn = 12);
}
module washer(d = 3.2, od = 7, t = 0.5) difference() { cylinder(d = od, h = t, $fn = 24); translate([0, 0, -1]) cylinder(d = d, h = t + 2, $fn = 12); }

// place a screw at p with its tip along dir
module at_screw(p, dir = [0, 0, -1]) translate(p) point_tip(dir) children();

// M3 four-prong tee-nut, flange on the board underside at z, barrel up into the board
module teenut(p, z) translate([p[0], p[1], z]) {
    translate([0, 0, -0.9]) difference() { cylinder(d = 13, h = 0.9, $fn = 32); translate([0, 0, -1]) cylinder(d = 3, h = 3, $fn = 12); }
    difference() { cylinder(d = 4.5, h = 5, $fn = 20); translate([0, 0, -1]) cylinder(d = 3, h = 7, $fn = 12); }
    for (a = [45 : 90 : 315]) rotate(a) translate([5.2, -0.7, 0]) cube([1.2, 1.4, 3]);
}

// cable / tube as a hull chain of spheres
module chain(pts, d = 4) for (i = [0 : len(pts) - 2])
    hull() for (p = [pts[i], pts[i + 1]]) translate(p) sphere(d = d, $fn = 12);
