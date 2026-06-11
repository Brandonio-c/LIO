// Lio v0.1 — Integrated Electronics Tray / Wire Management Plate
// Units: millimeters
//
// This part integrates:
// - Arduino Nano / ADS1115 / small breakout tray
// - ULN2003 driver board mount
// - USB pigtail strain relief base
// - separate USB strain relief clamp bar
// - wire tie-down slots
// - LED cable comb
// - flat label area
//
// PRINT ORIENTATION:
// - Main tray flat on bed
// - Clamp bar flat on bed
// - Supports OFF
//
// MATERIAL:
// - PETG recommended
//
// IMPORTANT:
// - Cheap Arduino/ADS1115/ULN2003 modules vary in size.
// - Measure your boards and tune the dimensions below.
// - This version uses zip-tie slots and generic standoffs instead of assuming exact PCB hole locations everywhere.

$fn = 96;
eps = 0.05;

// ---------------------------------------------------------
// Output selector
// ---------------------------------------------------------
//
// "both"       = tray + clamp bar side-by-side
// "tray"       = tray only
// "clamp_bar"  = USB pigtail clamp bar only

part = "both";

// ---------------------------------------------------------
// Main tray dimensions
// ---------------------------------------------------------

tray_w = 180;
tray_d = 110;
tray_t = 5.0;
corner_r = 6;

// ---------------------------------------------------------
// General hardware dimensions
// ---------------------------------------------------------

m3_clearance_d = 3.4;
m3_head_recess_d = 6.6;
m3_head_recess_depth = 2.0;

// Corner/frame mounting holes
frame_mount_x = tray_w/2 - 12;
frame_mount_y = tray_d/2 - 12;

// ---------------------------------------------------------
// Board zone dimensions
// ---------------------------------------------------------
//
// These are not exact board mounts. They are visual/physical zones with zip-tie slots.
// Use zip ties, M2/M3 screws where possible, or small adhesive foam tape.

zone_rail_h = 1.4;
zone_rail_w = 1.8;

// Arduino Nano zone.
// Official Nano PCB size is about 18 x 45 mm.
// Zone is larger for headers/wires.
nano_zone_x = -58;
nano_zone_y = 27;
nano_zone_w = 58;
nano_zone_d = 30;

// ADS1115 zones.
// Typical module sizes vary; use loose generic zones.
ads1_zone_x = 10;
ads1_zone_y = 30;
ads2_zone_x = 48;
ads2_zone_y = 30;
ads_zone_w = 34;
ads_zone_d = 24;

// Small breadboard / spare module zone.
spare_zone_x = -58;
spare_zone_y = -10;
spare_zone_w = 58;
spare_zone_d = 34;

// ---------------------------------------------------------
// ULN2003 driver board mount
// ---------------------------------------------------------
//
// ULN2003 boards are often around 31 x 35 mm.
// This is a generic standoff pattern.
// If your board holes do not align, use zip ties through the backup slots.

uln_zone_x = 47;
uln_zone_y = -26;

uln_board_w = 40;
uln_board_d = 38;

uln_standoff_spacing_x = 28;
uln_standoff_spacing_y = 24;

uln_standoff_d = 6.5;
uln_standoff_h = 5.0;
uln_pilot_hole_d = 2.7;

// Backup zip tie slots for ULN board
uln_zip_slot_w = 3.0;
uln_zip_slot_l = 15.0;

// ---------------------------------------------------------
// USB pigtail strain relief
// ---------------------------------------------------------
//
// USB pigtail enters from front edge.
// Red/black wires can route to ULN2003 VCC/GND.
//
// The base has a shallow cable groove.
// The separate clamp bar screws down over the cable.
// Do not crush the cable; tighten gently.

usb_x = -5;
usb_y = -tray_d/2 + 13;

usb_channel_w = 6.5;       // cable groove width
usb_channel_l = 42.0;      // cable groove length
usb_channel_depth = 2.2;

usb_clamp_hole_spacing = 24.0;
usb_clamp_hole_d = 3.4;

// Clamp bar separate part
clamp_bar_w = 36;
clamp_bar_d = 14;
clamp_bar_h = 5;

// ---------------------------------------------------------
// Wire clip rail / zip-tie slots
// ---------------------------------------------------------

// A row of through-slots for small zip ties.
clip_slot_count = 5;
clip_slot_w = 3.2;
clip_slot_l = 15.0;
clip_slot_spacing = 18.0;

clip_rail_x = 72;
clip_rail_y = 8;

// ---------------------------------------------------------
// LED cable comb
// ---------------------------------------------------------
//
// A row of raised teeth along back edge.
// Wires pass between teeth.
// No roofs/cantilevers, so supportless.

enable_led_comb = true;

comb_teeth_count = 17;       // 17 teeth creates 16 wire channels
comb_center_x = 0;
comb_center_y = tray_d/2 - 8;

comb_tooth_w = 2.0;
comb_tooth_d = 10.0;
comb_tooth_h = 9.0;
comb_pitch = 6.0;

// ---------------------------------------------------------
// Label area
// ---------------------------------------------------------
//
// Flat panel where you can put tape/marker labels.
// No raised text to avoid slicer weirdness.

label_area_x = -18;
label_area_y = -40;
label_area_w = 70;
label_area_d = 18;
label_border_h = 1.0;
label_border_w = 1.5;

// ---------------------------------------------------------
// Optional small wire exit notches
// ---------------------------------------------------------

enable_edge_wire_notches = true;
edge_notch_w = 5;
edge_notch_d = 4;
edge_notch_depth = 2.0;

// ---------------------------------------------------------
// Helper modules
// ---------------------------------------------------------

module rounded_plate(w, d, h, r) {
    hull() {
        for (x = [-w/2 + r, w/2 - r])
        for (y = [-d/2 + r, d/2 - r])
            translate([x, y, 0])
                cylinder(r = r, h = h);
    }
}

module outline_zone(cx, cy, w, d, rail_w, rail_h) {
    // Four raised rails marking a board area.
    // Open top, no supports.
    translate([cx, cy - d/2 + rail_w/2, tray_t + rail_h/2])
        cube([w, rail_w, rail_h], center = true);

    translate([cx, cy + d/2 - rail_w/2, tray_t + rail_h/2])
        cube([w, rail_w, rail_h], center = true);

    translate([cx - w/2 + rail_w/2, cy, tray_t + rail_h/2])
        cube([rail_w, d, rail_h], center = true);

    translate([cx + w/2 - rail_w/2, cy, tray_t + rail_h/2])
        cube([rail_w, d, rail_h], center = true);
}

module board_zip_slots_cut(cx, cy, w, d) {
    // Four vertical rectangular slots for zip ties.
    // Slots are through-cuts, so they print supportless.
    slot_w = 3.0;
    slot_l = 12.0;

    for (x = [-w/2 + 9, w/2 - 9]) {
        translate([cx + x, cy - d/2 + 5, -1])
            cube([slot_w, slot_l, tray_t + 2], center = false);

        translate([cx + x, cy + d/2 - 5 - slot_l, -1])
            cube([slot_w, slot_l, tray_t + 2], center = false);
    }
}

module frame_mount_holes_cut() {
    for (x = [-frame_mount_x, frame_mount_x])
    for (y = [-frame_mount_y, frame_mount_y]) {
        translate([x, y, -1])
            cylinder(d = m3_clearance_d, h = tray_t + 2);

        translate([x, y, tray_t - m3_head_recess_depth])
            cylinder(d = m3_head_recess_d, h = m3_head_recess_depth + 1);
    }
}

module uln2003_standoffs() {
    for (x = [-uln_standoff_spacing_x/2, uln_standoff_spacing_x/2])
    for (y = [-uln_standoff_spacing_y/2, uln_standoff_spacing_y/2]) {
        translate([uln_zone_x + x, uln_zone_y + y, tray_t])
            cylinder(d = uln_standoff_d, h = uln_standoff_h);
    }
}

module uln2003_holes_cut() {
    for (x = [-uln_standoff_spacing_x/2, uln_standoff_spacing_x/2])
    for (y = [-uln_standoff_spacing_y/2, uln_standoff_spacing_y/2]) {
        translate([
            uln_zone_x + x,
            uln_zone_y + y,
            tray_t + uln_standoff_h - 3.2
        ])
            cylinder(d = uln_pilot_hole_d, h = 4.5);
    }
}

module uln_zip_slots_cut() {
    // Backup slots if board holes do not align.
    for (y = [-uln_board_d/2 + 7, uln_board_d/2 - 7]) {
        translate([
            uln_zone_x - uln_zip_slot_l/2,
            uln_zone_y + y - uln_zip_slot_w/2,
            -1
        ])
            cube([uln_zip_slot_l, uln_zip_slot_w, tray_t + 2], center = false);

        translate([
            uln_zone_x + uln_zip_slot_l/2,
            uln_zone_y + y - uln_zip_slot_w/2,
            -1
        ])
            cube([uln_zip_slot_l, uln_zip_slot_w, tray_t + 2], center = false);
    }
}

module usb_channel_cut() {
    // Shallow top groove for USB pigtail.
    translate([
        usb_x,
        usb_y,
        tray_t - usb_channel_depth/2 + eps
    ])
        cube([usb_channel_w, usb_channel_l, usb_channel_depth + 2*eps], center = true);

    // Open exit notch at front edge.
    translate([
        usb_x,
        -tray_d/2 + edge_notch_d/2,
        tray_t - edge_notch_depth/2 + eps
    ])
        cube([usb_channel_w + 2, edge_notch_d + 2, edge_notch_depth + 2*eps], center = true);
}

module usb_clamp_holes_cut() {
    for (x = [-usb_clamp_hole_spacing/2, usb_clamp_hole_spacing/2]) {
        translate([usb_x + x, usb_y, -1])
            cylinder(d = usb_clamp_hole_d, h = tray_t + 2);
    }
}

module wire_clip_slots_cut() {
    // Row of through-slots for zip ties / cable straps.
    for (i = [0 : clip_slot_count - 1]) {
        y = clip_rail_y + (i - (clip_slot_count-1)/2) * clip_slot_spacing;

        translate([
            clip_rail_x - clip_slot_w/2,
            y - clip_slot_l/2,
            -1
        ])
            cube([clip_slot_w, clip_slot_l, tray_t + 2], center = false);
    }
}

module led_comb_teeth() {
    if (enable_led_comb) {
        for (i = [0 : comb_teeth_count - 1]) {
            x = comb_center_x + (i - (comb_teeth_count - 1)/2) * comb_pitch;

            translate([x, comb_center_y, tray_t + comb_tooth_h/2])
                cube([comb_tooth_w, comb_tooth_d, comb_tooth_h], center = true);
        }
    }
}

module label_area_border() {
    // Simple raised border around flat label area.
    outline_zone(
        cx = label_area_x,
        cy = label_area_y,
        w = label_area_w,
        d = label_area_d,
        rail_w = label_border_w,
        rail_h = label_border_h
    );
}

module edge_wire_notches_cut() {
    if (enable_edge_wire_notches) {
        // A few top-edge notches for routing wires off the tray.
        for (x = [-55, -35, 35, 55]) {
            translate([
                x,
                tray_d/2 - edge_notch_d/2,
                tray_t - edge_notch_depth/2 + eps
            ])
                cube([edge_notch_w, edge_notch_d + 2, edge_notch_depth + 2*eps], center = true);
        }
    }
}

module clamp_bar() {
    difference() {
        // Separate flat clamp bar.
        rounded_plate(clamp_bar_w, clamp_bar_d, clamp_bar_h, 2);

        // Two M3 clearance holes matching tray.
        for (x = [-usb_clamp_hole_spacing/2, usb_clamp_hole_spacing/2]) {
            translate([x, 0, -1])
                cylinder(d = m3_clearance_d, h = clamp_bar_h + 2);

            // Screw-head recess
            translate([x, 0, clamp_bar_h - m3_head_recess_depth])
                cylinder(d = m3_head_recess_d, h = m3_head_recess_depth + 1);
        }

        // Very shallow underside relief is intentionally omitted.
        // The cable sits in the tray groove; this clamp presses gently over it.
    }
}

// ---------------------------------------------------------
// Main tray model
// ---------------------------------------------------------

module electronics_tray() {
    difference() {
        union() {
            // Base tray plate.
            rounded_plate(tray_w, tray_d, tray_t, corner_r);

            // Board zone outline rails.
            outline_zone(nano_zone_x, nano_zone_y, nano_zone_w, nano_zone_d, zone_rail_w, zone_rail_h);
            outline_zone(ads1_zone_x, ads1_zone_y, ads_zone_w, ads_zone_d, zone_rail_w, zone_rail_h);
            outline_zone(ads2_zone_x, ads2_zone_y, ads_zone_w, ads_zone_d, zone_rail_w, zone_rail_h);
            outline_zone(spare_zone_x, spare_zone_y, spare_zone_w, spare_zone_d, zone_rail_w, zone_rail_h);
            outline_zone(uln_zone_x, uln_zone_y, uln_board_w, uln_board_d, zone_rail_w, zone_rail_h);

            // ULN2003 standoffs.
            uln2003_standoffs();

            // LED wire comb teeth.
            led_comb_teeth();

            // Label area border.
            label_area_border();
        }

        // Tray/frame mount holes.
        frame_mount_holes_cut();

        // Board zip slots.
        board_zip_slots_cut(nano_zone_x, nano_zone_y, nano_zone_w, nano_zone_d);
        board_zip_slots_cut(ads1_zone_x, ads1_zone_y, ads_zone_w, ads_zone_d);
        board_zip_slots_cut(ads2_zone_x, ads2_zone_y, ads_zone_w, ads_zone_d);
        board_zip_slots_cut(spare_zone_x, spare_zone_y, spare_zone_w, spare_zone_d);

        // ULN2003 pilot holes and backup slots.
        uln2003_holes_cut();
        uln_zip_slots_cut();

        // USB strain relief groove and clamp holes.
        usb_channel_cut();
        usb_clamp_holes_cut();

        // Wire tie-down rail slots.
        wire_clip_slots_cut();

        // Edge wire notches.
        edge_wire_notches_cut();
    }
}

// ---------------------------------------------------------
// Output selector
// ---------------------------------------------------------

if (part == "tray") {
    electronics_tray();
}

if (part == "clamp_bar") {
    clamp_bar();
}

if (part == "both") {
    translate([0, 0, 0])
        electronics_tray();

    // Separate clamp bar printed beside tray.
    translate([0, -tray_d/2 - 25, 0])
        clamp_bar();
}