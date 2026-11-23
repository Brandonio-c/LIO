# LIO V3 sensor-readings remediation plan

**Status:** implementation specification after independent QA; remediation has not been implemented by publishing this document.  
**Date:** 23 November 2026.  
**Audited implementation:** [main at 38eb8e6](https://github.com/Brandonio-c/LIO/commit/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8). Reconcile newer commits before editing.  
**Scope:** host software, simulator, tests, packaging and documentation. Core acquisition remains the owner-approved fixed gain 1.

Read the [QA report](research/LIO_V3_SENSOR_READINGS_QA_2026-11-23.md), [original upgrade specification](SENSOR_READINGS_UPGRADE_PLAN.md), [research assessment](research/LIO_V3_SENSOR_INFORMATION_ASSESSMENT_2026-11-23.md), and [remediation handoff](handoffs/2026-11-23_sensor_readings_remediation.md). This plan supplies concrete repairs and release gates; it does not waive the original M0–M6 scientific or safety contracts. Earlier “M0–M6 done”, “M7 complete” and “remaining bench-only” statements are superseded by the QA finding of partial implementation.

## 1. Required outcome and authorization

Deliver an actual working CLI/dashboard workflow for bounded fixed-position repeats, truthful acquisition facts, signed block estimates and quantity-specific eligibility. Fix existing callers and persistence, not just isolated helpers. Do not substitute an always-UNRESOLVED placeholder for the required tested valid-input path, or satisfy qualification gates by deleting raw data.

This publication authorizes documentation changes and their push to main only. The accompanying coding-agent prompt directs offline host remediation and testing when invoked. It does not authorize a real connection, POWER WAKE, motor movement, LEDs, firmware edit/flash, wiring/current changes, invented physical confirmations, physical stage-state edits or a live-dashboard restart. Implementation commits/pushes require the owner's authorization in that implementation session; this docs-only push is not blanket code-push permission.

A0, Rf and ammeter checks remain owner-deferred. Their absence blocks the specified InGaAs physical/quantitative claims, not offline implementation or raw-count exploration. Never promote code/simulator success into bench, optical-control or reference qualification.

## 2. Order and completion discipline

| Stage | Repair | Depends on | Required usable result |
|---|---|---|---|
| R0 | Preserve evidence; turn QA counterexamples into regression tests; correct status claims | None | Pinned fixtures, failure register, baseline CI evidence |
| R1 | One owner, authoritative light gate, conservative durable exposure, emergency OFF | R0 | Every real emitting path gated or explicitly refused; fault tests through actual callers |
| R2 | Actual acquisition facts, complete seals and immutable analysis identity | R0; safe real preflight uses R1 | New runs record applied settings; every consumed-input mutation invalidates reuse |
| R3 | Quantity/compatibility gates and evidence-backed channel/control roles | R2 | Valid and unqualified paths behave correctly in actual consumers |
| R4 | Identified fixed-N blocks, paired contrasts and uncertainty | R2–R3 | Numerically tested estimands, missingness/covariance/familywise policy |
| R5 | Finite protocol lifecycle, controls, checkpoints, budgets and resume | R1–R4 | CLI and dashboard execute a complete fixed-allocation workflow in simulation |
| R6 | Measured pilot freeze and one shared scout/confirm objective | R4–R5 | Real schedule/placement changes follow the frozen rule and independent confirmation |
| R7 | Complete profiles, baseline selection, reports and numerical UI | R3–R6 | Same selected product/eligibility/selection identities across tools |
| R8 | Release verification, migration and truthful M7 boundary | All above | Green required checks and evidence-backed M0–M6 acceptance matrix |

R1 and read-only R2–R4 work can proceed in parallel, but do not expose new real light-capable operation before R1 acceptance. Each stage needs a real caller-level integration test and persisted outputs before being called complete. Preserve the original plan's vertical slices: R5 must already offer usable fixed-allocation capture/analysis; R6 adds allocation/targeting rather than delaying everything behind it.

Do not mark a stage complete because a module exists, a payload has a key, or a helper ignores its inputs and returns a nominal answer. Keep unresolved capability gaps visible.

## 3. Failure register: reproduce, repair, prove

Source/test references and observed outputs are in the pinned [QA report](research/LIO_V3_SENSOR_READINGS_QA_2026-11-23.md). Test names below describe required cases, not already-existing APIs.

| ID | Observed counterexample at audited main | Required post-repair behavior | Stage |
|---|---|---|---|
| D01 | Shell CH1 1500 ms bypasses a 1000 ms budget; SR+CE bypasses accounting; real duty=False removes journal | Every emitting entry point reserves or refuses before transmission, irrespective of public bypass knobs | R1 |
| D02 | SWEEP returns 16 holes but durably charges only h16 | Whole operation reserves every possible exposure atomically; complete/partial results retain correct charges | R1 |
| D03 | Two preconstructed journal objects let the second erase a prior 900 ms charge | Ownership acquisition reloads/validates current durable state; stale objects/generations cannot spend or overwrite | R1 |
| D04 | Pending cancellation makes safe_off skip OFF; simulated CE stays high | Same-owner OFF/STOP works despite cancel/ledger errors; close always closes transport before releasing ownership | R1 |
| D05 | Returned 2001 ms accepted against a nominal 24.625 ms reservation and 1000 ms rolling duty budget | Supported conservative pulse bound before send; overrun/malformed/stale/partial response aborts and retains worst-case cost | R1 |
| D06 | Core height scan accepts gain 2 but records gain 1; 50 Hz plan records60; targeted path records mains without applying it | Core gain mismatch/missing readback rejects before light; acknowledged applied mains/gain/LSB match writer and reader | R2, R5 |
| D07 | Outside-range A0/unknown Rf still permit profile ratio reason=ok | Actual consumer gates block InGaAs physical current/quantitative optics/reference, preserving raw/ADC diagnostics and valid OPT101 | R3, R7 |
| D08 | Different config or NPZ input yields different outputs under the same ID/path | All consumed inputs/settings identified; same-ID/different-content is an error, never an overwrite | R2 |
| D09 | New legacy analysis with derived-out rewrites source analysis.json | Explicit analysis/report/audit writes only beneath derived-out; hashes of source files remain identical | R2 |
| D10 | Altering a raw stream leaves a new height run's terminal seal unchanged | Seal covers every raw file and relevant terminal facts without self-reference; revisions explicit | R2 |
| D11 | “Validated” controls inferred from expect/range include h6/h7 without evidence | Evidence-backed compatible controls only; candidate sensitivity and legacy estimates remain separate; unknown C=null | R3 |
| D12 | Varying heights become17 “blocks”; unequal [10,11,100]/[0,1] gives CI[10,10] | Correct phase/condition/block joins; no truncation/deduplication fiction; valid signed contrasts, covariance and qualification policy | R4 |
| D13 | all_off=false/no_motion=false checkpoint proceeds; one checkbox confirms future interventions | Verified safe state before occurrence-specific prompt; fresh linked answer required; failed/unknown states prevent MEAS | R5 |
| D14 | Pause=true and expired heartbeat still complete a protocol | Actual runner pauses at verified OFF, emits nothing while paused/prompting, remains responsive and safely abortable | R5 |
| D15 |300 ms reported under 200 ms total cap completes; cycle cap ignored; changed-facts half-block resume accepted | Persistent cumulative budgets, supported command bounds and completed-block resume; altered facts rejected | R5 |
| D16 | Measured pilot never changes production; allocator chooses 5,1 where equal3,3 is better at equal cost | Production freezes from actual pilot facts; bounded allocator meets stated objective/comparator without extra budget | R6 |
| D17 | H16 residual changes actual fine optimum; shared helper unused | Actual planner/fine/report/UI consume one frozen target-selection result; blind/h16 extremes cannot steer primary objective | R6 |
| D18 | Missing baseline geometry/model/reference passes; proxy extraction absent; “held-out” means full-batch distance | Fail-closed quantitative compatibility, semantic feature masks and real grouped held-out assessment | R7 |
| D19 | Hardware protocol CLI always refuses; protocol resume misroutes; numerical UI/progress incomplete | Working authorized-runtime routes and real UI inspection/control paths tested offline | R5, R7 |
| D20 | Completion claims despite red Ruff/mypy and skipped tests/coverage | Green required verification, accurate status and explicit capability/bench limits | R0, R8 |

## 4. R0 — Establish the repair baseline

1. Inspect status/history and applicable agent instructions. Fast-forward main only when local work is preserved. No side branches, reset/clean, force push or Git-config changes.
2. Record the current main SHA and compare with 38eb8e6. Reproduce each applicable D-case; if already fixed, retain a regression proving it. Do not overwrite newer owner changes or mechanically reapply old patches.
3. Preserve exact historical cubes, metadata, reports, NPZ streams and tray-v3 anchors. Tests read them or use temporary copies. Only test_results/stage_position.json remains local/ignored; never use or commit a fabricated physical position.
4. Restore lint/type checking early and record pre-existing failures separately from new ones. The audited [CI run](https://github.com/Brandonio-c/LIO/actions/runs/45131415874) failed Ruff and mypy 3.10/3.12 before tests; it supplies no passing-suite evidence.
5. Maintain a D01–D20 tracking table with failing test, repair location, passing evidence and unresolved limitations.

## 5. R1 — Repair exposure and device ownership first

**Primary files:** ownership.py, device.py, transport.py; CLI shell, dashboard, drive-tune, food/selftest/debug/STREAM/hold callers; ownership and fault tests.

- Acquire one canonical per-rig OS lease before journal load/mutation, serial open or POWER WAKE. Resolve tty/cu and filesystem aliases and use stable device identity where available; unknown identity requires a conservative shared fallback, not fresh budgets. Use serial exclusive mode where supported. Constructors must not rewrite a live owner's pending reservations.
- Load, validate and transact durable state under that lease. Use a new connection/owner generation; validate it at every reserve/completion. Support the correct per-hole rolling budget (rail selects the limit), with pending reservations counted. Fsync failures, semantic corruption, boot discontinuity and unreadable state fail closed. Use actual Linux/macOS boot identity providers or conservative unknown-state handling, never AppleSetupDone/root ctime as proof of boot identity.
- Put an authoritative operation/permit boundary adjacent to managed transport writes. Public raw/shell commands must route through guarded typed operations or be rejected if they can emit, alter exposure limits or bypass state. Include CE/select combinations, CH, MEAS, SWEEP, STREAM, debug and hold paths; reject ambiguous/multiline/raw escape routes. Real duty=False/budget=False cannot disable accounting. Isolate simulator-only faults explicitly.
- Reserve a whole operation before sending it. SWEEP needs an atomic set of all potential per-hole charges, not one overwritten pending slot. Partial/duplicate/missing records cannot erase reservations. Do not fabricate edge times by concatenating reported durations.
- Bound possible exposure before transmission, then validate hole/sequence/settings/generation, finite duration, WDT/BOOT events, completeness and OFF. Missing true edges means retaining conservative reserved charges through verified OFF plus a full duty window. Returned shorter sample spans are not automatic credit.
- Give emergency OFF/STOP/RELEASE a cancellation-independent, ledger-independent path through the current owner and serialized writer. Never open a competing serial connection. Failure to verify OFF retains uncertain recovery state. Nested finally blocks must close the transport even if accounting or safe-off fails, then release ownership.
- Recovery establishes all-off, conservative cooldown and fresh authorization before any emission. Reconnect/resume never grants fresh credit or auto-emits.

### Exposure-bound constraint in existing firmware

The [current watchdog](https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/firmware/lio_firmware/optics.cpp#L87) is checked by [cooperative service()](https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/firmware/lio_firmware/safety.cpp#L77), not a proven zero-latency interrupt. WDT settings are integer milliseconds with a [50 ms minimum](https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/firmware/lio_firmware/config.h#L66); firmware MEAS uses its rail watchdog, not the host's nominal duration estimate. A reserve of 24.625 ms plus an assumed exact watchdog is invalid.

Implement a versioned supported board/firmware/mode timing capability profile: cap/readback semantics, timer quantization, bounded service/transaction delays, buffered versus serial-limited streaming, applicable assumptions and evidence. Choose and verify an existing watchdog cap that permits the operation and whose conservative total exposure bound fits remaining approved budgets. Do not invent a numeric latency margin or raise owner-approved limits.

If a finite conservative bound cannot be supported for the current capability, refuse that real emitting operation before transmission, implement/test the explicit unsupported path and report the remaining capability gap. Do not call strict M1 complete or quietly weaken it. This is not permission to edit/flash firmware.

**Proof gate:** reverse D01–D05 through actual callers. Add competing-process/alias tests, stale pre-lock objects, all 16 SWEEP charges, reserve/transmit/record/OFF/commit/close crash boundaries, clock/boot changes, missing/mismatched cap readback, minimum/rounding boundaries, malformed/overrun/partial/stale responses and pending cancel plus ledger failure. No test may discover a real port.

## 6. R2 — Make acquisition facts and derived identity truthful

**Primary files:** scan/provenance.py, calibration.py, store.py, executor.py, scan/__init__.py, derived.py, food_profiles/runs.py.

- Verify actual INFO fields (gain, mains, rate and supported capabilities), using typed accessors. INFO does not supply adc_gain. Missing gain is not gain 1. Core new acquisition rejects non1/missing/unsupported gain before measurement; do not silently change PGA and retain old range evidence.
- Apply supported mains configuration, validate acknowledgement, refresh/read back state and update caches from acknowledged facts. Distinguish mains periods from ordinary conversion N; record configured versus effective rate and sequential detector order. Exact per-detector ADC windows remain unknown.
- Freeze the initial snapshot after successful preflight and before the first reading. Store complete configuration/channel-map/role content and evidence, requested/applied settings, rig/protocol/calibration/assembly epochs, Rf/current provenance and scoped input-range evidence. A file path/hash alone is not the frozen content. Defensively copy and canonically serialize nested facts, reject NaN/Inf, and prove later in-memory configuration changes cannot mutate the frozen manifest. Preserve unknown/conflicting facts; invalidate range verification after relevant analog/gain/mux/wiring changes.
- Write stable reading/block/condition/setting/phase IDs, shared reading ID for both rows of one MEAS, requested/applied settings, command bounds, reported on-time and timing quality. Preserve all returned signed dark/lit/net values and technical-repeat grouping.
- Seal the frozen snapshot, all raw cubes/NPZ/sidecars and canonical relevant terminal metadata/status/revision. Avoid hashing the seal into itself. Interrupted/resumed segments and later terminal revisions remain explicit; old products cannot masquerade as final.
- Analysis identity must cover complete consumed sources/seal/revision, actual analysis configuration/map/roles, model/estimator versions, numerical selections/settings and exact reference/control identities. Historical acquisition config and current analysis config are distinct inputs.
- Use one strict validity resolver in report/profile/reference/baseline consumers. Missing required identity fields, incomplete status, unknown compatibility or mismatch rejects quantitative reuse while preserving inspection.
- Refactor legacy computation to be side-effect free when called by new audit/analyse/report commands. Write under derived-out only. Deterministic repeated inputs must reuse verified immutable content; same ID/different content raises a conflict instead of replacing a file.

**Proof gate:** D06/D08–D10. Test applied gain 2 refusal in new core acquisition and correct supported different-gain interpretation by offline readers; 50 Hz and mains-off truth; source/stream/metadata/config/control/reference/estimator mutation; partial revisions; source-folder hashes invariant; existing-output conflict; missing fields rejected by actual readers. Synthetic different-gain fixtures stay labelled synthetic. Historical gain 1 records are not rewritten.

## 7. R3 — Enforce quantity and control semantics in every consumer

**Primary files:** provenance/calibration; analysis/coupling.py; derived/report; profile readers, features, schema and baselines.

Maintain explicit estimands and separate numerical availability from physical qualification:

| Quantity | Required behavior |
|---|---|
| Signed counts / descriptive drive response | Available without Rf; preserve negatives, zeros, missingness and labels |
| ADC-referred volts / conditional equivalent arithmetic | Supported actual LSB; conditional Rf arithmetic clearly distinguished from qualified physical current |
| Diagnostic count ratios | Only where mathematically defined and explicitly labelled diagnostic; no implied optical/reference qualification |
| InGaAs physical current / quantitative optics / reference use | Block if Rf unsupported/unknown or A0 unverified/outside range, per owner contract; require applicable calibration/control/geometry compatibility |
| Independently valid OPT101 quantities | Remain available despite InGaAs qualification failures |
| Corrected optical estimates | Require identified compatible C and uncertainty; unidentified C is null, never0 |
| Primary chemistry | Requires appropriate spectral/optical/reference evidence; current h16 cannot qualify as primary1850 |

Roles must be independent of diagnostic expect. Validated-control requires load-preserving optical/control evidence, compatible source/epoch and uncertainty, not nominal wavelength alone. H6/h7, broadband and h16 are not guaranteed blinds. Keep legacy_blind_median/current-ratio inference and candidate sensitivity explicitly labelled and separate from qualified correction. Do not change weak/expect/thresholds to hide findings.

H16 stays spectrally unassigned/proxy_unassigned; h15 remains cutoff-sensitive and broadband remains broadband. Evidence for drive response, optical path, target modulation, spectral kernel and held-out proxy value are separate assertions, not automatic consequences of height dependence.

**Proof gate:** D07/D11 through derived output and actual profile/reference/baseline consumers, including valid-input fixtures. Unknown/invalid InGaAs evidence blocks only dependent quantities, not raw/valid OPT101. Missing required geometry/model/reference fails quantitative selection; unknown==unknown is not compatible.

## 8. R4 — Implement the actual fixed-N block estimator

**Primary files:** analysis/uncertainty.py, derived.py, shared raw reader, profile/report adapters.

- Define the block estimand at fixed declared geometry/settings/condition. Two detector rows from one MEAS are linked observations, not independent blocks. Aggregate technical repeats within blocks and retain block/session identity.
- Keep pilot/scout separate from production/confirmation. Never silently pool heights, directions, settings, optical conditions or phases into 17 independent repeats.
- Pair conditions by immutable block/condition IDs. Reject duplicate/ambiguous joins and unmatched input arrays, or return explicit incomplete/unresolved reasons. No truncation, zero-fill or pseudoreplication.
- Estimate signed drive response and matched blocked/unblocked contrasts; propagate uncertainty of C and the joint cross-channel covariance created by a shared control. Raw variance across candidate rows is not covariance of the C estimator.
- Report planned/observed complete blocks, missingness, drift/instability, assumptions, effect/units and interval availability. Unknown covariance or insufficient independent blocks cannot qualify narrow corrected intervals. Raw-count intervals can remain available under their stated assumptions even when physical qualification is blocked.
- Freeze the detector×hole×contrast family before production. Implement the declared fixed-N t/paired-t method with Bonferroni simultaneous intervals/tests as the first implementation (alpha divided by the frozen family size), or a documented and tested equally conservative predeclared familywise method. Do not silently shrink the family when channels fail. No stop-when-positive or ordinary-CI optional stopping.
- Keep SciPy optional: capture, audit and basic summaries work without it; interval-dependent inference reports why unavailable.

**Proof gate:** D12 and plan §12. Test signed/zero/null/contaminated/missing/correlated/duplicated data, unequal arrays and shared-control covariance against numerical truth. Predeclare Monte Carlo models, seed, sample counts and bias/coverage/FWER tolerances before evaluating results; use at least 2000 independent null families with a 32-channel example at alpha=0.05, plus signed-signal and missingness cases. Evaluate tolerances with documented binomial/Monte Carlo uncertainty; invalid correlated-block assumptions must yield limited/unqualified inference rather than be advertised as nominal coverage. Do not tune seeds/tolerances to real-run verdicts. Test the integrated analysis selection, not just standalone arithmetic.

## 9. R5 — Finish the finite acquisition lifecycle

**Primary files:** scan/acquisition.py, typed ADC configuration, CLI protocol run/resume, dashboard/protocol_job.py, session.py and control endpoints.

Use one runner behind CLI and dashboard with explicit preflight/configure/readback/snapshot/acquire/checkpoint/paused/stopping/complete/incomplete states. Static operation never arms or moves motors; an unknown coordinate stays unknown and limits geometry reuse.

- Validate the complete versioned schema: supported version, exact integer holes/counts, finite positive budgets, supported firmware settings, nested unknown keys, declared sample/assembly/detector mapping, conditions and inference split. Add explicit supported mains frequency/mode/count semantics; version changed semantics and update/test the example. Existing saved runs without applied evidence remain unverified. Reject ambiguous ad-hoc overrides with protocol mode.
- Remove the hard-coded implementation-session refusal from the real CLI branch only after the actual runtime permission/preflight/ownership gates exist. Offline tests exercise the real branch with a fake transport. Planning/audit/analysis/view paths must never construct a real device.
- Wire pause, heartbeat, abort and live progress into actual acquisition and waits. Before reporting paused, establish verified OFF. No new MEAS while paused or awaiting a prompt. Hold the OS owner/device lease through safe pause, but never block HTTP control/view locks on serial I/O, prompts or analysis.
- Establish OFF and no-motion before presenting each manual intervention prompt. Failed/unknown states stop acquisition. Use existing CLI operator/session prompt facilities, with run/block/condition/occurrence IDs; stale answers rejected. A start checkbox cannot confirm every future block/unblock. Abort releases waits without inventing an answer.
- Enforce rolling duty and separate experiment-wide total exposure, elapsed/cycle time and block caps. Persist cumulative reserved/actual/uncertain exposure, including failed, discarded and reacquired blocks. Check conservative next-command completion/exposure bounds before starting. Define pause/manual-intervention time explicitly and show the same semantics in plan/UI.
- Resume validates original protocol, production freeze, actual calibration/config/assembly/rig/source revision and fresh authorization. Preserve all spent budgets and clock continuity; unknown reboot/time continuity fails closed. Interrupted condition pairs stay incomplete; if budgets permit, acquire a whole new block with a new ID rather than completing an old pair across interruptions.

Target CLI contract, retaining existing legacy syntax when no protocol is involved:

    lio scan plan --protocol protocol.json --json plan.json
    lio scan run --protocol protocol.json --allow-light --sample SAMPLE --out RESULTS
    lio scan resume RUN --allow-light
    lio scan audit RUN --model legacy|qualified-v2 --derived-out DERIVED
    lio scan analyse RUN --model qualified-v2 --derived-out DERIVED
    lio scan report RUN --analysis ANALYSIS_ID --derived-out DERIVED

These are implementation acceptance targets, not authorization to run on hardware. Global simulator/port options retain the existing CLI placement. Resume must detect a frozen protocol run and route correctly; do not accept changed protocol overrides.

**Proof gate:** D06/D13–D15/D19 via fake exact traces and real CLI/dashboard job/HTTP flows. Boot mains 0 must be configured before MEAS and match saved facts. No light on gain/mains mismatch or bad state. Pause/heartbeat/answer/abort endpoints remain responsive during delayed commands.300 ms against 200 ms cannot complete; changed facts/partial block cannot resume as valid.

## 10. R6 — Measured pilot freeze and shared targeting

### Pilot allocation

The initial snapshot freezes pilot design, allocation rule, possible production space, weights, controls and hard budgets. After collecting identified independent pilot blocks, compute measured variance/cost and write a separate immutable production-freeze artifact referencing exact pilot sources/IDs, assumptions, remaining budgets, chosen allocation and schedule hash. Do not mutate the initial snapshot or relabel priors/default 1 as measured variance.

Exclude pilot from confirmation. Production values cannot change its schedule or stop rule. Replace constant score/cost priority with an allocation appropriate to the declared objective. Marginal improvement for the current sum-of-standard-errors objective depends on current N; unequal integer costs may require a bounded discrete solver or an explicitly labelled heuristic. Include a feasible equal-allocation comparator/fallback under identical total costs, control floors, wall limits and caps, including pilot overhead. Do not claim global optimality without proof.

### Height selection

One versioned target-selection result must drive actual planner/fine placement, confirmation, report and UI. Persist objective/weights/eligibility, source hashes, safe grid, score/precision evidence, chosen height or unresolved reason and confirmation split. Freeze it before collecting held-out confirmation blocks.

Remove the qualified path's all-channel/noise maximum. Keep old objectives only under labelled legacy reproduction. Adding h16/blind extremes cannot change primary-SWIR placement. Missing targets/evidence or flat objectives return unresolved without fallback. If only raw drive-response scouting is supported, expose that as a different named diagnostic objective; do not call it qualified optical targeting.

**Proof gate:** D16–D17. Actual pilot perturbation changes frozen production; production perturbation cannot. With equal costs, equal weights and equal variances, six production readings after identical pilot overhead choose 3,3 rather than 5,1. Test useful unequal-cost/cap-constrained cases. End-to-end fine placement and planner/report/UI share one selection ID; independently acquired confirmation cannot alter frozen height. Never extend limits/home/rebase or infer sample gaps from CAD.

## 11. R7 — Complete downstream tools and user-visible evidence

- Let consumers select an explicit immutable derived product/revision and route through the common validity/quantity resolver. A complete run, matching gain or stage bounds alone does not establish compatible calibration/geometry/reference.
- Keep primary/cutoff/proxy/missing/unresolved feature masks consistent. Test actual opt-in h16 proxy extraction and default primary exclusion, not only manually constructed feature IDs. H16 is never a primary1850 namespace.
- Baseline selection must reject missing required facts and compare actual assembly/sample-plane, analog/calibration epoch, model, control/reference source and completion. Preserve raw comparisons with explicit reasons. Suite YAML, scan baseline, empty holder and calibrated white reference remain distinct.
- Replace or rename full-batch distance ablation honestly. A held-out added-value claim needs identical independent preparation/lot/day/session grouped splits, training-only fitted transforms, declared held-out metric/uncertainty and equal rows/support. Reuse existing profile validation tools; do not start a new classifier project. Insufficient measured groups yields unavailable, while synthetic fixtures test the valid path.
- Expose signed raw dark/lit/net observations, block/condition/setting/phase filters, paired contrasts, intervals, drift, C sensitivity, evaluated-hole scope and quantity eligibility in CLI/report/Scan UI. Show historical recorded verdicts/disagreements separately from new model output; h8/h9-only SNR never certifies h12–h15.
- Saved views do no analysis/writes/USB. Explicit analysis runs off acquisition/HTTP control threads without holding device locks or starving heartbeat. Preserve no-food-library and optional extras operation.

**Proof gate:** D07/D18–D19 through actual feature extraction, baseline/reference selection, report and HTTP/UI flows, including simultaneous acquisition/control and offline analysis. Nov19 disagreement is displayed; valid OPT101 remains visible when InGaAs is unqualified.

## 12. R8 — Release verification and M7 boundary

M7 remains a deferred experimental extension, not part of core M0–M6 acceptance. Keep default paths isolated from it and do not expand into PGA experiments/GLS/periodic modulation. Harden accidental use as needed: no missing-readback default, no applying a requested-gain label without actual setting/readback, no partial-stream sample span credited as exposure, no unsupported physical qualification. A synthetic override must not authorize real hardware. Document incomplete capability; a stub is not a complete acquisition method. Finishing M7 requires separate priority and qualification.

Required final verification:

1. Add regression tests reversing D01–D20, using actual caller paths. Retain golden legacy tests separately from synthetic estimator-truth tests.
2. Assert all original plan §12 facts: 764/544/17 rows; h16 vector/up-down differences; both detectors' C sensitivities; current h12 alternative and still-negative h13/h14; Nov19 h12 instability 181 and verdict disagreement; integration 78→640 ms with absent repeat variance; gain/Rf conditional arithmetic; censored 22.4 dB h8/h9 scope; shared covariance/null/coverage/FWER; no optional stopping; safety lifecycle faults.
3. Verify source bytes unchanged across every audit/analyse/report/view mode. Mutate each consumed source/config/control/reference input in temporary copies and prove identity/reuse changes. Verify deterministic repeat output and conflict handling.
4. Run the repository's Ruff check/format, strict mypy, unit/simulator/fault matrix and existing coverage gate on supported Python 3.10/3.12. Exercise core, precision absent/present, profiles extras and installed-wheel offline operation. Do not weaken checks, exclude new modules, skip failing contract tests or fabricate pass logs.
5. Exercise CLI/dashboard preview, run, prompt, pause, abort, heartbeat, resume, numerical reports/profiles and analysis/acquisition concurrency with isolated synthetic journals/output/stage state. Never use real-port, interactive-bench or motion flags.
6. Update docs/examples/agent context around actual final behavior. Report each original M0–M6 criterion with test name/result, not just R-stage status. Keep software-tested, bench-acquisition-qualified, optical-control-qualified and quantitative-reference-qualified separate.

If dependencies/platforms or a timing capability prevent a required check, record the exact limit and command/result. Continue independent feasible work; do not replace missing evidence with a completion claim or stop at a new plan.

## 13. Bench-only backlog and next measurement decision

After software gates pass, a separately authorized short stationary gain 1 repeat capture is the first acquisition acceptance exercise: h8/h9 positive-response/health monitors (not electrical-coupling controls), h12 priority, signed h13–h16 diagnostics, actual settings/exposure/raw observations retained. This is a proposal, not an instruction to connect now.

A quick scan later answers a gross-health/repeatability question. Full height scans require a defined geometry/targeting question, stable tray/sample plane, matched references and separate motion authorization. A longer sweep cannot fix incorrect metadata, lost duty reservations or invalid uncertainty.

Still bench-only and owner-deferred: actual A0 operating-range evidence, fitted Rf/Cf and accepted current measurements, optical-block/sham/restoration controls, detector aim/aperture/depth/seating and stable sample plane, electrical pickup/grounding/supply investigation and emitter identity/spectrum where needed. H8/h9 work and h12–h14 previously responded; do not call InGaAs globally dead or recommend higher current as free SNR.

**No measured SNR improvement or recovered SWIR/1850 chemistry is justified by software alone.** H16 remains spectrally unassigned. Real primary1850 information needs suitable source/detector/path/reference calibration, not a renamed OPT101 feature.
