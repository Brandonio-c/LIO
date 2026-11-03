# Changelog

## 2026-11-03: System test suite and firmware v2 (LIO-SW-TEST-001, M1–M5)

### Added
- `software/firmware/lio_firmware/`: firmware v2, a command-driven protocol (`docs/PROTOCOL.md`) with the safety rules in firmware:
  - power-up dark state and one channel at a time
  - per-rail on-time watchdog and a comms-loss failsafe
  - armed, bounded motor moves with the coils released afterwards
  - bounded legacy jogs for `lio_control.py`
  - flash 72 %, SRAM 51 % of the ATmega328P
- `software/host/`, the `lio` package and command:
  - device API, protocol parser, a simulator with 16 injectable faults
  - the test catalogue T01–T11 (automatic, interactive and motion tests)
  - HTML/Markdown reports with plots, baselines, and the `lio` CLI
- `software/config/lio_hw.yaml`: the hardware description and all test thresholds (provisional until calibrated)
- `docs/TESTING.md`: how to test, the catalogue, and the first-hardware-session checklist
- `docs/proposals/LIO-ELEC-001_firmware_v2_update.md`: proposed text for LIO-ELEC-001 §13–§15 and the appendices (not applied)
- CI (`.github/workflows/ci.yml`):
  - lint, strict typing
  - unit tests, simulator system tests and the fault-injection matrix
  - firmware compile with an SRAM gate

### Changed
- `software/logger/lio_logger.py`: rewritten on the host package for firmware v2. It keeps the same command line, the same `lio_sweep.csv` (byte-compatible) and `lio_sweep.png`.

### Preserved
- The TEST_MODE firmware: `software/firmware/legacy/lio_firmware_testmode/`, tag `fw-testmode-v1`.
- The old motor sketch: `software/firmware/legacy/lio_motor_control/`, marked do-not-flash.
- The original logger: `software/logger/legacy/`.

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
