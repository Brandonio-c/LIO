// Lio v2.1 Lean - Assembly Preview / Sanity Check
// File: V2_18_assembly_preview_v21_lean.scad
// Units: millimeters
//
// THIS FILE IS NOT FOR PRINTING.
//
// Purpose:
// - Simplified v2.1 assembly preview.
// - Keeps the good v2 architecture: centered optical axis, four guide rods,
//   two side M6 lead screws, two 28BYJ motors, true telescoping light seal.
// - Removes the bulky protruding drawer and replaces it with a small front hatch/plug.
// - Reduces base height/material versus the earlier v2 motor-box preview.
// - Keeps the center sample area clean and accessible.
// - Assumes reuse of old optical stack where possible: outer tube, detector cap,
//   LED ring/cartridges, sample accessories.
//
// Use:
// - Open in OpenSCAD.
// - Press F5 Preview.
// - Change stage_z near the top to test load/scan positions.
// - Do NOT export this whole file as a printable STL.
//
// Coordinate system:
// X = left/right
// Y = front/back; front/loading side is negative Y
// Z = vertical
//
// V2.1 axes:
// Optical/sample axis: X = 0,   Y = 0
// Left lead screw:     X = -60, Y = 0
// Right lead screw:    X = +60, Y = 0
// Guide rods:          X = +/-78, Y = +/-52

$fn = 96;
eps = 0.05;

// =========================================================
// MAIN MOTION TEST PARAMETER
// =========================================================
// Suggested checks:
// stage_z = stage_z_load;
// stage_z = stage_z_min;
// stage_z = 40;
// stage_z = stage_z_max;

stage_z = 40;
stage_z_load = 8;
stage_z_min = 20;
stage_z_max = 52;

show_ghost_positions = true;
show_load_position = true;
show_overlap_zone = true;
show_axes = true;
show_keepout_zone = true;
show_hatch_open_ghost = true;
show_labels = false;

// =========================================================
// GLOBAL LAYOUT - LEAN V2.1
// =========================================================

sample_x = 0;
sample_y = 0;

lead_screw_x = 60;
lead_screw_y = 0;

rod_x = 78;
rod_y = 52;

// Lean low-profile base. Motors are inside local pockets, not under the table.
base_w = 190;
base_d = 150;
base_h = 32;
base_top_deck_t = 8;
base_bottom_cover_t = 4;
base_wall_t = 4;

// Shorter overall frame than bulky v2 preview.
top_plate_w = 190;
top_plate_d = 150;
top_plate_t = 10;
top_plate_z = 175;

side_panel_t = 6;
side_panel_h = top_plate_z + top_plate_t - base_h;
side_panel_z0 = base_h;
side_panel_x = base_w/2 + side_panel_t/2;

// Rods and screws.
smooth_rod_d = 8;
m6_screw_d = 6;

rod_z0 = base_h;
rod_z1 = top_plate_z + top_plate_t;

m6_z0 = 6;
m6_z1 = top_plate_z + top_plate_t + 10;

// Motors/couplers.
motor_body_d = 28;
motor_body_h = 18;
motor_body_offset_y = -8;      // body center relative to shaft axis
motor_z0 = 5;                  // inside low base
motor_shaft_d = 5;

coupler_d = 20;
coupler_h = 25;
coupler_z0 = base_h - 11;      // coupler rises through/above deck
coupler_well_d = 34;
coupler_well_h = 34;

// Moving carriage: simplified, no drawer rails.
carriage_w = 152;
carriage_d = 112;
carriage_t = 10;

bearing_boss_d = 22;
bearing_boss_h = 16;

nut_block_w = 26;
nut_block_d = 22;
nut_block_h = 12;

// Sample cup area.
sample_cup_od = 44;
sample_cup_h = 8;
sample_pocket_d = 48;

// =========================================================
// TRUE NON-CONTACT TELESCOPING LIGHT SEAL
// =========================================================
// The rods guide the motion. The telescope blocks light.
// It should not be a friction-fit guide.

moving_sleeve_od = 63.5;
moving_sleeve_id = 52.0;
moving_sleeve_h = 80;
moving_sleeve_flange_od = 86;
moving_sleeve_flange_t = 6;

// Lead-in: reduced OD at top of moving sleeve.
moving_sleeve_leadin_h = 6;
moving_sleeve_top_od = 61.5;

// Small lower front loading window. No big drawer.
moving_sleeve_window_w = 58;
moving_sleeve_window_h = 32;
moving_sleeve_window_bottom = 0;

// Fixed receiver: bigger clearance and flared mouth.
fixed_receiver_id = 69.0;
fixed_receiver_od = 80.0;
fixed_receiver_len = 78;
fixed_receiver_flange_od = 104;
fixed_receiver_flange_t = 7;

receiver_mouth_h = 6;
fixed_receiver_mouth_id = 73.0;

receiver_top_z = top_plate_z;
receiver_bottom_z = receiver_top_z - fixed_receiver_len;

min_required_overlap = 35;
min_required_top_clearance = 5;

// =========================================================
// SMALL FRONT HATCH / LIGHT PLUG
// =========================================================
// Replaces the earlier oversized protruding drawer.

hatch_w = 64;
hatch_h = 36;
hatch_t = 4;
hatch_handle_w = 28;
hatch_handle_d = 8;
hatch_handle_h = 10;

// Hatch sits just outside the moving sleeve front window.
hatch_y = -moving_sleeve_od/2 - hatch_t/2 - 0.8;
hatch_z_offset = moving_sleeve_flange_t + 18;

// Open ghost position for showing access.
hatch_open_pull = 32;

// =========================================================
// REUSED OPTICAL STACK PREVIEW
// =========================================================
// These represent v1 parts we want to reuse where possible.

outer_tube_od = 80;
outer_tube_id = 60;
outer_tube_h = 100;
outer_tube_z0 = top_plate_z + top_plate_t;

inner_sleeve_od = 58.4;
inner_sleeve_id = 54.0;
inner_sleeve_h = 76;      // shortened to avoid end interference
inner_sleeve_z0 = outer_tube_z0 + 8;

led_ring_od = 125;
led_ring_id = 83;
led_ring_h = 16;
led_ring_z0 = outer_tube_z0 + 62;

detector_cap_od = 92;
detector_cap_t = 7;
detector_cap_z0 = outer_tube_z0 + outer_tube_h;

detector_snout_od = 18;
detector_snout_h = 12;

central_keepout_d = 92;

// =========================================================
// DERIVED MOTION FUNCTIONS
// =========================================================

function carriage_bottom_z(s) = base_h + s;
function carriage_top_z(s) = carriage_bottom_z(s) + carriage_t;
function moving_sleeve_bottom_z(s) = carriage_top_z(s);
function moving_sleeve_top_z(s) = moving_sleeve_bottom_z(s) + moving_sleeve_h;
function overlap_bottom_z(s) = max(receiver_bottom_z, moving_sleeve_bottom_z(s));
function overlap_top_z(s) = min(receiver_top_z, moving_sleeve_top_z(s));
function telescope_overlap(s) = max(0, overlap_top_z(s) - overlap_bottom_z(s));
function telescope_top_clearance(s) = receiver_top_z - moving_sleeve_top_z(s);

// Echo diagnostic values.
echo("LIO V2.1 LEAN ASSEMBLY PREVIEW");
echo("stage_z_mm", stage_z);
echo("stage_z_load_mm", stage_z_load);
echo("stage_z_min_scan_mm", stage_z_min);
echo("stage_z_max_scan_mm", stage_z_max);
echo("current_overlap_mm", telescope_overlap(stage_z));
echo("min_scan_overlap_mm", telescope_overlap(stage_z_min));
echo("max_scan_overlap_mm", telescope_overlap(stage_z_max));
echo("current_top_clearance_mm", telescope_top_clearance(stage_z));
echo("max_scan_top_clearance_mm", telescope_top_clearance(stage_z_max));
echo("fixed_receiver_id_mm", fixed_receiver_id);
echo("moving_sleeve_od_mm", moving_sleeve_od);
echo("raw_diameter_clearance_mm", fixed_receiver_id - moving_sleeve_od);
echo("raw_radial_clearance_mm", (fixed_receiver_id - moving_sleeve_od)/2);

// =========================================================
// HELPERS
// =========================================================

module box_centered(x, y, z, sx, sy, sz) {
    translate([x, y, z + sz/2])
        cube([sx, sy, sz], center = true);
}

module cyl_z(x, y, z, d, h) {
    translate([x, y, z])
        cylinder(d = d, h = h);
}

module ring(od, id, h) {
    difference() {
        cylinder(d = od, h = h);
        translate([0, 0, -1])
            cylinder(d = id, h = h + 2);
    }
}

module ring_at(x, y, z, od, id, h) {
    translate([x, y, z])
        ring(od, id, h);
}

module tapered_outer_ring(od1, od2, id, h) {
    difference() {
        cylinder(d1 = od1, d2 = od2, h = h);
        translate([0, 0, -1])
            cylinder(d = id, h = h + 2);
    }
}

module tapered_inner_receiver_ring(od, id_bottom, id_top, h) {
    difference() {
        cylinder(d = od, h = h);
        translate([0, 0, -1])
            cylinder(d1 = id_bottom, d2 = id_top, h = h + 2);
    }
}

module windowed_ring(od, id, h, window_w, window_h, window_bottom) {
    difference() {
        ring(od, id, h);
        // Front access cutout at negative Y.
        translate([0, -od/2, window_bottom + window_h/2])
            cube([window_w, od + 8, window_h], center = true);
    }
}

module label_3d(txt, x, y, z, size = 5) {
    if (show_labels) {
        color([0, 0, 0, 1])
        translate([x, y, z])
            linear_extrude(height = 0.4)
                text(txt,
                     size = size,
                     font = "Liberation Sans:style=Bold",
                     halign = "center",
                     valign = "center");
    }
}

// =========================================================
// LEAN BASE / MOTOR AREA
// =========================================================

module base_preview() {
    // Thin top deck.
    color([0.28, 0.28, 0.28, 0.70])
        box_centered(0, 0, base_h - base_top_deck_t, base_w, base_d, base_top_deck_t);

    // Thin bottom cover / floor.
    color([0.18, 0.18, 0.18, 0.55])
        box_centered(0, 0, 0, base_w, base_d, base_bottom_cover_t);

    // Perimeter walls/ribs instead of solid block.
    color([0.30, 0.30, 0.30, 0.45]) {
        // front and rear rails
        box_centered(0, -base_d/2 + base_wall_t/2, base_bottom_cover_t,
                     base_w, base_wall_t, base_h - base_bottom_cover_t);
        box_centered(0,  base_d/2 - base_wall_t/2, base_bottom_cover_t,
                     base_w, base_wall_t, base_h - base_bottom_cover_t);
        // left and right rails
        box_centered(-base_w/2 + base_wall_t/2, 0, base_bottom_cover_t,
                     base_wall_t, base_d, base_h - base_bottom_cover_t);
        box_centered( base_w/2 - base_wall_t/2, 0, base_bottom_cover_t,
                     base_wall_t, base_d, base_h - base_bottom_cover_t);
    }

    // Local motor/coupler wells only, not a giant block.
    for (sx = [-lead_screw_x, lead_screw_x]) {
        color([0.05, 0.05, 0.05, 0.35])
            cyl_z(sx, lead_screw_y, base_h - coupler_well_h, coupler_well_d, coupler_well_h);
    }

    label_3d("lean base", 0, -base_d/2 - 10, base_h + 2, 5);
}

module byj_motor_preview(x, y) {
    body_x = x;
    body_y = y + motor_body_offset_y;

    // Motor body inside low base.
    color([0.75, 0.75, 0.75, 0.75])
        cyl_z(body_x, body_y, motor_z0, motor_body_d, motor_body_h);

    // Motor face disk.
    color([0.95, 0.95, 0.95, 0.80])
        cyl_z(body_x, body_y, motor_z0 + motor_body_h, motor_body_d * 0.82, 1.2);

    // Blue connector.
    color([0.0, 0.25, 0.9, 0.75])
        box_centered(body_x, body_y - 17, motor_z0 + 2, 16, 8, 12);

    // Motor tabs.
    color([0.8, 0.8, 0.8, 0.65]) {
        box_centered(body_x - 17.5, body_y, motor_z0 + 7, 12, 6, 2);
        box_centered(body_x + 17.5, body_y, motor_z0 + 7, 12, 6, 2);
    }

    // Shaft centered on lead-screw axis.
    color([0.95, 0.72, 0.25, 0.95])
        cyl_z(x, y, motor_z0 + motor_body_h, motor_shaft_d,
              base_h - (motor_z0 + motor_body_h) + 4);

    // Coupler.
    color([0.70, 0.70, 0.72, 0.85])
        cyl_z(x, y, coupler_z0, coupler_d, coupler_h);
}

module motors_and_couplers_preview() {
    byj_motor_preview(-lead_screw_x, lead_screw_y);
    byj_motor_preview( lead_screw_x, lead_screw_y);
}

// =========================================================
// RODS AND SCREWS
// =========================================================

rod_positions = [
    [-rod_x, -rod_y],
    [ rod_x, -rod_y],
    [-rod_x,  rod_y],
    [ rod_x,  rod_y]
];

module guide_rods_preview() {
    color([0.75, 0.75, 0.75, 0.9]) {
        for (p = rod_positions) {
            cyl_z(p[0], p[1], rod_z0, smooth_rod_d, rod_z1 - rod_z0);
        }
    }

    // Lower rod sockets.
    color([0.05, 0.05, 0.05, 0.75]) {
        for (p = rod_positions) {
            cyl_z(p[0], p[1], base_h, 20, 20);
        }
    }
}

module lead_screws_preview() {
    color([0.95, 0.72, 0.25, 0.9]) {
        cyl_z(-lead_screw_x, lead_screw_y, m6_z0, m6_screw_d, m6_z1 - m6_z0);
        cyl_z( lead_screw_x, lead_screw_y, m6_z0, m6_screw_d, m6_z1 - m6_z0);
    }
}

// =========================================================
// SIDE PANELS AND TOP PLATE
// =========================================================

module side_panel_with_window(xpos) {
    color([0.0, 0.75, 0.25, 0.18])
    difference() {
        box_centered(xpos, 0, side_panel_z0, side_panel_t, base_d, side_panel_h);
        // Large window/cutout to reduce material and leave access.
        translate([xpos, 0, side_panel_z0 + side_panel_h/2])
            cube([side_panel_t + 2, base_d - 34, side_panel_h - 48], center = true);
    }
}

module side_panels_preview() {
    side_panel_with_window(-side_panel_x);
    side_panel_with_window( side_panel_x);
}

module top_plate_preview() {
    color([0.45, 0.45, 0.45, 0.62])
        box_centered(0, 0, top_plate_z, top_plate_w, top_plate_d, top_plate_t);

    // Central optical opening preview.
    color([0.0, 0.0, 0.0, 0.35])
        cyl_z(0, 0, top_plate_z - 1, 78, top_plate_t + 2);

    // Rod top sockets.
    color([0.1, 0.1, 0.1, 0.50]) {
        for (p = rod_positions) {
            cyl_z(p[0], p[1], top_plate_z - 3, 20, 16);
        }
    }

    // M6 screw clearances.
    color([0.1, 0.1, 0.1, 0.45]) {
        cyl_z(-lead_screw_x, 0, top_plate_z - 2, 14, top_plate_t + 4);
        cyl_z( lead_screw_x, 0, top_plate_z - 2, 14, top_plate_t + 4);
    }

    label_3d("top plate", 0, top_plate_d/2 + 8, top_plate_z + top_plate_t + 2, 5);
}

// =========================================================
// MOVING SAMPLE PLATE - SIMPLIFIED
// =========================================================

module moving_carriage_preview(s, alpha = 0.75) {
    cz = carriage_bottom_z(s);
    ctop = carriage_top_z(s);

    // Single clean moving plate.
    color([0.05, 0.25, 1.0, alpha])
        box_centered(0, 0, cz, carriage_w, carriage_d, carriage_t);

    // Centered sample pocket.
    color([0.8, 0.95, 1.0, alpha * 0.55])
        cyl_z(0, 0, ctop, sample_pocket_d, 4);

    // Bearing/bushing bosses at four rods.
    color([0.02, 0.12, 0.65, alpha]) {
        for (p = rod_positions) {
            cyl_z(p[0], p[1], ctop, bearing_boss_d, bearing_boss_h);
        }
    }

    // Floating nut blocks at two screws.
    color([0.0, 0.1, 0.55, alpha]) {
        box_centered(-lead_screw_x, 0, ctop, nut_block_w, nut_block_d, nut_block_h);
        box_centered( lead_screw_x, 0, ctop, nut_block_w, nut_block_d, nut_block_h);
    }

    // Sample cup placeholder drops into the center pocket.
    color([0.95, 0.95, 0.82, alpha])
        cyl_z(0, 0, ctop + 2, sample_cup_od, sample_cup_h);

    // Simple endstop flag.
    color([1.0, 0.1, 0.05, alpha])
        box_centered(-carriage_w/2 + 8, -carriage_d/2 + 12, ctop, 8, 18, 24);
}

// =========================================================
// SMALL FRONT HATCH / PLUG
// =========================================================

module front_hatch_preview(s, open = false, alpha = 0.85) {
    ctop = carriage_top_z(s);
    zc = ctop + hatch_z_offset;
    y = hatch_y - (open ? hatch_open_pull : 0);

    // Black plate covering the sleeve's front window.
    color([0.02, 0.02, 0.02, alpha])
        box_centered(0, y, zc - hatch_h/2, hatch_w, hatch_t, hatch_h);

    // Small handle only, not a giant drawer.
    color([0.1, 0.1, 0.1, alpha])
        box_centered(0, y - hatch_t/2 - hatch_handle_d/2,
                     zc - hatch_h/2 + hatch_handle_h/2,
                     hatch_handle_w, hatch_handle_d, hatch_handle_h);
}

// =========================================================
// TELESCOPING SLEEVE SYSTEM
// =========================================================

module moving_telescoping_sleeve_preview(s, alpha = 0.65) {
    z0 = moving_sleeve_bottom_z(s);
    sleeve_z = z0 + moving_sleeve_flange_t;
    main_h = moving_sleeve_h - moving_sleeve_leadin_h;

    // Flange on moving plate.
    color([0.0, 0.15, 0.85, alpha])
        ring_at(0, 0, z0, moving_sleeve_flange_od, moving_sleeve_id, moving_sleeve_flange_t);

    // Sleeve body with small front loading window.
    color([0.0, 0.1, 0.75, alpha])
        translate([0, 0, sleeve_z])
            windowed_ring(
                moving_sleeve_od,
                moving_sleeve_id,
                main_h,
                moving_sleeve_window_w,
                moving_sleeve_window_h,
                moving_sleeve_window_bottom
            );

    // Top lead-in taper.
    color([0.0, 0.1, 0.75, alpha])
        translate([0, 0, sleeve_z + main_h])
            tapered_outer_ring(
                moving_sleeve_od,
                moving_sleeve_top_od,
                moving_sleeve_id,
                moving_sleeve_leadin_h
            );
}

module fixed_receiver_preview() {
    // Flange at top plate.
    color([0.02, 0.02, 0.02, 0.55])
        ring_at(0, 0, receiver_top_z, fixed_receiver_flange_od, fixed_receiver_id, fixed_receiver_flange_t);

    // Main receiver.
    main_receiver_h = fixed_receiver_len - receiver_mouth_h;

    color([0.02, 0.02, 0.02, 0.42])
        ring_at(0,
                0,
                receiver_bottom_z + receiver_mouth_h,
                fixed_receiver_od,
                fixed_receiver_id,
                main_receiver_h);

    // Flared lower mouth.
    color([0.02, 0.02, 0.02, 0.42])
        translate([0, 0, receiver_bottom_z])
            tapered_inner_receiver_ring(
                fixed_receiver_od,
                fixed_receiver_mouth_id,
                fixed_receiver_id,
                receiver_mouth_h
            );
}

module overlap_zone_preview(s) {
    lo = overlap_bottom_z(s);
    hi = overlap_top_z(s);
    oh = telescope_overlap(s);

    if (show_overlap_zone && oh > 0) {
        color([1.0, 0.0, 1.0, 0.38])
            ring_at(0, 0, lo, fixed_receiver_id - 0.2, moving_sleeve_od + 0.2, oh);
    }

    // Red warning if scan overlap is too small.
    if (oh < min_required_overlap) {
        color([1.0, 0.0, 0.0, 0.45])
            cyl_z(0, 0, receiver_top_z + 5, fixed_receiver_od + 14, 4);
    }

    // Orange warning if top clearance is too small.
    if (telescope_top_clearance(s) < min_required_top_clearance) {
        color([1.0, 0.35, 0.0, 0.45])
            cyl_z(0, 0, receiver_top_z + 12, fixed_receiver_od + 24, 4);
    }
}

// =========================================================
// OPTICAL HEAD - REUSED V1 COMPONENTS
// =========================================================

module optical_head_preview() {
    // Existing/reused outer optical tube.
    color([0.02, 0.02, 0.02, 0.40])
        ring_at(0, 0, outer_tube_z0, outer_tube_od, outer_tube_id, outer_tube_h);

    // Shortened removable inner sleeve.
    color([0.0, 0.0, 0.0, 0.25])
        ring_at(0, 0, inner_sleeve_z0, inner_sleeve_od, inner_sleeve_id, inner_sleeve_h);

    // Existing/reused LED ring.
    color([0.65, 0.1, 0.95, 0.38])
        ring_at(0, 0, led_ring_z0, led_ring_od, led_ring_id, led_ring_h);

    // Existing/reused detector cap.
    color([0.12, 0.12, 0.12, 0.70])
        cyl_z(0, 0, detector_cap_z0, detector_cap_od, detector_cap_t);

    // Detector snout.
    color([0.02, 0.02, 0.02, 0.75])
        cyl_z(0, 0, detector_cap_z0 - detector_snout_h, detector_snout_od, detector_snout_h);
}

// =========================================================
// KEEP OUT, AXES, GHOSTS
// =========================================================

module keepout_zone_preview() {
    if (show_keepout_zone) {
        color([0.0, 1.0, 1.0, 0.08])
            cyl_z(0, 0, base_h, central_keepout_d, top_plate_z - base_h);
    }
}

module axes_preview() {
    if (show_axes) {
        color([0.0, 1.0, 1.0, 0.55])
            cyl_z(0, 0, 0, 1.8, detector_cap_z0 + detector_cap_t + 20);

        color([1.0, 0.85, 0.0, 0.4]) {
            cyl_z(-lead_screw_x, 0, 0, 1.4, detector_cap_z0 + 20);
            cyl_z( lead_screw_x, 0, 0, 1.4, detector_cap_z0 + 20);
        }
    }
}

module ghost_positions_preview() {
    if (show_ghost_positions) {
        // Low scan position.
        moving_carriage_preview(stage_z_min, 0.15);
        moving_telescoping_sleeve_preview(stage_z_min, 0.15);
        front_hatch_preview(stage_z_min, false, 0.15);
        overlap_zone_preview(stage_z_min);

        // High scan position.
        moving_carriage_preview(stage_z_max, 0.15);
        moving_telescoping_sleeve_preview(stage_z_max, 0.15);
        front_hatch_preview(stage_z_max, false, 0.15);
        overlap_zone_preview(stage_z_max);
    }

    if (show_load_position) {
        // Load position ghost.
        moving_carriage_preview(stage_z_load, 0.20);
        moving_telescoping_sleeve_preview(stage_z_load, 0.18);
        front_hatch_preview(stage_z_load, false, 0.22);
    }

    if (show_hatch_open_ghost) {
        // Small hatch opened at load position.
        front_hatch_preview(stage_z_load, true, 0.42);
    }
}

// =========================================================
// ENDSTOPS / ELECTRONICS ROUGH PREVIEW
// =========================================================

module endstop_preview() {
    color([1.0, 0.0, 0.0, 0.65])
        box_centered(-carriage_w/2 - 8, -carriage_d/2 + 12, base_h + 8, 10, 24, 14);

    color([1.0, 0.0, 0.0, 0.45])
        box_centered(-carriage_w/2 - 8, -carriage_d/2 + 12, top_plate_z - 26, 10, 24, 14);
}

module electronics_tray_preview() {
    // Compact side service panel. Reuse old electronics tray if possible.
    color([0.15, 0.15, 0.15, 0.28])
        box_centered(side_panel_x + 18, 0, base_h + 35, 4, 100, 60);

    color([0.0, 0.45, 0.0, 0.40])
        box_centered(side_panel_x + 21, -20, base_h + 48, 2, 35, 26);

    color([0.0, 0.2, 0.75, 0.40])
        box_centered(side_panel_x + 21, 20, base_h + 48, 2, 42, 28);
}

// =========================================================
// FULL ASSEMBLY
// =========================================================

module lio_v21_lean_assembly_preview() {
    // Fixed chassis.
    base_preview();
    motors_and_couplers_preview();
    guide_rods_preview();
    lead_screws_preview();
    side_panels_preview();
    top_plate_preview();

    // Fixed optical stack.
    fixed_receiver_preview();
    optical_head_preview();

    // Visual guides.
    keepout_zone_preview();
    axes_preview();

    // Ghosts.
    ghost_positions_preview();

    // Current active moving position.
    moving_carriage_preview(stage_z, 0.82);
    moving_telescoping_sleeve_preview(stage_z, 0.72);
    front_hatch_preview(stage_z, false, 0.85);
    overlap_zone_preview(stage_z);

    // Service pieces.
    endstop_preview();
    electronics_tray_preview();
}

lio_v21_lean_assembly_preview();
