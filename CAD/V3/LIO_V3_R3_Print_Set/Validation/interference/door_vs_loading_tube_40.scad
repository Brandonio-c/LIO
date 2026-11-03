part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
at(0,-40,chamber_z) door();
at(0,0,loading_h) shroud();
}
