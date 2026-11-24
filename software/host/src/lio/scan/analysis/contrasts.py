"""Connected paired / shared-control / familywise inference on SAVED rows (S5).

Production consumer: ``lio.scan.derived.analyse_model`` (qualified-v2), and from
there the report, dashboard summary and CLI. Pairs come only from stored
``pair_id`` / ``control_group_id`` identities; unmatched or duplicated pair
members make that contrast unavailable (raw rows stay inspectable). Pilot and
scout rows are excluded. A target-minus-control contrast needs applicable scoped
:class:`ControlEvidence`; without it the coupling term stays null. Numerical
results on labelled synthetic fixtures are software truth, never rig calibration.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from lio.scan.analysis.uncertainty import (
    Estimate,
    ValueKind,
    _t_interval,
    familywise_intervals,
)

EXCLUDED_PHASES = ("pilot", "scout")


def _lit_rows(rows: list[dict[str, str]], detector: str) -> list[dict[str, str]]:
    out = []
    for r in rows:
        if r.get("detector") != detector or str(r.get("state") or "lit") != "lit":
            continue
        if str(r.get("phase") or "").lower() in EXCLUDED_PHASES:
            continue
        if r.get("net_counts") in (None, ""):
            continue
        out.append(r)
    return out


def _estimate(diffs: list[float], what: str) -> Estimate:
    n = len(diffs)
    if n < 2:
        return Estimate(None, ValueKind.UNRESOLVED, n, extras={"reason": f"{n} pair(s); need >= 2",
                        "contrast": what})  # fmt: skip
    a = np.asarray(diffs, dtype=float)
    mean = float(a.mean())
    var_mean = float(a.var(ddof=1)) / n
    se = math.sqrt(var_mean)
    kind = ValueKind.POSITIVE if mean > 0 else ValueKind.NEGATIVE if mean < 0 else ValueKind.ZERO
    return Estimate(
        mean, kind, n, se=se, interval=_t_interval(mean, se, n),
        assumptions=["paired by stored identity", "pairs independent across blocks",
                     "technical repeats aggregated within a pair side"],
        extras={"contrast": what, "diffs": [float(x) for x in diffs], "var_of_mean": var_mean},
    )  # fmt: skip


def _pair(
    left: dict[str, list[float]], right: dict[str, list[float]], what: str
) -> tuple[list[str], list[float], str | None]:
    """Differences left - right over shared keys; refuse unmatched/duplicate members."""
    dup = [k for k, v in {**left, **right}.items() if len(v) > 1]
    if dup:
        return [], [], f"duplicate pair member(s) {sorted(dup)[:5]}"
    unmatched = sorted(set(left) ^ set(right))
    if unmatched:
        return [], [], f"{len(unmatched)} unmatched pair member(s), e.g. {unmatched[:3]}"
    keys = sorted(left)
    return keys, [left[k][0] - right[k][0] for k in keys], None


def connected_contrasts(
    rows: list[dict[str, str]],
    meta: dict[str, Any],
    *,
    control_holes: dict[str, list[int]] | None = None,
) -> dict[str, Any]:
    """Paired condition and target-minus-control contrasts + covariance + family."""
    proto = meta.get("protocol") or {}
    family = meta.get("inference_family")
    post_hoc = False
    if not isinstance(family, dict):
        from lio.scan.acquisition import frozen_inference_family, load_protocol

        family = (
            frozen_inference_family(load_protocol(proto))
            if proto
            else {"members": [], "size": 0, "alpha": 0.05, "method": "bonferroni"}
        )
        post_hoc = True
    members: list[str] = list(family.get("members") or [])
    conds = [c.get("id") for c in proto.get("conditions") or []]
    ests: dict[str, Estimate] = {}
    reasons: dict[str, str] = {}
    by_det_diffs: dict[str, dict[str, tuple[list[str], list[float]]]] = {}
    for m in members:
        det, hole_s, what = m.split(":", 2)
        hole = int(hole_s[1:])
        lit = _lit_rows(rows, det)
        if what.endswith(":minus-control"):
            cond = what.split(":", 1)[0]
            lit = [r for r in lit if r.get("condition_id") == cond]
            ctrl = [h for h in (control_holes or {}).get(det, []) if h != hole]
            if len(ctrl) != 1:
                reasons[m] = (
                    "coupling/control unidentified: no applicable scoped control evidence "
                    "(C stays null)"
                    if not ctrl
                    else "several applicable controls: declare one shared control"
                )
                continue
            tgt: dict[str, list[float]] = {}
            con: dict[str, list[float]] = {}
            for r in lit:
                g = r.get("control_group_id")
                if not g:
                    continue
                h = int(r["hole"])
                if h == hole:
                    tgt.setdefault(g, []).append(float(r["net_counts"]))
                elif h == ctrl[0]:
                    con.setdefault(g, []).append(float(r["net_counts"]))
            if not tgt and not con:
                reasons[m] = "no control_group_id identities stored (legacy run)"
                continue
            keys, diffs, err = _pair(tgt, con, m)
        else:
            a_id, b_id = what.split("-minus-")
            sa: dict[str, list[float]] = {}
            sb: dict[str, list[float]] = {}
            for r in lit:
                if int(r["hole"]) != hole or not r.get("pair_id"):
                    continue
                side = sa if r.get("condition_id") == a_id else sb if r.get(
                    "condition_id") == b_id else None  # fmt: skip
                if side is not None:
                    side.setdefault(str(r["pair_id"]), []).append(float(r["net_counts"]))
            keys, diffs, err = _pair(sa, sb, m)
        if err:
            reasons[m] = err
            continue
        ests[m] = _estimate(diffs, m)
        by_det_diffs.setdefault(det, {})[m] = (keys, diffs)
    # Covariance between contrasts that share pairing keys (shared control).
    cov: dict[str, float] = {}
    for _det, d in by_det_diffs.items():
        names = sorted(d)
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                ka, da = d[a]
                kb, db = d[b]
                if ka == kb and len(ka) >= 2:
                    c = float(np.cov(np.asarray(da), np.asarray(db), ddof=1)[0, 1]) / len(ka)
                    cov[f"{a}|{b}"] = c
    fw = familywise_intervals(ests, family_size=max(1, len(members)),
                              alpha=float(family.get("alpha", 0.05)))  # fmt: skip
    return {
        "family": {**family, "post_hoc": post_hoc},
        "estimates": {k: v.to_dict() for k, v in fw.items()},
        "unavailable": reasons,
        "covariance_of_means": cov,
        "conditions": conds,
        "evidence_origin": "synthetic" if meta.get("simulated") else "recorded",
        "physical_qualification": "not established (A0/Rf/optical/reference deferred)",
    }
