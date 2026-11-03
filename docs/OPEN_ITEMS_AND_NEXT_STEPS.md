# LIO V3 — Open Items and Next Steps

Ordered roughly by priority. Tick each item off as it's completed.

## A. Before trusting any readings

- [ ] **Re-wire the InGaAs photodiode** if it was built to the earlier instructions: cathode → TL072 pin 2, anode → GND. Add the 10 kΩ resistor between TL072 pin 1 and ADS1115 A0.
- [ ] **Continuity-test the InGaAs case lead.** Ground it only if it's isolated or tied to the anode.
- [ ] **Confirm −5 V stays up** for at least 5 minutes. If bank B sleeps, use a low-current mode or a 220 Ω dummy load.
- [ ] **Check that the Nano's 5V pin isn't connected** to the +5V rail.
- [ ] **Flash `lio_firmware.ino`** (with the corrected order: select the MOSFET, then raise CE) and run TEST_MODE 1 → 5.
- [ ] **Set the driver currents:** DRV1 at its minimum (≈30 mA); DRV2 at ≈45 mA or the lowest SWIR LED rating if that's lower. Measure with the meter in series.
- [ ] **Read the SWIR LED datasheets** (holes 12–16) for maximum current and forward voltage.
- [ ] **Confirm LD06AJSA CE polarity:** high = on.

## B. Mechanical

- [ ] Edit `LIO_V3_master.scad` `optical_deck()`: change `hole(24, -eps, deck_t+eps)` to about Ø34 (the plate's console output gives the exact minimum). Reprint the deck.
- [ ] Measure the TO-46 can (diameter, tab or flat) and the photodiode offset on the CJMCU-101 board. Set the plate parameters and print `LIO_V3_dual_detector_plate_v01.scad`.
- [ ] Optionally fold the plate into the master as the new `detector_mount()` and make the deck window a named parameter.
- [ ] Check the light-tightness of the chamber and head cover. Dark readings should be small and stable.

## C. Measurement quality

- [ ] Tune the ADS1115 gain (GAIN_ONE by default) and `SETTLE_MS` (8 ms) from repeated sweeps.
- [ ] If the InGaAs output saturates with the SWIR LEDs, change Rf from 1 MΩ to 100 kΩ.
- [ ] Record a reference sweep and normalise later sweeps to it.
- [ ] Cross-calibrate OPT101 and InGaAs using holes 8 and 9.

## D. Firmware and software integration

- [x] Reconcile the motor control with the new pin map (D2–D9 motors; A0–A3 and D10 optics; A4/A5 I²C): firmware v2 drives the motors on D2–D9 and accepts `software/control/lio_motor_control.py`'s jog commands, bounded (`docs/PROTOCOL.md` §7). To confirm on hardware: test T09.
- [x] Combine motor control and optical sweeps in one firmware. De-energise the coils after each move, and never sweep while the motors are moving (firmware v2, `docs/PROTOCOL.md` §6).
- [ ] Add a "dark only" mode and a timestamped file name to the logger.

## E. Hardware upgrades (later)

- [ ] Populate holes 10–11 with through-hole 1200 / 1300 nm emitters (Marktech MTE1200N5 / MTE1300N5).
- [ ] Add an extended-InGaAs (2.6 µm) detector for 1760 / 1850 nm.
- [ ] Optional 300 nm UVC channel: TO-39 part, MT3608 boost (≈9 V), and a lid microswitch in series with its drive.
- [ ] Mechanical limit switches at the top and bottom of travel.
- [ ] Once the breadboard is proven, move to perfboard or a PCB. Mount the drivers and the TL072 close to the head.
- [ ] Consider per-LED series resistors on RAIL A if visible LEDs ever need continuous illumination (30 mA exceeds their rating).
