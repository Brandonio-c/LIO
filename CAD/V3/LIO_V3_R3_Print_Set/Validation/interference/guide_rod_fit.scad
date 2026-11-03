part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
guide_housing(0);
at(0,0,-bearing_length-2) cylinder(d=rod_d,h=bearing_length+guide_flange_t+4);
}
