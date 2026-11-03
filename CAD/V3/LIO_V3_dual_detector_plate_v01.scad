// ============================================================
// LIO V3 — Dual-Detector Plate  (drop-in replacement for detector_mount)
//
// Dimensions now taken from LIO_V3_master.scad, not guessed:
//   PLATE      = rr(44, 36, 3, 3)      -> 44 x 36 x 3 mm, corner r=3
//   MOUNT HOLES= x=[-18,18], y=[-14,14], d=3.4  (matches optical_deck
//              hex-nut pockets: nuts in deck, screws from this plate)
//   DECK WINDOW= central hole in optical_deck, originally d=24
//   BOARD      = your measured CJMCU-101 = 28.575 x 19.05 mm (1.125 x 0.75 in)
//
// THE REAL CONSTRAINT:
//   Both detectors must see the sample through the deck's central hole.
//   A 28.575-wide board does NOT leave room beside a centered photodiode
//   inside the original Ø24 window. You MUST enlarge that deck hole.
//   In optical_deck(), change:   hole(24,-eps,deck_t+eps);
//                       to:       hole(32,-eps,deck_t+eps);
//   Set deck_center_hole_d below to match whatever you choose; the echo
//   check will tell you if the InGaAs actually clears.
// ============================================================

$fn = 96;

/* ---- PLATE + 4 MOUNT HOLES : exact from master, do not change to fit ---- */
// Plate AUTO-GROWS so every hole is fully surrounded by >= edge_margin of
// material. It never shrinks below the master floor (44 x 36).
plate_l_min    = 44;    // X floor (master rr width)
plate_w_min    = 36;    // Y floor (master rr depth)
edge_margin    = 5;     // solid material beyond the outermost hole/feature
plate_t        = 3;     // thickness (master)
corner_r       = 3;

mount_x        = 18;    // holes at x = +/-18   (master)
mount_y        = 14;    // holes at y = +/-14   (master)
mount_hole_d   = 3.4;   // (master)

/* ---- DECK WINDOW (for the fit check; change the deck to match) ---- */
deck_center_hole_d = 32;   // <-- enlarge optical_deck hole(24) to this

/* ---- OPT101 / CJMCU-101 BOARD : your measured size ---- */
board_l        = 28.575; // 1.125 in
board_w        = 19.05;  // 0.75 in
board_t        = 1.6;
board_clear    = 0.5;
divot_extra    = 0.4;    // divot slightly deeper than board

// Photodiode position relative to BOARD CENTER (measure the clear window
// on the chip). Photodiode is placed on the optical axis (plate center);
// the board is shifted so the window lands at 0,0. 0,0 = centered board.
pd_off_x       = 0;      // +X toward "right"
pd_off_y       = 0;      // +Y toward "back"

// OPT101 PDIP chip pocket (datasheet MAX -> always clears). Cut through;
// this opening is also the light path.
chip_l         = 9.91;
chip_w         = 6.99;
chip_clear     = 0.5;

/* ---- MTPD1346D InGaAs : TO-46 can ---- */
to46_dia       = 4.6;   // MEASURE your can
to46_clear     = 0.3;
ingaas_gap     = 1.5;   // wall between board edge and the can hole
ingaas_side    = "back";   // "back"(+Y),"front"(-Y),"right"(+X),"left"(-X)

key_type       = "tab"; // "tab", "flat", or "none"
tab_w          = 1.4;
tab_proj       = 0.9;
flat_depth     = 0.5;

/* ================= derived ================= */
bcx = -pd_off_x;  bcy = -pd_off_y;         // board center so photodiode = origin
dv_x0 = bcx - board_l/2 - board_clear;
dv_x1 = bcx + board_l/2 + board_clear;
dv_y0 = bcy - board_w/2 - board_clear;
dv_y1 = bcy + board_w/2 + board_clear;
divot_d = board_t + divot_extra;

pocket_l  = chip_l + 2*chip_clear;
pocket_w  = chip_w + 2*chip_clear;
to46_hole = to46_dia + 2*to46_clear;

edge_back = dv_y1; edge_front = -dv_y0; edge_right = dv_x1; edge_left = -dv_x0;
ing_pos =
  ingaas_side=="back"  ? [0,  edge_back  + ingaas_gap + to46_hole/2] :
  ingaas_side=="front" ? [0,-(edge_front + ingaas_gap + to46_hole/2)] :
  ingaas_side=="right" ? [ edge_right + ingaas_gap + to46_hole/2, 0] :
                         [-(edge_left + ingaas_gap + to46_hole/2), 0];
ing_dir = ingaas_side=="back" ? 90 : ingaas_side=="front" ? 270
        : ingaas_side=="right" ? 0 : 180;
ing_r_from_center = sqrt(ing_pos[0]*ing_pos[0]+ing_pos[1]*ing_pos[1]);
deck_r = deck_center_hole_d/2;

// --- auto-size the plate so ALL holes are fully surrounded ---
featX = max(mount_x + mount_hole_d/2,
            abs(ing_pos[0]) + to46_hole/2 + tab_proj,
            dv_x1, -dv_x0);
featY = max(mount_y + mount_hole_d/2,
            abs(ing_pos[1]) + to46_hole/2 + tab_proj,
            dv_y1, -dv_y0);
plate_l = max(plate_l_min, 2*(featX + edge_margin));
plate_w = max(plate_w_min, 2*(featY + edge_margin));
plate_diag = sqrt(pow(plate_l/2,2)+pow(plate_w/2,2));

/* ================= checks ================= */
echo(str("Plate ", plate_l, " x ", plate_w, " x ", plate_t,
         " | mount holes +/-", mount_x, ",", mount_y, " d", mount_hole_d));
if (plate_diag > 33)
    echo(str("WARNING: plate corner reaches r=", plate_diag,
             " mm; LED ring is at r=35 — reduce edge_margin if it crowds the LEDs"));
echo(str("InGaAs hole center ", ing_pos, "  radius-from-center ", ing_r_from_center));
if (ing_r_from_center + to46_hole/2 > deck_r)
    echo(str("WARNING: InGaAs cannot see through deck window. Enlarge deck hole to >= ",
             2*(ing_r_from_center + to46_hole/2), " mm (currently ", deck_center_hole_d, ")"));
if (sqrt(pow(pocket_l/2,2)+pow(pocket_w/2,2)) > deck_r)
    echo("WARNING: OPT101 aperture exceeds deck window — enlarge deck hole");
// board divot vs mount holes
if (dv_x1 > mount_x - mount_hole_d/2 - 0.5 && dv_y1 > mount_y - mount_hole_d/2 - 0.5)
    echo("WARNING: board divot may clip a mount hole — check pd_off or board size");

/* ================= geometry ================= */
module rr(w,d,t,r) linear_extrude(t) offset(r) offset(-r) square([w-2*r,d-2*r],center=true);

module plate() rr(plate_l, plate_w, plate_t, corner_r);

module mount_holes()
    for (sx=[-1,1], sy=[-1,1])
        translate([sx*mount_x, sy*mount_y, -1])
            cylinder(d=mount_hole_d, h=plate_t+2);

module opt101_cavity() {
    // board divot (open top)
    translate([dv_x0, dv_y0, plate_t-divot_d])
        cube([dv_x1-dv_x0, dv_y1-dv_y0, divot_d+1]);
    // chip pocket cut through = light aperture, at the photodiode (origin)
    translate([-pocket_l/2, -pocket_w/2, -1])
        cube([pocket_l, pocket_w, plate_t+2]);
}

module ingaas_hole() {
    translate([ing_pos[0], ing_pos[1], 0]) {
        translate([0,0,-1]) cylinder(d=to46_hole, h=plate_t+2);
        rotate([0,0,ing_dir]) {
            if (key_type=="tab")
                translate([to46_hole/2-0.01, -tab_w/2, -1])
                    cube([tab_proj+0.01, tab_w, plate_t+2]);
            if (key_type=="flat")
                translate([to46_hole/2-flat_depth, -to46_hole, -1])
                    cube([flat_depth+1, to46_hole*2, plate_t+2]);
        }
    }
}

difference() {
    plate();
    mount_holes();
    opt101_cavity();
    ingaas_hole();
}
