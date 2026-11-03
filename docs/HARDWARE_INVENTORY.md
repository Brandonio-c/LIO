# LIO V3 — Hardware Inventory

Status as of 2 November 2026. "In build" means it is on the breadboard prototype.

## Electronics

| Item | Qty held | Used in build | Status / notes |
|---|---|---|---|
| Arduino Nano | 1 | 1 | Controller |
| SN74HC595N shift register (DIP-16) | 25 | 2 | U1, U2 |
| 2N7000 MOSFET (TO-92) | 100 | 16 | Q1–Q16 |
| TL072CP dual op-amp (DIP-8) | 20 | 1 | U5, InGaAs amplifier |
| LD06AJSA constant-current LED driver module (2.8–6 V, 30–1500 mA) | 10 | 2 | DRV1 (RAIL A), DRV2 (RAIL B) |
| ADS1115 16-bit I²C ADC breakout | 1 | 1 | U3 |
| OPT101 module (CJMCU-101) | 1 | 1 | U4, detector 1 |
| MTPD1346D-100 InGaAs photodiode (TO-46) | 1 | 1 | D1, detector 2 |
| Resistor assortment (¼ W) | many | 220 Ω ×16, 10 kΩ ×19, 1 MΩ ×1 | |
| Capacitor assortment (10 pF–100 nF) | many | 100 nF ×6, 10 pF ×1 | No values above 100 nF on hand |
| ULN2003 boards + 28BYJ-48 steppers | 2 + 2 | 2 + 2 | Existing chamber drive |
| 5 V USB power banks | 2 | 2 | Must be separate units (series → ±5 V) |
| Breadboards (2× 830, 2× 400) + jumper wires | kit | yes | |
| 22 AWG solid wire, 6 colours | kit | yes | |
| ALAMSCN SMD-to-DIP adapter assortment | 51 | — | SMD route abandoned |
| TSOP38238 38 kHz IR receiver | 1 | — | Not analytical. Candidate lid interlock or beam-break |
| ITR20001/T reflective sensors | 5 | — | Not analytical. Candidates for drive-base or reflectance uses |

## Emitters

| Wavelength | Package | In hole | Notes |
|---|---|---|---|
| 395 nm UV | 5 mm (Chanzon) | 1 | |
| ≈405 nm violet/purple | 5 mm | 2 | |
| Blue, green, yellow, orange, red | 5 mm | 3–7 | |
| 850 nm IR | 5 mm (Chanzon, 100-pack) | 8 | 1.4–1.6 V, 20 mA |
| 940 nm IR | 5 mm (Chanzon, 100-pack) | 9 | 1.2–1.5 V, 20 mA |
| 1450, 1550, 1650, 1760, 1850 nm | through-hole | 12–16 | Confirm current ratings from datasheets |
| White, pink | 5 mm | — | Broadband; optional for holes 10–11 (on RAIL A) |
| 300 nm UVB, QLUV07EYGE (3535 SMD, 6.5 V / 30 mA) | SMD | — | Removed. Needs boost and interlock |
| 400, 900, 1000, 1100, 1200, 1300 nm | SMD | — | Removed (hand-mounting failed) |

## Tools

| Tool | Notes |
|---|---|
| Soldering iron, solder, fine tweezers | On hand |
| Defabee 8858 hot-air rework station | For SMD reflow (300–330 °C leaded, 350–380 °C lead-free, low airflow) |
| Mini heat-shrink gun + heat-shrink kit | Tubing only. It can't reflow solder (392 °F max) |
| Solder-seal butt connectors (520 pcs) | Wire splicing |
| FNIRSI 2C53T oscilloscope / multimeter / signal generator | Diode test, continuity, voltages, current setting |

## Returned or not held

| Item | Reason |
|---|---|
| MCP6002 op-amps (SMD) | Returned. TL072 used instead, on ±5 V |
| AO3400A MOSFETs (SMD) | Never actually held. 2N7000 used instead |

## Possible future purchases

| Item | For |
|---|---|
| Through-hole 1200 / 1300 nm emitters (e.g. Marktech MTE1200N5, MTE1300N5) | Holes 10–11 |
| Extended-InGaAs (2.6 µm) photodiode | Reading hole 16 (1850 nm) and a cleaner 1760 nm |
| MT3608 boost converter + TO-39 300 nm emitter + lid microswitch | A future UVC channel with a hardware interlock |
| Mechanical limit switches | Chamber end-of-travel protection |
| 100 nF–10 µF bulk capacitors, 16-pin DIP sockets | Nice to have |
