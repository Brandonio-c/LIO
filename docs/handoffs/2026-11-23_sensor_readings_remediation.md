# Coding-agent handoff: remediate LIO V3 sensor-readings QA failures

Read the [remediation plan](../SENSOR_READINGS_REMEDIATION_PLAN.md) and [independent QA report](../research/LIO_V3_SENSOR_READINGS_QA_2026-11-23.md). Copy the prompt below into the implementation agent.

---

You are the implementation agent for **Brandonio-c/LIO**, working from current **main**. Implement and test the sensor-readings remediation. Complete the work; do not return another research-only assessment, parser-only implementation or helper-only test suite.

## Start and authorization

- Read applicable AGENTS instructions and .agents/README.md, preferences.md, project-state.md, baselines.md and workflows.md.
- Inspect status/history and fast-forward main only when preserving local work. The audited code is 38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8; compare newer changes before applying repairs. Main only: no side branches, reset/clean, force push or Git-config changes.
- Offline host changes, tests and simulator work are the scope of this handoff. **No real device connection, POWER WAKE, LED exposure, motor movement, firmware edit/flash, wiring/current change, physical stage-state edit, invented operator confirmation or live-dashboard restart.**
- Do not push implementation commits unless the owner authorizes that in this coding session. The preceding request published documentation only. Finish the reviewable implementation and tests without waiting for bench access or a push decision.

## Read in full

1. docs/SENSOR_READINGS_REMEDIATION_PLAN.md — repair requirements, D01–D20 failures, R0–R8 order and proof gates.
2. docs/research/LIO_V3_SENSOR_READINGS_QA_2026-11-23.md — observed counterexamples, source/test citations and verification limits.
3. docs/SENSOR_READINGS_UPGRADE_PLAN.md — original M0–M6 contracts, especially§12.
4. docs/research/LIO_V3_SENSOR_INFORMATION_ASSESSMENT_2026-11-23.md.
5. docs/handoffs/2026-11-23_research_handoff_sensor_information_extraction.md and test_results/README.md.

The earlier “M0–M6 done / M7 complete / remaining bench-only” statements failed independent QA. Treat this remediation plan and its explicit status corrections as current. Historical results are tracked on main; only test_results/stage_position.json is local/ignored.

## Required implementation

Work through R0–R8. Begin by reproducing applicable D01–D20 failures and making them maintained regression tests. Repair actual CLI/dashboard/device/profile/report callers and persisted artifacts, not just standalone helpers.

1. Fix ownership, all emitting paths, atomic whole-SWEEP exposure, stale journal state and cancellation-safe same-owner OFF. Real duty=False/budget=False cannot remove protection. Existing watchdog timing is cooperative; require a supported conservative capability bound/readback or refuse before light. Do not invent a timing margin or alter firmware.
2. Make acquisition facts truthful: INFO uses gain/mains/rate; unknown gain is not 1. New core acquisition rejects unexpected gain. Apply/read back mains before measurement. Freeze complete actual settings/evidence, preserve raw reading/block identities, and seal every consumed raw/terminal input.
3. Make derived outputs immutable and source-safe, including legacy. Hash all actual source/config/model/control/reference inputs. Missing required identity/compatibility facts must reject quantitative reuse.
4. Wire quantity gates through actual consumers. Unknown Rf or unverified/outside A0 blocks InGaAs physical-current/quantitative optics/reference claims; preserve signed counts, clearly labelled ADC-referred diagnostics and independently valid OPT101 quantities.
5. Require evidence-backed controls; unknown C stays null. H16 remains proxy_unassigned, never primary1850. Do not change thresholds/expect to make weak channels pass.
6. Implement identified fixed-N blocks, condition pairing, shared-control covariance and declared familywise uncertainty. No height/phase pooling, truncation, duplicate-N fiction, noisy-max confirmation or stop-when-positive.
7. Finish finite protocol lifecycle: per-occurrence safe checkpoints, actual pause/heartbeat/progress, persistent total/cycle/wall caps and compatible completed-block resume. A start checkbox cannot confirm later manual interventions. Exercise real CLI run/resume and dashboard routes with fake transports.
8. Learn pilot variance/cost from actual pilot blocks, freeze production in a separate immutable artifact and exclude pilot from confirmation. Connect one shared target-selection result to actual planner/fine/report/UI and fresh held-out confirmation.
9. Finish baseline/reference/profile masks, opt-in proxy extraction and actual grouped held-out ablation using existing tools. Complete numerical inspection and nonblocking saved-data analysis.
10. Keep M7 deferred/incomplete and isolated. Do not expand into PGA experiments, firmware, a new framework or classifier.

## Verification and completion

Run the required D01–D20 regression, numerical-truth/coverage/FWER, real-record §12, ownership/crash/alias/clock/partial/cancel, offline transport, CLI/dashboard concurrency and packaging checks. Maintain Ruff/format, strict mypy, unit/simulator/fault matrix and existing coverage gate on Python 3.10/3.12; exercise precision absent/present, profiles extras and installed-wheel offline operation. Use isolated synthetic state/output only.

Do not relax checks, skip contract failures or call a module/key/button proof of functionality. Implement valid-input and unqualified paths without fabricating physical evidence. If a required timing capability or environment check remains unsupported, report it precisely and continue independent work; do not label the stage complete.

Deliver changed files, actual commands/results, a D01–D20 closure table and M0–M6 acceptance matrix, usable final commands, updated docs/status, and explicit unresolved capability/bench limits. Keep owner-deferred A0/Rf/ammeter checks pending. **No measured SNR improvement or recovered SWIR/1850 chemistry follows from software completion.**
