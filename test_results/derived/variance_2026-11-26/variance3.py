"""Sample-variance assessment with three foods (26 Nov 2026).

Empty chamber vs Citrucel (LIO-F-00001) vs whey (LIO-F-00002) vs The Barbecue Rub
(LIO-F-00003), compared at matched head heights with brightness removed. Offline,
read-only on the run folders. Reuses the 25 Nov method (variance_2026-11-25).
Writes results3.json next to this file.
"""

from __future__ import annotations

import itertools
import json
import math
import statistics as st
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "variance_2026-11-25"))
import variance_analysis as v1  # noqa: E402

v1.RUNS = {
    "empty": "20261125-130035_scan_quick",
    "citrucel": "20261125-141952_scan_fine",
    "whey": "20261125-172501_scan_fine",
    "rub": "20261126-004824_scan_fine",
    "whey_b": "20261125-160648_scan_fine",
}
FOODS = ("citrucel", "whey", "rub")
NAMES = {"citrucel": "Citrucel", "whey": "Whey", "rub": "Barbecue Rub", "empty": "Empty"}


def main() -> None:
    data = {k: v1.load(r) for k, r in v1.RUNS.items()}
    cur = {k: v1.curves(d) for k, d in data.items()}
    lows = {k: min(r["h"] for r in d) for k, d in data.items()}
    low = max(v for k, v in lows.items() if k != "whey_b")
    hs = [low * f for f in (0.35, 0.55, 0.75, 0.9, 1.0)]
    res: dict = {
        "runs": v1.RUNS,
        "lowest_hs": lows,
        "common_low_hs": low,
        "heights_mm": [h / v1.HS_PER_MM for h in hs],
    }
    # pairwise distances between foods (and vs empty) at each matched height
    pairs = {}
    for a, b in itertools.combinations((*FOODS, "empty"), 2):
        ds = [v1.shape_distance(v1.vec_at(cur[a], h), v1.vec_at(cur[b], h))[0] for h in hs]
        pairs[f"{a}|{b}"] = {
            "per_height": [round(x, 4) for x in ds],
            "mean": round(st.fmean(ds), 4),
            "min": round(min(ds), 4),
        }
    res["pairs"] = pairs
    # within-material
    within = {}
    for k in (*FOODS, "empty"):
        within[f"{k} start vs end (P1/P4)"] = round(
            v1.shape_distance(v1.vec_phase(data[k], "P1"), v1.vec_phase(data[k], "P4"))[0], 4
        )
        ref = v1.vec_at(cur[k], low)
        within[f"{k} 6 mm height change"] = round(
            v1.shape_distance(v1.vec_at(cur[k], hs[3]), ref)[0], 4
        )
    top = [-26218.0, -36052.0, -45886.0]
    within["whey two runs (near top)"] = round(
        st.fmean(
            [
                v1.shape_distance(v1.vec_at(cur["whey"], h), v1.vec_at(cur["whey_b"], h), 10.0)[0]
                for h in top
            ]
        ),
        4,
    )
    b = v1.bench_placements()
    within["white paper re-placed (24 Nov)"] = round(v1.shape_distance(b["W1"], b["W2"])[0], 4)
    within["black card re-placed (24 Nov)"] = round(v1.shape_distance(b["B1"], b["B2"])[0], 4)
    res["within"] = within
    # fingerprints relative to OPT101 850 nm at the common low height
    fp = {}
    for k in ("empty", *FOODS):
        vv = v1.vec_at(cur[k], low)
        fp[k] = {c: round(x / vv["h8/opt101"], 4) for c, x in vv.items()}
    res["fingerprint_rel_h8"] = fp
    # PCA of brightness-removed log fingerprints: 3 foods x 5 heights (+ empty)
    chans = list(fp["citrucel"])
    rows, labels = [], []
    for k in (*FOODS, "empty"):
        for h in hs:
            vv = v1.vec_at(cur[k], h)
            x = np.array([math.log(max(vv[c], 1.0)) for c in chans])
            rows.append(x - x.mean())
            labels.append(k)
    X = np.array(rows)
    Xc = X - X.mean(axis=0)
    u, s, vt = np.linalg.svd(Xc, full_matrices=False)
    ev = (s**2) / (s**2).sum()
    scores = (u * s)[:, :2]
    res["pca"] = {
        "explained": [round(float(x), 4) for x in ev[:4]],
        "points": [
            {
                "sample": lab,
                "h_mm": round(h / v1.HS_PER_MM, 1),
                "pc1": round(float(p[0]), 4),
                "pc2": round(float(p[1]), 4),
            }
            for lab, h, p in zip(labels, hs * 4, scores, strict=True)
        ],
        "loadings_pc1": dict(
            sorted(
                zip(chans, [round(float(x), 3) for x in vt[0]], strict=True),
                key=lambda kv: -abs(kv[1]),
            )[:6]
        ),
        "loadings_pc2": dict(
            sorted(
                zip(chans, [round(float(x), 3) for x in vt[1]], strict=True),
                key=lambda kv: -abs(kv[1]),
            )[:6]
        ),
    }
    # how many channels separate each pair by more than the light-material placement noise
    noise = within["white paper re-placed (24 Nov)"]
    sep = {}
    for a, bb in itertools.combinations(FOODS, 2):
        fa, fb = fp[a], fp[bb]
        lr = [math.log(fa[c] / fb[c]) for c in chans if fa[c] > 0.01 and fb[c] > 0.01]
        m = st.fmean(lr)
        big = [
            c
            for c in chans
            if fa[c] > 0.01 and fb[c] > 0.01 and abs(math.log(fa[c] / fb[c]) - m) > 3 * noise
        ]
        sep[f"{a}|{bb}"] = big
    res["channels_beyond_3x_placement_noise"] = sep
    (HERE / "results3.json").write_text(json.dumps(res, indent=1))
    print(
        json.dumps(
            {
                "pairs": {k: v["mean"] for k, v in pairs.items()},
                "within": within,
                "pca_explained": res["pca"]["explained"],
                "sep": sep,
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()


def without_h5_h7() -> dict:
    """Same comparisons excluding OPT101 h5-h7 (unstable within the Rub run, 26 Nov)."""
    drop = {(5, "opt101"), (6, "opt101"), (7, "opt101")}
    keep = [c for c in v1.SHAPE if c not in drop]
    saved, v1.SHAPE = v1.SHAPE, keep
    try:
        data = {k: v1.load(r) for k, r in v1.RUNS.items()}
        cur = {k: v1.curves(d) for k, d in data.items()}
        low = max(min(r["h"] for r in d) for k, d in data.items() if k != "whey_b")
        hs = [low * f for f in (0.35, 0.55, 0.75, 0.9, 1.0)]
        out = {"pairs": {}, "start_vs_end": {}}
        for a, b in itertools.combinations(FOODS, 2):
            ds = [v1.shape_distance(v1.vec_at(cur[a], h), v1.vec_at(cur[b], h))[0] for h in hs]
            out["pairs"][f"{a}|{b}"] = round(st.fmean(ds), 4)
        for k in FOODS:
            out["start_vs_end"][k] = round(
                v1.shape_distance(v1.vec_phase(data[k], "P1"), v1.vec_phase(data[k], "P4"))[0], 4
            )
        return out
    finally:
        v1.SHAPE = saved


if __name__ == "__main__":
    r = json.loads((HERE / "results3.json").read_text())
    r["without_h5_h7"] = without_h5_h7()
    (HERE / "results3.json").write_text(json.dumps(r, indent=1))
    print(json.dumps(r["without_h5_h7"], indent=1))
