# Caller regression catalogue: independent a0935fb audit

**Baseline:** a0935fb322e9a42459f577417b0167cfec830bfe.  
**Purpose:** turn independently executed actual-caller failures into maintained regression tests. This is documentation, not an imported test module or hardware instruction.

Read the [audit](LIO_V3_RESIDUAL_REMEDIATION_QA_a0935fb_2026-11-23.md) and [implementation plan](../SENSOR_READINGS_CALLER_REMEDIATION_PLAN.md).

The maintained baseline suite passed 120 targeted and 918 full unit/simulator tests. Separately, the first twelve cases below failed in three audit invocations: safety 3, saved statistics 3 and provenance 6. They are not added to maintained-suite failure totals. Historical audit scripts/logs were workspace artifacts; no unpublished scratch path is required to recreate these cases.

## Test boundary

Use actual LIODevice/CLI/dashboard/ScanStore/reader/estimator/selector code. Fake only the physical transport, operator, clock and external boundaries. For serial-branch tests, subclass SerialTransport and override every OS I/O operation to delegate to SimTransport; use a unique synthetic port identity and temporary state root. This exercises real managed serial ownership rather than the simulator shortcut. Trap any unintended physical serial open.

Capture per-write traces and before/after ledger/status snapshots. Do not make the validator/reader under test return a mocked expected result. Port behavior, not brittle audit bootstrap paths or exception wording. A corrected implementation may return a documented typed error where the old probe continued, but its state/admission guarantees must be proved.

## Twelve executed failing acceptance cases

| ID / canonical contract | Actual setup and observed baseline | Required assertion |
|---|---|---|
| A01 / D01 | After real-path fake open, send_raw(b'@123\tCH 1 ON 1500\n',.1) returns OK CH; CE1 stays high after1.1s; no reservation/history/uncertainty | Refuse before an emitting write. Trace/state must prove no emission, not merely an exception after send |
| A02 / D03 | Construct managed fake serial device, write corrupt JSON to deferred journal, call open; JournalError occurs with lease held and transport unopened | Failed open releases ownership and closes any partial transport; second owner is not blocked by leaked lease |
| A03 / D04 | Select h1; actual CE1 command ACKs; transport then reports STATUS ch1/CE1high/mask0. ce() drops reservation and returns success | Contradictory/unknown completion cannot erase full cost or claim safe; block new light pending verified recovery |
| A04 / D12,CE07 | Actual ScanStore rows: pilot100, production0/1/2, h12/InGaAs, height−100, distinct block/read IDs, conditionu/settings0. analyse_model qualified-v2 returns25.75,N4,includes_pilot=false | Production estimate1,N3 through saved reader |
| A05 / D12 | Same saved rows, empty height and one position_instance_id | Correct stationary estimate1,N3; no four-NaN-height rejection or invented coordinate |
| A06 / D12 | Save those four rows with condition_id=u; writer drops it; numerical filter returns0 | Actual stored rows retain identities; condition filter retrieves4 observations |
| A07 / D08,CE06 | Copy current historical run. Generate qualified-v2 analysis, save matching product as analysis.json, verify open_run. Change raw[0] in a valid NPZ by1 | Actual open_run invalidates saved reuse; do not merely pass current hashes directly to helper |
| A08 / D08 | Save only identity.source_cube_sha256 matching the copied cube | Missing required scan/calibration/estimator/consumed-input identity is not verified |
| A09 / D09 | Actual CLI scan analyse COPY --model qualified-v2 --derived-out COPY/derived creates products | Reject source-contained output, including symlinks; source manifest unchanged |
| A10 / D08,D19 | Derive product from copied runA; actual report CLI requests runB with A's analysis ID | Reject wrong-run/revision product and stale live sources |
| A11 / D10 | Actual ScanStore metadata identifies raw audit.npz as InGaAs; seal; change consumed detector mapping to OPT101; seal stays identical | Interpretation change changes source identity/seal; no self-reference |
| A12 / M0,D06 | Build frozen acquisition snapshot from nested dict; mutate original nested value1→2; manifest hash changes | Defensive immutable snapshot retains original facts/hash |

Executed audit test names:

```text
test_actual_managed_raw_tab_prefix_refuses_before_light
test_actual_failed_open_releases_lease_on_corrupt_journal
test_actual_ce_ack_conflicting_status_retains_charge
test_actual_derived_excludes_pilot
test_actual_unknown_height_stationary_instance_preserves_estimate
test_actual_saved_condition_filter_retains_observations
test_actual_profile_reader_refuses_changed_npz
test_actual_profile_reader_requires_complete_identity
test_actual_cli_rejects_derived_inside_acquisition
test_actual_cli_report_checks_requested_run
test_actual_terminal_seal_identifies_stream_mapping
test_snapshot_defensive_freeze
```

A01 is not just a simulator grammar quirk: firmware protocol.cpp tokenizes spaces AND tabs while host sequence stripping partitions only a literal space. The literal-space prefix is correctly refused. The real board was not used for the audit.

A04–A06 fixture must go through ScanStore.append_rows/finish, Cube and actual derived/numerical readers. Constructing FixedPositionBlock directly bypasses the defect. Both detector rows from one MEAS share reading identity; technical repeats are not extra independent blocks.

A07–A10 use copies of tracked runs only, for example test_results/20261123-003133_scan_quick and the Nov19/20 anchors. Never modify original analysis/cube/streams/reports.

## Additional executed caller probes to maintain

| ID | Baseline behavior / required result |
|---|---|
| A13 / D04,T10 | Actual t10_2 with working synthetic B13: admitted first pulse, then ERR OFF. CE remains high and ledger correctly uncertain/5000ms retained, but result is unsupported SKIP. Require post-emission FAIL/ERROR/incomplete, distinct from pre-send budget SKIP |
| A14 / D15,CE09 | Forward actual MEAS to SimTransport, then timeout before response. Lower journal retains92ms, but permanent run reserved/actual/uncertain all0. Require durable pre-send experiment charge |
| A15 / D16,CE10 | Measured production freeze{12:1,13:5}, interrupt/restart; total production becomes{12:5,13:1}, COMPLETE. Require exact full ordered frozen schedule and validated progress |
| A16 / D13,CE08 | First dashboard intervention auto-confirms start flag; actual HTTP confirmed="false" for issued ID becomes true/COMPLETE. Require fresh occurrence answer and strict Boolean schema |
| A17 / D14,D15 | Worker self-beats; prompt2s under1s cap still measures; monotonic1000→0 grants time. Require finite waits/deadlines/continuity and responsive safe abort |
| A18 / D06,CE05 | Live simulated gain2 matching frozen gain2 bypasses core gain1; missing mains readback accepted. Require core profile and actual applied facts on start AND resume |
| A19 / D07,D18,CE11 | Actual verified synthetic outside-A0/unknown-Rf O-envelope yields h12≈12.3333 reasonok; unknown-Rf matched ratio eligible; nested baseline facts dropped by CLI adapter. Require dependent physical/quantitative branches to refuse or be ineligible while preserving raw and valid OPT101; adapters retain required facts | 
| A20 / D11 | Bare{8} confers validated_control C_A193 OPT101/38 InGaAs with covariance stub. Require scoped source/load/epoch evidence and actual estimator covariance; no-evidence C stays null |
| A21 / D17,CE14 | Qualified product/summary omits stored selection ID; scaling scout values can retain ID; fresh confirmation not acquired. Require consumed source-bound decision. Labelled legacy objectives may remain separate |
| A22 / D18,CE12–13 | h16 extraction API works (proxy,280counts); actual batch/CLI does not opt in/grouped-evaluate. Require actual opt-in and valid held-out workflow without primary1850 namespace |
| A23 / D05 | Wrong ACK/readback admits actualWDT2000/reservation50; unsupported profile returns bound; wrong rail/hole/response word accepted. Require supported finite admission and complete validation |
| A24 / D02,D04 | SWEEP800ms reserved becomes384ms from invented edges; safe_off ERR+missing STATUS can clear accounting while CE high. Require conservative retained cost and verified OFF |

A15's1/5 allocation is a resume fixture. The h12N=1 interval must be unavailable unless a separately valid known-variance method is explicitly supported; use adequate-N independent fixtures for the successful statistical path.

## Positive controls that must remain

- Literal b'C' + b'H 1 ON 1500\n' fragments refuse; actual second managed constructor leaves the live journal unchanged.
- Known pre-emission wrong-rail CE refusal leaves CE low without poisoning the next MEAS.
- Actual t10_2 supported synthetic pulses each have reservations; selected live A3/B9 default-pulse requests may legitimately SKIP before emission.
- wait_needed_many waits for the whole operation, then16-record SWEEP succeeds.
- Ordinary n=2, mains2/8/8/2, negative ConsoleOperator answers, same-boot expired resume and exact gain2-under-gain1 rejection.
- Unknown C=null; h16 proxy extraction works, primary1850 exclusion retained.
- Full external-derived campaign preserves100 historical files/72 NPZ streams.
- Configured meter probes are A4/B10; alternate synthetic A6/B11 actually transmits those holes and preserves wrong-current FAIL/supported-current PASS.
- Short drift correctly SKIPs; >=330s saved healthy/fault controls satisfy the unchanged300s criterion.
- Margin16384 is unchanged; correct synthetic travel/target expectations and saturation WARN/global FUNCTIONAL policy remain.
- Actual offline protocol plan makes no Device/serial/port/WAKE/ARM call.

## Physical evidence limits

Use the archived live report for physical observations, not these synthetic probes. It records NOT FUNCTIONAL with high InGaAs noise/under-threshold responses, both chosen watchdog tests skipped, source944a820 dirty and hw_wdt=0. It does not identify a dead driver/LED/detector, qualify A0/Rf/reference or establish a worst-case timing margin.

No measured SNR improvement or recovered SWIR/1850 chemistry follows from this catalogue.
