"""Crossed-design ASCA (ANOVA simultaneous component analysis) for supported designs."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np

from lio.food_profiles.features import FeatureBatch
from lio.food_profiles.schema import CellReason, finite_json


@dataclass
class ASCAResult:
    factors: list[str]
    available: bool
    reason: str
    effect_ss: dict[str, float]
    effect_scores: dict[str, list[list[float]]]
    effect_loadings: dict[str, list[list[float]]]
    residual_ss: float
    warnings: list[str]

    def to_jsonable(self) -> dict[str, Any]:
        return finite_json(
            {
                "factors": self.factors,
                "available": self.available,
                "reason": self.reason,
                "effect_ss": self.effect_ss,
                "effect_scores": self.effect_scores,
                "effect_loadings": self.effect_loadings,
                "residual_ss": self.residual_ss,
                "warnings": self.warnings,
            }
        )


def _factor_levels(meta: list[dict[str, Any]], factors: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in factors:
        vals = [str(m.get(f) or "") for m in meta]
        if any(not v for v in vals):
            raise ValueError(f"missing levels for factor {f}")
        out[f] = vals
    return out


def _is_balanced_crossed(levels: dict[str, list[str]], factors: list[str]) -> bool:
    n = len(next(iter(levels.values())))
    uniq = {f: sorted(set(levels[f])) for f in factors}
    # Every combination should appear the same number of times
    combos = list(product(*(uniq[f] for f in factors)))
    counts: dict[tuple[str, ...], int] = {c: 0 for c in combos}
    for i in range(n):
        key = tuple(levels[f][i] for f in factors)
        if key not in counts:
            return False
        counts[key] += 1
    vals = list(counts.values())
    return bool(vals) and min(vals) == max(vals) and min(vals) >= 1


def _effect_matrix(X: np.ndarray, factor_vals: list[str]) -> np.ndarray:
    """Centered main-effect contribution (level means - grand mean)."""
    grand = np.nanmean(X, axis=0)
    out = np.zeros_like(X)
    for lev in sorted(set(factor_vals)):
        idx = [i for i, v in enumerate(factor_vals) if v == lev]
        mu = np.nanmean(X[idx], axis=0) - grand
        for i in idx:
            out[i] = mu
    return out


def _pca_effect(E: np.ndarray, n_components: int = 2) -> tuple[np.ndarray, np.ndarray, float]:
    """Return scores, loadings, SS for one effect matrix."""
    # Rows that are constant within level still span level means
    ok = np.isfinite(E).all(axis=1)
    if ok.sum() < 1:
        return np.zeros((E.shape[0], 0)), np.zeros((0, E.shape[1])), 0.0
    Ec = E[ok] - np.mean(E[ok], axis=0)
    ss = float(np.sum(Ec**2))
    if ss < 1e-18:
        return np.zeros((E.shape[0], 0)), np.zeros((0, E.shape[1])), 0.0
    _, s, Vt = np.linalg.svd(Ec, full_matrices=False)
    k = min(n_components, len(s))
    loadings = Vt[:k]
    scores_ok = Ec @ loadings.T
    scores = np.full((E.shape[0], k), np.nan)
    scores[ok] = scores_ok
    return scores, loadings, ss


def asca(
    batch: FeatureBatch,
    meta: list[dict[str, Any]],
    factors: list[str],
    *,
    n_components: int = 2,
) -> ASCAResult:
    warnings: list[str] = []
    if len(meta) != batch.n_rows:
        return ASCAResult(factors, False, "meta length mismatch", {}, {}, {}, 0.0, warnings)
    if len(factors) < 1 or len(factors) > 2:
        return ASCAResult(
            factors,
            False,
            CellReason.DESIGN_UNSUPPORTED.value,
            {},
            {},
            {},
            0.0,
            [*warnings, "supported: 1-2 crossed factors"],
        )
    try:
        levels = _factor_levels(meta, factors)
    except ValueError as e:
        return ASCAResult(
            factors, False, CellReason.GROUP_METADATA_INSUFFICIENT.value, {}, {}, {}, 0.0, [str(e)]
        )
    if not _is_balanced_crossed(levels, factors):
        return ASCAResult(
            factors,
            False,
            CellReason.DESIGN_UNSUPPORTED.value,
            {},
            {},
            {},
            0.0,
            [*warnings, "design must be balanced and crossed; confounded/unbalanced refused"],
        )
    X = batch.X.copy()
    if not np.isfinite(X).all():
        # Drop incomplete feature columns for ASCA (explicit)
        col_ok = np.isfinite(X).all(axis=0)
        if not col_ok.any():
            return ASCAResult(factors, False, "no complete features", {}, {}, {}, 0.0, warnings)
        X = X[:, col_ok]
        warnings.append("dropped_incomplete_feature_columns")
    grand = np.mean(X, axis=0)
    Xc = X - grand
    effect_mats = {f: _effect_matrix(X, levels[f]) for f in factors}
    if len(factors) == 2:
        # Interaction = residual after removing main effects from centered data
        inter = Xc - effect_mats[factors[0]] - effect_mats[factors[1]]
        # Re-express interaction as level-combination means
        combo = [f"{levels[factors[0]][i]}|{levels[factors[1]][i]}" for i in range(batch.n_rows)]
        effect_mats["interaction"] = _effect_matrix(Xc + grand, combo)
        # Prefer classical residual interaction estimate
        effect_mats["interaction"] = inter
    explained = sum(effect_mats.values())
    residual = Xc - explained
    effect_ss: dict[str, float] = {}
    effect_scores: dict[str, list[list[float]]] = {}
    effect_loadings: dict[str, list[list[float]]] = {}
    for name, E in effect_mats.items():
        sc, ld, ss = _pca_effect(E, n_components=n_components)
        effect_ss[name] = ss
        effect_scores[name] = sc.tolist()
        effect_loadings[name] = ld.tolist()
    res_ss = float(np.sum(residual**2))
    return ASCAResult(
        factors,
        True,
        "ok",
        effect_ss,
        effect_scores,
        effect_loadings,
        res_ss,
        warnings,
    )
