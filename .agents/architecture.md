# Architecture map

## Hardware (LIO V3)

- **Host:** Mac, Python (`lio` conda env), USB serial to Nano.
- **Arduino Nano** (fw 2.5.x): optics, ADC, motors, watchdogs, ARM.
- **74HC595 × 2:** U1 holes 1–8, U2 holes 9–16 (one hole selected at a time).
- **ADS1115:** I²C 0x48 — A0 InGaAs TIA, A1 OPT101.
- **DRV1 / Rail A (CE1):** holes 1–8 (30 mA; duty ≤ 1 s/min per LED).
- **DRV2 / Rail B (CE2):** holes 9–16 (~45 mA; duty ≤ 5 s/min; hole 9 capped like A).
- **Motors:** 28BYJ-48 × 2 + ULN2003; lead screws; stage tracked in `test_results/stage_position.json` (top = 0 light-tight).
- **Detectors:** OPT101 (Si, VIS–NIR), InGaAs TIA (SWIR). Shared holes ~8–9.

Docs: `docs/OPTICAL_CHANNEL_MAP.md`, `docs/PROTOCOL.md`, `docs/TESTING.md`, `docs/DIAGNOSTIC_SWEEP.md`.

## Software layout

```
software/config/lio_hw.yaml     # hardware + thresholds + scan modes
software/config/baseline_*.yaml # suite (T11) baselines
software/firmware/              # Nano sketch
software/host/src/lio/
  device.py, transport.py, sim.py
  suite/          # T01–T13 catalogue + runner
  scan/           # diagnostic height sweep (plan/executor/analysis)
  dashboard/      # local web UI :8765 (twin, motors, LEDs, scan, foods)
  foods/          # sample library / composition helpers
  baseline.py     # suite baseline save/load
test_results/                   # run folders (gitignored); scan_baselines/
docs/                           # plans, protocols, handoffs
.agents/                        # this context pack
```

## Two “test” systems

1. **Host suite (T01–T13)** — electrical / safety / channels / motors; dashboard System tab or `lio selftest`.
2. **Diagnostic scan** — height sweep + analysis matrix; dashboard Scan tab or `lio scan …`; T13 wraps a scan into the suite.

Overall twin verdict aggregates suite (+ loaded scan) results; WARNs alone stay **FUNCTIONAL**.
