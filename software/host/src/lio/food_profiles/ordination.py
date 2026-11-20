"""Frozen PCA fit/transform with loadings, scores and residuals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from lio.food_profiles.features import FeatureBatch
from lio.food_profiles.preprocessing import FittedPreprocess, fit_preprocess, transform_preprocess
from lio.food_profiles.schema import CellReason, Recipe, finite_json


def _require_sklearn() -> Any:
    try:
        from sklearn.decomposition import PCA
    except ImportError as e:
        raise ImportError(
            "PCA requires optional extra 'profiles' (scikit-learn). "
            "Install with: pip install 'lio[profiles]'"
        ) from e
    return PCA


@dataclass
class FittedPCA:
    recipe: Recipe
    feature_ids: list[str]
    preprocess: FittedPreprocess
    n_components: int
    mean: np.ndarray  # of preprocessed training matrix
    components: np.ndarray  # (n_components, n_features)
    explained_variance: np.ndarray
    explained_variance_ratio: np.ndarray
    training_row_ids: list[str]
    detector_mask: np.ndarray | None  # True = included feature
    scope: str  # fused | opt101 | ingaas

    def to_npz_dict(self) -> dict[str, Any]:
        out = {
            "feature_ids": np.array(self.feature_ids),
            "n_components": np.array([self.n_components]),
            "mean": self.mean.astype(np.float64),
            "components": self.components.astype(np.float64),
            "explained_variance": self.explained_variance.astype(np.float64),
            "explained_variance_ratio": self.explained_variance_ratio.astype(np.float64),
            "training_row_ids": np.array(self.training_row_ids),
            "scope": np.array([self.scope]),
            **{f"pp_{k}": v for k, v in self.preprocess.to_npz_dict().items()},
        }
        if self.detector_mask is not None:
            out["detector_mask"] = self.detector_mask.astype(np.bool_)
        return out

    @classmethod
    def from_npz_dict(cls, data: dict[str, Any], recipe: Recipe) -> FittedPCA:
        pp_keys = {k[3:]: data[k] for k in data if k.startswith("pp_")}
        preprocess = FittedPreprocess.from_npz_dict(pp_keys, recipe)
        return cls(
            recipe=recipe,
            feature_ids=[str(x) for x in data["feature_ids"].tolist()],
            preprocess=preprocess,
            n_components=int(data["n_components"][0]),
            mean=data["mean"].astype(np.float64),
            components=data["components"].astype(np.float64),
            explained_variance=data["explained_variance"].astype(np.float64),
            explained_variance_ratio=data["explained_variance_ratio"].astype(np.float64),
            training_row_ids=[str(x) for x in data["training_row_ids"].tolist()],
            detector_mask=data["detector_mask"].astype(bool) if "detector_mask" in data else None,
            scope=str(data["scope"][0]),
        )


@dataclass
class PCAResult:
    scores: np.ndarray  # (n_rows, n_components)
    residuals: np.ndarray  # (n_rows,) SPE / Q residual
    projectable: np.ndarray  # bool
    reasons: list[str]
    loadings: np.ndarray  # components
    explained_variance_ratio: np.ndarray
    row_ids: list[str]
    feature_ids: list[str]

    def to_jsonable(self) -> dict[str, Any]:
        return finite_json(
            {
                "scores": self.scores,
                "residuals": self.residuals,
                "projectable": self.projectable.tolist(),
                "reasons": self.reasons,
                "loadings": self.loadings,
                "explained_variance_ratio": self.explained_variance_ratio,
                "row_ids": self.row_ids,
                "feature_ids": self.feature_ids,
            }
        )


def _feature_mask(feature_ids: list[str], scope: str) -> np.ndarray:
    if scope == "fused":
        return np.ones(len(feature_ids), dtype=bool)
    return np.array([fid.startswith(f"{scope}:") for fid in feature_ids], dtype=bool)


def _complete_rows(X: np.ndarray) -> np.ndarray:
    return np.isfinite(X).all(axis=1)


def fit_pca(
    batch: FeatureBatch,
    *,
    n_components: int = 2,
    scope: str = "fused",
) -> FittedPCA:
    """Fit PCA on a FeatureBatch (already preparation-aggregated if desired)."""
    PCA = _require_sklearn()
    if scope not in ("fused", "opt101", "ingaas"):
        raise ValueError(f"unknown PCA scope: {scope}")
    preprocess = fit_preprocess(batch)
    prepped = transform_preprocess(batch, preprocess)
    mask = _feature_mask(prepped.feature_ids, scope)
    if not mask.any():
        raise ValueError(f"no features for scope {scope}")
    X = prepped.X[:, mask]
    ok = _complete_rows(X)
    if ok.sum() < 2:
        raise ValueError("need at least 2 complete rows for PCA")
    X_fit = X[ok]
    # Imputation forbidden: only complete rows
    n_comp = min(n_components, X_fit.shape[0] - 1, X_fit.shape[1])
    if n_comp < 1:
        raise ValueError("insufficient rank for PCA")
    pca = PCA(n_components=n_comp, svd_solver="full")
    pca.fit(X_fit)
    return FittedPCA(
        recipe=batch.recipe,
        feature_ids=list(batch.feature_ids),
        preprocess=preprocess,
        n_components=n_comp,
        mean=pca.mean_.astype(np.float64),
        components=pca.components_.astype(np.float64),
        explained_variance=pca.explained_variance_.astype(np.float64),
        explained_variance_ratio=pca.explained_variance_ratio_.astype(np.float64),
        training_row_ids=[batch.row_ids[i] for i in range(batch.n_rows) if ok[i]],
        detector_mask=mask,
        scope=scope,
    )


def transform_pca(batch: FeatureBatch, fitted: FittedPCA) -> PCAResult:
    if batch.feature_ids != fitted.feature_ids:
        raise ValueError("feature_ids mismatch: transform cannot change schema")
    prepped = transform_preprocess(batch, fitted.preprocess)
    mask = (
        fitted.detector_mask
        if fitted.detector_mask is not None
        else np.ones(batch.n_features, dtype=bool)
    )
    X = prepped.X[:, mask]
    scores = np.full((batch.n_rows, fitted.n_components), np.nan)
    residuals = np.full(batch.n_rows, np.nan)
    projectable = np.zeros(batch.n_rows, dtype=bool)
    reasons: list[str] = []
    for i in range(batch.n_rows):
        row = X[i]
        if not np.isfinite(row).all():
            reasons.append(CellReason.PROJECTION_NOT_SUPPORTED.value)
            continue
        xc = row - fitted.mean
        sc = xc @ fitted.components.T
        recon = sc @ fitted.components + fitted.mean
        scores[i] = sc
        residuals[i] = float(np.sum((row - recon) ** 2))
        projectable[i] = True
        reasons.append(CellReason.OK.value)
    return PCAResult(
        scores=scores,
        residuals=residuals,
        projectable=projectable,
        reasons=reasons,
        loadings=fitted.components,
        explained_variance_ratio=fitted.explained_variance_ratio,
        row_ids=list(batch.row_ids),
        feature_ids=[fid for fid, m in zip(batch.feature_ids, mask, strict=True) if m],
    )
