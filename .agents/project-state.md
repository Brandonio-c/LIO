# Project state (as of 2026-11-20)

## Verdict

**FUNCTIONAL with warnings** — ready to start collecting food LIO scan profiles, with provisional thresholds and known soft optics/mechanics.

Latest host suite: `test_results/20261120-003626_host` → **FUNCTIONAL**  
(`PASS` 39, `WARN` 3: T07.1 / T09.6 / T13.1, `SKIP` 3: T04.2 / T04.3 / T11.1 without compare, `FAIL` 0)

Latest empty quick scan (via T13): `20261120-012619_scan_quick` → **FUNCTIONAL** (InGaAs soft WARNs, h16 plausibility).

## Commissioning done

- Firmware **2.5.2**; rails A=1–8 / B=9–16 match the build.
- Dashboard twin + host suite: soft WARNs for V3 loose stage, weak InGaAs at sealed top, hole 16, intermittent/select-only, bogus SWEEP duty accounting.
- `set_top` rebases bottom / light-tight top documented; `top_margin` in config.
- USB-after-Stop: suite detects dead link, drops stale port, refuses new run until reconnect (see session `ensure_link` / `link_lost`).
- Suite baseline saved: `software/config/baseline_20261120.yaml` (sample `empty`).
- Extra remote branches removed; repo is **main-only**.

## Twin / LED display policy (V3)

| Symptom | Treatment |
|---------|-----------|
| Hole 16 OPT101 residual at 1850 nm | WARN (limited hole) |
| T06.3 weak cross-cal / “one detector” at top | WARN, not channel FAIL |
| T07.1 no step (esp. h13 InGaAs at top) | WARN |
| Stage repeatability large spread | Cap FAIL→WARN |
| Duty “46 s/min” with 0 cool-downs | WARN / accounting bug; SWEEP duty staggered |

## Not done / next for food work

1. Save a **fresh scan baseline** for `empty` (promote today’s empty quick or run a **full** empty scan, then `lio scan baseline save <run>`).
2. Optional references: `white_ptfe`, `black_cup` full scans → scan baselines.
3. Collect food profiles: Scan tab → **full** (or fine), sample id = food / `LIO-F-…`, lid closed.
4. UI: “Compare with latest baseline” may show “none saved yet” until session refresh — file on disk exists.
5. Thresholds still **provisional** (`docs/TESTING.md` §7.3).

## Open soft issues (do not block food collection)

- InGaAs weak / low SNR on some SWIR holes (13–14); hole 16 known coupling.
- Stage mechanically clunky (repeatability WARN by policy).
- Prefer sealed-top suite vs mid-travel / full-scan heatmaps when judging “LEDs work.”
