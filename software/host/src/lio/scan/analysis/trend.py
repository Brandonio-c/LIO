"""Trend and baselines (plan §6.7).

    lio scan baseline save <run>     stores the run's metrics under its sample id
    lio scan compare <runA> <runB>   per-hole ratios, with where the change sits

Baselines live in ``test_results/scan_baselines/<sample_id>/<run_id>.json``: the
scalar metrics, per-channel optical amplitudes and curves, the config hash. With 5 or
more baselines for a sample, each scalar metric gets a control chart (mean ± 3sigma and
an EWMA); a later run outside the limits is flagged.

Localisation of a change (per-hole ratio B/A on the expected channels):
one or a few holes -> that LED or its alignment; every hole on one detector ->
that detector or its front end; everything -> supply, geometry or the sample.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from lio.config import HwConfig
from lio.results import Status
from lio.scan.analysis.data import DETECTORS, Finding, health, pair

EWMA_LAMBDA = 0.2


def baseline_dir(root: Path, sample_id: str) -> Path:
    return Path(root) / "scan_baselines" / sample_id


def snapshot(analysis: dict[str, Any]) -> dict[str, Any]:
    """What a baseline keeps from an analysis.json."""
    ch = (analysis.get("context") or {}).get("optics", {}).get("channels", {})
    return {
        "run_id": analysis["run_id"],
        "sample_id": analysis["sample_id"],
        "mode": analysis.get("mode"),
        "metrics": {
            f["id"]: f["value"]
            for f in analysis["findings"]
            if isinstance(f.get("value"), (int, float)) and f["status"] != "SKIP"
        },
        "O": {det: {str(h): s["O"] for h, s in (ch.get(det) or {}).items()} for det in DETECTORS},
        "curves": {
            det: {
                str(h): {"h": s["h"], "smooth": s["smooth"]} for h, s in (ch.get(det) or {}).items()
            }
            for det in DETECTORS
        },
    }


def save_baseline(run: Path, root: Path, cfg: HwConfig) -> Path:
    a = json.loads((Path(run) / "analysis.json").read_text())
    if a.get("status") != "COMPLETE":
        raise ValueError("only a COMPLETE run can be a baseline")
    snap = snapshot(a) | {"config_sha256": cfg.sha256}
    d = baseline_dir(root, a["sample_id"])
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{a['run_id']}.json"
    out.write_text(json.dumps(snap, indent=1) + "\n")
    return out


def load_baselines(root: Path, sample_id: str) -> list[dict[str, Any]]:
    d = baseline_dir(root, sample_id)
    if not d.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))]


def compare(a: dict[str, Any], b: dict[str, Any], cfg: HwConfig) -> list[Finding]:
    """B against A (both snapshots): per-hole ratios and where the change sits."""
    w, f = pair(cfg, "trend.ratio_change")
    ratios: dict[str, dict[int, float]] = {}
    for det in DETECTORS:
        oa, ob = a["O"].get(det, {}), b["O"].get(det, {})
        floor = float(health(cfg, "trend.min_counts"))
        ratios[det] = {int(h): ob[h] / oa[h] for h in oa
                       if h in ob and oa[h] >= floor
                       and cfg.channel(int(h)).expect_for(det) == "signal"}  # fmt: skip
    out = []
    changed: dict[str, list[int]] = {}
    for det, r in ratios.items():
        if not r:
            continue
        dev = {h: abs(math.log(max(v, 1e-6))) for h, v in r.items()}
        changed[det] = [h for h, x in dev.items() if x >= math.log(1 + w)]
    n_exp = {d: len(r) for d, r in ratios.items()}
    det_wide = [d for d in changed if n_exp[d] and len(changed[d]) >= 0.75 * n_exp[d]]
    if not any(changed.values()):
        where, st = "no change beyond the band", Status.PASS
    elif len(det_wide) == len([d for d in n_exp if n_exp[d]]):
        where, st = "every hole on both detectors: supply, geometry or the sample", Status.WARN
    elif det_wide:
        where, st = (
            f"every hole on {', '.join(det_wide)}: that detector or its front end",
            Status.WARN,
        )
    else:
        holes = sorted({h for v in changed.values() for h in v})
        where, st = f"holes {holes}: those LEDs or their alignment", Status.WARN
    allr = [v for r in ratios.values() for v in r.values()]
    far = max(allr, key=lambda v: abs(math.log(max(v, 1e-6))), default=1.0)
    if st != Status.PASS and abs(math.log(max(far, 1e-6))) >= math.log(1 + f):
        st = Status.FAIL
    out.append(Finding(
        "trend/compare", f"{b['run_id']} vs {a['run_id']}", st,
        round(far, 3), "x (furthest per-hole ratio)", where,
        f"per-hole ratio within ±{w:g} (WARN), ±{f:g} (FAIL)",
        {"ratios": ratios, "changed": changed, "a": a["run_id"], "b": b["run_id"]},
    ))  # fmt: skip
    return out


def control(snap: dict[str, Any], baselines: list[dict[str, Any]], cfg: HwConfig) -> list[Finding]:
    """Each scalar metric against its baselines: mean ± 3sigma and an EWMA."""
    n_min = int(health(cfg, "trend.control_min_baselines"))
    base = [b for b in baselines if b["run_id"] != snap["run_id"]]
    if len(base) < n_min:
        why = f"needs {n_min} baselines of {snap['sample_id']} (have {len(base)})"
        return [Finding("trend/control", "control charts vs baselines", Status.SKIP, detail=why)]
    out_of: dict[str, dict[str, float]] = {}
    charts: dict[str, dict[str, Any]] = {}
    for mid, x in snap["metrics"].items():
        hist = [float(b["metrics"][mid]) for b in base if mid in b["metrics"]]
        if len(hist) < n_min:
            continue
        mu, sd = float(np.mean(hist)), float(np.std(hist, ddof=1))
        sd = max(sd, 1e-9 + 0.01 * abs(mu))  # a perfectly steady metric still has a band
        z = EWMA_LAMBDA
        e = mu
        for v in [*hist, float(x)]:
            e = z * v + (1 - z) * e
        lim = 3 * sd * math.sqrt(z / (2 - z))
        charts[mid] = {"mean": mu, "sd": sd, "value": float(x), "ewma": e, "ewma_limit": lim,
                       "history": hist}  # fmt: skip
        if abs(float(x) - mu) > 3 * sd or abs(e - mu) > lim:
            out_of[mid] = {"value": float(x), "mean": mu, "sd": sd}
    return [Finding(
        "trend/control", "control charts vs baselines", Status.WARN if out_of else Status.PASS,
        float(len(out_of)), "metrics out of limits",
        (", ".join(f"{k} {v['value']:.3g} (mean {v['mean']:.3g} ± {3 * v['sd']:.2g})"
                   for k, v in out_of.items()) if out_of else
         f"{len(charts)} metrics within limits over {len(base)} baselines"),
        "within mean ± 3sigma and the EWMA limits", {"charts": charts, "out_of_limits": out_of},
    )]  # fmt: skip
