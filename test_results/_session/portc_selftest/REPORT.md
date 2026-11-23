# Port C self-test: result (2026-11-10)

**Sketch:** `portc_selftest.ino`, verbatim as supplied. Flashed with FQBN `arduino:avr:nano:cpu=atmega328`.
**Raw output:** `testA_output.txt`, 3 runs, each started by a DTR reset.

## Output (identical in all 3 runs)

```
AVCC/Vcc = inf V
pin float_V pullup_V high_V low_V estR_to_GND verdict
A0 nan nan nan nan >1M STRONG LOAD/SHORT TO GND
A1 nan nan nan nan >1M STRONG LOAD/SHORT TO GND
A2 nan nan nan nan >1M STRONG LOAD/SHORT TO GND
A3 nan nan nan nan >1M STRONG LOAD/SHORT TO GND
A4 nan nan nan nan >1M STRONG LOAD/SHORT TO GND
A5 nan nan nan nan >1M STRONG LOAD/SHORT TO GND
```

## How to read it

- **`AVCC/Vcc = inf`:** the sketch computes `1.1 × 1023 / ADC`, so `inf` means the conversion of the internal 1.1 V bandgap returned **ADC = 0**, against the AVCC reference.
  - A working ADC with AVCC at about 4.7 V returns about 240 here.
  - A result of 0 means the ADC is not working at all. On the ATmega328P that points at **AVCC: the ADC's own supply and reference.**
- **The per-pin columns are invalid.** Every voltage is `raw × inf` (`nan`). The verdict branch falls through to "STRONG LOAD/SHORT TO GND" because every comparison with `nan` is false. The `>1M` estimate is also an artefact. The per-pin verdicts are therefore **inconclusive, not evidence of a short**.

## How this fits

The ATmega328P datasheet (pin descriptions, AVCC) says: "AVCC is the supply voltage pin for the A/D Converter, PC3:0, and ADC7:6 … Note that PC6..4 use digital supply voltage, VCC."

| Observation | Explained by "AVCC not connected"? |
|---|---|
| ADC reads 0 for the 1.1 V bandgap | yes |
| A0, A1, A2, A3 (PC0–PC3) cannot drive high (A2 measured 0.125 V; A3 0.105 V) | yes: their output drivers are supplied from AVCC |
| A4 (PC4) did not rise when commanded high, unloaded (0.144 V); A4/A5 failed hardware I²C on 2026-11-04 | **no**: PC4/PC5 run from VCC. Either a second fault, or the external holding-low seen earlier (A4 at 7 kΩ to GND on 2026-11-04) |
| Port B and port D pins work | yes |

## Not run

- **Test B** (A6/A7 pin-table check and the DIAG build): not run. Its precondition was "Test A shows A0–A5 DRIVES OK", and that was not met.
- **A raw-count variant** of the sketch (same pin sequence and timing, but printing raw ADC counts and the digital read-back): written to `../portc_selftest_raw/`, **not flashed**. It was not covered by the approval for the verbatim sketch.

## Restore

- Firmware 2.2.2 reflashed. INFO shows `fw=2.2.2`, `adc_ok=1`.
- STATUS: ch 0, ce1 0, ce2 0, mask 0x0000, both motors idle and released, faults 0x00.

## Confirming test (meter only, no wiring change)

Firmware 2.2.2 calls `analogRead(A6/A7)` at boot (`safety_init`). That selects the AVCC reference, which connects AVCC internally to the **AREF pin**. So:

- Measure the Nano **REF** pin (3rd on the A-pin row from the USB end) to GND.
  - **About 4.6 V** (equal to the 5V pin): AVCC is present. Then the ADC = 0 result needs another explanation, and a damaged port C becomes the leading hypothesis.
  - **About 0 V or floating:** AVCC is open on this Nano. This confirms (a): it is the board, not the firmware or the external wiring, for A0–A3.

## Confirming test result (2026-11-10)

- Nano **REF pin: 0.181 V**, measured by the operator with the meter, running firmware 2.2.2 (AVCC reference selected at boot). The Nano's 5V pin read 4.67 V earlier.
- **Conclusion: AVCC is not connected on this Nano.** Answer (a): a board fault, not the firmware and not the external wiring.
  - It explains A0–A3 being unable to drive high, and the ADC reading 0 in the self-test.
- **Still unexplained:** A4 (PC4, which runs from VCC) did not rise when driven, unloaded (0.144 V). Do not rely on A4/A5 on this board.
