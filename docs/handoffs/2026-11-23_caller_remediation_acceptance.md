# Caller remediation: acceptance evidence (23 November 2026)

**Base:** `c4d3b67` (caller-remediation handoff) on top of `a0935fb`.
**Candidate:** `8cdfd0f` (remediation) + `f78c6b6` (scan closing-check fix found live) +
`2212d1b` (exposure_bound in run records) + `7f080ea` (MEAS BUSY release, journaled abort
reasons; found live) + the documentation/archive commit that adds this file. Main only.
**Scope followed:** [caller remediation plan](../SENSOR_READINGS_CALLER_REMEDIATION_PLAN.md),
[regression catalogue](../research/LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md),
[independent audit](../research/LIO_V3_RESIDUAL_REMEDIATION_QA_a0935fb_2026-11-23.md).
Canonical IDs kept: **D03 = ownership, D04 = OFF**; original M0–M6 definitions unchanged.

This is an implementer's record. Treat each PASS below as a claim to re-check; a test
PASS proves only the behaviour that test executes.

## 1. Owner decisions recorded during this session

| Decision | Where it lives | Effect |
|---|---|---|
| Real-port LED admission without a hardware watchdog | `lio_hw.yaml` `timing.real_port_admission: cooperative_unproven_acknowledged` | Code default is **refuse**. The rig reports `hw_wdt=0` and the firmware hardware-watchdog option is AVR-only (the rig is a Nano R4), so no finite bound on a firmware hang exists. The owner accepted the cooperative watchdog *without* a proven hang bound. Runs record `exposure_bound=cooperative_unproven`. **Current-rig M1 therefore stays blocked.** No timing margin was invented. |
| One start confirmation for suite/scan setup facts | Dashboard `PreflightOperator` (owner request, 18 Nov) | Chamber clear, lid closed, earth bond and sample are answered by the owner in the start dialog for that run. In-run checkpoints (protocol optical blocks etc.) still need their own fresh occurrence answer. |
| Live scope | Owner answers 23 Nov | Automatic catalogue, motor tests + height scan, stationary capture with pause/abort/resume. Bench steps (walk test, meter, lid) **not authorised** this session. Sample `empty`, lid closed, chamber clear, earth bond connected (owner answers). |

## 2. Actual-caller regressions A01–A24

Maintained tests: `software/host/tests/unit/test_caller_regressions_{device,saved,workflow,science}.py`
(60 tests). Device cases run the **managed serial branch** (`FakeSerial` subclasses
`SerialTransport`; only OS I/O is delegated to the simulator; physical serial opens are
trapped). Saved-data cases go through `ScanStore.append_rows`/`rows`, `Cube`, the derived
readers and the real `lio` CLI `main`; historical runs are only copied (originals hashed
before/after).

| ID | Contract | Repair (actual caller) | Status |
|---|---|---|---|
| A01 / D01 | `@123\tCH 1 ON` | Firmware-exact tokenizer (CR dropped, spaces+tabs, any `@` first token) in the raw gate; no write at all | **Closed** (6 payloads + positive controls) |
| A02 / D03 | Failed open leaks lease | `open()` cleans up journal reload/parse/recovery, transport and first wake failures; aliases resolve (realpath + tty/cu); fresh owner generation per lease; stale completions refused; clock discontinuity carries charges forward (macOS boot id via `kern.boottime`) | **Closed** |
| A03 / D04 | CE ACK + contradictory STATUS | Reservation released only on `ERR code=3` **and** STATUS CE-low; contradictory/unknown keeps full charge, journal uncertain, light blocked until verified OFF | **Closed** |
| A04–A06 / D12 | Pilot pooled, NaN heights, identities dropped | Cube identity columns (operation/reading/block/attempt/condition/setting/segment/position_instance); reader uses `ScanStore.rows()`; pilot excluded; unknown stationary position grouped by one run-local instance; legacy cubes keep their header and refuse silent identity loss | **Closed** (1, N=3) |
| A07 / D08, CE06 | NPZ change not detected by `open_run` | Live stream hashes always supplied; terminal seal re-verified | **Closed** |
| A08 / D08 | Minimal identity verified | Complete identity required (cube, scan, calibration, channel map, estimator, coupling model, consumed streams, run id) | **Closed** |
| A09 / D09 | Derived output inside run (incl. symlink) | Canonical containment check before and at write; bare in-run rewrites need `--rewrite-legacy` | **Closed** |
| A10 / D08, D19 | Report for run B with run A's product | Product looked up under the requested run only and verified against live sources | **Closed** |
| A11 / D10 | Reinterpretation keeps seal | Seal includes stream catalogue, cube schema, mux map, channel-map/config hashes; `verify_store_seal` | **Closed** |
| A12 / M0, D06 | Snapshot mutable via caller dict | Deep-copied, canonical bytes frozen at construction | **Closed** |
| A13 / D04 | Post-emission OFF failure → SKIP | `light_sends` counter: pre-transmission refusal = SKIP, after transmission = FAIL + safe_off, no further emission | **Closed** |
| A14 / D15, CE09 | Timeout after MEAS costs 0 | Run cost reserved and persisted **before** send; failure adds the device's conservative charge as uncertain | **Closed** |
| A15 / D16, CE10 | Resume swaps frozen schedule | Resume executes the hash-checked frozen ordered steps only and validates durable records step by step | **Closed** |
| A16 / D13 | `"false"` confirms; start flag answers first prompt | Strict JSON Boolean at HTTP, session and job; every occurrence needs its own answer | **Closed** |
| A17 / D14 | Self-heartbeat; prompt overruns cap; clock reset grants time | No worker beat; persistent `RunClock` (pause/prompt/downtime counted, discontinuity expires); limits re-checked right before each MEAS | **Closed** |
| A18 / D06, CE05 | Gain-2 snapshot resumes; mains readback missing | `core_adc_preflight` on start and resume for protocol and height scan: gain read back as 1, mains applied and read back | **Closed** |
| A19 / D07, D18, CE11 | O-envelope / matched ratio with unknown A0/Rf; baseline facts dropped | InGaAs O-envelope cells excluded unless frozen A0 range verified and Rf known; matched ratio needs known Rf for InGaAs; baseline adapter carries Rf/assembly/A0 facts | **Closed for these consumers** (OPT101 and raw counts unaffected) |
| A20 / D11 | Bare `{8}` validates controls; covariance stub | `ControlEvidence` (run, load, condition, setting, calibration, assembly epoch, method) required and must apply to the run; real between-reading variance / n, None below two readings | **Closed** |
| A21 / D17, CE14 | Qualified product omits shared selection; no fresh confirmation | — | **OPEN** (not implemented) |
| A22 / D18, CE12–13 | h16 proxy opt-in/grouped held-out through batch/CLI | Extraction API still works; batch/CLI opt-in and grouped evaluation not wired | **OPEN** |
| A23 / D05 | Wrong ACK/readback, unsupported profile, wrong reply accepted | WDT ACK `rail`/`ms` + INFO readback must equal the request; CH/MEAS/SWEEP/DBG replies validated (word, hole, rail, settings, counts); wrong-rail DBG bounded by the energized rail; real port without supported bound refused | **Closed** |
| A24 / D02, D04 | SWEEP 800→384 ms refund; safe_off ERR clears accounting | SWEEP and STREAM keep the full reserved bound anchored at the reply; OFF/safe_off release only after `OK OFF` + STATUS CE-low | **Closed** |

Positive controls from the catalogue are kept (literal fragment refusal, constructor
deferral, known wrong-rail refusal, admitted T10 pulses, whole-set cooldown, n=2 and
mains paths, negative console answers, same-boot expiry, C=null, h16 proxy extraction,
offline protocol plan without device). Existing CE/D suites stay green.

**Not done (honest list):** A21, A22; the paired/shared-control/frozen-family statistics
are not wired into the production qualified path (D12 beyond the reader fix); measured
allocation and fresh-confirmation acquisition (D16/D17 beyond exact resume); real browser
rendering of numerical/control UI (D19); wheel-outside-checkout and isolated extras
installs; precision (SciPy) tests on 3.10 (SciPy not installed there).

## 3. Offline release evidence

| Check | Result |
|---|---|
| `ruff check .` / `ruff format --check .` (repo root, ruff 0.15.4) | Pass / 201 files formatted |
| `mypy` strict, Python 3.12.11 (mypy 2.4.1) | No issues, 125 files |
| `mypy` strict, Python 3.10.18 (mypy 2.4.1, NumPy 2.2.6) | No issues after replacing a NumPy-version-sensitive `type: ignore` in `food_profiles/distances.py` |
| `pytest -m "unit or sim" --lio-sim`, Python 3.12.11 (NumPy 2.5.4, SciPy 1.18.1) | **969 passed, 0 failed, 6 skipped** (on `8cdfd0f` minus one test-fixture update) |
| Same with `--cov`, Python 3.10.18 | **960 passed, 0 failed, 15 skipped**; skips: scikit-learn, zxing, SciPy (precision) not installed, plus the 6 simulator skips |
| Coverage gate `protocol.py,analysis.py ≥ 90 %` (3.10 run) | **98 %**, exit 0 |
| Offline protocol plan (`lio scan plan --protocol …`) while the dashboard owned the port | Planned 6 steps without opening the port |
| Re-run on the pushed tip `b5b8822`, Python 3.12, with coverage | **971 passed, 1 failed, 6 skipped**; gate 98 %. The failure, `test_fullpass_counterexamples.py::test_golden_dashboard_http_plan_numerical_answer` (real HTTP server), passed 6/6 when run alone, with and without coverage. Its failure output was not captured, so the cause is **unidentified**; treat it as an open intermittent failure, not a pass. |

Skips are recorded, not counted as passes. Historical runs used by the saved-data tests
were hashed before/after by a module fixture; unchanged.

Found and **not fixed**: simulator system tests rebase the local, ignored
`test_results/stage_position.json` (values unchanged, `updated` and log entries added).
Test isolation should give them their own stage file.

## 4. Live hardware evidence

Rig: Nano R4 on `/dev/cu.usbmodem101`, firmware 2.5.2 (`hw_wdt=0`, `rail_b_first=9`,
gain 1, rate 128). The long-running dashboard (old code, up since 21 Nov) was stopped
gracefully with the owner's permission and restarted on the candidate. Duty journal:
the existing per-rig journal (not replaced). Stage tracker: valid, top at the
light-tight position; recorded bottoms are **not level** (M1 −286 884, M2 −429 461).

### 4.1 Full catalogue, automatic + motion — `test_results/20261123-162705_host`

16:27–16:58 EST, candidate `8cdfd0f`. **NOT FUNCTIONAL**: 31 PASS, 1 WARN, 6 FAIL, 6 SKIP, 1 ERROR.

| Test | Result | Reading |
|---|---|---|
| T03.2 | FAIL | InGaAs A0 mean −331.2, σ 37.47 counts (n=64), limit σ ≤ 20. Same as the archived 23 Nov run (σ 37.22). Cause unresolved. |
| T05.1 | FAIL | h12 InGaAs below detection with CE2 high |
| T05.2 / T05.3 | FAIL | InGaAs nets h8 +23, h9 +42, h12 +22, h13 +8, h14 +1 (h15 WARN +1) against the detection threshold |
| T06.3 | FAIL | h8/h9 not seen by the InGaAs |
| T07.1 | WARN | h13 InGaAs shows no step |
| T08.3 | FAIL | h9 OPT101: sweep 102 vs MEAS 117 (12.6 %) — new vs earlier runs; h9 has a history of intermittency |
| T09.1–T09.4 | PASS | arming, both directions, stop latency, noise while moving (operator "saw it move" checks recorded SKIP: unattended start) |
| T09.6 / T09.7 | SKIP | tracked bottoms not level; refused before motion |
| T10.1, T10.3–T10.5 | PASS | |
| T10.2 | SKIP | both rails refused **before transmission** (A 2000 ms / h9 5000 ms default WDT vs 1000 ms budgets) — no watchdog cut-off observed |
| T04.2/T04.3/T11.1 | SKIP | no loopback jumper / delegated / no baseline |
| T13.1 | ERROR | the height scan reached its closing checks (step 18 of 19) and the managed port refused an ambiguous-mask CE before transmission; the scan did not expect that error. Fixed in `f78c6b6`; see 4.2. |

Every T10.2 and closing-check refusal happened before any light command was written
(the device's `light_sends` counter did not move).

### 4.2 Height scan re-runs

- `20261123-170350_host` / `20261123-170352_scan_quick` (17:03–17:29): **invalid as a fix
  test.** The dashboard restart had not taken effect (the old process ignored SIGINT as a
  background job; the new one could not bind and exited), so this ran `8cdfd0f` again and
  failed identically. Archived as recorded; the restart procedure is now: `POST
  /api/disconnect` (OFF/STOP, port released), SIGTERM, then verify the new PID.
- `20261123-173106_host` / `20261123-173108_scan_quick` (17:31–17:56, `f78c6b6`, verified new
  process): scan **COMPLETE**, terminal seal written, core preflight gain 1 / rate 128 /
  mains 60 read back, closing interlocks `light_while_moving: PASS`, `single_channel: SKIP:
  host refused before transmission; firmware interlock not exercised`. Run record
  `exposure_bound=cooperative_unproven`. Measured outcome **NOT FUNCTIONAL** (T13.1 FAIL:
  91 PASS, 8 WARN, 6 SKIP, 4 FAIL sub-results): InGaAs h13/h14 no height-dependent response,
  InGaAs throughput CV 136 %, InGaAs 60 Hz hum 9.5 mV.

The light-while-moving check's ERR code 5 had marked the journal uncertain (no reason
recorded); the next protocol start was then refused before light. Firmware `do_meas`
returns BUSY before any light, so `7f080ea` releases that reservation only when STATUS
shows both CE lines low, and journals the reason for every conservative abort.

### 4.3 Stationary capture → persist → analyse → report, with pause/abort/resume

Protocol: holes 8 and 12, InGaAs + OPT101, one unblocked condition, settle 8 ms, 2 mains
periods, equal fixed allocation, no checkpoints (`test_results/derived_caller_acceptance/
live_protocols/`). Driven through the dashboard HTTP API by a script acting as the page
(heartbeat every 3 s; it never answered any checkpoint).

| Run | What happened |
|---|---|
| `20261123-175731_scan_protocol` | Start at 17:57 **refused at the first MEAS before transmission** (journal cooldown from 4.2). Resumed at 18:07 (dashboard on `2212d1b`): resume validated the durable records against the frozen schedule, core preflight repeated, **COMPLETE** 6 steps. Budget: reserved 644 ms, actual 504 ms, uncertain 92 ms (the refused attempt was booked as uncertain although nothing was sent: safe but over-conservative), elapsed 614.8 s including downtime. |
| `20261123-180942_scan_protocol` (dashboard on `7f080ea`, PID verified) | Pause after step 2: held at 3 completed steps for >5 s with no MEAS. Unpause + abort: **INCOMPLETE `cancelled`** after 6 steps. Resume: **COMPLETE**, 24 rows (6 per hole × detector), steps 0–11 contiguous, 12 readings, one position instance; budget reserved 1104 ms, actual 1008 ms, uncertain 0. |

Offline products (`lio scan analyse … --model qualified-v2 --derived-out
test_results/derived_caller_acceptance`, `lio scan report … --analysis ID`), source run
hashed before/after: **unchanged**. Software identity in the product: `7f080ea`, clean.
Fixed-N production estimates (N=3 per hole, run 175731): InGaAs h8 +29, h12 +2; OPT101 h8
+154.7, h12 −8 counts. These are software products of a NOT FUNCTIONAL optical path, not
qualified measurements.

Operator answers used for every live run: owner (this session) — chamber empty and clear,
lid closed, earth bond connected. Bench-step sections (T04.4, T05.6, T06.4) were **not
run** (not authorised this session).

## 5. ORIGINAL M0–M6

| Milestone | Software | Current rig |
|---|---|---|
| M0 provenance/units/compatibility | **Substantially met for the repaired consumers** (frozen snapshot, complete identity, live-source reuse checks, seal interpretation, containment). Not every consumer audited (A21/A22 consumers open). | A0/Rf/geometry facts deferred |
| M1 one owner, bounded durable exposure | **Software contracts met for the audited paths** (A01–A03, A13, A14, A23, A24, D03 recovery). | **Blocked**: no hardware watchdog; owner-acknowledged unproven cooperative bound; T10.2 never observed a cut-off |
| M2 roles/coupling | **Partial**: scoped control evidence and real control-estimator variance; joint target/control covariance not propagated into qualified estimates | — |
| M3 fixed-N signed estimates | **Partial**: saved reader identities/pilot exclusion fixed; paired/shared-control/family pathway not connected in production | — |
| M4 stationary execution/allocation | **Partial**: permanent budgets, deadlines, operator answers, exact resume fixed; measured allocation beyond the frozen schedule not re-audited | Live: capture, pause, abort, resume work (4.3); optical path NOT FUNCTIONAL |
| M5 shared selection + fresh confirmation | **Not met** (A21 open) | — |
| M6 CLI/dashboard/report/profile/release | **Partial**: 3.10 + 3.12 matrix green; A22, browser rendering, wheel/extras isolation not done | — |
| M7 | Deferred, isolation preserved | — |

**No measured SNR improvement or recovered SWIR/1850 chemistry follows from any of this.**
