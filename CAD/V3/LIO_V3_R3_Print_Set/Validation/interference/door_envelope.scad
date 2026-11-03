part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
at(0,0,chamber_z) door();
difference(){at(0,0,chamber_z-1) cylinder(d=160,h=chamber_h+2); at(0,0,chamber_z-2) cylinder(d=chamber_od,h=chamber_h+4);}
}
