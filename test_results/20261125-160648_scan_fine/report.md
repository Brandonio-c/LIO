# LIO diagnostic sweep 20261125-160648_scan_fine

Mode **fine**, sample **LIO-F-00002**, status **INCOMPLETE**

## Verdict: FUNCTIONAL

- warnings: T13.T05, T13.T09, T13.T13, T13.T06

## Subsystem health

| Subsystem | Parts | Health | Reason |
|---|---|---|---|
| Link / firmware | Nano R4, USB, firmware | ✓ OK | 1 checks pass |
| ADC / I²C | ADS1115, software I²C D11/D12 | ✓ OK | 1 checks pass |
| Shift registers | U1, U2 | ✓ OK | 1 checks pass |
| LED drivers / rails | DRV1 (RAIL A), DRV2 (RAIL B) | ✓ OK | 4 checks pass |
| LED / MOSFET channels | LED1-16, Q1-16 | ! WATCH | optics/opt101/h16/plausibility: opt101 cannot see 1850 nm; residual +831 counts over C +2.0 |
| OPT101 | OPT101 (A1) | ✓ OK | 7 checks pass |
| InGaAs TIA | D1, U5, Rf, Cf (A0) | ✕ ACT | elec/ingaas/coupling: rail A: +4.0 counts (+0.50 mV) from 7 blind holes, rail B: +45.0 counts (+5.62 mV) from 3 blind holes |
| Motors / lead screws | M1, M2, ULN2003, couplers, M6 rods | ! WATCH | mech/travel: tracked range 50023 / 297371 half-steps (M1/right / M2/left): the two sides differ (thresholds.motion.travel.range_steps not set: not compared) |
| Stage tracking | lio.stage, soft limits | ✓ OK | 1 checks pass |
| Safety | interlocks, duty budget | ✓ OK | 1 checks pass |
| Power / earthing | supplies, GND, earth bond | ✕ ACT | elec/ingaas/ground_shift: +0.733 counts/mA |
| Optical path / ambient | window, shroud, lid, sample | ✓ OK | 5 checks pass |
| Run | the scan itself | ! WATCH | system/run: INCOMPLETE: All off pressed |

## Findings to act on

### ! WARN `system/run`: run complete

INCOMPLETE: All off pressed

- **Why:** The run did not complete: metrics needing the missing steps are SKIP.
- **Parts:** run
- **Next check:** See the abort reason; 'lio scan resume <run>' carries on from the next step.

### ! WARN `optics/opt101/h16/plausibility`: hole 16 (1850) seen by opt101?

opt101 cannot see 1850 nm; residual +831 counts over C +2.0

- **Why:** A detector responds to a hole whose nominal wavelength it should not see. This does NOT identify a wrong LED: secondary/shorter-wave emission, broadband tails, electrical pickup or a swapped part are all possible; the spectrum is unassigned (h16 stays a proxy_unassigned feature, never primary 1850 nm).
- **Parts:** LED16, optical path
- **Next check:** Compare the LED marking with docs/OPTICAL_CHANNEL_MAP.md and look for a response missing elsewhere (a swap). Do not replace a part on this finding alone.

### ! WARN `optics/ingaas/h16/plausibility`: hole 16 (1850) seen by ingaas?

ingaas cannot see 1850 nm; residual +73 counts over C +45.0; height-dependent (optical)

- **Why:** A detector responds to a hole whose nominal wavelength it should not see. This does NOT identify a wrong LED: secondary/shorter-wave emission, broadband tails, electrical pickup or a swapped part are all possible; the spectrum is unassigned (h16 stays a proxy_unassigned feature, never primary 1850 nm).
- **Parts:** LED16, optical path
- **Next check:** Compare the LED marking with docs/OPTICAL_CHANNEL_MAP.md and look for a response missing elsewhere (a swap). Do not replace a part on this finding alone.

### ✕ FAIL `elec/ingaas/coupling`: ingaas: electrical coupling (height-invariant, LED on)

rail A: +4.0 counts (+0.50 mV) from 7 blind holes, rail B: +45.0 counts (+5.62 mV) from 3 blind holes

- **Why:** The detector output changes when an LED is on even though it cannot see that light: electrical coupling from the LED drive (shared ground return, or capacitive pick-up).
- **Parts:** GND star point, SUM/TIA_REF routing, LED drive wiring
- **Next check:** Check that the TIA reference and the LED return do not share a thin ground path.

### ✕ FAIL `elec/ingaas/ground_shift`: ingaas: ground shift (coupling vs rail current)

+0.733 counts/mA

- **Why:** The coupling scales with the rail current: LED current through a shared ground resistance shifts the detector's reference (ground shift).
- **Parts:** GND star point, TIA_REF, rail returns
- **Next check:** Measure the voltage between the TIA ground and the supply ground with RAIL B lit; run the LED returns straight to the supply.

### ! WARN `elec/ingaas/hum`: ingaas: mains hum (coils off)

60/120/180 Hz: 7.172 / 0.120 / 0.681 mV; 100% of the variance at mains harmonics; broadband sigma 0.266 mV; readings integrate whole mains periods, so it cancels in the measurements

- **Why:** Mains hum on the detector output: a missing earth bond or leakage from a charger.
- **Parts:** earth bond, chargers, GND
- **Next check:** Check the earth bond (circuit GND to mains earth); unplug the laptop charger and repeat.

### ! WARN `mech/travel`: travel (top to bottom)

tracked range 50023 / 297371 half-steps (M1/right / M2/left): the two sides differ (thresholds.motion.travel.range_steps not set: not compared)

- **Why:** The tracked travel differs from the configured one (or between the sides).
- **Parts:** stage limits
- **Next check:** Re-mark the top and bottom.

### ! WARN `mech/repeatability`: repeatability at the reference heights

spread of repeated visits 368 half-steps (RMS over 3 groups); above minus below +520 half-steps (backlash, direct)

- **Why:** Repeated visits to one height do not land in the same place.
- **Parts:** couplers, lead screws
- **Next check:** Repeat the reference heights; inspect the couplers.

## Response vs height, per hole (down pass; blind holes blank)

![Response vs height, per hole (down pass; blind holes blank)](plots/heatmap.png)

## Response curves: down pass (solid) and up pass (dashed)

![Response curves: down pass (solid) and up pass (dashed)](plots/curves.png)

## Dark level vs height (light leak) and over time (drift)

![Dark level vs height (light leak) and over time (drift)](plots/dark.png)

## Dark noise: mains harmonics and broadband

![Dark noise: mains harmonics and broadband](plots/spectra.png)

## System

| Status | Metric | Value | Result | Criterion |
|---|---|---|---|---|
| ✓ PASS | `system/link` | 0 unexpected boots | firmware 2.5.2, no unexpected # BOOT |  |
| ✓ PASS | `system/adc` | 3044 readings | 3044 readings, no dropout |  |
| ✓ PASS | `system/addressing` | 0 pairs | 13 responding holes, all distinct |  |
| ✓ PASS | `system/rail/A` | 8 holes | 8/8 holes respond |  |
| ✓ PASS | `system/rail/B` | 4 holes | 4/8 holes respond |  |
| - SKIP | `system/interlocks` |  | P4 not reached |  |
| ✓ PASS | `system/duty` | 920 ms/min | max 920 ms of 1000 ms; 2 cool-down waits, 8.89 s in all |  |
| ✓ PASS | `system/stage` |  | position [-21990, -21990], limits respected |  |
| ! WARN | `system/run` |  | INCOMPLETE: All off pressed |  |

## Optics

| Status | Metric | Value | Result | Criterion |
|---|---|---|---|---|
| - SKIP | `optics/opt101/h01/response` | 89.1 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| - SKIP | `optics/opt101/h02/response` | 71 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| - SKIP | `optics/opt101/h03/response` | 74.3 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| - SKIP | `optics/opt101/h04/response` | 170.3 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| - SKIP | `optics/opt101/h05/response` | 57.8 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| - SKIP | `optics/opt101/h06/response` | 40.3 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| - SKIP | `optics/opt101/h07/response` | 98.2 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| - SKIP | `optics/opt101/h08/response` | 661.3 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| - SKIP | `optics/opt101/h09/response` | 527.2 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| - SKIP | `optics/opt101/h10/response` | 220.5 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| - SKIP | `optics/opt101/h11/response` | 546.5 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| ✓ PASS | `optics/opt101/h12/plausibility` | 21.1 counts | opt101 cannot see 1450 nm; residual +21 counts over C +2.0 | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/opt101/h13/plausibility` | 0.1 counts | opt101 cannot see 1550 nm; residual +0 counts over C +2.0 | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/opt101/h14/plausibility` | 0.8 counts | opt101 cannot see 1650 nm; residual +1 counts over C +2.0 | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/opt101/h15/plausibility` | 0.1 counts | opt101 cannot see 1760 nm; residual +0 counts over C +2.0 | < 30 counts (WARN), < 80 (FAIL) |
| ! WARN | `optics/opt101/h16/plausibility` | 830.9 counts | opt101 cannot see 1850 nm; residual +831 counts over C +2.0 | < 30 counts (WARN); FAIL capped to WARN: no in-range detector for this hole |
| ✓ PASS | `optics/opt101/electrical_only` | 0 fraction | 0/11 expected holes show no optical response; coupling small | FAIL when >= 75% of expected holes have O < 6 while |C| >= 8 |
| - SKIP | `optics/opt101/throughput` | 98.2 counts | median O over 11 expected holes; spread (CV) 94% across holes | sample 'LIO-F-00002': judged against its baseline only |
| ✓ PASS | `optics/ingaas/h01/plausibility` | 1.3 counts | ingaas cannot see 395 nm; residual +1 counts over C +4.0 | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/ingaas/h02/plausibility` | 1.8 counts | ingaas cannot see 405 nm; residual +2 counts over C +4.0 | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/ingaas/h03/plausibility` | -1.8 counts | ingaas cannot see 465 nm; residual -2 counts over C +4.0 | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/ingaas/h04/plausibility` | 1.5 counts | ingaas cannot see 525 nm; residual +2 counts over C +4.0 | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/ingaas/h05/plausibility` | 6.3 counts | ingaas cannot see 590 nm; residual +6 counts over C +4.0 | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/ingaas/h06/plausibility` | 4.1 counts | ingaas cannot see 605 nm; residual +4 counts over C +4.0 | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/ingaas/h07/plausibility` | 11.2 counts | ingaas cannot see 630 nm; residual +11 counts over C +4.0 | < 30 counts (WARN), < 80 (FAIL) |
| - SKIP | `optics/ingaas/h08/response` | 95.8 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| - SKIP | `optics/ingaas/h09/response` | 92.3 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| ✓ PASS | `optics/ingaas/h10/plausibility` | -32.5 counts | ingaas cannot see 450 nm; residual -33 counts over C +45.0 | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/ingaas/h11/plausibility` | 4.5 counts | ingaas cannot see 450 nm; residual +4 counts over C +45.0 | < 30 counts (WARN), < 80 (FAIL) |
| - SKIP | `optics/ingaas/h12/response` | 7.5 counts | sample 'LIO-F-00002' is not judged against absolute levels | O >= 15 (WARN below), >= 6 (FAIL below) |
| ! WARN | `optics/ingaas/h16/plausibility` | 73.1 counts | ingaas cannot see 1850 nm; residual +73 counts over C +45.0; height-dependent (optical) | < 30 counts (WARN); FAIL capped to WARN: no in-range detector for this hole |
| ✓ PASS | `optics/ingaas/electrical_only` | 0 fraction | 0/3 expected holes show no optical response; coupling present | FAIL when >= 75% of expected holes have O < 6 while |C| >= 8 |
| - SKIP | `optics/ingaas/throughput` | 92.3 counts | median O over 3 expected holes; spread (CV) 63% across holes | sample 'LIO-F-00002': judged against its baseline only |
| ✓ PASS | `optics/h01/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h02/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h03/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h04/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h05/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h06/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h07/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h08/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h09/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h10/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h11/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h12/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h13/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h14/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h15/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/h16/intermittent` | 0 heights | down and up agree at 6 heights |  |
| ✓ PASS | `optics/optimum` | -39511 half-steps | -39511 half-steps (-9.65 mm); weakest normalised response there 0.94 |  |
| ✓ PASS | `optics/opt101/snr` | 33.5 dB | weakest hole 6: 33.5 dB (noise sigma 0.107 mV) | >= 20 dB |
| ✓ PASS | `optics/opt101/headroom` | 97 % | highest lit reading 891 of 29600 counts | >= 10% |
| ✓ PASS | `optics/ingaas/snr` | 10.9 dB | weakest hole 12: 10.9 dB (noise sigma 0.266 mV) | >= 20 dB |
| ✓ PASS | `optics/ingaas/headroom` | 100.7 % | highest lit reading -190 of 28000 counts | >= 10% |
| - SKIP | `optics/stray` |  | needs a black_cup run (with a white_ptfe reference) |  |
| - SKIP | `optics/effectiveness` |  | needs a reference (baseline) of the same sample |  |
| ✓ PASS | `optics/wrong_rail/h01` | 0 counts | +0 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h02` | 0 counts | +0 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h03` | 0 counts | +0 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h04` | 0 counts | +0 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h05` | 0 counts | +0 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h06` | 0 counts | +0 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h07` | 0 counts | +0 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h08` | 1 counts | +1 counts on ingaas with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h09` | 0 counts | +0 counts on opt101 with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h10` | 0 counts | +0 counts on opt101 with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h11` | 0 counts | +0 counts on opt101 with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h12` | 3 counts | +3 counts on ingaas with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h13` | -3 counts | -3 counts on ingaas with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h14` | 0 counts | +0 counts on ingaas with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| ✓ PASS | `optics/wrong_rail/h15` | -1 counts | -1 counts on ingaas with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |

## Electrical

| Status | Metric | Value | Result | Criterion |
|---|---|---|---|---|
| ✓ PASS | `elec/opt101/coupling` | 2 counts | rail A: +1.3 counts (+0.17 mV) inferred, rail B: +2.0 counts (+0.25 mV) from 5 blind holes | corrected in software below 20 counts (FAIL at or above) |
| ✓ PASS | `elec/opt101/ground_shift` | 0.0056 mV/mA | +0.044 counts/mA | corrected in software below 0.08 mV/mA (FAIL at or above) |
| ✕ FAIL | `elec/ingaas/coupling` | 45 counts | rail A: +4.0 counts (+0.50 mV) from 7 blind holes, rail B: +45.0 counts (+5.62 mV) from 3 blind holes | corrected in software below 20 counts (FAIL at or above) |
| ✕ FAIL | `elec/ingaas/ground_shift` | 0.0917 mV/mA | +0.733 counts/mA | corrected in software below 0.08 mV/mA (FAIL at or above) |
| ✓ PASS | `elec/opt101/dark_offset` | 6.985 mV | +55.9 counts (+6.99 mV); equivalent input current not computed (Rf unsupported or unknown) | 0 to 800 counts (thresholds.dark) |
| ✓ PASS | `elec/ingaas/dark_offset` | -41.094 mV | -328.8 counts (-41.09 mV); equivalent input current not computed (InGaAs physical current blocked: input_range=unverified) | -400 to 2000 counts (thresholds.dark) |
| ✓ PASS | `elec/opt101/drift` | 0.009 mV/h | +0.01 ± 0.02 mV/h | |slope| < 3 mV/h (WARN), < 8 (FAIL) |
| ✓ PASS | `elec/ingaas/drift` | 0.386 mV/h | +0.39 ± 0.28 mV/h (-0.4 nA/h) | |slope| < 3 mV/h (WARN), < 8 (FAIL) |
| ✓ PASS | `elec/opt101/hum` | 0.0343 mV | 60/120/180 Hz: 0.034 / 0.033 / 0.034 mV; 13% of the variance at mains harmonics; broadband sigma 0.107 mV; readings integrate whole mains periods, so it cancels in the measurements | 60 Hz amplitude < 0.3 mV (WARN; not when the readings reject it), < 1 (FAIL); mains fraction < 0.5 |
| ! WARN | `elec/ingaas/hum` | 7.1715 mV | 60/120/180 Hz: 7.172 / 0.120 / 0.681 mV; 100% of the variance at mains harmonics; broadband sigma 0.266 mV; readings integrate whole mains periods, so it cancels in the measurements | 60 Hz amplitude < 1 mV (WARN; not when the readings reject it), < 3 (FAIL); mains fraction < 0.5 |
| ✓ PASS | `elec/opt101/coil_emi` | 9.25 x | sigma 1.156 mV moving vs 0.107 mV off (measured while moving, S0 D2); judged only when measuring while moving (continuous mode): every other reading is taken with the motors stopped | ratio < 3 (WARN), < 6 (FAIL) |
| ✓ PASS | `elec/ingaas/coil_emi` | 0.97 x | sigma 0.259 mV moving vs 0.266 mV off (measured while moving, S0 D2); judged only when measuring while moving (continuous mode): every other reading is taken with the motors stopped | ratio < 3 (WARN), < 6 (FAIL) |
| ✓ PASS | `elec/opt101/h16/select_only` | 0.5 counts | largest on hole 16: -0.5 counts | < 8 counts (WARN); FAIL capped to WARN (gate coupling, LED off) |
| ✓ PASS | `elec/ingaas/h14/select_only` | 3 counts | largest on hole 14: -3.0 counts | < 8 counts (WARN); FAIL capped to WARN (gate coupling, LED off) |
| ✓ PASS | `elec/opt101/ce_only` | 0 counts | CE1: +0.0, CE2: +0.0 | < 8 counts (WARN), < 20 (FAIL) |
| ✓ PASS | `elec/ingaas/ce_only` | 0 counts | CE1: +0.0, CE2: +0.0 | < 8 counts (WARN), < 20 (FAIL) |
| - SKIP | `elec/rails` |  | A2/A3 not wired for rail and ground monitoring |  |

## Mechanics

| Status | Metric | Value | Result | Criterion |
|---|---|---|---|---|
| - SKIP | `mech/home_sensors` |  | no home sensors fitted |  |
| ! WARN | `mech/travel` | 50023 half-steps | tracked range 50023 / 297371 half-steps (M1/right / M2/left): the two sides differ (thresholds.motion.travel.range_steps not set: not compared) |  |
| ✓ PASS | `mech/lockstep` | 0 moves | 109 moves; 0 ended with the two sides at different positions (without home sensors only the commanded steps are seen: a side losing steps shows as mech/step_loss) |  |
| ✓ PASS | `mech/settle` | 602 ms | median 602 ms, max 609 ms (mechanical wait 300 ms) | max - median < 500 ms (WARN), < 1500 (FAIL) |
| - SKIP | `mech/backlash` | 780 half-steps | +780 ± 784 half-steps (+0.191 mm) from 74 readings on 13 channels | < 600 (WARN), < 1500 (FAIL); not flagged within 3 sigma; not judged when the resolution is worse than 300 |
| - SKIP | `mech/step_loss` | -1156 half-steps per travel | the stage falls behind by -1156 ± 1689 half-steps over a full upward travel (one side losing steps: about twice that on that side, and a tilt) | < 400 (WARN), < 1000 (FAIL); not flagged within 3 sigma |
| ! WARN | `mech/repeatability` | 368 half-steps | spread of repeated visits 368 half-steps (RMS over 3 groups); above minus below +520 half-steps (backlash, direct) | < 300 (WARN), < 800 (would FAIL; capped at WARN for V3 mechanics) |

## Ambient

| Status | Metric | Value | Result | Criterion |
|---|---|---|---|---|
| ✓ PASS | `ambient/opt101/leak` | 0.1 counts | dark at the bottom +0.1 counts (+0.02 mV) vs the top; 0.13% of the median signal | rise < 8 counts (WARN), < 25 (FAIL) |
| ✓ PASS | `ambient/ingaas/leak` | 7.8 counts | dark at the bottom +7.8 counts (+0.98 mV) vs the top; rises from h -50023; 8.46% of the median signal | rise < 8 counts (WARN), < 25 (FAIL) |
| ✓ PASS | `ambient/opt101/flicker` | 0.0328 mV | 120 Hz amplitude in the dark streams 0.033 mV; readings integrate whole mains periods, so it cancels | < 0.4 mV (WARN), < 1.2 (FAIL) |
| ✓ PASS | `ambient/ingaas/flicker` | 0.1204 mV | 120 Hz amplitude in the dark streams 0.120 mV; readings integrate whole mains periods, so it cancels | < 0.4 mV (WARN), < 1.2 (FAIL) |
| - SKIP | `ambient/lid` |  | optional operator step (lid ajar at two heights) |  |

## Trend

| Status | Metric | Value | Result | Criterion |
|---|---|---|---|---|
| - SKIP | `trend/control` |  | needs 5 baselines of LIO-F-00002 (have 0) |  |

## Not measured (capability)

- rail_monitor: A2/A3 not wired for rail and ground monitoring
- home_sensors: no home sensors fitted
