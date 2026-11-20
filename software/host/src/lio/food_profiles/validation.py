"""Grouped splits, training-only pipeline and nearest-centroid evaluation."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from lio.food_profiles.features import FeatureBatch
from lio.food_profiles.ordination import FittedPCA, fit_pca, transform_pca
from lio.food_profiles.schema import CellReason, finite_json

Target = Literal["new-preparation", "new-lot", "new-day", "new-food"]


@dataclass
class FoldAssignment:
    train_idx: list[int]
    test_idx: list[int]
    group_id: str


@dataclass
class ValidationResult:
    target: str
    n_folds: int
    accuracies: list[float]
    fold_details: list[dict[str, Any]]
    warnings: list[str]
    available: bool
    reason: str

    def to_jsonable(self) -> dict[str, Any]:
        return finite_json(
            {
                "target": self.target,
                "n_folds": self.n_folds,
                "accuracies": self.accuracies,
                "mean_accuracy": float(np.mean(self.accuracies)) if self.accuracies else None,
                "fold_details": self.fold_details,
                "warnings": self.warnings,
                "available": self.available,
                "reason": self.reason,
            }
        )


def _group_key(
    batch: FeatureBatch, i: int, target: Target, meta: list[dict[str, Any]]
) -> str | None:
    m = meta[i] if i < len(meta) else {}
    if target == "new-preparation":
        return batch.preparation_ids[i] or m.get("preparation_id")
    if target == "new-lot":
        return m.get("lot_id")
    if target == "new-day":
        return m.get("day") or m.get("acquisition_day")
    if target == "new-food":
        return m.get("food_label")
    return None


def grouped_leave_one_out(
    batch: FeatureBatch,
    target: Target,
    meta: list[dict[str, Any]],
) -> list[FoldAssignment]:
    groups: dict[str, list[int]] = defaultdict(list)
    missing = 0
    for i in range(batch.n_rows):
        g = _group_key(batch, i, target, meta)
        if not g:
            missing += 1
            continue
        groups[str(g)].append(i)
    if missing == batch.n_rows:
        return []
    folds: list[FoldAssignment] = []
    keys = sorted(groups)
    if len(keys) < 2:
        return []
    for g in keys:
        test = groups[g]
        train = [i for k in keys if k != g for i in groups[k]]
        if not train or not test:
            continue
        folds.append(FoldAssignment(train, test, g))
    return folds


def _subset(batch: FeatureBatch, idx: list[int]) -> FeatureBatch:
    return FeatureBatch(
        [batch.row_ids[i] for i in idx],
        [batch.run_ids[i] for i in idx],
        [batch.preparation_ids[i] for i in idx],
        batch.feature_ids,
        batch.X[idx],
        batch.reasons[idx],
        [batch.source_links[i] for i in idx],
        batch.recipe,
        list(batch.warnings),
        batch.units,
    )


def nearest_centroid_accuracy(
    train_scores: np.ndarray,
    train_labels: list[str],
    test_scores: np.ndarray,
    test_labels: list[str],
) -> tuple[float, list[str]]:
    centroids: dict[str, np.ndarray] = {}
    for lab in set(train_labels):
        rows = [i for i, lab_i in enumerate(train_labels) if lab_i == lab]
        centroids[lab] = np.nanmean(train_scores[rows], axis=0)
    preds: list[str] = []
    correct = 0
    for i, true in enumerate(test_labels):
        row = test_scores[i]
        if not np.isfinite(row).all() or not centroids:
            preds.append("?")
            continue
        best = min(centroids, key=lambda lab: float(np.linalg.norm(row - centroids[lab])))
        preds.append(best)
        if best == true:
            correct += 1
    return correct / max(len(test_labels), 1), preds


def validate_grouped(
    batch: FeatureBatch,
    labels: list[str],
    meta: list[dict[str, Any]],
    *,
    target: Target = "new-preparation",
    n_components: int = 2,
    scope: str = "fused",
) -> ValidationResult:
    warnings: list[str] = []
    if len(labels) != batch.n_rows or len(meta) != batch.n_rows:
        return ValidationResult(target, 0, [], [], warnings, False, "label/meta length mismatch")
    if any(not g for g in (_group_key(batch, i, target, meta) for i in range(batch.n_rows))):
        warnings.append(CellReason.GROUP_METADATA_INSUFFICIENT.value)
    folds = grouped_leave_one_out(batch, target, meta)
    if not folds:
        return ValidationResult(
            target,
            0,
            [],
            [],
            warnings,
            False,
            CellReason.GROUP_METADATA_INSUFFICIENT.value,
        )
    # Class imbalance note
    counts = Counter(labels)
    if min(counts.values()) < 2:
        warnings.append("class_imbalance_or_singleton")
    accuracies: list[float] = []
    details: list[dict[str, Any]] = []
    for fold in folds:
        train_b = _subset(batch, fold.train_idx)
        test_b = _subset(batch, fold.test_idx)
        # Fit ONLY on train - never peek at test
        try:
            model = fit_pca(train_b, n_components=n_components, scope=scope)
        except (ValueError, ImportError) as e:
            details.append({"group": fold.group_id, "error": str(e)})
            continue
        tr = transform_pca(train_b, model)
        te = transform_pca(test_b, model)
        train_labels = [labels[i] for i in fold.train_idx]
        test_labels = [labels[i] for i in fold.test_idx]
        # Only projectable rows
        tr_ok = [i for i, p in enumerate(tr.projectable) if p]
        te_ok = [i for i, p in enumerate(te.projectable) if p]
        if len(tr_ok) < 2 or not te_ok:
            details.append({"group": fold.group_id, "error": "insufficient_projectable"})
            continue
        acc, preds = nearest_centroid_accuracy(
            tr.scores[tr_ok],
            [train_labels[i] for i in tr_ok],
            te.scores[te_ok],
            [test_labels[i] for i in te_ok],
        )
        accuracies.append(acc)
        details.append(
            {
                "group": fold.group_id,
                "accuracy": acc,
                "n_train": len(tr_ok),
                "n_test": len(te_ok),
                "predictions": preds,
                "true": [test_labels[i] for i in te_ok],
                # Fold coordinates stay separate - never merge into one plot space
                "train_scores": tr.scores[tr_ok].tolist(),
                "test_scores": te.scores[te_ok].tolist(),
            }
        )
    return ValidationResult(
        target,
        len(details),
        accuracies,
        details,
        warnings,
        bool(accuracies),
        "ok" if accuracies else "no_successful_folds",
    )


def assert_no_leakage(fitted: FittedPCA, held_out_ids: list[str]) -> None:
    """Training row IDs must not include held-out units."""
    overlap = set(fitted.training_row_ids) & set(held_out_ids)
    if overlap:
        raise AssertionError(f"leakage: training includes held-out {sorted(overlap)}")
