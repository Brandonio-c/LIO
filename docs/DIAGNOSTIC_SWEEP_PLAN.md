# LIO V3 — Full-System Diagnostic Height Sweep: Software Engineering Plan

**Document:** LIO-SW-SCAN-001 Rev A, 16 November 2026
**Repo:** github.com/Brandonio-c/LIO, host package `software/host/src/lio/`, firmware 2.4.0
**Builds on:**
- the existing suite (T01–T11)
- stage tracking (`lio.stage`)
- T09.6/T09.7 continuous-jog motion
- `docs/PROTOCOL.md`

---

## 1. Goal

One automated run, **the diagnostic sweep**, that moves the chamber top through its full travel and, at every height, measures every LED on both detectors in several electrical states.

From that one dataset it must:

1. **Prove full-system functionality.** Every subsystem gets exercised and judged with evidence: link, ADC, shift registers, both drivers and rails, all 16 channels, both detector front ends, both motors in lockstep, stage tracking and the safety interlocks.
2. **Characterise optical performance:**
   - response versus height for every hole (*reflection / collection effectiveness*);
   - the optimum measurement height;
   - wavelength plausibility;
   - stray light.
3. **Report health,** each item with a value, unit, threshold and trend:
   - circuit leakage and amplifier offset;
   - electrical crosstalk (LED-current coupling);
   - ground shift;
   - mains hum and noise;
   - ambient light pollution (and how it changes with chamber overlap);
   - mechanical repeatability, backlash and step loss;
   - drift during the run.
4. **Explain.** Every warning and failure names the subsystem and parts involved, the likely cause, and the next manual check.

### The key idea: height separates optical from electrical

Every signal component behaves in a characteristic way as the top moves:

| Component | Height dependence | Hole/wavelength dependence | Rail/state dependence |
|---|---|---|---|
| Real reflected light | **strong**, smooth, peaked | follows LED × detector responsivity | appears only with LED lit |
| Electrical coupling (LED current → detector) | **none** | follows rail current, not wavelength | also present in "CE-only" and "select-only" states |
| Ground shift | none | scales with LED current | present whenever current flows |
| Circuit leakage / TIA offset | none (drifts slowly with time/temperature) | none | present in dark |
| Ambient light leak | changes with chamber overlap (height) | none | present in dark, lid-dependent; 120 Hz flicker under room LEDs |
| Stray light (LED → detector, not via sample) | weak or none | follows wavelength | lit only; present with a black target |

A decomposition across height × hole × state therefore separates these components using the data alone. This is the diagnostic core of the sweep (§6).

## 2. Scope and non-goals

- **In:**
  - the sweep planner, executor, data model, analysis, health report, CLI and dashboard tab;
  - simulator models and fault injection;
  - tests and docs.
- **Optional, behind flags and needing owner approval:**
  - firmware debug states (CE-only, wrong-rail);
  - home-sensor support;
  - A2/A3 rail and ground monitoring.

  The sweep must run fully without them, and report those checks as SKIP with the reason.
- **Out:**
  - changes to `lio_motor_control.py`, the CAD and the electronics documents (proposals only);
  - flashing firmware or moving motors without the owner's "go".

## 3. Sweep procedure

### 3.1 Modes

| Mode | Heights | Direction | Repeats | Typical duration* | Purpose |
|---|---|---|---|---|---|
| `quick` | 9 (incl. top and bottom) | down only | 1 | ≈ 18 min | routine health check |
| `full` | 33 | down, then 9 back up | 2 at 5 reference heights | ≈ 45 min | commissioning, after rewiring |
| `fine` | 33 + 16 extra around the optimum | down + up | 3 | ≈ 70 min | optical characterisation |

\*Dominated by travel: 420,017 half-steps at 500 half-steps/s ≈ 14 min per full stroke. Heights are configurable in `lio_hw.yaml` (`scan.modes`). Spacing is uniform in half-steps by default, with optional densification near the sample (the bottom of travel).

### 3.2 Phases

**P0 — Preflight (gate: any failure aborts before motion).**
- Link (`INFO`, version ≥ 2.4.0), `STATUS` safe state, ADC present.
- Rails OK (if monitored).
- Stage: top and bottom limits marked, and position valid. That means no unseen `# BOOT`; home sensors confirm it if fitted.
- Operator confirmations, recorded:
  - chamber clear;
  - lid closed;
  - sample in place, with `sample_id` from a fixed vocabulary: `empty`, `white_ptfe`, `black_cup`, or a food id;
  - earth bond connected.
- Duty budget available.
- Arm motion (60 s window, renewed by the executor while the operator stays present; the existing token flow).

**P1 — Static electrical characterisation at the top (no motion).**
- Dark noise and hum spectrum on A0/A1: an `ADC STREAM` at 860 SPS with µs timestamps, 2 s per input.
- Long dark baseline: 30 s at 8 SPS.
- Coupling states per rail, if the firmware supports them:
  - **CE-only** (driver on, mask 0);
  - **select-only** (MOSFET on, CE low);
  - **wrong-rail** (hole selected, the other rail's CE on, which must be dark).

**P2 — Height scan (down).** At each height h:
1. Move (continuous jog, then exact finish per motor). Release the coils.
2. **Mechanical settle:** wait `scan.settle_ms_mech` (default 300 ms), then confirm two consecutive dark reads agree within 3σ.
3. **Dark frame:** everything off. Read A0/A1, n = 8.
4. **SWEEP:** the firmware already measures dark + lit per hole and can repeat. Use `SWEEP <settle_ms> <n>`. Then append the out-of-band detector values, which SWEEP returns for both inputs anyway.
5. **Dark frame again.** Drift within the step = difference between the two dark frames.
6. **Every k-th height** (default k = 4): a 1 s hum stream on both inputs with the coils released, and a 1 s stream with the coils energised. Coil EMI = the difference.
7. **Checkpoint:** append to the scan file. If interrupted, resume from the last completed height (§5.3).

**P3 — Return scan (up, `full`/`fine`).** Re-measure a subset of heights while moving up. Hysteresis between the down and up response curves gives the **backlash** estimate. At 5 **reference heights**, measure twice in each direction for repeatability.

**P4 — Return to top and closing checks.**
- Return to top.
- Re-measure the P1 dark and hole-8 response. The difference from P1 is drift over the whole run.
- Re-check the safety interlocks:
  - motion with light refused, unless `MOTOR LIGHT`;
  - comms-loss failsafe (optional; long);
  - single-channel invariant.
- Coils released, optics off, disarm.

### 3.3 Safety and duty rules

- **Lighting:** stop–measure–move only. No light while moving, so `MOTOR LIGHT` is not needed. An optional `continuous` sub-mode uses `MOTOR LIGHT 1` for a fast dynamic scan, and is labelled as such.
- **RAIL A duty:** the host duty tracker keeps every RAIL A LED ≤ 1 s on-time per minute, inserting waits and logging them. With about 25–40 ms per flash, 16 holes per height and ≈ 6 s per step, the duty is ≈ 0.5%.
- **Aborts:** the operator abort (dashboard button, Ctrl-C), an unexpected `# BOOT`, an ADC dropout, saturation, a rail out of range, a soft limit, or a lost comms heartbeat. Each abort sends `OFF`, `MOTOR STOP`, `MOTOR RELEASE`, records the reason and marks the run INCOMPLETE.
- **Motors:** the soft limits (and the 4,096 half-step top margin) always apply. Never run unattended; the dashboard keeps an "operator present" heartbeat, and the sweep pauses if it's missing for more than 60 s.

## 4. Data model

### 4.1 Scan cube
One run folder `test_results/<ts>_scan_<mode>/`:

| File | Content |
|---|---|
| `scan.json` | metadata (below), plan, phase timings, events, aborts, the operator answers |
| `cube.parquet` (or CSV fallback) | one row per reading: `run_id, phase, height_hs, direction, rep, hole, state, detector, dark_counts, lit_counts, net_counts, mV, t_us, duty_wait_ms` |
| `streams/*.npz` | raw timestamped streams (hum/EMI) |
| `analysis.json` | every derived metric with value, unit, threshold, status, evidence pointers |
| `report.html`, `report.md`, `plots/` | human report |

`state` ∈ `dark`, `lit`, `ce_only`, `select_only`, `wrong_rail`, `coils_on`, `coils_off`.

**Metadata:**
- firmware `INFO`, the host version and git commit;
- `lio_hw.yaml` hash and device-model hash (if present);
- `sample_id`, lid state, earth bond, operator;
- stage limits and position source (tracked / home sensor);
- start/end times, the ambient temperature if you enter it.

### 4.2 Units and conventions
- Counts and mV, both stored (GAIN_ONE: 0.125 mV/count).
- `height_hs` is negative downward from the top (the existing `lio.stage` convention).
- Every threshold is read from `lio_hw.yaml` (`scan.health.*`), marked provisional until a baseline exists.

## 5. Software architecture

```
software/host/src/lio/scan/
  plan.py        # ScanPlan from mode + config; heights, directions, reference heights, time/duty estimate
  executor.py    # state machine P0..P4; uses LIODevice; checkpoint/resume; abort handling; events
  store.py       # cube writer (parquet/CSV), streams, scan.json; resume index
  analysis/
    optics.py    # response curves, optimum height, effectiveness, plausibility, stray light
    electrical.py# offset/leakage, coupling, ground shift, hum/noise spectra, coil EMI
    ambient.py   # dark vs height, leak vs overlap, flicker
    mechanics.py # backlash, repeatability, step-loss, lockstep, travel
    system.py    # subsystem coverage matrix and functional verdict
    trend.py     # comparison with baselines and previous scans
  report.py      # HTML/MD, plots (heat-maps hole×height, curves, spectra, control charts)
  explain.py     # rules: finding → cause text, parts implicated, next manual check
```

- **CLI:**
  - `lio scan plan --mode full` (prints heights, duration, duty)
  - `lio scan run --mode full --sample white_ptfe [--resume <run>]`
  - `lio scan analyse <run>`
  - `lio scan report <run>`
  - `lio scan compare <runA> <runB>`
  - `lio scan baseline save <run>`
- **Suite integration:** register as **T13 Diagnostic sweep** (kind M+A, needs `--allow-motion`). Sub-results map onto existing modules, so the twin and verdict work unchanged (§7).
- **Dashboard:** a new **Scan** tab with:
  - mode/sample selector;
  - plan preview (duration, heights);
  - Start / Pause / Abort;
  - an operator-present heartbeat;
  - live progress (height, phase, ETA);
  - a live **hole × height heat-map** per detector, and live dark-level and hum gauges.

  When the run ends, the tab links to the report and colours the twin.

### 5.3 Checkpoint and resume
- After each completed height, `store` flushes and records the index.
- On resume:
  - verify the firmware version and config hash match;
  - verify stage position validity (abort if a `# BOOT` happened without a position re-establishment);
  - move to the next planned height and continue.
- Interrupted runs are reported as INCOMPLETE; metrics needing the missing data are marked SKIP.

## 6. Analysis — metrics and how each is computed

### 6.1 Optical performance
| Metric | Method | Output |
|---|---|---|
| Response curve S(h) per hole, per detector | net = lit − mean(adjacent darks); median over repeats; bootstrap 95% CI | curve + CI |
| **Optimum height** per hole and overall | argmax of a smoothed S(h) (Savitzky–Golay); overall = maximises min-normalised response across fitted holes | half-steps + mm (if the lead per turn is configured) |
| **Reflection/collection effectiveness** | with `white_ptfe`: E(h) = S(h) / S_ref, where S_ref is the per-hole reference from the baseline (or the max over h if no baseline). The radiometric-model ratio is optional: measured/expected from LED power × detector responsivity × geometry | dimensionless, per hole |
| Peak width / depth of field | FWHM of S(h) | half-steps |
| Signal-to-noise per hole at the optimum | S_opt / σ_dark | dB |
| Saturation headroom | max lit / ADC or TIA limit | % |
| Wavelength plausibility | ratio InGaAs/OPT101 per hole versus the responsivity table; height-dependent components only | PASS/WARN with the "possible swap or wrong LED" explanation |
| **Stray light** | with `black_cup`: S(h) relative to `white_ptfe` S(h). Without both runs: the height-invariant optical residual from the decomposition (§6.6) | % of signal |
| Hole uniformity | spread of E across holes at the optimum | CV % |

### 6.2 Electrical health
| Metric | Method | Output |
|---|---|---|
| **TIA dark offset and leakage** | dark A0 mean across all heights (height-invariant part). Equivalent input current I_eq = −V_dark / Rf; ΔI over the run = drift | mV, nA, nA/h |
| Offset stability | dark σ within step, drift slope over the run, dark difference P1 vs P4 | counts, counts/h |
| **Electrical coupling (crosstalk)** | per hole: the height-invariant component of net signal on each detector (intercept of the decomposition). Corroborated by the CE-only and select-only states and by out-of-band holes (InGaAs on holes 1–7) | counts per hole; flag if > threshold |
| Ground shift | coupling that scales with the rail current rather than the hole; plus the A3 probe if wired | mV per mA |
| Hum / noise spectrum | Lomb–Scargle on timestamped streams: RMS at 60/120/180 Hz, broadband σ, fraction of variance at mains harmonics | mV, % |
| Coil EMI | σ and spectrum, coils energised vs released | ratio |
| OPT101 dark and noise | as above for A1 | mV |
| Rails (optional) | A2/A3 readings across all states (sag under LED load) | V, mV sag |
| Rail-map correctness (optional) | wrong-rail state must be dark | PASS/FAIL per hole |

### 6.3 Ambient light pollution
| Metric | Method | Output |
|---|---|---|
| Dark level vs height | dark frames versus h. A rise as the chamber overlap shrinks = a light leak at the shroud | counts vs h; leak onset height |
| Lid sensitivity | optional operator step: one dark frame with the lid ajar at two heights | Δcounts |
| Flicker | 120 Hz component of dark streams (room lighting reaching the detector) | mV |
| Ambient fraction | dark / lit at optimum per hole | % |

### 6.4 Mechanical health
| Metric | Method | Output |
|---|---|---|
| Travel | reported steps top→bottom vs the configured 420,017 (and home-sensor counts if fitted) | half-steps |
| **Backlash** | horizontal offset between the down and up S(h) curves that minimises the squared difference, over well-sloped regions of strong holes | half-steps |
| **Repeatability / step loss** | the response signature at reference heights, re-visited; signature shift by cross-correlation; the P1 vs P4 hole-8 response at the top | half-steps, % |
| Lockstep / level | per-motor step counts always equal (firmware positions); with home sensors, per-side trip difference | half-steps |
| Settle time | dark-read convergence after each move | ms |

*Note:* without home sensors, step loss is detectable only as a signature shift, so resolution is limited by the curve slope. The report states the resolution achieved.

### 6.5 System functionality matrix
Every subsystem must be exercised and judged:

| Subsystem | Evidence in sweep |
|---|---|
| Link/firmware | P0, event log, no unexpected BOOT |
| ADC/I²C | every reading; dropouts counted |
| Shift registers U1/U2 | each of the 16 holes addressable and isolated (signature uniqueness across heights) |
| Drivers DRV1/DRV2 | rail-gated response; coupling states |
| Each LED/MOSFET channel | height-dependent response on its expected detector |
| OPT101, InGaAs TIA | noise, offset, response, plausibility |
| Motors M1/M2 | full travel, lockstep, backlash, repeatability |
| Stage tracking | positions consistent; soft limits respected |
| Safety | P4 interlock re-checks; aborts tested in sim |
| Power/earthing | hum metrics; rails if monitored |

The overall verdict reuses T11 logic: **FUNCTIONAL / DEGRADED / NOT FUNCTIONAL**, plus a **health score per subsystem** (OK / WATCH / ACT) with the dominant reason.

### 6.6 Decomposition model (the core)
For each hole i, detector d, height h, state s:

`net[i,d,h] = O[i,d]·g_i(h) + C[i,d] + ε`

- g_i(h) is a smooth, non-negative optical shape;
- O is the optical amplitude;
- C is the height-invariant electrical (coupling + ground shift) term.

Fit with a penalised spline for g, or non-parametrically: C = the robust minimum plateau where the optical signal is known to vanish (if such heights exist), else from the coupling states. If the coupling states are available, they constrain C directly.

**Interpretation:**
- O ≈ 0 with C ≠ 0 ⇒ electrical only (the disconnected-photodiode signature of 15 Nov);
- O > 0 on a detector that can't see that wavelength ⇒ wrong LED, swap, or optical leak between channels;
- C ≠ 0 scaling with rail current ⇒ ground shift.

Report O and C with confidence intervals.

### 6.7 Trend and baselines
- `lio scan baseline save <run>` stores, per `sample_id`, the curves, effectiveness, dark offsets and noise levels, with the config and model hashes.
- Later scans: per-metric control charts (EWMA, ±3σ from ≥5 baseline runs).
- Per-hole ratio to baseline localises drift: one hole ⇒ LED or alignment; all holes on one detector ⇒ detector or front end; everything ⇒ supply, geometry or sample.

## 7. Explanations (`explain.py`)

A rule table maps findings to cause, parts and next check. Examples:

| Finding | Explanation | Parts | Next check |
|---|---|---|---|
| Hole response flat in h with C > 0, O ≈ 0 on InGaAs | Signal is electrical, not light: photodiode not connected to the amplifier, or ground shift | D1, U5, SUM, TIA_REF | Fault tree "InGaAs coupling" (meter D1 leads, pin 2/3 wiring) |
| Hole dark on both detectors at all heights | LED dead, MOSFET open, wrong rail, or an LED that neither detector can see (swap) | LEDn, Qn, rail | Phone-camera check; Qn gate/drain voltages |
| OPT101 responds to holes ≥ 12 | Wrong LED or swapped holes (silicon can't see ≥ 1100 nm) | LEDs | Camera check on that hole |
| Dark rises toward the bottom of travel | Ambient light leaking past the shroud as overlap shrinks | shroud, lid | Repeat with the room dark; inspect the shroud seal |
| 60 Hz > 50% of noise variance | Mains hum: earthing or charger leakage | power, GND | Check the earth bond; the chargers |
| Down/up curves offset > N half-steps | Backlash or lost steps | M1, M2, lead screws | Repeat the reference heights; inspect couplers |
| Dark offset drifts > X nA/h | Leakage changing (humidity, temperature) or warm-up | U5 pin-2 node | Re-run after 30 min warm-up |

## 8. Firmware

- **None required.** The sweep uses `SWEEP`, `ADC READ`/`STREAM`, `MOTOR …`, `STATUS` and `OFF` from 2.4.0.
- **Optional (owner approval; 2.5.0):**
  - **debug coupling states:**
    - `CE <n> 1 FORCE` with mask 0 (CE-only);
    - select with CE low (already possible via `SR RAW`);
    - wrong-rail CE;
  - µs timestamps in `ADC STREAM`, if not already present;
  - home-sensor commands, if the ITR20001 sensors are fitted.

  All stay watchdog-bounded and single-LED.

## 9. Simulator (required for every check)

Extend `sim.py` with:

1. **Height optics:** g_i(h) per hole (a peaked function of the top position, defined in the sim config); detector responsivity per wavelength; a sample reflectance per `sample_id`.
2. **Ambient leak** as a function of chamber overlap; 120 Hz flicker.
3. **Electrical terms:**
   - coupling per rail;
   - ground shift ∝ rail current;
   - TIA offset (Vos, Rsh, leakage);
   - drift over time;
   - mains hum;
   - coil EMI.
4. **Mechanics:** backlash, step loss on a side, travel mismatch.

**Faults** (each with a row in `test_fault_matrix.py`, detected by the intended metric):
- `pd_disconnected`
- `ground_shift:<mV/mA>`
- `leakage:<nA>`
- `leakage_drift:<nA/h>`
- `ambient_leak:<onset_h>`
- `room_flicker`
- `mains_hum:<mV>`
- `coil_emi`
- `backlash:<hs>`
- `step_loss:<side>,<hs>`
- `led_swapped:9,16`
- `wrong_led:<hole>=<nm>`
- `dead_channel:<n>`
- `rail_miswired:<n>`
- `window_blocked:<factor>`
- `stray_light:<frac>`
- `mid_run_boot`
- `adc_dropout`

The simulator runs on its virtual clock, so a `full` scan finishes in seconds in CI.

## 10. Configuration (`lio_hw.yaml`, new `scan:` section)

- `modes` (heights, directions, repeats, reference heights)
- `settle_ms_mech`, `optical_settle_ms`, `sweep_n`
- `hum_every_k`
- `duty` limits
- `lead_mm_per_rev` (optional, for mm output)
- `health.*` thresholds (all provisional), and `sample_ids` vocabulary
- the responsivity tables (cited) and LED nominal power (if known) for the effectiveness/radiometric model

## 11. Testing and acceptance

- **Unit:**
  - planner (heights, ETA, duty);
  - store round-trip;
  - every analysis function on synthetic data with known answers (offset, backlash, coupling amplitude, optimum height);
  - explanation rules.
- **Simulator system tests:**
  - healthy `quick`/`full` scans ⇒ FUNCTIONAL, all metrics in range;
  - each fault in §9 ⇒ the intended metric flags it and `explain.py` names the right parts;
  - abort and resume paths;
  - a mid-run boot invalidates position.
- **Hardware acceptance (M6, with the owner):**
  - a `quick` scan with `empty`, then a `full` scan with `white_ptfe` if available;
  - the report reproduces the known bench state (InGaAs offset ≈ −21 mV; OPT101 dark ≈ 7 mV; the hole-9/16 anomaly is explained);
  - no safety rule violated;
  - the duty log stays within limits.
- **CI:** ruff, mypy strict, pytest including the fault matrix; no hardware tests.

## 12. Milestones (one PR each; never push to main)

| # | Milestone | Content | Effort |
|---|---|---|---|
| S0 | Recon | Read the current code (device, stage, T09.6/T09.7, SWEEP, dashboard); confirm the timing estimates on the sim; list deviations; questions | 0.5 d |
| S1 | Sim height model | Optics/ambient/electrical/mechanical models + all faults | 2–3 d |
| S2 | Plan + executor + store | P0–P4, checkpoint/resume, aborts, duty, CLI `plan/run` | 3–4 d |
| S3 | Analysis I | Optical metrics, decomposition, electrical health | 3–4 d |
| S4 | Analysis II | Ambient, mechanical, system matrix, verdict, trend/baselines | 2–3 d |
| S5 | Report + explanations + T13 integration | HTML/MD, plots, `explain.py`, twin mapping | 2–3 d |
| S6 | Dashboard Scan tab | Live heat-map, controls, heartbeat, report link | 2–3 d |
| S7 | Hardware commissioning *(with owner "go")* | Quick + full scan; calibrate thresholds; first baseline | 1 d bench |
| S8 *(optional)* | Firmware 2.5.0 debug states / A2–A3 / home sensors | Only after approval | 2–4 d |

## 13. Open questions for the owner

1. Is a white PTFE tile and/or a black cup available for the commissioning scans? Without them, effectiveness is relative only, and stray light comes only from the decomposition.
2. Default mode for routine use: `quick` (≈ 18 min)?
3. Approve firmware 2.5.0 coupling states (strongly improves the coupling/leakage diagnosis)?
4. Is the lead-screw pitch known, so heights can be reported in mm?
5. Wire A2/A3 for rail and ground monitoring, and fit home sensors? Both are optional and improve mechanical and electrical health accuracy.
