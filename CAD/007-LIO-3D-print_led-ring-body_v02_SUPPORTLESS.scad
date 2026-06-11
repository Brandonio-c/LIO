// Lio v0.2 — SUPPORTLESS 16-Slot LED Ring Body
// Units: millimeters
//
// FIXED FROM v01:
// - Cartridge slots are now OPEN-TOP pockets.
// - Removed raised text labels that can confuse slicers.
// - Removed horizontal clamp screw hole by default.
// - Ring should slice without "floating region" warnings.
//
// This part integrates:
// - LED ring structure
// - 16 open-top LED cartridge slots
// - M3 mounting holes
// - top wire-routing grooves
// - split gap / clamp ears
// - simple slot-index marks
//
// Print orientation:
// - Flat on bed
//
// Material:
// - PETG preferred
//
// Suggested print settings:
// - 0.20 mm layer height
// - 4 walls
// - 25–35% infill
// - supports OFF
// - brim optional

$fn = 160;
eps = 0.05;

// ---------------------------------------------------------
// Main ring dimensions
// ---------------------------------------------------------

ring_od = 125;          // outer diameter
ring_id = 83.0;         // clears 80 mm outer tube with ~1.5 mm radial clearance
ring_h  = 16;           // ring height

// ---------------------------------------------------------
// Split gap / clamp geometry
// ---------------------------------------------------------

enable_split_gap = true;
split_gap_w = 8;        // tangential gap width at +X side
split_gap_depth = (ring_od - ring_id) / 2 + 8;

enable_clamp_ears = true;
clamp_ear_w = 13;
clamp_ear_l = 13;
clamp_ear_h = ring_h;

// Horizontal clamp screw holes can cause small support warnings.
// Leave off for first print. Drill later if needed.
enable_horizontal_clamp_screw_hole = false;
clamp_screw_d = 3.4;
clamp_screw_z = ring_h / 2;

// ---------------------------------------------------------
// LED cartridge slots
// ---------------------------------------------------------

slot_count = 16;
slot_angle_step = 360 / slot_count;

// These are OPEN-TOP pockets.
// This is the important supportless fix.
slot_radial_depth = 23.5;
slot_tangent_w    = 9.8;

// Leave a thin bottom floor under the cartridge.
slot_floor_z = 2.4;

// Cut from slot_floor_z upward past the ring top.
// No roof remains, so no floating cantilever.
slot_cut_h = ring_h - slot_floor_z + 2.0;
slot_cut_z_center = slot_floor_z + slot_cut_h / 2;

// Slot radial center.
// Outer radius = ring_od/2.
// Slot cuts inward from outside.
slot_center_r = ring_od/2 - slot_radial_depth/2 + 0.5;

// Slight lead-in notch at outer edge so cartridges slide in easier.
enable_outer_leadin = true;
leadin_w = slot_tangent_w + 1.2;
leadin_depth = 4.0;

// ---------------------------------------------------------
// M3 mounting holes
// ---------------------------------------------------------

mount_bolt_circle_d = 104;
mount_r = mount_bolt_circle_d / 2;

m3_clearance_d = 3.4;
m3_head_recess_d = 6.6;
m3_head_recess_depth = 2.5;

// ---------------------------------------------------------
// Wire routing channels
// ---------------------------------------------------------

enable_wire_grooves = true;

// These are shallow top grooves only.
wire_groove_w = 3.2;
wire_groove_depth = 2.0;
wire_groove_len = 18;
wire_groove_center_r = ring_od/2 - 12;

// Optional outer circular race for LED wires.
// This is a shallow top recess.
enable_outer_wire_race = true;
wire_race_outer_d = ring_od - 5;
wire_race_inner_d = ring_od - 13;
wire_race_depth = 1.3;

// ---------------------------------------------------------
// Slot index marks
// ---------------------------------------------------------

enable_slot_index_marks = true;
index_mark_w = 1.2;
index_mark_l = 5.0;
index_mark_depth = 0.7;
index_mark_r = ring_od/2 - 4.0;

// Extra larger mark for slot 1.
enable_slot_1_marker = true;

// ---------------------------------------------------------
// Helper modules
// ---------------------------------------------------------

module ring(od, id, h) {
    difference() {
        cylinder(d = od, h = h);
        translate([0, 0, -1])
            cylinder(d = id, h = h + 2);
    }
}

module open_top_cartridge_slot_cut() {
    // Local coordinates:
    // X = radial direction
    // Y = tangential direction
    // Z = vertical
    //
    // This cuts an open-top rectangular tray.
    // It leaves bottom material from Z=0 to Z=slot_floor_z.
    translate([slot_center_r, 0, slot_cut_z_center])
        cube([slot_radial_depth + 2, slot_tangent_w, slot_cut_h], center = true);
}

module outer_leadin_cut() {
    if (enable_outer_leadin) {
        translate([ring_od/2 - leadin_depth/2 + eps, 0, slot_cut_z_center])
            cube([leadin_depth + 2*eps, leadin_w, slot_cut_h], center = true);
    }
}

module wire_groove_cut() {
    if (enable_wire_grooves) {
        translate([
            wire_groove_center_r,
            0,
            ring_h - wire_groove_depth/2 + eps
        ])
            cube([wire_groove_len, wire_groove_w, wire_groove_depth + 2*eps], center = true);
    }
}

module outer_wire_race_cut() {
    if (enable_outer_wire_race) {
        translate([0, 0, ring_h - wire_race_depth])
            difference() {
                cylinder(d = wire_race_outer_d, h = wire_race_depth + eps);
                translate([0, 0, -eps])
                    cylinder(d = wire_race_inner_d, h = wire_race_depth + 3*eps);
            }
    }
}

module m3_mount_holes_cut() {
    // Four vertical screw holes. These are safe/supportless.
    for (a = [45, 135, 225, 315]) {
        rotate([0, 0, a])
        translate([mount_r, 0, -1]) {
            cylinder(d = m3_clearance_d, h = ring_h + 2);

            // top screw-head recess
            translate([0, 0, ring_h - m3_head_recess_depth])
                cylinder(d = m3_head_recess_d, h = m3_head_recess_depth + 1.5);
        }
    }
}

module split_gap_cut() {
    if (enable_split_gap) {
        translate([ring_od/2 - split_gap_depth/2 + 1, 0, ring_h/2])
            cube([split_gap_depth + 4, split_gap_w, ring_h + 2], center = true);
    }
}

module clamp_ears() {
    if (enable_clamp_ears && enable_split_gap) {
        for (y = [-split_gap_w/2 - clamp_ear_w/2, split_gap_w/2 + clamp_ear_w/2]) {
            translate([ring_od/2 + clamp_ear_l/2 - 2, y, clamp_ear_h/2])
                cube([clamp_ear_l, clamp_ear_w, clamp_ear_h], center = true);
        }
    }
}

module horizontal_clamp_screw_hole_cut() {
    if (enable_horizontal_clamp_screw_hole && enable_clamp_ears && enable_split_gap) {
        translate([ring_od/2 + clamp_ear_l/2 - 2, 0, clamp_screw_z])
            rotate([90, 0, 0])
                cylinder(d = clamp_screw_d,
                         h = split_gap_w + 2*clamp_ear_w + 8,
                         center = true);
    }
}

module slot_index_mark_cut(i) {
    if (enable_slot_index_marks) {
        // Small shallow mark cut into top surface near each slot.
        translate([index_mark_r, 0, ring_h - index_mark_depth/2 + eps])
            cube([index_mark_l, index_mark_w, index_mark_depth + 2*eps], center = true);

        // Bigger orientation mark for slot 1.
        if (enable_slot_1_marker && i == 0) {
            translate([ring_od/2 - 9, 0, ring_h - 0.9/2 + eps])
                cube([9, 3.0, 0.9 + 2*eps], center = true);
        }
    }
}

// ---------------------------------------------------------
// Main model
// ---------------------------------------------------------

difference() {
    union() {
        // Main donut ring.
        ring(ring_od, ring_id, ring_h);

        // Solid clamp ears.
        clamp_ears();
    }

    // Re-cut center bore through full assembly, including any ear overlap.
    translate([0, 0, -1])
        cylinder(d = ring_id, h = ring_h + 3);

    // 16 open-top cartridge pockets.
    for (i = [0 : slot_count - 1]) {
        rotate([0, 0, i * slot_angle_step]) {
            open_top_cartridge_slot_cut();
            outer_leadin_cut();
            wire_groove_cut();
            slot_index_mark_cut(i);
        }
    }

    // M3 vertical mounting holes.
    m3_mount_holes_cut();

    // Top-side outer wire race.
    outer_wire_race_cut();

    // Split gap.
    split_gap_cut();

    // Optional horizontal clamp screw hole.
    horizontal_clamp_screw_hole_cut();
}