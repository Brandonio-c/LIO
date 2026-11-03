# LIO V3 — Project Log (optics and electronics)

A chronological record of the design work on the LIO V3 optical head: what was decided, what was tried, what failed, and why. Written 2 November 2026. Phases are listed in the order the work happened.

---

## Phase 1: Top LED circuit architecture

- **Goal:** drive the LEDs in the top optical deck from the Arduino Nano that already runs the chamber motors.
- **Decision:** a 16-channel, one-LED-at-a-time architecture. Each LED gets its own current control and its own low-side switch. Only one channel is on at a time, because the detector must see one illumination condition at a time.
- **Constraint found:** the Nano doesn't have 16 free pins. D2–D9 drive the two stepper motors (D2–D5 motor 1, D6–D9 motor 2). D10–D12 were motion buttons at the time (UP/DOWN/STOP); those buttons were later removed and D10–D12 freed.
- **Solution:** two daisy-chained 74HC595 shift registers give 16 outputs from 3 Nano pins.
- **Rule set early and kept:** one current-setting element per LED, never a shared resistor across parallel LEDs.

## Phase 2: The 16-hole optical deck

- The V3 CAD (`LIO_V3_master.scad`, `optical_deck()`) places 16 LED seats on a 35 mm radius ring, 22.5° apart, sized for 5 mm LED bodies. Each LED is tilted (`led_axis()`, `led_tilt` < 20°) to aim at the sample plane, and the LEDs are retained by a shared `led_keeper`. A central opening serves the detector.
- **Numbering convention:** hole 1 at 12 o'clock, then clockwise to hole 16. Channel n drives hole n.

## Phase 3: Wavelength plan, version 1

- **Inventory at the time:**
  - emitters at 300, 400, 890, 1020, 1200, 1300, 1450, 1550, 1650, 1760 and 1850 nm
  - visible LEDs: white, yellow, red, purple, blue, orange, green, pink
- **Plan v1:** a monotonic sweep. Holes 1–16 were 300, 400, blue, green, yellow, orange, red, 890, 1020, 1200, 1300, 1450, 1550, 1650, 1760, 1850 nm. White and pink were dropped as broadband, and purple as redundant with 400 nm.
- This plan was superseded in Phase 8 (archived as `SUPERSEDED_2026-11_16-channel_build_map_v1.md`).

## Phase 4: Detector review

- **Usable analytical detectors:**
  - **OPT101** (CJMCU-101 module): silicon photodiode with a built-in transimpedance amplifier, about 300–1100 nm, analog voltage out.
  - **MTPD1346D-100**: InGaAs PIN photodiode in a TO-46 can, about 800–1750 nm. It needs an external transimpedance amplifier.
- **Not analytical:**
  - **TSOP38238** is a 38 kHz demodulating IR receiver with digital output; it can't measure intensity.
  - **ITR20001/T** are reflective proximity sensors with their own built-in emitter.
- **Other uses identified for those two:**
  - TSOP: remote control input, a beam-break trigger, or an optical lid interlock.
  - ITR: line following, edge detection or wheel encoders on a drive base, or a possible ring-mounted reflectance channel.
- **Chamber motion safety:** mechanical limit switches are recommended for end-of-travel protection. A TSOP beam-break across the gap is an option for crush protection, and an ultrasonic sensor if true approach ranging is needed.
- **"No swapping" requirement:** both detectors stay live permanently. The firmware chooses which ADC channel to read; nothing is power-switched.

## Phase 5: Dual-detector plate (CAD)

- **Requirement:** replace the single-sensor `detector_mount()` with a plate that holds the OPT101 board and the InGaAs can together.
- **Iterations:**
  - **v1:** a tall plug.
  - **v2:** a flat plate with a board divot, chip pocket and InGaAs hole.
  - **v3:** thinned, with the chip pocket cut through so it doubles as the aperture, and a keyed TO-46 tab notch.
  - **v4:** OPT101 pocket sized to the datasheet maximum (9.91 × 6.99 mm DIP-8 body).
  - **v5:** board outline built from measurements; InGaAs hole auto-placed beyond the board edge.
  - **v6:** measured board, 1.125 × 0.75 in (28.575 × 19.05 mm).
  - **v7:** geometry taken from the master: plate 44 × 36 × 3 mm, mount holes at ±18 / ±14 mm, Ø3.4, matching the deck's hex-nut pockets.
  - **v8–v10:** the plate auto-grows so every hole keeps at least 5 mm of material around it.
- **Key finding:** the deck's central window (`hole(24, …)` in `optical_deck()`) is smaller than the 28.6 mm board, so no plate design can give the InGaAs a view through Ø24. The window must be enlarged to about Ø34; the `.scad` file reports the exact minimum.
- **Current file:** `CAD/V3/LIO_V3_dual_detector_plate_v01.scad`.

## Phase 6: The 300 nm UV emitter

- The 300 nm part was the **Quelighting QLUV07EYGE**: a 300–315 nm UVB emitter in a 3535 ceramic SMD package, rated 6.5 V at 30 mA, with a quartz window.
- **Requirements identified:** reflow onto a carrier board; a boost converter of about 9 V (MT3608) because it won't light on 5 V; and a lid interlock that cuts its drive in hardware, because UVB is an eye and skin hazard.
- **Outcome:** removed along with the other SMD parts (Phase 8). Deferred indefinitely.

## Phase 7: Tools and parts purchasing

- **Bought:** SN74HC595N ×25 (DIP-16); an ALAMSCN SMD-to-DIP adapter assortment; a heat-shrink kit with mini heat gun; solder-seal butt connectors; 22 AWG solid wire; a breadboard kit; a Defabee 8858 hot-air rework station.
- **Added later:** TL072CP ×20 (DIP-8), 2N7000 ×100 (TO-92), and Chanzon 5 mm 850 nm, 940 nm and 395 nm LED packs.
- **Already on hand:** LD06AJSA LED driver modules ×10; ADS1115 16-bit ADC breakout; a resistor assortment; capacitors from 10 pF to 100 nF; a soldering iron, solder and tweezers; a FNIRSI 2C53T oscilloscope/multimeter.
- **Returned or never held:** the SMD MCP6002 op-amps were returned, and the SMD AO3400A MOSFETs were not actually on hand.
- **Lesson:** the heat-shrink gun (392 °F) can't reflow solder; a hot-air station or iron is needed.

## Phase 8: SMD LEDs abandoned; through-hole only

- The SMD emitters at 300, 400, 900, 1000, 1100, 1200 and 1300 nm proved very hard to mount on adapter boards by hand. Only one of the three tested worked after mounting.
- **Decision:** remove every SMD emitter and use only through-hole parts.
- **Final ring:**
  - 1 = 395 nm UV
  - 2 = violet/purple, about 405 nm
  - 3–7 = blue, green, yellow, orange, red (unchanged)
  - 8 = 850 nm, 9 = 940 nm
  - 10–11 = reserved (the 1200 and 1300 nm positions)
  - 12–16 = through-hole 1450, 1550, 1650, 1760 and 1850 nm
- **Consequence:** the SWIR channels (holes 12–16) still need the InGaAs detector, and therefore its amplifier.

## Phase 9: Sourcing through-hole replacements

- Researched leaded parts for the removed wavelengths. These are mostly Marktech 5 mm "N5" radial emitters on DigiKey, at about $16–20 each. Cheap Chanzon packs cover 850 and 940 nm. See `LED_SOURCING.md`.
- A 300 nm emitter only exists as a metal-can (TO-39) part, because epoxy absorbs UVC. Those are expensive and need their own hole.

## Phase 10: Electronics design

- **Switches:** the SMD AO3400A plan was replaced by **2N7000** TO-92 MOSFETs, one per channel, each with a 220 Ω gate resistor and a 10 kΩ pull-down.
- **Current control:** started with a resistor per LED. Moved to the **LD06AJSA** constant-current modules in two groups:
  - DRV1 → RAIL A for holes 1–9
  - DRV2 → RAIL B for holes 10–16
  - each driver enabled through its CE pin from the Nano (A3 and D10), with a 10 kΩ pull-down
- **Driver minimum current:** found to be 30 mA.
- **InGaAs amplifier:** the MCP6002 (rail-to-rail, SMD) was returned. The **TL072** needs a negative rail, so two separate 5 V power banks are stacked in series to give ±5 V. Two ports on one bank measured 2 Ω between grounds, so they share a ground and can't be stacked.
- **ADC:** the **ADS1115** reads both detectors over I²C (A4/A5). This keeps the op-amp's possible negative output away from the Nano's pins and adds 16-bit resolution.
- **Final Nano pin map:**
  - A0 = DATA, A1 = CLOCK, A2 = LATCH
  - A3 = CE1, D10 = CE2
  - A4 = SDA, A5 = SCL
  - D2–D9 = motors
  - D11, D12, A6, A7 = spare

## Phase 11: Schematics and the consolidation review

- **Schematic v1:** sectioned, with net labels (archived).
- **Schematic v2:** every signal wire drawn, crossings marked with hops, and every part included, motors and decoupling capacitors among them (`electronics/LIO_full_schematic.svg`).
- **Corrections found during consolidation** (see `DESIGN_DECISIONS.md`, D-11 to D-14):
  - The InGaAs photodiode orientation was reversed: cathode now goes to TL072 pin 2 and anode to GND, so the output goes positive.
  - A 10 kΩ protection resistor was added in front of ADS1115 A0.
  - The InGaAs case lead must be tested before it is grounded.
  - DRV1's minimum current is 30 mA.
  - The Nano runs from USB only, with its 5V pin not connected.
  - In firmware, the MOSFET is selected before CE is raised.

## Phase 12: Documentation and software

- **Technical document** LIO-ELEC-001 Rev A, 32 pages, in DOCX and PDF.
- **Data files:** BOM, net list, channel map and Nano pin map as CSV.
- **Firmware** `lio_firmware.ino` with five test modes: I²C scan, live detectors, channel walk, single LED, and sweep with dark subtraction.
- **Logger** `lio_logger.py`: writes a CSV and a plot of dark-subtracted volts.
- **Breadboard prototype** built (photo: `images/build_photos/2026-11-02_breadboard_prototype.png`).
