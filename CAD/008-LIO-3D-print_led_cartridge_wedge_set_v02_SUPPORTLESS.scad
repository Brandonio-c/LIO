// Lio v0.2 — SUPPORTLESS LED Cartridge / Wedge Set
// Units: millimeters
//
// FIXES FROM v01:
// - Removed raised text labels.
// - Removed horizontal retention holes.
// - Replaced closed angled LED bores with open-top angled cradles.
// - Added simple top notches for identifying cartridge type.
// - Designed to slice with supports OFF.
//
// This print generates four cartridge variants:
// 1. 5 mm through-hole LED open-cradle cartridge
// 2. 3 mm through-hole LED open-cradle cartridge
// 3. SMD / flat LED carrier cartridge
// 4. TO-can / metal-can open-cradle cartridge
//
// Coordinate convention:
// - X axis = radial direction inside LED ring
//      +X = outside of ring / wire side
//      -X = inside of ring / sample side
// - Y axis = tangential width
// - Z axis = vertical
//
// These fit the Lio LED ring v02 open-top cartridge pockets.
// The cartridges are meant to be removable and adjusted/iterated.
//
// Print orientation:
// - Flat on bed.
// - Supports OFF.
//
// Material:
// - PETG preferred.

$fn = 72;
eps = 0.05;

// ---------------------------------------------------------
// Cartridge slot-fit dimensions
// ---------------------------------------------------------

body_len = 19.5;       // radial length inside ring slot
body_w   = 8.8;        // tangential width; below ~9.8 mm ring slot width
body_h   = 9.4;        // vertical height; below ~10.5 mm slot height

hood_len = 3.0;        // inner hood extension toward sample
hood_h   = 5.0;
hood_w   = body_w;

total_len = body_len + hood_len;

// Layout spacing for printing all four cartridges
part_spacing = 34;

// ---------------------------------------------------------
// Open cradle geometry
// ---------------------------------------------------------

// Cradle angle: 45 degrees downward/inward.
// The cradle is open from the top, so there is no enclosed roof.
cradle_angle_y = -45;

// Long enough to cut across cartridge body and hood.
cradle_len = total_len + 8;

// Cradle center.
// Tune if LED sits too high/low.
cradle_center_x = -1.5;
cradle_center_z = body_h * 0.62;

// Top opening depth makes sure the angled cradle is exposed to the top.
top_open_extra_len = total_len + 6;

// Through-hole LED cradle widths
cradle_5mm_w = 5.8;
cradle_3mm_w = 3.8;
cradle_tocan_w = 7.4;

// Cradle depth into body
cradle_5mm_depth = 4.8;
cradle_3mm_depth = 3.6;
cradle_tocan_depth = 5.8;

// Top opening depths
top_open_5mm_depth = 5.4;
top_open_3mm_depth = 4.2;
top_open_tocan_depth = 6.4;

// ---------------------------------------------------------
// Wire / lead exit features
// ---------------------------------------------------------

wire_channel_w = 3.2;
wire_channel_h = 2.4;
wire_channel_len = 10.0;

// Vertical lead holes for through-hole LEDs.
// These are vertical, so they print without support.
enable_vertical_lead_holes = true;

lead_hole_d = 1.4;
lead_spacing_5mm = 2.54;
lead_spacing_3mm = 2.54;
lead_spacing_tocan = 3.0;

lead_hole_x = body_len/2 - 5.0;

// ---------------------------------------------------------
// SMD carrier pocket
// ---------------------------------------------------------

smd_pocket_w = 7.4;       // Y width
smd_pocket_l = 9.0;       // along angled cradle direction
smd_pocket_depth = 1.6;
smd_top_open_depth = 3.4;
smd_wire_slot_w = 4.0;

// ---------------------------------------------------------
// Simple ID notch markers
// ---------------------------------------------------------
//
// Instead of raised labels, each part gets a different number of shallow
// top notches near the outside/wire side.
// 1 notch = 5mm
// 2 notches = 3mm
// 3 notches = SMD
// 4 notches = TO-can

enable_id_notches = true;
id_notch_w = 0.9;
id_notch_l = 3.0;
id_notch_depth = 0.8;

// ---------------------------------------------------------
// Helper modules
// ---------------------------------------------------------

module cartridge_solid() {
    union() {
        // Main rectangular body.
        translate([0, 0, body_h/2])
            cube([body_len, body_w, body_h], center = true);

        // Small hood extension on sample side.
        translate([-body_len/2 - hood_len/2, 0, hood_h/2])
            cube([hood_len, hood_w, hood_h], center = true);
    }
}

module open_top_cut(width, depth) {
    // Opens the top of the LED cradle so there is no enclosed roof.
    // This is the critical supportless change.
    translate([
        -hood_len/2,
        0,
        body_h - depth/2 + eps
    ])
        cube([top_open_extra_len, width, depth + 2*eps], center = true);
}

module angled_cradle_cut(width, depth) {
    // Angled open cradle for LED body.
    // This is an open recess, not a closed tunnel.
    translate([cradle_center_x, 0, cradle_center_z])
        rotate([0, cradle_angle_y, 0])
            cube([cradle_len, width, depth], center = true);
}

module wire_channel_cut(width = wire_channel_w) {
    // Top-side wire relief channel toward outside of ring.
    translate([
        body_len/2 - wire_channel_len/2 + 1.5,
        0,
        body_h - wire_channel_h/2 + eps
    ])
        cube([wire_channel_len, width, wire_channel_h + 2*eps], center = true);
}

module vertical_lead_holes(spacing) {
    if (enable_vertical_lead_holes) {
        for (y = [-spacing/2, spacing/2]) {
            translate([lead_hole_x, y, -1])
                cylinder(d = lead_hole_d, h = body_h + 2);
        }
    }
}

module id_notches(count) {
    if (enable_id_notches) {
        for (i = [0 : count - 1]) {
            y_pos = -body_w/2 + 1.4 + i * 1.4;
            translate([
                body_len/2 - 1.8,
                y_pos,
                body_h - id_notch_depth/2 + eps
            ])
                cube([id_notch_l, id_notch_w, id_notch_depth + 2*eps], center = true);
        }
    }
}

module round_led_open_cradle_cartridge(cradle_w, cradle_depth, top_depth, lead_spacing, notch_count) {
    difference() {
        cartridge_solid();

        // Supportless open-top LED cradle.
        open_top_cut(cradle_w + 0.5, top_depth);
        angled_cradle_cut(cradle_w, cradle_depth);

        // Wire channel.
        wire_channel_cut(wire_channel_w);

        // Vertical LED lead holes.
        vertical_lead_holes(lead_spacing);

        // Identification notches.
        id_notches(notch_count);
    }
}

module smd_pocket_cut() {
    // Angled shallow flat pocket for an SMD carrier.
    translate([cradle_center_x, 0, cradle_center_z])
        rotate([0, cradle_angle_y, 0])
            cube([smd_pocket_l, smd_pocket_w, smd_pocket_depth], center = true);
}

module smd_light_window_cut() {
    // Small optical opening through the angled SMD pocket region.
    // It is open from the top, so it should not create a floating roof.
    translate([cradle_center_x - 1.0, 0, cradle_center_z - 1.0])
        rotate([0, cradle_angle_y, 0])
            cube([cradle_len, 3.2, 2.2], center = true);
}

module smd_cartridge() {
    difference() {
        cartridge_solid();

        // Open-top region for the SMD carrier.
        open_top_cut(smd_pocket_w + 0.6, smd_top_open_depth);
        smd_pocket_cut();
        smd_light_window_cut();

        // Wider wire channel.
        wire_channel_cut(smd_wire_slot_w);

        // Identification notches.
        id_notches(3);
    }
}

// ---------------------------------------------------------
// Output: four cartridges side by side
// ---------------------------------------------------------

// 5 mm through-hole LED cartridge
translate([-1.5 * part_spacing, 0, 0])
    round_led_open_cradle_cartridge(
        cradle_w = cradle_5mm_w,
        cradle_depth = cradle_5mm_depth,
        top_depth = top_open_5mm_depth,
        lead_spacing = lead_spacing_5mm,
        notch_count = 1
    );

// 3 mm through-hole LED cartridge
translate([-0.5 * part_spacing, 0, 0])
    round_led_open_cradle_cartridge(
        cradle_w = cradle_3mm_w,
        cradle_depth = cradle_3mm_depth,
        top_depth = top_open_3mm_depth,
        lead_spacing = lead_spacing_3mm,
        notch_count = 2
    );

// SMD / flat LED carrier cartridge
translate([0.5 * part_spacing, 0, 0])
    smd_cartridge();

// TO-can / metal-can cartridge
translate([1.5 * part_spacing, 0, 0])
    round_led_open_cradle_cartridge(
        cradle_w = cradle_tocan_w,
        cradle_depth = cradle_tocan_depth,
        top_depth = top_open_tocan_depth,
        lead_spacing = lead_spacing_tocan,
        notch_count = 4
    );