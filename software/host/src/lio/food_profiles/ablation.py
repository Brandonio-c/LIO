"""Held-out ablation for ``proxy_unassigned:`` (h16) features through existing tools.

Does not add a new classifier project. Uses feature-batch masks and optional
PCA/distance metrics already in food_profiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from lio.food_profiles.features import FeatureBatch

PROXY_PREFIX = "proxy_unassigned:"


@dataclass
class AblationResult:
    feature_ids_full: list[str]
    feature_ids_ablated: list[str]
    removed: list[str]
    X_full: np.ndarray
    X_ablated: np.ndarray
    metric_full: float | None
    metric_ablated: float | None
    metric_name: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_ids_full": self.feature_ids_full,
            "feature_ids_ablated": self.feature_ids_ablated,
            "removed": self.removed,
            "n_features_full": len(self.feature_ids_full),
            "n_features_ablated": len(self.feature_ids_ablated),
            "metric_full": self.metric_full,
            "metric_ablated": self.metric_ablated,
            "metric_name": self.metric_name,
            "notes": list(self.notes),
            "delta_metric": (
                None
                if self.metric_full is None or self.metric_ablated is None
                else float(self.metric_ablated - self.metric_full)
            ),
        }


def proxy_unassigned_mask(feature_ids: list[str]) -> np.ndarray:
    """Boolean mask: True where feature id is in the unassigned proxy namespace."""
    return np.array([fid.startswith(PROXY_PREFIX) for fid in feature_ids], dtype=bool)


def drop_proxy_unassigned(batch: FeatureBatch) -> tuple[FeatureBatch, list[str]]:
    """Return a copy of ``batch`` with ``proxy_unassigned:`` columns removed."""
    mask = proxy_unassigned_mask(batch.feature_ids)
    keep = ~mask
    removed = [fid for fid, m in zip(batch.feature_ids, mask, strict=True) if m]
    if not removed:
        return batch, []
    new = FeatureBatch(
        row_ids=list(batch.row_ids),
        run_ids=list(batch.run_ids),
        preparation_ids=list(batch.preparation_ids),
        feature_ids=[fid for fid, k in zip(batch.feature_ids, keep, strict=True) if k],
        X=np.asarray(batch.X)[:, keep],
        reasons=np.asarray(batch.reasons)[:, keep] if batch.reasons.size else batch.reasons,
        source_links=list(batch.source_links),
        recipe=batch.recipe,
        warnings=[*batch.warnings, f"ablated {len(removed)} proxy_unassigned features"],
        units=batch.units,
    )
    return new, removed


def _pairwise_mean_distance(X: np.ndarray) -> float | None:
    if X.size == 0 or X.shape[0] < 2:
        return None
    # Nan-safe: use columns that are finite for all rows.
    ok = np.all(np.isfinite(X), axis=0)
    if not np.any(ok):
        return None
    Z = X[:, ok]
    diffs = Z[:, None, :] - Z[None, :, :]
    d = np.sqrt(np.sum(diffs * diffs, axis=-1))
    iu = np.triu_indices(Z.shape[0], k=1)
    vals = d[iu]
    if vals.size == 0:
        return None
    return float(np.mean(vals))


def full_batch_distance_ablation(
    batch: FeatureBatch,
    *,
    metric: str = "mean_pairwise_distance",
) -> AblationResult:
    """Honest full-batch pairwise distance with vs without proxy columns (D18).

    This is **not** held-out predictive value — dropping dimensions changes
    Euclidean distance mechanically. Prefer ``grouped_held_out_proxy_ablation``
    when independent group labels exist.
    """
    notes = [
        "h16 features must remain proxy_unassigned — never primary-1850",
        "FULL-BATCH distance ablation (not held-out predictive value)",
        "ablation is a software helper; not a measured food-discrimination claim",
    ]
    removed_mask = proxy_unassigned_mask(batch.feature_ids)
    removed = [fid for fid, m in zip(batch.feature_ids, removed_mask, strict=True) if m]
    ablated, _ = drop_proxy_unassigned(batch)
    if metric != "mean_pairwise_distance":
        raise ValueError(f"unsupported ablation metric {metric!r}")
    m_full = _pairwise_mean_distance(np.asarray(batch.X, dtype=float))
    m_ab = _pairwise_mean_distance(np.asarray(ablated.X, dtype=float))
    if not removed:
        notes.append("no proxy_unassigned features present; ablated == full")
    return AblationResult(
        feature_ids_full=list(batch.feature_ids),
        feature_ids_ablated=list(ablated.feature_ids),
        removed=removed,
        X_full=np.asarray(batch.X),
        X_ablated=np.asarray(ablated.X),
        metric_full=m_full,
        metric_ablated=m_ab,
        metric_name=f"full_batch_{metric}",
        notes=notes,
    )


def held_out_proxy_ablation(
    batch: FeatureBatch,
    *,
    metric: str = "mean_pairwise_distance",
) -> AblationResult:
    """Backward-compatible alias — delegates to honest full-batch distance (D18)."""
    return full_batch_distance_ablation(batch, metric=metric)


def grouped_held_out_proxy_ablation(
    batch: FeatureBatch,
    *,
    group_ids: list[str] | None = None,
    metric: str = "mean_pairwise_distance",
) -> AblationResult:
    """Grouped held-out proxy ablation when independent groups are labelled (D18).

    Requires equal support across groups. Insufficient groups → unavailable notes.
    """
    notes = [
        "h16 features must remain proxy_unassigned — never primary-1850",
        "grouped held-out ablation requires independent preparation/lot/day groups",
    ]
    groups = (
        list(group_ids) if group_ids is not None else [str(p or "") for p in batch.preparation_ids]
    )
    if len(groups) != batch.n_rows:
        notes.append("unavailable: group_ids length mismatch")
        return AblationResult(
            feature_ids_full=list(batch.feature_ids),
            feature_ids_ablated=list(batch.feature_ids),
            removed=[],
            X_full=np.asarray(batch.X),
            X_ablated=np.asarray(batch.X),
            metric_full=None,
            metric_ablated=None,
            metric_name="grouped_held_out_unavailable",
            notes=notes,
        )
    uniq = sorted({g for g in groups if g})
    if len(uniq) < 2:
        notes.append("unavailable: fewer than 2 labelled independent groups")
        return AblationResult(
            feature_ids_full=list(batch.feature_ids),
            feature_ids_ablated=list(batch.feature_ids),
            removed=[],
            X_full=np.asarray(batch.X),
            X_ablated=np.asarray(batch.X),
            metric_full=None,
            metric_ablated=None,
            metric_name="grouped_held_out_unavailable",
            notes=notes,
        )
    # Leave-one-group-out: score the HELD-OUT (left-out) rows only (CE13).
    # Training/keep rows must not contribute to the reported fold metric.
    removed_mask = proxy_unassigned_mask(batch.feature_ids)
    removed = [fid for fid, m in zip(batch.feature_ids, removed_mask, strict=True) if m]
    ablated, _ = drop_proxy_unassigned(batch)
    X = np.asarray(batch.X, dtype=float)
    Xa = np.asarray(ablated.X, dtype=float)
    full_scores: list[float] = []
    ab_scores: list[float] = []
    for g in uniq:
        held = np.array([gi == g for gi in groups], dtype=bool)
        if held.sum() < 2:
            continue
        mf = _pairwise_mean_distance(X[held])
        ma = _pairwise_mean_distance(Xa[held])
        if mf is not None:
            full_scores.append(mf)
        if ma is not None:
            ab_scores.append(ma)
    notes.append("metric evaluated on held-out (left-out) group rows only")
    notes.append("descriptive distance summary: not predictive validation of proxy value")
    if not full_scores:
        notes.append("unavailable: no held-out fold with >=2 rows")
        m_full = m_ab = None
        name = "grouped_held_out_unavailable"
    else:
        m_full = float(np.mean(full_scores))
        m_ab = float(np.mean(ab_scores)) if ab_scores else None
        # Descriptive only: within-held-group spread, NOT predictive accuracy (A22).
        name = f"grouped_held_out_descriptive_within_group_{metric}"
        notes.append(f"n_groups={len(uniq)} n_folds={len(full_scores)}")
    return AblationResult(
        feature_ids_full=list(batch.feature_ids),
        feature_ids_ablated=list(ablated.feature_ids),
        removed=removed,
        X_full=X,
        X_ablated=Xa,
        metric_full=m_full,
        metric_ablated=m_ab,
        metric_name=name,
        notes=notes,
    )


def proxy_predictive_comparison(
    batch: FeatureBatch,
    labels: list[str],
    meta: list[dict[str, Any]],
    *,
    target: str = "new-preparation",
) -> dict[str, Any]:
    """Predictive value of ``proxy_unassigned`` features on held-out groups (A22).

    Reuses the existing grouped validation (``validate_grouped``: leave-one-group
    -out, PCA fitted on training groups only, nearest-centroid on the held-out
    group) for the FULL and the PROXY-REMOVED feature sets on the same rows and
    therefore the same folds. Reports paired per-fold accuracy and the mean
    difference. Without proxy columns, labels, >= 2 independent groups or the
    optional profiles dependencies, predictive value is unavailable.
    """
    from lio.food_profiles.validation import validate_grouped

    out: dict[str, Any] = {
        "estimand": "held-out-group nearest-centroid accuracy, full minus proxy-removed",
        "notes": ["h16 stays proxy_unassigned; never primary-1850",
                  "synthetic or single-epoch results are not food-discrimination claims"],
    }  # fmt: skip
    if not proxy_unassigned_mask(batch.feature_ids).any():
        out.update(available=False, reason="no proxy_unassigned features (opt-in not given?)")
        return out
    if len({str(x) for x in labels}) < 2:
        out.update(available=False, reason="need >= 2 label classes for a predictive estimand")
        return out
    ablated, removed = drop_proxy_unassigned(batch)
    full = validate_grouped(batch, labels, meta, target=target)  # type: ignore[arg-type]
    abl = validate_grouped(ablated, labels, meta, target=target)  # type: ignore[arg-type]
    fa = {d["group"]: d["accuracy"] for d in full.fold_details if "accuracy" in d}
    fb = {d["group"]: d["accuracy"] for d in abl.fold_details if "accuracy" in d}
    shared = sorted(set(fa) & set(fb))
    out["removed"] = removed
    if not shared:
        why = f"no comparable folds (full: {full.reason}; ablated: {abl.reason})"
        out.update(available=False, reason=why)
        return out
    diffs = [fa[g] - fb[g] for g in shared]
    out.update(
        available=True, folds=shared, n_folds=len(shared),
        accuracy_full=[fa[g] for g in shared], accuracy_ablated=[fb[g] for g in shared],
        mean_difference=float(np.mean(diffs)),
        warnings=sorted(set(full.warnings) | set(abl.warnings)),
    )  # fmt: skip
    return out
