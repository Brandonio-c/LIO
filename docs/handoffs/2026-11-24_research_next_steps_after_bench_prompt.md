# Research handoff: determine next steps after the 24 Nov stationary optical bench

**Prepared:** 24 November 2026 · **Repo:** Brandonio-c/LIO, `main` at or after the commit adding this file
**For:** an independent research agent. Paste everything below the line as its prompt.

---

You are an independent research agent for LIO V3 (LED-Illuminated Optospectrometer for a
Light-based Ingredient Observer), repository Brandonio-c/LIO, branch `main`. Pull the latest
`main` and record the commit you review.

## Your task

Review the new bench evidence and **determine the next steps for LIO**: what the result means
for the instrument's usefulness, which experiments and changes should come next and in what
order, and what can already be done with the system as it is. Deliver a prioritised, concrete
plan the owner can act on. This is an analysis task: do not connect to hardware, change code,
or push.

## What was just measured (verify against the raw data)

Read `docs/research/LIO_V3_STATIONARY_OPTICAL_BENCH_2026-11-24.md` and the evidence in
`test_results/bench_20261124_stationary/` (frozen design, protocols, raw runs with seals,
`ambient_dark.json`, checkpoint history, qualified-v2 products under `derived/`,
`cross_run_exploratory.json`). Headline (fixed N = 12, mains-integrated MEAS, gain 1,
detectors/optics/currents unchanged):

| Hole / detector | White paper | Black cup | White − black (exploratory) |
|---|---|---|---|
| h12 InGaAs (1450 nm) | 71.1 ± 0.9 | 11.5 ± 1.6 | +59.6 (95 % 58.5..60.7) |
| h8 InGaAs | 146.3 ± 1.1 | 26.4 ± 2.0 | +119.8 |
| h8 OPT101 | 975 ± 2 | 148.8 ± 3.4 | +826 |
| h12 OPT101 | 1.3 ± 0.7 | 1.6 ± 0.7 | −0.3 |

Room lights ON/OFF/ON did not change InGaAs dark level (≈ −331) or raw noise (SD ≈ 30–34
counts at 128 SPS); OPT101 dark shifted ≈ 1 count. Limits: no optical blocker (optical vs
electrical not separated within a target); black cup not at the paper's surface plane;
fixed white-then-black order; cross-run comparison exploratory; nothing calibrated.

## Context you must also weigh

- Earlier assessment and plans: `docs/research/LIO_V3_FUNCTIONALITY_USABILITY_REPORT_2026-11-23.md`,
  `docs/handoffs/2026-11-24_research_optical_improvement_prompt.md` (optical-improvement brief;
  its premise that SWIR was missing should now be re-examined),
  `docs/handoffs/2026-11-23_sensor_suite_practical_acceptance.md` (software capabilities and
  open items: S4 comparisons, A21 selection/confirmation, browser protocol builder/prompts).
- Empty-chamber runs (`20261123-162705_host`, `20261123-173108_scan_quick`,
  `20261123-175731/180942_scan_protocol`) showed near-zero/negative h12–h14 InGaAs; the Citrucel
  food scan (`tray_v3/20261120-184450_scan_full`) predates the current LED/Rf state.
- Owner-declared, unmeasured facts: Rf 2 MΩ fitted (YAML 1 MΩ), LED rails ≈ 30 mA (YAML B
  45 mA). A0/Rf/ammeter/reference qualification is owner-deferred. Nano R4 `hw_wdt=0`
  (cooperative, unproven hang bound). InGaAs raw dark noise σ ≈ 30–37 counts remains, but
  integrated MEAS repeats were ≈ 1–2 counts.
- Holes 13–15 (1550–1760 nm) and h9 were not measured in this bench; h16 stays an
  unassigned proxy.

## Questions to answer

1. **What does the bench establish?** Re-state, with your own check of the raw data, what is
   and is not shown about SWIR sample-return, repeatability and ambient pickup. Does the
   result change the earlier conclusion that LIO "does not work reliably" for 1450–1650 nm?
2. **What should be measured next, in order?** Design the minimum set of bench experiments to
   (a) separate optical return from electrical pickup (a blocker design that is opaque,
   non-conductive and insertable without touching sensors/wiring; e.g. a printed black PETG
   slide: specify it), (b) extend the target comparison to h9 and h13–h15 with a flat black
   card at the same plane and alternated order (W-B-W-B), (c) quantify drift and day-to-day
   reproducibility, (d) establish a reference/normalisation scheme (white/black references per
   session). For each: protocol settings (holes, N, settle, mains periods, caps), checkpoints,
   success criteria, expected effect sizes from the current data, and analysis method
   (qualified-v2 contrasts; within-run paired blocked/unblocked where possible).
3. **Is LIO now usable for food work, and how?** Given ~60–120 counts of white-vs-black
   contrast on h8/h12 at ~1-count repeatability, what food experiment is now justified
   (stationary fixed-N vs height scans; which holes; references; preparation/day grouping;
   sample presentation in the tray)? What minimum effect size could it detect?
4. **Hardware/optics priorities.** With SWIR return demonstrated, which earlier optical or
   front-end proposals still matter (InGaAs raw noise/hum, sealing for the OPT101's 1-count leak,
   LED drive/seating, metadata reconciliation of Rf/current), and which can be deprioritised?
   Do any of them justify moving a detector? (The owner's current constraint: neither detector
   moves without strong evidence.)
5. **Software gaps that block the plan.** Which open items (S4 setting comparisons, A21
   selection/confirmation, browser protocol builder and checkpoint answers, multi-condition
   blocker protocols across targets, cross-run comparison support) are needed for your next
   experiments, and which are not? Keep requests minimal and specific.

## Constraints

- Offline analysis only: no serial connection, LEDs, motors, firmware, wiring/current changes,
  code changes, dashboard actions or Git push.
- Never modify historical runs; hash what you rely on; derived work goes outside source runs.
- Do not raise LED drive, relax duty/watchdog limits, invent physical facts or treat white paper
  as a calibrated SWIR standard. No calibrated reflectance/photocurrent, measured SNR
  improvement, recovered SWIR chemistry or 1850 nm claims without direct evidence.
- Bench experiments you propose are proposals for owner authorisation; state their physical
  prerequisites and checkpoints.

## Deliverable

Save `docs/research/LIO_V3_NEXT_STEPS_<date>.md` with:

1. A one-paragraph bottom line: what LIO can do now and the single most valuable next step.
2. Your verification of the 24 Nov bench (re-computed numbers, any disagreement).
3. A prioritised next-steps table: action, type (bench/software/hardware), purpose, cost/effort,
   prerequisites, success criterion, and what decision it unlocks.
4. Ready-to-run protocol specifications (JSON-ready fields) for the top 2–3 bench experiments,
   including the blocker design and target placement.
5. A food-pilot recommendation (design, holes, N, references, grouping, detectable effect).
6. A short list of software changes that are actually needed, and of items that can wait.
7. Open unknowns and what would resolve them; commit reviewed and files hashed.

Write for the owner, an engineer-researcher, in plain language with detail in tables.
