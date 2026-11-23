# LIO test report: 20261123-173106_host

**Verdict: NOT FUNCTIONAL**: failures not tied to a channel: T13.1

- Target: `/dev/cu.usbmodem101`
- Started 2026-11-23T17:31:06-05:00, finished 2026-11-23T17:56:40-05:00
- Sample: `empty`, operator: owner (answers via Claude session 2026-11-23), notes: T13.1 rerun on f78c6b6 (verified new dashboard pid); owner answers: chamber empty+clear, lid closed, earth bond connected
- Firmware 2.5.2 (proto 1, build 2026-11-17)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 493718927528 (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git 2212d1ba99 (dirty)
- Counts: FAIL 1
- LED duty budget: 175.4 s of cool-down waits, 0 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T13.1 | Diagnostic height sweep | ✕ FAIL | quick scan COMPLETE: NOT FUNCTIONAL (20261123-173108_scan_quick) |

## T13

### T13.1 Diagnostic height sweep: FAIL

quick scan COMPLETE: NOT FUNCTIONAL (20261123-173108_scan_quick)

| Check | Status | Result | Criterion |
|---|---|---|---|
| hole 13 (1550) on ingaas | ✕ FAIL | O -5 counts at h -286884, C +11.0, modulation 1.02 \| why: This hole gives no (or little) height-dependent light on a detector that should see it: the LED is dead or reversed, its MOSFET is open, it is wired to the wrong rail, or it is an LED that this detector cannot see (swapped or wrong part). \| parts: LED13, Q13, rail wiring | O >= 33.7671 (WARN below), >= 16.8835 (FAIL below) |
| hole 14 (1650) on ingaas | ✕ FAIL | O -10 counts at h -16384, C +11.0, modulation 0.25 \| why: This hole gives no (or little) height-dependent light on a detector that should see it: the LED is dead or reversed, its MOSFET is open, it is wired to the wrong rail, or it is an LED that this detector cannot see (swapped or wrong part). \| parts: LED14, Q14, rail wiring | O >= 33.7671 (WARN below), >= 16.8835 (FAIL below) |
| ingaas: optical throughput (window, alignment) | ✕ FAIL | median O over 5 expected holes; spread (CV) 136% across holes \| why: Every hole on this detector is weaker than expected while the shape vs height is normal: less light reaches the detector (a dirty or blocked window, misalignment, or a weaker sample). \| parts: detector window, alignment, sample | median O >= 60 (WARN below), >= 20 (FAIL below) for empty |
| ingaas: mains hum (coils off) | ✕ FAIL | 60/120/180 Hz: 9.475 / 0.190 / 1.143 mV; 100% of the variance at mains harmonics; broadband sigma 0.528 mV; readings integrate whole mains periods, so it cancels in the measurements \| why: Mains hum on the detector output: a missing earth bond or leakage from a charger. \| parts: earth bond, chargers, GND | 60 Hz amplitude < 1 mV (WARN; not when the readings reject it), < 3 (FAIL); mains fraction < 0.5 |
| hole 12 (1450) seen by opt101? | ! WARN | opt101 cannot see 1450 nm; residual +33 counts over C +1.0; height-dependent (optical) \| why: A detector responds, with a height-dependent (optical) signal, to a hole whose wavelength it cannot see: the LED in this hole is not the one in the channel map (swapped with another hole, or the wrong part). \| parts: LED12 | < 30 counts (WARN), < 80 (FAIL) |
| hole 16 (1850) seen by opt101? | ! WARN | opt101 cannot see 1850 nm; residual +381 counts over C +1.0; height-dependent (optical) \| why: A detector responds, with a height-dependent (optical) signal, to a hole whose wavelength it cannot see: the LED in this hole is not the one in the channel map (swapped with another hole, or the wrong part). \| parts: LED16 | < 30 counts (WARN); FAIL capped to WARN: no in-range detector for this hole |
| hole 9 (940) on ingaas | ! WARN | O 23 counts at h -151634, C +11.0, modulation 0.97 \| why: This hole gives no (or little) height-dependent light on a detector that should see it: the LED is dead or reversed, its MOSFET is open, it is wired to the wrong rail, or it is an LED that this detector cannot see (swapped or wrong part). \| parts: LED9, Q9, rail wiring | O >= 33.7671 (WARN below), >= 16.8835 (FAIL below) |
| hole 12 (1450) on ingaas | ! WARN | O 20 counts at h -16384, C +11.0, modulation 3.19 \| why: This hole gives no (or little) height-dependent light on a detector that should see it: the LED is dead or reversed, its MOSFET is open, it is wired to the wrong rail, or it is an LED that this detector cannot see (swapped or wrong part). \| parts: LED12, Q12, rail wiring | O >= 33.7671 (WARN below), >= 16.8835 (FAIL below) |
| hole 16 (1850) seen by ingaas? | ! WARN | ingaas cannot see 1850 nm; residual +40 counts over C +11.0; height-dependent (optical) \| why: A detector responds, with a height-dependent (optical) signal, to a hole whose wavelength it cannot see: the LED in this hole is not the one in the channel map (swapped with another hole, or the wrong part). \| parts: LED16 | < 30 counts (WARN); FAIL capped to WARN: no in-range detector for this hole |
| optimum height (all holes) | ! WARN | -16384 half-steps (-4.00 mm); weakest normalised response there 0.03; at an end of the travel: the true peak may lie beyond \| why: The best height is at an end of the travel: the true optimum may lie beyond it. \| parts: geometry |  |
| ingaas: signal-to-noise at the optimum | ! WARN | weakest hole 12: 13.4 dB (noise sigma 0.528 mV) \| why: A hole's signal is close to the noise. \| parts: LED, detector | >= 20 dB |
| travel (top to bottom) | ! WARN | tracked range 286884 / 429461 half-steps (M1/right / M2/left): the two sides differ (thresholds.motion.travel.range_steps not set: not compared) \| why: The tracked travel differs from the configured one (or between the sides). \| parts: stage limits |  |
| link and firmware (no unexpected reset, no lost replies) | ✓ PASS | firmware 2.5.2, no unexpected # BOOT |  |
| ADC / I²C (every reading answered) | ✓ PASS | 764 readings, no dropout |  |
| addressing (each hole lights its own LED) | ✓ PASS | 13 responding holes, all distinct |  |
| RAIL A (driver gates the LEDs) | ✓ PASS | 8/8 holes respond |  |
| RAIL B (driver gates the LEDs) | ✓ PASS | 4/8 holes respond |  |
| P4 interlock re-checks | ✓ PASS | light_while_moving: PASS; single_channel: SKIP: host refused before transmission (CE on refused: no single selected hole to reserve duty against); firmware interlock not exercised |  |
| LED duty (RAIL A <= budget per LED per minute) | ✓ PASS | max 92 ms of 1000 ms; 3 cool-down waits, 175.41 s in all |  |
| stage tracking (position trusted, soft limits respected) | ✓ PASS | position [-16384, -16384], limits respected |  |
| run complete | ✓ PASS | COMPLETE |  |
| hole 1 (395) on opt101 | ✓ PASS | O 72 counts at h -286884, C +0.7, modulation 0.54 | O >= 15 (WARN below), >= 6 (FAIL below) |
| hole 2 (purple) on opt101 | ✓ PASS | O 92 counts at h -286884, C +0.7, modulation 0.50 | O >= 15 (WARN below), >= 6 (FAIL below) |
| hole 3 (blue) on opt101 | ✓ PASS | O 63 counts at h -286884, C +0.7, modulation 0.52 | O >= 15 (WARN below), >= 6 (FAIL below) |
| hole 4 (green) on opt101 | ✓ PASS | O 105 counts at h -286884, C +0.7, modulation 0.47 | O >= 15 (WARN below), >= 6 (FAIL below) |
| hole 5 (yellow) on opt101 | ✓ PASS | O 34 counts at h -286884, C +0.7, modulation 0.34 | O >= 15 (WARN below), >= 6 (FAIL below) |
| hole 6 (orange) on opt101 | ✓ PASS | O 28 counts at h -286884, C +0.7, modulation 0.28 | O >= 15 (WARN below), >= 6 (FAIL below) |
| hole 7 (red) on opt101 | ✓ PASS | O 44 counts at h -286884, C +0.7, modulation 0.39 | O >= 15 (WARN below), >= 6 (FAIL below) |
| hole 8 (850) on opt101 | ✓ PASS | O 269 counts at h -286884, C +0.7, modulation 0.42 | O >= 15 (WARN below), >= 6 (FAIL below) |
| hole 9 (940) on opt101 | ✓ PASS | O 148 counts at h -219259, C +1.0, modulation 0.33 | O >= 15 (WARN below), >= 6 (FAIL below) |
| hole 10 (white) on opt101 | ✓ PASS | O 102 counts at h -286884, C +1.0, modulation 0.42 | O >= 15 (WARN below), >= 6 (FAIL below) |
| hole 11 (pink) on opt101 | ✓ PASS | O 252 counts at h -286884, C +1.0, modulation 0.42 | O >= 15 (WARN below), >= 6 (FAIL below) |
| hole 13 (1550) seen by opt101? | ✓ PASS | opt101 cannot see 1550 nm; residual +0 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 14 (1650) seen by opt101? | ✓ PASS | opt101 cannot see 1650 nm; residual -1 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 15 (1760) seen by opt101? | ✓ PASS | opt101 cannot see 1760 nm; residual +1 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| opt101: signal electrical only (no light)? | ✓ PASS | 0/11 expected holes show no optical response; coupling small | FAIL when >= 75% of expected holes have O < 6 while \|C\| >= 8 |
| opt101: optical throughput (window, alignment) | ✓ PASS | median O over 11 expected holes; spread (CV) 72% across holes | median O >= 60 (WARN below), >= 20 (FAIL below) for empty |
| hole 1 (395) seen by ingaas? | ✓ PASS | ingaas cannot see 395 nm; residual -1 counts over C +3.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 2 (purple) seen by ingaas? | ✓ PASS | ingaas cannot see 405 nm; residual +0 counts over C +3.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 3 (blue) seen by ingaas? | ✓ PASS | ingaas cannot see 465 nm; residual -1 counts over C +3.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 4 (green) seen by ingaas? | ✓ PASS | ingaas cannot see 525 nm; residual +0 counts over C +3.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 5 (yellow) seen by ingaas? | ✓ PASS | ingaas cannot see 590 nm; residual +6 counts over C +3.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 6 (orange) seen by ingaas? | ✓ PASS | ingaas cannot see 605 nm; residual +6 counts over C +3.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 7 (red) seen by ingaas? | ✓ PASS | ingaas cannot see 630 nm; residual +6 counts over C +3.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 8 (850) on ingaas | ✓ PASS | O 50 counts at h -286884, C +3.0, modulation 0.45 | O >= 33.7671 (WARN below), >= 16.8835 (FAIL below) |
| hole 10 (white) seen by ingaas? | ✓ PASS | ingaas cannot see 450 nm; residual -6 counts over C +11.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 11 (pink) seen by ingaas? | ✓ PASS | ingaas cannot see 450 nm; residual +5 counts over C +11.0 | < 30 counts (WARN), < 80 (FAIL) |
| ingaas: signal electrical only (no light)? | ✓ PASS | 2/5 expected holes show no optical response; coupling present | FAIL when >= 75% of expected holes have O < 16.8835 while \|C\| >= 8 |
| hole 1 (395) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 2 (purple) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 3 (blue) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 4 (green) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 5 (yellow) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 6 (orange) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 7 (red) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 8 (850) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 9 (940) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 10 (white) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 11 (pink) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 12 (1450) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 13 (1550) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 14 (1650) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 15 (1760) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| hole 16 (1850) intermittent | ✓ PASS | down and up agree at 8 heights |  |
| opt101: signal-to-noise at the optimum | ✓ PASS | weakest hole 6: 29.8 dB (noise sigma 0.113 mV) | >= 20 dB |
| opt101: saturation headroom | ✓ PASS | highest lit reading 439 of 29600 counts | >= 10% |
| ingaas: saturation headroom | ✓ PASS | highest lit reading -279 of 28000 counts | >= 10% |
| opt101: electrical coupling (height-invariant, LED on) | ✓ PASS | rail A: +0.7 counts (+0.08 mV) inferred, rail B: +1.0 counts (+0.12 mV) from 5 blind holes | corrected in software below 20 counts (FAIL at or above) |
| opt101: ground shift (coupling vs rail current) | ✓ PASS | +0.022 counts/mA | corrected in software below 0.08 mV/mA (FAIL at or above) |
| ingaas: electrical coupling (height-invariant, LED on) | ✓ PASS | rail A: +3.0 counts (+0.38 mV) from 7 blind holes, rail B: +11.0 counts (+1.38 mV) from 3 blind holes | corrected in software below 20 counts (FAIL at or above) |
| ingaas: ground shift (coupling vs rail current) | ✓ PASS | +0.200 counts/mA | corrected in software below 0.08 mV/mA (FAIL at or above) |
| opt101: dark offset / leakage | ✓ PASS | +56.6 counts (+7.08 mV) | 0 to 800 counts (thresholds.dark) |
| ingaas: dark offset / leakage | ✓ PASS | -332.3 counts (-41.54 mV); equivalent input current +41.5 nA (Rf 1 MΩ) | -400 to 2000 counts (thresholds.dark) |
| opt101: dark drift over the run | ✓ PASS | +0.04 ± 0.05 mV/h; P4 - P1 +0.04 mV | \|slope\| < 3 mV/h (WARN), < 8 (FAIL) |
| ingaas: dark drift over the run | ✓ PASS | -0.54 ± 0.58 mV/h (+0.5 nA/h); P4 - P1 -0.35 mV | \|slope\| < 3 mV/h (WARN), < 8 (FAIL) |
| opt101: mains hum (coils off) | ✓ PASS | 60/120/180 Hz: 0.033 / 0.044 / 0.036 mV; 14% of the variance at mains harmonics; broadband sigma 0.113 mV; readings integrate whole mains periods, so it cancels in the measurements | 60 Hz amplitude < 0.3 mV (WARN; not when the readings reject it), < 1 (FAIL); mains fraction < 0.5 |
| opt101: coil interference (moving vs coils off) | ✓ PASS | sigma 1.182 mV moving vs 0.113 mV off (measured while moving, S0 D2); judged only when measuring while moving (continuous mode): every other reading is taken with the motors stopped | ratio < 3 (WARN), < 6 (FAIL) |
| ingaas: coil interference (moving vs coils off) | ✓ PASS | sigma 0.577 mV moving vs 0.528 mV off (measured while moving, S0 D2); judged only when measuring while moving (continuous mode): every other reading is taken with the motors stopped | ratio < 3 (WARN), < 6 (FAIL) |
| opt101: select-only coupling (MOSFET on, CE low) | ✓ PASS | largest on hole 1: -0.2 counts | < 8 counts (WARN); FAIL capped to WARN (gate coupling, LED off) |
| ingaas: select-only coupling (MOSFET on, CE low) | ✓ PASS | largest on hole 14: +1.2 counts | < 8 counts (WARN); FAIL capped to WARN (gate coupling, LED off) |
| opt101: CE-only coupling (driver enabled, no LED) | ✓ PASS | CE1: +0.0, CE2: +1.0 | < 8 counts (WARN), < 20 (FAIL) |
| ingaas: CE-only coupling (driver enabled, no LED) | ✓ PASS | CE1: +0.0, CE2: -1.0 | < 8 counts (WARN), < 20 (FAIL) |
| hole 1 dark with only RAIL B enabled | ✓ PASS | -1 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 2 dark with only RAIL B enabled | ✓ PASS | +0 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 3 dark with only RAIL B enabled | ✓ PASS | +0 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 4 dark with only RAIL B enabled | ✓ PASS | +0 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 5 dark with only RAIL B enabled | ✓ PASS | +0 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 6 dark with only RAIL B enabled | ✓ PASS | +1 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 7 dark with only RAIL B enabled | ✓ PASS | +0 counts on opt101 with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 8 dark with only RAIL B enabled | ✓ PASS | +2 counts on ingaas with the hole selected and RAIL B enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 9 dark with only RAIL A enabled | ✓ PASS | +1 counts on ingaas with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 10 dark with only RAIL A enabled | ✓ PASS | +0 counts on opt101 with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 11 dark with only RAIL A enabled | ✓ PASS | +1 counts on opt101 with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 12 dark with only RAIL A enabled | ✓ PASS | -1 counts on ingaas with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 13 dark with only RAIL A enabled | ✓ PASS | +2 counts on ingaas with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 14 dark with only RAIL A enabled | ✓ PASS | -1 counts on ingaas with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| hole 15 dark with only RAIL A enabled | ✓ PASS | +0 counts on ingaas with the hole selected and RAIL A enabled | < 30 counts (WARN), < 80 (FAIL) |
| opt101: dark vs height (light leak at the shroud) | ✓ PASS | dark at the bottom +0.1 counts (+0.01 mV) vs the top; 0.07% of the median signal | rise < 8 counts (WARN), < 25 (FAIL) |
| ingaas: dark vs height (light leak at the shroud) | ✓ PASS | dark at the bottom +2.3 counts (+0.29 mV) vs the top; 10.03% of the median signal | rise < 8 counts (WARN), < 25 (FAIL) |
| opt101: room-light flicker (120 Hz) | ✓ PASS | 120 Hz amplitude in the dark streams 0.044 mV; readings integrate whole mains periods, so it cancels | < 0.4 mV (WARN), < 1.2 (FAIL) |
| ingaas: room-light flicker (120 Hz) | ✓ PASS | 120 Hz amplitude in the dark streams 0.190 mV; readings integrate whole mains periods, so it cancels | < 0.4 mV (WARN), < 1.2 (FAIL) |
| lockstep (firmware positions level after every move) | ✓ PASS | 20 moves; 0 ended with the two sides at different positions (without home sensors only the commanded steps are seen: a side losing steps shows as mech/step_loss) |  |
| settle time after a move (dark-read convergence) | ✓ PASS | median 602 ms, max 607 ms (mechanical wait 300 ms) | max - median < 500 ms (WARN), < 1500 (FAIL) |
| stray light | - SKIP | needs a black_cup run (with a white_ptfe reference) |  |
| effectiveness vs reference | - SKIP | needs a reference (baseline) of the same sample |  |
| lid sensitivity | - SKIP | optional operator step (lid ajar at two heights) |  |
| backlash (down vs up response curves) | - SKIP | -35503 ± 6339 half-steps (-8.668 mm) from 100 readings on 14 channels | < 600 (WARN), < 1500 (FAIL); not flagged within 3 sigma; not judged when the resolution is worse than 300 |
| step loss (offset growing over the up pass) | - SKIP | the stage falls behind by +54099 ± 8329 half-steps over a full upward travel (one side losing steps: about twice that on that side, and a tilt) | < 400 (WARN), < 1000 (FAIL); not flagged within 3 sigma |
| repeatability at the reference heights | - SKIP | no repeated reference visits in this mode (full, fine, repeatability have them) |  |
