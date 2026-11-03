part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
for(s=[-1,1]) at(s*screw_x,0,-shroud_flange_t-carriage_t-carrier_t) nut_carrier();
shroud();
}
