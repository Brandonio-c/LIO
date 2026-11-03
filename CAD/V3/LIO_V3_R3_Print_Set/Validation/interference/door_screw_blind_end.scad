part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
chamber();
for(a=panel_angles,z=panel_screw_z) radial(a,panel_or-panel_head_depth-panel_screw_length,z){ cylinder(d=3,h=panel_screw_length); at(0,0,panel_screw_length) cylinder(d=5.7,h=1.8); }
}
