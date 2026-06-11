// Lio v0.1 — Moving Telescoping Skirt / Lower Light-Seal Sleeve
// Units: millimeters
//
// This part integrates:
// - moving half of telescoping optical shroud
// - sample cup opening / optical path opening
// - flocking carrier sleeve
// - mounting flange to moving sample platform
//
// Physical role:
// - Mounts to the moving sample platform around the sample cup.
// - Moves up/down with the sample.
// - Slides into / overlaps with the fixed bottom collar receiver.
// - Preserves a dark optical path while the Z-stage moves.
//
// PRINT ORIENTATION:
// - Flange flat on bed at Z=0.
// - Sleeve prints upward.
// - Supports OFF.
//
// Material:
// - Black PETG recommended.
//
// Suggested print settings:
// - 0.20 mm layer height
// - 3–4 walls
// - 25–35% infill
// - supports OFF
// - brim optional

$fn = 160;
eps = 0.05;

// ---------------------------------------------------------
// Main skirt geometry
// ---------------------------------------------------------

// Main upper sleeve outer diameter.
// This slides into the fixed bottom collar receiver.
// Fixed collar receiver ID was about 64.5 mm,
// so 58.5 mm gives generous clearance for flocking and imperfect rods.
sleeve_od = 58.5;

// Inner optical/sample opening.
// 44–50 mm recommended.
// Use 46 mm as a sane v0.1 balance.
sleeve_id = 46.0;

// Total sleeve region above flange is:
// lower neck + tapered transition + main sleeve
lower_neck_od = 52.0;      // clears M3 mount holes better than full 58.5 OD
lower_neck_h  = 10.0;

transition_h = 10.0;       // tapered section from lower neck to full sleeve OD
main_sleeve_h = 55.0;      // straight upper sleeve height

total_sleeve_h = lower_neck_h + transition_h + main_sleeve_h;

// ---------------------------------------------------------
// Mounting flange geometry
// ---------------------------------------------------------

flange_od = 76.0;
flange_t  = 5.5;

// Must match moving platform skirt_mount_bcd = 57 from Print 12.
mount_bcd = 57.0;
mount_r = mount_bcd / 2;

m3_clearance_d = 3.4;

// No screw-head recess by default.
// Recesses would collide with the lower neck at this compact bolt circle.
enable_screw_head_recess = false;
m3_head_recess_d = 6.5;
m3_head_recess_depth = 2.0;

// Screw access notches cut into the lower neck so you can physically
// reach the M3 screws even though the sleeve is close to the bolt circle.
enable_screw_access_notches = true;
screw_access_radial_len = 12.0;
screw_access_tangent_w = 8.5;
screw_access_h = lower_neck_h + 1.0;

// ---------------------------------------------------------
// Flocking / liner features
// ---------------------------------------------------------

// Outer shallow grooves help locate/catch the edge of external flocking,
// if you decide to flock the outside of the moving skirt.
// Keep these shallow so the skirt remains strong.
enable_flocking_edge_grooves = true;
flocking_groove_depth = 0.5;
flocking_groove_h = 1.2;

// Position grooves near lower and upper areas of the main sleeve.
flocking_lower_groove_z = flange_t + lower_neck_h + transition_h + 3;
flocking_upper_groove_z = flange_t + total_sleeve_h - 6;

// ---------------------------------------------------------
// Lead-in / anti-scrape features
// ---------------------------------------------------------

// Slightly reduce OD at very top so it enters the fixed receiver more easily.
enable_top_leadin = true;
top_leadin_h = 4.0;
top_leadin_od_reduction = 1.5;

// Slight inner mouth bevel/relief.
// This is a straight relief, not a true curved chamfer.
enable_inner_mouth_relief = true;
inner_mouth_relief_d = sleeve_id + 2.0;
inner_mouth_relief_h = 2.0;

// ---------------------------------------------------------
// Optional alignment mark
// ---------------------------------------------------------

enable_alignment_mark = true;
alignment_mark_w = 3.0;
alignment_mark_l = 9.0;
alignment_mark_depth = 0.8;

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

module tapered_ring(od1, od2, id, h) {
    difference() {
        cylinder(d1 = od1, d2 = od2, h = h);
        translate([0, 0, -1])
            cylinder(d = id, h = h + 2);
    }
}

module mount_holes_cut() {
    for (a = [45, 135, 225, 315]) {
        rotate([0, 0, a])
        translate([mount_r, 0, -1]) {
            cylinder(d = m3_clearance_d, h = flange_t + 2);

            if (enable_screw_head_recess) {
                translate([0, 0, flange_t - m3_head_recess_depth])
                    cylinder(d = m3_head_recess_d,
                             h = m3_head_recess_depth + 1);
            }
        }
    }
}

module screw_access_notches_cut() {
    if (enable_screw_access_notches) {
        for (a = [45, 135, 225, 315]) {
            rotate([0, 0, a])
            translate([
                mount_r,
                0,
                flange_t + screw_access_h/2
            ])
                cube([
                    screw_access_radial_len,
                    screw_access_tangent_w,
                    screw_access_h + 2*eps
                ], center = true);
        }
    }
}

module flocking_edge_groove_cut(zpos) {
    if (enable_flocking_edge_grooves) {
        // Shallow external annular groove.
        // Cuts only the outside surface of the upper sleeve.
        translate([0, 0, zpos])
        difference() {
            cylinder(d = sleeve_od + 2, h = flocking_groove_h);
            translate([0, 0, -eps])
                cylinder(d = sleeve_od - 2*flocking_groove_depth,
                         h = flocking_groove_h + 2*eps);
        }
    }
}

module top_leadin_cut() {
    if (enable_top_leadin) {
        // Remove a shallow outer band at the very top,
        // reducing OD slightly for easier entry into fixed collar receiver.
        translate([0, 0, flange_t + total_sleeve_h - top_leadin_h])
        difference() {
            cylinder(d = sleeve_od + 2, h = top_leadin_h + eps);
            translate([0, 0, -eps])
                cylinder(d = sleeve_od - top_leadin_od_reduction,
                         h = top_leadin_h + 2*eps);
        }
    }
}

module inner_mouth_relief_cuts() {
    if (enable_inner_mouth_relief) {
        // Relief at top inner opening.
        translate([0, 0, flange_t + total_sleeve_h - inner_mouth_relief_h])
            cylinder(d = inner_mouth_relief_d,
                     h = inner_mouth_relief_h + eps);

        // Relief at bottom inner opening / flange entry.
        translate([0, 0, -eps])
            cylinder(d = inner_mouth_relief_d,
                     h = inner_mouth_relief_h + eps);
    }
}

module alignment_mark_cut() {
    if (enable_alignment_mark) {
        // Shallow notch on flange outer edge at +Y.
        translate([
            0,
            flange_od/2 - alignment_mark_l/2,
            flange_t - alignment_mark_depth/2 + eps
        ])
            cube([
                alignment_mark_w,
                alignment_mark_l,
                alignment_mark_depth + 2*eps
            ], center = true);
    }
}

// ---------------------------------------------------------
// Main model
// ---------------------------------------------------------

difference() {

    union() {

        // Bottom mounting flange.
        cylinder(d = flange_od, h = flange_t);

        // Lower neck. Smaller OD clears mounting screws.
        translate([0, 0, flange_t])
            ring(lower_neck_od, sleeve_id, lower_neck_h);

        // Sloped transition out to full telescoping sleeve OD.
        // Supportless because it is a gradual outward taper.
        translate([0, 0, flange_t + lower_neck_h])
            tapered_ring(
                od1 = lower_neck_od,
                od2 = sleeve_od,
                id = sleeve_id,
                h = transition_h
            );

        // Main moving telescoping sleeve.
        translate([0, 0, flange_t + lower_neck_h + transition_h])
            ring(sleeve_od, sleeve_id, main_sleeve_h);
    }

    // Mounting holes matching Print 12 moving platform.
    mount_holes_cut();

    // Access notches around lower neck for screw access.
    screw_access_notches_cut();

    // External flocking edge grooves.
    flocking_edge_groove_cut(flocking_lower_groove_z);
    flocking_edge_groove_cut(flocking_upper_groove_z);

    // Top lead-in relief.
    top_leadin_cut();

    // Inner mouth reliefs.
    inner_mouth_relief_cuts();

    // Alignment notch.
    alignment_mark_cut();
}

// ---------------------------------------------------------
// Optional small raised orientation marker opposite notch
// ---------------------------------------------------------

marker_h = 0.8;
marker_w = 3.0;
marker_l = 10.0;

translate([
    0,
    -flange_od/2 + marker_l/2,
    flange_t
])
    cube([marker_w, marker_l, marker_h], center = true);