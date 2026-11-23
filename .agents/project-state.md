# Project state (updated 2026-11-23)

## Current audited evidence and planned sensor-readings upgrade

- Latest audited quick scan: `test_results/20261123-003133_scan_quick` is **NOT FUNCTIONAL** under its saved analysis; h12–h14 and InGaAs electrical/throughput findings require attention. H8/h9 still respond; the detector is not globally dead. This supersedes treating the 20 November snapshot below as the current measurement verdict.
- Historical `test_results/` are tracked on `main` as of `138a963`; only physical `test_results/stage_position.json` stays local/ignored. Read `test_results/README.md` for the anchors.
- Research/code/raw-data assessment: [sensor information assessment](../docs/research/LIO_V3_SENSOR_INFORMATION_ASSESSMENT_2026-11-23.md). H16 OPT101 is a reproducible, spectrally unassigned response, not a primary-1850 channel. Nov 19 report/analysis verdicts disagree; preserve provenance.
- **Full-pass sensor-readings remediation (software-tested candidate):** mandatory counterexamples in `tests/unit/test_fullpass_counterexamples.py` + D01–D20 regressions. Acceptance matrix: [docs/handoffs/2026-11-23_fullpass_acceptance.md](../docs/handoffs/2026-11-23_fullpass_acceptance.md). Plan: [SENSOR_READINGS_REMEDIATION_PLAN.md](../docs/SENSOR_READINGS_REMEDIATION_PLAN.md). Prior closure note is **not** acceptance.
- **Honest status:** **software-tested candidate only** — not bench-acquisition-qualified, optical-control-qualified, or quantitative-reference-qualified. Do not treat another quick/full scan as upgrade qualification without separate authorization.
- **M7 remains deferred/incomplete experimental helpers**, isolated from core (missing gain readback refuses; never silent default to 1). Not part of M0–M6 acceptance.
- **M0–M6:** original upgrade-plan contracts software-tested offline; physical acceptance remains open. Canonical D03=ownership, D04=OFF. Cooperative WDT is not a proven wall-clock ceiling — finite real-rig timing may refuse fail-closed.
- **Release state:** offline/sim software gates green on required host suites; not bench-qualified. No measured SNR or recovered SWIR/1850 chemistry claim.
- **Still owner-deferred bench work:** A0 operating-range evidence, fitted Rf/Cf and actual accepted current, ammeter/voltmeter checks, unchanged-load optical controls and optical-path qualification. Their absence preserves raw/labelled ADC diagnostics and valid OPT101 quantities, while blocking the specified InGaAs physical/quantitative claims.

## Historical commissioning snapshot — 20 November 2026

This section records the earlier commissioning state. It is not the current upgrade qualification or authorization to operate the instrument.

### Verdict

**FUNCTIONAL with warnings** — ready to start collecting food LIO scan profiles, with provisional thresholds and known soft optics/mechanics.

Latest host suite: `test_results/20261120-003626_host` → **FUNCTIONAL**  
(`PASS` 39, `WARN` 3: T07.1 / T09.6 / T13.1, `SKIP` 3: T04.2 / T04.3 / T11.1 without compare, `FAIL` 0)

Latest empty quick scan (via T13): `20261120-012619_scan_quick` → **FUNCTIONAL** (InGaAs soft WARNs, h16 plausibility).

### Commissioning done

- Firmware **2.5.2**; rails A=1–8 / B=9–16 match the build.
- Dashboard twin + host suite: soft WARNs for V3 loose stage, weak InGaAs at sealed top, hole 16, intermittent/select-only, bogus SWEEP duty accounting.
- `set_top` rebases bottom / light-tight top documented; `top_margin` in config.
- USB-after-Stop: suite detects dead link, drops stale port, refuses new run until reconnect (see session `ensure_link` / `link_lost`).
- Suite baseline saved: `software/config/baseline_20261120.yaml` (sample `empty`).
- Extra remote branches removed; repo is **main-only**.

### Twin / LED display policy (V3)

| Symptom | Treatment |
|---------|-----------|
| Hole 16 OPT101 residual at 1850 nm | WARN (limited hole) |
| T06.3 weak cross-cal / “one detector” at top | WARN, not channel FAIL |
| T07.1 no step (esp. h13 InGaAs at top) | WARN |
| Stage repeatability large spread | Cap FAIL→WARN |
| Duty “46 s/min” with 0 cool-downs | WARN / accounting bug; SWEEP duty staggered |

### Food-profile software (M0–M7)

Implemented on `main`: `lio.food_profiles` + dashboard **Profiles** tab + `lio profiles …` CLI.
Offline Explore/Compare/Food Map, recipes (amplitude/SNV/MSC/reference/O), frozen PCA/distances,
whole-height fPCA, grouped validation, optional t-SNE/UMAP, ASCA, EWMA trends, portable reports.
Held-out ablation for `proxy_unassigned:` (h16) via `lio profiles ablate`; baseline selection via `lio profiles baseline`.
Synthetic fixtures are labeled; **no measured food-discrimination claims**. See `docs/FOOD_PROFILES.md`.

```bash
lio dashboard --results-dir test_results --no-food-library --no-browser
lio profiles fixtures --out /tmp/lio_synth
```

### Not done / next for food work (physical)

1. Save a **fresh scan baseline** for `empty` (promote today’s empty quick or run a **full** empty scan, then `lio scan baseline save <run>`).
2. Optional references: `white_ptfe`, `black_cup` full scans → scan baselines.
3. Collect food profiles: Scan tab → **full** (or fine), sample id = food / `LIO-F-…`, lid closed; annotate preparation/lot.
4. Qualify reference protocol and discrimination on **measured** data (software paths already tested on synthetic).
5. UI: “Compare with latest baseline” may show “none saved yet” until session refresh — file on disk exists.
6. Thresholds still **provisional** (`docs/TESTING.md` §7.3).

### Open soft issues (do not block food collection)

- InGaAs weak / low SNR on some SWIR holes (13–14); hole 16 known coupling.
- Stage mechanically clunky (repeatability WARN by policy).
- Prefer sealed-top suite vs mid-travel / full-scan heatmaps when judging “LEDs work.”

## Full-pass candidate (2026-11-23)
Uncommitted offline repairs on main@130dd77: ownership/raw gate, fw-matched MEAS timing, typed ScanStore/provenance, protocol ConsoleOperator/SimOperator, CE01–14 + D suites, FWER≥2000 with SciPy. See docs/handoffs/2026-11-23_fullpass_acceptance.md. No push; M7 deferred; A0/Rf owner-deferred; ~11 residual unit/sim fails remain.
