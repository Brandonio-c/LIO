# LIO V3 — Optical Channel Map

Holes are numbered clockwise from 12 o'clock on the 35 mm emitter ring of the optical deck. Channel n drives hole n.

```
                        1 (395)
            16 (1850)             2 (405)
       15 (1760)                       3 (blue)
     14 (1650)                           4 (green)
    13 (1550)        [ OPT101 | InGaAs ]   5 (yellow)
     12 (1450)                           6 (orange)
       11 (reserved)                   7 (red)
            10 (reserved)         8 (850)
                        9 (940)
```

## Current map (Rev A, as built)

| Hole / CH | Emitter | Register output (pin) | Rail / driver | Detector |
|---|---|---|---|---|
| 1 | 395 nm UV | U1 Q0 (15) | A / DRV1 | OPT101 |
| 2 | ≈405 nm violet | U1 Q1 (1) | A / DRV1 | OPT101 |
| 3 | Blue ≈465 nm | U1 Q2 (2) | A / DRV1 | OPT101 |
| 4 | Green ≈525 nm | U1 Q3 (3) | A / DRV1 | OPT101 |
| 5 | Yellow ≈590 nm | U1 Q4 (4) | A / DRV1 | OPT101 |
| 6 | Orange ≈605 nm | U1 Q5 (5) | A / DRV1 | OPT101 |
| 7 | Red ≈630 nm | U1 Q6 (6) | A / DRV1 | OPT101 |
| 8 | 850 nm | U1 Q7 (7) | A / DRV1 | OPT101 + InGaAs |
| 9 | 940 nm | U2 Q0 (15) | A / DRV1 | OPT101 + InGaAs |
| 10 | reserved | U2 Q1 (1) | B / DRV2 | (InGaAs) |
| 11 | reserved | U2 Q2 (2) | B / DRV2 | (InGaAs) |
| 12 | 1450 nm | U2 Q3 (3) | B / DRV2 | InGaAs |
| 13 | 1550 nm | U2 Q4 (4) | B / DRV2 | InGaAs |
| 14 | 1650 nm | U2 Q5 (5) | B / DRV2 | InGaAs |
| 15 | 1760 nm | U2 Q6 (6) | B / DRV2 | InGaAs (weak, at cutoff) |
| 16 | 1850 nm | U2 Q7 (7) | B / DRV2 | none yet |

**Holes 10–11:** fit through-hole 1200 / 1300 nm emitters (RAIL B) when bought. If white or pink LEDs go there instead, wire their anodes to RAIL A and change `isRailB()` in the firmware to `return h >= 11;`.

## Detector coverage

| Detector | Range | Holes |
|---|---|---|
| OPT101 (silicon) | ≈300–1100 nm | 1–9 |
| MTPD1346D (InGaAs) | ≈800–1750 nm | 8–15 |
| Overlap (cross-calibration) | 850, 940 nm | 8, 9 |
| Gap | > 1750 nm | 16 (needs a 2.6 µm extended-InGaAs detector) |

## History

| Version | Holes 1–16 | Why it changed |
|---|---|---|
| v1 | 300, 400, blue, green, yellow, orange, red, 890, 1020, 1200, 1300, 1450, 1550, 1650, 1760, 1850 | SMD emitters (300–1300 nm) couldn't be mounted reliably |
| Rev A (current) | Table above | Through-hole only |

## Mechanical notes

- The seats are sized for 5 mm LED bodies (`led_body_d = 5`), with a counterbore for the flange and a tilt toward the sample plane.
- Narrow-beam IR/SWIR parts depend most on accurate aiming.
- Through-hole metal-can parts (TO-46/TO-39) don't fit the 5 mm seats and need adapted seats.
