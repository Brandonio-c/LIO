# Sensor-readings caller remediation and full-test plan

**Date:** 23 November 2026  
**Audited implementation:** a0935fb322e9a42459f577417b0167cfec830bfe. Reconcile newer main changes before editing.  
**Status:** implementation specification after independent QA. Publishing it does not implement or qualify the repairs.

Read the [independent audit](research/LIO_V3_RESIDUAL_REMEDIATION_QA_a0935fb_2026-11-23.md), [reproduction catalogue](research/LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md), [original upgrade contracts](SENSOR_READINGS_UPGRADE_PLAN.md), [R0–R8 requirements](SENSOR_READINGS_REMEDIATION_PLAN.md) and [coding handoff](handoffs/2026-11-23_caller_remediation_implementation.md).

## 1. Required result and current authorization

Deliver functioning, bounded acquisition and connected analysis through actual device/CLI/dashboard/ScanStore/report/profile callers. A collection of passing helpers is insufficient.

The independent a0935fb audit found **120 maintained targeted passes**, **918 full unit/simulator passes / 0 failures / 12 skips**, and the full-run protocol/analysis coverage gate at **98%**. Separately, twelve audit-only actual-caller acceptance tests failed. Python 3.12 CI passes; Python 3.10 mypy fails. Original M0/M2 are partial, M1/M3–M6 are not accepted; M7 is deferred.

**The owner now reports that the board is connected and authorizes the coding agent to implement the repairs and run full tests.** This adds live testing to the prior offline-only implementation scope. It does not waive safety or scientific contracts.

- Finish offline safety repairs and actual-caller fault tests before new live emission/motion.
- Live connection, INFO/status, automatic catalogue and bounded supported light diagnostics are authorized after admission checks.
- Interactive and existing T09/T13 motion portions of the full host catalogue are in scope when their existing operator, sample-clearance and trusted-travel prerequisites are actually satisfied. Do not request the same general authorization again.
- Obtain required operator facts/answers through the existing operator/UI channel. Board connection is not proof of chamber clearance, lid/earth state, sample identity, physical range or trustworthy stage coordinates. Never invent answers.
- No firmware edit/flash, wiring/current/pot change, raised drive, relaxed exposure/travel limit, automatic homing/rebasing or invented physical stage state is authorized. Normal truthful tracking updates from authorized motion remain local; stage_position.json stays ignored.
- A0/Rf/ammeter/optical/reference checks remain owner-deferred. Do not start those physical investigations merely because the board is connected. M7 remains deferred/isolated.
- Do not kill/restart a live dashboard or steal its serial ownership. Reuse the owning session/control path or arrange a graceful release with the operator.
- This publication authorizes the documentation push. Implementation pushes follow the coding-session instruction; finish reviewable implementation/tests without waiting for a push decision.

“Full tests” means execute the supported test matrix and report every PASS/WARN/FAIL/SKIP/error honestly. It does not mean force the instrument to FUNCTIONAL. An unsupported pulse must refuse; a post-emission safety failure must not be labelled an unsupported SKIP. If a real timing capability cannot be justified without firmware work, complete independent repairs/tests, archive the precise refusal and keep current-rig M1 blocked. Do not invent a timing margin.

## 2. Delivery sequence

These work-package labels do not replace original M0–M6 or canonical D03=ownership / D04=OFF.

| Package | Existing boundaries | Required exit evidence |
|---|---|---|
| P0 | Tests, fixtures, status docs | Reproduce outstanding actual-caller cases on the baseline; preserve already-correct narrow behavior |
| P1 | ownership.py, device.py, timing_capability.py, transport/callers, T10 | One owner/serialized admission path; durable spending; conservative failure handling; all safety fault traces pass |
| P2 | scan store/provenance/calibration/derived and saved-run consumers | One authoritative record/facts/identity contract, verified at generation and reuse |
| P3 | acquisition/Control, CLI, dashboard session/server/job/UI | Real occurrence answers, finite persistent budgets/deadlines and exact resume |
| P4 | coupling/uncertainty, allocation/targets, profile/report consumers | Valid saved-data estimands/eligibility; immutable measured decisions consumed end to end |
| P5 | Release tools, packaging, numerical/UI integration | Full required offline matrix on one candidate, including actual caller regressions |
| P6 | Existing bench CLI/dashboard, archived results | Full supported live catalogue and bounded acquisition checks, with truthful physical facts and separate qualification |

Use small connected changes in existing modules. Do not add another daemon, workflow engine, statistics framework or classifier project. Work may proceed behind agreed interfaces, but original milestone dependencies remain the acceptance authority.

## 3. P0: prove failures before repairing them

Port the [catalogued cases](research/LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md) into maintained tests. The first twelve correspond to separately executed audit-only failures, not missing imports. Additional cases cover known budget/resume/UI/quantity/selection failures.

Mock only physical transport, clock/operator and external boundaries. The reader/gate/selector/runner being proved must execute. Use labelled synthetic data and copied acquisitions. No always-true assertions, unattached spies, numerical HTTP errors accepted as success, fake distribution metadata, weakened thresholds, silent skips or blanket ignores.

Preserve genuine a0935fb repairs: ordinary fragment refusal, constructor deferral, actual admitted T10 CH calls, whole-set cooldown, known pre-emission CE-refusal cleanup, TEN triage, gain-mismatch rejection, negative ConsoleOperator answer, same-boot expired resume, unknown C=null and h16 proxy extraction.

## 4. P1: close the managed device boundary before live work

### Raw grammar, ownership and operation permits

- Reject the valid firmware grammar bypass b'@123\tCH 1 ON 1500\n'. Parse exactly or reject unsupported external framing; literal-space partitioning is not sufficient. Cover spaces/tabs/CR, incomplete and cross-call input, unknown commands and sequence wrappers. Non-emitting firmware tests must not open a light escape.
- Acquire canonical rig ownership before journal access/open/WAKE. Keep the constructor fix, but include journal reload/parse/recovery in failed-open cleanup so every failure releases the lease and closes any opened transport.
- Resolve filesystem and tty/cu aliases, create a fresh owner generation, reject stale reservations/completions, and handle unknown boot/monotonic discontinuity without granting credit.
- Put a serialized one-use operation/permit boundary beside managed writes. Every CLI/shell, suite, scan/debug/STREAM, dashboard hold/ring/flash and food/drive-tune caller reserves or refuses. Private method names and budget=False are not exemptions.
- An unsuccessful new reservation must not erase tracking for an existing pending operation.

### Timing and durable cost

- Verify actual WDT ACK fields and refreshed readback together. Missing or contradictory facts never default to the request.
- Establish a supported board/firmware/mode finite bound, including applicable service/transaction/quantization assumptions. A cooperative WDT setting is not automatically an exact wall-clock bound. Synthetic profiles cannot admit a real port.
- Bound the actual energized rail; retain approved limits and correct n=2 / mains 2/8/8/2 behavior.
- Atomically reserve whole operations before transmission, independently per hole with rail-specific limits. Maintain permanent protocol totals independently of rolling-window pruning.
- Retain conservative charges when actual edges are unknown. Remove invented SWEEP timelines and early 800→384 ms refunds.
- Validate supported response word/sequence/hole/settings/counts/duration/completeness and fault events. Generation is host permit state; do not invent firmware telemetry.

### OFF, CE refusal and T10 classification

- A definitive supported pre-emission refusal may release only its unused reservation. Any unknown error, successful CE ACK followed by contradictory status, ambiguous mask or unverified CE state retains full charge/uncertainty.
- Inspect OFF success and supported CE/mask/channel/motor state before releasing accounting. ERR OFF or missing STATUS cannot become safe/COMPLETE.
- Same-owner OFF/STOP and close remain available despite cancellation or ledger failures. Transport closes before ownership release.
- Preserve T10.2 admission, but distinguish pre-admission unsupported cases from failures after transmission/emission. The latter are FAIL/ERROR/incomplete with safe recovery, never budget SKIP.
- Test actual T10 calls with per-write journal/permit traces, not AST inspection alone.

## 5. P2: make acquisition facts and saved records authoritative

Use the same actual preflight for start and resume, including before light-capable diagnostics. Core remains gain 1 even when both device and old snapshot say 2. Apply/ACK/read back supported mains/rate; do not substitute host cache or missing defaults.

Freeze complete finite, defensively copied configuration/map/roles, requested/applied/effective settings, calibration/current/input-range/assembly facts and their scope/origin. Use frozen or reading-specific facts for units, not today's YAML or hardcoded gain/Rf. Different-gain offline truth fixtures remain explicitly synthetic.

Implement one real ScanStore reader/writer contract preserving operation, shared reading, block/attempt, condition, setting, phase, segment and within-run position identities. Use actual rows(), not nonexistent iter_rows(). The cube writer must not silently discard these fields. Unknown stationary coordinates share a position instance; never NaN geometry, invented zero or unknown==unknown cross-run compatibility.

Seal consumed raw bytes plus interpretation mappings, settings/calibration links and relevant terminal/source revision without self-reference. Analysis identity must include code/estimator/model/numerical configuration and exact control/reference/selection inputs; truthfully record dirty-working-tree content identity.

Actual open_run/report/profile/reference consumers must verify complete required identity and live sources. NPZ mutation invalidates reuse; minimal identity is not verified; run B cannot request run A's product. Same-ID/same-content reuse is allowed; conflicting content refuses overwrite.

All supported audit/analyse/report/view routes remain source-safe, including explicit migration/refusal of bare legacy writes and canonical/symlink output containment. Historical acquisitions and reports are immutable. Saved views do no computation/writes/device construction.

## 6. P3: finite actual operator/runner workflow

Validate complete versioned schema, finite limits, exact integer holes/counts, supported settings, nested keys and override exclusivity. Reject schema999, fractional hole12.9, negative settling and unknown nested keys.

Use ConsoleOperator and real browser occurrence prompts. Generic start/light flags never answer questions. Require actual JSON Booleans; string "false", integer1, null and absent required fields are not confirmation. False/stale/duplicate answers cannot admit a measurement.

Safe pause/prompt requires supported OFF/CE/mask/channel/motor state. Workers never generate operator heartbeat. Keep the serial owner while safe-paused, but do not hold HTTP/session locks through I/O, computation or human waits.

Persistent wall/cycle limits include manual/pause/resume downtime; recheck after every wait and before the next conservative operation bound. Unknown clock/boot continuity cannot grant time.

Reserve permanent run cost in the device admission transaction BEFORE send. Timeout after transmission retains that cost. Resume loads the exact immutable ordered freeze and validates durable completed records, protocol/facts/source/ledger; do not rebuild from priors or trust completed_step. Interrupted pairs stay incomplete; bounded reacquisition uses fresh IDs and retained costs.

## 7. P4: connect science, decisions and consumers

- One resolver separates numerical availability, physical qualification, reasons and evidence origin. Connect it through derived/report/features/baselines/reference, including O-envelope branches.
- Preserve raw signed/ADC diagnostics and independently valid OPT101. Unknown Rf, unverified/outside A0 and supported clipping/nonlinearity evidence block dependent physical/quantitative uses. Global FUNCTIONAL/WARN policy is separate.
- Unknown C stays null. Bare hole IDs cannot validate controls; h8/h9 are response monitors. Require scoped source/load/condition/settings/calibration/assembly evidence and actual estimator/shared-control covariance.
- Actual stored analysis excludes pilot/scout, aggregates technical repeats, pairs by IDs at declared settings/position and preserves missingness. No truncation, duplicate N, zero-filled controls or phase pooling.
- Apply declared fixed-N intervals and frozen detector×hole×contrast family/Bonferroni policy in production. Cross-channel correlation is propagated; unsupported between-block dependence/drift limits inference.
- Valid labelled synthetic paths must produce correct estimates and applicable eligibility; neither constant-false evidence nor always-UNRESOLVED is completion. SciPy stays optional.
- Pilot variance is contrast-specific, with measured costs/remaining ledger budgets and feasible equal-cost comparator. Freeze exact pilot inputs and full ordered schedule immutably. The 1/5 fixture proves resume; N=1 cannot support a variance-estimated interval.
- One source-bound selection drives actual planner/fine/qualified report/UI and fresh acquired confirmation. Missing optical evidence yields unresolved or a separately named raw diagnostic. Labelled legacy objectives may retain their historical behavior.
- Derive actual target-context baseline requirements. Keep h16 proxy_unassigned, preserve its extraction API, and connect opt-in through batch/CLI/UI. Reuse real grouped held-out validation with equal groups/folds/support and training-only transforms; pairwise distances alone are not predictive added value.
- Render real signed observations, filters, contrasts/intervals/drift/control sensitivity and source/freeze/selection/qualification in the UI. Explicit analysis must not starve control/heartbeat.

Retain original upgrade §12 historical anchors, separate from new-estimator truth. No stop-when-positive, noisy-max qualification, raised LED drive or primary1850 inference.

## 8. P5: full offline release gate

Use genuine installed dependencies and reproducible interpreter-compatible tooling on Python 3.10 and 3.12. Obtain actual failing Python 3.10 diagnostics; do not assume the audit's five mypy 1.15 diagnostics are identical. Fix source types without broad escapes. Lint all declared maintained scope; document existing archived-script exclusions and do not add more or call narrowed scope unchanged.

Run on one candidate:

```bash
# Repository root
ruff check .
ruff format --check .

# software/host
LIO_CALLER_TEST_OUT="$(mktemp -d)"
export LIO_STATE_ROOT="$LIO_CALLER_TEST_OUT/state"
export COVERAGE_FILE="$LIO_CALLER_TEST_OUT/.coverage"
python -m mypy
python -m pytest -m "unit or sim" --lio-sim \
  --results-dir="$LIO_CALLER_TEST_OUT/run" \
  --cov=lio --cov-report=term \
  --cov-report="xml:$LIO_CALLER_TEST_OUT/coverage.xml"
python -m coverage report \
  --include="*/lio/protocol.py,*/lio/analysis.py" --fail-under=90
```

Also run maintained CE/D/new caller regressions, >=2000-family numerical tests AND integrated saved-record truth, core/precision/profiles absent/present installs and installed-wheel CLI/assets outside checkout without system-site-packages. Precision tests must execute, not silently skip. Prove actual protocol planning is offline: no Device/serial/port enumeration/WAKE/ARM.

Exercise real CLI and running browser/HTTP supported/invalid workflows, prompt/pause/abort/heartbeat/resume, analysis/acquisition concurrency, source mutation/reuse and before/after historical hashes. A server endpoint or HTTP400/404 is not numerical UI proof.

Keep failed CI red while preserving logs/coverage artifacts. Record unavailable checks as unavailable, not PASS. The objective is a new evidence-backed candidate, not a target passing-test count.

Preserve the legitimate TEN dispositions: configured A4/B10 meter mapping, >=300s drift requirements, safe PTY boundary, optical T13 rail mapping without implying ammeter proof, margin16384 and existing saturation WARN/global FUNCTIONAL policy. Do not reintroduce stale expectations or relax hardware limits.

## 9. P6: authorized live full tests

### Before connection or emission

1. Verify the intended board/port on the bench machine, current main/working-tree identity, installed environment/configuration and existing serial owner. “Connected” was owner-reported, not remotely verified by this documentation task.
2. Inspect opening/reset/keep_awake behavior: INFO/open can reset the board and energize holding coils. Do not call it passive merely because it does not step motors.
3. Use the current ownership/duty journal; never replace it with an empty/test journal or delete spending history. Resolve unknown state only through supported recovery.
4. Obtain required current operator facts, sample declaration and safe-state checks. Do not infer them from the old report or generic checkboxes.
5. Require the real capability/admission path. A simulated profile, board connection or owner authorization cannot manufacture a finite timing proof.

### Live sequence and recording

- After offline gates, run readback/status and the complete supported automatic host catalogue through the actual CLI/dashboard, using existing approved budgets. Existing dark-gain diagnostics may run as catalogue tests, with truthful settings and restoration/readback to approved core gain1. They do not qualify M7.
- Run the interactive/motion parts of the full catalogue when actual responses and trusted limits/sample clearance are available. No auto-confirmation, homing/rebasing, guessed travel or fabricated position. If prerequisites are unavailable, record the precise unrun portions and continue independent checks.
- Exercise a bounded fixed-position capture→persist→analyse→report path and controlled pause/abort/resume through existing software when admission permits. Motion/height capture remains within existing trusted limits; do not expand into an unplanned exposure campaign.
- If an operation is unsupported, refuse before transmission and report its true SKIP/blocker. If emission occurred and OFF/status/transport fails, retain worst-case cost, stop new emission and record FAIL/ERROR/incomplete. Do not classify it as a benign unsupported test.
- Do not retry until positive, adjust thresholds, raise current or change wiring to turn the report green. Planned retries are finite, justified and charged.
- Preserve actual software tests separately from optical/measurement health. A live NOT FUNCTIONAL result is a legitimate measured outcome, not a reason to fake software PASS or suppress data.

Current CLI shape, to be verified against the final implementation:

```bash
# Define these from the real bench/session, not invented defaults:
# LIO_TEST_PORT, LIO_SAMPLE_ID, LIO_OPERATOR_ID, LIO_LIVE_RESULTS

lio --port "$LIO_TEST_PORT" selftest \
  --sample-id "$LIO_SAMPLE_ID" --operator "$LIO_OPERATOR_ID" \
  --results-dir "$LIO_LIVE_RESULTS"

# Full interactive/motion catalogue only with actual responses and trusted
# existing travel/clearance prerequisites; retain operator interaction:
lio --port "$LIO_TEST_PORT" selftest --interactive --allow-motion \
  --sample-id "$LIO_SAMPLE_ID" --operator "$LIO_OPERATOR_ID" \
  --results-dir "$LIO_LIVE_RESULTS"
```

These are future coding-agent actions, not commands executed by this documentation publication. Do not silently skip a test section or say all hardware passed because available subsets did.

Archive run ID, timestamps, actual source+dirty-content identity, dependency versions, config/map/calibration/assembly facts, permissions/answers, raw counts/streams, operation/journal traces, reported timing, status/events and report. Keep physical stage state local/ignored. Never overwrite the earlier archived report.

The old live run remains NOT FUNCTIONAL with high InGaAs noise/under-threshold responses, both watchdog requests skipped and root cause unresolved. No evidence here identifies dead LEDs/driver/detector or verifies A0/Rf. New reports must retain that distinction.

## 10. Completion evidence

Deliver actual caller/test/output evidence for every D01–D20 variant and CE01–CE14, keeping original milestone definitions:

| Original milestone | Required connected proof |
|---|---|
| M0 | Frozen facts/units, strict live-source identity/reuse, actual compatibility consumers |
| M1 | Owner/permit/finite timing/durable cost/OFF and recovery, plus explicit real admission limits |
| M2 | Independent roles, scoped controls, unidentified C and actual covariance |
| M3 | Stored block/condition/phase truth, pairing, joint uncertainty and fixed family |
| M4 | Finite real runner/operator controls, permanent budgets, measured allocation and exact resume |
| M5 | Shared source-bound selection and fresh acquired confirmation |
| M6 | Real CLI/browser/report/profile integration and full required release matrix |
| M7 | Deferred/isolated; no new experiment authorization |

Report source changes, tested candidate identity, exact commands/results, working final syntax/migrations, source-byte invariance, archived live outcomes and precise remaining software/capability/physical blockers. Correct project-state/README/acceptance claims around actual evidence.

Complete all feasible implementation and tests. Do not return another plan, parser-only repair or helper-only closure. Do not pause to reconfirm already-granted general test permission; ask only genuinely missing required operator facts/decisions and continue independent work.

**No measured SNR improvement or recovered SWIR/1850 chemistry is justified by software completion.**
