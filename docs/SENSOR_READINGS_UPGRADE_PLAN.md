# LIO V3 sensor-readings software upgrade

**Status:** implementation specification; no feature or bench qualification is implied by this document.  
**Date:** 23 November 2026.  
**Evidence/source snapshot:** `main` at `138a9635df7538748b5dda1fddee88db5067b8fb`. Reconcile subsequent changes before implementation.  
**Scope:** host software using existing OPT101, MTPD1346D-100/TL072, ADS1115 and current firmware primitives. No new detector, firmware flash, increased drive, relaxed travel limit or new chemistry claim.

Read the [research assessment](research/LIO_V3_SENSOR_INFORMATION_ASSESSMENT_2026-11-23.md), [original research handoff](handoffs/2026-11-23_research_handoff_sensor_information_extraction.md), [test-results guide](../test_results/README.md) and [implementation handoff](handoffs/2026-11-23_sensor_readings_implementation.md).

## 1. Required outcome and implementation order

Deliver a usable workflow that collects bounded, repeated measurements from explicitly selected holes at a fixed position, preserves the actual acquisition facts, and distinguishes:

1. Raw signed detector readings.
2. Drive-synchronous response, `tau = E(lit - dark)`.
3. Optical-block contrast, `Delta_opt = tau_unblocked - tau_blocked`, conditional on adequate load-preserving controls.
4. Matched target/reference contrast, conditional on compatible geometry and calibration.
5. Calibrated reflectance/absorbance, available only when its extra physical/reference requirements are satisfied.

These are different estimands. A larger number, lower residual, changed warning or positive fit is not automatically more optical information. Better readings means demonstrably better precision or reproducibility at a stated exposure/time cost, with bias, missingness and provenance visible.

Implement **M0–M6 in order**, as usable vertical slices. Complete all feasible offline and simulator paths; do not leave them as stubs because the bench is unavailable. M7 is a deliberately deferred extension requiring a separate priority/qualification decision. Do not delay the core workflow for a new general workflow engine, auto-ranging, periodic lock-in or new machine-learning methods.

| Milestone | Deliverable | Dependency |
| --- | --- | --- |
| M0 | Reproducible audit, immutable provenance, calibrated units and compatibility gates | None |
| M1 | One device owner and crash-durable, strictly bounded exposure accounting | M0 acquisition identity |
| M2 | Independent channel roles and explicit coupling-model uncertainty | M0 |
| M3 | Signed fixed-N block estimates and honest uncertainty | M0, M2 |
| M4 | Targeted stationary protocol execution and pilot-frozen allocation | M1–M3 |
| M5 | Shared target-specific scout/confirm height selection | M3–M4 |
| M6 | Complete CLI/dashboard/report/profile integration, packaging and release checks | M0–M5 |
| M7 | Optional gain profiles and timestamped off–on–off experiments | Separately authorized extension after core qualification |

## 2. Evidence that controls this design

All three tracked historical cubes contain 764 rows. Audit their JSONs, cubes and reports without changing them:

- `test_results/20261123-003133_scan_quick/`: current h8/h9 InGaAs responses survive; h12 is weak; h13/h14 have little resolved return. H16 OPT101 is reproducible and height-associated.
- `test_results/20261120-012619_scan_quick/`: useful historical empty reference, with different electronics/geometry provenance. All three scans recorded ADS1115 gain 1; Rf and physical state may differ. It is not automatically a compatible quantitative reference.
- `test_results/20261119-152512_scan_quick/`: black cup; `analysis.json` says FUNCTIONAL while `report.md` says NOT FUNCTIONAL. Raw h12 is intermittent. Preserve this disagreement rather than selecting whichever artifact looks healthier.
- `test_results/tray_v3/INGAAS_REMOUNT_DEPTH_CHECK.json`: handheld/mounted differences indicate a path/load/measurement-state issue; they are not calibrated collection efficiencies.
- `INGAAS_BOOST_INTEGRATION_CHECK.json`: short/long settings changed settling, ordinary averaging and mains rejection together; no individual repeat variances are saved. It cannot establish an SNR gain or no-gain.
- `LED_CONFIRM_SWEEP.json`, `LED_REPLACE_SWEEP.json`, `DRIVE_TUNE_A.json`, `DRIVE_TUNE_B.json`: useful state history. Empty meter-reading lists and null accepted currents do not prove final current.

The exact diode's current manufacturer specification is 600–1750 nm, versus the repository's 800–1750 model. Treat this as a model/provenance discrepancy, not permission to claim strong new red sensitivity. H6/h7, broadband h10/h11 and h16 are not guaranteed optical-blind controls. OPT101 cannot supply a calibrated 1850 nm primary channel; h15/h16 InGaAs may include shorter-wave emission tails. Do not change the simulator response curve or primary eligibility merely to remove findings.

### Known implementation defects to repair

- `food_profiles/runs.py::_resolve_channel_map` treats `cfg.sha256` as callable, although `HwConfig.sha256` is a string. Test actual hash mismatch; do not allow it to mark a historical map verified.
- Saved analysis is currently accepted by run/sample identity without matching source, calibration, reference and estimator identity.
- `scan/store.py::MV_PER_COUNT` and related paths assume 0.125 mV/count. Rf/current/geometry may be unknown or inconsistent with today's YAML.
- `electrical.blind_holes/coupling` uses nominal wavelength and diagnostic expectation to infer optical blindness, pools rail medians, and sometimes scales by nominal current ratio. `CE_ONLY` is not a normal LED-loaded control.
- `optics.channel_stats` selects a maximum smoothed response; current SNR is not the uncertainty of the integrated estimator. Negative/unresolved estimates must survive.
- `executor.overall_optimum` includes normalized noisy/blind curves and differs from the report objective.
- `DutyTracker` permits a single request larger than its rolling budget. Fresh processes forget history; raw shell and `budget=False` are bypasses.
- Firmware mains integration uses `mains_periods` and internally samples at 860 SPS. `sweep_n` and configured rate do not control that path as users might assume. MEAS samples the two detectors sequentially and returns rounded means, not simultaneous fractional measurements.

## 3. Architectural boundaries

Extend `lio.scan`, `lio.device`, configuration and the existing dashboard job/control infrastructure. Reuse `lio.food_profiles` readers, schema, metadata and feature masks. Do not create a second spectral-analysis framework or a second dashboard service.

Suggested small additions, **not existing APIs**:

- `scan/provenance.py`: frozen facts, final source seal, quantity-specific eligibility, analysis/reference compatibility.
- `scan/analysis/coupling.py`: legacy, validated-control and unidentified coupling results.
- `scan/analysis/uncertainty.py`: fixed-block estimates, paired contrasts, covariance and intervals.
- `scan/acquisition.py`: bounded stationary protocol planning/execution through typed device operations.
- `scan/targets.py`: shared scout/confirm objective and eligibility policy.
- A small device-ownership/duty-journal module alongside `device.py`, used by every real light-capable entry point.

Names can change with a documented reason. Required behavior and dependency order cannot silently change. Prefer extending existing data adapters over restructuring the entire package.

## 4. M0 — Evidence, provenance and units

### Acquisition and derived-product identity

Keep `scan.json` for mutable progress/events and preserve existing raw-format readability. Introduce an immutable initial acquisition snapshot after preflight and before the first reading. It records:

- Schema, protocol/plan hash, acquisition/processing versions, real/simulated identity and physical rig identity.
- Frozen configuration and channel-map snapshots with source/version evidence.
- Requested and applied ADC gain, FSR, LSB, mux/reference mapping, configured rate versus effective integration mode/rate, mains frequency/periods, settling and detector order.
- Rf/Cf and rail currents with distinct measured, operator-declared, inferred, conflicting or unknown provenance. An intended pot target is not a measurement.
- Assembly/support/sample-plane, tray-lid state, detector mounting, target/reference and calibration-epoch identity. Unknown stays unknown.
- Planned reading/block/condition identities, budgets and inference split.
- Input-range evidence with states such as unverified, verified-in-range or observed-outside-range. A negative ADC code alone is not a voltmeter measurement of A0; metadata defaults cannot certify the pin's physical operating range.

An initial manifest cannot include final data hashes. Write a terminal source seal after acquisition ends, hashing the frozen manifest and actual raw/terminal metadata bytes. Keep it separate to avoid self-referential hashing. Partial/restarted data get explicit source revisions; incomplete data can be inspected but cannot silently become a qualified complete run. Define canonical serialization, finite-number validation and append/checkpoint recovery.

Add optional raw columns/sidecar links through the shared reader: reading ID, block ID, condition ID, setting ID, sequence, detector, actual returned dark/lit/net values, command start/end, reported on-time and timing quality. Preserve the existing cube schema's meaning. Both detector rows from one MEAS share a reading identity and are not two independent blocks.

Current firmware does not expose exact per-detector conversion/exposure windows. Store truthful command bounds, returned durations and known ordering; do not invent precise ADC timestamps from host command times. Timing-dependent advanced models remain unavailable where their inputs cannot be identified.

### Legacy and derived outputs

Historical raw data and `analysis.json`/reports remain untouched. An explicit `legacy` recipe reproduces old behavior using the appropriate frozen source facts, with unknown facts labelled. New analyses are versioned/content-addressed products under a dedicated derived root, using the existing profile-artifact conventions where practical.

An analysis identity includes source content/file hashes, terminal status/revision, calibration and channel-map identity, protocol/selection masks, model and estimator versions, numerical settings and exact reference/control sources. Identical run/sample names are insufficient. Report and profile readers share one validity resolver with reasons such as verified, legacy-unverified, source-changed, calibration-incompatible and unreadable. Rejected derived products remain inspectable; quarantine means exclusion from quantitative reuse, not moving/deleting files.

Eligibility is per quantity: counts do not require Rf; volts require supported LSB; equivalent current requires supported Rf; matched ratios require compatible geometry/acquisition/control evidence; primary chemistry requires appropriate spectral/optical calibration. Do not globally reject raw exploration because a higher-level quantity is unavailable. Do not silently import today's calibration into yesterday's run.

Physical transfer validity is also a detector-specific qualification prerequisite. Unknown or out-of-operating-range A0 permits raw counts and clearly labelled ADC-referred arithmetic/diagnostics, but cannot qualify InGaAs optical amplitude, equivalent physical current or quantitative reference ratios. Narrow intervals do not establish transfer linearity. Independently valid OPT101 quantities remain available. Invalidate physical range evidence after relevant analog, mux/reference, gain or wiring changes; never let one stale verification Boolean certify a new state.

Replace global count-to-mV assumptions in acquisition, analysis, reports and relevant profile recipes with one calibration resolver. Thresholds must carry units and intended acquisition profile. Preserve an explicit gain-1 legacy conversion where historically justified; unknown LSB disables physical units rather than assuming 0.125. Do not retrospectively change physical Rf to 2 MΩ for all historical records.

### Acceptance

- Current config hash mismatch is detected even though `sha256` is a string.
- Changing one raw value, a control/reference source, gain/Rf evidence or estimator version invalidates prior derived identity.
- Opening any saved-data view does not run analysis, write data or open USB.
- Same voltage represented at two known gains gives the same volts; all real historical fixtures remain identified as gain 1. Different-gain ground truth fixtures are labelled synthetic.
- Resume rejects changed frozen facts; a partial analysis never masquerades as final.
- Historical report/analysis disagreement is surfaced; neither file is rewritten or silently chosen by verdict.

## 5. M1 — One owner and strict durable exposure accounting

Do this before exposing longer targeted collection. No acquisition daemon is needed.

1. Acquire an OS-backed ownership lock **before serial open/POWER WAKE**; retain it through final safe OFF and close. Normalize physical-device aliases, including macOS tty/cu aliases. Use OS exclusive serial access where supported. Do not authorize another owner from an expired TTL or a PID check alone.
2. Use one crash-durable duty journal per physical rig, independent of results directory, selected protocol, config hash and CLI/dashboard process. A small atomic file plus file/directory fsync is adequate; a transactional SQLite store is an alternative, not a second required store. Device identity must not be spoofable accidentally by choosing another port spelling. If unique identity is unavailable, use a conservative shared rig lock/recovery policy rather than granting aliases fresh budgets.
3. Atomically persist a reservation before any light-capable command. Bind it to connection/owner generations. Never clamp a requested cost down to the budget to make it fit.
4. Bound actual pulse duration, not only its prediction. The default rail-A watchdog exceeds the per-hole rolling budget. Reject an operation whose conservative bound cannot fit, or use existing firmware commands to lower/read back its pulse cap to fit the reservation. Never exceed owner-approved existing limits; any scoped restoration must also remain within those limits and cannot enable a later unreserved pulse.
5. Reconcile validated reported on-time only after verified OFF. If true edge times are absent, keep a conservative charge through acknowledged completion plus the duty window. Do not fabricate exact SWEEP timelines by stacking on-times from host t0.
6. Crashes/timeouts/partial SWEEPs/stale acknowledgements retain worst-case charges. On uncertain recovery, establish all-off and require a full conservative cooldown before relighting. Never auto-resume an emitting protocol after reconnect.
7. Use monotonic time and boot identity. Wall-clock jumps, reboots or an unreadable/unwritable/corrupt journal cannot create budget credit. Unknown state means no light until safe recovery, not empty history.
8. All emitting paths share the gate: MEAS/SWEEP, scheduled streams, CH/CE, debug wrong-rail tests, dashboard flashes/hold/ring, food acquisition and selftests. Route supported raw-shell operations through it or reject light-capable bypasses. Remove unrestricted real-hardware `budget=False`. Simulation-only faults must not provide a hardware escape.
9. OFF/STOP/RELEASE remain available when accounting fails, through the current serial owner/control path. They bypass the ledger requirement, **not** exclusive ownership by opening a competing serial client.

Existing firmware remains unchanged. Software accounting protects managed LIO clients; it cannot certify exposure after an uncontrolled external serial program has operated the rig. Such uncertainty invokes recovery. Motion and light permissions remain separate. Static acquisition never arms motion; preserve all existing stage checks, aborts and heartbeat behavior.

### Acceptance

- A/h9 single-pulse budget plus 1 ms is rejected before transport transmission.
- Competing processes/aliases cannot both open, wake, reserve or spend the same budget; reservations are atomic.
- Journal write/replace/fsync/parse failure cannot send a light command; emergency safe-stop remains possible.
- Crash at every reserve/transmit/response/commit boundary leaves conservative persistent cost. Reconnect, new output folder and config changes do not reset it.
- Clock movement and boot discontinuities cannot grant credits.
- Missing/malformed timing, duration overrun, watchdog event, partial ring or stale-owner acknowledgement aborts and retains charges.
- A lower watchdog cap must be acknowledged/read back before the operation; failure sends no light. Check timer granularity and service latency margins.
- All simulator tests use a separate synthetic journal and fake transport. Offline commands must assert that real serial open, POWER WAKE and MOTOR ARM are never called.

## 6. M2 — Roles and coupling with explicit non-identifiability

Preserve `expect` for backward-compatible diagnostic policy, but stop using it as the sole physical/control contract. Add independent fields for nominal source band/kind, primary detector eligibility, electrical-control eligibility and diagnostic/profile-feature role. Track evidence source and calibration epoch. H16 starts unassigned; h15 is cutoff-sensitive; broadband channels remain broadband. A new manufacturer range or a user checkbox is not automatic primary/control qualification.

Keep h16 assertions separate: drive-synchronous observed; optical component supported; h16 path supported; target modulation supported; spectral kernel characterized; held-out predictive value supported. Each assertion links actual evidence, method, scope and limitations. None makes OPT101 an 1850 nm detector.

Implement explicit coupling models:

- `legacy_blind_median`: exactly the frozen legacy method for reproduction, including clearly labelled inferred current scaling.
- `validated_control`: supported load-preserving controls with estimate, units, covariance/uncertainty, support and compatibility evidence. Pool across holes/heights only under a stated tested model.
- `unidentified`: insufficient evidence. Return null plus a reason; never substitute C=0.

Keep candidate-control sensitivity separate from the validated estimate. Expose leave-one-control-out, per-height/direction and alternative-membership effects. Unknown actual rail current prevents unqualified 45/30 scaling. CE-only/select-only/wrong-rail remain useful distinct observations; they are not automatically normal LED-load controls.

Relative height contrasts can be computed under an explicit constant-C assumption without pretending to identify absolute optical amplitude. New models must not be selected because they improve the verdict. Preserve primary, proxy and unresolved masks in all derived outputs.

### Acceptance

- Removing every eligible control gives unidentified coupling and unavailable dependent optical quantities, while raw nets remain available.
- A synthetic control contaminated with optical return produces model/sensitivity warnings; no automatic healthy verdict follows its removal.
- Real-record sensitivity reproduces the table in section 12 without calling the alternative C calibrated.
- H16 is excluded from default primary-1850 chemistry and from guaranteed-blind control sets. A proxy assertion does not automatically authorize spectral features or coupling reuse.
- Static runs do not invent height modulation. Current `weak` behavior is not used as a hidden shortcut around response/plausibility analysis.

## 7. M3 — Fixed-N block estimators and uncertainty

Start with a simple, reviewable estimator, not high-dimensional GLS.

- Freeze conditions/settings, target channels, height and number/order of production blocks before acquisition.
- Preserve each integrated dark/lit reading and its technical-repeat/session grouping. A firmware mean containing N conversions or mains periods does not supply N independent observations. P1/P4 from one electrical run are linked observations.
- Estimate signed drive response and paired blocked/unblocked contrasts across suitable independent blocks. Propagate control variance and shared-control covariance into corrected quantities and comparisons.
- Report planned/observed blocks, within/between-block variability, drift, assumptions, effect estimate, interval and unresolved/missingness reason. Do not derive repeat noise from neighboring heights or substitute the fast hum residual for the integrated estimator's standard error.
- Use a predeclared detector×hole×contrast testing family for qualification. A fixed-N t/paired-t method with stated independent-normal-block assumptions and conservative familywise adjustment is an appropriate first implementation. Small-N results are provisional. Correlation/instability or inadequate blocks must limit inference; a bootstrap from a handful of blocks is not an automatic remedy.
- Use NumPy plus established statistical routines. Reuse the project's optional SciPy dependency through a documented `precision` extra if needed. Do not hand-build an unvalidated statistics package. Without that extra, raw capture/audit/basic summaries remain usable and unavailable interval-dependent decisions have an explicit reason. Test both dependency configurations.
- Keep raw, despiked, smoothed and modelled layers distinct. Never clamp signed estimates to zero, use absolute values to manufacture a signal or epsilon-fix a weak denominator. Qualification uses independent confirmation, not the scout's selected maximum.

Dark-bracketed/timestamped regression is a later method within the same versioned interface. It must validate actual exposure/conversion windows, mux order, design rank, residual degrees of freedom, conditioning and covariance assumptions. Missing exact ADC-window telemetry disables methods requiring it. Whole-period integrated mains bases can be degenerate. Rank deficiency returns not-identifiable; regularization cannot manufacture optical qualification.

Ordinary repeatedly inspected intervals are not anytime-valid. **No production stop-when-positive or stop-when-ordinary-CI-is-narrow rule in the core release.** Safety stops always apply and preserve incomplete/unresolved status.

### Acceptance

- Labelled synthetic mixtures recover known signed drive and optical-block contrasts with predeclared Monte Carlo bias/coverage tolerances; test nulls, contamination, correlated drift and missing control conditions.
- Shared controls create nonzero cross-channel uncertainty; they are not counted independently for each channel.
- Noise-only height curves do not qualify through maximizing over more heights.
- Negative, exact zero, structural blind, missing, saturated and unresolved values remain distinguishable.
- Unknown covariance/insufficient blocks cannot produce a narrow qualified interval; static data cannot produce a fake height fit.

## 8. M4 — Targeted stationary acquisition

Implement a bounded protocol using existing typed MEAS primitives: explicit holes, both sequential detector reads, the existing owner-approved fixed acquisition gain, mains periods/settling per condition, condition order, fixed block count, total exposure and wall-time/cycle limits. Core M4 does not introduce PGA changes: use gain 1 at this source snapshot, or the separately established approved rig profile if the owner later changes it. Reject a protocol request or device readback that differs from that approved fixed setting, with a precise reason. Other-gain offline unit tests do not authorize an experiment. Opt-in gain changes belong to M7 with its qualification prerequisites.

Keep h8/h9 controls, prioritize h12 and retain h13–h16 as explicitly qualified/unresolved investigation channels. Standard MEAS shares integration and gain across the two detectors; do not promise independent per-detector settings.

Support two core allocation policies:

1. Equal/fixed predeclared allocation.
2. A separate pilot followed by **frozen production allocation**, using pilot variance, declared target weights and measured acquisition costs under the same hard budgets. Pilot observations do not also count as independent confirmation. Optimize absolute uncertainty, not relative error that diverges near zero. Preserve minimum controls and finite caps.

Record every allocation/stop reason and the planned/actual settings and exposure. A bounded unresolved result is valid; do not integrate indefinitely until a weak channel passes. Compare allocation policies at the same total exposure and wall-time constraints in synthetic benchmarks. Do not claim measured LIO gain from those simulations.

Condition-order ABBA (for example 2/8/8/2 periods) is supported by repeated existing measurements. It is not a claim that firmware MEAS implements optical off–on–on–off: it implements dark then lit. Manual blocked/target conditions need truthful checkpoints with all light off and no motion. A software condition label is not an operator confirmation. Do not implement hardware-dependent automatic interventions.

### Proposed protocol/API contract — not available in current CLI

Extend existing `scan` commands, rather than adding a parallel acquisition application:

```text
lio scan audit RUN --model legacy|qualified-v2 --derived-out DIR
lio scan plan --protocol protocol.json --json plan.json
lio scan run --protocol protocol.json --allow-light --out RESULTS_ROOT
lio scan analyse RUN --model qualified-v2 --derived-out DERIVED_ROOT
lio scan report RUN --analysis ANALYSIS_ID --derived-out DERIVED_ROOT
```

`scan plan --protocol` must be fully offline: no device construction, serial, POWER WAKE or light. It shows assumptions, unknown physical checks, settings, order, exposure bounds, cooldowns, predicted duration and statistical budget; runtime preflight revalidates against the actual device. Motion protocols additionally require explicit `--allow-motion` and trusted limits. A current-position stationary protocol makes no translation; an unknown coordinate is recorded and limits quantitative geometry compatibility.

`--protocol` is mutually exclusive with legacy `--mode` and ambiguous ad-hoc overrides. Apply legacy parser behavior when no protocol is supplied. Existing `--out` meaning is not silently changed; `--derived-out` is a distinct new output location. Resume only compatible immutable protocols, from a safe completed block after fresh physical authorization; interrupted conditions are not silently reclassified as complete.

A protocol schema must include a stable ID/version, kind, declared sample/assembly identity, selected holes, detector mapping, current-position or verified-position policy, fixed gain, explicit conditions, fixed block design, maximum wall/cycle/total-on budgets, inference split, estimator/model choices and operator-checkpoint requirements. Reject unknown keys, NaN, invalid holes, missing bounds and unsupported firmware capabilities. Create and validate a documented example file during implementation; no untested sample protocol is labelled executable today.

### Acceptance

- Exact fake-transport traces show only intended holes/settings/order; stationary paths never arm or move motors.
- Targeted blocks persist complete raw observations and all exposure charges through cancel/failure/resume.
- Every protocol is finite. Safety/communications/operator stops cannot promote partial data to a healthy baseline.
- Pilot-frozen allocation improves its declared variance/cost objective on controlled synthetic problems under identical caps; it does not simply collect more exposure than the comparator.
- The new plan path and every audit/analysis path are provably offline. Real operation requires explicit light permission, actual preflight and current single-owner state.

## 9. M5 — One scout/confirm height objective

Use a shared, versioned target-selection function from the planner, fine-point placement, report and dashboard. Targets must be physically/semantically eligible for the declared objective. Exclude structural blinds and h16 primary-1850 claims; h16 proxy scouting can be a separate explicit diagnostic objective.

Start with one common verified operating height. The objective should describe useful target-channel precision/coverage per acquisition cost, with pilot optical evidence and uncertainty—not claim chemical Fisher information without a chemical forward model. Persist weights, eligibility/exclusions, scout source hashes, safe candidate grid, predicted precision and coverage. If the objective is flat, unresolved or lacks its required targets, report that result; do not silently choose the largest noisy response or switch to all channels.

Freeze selected heights, then collect held-out confirmation blocks through M4. Do not reuse the scout maximum as its own unbiased confirmation. Keep actual stage coordinates and, only when known, physical sample gaps. Do not extend limits, auto-home, rebase the current position or infer a ruler measurement from CAD. Per-hole heights remain optional and require same-height references and explicit feature identities; unmatched maxima are not a spectrum.

### Acceptance

- Adding an extreme blind/noise-only/h16 residual cannot change a primary-SWIR target optimum.
- Scout and confirmation sets are disjoint and identifiable in persisted outputs; perturbing confirmation values cannot change the frozen selected height.
- Endpoint and unresolved examples preserve safe bounds and return explicit limits.
- Planner, report and dashboard reproduce the same named objective and selection for identical inputs. Legacy historical objectives remain reproducible only as labelled legacy results.

## 10. M6 — Complete the usable workflow and qualification

Finish the new CLI commands and integrate the existing Scan/Profiles UI. Each earlier milestone should already expose its useful vertical slice. Provide:

- Protocol preview with duration/exposure bounds, physical prerequisites and unresolved calibration.
- Targeted-run progress, operator checkpoints, pause/abort, heartbeat and existing safe recovery.
- Raw signed curves/readings, condition/setting/block selection, paired contrasts, intervals, drift, coupling sensitivity and physical/semantic qualification states.
- Explicit separation of historical recorded verdict, current model output, evaluated-hole list and quantitative eligibility. An SNR PASS for h8/h9 cannot certify h12–h15.
- Shared profile masks/compatibility for primary, cutoff, proxy, missing and unresolved quantities. H16 proxy features use an unassigned proxy namespace, never a primary-1850 feature ID. Offer held-out ablation through existing profile tools rather than adding a new classifier project.
- Baseline selection that rejects incompatible geometry/calibration/model/reference or incomplete runs for quantitative reuse, while preserving raw comparison. Suite YAML, scan baseline, empty-holder response and calibrated white reference remain distinct.
- Nonblocking saved-data analysis that does not hold the device lock or starve the acquisition heartbeat. Long computation belongs in existing worker/job facilities. Preserve `--no-food-library` operation and optional profile dependencies.

Build numerical and persistence tests, migration/readme examples and simulator demonstrations. Update relevant agent state and usage documentation around the implemented final behavior. Do not advertise unimplemented flags or imply scientific qualification from software completion.

**Release states are separate:** code-complete/offline-tested; bench-acquisition-qualified; optical-control-qualified; quantitative-reference-qualified. Bench tests cannot be completed by the coding agent without authorization. Implement and test the valid-input qualification paths using labelled fixtures; keep real evidence gates unresolved until actual measurements exist. An unavailable bench is not a reason to leave safe planning, parsing, estimation or UI behavior unimplemented.

## 11. M7 — Explicitly deferred extension

After the core workflow is useful and priority is confirmed:

- Opt-in shared PGA profiles with supported readback, per-block calibration, both-detector headroom and actual A0 input-range qualification. No automatic per-detector auto-ranging with the present dual MEAS primitive.
- Repeated buffered off–on–off single-detector streams, real timestamps and strict exposure accounting, with a simple paired-estimator comparison. Serial-limited long streams are not uniform 860 SPS data.
- More elaborate GLS or genuine sequential inference only with validated data/assumptions and separate review. Ordinary CIs cannot become anytime-valid by renaming them adaptive.

Current firmware cannot provide simultaneous detector sampling, arbitrary deterministic periodic LED waveforms or fractional MEAS telemetry. Those are outside this host-only implementation. Do not flash or expand firmware as a shortcut.

## 12. Concrete regression and correctness tests

Use tiny immutable excerpts plus source hashes where appropriate, and full tracked runs for offline integration. Never edit historical acquisitions, store the physical `stage_position.json` or tune thresholds to make current data pass.

| Case | Required assertion |
| --- | --- |
| Three real cubes | 764 rows each; P2/P3 lit selection has 544 rows, 17 per detector/hole. Selection excludes controls and P1/P4. |
| Nov 23 h16 OPT101 | P2 nets `[391,360,329,301,280,258,238,228,217]`; eight exact-height up-minus-down values `[2,0,1,1,-1,0,-3,-5]`, median absolute 1, maximum 5. This is repeatability evidence, not a wavelength/control certificate. |
| InGaAs rail-B candidate sensitivity | Current 16→10 excluding h16; Nov 20 11→5.5; Nov 19 7→4.5. Removing h10/h11/h16 gives unidentified C, never zero. |
| OPT101 rail-B sensitivity | Current 2→1.5 excluding h16; Nov 20 13→12; Nov 19 unchanged 15. A robust median must not be called numerically ruined merely because a candidate is conceptually unsuitable. |
| Current h12 sensitivity | Legacy O 12.3333→18.3333 for C 16→10, without requiring a PASS or claiming a calibrated correction; h13/h14 remain negative in that sensitivity case. |
| Nov 19 h12 | Raw P2 `[-49,15,134,-88,90,62,52,45,40]`; maximum matched up/down difference 181. Preserve unstable points and flag instability. |
| Derived disagreement | Nov 19 report NOT FUNCTIONAL versus analysis FUNCTIONAL is surfaced; Nov 20/23 matching controls remain correctly identified. No source rewrite. |
| Integration artifact | 78→640 ms on-time, changed settling/n/mains and absent repeat variance. Never fabricate measured SNR benefit or no-benefit. |
| Calibration provenance | Declared gain-1 current dark -329.875 counts = -41.234375 mV ADC-referred arithmetic. With supported 1 MΩ, conditional equivalent magnitude 41.234375 nA; with supported 2 MΩ, 20.6171875 nA. Unverified physical input range keeps physical-current qualification unavailable. Do not infer physical Rf from counts or assign the companion bench value automatically. |
| Synthetic gain cases | 100 counts at known gain 1 = 12.5 mV, at gain 2 = 6.25 mV; same-voltage pairs agree. These are synthetic, not historical different-gain measurements. |
| Censored SNR | Current saved InGaAs SNR PASS 22.4 dB evaluates only h8/h9. Show that scope; do not qualify failed SWIR. |
| Shared-control covariance | Known synthetic covariance appears in contrasts/aggregate uncertainty; duplicated rows do not increase independent N. |
| False detections and peak selection | Fixed-seed Monte Carlo null/mixed-sign fixtures meet predeclared coverage/FWER and bias tolerances with Monte Carlo uncertainty accounted for; no thresholds fitted to make real fixtures pass. |
| Optional stopping | Core fixed-N production does not lengthen or stop because a response becomes positive or an ordinary interval happens to exclude zero. |
| Device safety | Property/fault tests cover atomic reservations, over-budget rejection, competing aliases/processes, every crash boundary, clock jumps, malformed timing, partial sweeps and cancellation. No real transport is opened. |

Keep legacy-golden tests and new-estimator truth tests separate. New science is not required to reproduce questionable old maxima/verdicts. Synthetic h16 mechanisms test behavior under hypotheses and never establish the real mechanism.

## 13. Verification, delivery and boundaries

Run existing repository checks appropriate to each slice: Ruff check/format, strict mypy, unit/simulator tests and fault matrix. Current CI uses Python 3.10 and 3.12; maintain both. Exercise minimal installs, precision extras, profile extras, installed-wheel/offline operation, dashboard smoke flows, pause/abort and acquisition-versus-analysis concurrency. Include the existing protocol/analysis coverage gate. Use the repository's simulator invocation and isolated output/state roots; tests may not discover or connect a real serial device automatically.

Verify user-visible workflows and numerical outputs, not just return types, dictionary keys or buttons. Avoid unrelated refactors, redundant test reruns after unchanged passing code and large dependency additions. Update docs to the final implemented syntax. Record deviations from this plan with reasons and consequences rather than silently changing the estimand or safety contract.

Implementation authorization is **offline host implementation and testing**. It does not authorize bench work, firmware flashing, wiring/current changes, motion, LED exposure, auto-confirmations, live-dashboard restarts or modification of physical travel state. Even INFO/plan connections may energize coils in the current software, so keep offline paths genuinely offline. Future physical protocols require explicit owner authorization and truthful preflight.

Work on `main`, preserve owner changes and never force-push or change Git configuration. The present request authorizes pushing these documentation files. Implementation commits/pushes follow the owner's instructions in the implementation session; do not infer an unrestricted future push authorization from the documentation publication. Report completed milestones, actual checks, usable commands, changed files/commits, limitations and the separate pending bench qualification.
