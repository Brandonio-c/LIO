// Lio v0.1 — Top Detector Cap with Integrated Detector Snout
// Units: millimeters
//
// This part integrates:
// - top cap
// - central aperture
// - detector snout / field-of-view tube
// - OPT101 module pocket
// - dogleg wire exit groove / light trap
// - 4x M3 mounting holes matching the outer tube flange
//
// Physical role:
// - Screws onto the top flange of the fixed outer optical tube.
// - Centers the detector above the sample.
// - Narrows the detector's field of view so it mostly sees the sample,
//   not the LED ring or upper wall reflections.
//
// IMPORTANT PRINT NOTE:
// - This model is physically oriented as installed:
//      top side = sensor pocket
//      underside = plug lip + detector snout
// - Because the snout protrudes downward, you may need slicer supports.
// - Easiest first print: print as-is with supports enabled under the overhang.
// - If supports are ugly, later split the detector snout into a separate screw-in part.

$fn = 128;
eps = 0.05;

// ---------------------------------------------------------
// Main cap dimensions
// ---------------------------------------------------------

cap_od = 92;              // outer cap diameter; matches 88–92 mm tube flange range
cap_t  = 7;               // cap thickness

// Plug lip fits inside the outer tube bore.
// Your outer tube inner bore was 60 mm, so use ~58.8–59.0 mm.
plug_lip_d = 58.8;
plug_lip_h = 4.0;

// ---------------------------------------------------------
// Detector aperture / snout
// ---------------------------------------------------------

aperture_d = 6.5;         // central viewing aperture, 5–8 mm recommended
snout_outer_d = 18;       // outside diameter of detector snout
snout_inner_d = aperture_d;
snout_len = 12;           // 10–15 mm recommended

// Extra flare/strength at snout base
snout_base_d = 24;
snout_base_h = 3;

// ---------------------------------------------------------
// OPT101 module pocket
// ---------------------------------------------------------
//
// Common CJMCU-101 OPT101 modules are often around 25 x 17 mm,
// but cheap modules vary. Measure your actual board.
// This pocket is intentionally oversized.

pcb_pocket_w = 28;
pcb_pocket_d = 22;
pcb_pocket_depth = 2.2;
pcb_corner_r = 2.0;

// Optional PCB retention screw holes.
// These are small pilot/clearance holes for M2-ish screws or printed pegs.
// Disable if you do not want them.
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

mount_bolt_circle_d = 74;     // must match outer tube m3_bolt_circle_d
mount_r = mount_bolt_circle_d / 2;

// ---------------------------------------------------------
// Dogleg wire exit groove
// ---------------------------------------------------------
//
// This is a shallow groove on the TOP side of the cap.
// It does NOT cut all the way through into the optical chamber.
// The dogleg shape avoids a straight outside-to-detector light path.

wire_channel_w = 5.0;
wire_channel_depth = 2.4;

// Channel path coordinates on top surface.
// Starts near PCB pocket, jogs sideways, then exits cap edge.
wire_start_x = pcb_pocket_w/2 - 2;
wire_start_y = 0;

wire_mid1_x = 28;
wire_mid1_y = 0;

wire_mid2_x = 28;
wire_mid2_y = 18;

wire_exit_x = cap_od/2 + 2;
wire_exit_y = 18;

// ---------------------------------------------------------
// Optional alignment mark
// ---------------------------------------------------------

enable_alignment_mark = true;
alignment_mark_w = 3;
alignment_mark_l = 10;
alignment_mark_depth = 1.0;

// ---------------------------------------------------------
// Helper modules
// ---------------------------------------------------------

module rounded_rect_2d(w, d, r) {
    // 2D rounded rectangle centered on origin.
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

module dogleg_channel_cut() {
    // Shallow top groove made from three rectangular segments.
    // All cuts start from the top face and go downward by wire_channel_depth.

    z0 = cap_t - wire_channel_depth;

    // Segment 1: from PCB pocket to first bend
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

    // Segment 2: vertical jog
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

    // Segment 3: from second bend to edge
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

module m3_mount_holes() {
    for (a = [0, 90, 180, 270]) {
        rotate([0, 0, a])
        translate([mount_r, 0, -snout_len - plug_lip_h - 1]) {

            // Through clearance hole
            cylinder(d = m3_clearance_d,
                     h = cap_t + snout_len + plug_lip_h + 4);

            // Top screw-head recess
            translate([0, 0, snout_len + plug_lip_h + cap_t - m3_head_recess_depth + 1])
                cylinder(d = m3_head_recess_d,
                         h = m3_head_recess_depth + 1.5);
        }
    }
}

module pcb_mount_holes() {
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
        // Small shallow notch on top edge at +Y.
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

// ---------------------------------------------------------
// Main model
// ---------------------------------------------------------

difference() {

    union() {

        // Main cap disk
        cylinder(d = cap_od, h = cap_t);

        // Underside plug lip.
        // This centers the cap inside the outer optical tube.
        translate([0, 0, -plug_lip_h])
            cylinder(d = plug_lip_d, h = plug_lip_h);

        // Snout base reinforcement under the cap
        translate([0, 0, -snout_base_h])
            cylinder(d = snout_base_d, h = snout_base_h);

        // Detector snout tube extending downward into optical chamber
        translate([0, 0, -snout_len])
            cylinder(d = snout_outer_d, h = snout_len);
    }

    // Central optical aperture through cap, plug lip, and snout
    translate([0, 0, -snout_len - 1])
        cylinder(d = aperture_d, h = cap_t + snout_len + 3);

    // Hollow the inside of snout using same aperture diameter
    // already handled by central aperture cut.

    // OPT101 PCB pocket on the top face
    translate([0, 0, cap_t - pcb_pocket_depth])
        rounded_box_cut(
            w = pcb_pocket_w,
            d = pcb_pocket_d,
            h = pcb_pocket_depth + 1,
            r = pcb_corner_r
        );

    // PCB mounting/pilot holes
    pcb_mount_holes();

    // Dogleg wire exit groove on top face
    dogleg_channel_cut();

    // 4x M3 mounting holes and screw-head recesses
    m3_mount_holes();

    // Optional alignment notch
    alignment_mark_cut();
}

// ---------------------------------------------------------
// Optional visual reference: centerline marker on top
// Comment this out if you want a perfectly plain top.
// ---------------------------------------------------------

// Small raised rim around aperture on top side.
// This helps visually locate the detector aperture and gives the sensor PCB a seat.
// It does not block the aperture.
rim_od = 11;
rim_id = aperture_d + 1.0;
rim_h = 0.8;

translate([0, 0, cap_t])
difference() {
    cylinder(d = rim_od, h = rim_h);
    translate([0, 0, -eps])
        cylinder(d = rim_id, h = rim_h + 2 * eps);
}