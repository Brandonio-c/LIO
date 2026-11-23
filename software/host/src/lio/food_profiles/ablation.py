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


def held_out_proxy_ablation(
    batch: FeatureBatch,
    *,
    metric: str = "mean_pairwise_distance",
) -> AblationResult:
    """Compare a simple held-out metric with vs without ``proxy_unassigned:`` features.

    ``metric=mean_pairwise_distance`` uses an existing distance idea (no new classifier).
    """
    notes = [
        "h16 features must remain proxy_unassigned — never primary-1850",
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
        metric_name=metric,
        notes=notes,
    )
