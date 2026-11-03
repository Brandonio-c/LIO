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
detachable_feet_layout();
