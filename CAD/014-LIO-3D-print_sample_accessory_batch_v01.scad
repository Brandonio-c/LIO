// Lio v0.1 — Sample / Calibration Accessory Batch
// Units: millimeters
//
// This print generates four separate physical pieces:
// 1. Powder sample cup
// 2. PTFE reference holder
// 3. Dark reference plug
// 4. Leveling ring / scraper guide
//
// These pieces are designed to fit:
// - Print 12 moving sample platform pocket: ~45 mm diameter
// - Print 13 moving skirt inner opening: ~46 mm diameter
//
// IMPORTANT:
// - The PTFE holder is NOT the white reference itself.
// - Cut a PTFE disk from your 3 mm PTFE sheet and press/place it into the holder.
// - The top PTFE surface should be flush with the holder rim.
// - The powder cup top rim defines the target powder surface plane.
//
// Print orientation:
// - Flat on bed.
// - Supports OFF.
//
// Material:
// - PETG recommended.
// - Dark plug should be printed black and/or topped with flocking/matte black material.

$fn = 128;
eps = 0.05;

// ---------------------------------------------------------
// Output selector
// ---------------------------------------------------------
//
// Options:
// "batch"          -> all four pieces arranged on the bed
// "sample_cup"     -> powder sample cup only
// "ptfe_holder"    -> PTFE holder only
// "dark_plug"      -> dark reference plug only
// "leveling_ring"  -> leveling ring only

part = "batch";

// ---------------------------------------------------------
// Shared fit dimensions
// ---------------------------------------------------------

// This must fit inside Print 12 sample_pocket_d = 45.0 mm
// and inside Print 13 sleeve_id = 46.0 mm.
accessory_od = 44.2;

// Lower locating foot.
locator_d = 44.2;
locator_h = 3.0;

// Overall height of cup / holder / plug.
accessory_h = 8.0;

// Powder cup dimensions.
cup_inner_d = 38.0;
powder_depth = 5.0;      // powder depth from top rim to bottom
cup_bottom_t = accessory_h - powder_depth;

// PTFE reference disk dimensions.
// Your PTFE sheet is 3 mm thick.
ptfe_disk_d = 38.0;
ptfe_recess_d = 38.4;
ptfe_recess_depth = 3.08; // tiny extra clearance for 3 mm PTFE

// Dark plug top flocking recess.
dark_top_recess_d = 38.0;
dark_top_recess_depth = 0.8;

// Leveling ring dimensions.
// This sits on top of the powder cup while filling, then gets removed.
leveling_ring_od = 44.0;
leveling_ring_id = cup_inner_d;
leveling_ring_h = 4.0;

// Small top bevel/lead-in dimensions.
top_bevel_h = 0.8;
top_bevel_d_extra = 1.2;

// Identification notch settings.
// These are shallow top-edge cuts so you can distinguish pieces without raised text.
enable_id_notches = true;
notch_w = 3.0;
notch_l = 5.0;
notch_depth = 1.0;

// Layout spacing for batch print.
layout_spacing = 62;

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

module shallow_top_notches(count, od, ztop) {
    if (enable_id_notches) {
        for (i = [0 : count - 1]) {
            angle = 90 + i * 18;
            rotate([0, 0, angle])
            translate([od/2 - notch_l/2 + eps, 0, ztop - notch_depth/2 + eps])
                cube([notch_l, notch_w, notch_depth + 2*eps], center = true);
        }
    }
}

module top_leadin_cut(od, ztop) {
    // Slight outer-edge relief at the top so pieces insert/remove more easily.
    translate([0, 0, ztop - top_bevel_h])
    difference() {
        cylinder(d = od + 2, h = top_bevel_h + eps);
        translate([0, 0, -eps])
            cylinder(d = od - top_bevel_d_extra, h = top_bevel_h + 2*eps);
    }
}

module bottom_locator_body() {
    // The whole piece is a straight cylinder for reliable pocket fit.
    // The lower 3 mm functions as the locating foot in the moving platform pocket.
    cylinder(d = accessory_od, h = accessory_h);
}

// ---------------------------------------------------------
// 14A — Powder sample cup
// ---------------------------------------------------------

module powder_sample_cup() {
    difference() {
        bottom_locator_body();

        // Powder cavity: open from top, leaves cup_bottom_t floor.
        translate([0, 0, cup_bottom_t])
            cylinder(d = cup_inner_d, h = powder_depth + 1);

        // Slight top lead-in / outer relief.
        top_leadin_cut(accessory_od, accessory_h);

        // One shallow notch = sample cup.
        shallow_top_notches(1, accessory_od, accessory_h);
    }
}

// ---------------------------------------------------------
// 14B — PTFE reference holder
// ---------------------------------------------------------

module ptfe_reference_holder() {
    difference() {
        bottom_locator_body();

        // Top recess for 3 mm PTFE disk.
        // PTFE disk should sit almost flush with top rim.
        translate([0, 0, accessory_h - ptfe_recess_depth])
            cylinder(d = ptfe_recess_d, h = ptfe_recess_depth + 1);

        // Small center push-through hole.
        // Lets you push PTFE disk out from below with a small rod if needed.
        translate([0, 0, -1])
            cylinder(d = 5.0, h = accessory_h + 2);

        // Slight top lead-in.
        top_leadin_cut(accessory_od, accessory_h);

        // Two shallow notches = PTFE holder.
        shallow_top_notches(2, accessory_od, accessory_h);
    }
}

// ---------------------------------------------------------
// 14C — Dark reference plug
// ---------------------------------------------------------

module dark_reference_plug() {
    difference() {
        bottom_locator_body();

        // Shallow top recess for black flocking, matte paint, or black felt disk.
        translate([0, 0, accessory_h - dark_top_recess_depth])
            cylinder(d = dark_top_recess_d, h = dark_top_recess_depth + 1);

        // Slight top lead-in.
        top_leadin_cut(accessory_od, accessory_h);

        // Three shallow notches = dark plug.
        shallow_top_notches(3, accessory_od, accessory_h);
    }
}

// ---------------------------------------------------------
// 14D — Leveling ring / scraper guide
// ---------------------------------------------------------

module leveling_ring() {
    difference() {
        union() {
            // Thin ring.
            ring(leveling_ring_od, leveling_ring_id, leveling_ring_h);

            // Two small grip ears that remain within skirt clearance.
            // These are full-height, not floating.
            for (a = [0, 180]) {
                rotate([0, 0, a])
                translate([leveling_ring_od/2 - 2, 0, leveling_ring_h/2])
                    cube([4.0, 10.0, leveling_ring_h], center = true);
            }
        }

        // Re-cut inner bore through everything, including ears if they intrude.
        translate([0, 0, -1])
            cylinder(d = leveling_ring_id, h = leveling_ring_h + 2);

        // Four shallow notches = leveling ring.
        shallow_top_notches(4, leveling_ring_od, leveling_ring_h);
    }
}

// ---------------------------------------------------------
// Output selector
// ---------------------------------------------------------

if (part == "sample_cup") {
    powder_sample_cup();
}

if (part == "ptfe_holder") {
    ptfe_reference_holder();
}

if (part == "dark_plug") {
    dark_reference_plug();
}

if (part == "leveling_ring") {
    leveling_ring();
}

if (part == "batch") {
    translate([-1.5 * layout_spacing, 0, 0])
        powder_sample_cup();

    translate([-0.5 * layout_spacing, 0, 0])
        ptfe_reference_holder();

    translate([0.5 * layout_spacing, 0, 0])
        dark_reference_plug();

    translate([1.5 * layout_spacing, 0, 0])
        leveling_ring();
}