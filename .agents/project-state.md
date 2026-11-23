# Project state (updated 2026-11-23)

## Current independent sensor-readings QA and implementation scope

- **Audited source:** `a0935fb322e9a42459f577417b0167cfec830bfe`. Read the [independent audit](../docs/research/LIO_V3_RESIDUAL_REMEDIATION_QA_a0935fb_2026-11-23.md), [actual-caller regression catalogue](../docs/research/LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md), [current remediation plan](../docs/SENSOR_READINGS_CALLER_REMEDIATION_PLAN.md) and [coding handoff](../docs/handoffs/2026-11-23_caller_remediation_implementation.md).
- **Software acceptance is incomplete:** maintained Python 3.12 checks passed (120 targeted; 918 full unit/simulator passes, 0 failures, 12 skips; 98% protocol/analysis gate), but twelve independent actual-caller acceptance tests failed. Additional budget/resume/operator/eligibility/selection integrations remain incomplete. Exact-candidate Python 3.10 CI mypy failed. These separate audit tests are not included in the maintained-suite totals.
- **ORIGINAL M0–M6:** M0/M2 partial; M1/M3–M6 not accepted. D03=ownership and D04=OFF. The prior residual acceptance handoff is a historical implementer claim, not current acceptance. M7 stays deferred/isolated.
- **Latest archived host measurements:** `test_results/20261123-135504_host_residual_hw/` is NOT FUNCTIONAL (28 PASS, 1 WARN, 5 FAIL, 4 SKIP, 0 ERROR). InGaAs dark/under-threshold responses remain unresolved; both selected T10.2 watchdog requests SKIP before emission. The archive records `944a820` with a dirty working tree, not a sealed final-candidate deployment. SWEEP and particular safety PASS outcomes do not prove every timing/ownership/OFF contract.
- **Latest empty quick scan:** `test_results/20261123-003133_scan_quick` remains NOT FUNCTIONAL under its saved analysis. H8/h9 respond; InGaAs is not globally dead. The [sensor-information assessment](../docs/research/LIO_V3_SENSOR_INFORMATION_ASSESSMENT_2026-11-23.md) remains the physics basis: H16 OPT101 is reproducible but spectrally unassigned/`proxy_unassigned`, never primary-1850 chemistry. Nov 19 report/analysis disagreement remains provenance, not permission to rewrite it.
- **Current owner instruction:** the owner reports the board connected and requests software implementation plus full offline and supported live tests. Follow the new handoff: repair/prove offline safety boundaries first, then use actual ownership/admission and real operator answers. Existing interactive/motion catalogue portions are in scope only with their actual clearance/trusted-travel prerequisites. Connection alone proves none of those facts; they have not been verified by this documentation task.
- **Limits remain:** no firmware edit/flash, wiring/current/pot change, raised drive, relaxed duty/travel limits, automatic homing/rebasing, invented stage state or live-dashboard takeover. Do not invent finite WDT margins or use a synthetic timing profile to admit a real port. Ordinary truthful position tracking remains local. A0/Rf/ammeter/optical/reference checks stay owner-deferred; their absence blocks the dependent physical/quantitative claims while preserving raw diagnostics and valid OPT101 quantities.
- **Data integrity:** historical `test_results/` are tracked on main from `138a963`; only physical `test_results/stage_position.json` stays local/ignored. Acquisitions/reports are immutable; new derived output must be external and source-bound. This publication changes documentation only and performs no new hardware test.
- No measured SNR improvement or recovered SWIR/1850 chemistry follows from this software or these documents.

## Caller remediation + authorised live tests (23 November 2026, latest)

- Acceptance record: [docs/handoffs/2026-11-23_caller_remediation_acceptance.md](../docs/handoffs/2026-11-23_caller_remediation_acceptance.md). Candidate `8cdfd0f`..`7f080ea` on main.
- Actual-caller regressions A01–A20, A23, A24 closed with maintained tests (`tests/unit/test_caller_regressions_*.py`); **A21, A22 open**.
- Offline: ruff/format pass; strict mypy clean on 3.10 and 3.12; unit+sim 969/0/6 (3.12), 960/0/15 (3.10, optional deps absent); coverage gate 98 %.
- Owner decision: `timing.real_port_admission: cooperative_unproven_acknowledged` (no hardware watchdog on the Nano R4). **Current-rig M1 blocked**; runs record `exposure_bound`.
- Live (empty chamber, lid closed): catalogue `20261123-162705_host` NOT FUNCTIONAL (InGaAs: T03.2 σ 37.5, weak/absent SWIR); height scan `20261123-173108_scan_quick` COMPLETE, NOT FUNCTIONAL (InGaAs); stationary capture + pause/abort/resume `20261123-175731/180942_scan_protocol` COMPLETE. T09.6/T09.7 SKIP: tracked bottoms not level. Bench steps not run.
- Dashboard restart procedure: `POST /api/disconnect`, SIGTERM, verify new PID (background jobs ignore SIGINT).

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

## Historical residual candidate claim (2026-11-23)

The residual implementation added ownership defer-load, fragment/CR refusal, CE `drop_pending`, `wait_needed_many`, admitted-or-SKIP T10.2 and TEN triage. Some narrow fixes are independently confirmed. Its blanket M0–M6/full-caller closure claims are superseded by the current independent audit above. The archived automatic host run remains NOT FUNCTIONAL. Apply the [current remediation plan](../docs/SENSOR_READINGS_CALLER_REMEDIATION_PLAN.md), not historical completion language.
