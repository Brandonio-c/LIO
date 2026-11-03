part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
at(0,0,chamber_z) chamber();
retained_v2_base();
}
