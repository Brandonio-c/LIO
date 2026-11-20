# Baselines (two different systems)

## 1. Suite baseline (T11 / “Compare with latest baseline”)

- **Files:** `software/config/baseline_YYYYMMDD.yaml`
- **API:** `lio.baseline.save` / `latest` / `load`
- **Contents:** per-hole nets, dark stats, InGaAs/OPT101 ratios, settle times, firmware, config hash
- **Current:** `software/config/baseline_20261120.yaml` from run `20261120-003626_host`, sample **`empty`**, verdict FUNCTIONAL
- **Use:** drift check on later selftests (`--baseline latest` or dashboard compare)

## 2. Scan baseline (height-sweep curves)

- **Files:** `test_results/scan_baselines/<sample_id>/<run_id>.json`
- **CLI:** `lio scan baseline save <run>` / `list`; compare via `lio scan compare`
- **Current:** only an older `empty` quick (`20261116-202110_scan_quick`). Newer empty quick `20261120-012619_scan_quick` is FUNCTIONAL but **not yet saved** as a scan baseline.
- **Use:** compare food / PTFE / black_cup sweeps to empty (and PTFE) references; trend / effectiveness

## Food-profile checklist

- [ ] Save fresh **empty** scan baseline (prefer **full** mode)
- [ ] Optional: `white_ptfe`, `black_cup` scan baselines
- [ ] Collect food scans with stable sample_id
- [ ] Suite baseline already present for electrical drift (optional compare on later host runs)

Do not confuse suite YAML drift with scan-curve baselines — food profiles need **scan** baselines.
