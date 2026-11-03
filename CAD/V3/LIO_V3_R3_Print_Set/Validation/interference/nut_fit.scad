part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
nut_carrier();
at(0,0,-lead_nut_flange_t) metal_nut_ref();
}
