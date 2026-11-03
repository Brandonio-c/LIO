/*
LIO V3 / R3 - CONSOLIDATED BOTTOM-UP PRINT SET - 2026-10-04
Units mm. Front -Y. Z=0 is the UNDERSIDE of the RETAINED motor base.
DERIVED FROM supplied LIO_V3_master.scad (R2) and the P1 consolidation plan.

IMPLEMENTED changes: one integrated base adapter; 16 angled LED seats inside
one deck; one common LED flange-retaining plate; eight numbered print jobs.
No printed bolts, lead-nut threads, door hooks or bayonet locks.

DEVELOPMENT CAD - physical hardware and printer fits are NOT qualified.
The screw/nut, guide bearing, axial bearing, insert, LED, detector PCB and cup
values below are explicit example profiles. Replace with actual measurements.
CAD checks do not qualify motor torque, axial load capacity, light rejection,
safety stops, homing, polymer creep or electrical operation.
Do not slice the assembly: hardware and the existing base are REFERENCES.
Read README.md. First run the relevant fit coupons in the final print material.

Job counts: 1=2, 2=18, 3=2, 4=1, 5=1, 6=3, 7=1, 8=1 optional.
Total: 28 core printed pieces + one optional guide tie. Hardware excluded.
All new mating parts use this SINGLE parameter block. Keep launchers beside it.
No external SCAD libraries or STL imports are needed by this file.
*/
/* [Output] */
part = "assembly"; // [assembly,exploded,section,sample_module,optical_module,job,base_adapter,sample_nest,chamber,door,carriage,shroud,optical_deck,led_retainer,detector_mount,head_cover,guide_primary,guide_secondary,guide_float,guide_cap,nut_carrier,axial_bridge,axial_cap,axial_spacer,guide_tie,datum_template,cylinder_coupon,closure_coupon,hardware_coupon,led_coupon,collision_check]
job = 1; // [1:8]
z_state = "loading"; // [low,mid,high,loading,custom]
custom_deck_z = 220;
door_open = false;
show_hardware = true;
show_optical_rays = false;
show_upper_tie = true;
show_electronics_cover = true;
preview_shroud_alpha = 0.24;
quality = 96; // [48:16:192]

/* [Release gates - do not mark verified without measurements] */
production_release = false;
base_as_built_verified = false;
screw_nut_verified = false;
guide_bearing_verified = false;
axial_support_verified = false;
led_packages_verified = false;
detector_board_verified = false;
cup_verified = false;
print_coupons_verified = false;

/* [Retained base datums - source values, DO NOT independently edit parts] */
base_top_z = 10;
base_recess_d = 92;
base_recess_depth = 0.8;
guide_x = 78;
guide_y = 55;
rod_d = 8;
screw_x = 74;
motor_body_x = 82;
motor_tower_d = 48;
motor_tower_top_z = 41;
coupler_collar_d = 36;
coupler_collar_top_z = 53;
frame_x = 98;
frame_y = 42;
frame_boss_top_z = 17;

/* [Stationary mounting and enclosure - proposed coupon dimensions] */
locator_pilot_d = 91.4;
locator_pilot_h = 0.7;
locator_top_d = 94;
// R3 has no inter-part locator pins: ring and saddle are one body.
saddle_t = 6;
chamber_od = 107;
chamber_wall = 3.5;
chamber_h = 140;
chamber_mount_t = 4;
chamber_mount_x = 22;
chamber_mount_y = 60;
chamber_mount_hole_d = 3.4;
frame_bolt_clearance = 3.4; // example M3 through to existing inserts; verify

/* [Sample panel and metal hardware] */
port_w = 60; // full clear chord width in rectangular part
port_bottom = 18;
port_rect_h = 50; // R3 adds lift clearance over the 4 mm sample-nest rim
port_crown_h = 24; // 45-degree shoulders leave only 12 mm crown bridge
panel_overlap = 10;
panel_fit = 0.35; // per-edge geometric clearance, not print accuracy
panel_recess = 0.3; // radial recess below chamber envelope
panel_t = 4;
seal_compressed_t = 0.6; // candidate opaque gasket, not a printed gasket
panel_screw_d = 3.4;
panel_screw_length = 6; // under-head example: verify against actual head/insert stack
panel_head_d = 6.6;
panel_head_depth = 2.2; // SELECT a metal low-profile head fitting this recess
panel_insert_pilot = 4.2; // EXAMPLE ONLY: match actual heat-set insert and coupon
panel_insert_depth = 5.0;
panel_insert_boss_d = 11;
panel_screw_angle = 41; // left/right about -Y; same transform used on both parts

/* [Moving enclosure and carriage] */
shroud_id = 110;
shroud_wall = 2.5;
shroud_length = 130; // from optical deck underside to open lower edge
shroud_flange_t = 4;
shroud_leadin_h = 3;
shroud_leadin_id = 112;
head_body_d = 122; // no inherited 140 mm disc at screw axes
head_bolt_r = 66;
head_ear_d = 16;
head_pilot_d = 117;
head_pilot_h = 3;
carriage_opening_d = 118;
carriage_w = 200;
carriage_d = 160;
carriage_t = 8;
head_bolt_d = 4.5; // M4 through, metal nuts under carriage
m4_nut_af = 7.4; // measured/coupon value required
m4_nut_h = 3.4;
deck_t = 10;
min_overlap = 40; // screening requirement, optical test still required
collar_safety = 2;

/* [Unverified screw / guide hardware envelopes] */
screw_d = 8; // unknown thread: visual envelope only, not T8 specification
thread_start_z = 55; // usable endpoint MUST be measured
thread_end_z = 286.3; // illustrative: 45 + 241.3, not established usable travel
thread_end_margin = 10;
guide_top_z = 315; // unmeasured rod endpoint
bearing_od = 12; // EXAMPLE cylindrical guide bearing, not selected catalog item
bearing_length = 20;
bearing_seat_extra = 0.3; // diametric
bearing_housing_od = 18;
guide_flange_t = 4;
guide_cap_t = 2;
guide_float_x = 0.75;
guide_float_xy = 0.75;
float_sleeve_od = 4; // metal shoulder/spacer OD around M3, verify actual hardware
float_axial_play = 0.15; // metal spacer length = flange_t + this amount

/* [Unverified manufactured flanged lead nut] */
lead_nut_body_d = 10;
lead_nut_flange_d = 22;
lead_nut_flange_t = 3.5;
lead_nut_total_h = 15;
lead_nut_bcd = 16;
lead_nut_bolt_d = 3.4;
lead_nut_bolt_phase = 45;
carrier_w = 26;
carrier_d = 46;
carrier_t = 6;
carrier_adjust = 1.5; // +/-X assembly adjustment, locked after alignment

/* [Unverified axial bearing and shaft collars] */
axial_bearing_id = 8;
axial_bearing_od = 22;
axial_bearing_h = 7;
axial_seat_extra = 0.3;
axial_inner_clearance = 16;
axial_bridge_t = 10;
axial_bridge_bottom_z = 70;
axial_cap_t = 2.5;
shaft_collar_od = 14;
shaft_collar_h = 5;
// Bearings must be rated for axial load; both inner/outer races must be retained.
// This example support does NOT authorize loading an unidentified bearing/motor.

/* [Sample / optical hardware - developmental examples] */
cup_od = 50;
cup_h = 40;
cup_fit_d = 1.0;
sample_seat_h = 18; // relative to saddle top, matches port sill
led_count = 16;
led_ring_r = 35;
led_body_d = 5;
led_hole_extra = 0.4;
led_flange_d = 6.2;
led_flange_t = 1.0;          // EXAMPLE physical LED flange thickness
led_body_length = 7.0;      // EXAMPLE flange front to lens tip along optical axis
led_flange_extra = 0.6;     // diametric pocket allowance, verify coupon
led_lead_exit_d = 4.2;      // keeper lead hole SMALLER than flange, verify lead pair
led_capture_gap = 0.20;     // axial endplay; optional compliant pad can take this up
led_flange_front_below_top = 0.8; // front face center below deck top (world vertical)
led_retainer_t = 3.0;
// Empty array means 16 copies of the example above. Or provide exactly 16 rows:
// [body_d, flange_d, flange_t, body_length, lead_exit_d]. No spectral identity implied.
led_profiles = [];
led_target_drop_override = 0; // 0 aims at proposed sample plane at middle Z
opt101_pcb_w = 28;
opt101_pcb_d = 22;
opt101_hole_dx = 22;
opt101_hole_dy = 16;
opt101_mount_d = 2.2;
detector_aperture_d = 6.5;
detector_tube_od = 18;
detector_tube_length = 16;
head_cover_h = 30;

/* [Hidden] */
output_part = is_undef(part_override) ? part : part_override;
output_job = is_undef(job_override) ? job : job_override;
eps = 0.035;
$fn = $preview ? min(quality,64) : quality;
chamber_id = chamber_od-2*chamber_wall;
R = chamber_od/2;
Ri = chamber_id/2;
shroud_od = shroud_id+2*shroud_wall;
saddle_z = frame_boss_top_z;
chamber_z = saddle_z+saddle_t;
chamber_top_z = chamber_z+chamber_h;
locator_bottom_z = base_top_z-locator_pilot_h;
locator_h = saddle_z-locator_bottom_z;
base_adapter_h = chamber_z-locator_bottom_z;
port_top = port_bottom+port_rect_h+port_crown_h;
panel_bottom = port_bottom-panel_overlap;
panel_top = port_top+panel_overlap;
panel_w = port_w+2*panel_overlap;
panel_or = R-panel_recess;
panel_ir = panel_or-panel_t;
seat_r = panel_ir-seal_compressed_t;
frame_ir = seat_r-5;
panel_screw_z = [panel_bottom+5,panel_top-5];
panel_angles = [-90-panel_screw_angle,-90+panel_screw_angle];
head_angles = [45,135,225,315];
opt_keeper_angles = [11.25,101.25,191.25,303.75]; // asymmetric: keeper cannot rotate into wrong channel indexing
cover_angles = [90,210,330];
rod_pts = [[-guide_x,guide_y],[guide_x,guide_y],[-guide_x,-guide_y],[guide_x,-guide_y]];
// Native guide housing: body -bearing_length..0, flange 0..4, cap 4..6.
// Nut occupies h-21.5 .. h-6.5 with default stack.
nut_bottom_offset = -(shroud_flange_t+carriage_t+carrier_t+lead_nut_flange_t);
nut_top_offset = nut_bottom_offset+lead_nut_total_h;
thread_low_h = thread_start_z+thread_end_margin-nut_bottom_offset;
thread_high_h = thread_end_z-thread_end_margin-nut_top_offset;
tie_bottom_z = guide_top_z-15;
max_guide_h = min(guide_top_z-5-(guide_flange_t+guide_cap_t-shroud_flange_t),
                  tie_bottom_z-8-(guide_flange_t+guide_cap_t-shroud_flange_t));
min_deck_h = max(coupler_collar_top_z+collar_safety+shroud_length,
                 thread_low_h,chamber_top_z+8);
max_mech_h = min(thread_high_h,max_guide_h);
max_measure_h = min(chamber_top_z+shroud_length-min_overlap,max_mech_h);
loading_h = min(max_mech_h,chamber_z+panel_top+12+shroud_length);
mid_h = (min_deck_h+max_measure_h)/2;
h = z_state=="low" ? min_deck_h : z_state=="mid" ? mid_h :
    z_state=="high" ? max_measure_h : z_state=="custom" ? custom_deck_z : loading_h;
sample_z = chamber_z+sample_seat_h+cup_h;
led_target_drop = led_target_drop_override>0 ? led_target_drop_override : mid_h-sample_z;
led_tilt = atan(led_ring_r/led_target_drop);
led_flange_front_axis = (deck_t-led_flange_front_below_top)/cos(led_tilt);
function led_profile(i) = len(led_profiles)==0 ?
    [led_body_d,led_flange_d,led_flange_t,led_body_length,led_lead_exit_d] : led_profiles[i];
function led_back_axis(i) = led_flange_front_axis+led_profile(i)[2];
carriage_top_z = h-shroud_flange_t;
carriage_bottom_z = carriage_top_z-carriage_t;
axial_spacer_h = axial_bridge_bottom_z-(saddle_z+saddle_t);
axial_bearing_bottom = axial_bridge_bottom_z+axial_bridge_t-axial_bearing_h;

function overlap_at(zz) = max(0,min(chamber_top_z,zz)-max(chamber_z,zz-shroud_length));
function p2(r,a) = [r*cos(a),r*sin(a)];
function hypot(x,y)=sqrt(x*x+y*y);
function on_bed_mode() = !(part=="assembly" || part=="exploded" || part=="section" || part=="collision_check");

assert(guide_x==78 && guide_y==55 && screw_x==74 && frame_x==98 && frame_y==42 && base_top_z==10,
       "Retained V2 base datums are frozen; record as-built offsets instead of moving nominal axes");
assert(h>=min_deck_h && h<=max_mech_h,"Selected Z is outside modeled mechanical limits");
assert(chamber_id>0 && shroud_id>chamber_od,"Invalid chamber/shroud diameters");
assert(screw_x-coupler_collar_d/2-R>=1,"Fixed chamber too close to base coupler collars");
assert(min_deck_h<max_measure_h,"No enclosure-limited measurement travel with these parameters");
assert(loading_h-shroud_length>=chamber_z+panel_top+6,"Loading position does not clear panel removal path");
assert(lead_nut_flange_d+2<=carrier_w,"Chosen nut does not fit carrier wall envelope");
assert(screw_x-carrier_w/2>shroud_od/2+1,"Carrier collides with moving tube");
assert(screw_x-head_body_d/2-screw_d/2>=3,"Optical flange crowds screw shaft");
assert(head_bolt_r-head_bolt_d/2-carriage_opening_d/2>=4,"Insufficient optical mounting ligament");
assert(port_crown_h<=port_w/2-4,"Crown leaves insufficient short bridge");
assert(panel_ir>frame_ir && panel_t>panel_head_depth+1,"Panel screw floor too thin");
assert(panel_screw_length <= panel_t-panel_head_depth+panel_insert_depth-0.5,
       "Door screw would bottom in blind insert pilot");
assert(panel_screw_length-(panel_t-panel_head_depth)>=3,
       "Insufficient candidate door thread engagement");
assert(led_count==16,"Baseline requires 16 LED positions");
assert(cup_od+6<=port_w && cup_h+5<=port_rect_h,"Cup plus loading allowance exceeds the rectangular port; resize and revalidate");
assert(bearing_od+bearing_seat_extra+3<bearing_housing_od,"Bearing housing wall too thin");
assert(shaft_collar_od+1<axial_inner_clearance,"Rotating shaft collar would contact stationary bearing support");
assert(led_tilt<20,"Integrated seats qualified geometrically only below 20 degrees; recheck envelope for steeper aim");
assert(len(led_profiles)==0 || len(led_profiles)==16,"Provide all 16 LED package rows or use the explicit default example");
for(i=[0:15]) let(p=led_profile(i)) {
    assert(p[1]>p[0]+led_hole_extra+0.4,"LED flange too small for positive locating shoulder");
    assert(p[4]>0 && p[4]<p[1]-1.0,"Lead exit must clear leads but retain the flange");
    assert((led_back_axis(i)+led_capture_gap)*cos(led_tilt)+(p[1]+led_flange_extra)/2*sin(led_tilt) < deck_t+led_retainer_t-1.2,
           "Not enough keeper roof above tilted flange pocket");
    assert(led_flange_front_axis-p[3]>0,"Example lens would protrude below deck; recheck against fixed chamber");
}
assert(base_adapter_h>0 && locator_h>locator_pilot_h+1.4,"Invalid integrated adapter stack");
assert(axial_bearing_od/2+1.5<14,"Axial bearing too large for collar-clearance support envelope");
assert(!production_release || (base_as_built_verified && screw_nut_verified &&
       guide_bearing_verified && axial_support_verified && led_packages_verified &&
       detector_board_verified && cup_verified && print_coupons_verified),
       "PRODUCTION BLOCKED: hardware and fit verification gates remain open");

echo("LIO R3 CONSOLIDATED DEVELOPMENT CAD; see README and hardware register");
echo("Fixed source guide/screw XY",rod_pts,[[-screw_x,0],[screw_x,0]]);
echo("Radial sleeve clearance",(shroud_id-chamber_od)/2);
echo("Lower/tower clearance",motor_body_x-motor_tower_d/2-R);
echo("Lower/coupler-collar clearance",screw_x-coupler_collar_d/2-R);
echo("Proposed deck low / high / loading",min_deck_h,max_measure_h,loading_h);
echo("Current deck / tube bottom / overlap",h,h-shroud_length,overlap_at(h));
if(overlap_at(h)<min_overlap) echo("LOADING / SERVICE ONLY: below measurement-overlap target; illumination OFF");
echo("Enclosure-only travel, NOT qualified optical travel",max_measure_h-min_deck_h);
echo("LED tilt / nominal target distance",led_tilt,led_target_drop);
if(!production_release) echo("UNVERIFIED: screw, bearings, inserts, LEDs, board, cup, rod/thread Z endpoints. NO POWERED AXIS RELEASE.");

// ---------- elementary solids / shared hole transforms ----------
module rr(w,d,t,r=3){ linear_extrude(height=t) offset(r=r) square([w-2*r,d-2*r],center=true); }
module ring(od,id,t){ difference(){ cylinder(d=od,h=t); translate([0,0,-eps]) cylinder(d=id,h=t+2*eps); } }
module at(x,y,z){ translate([x,y,z]) children(); }
module hole(d,z0,z1){ at(0,0,z0) cylinder(d=d,h=z1-z0); }
module hexhole(af,t){ cylinder(d=af/cos(30),h=t,$fn=6); }
module slot(d,travel,t){ hull(){ at(-travel,0,0) cylinder(d=d,h=t); at(travel,0,0) cylinder(d=d,h=t); } }
module beam_xy(a,b,w,t){ hull(){ at(a[0],a[1],0) cylinder(d=w,h=t); at(b[0],b[1],0) cylinder(d=w,h=t); } }
// Native +Z -> radially outward. Local X tangential, local Y vertical.
module radial(a,r,z){ translate([r*cos(a),r*sin(a),z]) rotate([90,0,a+90]) children(); }
module front_prism(w,z0,z1,depth=100){ at(-w/2,-depth,z0) cube([w,depth,z1-z0]); }
module port_prism(){
    // Constant chord, not a radial wedge: continuous straight removal path.
    pts=[[-port_w/2,port_bottom],[port_w/2,port_bottom],
         [port_w/2,port_bottom+port_rect_h],
         [port_w/2-port_crown_h,port_top],
         [-port_w/2+port_crown_h,port_top],
         [-port_w/2,port_bottom+port_rect_h]];
    rotate([90,0,0]) linear_extrude(height=100) polygon(pts);
}
module front_band(r0,r1,w,z0,z1){
    intersection(){ at(0,0,z0) ring(2*r1,2*r0,z1-z0); front_prism(w,z0-eps,z1+eps); }
}
module head_outline(t){
    union(){ cylinder(d=head_body_d,h=t);
        for(a=head_angles) let(p=p2(head_bolt_r,a)) at(p[0],p[1],0) cylinder(d=head_ear_d,h=t);
    }
}
module head_bolts(z0,z1){ for(a=head_angles) let(p=p2(head_bolt_r,a)) at(p[0],p[1],z0) cylinder(d=head_bolt_d,h=z1-z0); }

// ---------- merged base locator and saddle ----------
module saddle_blank(){
    union(){
        cylinder(d=chamber_od,h=saddle_t);
        for(s=[-1,1],t=[-1,1]){
            beam_xy([s*34,t*34],[s*87,t*34],10,saddle_t);
            beam_xy([s*87,t*34],[s*frame_x,t*frame_y],12,saddle_t);
            hull(){ at(s*chamber_mount_x,t*chamber_mount_y,0) cylinder(d=14,h=saddle_t);
                    at(s*chamber_mount_x,t*43,0) cylinder(d=14,h=saddle_t); }
        }
    }
}
module base_adapter(){
    // One connected body, NO loose locator and NO inter-part alignment pins.
    difference(){
        union(){
            difference(){
                union(){
                    cylinder(d=locator_pilot_d,h=locator_pilot_h+eps);
                    at(0,0,locator_pilot_h) cylinder(d1=locator_pilot_d,d2=locator_top_d,h=1.4);
                    at(0,0,locator_pilot_h+1.4-eps)
                        cylinder(d=locator_top_d,h=locator_h-locator_pilot_h-1.4+2*eps);
                }
                hole(80,-eps,locator_h+2*eps);
            }
            at(0,0,locator_h) saddle_blank();
        }
        for(s=[-1,1],t=[-1,1]){
            at(s*frame_x,t*frame_y,locator_h-eps) cylinder(d=frame_bolt_clearance,h=saddle_t+2*eps);
            at(s*chamber_mount_x,t*chamber_mount_y,locator_h-eps) cylinder(d=chamber_mount_hole_d,h=saddle_t+2*eps);
        }
        // Underside is open at these fastener positions: nut/tool access is preserved.
        for(a=[0,120,240]) let(p=p2(22,a)) at(p[0],p[1],locator_h-eps)
            cylinder(d=3.4,h=saddle_t+2*eps);
    }
}
module adapter_for_print(){ at(0,0,base_adapter_h) rotate([180,0,0]) base_adapter(); }


module chamber_feet(){
    for(s=[-1,1],t=[-1,1])
        hull(){ at(s*chamber_mount_x,t*chamber_mount_y,0) cylinder(d=14,h=chamber_mount_t);
                at(s*chamber_mount_x,t*44,0) cylinder(d=14,h=chamber_mount_t); }
}
module panel_seat_cut(){
    front_band(seat_r,80,panel_w+2*panel_fit,panel_bottom-panel_fit,panel_top+panel_fit);
}
module panel_bosses(){
    // Stop faces follow the SAME cylindrical seat as the door inner surface.
    // A flat tangent boss face would penetrate the curved door at its edges.
    intersection(){
        cylinder(r=panel_ir,h=chamber_h);
        union() for(a=panel_angles,z=panel_screw_z)
            radial(a,frame_ir-1,z) cylinder(d=panel_insert_boss_d,h=panel_ir-(frame_ir-1));
    }
}
module panel_insert_holes(){
    for(a=panel_angles,z=panel_screw_z)
        radial(a,panel_ir-panel_insert_depth,z) cylinder(d=panel_insert_pilot,h=panel_insert_depth+eps);
}
module chamber(){
    difference(){
        union(){
            difference(){
                union(){
                    ring(chamber_od,chamber_id,chamber_h);
                    // ONLY local access frame; the rest remains 3.5 mm wall.
                    front_band(frame_ir,R,panel_w+8,panel_bottom-3,panel_top+3);
                    chamber_feet();
                }
                port_prism();
                panel_seat_cut();
            }
            // Boss end faces are deliberate hard seating stops, gasket sits lower.
            panel_bosses();
        }
        panel_insert_holes();
        for(s=[-1,1],t=[-1,1]) at(s*chamber_mount_x,t*chamber_mount_y,-eps)
            cylinder(d=chamber_mount_hole_d,h=chamber_mount_t+2*eps);
    }
}
module door_holes(){
    for(a=panel_angles,z=panel_screw_z){
        radial(a,panel_ir-2,z) cylinder(d=panel_screw_d,h=panel_t+4);
        radial(a,panel_or-panel_head_depth,z) cylinder(d=panel_head_d,h=panel_head_depth+3);
    }
}
module door(){
    difference(){
        front_band(panel_ir,panel_or,panel_w,panel_bottom,panel_top);
        door_holes();
        // Blind shallow finger recess; never cuts through the panel.
        at(-10,-panel_or-1,(panel_bottom+panel_top)/2-5) cube([20,2.4,10]);
    }
}
module sample_nest(){
    // Placeholder cup pocket is intentionally a small replaceable part.
    difference(){
        union(){
            cylinder(d=cup_od+10,h=sample_seat_h+4);
            for(a=[0,120,240]) let(p=p2(22,a)) at(p[0],p[1],0) cylinder(d=9,h=sample_seat_h);
        }
        hole(cup_od+cup_fit_d,sample_seat_h,sample_seat_h+8);
        for(a=[0,120,240]) let(p=p2(22,a)) at(p[0],p[1],sample_seat_h-2.2) cylinder(d=6.6,h=3);
        // Weight relief underside, 45-degree closing cone, not a huge bridged roof.
        at(0,0,-eps) cylinder(d1=max(8,cup_od-10),d2=8,h=sample_seat_h-4);
        for(a=[0,120,240]) let(p=p2(22,a)) at(p[0],p[1],-eps) cylinder(d=3.4,h=sample_seat_h+6);
    }
}

// ---------- carriage / screw nut interface ----------
module carriage(){
    difference(){
        rr(carriage_w,carriage_d,carriage_t,6);
        hole(carriage_opening_d,-eps,carriage_t+eps);
        head_bolts(-eps,carriage_t+eps);
        for(a=head_angles) let(p=p2(head_bolt_r,a)) at(p[0],p[1],-eps) hexhole(m4_nut_af,m4_nut_h+eps);
        for(p=rod_pts){
            at(p[0],p[1],-eps) cylinder(d=bearing_housing_od+2.4,h=carriage_t+2*eps);
            for(y=[-13,13]) at(p[0],p[1]+y,-eps) cylinder(d=3.4,h=carriage_t+2*eps);
        }
        for(s=[-1,1]){
            at(s*screw_x,0,-eps) slot(lead_nut_body_d+2,carrier_adjust,carriage_t+2*eps);
            for(y=[-16,16]) at(s*screw_x,y,-eps) cylinder(d=4.5,h=carriage_t+2*eps);
            // Clearance for lead-nut flange screw tips (M3 x12 example), including carrier X adjustment.
            for(i=[0:3]) let(a=lead_nut_bolt_phase+90*i,p=p2(lead_nut_bcd/2,a))
                at(s*screw_x+p[0],p[1],-eps) slot(5.0,carrier_adjust,3+eps);
        }
        // Rear ties stay outside optical flange and guide seats.
        for(x=[-10,10]) at(x,72,-eps) rr(4,8,carriage_t+2*eps,1);
    }
}
module nut_carrier(){
    difference(){
        rr(carrier_w,carrier_d,carrier_t,3);
        hole(lead_nut_body_d+0.5,-eps,carrier_t+eps);
        for(i=[0:3]) let(a=lead_nut_bolt_phase+90*i,p=p2(lead_nut_bcd/2,a)){
            at(p[0],p[1],-eps) cylinder(d=lead_nut_bolt_d,h=carrier_t+2*eps);
            at(p[0],p[1],carrier_t-2.6) hexhole(5.8,2.6+eps);
        }
        for(y=[-16,16]){
            at(0,y,-eps) slot(4.5,carrier_adjust,carrier_t+2*eps);
            at(0,y,-eps) hull(){ at(-carrier_adjust,0,0) hexhole(m4_nut_af,m4_nut_h+eps);
                                at(carrier_adjust,0,0) hexhole(m4_nut_af,m4_nut_h+eps); }
        }
    }
}
module guide_housing(kind=0){
    difference(){
        union(){
            at(0,0,-bearing_length) cylinder(d=bearing_housing_od,h=bearing_length+eps);
            rr(24,34,guide_flange_t,3);
        }
        hole(rod_d+0.8,-bearing_length-eps,guide_flange_t+eps);
        hole(bearing_od+bearing_seat_extra,guide_flange_t-bearing_length,guide_flange_t+eps);
        for(y=[-13,13]) at(0,y,-eps){
            if(kind==0) cylinder(d=3.4,h=guide_flange_t+2*eps);
            else if(kind==1) slot(float_sleeve_od+0.3,guide_float_x,guide_flange_t+2*eps);
            else cylinder(d=float_sleeve_od+2*guide_float_xy+0.3,h=guide_flange_t+2*eps);
        }
        for(x=[-9.5,9.5]){
            at(x,0,-eps) cylinder(d=2.4,h=guide_flange_t+2*eps);
            at(x,0,-eps) hexhole(4.5,1.9+eps);
        }
    }
}
module guide_cap(){
    difference(){
        rr(24,18,guide_cap_t,3);
        hole(rod_d+0.8,-eps,guide_cap_t+eps);
        for(x=[-9.5,9.5]) at(x,0,-eps) cylinder(d=2.4,h=guide_cap_t+2*eps);
    }
}
module guide_tie(){
    difference(){
        rr(200,160,6,6);
        hole(148,-eps,6+eps);
        for(p=rod_pts) at(p[0],p[1],-eps) cylinder(d=8.6,h=6+2*eps);
        for(s=[-1,1]) at(s*screw_x,0,-eps) cylinder(d=screw_d+4,h=6+2*eps);
    }
}

// ---------- replaceable axial support - selected bearing MUST be verified ----------
module axial_outline(t){
    union(){
        cylinder(d=28,h=t);
        for(s=[-1,1]){
            beam_xy([0,0],[frame_x-screw_x,s*frame_y],14,t);
            at(frame_x-screw_x,s*frame_y,0) cylinder(d=14,h=t);
            at(0,s*18,0) cylinder(d=9,h=t);
        }
    }
}
module axial_bridge(){
    difference(){
        axial_outline(axial_bridge_t);
        hole(axial_inner_clearance,-eps,axial_bridge_t+eps);
        hole(axial_bearing_od+axial_seat_extra,axial_bridge_t-axial_bearing_h,axial_bridge_t+eps);
        for(s=[-1,1]){
            at(frame_x-screw_x,s*frame_y,-eps) cylinder(d=frame_bolt_clearance,h=axial_bridge_t+2*eps);
            at(0,s*18,-eps) cylinder(d=3.4,h=axial_bridge_t+2*eps);
            at(0,s*18,-eps) hexhole(5.8,2.6+eps);
        }
    }
}
module axial_cap(){
    difference(){
        hull(){ cylinder(d=28,h=axial_cap_t); for(y=[-18,18]) at(0,y,0) cylinder(d=9,h=axial_cap_t); }
        hole(axial_inner_clearance,-eps,axial_cap_t+eps);
        for(y=[-18,18]) at(0,y,-eps) cylinder(d=3.4,h=axial_cap_t+2*eps);
    }
}
module axial_spacer(){ ring(14,frame_bolt_clearance,axial_spacer_h); }

// ---------- detachable shroud and flat deck ----------
module shroud(){
    difference(){
        union(){
            at(0,0,-shroud_length) cylinder(d=shroud_od,h=shroud_length);
            at(0,0,-shroud_flange_t) head_outline(shroud_flange_t);
            at(0,0,-shroud_flange_t-head_pilot_h) cylinder(d=head_pilot_d,h=head_pilot_h+eps);
        }
        hole(shroud_id,-shroud_length-eps,eps);
        at(0,0,-shroud_length-eps) cylinder(d1=shroud_leadin_id,d2=shroud_id,h=shroud_leadin_h+eps);
        head_bolts(-shroud_flange_t-eps,eps);
    }
}
module led_pos(i){ rotate([0,0,i*360/led_count]) translate([led_ring_r,0,0]) children(); }
module led_axis(){ rotate([0,led_tilt,0]) children(); }
module led_seat_cut(i){
    p=led_profile(i);
    led_pos(i) led_axis(){
        hole(p[0]+led_hole_extra,-3,deck_t+12);
        // Tilted flange shoulder: package inserted lens-first from electronics side.
        hole(p[1]+led_flange_extra,led_flange_front_axis,deck_t+12);
    }
}
module optical_deck(){
    difference(){
        head_outline(deck_t);
        head_bolts(-eps,deck_t+eps);
        for(a=head_angles) let(p=p2(head_bolt_r,a)) at(p[0],p[1],deck_t-2) cylinder(d=8.5,h=2+eps);
        hole(24,-eps,deck_t+eps);
        for(x=[-18,18],y=[-14,14]){
            at(x,y,-eps) cylinder(d=3.4,h=deck_t+eps*2);
            at(x,y,-eps) hexhole(5.8,2.6+eps);
        }
        for(i=[0:led_count-1]) led_seat_cut(i);
        for(a=opt_keeper_angles) let(p=p2(46,a)){
            at(p[0],p[1],-eps) cylinder(d=3.4,h=deck_t+2*eps);
            at(p[0],p[1],-eps) hexhole(5.8,2.6+eps);
        }
        for(a=cover_angles) let(p=p2(55.5,a)){
            at(p[0],p[1],-eps) cylinder(d=3.4,h=deck_t+2*eps);
            at(p[0],p[1],-eps) hexhole(5.8,2.6+eps);
        }
        // Shallow datum notch at +X; no protruding feature or through light path.
        at(57,-1,deck_t-0.4) cube([3,2,0.5]);
    }
}
module led_retainer(){
    // Native coordinates: installed lower plane z=0; placed at deck_t in assembly.
    // Retains actual LED flanges: lead holes do NOT pass the 6.2 mm flange.
    difference(){
        ring(100,58,led_retainer_t);
        for(i=[0:led_count-1]) let(p=led_profile(i)) at(0,0,-deck_t) led_pos(i) led_axis(){
            hole(p[4],-2,deck_t+led_retainer_t+12);
            hole(p[1]+led_flange_extra,-2,led_back_axis(i)+led_capture_gap);
        }
        for(a=opt_keeper_angles) let(p=p2(46,a)) at(p[0],p[1],-eps)
            cylinder(d=3.4,h=led_retainer_t+2*eps);
        at(47,-1,led_retainer_t-0.4) cube([3,2,0.5]);
    }
}
module retainer_for_print(){ at(0,0,led_retainer_t) rotate([180,0,0]) led_retainer(); }
module optical_module(){
    color([0.40,0.46,0.51]) optical_deck();
    color([0.70,0.73,0.76]) at(0,0,deck_t) led_retainer();
    color([0.28,0.36,0.43]) installed_detector();
    if(show_hardware) for(i=[0:15]) color([0.9,0.67,0.24]) led_package_ref(i);
}
module led_package_ref(i){
    p=led_profile(i);
    led_pos(i) led_axis(){
        hole(p[0],led_flange_front_axis-p[3],led_flange_front_axis);
        hole(p[1],led_flange_front_axis,led_back_axis(i));
    }
}


module detector_mount(){
    // PRINT orientation: flat PCB face against bed, optical tube upward.
    difference(){
        union(){ rr(44,36,3,3); at(0,0,3-eps) cylinder(d=detector_tube_od,h=detector_tube_length+eps); }
        hole(detector_aperture_d,-eps,detector_tube_length+3+eps);
        for(x=[-18,18],y=[-14,14]) at(x,y,-eps) cylinder(d=3.4,h=3+2*eps);
        for(x=[-opt101_hole_dx/2,opt101_hole_dx/2],y=[-opt101_hole_dy/2,opt101_hole_dy/2]){
            at(x,y,-eps) cylinder(d=opt101_mount_d,h=3+2*eps);
            // Flush underside M2 screw into purchased standoff; board not trapped.
            at(x,y,1.5) cylinder(d=4.4,h=1.5+eps);
        }
    }
}
module head_cover(){
    // Native PRINT orientation: solid roof on bed, open electronics face upward.
    difference(){
        union(){ difference(){ cylinder(d=118,h=head_cover_h); hole(112,2,head_cover_h+eps); }
            for(a=cover_angles) let(p=p2(55.5,a)) at(p[0],p[1],0) cylinder(d=7.5,h=head_cover_h);
        }
        for(a=cover_angles) let(p=p2(55.5,a)) at(p[0],p[1],-eps) cylinder(d=3.4,h=head_cover_h+2*eps);
        // Rear cable outlet. MUST be filled with an opaque flexible gland/foam seal.
        at(-4,53,head_cover_h-4) cube([8,10,5]);
    }
}

// ---------- coupons ----------
module datum_template(){
    difference(){
        union(){ difference(){ rr(190,136,1.6,4); rr(178,124,2,3); }
            beam_xy([-guide_x,-guide_y-3],[-guide_x,guide_y+3],14,1.6);
            beam_xy([guide_x,-guide_y-3],[guide_x,guide_y+3],14,1.6);
            beam_xy([-screw_x,0],[screw_x,0],12,1.6);
        }
        for(p=rod_pts) at(p[0],p[1],-eps) cylinder(d=8.6,h=2);
        for(s=[-1,1]) at(s*screw_x,0,-eps) cylinder(d=screw_d+1,h=2);
        hole(6,-eps,2);
    }
}
module cylinder_coupon(){
    at(-51,-51,0) ring(chamber_od,chamber_id,10);
    at(47,47,0) ring(shroud_od,shroud_id,10);
}
module closure_coupon(){
    // Same exact production curved corner, insert, screw transform, and rebate.
    x0=22; y0=-60; z0=panel_bottom-2;
    translate([-x0,-y0,-z0]) intersection(){ chamber(); translate([x0,y0,z0]) cube([24,34,23]); }
    translate([34-x0,-y0,-panel_bottom]) intersection(){ door(); translate([x0,y0,panel_bottom]) cube([24,34,21]); }
}
module led_coupon(){
    // Actual +X channel and adjacent keeper attachment; two small independent pieces.
    at(-27,7,0) intersection(){ optical_deck(); at(27,-7,0) cube([26,24,deck_t]); }
    at(31-27,17,led_retainer_t) rotate([180,0,0])
        intersection(){ led_retainer(); at(27,-7,-eps) cube([26,24,led_retainer_t+2*eps]); }
}
module hardware_coupon(){
    guide_for_print(0);
    at(38,0,0) nut_carrier();
    at(0,40,0) guide_cap();
    at(42,38,0) difference(){ rr(50,14,8,2);
        for(i=[0:4]) at(-20+i*10,0,2) cylinder(d=3.9+0.1*i,h=6+eps);
    }
}



// ---------- nonprinted references, not pretend manufactured parts ----------
module screw_ref(d,l){ cylinder(d=d,h=l,$fn=24); }
module metal_nut_ref(){
    difference(){
        union(){ cylinder(d=lead_nut_flange_d,h=lead_nut_flange_t);
                 at(0,0,lead_nut_flange_t) cylinder(d=lead_nut_body_d,h=lead_nut_total_h-lead_nut_flange_t); }
        hole(screw_d,-eps,lead_nut_total_h+eps);
    }
}
module ring_hardware(od,id,l){ ring(od,id,l); }
module hardware_refs(){
    color([0.64,0.67,0.7]){
        for(p=rod_pts) at(p[0],p[1],10) screw_ref(rod_d,guide_top_z-10);
        for(s=[-1,1]) at(s*screw_x,0,45) screw_ref(screw_d,thread_end_z-45);
    }
    color([0.86,0.58,0.19]){
        for(s=[-1,1]) at(s*screw_x,0,h+nut_bottom_offset) metal_nut_ref();
        for(p=rod_pts) at(p[0],p[1],carriage_top_z+guide_flange_t-bearing_length) ring_hardware(bearing_od,rod_d,bearing_length);
    }
    color([0.58,0.61,0.63]) for(s=[-1,1]){
        at(s*screw_x,0,axial_bearing_bottom) ring_hardware(axial_bearing_od,axial_bearing_id,axial_bearing_h);
        for(zz=[axial_bearing_bottom-shaft_collar_h,axial_bearing_bottom+axial_bearing_h])
            at(s*screw_x,0,zz) ring_hardware(shaft_collar_od,screw_d,shaft_collar_h);
    }
    // Purchased guide stop collars: overload/catch capacity MUST be qualified.
    color([0.8,0.62,0.28]) for(p=rod_pts){
        at(p[0],p[1],min_deck_h-shroud_flange_t-bearing_length-6) ring_hardware(16,rod_d,6);
        if(show_upper_tie) for(zz=[tie_bottom_z-6,tie_bottom_z+6]) at(p[0],p[1],zz) ring_hardware(16,rod_d,6);
    }
    // Representative unselected sample container; exclude from all part exports.
    color([0.8,0.87,0.92,0.45]) at(0,0,chamber_z+sample_seat_h) ring_hardware(cup_od,cup_od-2,cup_h);
    color([0.12,0.43,0.25]) at(0,0,h+deck_t+5) rr(opt101_pcb_w,opt101_pcb_d,1.6,0.5);
    color([0.9,0.8,0.35]) for(i=[0:led_count-1]) at(0,0,h) led_package_ref(i);
    // Illustrative panel screw shanks/heads; insert shown, NOT printed.
    if(!door_open) for(a=panel_angles,z=panel_screw_z){
        color([0.75,0.77,0.8]) at(0,0,chamber_z) radial(a,panel_or-panel_head_depth-panel_screw_length,z){
            cylinder(d=3,h=panel_screw_length); at(0,0,panel_screw_length) cylinder(d=5.7,h=1.8);
        }
        color([0.85,0.59,0.22]) at(0,0,chamber_z) radial(a,panel_ir-panel_insert_depth,z)
            ring(4.2,3,panel_insert_depth);
    }
}
module installed_detector(){ at(0,0,deck_t+3) rotate([180,0,0]) detector_mount(); }
module fixed_new(){
    at(0,0,locator_bottom_z) base_adapter();
    at(0,0,chamber_z) chamber();
    at(0,0,chamber_z) sample_nest();
    for(s=[-1,1]){
        translate([s*screw_x,0,axial_bridge_bottom_z]) scale([s,1,1]) axial_bridge();
        at(s*screw_x,0,axial_bridge_bottom_z+axial_bridge_t) axial_cap();
        for(t=[-1,1]) at(s*frame_x,t*frame_y,chamber_z) axial_spacer();
    }
    if(show_upper_tie) at(0,0,tie_bottom_z) guide_tie();
}
module moving_solids(zz=h){
    at(0,0,zz-shroud_flange_t-carriage_t) carriage();
    at(0,0,zz) shroud();
    at(0,0,zz) optical_deck();
    at(0,0,zz+deck_t) led_retainer();
    at(0,0,zz) installed_detector();
    for(i=[0:3]) let(p=rod_pts[i]){
        at(p[0],p[1],zz-shroud_flange_t) guide_housing(i==0?0:i==1?1:2);
        at(p[0],p[1],zz-shroud_flange_t+guide_flange_t) guide_cap();
    }
    for(s=[-1,1]) at(s*screw_x,0,zz-shroud_flange_t-carriage_t-carrier_t) nut_carrier();
    if(show_electronics_cover) at(0,0,zz+deck_t+head_cover_h) rotate([180,0,0]) head_cover();
}
module assembly(exploded=false){
    e=exploded?30:0;
    color([0.22,0.24,0.26]) retained_v2_base();
    color([0.21,0.40,0.48]) at(0,0,locator_bottom_z) base_adapter();
    color([0.20,0.22,0.23]) at(0,0,chamber_z+e) chamber();
    color([0.92,0.44,0.13]) at(0,door_open||exploded?-52:0,chamber_z+e) door();
    color([0.48,0.51,0.53]) at(0,0,chamber_z) sample_nest();
    for(s=[-1,1]){
        color([0.31,0.39,0.47]) translate([s*screw_x,0,axial_bridge_bottom_z]) scale([s,1,1]) axial_bridge();
        color([0.41,0.47,0.52]) at(s*screw_x,0,axial_bridge_bottom_z+axial_bridge_t+e/3) axial_cap();
        color([0.25,0.32,0.40]) for(t=[-1,1]) at(s*frame_x,t*frame_y,chamber_z) axial_spacer();
    }
    color([0.21,0.40,0.48]) at(0,0,carriage_bottom_z+e*2) carriage();
    color([0.18,0.23,0.28,$preview?preview_shroud_alpha:1]) at(0,0,h+e*3) shroud();
    color([0.31,0.36,0.39]) at(0,0,h+e*4) optical_deck();
    color([0.70,0.74,0.78]) at(0,0,h+deck_t+e*5) led_retainer();
    color([0.43,0.5,0.58]) at(0,0,h+e*5) installed_detector();
    for(i=[0:3]) let(p=rod_pts[i]){
        color([0.40,0.49,0.56]) at(p[0],p[1],carriage_top_z+e*2) guide_housing(i==0?0:i==1?1:2);
        color([0.55,0.60,0.63]) at(p[0],p[1],carriage_top_z+guide_flange_t+e*2.5) guide_cap();
    }
    color([0.38,0.44,0.5]) for(s=[-1,1]) at(s*screw_x,0,carriage_bottom_z-carrier_t+e*1.5) nut_carrier();
    if(show_upper_tie) color([0.40,0.49,0.55]) at(0,0,tie_bottom_z+e*6) guide_tie();
    if(show_electronics_cover) color([0.31,0.38,0.43,$preview?0.45:1])
        at(0,0,h+deck_t+head_cover_h+e*7) rotate([180,0,0]) head_cover();
    if(show_hardware && !exploded) hardware_refs();
    if(show_optical_rays && !exploded) color([1,0.6,0.05,0.5]) for(i=[0:led_count-1])
        rotate([0,0,i*360/led_count]) hull(){ at(led_ring_r,0,h) sphere(d=0.5,$fn=8);
        at(led_ring_r-(h-sample_z)*tan(led_tilt),0,sample_z) sphere(d=0.5,$fn=8); }
}

// ---------- print transforms: all outputs placed on Z=0 ----------
module guide_for_print(kind=0){ at(0,0,guide_flange_t) rotate([180,0,0]) guide_housing(kind); }
module door_for_print(){ at(0,R-8,-panel_bottom) door(); }
module shroud_for_print(){ rotate([180,0,0]) shroud(); }
module print_single(name){
    if(name=="base_adapter") adapter_for_print();
    else if(name=="chamber") chamber();
    else if(name=="door") door_for_print();
    else if(name=="sample_nest") sample_nest();
    else if(name=="carriage") carriage();
    else if(name=="shroud") shroud_for_print();
    else if(name=="optical_deck") optical_deck();
    else if(name=="led_retainer") retainer_for_print();
    else if(name=="detector_mount") detector_mount();
    else if(name=="head_cover") head_cover();
    else if(name=="guide_primary") guide_for_print(0);
    else if(name=="guide_secondary") guide_for_print(1);
    else if(name=="guide_float") guide_for_print(2);
    else if(name=="guide_cap") guide_cap();
    else if(name=="nut_carrier") nut_carrier();
    else if(name=="axial_bridge") axial_bridge();
    else if(name=="axial_cap") axial_cap();
    else if(name=="axial_spacer") axial_spacer();
    else if(name=="guide_tie") guide_tie();
    else if(name=="datum_template") datum_template();
    else if(name=="cylinder_coupon") cylinder_coupon();
    else if(name=="closure_coupon") closure_coupon();
    else if(name=="hardware_coupon") hardware_coupon();
    else if(name=="led_coupon") led_coupon();
    else assert(false,str("Unknown part: ",name));
}
module print_job(n){
    if(n==1){
        at(0,-35,0) adapter_for_print();
        at(0,72,0) sample_nest();
    }
    else if(n==2){
        // 18 pieces. Separate rows; no nesting inside cavities.
        at(-55,-76,0) rotate([0,0,90]) axial_bridge();
        at(55,-76,0) rotate([0,0,90]) axial_bridge();
        for(i=[0:3]) at(-89+i*34,0,0) guide_for_print(i==0?0:i==1?1:2);
        for(i=[0:1]) at(49+i*37,0,0) nut_carrier();
        for(i=[0:3]) at(-89+i*34,37,0) guide_cap();
        for(i=[0:1]) at(46+i*40,57,0) axial_cap();
        for(i=[0:3]) at(-89+i*28,74,0) axial_spacer();
    }
    else if(n==3){ at(0,25,0) chamber(); at(0,-75,0) door_for_print(); }
    else if(n==4) carriage();
    else if(n==5) shroud_for_print();
    else if(n==6){
        at(-39,-39,0) optical_deck();
        at(53,53,0) retainer_for_print();
        at(-67,66,0) detector_mount();
    }
    else if(n==7) head_cover();
    else if(n==8) guide_tie();
    else assert(false,"R3 job must be 1..8; R2 numeric meanings DO NOT apply");
}



// ---------- V2 source is embedded below verbatim inside a local scope ----------

module retained_v2_base(){
// LIO V2.1 - Motor Base v16
// Actual 28BYJ-48 cylindrical motor towers - 90deg rotated motor orientation
// Units: mm
//
// DESIGN INTENT
// - Motor is pushed UP into each cylindrical tower from underneath.
// - Entire motor body, mounting ears/tabs and wire/connector region have clearance.
// - Motor mounting ears stop against the internal top mounting plane.
// - Two M3 mounting screw holes are in the tower roof, rotated 90 degrees.
// - Base deck is opened beneath each tower so the whole motor/tabs/wires can enter from below.
// - Shaft opening is coupler-sized; there is no constricted shaft-only hole.
// - Output shaft is OFFSET by 8 mm from the motor body center.
// - Shaft hole has a large open clamp/coupler clearance pocket above it.
// - Central Ø92 locating recess is retained.
// - Four 8 mm guide rods remain at X +/-78, Y +/-55.
//
// IMPORTANT 28BYJ-48 GEOMETRY USED
// body OD ~= 28
// mounting-hole spacing ~= 35
// mounting holes ~= 4.2
// shaft offset ~= 8 mm from body center
// mounting ears are on the shaft/front face

$fn = 128;
eps = 0.05;

// ---------- preview switches ----------
show_motor_reference = false;
show_coupler_reference = false;
show_rod_reference = false;
show_insert_reference = false;

// ---------- base ----------
base_w = 210;
base_d = 150;
deck_t = 10;
corner_r = 8;

// Central locating recess requested by user
center_recess_d = 92;
center_recess_depth = 0.8;

// ---------- guide rods ----------
rod_x = 78;
rod_y = 55;
rod_bore_d = 8.6;
rod_socket_od = 18;
rod_root_od = 21;
rod_socket_above = 16;
rod_total_engagement = 18;

// ---------- actual 28BYJ-48 geometry ----------
motor_body_d = 28;
motor_body_clearance_d = 30.5;  // loose FDM pass-through
motor_h = 19.5;
motor_ear_spacing = 35;
motor_mount_hole_d = 4.5;      // screw clearance through tower roof
motor_shaft_d = 5;
motor_shaft_offset = 8;        // shaft is offset from body center; v13 rotates motor 90deg so offset is along X

// ---------- motor tower geometry ----------
// Lead screw/shaft axes moved outward enough that tower OD clears Ø92 recess.
shaft_x = 74;
shaft_y = 0;

// V13: motors are rotated 90 degrees relative to v12.
// Shaft axes stay at X +/-74, Y 0.
// Motor bodies are offset OUTWARD by 8 mm in X.
left_body_x  = -shaft_x - motor_shaft_offset;
right_body_x =  shaft_x + motor_shaft_offset;
motor_body_y = 0;

// Cylindrical tower is centered on MOTOR BODY, not shaft.
motor_tower_od = 48;
motor_tower_id = 43.5;         // clears body + metal ears/tabs envelope locally
motor_tower_h = 31;
motor_roof_t = 6;

// Bottom loading mouth: extra generous opening for tabs and wires.
// This is cut from underside up to the internal mounting plane.
bottom_entry_d = 45;

// Ear relief pockets inside tower so the 35 mm tabs can pass upward.
ear_relief_w = 43;
ear_relief_d = 12;

// Shaft/coupler clamp clearance.
// User requested NO shaft-sized restriction: the roof opening itself is coupler-sized.
shaft_hole_d = 28;             // full coupler/clamp access through roof
clamp_clearance_d = 28;
clamp_clearance_h = 12;
clamp_wall_od = 36;

// M3 heat insert pockets in roof around mounting screw positions.
// Inserts are optional; the screw holes remain usable as through holes.
insert_bore_d = 4.15;
insert_depth = 5.2;
insert_boss_od = 10.5;

// ---------- frame mounting ----------
frame_x = 98;
frame_y = 42;
frame_boss_od = 10.5;
frame_insert_d = 4.15;
frame_insert_depth = 5.5;

// ---------- detachable feet ----------
// Feet are NOT fused to the base. They are laid out beside the base as
// separate printable pieces so the base itself has one uninterrupted flat
// underside. Glue them on after printing if desired.
foot_d = 16;
foot_h = 4;
// All four feet are placed in ONE ROW directly in front of the base.
// Front is negative Y. Keeping them within the base width prevents the
// combined multi-body STL from exceeding the Ender-3 V3 SE bed width.
foot_layout_gap = 6;
foot_row_spacing = 6;
foot_row_y = -(base_d/2 + foot_d/2 + foot_layout_gap);
foot_row_x = [-33, -11, 11, 33];
show_detachable_feet = true;

// ---------- diagnostics ----------
function dist2d(x1,y1,x2,y2) = sqrt((x1-x2)*(x1-x2)+(y1-y2)*(y1-y2));

// Tower center to optical center after 90deg rotation / outward offset.
tower_center_dist = shaft_x + motor_shaft_offset;
recess_r = center_recess_d/2;
tower_r = motor_tower_od/2;

echo("LIO V2.1 MOTOR BASE v16");
echo("shaft axes X", [-shaft_x, shaft_x]);
echo("shaft axis Y", shaft_y);
echo("left/right motor body X", [left_body_x,right_body_x]);
echo("motor body Y", motor_body_y);
echo("tower center distance from optical center", tower_center_dist);
echo("recess-to-tower radial clearance", tower_center_dist - recess_r - tower_r);
echo("motor tower ID", motor_tower_id);
echo("bottom entry diameter", bottom_entry_d);

assert(tower_center_dist > recess_r + tower_r,
       "Motor tower overlaps central Ø92 recess. Increase shaft_x or reduce tower OD.");

// ============================================================
// HELPERS
// ============================================================

module rounded_plate(w,d,h,r) {
    linear_extrude(height=h)
        offset(r=r)
            square([w-2*r,d-2*r], center=true);
}

module cyl_at(x,y,z,d,h) {
    translate([x,y,z]) cylinder(d=d,h=h);
}

// ============================================================
// GUIDE ROD SOCKET
// ============================================================

module rod_socket(x,y) {
    difference() {
        union() {
            cyl_at(x,y,deck_t-eps,rod_root_od,3.0);
            cyl_at(x,y,deck_t+2.0,rod_socket_od,rod_socket_above-2.0);
        }
        // Bore reaches into deck for total engagement.
        cyl_at(x,y,deck_t + rod_socket_above - rod_total_engagement,
               rod_bore_d, rod_total_engagement + 2);
    }
}

// ============================================================
// MOTOR TOWER
// ============================================================

module motor_tower(sign=1) {
    // Lead screw / motor output shaft datum.
    sx = sign * shaft_x;
    sy = shaft_y;

    // V13: motor is rotated 90 degrees from v12.
    // The round gearbox body is offset OUTWARD from the shaft by 8 mm.
    bx = sx + sign * motor_shaft_offset;
    by = 0;

    // The 35 mm mounting-ear line is now along Y (90deg rotation).
    earx  = bx;
    ear1y = by - motor_ear_spacing/2;
    ear2y = by + motor_ear_spacing/2;

    difference() {
        union() {
            // Cylindrical protective tower centered on the actual motor BODY.
            cyl_at(bx,by,deck_t-eps,motor_tower_od,motor_tower_h+eps);

            // Reinforced roof material around the two motor mounting screws.
            cyl_at(earx,ear1y,deck_t+motor_tower_h-motor_roof_t,
                   insert_boss_od,motor_roof_t);
            cyl_at(earx,ear2y,deck_t+motor_tower_h-motor_roof_t,
                   insert_boss_od,motor_roof_t);

            // Coupler/clamp collar centered on the OFFSET shaft axis.
            cyl_at(sx,sy,deck_t+motor_tower_h-eps,
                   clamp_wall_od,clamp_clearance_h+eps);
        }

        // A) TRUE BASE-PLATE MOTOR ENTRY HOLE.
        // This removes the base deck below the cylindrical tower so the
        // motor is pushed upward from below rather than hitting the deck.
        cyl_at(bx,by,-1,bottom_entry_d,
               deck_t + motor_tower_h - motor_roof_t + 2);

        // B) 90-degree rotated ear/tab entry relief.
        // Ear line is along Y, so the relief is narrow in X and long in Y.
        translate([bx,by,(deck_t + motor_tower_h - motor_roof_t)/2 - 0.5])
            cube([ear_relief_d, ear_relief_w,
                  deck_t + motor_tower_h - motor_roof_t + 2], center=true);

        // C) Wire/connector loading relief.
        // With the motor rotated 90deg, give the connector/wires a side
        // passage toward the OUTSIDE of the base (+/-X).
        translate([bx + sign*20, by,
                   (deck_t + motor_tower_h - motor_roof_t)/2 - 0.5])
            cube([28,18,
                  deck_t + motor_tower_h - motor_roof_t + 2], center=true);

        // D) Two motor mounting screw holes through the roof.
        cyl_at(earx,ear1y,deck_t+motor_tower_h-motor_roof_t-1,
               motor_mount_hole_d,motor_roof_t+3);
        cyl_at(earx,ear2y,deck_t+motor_tower_h-motor_roof_t-1,
               motor_mount_hole_d,motor_roof_t+3);

        // E) Heat-insert pockets from the top of the roof.
        cyl_at(earx,ear1y,
               deck_t+motor_tower_h-insert_depth,
               insert_bore_d,insert_depth+1);
        cyl_at(earx,ear2y,
               deck_t+motor_tower_h-insert_depth,
               insert_bore_d,insert_depth+1);

        // F) FULL COUPLER-SIZED SHAFT OPENING THROUGH THE ROOF.
        // Deliberately no 5-8 mm shaft bottleneck. The entire Ø28 opening
        // is available for the clamp/coupler and its grub-screw access.
        cyl_at(sx,sy,deck_t+motor_tower_h-motor_roof_t-1,
               shaft_hole_d,motor_roof_t+3);

        // G) Continue the same clamp/coupler opening through the collar.
        cyl_at(sx,sy,deck_t+motor_tower_h-eps,
               clamp_clearance_d,clamp_clearance_h+2);
    }

    if (show_motor_reference) {
        color([0.7,0.7,0.75,0.35]) {
            cyl_at(bx,by,
                   deck_t+motor_tower_h-motor_roof_t-motor_h,
                   motor_body_d,motor_h);

            // Rotated ear plate reference: long direction is Y.
            translate([bx,by,
                       deck_t+motor_tower_h-motor_roof_t-0.8])
                cube([8,43,1.6],center=true);
        }
        color([0.95,0.65,0.2,0.7])
            cyl_at(sx,sy,
                   deck_t+motor_tower_h-motor_roof_t,
                   motor_shaft_d,12);
    }

    if (show_coupler_reference) {
        color([0.65,0.65,0.7,0.35])
            cyl_at(sx,sy,deck_t+motor_tower_h+1,20,25);
    }

    if (show_insert_reference) {
        color([0.9,0.55,0.05,0.55]) {
            cyl_at(earx,ear1y,deck_t+motor_tower_h-insert_depth,
                   insert_bore_d,insert_depth);
            cyl_at(earx,ear2y,deck_t+motor_tower_h-insert_depth,
                   insert_bore_d,insert_depth);
        }
    }
}

// ============================================================
// FRAME MOUNT BOSSES
// ============================================================

module frame_mount(x,y) {
    difference() {
        cyl_at(x,y,deck_t-eps,frame_boss_od,7);
        cyl_at(x,y,deck_t+7-frame_insert_depth,
               frame_insert_d,frame_insert_depth+1);
    }
}


// ============================================================
// DETACHABLE FEET - PRINTED BESIDE BASE
// ============================================================

module detachable_foot() {
    // Deliberately simple glue-on puck. Flat on both faces, support-free.
    cylinder(d=foot_d, h=foot_h);
}

module detachable_feet_layout() {
    if (show_detachable_feet) {
        // Four feet in a single row at the FRONT (negative Y) of the base.
        // All centers remain well inside the 210 mm base width, so the feet
        // add only ~22 mm to depth rather than expanding both X and Y bounds.
        // They remain separate solids for gluing on after printing.
        for (x=foot_row_x)
            translate([x,foot_row_y,0]) detachable_foot();
    }
}

// ============================================================
// COMPLETE BASE
// ============================================================

module lio_motor_base_v16() {
    difference() {
        union() {
            // Main base only. No geometry protrudes below Z=0, so the entire
            // underside can sit directly on the printer bed.
            rounded_plate(base_w,base_d,deck_t,corner_r);
        }

        // Central shallow locating recess remains.
        cyl_at(0,0,deck_t-center_recess_depth,
               center_recess_d,center_recess_depth+1);

        // CRITICAL v14 FIX: actual motor-loading openings through the BASE DECK.
        // In v13 these cuts existed only inside motor_tower(), so OpenSCAD
        // subtracted them from the tower geometry but NOT from the separate
        // base plate. These global cuts remove the deck itself.
        //
        // Each opening is centered on the MOTOR BODY, not the offset shaft.
        // The circular opening plus the front/back ear slot allows the complete
        // 28BYJ body + mounting tabs to be pushed upward from below.
        for (sign=[-1,1]) {
            sx = sign * shaft_x;
            bx = sx + sign * motor_shaft_offset;
            by = motor_body_y;

            // Main motor-body opening through entire deck.
            cyl_at(bx,by,-1,bottom_entry_d,deck_t+2);

            // 90-degree-rotated mounting-ear clearance through deck.
            // Ear line runs along Y.
            translate([bx,by,deck_t/2])
                cube([ear_relief_d,ear_relief_w,deck_t+2],center=true);

            // Outward wire/connector loading notch through deck.
            translate([bx + sign*20,by,deck_t/2])
                cube([28,18,deck_t+2],center=true);
        }
    }

    // Four guide rod sockets.
    for (x=[-rod_x,rod_x])
        for (y=[-rod_y,rod_y])
            rod_socket(x,y);

    // Two complete motor towers.
    motor_tower(-1);
    motor_tower(1);

    // Four explicit chassis/frame mounts.
    for (x=[-frame_x,frame_x])
        for (y=[-frame_y,frame_y])
            frame_mount(x,y);

    if (show_rod_reference) {
        color([0.65,0.65,0.68,0.3])
            for (x=[-rod_x,rod_x])
                for (y=[-rod_y,rod_y])
                    cyl_at(x,y,deck_t,8,100);
    }
}

lio_motor_base_v16();
// detachable_feet_layout(); // excluded: feet already exist / not a new print

}

// ---------- dispatch ----------
if(output_part=="assembly") assembly(false);
else if(output_part=="exploded") assembly(true);
else if(output_part=="optical_module") optical_module();
else if(output_part=="none") {}
else if(output_part=="sample_module"){
    color([0.25,0.32,0.36]) chamber();
    color([0.92,0.44,0.13]) at(0,door_open?-52:0,0) door();
}
else if(output_part=="section") difference(){ assembly(false); at(0,-250,-10) cube([250,500,600]); }
else if(output_part=="collision_check"){
    // Strict solid intersection only between moving printed parts and fixed parts.
    // Intentional optical deck / flange / carriage contact is within moving group.
    // Excludes hardware fits; these are evaluated separately in validation script.
    intersection(){ moving_solids(h); union(){ retained_v2_base(); fixed_new(); at(0,0,chamber_z) door(); } }
}
else if(output_part=="job") print_job(output_job);
else print_single(output_part);
