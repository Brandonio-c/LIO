/*
 LIO V2.14 - Compact flat supportless moving top plate

 Changes from V2.13
 - Reduced footprint: 205 x 195 mm (was 230 x 220)
 - Completely flat top and bottom faces: no towers, pads, ribs, or raised bosses
 - Intended to print flat with NO supports
 - Retains exact optical-head interface: 118 mm opening, 4x M4 on 126 mm BCD @45deg
 - Four guide-rod through bores retained
 - Two lead-screw stations retained with central clearance + universal M3 radial slots

 IMPORTANT:
 Guide-rod and lead-screw XY coordinates remain parameterized because their exact
 centers were not defined in the optical-head SCAD. Defaults preserve the V2.13
 photographed-frame starting geometry while fitting inside this smaller plate.
*/

$fn = 128;
eps = 0.05;

// ---------------- MAIN PLATE ----------------
plate_x = 205;
plate_y = 195;
plate_t = 8;
corner_r = 8;

// ------------- OPTICAL HEAD INTERFACE -------------
// Matches LIO V2.9/V2.8 integrated optical shroud mount.
optical_opening_d = 118.0;
optical_mount_bcd = 126.0;
optical_mount_angle = 45.0;
optical_mount_hole_d = 4.5;  // M4 clearance
optical_mount_n = 4;

// Optional shallow underside locating recess. Leave 0 for two perfectly flat faces.
// The 118 mm opening itself clears the 117 mm locating pilot.
optical_seat_depth = 0;
optical_seat_d = 141.0;

// ---------------- GUIDE RODS ----------------
// Compact supportless design: bores pass directly through plate.
guide_rod_d = 8.0;
guide_bore_d = 8.6;
guide_x = 92;
guide_y = 78;

// Optional countersunk/chamfer lead-in from underside; 0 disables for pure simple bores.
guide_leadin_h = 1.2;
guide_leadin_d = 9.4;

// --------------- LEAD-SCREW DRIVES ---------------
// Moved slightly inward versus V2.13 to retain edge material on compact plate.
lead_x = 87;
lead_y = 0;
lead_clearance_d = 13.0;

// Four M3-compatible radial through-slots per station.
// Accommodates a range of common flange-nut bolt patterns without raised pads.
lead_slot_w = 3.6;
lead_slot_inner_r = 8.0;
lead_slot_outer_r = 13.0;
lead_slot_angles = [0,90,180,270];

// Optional shallow underside nut register; 0 keeps bottom completely flat too.
lead_nut_recess_d = 23.0;
lead_nut_recess_depth = 0;

// ---------------- CABLE ROUTING ----------------
// Compact rear cable slot, kept away from optical-head mounting holes.
cable_slot_w = 12;
cable_slot_l = 24;
cable_slot_x = 0;
cable_slot_y = 85;
strain_hole_d = 4.5;
strain_hole_spacing = 16;

// ---------------- HELPERS ----------------
module rounded_rect_2d(x,y,r){
    offset(r=r)
        square([x-2*r,y-2*r],center=true);
}

module plate_blank(){
    linear_extrude(height=plate_t)
        rounded_rect_2d(plate_x,plate_y,corner_r);
}

module optical_cutouts(){
    translate([0,0,-eps])
        cylinder(d=optical_opening_d,h=plate_t+2*eps);

    for(i=[0:optical_mount_n-1]){
        a=optical_mount_angle+i*360/optical_mount_n;
        rotate([0,0,a])
            translate([optical_mount_bcd/2,0,-eps])
                cylinder(d=optical_mount_hole_d,h=plate_t+2*eps);
    }

    if(optical_seat_depth>0)
        translate([0,0,-eps])
            difference(){
                cylinder(d=optical_seat_d,h=optical_seat_depth+eps);
                cylinder(d=optical_opening_d,h=optical_seat_depth+2*eps);
            }
}

module guide_cutouts(){
    for(x=[-guide_x,guide_x])
        for(y=[-guide_y,guide_y]){
            translate([x,y,-eps])
                cylinder(d=guide_bore_d,h=plate_t+2*eps);
            if(guide_leadin_h>0)
                translate([x,y,-eps])
                    cylinder(d1=guide_leadin_d,d2=guide_bore_d,h=guide_leadin_h+eps);
        }
}

module lead_cutouts(){
    for(x=[-lead_x,lead_x]){
        translate([x,lead_y,-eps])
            cylinder(d=lead_clearance_d,h=plate_t+2*eps);

        for(a=lead_slot_angles)
            translate([x,lead_y,0])
                rotate([0,0,a])
                    hull(){
                        translate([lead_slot_inner_r,0,-eps])
                            cylinder(d=lead_slot_w,h=plate_t+2*eps);
                        translate([lead_slot_outer_r,0,-eps])
                            cylinder(d=lead_slot_w,h=plate_t+2*eps);
                    }

        if(lead_nut_recess_depth>0)
            translate([x,lead_y,-eps])
                cylinder(d=lead_nut_recess_d,h=lead_nut_recess_depth+eps);
    }
}

module cable_cutouts(){
    translate([cable_slot_x,cable_slot_y,-eps])
        linear_extrude(height=plate_t+2*eps)
            offset(r=2)
                square([cable_slot_l-4,cable_slot_w-4],center=true);

    for(dx=[-strain_hole_spacing/2,strain_hole_spacing/2])
        translate([cable_slot_x+dx,cable_slot_y-13,-eps])
            cylinder(d=strain_hole_d,h=plate_t+2*eps);
}

module compact_flat_top_plate(){
    difference(){
        plate_blank();
        optical_cutouts();
        guide_cutouts();
        lead_cutouts();
        cable_cutouts();
    }
}

compact_flat_top_plate();

// ---------------- CHECKS ----------------
echo("LIO V2.14 compact flat supportless top plate");
echo(str("Plate: ",plate_x," x ",plate_y," x ",plate_t," mm"));
echo(str("Optical opening: ",optical_opening_d," mm"));
echo(str("Optical mount: 4 x M4 clearance on ",optical_mount_bcd," mm BCD @ 45 deg"));
echo(str("Guide rods: X +/-",guide_x," Y +/-",guide_y," bore ",guide_bore_d," mm"));
echo(str("Lead drives: X +/-",lead_x," central clearance ",lead_clearance_d," mm"));

assert(optical_opening_d > 117.0,"Optical opening must clear 117 mm optical-head locating pilot");
assert(optical_mount_bcd/2 + optical_mount_hole_d/2 < min(plate_x,plate_y)/2,
       "Optical mounting holes exceed plate boundary");
assert(guide_x + guide_bore_d/2 < plate_x/2,
       "Guide bore exceeds plate X edge");
assert(guide_y + guide_bore_d/2 < plate_y/2,
       "Guide bore exceeds plate Y edge");
assert(lead_x + lead_slot_outer_r + lead_slot_w/2 < plate_x/2,
       "Lead-screw mounting slots exceed plate X edge");
assert(cable_slot_y + cable_slot_w/2 < plate_y/2,
       "Cable slot exceeds plate Y edge");
