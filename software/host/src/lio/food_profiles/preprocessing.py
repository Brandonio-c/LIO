"""Vector normalization, SNV, MSC, scaling - fit on training only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from lio.food_profiles.features import FeatureBatch
from lio.food_profiles.schema import CellReason, Recipe


@dataclass
class FittedPreprocess:
    recipe: Recipe
    feature_ids: list[str]
    msc_reference: np.ndarray | None
    mean: np.ndarray | None
    scale: np.ndarray | None
    block_weights: dict[str, float]

    def to_npz_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "feature_ids": np.array(self.feature_ids),
            "block_weight_keys": np.array(list(self.block_weights.keys())),
            "block_weight_vals": np.array(list(self.block_weights.values()), dtype=np.float64),
        }
        if self.msc_reference is not None:
            out["msc_reference"] = self.msc_reference.astype(np.float64)
        if self.mean is not None:
            out["mean"] = self.mean.astype(np.float64)
        if self.scale is not None:
            out["scale"] = self.scale.astype(np.float64)
        return out

    @classmethod
    def from_npz_dict(cls, data: dict[str, Any], recipe: Recipe) -> FittedPreprocess:
        bw = {}
        keys = data.get("block_weight_keys")
        vals = data.get("block_weight_vals")
        if keys is not None and vals is not None:
            bw = {str(k): float(v) for k, v in zip(keys.tolist(), vals.tolist(), strict=True)}
        return cls(
            recipe=recipe,
            feature_ids=[str(x) for x in data["feature_ids"].tolist()],
            msc_reference=data.get("msc_reference"),
            mean=data.get("mean"),
            scale=data.get("scale"),
            block_weights=bw,
        )


def _rowwise_snv(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return transformed row and reason (OK or FLAT_PROFILE)."""
    finite = np.isfinite(x)
    if finite.sum() < 2:
        return x * np.nan, np.full(x.shape, CellReason.FLAT_PROFILE.value, dtype=object)
    mu = float(np.mean(x[finite]))
    sd = float(np.std(x[finite], ddof=1))
    if sd <= 1e-12:
        out = np.full_like(x, np.nan)
        return out, np.full(x.shape, CellReason.FLAT_PROFILE.value, dtype=object)
    y = (x - mu) / sd
    y[~finite] = np.nan
    reasons = np.where(finite, CellReason.OK.value, CellReason.MISSING.value)
    return y, reasons


def _rowwise_vector_norm(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    finite = np.isfinite(x)
    if not finite.any():
        return x * np.nan, np.full(x.shape, CellReason.ZERO_VECTOR.value, dtype=object)
    nrm = float(np.linalg.norm(x[finite]))
    if nrm <= 1e-12:
        return x * np.nan, np.full(x.shape, CellReason.ZERO_VECTOR.value, dtype=object)
    y = x / nrm
    y[~finite] = np.nan
    reasons = np.where(finite, CellReason.OK.value, CellReason.MISSING.value)
    return y, reasons


def _rowwise_msc(x: np.ndarray, ref: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    finite = np.isfinite(x) & np.isfinite(ref)
    if finite.sum() < 2:
        return x * np.nan, np.full(x.shape, CellReason.FLAT_PROFILE.value, dtype=object)
    # x ≈ a + b * ref  →  corrected = (x - a) / b
    A = np.vstack([np.ones(finite.sum()), ref[finite]]).T
    try:
        coef, _, _, _ = np.linalg.lstsq(A, x[finite], rcond=None)
    except np.linalg.LinAlgError:
        return x * np.nan, np.full(x.shape, CellReason.FLAT_PROFILE.value, dtype=object)
    a, b = float(coef[0]), float(coef[1])
    if abs(b) < 1e-12 or b < 0:
        return x * np.nan, np.full(x.shape, CellReason.FLAT_PROFILE.value, dtype=object)
    y = (x - a) / b
    y[~finite] = np.nan
    reasons = np.where(finite, CellReason.OK.value, CellReason.MISSING.value)
    return y, reasons


def fit_preprocess(batch: FeatureBatch) -> FittedPreprocess:
    recipe = batch.recipe
    X = batch.X.copy()
    msc_ref = None
    if recipe.msc:
        # Mean of finite training rows as MSC reference
        mask = np.isfinite(X)
        col_ok = mask.any(axis=0)
        ref = np.full(X.shape[1], np.nan)
        for j in range(X.shape[1]):
            if col_ok[j]:
                ref[j] = float(np.mean(X[mask[:, j], j]))
        msc_ref = ref
    mean = None
    scale = None
    if recipe.scale in ("mean_center", "autoscaling", "block"):
        mean = np.nanmean(X, axis=0)
    if recipe.scale == "autoscaling":
        scale = np.nanstd(X, axis=0, ddof=1)
        scale = np.where((~np.isfinite(scale)) | (scale < 1e-12), np.nan, scale)
    block_weights = {"opt101": 1.0, "ingaas": 1.0}
    if recipe.scale == "block":
        # Equalize detector block variance on training
        for det in ("opt101", "ingaas"):
            cols = [j for j, fid in enumerate(batch.feature_ids) if fid.startswith(f"{det}:")]
            if not cols:
                continue
            sub = X[:, cols]
            v = float(np.nanvar(sub))
            block_weights[det] = 1.0 / np.sqrt(v) if v > 1e-12 else 1.0
    return FittedPreprocess(recipe, list(batch.feature_ids), msc_ref, mean, scale, block_weights)


def transform_preprocess(batch: FeatureBatch, fitted: FittedPreprocess) -> FeatureBatch:
    if batch.feature_ids != fitted.feature_ids:
        raise ValueError("feature_ids mismatch: transform cannot change schema")
    recipe = fitted.recipe
    X = batch.X.copy()
    reasons = batch.reasons.copy()
    for i in range(X.shape[0]):
        row = X[i]
        if recipe.msc:
            assert fitted.msc_reference is not None
            row, rsn = _rowwise_msc(row, fitted.msc_reference)
            reasons[i] = rsn
        elif recipe.snv:
            row, rsn = _rowwise_snv(row)
            reasons[i] = rsn
        elif recipe.vector_norm:
            row, rsn = _rowwise_vector_norm(row)
            reasons[i] = rsn
        if fitted.mean is not None:
            row = row - fitted.mean
        if fitted.scale is not None:
            with np.errstate(divide="ignore", invalid="ignore"):
                row = row / fitted.scale
        if recipe.scale == "block":
            for j, fid in enumerate(batch.feature_ids):
                det = fid.split(":", 1)[0]
                w = fitted.block_weights.get(det, 1.0)
                row[j] = row[j] * w if np.isfinite(row[j]) else np.nan
        X[i] = row
    return FeatureBatch(
        batch.row_ids,
        batch.run_ids,
        batch.preparation_ids,
        batch.feature_ids,
        X,
        reasons,
        batch.source_links,
        recipe,
        batch.warnings,
        batch.units,
    )
