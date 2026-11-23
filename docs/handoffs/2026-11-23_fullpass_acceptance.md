# Full-pass sensor-readings acceptance (software-tested candidate)

**Candidate base:** `130dd7707aba36a95f302dd7080ed3403afe6b34` + uncommitted full-pass repairs (this working tree).  
**Status:** offline host software candidate after mandatory counterexample repairs. **NOT** bench-acquisition-qualified, optical-control-qualified, or quantitative-reference-qualified. **NOT** a live-hardware authorization. **M7 deferred.** No push in this session.

**Canonical labels:** D03 = ownership; D04 = OFF. Original M0–M6 from [SENSOR_READINGS_UPGRADE_PLAN.md](../SENSOR_READINGS_UPGRADE_PLAN.md). The earlier [D01–D20 closure](2026-11-23_remediation_d01_d20_closure.md) is historical, **not** acceptance.

## Evidence commands (host)

```bash
cd software/host
export LIO_FULLPASS_TEST_OUT=$(mktemp -d)
ruff check ../..
ruff format --check ../..
python -m mypy
python -m pytest \
  tests/unit/test_fullpass_counterexamples.py \
  tests/unit/test_remediation_d01_d20.py \
  tests/unit/test_ownership.py \
  tests/unit/test_provenance.py \
  tests/unit/test_coupling.py \
  tests/unit/test_uncertainty.py \
  tests/unit/test_acquisition.py \
  tests/unit/test_targets.py \
  tests/unit/test_scan_protocol_cli.py \
  tests/unit/test_baselines_ablation.py -q --tb=line
python -m pytest -m "unit or sim" --lio-sim \
  --results-dir="$LIO_FULLPASS_TEST_OUT/run" -q --tb=line
# optional precision:
python -m pytest tests/unit/test_uncertainty.py::test_predeclared_null_family_coverage_fwer -q
```

**Observed (this candidate):** whole-repo Ruff + format + strict mypy clean; CE/D suites green; FWER 2000-family test green with SciPy; `unit or sim` ≈ **894 passed / ~11 failed / 6 skipped** (remaining failures listed under blockers). Historical scan bytes unchanged under offline analyse (34 files hashed).

## Mandatory counterexamples (CE01–CE14)

| CE | Required behavior | Evidence |
|----|-------------------|----------|
| 1 | Multiline / `@seq` raw refuses on real-path; sim non-emitting garbage allowed | `test_ce01_*` |
| 2 | Constructor must not mutate a live owner's journal | `test_ce02_*` |
| 3 | 50 ms vs active 2000 ms WDT: refuse or lower+admit | `test_ce03_*` |
| 4 | Failed OFF with CE high → uncertain retained | `test_ce04_*` |
| 5 | Height resume gain 2 under gain-1 snapshot → reject before light | `test_ce05_*` |
| 6 | NPZ mutation invalidates saved analysis reuse | `test_ce06_*` |
| 7 | Pilot excluded; production mean 1 not 25.75 | `test_ce07_*` |
| 8 | `--allow-light` ≠ physical confirmation | `test_ce08_*` |
| 9 | Resume retains costs and original deadlines | `test_ce09_*` |
| 10 | Frozen `{12:1,13:5}` not swapped | `test_ce10_*` |
| 11 | Incompatible Rf/assembly/A0 baseline rejected | `test_ce11_*` |
| 12 | H16 opt-in extracts `proxy_unassigned` | `test_ce12_*` |
| 13 | Grouped ablation scores held-out only | `test_ce13_*` |
| 14 | Fine/report share one selection ID | `test_ce14_*` |

## D01–D20 / variant table

| ID | Canonical meaning | Software evidence | Residual |
|----|-------------------|-------------------|----------|
| D01 | Emitting paths reserve/refuse; no raw bypass | CE01, `test_d01_*` | Real serial not exercised |
| D02 | Atomic SWEEP×16 | `test_d02_*` | Bench SWEEP not run |
| D03 | **Ownership** — stale journal cannot erase | CE02, `test_d03_*` | — |
| D04 | **OFF** — cancel-safe; close before release | CE04, `test_d04_*` | — |
| D05 | Conservative WDT-bound pulses; fw-matched means | CE03, `test_d05_*`, `_mean_ms_fw` | Cooperative WDT only; no invented margin |
| D06 | INFO gain; mains apply/readback when supported | `test_d06_*`, CE05 | Boot mains 0 on hardware untested |
| D07 | InGaAs quantity gates; OPT101 preserved | `test_d07_*`, CE11 | A0/Rf bench evidence pending |
| D08–D10 | Seals / identity / NPZ | CE06, `test_d08–d10_*` | — |
| D11 | Validated control needs evidence; h16 proxy | `test_d11_*`, CE12 | — |
| D12 | Fixed-N; no pooling/truncation | `test_d12_*`, CE07 | — |
| D13 | Safe checkpoint; fresh occurrence answers | CE08, `test_d13_*`, protocol_job | — |
| D14 | Pause/heartbeat block MEAS | `test_d14_*` | — |
| D15 | Caps + resume facts/deadlines | CE09, `test_d15_*` | — |
| D16 | Measured pilot → freeze; equal → 3,3 | CE10, `test_d16_*` | — |
| D17 | Shared primary-SWIR selection | CE14, `test_d17_*` | Fine system scan not re-run |
| D18 | Baseline fail-closed; held-out ablation | CE11–13, `test_d18_*` | — |
| D19 | CLI/dashboard offline routes; golden plan/HTTP | `test_d19_*`, `test_golden_*` | Hardware port gated, not live |
| D20 | Suites + M7 refuse; honest docs | this doc + suites | Full 3.10/3.12 wheel matrix not re-run here |

## Original M0–M6 acceptance matrix (software)

| Milestone | Original criterion (short) | Software verdict | Bench / optical / quantitative |
|-----------|----------------------------|------------------|--------------------------------|
| M0 | Provenance, seals, validity, units | **PASS (software)** | Not qualified |
| M1 | One owner; durable exposure; conservative bounds | **PASS (software / fail-closed)** | Not bench-run; cooperative WDT limit |
| M2 | Roles / coupling; unknown C null; h16 proxy | **PASS (software)** | A0/Rf deferred |
| M3 | Fixed-N; pilot exclude; shared-control; Bonferroni; ≥2000 null FWER | **PASS (software)** with SciPy | — |
| M4 | Protocol lifecycle; checkpoints; resume; CLI | **PASS (software offline)** | Not acquisition-qualified |
| M5 | Pilot freeze; one TargetSelection | **PASS (software)** | No motion qualification |
| M6 | Profiles/baselines/ablation/UI integration | **PASS (software offline)** with residual suite fails | Not acquisition-qualified |
| M7 | PGA / STREAM / GLS | **DEFERRED** | Incomplete by design |

## Working commands / migration notes

```bash
# Offline plan — no Device/serial/WAKE
lio scan plan --protocol software/host/src/lio/scan/examples/stationary_targeted_h12.json

# Sim protocol run (SimOperator answers; --allow-light is not a physical confirm)
lio --sim scan run --protocol PROTOCOL.json --allow-light --sample empty --out DIR

# Offline audit/analyse/report (requires --derived-out; never writes into source tree)
lio scan analyse RUN --model qualified-v2 --derived-out DERIVED_ROOT
```

CLI protocol runs now route checkpoints through `ConsoleOperator` / `SimOperator` (`operator_confirm`), not invented `operator_checkpoint_flag=True`. Dashboard protocol answers reject unknown/stale/duplicate occurrence IDs.

## Residual blockers (exact)

1. **No real serial / POWER WAKE / LEDs / motors / firmware** exercised.
2. **Cooperative WDT** is not a proven zero-latency interrupt; host refuses when a finite conservative bound cannot be supported — no invented latency margin; **not** full current-rig M1 bench acceptance.
3. **A0 / Rf / ammeter / optical-block / quantitative reference** remain owner-deferred.
4. **~11 residual `unit or sim` failures** still open on this candidate (fault-matrix / travel-motion / pty-bridge / operator meter / scan report twin paths). Core CE/D/fullpass suites and lint/mypy are green; these residuals block claiming a fully green release matrix.
5. **Full CI matrix** (Python 3.10 **and** 3.12 + coverage gate + isolated wheel installs) not re-asserted end-to-end in this session beyond lint/mypy + listed suites on the active env.
6. **No measured SNR or recovered SWIR/1850 chemistry** claim follows from software completion.
7. First separately authorized bench step remains a short stationary gain-1 repeat protocol — not implied by this document.
