# Diagnostic height sweep

One run moves the chamber top through its travel. At every height it measures every LED on both detectors, in several electrical states. From that it judges the optics, the electronics, ambient light and the mechanics, gives a verdict, and explains each problem with the parts to check.

- Plan: [DIAGNOSTIC_SWEEP_PLAN.md](DIAGNOSTIC_SWEEP_PLAN.md).
- Deviations from the plan: [DIAGNOSTIC_SWEEP_S0.md](DIAGNOSTIC_SWEEP_S0.md) §3 (D1–D19).
- Code: `software/host/src/lio/scan/`.

## 1. Before a run (hardware)

1. **Mark the travel limits.** On the Motors tab, raise the top to its upper end and press *Set top here*. Lower it to the lowest safe position and press *Mark bottom here*. Or use `lio stage set-top` / `lio stage mark-bottom`.
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

Checks that need hardware or firmware not fitted are reported as **SKIP** with the reason:
- the CE-only and wrong-rail coupling states (firmware 2.5.0 proposal);
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
