// Lio v0.1 — LM8UU bearing bore + 8 mm rod spacing test block
// Units: millimeters
//
// Purpose:
// 1. Test LM8UU bearing bore fit with 15.0, 15.2, 15.4, 15.6 mm horizontal tunnels.
// 2. Test two 8 mm guide rods through vertical 8.5 mm holes spaced 90 mm apart.
// 3. Print flat on the bed.
//
// After printing:
// - Try sliding/pressing an LM8UU bearing into each horizontal tunnel.
// - The best tunnel is snug but not destructive.
// - Slide your two 8 mm rods through the vertical holes to check spacing/alignment.

$fn = 96;

// ----------------------
// Main parameters
// ----------------------

// Bearing test block parameters
bearing_hole_diameters = [15.0, 15.2, 15.4, 15.6];

block_w = 30;          // width of each bearing test block along X
block_d = 34;          // depth along Y; must exceed LM8UU length enough to grip/check fit
block_h = 26;          // height along Z; must exceed bearing OD
block_gap = 6;         // gap between bearing blocks

bearing_axis_z = block_h / 2;
bearing_axis_y = 0;

// Base plate parameters
base_margin_x = 8;
base_margin_y = 8;
base_t = 4;

// Rod spacing bridge
rod_spacing = 90;      // center-to-center spacing between 8 mm guide rods
rod_hole_d = 8.5;      // clearance for 8 mm rods; change to 8.4 or 8.6 if needed
rod_bridge_w = 120;
rod_bridge_d = 28;
rod_bridge_h = 10;

// Text label settings
label_size = 5;
label_depth = 0.7;

// Derived dimensions
num_blocks = len(bearing_hole_diameters);
total_blocks_w = num_blocks * block_w + (num_blocks - 1) * block_gap;
base_w = max(total_blocks_w + 2 * base_margin_x, rod_bridge_w + 2 * base_margin_x);
base_d = block_d + rod_bridge_d + 3 * base_margin_y;

// Place bearing blocks toward front, rod bridge toward back
bearing_row_y = -base_d/2 + base_margin_y + block_d/2;
rod_bridge_y  =  base_d/2 - base_margin_y - rod_bridge_d/2;

// ----------------------
// Helper modules
// ----------------------

module bearing_test_block(hole_d, label_text) {
    difference() {
        // Solid block
        cube([block_w, block_d, block_h], center = true);

        // Horizontal bearing tunnel through Y axis
        translate([0, 0, bearing_axis_z - block_h/2])
        rotate([90, 0, 0])
            cylinder(d = hole_d, h = block_d + 4, center = true);

        // Small bottom relief so bridging is not too ugly
        // Optional; comment out if you want a fully round tunnel.
        // translate([0, 0, 0])
        // cube([hole_d * 0.65, block_d + 5, hole_d * 0.25], center = true);
    }

    // Raised label on top
    translate([-block_w/2 + 3, -block_d/2 + 3, block_h/2])
        linear_extrude(height = label_depth)
            text(label_text, size = label_size, font = "Liberation Sans:style=Bold");
}

module rod_spacing_bridge() {
    difference() {
        cube([rod_bridge_w, rod_bridge_d, rod_bridge_h], center = true);

        // Two vertical holes for 8 mm guide rods
        for (x = [-rod_spacing/2, rod_spacing/2]) {
            translate([x, 0, -rod_bridge_h/2 - 1])
                cylinder(d = rod_hole_d, h = rod_bridge_h + 2);
        }
    }

    // Raised label
    translate([-rod_bridge_w/2 + 5, -rod_bridge_d/2 + 4, rod_bridge_h/2])
        linear_extrude(height = label_depth)
            text(str("Rod spacing ", rod_spacing, "mm / holes ", rod_hole_d, "mm"),
                 size = 4.2,
                 font = "Liberation Sans:style=Bold");
}

// ----------------------
// Full combined part
// ----------------------

union() {
    // Base plate connecting all features
    translate([0, 0, base_t/2])
        cube([base_w, base_d, base_t], center = true);

    // Four bearing test blocks
    for (i = [0 : num_blocks - 1]) {
        x_pos = -total_blocks_w/2 + block_w/2 + i * (block_w + block_gap);
        hole_d = bearing_hole_diameters[i];

        translate([x_pos, bearing_row_y, base_t + block_h/2])
            bearing_test_block(hole_d, str(hole_d, "mm"));
    }

    // Rod spacing bridge
    translate([0, rod_bridge_y, base_t + rod_bridge_h/2])
        rod_spacing_bridge();
}