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


def _t_interval(mean: float, se: float, n: int, level: float = 0.95) -> Interval:
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
        interval = Interval(None, None, level, "t", False, "single block: interval unavailable")
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
            interval = Interval(interval.low, interval.high, level, "paired-t", True, None)
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
    block_ids: Sequence[str] | None = None,
    control_block_ids: Sequence[str] | None = None,
) -> Estimate:
    """Corrected quantity ``O = S - C`` with shared-control covariance.

    When the same control observation is reused across channels, its variance
    contributes to the corrected SE (not counted as independent N per channel).

    Unequal or ambiguous joins are rejected — never truncated to invent a CI (D12).
    """
    assumptions = [
        "O = S - C with shared control C",
        "Var(O) = Var(S) + Var(C) - 2 Cov(S,C); Cov estimated when paired",
        "no truncation of unequal arrays",
    ]
    s = np.asarray(channel_nets, dtype=np.float64)
    c = np.asarray(control_nets, dtype=np.float64)
    if s.size == 0 or c.size == 0:
        return Estimate(None, ValueKind.MISSING, 0, assumptions=assumptions)
    if block_ids is not None or control_block_ids is not None:
        paired = pair_by_block_ids(
            list(s),
            list(c),
            list(block_ids) if block_ids is not None else [str(i) for i in range(len(s))],
            list(control_block_ids)
            if control_block_ids is not None
            else [str(i) for i in range(len(c))],
        )
        if paired.reason:
            return Estimate(
                None,
                ValueKind.UNRESOLVED,
                0,
                assumptions=assumptions,
                extras={"reason": paired.reason},
            )
        s = np.asarray(paired.left, dtype=np.float64)
        c = np.asarray(paired.right, dtype=np.float64)
    elif s.shape != c.shape:
        return Estimate(
            None,
            ValueKind.UNRESOLVED,
            0,
            assumptions=assumptions,
            extras={
                "reason": (
                    f"unequal lengths {s.size} vs {c.size}; "
                    "refuse truncation (provide block_ids to pair)"
                )
            },
        )
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
            interval=Interval(None, None, level, "shared-control", False, "single block"),
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


@dataclass
class PairingResult:
    left: list[float]
    right: list[float]
    ids: list[str]
    reason: str | None = None


def pair_by_block_ids(
    left: Sequence[float],
    right: Sequence[float],
    left_ids: Sequence[str],
    right_ids: Sequence[str],
) -> PairingResult:
    """Pair observations by immutable block/condition IDs (D12).

    Rejects duplicate/ambiguous joins and unmatched arrays. No truncation.
    """
    if len(left) != len(left_ids) or len(right) != len(right_ids):
        return PairingResult([], [], [], "id/value length mismatch")
    if len(set(left_ids)) != len(left_ids):
        return PairingResult([], [], [], "duplicate left block ids")
    if len(set(right_ids)) != len(right_ids):
        return PairingResult([], [], [], "duplicate right block ids")
    right_map = {str(i): float(v) for i, v in zip(right_ids, right, strict=True)}
    out_l: list[float] = []
    out_r: list[float] = []
    out_ids: list[str] = []
    missing: list[str] = []
    for i, v in zip(left_ids, left, strict=True):
        key = str(i)
        if key not in right_map:
            missing.append(key)
            continue
        out_l.append(float(v))
        out_r.append(right_map[key])
        out_ids.append(key)
    if missing:
        return PairingResult(
            [],
            [],
            [],
            f"unmatched block ids: {missing[:8]}{'…' if len(missing) > 8 else ''}",
        )
    if len(out_l) != len(right_ids):
        # right had extras not in left
        extras = [str(i) for i in right_ids if str(i) not in set(out_ids)]
        if extras:
            return PairingResult(
                [],
                [],
                [],
                f"unmatched control block ids: {extras[:8]}",
            )
    return PairingResult(out_l, out_r, out_ids, None)


def aggregate_with_shared_control(
    channel_block_means: dict[str, Sequence[float]],
    shared_control_blocks: Sequence[float],
    *,
    channel_block_ids: dict[str, Sequence[str]] | None = None,
    control_block_ids: Sequence[str] | None = None,
) -> dict[str, Estimate]:
    """Apply the same control series to each channel (shared covariance)."""
    out: dict[str, Estimate] = {}
    for name, vals in channel_block_means.items():
        ids = None if channel_block_ids is None else channel_block_ids.get(name)
        out[name] = shared_control_corrected(
            vals,
            shared_control_blocks,
            block_ids=ids,
            control_block_ids=control_block_ids,
        )
    return out


def bonferroni_level(family_size: int, alpha: float = 0.05) -> float:
    """Per-test level for Bonferroni familywise control (do not shrink family)."""
    m = max(1, int(family_size))
    return 1.0 - (alpha / m)  # convert to confidence level for intervals


def familywise_intervals(
    estimates: dict[str, Estimate],
    *,
    family_size: int | None = None,
    alpha: float = 0.05,
) -> dict[str, Estimate]:
    """Recompute intervals at Bonferroni level for a frozen family.

    Family size is the predeclared size (e.g. detector x hole x contrast). Failing
    channels do not silently shrink the family.
    """
    m = int(family_size) if family_size is not None else len(estimates)
    level = bonferroni_level(m, alpha)
    out: dict[str, Estimate] = {}
    for k, est in estimates.items():
        if est.value is None or est.se is None or est.n_blocks < 2:
            out[k] = est
            continue
        interval = _t_interval(float(est.value), float(est.se), est.n_blocks, level)
        if interval.available:
            interval = Interval(
                interval.low,
                interval.high,
                level,
                "bonferroni-t",
                True,
                f"family_size={m}",
            )
        out[k] = Estimate(
            est.value,
            est.kind,
            est.n_blocks,
            se=est.se,
            interval=interval,
            units=est.units,
            assumptions=[*est.assumptions, f"bonferroni family_size={m}"],
            extras={**est.extras, "family_size": m, "alpha": alpha},
        )
    return out


@dataclass(frozen=True)
class FixedPositionBlock:
    """One independent block at fixed geometry/settings/condition (D12)."""

    block_id: str
    hole: int
    height_hs: float | None
    direction: str | None
    condition_id: str | None
    phase: str | None
    net: float
    dark: float | None = None
    lit: float | None = None
    reading_id: str | None = None
    position_instance_id: str | None = None
    setting_id: str | None = None


def group_fixed_position_blocks(
    cube: Any,
    *,
    detector: str,
) -> dict[int, list[FixedPositionBlock]]:
    """Group readings into fixed-position blocks — never pool heights (D12).

    Two detector rows from one MEAS share identity via reading linkage when
    present; height/direction/condition remain part of the block key so visits
    at different heights are not treated as independent repeats of one estimand.
    """
    # The authoritative saved rows (ScanStore.rows), with their identities.
    store = getattr(cube, "store", None)
    rows: list[dict[str, Any]] = []
    if store is not None and hasattr(store, "rows"):
        rows = list(store.rows())
    by_hole: dict[int, list[FixedPositionBlock]] = {}

    def opt(v: Any) -> str | None:
        return None if v in (None, "") else str(v)

    def optf(v: Any) -> float | None:
        return None if v in (None, "") else float(v)

    if rows:
        for i, r in enumerate(rows):
            if str(r.get("detector") or "") != detector:
                continue
            if str(r.get("state") or "lit") != "lit":
                continue
            try:
                hole = int(r["hole"])
                net_raw = r.get("net_counts") if "net_counts" in r else r.get("net")
                if net_raw in (None, ""):
                    continue  # missing stays missing: never zero-filled
                net = float(net_raw)
            except (KeyError, TypeError, ValueError):
                continue
            h = optf(r.get("height_hs"))
            if h is not None and h != h:  # NaN is not a position
                h = None
            direction = opt(r.get("direction"))
            condition = opt(r.get("condition_id") or r.get("condition"))
            phase = opt(r.get("phase"))
            reading = opt(r.get("reading_id"))
            # A block groups technical repeats; legacy rows without ids fall back
            # to a per-row key that still separates heights/directions/phases.
            block_id = str(
                r.get("block_id") or reading or f"{hole}:{h}:{direction}:{condition}:{phase}:{i}"
            )
            by_hole.setdefault(hole, []).append(
                FixedPositionBlock(
                    block_id=block_id,
                    hole=hole,
                    height_hs=h,
                    direction=None if direction in (None, "none") else direction,
                    condition_id=condition,
                    phase=phase,
                    net=net,
                    dark=optf(r.get("dark_counts")),
                    lit=optf(r.get("lit_counts")),
                    reading_id=reading,
                    position_instance_id=opt(r.get("position_instance_id")),
                    setting_id=opt(r.get("setting_id")),
                )
            )
        return by_hole

    # Fallback: lit_all provides hole/height/net — keep height in block identity.
    holes, heights, net = cube.lit_all(detector)
    for i, (hole, height, nval) in enumerate(zip(holes, heights, net, strict=False)):
        h = int(hole)
        hs = float(height)
        by_hole.setdefault(h, []).append(
            FixedPositionBlock(
                block_id=f"{detector}:h{h}:hs{hs}:i{i}",
                hole=h,
                height_hs=hs,
                direction=None,
                condition_id=None,
                phase=None,
                net=float(nval),
            )
        )
    return by_hole


def production_blocks_only(
    blocks: Sequence[FixedPositionBlock],
) -> list[FixedPositionBlock]:
    """Exclude pilot (and non-production) rows from confirmation estimands (CE07)."""
    out: list[FixedPositionBlock] = []
    for b in blocks:
        phase = (b.phase or "").lower()
        if phase in ("pilot", "scout"):
            continue
        if phase in ("", "production", "fixed", "confirmation", "p2", "p3"):
            # Empty phase kept only when no pilot siblings exist in the set.
            out.append(b)
            continue
        # Unknown labelled phases stay out of production confirmation.
    # If the input mixed pilot+production, drop empty-phase rows too when pilots present.
    has_pilot = any((b.phase or "").lower() in ("pilot", "scout") for b in blocks)
    if has_pilot:
        out = [b for b in out if (b.phase or "").lower() in ("production", "fixed", "confirmation")]
    return out


def block_drive_response(
    blocks: Sequence[FixedPositionBlock],
    *,
    level: float = 0.95,
    require_fixed_geometry: bool = True,
    exclude_pilot: bool = True,
) -> Estimate:
    """Drive-response estimand at one fixed geometry.

    If heights/directions vary across ``blocks`` and ``require_fixed_geometry``,
    return unresolved rather than pooling into fake independent repeats (D12).
    Pilot rows are excluded from confirmation means by default (CE07).
    """
    assumptions = [
        "fixed-position independent blocks",
        "no height/direction/condition pooling",
        "no stop-when-positive",
        "pilot excluded from production confirmation",
    ]
    raw_blocks = list(blocks)
    if exclude_pilot:
        use_blocks = production_blocks_only(raw_blocks)
        has_pilot = any((b.phase or "").lower() in ("pilot", "scout") for b in raw_blocks)
        # Pooled-with-pilot must not silently become the confirmation mean.
        if has_pilot and not use_blocks:
            return Estimate(
                None,
                ValueKind.MISSING,
                0,
                assumptions=assumptions,
                extras={"reason": "only pilot blocks; no production confirmation"},
            )
    else:
        use_blocks = raw_blocks
    if not use_blocks:
        return Estimate(None, ValueKind.MISSING, 0, assumptions=assumptions)
    if require_fixed_geometry:
        heights = {b.height_hs for b in use_blocks if b.height_hs is not None}
        directions = {b.direction for b in use_blocks if b.direction is not None}
        conditions = {b.condition_id for b in use_blocks if b.condition_id is not None}
        settings = {b.setting_id for b in use_blocks if b.setting_id is not None}
        # Unknown stationary position: rows with no height must share ONE
        # position instance (same run); unknown != unknown across instances.
        unknown_pos = [b for b in use_blocks if b.height_hs is None]
        instances = {b.position_instance_id for b in unknown_pos}
        mixed_position = bool(unknown_pos) and (
            None in instances or len(instances) > 1 or bool(heights)
        )
        if (
            len(heights) > 1
            or len(directions) > 1
            or len(conditions) > 1
            or len(settings) > 1
            or mixed_position
        ):
            return Estimate(
                None,
                ValueKind.UNRESOLVED,
                0,
                assumptions=assumptions,
                extras={
                    "reason": "mixed geometry/condition; refuse height/phase pooling",
                    "n_heights": len(heights),
                    "n_directions": len(directions),
                    "n_conditions": len(conditions),
                    "n_settings": len(settings),
                    "mixed_unknown_position": mixed_position,
                    "n_rows": len(use_blocks),
                },
            )
    # Aggregate technical repeats within the same block_id.
    by_id: dict[str, list[float]] = {}
    for b in use_blocks:
        by_id.setdefault(b.block_id, []).append(b.net)
    vals = [float(np.mean(v)) for v in by_id.values()]
    dark = [0.0] * len(vals)
    est = drive_response_tau(vals, dark, level=level)
    est.assumptions = [*assumptions, *est.assumptions]
    est.extras = {
        **est.extras,
        "includes_pilot": False,
        "n_excluded_pilot": len(raw_blocks) - len(use_blocks),
    }
    return est


def scipy_available() -> bool:
    return scipy_stats is not None
