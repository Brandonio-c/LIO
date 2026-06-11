// Lio v0.1 — Removable Flocked Inner Sleeve
// Units: millimeters
//
// This part integrates:
// - flocking carrier
// - replaceable optical black liner support
// - flexible tolerance compensator
// - vertical seam/keyway for alignment and flex
//
// Print orientation:
// - vertical
//
// Material:
// - PETG preferred
//
// Important:
// - Test fit this sleeve inside the fixed outer tube BEFORE applying flocking.
// - After flocking, the inside diameter becomes smaller and the sleeve may become stiffer.
// - If it is too tight, reduce sleeve_od by 0.3–0.5 mm.
// - If it is too loose, increase sleeve_od by 0.2–0.3 mm.

$fn = 128;
eps = 0.05;

// ----------------------------
// Sleeve dimensions
// ----------------------------

sleeve_od = 58.4;       // outer diameter before flocking
sleeve_id = 54.0;       // inner optical bore before flocking
sleeve_h  = 90.0;       // sleeve height

// Wall thickness is calculated automatically.
wall_thickness = (sleeve_od - sleeve_id) / 2;

// ----------------------------
// Vertical split seam / keyway
// ----------------------------

seam_width = 3.0;       // tangential slot width
seam_depth = wall_thickness + 1.2;  
// depth should cut fully through the sleeve wall.
// It also acts as a keyway for the outer tube's internal alignment rib.

seam_z_margin = 0.0;    // set to 2–5 if you want seam not to reach ends

// ----------------------------
// Optional grip tabs / removal notches
// ----------------------------

enable_removal_notches = true;

notch_w = 10;           // width of small finger notches
notch_h = 5;            // notch height
notch_depth = 2.0;      // radial notch depth

// ----------------------------
// Optional top/bottom relief bands
// ----------------------------

enable_relief_bands = true;

relief_h = 3.0;         // height of relief at top and bottom
relief_depth = 0.25;    // reduce OD slightly at the ends for easier insertion

// ----------------------------
// Helper modules
// ----------------------------

module tube(od, id, h) {
    difference() {
        cylinder(d = od, h = h);
        translate([0, 0, -1])
            cylinder(d = id, h = h + 2);
    }
}

module vertical_seam_cut() {
    // Cut through the sleeve wall on +X side.
    // This creates both flex and an alignment slot.
    translate([
        sleeve_od/2 - seam_depth/2 + eps,
        0,
        sleeve_h/2
    ])
        cube([seam_depth + 2 * eps, seam_width, sleeve_h + 2], center = true);
}

module removal_notches() {
    // Small shallow notches near top and bottom on the side opposite the seam.
    // These make it easier to pull the sleeve out without touching the flocked interior.
    for (zpos = [8, sleeve_h - 8]) {
        translate([
            -sleeve_od/2 + notch_depth/2,
            0,
            zpos
        ])
            cube([notch_depth + 2 * eps, notch_w, notch_h], center = true);
    }
}

module relief_band_cuts() {
    // Slightly reduce OD near top and bottom edges.
    // This prevents the first few millimeters from binding inside the outer tube.
    difference() {
        // Nothing here directly; relief is implemented as subtractive annular cuts below.
    }
}

module annular_relief_cut(zpos) {
    // Removes a very shallow ring from the outside diameter.
    // This creates a lead-in relief but keeps the sleeve mostly cylindrical.
    difference() {
        translate([0, 0, zpos])
            cylinder(d = sleeve_od + 2, h = relief_h);

        translate([0, 0, zpos - eps])
            cylinder(d = sleeve_od - 2 * relief_depth, h = relief_h + 2 * eps);
    }
}

// ----------------------------
// Main model
// ----------------------------

difference() {

    // Main sleeve body
    tube(sleeve_od, sleeve_id, sleeve_h);

    // Full-height seam/keyway
    translate([0, 0, seam_z_margin])
        vertical_seam_cut();

    // Optional removal notches
    if (enable_removal_notches) {
        removal_notches();
    }

    // Optional shallow OD relief at top and bottom
    if (enable_relief_bands) {
        // bottom relief
        annular_relief_cut(0);

        // top relief
        annular_relief_cut(sleeve_h - relief_h);
    }
}