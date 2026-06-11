// Lio v0.1 — M6 nut trap + M3 heat-set insert + M3 screw clearance test strip
// Units: millimeters
//
// Purpose:
// 1. Test M6 nut-trap hex pocket across-flat sizes: 10.2, 10.4, 10.6, 10.8 mm.
// 2. Test M3 heat-set insert hole diameters: 4.0, 4.2, 4.4, 4.6 mm.
// 3. Test M3 screw clearance hole diameters: 3.2, 3.4, 3.6, 3.8 mm.
//
// Print orientation:
// - Flat on bed.
//
// Material:
// - PETG preferred if final Lio parts are PETG.
//
// After printing:
// - Press M6 nuts/coupling nuts into the hex pockets.
// - Thread M6 rod through center holes.
// - Heat-set M3 inserts into insert holes.
// - Test M3 screws through clearance holes.
// - Pick the tightest sizes that work without cracking, bulging, or rattling.

$fn = 96;

// ----------------------
// Global dimensions
// ----------------------

plate_w = 165;
plate_d = 82;
plate_t = 8;

corner_r = 3;

// Test values
m6_af_values = [10.2, 10.4, 10.6, 10.8];      // M6 nut trap across flats
m3_insert_hole_values = [4.0, 4.2, 4.4, 4.6]; // heat-set insert bore tests
m3_clearance_values = [3.2, 3.4, 3.6, 3.8];   // screw clearance tests

// M6 dimensions
m6_rod_clearance = 7.0;     // through-hole for M6 threaded rod
m6_hex_depth = 4.2;         // depth of hex pocket from top surface
m6_test_block_spacing = 34;

// M3 insert test
m3_insert_depth = plate_t + 2;     // through hole for test; insert depth decided physically
m3_insert_spacing = 24;

// M3 clearance test
m3_clearance_spacing = 24;

// Label settings
label_size = 4.2;
small_label_size = 3.5;
label_depth = 0.6;

// Row Y positions
m6_row_y = 22;
insert_row_y = -12;
clearance_row_y = -32;

// X layout
m6_start_x = -51;
insert_start_x = -36;
clearance_start_x = -36;

// ----------------------
// Helper modules
// ----------------------

// Rounded rectangle base using hull of cylinders
module rounded_plate(w, d, h, r) {
    hull() {
        for (x = [-w/2 + r, w/2 - r])
        for (y = [-d/2 + r, d/2 - r])
            translate([x, y, 0])
                cylinder(r = r, h = h);
    }
}

// Hex prism specified by across-flats dimension.
// OpenSCAD cylinder with $fn=6 uses a circumscribed diameter.
// For a true across-flat value AF, diameter = AF / cos(30).
module hex_pocket_by_af(af, h) {
    cylinder(d = af / cos(30), h = h, $fn = 6);
}

// Raised text label
module raised_label(txt, x, y, z, size = label_size) {
    translate([x, y, z])
        linear_extrude(height = label_depth)
            text(txt,
                 size = size,
                 font = "Liberation Sans:style=Bold",
                 halign = "center",
                 valign = "center");
}

// ----------------------
// Main model
// ----------------------

difference() {
    // Main solid plate
    rounded_plate(plate_w, plate_d, plate_t, corner_r);

    // ----------------------
    // M6 nut trap tests
    // ----------------------
    for (i = [0 : len(m6_af_values) - 1]) {
        x = m6_start_x + i * m6_test_block_spacing;
        af = m6_af_values[i];

        // M6 threaded rod through-hole
        translate([x, m6_row_y, -1])
            cylinder(d = m6_rod_clearance, h = plate_t + 2);

        // Hex pocket from top
        translate([x, m6_row_y, plate_t - m6_hex_depth])
            hex_pocket_by_af(af, m6_hex_depth + 1);
    }

    // ----------------------
    // M3 heat-set insert bore tests
    // ----------------------
    for (i = [0 : len(m3_insert_hole_values) - 1]) {
        x = insert_start_x + i * m3_insert_spacing;
        d = m3_insert_hole_values[i];

        translate([x, insert_row_y, -1])
            cylinder(d = d, h = m3_insert_depth);
    }

    // ----------------------
    // M3 screw clearance tests
    // ----------------------
    for (i = [0 : len(m3_clearance_values) - 1]) {
        x = clearance_start_x + i * m3_clearance_spacing;
        d = m3_clearance_values[i];

        translate([x, clearance_row_y, -1])
            cylinder(d = d, h = plate_t + 2);
    }

    // Optional hanging/storage hole
    translate([plate_w/2 - 12, plate_d/2 - 12, -1])
        cylinder(d = 5, h = plate_t + 2);
}

// ----------------------
// Raised labels on top
// ----------------------

// Title
raised_label("LIO FIT TEST: M6 NUT / M3 INSERT / M3 CLEARANCE",
             0, plate_d/2 - 8, plate_t, 3.4);

// M6 row label
raised_label("M6 NUT TRAP AF",
             -plate_w/2 + 33, m6_row_y, plate_t, 3.2);

// M6 individual labels
for (i = [0 : len(m6_af_values) - 1]) {
    x = m6_start_x + i * m6_test_block_spacing;
    af = m6_af_values[i];

    raised_label(str(af, " AF"), x, m6_row_y - 15, plate_t, small_label_size);
}

// M3 insert row label
raised_label("M3 INSERT HOLES",
             -plate_w/2 + 35, insert_row_y, plate_t, 3.2);

// M3 insert individual labels
for (i = [0 : len(m3_insert_hole_values) - 1]) {
    x = insert_start_x + i * m3_insert_spacing;
    d = m3_insert_hole_values[i];

    raised_label(str(d, "mm"), x, insert_row_y + 12, plate_t, small_label_size);
}

// M3 clearance row label
raised_label("M3 SCREW CLEARANCE",
             -plate_w/2 + 38, clearance_row_y, plate_t, 3.2);

// M3 clearance individual labels
for (i = [0 : len(m3_clearance_values) - 1]) {
    x = clearance_start_x + i * m3_clearance_spacing;
    d = m3_clearance_values[i];

    raised_label(str(d, "mm"), x, clearance_row_y + 12, plate_t, small_label_size);
}