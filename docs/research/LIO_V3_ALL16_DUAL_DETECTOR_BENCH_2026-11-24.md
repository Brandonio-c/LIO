# LIO V3 all-16 dual-detector stationary bench (24 November 2026)

**Evidence folder:** [`test_results/bench_20261124_all16/`](../../test_results/bench_20261124_all16/) ·
**Handoff:** [2026-11-24_all16_dual_detector_bench.md](../handoffs/2026-11-24_all16_dual_detector_bench.md) ·
**Protocols:** [`docs/research/protocols/2026-11-24_all16_dual_detector/`](protocols/2026-11-24_all16_dual_detector/) (byte-identical copies under `protocols/` in the evidence folder; SHA-256 matches `OFFLINE_VALIDATION.json`).

Port `/dev/cu.usbmodem101` (Nano R4, USB serial `3501131C…`), firmware 2.5.2, `hw_wdt=0`, admission
`cooperative_unproven` (owner-acknowledged; no firmware-hang bound claimed). Gain 1, settle 8 ms,
60 Hz × 2 mains periods, N = 12 technical readings per hole per run, holes 1–16, both detectors.
Owner-declared and **unmeasured**: Rf 2 MΩ fitted (YAML 1 MΩ); LED rails ≈ 30 mA (YAML B 45 mA). No
blocker was used. No calibrated reflectance, photocurrent, SNR, SWIR chemistry or 1850 nm claim is made.

## 1. Bottom line

With the rig in its final state (R6: top fitted, h16 reworked), the matched-plane sequence
**W1 → B1 → W2 → B2** (white printer paper vs flat matte black card, each placed twice) completed
cleanly: 4 × 192 MEAS = 768 operations, 1,536 detector rows, none missing, 0 ms uncertain exposure,
all seals verified.

- **Every hole gives a repeatable, target-associated response on at least one detector** (Bonferroni-32
  technical interval excludes 0, both W−B placement pairs agree in sign, and the target effect exceeds
  placement disagreement). 28 of the 32 hole × detector rows meet that rule.
- **OPT101:** h1–h11 and h16 give large white−black contrasts (43–836 counts). h12–h15 OPT101 show no
  resolved target effect, as expected for a silicon detector at 1450–1760 nm.
- **InGaAs (primary SWIR):** h12 (1450 nm) **+51.1 counts**, h15 (1760 nm, cutoff-sensitive) **+14.2**,
  h13 (1550 nm) **+2.7**, h14 (1650 nm) **+1.9**. h13 and h14 are resolved but tiny: usable only
  as weak channels, and they need a targeted optical check before food work.
- **h16 (proxy_unassigned)** gives 1,172 counts on the silicon OPT101 and 166 on the InGaAs from white.
  A real 1850 nm source cannot produce a silicon signal of that size, so the h16 part emits at much
  shorter wavelengths (or is not the labelled part). It stays a proxy and is never primary 1850 nm.
- **Black is not zero.** The black-card residual is 10–25 % of white on most OPT101 rows, 24–31 % on
  h12 InGaAs and **≈ 60 % on h15 InGaAs**. Without a blocker it is unknown how much of each residual is
  light from the card, stray light inside the chamber, or electrical pickup; most of h15's InGaAs signal
  does not depend on the target.
- **Placement and order matter.** W2 is ≈ 3–7 % below W1 on nearly every row, and B2 is up to 2.5×
  above B1 on the OPT101 (e.g. h11 84.5 → 190.9). The white−black effects are far larger than this,
  but the placement disagreement is real and must be designed in for food work (see §5).

## 2. What happened during the session (all retained)

The run of the day did not go to plan; every run is kept, labelled in `RUN_LABELS.json`, and every
checkpoint answer is in `checkpoint_history.txt` (each answer was given by the owner for that
occurrence; one `a` and three `n` deliveries were agent actions on declined/stale checkpoints and are
labelled as such).

| Time | Run | Rig state | What it is |
|---|---|---|---|
| 02:22 | `20261124-022255` | R0 | Planned W1, but the owner later reported the **black cup** was in place, not white. Values match the earlier black-cup bench (h12 InGaAs 11.3 vs 11.5). Excluded from the family. |
| 02:34 | `20261124-023438` | R0 | B1 declined at checkpoint (W1 had to be redone). No light. |
| 02:36 | `20261124-023620` | R0 | White W1 (night). Owner then disconnected the rig overnight. |
| 02:47 | `20261124-024754` | — | B1 waiting at checkpoint overnight; agent sent `a` at 12:07 → uncaught operator `Abort`; run left **RUNNING, no seal, no light**; safe-off to the vanished port marked the journal uncertain (cleared through the normal cooled path). |
| 12:09 | `20261124-120951` | R1 | White W1 after reconnect (board re-enumerated as `usbmodem1101`; owner moved it back so the same journal identity was used). |
| 12:31 | `20261124-123151` | R1 | B1 declined: owner fitted the top-plate bracket, puttied LEDs and moved wires. No light. |
| 12:48 | `20261124-124834` | R2 | White: **h12 erratic** on both detectors (OPT101 driven below dark) → electrical fault suspected. |
| 13:59 | `20261124-135925` | R3 | White after owner checked wiring: h12 recovered; **h14 zero**; h9 noisy. |
| 14:18 | `20261124-141830` | R3′ | Targeted h9, h12–h15 check after h14 wires were moved: h14 4.7 ± 1.0. |
| 14:22 | `20261124-142237` | R4 | All-16: h15 jumped 6.6 → 28.7, h12 81 → 62, h9 steady. |
| 14:47 | `20261124-144744` | R4 | INCOMPLETE `max_wall_s` before light: the checkpoint was answered 62 min after start (wall cap counts checkpoint wait). |
| 15:50 | `20261124-155019` | R4 | **Untouched repeat** of 14:22 (88 min apart): 13/16 LEDs within 2 % on their main detector. |
| 16:05 | `20261124-160543` | R5 | White after top fitted: **h16 intermittent** (0 ↔ 1128 within the run). Owner chose to fix h16. |
| 16:19 | `20261124-161944` | R6 | All-16 check after h16 rework: steady. |
| **16:29** | **`20261124-162954`** | **R6** | **Family W1** (white, fresh) |
| **16:40** | **`20261124-164006`** | **R6** | **Family B1** (flat black card, matched plane) |
| **16:51** | **`20261124-165136`** | **R6** | **Family W2** (white, reseated) |
| **17:04** | **`20261124-170431`** | **R6** | **Family B2** (black card, reseated) |

**Software changed mid-session at the owner's request** (between 13:24 and 13:52): the LEDs-tab click
now gives one 5 s watchdog-bounded flash (owner-acknowledged over-budget allowance with a clear-window
rule), and **LED duty budgets are per LED instead of per rail** (restoring the approved M0 per-channel
semantics). Config/loaded-source hashes therefore change from `b6d5…`/`0e24…` (runs up to 12:48) to
`ea6c…`/`516c…` (13:59 onward); **all four family runs share the same build and config**. Per-run
protocol on-time and N are unchanged; the all-16 run still takes ≈ 10 min because 12 consecutive
readings of one LED (≈ 1.1 s) exceed that LED's 1 s/min allowance on holes 1–9.

## 3. Results: 32 hole × detector channel table (family runs, rig R6)

Signed lit − dark nets (counts), mean/SD with N = 12 per cell; no rows missing in any cell.
D = mean(W1, W2) − mean(B1, B2). The interval is **technical only** (readings within runs, Welch,
Bonferroni over the 32 prespecified comparisons): it ignores placement-to-placement variance and
drift, so it is not a general reliability interval. Placement agreement = W2 − W1 / B2 − B1.

| Hole | Source (nm) | Detector | W1 | B1 | W2 | B2 | D (Bonf-32 technical) | W2−W1 / B2−B1 | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 395 | InGaAs | 4.3/1.6 | 0.7/1.2 | 3.7/0.9 | 0.7/0.8 | +3.3 (+2.2..+4.5) | −0.7 / +0.0 | repeatable target-assoc. (small, out of band) |
| 1 | 395 | OPT101 | 340.2/3.4 | 30.8/0.8 | 320.2/1.1 | 80.9/0.7 | +274.4 (+272.3..+276.4) | −19.9 / +50.2 | repeatable target-assoc. |
| 2 | 405 | InGaAs | 4.8/1.1 | 0.3/0.9 | 3.9/1.4 | 0.8/1.1 | +3.8 (+2.7..+5.0) | −0.9 / +0.4 | repeatable target-assoc. (small, out of band) |
| 2 | 405 | OPT101 | 365.2/4.9 | 22.2/0.9 | 339.5/4.2 | 51.9/0.5 | +315.3 (+311.9..+318.6) | −25.7 / +29.7 | repeatable target-assoc. |
| 3 | 465 | InGaAs | 1.4/1.0 | −0.3/0.9 | 1.1/1.1 | −0.2/1.4 | +1.5 (+0.5..+2.6) | −0.3 / +0.1 | repeatable target-assoc. (≈ 1 count, out of band) |
| 3 | 465 | OPT101 | 182.3/0.5 | 21.0/0.6 | 170.2/1.0 | 41.4/0.7 | +145.1 (+144.4..+145.8) | −12.1 / +20.4 | repeatable target-assoc. |
| 4 | 525 | InGaAs | 7.8/1.3 | 0.4/1.4 | 7.3/1.2 | 1.7/1.1 | +6.5 (+5.3..+7.7) | −0.4 / +1.2 | repeatable target-assoc. (out of band) |
| 4 | 525 | OPT101 | 324.5/1.0 | 25.7/0.5 | 307.1/1.2 | 64.9/0.5 | +270.5 (+269.7..+271.3) | −17.4 / +39.2 | repeatable target-assoc. |
| 5 | 590 | InGaAs | 11.9/1.0 | 6.7/1.1 | 11.2/1.1 | 5.1/1.6 | +5.7 (+4.5..+6.9) | −0.7 / −1.6 | repeatable target-assoc. (out of band) |
| 5 | 590 | OPT101 | 86.2/2.0 | 17.0/0.7 | 81.3/1.8 | 23.9/2.0 | +63.3 (+61.6..+65.0) | −4.9 / +6.9 | repeatable target-assoc. |
| 6 | 605 | InGaAs | 11.8/1.1 | 7.0/0.9 | 10.3/1.8 | 5.1/1.2 | +5.0 (+3.7..+6.3) | −1.4 / −1.9 | repeatable target-assoc. (out of band) |
| 6 | 605 | OPT101 | 62.8/0.8 | 17.2/0.6 | 59.5/1.4 | 19.9/1.0 | +42.6 (+41.6..+43.6) | −3.2 / +2.8 | repeatable target-assoc. |
| 7 | 630 | InGaAs | 17.0/1.2 | 6.1/1.6 | 15.5/1.9 | 5.0/2.0 | +10.7 (+9.1..+12.4) | −1.5 / −1.1 | repeatable target-assoc. (out of band) |
| 7 | 630 | OPT101 | 136.2/1.2 | 19.9/0.7 | 130.9/2.0 | 30.6/1.7 | +108.3 (+106.8..+109.8) | −5.2 / +10.7 | repeatable target-assoc. |
| 8 | 850 | InGaAs | 143.4/1.4 | 19.8/1.5 | 135.8/1.0 | 32.2/1.6 | +113.6 (+112.2..+115.0) | −7.6 / +12.4 | repeatable target-assoc. |
| 8 | 850 | OPT101 | 970.8/1.9 | 100.9/2.6 | 923.8/2.4 | 192.8/4.2 | +800.4 (+797.5..+803.3) | −46.9 / +91.9 | repeatable target-assoc. |
| 9 | 940 | InGaAs | 201.6/5.3 | 33.9/4.3 | 184.2/1.3 | 41.1/1.8 | +155.4 (+151.7..+159.0) | −17.4 / +7.2 | repeatable target-assoc. (h9 SD elevated in W1/B1) |
| 9 | 940 | OPT101 | 753.8/6.3 | 83.7/7.0 | 718.9/2.4 | 145.7/3.4 | +621.7 (+616.6..+626.9) | −34.9 / +62.0 | repeatable target-assoc. |
| 10 | white (broadband) | InGaAs | 17.5/0.9 | 1.6/1.3 | 16.9/0.9 | 3.5/1.6 | +14.7 (+13.5..+15.9) | −0.6 / +1.9 | repeatable target-assoc. |
| 10 | white (broadband) | OPT101 | 377.1/1.3 | 38.7/0.5 | 361.8/1.1 | 91.0/0.7 | +304.6 (+303.7..+305.6) | −15.2 / +52.3 | repeatable target-assoc. |
| 11 | pink (broadband) | InGaAs | 63.0/1.2 | 8.1/0.8 | 60.5/1.6 | 12.4/1.4 | +51.5 (+50.3..+52.7) | −2.5 / +4.3 | repeatable target-assoc. |
| 11 | pink (broadband) | OPT101 | 783.7/1.2 | 84.5/0.8 | 750.9/1.0 | 190.9/0.7 | +629.6 (+628.6..+630.5) | −32.8 / +106.4 | repeatable target-assoc. |
| 12 | 1450 | **InGaAs** | 65.4/1.9 | 15.8/3.0 | 76.2/3.5 | 23.6/0.9 | **+51.1 (+48.5..+53.6)** | **+10.8 / +7.7** | repeatable target-assoc.; **level drifts between runs** |
| 12 | 1450 | OPT101 | 5.3/2.1 | 5.8/2.2 | 20.0/3.4 | 15.3/0.8 | +2.1 (−0.3..+4.4) | +14.7 / +9.5 | drive response, target dependence unresolved (non-optical drift) |
| 13 | 1550 | **InGaAs** | 5.7/0.8 | 3.2/0.9 | 6.2/1.3 | 3.3/1.1 | **+2.7 (+1.7..+3.7)** | +0.5 / +0.2 | repeatable target-assoc. (**tiny**) |
| 13 | 1550 | OPT101 | 1.6/0.5 | 1.8/0.5 | 1.8/0.4 | 1.8/0.6 | −0.0 (−0.5..+0.5) | +0.2 / +0.0 | unresolved (expected: out of band) |
| 14 | 1650 | **InGaAs** | 4.2/1.2 | 2.1/0.9 | 4.2/1.1 | 2.5/1.2 | **+1.9 (+0.8..+3.0)** | −0.1 / +0.4 | repeatable target-assoc. (**tiny**) |
| 14 | 1650 | OPT101 | 1.8/0.6 | 1.8/0.4 | 1.8/0.5 | 1.7/0.5 | +0.0 (−0.4..+0.5) | −0.1 / −0.2 | unresolved (expected: out of band) |
| 15 | 1760 | **InGaAs** | 35.9/1.3 | 21.8/1.1 | 34.3/1.1 | 20.0/1.3 | **+14.2 (+13.1..+15.4)** | −1.6 / −1.8 | repeatable target-assoc.; **≈ 60 % of signal target-independent**; cutoff-sensitive |
| 15 | 1760 | OPT101 | 2.0/0.7 | 1.8/0.5 | 1.8/0.7 | 1.9/0.5 | +0.1 (−0.5..+0.7) | −0.2 / +0.2 | unresolved (expected: out of band) |
| 16 | 1850 (proxy_unassigned) | InGaAs | 166.0/1.1 | 39.6/0.9 | 153.9/1.2 | 47.7/1.1 | +116.3 (+115.3..+117.4) | −12.1 / +8.1 | repeatable target-assoc.; **proxy only** |
| 16 | 1850 (proxy_unassigned) | OPT101 | 1172.2/1.8 | 212.2/1.8 | 1093.8/1.9 | 382.7/1.1 | +835.5 (+833.9..+837.2) | −78.5 / +170.4 | repeatable target-assoc.; silicon response ⇒ not an 1850 nm emitter |

Status rule (frozen in `analyse_all16.py` before any all-16 data were inspected; text reformatted
for lint afterwards, rules unchanged): refused/not measured → unstable (any run SD > max(5, 10 %)) →
repeatable target-associated (Bonf-32 excludes 0, same sign in both pairs, smaller |pair effect| >
max placement disagreement) → drive response with unresolved target dependence → unresolved. No row
was refused or unstable. **An unresolved or small response is not evidence that an LED is dead or
wrong.** Out-of-band rows are diagnostics only.

Run timestamps (all EST): W1 16:29:54–16:39:42, B1 16:40:06–16:51:16, W2 16:51:36–17:04:13,
B2 17:04:31–17:17:23. Each run used reserved 17,664 ms / actual 16,128 ms / uncertain 0 ms light.

## 4. Interpretation by channel

| Group | Channels | Use now | Needs before food work |
|---|---|---|---|
| Strong, repeatable | OPT101 h1–h11; InGaAs h8, h9, h11; h16 (proxy) | Yes, as relative channels with session white/black references | Fix placement reproducibility (§5) |
| SWIR primary, usable | **InGaAs h12** (+51), **h15** (+14) | h12 yes; h15 with care (≈ 60 % target-independent, cutoff-sensitive) | h12: stabilise its connection (level moved 62 ↔ 85 across today's reworks; +16 % W1→W2 within the family). h15: blocker test to split optical vs electrical |
| SWIR weak | InGaAs **h13** (+2.7), **h14** (+1.9) | Only as a weak indicator | Targeted check: LED aim/seating and connection (hand-held 21 Nov h13 862, h14 1057 counts vs mounted ≈ 5) |
| Out of band | OPT101 h12–h15; InGaAs h1–h7 | Diagnostics only | — |

Notable rig observations this session: h12, h14, h15 and h16 all changed when wires near them were
moved (intermittent contacts are the common thread); h2 OPT101 fell 484 → 330 across the bracket/putty
work and then held steady over 88 untouched minutes (handling, not ongoing fading); the untouched
repeat (14:22 vs 15:50) shows the rig itself is stable to ≈ 1–2 % when nothing is touched.

## 5. Placement agreement and drift (why the second pair differs)

W2 is lower than W1 on 28 of 32 rows (median −5.2 % over the 18 rows with |W1| ≥ 20 counts); B2 is higher than B1 on most OPT101 rows
(often 1.5–2.5×) while InGaAs black rows moved by only a few counts. A monotonic drift would push
both whites and both blacks the same way; here white fell and black rose, which fits **placement
differences** (e.g. paper not lying as flat, the black card's edges or shim exposing lighter tray
material, or a slight offset into the illuminated spot) better than a single drift. W-B-W-B does not
cancel linear drift, and with two placements per target the data cannot separate placement from
drift. For food work: fix the target footprint mechanically (a registered recess or frame), and take
white/black references at the start and end of each session.

## 6. Limits and what is not claimed

- Two placements per target; 24 readings per target are technical repeats, not independent
  preparations. Intervals are technical only.
- No optical blocker: optical return vs LED-synchronous electrical pickup is not separated (C = null
  in all qualified-v2 analyses; verdict UNRESOLVED for single-condition runs, as designed). Black
  reference subtraction is not an electrical control.
- White printer paper is not a calibrated SWIR standard; a visibly black card is not SWIR-black.
- Rf/current/A0 unreconciled and unmeasured; cooperative-unproven exposure bound.
- No calibrated reflectance, photocurrent, SNR improvement, SWIR chemistry or 1850 nm claim. h16 is
  `proxy_unassigned` and its silicon response shows it is not a primary 1850 nm source.

## 7. Software findings (not fixed in this session unless stated)

1. **Operator abort at a checkpoint leaves the run RUNNING with no seal** (`20261124-024754`): `a`
   raises an uncaught `lio.operator.Abort` in `run_protocol`; `n` finalises correctly as INCOMPLETE.
2. **Wall cap counts checkpoint waiting time**: a run left at its start checkpoint for > 1 h ends
   INCOMPLETE `max_wall_s` before light (`20261124-144744`). Safe, but surprising; consider starting
   the wall clock after the start checkpoint or showing the deadline in the prompt.
3. **Offline plan ETA ignores duty pacing** (plan says ≈ 0.4 min; real ≈ 10 min).
4. **Journal identity follows the port path**: re-enumeration as `usbmodem1101` would have opened a
   fresh journal; the owner moved the cable back. Keying by USB serial would be safer.
5. **Fixed this session (owner request, tested, not committed):** dashboard click flash (5 s, off by
   itself; previous solid hold was always refused by a 1 ms conservative-margin off-by-one) and
   per-LED duty budgets. Gate: ruff, strict mypy, `pytest -m "unit or sim" --lio-sim` 1004 passed,
   0 failed, 7 skipped.

## 8. Next targeted tests

1. **h13/h14 optics**: inspect aim/seating against h12; a short h12–h15 protocol (≈ 2 min) after any
   change; expected success: h13/h14 InGaAs white ≥ 20 counts.
2. **h12 connection**: reflow; confirm with two untouched repeats (target: < 3 % run-to-run).
3. **Blocker pair on h12 and h15** (opaque, non-conductive slide) to split optical vs electrical,
   especially h15's 60 % target-independent residual.
4. **Registered target holder** and session white/black references to tighten placement agreement.

## 9. Commands, identities and hashes

```text
lio scan plan --protocol protocols/all16_{W1,B1,W2,B2}_n12.json --json protocols/all16_*_plan.json
POST /api/disconnect   (dashboard; graceful release, process kept/restarted only for the owner-requested code change)
lio --port /dev/cu.usbmodem101 scan run --protocol protocols/all16_<T>_n12.json --allow-light \
    --sample <protocol sample_id> --out runs      (start answer via tail -f <run>_answers.txt)
lio scan analyse runs/<RUN> --model qualified-v2 --derived-out derived
lio scan report  runs/<RUN> --analysis <ID> --derived-out derived
python -I analyse_all16.py   (reads RUNS.json -> channel_response_32.json)
```

| Item | Value |
|---|---|
| Source at session start | `main` e38b248 (clean); host package modified mid-session (click flash, per-LED duty), uncommitted |
| Family build (loaded source / config SHA-256) | `516ce787…` / `ea6c8a3f…` (all four runs) |
| Protocol SHA-256 W1/B1/W2/B2 | `74464e0b…` / `fdee1e03…` / `7358eeec…` / `72ad7e42…` |
| qualified-v2 analyses W1/B1/W2/B2 | `b0cf36c7ca84503a` / `ac93cd13120bf91e` / `7d505299b9c9578a` / `2c29ee88d64de213` |
| cube.csv.gz SHA-256 (W1/B1/W2/B2) | `c4c24552…` / `ce474e59…` / `3ad7916b…` / `cb871f52…` (full hashes in `seal_verification.json`) |
| 32-row table | `channel_response_32.json` (script SHA-256 `8635dd59…`) |
| Seals | 17/17 sealed runs verify; `024754` has no seal (finding 1) |
| Checkpoint history | `checkpoint_history.txt`; run labels `RUN_LABELS.json`; owner setup `OWNER_SETUP.json` |
