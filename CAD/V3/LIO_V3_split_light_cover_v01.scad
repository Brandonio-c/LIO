// LIO V3 — two-piece clamp-on light cover for the optical head (v01)
// Units: millimetres. OpenSCAD 2021.01 or later, no libraries.
//
// WHAT IT IS
//   An opaque cap that drops over the top of the optical deck and covers the
//   LED seats, LED leads and detector board, so no room light reaches the
//   detectors through the unsealed LED tops. It is split in two halves so it
//   can be closed AROUND the existing wiring: lay the wire bundle(s) in the
//   half-ports on one half, bring the other half up, bolt the two clamp tabs.
//   It replaces putty on the LED tops; it does not replace the chamber seal.
//
//   - lap joint along both split lines (no straight-through light gap)
//   - skirt that overlaps the outside edge of the deck (light trap)
//   - notches for the deck's four M4 ears, so the skirt can drop over them
//   - cable ports on the split lines, half in each piece (pack with black foam)
//   - two M3 clamp tabs, one per split line, with a nut trap on one half
//
// DEFAULTS come from CAD/V3/LIO_V3_R3_Print_Set/LIO_V3_R3_master.scad
// (head_body_d 122, deck_t 10, ears Ø16 at r 66 on 45/135/225/315°, lead
// screws at x = ±74). THE BUILT RIG MAY DIFFER: measure and edit the
// "MEASURE" values before printing. Print a 10 mm tall test ring first
// (part = "fit_ring") to check the fit on the deck.
//
// PRINT: black PETG or ABS (not PLA in a warm enclosure), 0.2 mm layers,
// 4+ walls, 20 % infill, roof DOWN on the bed (part = "print_layout" does
// this), no supports needed. Light-proof check: hold a phone torch against
// a printed half in a dark room; if it glows through, add walls.
//
// part = "assembly" | "half_a" | "half_b" | "print_layout" | "fit_ring"
part = "print_layout";

/* [MEASURE: optical deck] */
deck_d        = 122;   // outer diameter of the deck body (not the ears)
deck_t        = 10;    // deck thickness: the skirt must be shorter than this
ear_angles    = [45, 135, 225, 315];
ear_r         = 66;    // radius of the M4 ear centres
ear_d         = 16;    // ear diameter
// Fixed hardware the cover must clear as the head travels: [x, y, diameter]
keep_out      = [[74, 0, 8], [-74, 0, 8],                 // lead screws
                 [78, 55, 8], [-78, 55, 8], [78, -55, 8], [-78, -55, 8]]; // guide rods

/* [MEASURE: what has to fit under the cover] */
inner_h       = 40;    // headroom above the deck top: tallest wire loop / board + 5 mm
port_h        = 12;    // cable port height
// Cable ports sit on the two split lines (split_angle + 90 and + 270), so the
// wires can be laid in before the halves close. Set a port's width to 0 to drop it.
port_widths   = [16, 16];
port_top_gap  = 4;     // ports sit this far below the roof underside

/* [Cover] */
radial_clear  = 0.4;   // gap between deck edge and skirt (each side)
wall          = 2.8;   // side wall: >= 2.4 mm in black filament is opaque
roof_t        = 3.0;
skirt_drop    = 6;     // overlap down the deck edge (0 = sits on the deck top)
split_angle   = 0;     // 0: halves meet on the 90° and 270° lines (away from the screws)
lap_w         = 6;     // lap-joint overlap past the split line
lap_clear     = 0.3;   // fit allowance in the lap joint
ear_clear     = 1.0;   // extra width round each ear notch

/* [Clamp tabs: M3] */
tab_t         = 5;     // tab thickness per half
tab_len       = 12;    // how far a tab sticks out past the wall
tab_h         = 14;
bolt_d        = 3.4;
nut_af        = 5.8;   // M3 nut across flats (+ clearance)
nut_h         = 2.6;

$fn = 160;
eps = 0.02;

id      = deck_d + 2 * radial_clear;
od      = id + 2 * wall;
z_bot   = -skirt_drop;            // z = 0 is the deck top surface
z_roof  = inner_h;                // roof underside
z_top   = inner_h + roof_t;
port_z1 = z_roof - port_top_gap;
port_z0 = port_z1 - port_h;
tab_z0  = z_bot;
tab_z1  = z_bot + tab_h;

// ---------- sanity checks ----------
assert(skirt_drop < deck_t, "skirt_drop must be less than deck_t");
assert(tab_z1 + 2 <= port_z0, "clamp tab overlaps a cable port: raise inner_h or shrink tab_h");
for (k = keep_out)
    assert(norm([k[0], k[1]]) - k[2] / 2 - od / 2 >= 3,
           str("cover wall within 3 mm of fixed hardware at ", k));
// Tabs sit on the split lines at split_angle + 90 / + 270.
for (s = [90, 270]) for (k = keep_out) let(a = split_angle + s,
        tip = [(od / 2 + tab_len) * cos(a), (od / 2 + tab_len) * sin(a)],
        root = [(od / 2) * cos(a), (od / 2) * sin(a)])
    assert(min(norm(tip - [k[0], k[1]]), norm(root - [k[0], k[1]])) - k[2] / 2 - tab_t >= 3,
           str("clamp tab at ", a, "° within 3 mm of fixed hardware at ", k));

// ---------- helpers ----------
module tube(d_out, d_in, z0, z1) {
    translate([0, 0, z0]) difference() {
        cylinder(d = d_out, h = z1 - z0);
        translate([0, 0, -eps]) cylinder(d = d_in, h = z1 - z0 + 2 * eps);
    }
}
// Half-space on the +x side of the split plane (rotated by split_angle).
module side_a(extra = 0) {
    rotate([0, 0, split_angle]) translate([-extra, -200, -200]) cube([400, 400, 400]);
}
module side_b() {
    rotate([0, 0, split_angle]) translate([-400, -200, -200]) cube([400, 400, 400]);
}
// Slab just on the B side of the split plane, width w.
module lap_slab(w) {
    rotate([0, 0, split_angle]) translate([-w, -200, -200]) cube([w, 400, 400]);
}

// ---------- the whole cover before splitting ----------
module shell() {
    union() {
        tube(od, id, z_bot, z_roof + eps);
        translate([0, 0, z_roof]) cylinder(d = od, h = roof_t);
        for (s = [90, 270]) rotate([0, 0, split_angle + s])
            translate([od / 2 - wall / 2, -tab_t, tab_z0]) cube([tab_len + wall / 2, 2 * tab_t, tab_h]);
    }
}
// Inner half of the wall and roof: the tongue that half A extends past the split.
module lip_zone(grow = 0) {
    union() {
        tube(id + wall + 2 * grow, id - 2, z_bot - 1, z_roof + roof_t / 2 + grow);
        translate([0, 0, z_roof - eps]) cylinder(d = id + wall + 2 * grow, h = roof_t / 2 + grow + eps);
    }
}
module cutouts() {
    // Ear notches through the skirt (only up to the deck top).
    for (a = ear_angles) rotate([0, 0, a])
        hull() for (r = [id / 2 - 2, od / 2 + tab_len + 2])
            translate([r, 0, z_bot - 1]) cylinder(d = ear_d + 2 * ear_clear, h = skirt_drop + 1 + 0.3, $fn = 48);
    // Cable ports on the split lines.
    for (i = [0, 1]) if (port_widths[i] > 0) rotate([0, 0, split_angle + 90 + 180 * i])
        translate([id / 2 - 2, -port_widths[i] / 2, port_z0]) cube([wall + tab_len + 4, port_widths[i], port_h]);
    // Clamp bolts (tangential, across the split) and a nut trap on the B side.
    for (s = [90, 270]) rotate([0, 0, split_angle + s])
        translate([od / 2 + tab_len / 2 + 1, 0, (tab_z0 + tab_z1) / 2]) rotate([90, 0, 0]) {
            translate([0, 0, -tab_t - 1]) cylinder(d = bolt_d, h = 2 * tab_t + 2, $fn = 32);
            // hex nut trap on one half; the bolt head goes on the other
            translate([0, 0, tab_t - nut_h]) cylinder(d = nut_af / cos(30), h = nut_h + 1, $fn = 6);
        }
}

module half_a() {
    difference() {
        union() {
            intersection() { shell(); side_a(); }
            intersection() { shell(); lip_zone(); lap_slab(lap_w); }
        }
        cutouts();
    }
}
module half_b() {
    difference() {
        intersection() { shell(); side_b(); }
        intersection() { lip_zone(lap_clear); lap_slab(lap_w + lap_clear); }
        cutouts();
    }
}

// ---------- reference deck (not printed) ----------
module deck_ref() {
    color([0.6, 0.6, 0.65, 0.5]) translate([0, 0, -deck_t]) union() {
        cylinder(d = deck_d, h = deck_t);
        for (a = ear_angles) rotate([0, 0, a]) translate([ear_r, 0, 0]) cylinder(d = ear_d, h = deck_t);
    }
    for (k = keep_out) color([0.3, 0.3, 0.3]) translate([k[0], k[1], -30]) cylinder(d = k[2], h = 100);
}

if (part == "assembly") {
    deck_ref();
    color([0.15, 0.15, 0.15]) half_a();
    color([0.25, 0.25, 0.28]) half_b();
} else if (part == "half_a") {
    half_a();
} else if (part == "half_b") {
    half_b();
} else if (part == "fit_ring") {
    // Bottom 12 mm of both halves (skirt, ear notches, clamp tabs), printed
    // skirt-down, to check the fit on the deck around the wires before the full print.
    gap = lap_w + 6;
    for (h = [0, 1]) translate([h == 0 ? gap : -gap, 0, -z_bot]) rotate([0, 0, -split_angle])
        intersection() {
            if (h == 0) half_a(); else half_b();
            translate([-200, -200, z_bot]) cube([400, 400, 12]);
        }
} else {
    // print_layout: both halves roof-down, side by side.
    gap = lap_w + 6;
    translate([ gap, 0, z_top]) rotate([180, 0, 0]) rotate([0, 0, -split_angle]) half_a();
    translate([-gap, 0, z_top]) rotate([180, 0, 0]) rotate([0, 0, -split_angle]) half_b();
}
