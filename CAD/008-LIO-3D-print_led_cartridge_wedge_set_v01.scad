// Lio v0.1 — LED Cartridge / Wedge Set
// Units: millimeters
//
// This print generates four cartridge variants:
// 1. 5 mm through-hole LED cartridge
// 2. 3 mm through-hole LED cartridge
// 3. SMD / flat LED carrier cartridge
// 4. TO-can / metal-can cartridge
//
// Coordinate convention for each cartridge:
// - X axis = radial direction inside LED ring
//      +X = outside of ring / wire side
//      -X = inside of ring / sample side
// - Y axis = tangential width
// - Z axis = vertical
//
// The LED bore is angled about 45 degrees downward/inward.
// The body slides into the LED ring slot.
// The small hood extension points toward the sample side and helps block direct LED visibility.
//
// Designed to fit the previous Lio LED ring slot:
// - slot radial depth ~23 mm
// - slot tangential width ~9.5 mm
// - slot height ~10.5 mm
//
// Print orientation:
// - Flat on bed.
// - No supports should be needed for the outer body.
// - Angled bores may bridge slightly; clean with a drill bit by hand if needed.
//
// Material:
// - PETG preferred.

$fn = 96;
eps = 0.05;

// ---------------------------------------------------------
// Cartridge slot-fit dimensions
// ---------------------------------------------------------

body_len = 19.5;       // radial length inside ring slot
body_w   = 8.6;        // tangential width; below 9.5 mm slot width
body_h   = 9.6;        // vertical height; below 10.5 mm slot height

hood_len = 3.0;        // small inner light hood extension
hood_h   = 5.0;        // hood height
hood_w   = body_w;

total_len = body_len + hood_len;

// Small chamfer-like clearance by cutting tiny edge reliefs? Disabled for simplicity.
enable_corner_relief = false;

// ---------------------------------------------------------
// Angled bore geometry
// ---------------------------------------------------------

// Bore axis angle.
// 45 degrees downward/inward means cylinder axis roughly points in -X and -Z.
// The OpenSCAD cylinder default axis is +Z.
// rotate([0, -135, 0]) maps +Z toward [-X, 0, -Z].
bore_rot_y = -135;

// Long enough to cut through the whole cartridge diagonally.
bore_cut_len = 42;

// Bore center location.
// Increase bore_center_z if the bore exits too low.
// Decrease if the bore exits too high.
bore_center_x = 0;
bore_center_z = body_h * 0.68;

// Through-hole LED bore diameters.
// Slightly oversized for real printed clearance.
bore_5mm_d = 5.4;
bore_3mm_d = 3.4;
bore_tocan_d = 6.8;

// Wire channel geometry.
wire_channel_w = 3.0;
wire_channel_h = 2.2;
wire_channel_len = 10.0;

// Retention hole through cartridge.
// This can be used with an M3 screw/pin if you revise the ring to clamp cartridges.
enable_retention_hole = true;
retention_hole_d = 3.2;
retention_hole_x = 5.5;
retention_hole_z = body_h * 0.52;

// Label settings
enable_labels = true;
label_size = 3.2;
label_depth = 0.5;

// Layout spacing for printing multiple cartridges
part_spacing = 34;

// ---------------------------------------------------------
// SMD carrier pocket geometry
// ---------------------------------------------------------

// This pocket is intentionally generic.
// It is for small SMD LED boards or carrier PCBs.
// You should revise after measuring the actual SMD emitter/PCB.
smd_pocket_w = 7.5;        // along Y
smd_pocket_l = 9.0;        // along X/Z rotated plane
smd_pocket_depth = 1.4;    // pocket depth
smd_wire_slot_w = 3.0;

// ---------------------------------------------------------
// Helper modules
// ---------------------------------------------------------

module cartridge_solid(label_txt = "") {
    union() {
        // Main rectangular body.
        translate([0, 0, body_h/2])
            cube([body_len, body_w, body_h], center = true);

        // Inner hood extension on sample side.
        // This gives the LED a short shroud so the detector is less likely to see the LED directly.
        translate([-body_len/2 - hood_len/2, 0, hood_h/2])
            cube([hood_len, hood_w, hood_h], center = true);
    }

    // Raised label on top.
    if (enable_labels) {
        translate([0, 0, body_h + 0.02])
            linear_extrude(height = label_depth)
                text(label_txt,
                     size = label_size,
                     font = "Liberation Sans:style=Bold",
                     halign = "center",
                     valign = "center");
    }
}

module angled_round_bore(d) {
    translate([bore_center_x, 0, bore_center_z])
        rotate([0, bore_rot_y, 0])
            cylinder(d = d, h = bore_cut_len, center = true);
}

module wire_channel_cut() {
    // Simple top/outer-side wire relief channel.
    // Gives LED legs/wires somewhere to exit toward the outside of the ring.
    translate([body_len/2 - wire_channel_len/2 + 1.5, 0, body_h - wire_channel_h/2 + eps])
        cube([wire_channel_len, wire_channel_w, wire_channel_h + 2*eps], center = true);
}

module retention_hole_cut() {
    if (enable_retention_hole) {
        // Hole through Y direction.
        translate([retention_hole_x, 0, retention_hole_z])
            rotate([90, 0, 0])
                cylinder(d = retention_hole_d, h = body_w + 3, center = true);
    }
}

module led_round_cartridge(label_txt, bore_d) {
    difference() {
        cartridge_solid(label_txt);

        // Angled LED body/lens bore.
        angled_round_bore(bore_d);

        // Small wire channel.
        wire_channel_cut();

        // Optional retention hole.
        retention_hole_cut();
    }
}

module smd_pocket_cut() {
    // A tilted rectangular pocket on the same 45-degree aiming plane.
    // The pocket is made by subtracting a rotated rectangular box.
    // It creates a flat angled seat for an SMD LED carrier board.
    translate([bore_center_x, 0, bore_center_z])
        rotate([0, bore_rot_y, 0])
            cube([smd_pocket_l, smd_pocket_w, smd_pocket_depth], center = true);
}

module smd_wire_slot_cut() {
    // Wider top-side slot for SMD wires or small carrier-board leads.
    translate([body_len/2 - wire_channel_len/2 + 1.5, 0, body_h - wire_channel_h/2 + eps])
        cube([wire_channel_len + 3, smd_wire_slot_w, wire_channel_h + 2*eps], center = true);
}

module smd_cartridge() {
    difference() {
        cartridge_solid("SMD");

        smd_pocket_cut();
        smd_wire_slot_cut();
        retention_hole_cut();

        // Add a small optical aperture through the sloped pocket.
        // This gives light a route if the SMD emitter sits slightly recessed.
        translate([bore_center_x - 1.5, 0, bore_center_z - 1.5])
            rotate([0, bore_rot_y, 0])
                cylinder(d = 3.0, h = bore_cut_len, center = true);
    }
}

module tocan_cartridge() {
    difference() {
        cartridge_solid("TO");

        // Larger angled bore for TO-can/metal-can emitter.
        angled_round_bore(bore_tocan_d);

        // Larger wire channel for metal-can leads.
        translate([body_len/2 - wire_channel_len/2 + 1.5, 0, body_h - wire_channel_h/2 + eps])
            cube([wire_channel_len + 4, 4.0, wire_channel_h + 2*eps], center = true);

        retention_hole_cut();
    }
}

// ---------------------------------------------------------
// Output: four cartridges side by side
// ---------------------------------------------------------

translate([-1.5 * part_spacing, 0, 0])
    led_round_cartridge("5mm", bore_5mm_d);

translate([-0.5 * part_spacing, 0, 0])
    led_round_cartridge("3mm", bore_3mm_d);

translate([0.5 * part_spacing, 0, 0])
    smd_cartridge();

translate([1.5 * part_spacing, 0, 0])
    tocan_cartridge();