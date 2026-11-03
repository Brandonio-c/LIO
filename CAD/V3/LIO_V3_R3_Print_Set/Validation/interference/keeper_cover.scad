part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
at(0,0,deck_t) led_retainer();
at(0,0,deck_t+head_cover_h) rotate([180,0,0]) head_cover();
}
