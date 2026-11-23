# LIO diagnostic sweep 20261123-002839_scan_quick

Mode **quick**, sample **empty**, status **INCOMPLETE**

## Verdict: FUNCTIONAL

- warnings: T13.T09, T13.T13

## Subsystem health

| Subsystem | Parts | Health | Reason |
|---|---|---|---|
| Link / firmware | Nano R4, USB, firmware | ✓ OK | 1 checks pass |
| ADC / I²C | ADS1115, software I²C D11/D12 | ✓ OK | 1 checks pass |
| Shift registers | U1, U2 | - n/a | not measured: no optical response to compare |
| LED drivers / rails | DRV1 (RAIL A), DRV2 (RAIL B) | - n/a | not measured:  |
| LED / MOSFET channels | LED1-16, Q1-16 | - n/a | not measured:  |
| OPT101 | OPT101 (A1) | - n/a | not measured: no blind channels measured; needs hum records, coils off and moving; no dark frames; no select-only readings; under 5 min of dark frames: too short for a drift estimate |
| InGaAs TIA | D1, U5, Rf, Cf (A0) | - n/a | not measured: no blind channels measured; needs hum records, coils off and moving; no dark frames; no select-only readings; under 5 min of dark frames: too short for a drift estimate |
| Motors / lead screws | M1, M2, ULN2003, couplers, M6 rods | ! WATCH | mech/travel: tracked range 268806 / 406532 half-steps (M1/right / M2/left): the two sides differ (thresholds.motion.travel.range_steps not set: not compared) |
| Stage tracking | lio.stage, soft limits | ✓ OK | 1 checks pass |
| Safety | interlocks, duty budget | ✓ OK | 1 checks pass |
| Power / earthing | supplies, GND, earth bond | - n/a | not measured: no hum records; A2/A3 not wired for rail and ground monitoring |
| Optical path / ambient | window, shroud, lid, sample | ✓ OK | 1 checks pass |
| Run | the scan itself | ! WATCH | system/run: INCOMPLETE: All off pressed |

## Findings to act on

### ! WARN `system/run`: run complete

INCOMPLETE: All off pressed

- **Why:** The run did not complete: metrics needing the missing steps are SKIP.
- **Parts:** run
- **Next check:** See the abort reason; 'lio scan resume <run>' carries on from the next step.

### ! WARN `mech/travel`: travel (top to bottom)

tracked range 268806 / 406532 half-steps (M1/right / M2/left): the two sides differ (thresholds.motion.travel.range_steps not set: not compared)

- **Why:** The tracked travel differs from the configured one (or between the sides).
- **Parts:** stage limits
- **Next check:** Re-mark the top and bottom.

## System

| Status | Metric | Value | Result | Criterion |
|---|---|---|---|---|
| ✓ PASS | `system/link` | 0 unexpected boots | firmware 2.5.2, no unexpected # BOOT |  |
| ✓ PASS | `system/adc` | 0 readings | 0 readings, no dropout |  |
| - SKIP | `system/addressing` |  | no optical response to compare |  |
| - SKIP | `system/interlocks` |  | P4 not reached |  |
| ✓ PASS | `system/duty` | 0 ms/min | max 0 ms of 1000 ms; 0 cool-down waits, 0 s in all |  |
| ✓ PASS | `system/stage` |  | position [-16384, -16384], limits respected |  |
| ! WARN | `system/run` |  | INCOMPLETE: All off pressed |  |

## Optics

| Status | Metric | Value | Result | Criterion |
|---|---|---|---|---|
| - SKIP | `optics/curves` |  | no down pass in this mode (no height data) |  |

## Electrical

| Status | Metric | Value | Result | Criterion |
|---|---|---|---|---|
| - SKIP | `elec/opt101/coupling` |  | no blind channels measured |  |
| - SKIP | `elec/ingaas/coupling` |  | no blind channels measured |  |
| - SKIP | `elec/opt101/dark_offset` |  | no dark frames |  |
| - SKIP | `elec/ingaas/dark_offset` |  | no dark frames |  |
| - SKIP | `elec/opt101/drift` |  | under 5 min of dark frames: too short for a drift estimate |  |
| - SKIP | `elec/ingaas/drift` |  | under 5 min of dark frames: too short for a drift estimate |  |
| - SKIP | `elec/opt101/hum` |  | no hum records |  |
| - SKIP | `elec/ingaas/hum` |  | no hum records |  |
| - SKIP | `elec/opt101/coil_emi` |  | needs hum records, coils off and moving |  |
| - SKIP | `elec/ingaas/coil_emi` |  | needs hum records, coils off and moving |  |
| - SKIP | `elec/opt101/select_only` |  | no select-only readings |  |
| - SKIP | `elec/ingaas/select_only` |  | no select-only readings |  |
| - SKIP | `elec/rails` |  | A2/A3 not wired for rail and ground monitoring |  |

## Mechanics

| Status | Metric | Value | Result | Criterion |
|---|---|---|---|---|
| - SKIP | `mech/home_sensors` |  | no home sensors fitted |  |
| ! WARN | `mech/travel` | 268806 half-steps | tracked range 268806 / 406532 half-steps (M1/right / M2/left): the two sides differ (thresholds.motion.travel.range_steps not set: not compared) |  |
| ✓ PASS | `mech/lockstep` | 0 moves | 0 moves; 0 ended with the two sides at different positions (without home sensors only the commanded steps are seen: a side losing steps shows as mech/step_loss) |  |
| - SKIP | `mech/settle` |  | no settle records |  |
| - SKIP | `mech/backlash` |  | no down-pass reference curves (static or continuous mode, or no strong channel) |  |
| - SKIP | `mech/step_loss` |  | no down-pass reference curves (static or continuous mode, or no strong channel) |  |
| - SKIP | `mech/repeatability` |  | no down-pass reference curves (static or continuous mode, or no strong channel) |  |

## Ambient

| Status | Metric | Value | Result | Criterion |
|---|---|---|---|---|
| - SKIP | `ambient/opt101/leak` |  | needs dark frames at 4+ heights |  |
| - SKIP | `ambient/ingaas/leak` |  | needs dark frames at 4+ heights |  |
| - SKIP | `ambient/opt101/flicker` |  | no dark streams |  |
| - SKIP | `ambient/ingaas/flicker` |  | no dark streams |  |
| - SKIP | `ambient/lid` |  | optional operator step (lid ajar at two heights) |  |

## Trend

| Status | Metric | Value | Result | Criterion |
|---|---|---|---|---|
| ✓ PASS | `trend/compare` | 1 x (furthest per-hole ratio) | no change beyond the band | per-hole ratio within ±0.1 (WARN), ±0.25 (FAIL) |
| - SKIP | `trend/control` |  | needs 5 baselines of empty (have 1) |  |

## Not measured (capability)

- rail_monitor: A2/A3 not wired for rail and ground monitoring
- home_sensors: no home sensors fitted
