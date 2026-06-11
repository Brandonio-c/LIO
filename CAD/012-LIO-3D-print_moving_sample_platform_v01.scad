// Lio v0.1 — Moving Sample Platform / Elevator Carriage
// Units: millimeters
//
// This part integrates:
// - sample platform plate
// - LM8UU bearing housings
// - M6 nut trap
// - sample cup pocket
// - PTFE holder seat compatibility
// - endstop trigger flag
// - height pointer
// - mounting points for moving telescoping skirt
//
// IMPORTANT DESIGN CHOICE:
// The sample cup is offset forward from the M6 drive screw.
// Mechanical drive center: X=0, Y=0
// Optical/sample center:  X=0, Y=sample_y_offset
//
// Why:
// If the M6 threaded rod and sample cup were both centered at X0/Y0,
// the threaded rod would interfere with the sample cup.
// This offset avoids that problem while keeping the sample cup centered
// under the future optical tube/detector axis.
//
// Print orientation:
// - Flat on bed.
// - Supports OFF.
//
// Material:
// - PETG recommended.
//
// Suggested print settings:
// - 0.20 mm layer height
// - 4 walls
// - 35–45% infill
// - supports OFF
// - brim optional

$fn = 128;
eps = 0.05;

// ---------------------------------------------------------
// Main platform dimensions
// ---------------------------------------------------------

plate_w = 125;         // suggested 110–120+, widened for bearing bosses
plate_d = 135;         // deeper so sample cup can be offset from M6 screw
plate_t = 9;           // suggested 8–10 mm
corner_r = 6;

// ---------------------------------------------------------
// Guide rod / LM8UU bearing geometry
// ---------------------------------------------------------

rod_spacing = 90;
rod_x = rod_spacing / 2;
rod_y = 0;

// LM8UU nominal dimensions are 8 mm ID, 15 mm OD, 24 mm length.
// Use your LM8UU test block to choose final bore.
lm8uu_bore_d = 15.4;       // CHANGE after your fit test: maybe 15.2/15.4/15.6
lm8uu_len = 24.0;
lm8uu_pocket_depth = 25.5; // slightly deeper than bearing length

// Lower rod-clearance section under bearing pocket.
// This creates a shelf so the bearing does not fall through.
rod_clearance_d = 8.8;     // for your generic 8 mm rods; tune if needed

bearing_boss_d = 25.0;
bearing_boss_h = 32.0;

// Lead-in at top of bearing pocket
bearing_leadin_d = 16.3;
bearing_leadin_h = 2.0;

// ---------------------------------------------------------
// M6 threaded rod / nut trap geometry
// ---------------------------------------------------------

m6_x = 0;
m6_y = 0;

m6_clearance_d = 7.2;      // M6 threaded rod clearance

// Use result from M6 nut trap test.
m6_nut_af = 10.6;          // across flats; CHANGE after fit test
m6_nut_depth = 6.5;        // normal M6 nut depth; increase for coupling nut

m6_boss_d = 24;
m6_boss_h = 9;

// Optional retainer screw holes around nut boss.
// Leave enabled; they are vertical, support-free, and useful later.
enable_nut_retainer_holes = true;
nut_retainer_hole_d = 3.2;
nut_retainer_spacing = 20;

// ---------------------------------------------------------
// Sample cup / PTFE holder seat
// ---------------------------------------------------------

// Offset sample cup forward from drive screw.
sample_y_offset = 35;

// Pocket for removable sample cup / PTFE holder.
// This is only a shallow locating recess; the cup itself is printed separately.
sample_pocket_d = 45.0;     // suggested 40–45 mm
sample_pocket_depth = 3.0;

// Small anti-rotation notches in sample pocket
enable_sample_notches = true;
sample_notch_w = 4.0;
sample_notch_l = 6.0;
sample_notch_depth = sample_pocket_depth + 0.5;

// ---------------------------------------------------------
// Moving telescoping skirt mounting points
// ---------------------------------------------------------

// Skirt will mount around sample center.
skirt_mount_bcd = 57.0;     // bolt circle around sample pocket
skirt_mount_r = skirt_mount_bcd / 2;
skirt_mount_hole_d = 3.4;   // M3 clearance

// Optional shallow recesses for screw heads around skirt holes.
enable_skirt_recess = true;
skirt_recess_d = 6.5;
skirt_recess_depth = 2.0;

// ---------------------------------------------------------
// Endstop trigger flag
// ---------------------------------------------------------

enable_endstop_flag = true;

// Place the flag near the rear-left/front-left edge depending your endstop.
// This matches the motor-base endstop zone reasonably well.
flag_x = -55;
flag_y = -55;

flag_w = 9;
flag_d = 12;
flag_h = 22;

// Add a small beveled/stepped contact face? Simple rectangle for v0.1.
flag_contact_extra_h = 2;

// ---------------------------------------------------------
// Height pointer
// ---------------------------------------------------------

enable_height_pointer = true;

// Pointer protrudes from +X side and can line up with a printed height scale.
pointer_y = 42;
pointer_len = 12;
pointer_w = 10;
pointer_h = plate_t;

// ---------------------------------------------------------
// Generic accessory holes
// ---------------------------------------------------------

enable_accessory_holes = true;
accessory_hole_d = 3.4;

// Four generic accessory holes near the corners, but inside plate edge.
accessory_x = plate_w/2 - 13;
accessory_y = plate_d/2 - 13;

// ---------------------------------------------------------
// Shallow alignment marks
// ---------------------------------------------------------

enable_alignment_marks = true;
mark_depth = 0.7;
mark_w = 1.2;

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

module hex_prism_af(af, h) {
    // Hex specified by across-flats dimension.
    // OpenSCAD cylinder d is circumdiameter, so convert AF to diameter.
    cylinder(d = af / cos(30), h = h, $fn = 6);
}

module bearing_boss(xpos, ypos) {
    translate([xpos, ypos, plate_t])
        cylinder(d = bearing_boss_d, h = bearing_boss_h);
}

module bearing_bore_cut(xpos, ypos) {
    // Full rod clearance through the whole platform/boss.
    translate([xpos, ypos, -1])
        cylinder(d = rod_clearance_d, h = plate_t + bearing_boss_h + 3);

    // LM8UU vertical bearing pocket from top.
    // Leaves a shelf underneath so bearing does not drop through.
    pocket_z0 = plate_t + bearing_boss_h - lm8uu_pocket_depth;

    translate([xpos, ypos, pocket_z0])
        cylinder(d = lm8uu_bore_d, h = lm8uu_pocket_depth + 1);

    // Top lead-in
    translate([xpos, ypos, plate_t + bearing_boss_h - bearing_leadin_h])
        cylinder(d = bearing_leadin_d, h = bearing_leadin_h + 1);
}

module m6_boss() {
    translate([m6_x, m6_y, plate_t])
        cylinder(d = m6_boss_d, h = m6_boss_h);
}

module m6_cuts() {
    // M6 rod clearance through platform and boss.
    translate([m6_x, m6_y, -1])
        cylinder(d = m6_clearance_d, h = plate_t + m6_boss_h + 3);

    // Hex nut pocket from top of M6 boss.
    translate([
        m6_x,
        m6_y,
        plate_t + m6_boss_h - m6_nut_depth
    ])
        hex_prism_af(m6_nut_af, m6_nut_depth + 1);
}

module nut_retainer_holes_cut() {
    if (enable_nut_retainer_holes) {
        for (a = [0, 180]) {
            rotate([0, 0, a])
            translate([nut_retainer_spacing/2, 0, -1])
                cylinder(d = nut_retainer_hole_d, h = plate_t + m6_boss_h + 3);
        }
    }
}

module sample_pocket_cut() {
    // Shallow circular seat for sample cup / PTFE holder.
    translate([0, sample_y_offset, plate_t - sample_pocket_depth])
        cylinder(d = sample_pocket_d, h = sample_pocket_depth + 1);

    // Optional anti-rotation notches.
    if (enable_sample_notches) {
        for (a = [0, 90, 180, 270]) {
            rotate([0, 0, a])
            translate([
                sample_pocket_d/2 - sample_notch_l/2,
                sample_y_offset,
                plate_t - sample_notch_depth
            ])
                cube([
                    sample_notch_l,
                    sample_notch_w,
                    sample_notch_depth + 1
                ], center = true);
        }
    }
}

module skirt_mount_holes_cut() {
    for (a = [45, 135, 225, 315]) {
        x = skirt_mount_r * cos(a);
        y = sample_y_offset + skirt_mount_r * sin(a);

        translate([x, y, -1])
            cylinder(d = skirt_mount_hole_d, h = plate_t + 3);

        if (enable_skirt_recess) {
            translate([x, y, plate_t - skirt_recess_depth])
                cylinder(d = skirt_recess_d, h = skirt_recess_depth + 1);
        }
    }
}

module endstop_flag() {
    if (enable_endstop_flag) {
        translate([flag_x, flag_y, plate_t + flag_h/2])
            cube([flag_w, flag_d, flag_h], center = true);

        // Slight taller contact cap so the endstop has a clear target.
        translate([flag_x, flag_y, plate_t + flag_h + flag_contact_extra_h/2])
            cube([flag_w + 2, flag_d + 2, flag_contact_extra_h], center = true);
    }
}

module height_pointer() {
    if (enable_height_pointer) {
        // Plan-view triangular arrow protruding from +X side.
        // It prints flat as part of the plate.
        linear_extrude(height = pointer_h)
            polygon(points = [
                [plate_w/2 - 1, pointer_y - pointer_w/2],
                [plate_w/2 - 1, pointer_y + pointer_w/2],
                [plate_w/2 + pointer_len, pointer_y]
            ]);
    }
}

module accessory_holes_cut() {
    if (enable_accessory_holes) {
        for (x = [-accessory_x, accessory_x])
        for (y = [-accessory_y, accessory_y]) {
            translate([x, y, -1])
                cylinder(d = accessory_hole_d, h = plate_t + 3);
        }
    }
}

module alignment_marks_cut() {
    if (enable_alignment_marks) {
        // Mechanical drive centerline through rods.
        translate([0, 0, plate_t - mark_depth/2 + eps])
            cube([rod_spacing + 30, mark_w, mark_depth + 2*eps], center = true);

        // M6 screw axis line.
        translate([0, 0, plate_t - mark_depth/2 + eps])
            cube([mark_w, 40, mark_depth + 2*eps], center = true);

        // Sample optical center crosshair.
        translate([0, sample_y_offset, plate_t - mark_depth/2 + eps])
            cube([sample_pocket_d + 18, mark_w, mark_depth + 2*eps], center = true);

        translate([0, sample_y_offset, plate_t - mark_depth/2 + eps])
            cube([mark_w, sample_pocket_d + 18, mark_depth + 2*eps], center = true);
    }
}

// ---------------------------------------------------------
// Main model
// ---------------------------------------------------------

difference() {

    union() {
        // Main platform plate.
        rounded_plate(plate_w, plate_d, plate_t, corner_r);

        // LM8UU bearing housing bosses.
        bearing_boss(-rod_x, rod_y);
        bearing_boss( rod_x, rod_y);

        // Center M6 nut boss.
        m6_boss();

        // Endstop trigger flag.
        endstop_flag();

        // Height pointer.
        height_pointer();
    }

    // LM8UU bores and rod clearances.
    bearing_bore_cut(-rod_x, rod_y);
    bearing_bore_cut( rod_x, rod_y);

    // M6 center clearance and nut trap.
    m6_cuts();

    // Optional retainer holes around nut boss.
    nut_retainer_holes_cut();

    // Sample cup / PTFE holder pocket.
    sample_pocket_cut();

    // Mounting holes for moving telescoping skirt.
    skirt_mount_holes_cut();

    // Generic accessory holes.
    accessory_holes_cut();

    // Shallow alignment marks.
    alignment_marks_cut();
}