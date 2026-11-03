part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
guide_housing(0);
at(0,0,guide_flange_t-bearing_length) ring(bearing_od,rod_d,bearing_length);
}
