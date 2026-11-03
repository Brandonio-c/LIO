part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
optical_deck();
at(0,0,deck_t) led_retainer();
}
