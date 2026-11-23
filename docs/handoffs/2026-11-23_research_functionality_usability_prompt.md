# Research handoff: functionality and usability of the current LIO V3 system

**Prepared:** 23 November 2026
**Repo:** Brandonio-c/LIO, `main` at or after the commit that adds this file
**For:** an independent research/QA agent. Paste everything below the line as its prompt.

---

You are an independent research and QA agent for the LIO V3 instrument (LED-Illuminated
Optospectrometer for a Light-based Ingredient Observer), repository Brandonio-c/LIO, branch
`main`. Pull the latest `main` and record the commit you audit.

## Your task

Write an evidence-based report on the **actual functionality and usability of the LIO
system as it stands today**: what the instrument can reliably do, what it cannot, and how
usable it is for its owner. This is an assessment, not an implementation task and not another
remediation plan. Judge the system on recorded evidence, not on the implementers' claims.
Every implementer document, including the latest acceptance record, is a hypothesis for you to
test.

Answer these questions directly, each with a verdict (works / partly works / does not work /
unknown) and the evidence behind it:

1. **Measurement core.** Which of the 16 LED channels produce a usable, repeatable signal on
   which detector, today? Separate the OPT101 (silicon, visible/NIR) from the InGaAs (SWIR).
   Use the recorded counts, repeats and noise, not channel labels.
2. **InGaAs path.** What do the archives establish about the InGaAs dark noise (T03.2 σ ≈ 37
   counts against a limit of 20), its offset, its 60 Hz hum and its weak or absent responses
   on holes 8, 9 and 12–15? What is established, what is only consistent with a cause, and
   what is unknown? (Changes on record: Rf swapped 1 MΩ → 2 MΩ, detector remounted deeper,
   drilled hole later filled; LED tops not fully sealed. A0/Rf/ammeter/optical checks remain
   owner-deferred.)
3. **Mechanics and scanning.** Does the height stage move and track reliably? What do the
   motor tests, the height scans and the "two sides not level" refusals (tracked bottoms
   M1 −286 884, M2 −429 461 half-steps) mean for full-travel scans?
4. **Safety and exposure.** Is LED exposure bounded? The board has no hardware watchdog
   (Nano R4, `hw_wdt=0`); the owner accepted the cooperative firmware watchdog without a
   proven hang bound (`lio_hw.yaml` `timing.real_port_admission`). Assess the host-side
   protections actually exercised live versus only offline, and what remains unproven.
5. **Data integrity.** Are saved runs trustworthy and reproducible: identities, seals,
   reuse checks, source immutability, resume? Check against the live archives, not only tests.
6. **Usability for the owner.** How practical is the system to operate today: dashboard
   workflow (one start confirmation, no in-run popups for suite and scan), run times, refusals
   and cooldowns, error messages, restart procedure, what an operator must know. Note
   friction and failure modes seen in the archives and logs.
7. **Fitness for purpose.** For each use, give a clear verdict with conditions:
   (a) commissioning and self-test; (b) visible/NIR food-profile collection with the OPT101;
   (c) SWIR (1450–1650 nm) food measurement with the InGaAs; (d) any quantitative or
   calibrated claim; (e) 1850 nm. State what must change, physically or in software, before
   each use is supported.
8. **Highest-value next steps.** Rank the five actions most likely to make the instrument
   useful, with expected effect and how to verify each. Physical actions are proposals only.

## Read first (in full)

1. `docs/handoffs/2026-11-23_caller_remediation_acceptance.md`: latest implementer claims, live runs
2. `docs/research/LIO_V3_RESIDUAL_REMEDIATION_QA_a0935fb_2026-11-23.md` and
   `docs/research/LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md`: previous independent audit
3. `docs/research/LIO_V3_SENSOR_INFORMATION_ASSESSMENT_2026-11-23.md`: sensor-information research
4. `docs/SENSOR_READINGS_UPGRADE_PLAN.md` (original M0–M6) and `docs/SENSOR_READINGS_CALLER_REMEDIATION_PLAN.md`
5. `.agents/project-state.md`, `test_results/README.md`, `README.md`
6. `docs/OPTICAL_CHANNEL_MAP.md`, `docs/HARDWARE_INVENTORY.md`, `docs/TESTING.md`, `docs/DIAGNOSTIC_SWEEP.md`
7. `docs/handoffs/2026-11-23_agent_takeover_context.md` (history of the 19–23 Nov work)

## Evidence to analyse

Live archives under `test_results/` (read raw data, not just verdicts):

| Folder | What it is |
|---|---|
| `20261123-162705_host` (+ `20261123-163301_scan_quick`) | Full automatic + motion catalogue, 23 Nov, empty chamber. NOT FUNCTIONAL. T13.1 ERROR from a since-fixed closing-check bug. |
| `20261123-170350_host` (+ `20261123-170352_scan_quick`) | **Invalid fix test**: ran old code because a dashboard restart had not taken effect. Do not count it as evidence for the fix. |
| `20261123-173106_host` (+ `20261123-173108_scan_quick`) | Height scan on fixed code: COMPLETE, sealed, NOT FUNCTIONAL (InGaAs). |
| `20261123-175731_scan_protocol`, `20261123-180942_scan_protocol` | Stationary capture on holes 8 and 12; refused-then-resumed; pause/abort/resume. |
| `derived_caller_acceptance/` | Offline qualified-v2 products, reports, the protocol files and the HTTP driver log. |
| `20261123-135504_host_residual_hw` | Earlier 23 Nov automatic catalogue (residual remediation). |
| `20261123-003133_scan_quick`, `20261120-*`, `20261119-*`, `tray_v3/` | Earlier scans and bench records: tray baseline, Citrucel food scan `LIO-F-00001`, LED sweeps (`LED_CONFIRM_SWEEP.json`), InGaAs remount checks, drive-tune records. |
| `20261123-153237_sim`, `20261123-161237_sim` | Simulator runs from offline testing (not hardware evidence). |

Compare across dates: did InGaAs response degrade after the Rf change and remount
(18 Nov holes 12–14 passed weakly; 23 Nov they read about 0–22 counts)? Is h9's OPT101
sweep/MEAS disagreement in the latest run (102 vs 117) consistent with its earlier
intermittency? Is the OPT101 visible channel strength adequate for food profiles at the
current ≈30 mA drive?

Code under `software/host/src/lio/` and firmware under `software/firmware/lio_firmware/`
for any behaviour you need to confirm. CAD under `CAD/` (the split light cover
`CAD/V3/LIO_V3_split_light_cover_v01.scad` is designed but **not printed or fitted**).

## Known open items you must account for

- A21 (qualified shared selection + fresh confirmation) and A22 (h16 proxy opt-in and grouped
  held-out validation through batch/CLI) are not implemented.
- Paired/shared-control/familywise statistics are not connected to the production qualified path.
- Final-tip test run: 971 passed, 1 failed (`test_golden_dashboard_http_plan_numerical_answer`,
  intermittent, cause unidentified); earlier run on `8cdfd0f`: 969/0/6. Python 3.10: 960/0/15
  with optional packages absent; precision (SciPy) tests not run on 3.10.
- Simulator system tests touch the local `test_results/stage_position.json` (test isolation gap).
- Bench steps (walk test, meter current, lid ambient) were not run in the latest session.
- Rf in `lio_hw.yaml` is still 1 MΩ although 2 MΩ is fitted; RAIL B `current_ma` says 45 mA
  although ≈30 mA was set. Treat both as unreconciled metadata.

## Constraints

- Offline analysis by default. Do NOT flash firmware, change wiring/currents, move motors,
  light LEDs, or open the serial port unless the owner separately authorises it in your session.
  A dashboard may be running and owning the port: do not stop it.
- Never modify historical runs. Work on copies; hash anything you rely on.
- Do not invent physical facts (A0 voltage, Rf, currents, alignment) or operator confirmations.
- Keep software PASS separate from physical/optical qualification. A tested refusal proves
  protection, not capability. Unjudged results (e.g. T05.5 "not judged") are not positive evidence.
- No claim of measured SNR improvement or recovered SWIR/1850 nm chemistry without direct evidence.

## Deliverable

A report saved as `docs/research/LIO_V3_FUNCTIONALITY_USABILITY_REPORT_<date>.md`, with:

1. One-paragraph bottom line: what LIO can be used for today, and what it cannot.
2. A capability table: subsystem × verdict × evidence (file + values) × confidence.
3. A per-channel table (hole, wavelength, OPT101 status, InGaAs status, repeatability, notes).
4. Fitness-for-purpose verdicts (question 7) with conditions.
5. Usability findings (question 6) with concrete operator-facing problems.
6. Discrepancies between implementer claims and evidence.
7. Ranked next steps (question 8), each with a verification test.
8. Exact commands you ran, the commit audited, and anything you could not check.

Write for the owner, an engineer-researcher, in plain language; put detail in tables.
