# LIO V3 — Design Decisions

Each entry records a decision, the reason for it, and its consequences. Entries marked **Superseded** have been replaced by a later entry.

| ID | Decision | Status |
|---|---|---|
| D-01 | One LED lit at a time, each on its own switch | Active |
| D-02 | 16 channels from 2× 74HC595 | Active |
| D-03 | Monotonic wavelength order around the ring | Active |
| D-04 | Two detectors permanently live (OPT101 + InGaAs); no swapping | Active |
| D-05 | TSOP38238 and ITR20001 excluded from measurement | Active |
| D-06 | Through-hole emitters only (SMD abandoned) | Active |
| D-07 | 2N7000 low-side switch per channel | Active (replaced AO3400A) |
| D-08 | Two LD06AJSA constant-current groups with CE enable | Active (replaced per-LED resistors) |
| D-09 | TL072 on ±5 V from two stacked power banks | Active (replaced MCP6002) |
| D-10 | ADS1115 reads both detectors over I²C | Active |
| D-11 | InGaAs cathode to summing node, anode to GND | Active (corrects earlier wiring) |
| D-12 | 10 kΩ series protection in front of ADS1115 A0 | Active |
| D-13 | Nano powered from USB only; 5V pin not connected | Active |
| D-14 | Firmware: select MOSFET, then enable CE; dark reading every channel | Active |
| D-15 | Deck central window enlarged from Ø24 to about Ø34 | Pending reprint |
| D-16 | 300 nm UVC channel deferred | Deferred |

---

**D-01: One LED at a time.** The detector reports total light, so simultaneous wavelengths can't be separated. On top of that, two LEDs on one constant-current rail split the current unevenly. *Consequence:* sweeps are sequential, taking about 25 ms per channel.

**D-02: 2× 74HC595.** Three Nano pins (A0–A2) give 16 outputs, which leaves the motor pins D2–D9 untouched. Q0 is pin 15; Q1–Q7 are pins 1–7.

**D-03: Monotonic order.** Hole 1 holds the shortest wavelength and the order increases clockwise. This keeps wiring, firmware order and troubleshooting simple. Electrically, position doesn't matter.

**D-04: Both detectors live.** The OPT101 sits on the optical axis and the InGaAs just beside it on a new plate. The firmware picks the ADC channel. Holes 8 and 9 (850, 940 nm) are read by both detectors and serve as cross-calibration points.

**D-05: TSOP/ITR excluded.** The TSOP38238 only demodulates a 38 kHz carrier and outputs a digital level. The ITR20001 contains its own emitter. Neither can make an intensity measurement. They remain candidates for an interlock, a beam-break or a reflectance channel.

**D-06: Through-hole only.** Hand reflow of tiny SMD emitters was unreliable: one of three survived. Leaded parts are hand-solderable and fit the 5 mm seats. *Consequence:* the removed wavelengths (300, 400, 900, 1000, 1100, 1200, 1300 nm) were replaced or reserved, and some through-hole SWIR parts cost about $16–20 each.

**D-07: 2N7000.** A TO-92 package that fits a breadboard, with V_GS(th) of 0.8–3 V, R_DS(on) of 5.3 Ω max at 5 V, and 200 mA rating. At 45 mA it drops at most 0.24 V. It replaced the AO3400A, which was SMD and not actually on hand.

**D-08: Two LD06AJSA groups.** Constant current holds the LED current steady as the forward voltage drifts with temperature, which matters most for the weak SWIR parts. The visible and SWIR LEDs need different currents, so there are two groups:
- RAIL A (holes 1–9) at the driver's 30 mA minimum
- RAIL B (holes 10–16) at about 45 mA

The CE pins give a group on/off control and a guaranteed-dark state for baseline readings. *Consequence:* 30 mA exceeds the 20 mA rating of the 5 mm LEDs, which is acceptable only at low duty cycle.

**D-09: TL072 on ±5 V.** The JFET input suits a photodiode amplifier, but the part needs a negative rail. Two physically separate banks in series give ±5 V. Two ports on one bank share a ground (measured 2 Ω), so they can't be used. *Risk:* bank B (about 3 mA load) may auto-sleep.

**D-10: ADS1115.** 16-bit resolution (125 µV per count at ±4.096 V), and both detectors on two I²C pins. It also frees Nano A0–A3 for the shift registers and driver enables.

**D-11: InGaAs orientation.** With the cathode on pin 2 and the anode on GND, Vout = +I × Rf. The earlier orientation drove the output negative, to about −3.5 V, which exceeds the ADS1115 absolute limit of GND − 0.3 V. Zero bias also minimises dark current.

**D-12: ADC protection resistor.** 10 kΩ limits fault current to under 0.5 mA if the op-amp swings negative, for example at power-up or if −5 V is lost.

**D-13: Nano on USB.** The logger needs USB anyway. Tying the Nano's 5V pin to bank A as well would back-feed between the USB supply and the bank.

**D-14: Switching order and dark subtraction.** Selecting the MOSFET before enabling CE stops the driver's charged output capacitance dumping into an LED at switch-on. A dark reading before each lit reading removes ambient light and offsets.

**D-15: Deck window.** A 28.6 mm board can't leave room for a second detector inside Ø24. Enlarging the window to about Ø34 doesn't affect the LED ring (r = 35 mm) or the mount holes.

**D-16: 300 nm deferred.** The UVC part needs about 9 V, a metal-can or carrier mount, and a hardware interlock. This is revisited only once everything else works.
