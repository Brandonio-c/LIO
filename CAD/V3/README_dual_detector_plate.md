# Dual-detector plate (LIO V3)

`LIO_V3_dual_detector_plate_v01.scad` replaces `detector_mount()` in `LIO_V3_master.scad`. It holds both detectors in the centre of the optical deck:

- the **OPT101 / CJMCU-101 board** (28.575 × 19.05 mm), in a top divot, with the chip on the optical axis
- the **MTPD1346D InGaAs** TO-46 can, in a keyed hole just beyond the board edge

The four M3 mounting holes (±18 mm, ±14 mm, Ø3.4) come from the master file. The plate auto-sizes so every hole has at least 5 mm of material around it.

**Required deck change:** the master's `optical_deck()` central window is Ø24, which is smaller than the board. To give the InGaAs a line of sight, change `hole(24,-eps,deck_t+eps);` to about Ø34. The `.scad` file prints the exact minimum diameter in the OpenSCAD console.

**Measure before printing:**

- the TO-46 can diameter and its tab or flat (`to46_dia`, `key_type`, `tab_w`, `tab_proj`)
- the photodiode's offset from the board centre (`pd_off_x`, `pd_off_y`)
