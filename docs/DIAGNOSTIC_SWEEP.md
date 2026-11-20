# Diagnostic height sweep

One run moves the chamber top through its travel. At every height it measures every LED on both detectors, in several electrical states. From that it judges the optics, the electronics, ambient light and the mechanics, gives a verdict, and explains each problem with the parts to check.

- Plan: [DIAGNOSTIC_SWEEP_PLAN.md](DIAGNOSTIC_SWEEP_PLAN.md).
- Deviations from the plan: [DIAGNOSTIC_SWEEP_S0.md](DIAGNOSTIC_SWEEP_S0.md) §3 (D1–D19).
- Code: `software/host/src/lio/scan/`.

## 1. Before a run (hardware)

1. **Mark the travel limits.** On the Motors tab, raise the top to its highest **light-tight** height (telescoping sleeves still overlapping — not as high as the motors can physically go) and press *Set top here*. Lower it to the lowest safe position and press *Mark bottom here*. Or use `lio stage set-top` / `lio stage mark-bottom`. Soft limits keep `stage.top_margin_steps` (~4 mm) below the marked top so the seal cannot open.
   - The position is kept in `test_results/stage_position.json`.
   - After an unexpected board reset the position is marked *not trusted*. Scans then refuse to start until the top is set again.
2. **Put the sample in:** `empty`, `white_ptfe`, `black_cup`, or a food (`food` / `LIO-F-xxxxx`).
3. **Close the lid and connect the earth bond.** Stay at the bench: the run asks you to confirm the chamber is clear before anything moves.

## 2. Modes

Times are on the simulator. On the rig, expect them to be similar or a little longer.

| Mode | What | Time |
|---|---|---|
| `quick_down` | 9 heights down, ends at the bottom | ~17 min |
| `quick` (default) | 9 heights down and back up | ~31 min |
| `full` | 33 heights down, 9 up, 5 reference heights × 2 repeats from both sides | ~44 min |
| `fine` | as `full`, plus 16 points around the optimum | ~52 min |
| `repeatability` | 5 reference heights × 5 repeats from both sides | ~47 min |
| `electrical` | no motion: electrical health here | ~2 min |
| `continuous` | measures while moving (`MOTOR LIGHT 1`), down and back up | ~30 min |

Each run follows the same phases:
- **P0 preflight:** firmware, ADC, safe state, stage, operator questions.
- **P1 static:**
  - hum records;
  - a 30 s dark record at 8 SPS;
  - select-only coupling on every hole;
  - one sweep.
- **P2 down / P3 up:** stop, settle, dark, sweep, dark at each height. A hum record every 4th height, with coil interference recorded on the next move.
- **P4 closing:**
  - re-measure, for drift;
  - interlock re-checks: light refused while moving, CE refused with two holes selected;
  - everything off.

Every setting is in `scan:` in `software/config/lio_hw.yaml`, and any of them can be changed for one run (`--set key=value`, or *Settings for this run* in the dashboard). Defaults:
- 2 samples per reading;
- 8 ms optical settle;
- 300 ms mechanical settle;
- 500 half-steps/s between heights;
- 90 s heartbeat timeout.

## 3. Safety rules (enforced)

- One LED at a time: the MOSFET is selected, then CE is raised (`SWEEP`).
- RAIL A at most 1 s on-time per LED per minute. The duty tracker waits when needed, and every wait is logged in `cube.csv.gz` (`duty_wait_ms`).
- Stop–measure–move: no light while moving, except the labelled `continuous` mode.
- The soft limits always apply.
- Any abort sends `OFF`, `MOTOR STOP`, `MOTOR ALL RELEASE` and `MOTOR LIGHT 0`, records the reason, and marks the run INCOMPLETE. Abort causes:
  - the operator, or Ctrl-C;
  - saturation;
  - an ADC dropout;
  - lost contact with the board;
  - a soft limit;
  - an unexpected `# BOOT`.

  An unexpected boot also marks the position as not trusted.
- In the dashboard, if the page stops sending its heartbeat for the timeout, the scan pauses at the next safe point (everything off) and carries on when the heartbeat comes back. *All off* aborts a scan.

## 4. Running it

**Dashboard → Scan tab:**
1. Choose the mode and sample. *Preview plan* shows the heights, the duration and the predicted LED duty.
2. Tick *Someone is at the bench* (hardware), then *Start scan*.
3. While it runs:
   - progress, phase, height in mm and ETA;
   - a live hole × height heat-map per detector;
   - *Pause* / *Abort*.
4. At the end:
   - the verdict;
   - each problem with **why / parts / next check**;
   - a link to the report;
   - the twin coloured through T13.

*Earlier scans* lists the runs, with *Resume* for interrupted ones.

**Command line:**

```
lio scan plan --mode full [--set sweep_n=4]
lio scan run --mode quick --sample empty --allow-motion      # hardware: stay with the rig
lio --sim [--fault pd_disconnected] scan run --mode quick --sample empty
lio scan resume test_results/<ts>_scan_quick [--allow-motion]
lio scan analyse <run> [--reference <white_ptfe run>]       # writes analysis.json
lio scan report <run>                                        # report.html, report.md, plots/
lio scan baseline save <run>; lio scan baseline list
lio scan compare <runA> <runB>
```

**Catalogue:** `T13.1 Diagnostic height sweep` (motion: `lio selftest --allow-motion`, or `--modules scan`). It runs `scan.suite_mode` and feeds the twin and the T11 verdict.

## 5. What is measured, and how it is judged

The thresholds are in `scan.health`, as `[WARN, FAIL]` pairs. **All are provisional**: they were set from healthy and faulted simulator runs and must be recalibrated at commissioning.

- **Optics, per hole and detector.**
  - **Response:** the response curve S(h), and the optical amplitude O = S(h_opt) − C.
  - **Shape:** the modulation (how much the response changes with height, relative to O; flat means not light) and the FWHM.
  - **Optimum height**, per hole and overall, in mm (M6 × 1.0 rod, direct drive: 4096 half-steps per mm).
  - **Signal quality:** SNR and saturation headroom.
  - **Plausibility:** a detector responding to a hole it cannot see means a wrong or swapped LED.
  - **Electrical-only signature:** every expected hole flat while the coupling is large.
  - **Throughput:** the median O on the expected holes.
  - **Needing a reference run:**
    - stray light, from a `black_cup` run with a `white_ptfe` reference;
    - effectiveness, against a reference of the same sample.
- **Electrical.**
  - **Coupling C**, per detector and rail. It is measured on the blind holes, where the LED current flows but no light is seen (D15).
  - **Ground shift:** C against the rail current, in mV/mA.
  - **Dark offset**, with its equivalent input current, against the T06 dark ranges.
  - **Drift**, separated from height when both passes exist.
  - **Mains hum** at 60/120/180 Hz, with the coils off.
  - **Coil interference**, while moving against coils off.
  - **Select-only coupling.**
- **Ambient:** the dark level against height (a leak at the shroud, and the height where it starts), and 120 Hz flicker.
- **Mechanics:**
  - **Backlash and step loss**, read optically from the up pass against the down pass. The model is δ0 + κ·progress. Both are reported with their resolution and flagged only beyond 3σ.
  - **Repeatability** at the reference heights.
  - **Travel, lockstep, settle time.**
- **System:**
  - a health per subsystem (OK / WATCH / ACT, with the dominant reason);
  - the verdict, using the T11 rules unchanged: FUNCTIONAL / DEGRADED / NOT FUNCTIONAL.
- **Trend:** per-hole ratios against the previous baseline, localised:
  - one hole points to that LED or its alignment;
  - one whole detector points to that detector or its front end;
  - everything points to the supply, the geometry or the sample.

  With 5 or more baselines of a sample, each metric gets a control chart (±3σ and an EWMA).

**Coupling states (firmware ≥ 2.5.0, `DBG STATE`).** In P1:
- **CE-only**, per rail: CE high with nothing selected. Measures driver-enable coupling (`elec/<det>/ce_only`).
- **Wrong-rail**, per hole: the hole selected, the other rail enabled. The LED must stay dark; light means it is wired to the wrong rail (`optics/wrong_rail/hNN`).

Checks that need hardware or firmware not fitted are reported as **SKIP** with the reason:
- the coupling states on firmware 2.4.0 (the rig until 2.5.0 is flashed);
- rail and ground monitoring on A2/A3;
- home sensors.

## 6. Files

```
test_results/<YYYYmmdd-HHMMSS>_scan_<mode>/
  scan.json        plan, settings, events, aborts, operator answers, duty, health, resume index
  cube.csv.gz      one row per reading (step, phase, height, direction, hole, state, detector,
                   dark/lit/net counts, net mV, time, duty wait, settle, n)
  streams/*.npz    timestamped raw streams: hum (coils off), coil EMI (moving), long dark
  analysis.json    findings, explanations, health, verdict
  report.html, report.md, plots/
  results.json     the T13.1 result (dashboard runs), for the twin and the run list
test_results/scan_baselines/<sample_id>/<run>.json
```

## 7. Simulator and tests

Every check has a fault in the simulator and a row in `tests/system/test_fault_matrix.py` (`SCAN_MATRIX`). Each row requires three things:
- the intended finding flags the fault;
- its explanation names the right part;
- on a healthy rig, the same finding passes.

Healthy `quick` and `full` scans at full size give FUNCTIONAL. Faults are injected with `--fault`, for example:
- `pd_disconnected`
- `ground_shift:0.2`
- `backlash:2000`
- `step_loss:2,4200`
- `led_swapped:9,16`

## 8. Commissioning (S7, with the owner)

1. A `quick` scan with `empty`.
2. If the tile is available, a `full` scan with `white_ptfe`, then `black_cup` (for stray light).
3. Recalibrate `scan.health`, especially throughput and stray light. Set `thresholds.motion.travel.range_steps`.
4. Save the first baselines.

The report should reproduce the known bench state:
- InGaAs dark offset ≈ −21 mV, which flags `elec/ingaas/dark_offset`;
- OPT101 dark ≈ 7 mV;
- the hole 9 / 16 anomaly, explained.

### 8.1 First rig scan: 2026-11-16, `quick`, chamber empty (firmware 2.5.0)

Run `20261116-202110_scan_quick`. It completed: 19 steps in 46 min, no aborts, and the LED duty stayed within budget. The verdict was **NOT FUNCTIONAL**, and the scan pinned down the known problems:

| Finding | What it means | Next check |
|---|---|---|
| `optics/wrong_rail/h09` FAIL | Hole 9 gives nothing normally, but **lights when only RAIL B is enabled**. Its LED is wired to DRV2, not DRV1. This explains the "dead hole 9". | Trace LED9's return/anode to its driver; move it to RAIL A. |
| `optics/opt101/h16/plausibility` FAIL | The silicon OPT101 sees hole 16 strongly (333→764 counts, rising with height). It cannot be an 1850 nm LED. | Check hole 16 with a phone camera; check the LED part. |
| `optics/ingaas/throughput` FAIL | The InGaAs sees almost no light on any hole (~20–50 counts, nearly flat). | Inspect the window over D1 and the alignment; see the dark offset below. |
| `elec/ingaas/dark_offset` FAIL | −20.9 mV, about 21 nA into the TIA input (the bench state). | Fault tree "InGaAs coupling": the U5 pin-2 node, D1. |
| `elec/ingaas/hum` WARN | 2.0 mV at 60 Hz, 99% of the InGaAs noise. | Earth bond and chargers. |
| `elec/opt101/coil_emi` FAIL | The OPT101 noise rises tenfold (0.1 → 1.0 mV) while the motors run. It matters only for measuring while moving. | Route the motor cables away from the OPT101 leads. |
| `optics/optimum` WARN | The response rises all the way to the bottom of the travel, so the best height is at or below the bottom. | — |

Mechanics:
- Backlash and step loss were not resolvable from a quick scan (about ±4,000 half-steps), because the curves rise steadily rather than peaking.
- The up and down curves overlap closely.
- A `full` scan (repeat visits at 5 heights) is the better test.

**Calibration from this run.**
- The rig's optical levels are about 100× below the simulator's. The weakest working OPT101 hole (5) gives O ≈ 22 counts.
- The light floors are now `min_signal_counts [15, 6]`, or 8/4 × the detector noise if larger, and throughput `empty [60, 20]`.
- Partial losses are judged against the baseline of the same sample (`effectiveness`, `trend/compare`).
- The analysis now removes single-reading spikes (on the rig, holes 14–16 at the first and last steps) and fits the mechanics robustly.
- Saved as the first `empty` baseline.

### 8.2 Software fixes after commissioning (2026-11-17), and what remains

| Finding | Status now | How |
|---|---|---|
| InGaAs mains hum | Cancelled in the readings | Firmware 2.5.1 `ADC CFG MAINS 60`: each reading integrates 2 whole mains periods. The scan turns it on in P0 and off at the end. On the rig the InGaAs reading-to-reading spread fell from 1.9 to 0.9 counts with the hum at its 17 Nov level. The raw hum is still reported, as PASS unless above 3 mV. |
| Room-light flicker (120 Hz) | Cancelled the same way | 120 Hz is a mains harmonic. |
| OPT101 coupling and ground shift | Corrected (PASS below FAIL) | C is measured per rail on the blind holes and subtracted from every hole. FAIL only if it grows beyond 20 counts or 0.08 mV/mA. |
| OPT101 / InGaAs coil interference | Judged only in `continuous` mode | Stop–measure–move readings never see it. Continuous runs now record it at the start of each move. |
| T07.2 settle false warning (simulator) | Fixed | The settle band is never tighter than 4 robust sigmas of the plateau noise. |
| Hole 6 intermittent | Now detected | `optics/hNN/intermittent`: down and up readings at one height disagree on both detectors at once. It flags hole 6 in the black-cup run, and one-off RAIL B jumps (holes 13, 14, 16) at the first height of the empty run. |

Still failing: they need the bench.
1. **Hole 9 wired to RAIL B** (`optics/wrong_rail/h09`, `optics/*/h09/response`). Move LED9's connection from DRV2 to DRV1.
2. **Hole 16 is not an 1850 nm LED** (`optics/opt101/h16/plausibility`). Check it with a phone camera; check the part.
3. **Hole 6 intermittent** (`optics/h06/intermittent`). Reflow or re-seat LED6 and Q6; wiggle-test.
4. **InGaAs sees almost no light** (`optics/ingaas/throughput`). Check that D1 is in circuit, its orientation, and the window over it.
5. **InGaAs −21 mV dark offset: traced to U5 itself, and accepted.** On 17 Nov the offset stayed the same with D1 disconnected, with pin 2 lifted off the breadboard, and with Cf out. It also measured −22 mV between pin 1 and pin 3, with pin 2 equal to pin 3 and no ground difference to the ADC. So it is the TL072's own offset or input leakage. It is steady (about 0.2 counts of noise) and subtracted in every measurement, so `thresholds.dark.ingaas_counts` now allows down to −50 mV. A real leak still FAILs, and drift is still watched. Swapping U5 would remove it.
6. **Stray light**: the black cup keeps 84% of the empty-chamber response (`optics/stray`). Darken or baffle the chamber's inner surfaces. A white tile would give the absolute scale.

### 8.3 Check after the InGaAs rework (2026-11-17)

- **Dark levels as before:** InGaAs −21.0 mV, OPT101 +7.1 mV.
- **One sweep at the top** matched the empty baseline within about 10% on holes 1–13 and 16.
- **Hole 14 changed:** 8/4 counts (OPT101/InGaAs) against 22/23 in the baseline. Its LED current coupling has almost vanished, so LED14 is probably not getting its current.
- **Hole 15 changed the other way:** 40/80 against 19/27.

Both are RAIL B neighbours, so a wire on that side probably moved. Check LED14's and LED15's connections.

`lio watch` gives a live, read-only readout of both detectors, used for the remote-control test.
