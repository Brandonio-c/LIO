/*
 LIO V2
 V2_02_short_optical_datum_guard_ring_v02.scad

 Purpose
 -------
 Short removable optical-axis datum / lower guard ring for the already-printed
 V2 motor base. This REPLACES the earlier 60 mm-tall lower receiver concept.

 It intentionally does NOT form the final fixed telescoping receiver.
 The real fixed receiver will be mounted higher, above the sample-loading region,
 after the moving carriage and sleeve heights are established.

 Design goals
 ------------
 - Fit the existing Ø92.0 mm shallow recess in the motor base.
 - Establish physical X=0 / Y=0 optical datum.
 - Keep the sample-loading region open and accessible.
 - Provide a short lower light/guard labyrinth without constraining motion.
 - Be removable; no drilling of the successful base is required.
 - Print support-free, flange-down.

 IMPORTANT:
 This part is NOT a bearing and must not guide the moving telescope sleeve.
*/

$fn = 160;

// ---------- Existing base interface ----------
base_recess_d       = 92.0;
base_recess_depth   = 0.8;

// PETG/FDM locating clearance: 0.6 mm diametral
locating_flange_d   = 91.4;
locating_flange_h   = 0.75;   // deliberately <= base recess depth

// ---------- Guard ring ----------
// Keep this short so the operator can access the sample carriage at low Z.
guard_od            = 84.0;
guard_id            = 70.0;
guard_h              = 12.0;

// Wide flange above the recess gives a stable shoulder without needing screws.
shoulder_od          = 91.4;
shoulder_h           = 3.0;

// Gentle internal lead-in; useful if the future moving sleeve passes through
// this region, but intentionally generous and non-guiding.
lead_in_h            = 2.0;
lead_in_extra_d      = 2.0;

// Optional shallow gasket/light-seal groove on underside of shoulder.
gasket_enable        = true;
gasket_mean_d        = 86.0;
gasket_width         = 1.6;
gasket_depth         = 0.5;

// ---------- Visual references only ----------
show_base_reference          = false;
show_future_sleeve_reference = false;
future_moving_sleeve_od      = 63.5;

EPS = 0.02;

module annulus(od, id, h) {
    difference() {
        cylinder(d=od, h=h);
        translate([0,0,-EPS]) cylinder(d=id, h=h+2*EPS);
    }
}

module gasket_groove_cut() {
    if (gasket_enable) {
        difference() {
            cylinder(d=gasket_mean_d + gasket_width, h=gasket_depth + EPS);
            translate([0,0,-EPS])
                cylinder(d=gasket_mean_d - gasket_width, h=gasket_depth + 3*EPS);
        }
    }
}

module datum_guard_ring() {
    difference() {
        union() {
            // Locating tongue that drops into the existing Ø92 recess.
            annulus(locating_flange_d, guard_id + lead_in_extra_d,
                    locating_flange_h);

            // Stable shoulder sitting on the base surface.
            translate([0,0,locating_flange_h])
                annulus(shoulder_od, guard_id + lead_in_extra_d, shoulder_h);

            // Short guard wall only -- intentionally NOT a 60 mm receiver.
            translate([0,0,locating_flange_h + shoulder_h])
                annulus(guard_od, guard_id, guard_h);
        }

        // Internal tapered lead-in from the bottom into the guard bore.
        // Removes material only; does not create a tight sliding interface.
        translate([0,0,-EPS])
            cylinder(d1=guard_id + lead_in_extra_d,
                     d2=guard_id,
                     h=locating_flange_h + shoulder_h + lead_in_h + EPS);

        // Optional underside gasket groove in the shoulder contact region.
        if (gasket_enable)
            translate([0,0,locating_flange_h - gasket_depth])
                gasket_groove_cut();
    }
}

module base_reference() {
    color([0.55,0.55,0.55,0.25])
    difference() {
        cylinder(d=110, h=2);
        translate([0,0,1.2]) cylinder(d=base_recess_d, h=1);
    }
}

module future_sleeve_reference() {
    color([0.1,0.4,1.0,0.25])
        translate([0,0,locating_flange_h + shoulder_h + 1])
            difference() {
                cylinder(d=future_moving_sleeve_od, h=25);
                translate([0,0,-EPS])
                    cylinder(d=future_moving_sleeve_od-5, h=25+2*EPS);
            }
}

// ---------- Sanity checks ----------
assert(locating_flange_d < base_recess_d,
       "Locating flange must be smaller than the base recess.");
assert(locating_flange_h <= base_recess_depth,
       "Locating tongue is deeper than the existing base recess.");
assert(guard_id > future_moving_sleeve_od,
       "Guard bore must remain larger than future moving sleeve OD.");

echo("LIO V2 short datum/guard ring");
echo("base_recess_d", base_recess_d);
echo("locating_flange_d", locating_flange_d);
echo("diametral_fit_clearance", base_recess_d-locating_flange_d);
echo("guard_height_above_base_mm", shoulder_h+guard_h);
echo("guard_id", guard_id);
echo("future_sleeve_od_reference", future_moving_sleeve_od);
echo("future_radial_clearance_reference_mm", (guard_id-future_moving_sleeve_od)/2);

datum_guard_ring();

if (show_base_reference) base_reference();
if (show_future_sleeve_reference) future_sleeve_reference();
