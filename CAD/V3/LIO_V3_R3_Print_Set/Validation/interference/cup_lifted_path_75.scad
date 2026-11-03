part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
at(0,-75,chamber_z+sample_seat_h+5) cylinder(d=cup_od,h=cup_h);
union(){at(0,0,chamber_z) chamber();at(0,0,chamber_z) sample_nest();}
}
