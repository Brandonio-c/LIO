# Known issues & intentional softens

## USB / dashboard after Stop

Stopping mid-suite (especially during motor travel) can reset the Nano; the host keeps a **stale serial FD**. Symptom: every test `ERROR` with `Device not configured` / Errno 6 while UI still says connected.

**Mitigation (code):** `Session.ensure_link()` before start; on link-lost ERROR break suite + `link_lost()`; probe after run `finally`.  
**Operator:** Disconnect → Connect, then re-run.

## Twin vs full scan “LEDs work”

Suite at sealed top can WARN/FAIL weak InGaAs on 8/9/13 while full-scan heatmaps show light across travel. Prefer scan heatmaps for “LEDs light”; suite softens keep the twin from painting dead LEDs.

## Duty budget false FAIL

SWEEP used to attribute every hole’s on-time from one shared `t0`, so end-of-run “max ms/min” looked like the **whole-run total** (~46 s) with **0 cool-downs**. Fixed: sequential duty recording + analysis guard. Re-run scan for a clean duty PASS.

## Stage repeatability

Optical repeatability spread can be thousands of half-steps on V3. **Capped at WARN** so it does not force NOT FUNCTIONAL; next mechanical build expected tighter.

## Hole 16

1850 nm; OPT101 residual / limited-hole policy → WARN, not FAIL.

## InGaAs polarity advice

Do **not** swap D1 for a single negative hole; use hole-local advice (`HOLE_NEG_ADVICE` in T06). Bank-wide negative → check −5 V / wiring.

## “Compare baseline: none saved yet”

Suite file `software/config/baseline_20261120.yaml` may exist while the dashboard snapshot was taken before save or without refresh. Check `lio` / `baseline.latest()` / disk; reconnect or reload page.
