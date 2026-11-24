# All 16 LEDs on both detectors — stationary bench handoff

You are the LIO bench agent on the owner's bench Mac. Run the prepared all 16-LED, dual-detector stationary reference experiment, then analyse and report it. The owner explicitly expanded scope from h8/h12 to **ALL 16 holes, including h16, with both InGaAs and OPT101**. This authorises bounded managed serial/WAKE/light acquisition for this experiment, with real physical-state confirmations. It does not authorise detector/head movement, motors, firmware, current/wiring changes, product-code edits or Git push.

## Prepare and preserve the rig

- Read AGENTS instructions, `.agents/project-state.md`, `test_results/README.md`, `docs/handoffs/2026-11-23_sensor_suite_practical_acceptance.md`, `docs/research/LIO_V3_STATIONARY_OPTICAL_BENCH_2026-11-24.md`, and the current config/protocol help. Review current main at or after `fdcee9d`; record exact source and loaded executable identity. Do not alter a running dashboard's checkout, discard local work or silently restart software.
- Keep BOTH detectors, head height, LED currents, wiring, gain and optics unchanged. Use the existing owner-acknowledged cooperative-unproven mode without inventing a hang bound. Preserve every duty/timing/watchdog/journal gate.
- Establish one serial owner. If the dashboard owns the port, coordinate a normal graceful release; leave its process running. Do not kill it, interrupt an active job or open a competing client. Preserve the same physical-device persistent journal and ownership identity; never create fresh state or clear history to avoid cooldowns.
- Treat owner-reported Rf 2 MΩ/approximately 30 mA and stale config 1 MΩ/B 45 mA as unreconciled metadata, not measured facts. No drive increase is allowed. A known incompatible source condition must be reported/refused; do not claim that duty limits independently verify current ratings. A0/Rf/ammeter/reference qualification remains deferred.

## Experiment

Use the four supplied JSONs in order:

1. `all16_W1_n12.json`: fresh flat white reference placement.
2. `all16_B1_n12.json`: flat black card, matched TOP surface plane.
3. `all16_W2_n12.json`: remove/reseat white.
4. `all16_B2_n12.json`: remove/reseat black.

The files are under `docs/research/protocols/2026-11-24_all16_dual_detector/`. Its `SESSION_MANIFEST_NOT_A_PROTOCOL.json` is an analysis/design record, not a CLI protocol. Use these repository paths; no separate download is required.

Each acquisition has holes 1–16, both detector rows, N=12 technical readings per hole, gain 1, settle 8 ms, configured 60 Hz integration with 2 mains periods. It contains **192 individual managed MEAS operations /384 detector rows**. The four planned acquisitions total 768 operations /1536 rows. Do not replace this with a height scan, full suite, T05.5 or raw unguarded commands. Never omit rows because a detector is outside the source's nominal band.

Per-run experiment caps: total-on 24000 ms, finite wall/cycle 3600 s. Reviewed nominal light 15872 ms and normal reservations 17664 ms per run; actual timing/admission can differ. These experiment caps do not change the rolling limits. Honour all cooldowns and refusals. The four full-panel runs take tens of minutes: allow roughly 40–80 minutes for all four, subject to real journal state/handling. Offline ETA is not a live runtime guarantee.

Before light, run the actual offline `scan plan --protocol` for all four against the installed config. Verify all 16 holes, both detectors, fixed N/settings and finite caps. Do not silently shorten N/change integration or relax limits to obtain a plan or live PASS.

Ask the owner for actual white/black materials, surface-plane/backing/registration and chamber state. Keep equal footprint/orientation and shim the thinner insert so TOP surfaces match. White paper is not a calibrated SWIR standard and a visibly black card is not zero-reflectance. Do not substitute the earlier differently positioned black cup and claim matched-plane evidence.

If matched black card is unavailable before acquisition, proceed with the predeclared white-only fallback W1/W2, measuring all 16×both, and explicitly mark B1/B2 and white−black comparisons unavailable. Do not stall all useful channel screening or invent black-target measurements. No optical blocker is required for this panel, and none may be claimed.

There is one planned target-start checkpoint per run. With LEDs OFF/no motion, get the owner's actual confirmation of that fresh target, unchanged rig and closed chamber. Never reuse answers, auto-answer yes or pretend setup is confirmed. Between these checkpoints the run should proceed automatically with the normal safety gates and cooldowns. If an additional genuine refusal/setup dependency arises, explain it rather than bypassing it.

Use a new output directory per acquisition. Preserve raw counts including negatives, missing attempts, failures and incomplete runs. Resume only the same unchanged target/setup if supported; never resume a different material into the old run. No stopping when positive or rerunning for PASS.

## Analysis

- Verify seals and source hashes. Generate `qualified-v2` products outside source runs using `--derived-out`; never rewrite historical data or analysis.
- Build a 32-row channel table: hole, nominal source, detector, W1/B1/W2/B2 means/SD/N, white−black estimate/uncertainty, placement agreement, missingness and status.
- Show run means and actual timestamps. There are two placements per target, not 24 independent preparations. W-B-W-B does not cancel linear drift. Scope pair IDs by run; equal strings in different runs are not physical pairing.
- The manifest predeclares 32 external hole×detector target comparisons. Single-condition runs have no within-run condition contrast and can legitimately be UNRESOLVED. Do not call that a failed LED. Any technical-only interval must disclose placement/order limitations; do not present it as general day/food reliability.
- Keep C=null without valid optical/electrical controls. No blocker was used; black-reference subtraction is not an electrical-control measurement.
- Report statuses such as repeatable target-associated response, drive response with unresolved target dependence, unstable, unresolved, or refused/not measured. **A small/out-of-band response is not proof that an LED is dead or wrong.**
- Preserve spectral roles: h10/h11 are broadband; OPT101 h12–16 cannot establish primary SWIR; InGaAs h15 is cutoff-sensitive. H16 is included ONLY as `proxy_unassigned`, never primary 1850 chemistry. Other detector readings remain diagnostics; do not invent blind controls.

Save raw IDs, frozen protocols, actual settings/build identity, real checkpoint history, exposure accounting, source hashes, versioned derived products and `docs/research/LIO_V3_ALL16_DUAL_DETECTOR_BENCH_<date>.md`. State which channels give usable repeatable response and which need another targeted test. No calibrated reflectance/current, improved-SNR or SWIR/1850 chemistry claim without the requisite direct evidence. Do not push unless separately authorised.

Typical command forms, verified against the installed CLI before use:

```sh
lio scan plan --protocol "$PROTOCOL" --json "$PLAN"
lio --port "$LIO_PORT" scan run --protocol "$PROTOCOL" --allow-light --sample "$ACTUAL_SAMPLE_ID" --out "$NEW_OUT"
lio scan analyse "$RUN" --model qualified-v2 --derived-out "$DERIVED"
lio scan report "$RUN" --analysis "$ANALYSIS_ID" --derived-out "$DERIVED"
```

Offline preparation validated all four JSONs through the actual CLI at source `fdcee9d`, with guards blocking device construction, serial, port resolution and WAKE (zero hardware calls). See `docs/research/protocols/2026-11-24_all16_dual_detector/OFFLINE_VALIDATION.json`. The preparation environment had no bench-board connection and collected no live readings. This handoff and its JSONs are ready for the bench agent to validate and execute there.
