part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
union(){axial_bridge();at(0,0,axial_bridge_t) axial_cap();}
at(0,0,axial_bridge_t) ring(shaft_collar_od,screw_d,shaft_collar_h);
}
