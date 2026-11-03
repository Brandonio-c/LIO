part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
at(0,0,locator_bottom_z) base_adapter();
retained_v2_base();
}
