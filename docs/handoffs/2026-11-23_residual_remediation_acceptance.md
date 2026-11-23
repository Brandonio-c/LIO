# Residual sensor-readings remediation acceptance

**Prepared:** 23 November 2026  
**Base:** `944a820d2287b6677a0d0fde017b40bbbaff87f6` + residual caller-level repairs (this commit).  
**Status:** offline host software candidate **plus** one automatic live-host catalogue run. **NOT** bench-acquisition-qualified, optical-control-qualified, or quantitative-reference-qualified. **M7 deferred.** No measured SNR or recovered SWIR/1850 chemistry claim.

**Canonical labels:** D03 = ownership; D04 = OFF. Original M0–M6 from [SENSOR_READINGS_UPGRADE_PLAN.md](../SENSOR_READINGS_UPGRADE_PLAN.md). Prior closure/PASS tables are hypotheses unless re-proven here.

## What changed (residual)

1. **Ownership / exposure:** constructors defer journal load until lease (`defer_load`); incomplete/CR/cross-call raw fragments refused; `@seq` allowed only for non-emitting bodies; CE firmware refuse uses `drop_pending` (no 60 s uncertain lock); crash paths still `abort_conservative`; T10.2 uses admitted `ch_on` / `command` (no production `_command_unguarded` CH); T10.4 accepts host refuse for multi-select; T02.4 probes the gate on Serial/PTY (sim harness keeps firmware ERR injection).
2. **Duty multi-charge:** `wait_needed_many` so SWEEP×16 same-rail siblings cool instead of ERROR with `wait=0`.
3. **TEN maintained failures:** meter keys use configured A4/B10; short drift → SKIP + ≥300 s synthetic controls; PTY catalogue owned refuse path; T13 `…/A/rail` paints twin rails (T10 does not); travel fixtures respect margin 16384; saturation WARN under FUNCTIONAL policy.
4. **Mandatory residual CEs:** fragmented `send_raw(b'C')` then `H 1 ON…`; second device constructor vs live pending journal; T10.2 static admission check.

## Offline software evidence

```bash
cd /path/to/LIO
ruff check .
ruff format --check .
cd software/host
export LIO_REMEDIATION_TEST_OUT=$(mktemp -d)
export LIO_STATE_ROOT="$LIO_REMEDIATION_TEST_OUT/state"
export COVERAGE_FILE="$LIO_REMEDIATION_TEST_OUT/.coverage"
python -m mypy
python -m pytest tests/unit/test_fullpass_counterexamples.py tests/unit/test_remediation_d01_d20.py -q
python -m pytest -m "unit or sim" --lio-sim \
  --results-dir="$LIO_REMEDIATION_TEST_OUT/run" \
  --cov=lio --cov-report=term \
  --cov-report="xml:$LIO_REMEDIATION_TEST_OUT/coverage.xml"
coverage report --include="*/lio/protocol.py,*/lio/analysis.py" --fail-under=90
```

**Observed (Python 3.12.11, lio 0.2.0, SciPy 1.18.1):** Ruff + format + strict mypy clean; CE/D suites green; `unit or sim` **912 passed / 0 failed / 6 skipped**; protocol/analysis coverage gate **98%**.

## TEN maintained failures — disposition

| Case | Disposition |
|------|-------------|
| Meter h08/h12 | Expect configured `interactive.meter_holes` A→h04, B→h10; wrong-reading FAIL preserved |
| Drift short | SKIP preserved; `test_scan_drift_*_long_dark` ≥300 s healthy PASS / fault WARN\|FAIL |
| PTY catalogue | Light-capable malformed probes refuse on Serial; sim keeps ERR injection; wall budget 120 s |
| T13 twin rails | `twin.parts` accepts T13 `…/rail` evidence; T10 excluded |
| Travel 1500 | SKIP when margin consumes range; positive tests use `2*margin+4096` |
| Long travel | Assert near `range-margin` (~13616), not >25000 |
| Saturation | WARN detected; global FUNCTIONAL (WARN-only policy); quantitative gates separate |

## CE / D variants (caller evidence)

| ID | Actual caller / test | Result |
|----|----------------------|--------|
| CE01 / D01.fragments | `send_raw` fragment + multiline / light | PASS |
| CE02 / D03 | second journal/device vs live pending | PASS |
| CE03 / D05 | WDT 2000 vs reserved 50 | PASS |
| CE04 / D04 | failed OFF / CE high uncertainty; CE drop_pending on refuse | PASS |
| D01.t10 | T10.2 admitted CH only | PASS |
| CE06–CE14 | NPZ / pilot mean / timeout / freeze / baseline / h16 / ablation / selection | PASS (existing fullpass) |

## Original M0–M6 (software)

| Milestone | Software verdict | Physical / current-rig |
|-----------|------------------|------------------------|
| M0 provenance/units | **PASS (software)** | Not qualified |
| M1 ownership/durable exposure | **PASS (software / fail-closed)** | Cooperative WDT ≠ wall ceiling; **no invented margin**; T10.2 SKIPs when default WDT exceeds duty budget → **M1 current-rig operational admission blocked** for unrestricted watchdog pulses |
| M2 roles/coupling | **PASS (software)** | A0/Rf deferred |
| M3 fixed-N | **PASS (software)** with SciPy | — |
| M4 stationary/pilot lifecycle | **PASS (software offline)** | Not acquisition-qualified |
| M5 shared selection | **PASS (software)** | No motion qualification |
| M6 workflow/release | **PASS (software offline)** on 3.12 candidate | Dual 3.10 CI / wheel matrix not re-run here |
| M7 | **DEFERRED** | Incomplete by design |

## Live hardware run (2026-11-23)

**Port:** `/dev/cu.usbmodem101` · **fw** 2.5.2 · **adc_ok** 1 · **gain** 1  
**Command:** `lio --port /dev/cu.usbmodem101 selftest --sample-id none-empty-chamber --operator residual-remediation`  
**Report:** [test_results/20261123-135504_host_residual_hw/](../../test_results/20261123-135504_host_residual_hw/)  
**Scope:** automatic catalogue only (no `--interactive`, no `--allow-motion`).

| Area | Result |
|------|--------|
| Link / env / SR / timing / SWEEP / safety (T01–T02, T04, T07–T08, T10.1/3/4/5) | PASS |
| T10.2 watchdog | **SKIP** — RAIL A default WDT 2000 ms exceeds 1000 ms/min duty budget; no unguarded bypass |
| T03.2 InGaAs dark | **FAIL** — A0 mean ≈ −331, σ ≈ 37 counts |
| T05/T06.3 InGaAs optical response (h8/h9/h12–h14) | **FAIL** — little/no net InGaAs |
| T06.1 OPT101 / T06.2 InGaAs TIA polarity | PASS |
| Overall | **NOT FUNCTIONAL** (critical T03.2 + >2 channel fails) |

**Host fixes confirmed on this run:** `wait_needed_many` (SWEEP no longer ERROR), T10.2 budget SKIP, CE refuse `drop_pending` (no suite-wide uncertain lock).

**Spot MEAS (typed, duty-gated):**

| Hole | opt101 net | ingaas net |
|------|------------|------------|
| 4 (green) | ≈56 | ≈3 |
| 8 (850) | ≈171 | ≈30 |
| 12 (1450) | ≈12 | ≈13 |
| 13 (1550) | ≈2 | ≈5 |
| dark | opt101 ≈59 ±0.4 | ingaas ≈−331 ±37 |

## Residual blockers (exact)

1. **Optical / InGaAs path on the current rig is NOT FUNCTIONAL** (dark noise + missing SWIR response). Matches prior research quick-scan posture; not a software-gate miss.
2. **M1 current-rig:** cooperative WDT alone is not a wall-clock ceiling; T10.2 correctly SKIPs when default WDT exceeds duty budget — no invented margin.
3. A0 / Rf / ammeter / optical-block / quantitative reference remain owner-deferred.
4. Interactive (T05.6 meter) and motion (T09/T13) not yet run on this reconnect.
5. Python 3.10 dual CI matrix not available in this environment.
6. No measured SNR or recovered SWIR/1850 chemistry claim.

## Working syntax

```bash
lio scan plan --protocol software/host/src/lio/scan/examples/stationary_targeted_h12.json
lio --sim scan run --protocol PROTOCOL.json --allow-light --sample empty --out DIR
lio scan analyse RUN --model qualified-v2 --derived-out DERIVED_ROOT
lio --port /dev/cu.usbmodem101 selftest --sample-id none-empty-chamber --operator <name>
```

`--allow-light` is not a physical confirmation. Plan constructs no Device/serial and calls no WAKE/ARM.
