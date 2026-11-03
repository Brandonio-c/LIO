// LIO V2.9 - Integrated 16-LED Optical Head + OPT101 Detector + Through-Plate Moving Shroud - Wire Fix
// Units: mm
//
// PURPOSE
// One-piece moving optical chassis for LIO. It combines:
//   1) the 110 mm-ID non-contact light shroud for the V2.03 fixed chamber,
//   2) a centered OPT101 detector mount based on the old detector-cap SCAD,
//   3) SIXTEEN LED channels at 22.5 degree spacing based on the old LED-ring SCAD,
//   4) aimed LED tunnels, detector baffling, top-side wiring access, and a flat through-plate mounting flange.
//
// V2.7 TOP-PLATE INTERFACE
//   - 115 mm OD shroud passes through a nominal 118 mm top-plate clearance hole.
//   - 140 mm OD x 6 mm thick flange rests FLAT on top of the moving plate.
//   - 117 mm OD x 3 mm deep locating pilot enters the plate hole for repeatable centering.
//   - 4 x M4 clearance holes on a 126 mm bolt circle clamp the flange to the plate.
//   - The mating top plate should provide threaded holes / inserts for these four screws.
//   - No conical shoulder projects below the flange: everything below the plate stays within the 117 mm pilot envelope.
//
// OLD-SPEC VALUES PRESERVED
//   LED count              = 16
//   LED angular spacing    = 22.5 deg
//   Old ring OD reference  = 125 mm
//   OPT101 aperture        = 6.5 mm
//   OPT101 PCB pocket      = 28 x 22 mm, 2.2 mm deep
//   OPT101 hole spacing    = 22 x 16 mm
//   OPT101 hole diameter   = 2.2 mm
//   Detector snout         = 18 mm OD x 12 mm long
//
// DESIGN CHANGE
// The old split/clamp ring and large removable cartridge wedges are intentionally removed.
// The 16 LED positions are now integrated directly into the moving optical head.
// LED sockets are PARAMETRIC because the old ring explicitly supported multiple emitter
// packages (3 mm, 5 mm, SMD, TO-can) and therefore did not define one final LED body size.
// Defaults below are for nominal 5 mm through-hole LEDs; edit led_body_d as required.
//
// Recommended material: black PETG/ASA, matte interior preferred.
// Recommended orientation: optical deck on build plate, shroud upward if your slicer
// can bridge/handle the LED tunnel geometry; otherwise inspect preview and orient as needed.

$fn = 128;
eps = 0.08;
part = "assembly"; // "assembly", "clearance_preview", "optical_head_only"

// -----------------------------------------------------------------------------
// V2.03 FIXED CHAMBER ENVELOPE
// -----------------------------------------------------------------------------
fixed_chamber_od = 91.0;
fixed_chamber_h  = 120.0;
existing_max_od  = 105.3;  // V2.03 curved-door guide-lip swept envelope

// -----------------------------------------------------------------------------
// MOVING LIGHT SHROUD
// -----------------------------------------------------------------------------
shroud_id = 110.0;
wall_t    = 2.5;
shroud_od = shroud_id + 2*wall_t; // 115 mm
body_h    = 130.0;

lead_in_h  = 5.0;
lead_in_id = 113.0;

// V2.9 FDM optimization: smooth exterior.
// The former 120 mm bottom reinforcement ring and 118 mm circumferential
// stiffening ribs were removed because their horizontal undersides generated
// extensive support when the part is printed flange-side down.
// The 115 mm OD / 2.5 mm wall cylinder is retained continuously instead.

// -----------------------------------------------------------------------------
// FLAT THROUGH-PLATE OPTICAL DECK / MOUNTING FLANGE (V2.7)
// -----------------------------------------------------------------------------
// Recommended mating top-plate cutout. This is a reference dimension for the
// TOP PLATE, not a cut made by this SCAD part.
top_plate_clearance_hole_d = 118.0;

// The shroud itself is 115 mm OD. A shallow 117 mm pilot directly beneath the
// flange enters the 118 mm plate opening and establishes X/Y concentricity.
locating_pilot_od = 117.0;
locating_pilot_h  = 3.0;

// Broad, planar flange sits on TOP of the LIO moving plate.
deck_od = 140.0;
deck_t  = 6.0;
deck_z  = body_h;

// Four M4 clearance holes. The mating top plate should contain M4 threaded
// holes or heat-set inserts on the same bolt circle.
top_mount_hole_d = 4.5;
top_mount_bcd    = 126.0;
top_mount_n      = 4;
top_mount_angle  = 45.0;

// Optional shallow top counterbores for M4 socket-head screw heads.
// Set to 0 to disable if you prefer washers / exposed heads.
top_mount_counterbore_d = 8.0;
top_mount_counterbore_depth = 3.0;

// -----------------------------------------------------------------------------
// OPT101 - FROM OLD 006 DETECTOR CAP
// -----------------------------------------------------------------------------
opt101_pocket_w = 28.0;
opt101_pocket_d = 22.0;
opt101_pocket_depth = 2.2;
opt101_corner_r = 2.0;

opt101_hole_dx = 22.0;
opt101_hole_dy = 16.0;
opt101_hole_d  = 2.2;

// Actual detector aperture from old SCAD.
detector_aperture_d = 6.5;

// Preserve old snout geometry, now integrated directly into the deck.
detector_snout_od  = 18.0;
detector_snout_len = 12.0;

// Slightly wider root improves stiffness and blocks direct LED line-of-sight.
detector_baffle_root_od = 24.0;
detector_baffle_root_h  = 3.0;

// Old cap used a dogleg channel to avoid a straight optical leak.
opt101_wire_channel_w = 5.0;
opt101_wire_channel_depth = 2.4;

// -----------------------------------------------------------------------------
// 16 LED ILLUMINATION CHANNELS - COUNT/SPACING FROM OLD 007 LED RING
// -----------------------------------------------------------------------------
led_count = 16;
led_angle_step = 360/led_count; // 22.5 degrees

// The old ring's slot center radius was 51.5 mm. The integrated design moves the
// actual LED axis slightly inward so the complete LED tunnel remains inside the
// 110 mm optical volume and does not collide with the shroud wall.
led_ring_r = 47.0;

// Old ring did not commit to a package size. Default here is a 5 mm THT LED.
led_body_d = 5.0;
led_socket_clearance = 0.4;
led_socket_d = led_body_d + led_socket_clearance; // 5.4 mm default

// Opaque tunnel around each LED suppresses sideways/direct detector illumination.
led_tunnel_od = 10.0;
led_tunnel_len = 24.0;

// LEDs are aimed at the optical axis at a nominal target point below the deck.
// LIO can still vary Z; this is the nominal convergence geometry, not a hard focus.
nominal_target_drop = 70.0;

// LED tunnel starts slightly above deck so LED bodies can be inserted from top.
led_start_above_deck = 2.0;

// Optional top counterbore gives the LED flange / insertion end a seat.
led_top_counterbore_d = 6.4;
led_top_counterbore_depth = 2.0;

// Channel numbers are useful during wavelength wiring, but can slow render.
enable_channel_numbers = true;
channel_text_size = 2.8;
channel_text_h = 0.45;
channel_label_r = 56.0;

// Small raised orientation marker for channel 1 / 0 degrees.
marker_r = 61.0;
marker_d = 3.0;
marker_h = 1.0;

// -----------------------------------------------------------------------------
// DERIVED / SAFETY
// -----------------------------------------------------------------------------
rail_radial_clearance = (shroud_id-existing_max_od)/2;

function vsub(a,b) = [a[0]-b[0],a[1]-b[1],a[2]-b[2]];
function vlen(v) = sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);
function vscale(v,s) = [v[0]*s,v[1]*s,v[2]*s];
function vunit(v) = let(L=vlen(v)) [v[0]/L,v[1]/L,v[2]/L];
function vadd(a,b) = [a[0]+b[0],a[1]+b[1],a[2]+b[2]];

module cyl_between(p1,p2,d){
    v = vsub(p2,p1);
    L = vlen(v);
    axis = [-v[1],v[0],0];
    ang = acos(v[2]/L);
    translate(p1)
        rotate(a=ang,v=(vlen(axis)<0.0001 ? [1,0,0] : axis))
            cylinder(d=d,h=L);
}

module rounded_rect_2d(w,d,r){
    hull(){
        for(x=[-w/2+r,w/2-r])
        for(y=[-d/2+r,d/2-r])
            translate([x,y]) circle(r=r);
    }
}

module ring(od,id,h){
    difference(){
        cylinder(d=od,h=h);
        translate([0,0,-eps]) cylinder(d=id,h=h+2*eps);
    }
}

module shroud_internal_void(){
    translate([0,0,-eps])
        cylinder(d1=lead_in_id,d2=shroud_id,h=lead_in_h+eps);
    translate([0,0,lead_in_h-eps])
        cylinder(d=shroud_id,h=body_h-lead_in_h+2*eps);
}

module top_mount_holes(){
    for(i=[0:top_mount_n-1]){
        a=top_mount_angle+i*360/top_mount_n;
        rotate([0,0,a]){
            // Through clearance for M4 screw.
            translate([top_mount_bcd/2,0,deck_z-eps])
                cylinder(d=top_mount_hole_d,h=deck_t+4*eps);
            // Recess screw head from the electronics side while preserving
            // a flat uninterrupted underside mounting face.
            if(top_mount_counterbore_depth > 0)
                translate([top_mount_bcd/2,0,
                           deck_z+deck_t-top_mount_counterbore_depth])
                    cylinder(d=top_mount_counterbore_d,
                             h=top_mount_counterbore_depth+2*eps);
        }
    }
}

module opt101_mount_holes(){
    for(x=[-opt101_hole_dx/2,opt101_hole_dx/2])
    for(y=[-opt101_hole_dy/2,opt101_hole_dy/2])
        translate([x,y,deck_z-eps])
            cylinder(d=opt101_hole_d,h=deck_t+4*eps);
}

module opt101_pocket_cut(){
    translate([0,0,deck_z+deck_t-opt101_pocket_depth])
        linear_extrude(height=opt101_pocket_depth+eps)
            rounded_rect_2d(opt101_pocket_w,opt101_pocket_d,opt101_corner_r);
}

module opt101_dogleg_wire_cut(){
    z0 = deck_z + deck_t - opt101_wire_channel_depth;

    // V2.8 FIX: route the OPT101 cable BETWEEN adjacent LED tunnels instead of
    // radially through an LED position. LEDs are spaced every 22.5 deg, so the
    // outer leg uses the 11.25 deg bisector between LED channels 1 and 2.
    // A short inner dogleg also prevents a straight optical leak to the detector.
    a = led_angle_step/2;       // 11.25 deg: halfway between adjacent LEDs
    p0 = [14.0,  0.0];         // exits the OPT101 pocket
    p1 = [27.0,  0.0];         // short radial leg inside LED ring
    p2 = [34*cos(a),34*sin(a)]; // turn toward inter-LED corridor
    p3 = [(deck_od/2+1)*cos(a),(deck_od/2+1)*sin(a)]; // exit flange edge

    // Rounded constant-width trench made from hulled vertical cylinders.
    for(seg=[[p0,p1],[p1,p2],[p2,p3]])
        hull(){
            translate([seg[0][0],seg[0][1],z0])
                cylinder(d=opt101_wire_channel_w,h=opt101_wire_channel_depth+eps);
            translate([seg[1][0],seg[1][1],z0])
                cylinder(d=opt101_wire_channel_w,h=opt101_wire_channel_depth+eps);
        }
}

module detector_baffle_positive(){
    // Root disk immediately below deck.
    translate([0,0,deck_z-detector_baffle_root_h])
        cylinder(d=detector_baffle_root_od,h=detector_baffle_root_h);
    // 18 mm OD x 12 mm long snout from old detector cap.
    translate([0,0,deck_z-detector_snout_len])
        cylinder(d=detector_snout_od,h=detector_snout_len);
}

module detector_aperture_cut(){
    translate([0,0,deck_z-detector_snout_len-eps])
        cylinder(d=detector_aperture_d,h=detector_snout_len+deck_t+3*eps);
}

function led_start(i) =
    let(a=i*led_angle_step)
    [led_ring_r*cos(a),led_ring_r*sin(a),deck_z+deck_t+led_start_above_deck];

function led_target() = [0,0,deck_z-nominal_target_drop];

function led_end(i,extra=0) =
    let(p=led_start(i), u=vunit(vsub(led_target(),p)))
    vadd(p,vscale(u,led_tunnel_len+extra));

module one_led_tunnel_positive(i){
    p1=led_start(i);
    p2=led_end(i);
    cyl_between(p1,p2,led_tunnel_od);
}

module one_led_socket_cut(i){
    p1=led_start(i);
    // extend bore a little past physical tunnel so the optical path is completely open
    p2=led_end(i,2.0);
    cyl_between(p1,p2,led_socket_d);

    // shallow insertion counterbore at the top end, following same axis
    u=vunit(vsub(led_target(),p1));
    p_cb_end=vadd(p1,vscale(u,led_top_counterbore_depth));
    cyl_between(p1,p_cb_end,led_top_counterbore_d);
}

module led_tunnels_positive(){
    for(i=[0:led_count-1]) one_led_tunnel_positive(i);
}

module led_socket_cuts(){
    for(i=[0:led_count-1]) one_led_socket_cut(i);
}

module channel_numbers_positive(){
    if(enable_channel_numbers){
        for(i=[0:led_count-1]){
            a=i*led_angle_step;
            rotate([0,0,a])
                translate([channel_label_r,0,deck_z+deck_t])
                    linear_extrude(height=channel_text_h)
                        text(str(i+1),size=channel_text_size,
                             font="Liberation Sans:style=Bold",
                             halign="center",valign="center");
        }
    }
}

module orientation_marker_positive(){
    translate([marker_r,0,deck_z+deck_t]) cylinder(d=marker_d,h=marker_h);
}

module positive_geometry(){
    union(){
        // Lightweight moving shroud.
        // V2.9: completely smooth 115 mm OD exterior. No projecting
        // circumferential ribs or bottom lip; this eliminates the large
        // support trees those features required when printed upside down.
        cylinder(d=shroud_od,h=body_h);

        // V2.7 through-plate interface: no oversized cone below the plate.
        // The 117 mm pilot is the largest feature that enters the 118 mm hole.
        translate([0,0,deck_z-locating_pilot_h])
            cylinder(d=locating_pilot_od,h=locating_pilot_h+eps);

        // Flat mounting flange / optical deck. Its underside at Z=deck_z is
        // planar and seats directly on the upper face of the moving top plate.
        translate([0,0,deck_z]) cylinder(d=deck_od,h=deck_t);

        // Center detector baffle/snout.
        detector_baffle_positive();

        // 16 integrated opaque LED aiming tunnels.
        led_tunnels_positive();

        // Wiring/channel identification.
        channel_numbers_positive();
        orientation_marker_positive();
    }
}

module negative_geometry(){
    shroud_internal_void();
    top_mount_holes();

    // OPT101 locating and optical features.
    opt101_pocket_cut();
    opt101_mount_holes();
    detector_aperture_cut();
    opt101_dogleg_wire_cut();

    // Sixteen emitter sockets.
    led_socket_cuts();
}

module integrated_assembly(){
    difference(){
        positive_geometry();
        negative_geometry();
    }
}

module optical_head_only(){
    intersection(){
        integrated_assembly();
        translate([-deck_od,-deck_od,deck_z-detector_snout_len-3])
            cube([2*deck_od,2*deck_od,deck_t+detector_snout_len+12]);
    }
}

module clearance_preview(){
    color("black") integrated_assembly();
    %color("red") cylinder(d=existing_max_od,h=fixed_chamber_h);
    %color("gray") cylinder(d=fixed_chamber_od,h=fixed_chamber_h);
    // OPT101 PCB reference seated in top pocket.
    %color("green")
        translate([0,0,deck_z+deck_t+0.8])
            cube([opt101_pocket_w,opt101_pocket_d,1.6],center=true);
    // Nominal convergence target.
    %color("blue") translate(led_target()) sphere(d=4);
}

// -----------------------------------------------------------------------------
// VALIDATION
// -----------------------------------------------------------------------------
echo("LIO V2.9 integrated 16-LED + OPT101 through-plate optical head/shroud - smooth support-optimized exterior + inter-LED wire routing");
echo(str("LED channels: ",led_count," @ ",led_angle_step," deg"));
echo(str("Shroud ID: ",shroud_id," mm"));
echo(str("V2.03 max envelope: ",existing_max_od," mm"));
echo(str("Minimum radial clearance: ",rail_radial_clearance," mm"));
echo(str("OPT101 aperture: ",detector_aperture_d," mm"));
echo(str("OPT101 pocket: ",opt101_pocket_w," x ",opt101_pocket_d," x ",opt101_pocket_depth," mm"));
echo(str("LED default socket: ",led_socket_d," mm for nominal ",led_body_d," mm emitter"));
echo(str("Nominal LED convergence drop: ",nominal_target_drop," mm"));

echo(str("Top-plate recommended clearance hole: ",top_plate_clearance_hole_d," mm"));
echo(str("Locating pilot: ",locating_pilot_od," mm OD x ",locating_pilot_h," mm"));
echo(str("Flat flange: ",deck_od," mm OD x ",deck_t," mm"));
echo(str("M4 mount BCD: ",top_mount_bcd," mm"));

assert(shroud_od < top_plate_clearance_hole_d,
       "ERROR: shroud OD must pass through top-plate clearance hole");
assert(locating_pilot_od < top_plate_clearance_hole_d,
       "ERROR: locating pilot must fit inside top-plate clearance hole");
assert(top_mount_bcd/2 + top_mount_counterbore_d/2 < deck_od/2,
       "ERROR: mounting counterbores break through flange OD");
assert(led_count==16,"ERROR: LIO legacy optical specification requires 16 LED channels");
assert(abs(led_angle_step-22.5)<0.001,"ERROR: 16 channels must be spaced at 22.5 degrees");
assert(shroud_id>existing_max_od,"ERROR: shroud does not clear V2.03 envelope");
assert(rail_radial_clearance>=2.0,"ERROR: radial clearance below 2 mm");
assert(detector_aperture_d==6.5,"ERROR: detector aperture changed from old OPT101 specification");
assert(led_ring_r+led_tunnel_od/2 < shroud_id/2,
       "ERROR: LED tunnel envelope collides with shroud bore/wall");
assert(detector_snout_od < 2*(led_ring_r-led_tunnel_od/2),
       "ERROR: detector baffle collides with LED tunnels");

if(part=="assembly") integrated_assembly();
if(part=="clearance_preview") clearance_preview();
if(part=="optical_head_only") optical_head_only();
