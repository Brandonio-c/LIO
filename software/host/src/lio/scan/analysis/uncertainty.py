"""Signed fixed-N block estimators and honest uncertainty (M3).

Estimands:
- Drive response ``tau = mean(lit - dark)`` over independent blocks (signed).
- Paired blocked/unblocked contrasts.
- Shared-control covariance into corrected quantities.

Intervals use SciPy when the optional ``precision`` extra is installed; without
it, estimates are returned with an explicit unavailable-interval reason.

No stop-when-positive. No qualify-by-max-over-heights.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

try:
    from scipy import stats as scipy_stats
except ImportError:  # optional precision extra (scipy>=1.11)
    scipy_stats = None


class ValueKind(str, Enum):
    """Distinguish negative, zero, missing, saturated, unresolved."""

    NEGATIVE = "negative"
    ZERO = "zero"
    POSITIVE = "positive"
    MISSING = "missing"
    SATURATED = "saturated"
    UNRESOLVED = "unresolved"


@dataclass
class Interval:
    low: float | None
    high: float | None
    level: float
    method: str
    available: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "low": self.low,
            "high": self.high,
            "level": self.level,
            "method": self.method,
            "available": self.available,
            "reason": self.reason,
        }


@dataclass
class Estimate:
    value: float | None
    kind: ValueKind
    n_blocks: int
    se: float | None = None
    interval: Interval | None = None
    units: str = "counts"
    assumptions: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "kind": self.kind.value,
            "n_blocks": self.n_blocks,
            "se": self.se,
            "interval": None if self.interval is None else self.interval.to_dict(),
            "units": self.units,
            "assumptions": list(self.assumptions),
            "extras": self.extras,
        }


def classify_value(
    value: float | None,
    *,
    missing: bool = False,
    saturated: bool = False,
    unresolved: bool = False,
    zero_tol: float = 0.0,
) -> ValueKind:
    if missing or value is None or (isinstance(value, float) and not np.isfinite(value)):
        return ValueKind.MISSING
    if saturated:
        return ValueKind.SATURATED
    if unresolved:
        return ValueKind.UNRESOLVED
    if abs(float(value)) <= zero_tol:
        return ValueKind.ZERO
    if float(value) < 0:
        return ValueKind.NEGATIVE
    return ValueKind.POSITIVE


def _t_interval(
    mean: float, se: float, n: int, level: float = 0.95
) -> Interval:
    if n < 2 or se is None or not np.isfinite(se):
        return Interval(
            None,
            None,
            level,
            "t",
            False,
            "insufficient blocks for interval",
        )
    if scipy_stats is None:
        return Interval(
            None,
            None,
            level,
            "t",
            False,
            "scipy unavailable; install lio[precision] (scipy>=1.11)",
        )
    df = n - 1
    tcrit = float(scipy_stats.t.ppf(0.5 + level / 2.0, df))
    half = tcrit * se
    return Interval(mean - half, mean + half, level, "student-t", True, None)


def drive_response_tau(
    lit: Sequence[float],
    dark: Sequence[float],
    *,
    level: float = 0.95,
    saturated: bool = False,
) -> Estimate:
    """Signed fixed-N block drive response ``tau = mean(lit - dark)``.

    Each paired (lit, dark) is one independent block. A firmware mean of N
    conversions is still one observation.
    """
    assumptions = [
        "independent-normal blocks",
        "fixed-N paired lit/dark per block",
        "no stop-when-positive",
    ]
    lit_a = np.asarray(lit, dtype=np.float64)
    dark_a = np.asarray(dark, dtype=np.float64)
    if lit_a.shape != dark_a.shape or lit_a.size == 0:
        return Estimate(
            None,
            ValueKind.MISSING,
            0,
            assumptions=assumptions,
            extras={"reason": "lit/dark length mismatch or empty"},
        )
    diffs = lit_a - dark_a
    ok = np.isfinite(diffs)
    diffs = diffs[ok]
    n = int(diffs.size)
    if n == 0:
        return Estimate(None, ValueKind.MISSING, 0, assumptions=assumptions)
    mean = float(np.mean(diffs))
    if n == 1:
        se = None
        interval = Interval(
            None, None, level, "t", False, "single block: interval unavailable"
        )
    else:
        se = float(np.std(diffs, ddof=1) / np.sqrt(n))
        interval = _t_interval(mean, se, n, level)
    kind = classify_value(mean, saturated=saturated)
    return Estimate(
        mean,
        kind,
        n,
        se=se,
        interval=interval,
        assumptions=assumptions,
        extras={"block_diffs": diffs.tolist()},
    )


def paired_optical_contrast(
    tau_unblocked: Sequence[float],
    tau_blocked: Sequence[float],
    *,
    level: float = 0.95,
) -> Estimate:
    """Paired blocked/unblocked contrast ``Delta_opt = tau_unblocked - tau_blocked``."""
    assumptions = [
        "paired blocked/unblocked blocks",
        "independent-normal paired differences",
        "load-preserving controls assumed by caller",
    ]
    a = np.asarray(tau_unblocked, dtype=np.float64)
    b = np.asarray(tau_blocked, dtype=np.float64)
    if a.shape != b.shape or a.size == 0:
        return Estimate(
            None,
            ValueKind.MISSING,
            0,
            assumptions=assumptions,
            extras={"reason": "blocked/unblocked length mismatch or empty"},
        )
    d = a - b
    ok = np.isfinite(d)
    d = d[ok]
    n = int(d.size)
    if n == 0:
        return Estimate(None, ValueKind.MISSING, 0, assumptions=assumptions)
    mean = float(np.mean(d))
    if n == 1:
        se = None
        interval = Interval(
            None, None, level, "paired-t", False, "single pair: interval unavailable"
        )
    else:
        se = float(np.std(d, ddof=1) / np.sqrt(n))
        interval = _t_interval(mean, se, n, level)
        if interval.available:
            interval = Interval(
                interval.low, interval.high, level, "paired-t", True, None
            )
    return Estimate(
        mean,
        classify_value(mean),
        n,
        se=se,
        interval=interval,
        assumptions=assumptions,
    )


def shared_control_corrected(
    channel_nets: Sequence[float],
    control_nets: Sequence[float],
    *,
    level: float = 0.95,
) -> Estimate:
    """Corrected quantity ``O = S - C`` with shared-control covariance.

    When the same control observation is reused across channels, its variance
    contributes to the corrected SE (not counted as independent N per channel).
    """
    assumptions = [
        "O = S - C with shared control C",
        "Var(O) = Var(S) + Var(C) - 2 Cov(S,C); Cov estimated when paired",
    ]
    s = np.asarray(channel_nets, dtype=np.float64)
    c = np.asarray(control_nets, dtype=np.float64)
    if s.size == 0 or c.size == 0:
        return Estimate(None, ValueKind.MISSING, 0, assumptions=assumptions)
    # Align to common length for paired cov; else use independent-sum variance.
    n = int(min(s.size, c.size))
    s, c = s[:n], c[:n]
    ok = np.isfinite(s) & np.isfinite(c)
    s, c = s[ok], c[ok]
    n = int(s.size)
    if n == 0:
        return Estimate(None, ValueKind.UNRESOLVED, 0, assumptions=assumptions)
    o = s - c
    mean = float(np.mean(o))
    if n == 1:
        return Estimate(
            mean,
            classify_value(mean),
            1,
            se=None,
            interval=Interval(
                None, None, level, "shared-control", False, "single block"
            ),
            assumptions=assumptions,
            extras={"shared_control_var": 0.0, "cov_sc": 0.0},
        )
    var_s = float(np.var(s, ddof=1))
    var_c = float(np.var(c, ddof=1))
    cov_sc = float(np.cov(s, c, ddof=1)[0, 1])
    var_o = var_s + var_c - 2.0 * cov_sc
    se = float(np.sqrt(max(var_o, 0.0) / n))
    interval = _t_interval(mean, se, n, level)
    return Estimate(
        mean,
        classify_value(mean),
        n,
        se=se,
        interval=interval,
        assumptions=assumptions,
        extras={
            "var_s": var_s,
            "var_c": var_c,
            "cov_sc": cov_sc,
            "var_o": var_o,
            "shared_control_covariance_nonzero": abs(cov_sc) > 0,
        },
    )


def aggregate_with_shared_control(
    channel_block_means: dict[str, Sequence[float]],
    shared_control_blocks: Sequence[float],
) -> dict[str, Estimate]:
    """Apply the same control series to each channel (shared covariance)."""
    return {
        name: shared_control_corrected(vals, shared_control_blocks)
        for name, vals in channel_block_means.items()
    }


def scipy_available() -> bool:
    return scipy_stats is not None
