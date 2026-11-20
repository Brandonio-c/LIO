"""Chronological baseline / EWMA control views (no future leakage)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from lio.food_profiles.schema import finite_json


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass
class TrendSeries:
    timestamps: list[str]
    values: list[float]
    ewma: list[float | None]
    ucl: list[float | None]
    lcl: list[float | None]
    as_of: str
    lambda_: float
    available: bool
    reason: str
    warnings: list[str]

    def to_jsonable(self) -> dict[str, Any]:
        return finite_json(
            {
                "timestamps": self.timestamps,
                "values": self.values,
                "ewma": self.ewma,
                "ucl": self.ucl,
                "lcl": self.lcl,
                "as_of": self.as_of,
                "lambda": self.lambda_,
                "available": self.available,
                "reason": self.reason,
                "warnings": self.warnings,
            }
        )


def chronological_ewma(
    timestamps: list[str],
    values: list[float],
    *,
    as_of: str,
    lambda_: float = 0.2,
    baseline_n: int = 5,
    L: float = 3.0,
) -> TrendSeries:
    """EWMA using only observations with timestamp <= as_of.

    Control limits for point i use only the baseline prefix available at that time
    (no self/future-history leakage).
    """
    warnings: list[str] = []
    as_of_dt = _parse_ts(as_of)
    if as_of_dt is None:
        return TrendSeries([], [], [], [], [], as_of, lambda_, False, "invalid_as_of", warnings)
    pairs: list[tuple[datetime, str, float]] = []
    for ts, v in zip(timestamps, values, strict=True):
        dt = _parse_ts(ts)
        if dt is None or not np.isfinite(v):
            continue
        if dt <= as_of_dt:
            pairs.append((dt, ts, float(v)))
    pairs.sort(key=lambda p: p[0])
    if len(pairs) < 2:
        return TrendSeries(
            [], [], [], [], [], as_of, lambda_, False, "insufficient_history", warnings
        )
    ts_out = [p[1] for p in pairs]
    vals = [p[2] for p in pairs]
    ewma: list[float | None] = []
    ucl: list[float | None] = []
    lcl: list[float | None] = []
    z: float | None = None
    for i, v in enumerate(vals):
        # Baseline = observations strictly before i (or first baseline_n once available)
        if i == 0:
            z = v
            ewma.append(z)
            ucl.append(None)
            lcl.append(None)
            continue
        hist = vals[:i]  # exclude current - no self-inclusion in sigma
        if len(hist) < 2:
            z = (1 - lambda_) * (z if z is not None else v) + lambda_ * v
            ewma.append(z)
            ucl.append(None)
            lcl.append(None)
            continue
        base = hist[: max(baseline_n, 2)] if len(hist) >= baseline_n else hist
        mu0 = float(np.mean(base))
        sigma = float(np.std(base, ddof=1))
        z = (1 - lambda_) * (z if z is not None else mu0) + lambda_ * v
        # Approximate EWMA variance factor
        factor = np.sqrt(lambda_ / (2 - lambda_) * (1 - (1 - lambda_) ** (2 * (i + 1))))
        half = L * sigma * float(factor) if np.isfinite(sigma) else float("nan")
        ewma.append(z)
        if np.isfinite(half):
            ucl.append(mu0 + half)
            lcl.append(mu0 - half)
        else:
            ucl.append(None)
            lcl.append(None)
    return TrendSeries(ts_out, vals, ewma, ucl, lcl, as_of, lambda_, True, "ok", warnings)
