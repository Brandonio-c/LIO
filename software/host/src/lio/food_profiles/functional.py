"""Whole-height grids, difference maps and discretized functional PCA."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from lio.food_profiles.runs import RunData, curve_payload
from lio.food_profiles.schema import DEFAULT_SELECTION, CellReason, finite_json


@dataclass
class HeightGrid:
    heights_hs: np.ndarray
    weights: np.ndarray  # quadrature weights
    max_gap_hs: float

    def to_npz_dict(self) -> dict[str, Any]:
        return {
            "heights_hs": self.heights_hs.astype(np.float64),
            "weights": self.weights.astype(np.float64),
            "max_gap_hs": np.array([self.max_gap_hs]),
        }

    @classmethod
    def from_npz_dict(cls, data: dict[str, Any]) -> HeightGrid:
        return cls(
            data["heights_hs"].astype(np.float64),
            data["weights"].astype(np.float64),
            float(data["max_gap_hs"][0]),
        )


def trapz_weights(heights: np.ndarray) -> np.ndarray:
    """Composite trapezoidal quadrature weights on a sorted height grid."""
    h = np.asarray(heights, dtype=np.float64)
    n = len(h)
    w = np.zeros(n)
    if n < 2:
        return w
    for i in range(n - 1):
        dh = h[i + 1] - h[i]
        w[i] += 0.5 * dh
        w[i + 1] += 0.5 * dh
    return w


def common_height_grid(
    runs: list[RunData],
    *,
    hole: int,
    detector: str,
    selection: dict[str, Any] | None = None,
    max_gap_hs: float = 5000.0,
) -> HeightGrid:
    """Exact common heights across runs (intersection). Reject large gaps."""
    sets: list[set[float]] = []
    for run in runs:
        hs: set[float] = set()
        for _, r in run.iter_selected(selection):
            try:
                if r.get("detector") != detector:
                    continue
                if int(float(r["hole"])) != hole:
                    continue
                hs.add(float(r["height_hs"]))
            except (KeyError, ValueError):
                continue
        sets.append(hs)
    if not sets:
        raise ValueError("no heights")
    common = sorted(set.intersection(*sets)) if sets else []
    if len(common) < 2:
        raise ValueError("insufficient common heights for functional analysis")
    arr = np.asarray(common, dtype=np.float64)
    gaps = np.diff(arr)
    if float(np.max(gaps)) > max_gap_hs:
        raise ValueError(
            f"height gap {float(np.max(gaps)):g} exceeds max_gap_hs={max_gap_hs:g}; "
            "interpolation/extrapolation is not performed"
        )
    return HeightGrid(arr, trapz_weights(arr), max_gap_hs)


def sample_curves_on_grid(
    runs: list[RunData],
    grid: HeightGrid,
    *,
    hole: int,
    detector: str,
    selection: dict[str, Any] | None = None,
) -> tuple[np.ndarray, list[str], list[str]]:
    """Exact-height sampling only (no peak warping / no interpolation)."""
    Y = np.full((len(runs), len(grid.heights_hs)), np.nan)
    row_ids: list[str] = []
    reasons: list[str] = []
    hset = {float(h): i for i, h in enumerate(grid.heights_hs)}
    for ri, run in enumerate(runs):
        row_ids.append(run.run_id)
        if run.is_blind(hole, detector):
            reasons.append(CellReason.BLIND.value)
            continue
        vals: dict[float, list[float]] = {}
        for _, r in run.iter_selected(selection):
            try:
                if r.get("detector") != detector or int(float(r["hole"])) != hole:
                    continue
                h = float(r["height_hs"])
                if h not in hset:
                    continue
                vals.setdefault(h, []).append(float(r["net_counts"]))
            except (KeyError, ValueError):
                continue
        ok = True
        for h, j in hset.items():
            if h not in vals:
                ok = False
                break
            Y[ri, j] = float(np.mean(vals[h]))
        reasons.append(CellReason.OK.value if ok else CellReason.UNSUPPORTED_HEIGHT.value)
    return Y, row_ids, reasons


def difference_map(
    run_a: RunData,
    run_b: RunData,
    *,
    detector: str,
    selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Hole x height difference of mean nets (exact common heights only)."""
    from lio.food_profiles.runs import heatmap_payload

    ha = heatmap_payload(run_a, detector, selection)
    hb = heatmap_payload(run_b, detector, selection)
    common = sorted(set(ha["heights_hs"]) & set(hb["heights_hs"]))
    if not common:
        return {
            "available": False,
            "reason": CellReason.UNSUPPORTED_HEIGHT.value,
            "heights_hs": [],
            "diff": [],
        }
    ia = {h: i for i, h in enumerate(ha["heights_hs"])}
    ib = {h: i for i, h in enumerate(hb["heights_hs"])}
    diff: list[list[float | None]] = []
    for hole_i in range(16):
        row: list[float | None] = []
        for h in common:
            va = ha["net"][hole_i][ia[h]]
            vb = hb["net"][hole_i][ib[h]]
            if va is None or vb is None:
                row.append(None)
            else:
                row.append(float(va) - float(vb))
        diff.append(row)
    return {
        "available": True,
        "reason": "ok",
        "run_a": run_a.run_id,
        "run_b": run_b.run_id,
        "detector": detector,
        "heights_hs": common,
        "holes": list(range(1, 17)),
        "diff": diff,
        "note": "exact common heights only; no peak alignment",
    }


@dataclass
class FittedFPCA:
    hole: int
    detector: str
    grid: HeightGrid
    n_components: int
    mean: np.ndarray
    components: np.ndarray  # (n_components, n_heights) - eigenfunctions on grid
    explained_variance: np.ndarray
    explained_variance_ratio: np.ndarray
    training_row_ids: list[str]
    selection: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_SELECTION))

    def to_npz_dict(self) -> dict[str, Any]:
        return {
            "hole": np.array([self.hole]),
            "detector": np.array([self.detector]),
            "n_components": np.array([self.n_components]),
            "mean": self.mean.astype(np.float64),
            "components": self.components.astype(np.float64),
            "explained_variance": self.explained_variance.astype(np.float64),
            "explained_variance_ratio": self.explained_variance_ratio.astype(np.float64),
            "training_row_ids": np.array(self.training_row_ids),
            **{f"grid_{k}": v for k, v in self.grid.to_npz_dict().items()},
        }

    @classmethod
    def from_npz_dict(cls, data: dict[str, Any]) -> FittedFPCA:
        grid = HeightGrid.from_npz_dict({k[5:]: data[k] for k in data if k.startswith("grid_")})
        return cls(
            hole=int(data["hole"][0]),
            detector=str(data["detector"][0]),
            grid=grid,
            n_components=int(data["n_components"][0]),
            mean=data["mean"].astype(np.float64),
            components=data["components"].astype(np.float64),
            explained_variance=data["explained_variance"].astype(np.float64),
            explained_variance_ratio=data["explained_variance_ratio"].astype(np.float64),
            training_row_ids=[str(x) for x in data["training_row_ids"].tolist()],
        )


@dataclass
class FPCAResult:
    scores: np.ndarray
    reconstructions: np.ndarray
    projectable: np.ndarray
    reasons: list[str]
    row_ids: list[str]
    heights_hs: np.ndarray
    eigenfunctions: np.ndarray
    explained_variance_ratio: np.ndarray

    def to_jsonable(self) -> dict[str, Any]:
        return finite_json(
            {
                "scores": self.scores,
                "reconstructions": self.reconstructions,
                "projectable": self.projectable.tolist(),
                "reasons": self.reasons,
                "row_ids": self.row_ids,
                "heights_hs": self.heights_hs,
                "eigenfunctions": self.eigenfunctions,
                "explained_variance_ratio": self.explained_variance_ratio,
            }
        )


def fit_fpca(
    runs: list[RunData],
    *,
    hole: int,
    detector: str,
    n_components: int = 2,
    selection: dict[str, Any] | None = None,
    max_gap_hs: float = 5000.0,
) -> FittedFPCA:
    """Discretized multivariate fPCA via weighted SVD on exact common grid."""
    grid = common_height_grid(
        runs, hole=hole, detector=detector, selection=selection, max_gap_hs=max_gap_hs
    )
    Y, row_ids, reasons = sample_curves_on_grid(
        runs, grid, hole=hole, detector=detector, selection=selection
    )
    ok = np.array([r == CellReason.OK.value for r in reasons]) & np.isfinite(Y).all(axis=1)
    if ok.sum() < 2:
        raise ValueError("need at least 2 complete curves for fPCA")
    Yf = Y[ok]
    mean = Yf.mean(axis=0)
    Yc = Yf - mean
    # Weight by sqrt(quadrature weights) so SVD approximates L2(height)
    sw = np.sqrt(np.clip(grid.weights, 0, None))
    Yw = Yc * sw
    # Economy SVD
    _, s, Vt = np.linalg.svd(Yw, full_matrices=False)
    n_comp = min(n_components, len(s), Yf.shape[0] - 1)
    if n_comp < 1:
        raise ValueError("insufficient rank for fPCA")
    # Unweight components back to function space
    comps = Vt[:n_comp] / np.where(sw > 0, sw, 1.0)
    # Orthonormalize in discrete L2 sense
    for i in range(n_comp):
        nrm = float(np.sqrt(np.sum(comps[i] ** 2 * grid.weights)))
        if nrm > 1e-12:
            comps[i] /= nrm
    var = (s[:n_comp] ** 2) / max(Yf.shape[0] - 1, 1)
    total = float(np.sum(s**2) / max(Yf.shape[0] - 1, 1)) or 1.0
    return FittedFPCA(
        hole=hole,
        detector=detector,
        grid=grid,
        n_components=n_comp,
        mean=mean,
        components=comps,
        explained_variance=var,
        explained_variance_ratio=var / total,
        training_row_ids=[row_ids[i] for i in range(len(row_ids)) if ok[i]],
        selection={**DEFAULT_SELECTION, **(selection or {})},
    )


def transform_fpca(runs: list[RunData], fitted: FittedFPCA) -> FPCAResult:
    Y, row_ids, reasons_in = sample_curves_on_grid(
        runs,
        fitted.grid,
        hole=fitted.hole,
        detector=fitted.detector,
        selection=fitted.selection,
    )
    n = len(runs)
    scores = np.full((n, fitted.n_components), np.nan)
    recon = np.full((n, len(fitted.grid.heights_hs)), np.nan)
    projectable = np.zeros(n, dtype=bool)
    reasons: list[str] = []
    w = fitted.grid.weights
    for i in range(n):
        if reasons_in[i] != CellReason.OK.value or not np.isfinite(Y[i]).all():
            reasons.append(
                reasons_in[i]
                if reasons_in[i] != CellReason.OK.value
                else CellReason.PROJECTION_NOT_SUPPORTED.value
            )
            continue
        yc = Y[i] - fitted.mean
        sc = np.array(
            [float(np.sum(yc * fitted.components[k] * w)) for k in range(fitted.n_components)]
        )
        scores[i] = sc
        recon[i] = fitted.mean + sc @ fitted.components
        projectable[i] = True
        reasons.append(CellReason.OK.value)
    return FPCAResult(
        scores=scores,
        reconstructions=recon,
        projectable=projectable,
        reasons=reasons,
        row_ids=row_ids,
        heights_hs=fitted.grid.heights_hs,
        eigenfunctions=fitted.components,
        explained_variance_ratio=fitted.explained_variance_ratio,
    )


def curve_compare_payload(
    run_a: RunData,
    run_b: RunData,
    hole: int,
    detector: str,
    selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ca = curve_payload(run_a, hole, detector, selection)
    cb = curve_payload(run_b, hole, detector, selection)
    return {"a": ca, "b": cb, "alignment": "none_exact_heights_only"}
