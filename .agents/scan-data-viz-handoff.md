# Research handoff: LIO scan data — what we collect & how to visualize it

**Audience:** a research / viz agent designing the best way to explore LIO diagnostic (and future food-profile) scans.  
**Repo:** https://github.com/Brandonio-c/LIO · local `LIO/` · code `software/host/src/lio/scan/`  
**Canonical docs:** `docs/DIAGNOSTIC_SWEEP.md`, `docs/DIAGNOSTIC_SWEEP_PLAN.md`  
**Example full run:** `test_results/20261119-171756_scan_full/` (sample `black_cup`, ~39 min, 2360 cube rows, 111 findings)  
**Owner prefs:** work only on `main`; see `.agents/preferences.md`.

---

## 1. What a “LIO scan” is

A **diagnostic height sweep**: the chamber head moves through its vertical travel. At programmed heights it measures **all 16 LEDs × 2 detectors** (and several electrical states). From that cube the host judges optics, electronics, ambient light, and mechanics, then writes a verdict + report.

This is **not** yet a finished “food spectrum product UI.” Food runs reuse the same scan machinery with `sample_id` = food / `LIO-F-…`. Visualization should serve:

1. **Commissioning / health** (empty, PTFE, black cup) — find faults, drift, weak channels.  
2. **Food profiles** — compare reflectance-vs-height (and derived scalars) across samples and over time.

**Geometry / units**

- Height is tracked in **half-steps from the light-tight top** (`height_hs`; top ≈ 0, deeper = more negative).  
- `height_mm` ≈ `height_hs / 4096` for M6×1.0 direct drive (`scan.lead_mm_per_rev`).  
- Detectors: **`opt101`** (Si, VIS–NIR, ADS A1) and **`ingaas`** (SWIR TIA, ADS A0).  
- ADC: **0.125 mV/count** (`MV_PER_COUNT`).  
- Holes 1–16: wavelengths / labels in `software/config/lio_hw.yaml` / `docs/OPTICAL_CHANNEL_MAP.md`. Many hole×detector pairs are **blind** (expect `none`) — do not normalize those as if they were signal.

---

## 2. Run folder layout (primary data product)

```
test_results/<YYYYmmdd-HHMMSS>_scan_<mode>/
  scan.json          # metadata, plan, health, events, streams index, resume
  cube.csv.gz        # PRIMARY TABLE: one row per reading
  streams/*.npz      # raw ADC time series (hum, EMI, long dark)
  analysis.json      # findings + explanations + health + verdict + context
  report.html        # human report (existing)
  report.md
  plots/             # existing static PNGs (see §6)
  results.json       # optional T13 wrapper for dashboard twin
```

Baselines (for compare / trend):

```
test_results/scan_baselines/<sample_id>/<run_id>.json
  → metrics, O[det][hole], curves[det][hole] = list of {h, net, …}
```

---

## 3. Modes & experimental design (what heights exist)

| Mode | Motion / sampling (approx) | Typical use |
|------|----------------------------|-------------|
| `quick_down` | ~9 heights down only | Fast check |
| `quick` | ~9 down + up | Default commissioning |
| `full` | ~33 down, ~9 up, 5 ref heights × 2 reps each side | Main profile (~44 min sim) |
| `fine` | full + dense points near optical optimum | Peak resolution |
| `repeatability` | 5 refs × 5 reps both sides | Mechanics |
| `electrical` | no motion | Bench electrical only |
| `continuous` | measure while moving (`MOTOR LIGHT 1`) | Motion coupling |

**Phases (every run)**

| Phase | Content |
|-------|---------|
| **P0** | Preflight (fw, ADC, stage, operator confirm) — little/no cube |
| **P1** | Static at one height: hum streams, **30 s long dark @ 8 SPS**, select-only / CE-only / wrong-rail states, one full LED sweep |
| **P2** | Down pass: stop → settle → dark → **SWEEP all holes** → dark; hum every Nth height; EMI streams on moves |
| **P3** | Up pass + **reference repeats** (`rep` > 0, approach from above/below) |
| **P4** | Closing re-measure + interlock re-checks |

Example `full` (`black_cup`): **63 steps**, `heights_down` n=33, up n=8, `ref_heights` five values, **2360** cube rows.

---

## 4. Primary dataset: `cube.csv.gz`

Gzipped CSV (possibly multi-member gzip). Schema (`CUBE_FIELDS`):

| Column | Meaning |
|--------|---------|
| `run_id` | Folder / run name |
| `step` | Plan step index |
| `phase` | `P1`…`P4` |
| `height_hs`, `height_mm` | Stage height |
| `direction` | `down` / `up` / `none` |
| `rep` | `0` = primary visit; `>0` = repeatability visit |
| `hole` | `1`–`16`, or `0` for dark/hum aggregate rows |
| `state` | See below |
| `detector` | `opt101` \| `ingaas` |
| `dark_counts`, `lit_counts`, `net_counts` | ADC counts; **net = lit − dark** for lit rows |
| `net_mv` | `net_counts * 0.125` |
| `t_s` | Seconds since run start |
| `duty_wait_ms` | LED duty cool-down wait before that sweep |
| `settle_ms` | Time spent settling (mech + dark-agree) before measure |
| `n` | Samples averaged in MEAS/SWEEP (`sweep_n`, default 2) |

**`state` vocabulary**

| state | What it is |
|-------|------------|
| `lit` | Normal dark-then-lit MEAS/SWEEP (main optical signal) |
| `dark` | Dark frame (hole often `0`) |
| `select_only` | MOSFET selected, CE low — coupling without intended light |
| `ce_only` | CE high, nothing selected (`rep` encodes rail) |
| `wrong_rail` | Hole selected on other rail’s CE — must stay dark |
| `coils_off` | Hum / noise with motors released (often hole `0`) |
| `coils_moving` | EMI while stepping (streams; may appear in meta) |

**How to think about the lit cube for viz**

- Core tensor-like object: **`(detector, hole, height, direction[, rep]) → net_counts`**.  
- Dashboard live UI and `plots/heatmap.png` already treat this as **hole × height heatmaps**, one per detector, typically **down-pass `lit`**.  
- Blind hole×detector cells should stay blank / NaN (existing report does this).  
- Color scale: net counts, often scaled per-detector to the strongest reading so far (dashboard) or vmax = max finite (report).

**Scale reference (example full black_cup run)**

- ~2016 `lit` rows, ~252 `dark`, plus coupling states.  
- Equal rows for `opt101` and `ingaas`.

Loader: `lio.scan.analysis.data.Cube` (masks, `.curve(hole, det)`, darks, streams).

---

## 5. Streams: `streams/*.npz`

Compressed NumPy archives with:

- `t_us`: int64 timestamps (µs, run-relative / burst-stitched)  
- `raw`: int32 ADC raw counts  

Indexed in `scan.json` → `streams[]` with `name`, `file`, `state`, `detector`, `height_hs`, `rate_setting`, …

**Kinds**

| Name pattern | Purpose | Typical length |
|--------------|---------|----------------|
| `long_dark_{det}.npz` | P1 30 s dark @ 8 SPS | e.g. 240 samples |
| `sNNN_coils_off_{det}.npz` | Mains hum, coils off (multi-burst @ 860 SPS) | e.g. 816 |
| `emi_*_{det}.npz` / `*_coils_moving_*` | Coil EMI during moves | bursts |
| continuous-mode streams | If mode=`continuous` | varies |

**Viz value:** spectra (60/120/180 Hz), spectrograms, compare coils_off vs coils_moving, long-dark drift/leak vs time. Existing `plots/spectra.png` covers a static summary.

---

## 6. Derived products already on disk

### `analysis.json`

```json
{
  "run_id", "sample_id", "mode", "status",
  "verdict": { "verdict": "FUNCTIONAL|DEGRADED|NOT FUNCTIONAL", "reasons", "modules" },
  "health": [ { "subsystem", "status": "OK|WATCH|ACT|n/a", "reason" } ],
  "findings": [ Finding, ... ],
  "context": { "electrical", "optics", "reference" }
}
```

**Finding** (typical): `id`, `title`, `status` (PASS/WARN/FAIL/SKIP/ERROR), `value`, `unit`, `detail`, `criteria`, `data` (e.g. `O`, `C`, `modulation`, `fwhm_hs`, `h_opt`), optional `explanation` `{cause, parts, check}`.

Finding id prefixes (example full run counts): `optics` ≫ `elec` > `system` > `mech` > `ambient`.

**Optics scalars of interest for food viz** (per hole × detector, when meaningful):

- **O** — optical amplitude ≈ S(h_opt) − C (coupling)  
- **C** — electrical coupling estimate  
- **modulation** — height dependence (flat ⇒ not optical)  
- **FWHM**, **h_opt** — peak location / width  
- **SNR**, saturation headroom  
- **plausibility** — detector responding where it shouldn’t  

**Electrical / ambient / mech:** coupling, ground shift, dark offset, drift, hum, coil EMI, select-only / wrong-rail, shroud leak vs height, backlash / step loss / repeatability / settle / lockstep / travel, duty, interlocks.

### `plots/` (current static set)

| File | Content |
|------|---------|
| `heatmap.png` | Hole × height net, down pass, both detectors |
| `curves.png` | Per-hole response vs height; down solid / up dashed |
| `dark.png` | Dark vs height (leak) and vs time (drift) |
| `spectra.png` | Mains / noise spectra |
| `control.png` | Present when baselines exist (control charts) |

Regenerate: `lio scan analyse <run>` then `lio scan report <run>`.

### Dashboard live viz

Scan tab: progress + **live hole×height heatmap per detector** while the run appends cube rows. Twin colors from T13 findings after load.

### Scan baseline JSON

Compact: per-hole **O**, downsampled **curves**, selected **metrics** for trend / EWMA when ≥5 baselines of same `sample_id`.

---

## 7. What “food profile” data looks like

Same schema as above. Differences are mostly **interpretation**:

- Absolute O thresholds are often **SKIP** for non-judged samples (e.g. `black_cup`); food may be judged vs **same-sample baseline** / PTFE effectiveness / black_cup stray, not empty absolute floors.  
- Scientifically useful food features from one full scan:  
  - **Spectral vector** at optimum height: net or O per hole (and per detector).  
  - **Curve shape** vs height per hole (scattering / fill / geometry).  
  - **Down vs up** hysteresis (mechanics + sample settle).  
  - Ratios (e.g. InGaAs/OPT101 on shared holes 8–9).  
- Cross-sample compare needs consistent packing, nest, lid, and preferably a saved **empty** (and PTFE) scan baseline.

Suite YAML baseline (`software/config/baseline_*.yaml`) is **not** a height-sweep profile — it is single-height channel nets for T11 drift. Do not use it as the food viz primary.

---

## 8. Visualization research brief (what to investigate)

### Must-have views (extend or replace current PNGs)

1. **Interactive hole × height heatmaps** (both detectors), brush height, toggle down/up/rep, logarithmic / per-row normalize, mask blinds.  
2. **Spectral strip / parallel coordinates** at chosen height or at each hole’s `h_opt`: 16 channels × 2 detectors.  
3. **Small-multiples curves** S(h) with down/up overlay + coupling C annotation.  
4. **Finding overlay**: click FAIL/WARN → jump to hole/height/stream.  
5. **Compare mode**: run A vs B, or run vs scan baseline (ratio heatmap, ΔO bar chart).

### High-value extras

6. **3D / surface:** height × wavelength × net (careful with dual detectors and blind cells).  
7. **Stream explorer:** FFT / spectrogram for hum & EMI; long-dark time series.  
8. **Trajectory:** stage height vs time with measure markers (debug motion + duty waits).  
9. **Food library gallery:** thumbnail heatmap + O fingerprint per sample_id.  
10. **Trend dashboard:** EWMA / ±3σ once ≥5 baselines (plan already specifies this).

### Constraints / pitfalls for viz design

- Dual detectors have **different dynamic ranges and blind patterns** — never one shared scale without labeling.  
- `net_counts` can be weak/negative on SWIR at sealed top; full travel matters.  
- Repeats (`rep>0`) are for mechanics — mixing them into a single heatmap without separation confuses optics.  
- Cube is modest (~2–10k rows); streams are the heavy part — lazy-load NPZs.  
- Prefer open formats (Parquet/Arrow export of cube) if building a heavier app; today CSV.GZ + NPZ is source of truth.  
- Existing matplotlib report is the baseline UX to beat, not discard (reproducible `lio scan report`).

### Suggested evaluation criteria for “best” viz

- Time-to-insight for “is hole 14 dead or weak?”  
- Time-to-insight for “how does flour A differ from flour B?”  
- Faithfulness to blinds / expect map  
- Works offline from a run folder alone (`scan.json` + `cube.csv.gz` + optional `analysis.json`)  
- Can grow into food-library browsing without a second data model  

### Implementation sketch (non-binding)

- **Notebook / Panel / Streamlit / Observable** prototype reading `Cube` or pandas from `cube.csv.gz`.  
- Or **enhance dashboard Scan tab** with post-run explorer (already has live heatmap + report link).  
- Keep analysis in Python (`analyse` / findings); viz should consume **cube + analysis.json**, not re-implement physics.

---

## 9. How to load data quickly (for the research agent)

```python
from pathlib import Path
from lio.scan.analysis.data import Cube

folder = Path("test_results/20261119-171756_scan_full")
cube = Cube.open(folder)          # wraps ScanStore; .meta, .curve(), .mask(), …
# c = cube.curve(8, "opt101")   # → .h (heights), .net (net_counts), …

import pandas as pd
df = pd.read_csv(folder / "cube.csv.gz", compression="gzip")
lit = df[(df.state == "lit") & (df.phase == "P2") & (df.rep == 0)]
```

CLI: `lio scan analyse <run>`, `lio scan report <run>`, `lio scan compare <a> <b>`, `lio scan baseline list`.

---

## 10. Related agent context

- `.agents/project-state.md` — rig FUNCTIONAL; food collection OK with caveats  
- `.agents/baselines.md` — suite vs scan baselines  
- `.agents/workflows.md` — how to run scans  
- `.agents/known-issues.md` — weak InGaAs, h16, duty accounting, stage WARN  

**Bottom line for the research agent:** the atomic scientific table is **`cube.csv.gz` (lit net vs height × hole × detector)**; streams add EMI/hum; `analysis.json` adds judged scalars and fault narrative; existing heatmaps/curves/reports are the MVP. Design viz that makes **spectral fingerprints + height response + run compare** immediate for both health and food profiles.
