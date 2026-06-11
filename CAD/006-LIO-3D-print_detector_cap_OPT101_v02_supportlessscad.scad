// Lio v0.2 — Top Detector Cap for OPT101, SUPPORTLESS VERSION
// Units: millimeters
//
// FIXED ISSUE:
// The old one-piece version had the snout and plug lip below Z=0.
// Creality Print put the snout on the bed and treated the cap disk as a floating cantilever.
// This version splits the part into:
//   1. flat detector cap
//   2. separate underside plug-lip + snout insert
//   3. small alignment pin for gluing/assembly
//
// Print all parts flat on the bed.
// After printing, glue or screw the snout insert to the underside of the cap,
// using the printed alignment pin through the apertures to center it.
//
// Recommended:
// - PETG
// - 0.20 mm layer height
// - 4 walls for cap
// - supports off
// - brim optional

$fn = 128;
eps = 0.05;

// ---------------------------------------------------------
// SELECT WHAT TO EXPORT
// ---------------------------------------------------------
//
// Options:
//   "both"          -> prints cap + snout insert + alignment pin, separated on the bed
//   "cap"           -> cap only
//   "snout_insert"  -> snout insert only
//   "alignment_pin" -> alignment pin only

part = "both";

// ---------------------------------------------------------
// Main cap dimensions
// ---------------------------------------------------------

cap_od = 92;
cap_t  = 7;

// Central viewing aperture through the cap.
// This is the actual detector aperture.
aperture_d = 6.5;

// ---------------------------------------------------------
// Underside insert dimensions
// ---------------------------------------------------------
//
// This separate insert replaces the old negative-Z plug lip and snout.
//
// plug_lip_d should fit inside the 60 mm ID outer tube.
// plug_lip_h is the short centering lip.
// snout extends below the cap into the optical tube after assembly.

plug_lip_d = 58.8;
plug_lip_h = 4.0;

snout_outer_d = 18;
snout_inner_d = aperture_d;
snout_len = 12;

snout_base_d = 24;
snout_base_h = 3;

// Optional small glue relief grooves on snout insert bottom.
// These are just shallow radial grooves so glue has somewhere to go.
enable_glue_grooves = true;
glue_groove_w = 2.0;
glue_groove_depth = 0.7;

// ---------------------------------------------------------
// OPT101 PCB pocket
// ---------------------------------------------------------
//
// Measure your module. Defaults are intentionally loose.

pcb_pocket_w = 28;
pcb_pocket_d = 22;
pcb_pocket_depth = 2.2;
pcb_corner_r = 2.0;

enable_pcb_mount_holes = true;
pcb_mount_hole_d = 2.2;
pcb_mount_spacing_x = 22;
pcb_mount_spacing_y = 16;

// ---------------------------------------------------------
// M3 mounting pattern to outer tube
// ---------------------------------------------------------

m3_clearance_d = 3.4;
m3_head_recess_d = 6.5;
m3_head_recess_depth = 2.4;

mount_bolt_circle_d = 74;
mount_r = mount_bolt_circle_d / 2;

// ---------------------------------------------------------
// Dogleg wire exit groove
// ---------------------------------------------------------
//
// Shallow top-side groove. It does not cut all the way through.
// It gives the OPT101 wires a path without creating a straight optical leak.

wire_channel_w = 5.0;
wire_channel_depth = 2.4;

wire_start_x = pcb_pocket_w/2 - 2;
wire_start_y = 0;

wire_mid1_x = 28;
wire_mid1_y = 0;

wire_mid2_x = 28;
wire_mid2_y = 18;

wire_exit_x = cap_od/2 + 2;
wire_exit_y = 18;

// ---------------------------------------------------------
// Alignment mark
// ---------------------------------------------------------

enable_alignment_mark = true;
alignment_mark_w = 3;
alignment_mark_l = 10;
alignment_mark_depth = 1.0;

// ---------------------------------------------------------
// Top rim around detector aperture
// ---------------------------------------------------------

enable_top_aperture_rim = true;
rim_od = 11;
rim_id = aperture_d + 1.0;
rim_h = 0.8;

// ---------------------------------------------------------
// Alignment pin
// ---------------------------------------------------------
//
// Used only during assembly to center cap and snout insert.
// Do not leave it installed if it blocks the optical path.

alignment_pin_d = aperture_d - 0.35;
alignment_pin_h = 28;

// ---------------------------------------------------------
// Helper modules
// ---------------------------------------------------------

module rounded_rect_2d(w, d, r) {
    hull() {
        for (x = [-w/2 + r, w/2 - r])
        for (y = [-d/2 + r, d/2 - r])
            translate([x, y])
                circle(r = r);
    }
}

module rounded_box_cut(w, d, h, r) {
    linear_extrude(height = h)
        rounded_rect_2d(w, d, r);
}

module ring(od, id, h) {
    difference() {
        cylinder(d = od, h = h);
        translate([0, 0, -1])
            cylinder(d = id, h = h + 2);
    }
}

module dogleg_channel_cut() {
    z0 = cap_t - wire_channel_depth;

    // Segment 1
    translate([
        (wire_start_x + wire_mid1_x)/2,
        wire_start_y,
        z0
    ])
        cube([
            abs(wire_mid1_x - wire_start_x) + wire_channel_w,
            wire_channel_w,
            wire_channel_depth + eps
        ], center = true);

    // Segment 2
    translate([
        wire_mid1_x,
        (wire_mid1_y + wire_mid2_y)/2,
        z0
    ])
        cube([
            wire_channel_w,
            abs(wire_mid2_y - wire_mid1_y) + wire_channel_w,
            wire_channel_depth + eps
        ], center = true);

    // Segment 3
    translate([
        (wire_mid2_x + wire_exit_x)/2,
        wire_mid2_y,
        z0
    ])
        cube([
            abs(wire_exit_x - wire_mid2_x) + wire_channel_w,
            wire_channel_w,
            wire_channel_depth + eps
        ], center = true);
}

module m3_mount_holes_cut() {
    for (a = [0, 90, 180, 270]) {
        rotate([0, 0, a])
        translate([mount_r, 0, -1]) {

            // Through clearance hole
            cylinder(d = m3_clearance_d, h = cap_t + 2);

            // Top screw-head recess
            translate([0, 0, cap_t - m3_head_recess_depth])
                cylinder(d = m3_head_recess_d,
                         h = m3_head_recess_depth + 1.5);
        }
    }
}

module pcb_mount_holes_cut() {
    if (enable_pcb_mount_holes) {
        for (x = [-pcb_mount_spacing_x/2, pcb_mount_spacing_x/2])
        for (y = [-pcb_mount_spacing_y/2, pcb_mount_spacing_y/2]) {
            translate([x, y, cap_t - pcb_pocket_depth - 1])
                cylinder(d = pcb_mount_hole_d,
                         h = pcb_pocket_depth + 2);
        }
    }
}

module alignment_mark_cut() {
    if (enable_alignment_mark) {
        translate([
            0,
            cap_od/2 - alignment_mark_l/2,
            cap_t - alignment_mark_depth
        ])
            cube([
                alignment_mark_w,
                alignment_mark_l,
                alignment_mark_depth + eps
            ], center = true);
    }
}

module glue_grooves_cut() {
    if (enable_glue_grooves) {
        for (a = [0, 90, 180, 270]) {
            rotate([0, 0, a])
            translate([plug_lip_d/4, 0, plug_lip_h - glue_groove_depth/2])
                cube([plug_lip_d/2, glue_groove_w, glue_groove_depth + eps],
                     center = true);
        }
    }
}

// ---------------------------------------------------------
// PART 1: flat detector cap
// ---------------------------------------------------------

module detector_cap() {
    difference() {
        union() {
            // Main flat cap disk: fully supported on bed.
            cylinder(d = cap_od, h = cap_t);

            // Optional raised rim around aperture on top.
            if (enable_top_aperture_rim) {
                translate([0, 0, cap_t])
                    ring(rim_od, rim_id, rim_h);
            }
        }

        // Central optical aperture through cap.
        translate([0, 0, -1])
            cylinder(d = aperture_d, h = cap_t + rim_h + 3);

        // OPT101 PCB pocket on top face.
        translate([0, 0, cap_t - pcb_pocket_depth])
            rounded_box_cut(
                w = pcb_pocket_w,
                d = pcb_pocket_d,
                h = pcb_pocket_depth + 1,
                r = pcb_corner_r
            );

        // PCB pilot/mount holes.
        pcb_mount_holes_cut();

        // Dogleg wire channel on top face.
        dogleg_channel_cut();

        // M3 flange mounting holes.
        m3_mount_holes_cut();

        // Optional shallow alignment notch.
        alignment_mark_cut();
    }
}

// ---------------------------------------------------------
// PART 2: underside plug-lip + detector snout insert
// ---------------------------------------------------------

module snout_insert() {
    difference() {
        union() {
            // Centering plug/lip disk.
            // This part will be glued/screwed under the cap after printing.
            cylinder(d = plug_lip_d, h = plug_lip_h);

            // Reinforced snout base.
            translate([0, 0, plug_lip_h])
                cylinder(d = snout_base_d, h = snout_base_h);

            // Detector snout tube.
            translate([0, 0, plug_lip_h])
                cylinder(d = snout_outer_d, h = snout_len);
        }

        // Central optical bore through entire insert.
        translate([0, 0, -1])
            cylinder(d = snout_inner_d, h = plug_lip_h + snout_len + 3);

        // Shallow glue relief grooves on cap-contact face.
        glue_grooves_cut();
    }
}

// ---------------------------------------------------------
// PART 3: assembly alignment pin
// ---------------------------------------------------------

module alignment_pin() {
    cylinder(d = alignment_pin_d, h = alignment_pin_h);
}

// ---------------------------------------------------------
// Output selector
// ---------------------------------------------------------

if (part == "cap") {
    detector_cap();
}

if (part == "snout_insert") {
    snout_insert();
}

if (part == "alignment_pin") {
    alignment_pin();
}

if (part == "both") {
    // Cap centered.
    translate([0, 0, 0])
        detector_cap();

    // Snout insert placed to the right.
    translate([120, 0, 0])
        snout_insert();

    // Alignment pin placed to the left.
    translate([-75, 0, 0])
        alignment_pin();
}