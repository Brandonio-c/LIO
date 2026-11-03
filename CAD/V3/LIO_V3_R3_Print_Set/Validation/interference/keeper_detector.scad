part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
at(0,0,deck_t) led_retainer();
installed_detector();
}
