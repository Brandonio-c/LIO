part_override="none";
include <../../LIO_V3_R3_master.scad>

intersection(){
for(i=[0:3]) let(p=rod_pts[i]) at(p[0],p[1],0) guide_housing(i==0?0:i==1?1:2);
at(0,0,-carriage_t) carriage();
}
