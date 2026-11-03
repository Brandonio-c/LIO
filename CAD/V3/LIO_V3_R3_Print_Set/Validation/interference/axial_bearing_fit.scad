part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
axial_bridge();
at(0,0,axial_bridge_t-axial_bearing_h) ring(axial_bearing_od,axial_bearing_id,axial_bearing_h);
}
