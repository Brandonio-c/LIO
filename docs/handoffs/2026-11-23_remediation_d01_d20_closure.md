# D01–D20 remediation closure (software-tested)

**Status:** Historical R0–R8 offline evidence. **This document is NOT acceptance.** Prefer [2026-11-23_fullpass_acceptance.md](2026-11-23_fullpass_acceptance.md) for the software-tested candidate matrix (canonical D03=ownership, D04=OFF; original M0–M6). **Not** bench-acquisition-qualified, optical-control-qualified, or quantitative-reference-qualified. **M7 deferred.** No push.

**Evidence command (host):**

```bash
cd software/host && python -m pytest \
  tests/unit/test_remediation_d01_d20.py \
  tests/unit/test_acquisition.py \
  tests/unit/test_targets.py \
  tests/unit/test_scan_protocol_cli.py \
  tests/unit/test_baselines_ablation.py \
  tests/unit/test_m7_gain.py -q --tb=line
ruff check src/lio/scan/acquisition.py src/lio/scan/executor.py src/lio/scan/derived.py \
  src/lio/scan/m7_gain.py src/lio/device.py src/lio/cli.py \
  src/lio/dashboard/protocol_job.py src/lio/dashboard/session.py src/lio/dashboard/server.py \
  src/lio/food_profiles/features.py src/lio/food_profiles/ablation.py src/lio/food_profiles/baselines.py
```

Result at closure: **68 passed**; touched-module ruff clean.

## D01–D20 closure table

| ID | Repair | Passing evidence | Unresolved limits |
|----|--------|------------------|-------------------|
| D01 | Duty journal on all emit paths; budget=False cannot strip accounting | `test_d01_*` | Real serial not exercised |
| D02 | SWEEP atomic 16-hole reserve | `test_d02_*` | Bench SWEEP not run |
| D03 | Cancel clears without inventing OFF ownership | `test_d03_*` | — |
| D04 | Multi-pending journal + reload under lease | `test_d04_*` | — |
| D05 | Timing capability + WDT-bound pulses; MEAS est includes +10 | `test_d05_*`, sim MEAS via D19 | Cooperative WDT only |
| D06 | INFO `gain`; mains apply/readback before MEAS | `test_d06_*` | Boot mains 0 on hardware untested |
| D07 | InGaAs quantity gates; OPT101 preserved | `test_d07_*`, `test_d10_*` | A0/Rf bench evidence pending |
| D08–D10 | Provenance seals / derived identity | remediation + provenance units | — |
| D11 | Validated control needs optical evidence; h16 proxy forever | `test_d11_*` | — |
| D12 | Fixed-N; no height pooling; unequal shared-control refuse | `test_d12_*` | — |
| D13 | Safe-state before checkpoint; fresh occurrence answers; flag ≠ step | `test_d13_*` | Interactive dashboard prompt UX thin |
| D14 | Pause/heartbeat block MEAS; abort responsive | `test_d14_*` | — |
| D15 | Cumulative total/cycle/wall; 300 under 200 incomplete; resume facts | `test_d15_*` | Cycle-cap path covered in runner; dedicated cycle unit light |
| D16 | Measured pilot → production_freeze; equal costs → 3,3 | `test_d16_*` | — |
| D17 | Shared primary-SWIR selection; h16 cannot steer | `test_d17_*`, `test_targets` | Fine-mode system scan not re-run |
| D18 | Baseline fail-closed; h16 opt-in; honest ablation names | `test_d18_*`, baselines/ablation | Grouped held-out needs labelled groups |
| D19 | CLI sim protocol + resume routing; numerical/saved views | `test_d19_*` | Hardware port path gated, not live |
| D20 | Suites green; M7 missing-readback refuse; honest docs | `test_d20_*`, this table | Full CI matrix / coverage gate not re-asserted here |

## M0–M6 acceptance matrix (software evidence)

| Milestone | Criterion (short) | Software evidence | Bench / optical / quantitative |
|-----------|-------------------|-------------------|--------------------------------|
| M0 | Honest status + regression harness | D01–D20 tests; project-state | Not qualified |
| M1 | Exposure/ownership | D01–D05 | Not bench-run |
| M2 | Acquisition facts / seals | D06, D08–D10 | — |
| M3 | Quantity / control semantics | D07, D11 | A0/Rf deferred |
| M4 | Fixed-N estimator | D12 | — |
| M5 | Targeting / scout | D17, targets units | No motion qualification |
| M6 | Protocol lifecycle / profiles | D13–D16, D18–D19 | Not acquisition-qualified |
| M7 | PGA / STREAM / GLS | **Deferred**; missing readback refuse | Incomplete by design |

## Unresolved capability / bench limits

- No real serial, POWER WAKE, LEDs, motors, or firmware changes in this work.
- Not bench-acquisition-qualified; first stationary gain-1 repeat remains owner-deferred.
- A0 operating-range, fitted Rf/Cf, optical-block controls, and quantitative reference remain owner-deferred.
- Full Ruff/mypy/CI matrix across 3.10/3.12 and coverage gate: touched modules cleaned; some pre-existing `src/lio/` lint may remain outside remediation paths.
- No measured SNR or recovered SWIR/1850 chemistry claim follows from software completion.
