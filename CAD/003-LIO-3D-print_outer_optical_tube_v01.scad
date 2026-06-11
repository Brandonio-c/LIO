// Lio v0.1 — Fixed Outer Optical Tube with Top/Bottom Flanges
// Units: millimeters
//
// This part integrates:
// - outer optical tube
// - top flange
// - bottom flange
// - M3 insert bosses / mounting holes
// - alignment key for removable inner sleeve
// - internal baffle-retaining ledges
// - external wire-routing groove
//
// Print orientation:
// - vertical, open cylinder upward
//
// Suggested material:
// - black PETG
//
// Print settings:
// - 0.20 mm layer height
// - 4 walls
// - 25–35% infill
// - brim on
// - supports off if possible

$fn = 128;
eps = 0.05;

// ----------------------------
// Main tube dimensions
// ----------------------------

tube_od = 80;          // main tube outside diameter
tube_id = 60;          // clear inner bore
tube_h  = 100;         // total height

wall_thickness = (tube_od - tube_id) / 2;

// ----------------------------
// Flange dimensions
// ----------------------------

flange_od = 92;        // top/bottom flange outside diameter
flange_t  = 6;         // flange thickness

// ----------------------------
// M3 insert boss / mounting pattern
// ----------------------------

m3_insert_d = 4.3;     // CHANGE after your M3 heat-set insert test
m3_bolt_circle_d = 74; // mounting hole bolt circle
boss_d = 14;           // local boss/lug diameter
boss_center_r = m3_bolt_circle_d / 2;

// If your insert test says 4.2 or 4.4 is better,
// change m3_insert_d here before printing the final version.

// ----------------------------
// Internal baffle ledges
// ----------------------------

baffle_ledge_z = [18, 48, 78];  // heights of internal ledges
baffle_ledge_h = 1.4;           // vertical thickness of ledge
baffle_ledge_id = 54;           // ledge opening diameter

// The ledge is a small inward shelf:
// tube inner bore = 60 mm
// ledge opening = 54 mm
// so ledge projects inward by 3 mm radially.

// ----------------------------
// Inner sleeve alignment key
// ----------------------------

key_width = 4.0;       // tangential width of key
key_depth = 2.0;       // inward protrusion into bore
key_z0 = flange_t + 4;
key_z1 = tube_h - flange_t - 4;

// This key is designed to match the split seam/notch
// in the removable flocked inner sleeve.

// ----------------------------
// External wire-routing groove
// ----------------------------

wire_groove_w = 9;       // groove width along X
wire_groove_depth = 3;   // depth into outer tube wall
wire_groove_z0 = 8;
wire_groove_z1 = tube_h - 8;

// Groove is cut into the outside wall only.
// It should NOT reach the inner bore.

// ----------------------------
// Helper modules
// ----------------------------

module ring(od, id, h) {
    difference() {
        cylinder(d = od, h = h);
        translate([0, 0, -eps])
            cylinder(d = id, h = h + 2 * eps);
    }
}

module flange_with_bosses(zpos) {
    translate([0, 0, zpos]) {
        union() {
            // main flange ring
            cylinder(d = flange_od, h = flange_t);

            // four local bosses/lugs around flange
            for (a = [0, 90, 180, 270]) {
                rotate([0, 0, a])
                    translate([boss_center_r, 0, 0])
                        cylinder(d = boss_d, h = flange_t);
            }
        }
    }
}

module m3_insert_holes_top() {
    // Holes through the top flange/bosses.
    // Heat-set inserts can be pressed/melted into these from the top face.
    for (a = [0, 90, 180, 270]) {
        rotate([0, 0, a])
            translate([boss_center_r, 0, tube_h - flange_t - eps])
                cylinder(d = m3_insert_d, h = flange_t + 2 * eps);
    }
}

module m3_insert_holes_bottom() {
    // Holes through the bottom flange/bosses.
    // These are accessible from the bottom face after printing.
    for (a = [0, 90, 180, 270]) {
        rotate([0, 0, a])
            translate([boss_center_r, 0, -eps])
                cylinder(d = m3_insert_d, h = flange_t + 2 * eps);
    }
}

module external_wire_groove() {
    // Vertical shallow outside groove on +Y side.
    // Used for routing wires without cutting into the optical bore.
    groove_h = wire_groove_z1 - wire_groove_z0;

    translate([
        0,
        tube_od/2 - wire_groove_depth/2 + eps,
        wire_groove_z0 + groove_h/2
    ])
        cube([wire_groove_w, wire_groove_depth + 2 * eps, groove_h], center = true);
}

module internal_alignment_key() {
    // Small inward rib/key on inner bore wall.
    // Sleeve seam/notch should align with this.
    key_h = key_z1 - key_z0;

    translate([
        tube_id/2 - key_depth/2,
        0,
        key_z0 + key_h/2
    ])
        cube([key_depth, key_width, key_h], center = true);
}

module internal_baffle_ledge(zpos) {
    // Small internal annular shelf to retain loose baffle rings.
    translate([0, 0, zpos])
        ring(tube_id, baffle_ledge_id, baffle_ledge_h);
}

// ----------------------------
// Main model
// ----------------------------

union() {

    // Main structural shell with flanges, bosses, bore, mounting holes, and groove.
    difference() {

        union() {
            // Main vertical tube body
            cylinder(d = tube_od, h = tube_h);

            // Bottom flange and top flange
            flange_with_bosses(0);
            flange_with_bosses(tube_h - flange_t);
        }

        // Main optical bore through full tube
        translate([0, 0, -1])
            cylinder(d = tube_id, h = tube_h + 2);

        // M3 insert holes
        m3_insert_holes_top();
        m3_insert_holes_bottom();

        // Outside wire-routing groove
        external_wire_groove();
    }

    // Internal alignment key for removable sleeve
    internal_alignment_key();

    // Internal baffle-retaining ledges
    for (z = baffle_ledge_z) {
        internal_baffle_ledge(z);
    }
}