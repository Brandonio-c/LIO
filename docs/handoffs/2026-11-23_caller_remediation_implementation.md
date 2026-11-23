# Coding-agent handoff: caller remediation and full offline/live tests

Invoke the coding agent with this document. The owner reports the board connected and has requested implementation plus full tests.

## Read first

Read applicable AGENTS/.agents instructions, then IN FULL:

1. docs/SENSOR_READINGS_CALLER_REMEDIATION_PLAN.md
2. docs/research/LIO_V3_RESIDUAL_REMEDIATION_QA_a0935fb_2026-11-23.md
3. docs/research/LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md
4. docs/SENSOR_READINGS_UPGRADE_PLAN.md (ORIGINAL M0–M6 and §12)
5. docs/SENSOR_READINGS_REMEDIATION_PLAN.md
6. docs/handoffs/2026-11-23_residual_remediation_acceptance.md and residual research prompt, as historical implementer claims
7. .agents/project-state.md and test_results/README.md
8. test_results/20261123-135504_host_residual_hw/report.md

## Task

You are the coding agent for Brandonio-c/LIO. Pull latest main and implement all remaining caller-level sensor-readings repairs, then run full offline and authorized live tests. Do the work; do not return another plan or helper-only closure.

Baseline is a0935fb322e9a42459f577417b0167cfec830bfe plus the documentation commit containing this handoff. Preserve newer compatible repairs/local owner work. Main only; no destructive reset/clean, force push or Git-config changes.

Preserve D03=ownership, D04=OFF and original milestone definitions. The maintained baseline is green on Python 3.12 (120 targeted; 918 full passes / 0 failures / 12 skips; 98% subset gate). Twelve independent actual-caller acceptance tests fail and Python 3.10 CI mypy fails. Passing inherited tests does not close the contracts.

### Implement

Follow packages P0–P6 in the plan:

- Add maintained actual-caller versions of all A01–A24 catalogue cases. Mock only transport/operator/clock/external boundaries. Do not mock the reader/gate/selector/runner being proved.
- Fix valid-TAB raw sequence bypass; preserve fragment refusal. Keep constructor deferral, fix failed-open lease cleanup, canonical aliases/generations/boot recovery and one serialized permit boundary.
- Fix contradictory CE/drop_pending handling, safe_off verification, complete response/energized-rail validation, strict finite timing capability and conservative durable rolling/permanent cost. No invented watchdog margin or SWEEP edges/refunds.
- Preserve admitted T10 pulses but classify post-emission OFF failure as failure, not unsupported SKIP.
- Implement truthful start/resume preflight/core gain1, complete immutable facts and authoritative ScanStore identities. Actual saved readers must exclude pilot, preserve conditions and unknown stationary position, validate all consumed sources and report/run association.
- Fix permanent pre-send costs, occurrence-specific real answers/strict JSON Booleans, safe pause/heartbeat/deadlines and exact immutable restart schedule.
- Connect actual quantity/control/reference/baseline gates, paired/shared-control/frozen-family statistics, measured allocation, source-bound selection and fresh acquired confirmation.
- Finish actual proxy opt-in/grouped held-out profiles and browser numerical/control integration. H16 stays proxy_unassigned; raw/valid OPT101 remain available; no always-UNRESOLVED substitute for supported synthetic paths.
- Preserve the legitimate TEN corrections and production limits. Do not change currents, 300 s drift requirement, margin16384, saturation threshold or existing WARN-only global FUNCTIONAL policy merely for green tests.

### Full offline verification

Use genuine installed interpreter-compatible dependencies on Python 3.10/3.12. Run full Ruff/format, full strict mypy, CE/D/new actual-caller regressions, complete unit/simulator/fault tests WITH coverage and the existing 90% protocol/analysis gate. Retain >=2000-family tests AND saved-record numerical truth. Test isolated core/precision/profiles installs, wheel outside checkout, actual CLI/browser/HTTP positive and invalid paths, pause/abort/resume/concurrency and historical byte invariance.

No weakened checks, new blanket exclusions, fake metadata or skipped contract failures. Keep failed CI red and archive logs. Record missing platforms/checks honestly and finish independent work.

### Hardware authorization and sequence

The owner now authorizes live connection, readback, automatic host catalogue and full supported hardware tests after offline safety/admission gates pass. Interactive and existing T09/T13 motion tests are in scope when their existing operator, sample-clearance and trusted-limit prerequisites are actually satisfied. Do not ask again for this general permission.

Use real operator/UI answers where required; do not infer them from board connection or an old run. If required facts/answers are unavailable, ask only for those missing facts, continue independent tests, and record the precise blocked sections.

Respect the current serial owner/dashboard. Do not kill/restart it or steal the port. Opening/INFO may reset the board or POWER WAKE holding coils; account for that behavior.

No firmware edit/flash, wiring/current/pot change, raised drive, relaxed travel/exposure limit, automatic homing/rebasing or fabricated physical stage state. Normal truthful tracking updates from authorized movement remain local/ignored. A0/Rf/ammeter/optical/reference work stays owner-deferred. M7 stays deferred.

Run the complete supported automatic catalogue, interactive/motion sections when actual prerequisites are met, and bounded capture→persist→analyse→report plus pause/abort/resume acceptance. Use existing CLI/dashboard. Every emission must pass the repaired real gateway; synthetic profiles cannot authorize a real port.

If a finite existing-capability bound cannot be supported, refuse the operation and record unsupported status. Never bypass admission to complete a test. If emission occurred and OFF/status fails, retain worst-case charge, stop new emission and report FAIL/ERROR/incomplete. Do not retry until positive or tune optics verdicts.

Archive exact software/dirty-content identity, environment/config/readback, operator answers, raw observations/timing/events/journal traces and reports. Restore/read back approved core gain/settings after supported diagnostics. Do not overwrite historical runs or publish physical stage_position.json.

A live NOT FUNCTIONAL outcome may persist; report its observations and unknown causes separately from software acceptance. Existing T06.2 PASS versus stricter T03.2 FAIL is not contradictory; T05.5 unjudged and T10.2 SKIP are not positive optical/watchdog evidence.

### Deliver

Complete reviewable implementation and all feasible tests. Report changed files, tested candidate/versions, exact commands/results, A/CE/D closure tied to actual callers, ORIGINAL M0–M6 matrix, source-byte invariance, working syntax/migrations, archived live results and exact remaining blockers.

Update status/README/acceptance docs to the tested reality. Implementation commit/push follows the coding-session instruction; this documentation publication is not blanket future code-push permission. Do not stall implementation asking about push.

No measured SNR improvement or recovered SWIR/1850 chemistry claim follows from software completion.
