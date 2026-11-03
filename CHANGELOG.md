# Changelog

## 2026-11-02: LIO V3 optical head electronics, Rev A

### Added
- `electronics/`:
  - full schematic (`LIO_full_schematic.svg` / `.html`)
  - technical document LIO-ELEC-001 Rev A (`docs/`, PDF and DOCX)
  - BOM, net list, channel map and Nano pin map CSVs (`data/`)
  - wiring checklist
  - schematic and document generator sources (`source/`)
- `software/firmware/lio_firmware/lio_firmware.ino`: test and sweep firmware (5 modes, dark subtraction)
- `software/logger/lio_logger.py`: serial logger with CSV and plot
- `CAD/V3/LIO_V3_dual_detector_plate_v01.scad`: OPT101 + InGaAs detector plate for the optical deck
- `docs/`: project log, design decisions, hardware inventory, optical channel map, LED sourcing, open items
- `images/lio_v3_electronics_schematic.png`, `images/build_photos/2026-11-02_breadboard_prototype.png`
- `CAD/V2`, `CAD/V3` copied from the project Drive folder (if selected during install)

### Changed (relative to earlier build instructions)
- InGaAs photodiode orientation: cathode → TL072 pin 2, anode → GND
- 10 kΩ protection resistor added before ADS1115 A0
- DRV1 current set to the module minimum (≈30 mA)
- Nano powered from USB only (5V pin not connected)
- Firmware selects the MOSFET before enabling CE; adds a dark reading per channel
- Holes 10–11 reserved (SMD 1200 / 1300 nm emitters removed)

### Requires
- Optical deck central window enlarged from Ø24 to ≈Ø34 (reprint)
