# LIO V3 residual remediation: independent QA at a0935fb

**Date:** 23 November 2026  
**Audited main:** [a0935fb322e9a42459f577417b0167cfec830bfe](https://github.com/Brandonio-c/LIO/commit/a0935fb322e9a42459f577417b0167cfec830bfe)  
**Comparator:** 944a820d2287b6677a0d0fde017b40bbbaff87f6  
**Publication note:** archived independent audit, not an implementation or a new live run. See the current plan/handoff for subsequently authorized coding and hardware tests.

**Decision:** **Do not accept original M0–M6 as complete.** The maintained Python 3.12 suite is green, several residual repairs are real, and the archived live run is NOT FUNCTIONAL. Independent caller-level failures still refute full software acceptance.

This is an audit, not another implementation plan. No physical device was connected, no new INFO/POWER WAKE/light/motion was requested, and no firmware/wiring/current, physical stage state, product implementation or Git ref was changed. Serial exercises used explicit simulators or an owned pseudo-terminal bridge only. Mutations used scratch copies. D03=ownership and D04=OFF throughout; milestone definitions are the originals.

## 1. Scope, source identity and method

A fresh GitHub snapshot was pinned to a0935fb. All **542 materialized Git blobs** matched their hashes before and after the audit: host source/tests, requested docs, three historical scans,104 composition resources and all nine live-archive files. One previously unavailable1.26MB composition JPEG was not substituted; it did not cause the reported test failures or skips. This is not a claim that a Git clone/pull succeeded.

The new acceptance/research handoffs, project state, test-results guide and complete547-line live report were read; unchanged original plans, historical QA and prior fullpass/D01–D20 handoffs were checked against the previously read identical Git blobs. New acceptance tables were treated as hypotheses.

The commit changes **five production host modules**: device.py, ownership.py, dashboard/twin.py and suite checks T01/T02/T10. Acquisition, scientific estimators, derived/provenance reuse, target and profile consumers remain byte-identical to944a820. Their prior failures were nonetheless rerun through actual imported current-snapshot callers, not inferred from file equality.

## 2. Actual verification results

| Check | Independent result |
|---|---|
| Maintained CE/D/residual+related tests | **120 passed in25.82 s** |
| Complete unit/simulator+coverage invocation | **918 passed,0 failed,12 skipped,31 deselected in484.14 s** |
| Existing protocol/analysis≥90% coverage gate | **98%, exit0**;321 statements,8 missed |
| Overall lio line coverage | **79%** |
| Three new audit-only safety acceptance tests | **3 failed in0.25 s** |
| Three audit-only actual saved-data tests | **3 failed in1.50 s** |
| Six audit-only provenance acceptance tests | **6 failed in1.52 s** |
| Actual offline protocol plan | Exit0; zero guarded Device/serial/open/port-selection/WAKE calls |
| Running dashboard HTTP | Real start/pending/answer/numerical routes tested with simulator; string-Boolean bug reproduced |
| Rendered browser | Unverified: Chromium launch fails socket()/Operation not permitted |
| External-derived historical campaign |18 actual CLI audit/analyse/report calls plus saved readers;100 files including72 NPZ unchanged |
| Live-archive inspection |9 files unchanged;99 CSV measurements; report/results status counts agree |
| Exact-candidate CI | Ruff/format and complete Python 3.12 job **pass**; Python 3.10 mypy **fails**, tests/coverage skipped |
| Local whole-host strict mypy |5 diagnostics/5 files/125 files checked under mypy 1.15; version-sensitive |

**The twelve audit-only failures are separate from the maintained suite totals.** No failed assertions were hidden or replaced in obtaining the green maintained run.

Runtime: Python **3.12.14**, NumPy **2.3.5**, SciPy **1.17.0**, scikit-learn **1.8.0**, Matplotlib **3.10.8**, PyYAML **6.0.3**, pyserial **3.5**, Jinja2 **3.1.6**. Genuine verified-source pytest 8.4.2, Hypothesis 6.125.3, coverage 7.6.12 and pytest-cov 6.0.0 were used. Actual pyserial/Jinja distributions were installed before testing; the previous audit's metadata confounders did not recur.

Coverage used genuine **SysMonitor** on Python 3.12, smoke-tested against known executed lines before the complete invocation. The98% gate is now from **full unit/simulator coverage**, not the preceding audit's unit-only run.

The implementer reports Python 3.12.11/SciPy 1.18.1 and912/0/6. The live archive separately records NumPy 2.5.4. Different platform/dependency/optional-test environments can change counts;918/0/12 is not itself evidence their912/0/6 was false.

### Commands actually executed

Working directory: /workspace/scratch/98bb007a88b1.

```bash
python3 residual_audit_a0935fb_20261123/checks/run_pytest.py \
  tests/unit/test_fullpass_counterexamples.py \
  tests/unit/test_remediation_d01_d20.py \
  tests/unit/test_ownership.py tests/unit/test_provenance.py \
  tests/unit/test_coupling.py tests/unit/test_uncertainty.py \
  tests/unit/test_acquisition.py tests/unit/test_targets.py \
  tests/unit/test_scan_protocol_cli.py tests/unit/test_baselines_ablation.py \
  tests/unit/test_m7_gain.py tests/unit/test_precision_extras.py -q --tb=short

python3 residual_audit_a0935fb_20261123/checks/run_full_coverage.py
python3 residual_audit_a0935fb_20261123/root_http_cli_probe.py
```

The full launcher executes unchanged genuine pytest with:

```text
-m "unit or sim" --lio-sim
--results-dir=/workspace/scratch/98bb007a88b1/residual_audit_a0935fb_20261123/checks/full_sim_output
--cov=lio --cov-report=term
--cov-report=xml:/workspace/scratch/98bb007a88b1/residual_audit_a0935fb_20261123/checks/coverage.xml
```

Plugin autoload is disabled; genuine pytest-timeout, Hypothesis and pytest-cov plugins are explicitly loaded. State/cache/results are isolated. A transport guard rejects physical serial destinations and allows the software simulator's owned PTY/loopback.

The existing coverage report include is */lio/protocol.py,*/lio/analysis.py with fail-under90. It reports analysis96%, protocol100%, combined98%. High line coverage does not establish the missing behavioral contracts below.

## 3. Repairs genuinely verified

| Claimed repair | Actual caller evidence | Scope |
|---|---|---|
| Incomplete/cross-call fragments refuse | b'C' followed by b'H 1 ON 1500\n' is blocked before write | Correct literal fix; new sequence-tab bypass remains |
| Deferred journal constructor | Second actual managed serial-path fake device does not read/rewrite the live pending journal | Correct constructor fix; failed-open cleanup/aliases/generations remain |
| T10.2 no private CH bypass | Actual t10_2 with working syntheticB13 produces two admitted CH writes, pending5000 then300 | Correct former bypass repair; later OFF failure is misclassified SKIP |
| wait_needed_many | Actual SWEEP waits60 s in the tested history scenario, then returns16 records without wait=0/reserve failure | Correct liveness fix; not conservative accounting proof |
| Known wrong-rail CE refusal | Definite refusal leaves CE low, no pending/uncertainty and following MEAS works | Correct known-case cleanup; not safe for contradictory/unknown evidence |
| TEN triage | Correct configuration/duration/domain/policy expectations, independently rerun | Mostly legitimate test-contract corrections, detailed below |
| h16 opt-in extraction | Actual API still returns proxy_unassigned feature,280 counts | Preserved earlier fix; batch/CLI/grouped workflow incomplete |

## 4. New or expanded software failures

### A. Blocking: a TAB sequence prefix bypasses the newly relaxed raw gate

Actual managed fake-serial caller:

```python
dev.send_raw(b'@123\tCH 1 ON 1500\n', .1)
```

returns:

```text
@123 OK CH ch=1 rail=A until_ms=1500 clamped=0
```

Simulated CE1 remains high after1.1 s, beyond the1000 ms rail-A allowance, with pending=null, history=[] and uncertain=false. This is an actual transport-state/reservation failure, not merely a helper returning the wrong classification.

The host strips the sequence prefix with partition(" "), then accepts the apparent unknown body. Firmware tokenizes **both spaces and tabs**, so the same bytes become CH on firmware. The literal-space prefix correctly refuses.944a820 rejected external prefixes on real paths; the new relaxation exposes this variant. [device.py:685](https://github.com/Brandonio-c/LIO/blob/a0935fb322e9a42459f577417b0167cfec830bfe/software/host/src/lio/device.py#L685), [device.py:790](https://github.com/Brandonio-c/LIO/blob/a0935fb322e9a42459f577417b0167cfec830bfe/software/host/src/lio/device.py#L790), [firmware protocol.cpp:14](https://github.com/Brandonio-c/LIO/blob/a0935fb322e9a42459f577417b0167cfec830bfe/software/firmware/lio_firmware/protocol.cpp#L14).

### B. High: deferred journal failure leaks ownership

After constructing an actual managed fake-serial device, put corrupt JSON at its deferred journal path and call open(). JournalError occurs before transport open, but the acquired lease remains held; a second owner cannot open.

journal.reload() is before the cleanup try. A failed context-manager enter does not call exit automatically. The constructor improvement moved this failure into an unprotected open path. [device.py:330](https://github.com/Brandonio-c/LIO/blob/a0935fb322e9a42459f577417b0167cfec830bfe/software/host/src/lio/device.py#L330).

### C. High: drop_pending treats contradictory evidence as no emission

After successful CE1 ACK, inject STATUS with CE1=1/mask=0. Actual simulated CE stays high; ce() returns success while pending/history are empty and uncertain=false. A missing selectable hole is not proof of no emission after a successful ACK. [device.py:961](https://github.com/Brandonio-c/LIO/blob/a0935fb322e9a42459f577417b0167cfec830bfe/software/host/src/lio/device.py#L961).

The broad DeviceError handler also drops every reservation for unknown errors. A separate fault-contract test forwards CE then injects ERR99; accounting disappears while CE stays high. This is explicitly a robustness injection, not a claim that stock firmware emits after ERR99.

A stronger no-fault “CE1 already high then wrong-rail CE2” case was tested too: the second reserve is rejected before firmware and durable prior pending remains. That particular sequence does **not** demonstrate erased durable exposure; its failed reserve does clear in-memory pending tracking. The report does not use it as the primary drop_pending proof.

### D. High: T10.2 calls a post-emission OFF failure unsupported SKIP

Actual t10_2 admits a B13 pulse, then an injected ERR OFF leaves CE2 high. The broad exception handler records unsupported-budget/capability **SKIP**. The journal correctly retains uncertainty and5000 ms cost; this is a classification failure, not lost accounting in that probe.

The catch covers both admission and OFF. A failure after emission is not the archive's safe pre-emission budget refusal. [t10_safety.py:124](https://github.com/Brandonio-c/LIO/blob/a0935fb322e9a42459f577417b0167cfec830bfe/software/host/src/lio/suite/checks/t10_safety.py#L124).

## 5. Previous caller failures still reproduced at a0935fb

These were rerun against current imports; relevant source-file hashes also match944a820.

| Area | Fresh actual result | Source |
|---|---|---|
| WDT/readback | Actual cap2000, reservation50, MEAS proceeds after contradictory ACK/readback | device.py1237 onward |
| OFF verification | safe_off ERR OFF+unavailable STATUS leaves CE high, pending=null, uncertain=false | device.py415 |
| SWEEP retention | All16 reservations exist, but800 ms becomes384 ms charged using invented stacked edges | device.py1071 onward |
| Response/rail identity | Wrong returned hole/word accepted; wrong-rail debug bounds selected rail rather than energized rail | device MEAS/debug |
| Ownership recovery | Filesystem aliases can acquire separate leases; unknown boot/clock reset grants credit without new generation | ownership.py |
| Permanent protocol cost | Timeout after actual MEAS transmission leaves run reserved/actual/uncertain all0; lower journal retains92 ms | acquisition.py1087 |
| Exact resume | Frozen{12:1,13:5} resumes as{12:5,13:1}, COMPLETE | acquisition.py1250 |
| Operator controls | First actual dashboard intervention auto-confirms start flag; worker self-beats; failed safe state can complete | protocol_job.py111; acquisition.py681 |
| Deadlines |2 s prompt under1 s cap still measures; monotonic1000→0 grants time | acquisition lifecycle |
| Core facts | Gain2 matching gain2 snapshot resumes7 simulated SWEEPs; missing mains readback accepted | scan start/resume/preflight |
| Saved inference | Pilot100+production0,1,2 becomes **25.75, N=4**, claiming includes_pilot=false | uncertainty.py480; derived.py259 |
| Unknown stationary position | Four NaN heights, unresolved N=0; condition-ID filter returns0 after writer drops fields | store.py28; uncertainty.py480 |
| Control/quantity | Bare{8} validates C_A193 OPT101/38 InGaAs; unknown Rf passes matched/profile gate; outside-A0/unknown-Rf O-envelope h12=12.3333, reason=ok | coupling.py156; features.py226; provenance.py597 |
| Reuse/seals | NPZ−280→−279 remains verified; minimal identity accepted; changed detector interpretation leaves seal unchanged | runs.py201; provenance.py |
| Report/source safety | Wrong-run/stale report succeeds; nested derived output and bare legacy writes remain | derived.py239/357; cli.py917 |
| Baselines/profiles | Actual nested Rf/range/assembly facts disappear in baseline adapter; proxy/grouped CLI workflow still disconnected | baselines.py84; profile CLI |
| Qualified target selection | Stored primary selection ID disappears from qualified product/summary; source identity/fresh confirmation incomplete | executor.py47; derived.py269; targets.py |

The labelled legacy report may retain its legacy objective. Its different optimum is not, by itself, a defect requiring legacy output to change. The decisive M5 failure is that the **qualified** path does not consume the stored shared selection or acquire the prescribed fresh confirmation.

The passing FWER helper uses2000 independent32-channel null families at N=8. Production still does not invoke the connected paired/shared-control/familywise pathway. Its ordinary95% intervals and phase/ID loss are not validated by that helper test.

### Actual HTTP and offline plan

A real DashboardServer with simulator starts, publishes a pending occurrence, rejects an unknown occurrence with HTTP400 and returns numerical HTTP200. But submitting JSON confirmed="false" for an actual pending ID returns confirmed=true and completes. The handler coerces truthiness rather than requiring a Boolean.

The served Scan UI still has no answer/numerical endpoint or pending occurrence wiring. This conclusion uses HTTP execution plus source inspection; rendered browser testing remains unavailable because installed Chromium cannot create its socket. [server.py:610](https://github.com/Brandonio-c/LIO/blob/a0935fb322e9a42459f577417b0167cfec830bfe/software/host/src/lio/dashboard/server.py#L610), [index.html:1214](https://github.com/Brandonio-c/LIO/blob/a0935fb322e9a42459f577417b0167cfec830bfe/software/host/src/lio/dashboard/static/index.html#L1214).

The actual protocol-plan route independently succeeds with zero guarded device/serial/WAKE/port calls. That passing offline contract is preserved.

## 6. Residual CE and D01–D20 closure

### CE01–CE14

A narrow PASS below is not acceptance of its broader related milestone.

| CE | Independent result |
|---|---|
| CE01 | Literal fragments/multiline/light-prefix cases PASS; new valid-TAB prefix bypass FAIL |
| CE02 | Actual second-device constructor PASS; failed-open cleanup and full D03 remain FAIL |
| CE03 | Normal WDT lowering PASS; contradictory readback/finite-profile/rail variants FAIL |
| CE04 | Direct off exception/known CE refusal improve; safe_off and contradictory drop_pending FAIL |
| CE05 | Gain2-under-gain1 mismatch PASS; matching gain2 snapshot still violates core gain1 on resume |
| CE06 | FAIL actual open_run after NPZ mutation |
| CE07 | FAIL actual saved pipeline:25.75, N=4 instead of1, N=3 |
| CE08 | FAIL actual dashboard occurrence/false-answer behavior |
| CE09 | FAIL transmitted timeout costs0 and waiting/clock-reset variants; same-boot expiry refusal preserved |
| CE10 | FAIL actual unequal freeze restart |
| CE11 | FAIL actual nested-facts baseline CLI |
| CE12 | PASS actual h16 extraction API; usable batch/CLI opt-in remains incomplete |
| CE13 | Literal left-out indexing fixed; regression can still pass old implementation; actual grouped/proxy workflow not accepted |
| CE14 | FAIL qualified shared-selection identity/consumption and confirmation |

### Canonical D-gates

“Fail” means the complete contract is unmet, not that every subcase remains broken.

| ID | Full gate | Evidence |
|---|---|---|
| D01 | Fail | New TAB raw bypass despite fragment and T10 bypass repairs |
| D02 | Fail | Many-charge waiting works; retained conservative accounting does not |
| D03 ownership | Fail | Constructor fixed; failed-open lease leak, aliases/generation/boot remain |
| D04 OFF | Fail | ERR/unverified OFF and contradictory CE status can lose protection; post-emission T10 failure mislabelled |
| D05 | Fail | Readback, finite bound, energized rail and response validation remain |
| D06 | Fail | Core gain/mains/frozen-facts resume variants remain |
| D07 | Fail | Actual physical/quantitative consumer gates incomplete |
| D08 | Fail | Generation improves but actual live-source reuse remains permissive |
| D09 | Fail broad gate; external routes pass |100-file external-derived invariant; bare/nested source writes remain |
| D10 | Fail | Raw-byte coverage improves; consumed interpretation missing from seal |
| D11 | Fail full contract | C=null preserved; unscoped control validation/covariance remain |
| D12 | Fail | Actual phase/condition/ID loss; disconnected paired/joint/familywise estimator |
| D13 | Fail | Generic first answer, false-safe state and string-Boolean acceptance |
| D14 | Fail | Self-heartbeat, unsafe pause and waiting behavior |
| D15 | Fail | Permanent costs0 after transmission and clock/deadline gaps |
| D16 | Fail | Overwritable freeze, swapped resume, pooled pilot contrast and infeasible comparator |
| D17 | Fail | Qualified shared-selection/fresh-confirmation incomplete |
| D18 | Fail | Baseline and grouped/proxy consumer workflow incomplete |
| D19 | Fail complete workflow | Offline/HTTP pieces pass; real UI/numerical/control integration incomplete |
| D20 | Fail complete release | Python 3.12 checks pass; required Python 3.10 and acceptance evidence do not |

## 7. TEN maintained failures: disposition is largely legitimate

All maintained cases now pass in the complete local run. These corrections must not be misreported as ten repaired physical defects.

| Former cases | Independent assessment |
|---|---|
| Two meter-key failures | Correct default A4/B10. Extra synthetic A6/B11 probe actually emits CH[6,11], preserving wrong-current FAIL/supported-current PASS |
| Two short drift failures | Correct short-data SKIP; separate actual ScanStore/Cube≥330 s healthy/fault controls preserve the300 s threshold |
| PTY robustness | Correct host refusal criterion for malformed light requests on owned serial bridge; not a reason for a private emission bypass |
| T13 rail twin | Correct optical-response rail evidence mapping, with T10 excluded; not an ammeter result |
| Two short-travel fixtures | Correct synthetic positive ranges and unsafe-range SKIP, preserving real margin16384 |
| Long-travel assertion | Old>25000 was incompatible with30000−16384=13616 permitted steps; sampled13412 does not prove truncation |
| Saturation verdict | T06.2 WARN detection retained; existing WARN-only FUNCTIONAL policy predates candidate. This is a test/policy correction, not undetected saturation |

Useful tests remain weak in other places: the new T10 test inspects AST/text rather than executed reservations; the constructor test injects a deferred helper/SimTransport instead of proving the real default; Serial/PTY malformed-light checks reach the gate helper directly; older close-order spy remains unattached. Independent caller probes are therefore material evidence.

## 8. Archived live report: measured failures versus software/capability

Archive: [20261123-135504_host_residual_hw/report.md](https://github.com/Brandonio-c/LIO/blob/a0935fb322e9a42459f577417b0167cfec830bfe/test_results/20261123-135504_host_residual_hw/report.md). Recorded run ID135125_host, start/finish **13:51:25–13:54:54 EST**; the archive folder name is not a second experiment.

Report/results agree: **NOT FUNCTIONAL;28 PASS,1 WARN,5 FAIL,4 SKIP,0 ERROR**, critical T03.2 plus five failing channels. Firmware2.5.2, initial gain1/rate128/mains0; BOOT records **hw_wdt=0**. The source stamp is **944a820 dirty**, not a working-tree content seal proving exact finala0935fb. This can be precommit evidence; it cannot independently establish every final repair was live-tested.

### Each FAIL/SKIP

| Test | Recorded evidence | Classification and limit |
|---|---|---|
| T03.2 FAIL | A0 mean−331.39,sigma37.22 counts,n64; limit sigma≤20 | Real recorded measurement-chain variability; cause unresolved, not a software exception or proof of physical A0 voltage |
| T05.1 FAIL | h12 InGaAs below detection while OPT101 responds | Under-threshold response; driver/CE/LED-dead causal wording is unsupported |
| T05.2 FAIL | InGaAs nets h8=22,h9=38,h12=8,h13=−1,h14=−2 versus≈263 threshold | Expected responses unresolved in this configuration; no globally-dead detector or calibrated optical amplitude established |
| T05.3 FAIL | Expected InGaAs patterns absent | Detector-pattern criterion fails; swapped/misrouted/stuck-on cause not isolated |
| T06.3 FAIL | h8/h9 not detected above threshold by both detectors | Cross-response/calibration requirement unmet; no quantitative ratio qualification |
| T04.2 SKIP | No loopback jumper | Optional physical capability unavailable, not a passed test |
| T04.3 SKIP | Delegated to T05.3 | No duplicate test; T05.3 failed, so no optical-address qualification follows |
| T10.2 SKIP, BOTH rails | A/h3:2000 ms default versus1000 ms budget; B/h9:5000 ms versus h9's1000 ms override | Legitimate pre-send policy refusal in these cases; watchdog cut-off not observed; other B holes have5000 ms limits |
| T11.1 SKIP | No baseline supplied | Comparison/reference unavailable |

The measurement FAILs are consistent with analog/optical/setup/measurement-state problems, but this archive does not identify their cause or prove they are categorically unrelated to software/settings. Preserve the failures; do not relabel them optical PASS because offline tests pass. Prior successful h8/h9 responses and mounted/handheld differences still preclude calling InGaAs globally dead.

### What the PASS labels do and do not prove

- **T06.2 versus T03.2:** the broader TIA sanity gate uses sigma≤100 and offset/polarity/headroom checks. Its PASS is consistent with sigma37.22 failing the stricter20-count test. It is not optical throughput or physical-range qualification.
- **T03.5:**60 s stability under a separate2%FS/min rule is not low instantaneous noise or the scan-analysis300 s drift criterion.
- **T05.5:** its PASS explicitly says weak/detector-unusable readings were **not judged**. No positive repeatability or SNR evidence follows.
- **T08.1/2:**16-record schema/order/timing and per-sweep averaged-dark stability pass. Individual InGaAs h12 repeated nets are[17,−88,26,43,−7]; an averaged-dark PASS does not qualify per-hole precision.
- **T08.3:** agreement is tested only on OPT101 holes4,8,9,10,11; not InGaAs.
- **T10.1/3/5:** observed reset/reopen/failsafe states pass in those cases; every crash/OFF failure path is not thereby proven. T10.4 records **host refusal before write**, not newly exercised invalid-mask firmware behavior.
- **H16:** OPT101 net199 is recorded, with repeated SWEEP nets[201,200,201,201,198]. “Seen by nothing as expected” means no eligible detector was judged, not absence of measured response. It remains spectrally unassigned/proxy, never primary1850 chemistry.
- **Duty:**112.42 s cooldown and no reported in-memory over-budget entries are archived. No complete durable journal/edge trace proves all M1 invariants.
- **Automatic scope:** no interactive meter or T09/T13 stepping/height workflow was qualified. The archive does include dark ADC gain sweeps and motion arming/disarming; source can POWER WAKE coils. No allow-motion flag means no commanded travel tests, not a passive/no-actuation catalogue. Those are archived actions, not actions by this audit.

The acceptance document's separate spot-MEAS table lacks its own linked raw transcript/settings/timing evidence. Treat it as supplementary notes, not independent qualified measurement proof. The archived gain checks are not a voltmeter/Rf measurement or M7 qualification.

## 9. ORIGINAL M0–M6 matrix

| Original milestone | Software verdict | Physical/current-rig distinction |
|---|---|---|
| M0 reproducible provenance, units and compatibility | **Partial; not accepted** | Live-source reuse/frozen facts/consumer restrictions still fail; A0/Rf/geometry evidence deferred |
| M1 one owner and strictly bounded durable exposure | **Fail** | New raw/status/cleanup failures plus old timing/accounting defects; archived T10 skips do not establish current-rig admission |
| M2 independent roles/coupling uncertainty | **Partial; not accepted** | Correct C=null/h16 restrictions; scoped controls and estimator covariance incomplete |
| M3 signed fixed-N estimates and honest uncertainty | **Fail** | Saved-data pipeline violates split/identity and connected covariance/family policy despite helper FWER PASS |
| M4 stationary execution/pilot allocation | **Fail** | Permanent budget, prompt/heartbeat/deadline and exact-resume contracts fail offline |
| M5 shared target-specific scout/confirm | **Fail** | Qualified selection consumption/source identity/fresh acquired confirmation incomplete |
| M6 complete CLI/dashboard/report/profile/release | **Fail** | Actual integrations incomplete; Python 3.10 CI fails; isolated wheel/extras matrix not qualified |
| M7 | **Deferred; isolation preserved** | No automatic core caller found; legacy live gain selftest is not extension qualification |

A0/Rf/ammeter/optical/reference checks remain owner-deferred. Synthetic success can exercise software but cannot supply those physical facts. Their absence cannot excuse unfinished offline implementation.

## 10. Static/CI evidence and documentation overclaims

Exact-candidate [Actions run45244330995](https://github.com/Brandonio-c/LIO/actions/runs/45244330995):

| Step | Final observed result |
|---|---|
| Ruff 0.15.4 check + format | Success |
| Python 3.10 mypy | Failure; unit/sim and coverage skipped |
| Python 3.12 mypy | Success |
| Python 3.12 unit/sim/fault tests + coverage gate | Success |
| Firmware compile/SRAM jobs | Success in CI; not evidence that a hardware-watchdog build was flashed |

Local Ruff check/format attempts exit127 because the binary is unavailable. CI is the genuine passing evidence. Existing exclusions for three archived scripts remain unchanged from944a820; no new narrowing occurred in this commit.

Local whole-host strict mypy checked125 files with genuine mypy 1.15.0/Python 3.12.14 and reported five diagnostics: config.py98, foods/structure.py778, uncertainty.py521, food_profiles/distances.py116, cli.py958. These are version-sensitive and are **not asserted to be the exact CI3.10 diagnostics**. Exact CI3.12 passes; Python 3.10 diagnostic logs were not retrievable through the reader. Full command/environment are in static_live/FINDINGS.md.

The new acceptance handoff overclaims:

1. Its blanket **“CE06–CE14 PASS(existing fullpass)”** inherits known failed actual callers. The associated production files were not repaired.
2. Its original M0–M6 PASS table is contradicted by fresh saved-data, budget, operator, reuse, target and baseline reproductions.
3. **M1 “software/fail-closed PASS”** is contradicted by the new TAB bypass and status/error handling, independently of the real-rig timing disclaimer.
4. **“Live host fixes confirmed”** is too broad without an exact working-tree seal and complete reservation trace. The archive supports particular observed outcomes, not every final caller invariant.
5. **“Not a software-gate miss”** cannot be inferred as a general root-cause exclusion. The live measurement failures and software failures are separate findings.

The documented912/0/6 run and our918/0/12 run can both be real. The problem is promoting passing selected/maintained checks into proof of complete contracts.

## 11. Blockers and evidence record

Full software acceptance remains blocked by actual emission/ownership/OFF failures, unsupported finite timing assumptions, nonpersistent experiment spending, broken resume/operator controls, incomplete source/quantity eligibility, disconnected stored-data statistics/selection and missing downstream UI/profile integration. Required Python 3.10 release proof also fails.

Current-rig acceptance separately remains limited by unobserved watchdog cutoffs in the chosen live tests, no defensible finite cooperative-service exposure proof, the archived NOT FUNCTIONAL measurement outcome and deferred physical/reference evidence. This audit proposes no new bench action.

External-derived audit/analyse/report paths preserve all100 files in the three historical acquisitions, including72 NPZ streams. The live archive's nine files and all542 materialized source blobs also remain unchanged. Bare/nested legacy-writing counterexamples used copies; no historical evidence was rewritten.

**No measured SNR improvement or recovered SWIR/1850 chemistry is justified by this software alone.**

### Reproduction and verification provenance

The [caller regression catalogue](LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md) records actual inputs, observed failures, expected assertions and the twelve executed audit-test names. The [current implementation plan](../SENSOR_READINGS_CALLER_REMEDIATION_PLAN.md) maps them to connected repairs.

Commands referring to residual_audit_a0935fb_20261123 above are records from the independent audit workspace, not installed repository APIs. Audit-only executable scripts/logs were workspace artifacts; this documentation publication does not add tests or product-code changes. The catalogue provides reproduction recipes that can be implemented as maintained tests without those unpublished paths.

Subsequent authorization: the owner now reports the board connected and requests implementation plus full offline/live tests. That prospective scope is in the [implementation handoff](../handoffs/2026-11-23_caller_remediation_implementation.md). It does not change what this earlier offline audit did or qualify the archived physical measurements.
