part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
at(0,0,chamber_z) chamber();
for(s=[-1,1]) translate([s*screw_x,0,axial_bridge_bottom_z]) scale([s,1,1]) axial_bridge();
}
