part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
led_package_ref(12);
at(0,0,deck_t) led_retainer();
}
