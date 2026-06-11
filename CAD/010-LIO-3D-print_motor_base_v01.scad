    // Lio v0.1 — Motor Base with Integrated 28BYJ Mount and Lower Rod Sockets
// Units: millimeters
//
// This part integrates:
// - base plate
// - 28BYJ-48 motor mount / alignment pocket
// - lower 8 mm guide rod sockets
// - M6 threaded rod / coupler clearance
// - optional ULN2003 driver board mount
// - bottom endstop mounting zone
// - feet/riser holes
// - M3 holes for attaching later frame/electronics components
//
// Physical role:
// - Keeps the motor, M6 screw, and two 8 mm guide rods aligned.
// - Provides the mechanical foundation for the Lio motorized Z-stage.
//
// IMPORTANT ASSEMBLY NOTE:
// - This v0.1 base assumes the 28BYJ-48 is mounted on the TOP SIDE
//   of the base, centered under the M6 threaded rod.
// - The motor shaft points upward into the coupler.
// - If your exact 28BYJ-48 body/mount geometry differs, measure it
//   and adjust motor_* parameters below.
//
// Print orientation:
// - Flat on bed.
// - Supports OFF.
//
// Material:
// - PETG recommended.
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
// Main base dimensions
// ---------------------------------------------------------

base_w = 150;        // suggested 130–150 mm
base_d = 120;        // suggested 100–130 mm
base_t = 10;         // suggested 8–12 mm
base_corner_r = 6;

// ---------------------------------------------------------
// Guide rod sockets
// ---------------------------------------------------------

rod_spacing = 90;        // center-to-center spacing between 8 mm guide rods
rod_x = rod_spacing / 2;

rod_socket_od = 20;      // outside diameter of printed rod socket tower
rod_socket_h  = 22;      // tower height above base
rod_socket_d  = 8.8;     // hole diameter for 8 mm rods; increase if your rods bind
rod_socket_depth = 18;   // blind socket depth; should be 10–20 mm

// Optional larger lead-in at the top of rod socket.
rod_socket_leadin_d = 10.2;
rod_socket_leadin_h = 2.0;

// ---------------------------------------------------------
// M6 threaded rod / shaft coupler clearance
// ---------------------------------------------------------

// Your M6 threaded rod sits on the centerline.
// The 5mm-to-6mm coupler is usually ~20 mm OD,
// so this clearance hole gives space around it.
coupler_clearance_d = 23.0;
m6_rod_clearance_d  = 7.2;

// Raised circular boss around coupler zone.
center_boss_d = 38;
center_boss_h = 4;

// ---------------------------------------------------------
// 28BYJ-48 motor mount
// ---------------------------------------------------------

// Common 28BYJ-48 values:
// - body diameter around 28 mm
// - shaft diameter around 5 mm
// - mounting hole spacing around 35 mm
//
// This mount uses a shallow circular alignment pocket and two vertical
// mounting holes. The pocket is open from the top, so it prints support-free.

motor_body_pocket_d = 30.5;   // shallow top pocket for motor face/body alignment
motor_pocket_depth  = 1.4;

motor_mount_spacing = 35.0;   // distance between mounting holes
motor_mount_hole_d  = 4.2;    // 28BYJ tabs often have ~4.2 mm holes; use washer if using M3

// Pocket orientation:
// motor tabs along X axis by default.
motor_mount_axis_angle = 0;

// ---------------------------------------------------------
// Frame / optical tube attachment holes
// ---------------------------------------------------------

// These are generic M3 clearance holes for future side brackets,
// tube supports, electronics tray brackets, etc.
frame_hole_d = 3.4;
frame_hole_x = 63;
frame_hole_y = 48;

// Optional head recesses on top of frame holes.
enable_frame_hole_recess = true;
frame_recess_d = 6.6;
frame_recess_depth = 2.0;

// ---------------------------------------------------------
// Bottom endstop mounting zone
// ---------------------------------------------------------

enable_endstop_mount = true;

// A small raised pad near the front-left side.
// Most cheap endstop modules have varying hole spacing;
// this gives two M3 vertical holes spaced 20 mm apart.
endstop_pad_w = 34;
endstop_pad_d = 18;
endstop_pad_h = 3;
endstop_pad_x = -48;
endstop_pad_y = -44;

endstop_hole_spacing = 20;
endstop_hole_d = 3.2;

// ---------------------------------------------------------
// Optional ULN2003 driver board mount
// ---------------------------------------------------------

enable_uln2003_mount = true;

// Common ULN2003 boards vary around 31–35 mm.
// This is a generic 4-standoff pattern.
uln_center_x = 45;
uln_center_y = 39;

uln_standoff_spacing_x = 28;
uln_standoff_spacing_y = 24;
uln_standoff_d = 6.5;
uln_standoff_h = 5.0;
uln_hole_d = 2.8;       // use M2.5/M3 self-tap/pilot; widen if needed

// ---------------------------------------------------------
// Feet / riser holes
// ---------------------------------------------------------

enable_feet_holes = true;
foot_hole_d = 4.0;
foot_x = 65;
foot_y = 52;

// ---------------------------------------------------------
// Optional alignment marks
// ---------------------------------------------------------

enable_shallow_alignment_marks = true;
mark_depth = 0.8;

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

module rod_socket_tower(xpos) {
    translate([xpos, 0, base_t])
        cylinder(d = rod_socket_od, h = rod_socket_h);
}

module rod_socket_hole_cut(xpos) {
    // Blind vertical hole from top of socket tower downward.
    translate([
        xpos,
        0,
        base_t + rod_socket_h - rod_socket_depth
    ])
        cylinder(d = rod_socket_d, h = rod_socket_depth + eps);

    // Larger lead-in chamfer/relief at top.
    translate([
        xpos,
        0,
        base_t + rod_socket_h - rod_socket_leadin_h
    ])
        cylinder(d = rod_socket_leadin_d, h = rod_socket_leadin_h + eps);
}

module center_boss() {
    translate([0, 0, base_t])
        cylinder(d = center_boss_d, h = center_boss_h);
}

module center_clearance_cuts() {
    // Through-hole for coupler/motor shaft/M6 rod axis.
    translate([0, 0, -1])
        cylinder(d = coupler_clearance_d, h = base_t + center_boss_h + 3);

    // Optional smaller center guide hole reference is not used because
    // coupler clearance dominates.
}

module motor_alignment_pocket_cut() {
    // Shallow open-top pocket. No support needed.
    translate([0, 0, base_t + center_boss_h - motor_pocket_depth])
        cylinder(d = motor_body_pocket_d, h = motor_pocket_depth + eps);
}

module motor_mount_holes_cut() {
    // Two vertical holes for 28BYJ-48 mounting tabs.
    rotate([0, 0, motor_mount_axis_angle]) {
        for (x = [-motor_mount_spacing/2, motor_mount_spacing/2]) {
            translate([x, 0, -1])
                cylinder(d = motor_mount_hole_d,
                         h = base_t + center_boss_h + 3);
        }
    }
}

module frame_mount_holes_cut() {
    for (x = [-frame_hole_x, frame_hole_x])
    for (y = [-frame_hole_y, frame_hole_y]) {
        translate([x, y, -1])
            cylinder(d = frame_hole_d, h = base_t + 3);

        if (enable_frame_hole_recess) {
            translate([x, y, base_t - frame_recess_depth])
                cylinder(d = frame_recess_d, h = frame_recess_depth + 1);
        }
    }
}

module feet_holes_cut() {
    if (enable_feet_holes) {
        for (x = [-foot_x, foot_x])
        for (y = [-foot_y, foot_y]) {
            translate([x, y, -1])
                cylinder(d = foot_hole_d, h = base_t + 3);
        }
    }
}

module endstop_pad() {
    if (enable_endstop_mount) {
        translate([endstop_pad_x, endstop_pad_y, base_t])
            cube([endstop_pad_w, endstop_pad_d, endstop_pad_h], center = true);
    }
}

module endstop_holes_cut() {
    if (enable_endstop_mount) {
        for (x = [-endstop_hole_spacing/2, endstop_hole_spacing/2]) {
            translate([
                endstop_pad_x + x,
                endstop_pad_y,
                base_t - 1
            ])
                cylinder(d = endstop_hole_d,
                         h = endstop_pad_h + 3);
        }
    }
}

module uln2003_standoffs() {
    if (enable_uln2003_mount) {
        for (x = [-uln_standoff_spacing_x/2, uln_standoff_spacing_x/2])
        for (y = [-uln_standoff_spacing_y/2, uln_standoff_spacing_y/2]) {
            translate([
                uln_center_x + x,
                uln_center_y + y,
                base_t
            ])
                cylinder(d = uln_standoff_d, h = uln_standoff_h);
        }
    }
}

module uln2003_holes_cut() {
    if (enable_uln2003_mount) {
        for (x = [-uln_standoff_spacing_x/2, uln_standoff_spacing_x/2])
        for (y = [-uln_standoff_spacing_y/2, uln_standoff_spacing_y/2]) {
            translate([
                uln_center_x + x,
                uln_center_y + y,
                base_t + uln_standoff_h - 3.0
            ])
                cylinder(d = uln_hole_d, h = 4.5);
        }
    }
}

module shallow_alignment_marks_cut() {
    if (enable_shallow_alignment_marks) {
        // Long shallow centerline mark along X through guide rods.
        translate([0, 0, base_t - mark_depth/2 + eps])
            cube([rod_spacing + 35, 1.4, mark_depth + 2*eps], center = true);

        // Short shallow centerline mark along Y through motor axis.
        translate([0, 0, base_t - mark_depth/2 + eps])
            cube([1.4, 55, mark_depth + 2*eps], center = true);
    }
}

// ---------------------------------------------------------
// Main model
// ---------------------------------------------------------

difference() {

    union() {
        // Main base plate.
        rounded_plate(base_w, base_d, base_t, base_corner_r);

        // Raised center boss around motor/coupler region.
        center_boss();

        // Lower guide rod socket towers.
        rod_socket_tower(-rod_x);
        rod_socket_tower( rod_x);

        // Endstop pad.
        endstop_pad();

        // ULN2003 optional standoffs.
        uln2003_standoffs();
    }

    // Center clearance hole for coupler/M6 rod path.
    center_clearance_cuts();

    // Shallow motor alignment pocket.
    motor_alignment_pocket_cut();

    // 28BYJ-48 motor tab mounting holes.
    motor_mount_holes_cut();

    // Guide rod blind socket holes.
    rod_socket_hole_cut(-rod_x);
    rod_socket_hole_cut( rod_x);

    // Generic frame/tube bracket mount holes.
    frame_mount_holes_cut();

    // Feet/riser holes.
    feet_holes_cut();

    // Endstop mounting holes.
    endstop_holes_cut();

    // ULN2003 board holes.
    uln2003_holes_cut();

    // Shallow centerline marks.
    shallow_alignment_marks_cut();
}