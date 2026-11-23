# LIO V3: extracting more information from the existing sensors

> Research evidence snapshot, not an implementation release. The current implementation specification is [SENSOR_READINGS_UPGRADE_PLAN.md](../SENSOR_READINGS_UPGRADE_PLAN.md).

Research assessment, 23 November 2026. Repository snapshot: [`Brandonio-c/LIO`, main `138a9635df7538748b5dda1fddee88db5067b8fb`](https://github.com/Brandonio-c/LIO/tree/138a9635df7538748b5dda1fddee88db5067b8fb).

The updated sensor-information handoff and `test_results/README.md` were read in full. This assessment uses the three requested scan metadata files, saved analyses, reports and raw compressed cubes (764 rows each; 2,292 rows total), all six requested tray-v3 bench JSONs, current configuration, optical/electrical analysis, acquisition implementation and protocol. Historical results are now tracked on main; the earlier availability limitation is superseded. Direct Git cloning was blocked by the execution environment; the exact main snapshot was retrieved through the GitHub connection instead. Nothing was run on the instrument. No firmware, product code, configuration, wiring, motor state or Git remote was changed.

## Decision

**Yes: software can extract more useful information, particularly more defensible weak-signal estimates, better diagnostics and more efficient repeat acquisition. It cannot create a calibrated 1850 nm measurement on OPT101.**

The order should be:

1. Correct measurement provenance and test the electrical-coupling assumptions offline.
2. Quantify repeatability and uncertainty using measurements with the same integration settings as the intended signal estimator.
3. Under a later bench authorization, distinguish optical return from current-synchronous pickup with unchanged-load optical controls.
4. Spend acquisition time on optically verified weak channels and independently selected safe heights.
5. Treat h16 OPT101 as a separate, spectrally unassigned diagnostic candidate; establish any sample information through controlled comparisons and held-out ablation.

H12 is a more promising immediate software-assisted recovery target than h13/h14. H13/h14 presently show little resolved height-dependent return. The existing integration experiment does not measure its claimed SNR outcome, and a blind-control correction alone does not restore those channels.

## 1. What the recorded data actually establishes

### 1.1 Historical fitted amplitudes

The following are saved **model-derived O values in ADC counts**, not raw lit-minus-dark readings, radiant power, calibrated reflectance or chemical concentrations. Current code defines O as the maximum smoothed down-pass response minus its estimated rail coupling C. All three scans recorded ADS1115 gain 1. Different targets, mounting/feedback-resistor epochs, current records and stage ranges prevent interpreting these columns as a controlled before/after sensitivity comparison.

| Detector / hole | Nov 19 black cup | Nov 20 empty | Nov 23 empty |
| --- | ---: | ---: | ---: |
| InGaAs h8 / 850 | 26.8 | 27.0 | 47.0 |
| InGaAs h9 / 940 | 25.6 | 20.4 | 45.8 |
| InGaAs h12 / 1450 | 75.5 | 54.7 | 12.3 |
| InGaAs h13 / 1550 | 24.0 | 19.8 | -10.6 |
| InGaAs h14 / 1650 | 27.3 | 14.0 | -13.8 |
| InGaAs h15 / 1760 | 11.1 | 5.3 | -8.7 |
| InGaAs h16 / nominal 1850 | 19.6 | 24.7 | 43.8 |
| OPT101 h16 / nominal 1850 | 411.3 | 724.5 | 389.0 |

Sources: each run's `analysis.json` and `cube.csv.gz`: [Nov 19](https://github.com/Brandonio-c/LIO/tree/138a9635df7538748b5dda1fddee88db5067b8fb/test_results/20261119-152512_scan_quick), [Nov 20](https://github.com/Brandonio-c/LIO/tree/138a9635df7538748b5dda1fddee88db5067b8fb/test_results/20261120-012619_scan_quick), [Nov 23](https://github.com/Brandonio-c/LIO/tree/138a9635df7538748b5dda1fddee88db5067b8fb/test_results/20261123-003133_scan_quick).

Important qualifications:

- Nov 19 is **black_cup**, not empty. Its saved analysis says FUNCTIONAL, while its report says NOT FUNCTIONAL. The derived artifacts disagree in verdict policy; they must not be silently treated as one authoritative qualification. Its raw h12 down-pass values span -88 to +134 counts, with a maximum matched up/down difference of 181 counts. Absolute h12–h14 response findings are SKIP for that sample type. A FUNCTIONAL label therefore does not establish a clean SWIR spectrum.
- Nov 20 empty is the stronger relevant reference: h12 and h13 response PASS, h14 WARN. H13's raw down-pass range is only 27–31 counts; its nominal PASS is not independent proof of a large sample-mediated modulation.
- Nov 23 h8/h9 remain responsive: a blanket “InGaAs dead” diagnosis is contradicted. Its h12–h14 response and throughput findings FAIL. Its InGaAs SNR PASS of 22.4 dB includes **only h8/h9**, excluding the failed channels.
- All three scans used 60 Hz mains rejection, two periods and 8 ms optical settling. Their configurations differ. Planned stage coordinates span approximately -102.54 to -1 mm, -79.54 to -4 mm, and -70.04 to -4 mm respectively. Those are travel coordinates below separately marked tops, not verified common detector-to-sample gaps. Nov 23 also records unequal per-motor bottom limits. Do not infer actual tilt or perform geometric normalization from those counters alone.

### 1.2 H16 is reproducible; its wavelength and path remain unidentified

Nov 23 OPT101 h16 raw down-pass nets, ordered from the lowest to highest measured head position, are:

`391, 360, 329, 301, 280, 258, 238, 228, 217` counts.

At the eight heights present in both passes, median absolute up/down difference is 1 count; the maximum is 5 counts. Saved modulation is 0.447. This is compelling evidence of a repeatable **height-associated response**, much larger than random scatter in those paired visits. Two passes are not independent replicate trials or proof of optical causation. Cable geometry, drive pickup and sample/chamber paths still need controlled separation.

The fitted h16 amplitudes and WARNs predate the present NOT FUNCTIONAL state. The current warning cannot be used to conclude that the owner has just installed a wrong LED. Equally, a repeatable residual cannot prove the nominal 1850 nm die is healthy or identify its emission spectrum.

### 1.3 Coupling subtraction changes h12, but does not recover h13/h14

Recomputing the current code's raw-row medians while leaving h16 out gives:

| InGaAs rail-B estimated C | Nov 19 | Nov 20 | Nov 23 |
| --- | ---: | ---: | ---: |
| Current pool: h10, h11, h16 | 7.0 | 11.0 | 16.0 |
| Pool without h16: h10, h11 | 4.5 | 5.5 | 10.0 |

For Nov 23, that sensitivity change alone moves h12 O from 12.3 to 18.3 counts, h13 from -10.6 to -4.6, and h14 from -13.8 to -7.8. H12 is borderline under the current provisional detection floor, 13.96 counts. H13/h14 remain unresolved under this alternative.

This is a **sensitivity calculation**, not a calibrated corrected C: white/pink h10/h11 are themselves unvalidated optical controls. Removing all three leaves rail-B C unidentified, not zero. Conversely, OPT101's rail-B median changes only 2.0 to 1.5 counts when h16 is excluded; the strong h16 signal is not substantially driving that particular median.

The latest InGaAs h12 down-pass raw nets are 16–28 counts and show a small repeatable height trend; h13 is 2–6 and h14 is -3–3. These observations support concentrating recovery experiments on h12 first, while preserving signed values and uncertainty for h13/h14.

### 1.4 The integration experiment is not an SNR comparison

[`INGAAS_BOOST_INTEGRATION_CHECK.json`](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/test_results/tray_v3/INGAAS_BOOST_INTEGRATION_CHECK.json) compares:

- Short: settle 8 ms, n=4 ordinary conversions, mains rejection off, reported LED on-time 78 ms.
- Long: settle 100 ms, n=16 whole 60 Hz periods, mains rejection on, reported on-time 640 ms.
- Three repetitions are declared, but their individual values/variances are not saved in this file.

| InGaAs hole | Short saved net | Long saved net |
| --- | ---: | ---: |
| 8 | 29 | 30 |
| 9 | -20 | -15 |
| 12 | -31 | -31 |
| 13 | -10 | -7 |
| 14 | -16 | -21 |
| 15 | -53 | -52 |
| 16 | -10 | -9 |

The extra on-time did not reveal a large positive mounted return. **Similar averages are not evidence that averaging failed to improve precision:** averaging normally changes uncertainty, not the expected mean. Three acquisition variables changed together, and no repeat variance was retained. The observed SNR benefit, if any, cannot be recovered from this summary. The recommendation text “need aim or current” is an interpretation, not evidence supporting higher current.

### 1.5 Mounted/handheld and current records

The [remount check](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/test_results/tray_v3/INGAAS_REMOUNT_DEPTH_CHECK.json) reports, at 2 MΩ, handheld nets of 4,107/862/1,057 counts on h12/h13/h14 versus mounted -15/9/22. H8/h9 handheld responses are 7,909/16,890. This supports a serious collection-path/load/measurement-state problem, not global detector death. Direct handheld illumination and mounted sample/chamber return are different experiments; their ratio is not calibrated throughput. The large handheld h16 reading likewise does not identify 1850 nm.

The [replacement sweep](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/test_results/tray_v3/LED_REPLACE_SWEEP.json) and [confirmation sweep](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/test_results/tray_v3/LED_CONFIRM_SWEEP.json) document visible-channel recovery and persistent weak SWIR. The latter records repeated visible returns, not calibrated source powers.

Both [DRIVE_TUNE_A](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/test_results/tray_v3/DRIVE_TUNE_A.json) and [DRIVE_TUNE_B](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/test_results/tray_v3/DRIVE_TUNE_B.json) have empty current-reading lists and `accepted_ma: null`. Optical traces and target-current fields do not establish final measured current. Record the owner's approximately 30 mA setup statement as such, separately from the YAML's nominal 30/45 mA and actual meter readings when available.

## 2. Physics and information bounds

A suitable working model is

`net(detector, hole, height, time) = gain × integral[detector_response(λ) × actual_LED_spectrum(λ,time) × optical_path(λ,height) × target_response(λ,height)] dλ + current-synchronous electrical term + residual drift/noise`.

This is a proposed inference model, not an already identified decomposition. Unknown secondary emission belongs in the actual spectrum. Direct chamber leakage may bypass the target. Dark subtraction does not necessarily remove the electrical term because LED current changes supplies, grounds and pickup.

The [OPT101 datasheet](https://www.ti.com/lit/ds/symlink/opt101.pdf) supports visible/NIR linear detection, with the silicon long-wave edge near 1.1 µm. It does not specify useful linear 1850 nm detection. The exact [MTPD1346D-100 datasheet](https://specs.marktechopto.com/pdf/products/datasheet/MTPD1346D-100.pdf) specifies **600–1750 nm**, whereas the repository uses 800–1750. That discrepancy must be resolved against the actual installed unit; red/broadband sources cannot automatically be called blind. Manufacturer range limits do not establish strong sensitivity at every edge wavelength.

| Hole / nominal source | OPT101 information physically available | InGaAs information physically available |
| --- | --- | --- |
| 1–4: 395, 405, blue ~465, green ~525 | Primary-band weighted optical return | No established useful primary-band channel; verify unwanted source tails before using as a pure electrical control |
| 5: yellow ~590 | Primary-band return | Near the stated lower sensitivity boundary; source tail needs checking |
| 6: orange ~605 | Primary-band return | Possible lower-edge optical contribution; not guaranteed blind |
| 7: red ~630 | Primary-band return | Possible genuine optical contribution; not guaranteed blind |
| 8: 850 | Primary-band return | Primary-band return |
| 9: 940 | Primary-band return | Primary-band return |
| 10: white | Broadband weighted return, not monochromatic 450 nm | Red/NIR source tails may contribute; unknown without controls/spectrum |
| 11: pink | Broadband weighted return, not monochromatic 450 nm | Red/NIR source tails may contribute; unknown without controls/spectrum |
| 12: 1450 | Primary band unavailable; residual needs separate attribution | Primary-band return physically possible |
| 13: 1550 | Primary band unavailable; residual needs separate attribution | Primary-band return physically possible |
| 14: 1650 | Primary band unavailable; residual needs separate attribution | Primary-band return physically possible |
| 15: nominal 1760 | No useful specified primary-band response | LED short-wave wing may overlap the detector; cutoff-weighted measurement, not calibrated monochromatic 1760 nm |
| 16: nominal 1850 | Unassigned shorter-band optical contribution or electrical artifact; not primary 1850 reflectance | Short-wave emission tail/unwanted shorter emission could register; no established primary 1850 channel |

Electrical pickup is possible in every row. The installed 1850 emitter's manufacturer/SKU and measured spectrum were not established from the supplied inventory. The owner's belief that a real 1850 part is fitted is compatible with an unexplained OPT101 response; neither establishes its physical mechanism.

Ordinary one-photon fluorescence does not turn 1850 nm photons into higher-energy visible photons without additional energy. Package fluorescence, parasitic electroluminescence and special upconversion are different hypotheses; none is demonstrated here. Do not describe visible glow as an established common property of this particular emitter.

Each detector supplies a spectral integral, not a resolved spectrum. Additional heights can add geometric/scattering information or repeat precision. If the height kernel is separable, they mostly remeasure the same spectral amplitude. They do not create new wavelengths or make an unknown sideband a nominal-1850 absorption band.

## 3. Software findings and ranked opportunities

### Priority 1: separate optical capability, electrical-control eligibility and diagnostic policy

[`electrical.py`, lines 31–76](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/software/host/src/lio/scan/analysis/electrical.py#L31) chooses blind controls from nominal wavelength, configured detector limits and `expect: none`. It then takes one median per rail across non-P1/P4 readings. OPT101 rail-A C is inferred from rail B using the nominal current ratio. CE_ONLY is recorded separately; it is not a load-matched C anchor.

Make candidate controls explicit, independently validated and versioned. Perform leave-one-hole-out, per-height/per-direction and load-sensitivity analyses first. Propagate uncertainty when a rail lacks an identified C. A robust median can tolerate contamination; the numerical sensitivity above is more informative than asserting that all current results are corrupted.

Keep h16 labeled **drive-synchronous, spectrally unassigned response**. Add a separate diagnostic/proxy role only after optical controls; distinguish it from nominal primary wavelength eligibility. The [current optics branch](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/software/host/src/lio/scan/analysis/optics.py#L164) calls sufficient amplitude/modulation optical and suggests a wrong LED without a spectral test. Revise that causal language.

A one-line `expect: weak` change is not a proper implementation: it removes h16 from the blind/plausibility branch while the normal response/throughput/optimum paths only process `signal`. A new diagnostic class requires config/schema, analysis, dashboard and profile-mask changes. No such change was implemented in this research.

### Priority 2: estimate uncertainty for the measurement actually being used

[`channel_stats`](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/software/host/src/lio/scan/analysis/optics.py#L81) maximizes a smoothed curve; weak-channel peaks can select noise. [`Cube.curve`](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/software/host/src/lio/scan/analysis/data.py#L137) selects first visits and despikes them. Preserve raw signed points, direction, repeats, flags and processing layers. Use independent confirmation at a prespecified height, or validated weighted/template amplitude fits with explicit nuisance terms and sensitivity intervals. A template must not manufacture a detection from a mismatched geometry.

Current SNR uses residual noise from fast raw hum bursts, not the standard error of the integrated lit-minus-dark estimator. Measure repeat variability under the actual mains-period, settling and load settings. Use timestamp-aware drift/correlation analysis and averaging-time stability curves; stop adding integration when correlated drift dominates. Independent white-noise averaging is an ideal model, not a guaranteed gain on this rig. The [NIST stability handbook](https://www.nist.gov/publications/handbook-frequency-stability-analysis) provides methods; applying them to LIO intensity data remains proposed work.

### Priority 3: targeted, duty-capped acquisition at independently qualified heights

Keep h8/h9 as positive controls and focus added time on h12 first, then h13–h15 when optical controls support them. Compare options at both equal exposure and equal wall time. More time cannot identify an absent optical component or correct coherent load pickup.

Important implementation traps:

- With mains rejection active, [`executor._n`](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/software/host/src/lio/scan/executor.py#L222) uses `mains_periods`; increasing `sweep_n` does not lengthen normal scan readings.
- [Firmware mains integration](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/software/firmware/lio_firmware/adc.cpp#L110) forces 860 SPS internally. Changing the nominal ADC rate does not slow that path. Means are returned rounded to counts.
- Per-hole adaptive N, a target-only repeated stare and multi-cycle lock-in scheduling are not existing CLI flags. They require proposed host work.
- [`fine` placement](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/software/host/src/lio/scan/executor.py#L45) normalizes every detector/hole curve, including blind/noisy responses, and differs from the report's optimum objective. Use a target-specific, uncertainty-qualified objective and independent validation. An endpoint maximum never authorizes extending safe travel.
- [`DutyTracker`](https://github.com/Brandonio-c/LIO/blob/138a9635df7538748b5dda1fddee88db5067b8fb/software/host/src/lio/device.py#L172) permits a single over-budget request after clearing its window. Adaptive collection should explicitly reject pulses exceeding either rolling budget or watchdog. Preserve the stricter h9 limit. Raw-shell loops and session resets must not bypass accumulated exposure accounting.

### Priority 4: useful features without unsupported chemistry

Retain amplitude and shape as separate representations. Use qualified full height curves, matched-height contrasts, repeatability and h8/h9 cross-detector relationships as diagnostics. The detectors are sampled sequentially and view different fields, so their ratio is not a simultaneous source monitor or a calibration transferable to SWIR.

Evaluate whether h16 adds information beyond existing visible/white/pink channels by held-out feature ablation. Group validation by independent preparation, lot/day and acquisition state. Do not let classifier labels encode current, mount, session or target handling. A useful h16 classifier feature would remain empirical, spectrally unassigned information, not 1850 nm chemistry. The existing food-profile stack should consume qualified features and masks rather than receive imputed SWIR detections.

### Priority 5: gain-aware acquisition and synchronous fitting, conditionally

The [ADS1115 datasheet](https://www.ti.com/lit/ds/symlink/ads1115.pdf) distinguishes differential full-scale span from allowed absolute pin voltage. Verify actual A0 voltage before gain experiments: the saved dark values imply about -41.2 mV at gain 1, but a real below-ground input is outside recommended single-ended operation. Dark subtraction cannot establish missing transfer linearity.

The scan store hardcodes 0.125 mV/count. Make actual gain/LSB, Rf, current and calibration epoch persistent before changing gain; physical-unit thresholds and both inputs' dark/lit/transient limits must be checked. More PGA gain does not increase photons or remove analog pickup. Retain signed counts and do not interpret the present 101% headroom report as a valid input-range check.

Phase-sensitive fitting can reject off-reference noise, as described by [SRS](https://www.thinksrs.com/downloads/PDFs/ApplicationNotes/AboutLIAs.pdf). A drive-synchronous electrical artifact survives alongside light. Existing STREAM offers one contiguous LED-on interval, not an arbitrary periodic lock-in waveform; up to 48 samples use the fast buffered path. Repeated timestamped off–on–off blocks are a plausible host extension. Faster deterministic multi-pulse modulation or fractional firmware telemetry needs separate firmware authorization and is not a near-term software-only result here.

## 4. What still needs the physical instrument or additional hardware

- **Existing optical path:** inspect aperture/window clearance, diode recess/depth, detector orientation, LED aim, seating and sample plane. The 1 mm active diameter makes alignment relevant. Verify with unchanged-load blocking before assigning individual LEDs as dead. Do not move motors while a detector is hand-held.
- **Analog/electrical validity:** verify A0 against ADC ground, fitted Rf/Cf, supply rails, grounding, shielding and pickup. The reported ADC-referred hum increased from about 1.29 to 6.35 mV, while the reported gain state also changed. Do not assume all voltage growth is extra photocurrent or all noise is earth-related. Never lift protective earth as a hum remedy.
- **Metadata reconciliation:** the YAML remains 1 MΩ; the bench records 2 MΩ. Current -41.2 mV implies approximately 20.6 nA if 2 MΩ is fitted, versus the report's 41.2 nA using 1 MΩ. This is close to the older approximately 21 nA equivalent offset, so it does not by itself establish a new leak. Preserve historical gain states.
- **Emitter validation:** confirm manufacturer/part, actual optical spectrum, condition and safe current. The drive-tune files do not record an accepted meter current. Do not increase drive current; the owner has already reported visible LED damage near 50 mA. Longer duty is also extra exposure, not free SNR.
- **True 1850 nm work:** requires an established source spectrum, calibrated sensitivity at 1850 nm and adequate sample-path collection. Extended InGaAs is a possible route; a 2.6 µm cutoff is not uniquely required. A suitable detector/TIA must be chosen from a complete noise, geometry and calibration budget. Current hardware can first support better 1450–1650 work without claiming this additional band.

## 5. Explicit no-gos

- No OPT101 h16 feature labeled 1850 nm reflectance, water/fat absorption or recovered SWIR chemistry.
- No assertion that a handheld h16 InGaAs response proves its primary 1850 output or excludes an in-range emission tail.
- No assumption that height dependence proves wavelength, optical origin or sample mediation; no automatic wrong-part conclusion.
- No equal treatment of white/pink channels as monochromatic 450 nm, or unvalidated blind holes as pure electrical controls.
- No clipping negative nets to zero, epsilon-fixing weak reference denominators or logging them into artificial absorbance.
- No dividing unmatched peak amplitudes across changed geometry/gain/current epochs; no silent height extrapolation or peak alignment that removes mechanics.
- No claim that longer integration failed to improve SNR from equal averages without uncertainty data.
- No demodulation claim that current-synchronous electrical pickup is rejected as if it were out-of-band noise.
- No current increase, relaxed duty/watchdog, firmware flashing, motor movement, wiring changes, operator confirmations, code implementation or Git push during this research.

## 6. Concrete next bench protocols — proposals only

**These commands were not executed. They require owner authorization for the relevant bench work.** Use one verified serial owner and the existing environment. A connection can issue POWER WAKE, holding coils without taking steps. Install/remove masks and targets only with LEDs off and motors stopped; remove hands/tools before acquisition. Keep actual safe limits, closed light seal and operator/earth confirmations truthful.

### A. Resolve load versus optical return at a fixed safe position

First verify the A0 operating-voltage concern. Keep current, PGA, Rf, wiring and mount unchanged. Collect stationary blocks in normal state, with a suitably opaque insulated detector mask, with only the h16 optical exit blocked, then restored. Include h8/h9 and weak SWIR controls. Use an electrically similar sham/restoration control where a mask could alter pickup or temperature; visibly black material is not automatically SWIR-opaque.

Use the existing Scan tab's **electrical** mode, with `mains_hz=60`, `mains_periods=2`, `optical_settle_ms=8`, or:

```bash
lio --port "$PORT" scan run --mode electrical --sample empty \
  --set mains_hz=60 --set mains_periods=2 --set optical_settle_ms=8 \
  --out test_results/sensor_information/controls
```

Use `empty` only for an actual empty holder. Annotate each mask/target state truthfully in supported metadata or an adjacent acquisition record. A component that disappears under a load-preserving optical block supports light; one blocked by the h16 exit links to that optical path. Neither determines wavelength. The unblocked–blocked difference inherits uncertainty from both measurements and from any change introduced by the block.

Next compare an empty holder and suitable white/black targets at a matched sample-facing plane. Use actual `white_ptfe`/`black_cup` identities only when those objects are present. Different cup walls and target geometry remain confounders. A reversible target contrast is needed before calling h16 sample-modulated; certified spectral reference data are needed for quantitative reflectance.

### B. Isolate the integration variable and retain repeat variance

At unchanged fixed geometry, compare the command above with `mains_periods=8`, keeping settling at 8 ms and mains rejection at 60 Hz. Use a counterbalanced 2/8/8/2 order; repeat the block for an initial precision pilot. Treat whole runs as blocks, with P1/P4 as linked within-run observations. Save all signed dark/lit/net readings, timestamps, actual exposure and settings. A later settling experiment can independently compare 8 versus 40 or 100 ms at fixed mains periods, rather than changing everything together.

```bash
lio --port "$PORT" scan run --mode electrical --sample empty \
  --set mains_hz=60 --set mains_periods=8 --set optical_settle_ms=8 \
  --out test_results/sensor_information/integration
```

Electrical mode deliberately commands no translation and archives two lit sweeps plus control/dark/hum records. Its height-curve metrics are correctly SKIP. Compare raw P1/P4 block variability, drift, usable signed signal and uncertainty per exposure and wall time; do not compare nonexistent fitted O curves. More independent blocks are needed for narrow confidence intervals.

Prefer a persistent dashboard session, which retains duty history. Fresh standalone CLI invocations reset it; allow the complete configured duty window, currently 60 s, after a session's final LED exposure before another session. Verify actual pulse duration against both limits. Do not use unbounded shell MEAS loops or assume standalone `lio meas --n` enables mains rejection; it normally counts plain conversions.

### C. Qualify geometry only after useful optical return is established

With later motion authorization and verified physical limits, collect matched-state full scans; repeat the reference after target changes to measure drift:

```bash
lio --port "$PORT" scan run --mode full --sample white_ptfe --allow-motion \
  --set mains_hz=60 --set mains_periods=2 \
  --out test_results/sensor_information/geometry
```

Use `empty` and `black_cup` for their actual conditions. Preserve the tray/support/sample plane and acquisition epoch. Use the existing `repeatability` mode if repositioning/backlash needs separate assessment; it moves, and is not a fixed-position stare. Select candidate weak-SWIR heights from scouting data and validate using independent measurements; do not extend travel for an endpoint optimum or assume current `fine` is SWIR-optimal.

### D. Analyse without mixing historical baselines

```bash
lio scan analyse "$RUN" --no-baselines --out test_results/sensor_information
lio scan report "$RUN" --no-baselines --out test_results/sensor_information
```

These commands write derived files into a run; use research copies when preserving committed records. Keep static-repeat analysis separate from height-profile analysis. Preserve configuration/gain identity and report provenance. Do not overwrite old derived artifacts or promote a newly completed but unexplained faulty run as a healthy baseline.

## 7. Evaluation criteria and limits

Expected gains in the matrix are qualitative because no new authorized controlled acquisition has been performed. Distinguish acquisition precision, optical attribution, reproducibility and chemical predictive value. Passing one does not establish the others.

Before accepting h16 as a proxy, require reversible optical-path response, target modulation beyond blank/reseat/drift variability, stable acquisition provenance, and held-out added value beyond existing visible/broadband features. Before accepting weak SWIR quantification, require a resolved signed optical component against an appropriate load-matched control, uncertainty under actual acquisition settings, adequate reference denominator and stable physical geometry. No fixed new detection threshold is claimed as validated.

Primary external evidence used: [OPT101 datasheet](https://www.ti.com/lit/ds/symlink/opt101.pdf); [MTPD1346D-100 datasheet](https://specs.marktechopto.com/pdf/products/datasheet/MTPD1346D-100.pdf); [ADS1115 datasheet, operating conditions and single-ended inputs](https://www.ti.com/lit/ds/symlink/ads1115.pdf); [SRS lock-in application note](https://www.thinksrs.com/downloads/PDFs/ApplicationNotes/AboutLIAs.pdf); [NIST stability-analysis handbook](https://www.nist.gov/publications/handbook-frequency-stability-analysis). Apparatus-specific numbers come from the linked pinned repository files, not those datasheets. Proposed estimators and protocols are recommendations, not implemented or bench-validated results.

## Recommendation matrix

| Idea | Expected gain | Main risk / limitation | Needs bench? | Code/config touched if authorized |
| --- | --- | --- | --- | --- |
| Independent control eligibility; coupling/provenance sensitivity | High interpretability; possible h12 recovery, not new photons | Unvalidated C can still subtract light; no valid B control may remain | No for offline audit; yes for calibration | `lio_hw.yaml`, config schema, `analysis/electrical.py`, scan metadata |
| Matched-estimator uncertainty, signed repeats and held-out quantification | High for defensible weak-signal decisions | Correlated drift, biased peak selection, insufficient independent blocks | No for historical reanalysis; yes for validation | `analysis/data.py`, `optics.py`, report/profile QC |
| Duty-capped target acquisition and SWIR-specific height objective | Conditional precision/throughput improvement | Missing photons, current-synchronous bias, thermal/duty cost | Yes | Scan settings first; proposed `plan.py`, `executor.py`, `device.py` scheduler |
| Separate h16 unassigned optical/proxy feature | Useful QC/scatter channel if validated; chemistry gain unknown | Mistaking a sideband or pickup for primary 1850 | Yes for causal/value validation | Config schema, `optics.py`, dashboard and profile masks |
| Gain-aware PGA optimization | Conditional ADC-resolution benefit | Analog noise/input validity, saturation and wrong unit scaling | Yes | `device.py`, `store.py`, metadata, count/physical thresholds |
| Timestamped off–on–off regression / lock-in-style experiment | Conditional off-reference-noise reduction | Synchronous pickup survives; current STREAM is not periodic lock-in | Yes | Proposed host orchestration; firmware only for capabilities absent today |
| Correct aperture/aim, analog operating range, safe bonding/supply issues | Potentially high restoration of real h12–h14 information | Physical changes require requalification and matched references | Yes | Hardware plus verified configuration/provenance; no higher-current shortcut |
| Detector/source calibration genuinely covering 1850 nm | Enables a real additional spectral band | New noise, geometry, source-spectrum and calibration requirements | Yes; additional hardware | Detector/TIA hardware, spectral calibration, channel map and analysis |
