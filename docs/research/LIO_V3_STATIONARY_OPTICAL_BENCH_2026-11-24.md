# LIO V3 stationary optical bench: h8/h12 target dependence and ambient pickup

**Bench session 24 November 2026, 01:30–01:45 EST.** Repository `main` at `fe1d1d6` (clean),
run with the editable conda `lio` environment (Python 3.12.11) from that checkout; loaded-build
identity is recorded in every `scan.json` (`software`) and in `ambient_dark.json`. Port
`/dev/cu.usbmodem101`, firmware 2.5.2, `hw_wdt=0`, admission `cooperative_unproven`
(owner-acknowledged; no finite firmware-hang bound). Evidence folder:
[`test_results/bench_20261124_stationary/`](../../test_results/bench_20261124_stationary/).

Detectors, head position, wiring, LED currents, gain and optics were **not changed**. No motors,
scans, firmware, code or stage edits. The dashboard was released through its own API
(`/api/disconnect`: OFF/STOP, port closed); its process was left running, disconnected.

## 1. Bottom line

The mounted InGaAs **does detect repeatable, strongly target-dependent light on h12 (1450 nm)
and h8 (850 nm)**: on white printer paper h12 InGaAs reads **71.1 ± 0.9 counts (SD, n = 12)**,
on the black cup **11.5 ± 1.6**; difference **+59.6 counts (95 % Welch 58.5..60.7)**. The
silicon OPT101 shows no h12 response on either target (1.3 vs 1.6), as expected outside its
range. **Room lighting does not change the InGaAs dark level or its noise** (σ ≈ 30–34 counts in
every state), so its high noise is not ambient light leaking through the unsealed LED tops; the
OPT101 shows a small, reversible ~1-count ambient leak. The weak SWIR seen in empty-chamber runs
is therefore consistent with **little light coming back from an empty/dark sample plane**, not a
dead or misaimed InGaAs path. This is not calibrated reflectance, photocurrent or SWIR chemistry.

## 2. Design actually used (frozen before data) and deviations

Frozen in `DESIGN_FROZEN.json` before any measurement.

| Item | Planned (prompt) | Used | Reason |
|---|---|---|---|
| Optical blocker pairs (D = unblocked − blocked) | 6 pairs/hole | **Not run** | Owner: no blocker can be inserted ("i cant"). No blocked steps were recorded without a blocker. |
| Diffuse reference run | 6 pairs/hole | **12 fixed readings/hole**, one condition, start checkpoint | Same 24 MEAS / 1.984 s nominal light |
| Black target | same surface plane | **Black collection cup** | Owner's available black target; **not the same surface plane** as the paper |
| Settings | gain 1, settle 8 ms, 60 Hz × 2 periods | Same; preflight readback gain 1, rate 128, mains 60 | — |
| Order | h8 then h12 | h8 ×12 then h12 ×12 | h8 is not a simultaneous drift monitor |
| Caps | finite | wall 1800 s, total on 6000 ms per run | — |
| Ambient | ON/OFF/ON, fixed count | 3 records × 64 samples per detector per state, LEDs off, CE verified low | — |

Checkpoints: every physical state (3 ambient states, 2 run starts) was confirmed by the owner for
that occurrence; each answer was delivered as one line to the waiting process only after it was
given (`checkpoint_history.txt`). No `--yes`, scripted or reused answers.

## 3. Results

### 3.1 Stationary runs (signed lit − dark nets, counts; fixed N = 12 each)

| Run | Hole / detector | Mean | SD | 95 % interval (qualified-v2) | Raw nets |
|---|---|---|---|---|---|
| White paper `20261124-014043_scan_protocol` | **h12 InGaAs** | **71.08** | 0.90 | 70.51..71.66 | 71 70 71 70 71 72 71 70 71 73 71 72 |
| | h8 InGaAs | 146.25 | 1.14 | 145.53..146.97 | 146 144 145 146 145 147 147 147 148 147 147 146 |
| | h8 OPT101 | 975.00 | 2.00 | 973.73..976.27 | 971–979 |
| | h12 OPT101 | 1.33 | 0.65 | 0.92..1.75 | 1–3 |
| Black cup `20261124-014245_scan_protocol` | **h12 InGaAs** | **11.50** | 1.57 | 10.50..12.50 | 10 12 11 13 11 14 11 9 14 12 10 11 |
| | h8 InGaAs | 26.42 | 2.02 | 25.13..27.70 | 23–30 |
| | h8 OPT101 | 148.83 | 3.35 | 146.70..150.96 | 142–153 |
| | h12 OPT101 | 1.58 | 0.67 | 1.16..2.01 | 0–2 |

Both runs COMPLETE, terminal seals written, exposure reserved 2208 ms / actual 2016 ms / uncertain
0 ms each. qualified-v2: C = null for both detectors (no eligible controls); verdict UNRESOLVED
(no declared contrasts in a single-condition run), as expected.

### 3.2 Target dependence (white − black cup) — **exploratory, cross-run**

Not covered by a within-run frozen family. Welch intervals; Bonferroni over the 4
hole/detector comparisons declared in `DESIGN_FROZEN.json`.

| Hole / detector | Difference | SE | 95 % | Bonferroni (4) |
|---|---|---|---|---|
| **h12 InGaAs** | **+59.58** | 0.52 | +58.49..+60.68 | +58.13..+61.03 |
| h8 InGaAs | +119.83 | 0.67 | +118.42..+121.24 | +117.97..+121.70 |
| h8 OPT101 | +826.17 | 1.13 | +823.80..+828.53 | +823.04..+829.29 |
| h12 OPT101 | −0.25 | 0.27 | −0.81..+0.31 | −0.98..+0.48 |

### 3.3 Source-off ambient (LEDs off, CE verified low; 3 × 64 samples per state)

| Room lights | InGaAs mean | InGaAs SD per record | OPT101 mean | OPT101 SD |
|---|---|---|---|---|
| ON | −330.7, −331.1, −331.1 | 29.6, 29.4, 32.8 | 56.3, 56.2, 56.2 | 0.37–0.45 |
| OFF | −330.8, −330.8, −330.7 | 30.4, 30.8, 34.0 | 55.2, 55.2, 55.3 | 0.38–0.48 |
| ON | −330.5, −330.6, −331.2 | 34.0, 31.7, 34.0 | 56.2, 56.2, 56.2 | 0.42–0.44 |

Raw streams at the configured 128 SPS (aliased mains content); not comparable to
mains-integrated MEAS precision.

## 4. Established, confounded and unknown

**Established (this setup):**
- h12 and h8 InGaAs readings are **repeatable at the count level** (SD 0.9–2.0, n = 12) under
  mains-integrated MEAS, despite the ~30-count raw dark noise.
- They are **strongly target dependent** (white ≫ black cup) while h12 OPT101 is not: an
  electrical pickup that ignores the target cannot produce this pattern.
- Room lighting does **not** measurably affect InGaAs dark level or noise; OPT101 sees ~1 count.

**Confounded / not established:**
- No optical blocker: within one target, optical return versus LED-current-synchronous pickup is
  not separated. The black-cup residual (h12 11.5, h8 26.4) may be light from the cup, stray
  light, or electrical; it is unknown.
- The black cup is **not at the paper's surface plane** and has different shape/height, so the
  difference mixes reflectance and geometry. Visible blackness ≠ SWIR blackness; white paper is
  not a calibrated SWIR standard.
- Runs were 2 minutes apart in fixed order (white then black): drift/order not controlled.
- Rf 2 MΩ / ~30 mA are owner-declared; YAML still says 1 MΩ / B 45 mA. No physical units claimed.

**Unknown:** the InGaAs noise source (not ambient; electrical candidates remain), calibrated
reflectance, field of view and illumination overlap.

## 5. Does anything justify an InGaAs-only mounting change?

**No.** The current mount returns 71 counts at 1450 nm from white paper with ~1-count
repeatability, and a clear target contrast. The earlier "no SWIR" impression came from
empty/dark sample planes. Moving the detector could gain signal but is not indicated by these data
and would invalidate the comparison with this baseline.

## 6. Refusals and skips

- Blocked/unblocked pairs: skipped (no blocker available).
- T05.5 precision-2: skipped: its caller illuminates every expected hole, outside the h8/h12 scope.
- Full catalogue, height scans, h16: not run (out of scope).
- No refusals, timeouts or incomplete runs occurred.

## 7. Next single useful experiment

Repeat the **white-paper vs black-target** comparison with a **flat matte black card at the
same surface plane as the paper**, alternating targets W-B-W-B (two runs each) so drift and
order are bounded, and add an opaque non-conductive blocker if one can be made (e.g. a printed
black PETG slide) to separate optical return from electrical pickup on each target.

## 8. Commands, identities and hashes

```text
lio scan plan --protocol protocols/white_paper.json --json protocols/white_paper_plan.json
lio scan plan --protocol protocols/black_cup.json   --json protocols/black_cup_plan.json
POST /api/disconnect   (dashboard, graceful port release)
python -u ambient_dark.py /dev/cu.usbmodem101   (answers via tail -f ambient_answers.txt)
lio --port /dev/cu.usbmodem101 scan run --protocol protocols/white_paper.json --allow-light \
    --sample white_paper_on_tray --out runs        (answer via tail -f white_answers.txt)
lio --port /dev/cu.usbmodem101 scan run --protocol protocols/black_cup.json --allow-light \
    --sample black_cup --out runs                  (answer via tail -f black_answers.txt)
lio scan analyse runs/<RUN> --model qualified-v2 --derived-out derived
lio scan report  runs/<RUN> --analysis <ID> --derived-out derived
```

| Item | Value |
|---|---|
| White run / analysis | `20261124-014043_scan_protocol` / `7e18a55f4fee916e`; source tree hash before = after `5b83c958751bc572` |
| Black run / analysis | `20261124-014245_scan_protocol` / `370fc49e8f6adc54`; before = after `abcef6884279d7ec` |
| Exploratory comparison | `cross_run_exploratory.json` |
| Ambient | `ambient_dark.json`, `ambient_console.log` |

Opening the port through the CLI attaches the physical stage tracker, which logs a boot rebase
(absolute position unchanged); no stage position was edited.

**No calibrated photocurrent/reflectance, measured SNR improvement, recovered SWIR chemistry or
1850 nm claim. h16 was not illuminated.**
