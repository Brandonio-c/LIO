# LIO V3 sensor suite: practical software upgrade plan

**Date:** 23 November 2026.  
**Evidence/code baseline:** `92bee4a2b3f702b3ba6c294e5ef4d9af716729e4`, verified as GitHub `main` when preparing this plan.  
**Status:** implementation specification, not an implementation or acceptance record.  
**Owner request:** implement all seven software priorities identified after the functionality/usability assessment. This publication changes documentation only.

Read the [functionality/usability report](research/LIO_V3_FUNCTIONALITY_USABILITY_REPORT_2026-11-23.md) and [coding-agent handoff](handoffs/2026-11-23_sensor_suite_practical_implementation.md). The [original upgrade plan](SENSOR_READINGS_UPGRADE_PLAN.md), especially original M0–M6 and section12, and the [caller remediation plan](SENSOR_READINGS_CALLER_REMEDIATION_PLAN.md) remain contracts. This plan supplies concrete remaining work; it does not redefine acceptance downward. Preserve D03=ownership, D04=OFF, and the previous CE/D/A regressions.

## 1. Result required

Deliver a reliable host workflow that can collect and assess realistic low-count readings, preserve their complete identities, expose effective acquisition settings, and carry supported inference through CLI, dashboard, reports and profiles. Implement **all S1–S7 below**, including A21/A22 and the connected statistics. Finishing only helper functions or dashboard controls is incomplete.

Software success is useful even while the physical rig remains unqualified. Maintain separate states for acquisition completion, numerical availability, statistical support, optical eligibility, physical calibration and evidence origin. A valid labelled fixture must exercise a useful numerical path; an unknown physical fact must still block dependent real-rig qualification. Neither hardcoded PASS nor permanent hardcoded UNRESOLVED is acceptable.

### What the evidence does and does not support

| Baseline observation | Consequence for implementation |
|---|---|
| Current OPT101 visible nets are often only23–167counts; H23 T05.5 judges none under its1000count prefilter | Assess low-count precision explicitly; do not lower optical/safety thresholds to manufacture PASS. |
| T08.2 stores large InGaAs net variation but its PASS can come from dark-mean checks alone | Report and judge net repeatability separately from dark stability. |
| P2 stationary h8 InGaAs `[28,28,28,29,30,28]`; h12 `[−11,−9,−17,0,−12,−3]` | Signed local technical repeatability is measurable. It does not establish optical transfer, independent sample repeatability or recovered SWIR. |
| Q23 COMPLETE/sealed, but all764rows have blank new identity fields | Fix the height producer, not only the common reader. |
| Two corrupted copied protocol end states were accepted and resealed | Validate semantic completeness before resume/promotion. Preserve legal crash recovery. |
| Browser protocol Resume uses the height endpoint; manual checkpoint UI is absent | Test actual browser actions through server, runner and persisted records. HTTP endpoint existence is insufficient. |
| Core mains acquisition uses `mains_periods`; UI samples edits `sweep_n` | A visible setting must alter the effective planned/applied setting, or be disabled with a reason. |
| Qualified products retain C=null; paired/shared/family helpers and A21/A22 are disconnected | Connect the production path without inventing controls, optical facts or predictive validation. |
| Final archived release run971passed/1failed/6skipped; this audit's focused run63passed | Preserve the unidentified intermittent HTTP failure as open until diagnosed. Counts from different scopes are not a release certificate. |

H23=`test_results/20261123-162705_host`; Q23=`20261123-173108_scan_quick`; P2=`20261123-180942_scan_protocol`. Full sources and numerical context are in the report. `170350_host/170352_scan_quick` is an invalid fix test, and simulator runs are not hardware evidence.

## 2. Scope and boundaries

This is **host-software implementation plus full offline verification**. The coding agent may edit source/tests/current documentation and use simulator, fake transport, copied archives and test-created local servers. Do not ask permission for routine authorized implementation or offline testing. Complete all independent software work even when bench validation is unavailable.

This request does not authorize real serial/Device connection, POWER WAKE, LEDs, motors, live-dashboard restart/takeover, firmware edits/flash, wiring/current/pot changes, fabricated or inferred physical operator confirmations, physical stage-state changes or hardware calibration. Historical session authorizations in older handoffs are not authorization for these operations under this handoff. Bench comparisons below are future proposals requiring owner authorization and actual prerequisite answers. Code publication follows the coding session's instruction; this documentation push alone is not future code-push permission.

Keep core gain1 and existing duty/travel/current limits. M7 remains deferred. Preserve the owner-acknowledged `cooperative_unproven` admission policy and expose its limits truthfully; do not invent a finite firmware-hang bound or a timing margin. A0/Rf/ammeter/optical/reference checks remain owner-deferred. Do not change physical stage marks, auto-home/rebase or interpret unequal recorded bottom distances as measured tilt.

Historical raw runs, cubes, streams, reports and `analysis.json` are immutable. Work on copies and put new source-bound derived products under an external `--derived-out`. Current documentation may be corrected, retaining historical conclusions as explicitly historical. Do not commit physical `test_results/stage_position.json`, ephemeral simulator runs or personal food-library data.

## 3. Integration approach and order

Reuse the existing architecture: `SuiteContext`/`Recorder`, typed `LIODevice` and ownership/duty gates, `ProtocolSpec` and acquisition runner, `ScanStore`/provenance/calibration, derived analysis, Scan/Profiles dashboard and existing profile tools. Do not create a second acquisition daemon, ledger, protocol parser or independent validity resolver.

Implement S1–S3 as the first working slice, then S4–S6 and finish S7. Integrity foundations may precede S1 where shared recording requires them. Add small maintained counterexamples before fixes, and test real consumers after each slice. Existing helper APIs may remain for compatibility, but cannot substitute for connected behavior.

| Package | Primary code to inspect/change | Delivered behavior |
|---|---|---|
| S1 repeatability | `suite/checks/t05_channels.py`, `t07_t08_timing_sweep.py`, suite recording/reporting, shared statistics | Truthful low-count precision and explicit missingness |
| S2 integrity | `scan/{store,provenance,calibration,acquisition,executor}.py`, `cli.py`, dashboard jobs | Complete new observations and safe semantic resume |
| S3 workflow | `dashboard/{server,session,protocol_job,scan_job}.py`, static Scan UI, CLI | Working fixed-position capture, prompts and resume |
| S4 acquisition comparison | `scan/{acquisition,targets}.py`, timing/ownership consumers, CLI/UI | Effective settings and finite, comparable pilot/confirmation experiments |
| S5 inference | `scan/analysis/{coupling,uncertainty}.py`, `derived.py`, reports/profiles | Correct connected contrasts/covariance/family inference |
| S6 profiles and A21/A22 | `scan/targets.py`, planner/executor; `food_profiles/{schema,features,runs,baselines,ablation,cli}.py` and UI | Shared frozen selection/fresh confirmation; compatible profiles and honest grouped evaluation |
| S7 release/status | suite/dashboard status, software identity, transport/ownership callers, test configuration, current docs | Trustworthy status, isolated tests and reproducible release evidence |

A new shared pure helper is appropriate only when these production consumers actually use it. Keep optional precision/profiles dependencies optional.

## 4. S1 — Measure repeatability at the instrument's actual signal levels

### Required behavior

1. Replace the first-reading/1000count gate that currently determines whether T05.5 collects any repeats. Freeze selected channels, settings, order, N and budgets before acquisition. Preserve safety/ADC availability checks, but do not globally suppress raw InGaAs diagnostics merely because physical qualification or a noise criterion fails.
2. Retain every planned attempt and returned dark/lit/signed-net observation, settings, identities, reported duration and explicit missing/dropout reason. Distinguish a missing record from a genuine zero or negative response. Interleave safely under the shared duty gate; additional repeats cannot create free exposure.
3. Report planned/observed N, signed mean, sample SD, standard error/interval where supported, drift/order information, intermittency/dropouts, saturation and assumptions. Integrated conversion counts or two detector rows are not independent repeat blocks.
4. Separate absolute repeat dispersion from signal/detection and from optical qualification. CV is unavailable when its denominator is weak, nonpositive or not meaningfully resolved; do not use absolute values or epsilon denominators to make it pass. A stable near-zero reading can have a stable dispersion without becoming an optical detection.
5. T08.2 must expose net repeatability for each selected detector/hole, not only averaged dark stability. MEAS and SWEEP have different acquisition profiles; keep their repeat summaries distinct and label cross-mode comparisons.
6. Preserve legacy recipes and historical verdicts. For new results, no evaluated precision channels means explicit SKIP/unavailable for precision, never a vacuous precision PASS. Use existing status conventions or a versioned extension; do not silently break report/twin consumers. Do not relax existing global FUNCTIONAL/WARN policy to hide changed subresults.

### Acceptance

- Actual T05.5 callers collect the frozen N for labelled stable20–200count fixtures; fixtures at zero/negative/unstable/missing/saturated states retain distinct outcomes and raw observations.
- A positive stable fixture produces a meaningful numerical precision result; an unstable fixture is detected; no-net-signal remains separate from precision stability. No preselection from a lucky first reading.
- T08.2 fixture with stable dark means and wildly variable nets cannot report overall net-repeatability PASS. Zero judged or missing required records cannot silently pass.
- New summaries survive save/reopen/report and dashboard display. Counts below1000are covered through the actual persisted path.
- Fake transport traces and clocks show bounded predeclared exposure/cooldowns. Plan previews include the additional cost and say when the requested repeat design cannot fit.

## 5. S2 — Complete identities, frozen facts and semantic resume

### Required behavior

All NEW height and stationary producers populate the shared identity fields. One physical MEAS has one reading/operation identity shared by its two detector rows. Preserve block, attempt, condition, setting, segment and position-instance identity. Retries use new attempt IDs; unknown height stays unknown, not zero. If existing block IDs cannot identify cross-condition or shared-control pairs, introduce a versioned experimental pairing/shared-control-group identity rather than guessing by sort order.

Freeze canonical configuration content, channel roles/wavelength/mux mapping, applied gain/rate/mains settings and detector order, requested settings, protocol/schedule, source/assembly/sample/reference identity and fact provenance. Include the exposure-bound label in every run type. Path+hash alone is not a self-contained snapshot. Preserve both measured and operator-declared/unknown/conflicting facts; an intended current is not measured current. Current YAML1MΩ conflicts with owner-reported fitted2MΩ, and B45mA conflicts with reported≈30mA. Represent that provenance honestly, without certifying A0 or rewriting old epochs.

Apply the quantity resolver to legacy report consumers too. Unverified A0/unknown required Rf block dependent physical-current and quantitative-optics labels, while raw counts, supported ADC arithmetic and independently valid OPT101 quantities remain usable. Historical reports remain unchanged; a new rendering may explain their assumptions or quarantine unsupported reuse.

Before resume, validate config/protocol/schedule/assembly compatibility, source/catalogue hashes, durable committed-record checkpoints, and any existing terminal seal. Validate ordered steps, exact expected detector-row multiplicity and complete identities/settings/conditions/blocks/pair membership. Missing or duplicate detector rows, swapped settings/conditions and inconsistent completed_step must refuse before Device construction or MEAS where detectable offline.

A legitimate RUNNING crash may have no terminal seal. Support this through validated crash-durable committed-step/checkpoint evidence and an explicit source-revision/recovery state; do not reject every legitimate resume or blindly seal an unverified prefix. Incomplete atomic readings/pairs are not complete independent blocks. Any supported bounded reacquisition preserves previous charges and records new attempts. Never overwrite an invalid existing seal to erase evidence of corruption.

Persist resume segments, a monotonic logical sequence and truthful absolute/relative time provenance; do not fabricate continuous timestamps across process restarts. Preserve append-only pause/abort/refusal/resume history instead of replacing it with an empty terminal list. Retain permanent costs and deadlines through downtime.

### Acceptance

- Actual height executor creates complete IDs/facts; both detector rows share a reading but do not inflate N. Full save/reopen/derived/profile paths retain them.
- Actual CLI and dashboard resume callers reject missing, duplicated, swapped or altered detector/condition/setting/identity rows, changed snapshot/schedule/NPZ and bad existing seal with no MEAS. Include both a partial prefix and the audit's all12steps-present, `completed_step=11`, INCOMPLETE end-state.
- A valid interrupted run resumes only the remaining frozen schedule, produces no duplicate completed reading and preserves budget/history. A legal unsealed crash case succeeds with explicit validated recovery evidence.
- Cumulative ordering/segments remain unambiguous when local `t_s` resets. Existing genuine P1/P2 archives remain inspectable and are not silently given invented facts.
- Snapshot deep-freeze, derived-output containment, run/product association and source-mutation checks still pass. Hash all relied-on historical bytes before/after saved analyse/audit/report/view tests.
- New legacy-height rendering cannot print physical leakage/current PASS from unverified A0 plus stale configRf; conditional diagnostic arithmetic is clearly named and excluded from calibrated reuse.

## 6. S3 — Finish the owner workflow for short stationary measurements

Provide a small Scan UI flow for sample ID, current-position policy, explicit holes/detectors, fixed production blocks, effective integration/settling and finite caps. Use the SAME versioned protocol validation as CLI and offline planning. Include an exploratory OPT101 preset for appropriate visible/NIR channels, a clearly diagnostic InGaAs preset, and an explicit proxy option; these are collection roles, not physical qualifications. Persist the actual protocol; no hidden ad-hoc acquisition path.

Fix saved protocol Resume to use its protocol endpoint/caller and height Resume to use its height caller. Recheck the additional CLI height-resume path: at this baseline its parser does not supply `sample` while the caller accesses `args.sample`. Preserve the saved sample identity on resume and reject incompatible overrides. Do not mask missing attributes by guessing experimental facts.

Ordinary suite, height and unblocked stationary runs use one truthful initial setup confirmation and no in-run popups. Intentional optical interventions and attended bench tests remain separate: render prompt text/occurrence identity, require a fresh strict Boolean answer for each occurrence, remain verified OFF/no-motion while waiting, and keep heartbeat/abort responsive. Start flags and old answers cannot answer later prompts. Resume needs current start authorization and fresh answers for any newly entered manual condition; previous answers stay history.

Separate ordinary-conversion N from mains frequency/periods. Display effective integration, requested/applied gain1 and detector order. Disable or explain controls that do not apply. Show consistent progress units, capture/analysis/qualification states, actual errors, and next safe actions. Analysis of saved data must not require or monopolize the hardware owner.

### Acceptance

- A real headless browser interaction through current DOM/server/session/runner creates a valid stationary fixed-N protocol, previews it, starts a simulator job, pauses at a safe boundary, aborts, resumes correctly and displays persisted values. A scripted HTTP driver alone is insufficient browser evidence.
- Correct browser protocol Resume no longer reaches `Session.scan_start`'s missing `plan`; real CLI height Resume no longer depends on absent parser attributes. Both valid and incompatible cases are tested.
- Two manual occurrences with the same text need two fresh answers. False/string`"false"`/integer1/stale/duplicate answers do not authorize collection. Missing answers remain OFF and abortable.
- Normal unblocked capture, suite and height examples complete after one start confirmation without synthetic operator facts or new routine popups.
- Switching periods2→8 changes the actual fake MEAS argument, plan cost and recorded setting2→8. An ordinary-N control cannot appear effective while ignored in mains mode.
- All plan/audit/report/saved-view paths construct zero Device/serial and call no WAKE/ARM; stationary traces contain no motion ARM/STEP/JOG/home/rebase. Unknown position remains unknown with a run-local position instance.

## 7. S4 — Compare effective acquisition settings and freeze production allocation

Expose a finite protocol-based comparison of predeclared settling/integration profiles using current typed MEAS. A pilot estimates variance of the declared target contrast and actual acquisition costs, records drift/order effects, and freezes a separate finite production design. Keep all pilot observations available but exclude them from independent confirmation.

Do not assume1/sqrt(N) improvement under drift/correlation or equate fast dark residuals with integrated net uncertainty. Compare candidate profiles/policies at the SAME declared total exposure and wall/cycle constraints, including conservative device bounds, detector sequencing, waits and minimum controls. An equal comparator based on the same number of slots is not equal-cost when costs differ. Handle infeasible minimum allocation explicitly. Distinguish response monitors h8/h9 from validated coupling controls.

Persist pilot source hashes, actual setting/detector/contrast-specific variance support, measured/predicted costs, weights, caps, allocation objective, feasible comparator, frozen schedule hash and stop reason. Unsupported variance/cost cannot silently become an exact1.0prior in a supposedly measured optimization; labelled priors or equal-fixed fallback require explicit reasons. No stop-when-positive, repeated optional peeking until a CI narrows, core PGA experiment or increased drive.

Condition order may be counterbalanced to examine drift. Do not describe a sequence of firmware dark-then-lit MEAS commands as hardware off–on–on–off telemetry. Timing-based regression requiring unknown ADC exposure windows stays unavailable. Existing whole-mains-period integration is not a new lock-in instrument.

### Acceptance

- Production fake-transport traces match the frozen settings/order/exposure, including resume. Changed UI values cause changed actual commands, not metadata-only changes.
- Unequal-cost fixtures prove both optimized and equal comparators obey identical caps; infeasible designs refuse before light; pilot/confirmation IDs and consumed sources are disjoint.
- Known drift/noise fixtures assess profile comparisons without false precision; allocation handles zero/negative/missing responses without divergent relative-error objectives.
- Offline recorded-stream hum diagnostics retain raw and fitted/residual layers separately. They do not relabel fitted residuals as measured optical improvement.
- A future owner-authorized real comparison can record precision versus time/exposure using fixed N. Until then, simulator gains are labelled synthetic and no measured SNR claim is made.

## 8. S5 — Connect controls, covariance and inference through production consumers

Wire actual persisted condition/block/pair identities into paired target/optical-block contrasts and applicable shared-control correction. Require load-preserving, compatible control evidence scoped to run, condition, settings, calibration and assembly. Bare hole numbers, red/broadband labels and h8/h9 response monitors do not validate controls. Unknown C remains null with a reason; raw signed drive contrasts remain available.

Carry control-estimator variance, target/control covariance and cross-channel shared-control covariance through the supported estimator, derived identity, report and profile consumers. Never silently zip arrays by sorting, truncate unmatched pairs or fill missing controls with zero. Signed negative, zero, missing, saturated and structurally ineligible remain distinct.

Freeze the detector×hole×contrast family, significance level, split and assumptions before confirmation. Apply the declared familywise method in production. Missing/failed targets remain in the declared family accounting; do not shrink the family after seeing results. Technical repeats, paired readings and two detectors do not create independent biological/preparation samples. Inadequate independent blocks, strong correlation/drift or unknown required covariance limit inference explicitly.

Expose effect/interval/N, assumptions, control scope/sensitivity, multiplicity method, unavailable reasons and evidence origin in CLI, qualified products, report, dashboard and applicable profile features. Maintain independent numerical/physical eligibility; a useful synthetic numerical result is not a rig calibration. Do not leave `qualified-v2` as an unconditional verdict stub, and do not turn software-valid arithmetic into physical optical PASS.

### Acceptance

- Actual CLI saved analyse→report→dashboard/profile path on labelled fixtures produces known signed estimates and matched covariance, not merely helper results. Example paired target `[10,12,14]` minus control `[1,2,3]` yields `[9,10,11]`, mean10 and variance of mean1/3, not independent-error5/3.
- Missing/duplicate pairs or incompatible control facts refuse dependent inference while preserving raw inspection. Pilot/scout contamination and detector double-counting are detected.
- Shared controls induce the expected nonzero cross-channel covariance; the frozen family is unchanged by missing/negative results.
- Run existing >=2000-family precision/false-positive simulations with predeclared tolerances AND an integrated saved-record regression. Archive seeds/versions/results; do not choose tolerance after seeing outcomes.
- Eligible positive labelled fixtures yield useful numbers; invalid/unsupported fixtures yield precise unavailable reasons. Without SciPy, raw capture/audit/basic summaries still work and unsupported interval-dependent decisions are unavailable, not approximated silently.
- Current P1/P2 data retain C=null and unresolved dependent optics; h16 remains outside primary-SWIR features. No historical requalification by software version alone.

## 9. S6 — Compatible profiles, shared selection and honest grouped validation

### References and food profiles

Use one compatibility/quantity resolver across run lookup, baseline/reference selection, features, report, batch CLI and UI. Bind source/calibration, physical assembly/sample plane/lid/mount/current epoch, applied acquisition and estimator/control/reference identity. Distinguish suite YAML baselines, empty-holder diagnostics and calibrated optical references. Unknown required facts prevent quantitative reuse but preserve labelled raw exploration. Do not apply today's source/Rf/geometry to an older run.

Support repeat-preparation/session/day metadata and explicit collection batches. A raw fingerprint batch is useful without pretending it is a calibrated spectrum. Keep missingness and common-feature support visible; do not compare different unmatched per-hole maxima as a spectrum or select a baseline because it makes the sample pass.

### A21: shared scout/selection/fresh confirmation

Connect ONE source-bound versioned selection object through planner, fine placement, runner, CLI, dashboard, report and relevant profile output. Freeze objective, eligible/excluded targets, weights, safe candidate grid, uncertainty/cost support, scout sources and selection ID. Exploratory OPT101 and primary-SWIR are different declared objectives. Flat, missing-target or physically unsupported objectives return explicit unresolved status, not a noisy-maximum fallback.

A shared selection must drive a genuinely NEW held-out confirmation protocol with new reading IDs and disjoint observations. Resume is continuation, not new confirmation. Changing confirmation cannot change the already frozen choice. Do not extend travel, auto-home/rebase or infer a measured sample gap from CAD. When motion evidence/prerequisites are unavailable, the complete software workflow must still work on synthetic data and refuse unsupported real motion truthfully.

### A22: explicit proxy opt-in and genuine group separation

Preserve h16 extraction but require explicit opt-in consistently through batch construction, CLI and UI. Keep the namespace `proxy_unassigned`; never primary1850, guaranteed optical blind or automatic coupling control. Default primary recipes exclude it.

Audit the existing grouped helper, not just its name. Its within-held-group pairwise-distance summaries are descriptive; they are not predictive held-out validation. Reuse the existing supported modelling/validation facilities where applicable: train all fitted transforms/feature selection on training groups, test on disjoint preparation/lot/day groups, compare full versus proxy-removed features on identical folds/support and report the actual estimand. Do not introduce a new classifier project just to create a positive result. If no applicable predictive method, labels or independent groups exist, return predictive value unavailable and retain an honestly named descriptive ablation.

### Acceptance

- Actual baseline→features→batch→CLI/UI rejects incompatible current/Rf/A0/geometry/reference/model facts per quantity, while independently valid OPT101 and raw diagnostics remain available. Unknown does not equal compatible.
- Adding an extreme blind/noise-only/h16 point cannot move a primary objective's choice; all selection consumers show the same ID/result. Fresh confirmation sources are disjoint; perturbing confirmation leaves the selection frozen.
- A positive actual-caller fixture with eligible scout evidence and a known unique safe interior optimum selects that height, then collects NEW fixed-N confirmation through typed fake/simulator acquisition. Assert actual new MEAS calls and disjoint observations/IDs, not newly minted IDs over copied scout values. Flat/missing/ineligible fixtures remain unresolved; an always-unresolved selector cannot pass.
- Actual batch/CLI/UI opt-in changes h16 inclusion and namespace. Default exclusion and mixed legacy/current behavior are covered; a checkbox alone cannot confer optical eligibility.
- Synthetic grouped fixtures prove group disjointness, training-only transforms and paired fold/support comparison. Missing labels/groups, insufficient independent-group/class support for the declared metric, or leakage are unavailable/fail with clear reasons; no random row split of technical repeats. A singleton held-out group may be valid for supported prediction with sufficient training support, while a within-group distance needs at least two observations; test the appropriate distinction.
- Descriptive distances are never called predictive accuracy or proof of proxy value. No claim about measured food discrimination follows from synthetic validation.

## 10. S7 — Honest operation, status and release evidence

### Owner-facing status and planning

Render separate capture completion, optical judgment, quantity eligibility and historical-versus-current analysis. Unjudged/SKIP is not positive evidence. A cumulative dashboard twin must identify each tile's run/config epoch so it does not look like one coherent passing scan. Correct current diagnostic wording: unequal distance-to-bottom marks is not measured physical tilt; h16 response does not identify a wrong LED; mains integration does not prove physical hum removal.

Split predicted acquisition, motion, known cooldown and unknown/manual time. Use a read-only view of current journal constraints for estimates without spending/reserving, invoking writable journal recovery, acquiring the hardware-owner lease or constructing Device in offline preview. An unreadable/missing journal means an unknown or conservative estimate, never fabricated empty credit. Runtime remains authoritative. Show queued/cooldown/refusal reason, countdown where supportable, next safe action and actual waits. Recheck wall/cycle bounds after every wait. Do not change conservative accounting/refunds to improve ETA.

Record startup loaded-build identity, source/dirty-content evidence, PID and start time. `Session.version` is a UI revision token, not software version. Reading current disk Git HEAD on every request does not identify already loaded code. Detect changed deployment files/new jobs appropriately and document a controlled disconnect/stop/restart/verify procedure; never restart the owner's running dashboard during offline tests.

Test a fake server started with buildA, then change its on-disk revision/files toB: status and any admitted fake job retain loaded-A identity and expose deployment changes, never advertise loadedB until a verified restart. A replacement server's failed bind must not mark a new build active.

Preserve the managed ownership lock before open/WAKE. Request supported platform-exclusive serial access where available and test admission/cleanup with fake platform transports. Document its actual semantics and unsupported cases; do not claim the LIO advisory lock excludes unrelated serial programs or that this closes the firmware-hang bound. No live competing-client test is authorized here.

### Test isolation and release gate

Route EVERY simulator/test stage path to temporary synthetic state. `LIO_STATE_ROOT` alone currently isolates the duty journal, not necessarily stage state. Add a guard against default physical stage-path writes, including from CLI/dashboard and exception cleanup. Unit/sim tests must neither alter nor restore the real file as a workaround. Hardware authorization paths and ordinary truthful tracking remain intact.

Investigate the unidentified intermittent golden HTTP numerical test with retained failing output, request/job states and deterministic synchronization. Do not call repeated passes a diagnosis, increase sleeps blindly, skip/xfail the contract or weaken its numerical assertions.

Run genuine clean-environment checks on the final candidate, not a mixture of SHAs. Preserve full outputs, exact versions/commands, failures and skips. Required scope:

```bash
# Repository root
ruff check .
ruff format --check .

# software/host, AFTER synthetic stage-path isolation/guards are in place
LIO_SOFTWARE_QA_OUT="$(mktemp -d)"
export LIO_STATE_ROOT="$LIO_SOFTWARE_QA_OUT/state"
export COVERAGE_FILE="$LIO_SOFTWARE_QA_OUT/.coverage"
python -m mypy
python -m pytest -m "unit or sim" --lio-sim \
  --results-dir="$LIO_SOFTWARE_QA_OUT/results" \
  --cov=lio --cov-report=term \
  --cov-report="xml:$LIO_SOFTWARE_QA_OUT/coverage.xml"
python -m coverage report \
  --include="*/lio/protocol.py,*/lio/analysis.py" --fail-under=90
```

Run maintained CE/D/caller/new regressions, real CLI/browser positive and refusal paths, and saved-record numerical truth. Test Python3.10/3.12 with genuine interpreter-compatible dependencies; precision tests must execute in an environment with SciPy. Separately test core/precision/profiles absent/present installs and an installed wheel/assets outside the checkout. Missing tools/platforms are explicit gaps, never PASS. Keep network/hardware transports guarded in tests; local HTTP reaches only newly created test servers.

Hash relied-on historical files before/after complete tests and saved audit/analyse/report/view, plus guard physical stage-state path against all writes. Keep new products external. Update README, TESTING, DIAGNOSTIC_SWEEP, relevant usage/help and `.agents/project-state.md` to the final supported behavior; preserve old findings with dates/epochs rather than advertising them as current facts.

## 11. Completion record and review gates

Deliver working code, tests and updated current documentation, plus one acceptance record containing:

1. Exact candidate/dirty-content identity, changed files and commands/versions with full results, including the intermittent test's diagnosis or remaining failure.
2. S1–S7 checklist tied to actual callers; A21/A22 closure evidence and ORIGINAL M0–M6 matrix. M7 remains deferred; physical M1 is not closed by host work.
3. Browser/CLI walkthrough evidence; effect of effective-setting changes; valid and adverse resume results; complete new-height identities/snapshots; no port I/O in offline paths.
4. Integrated numerical/control/covariance/family truth and grouped-validation results, with assumptions and synthetic/real origin separated.
5. Before/after historical hashes, test-stage isolation and external derived-output evidence.
6. Working documented command examples/presets and migration behavior for old unsealed/legacy data. Do not rewrite old artifacts or invent missing identities to make migration look complete.
7. Separate bench-only questions, prerequisites and proposed finite comparisons. Report owner-deferred checks as deferred; do not stall the software implementation for them.

Every completion claim requires evidence. Passing the inherited suite alone, changing documentation to say complete, adding unused helpers, rendering mock values, creating no-op controls or returning blanket unavailable results does not complete this plan. Actual real-rig SNR, SWIR recovery, calibration and1850nm chemistry remain unproved unless separately authorized measurements establish them.
