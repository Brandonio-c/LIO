# LIO V3 — Optical Channel Map

Holes are numbered clockwise from 12 o'clock on the 35 mm emitter ring of the optical deck. Channel n drives hole n.

```
                        1 (395)
            16 (1850)             2 (purple)
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
| 2 | purple (~405 nm) | U1 Q1 (1) | A / DRV1 | OPT101 |
| 3 | Blue ≈465 nm | U1 Q2 (2) | A / DRV1 | OPT101 |
| 4 | Green ≈525 nm | U1 Q3 (3) | A / DRV1 | OPT101 |
| 5 | Yellow ≈590 nm | U1 Q4 (4) | A / DRV1 | OPT101 |
| 6 | Orange ≈605 nm | U1 Q5 (5) | A / DRV1 | OPT101 |
| 7 | Red ≈630 nm | U1 Q6 (6) | A / DRV1 | OPT101 |
| 8 | 850 nm | U1 Q7 (7) | A / DRV1 | OPT101 + InGaAs |
| 9 | 940 nm | U2 Q0 (15) | B / DRV2 | OPT101 + InGaAs |
| 10 | reserved | U2 Q1 (1) | B / DRV2 | (InGaAs) |
| 11 | reserved | U2 Q2 (2) | B / DRV2 | (InGaAs) |
| 12 | 1450 nm — Quelighting QLIR01MXGM | U2 Q3 (3) | B / DRV2 | InGaAs |
| 13 | 1550 nm — Marktech MTE5115D4 | U2 Q4 (4) | B / DRV2 | InGaAs |
| 14 | 1650 nm — Marktech MTE5116D4 | U2 Q5 (5) | B / DRV2 | InGaAs |
| 15 | 1760 nm — Marktech MTE2117C1 | U2 Q6 (6) | B / DRV2 | InGaAs (weak, at cutoff) |
| 16 | 1850 nm | U2 Q7 (7) | B / DRV2 | none yet |

**Historical rail record:** RAIL A (DRV1, 30 mA) feeds holes 1–8 on U1, with red/black leads. RAIL B (DRV2, ≈45 mA) feeds holes 9–16 on U2, with yellow/white leads. The split is `RAIL_B_FIRST_HOLE = 9` in the firmware and `rails` in `lio_hw.yaml`. Firmware ≥ 2.5.2 reports it as `INFO rail_b_first`, and the host refuses to run if it differs from the config. Hole 9's 940 nm LED is rated 20 mA, so `duty.max_on_ms_per_hole` gives it RAIL A's 1 s/min budget even though it is on RAIL B.

**Current declaration:** the owner reports approximately 30 mA on both rails; those currents remain unmeasured, and YAML still records B 45 mA. The historical values above are not fresh measurements. No current or operating limit is changed by this purchase record.

**Holes 10–11** hold white and pink LEDs on RAIL B (`lio_hw.yaml`).

## Purchased source identities

The owner confirmed the h12–h15 purchase part numbers on 25 November 2026 (purchase date 7 May 2026). The table above associates those purchases with the existing nominal hole map; physical fitted-part confirmation after replacements remains open. See [SWIR purchase record](hardware/SWIR_COMPONENTS_PURCHASED_2026-05-07.md) for datasheets and discrepancies. h16 still lacks an identified purchased part and remains `proxy_unassigned`.

The MTPD1346D-100 is broadband: the manufacturer's current datasheet specifies 600–1750 nm, while the DigiKey catalog says 800–1750 nm. The catalog's “1300 nm” descriptor is not a narrow passband. Sources 1450/1550/1650 nm are spectrally compatible; the broad MTE2117C1 has partial overlap near cutoff. That is not a calibrated 1760 nm band measurement.

## Detector coverage

| Detector | Range | Holes |
|---|---|---|
| OPT101 (silicon) | ≈300–1100 nm | 1–9 |
| MTPD1346D-100 (InGaAs) | Manufacturer 600–1750 nm; catalog 800–1750 nm | h8/h9 and h12–14; h15 spectral-tail/cutoff-sensitive; other responses require spectral attribution |
| Overlap (cross-calibration) | 850, 940 nm | 8, 9 |
| Gap | > 1750 nm | 16 (needs a 2.6 µm extended-InGaAs detector) |

## History

| Version | Holes 1–16 | Why it changed |
|---|---|---|
| v1 | 300, 400, blue, green, yellow, orange, red, 890, 1020, 1200, 1300, 1450, 1550, 1650, 1760, 1850 | SMD emitters (300–1300 nm) couldn't be mounted reliably |
| Rev A (current) | Table above | Through-hole only |
| Rev A, 2026-11-17 | Unchanged | Hole 9 moved from RAIL A to RAIL B in software, to match the wiring (U2 holes 9–16 on DRV2) |

## Mechanical notes

- Nominal seats are sized for 5 mm LED bodies (`led_body_d = 5`), with a flange counterbore and tilt toward the sample. Purchased h13/h14 D4 and h15 C1 parts are **3 mm packages**; verify adapters, flange retention and lens recess. The nominal R3 keeper exit (4.2 mm) is larger than the D4 flange (about 3.75 mm), so a standard keeper alone does not positively locate/retain that flange. This is a CAD/package comparison, not an as-built measurement.
- h12 is a narrow 20°-full-angle source; h13/h14 are very wide-angle D4 parts (PDF 120° versus catalog 240°, convention unresolved). Both aim and obstruction of broad emission by a recess can matter; do not model every SWIR LED as a narrow 5 mm source.
- Through-hole metal-can parts (TO-46/TO-39) don't fit the 5 mm seats and need adapted seats.

