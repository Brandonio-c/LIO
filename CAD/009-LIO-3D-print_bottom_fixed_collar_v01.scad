// Lio v0.1 — Bottom Fixed Collar / Upper Telescoping Receiver
// Units: millimeters
//
// This part integrates:
// - bottom collar for optical tube
// - fixed half of telescoping light seal
// - sample-stage opening
// - M3 tube attachment holes
// - internal flocking/felt relief seat
//
// Physical role:
// - Screws to the bottom flange of the fixed outer optical tube.
// - Provides the fixed receiver sleeve for the moving telescoping skirt.
// - Keeps the lower chamber light-sealed while the sample platform moves.
//
// PRINT ORIENTATION:
// - This model is oriented for SUPPORT-FREE printing.
// - Flange sits flat on the print bed at Z=0.
// - Receiver sleeve prints upward.
// - After printing, install it with the receiver sleeve pointing downward.
//
// Suggested material:
// - Black PETG
//
// Suggested settings:
// - 0.20 mm layer height
// - 4 walls
// - 25–35% infill
// - supports OFF
// - brim optional

$fn = 160;
eps = 0.05;

// ---------------------------------------------------------
// Main flange dimensions
// ---------------------------------------------------------

flange_od = 92;          // matches top/bottom flange range of outer optical tube
flange_t  = 6.0;         // flange thickness

// Matches the outer optical tube's M3 bolt circle.
// Previous outer tube used m3_bolt_circle_d = 74.
mount_bolt_circle_d = 74;
mount_r = mount_bolt_circle_d / 2;

m3_clearance_d = 3.4;    // M3 clearance hole
m3_head_recess_d = 6.6;  // optional shallow head recess
m3_head_recess_depth = 2.0;

enable_head_recess = true;

// ---------------------------------------------------------
// Telescoping receiver sleeve dimensions
// ---------------------------------------------------------

receiver_len = 45;       // suggested 35–50 mm
receiver_od  = 70;       // outside diameter of fixed receiver sleeve
receiver_id  = 64.5;     // raw inside diameter before flocking

// Moving skirt target OD is expected around 58–60 mm.
// With receiver_id = 64.5, you have generous clearance for skirt + flocking.

// ---------------------------------------------------------
// Flocking / felt relief seat
// ---------------------------------------------------------
//
// The inside of the receiver may be lined with flocking.
// This relief slightly enlarges the inner bore through most of the receiver
// so the liner does not choke the telescoping skirt.
//
// Leave small lips at the top and bottom so the liner edge is protected.

enable_flocking_relief = true;

flocking_relief_radial = 0.7;       // increases radius by this amount in relief region
flocking_lip_h = 3.0;               // unrelieved lip height at both ends

// Derived
flocking_relief_id = receiver_id + 2 * flocking_relief_radial;
flocking_relief_z0 = flange_t + flocking_lip_h;
flocking_relief_h  = receiver_len - 2 * flocking_lip_h;

// ---------------------------------------------------------
// Lead-in / entry relief
// ---------------------------------------------------------
//
// Slight larger openings at the receiver mouth and flange transition.
// This helps the moving skirt enter without scraping.

enable_mouth_relief = true;
mouth_relief_id = receiver_id + 2.0;
mouth_relief_h = 2.0;

// ---------------------------------------------------------
// Alignment notch / orientation mark
// ---------------------------------------------------------

enable_alignment_notch = true;
alignment_notch_w = 5.0;
alignment_notch_l = 10.0;
alignment_notch_depth = 1.2;

// ---------------------------------------------------------
// Optional screw alignment bosses/pads on flange
// ---------------------------------------------------------

enable_mount_boss_pads = true;
boss_pad_d = 12.0;
boss_pad_h = 1.2;

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

module m3_mount_holes_cut() {
    for (a = [0, 90, 180, 270]) {
        rotate([0, 0, a])
        translate([mount_r, 0, -1]) {

            // Through clearance hole
            cylinder(d = m3_clearance_d, h = flange_t + 2);

            // Shallow head recess from print-top side.
            // Since this part is later flipped for installation, treat this as optional.
            if (enable_head_recess) {
                translate([0, 0, flange_t - m3_head_recess_depth])
                    cylinder(d = m3_head_recess_d,
                             h = m3_head_recess_depth + 1);
            }
        }
    }
}

module boss_pads() {
    if (enable_mount_boss_pads) {
        for (a = [0, 90, 180, 270]) {
            rotate([0, 0, a])
            translate([mount_r, 0, flange_t])
                cylinder(d = boss_pad_d, h = boss_pad_h);
        }
    }
}

module flocking_relief_cut() {
    if (enable_flocking_relief && flocking_relief_h > 0) {
        translate([0, 0, flocking_relief_z0])
            cylinder(d = flocking_relief_id, h = flocking_relief_h);
    }
}

module mouth_relief_cuts() {
    if (enable_mouth_relief) {
        // Relief at top mouth of receiver sleeve.
        translate([0, 0, flange_t + receiver_len - mouth_relief_h])
            cylinder(d = mouth_relief_id, h = mouth_relief_h + eps);

        // Relief at flange transition.
        translate([0, 0, flange_t - eps])
            cylinder(d = mouth_relief_id, h = mouth_relief_h + eps);
    }
}

module alignment_notch_cut() {
    if (enable_alignment_notch) {
        // Small shallow notch on flange outer edge at +Y.
        // Used as orientation marker when assembling.
        translate([
            0,
            flange_od/2 - alignment_notch_l/2,
            flange_t - alignment_notch_depth/2 + eps
        ])
            cube([
                alignment_notch_w,
                alignment_notch_l,
                alignment_notch_depth + 2*eps
            ], center = true);
    }
}

// ---------------------------------------------------------
// Main model
// ---------------------------------------------------------

difference() {

    union() {

        // Main bottom collar flange.
        // This sits on the bed while printing.
        cylinder(d = flange_od, h = flange_t);

        // Fixed receiver sleeve.
        // Prints upward for support-free printing.
        translate([0, 0, flange_t])
            cylinder(d = receiver_od, h = receiver_len);

        // Optional raised boss pads around M3 holes.
        boss_pads();
    }

    // Main through-opening for optical path and moving sample/skirt clearance.
    translate([0, 0, -1])
        cylinder(d = receiver_id, h = flange_t + receiver_len + 2);

    // Internal flocking relief seat.
    flocking_relief_cut();

    // Mouth/entry reliefs.
    mouth_relief_cuts();

    // M3 mounting holes matching outer tube bottom flange.
    m3_mount_holes_cut();

    // Alignment notch / orientation mark.
    alignment_notch_cut();
}

// ---------------------------------------------------------
// Optional raised orientation marker outside optical path
// ---------------------------------------------------------

marker_h = 0.8;
marker_w = 3.0;
marker_l = 12.0;

translate([
    0,
    -flange_od/2 + marker_l/2,
    flange_t
])
    cube([marker_w, marker_l, marker_h], center = true);