// Lio v0.2 — SUPPORTLESS Top Guide Bridge
// Units: millimeters
//
// FIXED FROM v01:
// - The old top endstop pad was a raised cantilever hanging off the front edge.
// - This version makes the endstop zone a full-thickness front extension
//   that starts on the print bed, so there is no floating tab.
// - Rod bosses and center M6/bearing boss remain supported from below.
//
// This part integrates:
// - upper guide rod support
// - upper M6 threaded rod clearance/support
// - optional 606ZZ bearing pocket
// - tube-frame / side-strut stabilizer holes
// - supportless top endstop mounting extension
//
// Print orientation:
// - Flat on bed
// - Supports OFF
//
// Material:
// - PETG recommended
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
// Main bridge dimensions
// ---------------------------------------------------------

bridge_w = 132;       // X width, spans both rods plus margin
bridge_d = 48;        // Y depth of main bridge body
bridge_t = 10;        // base thickness
corner_r = 5;

// ---------------------------------------------------------
// Guide rod geometry
// ---------------------------------------------------------

rod_spacing = 90;         // must match motor base
rod_x = rod_spacing / 2;

// 8 mm rods; using 8.8 mm hole because your rods are generic,
// not precision linear shafts. Tune after test fit.
rod_hole_d = 8.8;

// Raised boss around each rod hole for strength.
rod_boss_d = 24;
rod_boss_h = 8;

// Optional lead-in recess at top for easier rod insertion.
enable_rod_leadin = true;
rod_leadin_d = 10.2;
rod_leadin_depth = 2.0;

// ---------------------------------------------------------
// Center M6 / 606ZZ bearing geometry
// ---------------------------------------------------------

// M6 threaded rod clearance.
m6_clearance_d = 7.5;

// Raised central boss around M6/bearing area.
center_boss_d = 38;
center_boss_h = 5;

// Optional 606ZZ bearing pocket.
// 606ZZ standard is 6 mm ID, 17 mm OD, 6 mm width.
// This pocket is slightly oversized for printed clearance.
enable_606_bearing_pocket = true;
bearing_606_od = 17.4;
bearing_606_depth = 6.4;

// ---------------------------------------------------------
// M3 mounting holes for side struts / tube frame
// ---------------------------------------------------------

m3_clearance_d = 3.4;
m3_head_recess_d = 6.6;
m3_head_recess_depth = 2.2;

enable_m3_recesses = true;

// Four general mounting holes near corners.
// These line up with future side brackets/frame struts.
mount_x = 56;
mount_y = 16;

// ---------------------------------------------------------
// SUPPORTLESS top endstop mounting extension
// ---------------------------------------------------------

enable_top_endstop_mount = true;

// Instead of a raised floating pad, this is a full-thickness front extension.
// It prints directly from the bed and overlaps the main bridge body.
endstop_ext_w = 46;
endstop_ext_d = 24;
endstop_ext_overlap = 7;
endstop_ext_corner_r = 4;

// Front extension sticks out from -Y side.
endstop_ext_x = 0;
endstop_ext_y = -bridge_d/2 - endstop_ext_d/2 + endstop_ext_overlap;

// Optional small raised boss pads around endstop holes.
// These are fully supported by the extension underneath.
enable_endstop_bosses = true;
endstop_boss_d = 8;
endstop_boss_h = 2;

// Cheap endstop modules vary. This gives two vertical M3-ish holes spaced 20 mm apart.
endstop_hole_spacing = 20;
endstop_hole_d = 3.2;

// ---------------------------------------------------------
// Optional alignment / centerline marks
// ---------------------------------------------------------

enable_alignment_grooves = true;
mark_depth = 0.8;
mark_w = 1.4;

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

module rod_boss(xpos) {
    translate([xpos, 0, bridge_t])
        cylinder(d = rod_boss_d, h = rod_boss_h);
}

module rod_hole_cut(xpos) {
    // Main through-hole for 8 mm rod.
    translate([xpos, 0, -1])
        cylinder(d = rod_hole_d, h = bridge_t + rod_boss_h + 3);

    // Larger lead-in recess at top.
    if (enable_rod_leadin) {
        translate([xpos, 0, bridge_t + rod_boss_h - rod_leadin_depth])
            cylinder(d = rod_leadin_d, h = rod_leadin_depth + 1);
    }
}

module center_boss() {
    translate([0, 0, bridge_t])
        cylinder(d = center_boss_d, h = center_boss_h);
}

module center_m6_and_bearing_cut() {
    // Full M6 threaded rod clearance.
    translate([0, 0, -1])
        cylinder(d = m6_clearance_d, h = bridge_t + center_boss_h + 3);

    // Optional 606ZZ bearing pocket from top.
    if (enable_606_bearing_pocket) {
        translate([0, 0, bridge_t + center_boss_h - bearing_606_depth])
            cylinder(d = bearing_606_od, h = bearing_606_depth + 1);
    }
}

module m3_mount_holes_cut() {
    for (x = [-mount_x, mount_x])
    for (y = [-mount_y, mount_y]) {

        // vertical M3 through-hole
        translate([x, y, -1])
            cylinder(d = m3_clearance_d, h = bridge_t + 3);

        // top screw-head recess
        if (enable_m3_recesses) {
            translate([x, y, bridge_t - m3_head_recess_depth])
                cylinder(d = m3_head_recess_d,
                         h = m3_head_recess_depth + 1);
        }
    }
}

module supportless_endstop_extension() {
    if (enable_top_endstop_mount) {
        translate([endstop_ext_x, endstop_ext_y, 0])
            rounded_plate(
                w = endstop_ext_w,
                d = endstop_ext_d,
                h = bridge_t,
                r = endstop_ext_corner_r
            );

        // Optional raised, fully-supported boss pads around holes.
        if (enable_endstop_bosses) {
            for (x = [-endstop_hole_spacing/2, endstop_hole_spacing/2]) {
                translate([endstop_ext_x + x, endstop_ext_y, bridge_t])
                    cylinder(d = endstop_boss_d, h = endstop_boss_h);
            }
        }
    }
}

module top_endstop_holes_cut() {
    if (enable_top_endstop_mount) {
        for (x = [-endstop_hole_spacing/2, endstop_hole_spacing/2]) {
            translate([
                endstop_ext_x + x,
                endstop_ext_y,
                -1
            ])
                cylinder(d = endstop_hole_d,
                         h = bridge_t + endstop_boss_h + 3);
        }
    }
}

module alignment_grooves_cut() {
    if (enable_alignment_grooves) {

        // Long recessed line through guide rods.
        translate([0, 0, bridge_t - mark_depth/2 + eps])
            cube([rod_spacing + 30, mark_w, mark_depth + 2*eps], center = true);

        // Short recessed centerline through M6 axis.
        translate([0, 0, bridge_t - mark_depth/2 + eps])
            cube([mark_w, 34, mark_depth + 2*eps], center = true);

        // Endstop extension center mark.
        if (enable_top_endstop_mount) {
            translate([endstop_ext_x, endstop_ext_y, bridge_t - mark_depth/2 + eps])
                cube([endstop_hole_spacing + 18, mark_w, mark_depth + 2*eps], center = true);
        }
    }
}

// ---------------------------------------------------------
// Main model
// ---------------------------------------------------------

difference() {

    union() {
        // Main bridge plate.
        rounded_plate(bridge_w, bridge_d, bridge_t, corner_r);

        // Full-thickness supportless endstop extension.
        supportless_endstop_extension();

        // Raised rod bosses.
        rod_boss(-rod_x);
        rod_boss( rod_x);

        // Raised central boss for M6/bearing area.
        center_boss();
    }

    // Two 8 mm guide rod holes.
    rod_hole_cut(-rod_x);
    rod_hole_cut( rod_x);

    // Center M6 clearance and optional 606ZZ pocket.
    center_m6_and_bearing_cut();

    // M3 side/frame mounting holes.
    m3_mount_holes_cut();

    // Endstop extension holes.
    top_endstop_holes_cut();

    // Shallow alignment grooves.
    alignment_grooves_cut();
}