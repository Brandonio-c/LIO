# Coding-agent handoff: implement LIO food-profile analysis

Copy the prompt below into the coding agent with access to this repository.

---

You are implementing the LIO food-profile processing and visualization system in `Brandonio-c/LIO`.

**Do the implementation, not another research report or plan.** Complete milestones M0–M7 in `docs/FOOD_PROFILE_ANALYSIS_PLAN.md` in dependency order. Build tested numerical capabilities and usable UI/CLI workflows; do not stop after basic heatmaps or replace analytical methods with placeholders.

## Repository and working rules

- Work only on `main`. Do not create branches or side-branch PRs.
- Inspect current status/history and preserve owner work. No force pushes, destructive resets/cleans or git-config changes.
- Commit coherent milestones directly on `main` and push `main` after the relevant checks pass.
- Do not operate hardware, start scans, move motors, flash firmware or restart a live dashboard without explicit bench authorization. Offline work, simulator tests and synthetic fixtures are authorized.
- Follow current repository instructions. Prefer current code over stale context; document justified changes to the plan rather than silently changing scientific meaning.

## Read first

1. `.agents/README.md`, `.agents/preferences.md`, `.agents/project-state.md`, `.agents/baselines.md`.
2. **`docs/FOOD_PROFILE_ANALYSIS_PLAN.md` — the implementation specification and acceptance criteria.**
3. `docs/research/LIO_FOOD_SCAN_LITERATURE_REVIEW.md` and `docs/research/LIO_FOOD_SCAN_EVIDENCE.csv`.
4. `.agents/scan-data-viz-handoff.md`, `docs/DIAGNOSTIC_SWEEP.md`, `docs/FOOD_LIBRARY.md`.
5. Current `lio/scan/`, `lio/dashboard/`, `lio/foods/scans.py`, CLI, configuration, tests and CI.

The plan was grounded in `main` at `dc7235ac46776ad1f390ed666a3d2716656401d5`. Reconcile subsequent code changes before editing.

## Required result

Extend the existing dashboard and offline CLI with a shared `lio.food_profiles` domain layer:

- Saved-run **Explore**, exact/capability-aware **Compare**, and a **Food Map/gallery**.
- Raw signed readings, processed curves, findings, lazy stream inspection and honest missingness.
- Dataset/annotation manifests distinguishing runs, physical material/lot and independent preparations.
- Common-height amplitude; qualified reference-relative features; vector/SNV/MSC challengers; existing-analysis O envelopes and curve summaries.
- Food × feature heatmaps, frozen PCA with loadings/residuals, detector-specific/fused models and original-space distances.
- Whole-height difference maps, physically weighted curve distances and actual discretized multivariate functional PCA with frozen projection.
- Working optional UMAP/t-SNE sensitivity views, supported crossed-design ASCA, grouped evaluation and compatible chronological EWMA/control displays.
- Safe versioned bundles, reproducible reports/exports, installed-package offline operation and regression tests.

Treat the plan's research extensions/non-goals as such: do not implement chemistry/ingredient claims, blind-spectrum reconstruction, automatic peak warping or tensor unmixing merely because a paper mentions them.

## Non-negotiable scientific contracts

- Start from `scan.json` + `cube.csv.gz`; analysis and NPZs are optional. No USB, food DB or `results.json` requirement; implement the plan's explicit --no-food-library startup path.
- Existing food database repeated sweeps are a different schema. Do not reinterpret them as height profiles.
- `Cube.curve()` aggregates/despikes. Use raw rows for raw markers and retain separate processed layers. Opening a view must never call the diagnostic `analyse()`, which writes files.
- Use stationary kind=measure for default P2 food features. Never pool P3/repeats/extra/continuous/P1/P4/coupling states into that selection.
- Mask structural blinds; distinguish blind/missing/invalid/excluded/zero. Keep white/pink broadband channels categorical. Unverified historical channel maps remain unverified.
- Check saved-analysis identity/provenance before using derived products. Keep amplitude and shape representations separate. Do not subtract dark twice, assume C=0, invent a white reference, epsilon-fix weak/negative reference denominators or substitute peak ratios for matched-height measurements.
- Preserve original physical heights and processing/reference provenance. No silent extrapolation or automatic peak alignment.
- Rows are runs, not automatically independent observations. Default known-preparation aggregation prevents technical repeats dominating PCA. Unknown independence metadata limits claims.
- Separate fit from transform. Freeze feature order, QC selection, MSC reference, means/scales, height grid, weights and basis. New projections cannot move old points.
- Split by the intended preparation/lot/day target before learned preprocessing/model selection. No fallback to random cube rows; no label-driven “best-looking clusters” selection.
- Persist JSON + numeric NPZ with `allow_pickle=False`; no arbitrary pickle/joblib model loading.
- Heavy analysis must not block acquisition, hold device locks or interfere with heartbeat. Browsing saved data remains independent of an active scan.
- Real-data gaps gate scientific conclusions, not whether the software is implemented. Use clearly labeled synthetic fixtures to exercise valid algorithm paths; never claim measured LIO accuracy or completed bench validation.

## Execution and verification

Deliver vertical slices following M0–M7. Start with source/metadata contracts and synthetic fixtures; then complete Explore, Compare/recipes, frozen PCA/distances, full-height analysis, gallery/grouped evaluation, experimental methods/trends, and packaging/docs.

Use existing simulator infrastructure and maintain strict typing. Run the existing Ruff, mypy and unit/simulator checks plus the targeted numerical, persistence, leakage, path-resolution, browser/offline-wheel and acquisition-concurrency tests required in the plan. Check Python 3.10/3.12 and both absent/present optional extras. Test actual algorithm outputs and invariants, not merely functions returning or UI buttons existing.

If no physical food runs exist locally, finish the software and synthetic demonstration; list real-food qualification separately. If a prerequisite blocks an operation, implement and test its valid-input path and return a precise unavailable reason for invalid inputs. Do not silently defer requested milestones or call a stub complete.

Keep progress concise. Resolve ordinary engineering choices autonomously. At completion, report commits pushed to `main`, milestones completed, checks actually run, example launch/CLI commands, optional dependencies, material limitations and pending physical-validation tasks. Update usage docs and relevant agent context so the next session can continue without reconstructing this conversation.

