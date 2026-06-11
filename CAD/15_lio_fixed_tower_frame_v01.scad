// Lio v0.1 - Fixed Tower Frame
// File: 15_lio_fixed_tower_frame_v01.scad
// Units: millimeters
//
// Purpose:
// This is the missing structural frame that connects the fixed optical chamber
// to the motorized Z-stage.
//
// It creates:
// 1. side_plate      - print two copies
// 2. optical_saddle - print one copy
//
// Coordinate logic for the actual assembled Lio machine:
// M6 drive axis:       X = 0, Y = 0
// left guide rod:      X = -45, Y = 0
// right guide rod:     X = +45, Y = 0
// sample/optical axis: X = 0, Y = +35
//
// The side plates are printed flat, then installed vertically.
// The optical saddle is printed flat and mounted between/onto the tower plates.
// The optical saddle centers the fixed optical tube/collar over the sample axis.
//
// Print orientation:
// - side plates: flat on bed
// - optical saddle: flat on bed
//
// Recommended material/settings:
// - PETG
// - 0.20 mm layer height
// - 4 walls
// - 35-45% infill
// - supports OFF
// - brim optional

$fn = 128;
eps = 0.05;

// ---------------------------------------------------------
// OUTPUT SELECTOR
// ---------------------------------------------------------
//
// Options:
// "side_plate"       -> one tower side plate; print two copies
// "optical_saddle"   -> forward-offset optical collar saddle
// "layout_preview"   -> shows side plate + saddle together, not guaranteed optimal bed layout
//
// Recommended:
// 1. Export side_plate STL and print it twice.
// 2. Export optical_saddle STL and print it once.

part = "side_plate";

// ---------------------------------------------------------
// Shared system geometry
// ---------------------------------------------------------

rod_spacing = 90;
sample_y_offset = 35;       // optical/sample axis offset from M6 drive axis

m3_clearance_d = 3.4;
m3_slot_w = 3.6;

// ---------------------------------------------------------
// Side plate geometry
// ---------------------------------------------------------
//
// In side_plate local printed coordinates:
// X = actual front/back direction of the machine
//     X = 0 corresponds roughly to M6/rod axis line
//     X = +35 corresponds to optical/sample axis line
// Y = vertical height after assembly
// Z = plate thickness while printing
//
// The plate is printed flat, then installed upright.

side_plate_depth = 80;       // front/back depth of side plate
side_plate_h = 172;          // tower height
side_plate_t = 7;            // side plate thickness
side_plate_corner_r = 5;

side_plate_x_min = -22;
side_plate_x_max = side_plate_x_min + side_plate_depth;
side_plate_x_center = (side_plate_x_min + side_plate_x_max) / 2;

// Mounting levels on the side plate
bottom_mount_y1 = 18;
bottom_mount_y2 = 38;

top_mount_y1 = side_plate_h - 38;
top_mount_y2 = side_plate_h - 18;

// Optical saddle mounting levels.
// These are where the saddle/optical support brackets can bolt to the tower.
optical_mount_y1 = 106;
optical_mount_y2 = 130;

// Large cutout for moving platform clearance / weight reduction.
// Kept toward mechanical side so the optical forward region remains stiff.
enable_side_plate_window = true;
window_x = -2;
window_y = 84;
window_w = 30;
window_h = 78;
window_r = 7;

// Rib / datum notches
enable_side_plate_alignment_notches = true;
notch_w = 4;
notch_l = 10;
notch_depth = side_plate_t + 2;

// Slots
mount_slot_len = 22;         // horizontal adjustment slots for base/top bridge
optical_slot_len = 22;       // vertical adjustment slots for optical saddle

// ---------------------------------------------------------
// Optical saddle geometry
// ---------------------------------------------------------
//
// The optical saddle is a flat top-view flange/bridge.
// It encodes the sample axis offset.
//
// In saddle local printed coordinates:
// X = left/right across rods
// Y = front/back
// Z = thickness while printing
//
// M6/rod frame center is around Y=0.
// Optical tube/collar center is at Y=sample_y_offset.

saddle_t = 8;

saddle_ring_od = 104;        // supports 92 mm bottom collar flange with margin
saddle_ring_id = 66;         // large light/sample opening

// Matches bottom fixed collar / outer tube bolt circle
collar_bolt_circle_d = 74;
collar_bolt_r = collar_bolt_circle_d / 2;

// Side ears for attaching saddle to tower side plates / brackets
side_plate_spacing = 132;    // distance between left/right side attachment zones
ear_x = side_plate_spacing / 2;

ear_w = 24;                  // left/right ear width
ear_d = 78;                  // front/back ear depth
ear_corner_r = 5;

// Bridge web connecting ears and ring.
// This keeps saddle rigid.
bridge_w = side_plate_spacing + ear_w;
bridge_d = 28;

// Saddle side attachment slots
saddle_side_slot_len = 22;
saddle_side_slot_w = 3.6;

// Side attachment slot Y positions in saddle coordinates.
// These give Y adjustment around the mechanical-to-optical offset.
saddle_side_y1 = 10;
saddle_side_y2 = sample_y_offset + 20;

// Optional large clamp-relief flats
enable_saddle_alignment_marks = true;
saddle_mark_depth = 0.8;

// ---------------------------------------------------------
// Helper modules
// ---------------------------------------------------------

module rounded_rect_2d(w, h, r) {
    hull() {
        for (x = [-w/2 + r, w/2 - r])
        for (y = [-h/2 + r, h/2 - r])
            translate([x, y])
                circle(r = r);
    }
}

module rounded_plate_2d(w, h, r) {
    rounded_rect_2d(w, h, r);
}

module slot_2d(len, d) {
    hull() {
        translate([-len/2, 0])
            circle(d = d);
        translate([ len/2, 0])
            circle(d = d);
    }
}

module side_plate_profile_2d() {
    translate([side_plate_x_center, side_plate_h/2])
        rounded_plate_2d(side_plate_depth, side_plate_h, side_plate_corner_r);
}

module side_plate_slots_2d() {

    // Bottom base attachment slots near mechanical axis.
    // Horizontal slots give front/back adjustment.
    for (yy = [bottom_mount_y1, bottom_mount_y2]) {
        translate([0, yy])
            slot_2d(mount_slot_len, m3_slot_w);
    }

    // Top bridge attachment slots near mechanical axis.
    // Horizontal slots give front/back adjustment.
    for (yy = [top_mount_y1, top_mount_y2]) {
        translate([0, yy])
            slot_2d(mount_slot_len, m3_slot_w);
    }

    // Optical saddle/frame attachment slots at sample axis offset.
    // Vertical slots give height adjustment for the optical saddle.
    for (yy = [optical_mount_y1, optical_mount_y2]) {
        translate([sample_y_offset, yy])
            rotate(90)
                slot_2d(optical_slot_len, m3_slot_w);
    }

    // Additional optional saddle stabilization holes.
    // These give you extra mounting options if the frame flexes.
    translate([sample_y_offset, (optical_mount_y1 + optical_mount_y2)/2])
        circle(d = m3_clearance_d);
}

module side_plate_window_2d() {
    if (enable_side_plate_window) {
        translate([window_x, window_y])
            rounded_rect_2d(window_w, window_h, window_r);
    }
}

module side_plate_alignment_notches_2d() {
    if (enable_side_plate_alignment_notches) {
        // Small datum notch at mechanical axis near bottom
        translate([0, 5])
            square([notch_w, notch_l], center = true);

        // Small datum notch at optical axis near optical support region
        translate([sample_y_offset, optical_mount_y2 + 13])
            square([notch_w, notch_l], center = true);
    }
}

// ---------------------------------------------------------
// PART 15A / 15B - side plate
// ---------------------------------------------------------

module side_plate() {
    linear_extrude(height = side_plate_t)
    difference() {
        side_plate_profile_2d();

        side_plate_slots_2d();

        side_plate_window_2d();

        side_plate_alignment_notches_2d();
    }
}

// ---------------------------------------------------------
// Optical saddle 2D profile
// ---------------------------------------------------------

module saddle_profile_2d() {
    union() {
        // Main ring centered on optical/sample axis.
        translate([0, sample_y_offset])
            circle(d = saddle_ring_od);

        // Left/right ears.
        for (sx = [-ear_x, ear_x]) {
            translate([sx, sample_y_offset/2])
                rounded_rect_2d(ear_w, ear_d, ear_corner_r);
        }

        // Main cross bridge web connecting ears to the ring.
        translate([0, sample_y_offset])
            rounded_rect_2d(bridge_w, bridge_d, 5);

        // Rear cross bridge around mechanical axis.
        // Helps resist twist between side plates.
        translate([0, 0])
            rounded_rect_2d(bridge_w * 0.72, 18, 4);
    }
}

module saddle_cuts_2d() {

    // Central optical/sample opening.
    translate([0, sample_y_offset])
        circle(d = saddle_ring_id);

    // M3 holes matching bottom collar / outer tube bolt circle.
    for (a = [0, 90, 180, 270]) {
        translate([
            collar_bolt_r * cos(a),
            sample_y_offset + collar_bolt_r * sin(a)
        ])
            circle(d = m3_clearance_d);
    }

    // Side mounting slots for attaching saddle to side plates/brackets.
    // Slots are elongated in Y to permit front/back adjustment.
    for (sx = [-ear_x, ear_x]) {
        for (yy = [saddle_side_y1, saddle_side_y2]) {
            translate([sx, yy])
                rotate(90)
                    slot_2d(saddle_side_slot_len, saddle_side_slot_w);
        }
    }

    // Optional shallow datum/alignment marks.
    // These are through-cuts so they are visible and do not create raised text.
    if (enable_saddle_alignment_marks) {
        // Mechanical centerline mark near Y=0
        translate([0, 0])
            square([50, 1.2], center = true);

        // Optical axis centerline mark near Y=sample_y_offset
        translate([0, sample_y_offset])
            square([saddle_ring_od + 14, 1.2], center = true);

        // X-axis optical mark
        translate([0, sample_y_offset])
            square([1.2, saddle_ring_od + 14], center = true);
    }
}

// ---------------------------------------------------------
// PART 15C - optical tube saddle / collar support
// ---------------------------------------------------------

module optical_saddle() {
    linear_extrude(height = saddle_t)
    difference() {
        saddle_profile_2d();
        saddle_cuts_2d();
    }
}

// ---------------------------------------------------------
// Layout preview
// ---------------------------------------------------------

module layout_preview() {
    // This is a convenience layout only.
    // If it does not fit your bed cleanly, export/print individual parts.
    translate([-70, 0, 0])
        side_plate();

    translate([35, 0, 0])
        side_plate();

    translate([0, -135, 0])
        optical_saddle();
}

// ---------------------------------------------------------
// Output selector
// ---------------------------------------------------------

if (part == "side_plate") {
    side_plate();
}

if (part == "optical_saddle") {
    optical_saddle();
}

if (part == "layout_preview") {
    layout_preview();
}