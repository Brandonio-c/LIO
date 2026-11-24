"""Fit/transform orchestration over datasets (fit ≠ transform; no leakage)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lio.food_profiles.artifacts import load_bundle, write_bundle
from lio.food_profiles.distances import cluster_from_distances, pairwise_distances
from lio.food_profiles.features import (
    FeatureBatch,
    aggregate_by_preparation,
    extract_run_vector,
    stack_batches,
)
from lio.food_profiles.functional import fit_fpca, transform_fpca
from lio.food_profiles.metadata import Dataset, resolve_run_folder
from lio.food_profiles.ordination import FittedPCA, fit_pca, transform_pca
from lio.food_profiles.preprocessing import FittedPreprocess
from lio.food_profiles.runs import open_run
from lio.food_profiles.schema import BUILTIN_RECIPES, Recipe


@dataclass
class FittedPipeline:
    recipe: Recipe
    pca: FittedPCA | None = None
    preprocess_only: FittedPreprocess | None = None


def build_feature_batch(
    results_root: Path,
    dataset: Dataset,
    recipe: Recipe | str,
    *,
    reference_run_id: str | None = None,
    aggregate: bool = True,
    fingerprint_height_hs: float | None = None,
    include_proxy_h16: bool = False,
) -> FeatureBatch:
    if isinstance(recipe, str):
        recipe = BUILTIN_RECIPES[recipe]
    reference = None
    if reference_run_id:
        reference = open_run(resolve_run_folder(results_root, dataset, reference_run_id))
    runs = []
    for rid in dataset.run_ids:
        folder = resolve_run_folder(results_root, dataset, rid)
        runs.append(open_run(folder))
    # Freeze one fingerprint height for the whole dataset (exact common intersection).
    lock_h = fingerprint_height_hs
    if lock_h is None and recipe.representation not in ("o_envelope",):
        from lio.food_profiles.features import _common_heights

        sets = [_common_heights(r, recipe) for r in runs]
        common: set[float] | None = None
        for hs in sets:
            s = set(hs)
            common = s if common is None else (common & s)
        if common:
            ordered = sorted(common)
            lock_h = float(ordered[len(ordered) // 2])
    prev = getattr(extract_run_vector, "_lock_height_hs", None)
    extract_run_vector._lock_height_hs = lock_h  # type: ignore[attr-defined]
    try:
        batches: list[FeatureBatch] = []
        for rid, run in zip(dataset.run_ids, runs, strict=True):
            ann = dataset.annotations.get(rid) or {}
            prep = ann.get("preparation_id") or run.meta.get("preparation_id")
            batches.append(
                extract_run_vector(
                    run,
                    recipe,
                    reference=reference,
                    preparation_id=prep,
                    include_proxy_h16=include_proxy_h16,
                )
            )
        # Align schemas: intersect feature_ids (handles slight map differences)
        if len(batches) > 1:
            common_f = list(batches[0].feature_ids)
            for b in batches[1:]:
                common_f = [f for f in common_f if f in b.feature_ids]
            if not common_f:
                raise ValueError("no common features across runs")
            aligned: list[FeatureBatch] = []
            for b in batches:
                idx = [b.feature_ids.index(f) for f in common_f]
                aligned.append(
                    FeatureBatch(
                        b.row_ids,
                        b.run_ids,
                        b.preparation_ids,
                        common_f,
                        b.X[:, idx],
                        b.reasons[:, idx],
                        b.source_links,
                        b.recipe,
                        b.warnings,
                        b.units,
                    )
                )
            batches = aligned
        batch = stack_batches(batches)
    finally:
        extract_run_vector._lock_height_hs = prev  # type: ignore[attr-defined]
    if aggregate and recipe.aggregation == "preparation_mean":
        batch = aggregate_by_preparation(batch)
    return batch


def fit_dataset_pca(
    results_root: Path,
    dataset: Dataset,
    recipe: Recipe | str,
    *,
    n_components: int = 2,
    scope: str = "fused",
    reference_run_id: str | None = None,
    out_dir: Path | None = None,
) -> tuple[FittedPCA, FeatureBatch, Any]:
    batch = build_feature_batch(results_root, dataset, recipe, reference_run_id=reference_run_id)
    model = fit_pca(batch, n_components=n_components, scope=scope)
    result = transform_pca(batch, model)
    if out_dir is not None:
        write_bundle(
            out_dir,
            kind="pca",
            recipe=batch.recipe,
            arrays=model.to_npz_dict(),
            payload={
                "scores": result.to_jsonable(),
                "dataset_id": dataset.dataset_id,
                "scope": scope,
            },
            synthetic=dataset.synthetic,
            notes=f"PCA scope={scope}",
            extras={"scope": scope, "n_components": model.n_components},
        )
    return model, batch, result


def project_dataset_pca(
    results_root: Path,
    dataset: Dataset,
    model_dir: Path,
) -> Any:
    meta, arrays, _ = load_bundle(model_dir)
    recipe = Recipe.from_dict(meta["recipe"])
    model = FittedPCA.from_npz_dict(arrays, recipe)
    batch = build_feature_batch(results_root, dataset, recipe)
    # Transform must not refit
    return transform_pca(batch, model)


def compare_runs_payload(
    results_root: Path,
    dataset: Dataset,
    run_a: str,
    run_b: str,
    recipe: Recipe | str = "amplitude_raw",
) -> dict[str, Any]:
    from lio.food_profiles.functional import difference_map
    from lio.food_profiles.runs import heatmap_payload

    if isinstance(recipe, str):
        recipe = BUILTIN_RECIPES[recipe]
    a = open_run(resolve_run_folder(results_root, dataset, run_a))
    b = open_run(resolve_run_folder(results_root, dataset, run_b))
    fa = extract_run_vector(a, recipe)
    fb = extract_run_vector(b, recipe)
    return {
        "run_a": run_a,
        "run_b": run_b,
        "recipe": recipe.to_dict(),
        "features_a": fa.to_jsonable(),
        "features_b": fb.to_jsonable(),
        "heatmap_a": {d: heatmap_payload(a, d) for d in ("opt101", "ingaas")},
        "heatmap_b": {d: heatmap_payload(b, d) for d in ("opt101", "ingaas")},
        "difference": {d: difference_map(a, b, detector=d) for d in ("opt101", "ingaas")},
    }


def distance_bundle(
    results_root: Path,
    dataset: Dataset,
    recipe: Recipe | str,
    *,
    metric: str = "euclidean",
    n_clusters: int = 2,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    batch = build_feature_batch(results_root, dataset, recipe)
    dm = pairwise_distances(batch, metric=metric)  # type: ignore[arg-type]
    try:
        clustered = cluster_from_distances(dm, n_clusters=n_clusters)
    except ImportError as e:
        clustered = dm
        note = str(e)
    else:
        note = "ok"
    payload = clustered.to_jsonable()
    payload["cluster_status"] = note
    if out_dir is not None:
        write_bundle(
            out_dir,
            kind="distances",
            recipe=batch.recipe,
            arrays={"D": clustered.D},
            payload=payload,
            synthetic=dataset.synthetic,
        )
    return payload


def fit_dataset_fpca(
    results_root: Path,
    dataset: Dataset,
    *,
    hole: int = 5,
    detector: str = "opt101",
    n_components: int = 2,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    runs = [open_run(resolve_run_folder(results_root, dataset, rid)) for rid in dataset.run_ids]
    model = fit_fpca(runs, hole=hole, detector=detector, n_components=n_components)
    result = transform_fpca(runs, model)
    payload = result.to_jsonable()
    payload["hole"] = hole
    payload["detector"] = detector
    if out_dir is not None:
        write_bundle(
            out_dir,
            kind="functional_pca",
            recipe=BUILTIN_RECIPES["amplitude_raw"],
            arrays=model.to_npz_dict(),
            payload=payload,
            synthetic=dataset.synthetic,
            extras={"hole": hole, "detector": detector},
        )
    return payload


def gallery_payload(results_root: Path, dataset: Dataset) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for rid in dataset.run_ids:
        ann = dataset.annotations.get(rid) or {}
        folder = resolve_run_folder(results_root, dataset, rid)
        run = open_run(folder)
        food = ann.get("food_label") or run.meta.get("food_label") or "unknown"
        prep = ann.get("preparation_id") or run.meta.get("preparation_id")
        lot = ann.get("lot_id") or run.meta.get("lot_id")
        groups.setdefault(str(food), []).append(
            {
                "run_id": rid,
                "preparation_id": prep,
                "lot_id": lot,
                "sample_id": run.sample_id,
                "synthetic": bool(run.meta.get("synthetic")),
            }
        )
    return {
        "dataset_id": dataset.dataset_id,
        "foods": groups,
        "n_runs": len(dataset.run_ids),
        "synthetic": dataset.synthetic,
    }
