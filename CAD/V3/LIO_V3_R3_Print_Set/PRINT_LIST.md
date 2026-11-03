# Bottom-up print list - R3

Reuse the existing V2 motor base; do not print it again.

| File | Pieces | Geometric envelope X x Y x Z (mm) | Orientation |
|---|---:|---|---|
| `01_Base_Mount_and_Nest.scad` | 2 | 208.0 x 204.0 x 22.0 | Adapter saddle-face down; nest upright |
| `02_Motion_Interfaces.scad` | 18 | 208.0 x 171.0 x 47.0 | Guide flanges down; spacers up; remaining parts flat |
| `03_Chamber_and_Door.scad` | 2 | 107.0 x 174.7 x 140.0 | Chamber and panel upright |
| `04_Carriage.scad` | 1 | 200.0 x 160.0 x 8.0 | Flat |
| `05_Shroud.scad` | 1 | 122.0 x 122.0 x 130.0 | Flange down, tube up |
| `06_Optical_Head.scad` | 3 | 203.0 x 203.0 x 19.0 | Deck flat; retainer top face down; detector tube up |
| `07_Electronics_Cover.scad` | 1 | 118.0 x 118.2 x 30.0 | Solid roof down |
| `08_Upper_Guide_Tie.scad` | 1 | 200.0 x 160.0 x 6.0 | Flat, conditional |

**Total: 28 core pieces + 1 conditional guide tie.** Hardware and coupons excluded.

Run the relevant `00_Fit_Tests.scad` selections before each full-size interface. All supplied hardware dimensions are examples until the matching physical parts are checked. The guide tie, if required for alignment, must be installed before powered motion even though its filename is last.

`README.md` gives the actual bottom-up assembly procedure and the required bought hardware. `Single_Part.scad` permits individual replacement exports.
