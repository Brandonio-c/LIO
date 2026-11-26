"""Sample-variance assessment, 25 Nov 2026: empty chamber vs Citrucel vs whey.

Offline, read-only on the run folders. Writes variance_results.json next to this file.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]  # test_results/
OUT = Path(__file__).resolve().parent
RUNS = {
    "empty": "20261125-130035_scan_quick",
    "citrucel": "20261125-141952_scan_fine",
    "whey": "20261125-172501_scan_fine",
    "whey_b": "20261125-160648_scan_fine",  # cancelled at 81/89 (All off), 500 hs/s, old marks
}
LABEL = {
    1: "395",
    2: "405",
    3: "465",
    4: "525",
    5: "590",
    6: "605",
    7: "630",
    8: "850",
    9: "940",
    10: "white",
    11: "pink",
    12: "1450",
    13: "1550",
    14: "1650",
    15: "1760",
    16: "1850*",
}
# channels a detector can see (expected or broadband); h16 is proxy_unassigned
CHANNELS = [(h, "opt101") for h in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 16)] + [
    (h, "ingaas") for h in (8, 9, 11, 12, 13, 14, 15, 16)
]
HS_PER_MM = 4096.0


def load(run: str) -> list[dict]:
    rows = []
    with gzip.open(ROOT / run / "cube.csv.gz", "rt", newline="") as f:
        for r in csv.DictReader(f):
            if r["state"] != "lit" or r["net_counts"] in ("", "None") or not r["height_hs"]:
                continue
            rows.append(
                {
                    "phase": r["phase"],
                    "dir": r["direction"],
                    "rep": r["rep"],
                    "hole": int(r["hole"]),
                    "det": r["detector"],
                    "h": float(r["height_hs"]),
                    "net": float(r["net_counts"]),
                    "t": float(r["t_s"] or 0),
                }
            )
    return rows


def curves(rows):
    """(hole, det) -> {height: [nets]} over every visit."""
    out: dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        out[(r["hole"], r["det"])][r["h"]].append(r["net"])
    return out


def interp(curve: dict, h: float) -> float:
    hs = sorted(curve)
    ms = [st.fmean(curve[x]) for x in hs]
    return float(np.interp(h, hs, ms))


def revisit_sd(curve: dict, near: float, width: float) -> tuple[float, int]:
    """Pooled SD of repeated visits at heights within ``width`` of ``near``."""
    ss, df = 0.0, 0
    for h, v in curve.items():
        if abs(h - near) <= width and len(v) >= 2:
            ss += st.variance(v) * (len(v) - 1)
            df += len(v) - 1
    return (math.sqrt(ss / df), df) if df else (float("nan"), 0)


def drift(rows):
    """P1 (start) vs P4 (end) at the top, per channel."""
    p = defaultdict(dict)
    for r in rows:
        if r["phase"] in ("P1", "P4"):
            p[(r["hole"], r["det"])][r["phase"]] = r["net"]
    return {k: (v.get("P1"), v.get("P4")) for k, v in p.items()}


def main() -> None:
    data = {k: load(v) for k, v in RUNS.items()}
    cur = {k: curves(v) for k, v in data.items()}
    lows = {k: min(r["h"] for r in v) for k, v in data.items()}
    # whey_b's marks were broken (it only reached -50023): it is compared near the top only.
    common_low = max(v for k, v in lows.items() if k != "whey_b")
    grid = [common_low * f for f in (0.15, 0.35, 0.55, 0.75, 0.9, 1.0)]
    res: dict = {
        "runs": RUNS,
        "lowest_height_hs": lows,
        "common_low_hs": common_low,
        "grid_hs": grid,
        "grid_mm": [g / HS_PER_MM for g in grid],
        "channels": {},
    }
    for hole, det in CHANNELS:
        key = f"h{hole}/{det}"
        ch = {"label": LABEL[hole]}
        for k in RUNS:
            c = cur[k].get((hole, det))
            if not c:
                continue
            ch[k] = {
                "at_grid": [round(interp(c, g), 2) for g in grid],
                "revisit_sd_low": round(revisit_sd(c, common_low, 0.12 * abs(common_low))[0], 3),
                "revisit_df_low": revisit_sd(c, common_low, 0.12 * abs(common_low))[1],
                "own_max": round(max(st.fmean(v) for v in c.values()), 2),
            }
            d = drift(data[k]).get((hole, det))
            if d and None not in d:
                ch[k]["drift_p1_p4"] = [d[0], d[1]]
        res["channels"][key] = ch
    (OUT / "variance_results.json").write_text(json.dumps(res, indent=1))
    print("common low", common_low, "lows", lows)


if __name__ == "__main__":
    main()


# ----------------------------------------------------------------- shape analysis
SHAPE = [(h, "opt101") for h in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)] + [
    (h, "ingaas") for h in (8, 9, 11, 12, 15)
]  # usable channels: h13/h14 too weak, h16 intermittent


def shape_distance(a: dict, b: dict, floor: float = 15.0) -> tuple[float, int]:
    """RMS of per-channel log-ratios after removing the common (brightness) factor."""
    lr = [math.log(a[k] / b[k]) for k in a if k in b and a[k] >= floor and b[k] >= floor]
    if len(lr) < 4:
        return float("nan"), len(lr)
    m = st.fmean(lr)
    return math.sqrt(st.fmean([(x - m) ** 2 for x in lr])), len(lr)


def vec_at(c, h):
    return {f"h{k[0]}/{k[1]}": interp(c[k], h) for k in SHAPE if k in c}


def vec_phase(rows, phase):
    out = {}
    for r in rows:
        if r["phase"] == phase and (r["hole"], r["det"]) in SHAPE:
            out[f"h{r['hole']}/{r['det']}"] = r["net"]
    return out


def bench_placements():
    """24 Nov stationary bench, rig R6: white W1 vs W2, black B1 vs B2 (same material)."""
    p = ROOT / "bench_20261124_all16" / "channel_response_32.json"
    d = json.loads(p.read_text())
    out = {}
    for t in ("W1", "W2", "B1", "B2"):
        out[t] = {
            f"h{r['hole']}/{r['detector']}": r["runs"][t]["mean"]
            for r in d["rows"]
            if (r["hole"], r["detector"]) in SHAPE
        }
    return out


def shapes() -> dict:
    data = {k: load(v) for k, v in RUNS.items()}
    cur = {k: curves(v) for k, v in data.items()}
    low = max(min(r["h"] for r in v) for k, v in data.items() if k != "whey_b")
    res: dict = {}
    # 1. between foods at matched heights
    hs = [low * f for f in (0.35, 0.55, 0.75, 0.9, 1.0)]
    res["citrucel_vs_whey"] = [
        {
            "h_mm": h / HS_PER_MM,
            "d": shape_distance(vec_at(cur["citrucel"], h), vec_at(cur["whey"], h)),
        }
        for h in hs
    ]
    res["citrucel_vs_empty"] = [
        {
            "h_mm": h / HS_PER_MM,
            "d": shape_distance(vec_at(cur["citrucel"], h), vec_at(cur["empty"], h)),
        }
        for h in hs
    ]
    res["whey_vs_empty"] = [
        {
            "h_mm": h / HS_PER_MM,
            "d": shape_distance(vec_at(cur["whey"], h), vec_at(cur["empty"], h)),
        }
        for h in hs
    ]
    # 2. same sample, different height (how much the shape depends on height)
    for k in ("citrucel", "whey", "empty"):
        ref = vec_at(cur[k], low)
        res[f"{k}_height_effect"] = [
            {"h_mm": h / HS_PER_MM, "d": shape_distance(vec_at(cur[k], h), ref)} for h in hs[:-1]
        ]
    # 3. same sample, start vs end of the run at the top (drift over ~45-60 min)
    for k in ("empty", "citrucel", "whey"):
        res[f"{k}_P1_vs_P4"] = shape_distance(vec_phase(data[k], "P1"), vec_phase(data[k], "P4"))
    # 4. whey placement A (final) vs B (cancelled run, earlier), near the top only
    top_hs = [-26218.0, -36052.0, -45886.0]
    res["whey_vs_whey_b_near_top"] = [
        {
            "h_mm": h / HS_PER_MM,
            "d": shape_distance(vec_at(cur["whey"], h), vec_at(cur["whey_b"], h), 10.0),
        }
        for h in top_hs
    ]
    res["citrucel_vs_whey_near_top"] = [
        {
            "h_mm": h / HS_PER_MM,
            "d": shape_distance(vec_at(cur["citrucel"], h), vec_at(cur["whey"], h), 10.0),
        }
        for h in top_hs
    ]
    # 5. bench placements of the same material (24 Nov)
    b = bench_placements()
    res["bench_W1_vs_W2"] = shape_distance(b["W1"], b["W2"])
    res["bench_B1_vs_B2"] = shape_distance(b["B1"], b["B2"])
    res["bench_white_vs_black"] = shape_distance(
        {k: (b["W1"][k] + b["W2"][k]) / 2 for k in b["W1"]},
        {k: (b["B1"][k] + b["B2"][k]) / 2 for k in b["B1"]},
    )
    # 6. normalised fingerprints at the common low height (relative to h8/opt101)
    fp = {}
    for k in ("empty", "citrucel", "whey"):
        v = vec_at(cur[k], low)
        fp[k] = {c: round(x / v["h8/opt101"], 4) for c, x in v.items()}
    res["fingerprint_rel_h8"] = fp
    # 7. height sensitivity near the low end: % change per mm
    sens = {}
    for k in ("citrucel", "whey"):
        sens[k] = {}
        for ch in SHAPE:
            c = cur[k][ch]
            a, b2 = interp(c, low), interp(c, low + 4 * HS_PER_MM)  # 4 mm higher
            if a >= 15:
                sens[k][f"h{ch[0]}/{ch[1]}"] = round(100 * (a - b2) / a / 4, 2)
    res["pct_per_mm_near_low"] = sens
    return res


if __name__ == "__main__":
    r = shapes()
    (OUT / "shape_results.json").write_text(json.dumps(r, indent=1))
