# Changelog

## 2026-11-03: Dashboard

### Added
- `lio dashboard`: a local web page to run the tests and see the instrument's state (`docs/TESTING.md` §3):
  - connect to the Nano or the simulator, run any subsystem or the whole system, answer operator questions in the page, stop safely
  - a digital twin (Nano, shift registers, rails, the 16 holes, detectors, ADC, motors, safety) coloured by result, with the evidence behind each part, and Measure / Flash on each hole
  - the overall verdict over the latest result of every test, with its coverage; earlier runs and their reports
- `dashboard:` settings in `lio_hw.yaml` (local address, port, poll rate, flash time).
- `LIODevice.request_cancel()`: a stop request ends the running test at its next command or wait (the dashboard's Stop). The command line is unchanged.

## 2026-11-03: System test suite and firmware v2 (LIO-SW-TEST-001, M1–M5)

### Added
- `software/firmware/lio_firmware/`: firmware v2, a command-driven protocol (`docs/PROTOCOL.md`) with the safety rules in firmware:
  - power-up dark state and one channel at a time
  - per-rail on-time watchdog and a comms-loss failsafe
  - armed, bounded motor moves with the coils released afterwards
  - bounded legacy jogs for `lio_motor_control.py`
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

- `software/control/lio_control.py` renamed `lio_motor_control.py` (contents unchanged).
- The root README's repository-structure section now matches the actual tree.

### Removed (kept in git)
- The TEST_MODE firmware and the original logger: at tag `fw-testmode-v1`.
- `software/firmware/legacy/` (TEST_MODE firmware copy and the old AccelStepper motor sketch, do-not-flash) and `software/logger/legacy/`: at tag `software-legacy-v1`.
- CI's legacy-firmware build step.
- A stray `CAD/creality_print_files/.DS_Store`.

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
