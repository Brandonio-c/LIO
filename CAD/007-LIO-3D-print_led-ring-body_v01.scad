// Lio v0.1 — 16-Slot LED Ring Body
// Units: millimeters
//
// This part integrates:
// - LED ring structure
// - 16 removable LED cartridge slots
// - M3 mounting holes
// - wire routing channels
// - outer labeling positions
// - split/clamp gap so the ring can be installed around the outer tube
//
// IMPORTANT:
// - This ring does NOT directly hold every LED.
// - It holds removable LED cartridges/wedges.
// - LED cartridges will handle 3mm, 5mm, SMD, or TO-can emitters later.
// - This lets you revise LED geometry without reprinting the whole ring.
//
// Print orientation:
// - Flat on bed
//
// Material:
// - PETG preferred
//
// Recommended print settings:
// - 0.20 mm layer height
// - 4 walls
// - 25–35% infill
// - supports off if possible
// - brim optional

$fn = 160;
eps = 0.05;

// ---------------------------------------------------------
// Main ring dimensions
// ---------------------------------------------------------

ring_od = 125;          // outer diameter, suggested 115–130 mm
ring_id = 83.0;         // clears 80 mm outer tube with ~1.5 mm radial clearance
ring_h  = 16;           // ring thickness/height, suggested 12–18 mm

// Split gap so ring can flex/clamp around tube instead of sliding over flanges.
enable_split_gap = true;
split_gap_w = 8;        // tangential gap width at +X side
split_gap_depth = (ring_od - ring_id) / 2 + 8;

// ---------------------------------------------------------
// LED cartridge slots
// ---------------------------------------------------------

slot_count = 16;
slot_angle_step = 360 / slot_count;

// Slot receives a removable LED cartridge/wedge.
slot_radial_depth = 23;       // how far slot cuts inward from outside
slot_tangent_w    = 9.5;      // cartridge slot width tangent to ring
slot_h            = 10.5;     // vertical pocket height
slot_z_center     = ring_h/2;

// Slot radial center position.
// Outer radius = ring_od/2. Slot starts at outside and cuts inward.
slot_center_r = ring_od/2 - slot_radial_depth/2 + 0.5;

// Cartridge retention screw/pin holes.
// These are optional small radial M3 clearance holes through each slot wall.
enable_cartridge_retention_holes = true;
retention_hole_d = 3.2;
retention_hole_r = ring_od/2 - 7;
retention_hole_z = ring_h/2;

// ---------------------------------------------------------
// Mounting holes to attach LED ring to outer tube / brackets
// ---------------------------------------------------------

mount_hole_count = 4;
mount_bolt_circle_d = 104;     // outside tube/flange but inside ring OD
mount_r = mount_bolt_circle_d / 2;

m3_clearance_d = 3.4;
m3_head_recess_d = 6.6;
m3_head_recess_depth = 2.5;

// ---------------------------------------------------------
// Wire routing channels
// ---------------------------------------------------------

// Shallow top-side radial grooves from each cartridge slot toward outer edge.
// These are not full through-cuts; they help route LED wires.
enable_wire_grooves = true;

wire_groove_w = 3.2;
wire_groove_depth = 2.0;      // shallow groove cut downward from top
wire_groove_len = 17;
wire_groove_center_r = ring_od/2 - 12;

// Larger external circumferential wire race groove around outer top edge.
// Useful for collecting LED wires.
enable_outer_wire_race = true;
wire_race_outer_d = ring_od - 5;
wire_race_inner_d = ring_od - 13;
wire_race_depth = 1.5;

// ---------------------------------------------------------
// Label pads
// ---------------------------------------------------------

enable_label_pads = true;
label_pad_w = 11;           // tangent width
label_pad_radial = 7;       // radial depth
label_pad_h = 0.8;          // raised pad height
label_pad_r = ring_od/2 + 1.5;

enable_number_labels = true;
label_text_size = 3.2;
label_text_depth = 0.55;

// ---------------------------------------------------------
// Clamp ears around split gap
// ---------------------------------------------------------

enable_clamp_ears = true;
clamp_ear_w = 13;       // tangent/side dimension
clamp_ear_l = 13;       // outward radial dimension
clamp_ear_h = ring_h;
clamp_screw_d = 3.4;    // M3 clearance
clamp_screw_z = ring_h/2;

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

// Rounded-ish rectangular slot cutter.
// In local coordinates:
// X = radial direction
// Y = tangential direction
// Z = vertical
module cartridge_slot_cut() {
    translate([slot_center_r, 0, slot_z_center])
        cube([slot_radial_depth + 2, slot_tangent_w, slot_h], center = true);
}

// Small radial retention hole for one slot.
// Hole axis points along local X/radial direction.
module cartridge_retention_hole_cut() {
    if (enable_cartridge_retention_holes) {
        translate([retention_hole_r, 0, retention_hole_z])
            rotate([0, 90, 0])
                cylinder(d = retention_hole_d, h = 18, center = true);
    }
}

// Top-side shallow radial wire groove for one slot.
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

// Outer circumferential wire race on top.
// This is an annular shallow recess, not a through-cut.
module outer_wire_race_cut() {
    if (enable_outer_wire_race) {
        translate([0, 0, ring_h - wire_race_depth])
            difference() {
                cylinder(d = wire_race_outer_d, h = wire_race_depth + eps);
                translate([0,0,-eps])
                    cylinder(d = wire_race_inner_d, h = wire_race_depth + 3*eps);
            }
    }
}

// Four M3 mount holes through ring.
module mount_holes_cut() {
    for (a = [45, 135, 225, 315]) {
        rotate([0, 0, a])
        translate([mount_r, 0, -1]) {
            cylinder(d = m3_clearance_d, h = ring_h + 2);

            // top screw-head recess
            translate([0, 0, ring_h - m3_head_recess_depth])
                cylinder(d = m3_head_recess_d, h = m3_head_recess_depth + 1);
        }
    }
}

// Split gap at +X side.
// Makes the ring installable around the tube rather than sliding over flanges.
module split_gap_cut() {
    if (enable_split_gap) {
        translate([ring_od/2 - split_gap_depth/2 + 1, 0, ring_h/2])
            cube([split_gap_depth + 4, split_gap_w, ring_h + 2], center = true);
    }
}

// Clamp ears on either side of split gap.
module clamp_ears() {
    if (enable_clamp_ears && enable_split_gap) {
        // two ears at +X, one above and one below the gap in Y
        for (y = [-split_gap_w/2 - clamp_ear_w/2, split_gap_w/2 + clamp_ear_w/2]) {
            translate([ring_od/2 + clamp_ear_l/2 - 2, y, clamp_ear_h/2])
                cube([clamp_ear_l, clamp_ear_w, clamp_ear_h], center = true);
        }
    }
}

// Screw hole through clamp ears, tangentially across gap.
// Axis runs along Y.
module clamp_screw_hole_cut() {
    if (enable_clamp_ears && enable_split_gap) {
        translate([ring_od/2 + clamp_ear_l/2 - 2, 0, clamp_screw_z])
            rotate([90, 0, 0])
                cylinder(d = clamp_screw_d, h = split_gap_w + 2*clamp_ear_w + 8, center = true);
    }
}

// Raised label pad for one slot.
// This is outside the ring edge so it doesn't interfere with cartridge pockets.
module label_pad(i) {
    if (enable_label_pads) {
        translate([label_pad_r, 0, ring_h])
            cube([label_pad_radial, label_pad_w, label_pad_h], center = true);

        if (enable_number_labels) {
            translate([label_pad_r, 0, ring_h + label_pad_h])
                linear_extrude(height = label_text_depth)
                    text(str(i + 1),
                         size = label_text_size,
                         font = "Liberation Sans:style=Bold",
                         halign = "center",
                         valign = "center");
        }
    }
}

// ---------------------------------------------------------
// Main model
// ---------------------------------------------------------

difference() {
    union() {
        // Main donut ring
        ring(ring_od, ring_id, ring_h);

        // Clamp ears
        clamp_ears();

        // Raised label pads outside each slot
        for (i = [0 : slot_count - 1]) {
            rotate([0, 0, i * slot_angle_step])
                label_pad(i);
        }
    }

    // 16 cartridge slots
    for (i = [0 : slot_count - 1]) {
        rotate([0, 0, i * slot_angle_step]) {
            cartridge_slot_cut();
            cartridge_retention_hole_cut();
            wire_groove_cut();
        }
    }

    // Central bore already cut inside ring() but clamp ears may extend;
    // cut the bore again through the full assembly to ensure clearance.
    translate([0, 0, -1])
        cylinder(d = ring_id, h = ring_h + label_pad_h + label_text_depth + 4);

    // 4 M3 mounting holes
    mount_holes_cut();

    // Top outer wire race
    outer_wire_race_cut();

    // Split gap
    split_gap_cut();

    // Clamp screw hole
    clamp_screw_hole_cut();
}

// ---------------------------------------------------------
// Optional orientation mark
// ---------------------------------------------------------

// Small raised triangle/marker at slot 1 location.
// Helps you keep LED channel ordering consistent.
orientation_marker_h = 1.0;
orientation_marker_r = ring_od/2 - 5;

translate([orientation_marker_r, 0, ring_h])
linear_extrude(height = orientation_marker_h)
    polygon(points = [
        [0, 4],
        [-3, -3],
        [3, -3]
    ]);