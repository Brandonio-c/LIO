part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
at(0,0,mid_h) shroud();
at(0,0,chamber_z) chamber();
}
