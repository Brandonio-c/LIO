/*
 LIO / LEO V2.15 - Z-axis carrier + guide-bushing kit
 Prototype bolt-on hardware for the existing V2.14 moving top plate.

 PURPOSE
 - 2x adjustable lead-screw nut carriers
 - 2x removable nut retaining caps
 - 4x flanged guide-rod bushings
 - Support-free FDM geometry; all parts print flat.

 IMPORTANT
 The exact purchased lead-screw nut was not specified in the available CAD.
 Nut-pocket dimensions are therefore PARAMETRIC defaults and MUST be checked
 against the physical nut before printing the complete kit.

 V2.14 reference geometry:
   guide rods nominal 8.0 mm
   guide bores 8.6 mm
   lead screw stations x = +/-87 mm
   lead screw central clearance = 13 mm

 Set `part` below to export one component or a laid-out kit.
*/

$fn = 72;
eps = 0.02;
part = "kit"; // "kit", "carrier", "cap", "bushing", "carrier_preview"

// ---------- LEAD-SCREW / NUT INTERFACE ----------
lead_clearance_d = 13.0;       // matches V2.14 plate clearance
nut_body_d = 22.0;             // PARAMETRIC: measure actual flange/body
nut_body_h = 4.0;              // PARAMETRIC: captured body thickness
nut_flange_d = 30.0;           // PARAMETRIC: max flange diameter
nut_pocket_clearance = 0.35;   // diametric pocket clearance
nut_pocket_d = nut_body_d + nut_pocket_clearance;

// Optional anti-rotation flats in the circular pocket.
// Set 0 to disable. If your nut is round with screw flange, leave disabled.
nut_flat_width = 0;

// ---------- CARRIER BODY ----------
carrier_x = 54;
carrier_y = 42;
carrier_h = 9;
corner_r = 5;

// Four elongated mounting slots allow real-machine alignment.
mount_screw_d = 4.4;           // M4 clearance
mount_slot_len = 10.0;         // total slot length
mount_x = 20;
mount_y = 14;

// Recess nut from top; retaining cap traps it after alignment.
pocket_depth = 5.0;
cap_register_d = 34.0;
cap_register_depth = 1.2;

// Cap screws: M3, four at 90 degrees.
cap_screw_d = 3.4;
cap_bcd = 38.0;

// ---------- RETAINER CAP ----------
cap_d = 44.0;
cap_h = 3.0;
cap_center_d = lead_clearance_d;

// ---------- GUIDE BUSHING ----------
rod_d = 8.0;
rod_running_clearance = 0.35;  // diametric clearance for prototype printed bushing
bushing_id = rod_d + rod_running_clearance; // 8.35 mm
bushing_body_od = 12.0;
bushing_body_h = 18.0;
bushing_flange_od = 18.0;
bushing_flange_h = 3.0;
lead_in_h = 1.0;
lead_in_extra = 0.8;

// ---------- HELPERS ----------
module rounded_box(x,y,z,r){
    linear_extrude(height=z)
        offset(r=r)
            offset(delta=-r)
                square([x,y],center=true);
}

module slot_hole(len,d,h){
    hull(){
        translate([-(len-d)/2,0,0]) cylinder(d=d,h=h);
        translate([ +(len-d)/2,0,0]) cylinder(d=d,h=h);
    }
}

module carrier(){
    difference(){
        rounded_box(carrier_x,carrier_y,carrier_h,corner_r);

        // Lead screw through-hole
        translate([0,0,-eps])
            cylinder(d=lead_clearance_d,h=carrier_h+2*eps);

        // Nut capture pocket from top
        translate([0,0,carrier_h-pocket_depth])
            cylinder(d=nut_pocket_d,h=pocket_depth+eps);

        // Shallow cap locating register
        translate([0,0,carrier_h-cap_register_depth])
            difference(){
                cylinder(d=cap_register_d,h=cap_register_depth+eps);
                cylinder(d=nut_pocket_d-1.0,h=cap_register_depth+2*eps);
            }

        // Four adjustable M4 mounting slots; X-oriented for +/- alignment.
        for(x=[-mount_x,mount_x])
            for(y=[-mount_y,mount_y])
                translate([x,y,-eps])
                    slot_hole(mount_slot_len,mount_screw_d,carrier_h+2*eps);

        // Four cap screw clearance/tap pilot holes.
        for(a=[0:90:270])
            rotate([0,0,a])
                translate([cap_bcd/2,0,-eps])
                    cylinder(d=cap_screw_d,h=carrier_h+2*eps);
    }
}

module cap(){
    difference(){
        cylinder(d=cap_d,h=cap_h);
        translate([0,0,-eps]) cylinder(d=cap_center_d,h=cap_h+2*eps);
        for(a=[0:90:270])
            rotate([0,0,a])
                translate([cap_bcd/2,0,-eps])
                    cylinder(d=cap_screw_d,h=cap_h+2*eps);
    }
}

module bushing(){
    difference(){
        union(){
            cylinder(d=bushing_flange_od,h=bushing_flange_h);
            translate([0,0,bushing_flange_h])
                cylinder(d=bushing_body_od,h=bushing_body_h);
        }
        // Running bore with entry chamfer on flange side.
        translate([0,0,-eps])
            cylinder(d1=bushing_id+lead_in_extra,d2=bushing_id,
                     h=lead_in_h+eps);
        translate([0,0,lead_in_h-eps])
            cylinder(d=bushing_id,
                     h=bushing_flange_h+bushing_body_h-lead_in_h+2*eps);
    }
}

module nut_dummy(){
    color("silver",0.7){
        cylinder(d=nut_flange_d,h=2);
        translate([0,0,2]) cylinder(d=nut_body_d,h=nut_body_h);
    }
}

module carrier_preview(){
    color("dimgray") carrier();
    translate([0,0,carrier_h-pocket_depth]) nut_dummy();
    translate([0,0,carrier_h+0.2]) color("black",0.7) cap();
}

module kit(){
    // Two carriers
    translate([-32,28,0]) carrier();
    translate([ 32,28,0]) carrier();
    // Two caps
    translate([-24,-28,0]) cap();
    translate([ 24,-28,0]) cap();
    // Four bushings, flange on bed
    for(x=[-54,-18,18,54])
        translate([x,-62,0]) bushing();
}

if(part=="carrier") carrier();
else if(part=="cap") cap();
else if(part=="bushing") bushing();
else if(part=="carrier_preview") carrier_preview();
else kit();

// ---------- DESIGN CHECKS ----------
assert(bushing_id > rod_d,"Bushing bore must exceed rod diameter");
assert(pocket_depth <= carrier_h,"Nut pocket deeper than carrier");
assert(cap_bcd/2 + cap_screw_d/2 < cap_d/2,"Cap screw holes exceed cap edge");

echo(str("Guide rod nominal: ",rod_d," mm"));
echo(str("Printed bushing bore: ",bushing_id," mm"));
echo(str("Top plate holes must be drilled/reamed to approx: ",bushing_body_od+0.2," mm for bushing body"));
echo(str("Lead screw clearance: ",lead_clearance_d," mm"));
echo(str("DEFAULT nut pocket: ",nut_pocket_d," mm dia x ",pocket_depth," mm deep - VERIFY ACTUAL NUT"));
echo(str("Carrier mounting: M4 slots, +/-",(mount_slot_len-mount_screw_d)/2," mm adjustment along slot axis"));
