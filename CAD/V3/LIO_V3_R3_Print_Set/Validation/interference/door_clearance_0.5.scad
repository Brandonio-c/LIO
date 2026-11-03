part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
at(0,-0.5,chamber_z) door();
at(0,0,chamber_z) chamber();
}
