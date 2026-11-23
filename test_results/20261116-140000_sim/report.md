# LIO test report: 20261116-140000_sim

**Verdict: FUNCTIONAL**: no failures or warnings

- Target: `sim`
- Started 2026-11-16T14:00:00-05:00, finished 2026-11-16T14:00:13-05:00
- Sample: `none-empty-chamber`, operator: unknown
- Firmware 2.4.0 (proto 1, build 2026-11-03)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 22c2ed4f62a0 (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.4, lio 0.2.0, git 5a814da780 (dirty)
- Counts: PASS 1
- LED duty budget: 0.0 s of cool-down waits, 0 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T13.1 | Diagnostic height sweep | ✓ PASS | quick scan COMPLETE: FUNCTIONAL (20261116-140000_scan_quick) |

## T13

### T13.1 Diagnostic height sweep: PASS

quick scan COMPLETE: FUNCTIONAL (20261116-140000_scan_quick)

| Check | Status | Result | Criterion |
|---|---|---|---|
| link and firmware (no unexpected reset, no lost replies) | ✓ PASS | firmware 2.4.0, no unexpected # BOOT |  |
| ADC / I²C (every reading answered) | ✓ PASS | 728 readings, no dropout |  |
| addressing (each hole lights its own LED) | ✓ PASS | 15 responding holes, all distinct |  |
| RAIL A (driver gates the LEDs) | ✓ PASS | 9/9 holes respond |  |
| RAIL B (driver gates the LEDs) | ✓ PASS | 6/7 holes respond |  |
| P4 interlock re-checks | ✓ PASS | light_while_moving: PASS; single_channel: PASS |  |
| LED duty (RAIL A <= budget per LED per minute) | ✓ PASS | max 80 ms of 1000 ms; 0 cool-down waits, 0 s in all |  |
| stage tracking (position trusted, soft limits respected) | ✓ PASS | position [-4096, -4096], limits respected |  |
| run complete | ✓ PASS | COMPLETE |  |
| hole 1 (395) on opt101 | ✓ PASS | O 2759 counts at h -368027, C +0.7, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 2 (405) on opt101 | ✓ PASS | O 3932 counts at h -368027, C +0.7, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 3 (blue) on opt101 | ✓ PASS | O 6756 counts at h -368027, C +0.7, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 4 (green) on opt101 | ✓ PASS | O 4886 counts at h -368027, C +0.7, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 5 (yellow) on opt101 | ✓ PASS | O 3311 counts at h -368027, C +0.7, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 6 (orange) on opt101 | ✓ PASS | O 5842 counts at h -316037, C +0.7, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 7 (red) on opt101 | ✓ PASS | O 8212 counts at h -316037, C +0.7, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 8 (850) on opt101 | ✓ PASS | O 13058 counts at h -316037, C +0.7, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 9 (940) on opt101 | ✓ PASS | O 13390 counts at h -316037, C +0.7, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 10 (white) on opt101 | ✓ PASS | O 5778 counts at h -316037, C +1.0, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 11 (pink) on opt101 | ✓ PASS | O 2893 counts at h -316037, C +1.0, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 12 (1450) seen by opt101? | ✓ PASS | opt101 cannot see 1450 nm; residual +3 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 13 (1550) seen by opt101? | ✓ PASS | opt101 cannot see 1550 nm; residual +2 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 14 (1650) seen by opt101? | ✓ PASS | opt101 cannot see 1650 nm; residual +3 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 15 (1760) seen by opt101? | ✓ PASS | opt101 cannot see 1760 nm; residual +5 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 16 (1850) seen by opt101? | ✓ PASS | opt101 cannot see 1850 nm; residual +4 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| opt101: signal electrical only (no light)? | ✓ PASS | 0/11 expected holes show no optical response; coupling small | FAIL when >= 75% of expected holes have O < 40 while \|C\| >= 8 |
| opt101: optical throughput (window, alignment) | ✓ PASS | median O over 11 expected holes; spread (CV) 56% across holes | median O >= 2000 (WARN below), >= 800 (FAIL below) for empty |
| hole 1 (395) seen by ingaas? | ✓ PASS | ingaas cannot see 395 nm; residual +6 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 2 (405) seen by ingaas? | ✓ PASS | ingaas cannot see 405 nm; residual +4 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 3 (blue) seen by ingaas? | ✓ PASS | ingaas cannot see 465 nm; residual +2 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 4 (green) seen by ingaas? | ✓ PASS | ingaas cannot see 525 nm; residual +4 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 5 (yellow) seen by ingaas? | ✓ PASS | ingaas cannot see 590 nm; residual +1 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 6 (orange) seen by ingaas? | ✓ PASS | ingaas cannot see 605 nm; residual +3 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 7 (red) seen by ingaas? | ✓ PASS | ingaas cannot see 630 nm; residual +7 counts over C +1.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 8 (850) on ingaas | ✓ PASS | O 5921 counts at h -316037, C +1.0, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 9 (940) on ingaas | ✓ PASS | O 15090 counts at h -316037, C +1.0, modulation 0.66 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 10 (white) seen by ingaas? | ✓ PASS | ingaas cannot see 450 nm; residual +4 counts over C +2.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 11 (pink) seen by ingaas? | ✓ PASS | ingaas cannot see 450 nm; residual +4 counts over C +2.0 | < 30 counts (WARN), < 80 (FAIL) |
| hole 12 (1450) on ingaas | ✓ PASS | O 8691 counts at h -316037, C +2.0, modulation 0.67 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 13 (1550) on ingaas | ✓ PASS | O 11366 counts at h -316037, C +2.0, modulation 0.67 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 14 (1650) on ingaas | ✓ PASS | O 7522 counts at h -316037, C +2.0, modulation 0.67 | O >= 100 (WARN below), >= 40 (FAIL below) |
| hole 16 (1850) seen by ingaas? | ✓ PASS | ingaas cannot see 1850 nm; residual +10 counts over C +2.0 | < 30 counts (WARN), < 80 (FAIL) |
| ingaas: signal electrical only (no light)? | ✓ PASS | 0/5 expected holes show no optical response; coupling small | FAIL when >= 75% of expected holes have O < 40 while \|C\| >= 8 |
| ingaas: optical throughput (window, alignment) | ✓ PASS | median O over 5 expected holes; spread (CV) 33% across holes | median O >= 3000 (WARN below), >= 1000 (FAIL below) for empty |
| optimum height (all holes) | ✓ PASS | -316037 half-steps (-77.16 mm); weakest normalised response there 0.96 |  |
| opt101: signal-to-noise at the optimum | ✓ PASS | weakest hole 1: 61.5 dB (noise sigma 0.291 mV) | >= 30 dB |
| opt101: saturation headroom | ✓ PASS | highest lit reading 13802 of 29600 counts | >= 10% |
| ingaas: signal-to-noise at the optimum | ✓ PASS | weakest hole 8: 64.2 dB (noise sigma 0.458 mV) | >= 30 dB |
| ingaas: saturation headroom | ✓ PASS | highest lit reading 15427 of 28000 counts | >= 10% |
| opt101: electrical coupling (height-invariant, LED on) | ✓ PASS | rail A: +0.7 counts (+0.08 mV) inferred, rail B: +1.0 counts (+0.12 mV) from 5 blind holes | \|C\| < 8 counts (WARN), < 20 (FAIL) |
| opt101: ground shift (coupling vs rail current) | ✓ PASS | +0.022 counts/mA | \|slope\| < 0.03 mV/mA (WARN), < 0.08 (FAIL) |
| ingaas: electrical coupling (height-invariant, LED on) | ✓ PASS | rail A: +1.0 counts (+0.12 mV) from 7 blind holes, rail B: +2.0 counts (+0.25 mV) from 3 blind holes | \|C\| < 8 counts (WARN), < 20 (FAIL) |
| ingaas: ground shift (coupling vs rail current) | ✓ PASS | +0.041 counts/mA | \|slope\| < 0.03 mV/mA (WARN), < 0.08 (FAIL) |
| opt101: dark offset / leakage | ✓ PASS | +200.1 counts (+25.02 mV) | 0 to 800 counts (thresholds.dark) |
| ingaas: dark offset / leakage | ✓ PASS | +39.8 counts (+4.97 mV); equivalent input current -5.0 nA (Rf 1 MΩ) | -100 to 2000 counts (thresholds.dark) |
| opt101: dark drift over the run | ✓ PASS | -0.08 ± 0.11 mV/h; P4 - P1 -0.10 mV | \|slope\| < 3 mV/h (WARN), < 8 (FAIL) |
| ingaas: dark drift over the run | ✓ PASS | -0.00 ± 0.18 mV/h (+0.0 nA/h); P4 - P1 -0.05 mV | \|slope\| < 3 mV/h (WARN), < 8 (FAIL) |
| opt101: mains hum (coils off) | ✓ PASS | 60/120/180 Hz: 0.090 / 0.085 / 0.094 mV; 12% of the variance at mains harmonics; broadband sigma 0.291 mV | 60 Hz amplitude < 0.3 mV (WARN), < 1 (FAIL); mains fraction < 0.5 |
| ingaas: mains hum (coils off) | ✓ PASS | 60/120/180 Hz: 0.298 / 0.148 / 0.171 mV; 25% of the variance at mains harmonics; broadband sigma 0.458 mV | 60 Hz amplitude < 1 mV (WARN), < 3 (FAIL); mains fraction < 0.5 |
| opt101: coil interference (moving vs coils off) | ✓ PASS | sigma 0.280 mV moving vs 0.291 mV off (firmware has no coils-held state: measured while moving, S0 D2) | ratio < 3 (WARN), < 6 (FAIL) |
| ingaas: coil interference (moving vs coils off) | ✓ PASS | sigma 0.476 mV moving vs 0.458 mV off (firmware has no coils-held state: measured while moving, S0 D2) | ratio < 3 (WARN), < 6 (FAIL) |
| opt101: select-only coupling (MOSFET on, CE low) | ✓ PASS | largest on hole 10: -2.5 counts | < 8 counts (WARN), < 20 (FAIL) |
| ingaas: select-only coupling (MOSFET on, CE low) | ✓ PASS | largest on hole 10: +4.9 counts | < 8 counts (WARN), < 20 (FAIL) |
| opt101: dark vs height (light leak at the shroud) | ✓ PASS | dark at the bottom +0.8 counts (+0.09 mV) vs the top; 0.01% of the median signal | rise < 8 counts (WARN), < 25 (FAIL) |
| ingaas: dark vs height (light leak at the shroud) | ✓ PASS | dark at the bottom +1.9 counts (+0.24 mV) vs the top; 0.02% of the median signal | rise < 8 counts (WARN), < 25 (FAIL) |
| opt101: room-light flicker (120 Hz) | ✓ PASS | 120 Hz amplitude in the dark streams 0.085 mV | < 0.4 mV (WARN), < 1.2 (FAIL) |
| ingaas: room-light flicker (120 Hz) | ✓ PASS | 120 Hz amplitude in the dark streams 0.148 mV | < 0.4 mV (WARN), < 1.2 (FAIL) |
| travel (top to bottom) | ✓ PASS | tracked range 420017 / 420017 half-steps (left / right) (thresholds.motion.travel.range_steps not set: not compared) |  |
| lockstep (firmware positions level after every move) | ✓ PASS | 20 moves; 0 ended with the two sides at different positions (without home sensors only the commanded steps are seen: a side losing steps shows as mech/step_loss) |  |
| settle time after a move (dark-read convergence) | ✓ PASS | median 588 ms, max 589 ms (mechanical wait 300 ms) | max - wait < 500 ms (WARN), < 1500 (FAIL) |
| backlash (down vs up response curves) | ✓ PASS | +390 ± 203 half-steps (+0.095 mm) from 128 readings on 16 channels | < 600 (WARN), < 1500 (FAIL); not flagged within 3 sigma |
| step loss (offset growing over the up pass) | ✓ PASS | the stage falls behind by -780 ± 468 half-steps over a full upward travel (one side losing steps: about twice that on that side, and a tilt) | < 400 (WARN), < 1000 (FAIL); not flagged within 3 sigma |
| stray light | - SKIP | needs a black_cup run (with a white_ptfe reference) |  |
| effectiveness vs reference | - SKIP | needs a reference (baseline) of the same sample |  |
| lid sensitivity | - SKIP | optional operator step (lid ajar at two heights) |  |
| repeatability at the reference heights | - SKIP | no repeated reference visits in this mode (full, fine, repeatability have them) |  |
