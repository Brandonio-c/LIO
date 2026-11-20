# Workflows

## Dashboard

```bash
cd /Users/coleloughbc/Documents/VSCode-Local/LIO
/Users/coleloughbc/miniconda3/envs/lio/bin/lio --port /dev/cu.usbmodem101 \
  dashboard --no-browser --no-phone --no-tunnel
# → http://127.0.0.1:8765/
```

- Connect on System tab; **Clear results** starts the twin afresh (reports stay on disk).
- After **Stop** mid-run: if Run fails or ERROR-cascades, **Disconnect → Connect**, then run again.
- Whole-system run: confirm chamber clear / lid when motion overlay appears.

## Host suite

```bash
lio selftest --allow-motion --save-baseline --sample-id empty
lio selftest --baseline latest
```

Dashboard: Run whole system (± Save as baseline). Motion tests need the preflight checkbox / overlay.

## Diagnostic scan

```bash
lio scan plan --mode full
lio scan run --mode full --sample-id empty   # or white_ptfe, black_cup, food id
lio scan baseline save <run_id>
lio scan baseline list
lio scan compare <runA> <runB>
```

Modes: `quick`, `full`, `fine`, `repeatability`, … (see `lio_hw.yaml` `scan.modes`).

## Food profiles (collection)

1. Prefer a saved **empty** scan baseline (full if time allows).
2. Optional: `white_ptfe` / `black_cup` references.
3. Load sample; Scan → **full**; sample id = food code / name.
4. Keep packing / lid / nest consistent across runs.
5. Compare later with scan baselines / trend tools — not the suite YAML baseline.

## Stage

- Top = highest **light-tight** height (sleeves overlapping); stored in `test_results/stage_position.json`.
- After moving the head by hand or another program: **set top** again.
- `set_top` rebases soft limits / bottom travel.
