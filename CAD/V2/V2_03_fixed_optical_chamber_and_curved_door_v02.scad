// LIO V2.2 - Fixed Optical Chamber + Curved Sliding Light-Trap Door
// Units: mm
// Two separate printable objects in one SCAD file.
// Chamber prints upright. Curved door prints upright beside it.

$fn = 160;
eps = 0.08;

// -------------------- OUTPUT --------------------
part = "both"; // "both", "chamber", "door"

// -------------------- CHAMBER --------------------
chamber_od = 91.0;
chamber_id = 81.0;
chamber_h  = 120.0;
chamber_r  = chamber_od/2;

// Fits over the V2_02 short datum/guard ring (~84 mm OD).
lower_socket_id    = 84.6;
lower_socket_depth = 8.0;

// Future electronics/top plate plug interface.
top_plug_receiver_id = 80.0;
top_plug_depth       = 14.0;

// -------------------- SAMPLE ACCESS --------------------
// Front is -Y (270 degrees around Z).
access_angle    = 90.0;  // ~71.5 mm arc at chamber OD
access_h        = 55.0;
access_bottom_z = 12.0;
access_start    = 270 - access_angle/2;

// -------------------- CURVED DOOR --------------------
// Door wraps farther than the opening to create a circumferential light overlap.
door_angle      = 118.0;
door_overlap_a  = (door_angle-access_angle)/2; // 14 deg each side

door_t          = 3.0;
door_radial_gap = 0.70; // PETG sliding clearance from chamber OD
door_inner_r    = chamber_r + door_radial_gap;
door_outer_r    = door_inner_r + door_t;

door_h          = 70.0; // gives 7.5 mm vertical overlap above/below 55 mm opening
door_closed_z   = access_bottom_z - (door_h-access_h)/2;
door_start      = 270 - door_angle/2;

// Guide lips: outside the curved door edges, leaving the door free to slide vertically.
rail_angle_w    = 7.0;
rail_radial_gap = 0.45;
rail_t          = 3.0;
rail_inner_r    = door_outer_r + rail_radial_gap;
rail_outer_r    = rail_inner_r + rail_t;
rail_h          = 100.0;
rail_bottom_z   = door_closed_z;
rail_edge_a     = door_angle/2;

// Small bottom stops at the two door edges.
stop_angle_w = 8.0;
stop_h       = 3.0;

// Door handle/tab.
handle_w = 24.0;
handle_h = 9.0;
handle_t = 4.0;

// -------------------- PRINT LAYOUT --------------------
// Door stands upright beside chamber, well separated.
door_layout_x = 115.0;

// -------------------- HELPERS --------------------
module ring(od,id,h){
    difference(){
        cylinder(d=od,h=h);
        translate([0,0,-eps]) cylinder(d=id,h=h+2*eps);
    }
}

// Annular sector between radii r1/r2, spanning 'angle' degrees from +X.
module annular_sector(r1,r2,h,angle){
    rotate_extrude(angle=angle, convexity=10)
        translate([r1,0,0])
            square([r2-r1,h],center=false);
}

// Wedge used to remove a full radial sector from the chamber wall.
module radial_wedge(r,h,angle){
    // A very thin inner radius avoids rotate_extrude degeneracy at r=0.
    annular_sector(0.01,r,h,angle);
}

module access_cut(){
    rotate([0,0,access_start])
        translate([0,0,access_bottom_z])
            radial_wedge(chamber_r+8,access_h,access_angle);
}

module curved_door_shell(){
    rotate([0,0,door_start])
        annular_sector(door_inner_r,door_outer_r,door_h,door_angle);
}

module guide_lips(){
    // Two narrow outer retaining lips positioned at the door's angular edges.
    for(a=[270-rail_edge_a,270+rail_edge_a]){
        rotate([0,0,a-rail_angle_w/2])
            translate([0,0,rail_bottom_z])
                annular_sector(rail_inner_r,rail_outer_r,rail_h,rail_angle_w);
    }
}

module bottom_stops(){
    // Stops only at the two edge channels; center remains completely open for sample access.
    for(a=[270-rail_edge_a,270+rail_edge_a]){
        rotate([0,0,a-stop_angle_w/2])
            translate([0,0,door_closed_z])
                annular_sector(chamber_r+0.4,rail_outer_r,stop_h,stop_angle_w);
    }
}

module chamber(){
    difference(){
        union(){
            ring(chamber_od,chamber_id,chamber_h);
            guide_lips();
            bottom_stops();
        }

        // Large 90-degree curved sample loading aperture.
        access_cut();

        // Lower locating socket over the V2_02 datum/guard ring.
        translate([0,0,-eps])
            cylinder(d=lower_socket_id,h=lower_socket_depth+eps);

        // Defined top receiver for the future electronics/detector plate plug.
        translate([0,0,chamber_h-top_plug_depth])
            cylinder(d=top_plug_receiver_id,h=top_plug_depth+eps);
    }
}

module curved_door(){
    union(){
        curved_door_shell();

        // External thumb handle near top center of door.
        // It sits radially outside the shell and does not enter the chamber.
        translate([0,-(door_outer_r + handle_t/2 - 0.8),door_h-handle_h-5])
            cube([handle_w,handle_t,handle_h],center=true);
    }
}

// -------------------- OUTPUT --------------------
if(part=="chamber") chamber();

if(part=="door") curved_door();

if(part=="both"){
    chamber();
    translate([door_layout_x,0,0]) curved_door();
}
