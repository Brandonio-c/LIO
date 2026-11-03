part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
at(0,0,-shroud_flange_t-carriage_t) carriage();
shroud();
}
