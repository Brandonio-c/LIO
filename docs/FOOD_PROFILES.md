# Food-profile Explore / Compare / Food Map

Offline analysis of saved diagnostic height scans (`scan.json` + `cube.csv.gz`). Independent of USB, the food library database, and `lio scan analyse` (which writes artifacts). See `docs/FOOD_PROFILE_ANALYSIS_PLAN.md`.

## Launch

```bash
# Dashboard without food DB (profiles tab still works)
lio dashboard --results-dir test_results --no-food-library --no-browser --no-phone

# Open the Profiles tab (#profiles)
```

Optional extras:

```bash
pip install 'lio[profiles]'      # PCA, distances/clustering, t-SNE
pip install 'lio[embeddings]'    # UMAP
```

## CLI

```bash
# Labeled synthetic library (algorithm tests only — not measured LIO data)
lio profiles fixtures --out /tmp/lio_synth

lio profiles list --results-dir /tmp/lio_synth
lio profiles explore /tmp/lio_synth/<run_folder>
lio profiles init --results-dir /tmp/lio_synth --all-synthetic --out demo-ds
lio profiles build --results-dir /tmp/lio_synth demo-ds --recipe amplitude_raw --out /tmp/feat
lio profiles fit --results-dir /tmp/lio_synth demo-ds --method pca --out /tmp/pca
lio profiles project --results-dir /tmp/lio_synth --dataset demo-ds --model /tmp/pca --out /tmp/proj
lio profiles compare --results-dir /tmp/lio_synth demo-ds --a RUN_A --b RUN_B
lio profiles distances --results-dir /tmp/lio_synth demo-ds --out /tmp/dist
lio profiles fit --results-dir /tmp/lio_synth demo-ds --method functional-pca --hole 5 --detector opt101 --out /tmp/fpca
lio profiles validate --results-dir /tmp/lio_synth demo-ds --target new-preparation
lio profiles effects --results-dir /tmp/lio_synth demo-ds --design food_label,day
lio profiles trends --results-dir /tmp/lio_synth demo-ds --as-of 2026-01-03T00:00:00+00:00
lio profiles gallery --results-dir /tmp/lio_synth demo-ds
lio profiles report /tmp/pca --out /tmp/report
lio profiles verify /tmp/pca
```

Built-in recipes: `amplitude_raw`, `amplitude_shape_snv`, `amplitude_vector_norm`, `amplitude_msc`, `reference_relative`, `o_envelope`.

## Scientific contracts (summary)

- Raw cube rows are preserved; Explore never calls `analyse()`.
- Default selection: `state=lit`, `phase=P2`, `direction=down`, `rep=0`, `kind=measure`.
- Blinds / missing / weak denominators are explicit reasons, not zeros.
- Fit vs transform are separate; frozen PCA/fPCA bundles use NPZ (`allow_pickle=False`), never pickle.
- Preparation-level aggregation is the default fitting unit; unknown independence is labeled.
- Synthetic fixtures are always marked `synthetic: true` and must not be reported as instrument performance.

## Physical validation (not done by software)

- Real food acquisitions with preparation/lot annotations
- Reference-protocol qualification on the bench
- Discrimination / trend claims on measured data
- Hardware/session authorization for live scans
