/*
 LIO V2.12 - Tight-fit full 360-degree stationary transition light-trap collar

 Mating geometry:
   Existing stationary chamber OD = 91.0 mm
   Existing moving optical shroud ID = 110.0 mm

 Revised tighter clearances:
   Lower collar ID = 92.0 mm -> 0.50 mm radial slip clearance
   Upper collar OD = 108.0 mm -> 1.00 mm radial running clearance

 The collar sits only on the unobstructed upper portion of the stationary chamber,
 above the sample door/guide hardware. It is a complete 360-degree ring.
 No internal stop shelf is used; the bore remains fully open.

 Print upright with the 92 mm-ID end on the bed. No supports intended.
*/

$fn = 180;

// ---- Known mating dimensions ----
stationary_od    = 91.0;
moving_shroud_id = 110.0;

// ---- Tight clearances ----
lower_radial_clearance = 0.50; // tighter stationary slip fit
upper_radial_clearance = 1.00; // tighter non-contact moving fit
wall = 2.0;

// ---- Derived diameters ----
lower_id = stationary_od + 2*lower_radial_clearance; // 92.0
lower_od = lower_id + 2*wall;                        // 96.0
upper_od = moving_shroud_id - 2*upper_radial_clearance; // 108.0
upper_id = upper_od - 2*wall;                        // 104.0

// ---- Heights ----
lower_engagement_h = 18.0;
// 45-degree exterior transition: radial growth = (108-96)/2 = 6 mm
transition_h = (upper_od - lower_od)/2; // 6.0
upper_lighttrap_h = 34.0;
total_h = lower_engagement_h + transition_h + upper_lighttrap_h; // 58 mm

// Small installation lead-in at bottom only
lead_h = 1.2;
lead_extra_d = 0.6;

eps = 0.05;

module outer_body() {
    union() {
        cylinder(d=lower_od, h=lower_engagement_h);

        translate([0,0,lower_engagement_h])
            cylinder(d1=lower_od, d2=upper_od, h=transition_h);

        translate([0,0,lower_engagement_h + transition_h])
            cylinder(d=upper_od, h=upper_lighttrap_h);
    }
}

module open_bore() {
    union() {
        // Slight lead-in makes the 0.5 mm radial fit easier to start.
        translate([0,0,-eps])
            cylinder(d1=lower_id + lead_extra_d,
                     d2=lower_id,
                     h=lead_h + eps);

        translate([0,0,lead_h-eps])
            cylinder(d=lower_id,
                     h=lower_engagement_h - lead_h + 2*eps);

        // Smooth hollow transition; no shelf or center membrane.
        translate([0,0,lower_engagement_h-eps])
            cylinder(d1=lower_id,
                     d2=upper_id,
                     h=transition_h + 2*eps);

        translate([0,0,lower_engagement_h + transition_h-eps])
            cylinder(d=upper_id,
                     h=upper_lighttrap_h + 2*eps);
    }
}

difference() {
    outer_body();
    open_bore();
}

// ---- Console checks ----
echo("stationary chamber OD", stationary_od);
echo("collar lower ID", lower_id);
echo("stationary radial clearance", (lower_id-stationary_od)/2);
echo("collar lower OD", lower_od);
echo("collar upper OD", upper_od);
echo("collar upper ID", upper_id);
echo("moving shroud ID", moving_shroud_id);
echo("moving radial clearance", (moving_shroud_id-upper_od)/2);
echo("total height", total_h);
