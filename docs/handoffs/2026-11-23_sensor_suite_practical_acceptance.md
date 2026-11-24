# Practical sensor-suite upgrades: acceptance record (23 November 2026)

**Plan:** [SENSOR_SUITE_PRACTICAL_UPGRADE_PLAN.md](../SENSOR_SUITE_PRACTICAL_UPGRADE_PLAN.md) ·
**Handoff:** [2026-11-23_sensor_suite_practical_implementation.md](2026-11-23_sensor_suite_practical_implementation.md) ·
**Evidence report:** [LIO_V3_FUNCTIONALITY_USABILITY_REPORT_2026-11-23.md](../research/LIO_V3_FUNCTIONALITY_USABILITY_REPORT_2026-11-23.md)

**Start:** `main` at `f0668fd` (clean except untracked local files). **Candidate:** `813d5f1` (on `266b225`)
plus the documentation commit adding this file. Scope: host software and OFFLINE verification
only. No serial port, device, light, motion, firmware, wiring, current or stage-state change was
made; the owner's running dashboard was not touched. Not pushed (publication follows the owner's
instruction).

This record states what was implemented and tested, and what was **not**. Inherited test counts
are not used as evidence for new packages.

## 1. Package status

| Package | Status | Actual callers exercised (tests) |
|---|---|---|
| **S1** repeatability | **Implemented** | `T05.5` precision-2 via `run_test` with transport-injected labelled fixtures: stable 50±1 PASS with CV; unstable FAIL; zero/negative stable with CV unavailable; dropout FAIL with the `None` attempt kept; saturated SKIP; zero evaluated channels = SKIP "not a precision PASS". `T08.2` SWEEP net repeatability FAIL on wild nets while dark stability passes. (`test_practical_s1_precision.py`) |
| **S2** identities, provenance, resume | **Mostly implemented** | Height executor fills all identity fields (one reading per physical operation, both detector rows share it); `scan.json` carries `exposure_bound`, loaded build, segments. Protocol resume refuses missing/duplicate detector rows, changed condition, mismatched settings/blocks/readings/position, and an invalid existing seal (not resealed); legal unsealed crash resumes only the remaining steps with an explicit `unsealed_crash_recovery` record; segments/events append-only. Legacy dark-offset no longer prints nA without verified A0 + run-frozen Rf. Height mains readback must exist. (`test_practical_s2_s3.py`, `test_scan_analysis.py`) **Not done:** full self-contained config/channel/mux snapshot content (still path+hash for config), per-fact provenance for declared-vs-measured current (YAML Rf 1 MΩ vs fitted 2 MΩ and B 45 vs ≈30 mA remain unreconciled metadata, not rewritten). |
| **S3** owner workflow | **Partly implemented** | Browser Resume now routes protocol runs to `/api/scan/protocol/start` (JS); CLI height resume no longer reads an absent `--sample`; `mains_periods` exposed in the Scan settings, the ignored control disabled with a reason, ineffective overrides refused; periods change actual SWEEP/MEAS arguments, plan cost and recorded `setting_id` (1→2 height, 2→8 protocol). Infeasible integration (≥3 periods × 8 RAIL A holes in one SWEEP) is refused before light with a clear reason instead of "wait 0 s". **Not done:** stationary protocol builder UI, OPT101/diagnostic-SWIR presets, browser rendering of protocol checkpoint occurrences/answers, and a real headless-browser test (not run: no browser automation installed in this environment). |
| **S4** acquisition comparisons | **Not implemented** | Settling/integration profile comparison with measured pilot variance/cost, equal-cost comparators under identical exposure+wall caps and a separate frozen production allocation were not built in this session. Existing pilot/freeze/exact-resume behaviour (A15) is unchanged. |
| **S5** connected inference | **Implemented** | `pair_id` / `control_group_id` identities; frozen inference family at run creation; `qualified-v2` computes paired condition contrasts and per-condition target-minus-control contrasts only with applicable scoped `ControlEvidence` (CLI `--control-evidence`), covariance of means for shared controls, Bonferroni over the frozen family; consumed by report and dashboard summary. Saved-record truth through `lio scan analyse` → `analysis.json` → `lio scan report`: paired [10,12,14]−[1,2,3] = [9,10,11], mean 10, variance of mean 1/3; shared-control covariance −1/3; missing pair → unavailable; out-of-scope evidence → C stays null; family size unchanged by missing members. Verdict stub replaced by computed numerical availability, separate from physical qualification. (`test_practical_s5_inference.py`) **Not done:** profile-feature consumption of contrasts; drift/correlation limits beyond the paired-difference model. |
| **S6** references, A21, A22 | **A22 implemented; A21 not implemented** | A22: `include_proxy_h16` through `build_feature_batch` and `lio profiles build/validate/ablate --include-proxy-h16`; default excludes h16; ablate refuses without the opt-in; descriptive distances labelled descriptive; new predictive comparison reuses `validate_grouped` (training-only PCA, held-out groups) on identical folds for full vs proxy-removed, unavailable without labels/groups/proxy columns or the profiles extra. (`test_practical_s6_proxy.py`) **Not done:** A21 shared source-bound selection with genuinely new held-out confirmation; reference/baseline compatibility beyond the earlier A19 facts; UI opt-in. |
| **S7** status and release | **Partly implemented** | Loaded-build identity fixed at process start (`lio.buildinfo`) with a disk-change check in `/api/state`; `LIO_STAGE_FILE` override and a physical stage-write guard; test session fixture isolates stage and journal state; corrected "not level" (distances to marks, not tilt) and h16 plausibility wording. **Not done:** twin tile run/epoch labels, cooldown/progress cost display, fake-server restart-semantics test, OS-exclusive serial request, wheel/extras isolation installs, documentation sweep of README/TESTING/DIAGNOSTIC_SWEEP. Intermittent golden HTTP failure: see §3. |

## 2. Offline verification

Final gate on candidate `813d5f1` (both interpreters run on the same commit; full logs kept outside the repo):

| Check | Python 3.12.11 (NumPy 2.5.4, SciPy 1.18.1, no scikit-learn) | Python 3.10.18 (NumPy 2.0.1, SciPy 1.15.3, scikit-learn 1.7.1) |
|---|---|---|
| `ruff check .` / `ruff format --check .` (ruff 0.15.4) | pass / 207 files formatted | (repo-wide, same) |
| strict `mypy` (2.4.1) | no issues, 127 files | no issues, 127 files |
| `pytest -m "unit or sim" --lio-sim` + coverage | **998 passed, 0 failed, 7 skipped** | **1004 passed, 0 failed, 12 skipped** |
| protocol/analysis coverage gate ≥ 90 % | 98 % | 98 % |
| Real headless browser | **not run** (no browser automation available) | — |
| Installed wheel outside checkout; core/precision/profiles absent/present matrix | **not run** as a matrix; precision (SciPy) runs on both; profiles present only on 3.10 | — |

Skips: 3.12: T04.2/T04.3/T09.6/T09.7/T11.1 simulator skips, scikit-learn absent (1 food-profiles test, 1 S6 predictive test). 3.10: the same simulator skips, zxing absent (6 food-library tests), and the profiles-absent branch test (correctly skipped when scikit-learn is present).

The first gate on `266b225` failed (13 tests, 18 ruff errors). Causes and fixes: the S1 absolute 5-count SD limit wrongly failed proportional-noise strong channels and dark-noise-limited ones (now max(5, 3·√2·dark σ), or CV ≤ cv_max for resolved means); callers still echoed `sweep_n` in mains mode (unchanged echoes are now accepted, changes refused); single-class predictive comparison returned "available" (now unavailable); the archived live driver script was linted (excluded as an archive).

Historical bytes: the saved-data regression module hashes the archived runs it copies before and
after its tests; the physical stage file is protected by the write guard (an attempted write raises).

## 3. Intermittent golden HTTP failure: diagnosed

During a loaded run (two full suites in parallel, coverage tracing) `test_dashboard.py::
TestProtocolAndDerived::test_derived_list_http` failed with `TimeoutError: timed out`: the
same failure family as the unexplained golden test. Profiling the route showed the
first request to any plan/derived/numerical route imported `lio.scan.derived` ->
`scipy.stats` **inside the request handler**: 1.93 s on an idle machine, above the client's
10 s timeout under load. The golden test's first request is such a route. Fix: the dashboard
server imports the analysis stack at startup (`_warm_imports`), and a maintained test asserts
the modules are loaded before serving and that the first derived request returns in < 1 s.
Both final full runs passed. The exact failing trace of the original golden failure was never
captured, so this is the demonstrated mechanism for the observed timeout family, not a replay
of that specific failure.

## 4. ORIGINAL M0–M6 (software vs physical)

| Milestone | Software after this candidate | Physical / current rig |
|---|---|---|
| M0 | Stronger: height identities, exposure/build provenance, semantic resume, seal refusal | Self-contained config/mux snapshot and declared-vs-measured facts still incomplete; A0/Rf deferred |
| M1 | Unchanged contracts preserved; infeasible same-rail sets refused | Blocked: no hardware watchdog (owner-acknowledged unproven bound) |
| M2 | Scoped control evidence feeds connected contrasts; C null without evidence | No eligible real controls |
| M3 | Paired/shared-control/familywise inference connected in production | Real data: C null; dependent optics unresolved |
| M4 | Exact resume + semantic validation + segments; S4 comparisons missing | — |
| M5 | Not met (A21 open) | — |
| M6 | Partial: CLI paths connected; browser builder/prompts, wheel matrix missing | — |
| M7 | Deferred | — |

## 5. Proposed owner-authorised bench comparisons (not performed)

1. Fixed-N T05.5 precision-2 on the current rig (OPT101 holes 1–11, InGaAs 8/9/12–15) to replace the vacuous historical PASS with measured dispersion.
2. Stationary paired optical-block protocol on h8/h12 with a declared scoped control hole, to exercise S5 on real data.
3. Mains periods 1 vs 2 at fixed N on h8 InGaAs, recording precision versus exposure (no SNR claim until measured).

**Software green is not optical PASS. No measured SNR improvement or recovered SWIR/1850 nm
chemistry follows from this work.**
