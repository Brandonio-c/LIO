# Research handoff: extract more from existing LIO sensors (software-first)

**Date:** 23 November 2026  
**From:** engineering session after visible-LED replace + `20261123-003133_scan_quick`  
**Repository:** https://github.com/Brandonio-c/LIO — local clone `/Users/coleloughbc/Documents/VSCode-Local/LIO`  
**Data on GitHub:** historical `test_results/` (scans, `tray_v3/` artifacts, corpora) are **tracked on `main`**. See `test_results/README.md`. Only `test_results/stage_position.json` remains local/gitignored.  
**Branch rule:** work conceptually on `main` knowledge; do **not** flash firmware, move motors, light LEDs, or change wiring unless the hardware owner explicitly authorizes a bench session.

---

## 1. Your task

You are a **research agent**. Produce a grounded assessment and plan for:

> **Given only the hardware we already have** (16 ring LEDs, OPT101, InGaAs+TIA, ADS1115, Nano R4 firmware, host scan/analysis stack), is there a **more optimal way to collect and analyse** readings so we get more scientifically useful information — especially for weak / out-of-band channels (SWIR 12–15, and hole 16 / 1850 nm via any secondary emission OPT101 can see)?

Deliverables (research only unless later authorized to implement):

1. **Physics / information-theory bound:** what each detector can and cannot measure for each hole (primary λ vs secondary glow vs electrical coupling).
2. **Software-only opportunities:** collection parameters, estimators, models, and diagnostic reinterpretations that do not require new parts.
3. **Hybrid opportunities:** small config/threshold changes vs real optical/electrical fixes (aim, Rf already changed, current pots, LED replace) — ranked by expected information gain.
4. **Explicit no-gos:** things that look like “more signal” but are not spectral information about the sample at the nominal LED wavelength.
5. **Recommended experiments** (protocol + which existing CLI/dashboard commands) the owner can run later to validate your proposals.

Do **not** treat the hole-16 OPT101 residual as proof that OPT101 “sees 1850 nm.” Treat it as a candidate **secondary emission / phosphor / package glow / crosstalk** proxy unless you prove otherwise from datasheets + height-dependent optical decomposition already in the code.

---

## 2. Direct engineering question that triggered this handoff

### 2.1 Observation

Hole 16 is mapped as **1850 nm**, beyond both detector ranges in config:

- OPT101 silicon responsivity model → 0 by ~1150 nm (`lio_hw.yaml` `sim.responsivity.opt101`)
- InGaAs model → 0 by ~1800 nm (`sim.responsivity.ingaas`); photodiode MTPD1346D-100 roughly **800–1750 nm**

Yet every recent diagnostic scan shows a **large, height-dependent OPT101 residual on hole 16** (~400–700 counts historically; **+389** on `20261123-003133_scan_quick`). Soft-verdict currently emits:

`optics/opt101/h16/plausibility` **WARN** — “detector responds to a hole whose wavelength it cannot see → swapped / wrong part.”

### 2.2 Owner clarification

The owner reports hole 16 **was** swapped and has been corrected with a part they believe is genuinely **1850 nm**. The WARN is **not new**: the same OPT101 residual existed on **FUNCTIONAL** runs (e.g. `20261119-152512`, `20261120-012619`).

### 2.3 Research ask

If that OPT101 light is real optical return from secondary emission of the 1850 package (or phosphor/leak), can we:

- **use OPT101 deliberately** as a proxy channel for “hole 16 alive / aligned / sample-modulated”?
- improve **collection or analysis in software** so we get more from OPT101 + InGaAs without new detectors?

**Constraint to keep honest:** secondary visible/NIR glow is **not** water/fat absorption at 1850 nm. It may still be useful for **diagnostics, presence, crude scatter geometry**, and maybe a weak correlated feature — research must separate those uses.

---

## 3. What the instrument is (scanning apparatus)

LIO V3 = open-hardware **multispectral diffuse-reflectance** scanner for powdered food (and empty / PTFE / black-cup diagnostics).

### 3.1 Optical geometry

- **16 LEDs** in a ring around a sample chamber; **exactly one LED** lit at a time; only that LED’s **rail CE** enabled.
- **Two detectors** under the deck, looking up at the sample / chamber top:
  - **OPT101** (CJMCU-101, internal 1 MΩ feedback jumper) → ADS1115 **A1**
  - **InGaAs** photodiode **MTPD1346D-100** + **TL072** TIA (±5 V) → ADS1115 **A0** (10 kΩ series)
- **Motorised chamber top** (two 28BYJ-48 + ULN2003, M6×1.0 leadscrews, **4096 half-steps = 1 mm**). Height sweep changes return geometry. Soft limits via `lio.stage` (no hard limit switches).

### 3.2 Channel map (authoritative: `software/config/lio_hw.yaml`)

| Hole | Label | λ (nm) | Rail | Expected detector(s) |
|-----:|-------|-------:|:----:|----------------------|
| 1 | 395 | 395 | A | OPT101 |
| 2 | purple | ~405 | A | OPT101 |
| 3 | blue | ~465 | A | OPT101 |
| 4 | green | ~525 | A | OPT101 |
| 5 | yellow | ~590 | A | OPT101 |
| 6 | orange | ~605 | A | OPT101 |
| 7 | red | ~630 | A | OPT101 |
| 8 | 850 | 850 | A | OPT101 + InGaAs (cross-cal) |
| 9 | 940 | 940 | B | OPT101 + InGaAs (cross-cal) |
| 10 | white | 450+phosphor | B | OPT101 |
| 11 | pink | 450+phosphor | B | OPT101 |
| 12 | 1450 | 1450 | B | InGaAs |
| 13 | 1550 | 1550 | B | InGaAs |
| 14 | 1650 | 1650 | B | InGaAs |
| 15 | 1760 | 1760 | B | InGaAs **weak** (cutoff) |
| 16 | 1850 | 1850 | B | **none** (beyond both; absence never FAIL; unexpected optical residual → WARN) |

**Rails / drive (as of late Nov 2026):**

- **DRV1 / RAIL A** holes 1–8: target **~30 mA** (LD06AJSA floor; LEDs rated ~20 mA → duty-limited).
- **DRV2 / RAIL B** holes 9–16: config nominal 45 mA / `safe_max` 50; owner intending **~30 mA** after killing visibles at 50 mA.
- Firmware **cannot clamp** pot current; `lio drive-tune` coaches pots with OPT101 + optional ammeter.

### 3.3 Electronics summary

Sources of truth: `electronics/data/{netlist,bom,nano_pinmap,channel_map}.csv`, `docs/OPTICAL_CHANNEL_MAP.md`, `docs/HARDWARE_INVENTORY.md`, `electronics/docs/LIO-ELEC-001_*`.

- Controller: **Arduino Nano R4** (also builds for classic Nano).
- LED select: 2× **74HC595** → **2N7000** + 220 Ω gate + 10 kΩ pulldown.
- ADC: **ADS1115** @ 0x48 on **software I²C D11/D12**.
- Power: +5 V / −5 V supplies; circuit GND earthed (hum reduced historically but InGaAs hum can still FAIL).
- InGaAs **Rf**: config still lists `rf_ohm: 1.0e6`; bench work Nov 21 used **Rf = 2 MΩ**. Treat yaml as stale until reconciled — research should note gain implications (×2 photocurrent→voltage, more noise/hum sensitivity).

### 3.4 Critical empirical fact (LEDs vs mounted coupling)

`test_results/tray_v3/INGAAS_REMOUNT_DEPTH_CHECK.json` (Rf=2 MΩ):

- **Handheld** InGaAs close to LEDs: huge nets (e.g. h8≈7909, h9≈16890, h12≈4107, h16≈7965).
- **Mounted** detector in deck: nets near noise for many SWIR holes.

**Interpretation for research:** many SWIR emitters **do emit**; the mounted path often **does not collect** enough photons. Software cannot invent SWIR sample absorbance that never reached the diode. Software *can* improve SNR, coupling diagnostics, and use of whatever *does* reach OPT101/InGaAs (including secondary glow).

---

## 4. Firmware & host measurement capabilities (what we can already do)

### 4.1 Protocol primitives (`docs/PROTOCOL.md`, firmware ≥ 2.5.x)

| Capability | Command / feature | Notes |
|------------|-------------------|-------|
| Dual-detector dark/lit | `MEAS <hole> [settle_ms] [n]` | Returns `dark0,dark1,lit0,lit1` (InGaAs, OPT101) |
| Full ring | `SWEEP [settle_ms] [n]` | 16× MEAS |
| Averaging | `n` up to **64** (meas_n_max) | Plain mean, or mains-period integral |
| Mains nulling | `ADC CFG MAINS 60` | fw ≥ 2.5.1; dark−lit cancels 60/120/180 Hz |
| ADC PGA / rate | `ADC CFG GAIN`, `ADC CFG RATE` | 8…860 SPS; gain changes LSB |
| Streaming | `ADC STREAM` | up to 2000 samples; optional LED on/off indices |
| Coupling states | `DBG STATE CE_ONLY` | rail enable, no LED — electrical coupling C |
| Motion + measure | `MOTOR LIGHT 1` | continuous height profiles |
| Duty / WDT | rail watchdogs | A shorter than B; host also budgets on-time |
| Solid hold | dashboard / `led_hold` | renew within WDT for pot/aim work |

**Derived quantity used everywhere:**  
`net = lit − dark` per detector. Scan analysis further decomposes height curves as approximately **`S(h) ≈ O·g(h) + C`** (`lio/scan/analysis/optics.py`, electrical coupling from blind channels).

### 4.2 Diagnostic height sweep (`lio scan`, dashboard T13)

Config: `lio_hw.yaml` → `scan.*`. Modes: `quick`, `full`, `fine`, `electrical`, `continuous`, `repeatability`, …

Typical quick: **9 heights down + same up**, `optical_settle_ms: 8`, `sweep_n: 2`, `mains_hz: 60`, `mains_periods: 2`, hum bursts every k heights.

Outputs under `test_results/<run_id>_scan_<mode>/`:

- `scan.json`, `cube.csv.gz`, `streams/`, `analysis.json`, `report.md` / `report.html`, plots

Analysis packages: `lio/scan/analysis/{optics,electrical,mechanics,ambient,trend,system}.py`.

### 4.3 Soft-verdict / health knobs (already software)

Provisional thresholds in `scan.health` — especially:

- `optics.min_signal_counts`, `plausibility_counts`, `modulation_min`
- `optics.throughput_counts` per sample type
- `hum_mv` / `hum_fraction_warn`
- `trend.ratio_change`
- channel `expect: signal|weak|none` per detector

**Hole 16 policy today:** `expect: {}` → no FAIL for absence; unexpected height-dependent residual → **WARN** (assumes wrong LED). Research may propose reclassifying residual as **expected secondary** if evidence supports it.

### 4.4 Food / profile stack (downstream of healthy spectra)

- Food library + phone intake (`foods.*`)
- Spectral scans with repeats (`foods.scan_repeats`)
- `lio food_profiles` / dashboard Explore–Compare–Food Map (`docs/FOOD_PROFILES.md`, `docs/FOOD_PROFILE_AGENT_HANDOFF.md`)

Research on “more from sensors” should say what features become usable **before** claiming food-classification value.

### 4.5 Host CLI surface

`lio` subcommands: `ports, info, status, ping, ch, off, meas, sweep, watch, drive-tune, stage, motor, selftest, report, shell, dashboard, profiles, scan, bench`.

Simulator: `--sim` / `--fault …` for offline method development.

---

## 5. Current rig state (as of 2026-11-23) — facts for the research

### 5.1 Latest empty quick scan

**Run:** `test_results/20261123-003133_scan_quick`  
**Verdict:** **NOT FUNCTIONAL**  
**Reasons:** unattributed **T13.T06** (electrical / InGaAs path) + **failing channels 12, 13, 14**.

| Class | Items |
|-------|--------|
| FAIL | InGaAs h12/h13/h14 response; InGaAs throughput (CV 163%); InGaAs mains hum 6.35 mV@60 Hz; trend vs `20261116-202110` |
| WARN | OPT101 & InGaAs h16 plausibility; optimum at end of travel; M1/M2 travel mismatch |
| PASS (important) | **All OPT101 holes 1–11**; InGaAs **h8 & h9**; addressing; rails; OPT101 throughput |

### 5.2 Visible LEDs

Owner replaced visibles; confirm sweep `test_results/tray_v3/LED_CONFIRM_SWEEP.json` showed **no OPT101-dead** holes 1–11 at ~30 mA (many “weak” vs bright threshold).

### 5.3 History that matters for 12–14 (sensor vs LED)

| Era | InGaAs 12 / 13 / 14 | InGaAs 8 / 9 |
|-----|---------------------|--------------|
| Nov 19–20 FUNCTIONAL | **strong / OK** | OK |
| Nov 21 remount/boost / LED crisis | collapsed | partial |
| Nov 23 after visible replace | **FAIL** | **better (~47/46)** |

So InGaAs **front-end is not globally dead**. 12–14 regression is **channel- or coupling-specific**. Handheld data shows those LEDs can still produce large close-range photocurrent.

### 5.4 Hole 16 OPT101 residual

Persistent across FUNCTIONAL and NOT FUNCTIONAL runs → not explained solely by “operator just swapped wrong.” Candidate mechanisms for research:

1. True **secondary visible/NIR emission** from 1850 die/package (common in IR LEDs).
2. **Phosphor / encapsulant** fluorescence under IR drive (less common but check part).
3. **Optical crosstalk** from another hole (addressing PASS argues against simultaneous light, but scattered return paths exist).
4. **Electrical coupling C** — analysis already separates via modulation + blind-channel C; report claims height-dependent (**optical**).
5. Wrong part still installed (owner disputes).

---

## 6. Research hypotheses (software-relevant)

### H1 — OPT101-as-proxy for hole 16 (diagnostics only)

**Claim:** Height-dependent OPT101 net on h16 is usable as:

- LED-alive / MOSFET-alive check for hole 16  
- crude geometry / sample-scatter proxy (empty vs PTFE vs food)  
**not** as 1850 nm absorbance feature for chemistry.

**Software changes to evaluate:**

- Change `channels[16].expect` to e.g. `{opt101: weak}` or a new expect class `secondary` so WARN becomes expected.
- Add finding `optics/opt101/h16/secondary` with its own floors.
- Compare O_opt101(h16) vs O_opt101(h10/h11) and vs sample id — is it sample-modulated or only emitter-glow into the chamber?

### H2 — Better estimators without new photons

Within existing MEAS/SWEEP/scan:

- Longer `settle_ms` / more `mains_periods` / more repeats at optimum height only (duty-aware).
- Per-hole adaptive n (spend budget on weak SWIR, not on strong pink).
- Optimal height first (fine/extra_near_optimum) then stare — current quick peak is **at travel end** (−70 mm): geometry may be leaving SNR on the table.
- Lock-in / synchronous demod beyond dark−lit (STREAM with on/off indices) for weak InGaAs.
- Gain change on ADS1115 for InGaAs only (if headroom allows) — firmware supports PGA; host may not yet orchestrate per-detector gain.
- Use **both** detectors on dual-expect holes (8/9) for cross-calibration and drift correction of weaker channels.
- Multivariate use of full height curves `g(h)`, not only scalar O (food_profiles already explores related ideas).

### H3 — Reinterpret 12–14 failures

Software cannot fix missing photons, but analysis can:

- Distinguish **dead LED** vs **aim** vs **hum-dominated** using: modulation, FWHM, handheld-vs-mounted ratios already on disk, OPT101 residual≈0 (argues against visible-LED-in-SWIR-hole), rail-B CE/coupling tests.
- Propose a “SWIR coupling score” from h8/h9 InGaAs vs h12–14 ratios vs historical FUNCTIONAL baselines.

### H4 — What software cannot do

- Recover true **1850 nm** sample chemistry from silicon secondary glow.
- Replace InGaAs spectral coverage with OPT101.
- Undo LED death or wrong rail wiring by averaging.
- Ignore duty/WDT/thermal limits on overdriven 5 mm LEDs.

---

## 7. Suggested research method

1. **Literature / datasheets:** OPT101 spectral response; MTPD1346D-100; typical 1850 nm LED visible leakage; diffuse reflectance NIR/SWIR food sensing (existing `docs/research/` if present).
2. **Offline data audit:** re-analyse cubes in `test_results/*_scan_*` — especially FUNCTIONAL Nov 19–20 vs Nov 23 — for h16 OPT101 O, modulation, sample dependence; h12–14 InGaAs trajectories.
3. **Simulator probes:** `lio --sim` faults (`dead_channel`, etc.) to see how proposals interact with soft-verdict.
4. **Design A/B collection protocols** as yaml overrides (`lio scan run --set …`) without claiming they are implemented until owner asks.
5. **Rank interventions:**
   - A. Config/expect/threshold only  
   - B. Host analysis / feature changes  
   - C. Collection schedule changes (still software)  
   - D. Requires bench (aim, Rf yaml sync, pot, LED replace, earth)

---

## 8. Key files to read (priority order)

| Priority | Path | Why |
|---------:|------|-----|
| 1 | `software/config/lio_hw.yaml` | channels, expect, scan modes, health thresholds, responsivity curves |
| 2 | `software/host/src/lio/scan/analysis/optics.py` | O, C, modulation, plausibility |
| 3 | `software/host/src/lio/scan/analysis/electrical.py` | coupling, hum |
| 4 | `docs/PROTOCOL.md` | MEAS/SWEEP/MAINS/STREAM limits |
| 5 | `docs/OPTICAL_CHANNEL_MAP.md`, `docs/DIAGNOSTIC_SWEEP.md` | apparatus intent |
| 6 | `test_results/README.md` then `test_results/20261123-003133_scan_quick/analysis.json` | **on GitHub `main`** — latest soft findings |
| 7 | `test_results/20261120-012619_scan_quick/` | **on GitHub** — last strong empty FUNCTIONAL baseline |
| 8 | `test_results/tray_v3/INGAAS_REMOUNT_DEPTH_CHECK.json` | **on GitHub** — handheld vs mounted proof |
| 9 | `test_results/tray_v3/LED_CONFIRM_SWEEP.json` | **on GitHub** — post-replace LED alive map |
| 10 | `test_results/tray_v3/INGAAS_BOOST_INTEGRATION_CHECK.json` | **on GitHub** — longer integration ≠ enough |
| 11 | `docs/handoffs/2026-11-16_research_handoff_diagnostics_dashboard.md` | prior research context |
| 12 | `docs/FOOD_PROFILE_ANALYSIS_PLAN.md` | what “more signal” must feed |

Pull/clone `main` and read these paths in-repo; they are no longer bench-Mac-only.

---

## 9. Constraints & safety

- **Main-only** repo discipline; no invented operator confirmations.
- Do not raise LED current in software narratives as a free lunch — pots already killed visibles at ~50 mA; ratings ~20 mA.
- No motion while holding detectors through open door (owner rule from prior sessions).
- DEGRADED / weak h14 historically acceptable for some food collection — do not over-promise SWIR.
- Research output should mark **provisional** thresholds as provisional.

---

## 10. Success criteria for your report

A good report answers clearly:

1. **Can OPT101 be used “better” for hole 16?** → diagnostics vs chemistry, with proposed expect/analysis changes.  
2. **What software-only collection/analysis changes** maximize information under photon and duty limits?  
3. **What still requires hardware** (aim for 12–14, earth/hum, extended InGaAs for true 1850, etc.)?  
4. **Concrete next bench protocol** (commands + sample ids + what to record) ranked by value.

End with a short **recommendation matrix**: idea → expected gain → risk → needs bench? → touches which code/config.
