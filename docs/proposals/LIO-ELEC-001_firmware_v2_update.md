# Proposed update to LIO-ELEC-001 for firmware v2 (not applied)

**Status: proposal for the user's approval (M0 decision 12).** No electronics file has been edited. If approved, the text below replaces the corresponding parts of `electronics/source/build_doc.js` (§13.1, §13.2, §14, §15 rows, Appendix A, Appendix B), and the DOCX/PDF are regenerated with `node build_doc.js`.

Why: §13–§14 and Appendices A–B describe the TEST_MODE firmware (five compile-time modes). That firmware has been replaced by the command-driven firmware v2 (`docs/PROTOCOL.md`); the old sketch is preserved in `software/firmware/legacy/` (tag `fw-testmode-v1`).

---

## 13  Bring-up and calibration

### 13.1  Firmware and test suite

The Nano runs firmware v2 (Appendix A). It accepts one-line text commands over USB at 115200 baud and answers each one. The host program `lio` (`software/host`) sends them, and its test suite replaces the old test modes:

| Old mode | Now | Expected result | If it fails |
|---|---|---|---|
| 1 I²C scan | `lio selftest --modules adc` (T03.1) | ADS1115 at 0x48 | Check SDA/SCL (A4/A5), ADS1115 power, ADDR to GND |
| 2 Live readings | `lio shell`, then `ADC READ 1 16` | Both channels change with light | OPT101: 1M jumper, −V/COM grounds. InGaAs: orientation, −5 V present |
| 3 Walk test | `lio selftest --modules T04.4 --interactive` | Each LED lights in turn for 0.4 s; the operator confirms | See §15 |
| 4 Hole 8 pulse | `lio selftest --modules T05.6 --interactive` | 1 s flashes (RAIL A), 2 s (RAIL B) while the current is read | Driver, rail or CH8 wiring |
| 5 Sweep | `lio sweep --csv lio_sweep.csv --plot lio_sweep.png` | 16 records; CSV in the old logger's format | — |

`lio selftest` runs the whole catalogue (`docs/TESTING.md`) and writes an HTML report with a verdict: FUNCTIONAL, DEGRADED or NOT FUNCTIONAL.

### 13.2  Calibration steps

1. **Driver currents.** Set DRV1 to its minimum and DRV2 to the target from §6.2, using T05.6 with the meter in series.
2. **ADC gain.** If T05.2 reports saturation, use `ADC CFG GAIN 2/3`. If the largest net signals are under 8000 counts, gain 2 doubles the resolution. Record the choice in `lio_hw.yaml` (`adc.gain`).
3. **TIA gain.** If T06.2 reports InGaAs saturation, fit Rf = 100 kΩ (§7.2).
4. **Settle time.** T07.2 recommends a settle time from the measured step response. If it exceeds 8 ms, raise `SETTLE_MS_DEFAULT` in the firmware and `firmware.limits.settle_ms` in `lio_hw.yaml` together.
5. **Ambient light.** T03.5 (drift) and T06.4 (lid open / closed) quantify light-tightness.
6. **Reference.** `lio selftest --save-baseline` stores the per-channel response of the empty, closed chamber. Later runs compare against it (`--baseline latest`), and sweeps can be divided by it to remove LED-to-LED brightness differences.

## 14  Firmware and software

### 14.1  Measurement sequence (`MEAS`, `SWEEP`)

Unchanged in principle; the firmware now also enforces the safety rules:

1. Turn both drivers off and clear the registers; wait `settle_ms`; read A0 and A1 (mean of n) as the dark values.
2. Shift in the pattern with only this hole's bit set and latch it (selects the MOSFET).
3. Raise the CE line for this hole's rail. The rail's watchdog starts: RAIL A 2 s, RAIL B 5 s by default (hard caps 5 s / 10 s).
4. Wait `settle_ms` (8 ms default).
5. Read A0 (InGaAs) and A1 (OPT101) as the lit values.
6. Drop CE and clear the registers. Report `ch dark0 dark1 lit0 lit1 t_on_ms`.

A measurement whose estimated on-time would exceed the watchdog is refused. Only one channel can be lit at a time.

### 14.2  Safety behaviour

- **Power-up and RESET:** CE low before the registers are cleared; everything dark.
- **Watchdog:** each lit channel turns off at its rail's limit.
- **Comms loss:** 10 s without a command while anything is active turns everything off and disarms the motors.
- **Motors:** a motor move needs `MOTOR ARM` with a token from `INFO` (valid for 60 s). Moves are bounded to 2048 half-steps, and the coils are released afterwards. No LED may be on during a move, and no measurement is allowed while a motor moves.
- **Legacy jogs:** `lio_control.py` keeps working (`U`, `D`, `LU`, …), each jog bounded to 2048 half-steps (`docs/PROTOCOL.md` §7).

### 14.3  Libraries and tools

Arduino: **Adafruit ADS1X15** and **Adafruit BusIO** (Library Manager), or `arduino-cli` as in `docs/TESTING.md` §7.2. Python 3.10+: `pip install -e software/host`. The logger (`software/logger/lio_logger.py`, Appendix B) keeps its command line and outputs, `lio_sweep.csv` and `lio_sweep.png`. Close the Arduino Serial Monitor first: only one program can hold the port.

## 15  Troubleshooting: rows to change

| Symptom | Likely cause | Check / fix |
|---|---|---|
| T03.1 "ADS1115 not found" | I²C wiring or power | A4 = SDA, A5 = SCL; VDD and GND; ADDR to GND |
| No LED lights (T05.1, T05.2) | Drivers not enabled or registers inactive | CE wiring to A3/D10; driver V1 and G; rail connected; /OE grounded; /SRCLR high |
| T05.3 "U2 receives no data" | Chain wiring | U1 pin 9 → U2 pin 14 |
| T06.2 polarity gate fails | InGaAs reversed | Swap the photodiode leads at the TIA input |
| T06.2 dark erratic | −5 V missing (bank B asleep) | Low-current mode or a 220 Ω dummy load (§3.2) |
| Readings jumpy (T05.5, T08.2) | Settling, rail noise, light leaks | T07.2 settle recommendation; decoupling; motors stationary (T09.4); close the chamber |

## Appendix A  Arduino firmware

Files: `software/firmware/lio_firmware/` (`lio_firmware.ino`, `config.h`, `protocol.*`, `optics.*`, `adc.*`, `motors.*`, `safety.*`). The full command reference is `docs/PROTOCOL.md`. Proposal: print `config.h` and the command table from PROTOCOL.md §5 here, instead of the full source (now about 1400 lines in seven files).

## Appendix B  Python logger

File: `software/logger/lio_logger.py`. Usage: `python lio_logger.py COM3` (Windows) or `python3 lio_logger.py /dev/cu.usbserial-XXXX` (macOS). Requires firmware v2 and `pip install -e software/host`. The same output comes from `lio sweep --csv lio_sweep.csv --plot lio_sweep.png`.
