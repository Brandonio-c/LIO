"""Mechanical health (plan §6.4): travel, backlash, step loss, repeatability, lockstep,
settle time.

Without home sensors the stage position is read optically: the down pass gives the
reference response S_ref(h) of every strong channel; a later reading at commanded
height h is S_ref(h + δ), δ being how far the stage really is from where it was
told to be. On the up pass δ(p) = δ0 + κ·p (p = 0 at the bottom, 1 at the top):
backlash = -δ0 (on a reversal the first steps only take up slack, so the stage sits
lower going up), step loss = -κ (lost upward steps accumulate). The resolution is
set by the curve slopes and reported with every number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from lio.config import HwConfig
from lio.results import Status
from lio.scan.analysis.data import DETECTORS, Array, Cube, Finding, grade, health, pair


def spline_m(h: Array, s: Array) -> Array:
    """Second derivatives of the natural cubic spline through (h, s)."""
    n = len(h)
    m = np.zeros(n)
    if n < 3:
        return m
    dh = np.diff(h)
    a = np.zeros((n - 2, n - 2))
    r = np.zeros(n - 2)
    for i in range(1, n - 1):
        a[i - 1, i - 1] = 2 * (dh[i - 1] + dh[i])
        if i > 1:
            a[i - 1, i - 2] = dh[i - 1]
        if i < n - 2:
            a[i - 1, i] = dh[i]
        r[i - 1] = 6 * ((s[i + 1] - s[i]) / dh[i] - (s[i] - s[i - 1]) / dh[i - 1])
    m[1:-1] = np.linalg.solve(a, r)
    return m


def spline_eval(h: Array, s: Array, m: Array, x: Array) -> tuple[Array, Array]:
    """Value and slope of the spline at x (clamped to the measured range)."""
    x = np.clip(x, h[0], h[-1])
    i = np.clip(np.searchsorted(h, x) - 1, 0, len(h) - 2)
    h0, h1 = h[i], h[i + 1]
    d = h1 - h0
    a = (h1 - x) / d
    b = (x - h0) / d
    v = a * s[i] + b * s[i + 1] + ((a**3 - a) * m[i] + (b**3 - b) * m[i + 1]) * d * d / 6
    dv = (s[i + 1] - s[i]) / d + (-(3 * a * a - 1) * m[i] + (3 * b * b - 1) * m[i + 1]) * d / 6
    return v, dv


@dataclass
class Ref:
    """A channel's down-pass response, as a natural cubic spline through the raw
    readings: exact at the measured heights, curved between them (linear interpolation
    of a coarse peak under-reads it and biases the offsets)."""

    det: str
    hole: int
    h: Array  # ascending heights of the down pass
    s: Array  # raw net readings there
    m: Array  # spline second derivatives
    o: float

    def at(self, x: Array) -> tuple[Array, Array]:
        return spline_eval(self.h, self.s, self.m, x)


@dataclass
class Point:
    ref: Ref
    h: float  # commanded height
    v: float  # measured net
    p: float  # progress up the travel (0 bottom, 1 top)
    visit: int  # step index


def references(cfg: HwConfig, optics_ctx: dict[str, Any]) -> dict[tuple[str, int], Ref]:
    w_sig, _ = pair(cfg, "optics.min_signal_counts")
    out = {}
    for det in DETECTORS:
        for hole, st in ((optics_ctx.get("channels") or {}).get(det) or {}).items():
            ch = cfg.channel(int(hole))
            if ch.expect_for(det) != "signal" or st["O"] < w_sig or len(st["h"]) < 4:
                continue
            # the raw down-pass curve, not the smoothed one: smoothing a coarse peak bends
            # it, and that bend would read as an offset (a bias of a few hundred half-steps)
            h = np.array(st["h"], dtype=np.float64)
            s = np.array(st["net"], dtype=np.float64)
            out[(det, int(hole))] = Ref(det, int(hole), h, s, spline_m(h, s), float(st["O"]))
    return out


def points(cube: Cube, refs: dict[tuple[str, int], Ref], *, phase: str, direction: str,
           reps: bool, top: float, bottom: float) -> list[Point]:  # fmt: skip
    """Lit readings in ``phase`` approached from ``direction`` (first visits, or the
    repeatability visits with ``reps``), on the reference channels."""
    m = cube.mask(state="lit", phase=phase, direction=direction)
    m &= (cube.num["rep"] > 0) if reps else (cube.num["rep"] == 0)
    m &= cube.str["kind"] == "measure"
    out = []
    span = (top - bottom) or 1.0
    for i in np.where(m)[0]:
        key = (str(cube.str["detector"][i]), int(cube.num["hole"][i]))
        r = refs.get(key)
        if r is None or not math.isfinite(cube.num["net_counts"][i]):
            continue
        h = float(cube.num["height_hs"][i])
        out.append(Point(r, h, float(cube.num["net_counts"][i]), (h - bottom) / span,
                         int(cube.num["step"][i])))  # fmt: skip
    return out


def _cost(pts: list[Point], d0: Array, k: Array) -> Array:
    """Mean squared normalised residual for every (d0, k) pair (broadcast)."""
    tot = np.zeros(np.broadcast(d0, k).shape)
    for pt in pts:
        pred, _ = pt.ref.at(np.asarray(pt.h + d0 + k * pt.p, dtype=np.float64))
        tot = tot + ((pt.v - pred) / pt.ref.o) ** 2
    return tot / max(1, len(pts))


def fit_offset(pts: list[Point], span: float, *, with_k: bool) -> dict[str, float] | None:
    """Robust: fit, drop readings beyond 5 robust sigma (glitches), fit again."""
    first = _fit_offset(pts, span, with_k=with_k)
    if first is None:
        return None
    res = np.array([
        (pt.v - float(pt.ref.at(np.array([pt.h + first["d0"] + first.get("k", 0.0) * pt.p]))[0][0]))
        / pt.ref.o for pt in pts
    ])  # fmt: skip
    scale = 1.4826 * float(np.median(np.abs(res - np.median(res)))) or 1e-9
    keep = [pt for pt, r in zip(pts, res, strict=True) if abs(r) <= 5 * scale]
    if len(keep) == len(pts):
        return first
    second = _fit_offset(keep, span, with_k=with_k)
    if second is None:
        return first
    second["dropped"] = float(len(pts) - len(keep))
    return second


def _fit_offset(pts: list[Point], span: float, *, with_k: bool) -> dict[str, float] | None:
    """δ0 (and κ) minimising the squared residual; standard errors from the Jacobian."""
    if len(pts) < 3:
        return None
    g0 = np.linspace(-span, span, 121)
    gk = np.linspace(-span, span, 61) if with_k else np.zeros(1)
    d0, k = np.meshgrid(g0, gk, indexing="ij")
    c = _cost(pts, d0, k)
    i, j = np.unravel_index(int(np.argmin(c)), c.shape)
    best0, bestk = float(g0[i]), float(gk[j])
    for step0, stepk in ((g0[1] - g0[0], gk[1] - gk[0] if with_k else 0.0),):
        f0 = np.linspace(best0 - 2 * step0, best0 + 2 * step0, 41)
        fk = np.linspace(bestk - 2 * stepk, bestk + 2 * stepk, 41) if with_k else np.zeros(1)
        d0, k = np.meshgrid(f0, fk, indexing="ij")
        c = _cost(pts, d0, k)
        i, j = np.unravel_index(int(np.argmin(c)), c.shape)
        best0, bestk = float(f0[i]), float(fk[j])
    # Jacobian of the normalised residuals, and their variance
    jac = []
    res = []
    for pt in pts:
        v, dv = pt.ref.at(np.array([pt.h + best0 + bestk * pt.p]))
        sl = float(dv[0]) / pt.ref.o
        jac.append([sl, sl * pt.p] if with_k else [sl])
        res.append((pt.v - float(v[0])) / pt.ref.o)
    jm = np.array(jac)
    r = np.array(res)
    dof = max(1, len(pts) - jm.shape[1])
    s2 = float(r @ r) / dof
    cov = s2 * np.linalg.pinv(jm.T @ jm)
    out = {"d0": best0, "se_d0": float(math.sqrt(max(0.0, cov[0, 0]))), "n": float(len(pts))}
    if with_k:
        out |= {"k": bestk, "se_k": float(math.sqrt(max(0.0, cov[1, 1])))}
    return out


def _significant(value: float, se: float, warn: float, fail: float) -> Status:
    if se > warn / 2:
        return Status.SKIP  # the curves are too flat or noisy to resolve it
    st = grade(abs(value), warn, fail)
    if st != Status.PASS and abs(value) < 3 * se:
        return Status.PASS  # within the resolution: not shown
    return st


def analyse(cube: Cube, cfg: HwConfig, optics_ctx: dict[str, Any]) -> list[Finding]:
    out: list[Finding] = []
    plan = cube.meta.get("plan") or {}
    top, bottom = float(plan.get("top", 0)), float(plan.get("bottom", 0))
    hd = sorted(plan.get("heights_down") or [])
    span = (abs(hd[1] - hd[0]) if len(hd) > 1 else 4096) * 1.5
    refs = references(cfg, optics_ctx)
    out += _travel(cube, cfg)
    out += _lockstep(cube)
    out += _settle(cube, cfg)
    if not refs or plan.get("static") or plan.get("continuous"):
        why = "no down-pass reference curves (static or continuous mode, or no strong channel)"
        for fid, title in (("mech/backlash", "backlash"), ("mech/step_loss", "step loss"),
                           ("mech/repeatability", "repeatability")):  # fmt: skip
            out.append(Finding(fid, title, Status.SKIP, detail=why))
        return out
    up = points(cube, refs, phase="P3", direction="up", reps=False, top=top, bottom=bottom)
    fit = fit_offset(up, span, with_k=True) if len(up) >= 3 * len(refs) // 2 else None
    if fit is None:
        out.append(Finding("mech/backlash", "backlash (down vs up curves)", Status.SKIP,
                           detail="needs an up pass"))  # fmt: skip
        out.append(Finding("mech/step_loss", "step loss over the up pass", Status.SKIP,
                           detail="needs an up pass"))  # fmt: skip
    else:
        b, se_b = -fit["d0"], fit["se_d0"]
        w, f = pair(cfg, "mech.backlash_hs")
        mm = _mm(cfg, b)
        out.append(Finding(
            "mech/backlash", "backlash (down vs up response curves)", _significant(b, se_b, w, f),
            round(b, 0), "half-steps",
            f"{b:+.0f} ± {se_b:.0f} half-steps" + (f" ({mm:+.3f} mm)" if mm is not None else "")
            + f" from {int(fit['n'])} readings on {len(refs)} channels",
            f"< {w:g} (WARN), < {f:g} (FAIL); not flagged within 3 sigma; not judged when "
            f"the resolution is worse than {w / 2:g}",
            fit,
        ))  # fmt: skip
        loss, se_l = -fit["k"], fit["se_k"]
        w, f = pair(cfg, "mech.step_loss_hs")
        out.append(Finding(
            "mech/step_loss", "step loss (offset growing over the up pass)",
            _significant(loss, se_l, w, f), round(loss, 0), "half-steps per travel",
            f"the stage falls behind by {loss:+.0f} ± {se_l:.0f} half-steps over a full upward "
            "travel (one side losing steps: about twice that on that side, and a tilt)",
            f"< {w:g} (WARN), < {f:g} (FAIL); not flagged within 3 sigma", fit,
        ))  # fmt: skip
    out += _repeatability(cube, cfg, refs, span, top, bottom)
    return out


def _mm(cfg: HwConfig, hs: float) -> float | None:
    lead = cfg.section.raw("scan.lead_mm_per_rev")
    return None if lead in (None, "") else hs / 4096.0 * float(lead)


def _repeatability(cube: Cube, cfg: HwConfig, refs: dict[tuple[str, int], Ref], span: float,
                   top: float, bottom: float) -> list[Finding]:  # fmt: skip
    """Reference heights re-visited from above and below: spread and the direct backlash."""
    groups: dict[tuple[float, str], list[tuple[float, float]]] = {}
    for direction in ("down", "up"):
        pts = points(cube, refs, phase="P3", direction=direction, reps=True, top=top, bottom=bottom)
        by_visit: dict[int, list[Point]] = {}
        for pt in pts:
            by_visit.setdefault(pt.visit, []).append(pt)
        for vp in by_visit.values():
            fit = fit_offset(vp, span, with_k=False)
            if fit is not None and fit["se_d0"] < span / 3:
                groups.setdefault((vp[0].h, direction), []).append((fit["d0"], fit["se_d0"]))
    if not groups:
        return [Finding("mech/repeatability", "repeatability at the reference heights", Status.SKIP,
                        detail="no repeated reference visits in this mode (full, fine, "
                        "repeatability have them)")]  # fmt: skip
    spreads = [float(np.std([d for d, _ in v], ddof=1)) for v in groups.values() if len(v) > 1]
    rep = float(np.sqrt(np.mean(np.square(spreads)))) if spreads else 0.0
    diffs = []
    for (h, direction), v in groups.items():
        if direction == "down" and (h, "up") in groups:
            diffs.append(np.mean([d for d, _ in v]) - np.mean([d for d, _ in groups[(h, "up")]]))
    b = float(np.mean(diffs)) if diffs else float("nan")
    w, f = pair(cfg, "mech.repeatability_hs")
    if not spreads:
        return [Finding("mech/repeatability", "repeatability at the reference heights",
                        Status.SKIP, detail="each reference height visited once per side: "
                        "no spread to measure (full, fine, repeatability repeat them)",
                        data={"backlash_direct": b})]  # fmt: skip
    st = grade(rep, w, f)
    return [Finding(
        "mech/repeatability", "repeatability at the reference heights", st, round(rep, 0),
        "half-steps",
        f"spread of repeated visits {rep:.0f} half-steps (RMS over {len(spreads)} groups)"
        + (f"; above minus below {b:+.0f} half-steps (backlash, direct)" if diffs else ""),
        f"< {w:g} (WARN), < {f:g} (FAIL)",
        {"groups": {f"{h:.0f}/{d}": v for (h, d), v in groups.items()}, "backlash_direct": b},
    )]  # fmt: skip


def _travel(cube: Cube, cfg: HwConfig) -> list[Finding]:
    st = (cube.meta.get("health") or {}).get("stage_end") or cube.meta.get("stage") or {}
    rng = st.get("range")
    if not rng:
        return [Finding("mech/travel", "travel (top to bottom)", Status.SKIP,
                        detail="travel limits not tracked")]  # fmt: skip
    want = int(cfg.thresholds.raw("motion.travel.range_steps") or 0)
    detail = f"tracked range {rng[0]} / {rng[1]} half-steps (left / right)"
    status = Status.PASS
    if rng[0] != rng[1]:
        status, detail = Status.WARN, detail + ": the two sides differ"
    if want:
        tol = float(health(cfg, "mech.travel_tol_hs"))
        if abs(rng[0] - want) > tol:
            status = Status.WARN
            detail += f"; configured {want}"
    else:
        detail += " (thresholds.motion.travel.range_steps not set: not compared)"
    return [Finding("mech/travel", "travel (top to bottom)", status, float(rng[0]), "half-steps",
                    detail)]  # fmt: skip


def _lockstep(cube: Cube) -> list[Finding]:
    h = cube.meta.get("health") or {}
    if "moves" not in h:
        return [Finding("mech/lockstep", "lockstep (both sides level)", Status.SKIP,
                        detail="no health record (run interrupted early)")]  # fmt: skip
    bad = h.get("unlevel") or []
    return [Finding(
        "mech/lockstep", "lockstep (firmware positions level after every move)",
        Status.FAIL if bad else Status.PASS, float(len(bad)), "moves",
        f"{h['moves']} moves; {len(bad)} ended with the two sides at different positions"
        " (without home sensors only the commanded steps are seen: a side losing steps shows "
        "as mech/step_loss)",
    )]  # fmt: skip


def _settle(cube: Cube, cfg: HwConfig) -> list[Finding]:
    vals = _settle_values(cube)
    if not len(vals):
        return [Finding("mech/settle", "settle time after a move", Status.SKIP,
                        detail="no settle records")]  # fmt: skip
    base = float(cfg.section.raw("scan.settle_ms_mech"))
    w, f = pair(cfg, "mech.settle_extra_ms")
    # time lost to repeated dark reads (the median step needs none)
    extra = float(np.max(vals)) - float(np.median(vals))
    return [Finding(
        "mech/settle", "settle time after a move (dark-read convergence)", grade(extra, w, f),
        round(float(np.median(vals)), 0), "ms",
        f"median {np.median(vals):.0f} ms, max {np.max(vals):.0f} ms "
        f"(mechanical wait {base:.0f} ms)",
        f"max - median < {w:g} ms (WARN), < {f:g} (FAIL)",
    )]  # fmt: skip


def _settle_values(cube: Cube) -> Array:
    """One settle time per step (every lit row of a step carries the same value)."""
    steps: dict[str, float] = {}
    for r in cube.store.rows():
        if r.get("settle_ms") not in ("", None):
            steps[r["step"]] = float(r["settle_ms"])
    return np.array(list(steps.values()), dtype=np.float64)
