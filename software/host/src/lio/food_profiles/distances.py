"""Amplitude / shape / functional distances and simple clustering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from lio.food_profiles.features import FeatureBatch
from lio.food_profiles.schema import finite_json

Metric = Literal["euclidean", "cosine", "correlation", "manhattan"]


@dataclass
class DistanceMatrix:
    row_ids: list[str]
    metric: str
    D: np.ndarray  # (n, n) symmetric
    linkage: str | None = None
    labels: list[int] | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return finite_json(
            {
                "row_ids": self.row_ids,
                "metric": self.metric,
                "D": self.D,
                "linkage": self.linkage,
                "labels": self.labels,
            }
        )


def pairwise_distances(batch: FeatureBatch, metric: Metric = "euclidean") -> DistanceMatrix:
    X = batch.X
    n = batch.n_rows
    D = np.full((n, n), np.nan)
    for i in range(n):
        D[i, i] = 0.0
        for j in range(i + 1, n):
            a, b = X[i], X[j]
            mask = np.isfinite(a) & np.isfinite(b)
            if mask.sum() < 2:
                continue
            aa, bb = a[mask], b[mask]
            if metric == "euclidean":
                d = float(np.linalg.norm(aa - bb))
            elif metric == "manhattan":
                d = float(np.sum(np.abs(aa - bb)))
            elif metric == "cosine":
                na, nb = float(np.linalg.norm(aa)), float(np.linalg.norm(bb))
                if na < 1e-12 or nb < 1e-12:
                    continue
                d = 1.0 - float(np.dot(aa, bb) / (na * nb))
            elif metric == "correlation":
                if aa.std() < 1e-12 or bb.std() < 1e-12:
                    continue
                d = 1.0 - float(np.corrcoef(aa, bb)[0, 1])
            else:
                raise ValueError(f"unknown metric: {metric}")
            D[i, j] = D[j, i] = d
    return DistanceMatrix(list(batch.row_ids), metric, D)


def cluster_from_distances(
    dm: DistanceMatrix, *, n_clusters: int = 2, linkage: str = "average"
) -> DistanceMatrix:
    try:
        from scipy.cluster.hierarchy import fcluster
        from scipy.cluster.hierarchy import linkage as sci_linkage
        from scipy.spatial.distance import squareform
    except ImportError as e:
        raise ImportError(
            "clustering requires optional extra 'profiles' (scipy). "
            "Install with: pip install 'lio[profiles]'"
        ) from e
    # Condensed form needs finite upper triangle
    n = dm.D.shape[0]
    if n < 2:
        return DistanceMatrix(dm.row_ids, dm.metric, dm.D, linkage, [0] * n)
    D = dm.D.copy()
    # Fill NaN with large finite for clustering only (flagged)
    finite = np.isfinite(D)
    if not finite.all():
        fill = float(np.nanmax(D[finite])) * 10 + 1.0 if finite.any() else 1.0
        D = np.where(finite, D, fill)
        np.fill_diagonal(D, 0.0)
    condensed = squareform(D, checks=False)
    Z = sci_linkage(condensed, method=linkage)
    labels = fcluster(Z, t=n_clusters, criterion="maxclust").tolist()
    return DistanceMatrix(dm.row_ids, dm.metric, dm.D, linkage, [int(x) for x in labels])


def integrated_curve_distance(
    heights: np.ndarray,
    ya: np.ndarray,
    yb: np.ndarray,
    *,
    weights: np.ndarray | None = None,
) -> float:
    """Trapezoidal L2 distance along physical height (no peak warping)."""
    mask = np.isfinite(heights) & np.isfinite(ya) & np.isfinite(yb)
    if mask.sum() < 2:
        return float("nan")
    h = heights[mask]
    diff = ya[mask] - yb[mask]
    if weights is not None:
        w = weights[mask]
        diff = diff * np.sqrt(np.clip(w, 0, None))
    order = np.argsort(h)
    h, diff = h[order], diff[order]
    # NumPy >= 2.0 has trapezoid; older releases only trapz (removed in 2.5).
    trapezoid = getattr(np, "trapezoid", None) or getattr(np, "trapz")  # noqa: B009
    return float(np.sqrt(trapezoid(diff**2, h)))
