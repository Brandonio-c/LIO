# Handoff: LIO V3: no LED ever lights; Nano A0–A5 will not drive high

**Date:** 2026-11-10
**From:** the test-suite agent working at the bench with the operator.
**To:** a research agent.

**What you are asked to do:**
- Work out the most likely root cause of the faults below.
- Say what single test would confirm it.
- Recommend the fix.

Everything below was measured on the real hardware today unless it is marked otherwise. Readings marked *(firmware-reported)* are the firmware's own record of what it commanded. They are not read back from the pins.

---

## 1. The system in brief

**Purpose.** LIO V3 is an optical test head. An Arduino Nano selects one of 16 LEDs, the LED shines into a chamber, and two detectors read the light through an ADS1115 ADC. Two stepper motors lift the chamber.

**Controller: Arduino Nano.**
- Chip: ATmega328P at 5 V.
- Firmware: custom, currently **2.2.2**. The upload worked only with `arduino:avr:nano:cpu=atmega328` (new bootloader). The `atmega328old` setting failed with "not in sync resp=0x8c".
- Powered **only from the laptop's USB**. The Nano's 5V pin is **not** connected to the +5 V bus. The Nano's GND is tied to system GND.

**Power: two USB wall chargers in series.**
- Charger 1 (+) feeds the **+5 V bus**, measured at 5.06–5.12 V. This bus powers the shift registers, the LED drivers, the ADS1115, the OPT101 and TL072 pin 8.
- Charger 1 (−) and charger 2 (+) are joined at **GND**.
- Charger 2 (−) gives **−4.93 V** on TL072 pin 4 only.
- These chargers replaced two USB power banks on about 2026-11-06.
- During the power-bank period, charger/bank 2 was briefly wired reversed, which put about +4.95 V on TL072 pin 4. This was corrected.

**Intended Nano pin map** (from `electronics/data/nano_pinmap.csv` and `software/firmware/lio_firmware/config.h`):

| Nano pin | AVR pin | Signal | Goes to |
|---|---|---|---|
| A0 | PC0 | DATA | U1 pin 14 (SER) |
| A1 | PC1 | CLOCK | U1 pin 11 and U2 pin 11 (SRCLK) |
| A2 | PC2 | LATCH | U1 pin 12 and U2 pin 12 (RCLK) |
| A3 | PC3 | CE1 | DRV1 CE, with a 10 kΩ pull-down. Moved to A4 in firmware 2.2.2, see §4 |
| A4 / A5 | PC4 / PC5 | unused | Originally the hardware I²C bus to the ADS1115, abandoned 2026-11-04 (see §3) |
| A6 / A7 | — | analogue input only | `analogRead` seeds a random token (`safety.cpp`) |
| D2–D5 | PD2–PD5 | motor 1 | ULN2003 #1 (works) |
| D6–D9 | PD6, PD7, PB0, PB1 | motor 2 | ULN2003 #2 (works) |
| D10 | PB2 | CE2 | DRV2 CE, with a 10 kΩ pull-down (works: drove a CE to 4.1 V today) |
| D11 / D12 | PB3 / PB4 | software I²C SDA / SCL | ADS1115 (works, about 166 kHz) |
| D13 | PB5 | free | on-board LED |

**LED chain** (schematic: `electronics/LIO_full_schematic.svg`; checklist: `electronics/WIRING_CHECKLIST.md`):
- Two 74HC595 shift registers (SN74HC595N, DIP-16) in a daisy chain. U1 pin 9 (Q7′) feeds U2 pin 14.
- Each output drives one channel: output → 220 Ω → gate of a 2N7000 transistor. The gate has a 10 kΩ pull-down, the source goes to GND, and the drain goes to the LED's cathode.
- The LED anodes go to RAIL A (holes 1–9) or RAIL B (holes 10–16).
- Each rail is fed by an LD06AJSA constant-current module (2.8–6 V input, 30–1500 mA, pins V1 / CE / G / LED).
  - DRV1 runs RAIL A at about 30 mA and is enabled by CE1.
  - DRV2 runs RAIL B at about 45 mA and is enabled by CE2.
- An LED lights only when **both** of these are true:
  - its 595 output is latched high;
  - its rail's CE is high.

**Firmware behaviour that matters** (`software/firmware/lio_firmware/optics.cpp`):
- `optics_init()` runs first in `setup()`:
  - it drives CE1 and CE2 low and makes them outputs;
  - it makes DATA, CLOCK and LATCH outputs;
  - it calls `latch(0)`.
- `latch(bits)` sets LATCH low, then calls `shiftOut(DATA, CLOCK, MSBFIRST, …)` twice (U2 byte first, then U1), then sets **LATCH high and leaves it high**. So at rest, after any latch, **A2 should be held at about 5 V**. DATA is left at the last bit shifted, which is 0 after `latch(0)`.
- `CH <hole> ON [ms]` turns both CEs off, latches the hole's single bit, then raises its rail's CE using `digitalWrite`. A watchdog turns it off again (RAIL A at most 2 s, RAIL B at most 5 s).
- `STATUS` reports `ce1`, `ce2` and `mask` from firmware variables, **not** from reading the pins back.
- The software I²C driver (`softi2c.cpp`) writes ports directly. It resolves the ports with `digitalPinToPort` and `portModeRegister` / `portOutputRegister`, for D11/D12 (PORTB) only. No code anywhere writes `PORTC` or `DDRC` directly.

---

## 2. The symptom

- **No LED in any of the 16 holes has ever been seen to light** on this build.
- The visible LEDs in holes 1–7 (395 nm to 630 nm) were watched by eye during a ring sequence and when one hole was held on.
- Both detectors show no response to any hole. The InGaAs amplifier and ADS1115 A0 read a dark −28 mV and do not change.
- No light reaching the detectors fully explains why the detectors see nothing. There is also a separate OPT101 wiring puzzle, described in §5.

---

## 3. Earlier history that may be the same fault (2026-11-04)

**What happened:**
- The ADS1115 was first wired to the **hardware I²C pins A4 (SDA) and A5 (SCL)**. It was not found on the bus.
- With the I²C wires disconnected and left "in the air", **A4 read 0.15 V and A5 read 0.6 V**.

**Resistance to GND at the Nano pins, measured by the operator:**

| Pin | To GND |
|---|---|
| A4 | 7 kΩ |
| A5 | 9 MΩ |
| A3 | 4 kΩ |
| A2 | 1.6 MΩ |
| A1 | 800 Ω |
| A0 | 194 kΩ |

The operator noted that A0–A3 were wired to the shift registers at the time. **Caveats:** it is unknown whether the circuit was powered during these resistance readings, and the 595 and driver inputs were connected.

**What was done:**
- I²C moved to a software bus on D11/D12 (firmware 2.2.0) and has worked ever since.
- A loose breadboard contact on the ADS1115 module's VDD was also found and reseated. Its supply had been an unsteady 1.4–2 V.
- The A4/A5 failure was put down to that loose contact plus the module's pull-ups dragging the lines low. It was recorded as **"unconfirmed whether A4/A5 are damaged"** (`docs/OPEN_ITEMS_AND_NEXT_STEPS.md`).
- Hardware I²C on A4/A5 was never tried again.

---

## 4. Today's diagnosis, in order (2026-11-10)

**Measurement method:**
- Handheld DMM on DC volts, black probe on system GND.
- Where a reading had to be taken during a short flash, the ADS1115's two **unused inputs A2 and A3** were jumpered to the point under test. A script then sampled them while the firmware lit a hole.
  - ADS settings: gain ±4.096 V, 0.125 mV per count, single-ended, ADS1115 VDD = 5.12 V. **Readings clip at 4.096 V.**
  - Two capture methods:
    - `ADC STREAM`: 40 samples 10 ms apart, LED on for samples 10–29 (about 200 ms);
    - `CH <h> ON 1500`, then `ADC READ` with n = 8 while the LED is on.
- **Reference:** an unconnected ADS input reads about **0.557 V**.

| # | Test | Result | Interpretation |
|---|---|---|---|
| 1 | DMM at rest: DRV1 and DRV2 V1 / G / CE / LED | V1 5.117 V both; G 0 V both; CE 0.085 V / 0.10 V; LED out 0.6 V / −0.036 V | Driver power is good, CE is low at rest |
| 2 | DMM at rest: U1 and U2 pins 16 / 8 / 10 / 13 | 16: 5.12 V / 5.119 V; 8: 0 / 0; **10 (/SRCLR): 0 V / 0 V**; 13 (/OE): 0 / 0 | **Wiring fault:** /SRCLR was tied low, holding both registers cleared. The operator rewired pin 10 to +5 V on both. Afterwards U1 pin 10 read 4.096 V (clipped, so high) through the ADS probe |
| 3 | Firmware `STATUS` during `CH 7 ON 500`, `CH 3 ON 500`, `CH 13 ON 500` *(firmware-reported)* | hole 7: ce1=1, mask 0x0040; hole 3: ce1=1, mask 0x0004; hole 13: ce2=1, mask 0x1000; faults 0x00 | The firmware commands the right thing |
| 4 | ADS probe on the **DRV1 CE pin** during flashes | Hole 7 and hole 3 (CE1 = A3): **stayed 0.087 V**. Hole 13 (CE2 = D10): **rose to 4.1 V** | **Wiring fault:** the CE wires were swapped (A3 went to DRV2, D10 to DRV1). D10 drives a CE input high without trouble |
| 5 | The operator rewired: DRV1 CE goes to a breadboard rail, then to **Nano A3**, with a 10 kΩ pull-down on that rail. DRV2 CE likewise to **D10** | — | — |
| 6 | ADS probe on the DRV1 CE rail, holes 7 and 13 | 0.104 V, no change for either | CE1 does not rise |
| 7 | ADS probe directly on the **Nano A3** strip as well, hole 7 | Nano A3 **0.105 V**, no change; CE rail 0.104 V | The pin itself does not rise. The wire is good (both points are the same node) |
| 8 | **Firmware 2.2.2:** CE1 moved to **A4** (`config.h`, `PIN_CE1 = A4`). Flashed and confirmed `fw=2.2.2`, adc_ok=1, faults 0x00. The operator moved the DRV1 CE wire to A4 | A4 0.100 V and CE rail 0.100 V during flashes of holes 7 and 3 | A4 does not rise either |
| 9 | **Both 10 kΩ CE pull-downs removed** | A4 0.145 V, CE rail 0.144 V, no change on holes 7, 3 and 13 | Not caused by the resistor value |
| 10 | `CH 7 ON 1500`, then `ADC READ` while on | `STATUS` ce1=1, mask 0x0040 *(firmware-reported)*; A4 145 → 145 mV | The firmware says it is high; the pin is not |
| 11 | **A4 unloaded:** the DRV1 CE wire moved back to A3 (now undriven, no pull-down); only the ADS probe on A4, and a second probe on A5 (unused) | A4: 144 → 144 mV with ce1=1. A5: 153 mV steady | **A4 cannot drive high even with no load.** A4 and A5 sit at about 0.15 V, not at the 0.557 V of a floating ADS input. Something holds them low |
| 12 | DMM directly on the Nano's header solder joints, at rest | **Nano 5V pin: 4.67 V**; **A2 (LATCH): 0.125 V** (firmware holds it high); A0 (DATA): 0.213 V (expected low) | **A2 cannot drive high either.** So LATCH never rises, the 595s never latch, and no hole has ever been selected, whatever the CE does |

**For comparison, port B and port D pins that work:**
- D10 (PB2) drove the DRV1 CE input to over 4.1 V.
- D11/D12 (PB3/PB4) run I²C, including open-drain releases and an SCL rise-time check.
- D2–D9 run both steppers.

**Also seen today:** an unexpected USB disconnect while the dashboard sat idle (`[Errno 6] Device not configured`). The Nano reset: its motor positions went back to 0. The cause is unknown; it may have been the laptop sleeping or the cable being knocked.

---

## 5. A separate, unresolved puzzle: the OPT101 output does not reach ADS A1

| Measurement | Value |
|---|---|
| OPT101 module VCC to COM | 5.123 V |
| OUT pad to COM | **2.594 V**, with the chamber open |
| 1M pin to OUT pin (feedback jumper) | 0.7 Ω |
| OUT pad to the ADS1115 A1 header pin | **0.5 Ω** |
| What the ADS reads on A1 | about **0.557 V**, the same as unconnected A2 and A3; shifts with gain; picks up mains |

With the probe left hanging, the meter read about 2.5 V. When it touched the OPT101 OUT pin or ADS A1, the reading dropped to about 1.8 V.

**Unknowns:**
- whether the ADS1115 module's A1 header joint is open;
- whether the module's silkscreen order differs from the actual pin order.

This is probably independent of the Nano fault, but it is listed so you can say whether one cause could explain both.

---

## 6. Hypotheses so far (evaluate, rank, or replace)

1. **The ATmega328P's port C output drivers are damaged** (PC0–PC5: A0–A5).
   - Possible causes: overvoltage, ESD, or latch-up.
   - A possible event: a port C pin connected to a powered external circuit (the +5 V bus from the chargers or banks, or the ADS1115 module's pull-ups to a separate supply) while the Nano had no USB power. Or the power-bank reversal period.
   - Note: the Nano and the bus have separate 5 V supplies, joined only at GND.
2. **A fault in AVCC.** The ATmega328P datasheet is believed to say that AVCC supplies PC0–PC3 (and ADC6/7), while PC4–PC6 run from VCC. **Please verify this.**
   - If AVCC is not connected on this board (an open trace or ferrite on a clone Nano), A0–A3 could not drive high.
   - But A4 (PC4) also fails, and A4/A5 failed back on 2026-11-04. So AVCC alone does not fit unless there are two faults.
   - AVCC is not on a header. AREF (the REF pin) may show it only when the ADC uses the AVCC reference, as `analogRead(A6/A7)` in `safety.cpp` does.
3. **A firmware or configuration cause.** Considered unlikely:
   - plain `pinMode` / `digitalWrite` are used;
   - no direct PORTC/DDRC writes exist;
   - the same firmware drives PORTB/PORTD pins fine.
   - Please check whether anything in the Arduino AVR core 1.8.8, `shiftOut`, or the analogue reads of A6/A7 could leave port C as inputs or held low. One example to check: `DIDR0` only disables digital input buffers and should not affect outputs.
4. **The ADS-probe readings are unreliable.**
   - Weakened by the DMM confirming A2 at 0.125 V against 4.67 V on the 5V pin.
   - And by the same ADS probe catching D10 rising to 4.1 V and U1 pin 10 at about 4.1 V.

---

## 7. Questions for you

1. What is the most likely physical root cause, considering all of §3–§4? Which hypothesis fits **A0–A5 all failing to drive high, with PB/PD pins fine**, and **A4/A5 resting at about 0.15 V rather than floating**?
2. Is there a **non-destructive test** that tells "port C drivers damaged" apart from "AVCC missing"? The constraints:
   - DMM and ADS1115 only, no oscilloscope;
   - the Nano should not be removed from the breadboard if avoidable;
   - firmware can be changed and flashed with the operator's approval.
   - For example: a test sketch that drives each PCx high and reads back `PINC`; measuring REF with the ADC reference set to AVCC; checking for a short between the 5V pin and AVCC pads; or each Ax to GND and to 5V with the Nano unpowered.
3. Could anything in this circuit have **caused** it? For example, a port C pin driving the 595 inputs or CE inputs while the 595s and drivers were powered from the separate +5 V bus and the Nano had no USB power (back-powering through the clamp diodes). Or the earlier ADS1115 pull-ups with a floating VDD. **What should change so a replacement Nano isn't damaged the same way?** For example, series resistors, powering both from a common 5 V, or a power-up sequence.
4. Is it safe to keep using the healthy pins of this Nano (D2–D13), or does a damaged port C make the whole chip suspect?
5. The proposed interim workaround is to move DATA, CLOCK, LATCH and CE1 to D6–D9, which disables motor 2 and requires unplugging ULN2003 #2. Is that sound, and is there a better pin plan?
6. Optionally, any insight on the OPT101 → ADS A1 puzzle in §5.

---

## 8. Constraints at the bench (the operator's rules)

- No firmware changes or flashing without the operator's explicit approval.
- No motor motion unless the operator says "go".
- Optics safety:
  - one LED channel at a time;
  - select the channel's transistor before raising CE;
  - leave everything off at the end.
- The CE pull-downs are **currently removed**, and the DRV1 CE wire is on A3 (undriven). The operator has been asked to refit both 10 kΩ pull-downs.
- **Current hardware state:**
  - firmware 2.2.2, with CE1 on A4;
  - DRV1 CE wire on A3;
  - ADS1115 A2 jumpered to Nano A4, ADS1115 A3 jumpered to Nano A5;
  - U1/U2 pin 10 now at +5 V;
  - the CE wires to the correct drivers (DRV1 → A3, DRV2 → D10).

## 9. Files

- Raw diagnostics: `test_results/20261110-144616_led_diag.json`, and `test_results/_session/probe_log.txt` (every ADS-probe capture with timestamps).
- Probe scripts: `test_results/_session/led_diag.py`, `test_results/_session/probe.py`.
- Firmware source: `software/firmware/lio_firmware/` (`config.h` pin map; `optics.cpp`; `softi2c.cpp`).
- Design docs: `electronics/README.md`, `electronics/WIRING_CHECKLIST.md`, `electronics/data/{nano_pinmap,netlist,channel_map,bom}.csv`, `docs/PROTOCOL.md`, `docs/OPEN_ITEMS_AND_NEXT_STEPS.md`.

**Please return:**
- a ranked diagnosis with the reasoning;
- the single best confirming test, with exact steps;
- the recommended fix;
- any wiring changes that protect a replacement Nano.
