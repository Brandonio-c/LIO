"""Ambient light pollution (plan §6.3): dark level vs height (a leak as the chamber
overlap shrinks), room-light flicker at 120 Hz, the ambient fraction."""

from __future__ import annotations

from typing import Any

import numpy as np

from lio.config import HwConfig
from lio.results import Status
from lio.scan.analysis.data import DETECTORS, Cube, Finding, grade, mv, pair


def leak(cube: Cube, cfg: HwConfig, optics_ctx: dict[str, Any]) -> list[Finding]:
    out = []
    for det in DETECTORS:
        _, h, d, ph = cube.darks(det)
        m = np.isfinite(d) & np.isin(ph, ["P2", "P3"])
        h, d = h[m], d[m]
        heights = np.unique(h)
        if len(heights) < 4:
            out.append(Finding(f"ambient/{det}/leak", f"{det}: dark vs height (light leak)",
                               Status.SKIP, detail="needs dark frames at 4+ heights"))  # fmt: skip
            continue
        per_h = np.array([float(np.median(d[h == x])) for x in heights])  # ascending: bottom first
        n3 = max(1, len(heights) // 3)
        top = float(np.median(per_h[-n3:]))
        rise = per_h - top
        noise = float(np.std(per_h[-n3:])) if n3 > 1 else 1.0
        worst = float(np.max(rise[:n3]))  # the lower third of the travel
        w, f = pair(cfg, f"ambient.leak_counts.{det}")
        st = grade(worst, w, f)
        onset = None
        thr = max(3 * noise, w / 2)
        above = rise > thr
        if above.any():
            # the highest height at which the dark has risen, with every height below it too
            k = 0
            while k < len(above) and above[k]:
                k += 1
            if k:
                onset = float(heights[k - 1])
        o = [s["O"] for hole, s in (optics_ctx.get("channels") or {}).get(det, {}).items()
             if cfg.channel(int(hole)).expect_for(det) == "signal" and s["O"] > 0]  # fmt: skip
        frac = worst / float(np.median(o)) if o and worst > 0 else 0.0
        out.append(Finding(
            f"ambient/{det}/leak", f"{det}: dark vs height (light leak at the shroud)", st,
            round(worst, 1), "counts",
            f"dark at the bottom {worst:+.1f} counts ({mv(worst):+.2f} mV) vs the top"
            + (f"; rises from h {onset:.0f}" if onset is not None else "")
            + (f"; {100 * frac:.2f}% of the median signal" if frac else ""),
            f"rise < {w:g} counts (WARN), < {f:g} (FAIL)",
            {"heights": heights.tolist(), "dark": per_h.tolist(), "onset_hs": onset,
             "ambient_fraction": frac},
        ))  # fmt: skip
    return out


def mains_rejected_meta(meta: dict[str, Any]) -> bool:
    return bool((meta.get("capabilities") or {}).get("mains_rejection"))


def flicker(cfg: HwConfig, spectra: dict[str, Any], meta: dict[str, Any]) -> list[Finding]:
    out = []
    for det in DETECTORS:
        sp = spectra.get(det)
        if not sp:
            out.append(Finding(f"ambient/{det}/flicker", f"{det}: room-light flicker",
                               Status.SKIP, detail="no dark streams"))  # fmt: skip
            continue
        a = mv(float(sp["amp_counts"]["120"]))
        w, f = pair(cfg, f"ambient.flicker_mv.{det}")
        rejected = mains_rejected_meta(meta)
        out.append(Finding(
            f"ambient/{det}/flicker", f"{det}: room-light flicker (120 Hz)",
            Status.PASS if rejected and grade(a, w, f) == Status.WARN else grade(a, w, f),
            round(a, 4), "mV", f"120 Hz amplitude in the dark streams {a:.3f} mV"
            + ("; readings integrate whole mains periods, so it cancels" if rejected else ""),
            f"< {w:g} mV (WARN), < {f:g} (FAIL)",
        ))  # fmt: skip
    return out


def analyse(
    cube: Cube, cfg: HwConfig, elec: dict[str, Any], optics_ctx: dict[str, Any]
) -> list[Finding]:
    out = leak(cube, cfg, optics_ctx)
    out += flicker(cfg, elec.get("spectra") or {}, cube.meta)
    out.append(Finding("ambient/lid", "lid sensitivity", Status.SKIP,
                       detail="optional operator step (lid ajar at two heights)"))  # fmt: skip
    return out
