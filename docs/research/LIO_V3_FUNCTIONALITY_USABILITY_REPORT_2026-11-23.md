# LIO V3: actual functionality and owner usability

**Independent assessment — 23 November 2026.** Repository: Brandonio-c/LIO, `main` snapshot **`92bee4a2b3f702b3ba6c294e5ef4d9af716729e4`**. This is an assessment of recorded operation and current callers, not an optical acceptance certificate or an implementation plan. “Today” means the latest evidence committed at this revision; the physical instrument was not contacted during this audit.

**Publication note:** the owner subsequently authorized publishing this report with the [practical software upgrade plan](../SENSOR_SUITE_PRACTICAL_UPGRADE_PLAN.md) and coding handoff. The no-push statements below describe the completed audit, before that separate documentation publication. Publication adds no new software acceptance, bench observation or physical qualification.

## 1. Bottom line

LIO is usable today as a commissioning and diagnostic prototype, and conditionally for exploratory visible/NIR fingerprints from the OPT101. It can execute a substantial height scan, save raw data, enforce many managed operating restrictions, and perform short stationary captures. It is not yet a reliable SWIR food instrument, a calibrated quantitative analyser, or an 1850 nm measurement system. The most recent completed height scan remains **NOT FUNCTIONAL** optically: InGaAs noise is high and mounted 1450–1650 nm responses are weak, absent or unstable. The detector is not globally dead: a small integrated hole-8 response repeats locally, and earlier direct-illumination records are strong. Commanded motion over the common tracked range works, but full travel, physical level and mechanical repeatability are unqualified. The cooperative watchdog has no proven firmware-hang bound. Raw archives and several reuse checks work, but incomplete height identities, permissive resume validation and dashboard workflow defects prevent calling the acquisition-to-analysis system fully reproducible or straightforward for its owner.

## 2. Evidence and verdict conventions

**Works** means the specified behavior was demonstrated under the recorded conditions. **Partly works** means useful behavior exists with a material limitation. **Does not work** means the intended use is contradicted by current evidence or lacks the required physical measurement path. **Unknown** means the necessary observation is absent. A refusal demonstrates protection, not measurement capability. A saved COMPLETE status means acquisition finished, not that the optics passed.

Confidence is confidence in the stated conclusion, not a probability that an untested future run will succeed. Small repeat sets establish local technical consistency, not independent preparation/day reproducibility.

| Evidence key | Pinned-repository location and use |
|---|---|
| H23 | [`20261123-162705_host/results.json`](../../test_results/20261123-162705_host/results.json): full automatic/motion catalogue; raw subresults and repeat arrays |
| Q23 | [`20261123-173108_scan_quick/`](../../test_results/20261123-173108_scan_quick/): fixed closing-check code; `scan.json`, raw `cube.csv.gz`, `streams/*.npz`, analysis/report |
| P1 / P2 | [`175731_scan_protocol`](../../test_results/20261123-175731_scan_protocol/) / [`180942_scan_protocol`](../../test_results/20261123-180942_scan_protocol/): stationary holes 8 and 12; raw cubes, frozen schedules, progress and budgets |
| D23 | [`derived_caller_acceptance/`](../../test_results/derived_caller_acceptance/): source-bound qualified-v2 products and reports; `live_protocols/live_protocol_log.json` and `live_protocol2_log.json` |
| HR | [`135504_host_residual_hw/results.json`](../../test_results/20261123-135504_host_residual_hw/results.json): earlier current-state automatic catalogue |
| H18 / H19 / H20 | [`20261118-002742_host`](../../test_results/20261118-002742_host/), [`20261119-142221_host`](../../test_results/20261119-142221_host/), [`20261120-003626_host`](../../test_results/20261120-003626_host/): historical dark, LED, repeatability and safety observations |
| Q19 / Q20 / Q00 | [`20261119-152512_scan_quick`](../../test_results/20261119-152512_scan_quick/), [`20261120-012619_scan_quick`](../../test_results/20261120-012619_scan_quick/), [`20261123-003133_scan_quick`](../../test_results/20261123-003133_scan_quick/): raw streams and height comparisons |
| Tray records | [`tray_v3/`](../../test_results/tray_v3/): empty-tray and Citrucel scans; remount, handheld, integration and replacement/current records |

The `170350_host` / `170352_scan_quick` pair is retained as an operational failure but **excluded as a test of the closing-check fix**: the restart had not taken effect. The `153237_sim` and `161237_sim` runs are simulator evidence only. Merged historical host records are not counted as independent repeats of the measurements they copy.

## 3. Capability table

| Subsystem or claim | Verdict | Recorded evidence and practical limit | Confidence |
|---|---|---|---|
| OPT101 raw visible/NIR acquisition | **Works**, within the tested setup | H23 T03.2 dark σ **0.47 count**, n=64; T05.2/T08.2 show useful signals on holes 1–11. Most five-sweep visible channels have SD below 1 count; holes 1, 9 and 10 need flags. This is raw response, not calibrated reflectance. | High locally; between-day transfer unknown |
| Current OPT101 food fingerprints | **Partly works** | Current empty-chamber responses are observable. A real historical Citrucel scan has large OPT101 signals, but it predates LED/current changes. No current-epoch, independent preparation/day classification validation is demonstrated. | Medium |
| InGaAs raw acquisition | **Partly works** | P2 hole 8: **28.5 ± 0.84 counts**, sample SD, n=6 integrated readings. H23 fast sweeps are very variable; T03.2 σ **37.47 > 20**. Narrow low-bandwidth repeats do not make the entire path healthy. | High |
| Mounted 1450–1650 nm food measurement | **Does not work reliably** | H23 holes 12/13/14 nets **22/8/1 counts**; P2 hole 12 **−8.67 ± 6.22**, n=6. Q23 hole 12 changes sign; holes 13/14 show little height response. | High for latest state |
| 1760 / 1850 nm primary measurement | **Does not work as an established primary measurement** | Hole 15 lies beyond the InGaAs's specified 1750 nm range; emitter-tail overlap is unqualified. Hole 16 OPT101 has a repeatable raw response with unassigned spectrum, not primary-1850 evidence. | High |
| Height motion and tracked return | **Partly works** | Q23 COMPLETE, 20 managed moves, no recorded unlevel events/unexpected boots; tracked start/end both `[−16384,−16384]`. No independent position measurement. | High for command/tracker consistency |
| Full travel and mechanical repeatability | **Unknown** | T09.6/.7 refused; latest backlash and repeatability findings are SKIP. Unequal bottom marks prevent the catalogue's both-bottoms operation. | High that qualification is absent |
| Normal managed light restrictions | **Partly works** | Live reset/idle, communication timeout, arming and host refusals; persistent cooldown refusal in P1. Numerous fault branches have offline tests, not matching live fault injections. | High within tested cases |
| Finite exposure after a firmware hang | **Unknown / unproven** | Nano R4 reports `hw_wdt=0`; both cutoff services require executing firmware. Owner explicitly accepted cooperative operation without a proven hang bound. | High that no finite bound is established |
| Existing archived bytes and derived source binding | **Works in checked cases** | All three recent scan seals verify; both D23 qualified products validate against source hashes. Actual saved-data callers reject a copied NPZ mutation. | High for checked archives |
| Complete identities, reconstruction and robust resume | **Partly works** | Stationary identities are present, but all eight new identity fields are blank in all **764** Q23 rows. Copy-only missing-detector/changed-condition resume probes were accepted and resealed. | High; reproduced callers |
| Dashboard-only owner workflow | **Partly works** | Suite/height scan can run after one setup confirmation. Protocol API capture/pause/abort/resume works in archives; browser Resume routes protocols to the wrong caller, and browser checkpoint-answer controls are absent. | High on sources/probes; no fresh live browser test |
| Calibrated current, reflectance or ingredient concentration | **Does not work as a supported claim** | Unverified A0, unreconciled Rf/current metadata, unknown coupling/reference qualification and missing validation. Correct raw counts and supported ADC-referred arithmetic remain useful. | High |

## 4. Per-channel measurement core

These are **signed lit-minus-dark counts**. Wavelengths are nominal source labels, not measured spectra. In the table, `M` is H23's single T05.2 MEAS; `S` is mean ± sample SD of its five T08.2 SWEEPs. MEAS used approximately **78 ms** light and SWEEP **25 ms** per hole; these modes must not be pooled as interchangeable repeats. Q23 used gain 1, 60 Hz × 2-period integration, 8 ms settling. “Return difference” is median/max absolute up/down difference at eight exactly shared heights; it is not fixed-position independent replication.

| Hole | Nominal source | OPT101 status and counts: M; S, n=5 | InGaAs status and counts: M; S, n=5 | Repeatability / qualification note |
|---|---|---|---|---|
| 1 | 395 nm | **Partly works:** +31; **25.2 ± 3.5** | **Unknown optical component:** −3; 15.2 ± 75.3; no assigned primary response | OPT sweep 21–30; return difference 1/2 counts. Local height consistency does not remove sweep variability. |
| 2 | Purple, ~405 nm | **Works locally:** +47; **51.8 ± 0.4** | **Unknown optical component:** −2; 33.8 ± 71.4; no assigned primary response | OPT return 1/3 counts. |
| 3 | Blue, ~465 nm | **Works locally:** +31; **31.6 ± 0.5** | **Unknown optical component:** −8; 30.4 ± 78.9; no assigned primary response | OPT return 1/1. |
| 4 | Green, ~525 nm | **Works locally:** +56; **56.4 ± 0.5** | **Unknown optical component:** −6; 11.2 ± 87.5; no assigned primary response | OPT return 1/2. |
| 5 | Yellow, ~590 nm | **Works locally, weaker:** +26; **26.2 ± 0.4** | **Unknown optical component:** 0; −2.4 ± 79.0 | OPT return 0.5/2. Do not use a source label alone to certify an InGaAs electrical control. |
| 6 | Orange, ~605 nm | **Works locally, weaker:** +23; **22.0 ± 0.0** | **Unknown optical component:** +4; −24.2 ± 70.9 | OPT return 1/3; past intermittency. Zero SD for five rounded counts is not zero instrument noise. |
| 7 | Red, ~630 nm | **Works locally:** +31; **30.8 ± 0.8** | **Unknown optical component:** +11; −25.6 ± 77.8 | OPT return 1.5/3. Manufacturer InGaAs range includes a red edge; guaranteed blindness is unproved. |
| 8 | 850 nm | **Works locally, strong:** +167; **163.0 ± 2.4** | **Partly works:** +23; 17.8 ± 88.2; weak integrated response survives | P2 OPT **157.67 ± 3.50**, InGaAs **28.5 ± 0.84**, n=6 each. Unknown coupling prevents optical qualification. |
| 9 | 940 nm | **Partly works:** +117; **102.2 ± 5.1** | **Partly works:** +42; 40.6 ± 80.3; weak/unstable, not qualified | OPT sweep/MEAS disagreement 12.6%; return OPT 7.5/17, InGaAs 8.5/23. Historical intermittency is relevant. |
| 10 | White broadband | **Partly works:** +53; **56.6 ± 15.3** | **Unknown optical component:** +15; 32.8 ± 76.2 | OPT sweep 30–66. Broadband, not monochromatic 450 nm; InGaAs tail contribution/control validity unknown. |
| 11 | Pink broadband | **Works locally:** +153; **152.8 ± 2.0** | **Unknown optical component:** +20; 47.4 ± 75.5 | OPT return 2.5/9. Broadband; not a guaranteed blind InGaAs control. |
| 12 | 1450 nm | **Does not work as primary 1450:** +10; 9.2 ± 1.3, unassigned | **Does not work reliably:** +22; 29.0 ± 87.2 | Q23 descent ranges OPT −22..41, InGaAs −37..33; return differences 15.5/41 and 16/52. Stationary P2 InGaAs mean is negative. |
| 13 | 1550 nm | **Does not work as primary 1550:** +1; 2.0 ± 0.0 | **Does not work reliably:** +8; −2.0 ± 82.0 | Q23 InGaAs approximately 2–6 counts on descent; no useful height-dependent response demonstrated. |
| 14 | 1650 nm | **Does not work as primary 1650:** +1; −0.8 ± 0.4 | **Does not work reliably:** +1; −27.2 ± 71.7 | Q23 InGaAs −1..2 counts on descent. Failure predates the recorded Rf/remount checks. |
| 15 | 1760 nm | **Does not work as primary 1760:** +1; 2.0 ± 0.7 | **Does not work as a qualified 1760 channel:** +1; −32.2 ± 73.8 | Cutoff-sensitive possible tail overlap, not calibrated nominal-band sensitivity. |
| 16 | 1850 nm | **Partly works only as an unassigned proxy:** +197; **194.0 ± 2.7** | **Does not work as primary 1850:** +24; 7.8 ± 85.2, unassigned | Q23 OPT 184→382 on descent; return median 3.5/max 27. Repeatability/height modulation does not assign its spectrum. |

The OPT101's visible/NIR coverage supports interpreting holes 1–9 and appropriate components of broadband 10/11 as plausible primary optical channels; it does not turn holes 12–16 into silicon SWIR measurements. The [TI OPT101 datasheet, spectral-responsivity plot](https://www.ti.com/lit/ds/symlink/opt101.pdf) and [Marktech MTPD1346D-100 datasheet, p.1](https://specs.marktechopto.com/pdf/products/datasheet/MTPD1346D-100.pdf) were checked. Marktech specifies **600–1750 nm**, while the repository often says 800–1750 nm. Neither the range nor a small nonzero net establishes an eligible optical control or a calibrated channel near an edge. A genuine 1850 nm LED is compatible with shorter-wave secondary emission and/or electrical pickup being recorded by this apparatus; the data do not establish a wrong LED, upconversion, or primary-1850 sensitivity.

### What the repeat tests actually establish

| Observation | Evidence | Interpretation |
|---|---|---|
| Current OPT101 has useful local resolution | H23 dark mean 56.33, σ 0.47, n=64; visible nets mostly 23–56 counts, h8/h11 about 150–167 | Adequate for exploratory raw profiles if the sample effect exceeds acquisition/preparation drift. It is not evidence of food discrimination across preparations. |
| T05.5 is PASS | Every expected channel is **“not judged”**, net <1000 or detector unusable; no ten-repeat array | **No per-channel repeatability qualification.** |
| T08.2 is PASS | Its subchecks judge averaged dark stability; InGaAs dark span 4 counts | **Not net-signal repeatability:** InGaAs h8 spans −73..127, h9 −64..127, h12 −89..116 across five sweeps. |
| Current h8 InGaAs survives integrated stationary capture | P1 `[28,29,30]`; P2 `[28,28,28,29,30,28]` | The path is not globally dead. This is weak raw drive response; coupling and optical provenance remain unresolved. |
| Current h12 does not recover in those captures | P1 `[−11,15,2]`, mean +2, 95% interval −30.29..34.29; P2 `[−11,−9,−17,0,−12,−3]`, mean −8.67 | A `kind=positive` sign label in P1 is not detection. A negative interval in P2 is not negative light. Neither run measured the needed eligible optical/electrical controls. |
| Current h9 disagrees between modes | H23 MEAS 117 vs SWEEP about 102 OPT counts; T08.3 FAIL | Consistent with its history of failure/rework and variable return, but mode differences and uncontrolled state prevent assigning a contact, LED or geometry cause. |

The current ≈30 mA drive is owner-reported and stated in `LED_CONFIRM_SWEEP.json`; `DRIVE_TUNE_A/B.json` have empty `readings` and `accepted_ma:null`. This is not ammeter confirmation. Current visible output is usable for a pilot, but historical food amplitudes cannot be promised at this source epoch, and increasing drive is not a free signal-to-noise remedy. Earlier weak/dead visible outputs after reported ≈50 mA and subsequent replacement are recorded.

## 5. InGaAs: established facts, possible causes and unknowns

| Question | Verdict | Established from raw records | Consistent with, but not established | Still unknown |
|---|---|---|---|---|
| Dark noise | **Does not meet the present T03.2 limit** | H23 n=64, mean **−331.22**, σ **37.47 counts**, limit 20; HR σ 37.22. Latest raw high-rate coils-off streams have σ **52.96–55.89**. | Dominant periodic interference contributes strongly; electrical pickup and ambient modulation are candidates. | Exact source, stability over days, and response to a controlled electrical/ambient intervention. |
| Dark offset | **Recorded reliably; physical interpretation unknown** | Around −167..−169 counts in earlier epochs, approximately −330..−332 now. Q23 median −332.31 gives **−41.53875 mV ADC-referred** at supported gain-1 scale. | Approximate doubling is consistent with the reported 1→2 MΩ feedback change amplifying an existing offset. | A0's measured operating voltage, actual resistor verification, bias/leakage mechanism and transfer validity. A negative ADC code alone is not a voltmeter observation. |
| 60 Hz hum | **Established; not physically solved** | Independent fits to Q23 `{t_us,raw}` NPZ arrays reproduce **75.8025 counts / 9.4753 mV** 60 Hz sinusoidal amplitude; 180 Hz **9.142 counts / 1.143 mV**. Harmonics account for **99.57%** of fitted-burst variance. | Earth/charger path, shielding, synchronous ambient light and changed transimpedance/Rf may contribute; compared core scans retain ADC gain1. | Which path dominates and whether one intervention changes it reproducibly. Owner-declared earth connection refutes treating “missing earth” as a verified fact. |
| h8 / h9 | **Partly works, weak** | H23 +23/+42; P2 h8 28.5 ±0.84, n=6. Direct-illumination handheld values were much larger. | Poor sample-return coupling, integration sensitivity and source/contact state are plausible. | Fraction truly optical under the current load, and reliable mounted throughput on independent repeats. |
| h12–15 | **Does not work reliably now** | Latest mounted measurements are near zero, negative or unstable; longer integration record did not restore their means. | Mount/aim/path loss and source condition are strongly motivated by handheld versus mounted comparisons. | A causal separation of source output, optical geometry, ambient leak and front-end behavior. |

The low-bandwidth results must be kept separate: Q23 longdark at **8 SPS**, n=240, has σ **1.278 counts**; harmonic-fit residual σ is **4.22 counts**. These are different estimators/bandwidths from T03.2. They show that selected processing/integration can reject a periodic component; they do not refute the noise failure or demonstrate a measured improvement in food-measurement SNR.

### Chronology prevents a simple “Rf/remount caused everything” conclusion

| Date/state | Direct numbers or event | What can be concluded |
|---|---|---|
| 18 Nov, H18 | Dark −167.45, σ **2.59**; InGaAs h12/h13/h14 **81/36/35** counts, threshold 18 | Weak positive SWIR existed in that setup. Not calibrated chemistry. |
| 19 Nov, H19 | Dark −168.55, σ **4.80**; h12 MEAS **−98**, while SWEEP **311**; h13/h14 31/39 | Earlier operation was already intermittent/inconsistent. It was not uniformly healthy. |
| 20 Nov, H20 / Q20 | Dark σ **3.34**; h12/h13/h14 **66/29/27**, threshold 24. Q20 raw 60 Hz amplitude **1.289 mV** | Another weak working state, with a small margin above its criterion. |
| 20 Nov, new empty tray `173515_scan_full` | Legacy h12/h13/h14 O **38.0/12.8/4.7**; h14 FAIL | h14 failure predates recorded 2 MΩ/remount checks. New tray/nest/lid geometry is explicitly not comparable with bare-chamber empty. |
| 21 Nov, post-food `122331_scan_quick` | h12/h13/h14 O **35.2/14.8/2.2**, dark about −168; hum **0.903 mV** | Weak h14 persisted before the recorded electronics/remount state. O is a legacy corrected estimate, not a calibrated amplitude. |
| 21 Nov 13:36–13:42 EST | `HANDHELD_INGAAS_2M_RF.json`, then `INGAAS_REMOUNT_DEPTH_CHECK.json`: reported 2 MΩ, deeper remount after drilling; door/ambient state changed | Rf was changed by this time. No isolated before/after experiment exists. |
| Handheld → mounted in those records | h8 **7909→41**, h9 **16890→−4**, h12 **4107→−15**, h13 **862→9**, h14 **1057→22**, h15 **679→−28** | Detector/front-end/source combinations can produce large responses. Geometry matters, but ratios are not collection efficiencies because distance, mount, door and illumination changed. |
| 23 Nov, Q00 → Q23 | 60 Hz amplitude **6.351→9.475 mV**; T03.2 approximately 37 counts; mounted SWIR near zero | Worse raw periodic pickup/current mounted performance is real. Attribution to one physical modification is not established. |

The drilled hole being filled and LED tops remaining incompletely sealed are reported physical facts, not controlled comparisons. There is no measured ambient on/off contrast here establishing their contribution. The split light cover is **designed but not printed/fitted** for this assessment. It may help ambient exclusion; neither offset removal, hum removal nor SWIR recovery can be credited to it in advance.

## 6. Mechanics and scanning

**Verdict: partly works for managed motion over the common tracked range; unknown for full-travel mechanical reliability.**

| Evidence | Actual result | Limit |
|---|---|---|
| H23 T09.1 | Unarmed/wrong-token moves refused; ARM about 60 s; expired moves refused | Demonstrates command authorization. |
| T09.2 | Each motor's ±64-half-step command completes and counter returns | All four operator “saw it move” checks SKIP: not watched. Counter agreement is not measured displacement/direction. |
| T09.3 | STOP response **1.80 ms**, 46/2048 commanded steps before stopping; counter then frozen | Good normal-operation response, not a firmware-hang bound or independent physical stopping measurement. |
| T09.4 | InGaAs σ **38.67** rest / **37.58** moving, ratio 0.972 | The small tested move did not add appreciably to already high noise. |
| Q23 | COMPLETE, **25 min 29 s**, nine down/eight up sampled heights, 20 managed moves; no unexpected boots or recorded unlevel event | Command/tracker consistency, not an encoder or independent level measurement. |
| Q23 return and span | Start/end `[−16384,−16384]`; sampled common range **−16384 to −286884** half-steps | Does not demonstrate M2's longer marked range to −429461. Configured screw-model millimetres are not measured sample gaps. |
| Q23 mechanical findings | Backlash **SKIP**: fitted −35503 ±6339 half-steps, resolution criterion ≤300; repeatability **SKIP**, no repeated reference visits | Neither finding is a mechanical PASS; the large fitted shift is not a validated physical backlash measurement. |

**The “two sides not level” refusal is not a tilt measurement.** The tracked bottoms are M1/right **−286884** and M2/left **−429461**. H23 T09.6/.7 refuse while printing equal current positions, **−18496/−18496**. `_start_at_bottom` in [`t09_motors.py`](../../software/host/src/lio/suite/checks/t09_motors.py) compares each side's distance to its own bottom mark. Those distances differ by **142577 half-steps** even with equal current counters. The catalogue refuses that both-bottoms operation; the quick scanner instead uses the conservative common bottom. Therefore the refusal and successful quick scan are compatible.

There is no evidence justifying moving one side by that difference, rebasing marks to make a test pass, or extending travel. Physical level, safe marks and clearance must be verified by the owner before such a change. [`stage.py`](../../software/host/src/lio/stage.py) tracks commanded movement across firmware resets; unseen manual/external moves and missed steps are not independently sensed. No home/limit switches are reported.

**Rerun recommendation:** do not repeat a broad/full scan merely to seek a different optical verdict. A short fixed-position, fixed-N experiment is more useful for a defined noise/path question. Another quick scan can map response after a controlled, authorized change; a full/repeatability scan becomes useful when physical marks/level/clearance are verified and its repeated heights answer a specific mechanical or measurement question. More heights cannot create missing SWIR or independent confirmation of a noise-selected maximum.

## 7. Safety and exposure: protection versus an actual bound

**Verdict: partly works.** The owner-approved mode is explicitly `timing.real_port_admission: cooperative_unproven_acknowledged` in [`lio_hw.yaml`](../../software/config/lio_hw.yaml). This is an admission policy, not a physical proof. Original current-rig **M1 remains blocked** because a finite firmware-hang exposure bound is absent.

| Layer | Live evidence | What remains unproven / offline-only |
|---|---|---|
| Reset/reopen and normal idle | H23 T10.1 reports CH/mask/CE/armed all zero after reset and reopen, with dark readings | No independent current/scope trace for all reset/brownout states. |
| Comms-loss and arm expiry | T10.3 `FAILSAFE reason=comms idle_ms=10000`, all-off reported; T10.5 arm expires | This test does not leave an LED on or inject a dead firmware CPU. |
| Invalid multi-channel operations | All seven current T10.4 cases refused **by the host before write** | Latest cases do not exercise firmware CE rejection. Historical H20 has seven firmware ERR3/exactly-one-channel rejections, CE low. |
| Normal cooperative LED cutoff | **Historical H20** T10.2: rail A/h3 WDT event 300 ms, dark after **314.148 ms**; B/h13 300 ms, dark after **306.612 ms** | Normal serviced cutoff was observed historically. No fatal-hang bound follows. Latest T10.2 is SKIP before transmission: A default 2000 ms and B/h9 default 5000 ms exceed applicable 1000 ms budgets. |
| Motion/light interlock | Q23 closing `light_while_moving: PASS`; `single_channel: SKIP`, host refused | Aggregate interlocks PASS means no failed checked condition; it does not mean every firmware check executed. |
| Managed duty accounting | H23 60 s window, A1000/B5000/h9 1000 ms; **8 waits /349.044 s**, `over_budget=[]`. Q23 **3 waits /175.41 s** | Bookkeeping is not independent LED-edge, irradiance, current or LED-survival metrology. |
| Persistent uncertain recovery | P1 refuses emission under conservative cooldown; resumption retains booked cost. P2 retains **1104 ms reserved /1008 actual /0 uncertain** | Fatal kills during light, reboot/clock faults, fsync failures and contradictory OFF states have fake-transport tests, not corresponding current live demonstrations. |
| One managed owner | Current code takes advisory `DeviceLock` before journal load/serial/WAKE; maintained caller tests exercise failure cleanup | No fresh live two-process/alias contest here. `SerialTransport.open` does not request OS-exclusive serial mode; unrelated Serial Monitor/legacy clients are not excluded by the advisory LIO lock. |
| Firmware hang | Board `hw_wdt=0`; [`safety.cpp`](../../software/firmware/lio_firmware/safety.cpp) calls cutoff/comms services from the executing loop | **No proven finite on-time bound if that loop hangs.** Normal-operation milliseconds cannot be promoted into an invented hang margin. |

Current host code also verifies watchdog ACK/readback, retains uncertain charges after unsuccessful OFF, and gates supported raw/typed emitting paths. The focused tests below support these software paths. They do not prove all physical failure behavior.

Current-run provenance does not consistently display this distinction: suite results contain `exposure_bound=cooperative_unproven`, but the Q23/P1/P2 `scan.json` records do not contain that field. Q23 retains `hw_wdt=0`, so the limitation is recoverable, but acceptance's general “runs record it” claim is too broad. Meter-current, physical LED walk and lid/ambient bench checks were not run in this session. A rolling time quota is not confirmation of each emitter's safe instantaneous current.

## 8. Data integrity and reproducibility

**Verdict: partly works.** The saved archives checked here are internally intact; end-to-end semantic completeness and exact physical reconstruction are not fully established.

| Check through current production callers | Result | Meaning |
|---|---|---|
| `ScanStore.open` + `verify_store_seal` on Q23, P1, P2 | **All three PASS** | Existing archived raw/terminal bytes match their recorded seals. Not proof of optical truth or correct physical metadata. |
| Both archived D23 qualified products against source cube/scan/NPZ hashes | **PASS** | Those products bind to these source bytes and retain unknown coupling. |
| Actual saved analyse, audit, report and numerical/heatmap/curve views | **Works**; original sources read only, new output outside them; source hashes unchanged | Useful offline inspection and generation are supported. Mutation and adverse-resume probes used copies. This audit did not rewrite historical analysis/report/raw data. |
| Append bytes to copied Q23 NPZ, then actual derived report | **Refused**, `source-changed: stream/npz hash mismatch` | Good source-mutation detection through a real consumer. |
| Q23 row identities | **Gap:** all 764 rows have blank operation/reading/block/attempt/condition/setting/segment/position-instance fields | The reader supports identities; the height writer did not populate them. Legacy height/phase/direction/rep remain usable, but complete new traceability is absent. |
| P1/P2 row identities | **Present:** 6/12 distinct readings respectively; P2 steps 0–11 contiguous, 24 detector rows, one position instance | Ordinary recorded stationary resume preserves these identities; two detector rows are one reading, not two independent replicates. |
| Frozen acquisition facts | **Incomplete:** config snapshot is path+hash, channel map is hole list/source; mux map empty, configured rate null, rail-current empty; Q23 assembly empty | Corresponding config and human records are still required. Rf is frozen as config-declared 1 MΩ despite owner-reported fitted 2 MΩ. INFO separately records gain 1/rate128/mains60. A seal cannot supply missing facts. |
| Actual protocol resume, adverse copied records | **Fails semantic validation in two probes** described below | Frozen schedule coverage is checked, but full detector/condition/setting completeness is not. |
| Resumed timestamps/history | P2 `t_s` resets **14.165→0.210** across resume while segment remains `stationary`; final `events=[]`, `aborts=[]` | Do not sort resumed observations solely by `t_s`. HTTP logs preserve the abort/pause history that the terminal record omits. |
| Food-profile reuse of Q23 legacy analysis | Correctly quarantined as **legacy-unverified: no source/calibration identity** | A sealed raw scan is not automatically an eligible analysed food-profile object. External stationary products also do not automatically satisfy the old profile recipe's in-run analysis lookup. |

### Resume counterexamples, on copies only

The genuine P2 archive is seal-valid and was not modified. Two copies were put into an INCOMPLETE end-state, representing records requiring resume. One lost a detector row for a completed step; the other had condition/setting identities changed. Both retained all12 step numbers, `completed_step=11`, and the scheduled hole/phase. Their existing seals correctly failed. Actual `resume_protocol`, with a fake MEAS callback and injected clocks held at the archived last values, then **accepted both, made zero MEAS calls, marked COMPLETE, and wrote valid replacement seals**: 23 rows in the missing-detector case, 24 in the changed-condition case. No steps remained to acquire; these probes test semantic revalidation/resealing of an interrupted terminal state, not remaining-step execution or elapsed-time enforcement.

[`acquisition.py`](../../software/host/src/lio/scan/acquisition.py), lines 1364–1385, reduces durable records to sets of `(hole,phase)` per step. This cannot detect a missing detector row, altered setting/condition or some duplicates, and resume does not verify the existing terminal seal before resealing. These probes do not allege corruption of the actual live runs. They refute a general claim that durable records are fully validated against the frozen experiment before promotion to COMPLETE.

### Scientific eligibility and production statistics

| Item | What current evidence/code actually does |
|---|---|
| Unknown coupling | D23 correctly stores **C=null**, model `unidentified`, **UNRESOLVED**. There were no eligible controls. Legacy height reports instead use inferred blind-channel correction; their O values have different meaning. |
| InGaAs physical quantities | Modern quantity/profile gates block physical-current and quantitative optical reuse for unverified A0/unknown required Rf, preserving raw counts and supported ADC arithmetic. This is not consistently applied to legacy height-report findings. |
| Legacy current overclaim | Q23 `elec/ingaas/dark_offset` PASS prints **+41.5 nA (Rf 1 MΩ)** from −332.31 counts. [`analysis/electrical.py`](../../software/host/src/lio/scan/analysis/electrical.py), lines124–149, directly uses config Rf without the new physical-range gate. This is conditional arithmetic, not measured leakage/current. Ground-shift mV/mA also uses unreconciled nominal current. |
| Signed fixed-N results | Present and useful diagnostically. P2 h8 InGaAs 95% interval **27.62..29.38 counts** is a pointwise raw contrast interval, not a qualified optical/current/chemistry interval. Small technical N and process interruptions limit its interpretation. |
| Paired/shared-control/familywise inference | Helper functions exist, but [`derived.py`](../../software/host/src/lio/scan/derived.py) production analysis calls grouping + `block_drive_response`; the paired/shared-control/familywise helpers are not connected there. Tested helper precision is not delivered experimental precision. |
| Selection and h16 predictive value | **A21/A22 remain open.** Qualified shared selection plus new confirmation, and h16 opt-in/grouped held-out evaluation through batch/CLI, are not integrated. The batch tool's old “held-out” distance ablation does not establish predictive benefit on unseen preparations/days. |
| Core acquisition gain | Archived core reads gain 1; no M7 gain experiment establishes an improvement. **M7 stays deferred.** No stop-when-positive qualification or noisy-height maximum should be inferred from fixed-N captures or legacy fitted peaks. |

## 9. Fitness for purpose

| Intended use | Verdict today | Conditions / what must change before a stronger use is supported |
|---|---|---|
| **(a) Commissioning and self-test** | **Partly works; useful now within the recorded cooperative operating mode** | It finds failures, exercises managed commands/refusals, captures diagnostics and can complete a quick scan. Read subresults, not just aggregate PASS. Full commissioning still needs truthful physical observations, verified operating facts, mounted optical/reference checks and mechanical qualification. A finite firmware-hang claim requires a separately established cutoff; the owner's accepted mode does not supply it. |
| **(b) Visible/NIR food profiles, OPT101** | **Partly works for exploratory raw fingerprints; validated identification unknown** | Use a stable current source/geometry/sample epoch, repeat independent preparations/days and references, and predeclare channels/analysis. Flag h1/h9/h10 variability. Verify changes exceed preparation/drift variation on held-out groups before ingredient-identification claims. Repair owner/data workflow defects before relying on resume/automatic batch qualification. |
| **(c) 1450–1650 nm InGaAs food measurement** | **Does not work reliably** | Establish valid front-end operation and reproducible mounted h12–14 optical response, distinguish load-coupled from optical components, and validate precision/references. More averaging alone did not recover missing means. Owner-deferred A0/Rf/current/optical checks remain proposals, not completed prerequisites. |
| **(d) Any quantitative or calibrated claim** | **Does not work as a supported calibrated instrument claim** | Verify physical operating point/transfer, source/current/geometry epochs, suitable standards and references, control compatibility, uncertainty and independent calibration validation. Raw counts and supported ADC-referred mV are legitimate diagnostics; they are not concentration, reflectance or measured input current. |
| **(e) 1850 nm** | **Does not work as primary-1850 chemistry** | Requires appropriate independently verified spectral coverage/source-path characterization, such as an extended-range detector, plus optical/reference calibration. Existing h16 can only be an explicitly unassigned proxy; its predictive usefulness is unknown and needs grouped held-out validation. It must not enter primary-1850 chemistry features. |

The real food record is [`tray_v3/20261120-184450_scan_full`](../../test_results/tray_v3/20261120-184450_scan_full/), sample **LIO-F-00001, Citrucel Orange**, COMPLETE in **34 min 27 s**, 2360 rows. Actual down-pass OPT101 h8/h9/h11 ranges were **700–2169 /701–2009 /994–2365 counts**. That demonstrates acquisition from one labelled food/setup, not identification accuracy. Its absolute sample-response findings are SKIP, T06 is FAIL, and its global FUNCTIONAL label is therefore not an optical qualification. It predates source/current changes, so it is not a present-day amplitude guarantee.

## 10. Usability for the owner

**Verdict: partly works.** The owner can run useful diagnostics, but must understand stage bookkeeping, source epochs, journal/cooldown behavior and several distinctions the UI currently obscures.

| Operator-facing problem | Concrete evidence / consequence |
|---|---|
| One start confirmation is useful but must be truthful | `PreflightOperator` supports suite/height setup facts once, then runs unattended. Watching motor direction, meter readings and opening the lid remain SKIP in these unattended runs rather than invented answers; explicit bench mode is separate. Protocol optical interventions are separate fresh occurrence confirmations, not covered by a generic start checkbox. |
| Browser protocol Resume is broken | `index.html` saved-run Resume always calls **`/api/scan/start`**, the height path. Actual `Session.scan_start` on a copied P2 protocol raises **`KeyError('plan')`**, because protocols store `protocol_plan`. API resume in the archive used the correct protocol endpoint. This was reproduced offline before hardware construction. |
| Browser cannot answer protocol checkpoints | Current HTML has no `/api/scan/protocol/answer`, `occurrence_id` or `pending_prompts` handling. Server/job waits support those concepts, but no corresponding browser answer control was found. P1/P2 had `checkpoint=null`, so their success does not test this workflow. |
| A visible precision setting can have no effect | “Samples per reading” edits `sweep_n`; `Executor._n()` uses `mains_periods` when mains mode is active. Standard latest scans use mains integration, while that setting is not exposed in the same UI. Turning up the visible samples field need not lengthen a lit reading. |
| Runtime estimates omit important costs | Q23 plan **22 min 26 s**, actual **25 min 29 s**, about14% longer; predicted zero duty waits versus **175.41 s** actual. H23 catalogue took **31 min 35 s**. Current diagnostic work is practical on a bench, but expensive to repeat without a question. |
| Refusal and downtime can look like slow acquisition | P1 estimated **0.796 s** acquisition but persisted **614.75 s** elapsed, mainly refused start and later recovery. Polling continued while no scan ran. Pause/abort attempts on that already ended refusal returned400 “no scan is running”; they did not test active controls. |
| Pause is at a safe boundary, not immediate | P2 pause requested at done2; observed held at done3 for >5 s. Abort produced INCOMPLETE; correct API resume completed. One additional reading can finish before the pause takes effect. Heartbeat was supplied by a script, not a tested browser page. |
| A restart can leave old code operating | Invalid170350 run consumed **25 min 32 s** and repeated the old closing error. Acceptance records ignored background SIGINT/new process bind failure. Documented owner procedure is graceful disconnect/OFF/STOP/port release, terminate old server, verify replacement PID/bind. This audit did not restart or contact the dashboard. |
| Some errors suggest unsupported physical diagnoses | “Not level” prints equal counters but compares distances to different bottom marks. Legacy reports infer “wrong LED” from out-of-band counts. Following these literally could cause an unnecessary physical adjustment. |
| COMPLETE/PASS badges are easy to overread | Saved list renders COMPLETE as a passing badge. Current complete scan is NOT FUNCTIONAL; T05.5 PASS has no judged channels. The dashboard twin accumulates latest results across runs, rather than proving all green tiles passed on one current configuration. |
| Protocol and height result displays differ | Standard scan-result uses height `job.result`; protocol completion does not automatically produce the same result presentation. Progress units can also change between planned steps and persisted detector rows. |
| Resume history is not self-contained | P2 terminal metadata loses abort/event history visible in HTTP logs; row times reset. Owner review needs more than the final COMPLETE label. |
| Documentation conflicts with the rig and itself | Root README contains duplicated/truncated fragments and describes fixed-top/moving-platform, single-M6/homing/endstop/OPA381 details alongside the current dual-motor moving head/TL072/no-home-sensor rig. Inventory/map retain older current/channel/board facts. TESTING still says result folders ignored and uses AVR-flash guidance. The current owner must reconcile multiple epochs manually. |

The HTTP archives demonstrate supported endpoint behavior, not complete browser usability. No live browser rendering, current dashboard process state or restart sequence was independently exercised in this audit.

## 11. Implementer claims versus evidence

The latest [caller acceptance](../handoffs/2026-11-23_caller_remediation_acceptance.md) correctly acknowledges optical NOT FUNCTIONAL, A21/A22 open, M7 deferred and no recovered chemistry. Those limits are supported. Its broader closure wording still needs qualification:

| Claim/presentation | Evidence-based assessment |
|---|---|
| New identities / complete provenance are substantially delivered | Stationary caller works; **Q23 all eight new identity fields blank**, physical snapshots incomplete. Reader tests do not qualify every producer. |
| Resume validates durable records against the frozen experiment | It validates hole/phase step coverage, not complete detector/condition/setting identity. Two adverse copied runs were resealed COMPLETE. Actual historical resumes remain valid as recorded. |
| Runs record unproven cooperative exposure mode | Suite does; all three new scan metadata files omit the label. No firmware-hang bound is established anywhere. |
| Current-rig safety tests all passed | Latest T10.2 never emitted; T10.4 is host-side refusal; a T13 interlock is SKIP. Historical normal cooperative cutoff exists, but has a narrower meaning. |
| “Bottoms are not level” | Marks differ; code proves unequal distances to them, not physical tilt. The physical state is unknown. |
| A0/Rf physical quantities correctly gated | Modern consumers gate them, but the latest legacy height report still prints unqualified **41.5 nA with stale1 MΩ**. YAML B45 mA also conflicts with reported≈30 mA. Neither target pot logs nor config entries are measurements. |
| Original M6 Python matrix green | Acceptance itself records **971 passed,1 failed,6 skipped** on the final test revision. The unidentified intermittent HTTP numerical failure remains open; isolated retries, including this audit's pass, do not identify its cause. |
| Project-state/test-results summary is the current single answer | `.agents/project-state.md` still quotes older969/0/6, while `test_results/README.md` mixes earlier a093 independent failures and later acceptance. Both need chronological reading, not blanket reliance. |
| Hum cancelled / blind coupling corrected / h16 wrong emitter | Old `DIAGNOSTIC_SWEEP.md` language exceeds current evidence. Raw hum remains large, qualified coupling remains null, and h16's spectrum is unassigned. |
| Broad software acceptance implies useful chemical readings | False. Tests protect behavior and data handling; they cannot provide missing photons, valid A0 transfer, reference calibration or independent food validation. |

Original milestones remain distinct from current functionality:

| Original milestone | Assessment of connected functionality, not helper presence |
|---|---|
| M0 provenance/units/compatibility | **Partial:** seals/reuse and stationary IDs work; height IDs/snapshots/legacy physical units remain incomplete. |
| M1 ownership/bounded durable exposure | **Partial software protection; current-rig bounded exposure blocked:** finite hang bound absent, OS-exclusive serial unrequested; many managed paths are exercised offline/live. |
| M2 roles/coupling | **Partial:** unknown C and proxy role preserved in qualified products; eligible current controls/joint uncertainty absent. |
| M3 fixed-N estimators | **Partial:** signed pointwise contrasts work; paired/shared-control/familywise production inference disconnected. |
| M4 stationary execution/allocation | **Partial:** equal fixed capture, permanent costs and normal API resume demonstrated; adverse resume semantics and complete owner UI fail, measured allocation benefit unestablished. |
| M5 shared selection + fresh confirmation | **Does not work as the delivered qualified workflow:** A21 open. |
| M6 CLI/dashboard/report/profile/release | **Partial:** useful saved-data paths and focused tests pass; browser gaps, A22, packaging/extras scope and intermittent full-suite failure remain. |
| M7 | **Deferred**, not a source of current measurement capability. |

## 12. Five actions most likely to make LIO useful

These are ranked proposals, not authorization or work performed. Expected effects are hypotheses with explicit tests; none promises a numerical SNR improvement.

| Rank | Action and type | Expected useful effect | Verification test |
|---|---|---|---|
| **1** | Establish a small **current-epoch OPT101 food/reference pilot** at one reproducible position, with fixed acquisition and independent preparations. Bench collection requires owner authorization. | Uses the detector that currently produces clear signals and determines whether differences survive real sample/placement variation. Avoids spending25–35min per exploratory full scan. | Predeclare channels/settings and fixed N; acquire blanks/references and independently prepared samples across sessions. Compare between-food effects against within-food/preparation drift with held-out preparation/day groups. Flag h1/h9/h10 and retain negatives/missingness. Success is repeatable discrimination in that experiment, not a global ingredient claim. |
| **2** | Make the existing owner capture/review workflow trustworthy: **specific resume/UI/identity/quantity-label defects**, plus one current operating guide. Software work proposed only. | Prevents failed browser resumes, unanswered checkpoints, incomplete records becoming “complete,” misleading current labels and wasted runs on stale processes. | On copies/simulator, missing detector/changed condition/invalid seal must refuse; new height rows carry expected IDs/facts; browser starts, answers, pauses, aborts and resumes the correct run type; supported settings change actual plans. Preserve original bytes; reproduce/log the intermittent HTTP failure rather than rerun it away. |
| **3** | Isolate the **InGaAs operating point and interference** with the deferred A0/Rf/current checks and controlled power/ambient comparisons. Physical proposals remain owner-deferred. | Separates invalid transfer/offset from periodic pickup and establishes which raw quantities can be interpreted. | Record measured facts and assembly epoch; repeat the same n64 dark and raw-stream fit under one changed factor at a time, alongside fixed-N integrated dark/lit. Check A0 against the actual ADC/front-end operating requirements. T03.2≤20 is one criterion, not proof of optical throughput or chemical calibration. |
| **4** | Test **mounted SWIR optical path and ambient sealing** without raising drive; use the cover only after fit/clearance checks. Physical proposal. | May recover collection if aim/path/ambient is responsible, or localize missing response to source versus mount/front-end. | Hold source/current/position fixed; compare truthful load-preserving optical-block/reference conditions and permitted ambient-on/off contrasts for h8/9/12–15. Change one geometry/seal factor at a time, keep all repeats, and verify reproducible target-dependent response. A cover's benefit is whatever the comparison measures. |
| **5** | Qualify **extended-scan mechanics and the actual operating envelope** before relying on long unattended runs. Physical/safety proposal. | Establishes safe usable travel and makes the distinction between cooperative operation and a proven independent cutoff explicit. | Verify physical level, original safe endpoint marks and cover/head clearance without automatic rebase/catch-up; then observe authorized direction/full-range and repeated-reference tests. Reconcile meter-backed current limits; observe an admitted nominal cutoff on each rail. Any finite firmware-hang claim additionally needs separately engineered and tested independent cutoff evidence. |

A21/A22 and connected statistics matter before formal optimized/validated food claims. They do not replace these current physical and owner-workflow bottlenecks. The owner has deferred A0/Rf/ammeter/optical/reference work; this report neither performs it nor treats it as confirmed.

## 13. Audit method, commands and limitations

### Source acquisition and immutability

The requested direct acquisition was attempted from `/workspace/scratch/98bb007a88b1`:

```bash
git clone --branch main --single-branch --no-tags https://github.com/Brandonio-c/LIO.git functionality_audit_20261123/repo
```

It failed with **403: “Calls to this URL are not allowed.”** No successful native clone or pull is claimed. The GitHub connector then resolved `main` to `92bee4a2b3f702b3ba6c294e5ef4d9af716729e4`; selected files were materialized from that pinned tree. All **780 blobs /30,093,954 bytes** were checked against expected Git blob SHA-1 and size, with SHA-256 recorded. Coverage includes all host source/tests, firmware/config, required docs and dated raw evidence used here, including six large JSON/HTTP files. It is a verified research snapshot, not a `.git` checkout or a claim to mirror every unrelated corpus.

Before/after verification found **zero changes to all780 selected blobs**; local `test_results/stage_position.json` remained absent. Manifest: `functionality_audit_20261123/retrieval/verified_manifest_before.json`, SHA-256 **`411a2604b758810abe047cd7e76a39a4895ebd5f3dd92d11c1f7b601a146b692`**. Final result: `retrieval/invariance_after.json`. Large-file retrieval has its own blob/size/SHA manifest. Principal sources are also individually hashed in the measurement, safety, mechanics and integrity extracts. All mutation/resume/report-generation probes used separate copies or derived-output folders.

### Commands actually executed

The measurement commands ran from `/workspace/scratch/98bb007a88b1/functionality_audit_20261123`:

```bash
python measurement/inspect_sources.py
python measurement/analyse_measurement.py
python measurement/check_streams.py
python measurement/write_findings.py
```

The following commands ran from `/workspace/scratch/98bb007a88b1`:

```bash
python functionality_audit_20261123/measurement/audit_history.py
python functionality_audit_20261123/safety/extract_safety.py
python functionality_audit_20261123/integrity/check_archives.py
python functionality_audit_20261123/integrity/probe_saved_callers.py
python functionality_audit_20261123/mechanics_usability/protocol_timeline.py > functionality_audit_20261123/mechanics_usability/protocol_timeline.txt
node functionality_audit_20261123/mechanics_usability/probe_ui_wiring.js > functionality_audit_20261123/mechanics_usability/ui_wiring_probe.json
PYTHONPATH=functionality_audit_20261123/repo/software/host/src:/workspace/scratch/98bb007a88b1/fullpass_audit_20261123/checks/installed:/workspace/scratch/98bb007a88b1/fullpass_audit_20261123/tooling/site-packages:/workspace/scratch/98bb007a88b1/qa_remediation_20261123/qa_tooling/site-packages python functionality_audit_20261123/mechanics_usability/probe_protocol_ui_resume.py > functionality_audit_20261123/mechanics_usability/protocol_ui_resume_probe.json
python functionality_audit_20261123/integrity/run_focused_pytest.py tests/unit/test_caller_regressions_device.py tests/unit/test_caller_regressions_saved.py tests/unit/test_caller_regressions_workflow.py tests/unit/test_caller_regressions_science.py tests/unit/test_scan_protocol_cli.py tests/unit/test_fullpass_counterexamples.py::test_golden_dashboard_http_plan_numerical_answer --lio-sim -q > functionality_audit_20261123/integrity/focused_pytest.log 2>&1
python functionality_audit_20261123/integrity/run_focused_pytest.py tests/unit/test_caller_regressions_device.py tests/unit/test_caller_regressions_saved.py tests/unit/test_caller_regressions_workflow.py tests/unit/test_caller_regressions_science.py tests/unit/test_scan_protocol_cli.py tests/unit/test_fullpass_counterexamples.py::test_golden_dashboard_http_plan_numerical_answer --lio-sim --collect-only -q > functionality_audit_20261123/integrity/focused_collect.log 2>&1
python functionality_audit_20261123/verify_snapshot.py
```

The focused runner changes directory to the new snapshot's `software/host`, asserts the imported LIO path belongs to this revision, and uses genuine available dependencies. It blocks physical serial and historical writes, isolates synthetic state, and permits HTTP only to its own newly bound ephemeral localhost test servers. Its appended pytest flags are `-p no:cacheprovider -p pytest_timeout -p _hypothesis_pytestplugin`.

Read-only `rg`, `cat`, `sed`, JSON/CSV/gzip/NPZ inspection and source reads supplemented these scripts. Supporting scripts, exact selectors, input hashes, extraction results and command notes are under `functionality_audit_20261123/{measurement,safety,integrity,mechanics_usability}/`. Initial probe attempts that failed on missing Jinja2 or the mistaken import name `Device` were corrected using genuine dependencies/the actual `LIODevice` name; those setup failures were not counted as product defects. Manufacturer datasheets were retrieved separately for spectral bounds, not used as evidence of installed-rig behavior.

| Verification scope | Actual result / limit |
|---|---|
| Fresh focused maintained tests | **63 passed,0 failed,0 skipped**,10.38s:59 caller regressions,3 protocol-CLI tests,1 golden HTTP numerical test. Exact collection: device29/saved13/workflow11/science6. Serial guard calls0; historical-write attempts0. |
| Audit runtime | **Python3.12.14, pytest8.4.2, NumPy2.3.5, SciPy1.17.0, pyserial3.5.** Acquisition archive runtime differs: Python3.12.11. |
| Full release suite | Not rerun here. Recorded earlier969/0/6 differs from final **971/1/6**; final intermittent `test_golden_dashboard_http_plan_numerical_answer` remains unexplained. Its passing once here is not closure. |
| Python3.10 / precision | Not independently rerun. Recorded960/0/15 lacked optional packages including SciPy, so those precision tests did not execute there. |
| Ruff/mypy/coverage/installed wheels | Prior acceptance results read, not independently rerun for this functionality assessment. No new whole-release-green claim. |
| Simulator isolation | Known broader simulator suite writes local stage-position state. Focused tests used a write guard and did not do so; the broader gap remains. |
| Exact live executable identity | Limited: `173106_host` environment records **2212d1b… dirty=true**, while acceptance describes the restarted f78c6b6 process. Q23 records package0.2.0/Python3.12.11, not exact source bytes. D23 product identity records clean **7f080ea…**. These facts do not independently prove a pristine acquisition checkout or loaded process SHA. |
| Physical and operator checks | No new hardware connection, serial open, POWER WAKE, light, motion, firmware/wiring/current change, stage edit, dashboard restart or operator confirmation. No new walk/meter/lid/optical/reference test. Private bench-Mac chat/file URLs were unavailable; only committed records and supplied owner facts were used. |
| Publication during the audit | Report created locally under `docs/research`; **no GitHub push** performed as part of that audit. Subsequent documentation publication was separately authorized; see the publication note above. |

**No measured SNR improvement, recovered SWIR food chemistry or 1850 nm chemistry is justified by this software alone.**
