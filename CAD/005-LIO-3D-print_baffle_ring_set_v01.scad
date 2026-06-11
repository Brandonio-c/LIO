// Lio v0.1 — Internal Baffle Ring Set
// Units: millimeters
//
// This print generates:
// - lower baffle ring
// - middle baffle ring
// - upper baffle ring
// - optional detector-field limiter ring
//
// Purpose:
// - Stop shallow-angle wall reflections.
// - Reduce stray light reaching the detector.
// - Give you swappable/testable apertures inside the optical tube.
//
// Print orientation:
// - Flat on bed.
//
// Material:
// - Black PETG.
// - Optionally coat/flock/paint after printing.
//
// Notes:
// - These are separate rings placed side by side for printing.
// - Outer diameter is slightly under the planned 54 mm inner sleeve bore.
// - Inner openings are intentionally different so you can test detector signal vs. field restriction.

$fn = 160;
eps = 0.05;

// ----------------------------
// Global dimensions
// ----------------------------

// Planned removable inner sleeve ID is about 54 mm.
// Use a slightly smaller baffle OD so the rings slide in.
baffle_od = 53.2;

// Main ring thickness.
ring_t = 2.0;

// Top chamfer / knife-edge geometry.
// Larger chamfer_radial = longer sloped top surface.
// inner_lip_h is the small vertical inner lip left for strength.
chamfer_radial = 3.0;
inner_lip_h = 0.45;

// Print spacing between rings.
spacing = 66;

// Text label settings
enable_labels = true;
label_size = 4.0;
label_depth = 0.6;

// Ring definitions:
// [name, inner_opening_diameter]
rings = [
    ["LOWER 48",   48],
    ["MID 44",     44],
    ["UPPER 40",   40],
    ["LIMIT 36",   36]
];

// ----------------------------
// Helper modules
// ----------------------------

// Chamfered annular baffle using rotate_extrude.
// The 2D polygon is defined in [radius, height] coordinates.
// rotate_extrude revolves it around the Z axis.
//
// Cross-section shape:
//
// outer top ┌────────────
//           │            \ chamfer toward aperture
// outer wall│             \
//           │              │ inner lip
// bottom    └──────────────┘
//
// This gives a shallow sloped inner edge rather than a blunt washer.

module chamfered_baffle_ring(od, id, t, chamfer, lip_h) {

    outer_r = od / 2;
    inner_r = id / 2;

    // Guard against impossible geometry.
    safe_chamfer = min(chamfer, max(0.5, outer_r - inner_r - 1.0));
    safe_lip_h = min(lip_h, t * 0.8);

    rotate_extrude(convexity = 10)
        polygon(points = [
            [inner_r, 0],                         // inner bottom
            [outer_r, 0],                         // outer bottom
            [outer_r, t],                         // outer top
            [inner_r + safe_chamfer, t],          // top before chamfer
            [inner_r, safe_lip_h]                 // inner lip / knife edge
        ]);
}

// Raised label placed beside each ring.
// Labels are intentionally outside the ring so they do not interfere with the optical part.
module ring_label(txt) {
    if (enable_labels) {
        translate([0, -baffle_od/2 - 7, 0])
            linear_extrude(height = label_depth)
                text(txt,
                     size = label_size,
                     font = "Liberation Sans:style=Bold",
                     halign = "center",
                     valign = "center");
    }
}

// Small orientation mark on each ring.
// This gives you a visible "up" reference if you want all chamfers facing the same direction during assembly.
module orientation_tick(od) {
    tick_w = 2.0;
    tick_l = 5.0;
    tick_h = 0.8;

    translate([0, od/2 - tick_l/2, ring_t])
        cube([tick_w, tick_l, tick_h], center = true);
}

// ----------------------------
// Full ring set
// ----------------------------

for (i = [0 : len(rings) - 1]) {
    x = (i - (len(rings)-1)/2) * spacing;
    label = rings[i][0];
    id = rings[i][1];

    translate([x, 0, 0]) {
        chamfered_baffle_ring(
            od = baffle_od,
            id = id,
            t = ring_t,
            chamfer = chamfer_radial,
            lip_h = inner_lip_h
        );

        orientation_tick(baffle_od);
        ring_label(str(label, " ID"));
    }
}