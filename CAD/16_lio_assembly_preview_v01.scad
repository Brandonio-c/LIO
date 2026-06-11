// Lio v0.1 — Assembly Preview / Sanity Check
// File: 16_lio_assembly_preview_v01.scad
// Units: millimeters
//
// THIS IS NOT A PRINTABLE PART.
//
// Purpose:
// - Show the full Lio assembly in operating orientation.
// - Verify that the moving telescoping skirt overlaps the fixed bottom receiver.
// - Verify that the sample cup axis lines up with the optical tube/detector axis.
// - Verify that the M6 drive axis does NOT pass through the sample cup.
// - Verify that the fixed tower frame ties the optical chamber to the Z-stage.
// - Let you simulate low/mid/high sample heights using stage_z.
//
// Use:
// - Change stage_z near the top.
// - Press F5 Preview.
// - Do not export this as a print STL.
// - Do not slice this file.
//
// Coordinate system:
// X = left/right
// Y = front/back
// Z = vertical
//
// Important axes:
// M6 drive axis:       X = 0, Y = 0
// left guide rod:      X = -45, Y = 0
// right guide rod:     X = +45, Y = 0
// optical/sample axis: X = 0, Y = +35

$fn = 96;
eps = 0.05;

// ---------------------------------------------------------
// MAIN VARIABLE TO TEST MOTION
// ---------------------------------------------------------
//
// Change this value and press F5.
// Recommended checks:
// stage_z = stage_z_min;
// stage_z = 35;
// stage_z = stage_z_max;

stage_z = 35;          // current moving-platform height above base top
stage_z_min = 15;
stage_z_max = 65;

show_ghost_positions = true;
show_telescoping_overlap = true;
show_axes = true;
show_clearance_warning = true;

// ---------------------------------------------------------
// Core coordinate logic
// ---------------------------------------------------------

rod_spacing = 90;
rod_x = rod_spacing / 2;

sample_y_offset = 35;      // optical/sample axis offset from M6 drive axis

// ---------------------------------------------------------
// Base / Z-stage dimensions
// ---------------------------------------------------------

base_w = 150;
base_d = 120;
base_t = 10;

top_bridge_w = 132;
top_bridge_d = 48;
top_bridge_t = 10;
top_bridge_z = 185;       // bottom Z of top guide bridge

rod_d = 8;
rod_z0 = base_t;
rod_z1 = top_bridge_z + top_bridge_t;

m6_d = 6;
m6_z0 = base_t;
m6_z1 = top_bridge_z + top_bridge_t;

// ---------------------------------------------------------
// Moving sample platform dimensions
// ---------------------------------------------------------

platform_w = 125;
platform_d = 135;
platform_t = 9;

platform_z = base_t + stage_z;
platform_top_z = platform_z + platform_t;

// Sample/cup placeholder
sample_cup_od = 44.2;
sample_cup_h = 8;
sample_surface_z = platform_top_z + sample_cup_h;

// ---------------------------------------------------------
// Moving telescoping skirt dimensions
// ---------------------------------------------------------

skirt_od = 58.5;
skirt_id = 46.0;

// From Print 13:
// flange_t 5.5 + lower neck 10 + transition 10 + main sleeve 55 = 80.5
skirt_total_h = 80.5;

skirt_bottom_z = platform_top_z;
skirt_top_z = skirt_bottom_z + skirt_total_h;

// ---------------------------------------------------------
// Fixed bottom collar / receiver dimensions
// ---------------------------------------------------------

collar_flange_od = 92;
collar_flange_t = 6;

receiver_len = 45;
receiver_od = 70;
receiver_id = 64.5;

// In installed orientation:
// collar flange is fixed at collar_flange_z.
// receiver sleeve points downward.
collar_flange_z = 125;

receiver_top_z = collar_flange_z;
receiver_bottom_z = collar_flange_z - receiver_len;

// ---------------------------------------------------------
// Fixed optical stack dimensions
// ---------------------------------------------------------

outer_tube_od = 80;
outer_tube_id = 60;
outer_tube_h = 100;

outer_tube_z0 = collar_flange_z + collar_flange_t;
outer_tube_z1 = outer_tube_z0 + outer_tube_h;

inner_sleeve_od = 58.4;
inner_sleeve_id = 54.0;
inner_sleeve_h = 90;
inner_sleeve_z0 = outer_tube_z0 + 5;

detector_cap_od = 92;
detector_cap_t = 7;
detector_cap_z0 = outer_tube_z1;

led_ring_od = 125;
led_ring_id = 83;
led_ring_h = 16;
led_ring_z0 = outer_tube_z0 + 62;

// ---------------------------------------------------------
// Fixed tower frame preview dimensions
// ---------------------------------------------------------

side_plate_spacing = 132;
side_plate_x = side_plate_spacing / 2;

side_plate_t = 7;
side_plate_depth = 80;
side_plate_h = 172;
side_plate_y_center = 18;     // spans approximately Y -22 to +58
side_plate_z0 = base_t;

saddle_t = 8;
saddle_ring_od = 104;
saddle_ring_id = 66;
saddle_z0 = collar_flange_z - saddle_t;

saddle_bridge_w = side_plate_spacing + 24;
saddle_bridge_d = 28;

// ---------------------------------------------------------
// Telescoping overlap computation
// ---------------------------------------------------------

overlap_bottom_z = max(receiver_bottom_z, skirt_bottom_z);
overlap_top_z = min(receiver_top_z, skirt_top_z);
telescoping_overlap = max(0, overlap_top_z - overlap_bottom_z);

echo("LIO ASSEMBLY PREVIEW");
echo("stage_z_mm", stage_z);
echo("platform_top_z_mm", platform_top_z);
echo("skirt_bottom_z_mm", skirt_bottom_z);
echo("skirt_top_z_mm", skirt_top_z);
echo("receiver_bottom_z_mm", receiver_bottom_z);
echo("receiver_top_z_mm", receiver_top_z);
echo("telescoping_overlap_mm", telescoping_overlap);

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

module box_at(x, y, z, sx, sy, sz) {
    translate([x, y, z + sz/2])
        cube([sx, sy, sz], center = true);
}

module cyl_at(x, y, z, d, h) {
    translate([x, y, z])
        cylinder(d = d, h = h);
}

module axis_line(x, y, z0, z1, d) {
    translate([x, y, z0])
        cylinder(d = d, h = z1 - z0);
}

// ---------------------------------------------------------
// Fixed Z-stage hardware preview
// ---------------------------------------------------------

module motor_base_preview() {
    color([0.35, 0.35, 0.35, 0.65]) {
        box_at(0, 0, 0, base_w, base_d, base_t);

        // lower guide rod socket towers
        cyl_at(-rod_x, 0, base_t, 20, 22);
        cyl_at( rod_x, 0, base_t, 20, 22);

        // central boss/coupler zone
        cyl_at(0, 0, base_t, 38, 4);
    }

    // approximate 28BYJ motor body
    color([0.15, 0.15, 0.15, 0.75]) {
        cyl_at(0, 0, -10, 30, 10);
    }
}

module guide_rods_preview() {
    color([0.75, 0.75, 0.75, 0.85]) {
        axis_line(-rod_x, 0, rod_z0, rod_z1, rod_d);
        axis_line( rod_x, 0, rod_z0, rod_z1, rod_d);
    }
}

module m6_screw_preview() {
    color([0.95, 0.72, 0.25, 0.9]) {
        axis_line(0, 0, m6_z0, m6_z1, m6_d);
    }
}

module top_guide_bridge_preview() {
    color([0.45, 0.45, 0.45, 0.65]) {
        box_at(0, 0, top_bridge_z, top_bridge_w, top_bridge_d, top_bridge_t);

        // rod bosses
        cyl_at(-rod_x, 0, top_bridge_z + top_bridge_t, 24, 8);
        cyl_at( rod_x, 0, top_bridge_z + top_bridge_t, 24, 8);

        // center boss
        cyl_at(0, 0, top_bridge_z + top_bridge_t, 38, 5);
    }
}

// ---------------------------------------------------------
// Moving stage preview
// ---------------------------------------------------------

module moving_stage_preview(stage, alpha = 0.75) {
    pz = base_t + stage;
    ptop = pz + platform_t;
    s_bottom = ptop;
    s_top = s_bottom + skirt_total_h;

    // moving platform
    color([0.1, 0.35, 1.0, alpha]) {
        box_at(0, 0, pz, platform_w, platform_d, platform_t);

        // LM8UU bearing bosses
        cyl_at(-rod_x, 0, ptop, 25, 32);
        cyl_at( rod_x, 0, ptop, 25, 32);

        // M6 nut boss
        cyl_at(0, 0, ptop, 24, 9);
    }

    // moving telescoping skirt
    color([0.0, 0.15, 0.8, alpha * 0.75]) {
        translate([0, sample_y_offset, s_bottom])
            ring(skirt_od, skirt_id, skirt_total_h);
    }

    // sample cup / PTFE placeholder
    color([0.95, 0.95, 0.85, alpha]) {
        cyl_at(0, sample_y_offset, ptop, sample_cup_od, sample_cup_h);
    }

    // height pointer / endstop flag approximations
    color([1.0, 0.25, 0.1, alpha]) {
        // endstop flag
        box_at(-55, -55, ptop, 9, 12, 22);

        // height pointer
        translate([platform_w/2 + 4, 42, pz + platform_t/2])
            cube([12, 10, platform_t], center = true);
    }
}

// ---------------------------------------------------------
// Fixed optical stack preview
// ---------------------------------------------------------

module fixed_bottom_collar_preview() {
    // receiver sleeve, installed pointing downward
    color([0.02, 0.02, 0.02, 0.50]) {
        translate([0, sample_y_offset, receiver_bottom_z])
            ring(receiver_od, receiver_id, receiver_len);
    }

    // flange
    color([0.02, 0.02, 0.02, 0.65]) {
        translate([0, sample_y_offset, collar_flange_z])
            ring(collar_flange_od, receiver_id, collar_flange_t);
    }
}

module outer_tube_preview() {
    color([0.02, 0.02, 0.02, 0.38]) {
        translate([0, sample_y_offset, outer_tube_z0])
            ring(outer_tube_od, outer_tube_id, outer_tube_h);
    }

    // inner sleeve
    color([0.0, 0.0, 0.0, 0.25]) {
        translate([0, sample_y_offset, inner_sleeve_z0])
            ring(inner_sleeve_od, inner_sleeve_id, inner_sleeve_h);
    }
}

module detector_cap_preview() {
    color([0.1, 0.1, 0.1, 0.65]) {
        cyl_at(0, sample_y_offset, detector_cap_z0, detector_cap_od, detector_cap_t);

        // detector snout preview
        cyl_at(0, sample_y_offset, detector_cap_z0 - 12, 18, 12);
    }
}

module led_ring_preview() {
    color([0.6, 0.15, 0.9, 0.45]) {
        translate([0, sample_y_offset, led_ring_z0])
            ring(led_ring_od, led_ring_id, led_ring_h);
    }
}

// ---------------------------------------------------------
// Fixed tower frame preview
// ---------------------------------------------------------

module fixed_tower_frame_preview() {
    // side plates
    color([0.0, 0.75, 0.25, 0.38]) {
        box_at(-side_plate_x, side_plate_y_center, side_plate_z0,
               side_plate_t, side_plate_depth, side_plate_h);

        box_at( side_plate_x, side_plate_y_center, side_plate_z0,
               side_plate_t, side_plate_depth, side_plate_h);
    }

    // optical saddle ring
    color([0.0, 0.75, 0.25, 0.55]) {
        translate([0, sample_y_offset, saddle_z0])
            ring(saddle_ring_od, saddle_ring_id, saddle_t);

        // bridge web between side plates
        box_at(0, sample_y_offset, saddle_z0,
               saddle_bridge_w, saddle_bridge_d, saddle_t);

        // rear stabilizer bridge near mechanical axis
        box_at(0, 0, saddle_z0,
               saddle_bridge_w * 0.72, 18, saddle_t);
    }
}

// ---------------------------------------------------------
// Telescoping overlap visualization
// ---------------------------------------------------------

module overlap_preview(stage) {
    pz = base_t + stage;
    ptop = pz + platform_t;
    s_bottom = ptop;
    s_top = s_bottom + skirt_total_h;

    lo = max(receiver_bottom_z, s_bottom);
    hi = min(receiver_top_z, s_top);
    oh = max(0, hi - lo);

    if (show_telescoping_overlap && oh > 0) {
        color([1.0, 0.0, 1.0, 0.45]) {
            // annular volume showing where moving skirt overlaps fixed receiver
            translate([0, sample_y_offset, lo])
                ring(receiver_id - 0.3, skirt_od + 0.3, oh);
        }
    }

    if (show_clearance_warning && oh < 20) {
        color([1.0, 0.0, 0.0, 0.55]) {
            // red warning disk above the receiver if overlap is too low
            translate([0, sample_y_offset, receiver_top_z + 3])
                cylinder(d = receiver_od + 8, h = 3);
        }
    }
}

// ---------------------------------------------------------
// Axis markers
// ---------------------------------------------------------

module axis_markers() {
    if (show_axes) {
        // M6 mechanical axis
        color([1.0, 0.85, 0.0, 0.45]) {
            axis_line(0, 0, 0, outer_tube_z1 + 20, 1.4);
        }

        // optical/sample axis
        color([0.0, 1.0, 1.0, 0.45]) {
            axis_line(0, sample_y_offset, 0, outer_tube_z1 + 20, 1.8);
        }

        // guide rod axis markers are already physical rods
    }
}

// ---------------------------------------------------------
// Travel ghost preview
// ---------------------------------------------------------

module travel_ghosts_preview() {
    if (show_ghost_positions) {
        // lowest platform ghost
        moving_stage_preview(stage_z_min, 0.18);

        // highest platform ghost
        moving_stage_preview(stage_z_max, 0.18);

        // overlap ghosts
        overlap_preview(stage_z_min);
        overlap_preview(stage_z_max);
    }
}

// ---------------------------------------------------------
// FULL ASSEMBLY
// ---------------------------------------------------------

module lio_assembly_preview() {

    // fixed foundation / frame
    motor_base_preview();
    guide_rods_preview();
    m6_screw_preview();
    top_guide_bridge_preview();

    // tower and optical stack
    fixed_tower_frame_preview();
    fixed_bottom_collar_preview();
    outer_tube_preview();
    led_ring_preview();
    detector_cap_preview();

    // ghost min/max positions first
    travel_ghosts_preview();

    // current active moving stage
    moving_stage_preview(stage_z, 0.82);
    overlap_preview(stage_z);

    // axis markers last
    axis_markers();
}

// Render preview
lio_assembly_preview();