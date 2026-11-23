"""Shared scout/confirm height objective (M5).

One versioned objective used by planner, report and dashboard helpers.
Primary-SWIR excludes structural blinds and h16 primary-1850 claims. H16 proxy
scouting is a separate explicit diagnostic objective. Scout and confirmation
sets are disjoint; perturbing confirmation cannot change a frozen scout height.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

OBJECTIVE_VERSION = "m5-primary-swir-v1"
H16_PROXY_OBJECTIVE = "m5-h16-proxy-diagnostic-v1"

# Primary-SWIR eligible targets on current hardware (investigation channels).
PRIMARY_SWIR_HOLES = (12, 13, 14, 15)
PRIMARY_SWIR_CONTROLS = (8, 9)
# Structural / not primary-1850.
EXCLUDED_PRIMARY = frozenset({16})  # h16 never primary-1850


@dataclass(frozen=True)
class TargetObjective:
    name: str
    version: str
    detector: str
    target_holes: tuple[int, ...]
    control_holes: tuple[int, ...]
    excluded_holes: tuple[int, ...]
    weights: dict[int, float]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["target_holes"] = list(self.target_holes)
        d["control_holes"] = list(self.control_holes)
        d["excluded_holes"] = list(self.excluded_holes)
        d["weights"] = {str(k): float(v) for k, v in self.weights.items()}
        return d


@dataclass
class HeightScore:
    height_hs: float
    score: float
    per_hole: dict[int, float]
    eligible: bool
    reason: str = ""


@dataclass
class ScoutResult:
    objective: TargetObjective
    status: str  # selected | flat | unresolved | missing_target
    frozen_height_hs: float | None
    scores: list[HeightScore]
    scout_source_hash: str | None
    candidate_grid: list[float]
    predicted_precision: dict[str, Any] = field(default_factory=dict)
    exclusions: list[str] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective.to_dict(),
            "status": self.status,
            "frozen_height_hs": self.frozen_height_hs,
            "scores": [asdict(s) for s in self.scores],
            "scout_source_hash": self.scout_source_hash,
            "candidate_grid": list(self.candidate_grid),
            "predicted_precision": self.predicted_precision,
            "exclusions": list(self.exclusions),
            "detail": self.detail,
            "confirmation_disjoint": True,
        }


@dataclass
class ConfirmPlan:
    objective: TargetObjective
    frozen_height_hs: float
    scout_block_ids: tuple[str, ...]
    confirm_block_ids: tuple[str, ...]
    n_confirm_blocks: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective.to_dict(),
            "frozen_height_hs": self.frozen_height_hs,
            "scout_block_ids": list(self.scout_block_ids),
            "confirm_block_ids": list(self.confirm_block_ids),
            "n_confirm_blocks": self.n_confirm_blocks,
            "scout_equals_confirm": False,
        }


def primary_swir_objective(
    *,
    detector: str = "ingaas",
    weights: dict[int, float] | None = None,
) -> TargetObjective:
    """Named primary-SWIR objective (shared across planner/report/dashboard)."""
    w = {h: 1.0 for h in PRIMARY_SWIR_HOLES}
    # Prefer h12 recovery first.
    w[12] = 2.0
    if weights:
        w.update({int(k): float(v) for k, v in weights.items()})
    return TargetObjective(
        name="primary_swir",
        version=OBJECTIVE_VERSION,
        detector=detector,
        target_holes=PRIMARY_SWIR_HOLES,
        control_holes=PRIMARY_SWIR_CONTROLS,
        excluded_holes=tuple(sorted(EXCLUDED_PRIMARY)),
        weights=w,
        notes="h16 excluded from primary-1850; blinds excluded; h12 prioritized",
    )


def h16_proxy_diagnostic_objective(*, detector: str = "opt101") -> TargetObjective:
    """Separate explicit diagnostic objective — never a primary-1850 claim."""
    return TargetObjective(
        name="h16_proxy_diagnostic",
        version=H16_PROXY_OBJECTIVE,
        detector=detector,
        target_holes=(16,),
        control_holes=(),
        excluded_holes=(),
        weights={16: 1.0},
        notes="spectrally unassigned proxy; not primary-1850 chemistry",
    )


def named_objective(name: str, **kwargs: Any) -> TargetObjective:
    if name in ("primary_swir", "primary-SWIR", OBJECTIVE_VERSION):
        return primary_swir_objective(**kwargs)
    if name in ("h16_proxy", "h16_proxy_diagnostic", H16_PROXY_OBJECTIVE):
        return h16_proxy_diagnostic_objective(**kwargs)
    raise ValueError(f"unknown objective {name!r}")


def _eligible_holes(obj: TargetObjective, structural_blinds: Sequence[int] | None) -> list[int]:
    blinds = set(structural_blinds or ())
    out = []
    for h in obj.target_holes:
        if h in obj.excluded_holes or h in blinds:
            continue
        if obj.name == "primary_swir" and h in EXCLUDED_PRIMARY:
            continue
        out.append(h)
    return out


def score_height(
    height_hs: float,
    responses: dict[int, float],
    variances: dict[int, float],
    obj: TargetObjective,
    *,
    structural_blinds: Sequence[int] | None = None,
    acquisition_cost: float = 1.0,
) -> HeightScore:
    """Useful target-channel precision/coverage per acquisition cost.

    score = sum_h w_h * |signal_h| / (sigma_h * cost) for eligible targets only.
    Does not use max noisy channel as a hidden shortcut when targets are missing.
    """
    holes = _eligible_holes(obj, structural_blinds)
    if not holes:
        return HeightScore(height_hs, float("nan"), {}, False, "missing_target")
    per: dict[int, float] = {}
    numer = 0.0
    for h in holes:
        if h not in responses or not np.isfinite(responses[h]):
            continue
        sig = float(variances.get(h, 1.0))
        sig = math_sqrt(max(sig, 1e-12))
        w = float(obj.weights.get(h, 1.0))
        contrib = w * abs(float(responses[h])) / (sig * max(acquisition_cost, 1e-9))
        per[h] = contrib
        numer += contrib
    if not per:
        return HeightScore(height_hs, float("nan"), {}, False, "unresolved_no_finite_targets")
    return HeightScore(height_hs, float(numer), per, True, "ok")


def math_sqrt(x: float) -> float:
    return float(np.sqrt(x))


def scout_height(
    candidate_heights: Sequence[float],
    responses_by_height: dict[float, dict[int, float]],
    variances_by_height: dict[float, dict[int, float]] | None = None,
    *,
    objective: TargetObjective | None = None,
    structural_blinds: Sequence[int] | None = None,
    scout_source_hash: str | None = None,
    flat_eps: float = 1e-9,
) -> ScoutResult:
    """Scout then freeze one operating height. Flat/unresolved → explicit status."""
    obj = objective or primary_swir_objective()
    exclusions = [f"excluded hole {h}" for h in obj.excluded_holes]
    if structural_blinds:
        exclusions += [f"structural blind {h}" for h in structural_blinds]
    if obj.name == "primary_swir":
        exclusions.append("h16 not eligible for primary-1850 / primary_swir")

    grid = [float(h) for h in candidate_heights]
    scores: list[HeightScore] = []
    for h in grid:
        resp = responses_by_height.get(h) or {}
        # Strip objective exclusions (and structural blinds). For primary_swir,
        # also drop h16 so residuals cannot steer the optimum.
        ban = set(obj.excluded_holes)
        if obj.name == "primary_swir":
            ban |= set(EXCLUDED_PRIMARY)
        if structural_blinds:
            ban |= set(structural_blinds)
        cleaned = {k: v for k, v in resp.items() if k not in ban}
        var = (variances_by_height or {}).get(h) or {}
        scores.append(score_height(h, cleaned, var, obj, structural_blinds=structural_blinds))

    eligible = [s for s in scores if s.eligible and np.isfinite(s.score)]
    if not eligible:
        return ScoutResult(
            objective=obj,
            status="missing_target",
            frozen_height_hs=None,
            scores=scores,
            scout_source_hash=scout_source_hash,
            candidate_grid=grid,
            exclusions=exclusions,
            detail="no eligible target responses on the candidate grid",
        )

    vals = np.array([s.score for s in eligible], dtype=np.float64)
    if float(np.ptp(vals)) <= flat_eps:
        return ScoutResult(
            objective=obj,
            status="flat",
            frozen_height_hs=None,
            scores=scores,
            scout_source_hash=scout_source_hash,
            candidate_grid=grid,
            exclusions=exclusions,
            detail="objective flat across candidates; no silent max-noise fallback",
            predicted_precision={"score_range": float(np.ptp(vals))},
        )

    best = max(eligible, key=lambda s: s.score)
    return ScoutResult(
        objective=obj,
        status="selected",
        frozen_height_hs=best.height_hs,
        scores=scores,
        scout_source_hash=scout_source_hash,
        candidate_grid=grid,
        exclusions=exclusions,
        detail=f"frozen height {best.height_hs}",
        predicted_precision={"best_score": best.score, "per_hole": best.per_hole},
    )


def freeze_confirm_plan(
    scout: ScoutResult,
    *,
    n_confirm_blocks: int = 4,
    scout_block_ids: Sequence[str] | None = None,
) -> ConfirmPlan:
    """Held-out confirmation blocks; scout set is not reused as confirmation."""
    if scout.status != "selected" or scout.frozen_height_hs is None:
        raise ValueError(f"cannot confirm: scout status={scout.status}")
    scout_ids = tuple(scout_block_ids or (f"scout-{i}" for i in range(1)))
    confirm_ids = tuple(f"confirm-{i}" for i in range(n_confirm_blocks))
    if set(scout_ids) & set(confirm_ids):
        raise ValueError("scout and confirm block ids must be disjoint")
    return ConfirmPlan(
        objective=scout.objective,
        frozen_height_hs=float(scout.frozen_height_hs),
        scout_block_ids=scout_ids,
        confirm_block_ids=confirm_ids,
        n_confirm_blocks=n_confirm_blocks,
    )


def apply_confirm_perturbation(
    plan: ConfirmPlan,
    confirm_values: dict[str, float],
) -> ConfirmPlan:
    """Perturbing confirmation values must not change the frozen height."""
    _ = confirm_values  # intentionally unused: height is frozen from scout only
    return ConfirmPlan(
        objective=plan.objective,
        frozen_height_hs=plan.frozen_height_hs,
        scout_block_ids=plan.scout_block_ids,
        confirm_block_ids=plan.confirm_block_ids,
        n_confirm_blocks=plan.n_confirm_blocks,
    )
