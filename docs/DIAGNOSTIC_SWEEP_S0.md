# Diagnostic sweep: S0 reconnaissance

S0 of [DIAGNOSTIC_SWEEP_PLAN.md](DIAGNOSTIC_SWEEP_PLAN.md) (LIO-SW-SCAN-001 Rev A), 16 November 2026. Everything below was read from the code and firmware 2.4.0, or measured on the simulator's virtual clock. Nothing touched the rig.

## 1. Building blocks: what exists, and whether the sweep can use it unchanged

| Block | How it behaves now | Usable unchanged? |
|---|---|---|
| **`SWEEP [settle_ms] [n]`** (firmware) | One atomic `MEAS` per hole 1–16, back to back: off, settle, dark A0 and A1 (mean of `n`), CH on, settle, lit A0 and A1, off. It emits `# M ch dark0 dark1 lit0 lit1 t_on_ms` per hole, so **both detectors for every hole**. There is no repeat argument (`n` is samples per mean). It's refused while moving (unless `MOTOR LIGHT 1`) and refused if a hole's estimated on-time exceeds the rail watchdog. | **Yes.** P2's "SWEEP, then append the out-of-band detector" needs nothing extra: SWEEP already returns both inputs. |
| **`LIODevice.sweep()`** (host) | Checks the duty budget for each of the 16 holes before sending (`_duty_gate`, which sleeps if needed and logs the wait), then records each hole's on-time. Holes are recorded as starting at the SWEEP start, which over-counts slightly (conservative). | **Yes.** The duty waits are already logged in `dev.duty.cooldowns`. |
| **`ADC STREAM <ch> <n> <iv> [hole on off]`** | **Yes, µs timestamps:** `# S i t_us raw`, with `t_us` from `micros()` relative to the stream start. **One input per stream.** It **switches the LEDs off** when it starts. Up to **48 samples are captured into RAM** at the full ADC rate; longer streams print each sample as taken (serial-limited). Allowed while moving without an LED schedule (T09.4). | **Yes, but not at 860 SPS** (see deviation D1). |
| **Real conversion rate** | Measured on the rig on 16 Nov: 48 samples at the "860 SPS" setting took **119 ms (≈ 400 SPS)**. Single-shot conversion plus the software I²C overhead is about 2.5 ms per sample. At the 128 SPS setting it's about 102 SPS (≈ 9.7 ms per sample). | Hum analysis must use what's really achievable (D1). |
| **Motion: `MOTOR STEP`** | ≤ 2,048 half-steps, needs arming (60 s), trapezoidal at 250 half-steps/s², coils released at the end. The host checks the soft limits first. | **Yes**, for exact finishes and short moves. |
| **Motion: legacy jogs `U`/`D`/`S`** | One command moves both motors at the synchronised speed `VS`. A repeat in the same direction renews the 2,048-step bound without a new ramp. `S` stops both at once and releases the coils. No arming needed. | **Yes.** This is what the T09.6/T09.7 rewrite uses (`_lockstep`): continuous jog, stop just before the target, exact finish per motor. The sweep will reuse it, moved from the test module into the scan package. |
| **`MOTOR LIGHT 1`** | Light and measurements allowed while moving; armed only; lapses with the arm. | Only for the labelled continuous sub-mode. |
| **Coils held without stepping** | Only via `POWER WAKE ≤ 3 s`, which **blocks the firmware** (no other command runs meanwhile) and is disabled in this session's config (`power.wake: false`). | **No:** "stream with coils energised" isn't possible as written (D2). |
| **Coupling states** | **Select-only** (MOSFET on, CE low): **possible now** with `SR RAW <mask>`, which forces CE low and latches the mask, then `ADC READ`, then `OFF`. **CE-only** (driver on, mask 0) and **wrong-rail** are **refused**: `CE n 1` needs exactly one selected hole on that rail. | Select-only: yes. The other two: SKIP until firmware 2.5.0 (if approved). |
| **Stage tracking (`lio.stage`)** | The absolute position is kept in `test_results/stage_position.json`. **It rebases at every `# BOOT` and carries the position on**, with no notion of an *unexpected* boot. Soft limits are applied to step moves and jogs; the top margin is 4,096 half-steps. | **Needs a change** (D3): the plan requires that a mid-run boot **invalidates** the position. |
| **Duty tracker** | Per hole, a rolling 60 s window. Budget: **rail A 1,000 ms, rail B 5,000 ms** of on-time per hole per window. Asked before each LED action; waits are logged. | **Yes.** See the note on duty in D5. |
| **Comms failsafe** | 10 s without a byte while lit, moving or armed: everything off. | The executor polls `STATUS` during moves, so this is fine. |
| **Simulator** | Virtual clock (`dev.now()`/`dev.sleep()` advance simulated time), firmware-accurate command semantics, fault injection. **No height-dependent optics yet** (S1). | It needs S1, plus one fidelity fix (D4). |

## 2. Timing (plan §3.1)

### Measured on the simulator (virtual clock)

| Block | Simulated time |
|---|---|
| `SWEEP 8 4` | 2.32 s |
| `SWEEP 8 1` | 0.78 s |
| Dark frame (A0 + A1, n = 8) | 0.14 s |
| Stream 48 at 860 SPS | 0.19 s |
| Stream 400 at 860 SPS | 1.04 s |
| Stream 128 at 128 SPS | 1.03 s |
| Full stroke (420,017 half-steps) | **1,049 s (17.5 min)** |
| Segment 1/8 of travel | 134 s |
| Segment 1/32 | 36 s |
| Segment 1/48 | 25 s |

The full stroke should be 840 s at 500 half-steps/s. The simulator models each jog *renewal* as a fresh 2,048-step move ending in a deceleration, so its average speed is about 400 half-steps/s. That's a simulator fidelity bug (D4), fixed in S1.

### Estimates for the rig

These use the real jog speed of 500 half-steps/s, the 16 Nov measured conversion times, about 3 s of stop overhead per height (ramp, abrupt `S`, exact finish), and about 3.4 s of measurement per height (0.3 s settle, dark frames, `SWEEP 8 4`):

| Mode (plan) | Plan estimate | Sim (current model) | Rig estimate | Note |
|---|---|---|---|---|
| quick: 9 heights, down only | ≈ 18 min | 20 min (ends at the bottom) | **≈ 17 min** if it ends at the bottom | **P4 "return to top" adds a full stroke: ≈ 31 min** (D6) |
| full: 33 down + 9 up, 2 repeats at 5 reference heights | ≈ 45 min | 45 min | **≈ 37 min** | |
| fine: 33 + 16 around the optimum, down and up, 3 repeats | ≈ 70 min | 48 min (without the 16 extra heights) | **≈ 45–50 min** | the optimum must be known mid-run (D7) |

## 3. Deviations from the plan (proposed; none taken silently)

**D1. Hum streams can't run at 860 SPS for 2 s.** The real conversion rate is about 400 SPS (2.5 ms per sample), and unbuffered streams are also serial-limited.
- **Proposal:** take the hum record as repeated **48-sample buffered bursts** at the 860 SPS setting (≈ 120 ms each, ≈ 400 SPS, Nyquist ≈ 200 Hz, so 60/120/180 Hz are resolvable), about 17 bursts per 2 s, with µs timestamps.
- Then a Lomb–Scargle fit across bursts.
- The achieved rate is recorded and reported.

**D2. "Coils energised, not moving" isn't possible on 2.4.0.** `POWER WAKE` blocks the firmware, and wake is disabled in this setup.
- **Proposal:** measure coil EMI as **streams during a short move** (the T09.4 method: stepping coils, which is the realistic EMI case), compared with the coils released.
- A static "coils held" state goes into the optional firmware 2.5.0 list.

**D3. Stage validity.** Today every `# BOOT` rebases and keeps the position. Booting is expected on connect and `RESET`; a brown-out mid-move silently loses steps.
- **Proposal:** a `valid` flag in `lio.stage`:
  - boots the host *expects* (port open, `RESET`) keep the position;
  - an *unexpected* `# BOOT` sets `valid = false` and records it;
  - moves and scans then refuse until the top is re-established (`set-top`), or a home sensor confirms.
- P0 checks `valid`, and the executor aborts on an unexpected boot.
- This changes `stage.py` and `device.py` (small).

**D4. Simulator jog-renewal model.** It's slow and shaped wrong, as above.
- **Proposal:** in S1, model a renewal as continuing cruise, plus position as a piecewise trapezoid.
- The existing T09.6/T09.7 simulator tests stay valid.

**D5. Duty and spacing.**
- **On-time per LED.** On the rig, `SWEEP 8 4` keeps each LED on for about **86 ms**: the settle plus the lit readings, 8 ms + 2 × 4 conversions at about 9.7 ms. (The whole per-hole cycle, including the dark readings, is about 170 ms, so a `SWEEP` lasts about 2.7 s.)
- **Duty.** At heights about 6 s apart, that's ≈ 0.86 s per minute per rail A LED, just under the 1 s budget. **Repeats at the same height** (reference heights) and dense fine-mode heights will exceed it, and the duty tracker will insert waits. The plan's "≈ 0.5%" assumed 25–40 ms flashes.
- **Proposal:** default `sweep_n = 2` (≈ 47 ms on-time), and a planner that predicts the duty waits in its ETA. Waits are logged as required.

**D6. P4 "return to top" in quick mode.** It doubles the time (≈ 31 min, not 18). Options:
- **(a)** accept ≈ 31 min, and measure the 9 heights on the way up too (backlash data for free);
- **(b)** quick ends at the bottom, and its P1-vs-P4 drift uses a dark frame at the bottom plus the time trend of the dark frames, not the hole-8 response at the top.

I recommend **(a)** as the default quick check, since the extra data is nearly free once the stroke is spent anyway.

**D7. "16 extra heights around the optimum" (fine mode)** needs the optimum mid-run.
- **Proposal:** fine mode analyses the down pass when it ends (`optics.optimum`), then places the extra heights in the up pass.

**D8. Storage format.** pyarrow, pandas and scipy aren't installed or declared.
- **Proposal:** `cube.csv.gz` (plus an index file for resume), `streams/*.npz` (numpy), and numpy implementations of Savitzky–Golay and Lomb–Scargle (both short and testable).
- Alternative: add `scipy` (and optionally `pyarrow`) as an optional `scan` extra. Your call (Q6).

**D9. Test ID and kind.** T12 and T13 are both free. I'll use **T13** as the plan says. The registry has one kind per test, so T13 is kind **M** (it needs `--allow-motion`). Its automatic analysis checks are sub-results.

**D10. Operator heartbeat.**
- Browsers throttle timers in hidden tabs; Chrome drops background timers to about once a minute after 5 minutes hidden.
- A 60 s heartbeat timeout would therefore pause the run whenever the tab is hidden.
- **Proposal:** send the heartbeat from a Web Worker (much less throttled), show "keep this tab open" on the Scan tab, and make the timeout configurable (default 90 s).
- On pause, the executor stops at the next safe point: motion stopped, optics off, coils released.

**D11. Branch base.** `feature/motion-travel-tests` (firmware 2.4.0, stage, continuous motion) exists **only locally**, and it sits on `feature/structured-ingredients` (food library, pushed, not merged). A pull request from the scan work into `main` would carry both. See Q7.

**D12 (found in S2). Reference repeats ride the up pass.** Plan §3.1 lists the repeatability pairs after the up pass. Run that way, `full` took 65 min on the simulator (two extra strokes: back down to the reference heights, then up again). The up-pass heights and the reference pairs (from above, then from below, at each reference height) are now one list in height order, bottom first. Same measurements, no extra strokes: `full` takes 44 min and `fine` 52 min. Mode labels in `lio_hw.yaml` updated.

**D13 (found in S2). P4 in static mode.** `electrical` (no motion) also ends with P4 here: a drift re-measure and the single-channel interlock. Light-while-moving is SKIP there (nothing moves).

**D14 (found in S2). ADC rate changes re-read INFO.** The device's timeouts assume 128 SPS until INFO is read again. The P1 long dark record (8 SPS, 30 s) timed out. The executor now re-reads INFO after each rate change. `LIODevice` itself is unchanged: changing its default shifted catalogue timings (T07.2).

**D15 (found in S3). Coupling C is anchored on the blind channels.** Plan §6.6 takes C from a plateau where the light vanishes, else from the coupling states. In the simulator, as on the rig as far as we know, the optical response never vanishes inside the travel: far from the peak it is still about a third of the peak. And select-only carries no LED current, so it cannot show ground shift. So C per detector and rail is the median net on the holes that detector cannot see: InGaAs on 1–7, 10, 11 and 16; OPT101 on 12–16. There the LED current flows but no light is detected. The OPT101 has no blind hole on rail A, so its rail-A C is inferred from rail B by the current ratio (marked "inferred"). Select-only is reported separately, as gate-drive coupling.

**D16 (found in S3). Wavelength plausibility uses the channel map's `expect`**, not a responsivity ratio. The only responsivity tables in the config are the simulator's, and the analysis must not judge the rig by the simulator's own physics. The ratio form can follow once cited tables are added (plan §10).

**D17 (found in S3). Thresholds come from the simulator.** `scan.health` values are set between healthy and faulted simulator runs and marked provisional. Commissioning (S7) must recalibrate them, especially throughput (absolute counts) and stray light. The simulated white-tile reflectance was lowered from 1.8 to 1.5: at 1.8 a healthy white run came within 2% of InGaAs saturation, which would trip the saturation abort.

**D18 (found in S4). Mechanics are read optically, with a two-term model.** There are no home sensors, so the stage's real height is read from the response curves. The down pass is the reference: a natural cubic spline through the raw readings. Smoothing the reference, or interpolating it linearly, biased the offsets by a few hundred half-steps on the coarse quick grid. On the way up the offset is fitted as δ0 + κ·progress. Backlash is −δ0. Step loss is −κ: a side losing steps makes the offset grow as the top climbs. Both are flagged only beyond 3σ of their own resolution, which is reported. Step loss reads about 20% high when other upward moves (reference approaches) add to the loss. The P1-versus-P4 comparison at the top (plan §6.4) is reported but not judged: at the top the response is flat, so the comparison has no resolution.

**D19 (found in S4). The verdict is the T11 function, unchanged.** Findings are grouped into the catalogue modules they test (T02 link, T03 ADC, T04 addressing, T05 rails and channels, T06 detectors and power, T09 motion and stage, T10 safety, T13 optical path and run), and `overall_verdict` is applied. So a failure not tied to a channel (dark offset, ground shift, backlash) gives NOT FUNCTIONAL, as it would in the suite. An incomplete run is a WARN (DEGRADED at best). Drift needs at least 5 minutes of dark frames, otherwise SKIP.

## 4. Questions

Plan §13:
1. **Reference targets.** Is a white PTFE tile and/or a black cup available for commissioning? Without them, effectiveness is relative only, and stray light comes only from the decomposition.
2. **Routine mode.** Quick as the default, as D6(a) at about 31 min, or D6(b) at about 17 min ending at the bottom?
3. **Firmware 2.5.0** coupling states (CE-only, wrong-rail, coils-held): approve for S8? The sweep runs without them; those checks SKIP.
4. **Lead-screw pitch:** known? If so, heights are also reported in mm.
5. **A2/A3 rail and ground monitoring and home sensors:** wire them? Optional; S8.

From S0:

6. **Dependencies:** numpy-only implementations (no new dependencies), or add `scipy` (+ `pyarrow`) as an optional `scan` extra? I recommend numpy-only.
7. **Branches.** I propose to:
   - push `feature/motion-travel-tests` and open its PR (base: `feature/structured-ingredients`, or `main` once that merges);
   - stack the scan milestones on it: `feature/diagnostic-sweep-s0` … `-s6`, each PR based on the previous one.

   The alternative is to rebase the motion work onto `main` without the food-library commits, which may conflict on `CHANGELOG.md` and the shared files. Which do you prefer?
8. **Stage validity (D3):** OK to add the `valid` flag, so an unexpected boot blocks motion until the top is re-established?
9. **`sweep_n` default 2 (D5)** and heartbeat timeout 90 s (D10): OK?
