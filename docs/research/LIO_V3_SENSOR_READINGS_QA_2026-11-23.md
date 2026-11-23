# LIO V3 sensor-readings implementation QA

> Historical audit of code at 38eb8e6. Follow the [remediation plan](../SENSOR_READINGS_REMEDIATION_PLAN.md) and [coding-agent handoff](../handoffs/2026-11-23_sensor_readings_remediation.md) for current repair work. Publishing these documents does not implement the fixes. Scratch reproduction files mentioned below were audit artifacts; the coding agent must turn the described cases into maintained repository tests.

**Audit date:** 23 November 2026  
**Audited main:** [38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8][commit]  
**Decision:** **Do not accept M0–M6 as complete. Do not use a new quick or full scan to certify this upgrade yet.** Useful helpers exist, but acquisition safety, acquisition facts, quantitative eligibility and workflow integration fail the specified contracts. M7 is isolated from the core, but its completion claim also exceeds the implementation.

This is an independent read-only audit. No instrument was connected, no real LED or motor was operated, no firmware was flashed, no operator confirmation was invented for a physical experiment, and no product code or Git ref was changed.

## Evidence and verification scope

I read all six requested documents in full: the [upgrade plan][plan], [implementation handoff][handoff], [research assessment][assessment], [original research handoff][original], [test-results guide][results-readme] and [project state][state]. I inspected the requested modules, their callers, the Scan UI and the named tests.

Direct Git clone/pull was blocked by this environment with HTTP 403. I instead obtained a fresh GitHub snapshot pinned to the branch head through the connected GitHub reader. Main was checked again at the end and remained 38eb8e6. All 335 entries in the source/fixture verification manifests matched their Git blob hashes. This included every host source/test file and all 106 files from the three historical runs and six tray-v3 anchors. Historical files were analysed in place only through read-only paths; mutation probes used separate scratch copies.

Verification actually performed:

- Executed a guarded protocol-plan call: exit 0, zero Device/transport constructions.
- Recomputed real-cube counts, h16 trajectories, Nov19 h12 instability and candidate-coupling sensitivities.
- Ran qualified-v2 on all three exact historical runs into a separate derived root; all 107 files under the snapshot's test-results root retained their hashes.
- Executed and independently reran simulator/fake-device probes for exposure accounting, emergency OFF, protocol settings/caps, checkpoints, pause/heartbeat, allocation, resume, legacy output mutation, height-scan calibration and stream/seal identity.
- Executed scientific helper/consumer probes, including missing identity fields, incompatible baseline facts, range/Rf gating, mismatched controls and analysis-ID collisions.
- Checked optional-SciPy behavior both with SciPy present and by loading the actual module with SciPy unavailable. Raw estimates remain available and intervals report an explicit unavailable reason in the latter case.

**I did not rerun pytest, Ruff or mypy locally.** They were unavailable; dependency installation was blocked by PyPI HTTP 403. This is not a passing-suite claim. Independently, [GitHub CI for this exact commit][ci] failed Ruff and mypy on **both Python 3.10 and 3.12**. Its unit/simulator/fault-matrix and coverage steps were **skipped**, as was the formatting step after Ruff failed. Firmware compile jobs succeeded in CI; nothing was flashed during this audit. Installed-wheel and full extras-matrix qualification remain unverified here.

## A. M0–M7 acceptance matrix

“Fail” means the milestone's complete acceptance contract is unmet; it does not mean every helper is broken. Test links identify existing coverage inspected, not tests claimed to have passed locally.

| Milestone | Result | Passing pieces | Acceptance failures and evidence | Existing tests inspected |
|---|---|---|---|---|
| M0: provenance, units, compatibility | **FAIL** | String config-hash bug fixed; changed present cube hash rejected; new height snapshots/seals are written | Applied gain/mains can be misrecorded; A0/Rf gates disconnected; missing identity accepted; NPZ streams omitted from seal/identity; same ID can overwrite different products; legacy analysis mutates source | [test_provenance][t-prov], [runs reader][runs], [derived writer][derived], [height snapshot][height-start] |
| M1: ownership and durable exposure | **FAIL** | OS lock is acquired before serial open; typed over-budget requests and reservation-fsync errors have guards | Shell/CE bypass; SWEEP loses 15 reservations; stale journal overwrites history; cancellation suppresses OFF; no hard pulse/readback bound; real duty=False removes journal | [test_ownership][t-owner], [device][device], [journal][owner] |
| M2: roles and coupling | **FAIL** | H16 excluded from primary1850/default blind pool; absent C stays null in the new coupling helper | “Validated” controls still selected by expect and nominal range without evidence; h6/h7 called guaranteed blinds; covariance is a placeholder, not estimator/shared-channel covariance | [test_coupling][t-coupling], [role selection][roles], [coupling estimate][coupling] |
| M3: fixed-N inference | **FAIL** | Signed means and ordinary paired-t arithmetic; explicit missing-SciPy fallback; no stop-positive loop | Actual derived workflow pools heights/conditions/pilot rows as independent blocks; unequal controls silently truncated; no predeclared familywise qualification, block-ID deduplication or joint shared-control product | [test_uncertainty][t-uncertainty], [test_precision_extras][t-precision], [derived estimator][derived-est], [uncertainty][uncertainty] |
| M4: targeted protocols | **FAIL** | Genuine offline preview; gain 1 protocol-request guard; finite schedule; explicit allow-light check | Mains not applied; runtime total/cycle caps absent; checkpoints don't enforce safe states; resume accepts changed facts and partial blocks; pilot never informs production; hardware CLI unconditionally refuses | [test_acquisition][t-acq], [test_scan_protocol_cli][t-cli], [execution][acq-run], [real CLI branch][cli-run] |
| M5: shared scout/confirm objective | **FAIL** | Detached helper excludes h16 and represents unresolved/flat cases | Real fine placement still uses old all-channel peak; report uses a different objective; no integrated held-out scout/confirm acquisition/persistence | [test_targets][t-targets], [actual fine objective][fine], [actual report objective][optimum] |
| M6: complete usable workflow/release | **FAIL** | Protocol preview and derived-summary browser exist; proxy namespace is safe; incomplete baseline rejection exists | Pause/heartbeat ignored; per-condition confirmation absent; progress terminal-only; detailed numerical UI absent; baseline/feature eligibility fail open; “held-out ablation” is a distance comparison; CI red | [protocol job][job], [Scan UI][ui], [baseline selector][baselines], [test_baselines_ablation][t-baselines], [CI][ci] |
| M7: optional extension | **PASS isolation; INCOMPLETE extension** | No production core caller imports the module; nondefault gain planning requires opt-in; GLS stub never qualifies | No integrated qualified gain workflow; missing readback accepted; execution does not set/check requested gain; sample timestamp span is not a conservative pulse bound | [M7 module][m7], [test_m7_gain][t-m7] |

## B. Ranked concrete findings

### 1. Blocking: managed light paths and emergency OFF are not reliably gated

These reproductions used SimTransport and temporary synthetic duty journals:

- A shell-equivalent command, CH 1 ON 1500, emitted in the simulator against a 1000 ms rail-A budget and left durable history empty. SR selection followed by CE also left history empty. Arbitrary [command/send_raw][raw-command] bypasses the typed guard, and the CLI shell reaches that path.
- SWEEP returned 16 readings, but durable history contained only one 24 ms entry, attributed to h16. Each pre-reservation overwrites the same pending slot; the first completion commits the final reservation.
- Two journal objects loaded before ownership can spend sequentially from stale memory. After the first commits 900 ms, the second reports zero wait for another 900 ms and overwrites disk history with an empty history. Real journal construction happens before acquiring the serial-owner lock.
- With a pending cancellation, safe_off sent MOTOR STOP but skipped OFF. Subsequent simulator status still had channel1/CE1 enabled. The cancellation check consumes the OFF command.
- A nominal 24.625 ms MEAS reservation accepted a returned 2001 ms duration under a 1000 ms budget, committed it and left uncertain=false. No firmware pulse-cap reduction/readback or validated OFF gate bounds the possible duration before sending.
- Constructing a real SerialTransport-backed device with duty=False, without opening it, yields neither journal nor in-memory duty tracker.

See [device construction][device-ctor], [safe_off][safe-off], [MEAS/SWEEP][meas-sweep], [reservation/commit][owner-reserve]. Additional inspection gaps include unverified owner generations, mutable pending reservations, incomplete alias/serial-exclusive handling and unreliable macOS boot identity.

**Repair priority:** one transport-adjacent gate for every emitting command; nonoptional real-HW accounting; journal loading/reserving under the current owner transaction; whole-operation SWEEP reservations; validated conservative duration bounds; cancellation-independent same-owner emergency OFF. Add crash/alias/stale-ack/cancel tests at the real caller boundary. These fixes require software work, not the bench.

### 2. Blocking: acquisition can record settings it never applied, and UI controls can be ineffective

The [targeted runner][acq-run] calls MEAS with n=mains_periods but never configures/validates mains rejection. A fresh device boots with mains off. A fake trace completed MEAS(12,8,2) at mains_hz=0 while the snapshot recorded effective_mode=mains, mains_hz=60.

For new height scans, a simulator at applied gain 2 and a 50 Hz plan completed 142 rows, while its [snapshot helper][snapshot-helper] recorded gain 1/60 Hz. The core height path did not reject the unexpected gain. The row conversion uses current config calibration: a synthetic 1864-count row was saved as 233 mV instead of the applied-gain 2 116.5 mV. This is a core acquisition/provenance failure, not a recommendation to experiment with gain.

Protocol-wide checks also fail:

| Probe | Observed result |
|---|---|
| Two readings report 150 ms each under a 200 ms total cap | COMPLETE at 300 ms; actual returned exposure not accumulated |
| max_cycle_s=0.001 | Ignored |
| Checkpoint status says all_off=false and no_motion=false | Event records both false, then MEAS runs and completes |
| ProtocolJob pause=true and expired heartbeat | Both readings execute; COMPLETE, paused=false |
| Interrupt after “unblocked”, change config hash, resume | Starts at “blocked” inside the partial condition block and completes |

The [dashboard job][job] only polls abort_reason. Its confirmation callback returns the original start checkbox for every future occurrence. That cannot stand in for fresh manual blocking/unblocking. Progress is only populated after acquisition returns. [Resume][resume] does not compare frozen facts or require a complete-block boundary and restarts timing budgets.

The [hardware CLI branch][cli-run] is unconditionally disabled with an implementation-session authorization error. This prevents a real CLI run today, but does not protect dashboard/other device callers or satisfy the usable CLI contract. Correct software authorization gates must be implemented and tested offline; this audit does not authorize exercising them on hardware.

### 3. High: quantity eligibility and provenance are not enforced by consumers

The [quantity_eligibility helper][eligibility] correctly blocks unverified InGaAs current in its unit example, but has **no production caller**. The [derived workflow][derived-est] hardcodes gain 1 and current-config Rf. [Profile ratios][features] use available C/finite denominators without the range/geometry/calibration compatibility gate.

On a labelled synthetic metadata copy of the real cube, recording gain 2, unknown Rf and observed-outside-range A0:

- Qualified-v2 still stamped gain 1, 0.125 mV/count and declared 1 MΩ from today's config.
- A persisted scratch analysis accepted by the actual profile reader allowed an InGaAs h12 reference ratio of 1.0 with reason=ok and no warnings.
- A matching cube hash alone could produce VERIFIED even when required scan/calibration/estimator fields were missing.
- A quantitative baseline candidate with required geometry/model/reference all missing was accepted. [Baseline matching][baseline-match] only rejects these when the candidate field is truthy.

Preserve counts and labelled ADC-referred observations. Apply quantity-specific physical validity to current/optics/reference consumers, while keeping independently valid OPT101 quantities available. Unknown required compatibility facts must refuse quantitative reuse.

### 4. High: historical/derived immutability is violated by new commands

Git comparison from 138a963 to 38eb8e6 shows **no committed test_results changes**. That passing historical-repository fact must be distinguished from these runtime failures:

- [analyse_model legacy][legacy-write] calls the old analyser, which writes source-run analysis.json even when the new command specifies --derived-out. On a scratch copy, source analysis SHA changed from 484d802a… to 385e2ef8…. The original fixture stayed untouched.
- Changing analysis config from the 800 nm to a labelled synthetic 600 nm lower boundary changed C_A from 5 to 2, yet produced the same analysis ID and path, overwriting different bytes. Identity stamps recorded acquisition config while computation uses supplied current config.
- Changing an NPZ raw-stream sample changed the legacy analysis, yet kept the same analysis ID/path. Both [terminal sealing][seal] and derived identity omit raw stream files. A new height run's seal also stayed identical after a raw-stream sample changed.

The [derived writer][derived-write] unconditionally replaces existing content. Hash all inputs actually consumed, frozen calibration/map/model/settings/reference identities and terminal revision; detect existing-content conflicts; isolate legacy calculation from source writes.

### 5. High: “qualified” inference does not implement the prescribed estimand

The [derived estimator][derived-est] pools all selected rows per hole, discards height/direction/condition/phase grouping and treats them as independent fixed-position blocks. Nov23 h16 becomes n=17, mean282.824, CI254.110–311.537, using nine down/eight up visits at different heights. Protocol data can similarly mix pilot/production and blocked/unblocked rows. No integrated paired optical contrast is calculated.

A direct [shared-control helper][uncertainty] probe with signal=[10,11,100], control=[0,1] silently drops 100 and returns value10, SE0, interval[10,10]. Duplicated observations cannot be identified as repeated block IDs. Per-channel signal/control covariance is not the cross-channel covariance induced by a common control. Familywise qualification and Monte Carlo coverage/FWER tests are absent.

**Important limit:** qualified-v2 currently hardcodes UNRESOLVED. These probes demonstrate invalid estimands/interval interpretation and missing acceptance behavior; they do not establish a current false FUNCTIONAL verdict.

### 6. High: roles, targeting and pilot allocation remain disconnected or overstated

[“Validated” coupling][roles] still comes from diagnostic expect and nominal detector ranges without compatible load-preserving control evidence. Current InGaAs guaranteed-blind candidates include h6/h7 at 605/630 nm despite the explicitly recorded manufacturer-range uncertainty. Removing all controls correctly yields null, but remaining unvalidated candidates do not become validated merely because they have readings.

The [actual fine objective][fine] remains the old normalized all-channel maximum. A clean h12 two-height example selected −100; adding an h16 OPT101 residual changed it to −200. The new targets helper is not called by the actual planner/fine/report/UI. The helper test cannot establish integrated held-out confirmation.

Pilot-frozen production is scheduled from prior variances before collecting the pilot; measured pilot values never update it. The allocator also ignores diminishing marginal gain: equal costs/weights/variances with six production readings gives5,1, objective1.4472, while equal3,3 gives1.1547 at identical cost. The current [allocation test][t-acq-allocation] uses a cap large enough to saturate channel maxima and does not establish useful adaptive improvement.

## Contract checklist

| User contract | Verdict |
|---|---|
| M0–M6 complete; core gain 1; no core PGA experiments | **Fail completeness and gain enforcement.** Default is 1 and no M7 auto-experiment is wired in, but height acquisition accepts/mislabels gain 2. |
| Unknown C never zero in qualified paths | **Pass in the new coupling/optical-amplitude helpers.** Missing rails remain null; control validity/integration still fail. |
| H16 never primary1850 chemistry | **Pass namespace/default-primary exclusion.** Actual proxy extraction/value assessment is incomplete. |
| Unknown A0/Rf blocks InGaAs physical/quantitative reuse, preserves raw/OPT | **Fail end to end.** Primitive range gate exists but consumers bypass it. |
| No stop-positive/noise-max qualification | Fixed schedule has **no stop-positive**. Actual fine peak selection/scout-confirm contract **fails**; qualified product stays unresolved. |
| Protocol plan genuinely offline | **Pass**, source and executed guarded call; existing guard test present. |
| Ownership/duty gates all light; no real bypass | **Fail**, reproduced. |
| Historical bytes untouched, derived separate | Git history and qualified-v2 probe **pass**; new legacy command and immutable derived products **fail**. |
| New height snapshot/seal, old optional | Presence/old-readability **pass**; applied facts and complete sealing **fail**. |
| Plan §12 assertions/tests | Numerical anchors largely hold; coverage and acceptance behaviors incomplete, detailed below. |

## Plan §12 numerical/regression check

| Required case | Audit result | Current test evidence / gap |
|---|---|---|
| Three cubes764; P2/P3lit544;17/detector/hole | Recomputed, all hold | [test_provenance][t-prov] asserts764;544/17 absent |
| Nov23 h16 vector and paired differences | Exact vector and [2,0,1,1,−1,0,−3,−5] hold; medianabs1,max5 | [h16 test][t-h16] present |
| InGaAs B candidate C sensitivity | Nov19 7→4.5; Nov20 11→5.5; Nov23 16→10; removeall→null | [coupling tests][t-coupling] present |
| OPT101 B sensitivity | Recomputed15→15,13→12,2→1.5 | [coupling tests][t-coupling] present |
| Current h12 legacy sensitivity | Saved12.3333→18.3333 for C16→10; h13/h14 stay negative | [h12 sensitivity test][t-h12] present; does not establish optical recovery |
| Nov19 h12 instability | Exact P2 vector and max181 hold | No corresponding numerical assertion found |
| Nov19 analysis/report disagreement | FUNCTIONAL versus NOT FUNCTIONAL persists; Nov20/23 agree | New derived summary returns historical verdict null; no disagreement regression |
| Integration artifact |78→640ms, multiple settings changed, no individual repeat variance | No numerical/interpretive regression found |
| Gain1 dark/Rf arithmetic |−329.875counts=−41.234375mV; conditional1MΩ41.234375nA or2MΩ20.6171875nA |1MΩ helper test present;2MΩ assertion absent; physical eligibility integration fails |
| Synthetic gains | Synthetic100counts→12.5mV(g1) or6.25mV(g2); same-voltage helper supported | Present in provenance tests; not evidence of historical gain experiments |
| Censored SNR | Saved22.4dB evaluates only h8/h9 | No numerical scope regression; generic explanatory UI note only |
| Shared-control covariance/duplicate N | No joint product/block-ID enforcement; unequal controls give bogus exact interval | Existing test checks Cov(S,C); its duplicate-row comment never duplicates rows |
| Nulls/peak bias/coverage/FWER | Required integrated qualification tests absent | Five simple uncertainty tests are not Monte Carlo coverage/FWER acceptance |
| Optional stopping | Finite fixed schedules; no positive-response stopping found | Broader incomplete-stop/resume semantics fail |
| Device fault matrix | Multiple concrete guard failures reproduced | Five ownership tests do not cover requested lifecycle/alias/crash/cancel matrix |

## Documentation/UI overclaims

- [Project state lines8–11][state-claims] says M0–M6 done, M7 code-complete and remaining work bench-only. The software failures above contradict all three completion statements.
- [Host README][host-readme] advertises pause/heartbeat, usable protocol workflow, immutable derived output and unexpected-gain rejection. The actual paths do not consistently implement these claims.
- The Scan UI has preview and a summary browser; it lacks the promised signed block/condition inspection, paired contrasts, intervals, drift and usable per-occurrence operator workflow.
- [Ablation][ablation] has no held-out grouping/split; it compares full-batch pairwise distances with/without proxy columns. Dropping dimensions mechanically changes Euclidean distance; that is not held-out incremental predictive value. Actual extraction still masks current h16 as expect=none, so the manual namespace test does not prove the proxy is collected.
- Historical [optics wording][old-optics] still attributes h16 silicon response to a wrong LED. That causal conclusion remains unsupported.
- [test_results/README][results-readme] preserves useful anchors but still calls Nov19 simply FUNCTIONAL and labels the integration artifact without the report disagreement/variance caveat. The research assessment is more accurate about those limits.
- The plan/handoff remain specifications, not release evidence. Original M7 deferral versus current “complete” claims should be reconciled explicitly.

## C. Should the owner rerun quick or full now?

**Neither as qualification of this software upgrade.** A longer acquisition cannot repair missed OFF, lost duty reservations, false integration metadata or invalid block/eligibility semantics.

After software blockers and offline integration/fault tests are fixed, the first separately authorized bench collection should be a short bounded stationary gain 1 repeat protocol at the existing safe position, retaining h8/h9 controls, prioritizing h12 and preserving signed h13–h16 diagnostics. Verify actual integration/readback, exposure and persisted facts before expanding collection.

A **quick** scan can then answer a specific gross-health/repeatability question. A **full** scan is justified when optical-path/holder/sample-plane state is stable and a geometry/height-profile question warrants the extra motion/time, with separate motion authorization. A changed tray/holder needs an appropriately matched baseline; old geometry does not become compatible by software relabelling.

Owner-deferred A0/Rf/ammeter checks remain deferred. After software repair, their absence need not block raw-count/labelled ADC-referred diagnostics or independently valid OPT101 work. It must continue to block unqualified InGaAs physical-current/quantitative optics/reference claims. No confirmation or physical measurement has been inferred here.

## D. Ranked remaining work

| Priority | Software work possible offline | Required acceptance evidence |
|---|---|---|
| 1 | Fix global light gate, real accounting bypass, emergency OFF, durable owner/journal lifecycle and hard pulse bounds | Fake exact transport traces, multiprocess/alias/crash/clock/overrun/partial/cancel tests |
| 2 | Apply/read back actual gain/mains/settings; enforce safe checkpoints, pause/heartbeat and runtime caps; implement completed-block resume | End-to-end CLI/dashboard tests, failure injection, persisted raw exposure/timing and changed-facts rejection |
| 3 | Wire calibration/range/compatibility gates into derived/profile/reference/baseline consumers; repair identities/seals/legacy isolation | Valid-input and unverified/outside/unknown paths; every consumed input mutation changes ID; source bytes invariant |
| 4 | Integrate fixed-position block/condition/phase identity, paired contrasts and shared-control covariance | Duplicate/missing/correlated/null/mixed-sign tests; predeclared coverage/FWER; no peak/self-confirmation |
| 5 | Integrate one target objective across actual planner/fine/report/UI; learn pilot variance then freeze production | Same-objective golden workflow, h16/noise noninterference, independent confirmation, equal-budget allocator benchmarks |
| 6 | Complete numerical UI, truthful release docs, profile proxy extraction/held-out ablation and packaging | Real UI smoke/control tests, core/extras/installed-wheel matrix, green Ruff/mypy/tests/coverage on3.10/3.12 |
| 7 | Keep M7 deferred/incomplete until core accepted; qualify gain/readback/headroom/inputrange and timestamp accounting if prioritized | Explicit opt-in, both-detector prerequisites, missing/partial-window failures; no GLS qualification from a stub |

**Bench-only, still pending:** actual A0 voltage/input-range evidence; fitted Rf/Cf and measured current provenance; unchanged-load optical-block/sham/restoration controls; detector aim/aperture/depth/seating and matched sample plane; safe grounding/supply/pickup diagnosis; emitter identity/condition/spectrum if required. H8/h9 response and past h12–h14 activity argue against calling InGaAs globally dead. Software cannot correct a blocked/misaligned optical path or create missing photons. Do not raise current as a free SNR remedy.

True primary1850 work additionally needs an established source spectrum, a detector/analog chain with calibrated1850 sensitivity and qualified sample-path/reference geometry. Existing OPT101 h16 remains spectrally unassigned.

## E. Scientific conclusion

**No measured SNR improvement, recovered weak-SWIR chemistry, or recovered1850 chemistry is justified by this software alone.** Offline arithmetic and simulator tests can validate software behavior. They do not establish optical causation, wavelength, input linearity, quantitative reflectance or predictive food information.

The defensible release description at this commit is: **partial implementation with useful offline helpers and confirmed software blockers; no bench/optical/reference qualification.**

[commit]: https://github.com/Brandonio-c/LIO/commit/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8
[ci]: https://github.com/Brandonio-c/LIO/actions/runs/45131415874

[plan]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/docs/SENSOR_READINGS_UPGRADE_PLAN.md#L1
[handoff]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/docs/handoffs/2026-11-23_sensor_readings_implementation.md#L1
[assessment]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/docs/research/LIO_V3_SENSOR_INFORMATION_ASSESSMENT_2026-11-23.md#L1
[original]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/docs/handoffs/2026-11-23_research_handoff_sensor_information_extraction.md#L1
[results-readme]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/test_results/README.md#L1
[state]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/.agents/project-state.md#L1
[state-claims]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/.agents/project-state.md#L8
[t-prov]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_provenance.py#L43
[t-owner]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_ownership.py#L59
[t-coupling]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_coupling.py#L33
[t-uncertainty]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_uncertainty.py#L20
[t-precision]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_precision_extras.py#L15
[t-acq]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_acquisition.py#L42
[t-cli]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_scan_protocol_cli.py#L29
[t-targets]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_targets.py#L18
[t-baselines]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_baselines_ablation.py#L47
[t-m7]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_m7_gain.py#L24
[t-acq-allocation]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_acquisition.py#L103
[t-h16]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_provenance.py#L173
[t-h12]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/tests/unit/test_coupling.py#L96
[runs]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/food_profiles/runs.py#L163
[derived]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/derived.py#L101
[height-start]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/__init__.py#L131
[device]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/device.py#L279
[owner]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/ownership.py#L226
[roles]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/analysis/coupling.py#L71
[coupling]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/analysis/coupling.py#L201
[derived-est]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/derived.py#L121
[uncertainty]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/analysis/uncertainty.py#L246
[acq-run]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/acquisition.py#L713
[cli-run]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/cli.py#L760
[fine]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/executor.py#L46
[optimum]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/analysis/optics.py#L305
[job]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/dashboard/protocol_job.py#L79
[ui]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/dashboard/static/index.html#L1214
[baselines]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/food_profiles/baselines.py#L129
[m7]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/m7_gain.py#L234
[raw-command]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/device.py#L518
[device-ctor]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/device.py#L270
[safe-off]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/device.py#L379
[meas-sweep]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/device.py#L719
[owner-reserve]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/ownership.py#L342
[snapshot-helper]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/provenance.py#L208
[resume]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/acquisition.py#L880
[eligibility]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/provenance.py#L443
[features]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/food_profiles/features.py#L296
[baseline-match]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/food_profiles/baselines.py#L169
[legacy-write]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/derived.py#L123
[seal]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/provenance.py#L264
[derived-write]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/derived.py#L101
[host-readme]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/README.md#L80
[ablation]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/food_profiles/ablation.py#L94
[old-optics]: https://github.com/Brandonio-c/LIO/blob/38eb8e6240dbbbde9f562c8b4b94ccba564ad8d8/software/host/src/lio/scan/analysis/optics.py#L171
