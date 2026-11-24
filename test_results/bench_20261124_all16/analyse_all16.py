"""All-16 dual-detector bench: 32-row channel-response table (external, cross-run).

Written and frozen BEFORE any all-16 data were inspected (W1 was acquiring).
Reads only sealed raw runs (cube.csv.gz) listed in RUNS; never writes into them.
Usage: python -I analyse_all16.py  (run from anywhere; paths are relative to this file)

Rules (frozen):
- Unit: one raw detector row (net_counts = lit - dark, signed, never clipped). Missing or
  failed rows are counted, not imputed. N expected 12 per hole/detector/run.
- Per run: mean, SD, N, missing, first/last t_s.
- Target effect: D = mean(W1, W2) - mean(B1, B2) of placement means.
  Technical SE = 0.5 * sqrt(sW1^2/nW1 + sW2^2/nW2 + sB1^2/nB1 + sB2^2/nB2) (readings only;
  ignores placement-to-placement variance and drift; two placements per target, not 24
  preparations). Welch-Satterthwaite df. 95 % and Bonferroni-32 intervals (family of 32
  prespecified in SESSION_MANIFEST_NOT_A_PROTOCOL.json).
- Placement agreement: dW = W2 - W1, dB = B2 - B1 (absolute counts and relative to D).
- Status (first matching):
  1. "refused/not measured": any run missing or any N < 12.
  2. "unstable": any run SD > max(5, 0.10*|mean|).
  3. "repeatable target-associated response": Bonferroni-32 interval excludes 0, sign(W1-B1)
     == sign(W2-B2) == sign(D), and min(|W1-B1|, |W2-B2|) > max(|dW|, |dB|).
  4. "drive response with unresolved target dependence": some run mean has |t| > 3
     (mean/SE) and |mean| >= 5 counts, but rule 3 fails.
  5. "unresolved": otherwise. NOT evidence that an LED is dead or wrong.
- White-only fallback: if B1/B2 missing, D and rule 3 are unavailable; rule 4/5 apply.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

from scipy import stats

HERE = Path(__file__).resolve().parent
RUNS = json.loads((HERE / "RUNS.json").read_text())  # {"W1": "runs/<id>", ...}
OPT_ROLE = {
    **{h: "visible primary" for h in range(1, 8)},
    8: "NIR primary (both)",
    9: "NIR primary (both)",
    10: "broadband (white)",
    11: "broadband (pink)",
    **{h: "out of band diagnostic (not primary SWIR)" for h in range(12, 17)},
}
ING_ROLE = {
    **{h: "out of band diagnostic" for h in range(1, 8)},
    8: "NIR primary (both)",
    9: "NIR primary (both)",
    10: "broadband diagnostic",
    11: "broadband diagnostic",
    12: "SWIR primary",
    13: "SWIR primary",
    14: "SWIR primary",
    15: "SWIR, cutoff-sensitive",
    16: "proxy_unassigned (never primary 1850 nm)",
}
SOURCE = {
    1: "395",
    2: "405 purple",
    3: "465 blue",
    4: "525 green",
    5: "590 yellow",
    6: "605 orange",
    7: "630 red",
    8: "850",
    9: "940",
    10: "white (450 peak + phosphor)",
    11: "pink (450 peak + phosphor)",
    12: "1450",
    13: "1550",
    14: "1650",
    15: "1760",
    16: "1850 (proxy_unassigned)",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(run: str) -> tuple[dict, dict]:
    folder = HERE / run
    meta = json.loads((folder / "scan.json").read_text())
    cells: dict = {}
    with gzip.open(folder / "cube.csv.gz", "rt", newline="") as f:
        for r in csv.DictReader(f):
            key = (int(r["hole"]), r["detector"])
            c = cells.setdefault(key, {"vals": [], "missing": 0, "t": []})
            if r["net_counts"] in ("", "None", "nan"):
                c["missing"] += 1
            else:
                c["vals"].append(float(r["net_counts"]))
                c["t"].append(float(r["t_s"]))
    return meta, cells


def summ(c: dict | None) -> dict | None:
    if not c:
        return None
    v = c["vals"]
    n = len(v)
    m = statistics.fmean(v) if n else None
    s = statistics.stdev(v) if n > 1 else None
    return {
        "mean": m,
        "sd": s,
        "n": n,
        "missing": c["missing"],
        "raw": v,
        "t_first": min(c["t"]) if c["t"] else None,
        "t_last": max(c["t"]) if c["t"] else None,
    }


def main() -> None:
    data, provenance = {}, {}
    for tag, run in RUNS.items():
        meta, cells = load(run)
        data[tag] = cells
        provenance[tag] = {
            "run": run,
            "status": meta.get("status"),
            "started": meta.get("started"),
            "finished": meta.get("finished"),
            "sample_id": meta.get("sample_id"),
            "cube_sha256": sha(HERE / run / "cube.csv.gz"),
            "scan_sha256": sha(HERE / run / "scan.json"),
            "exposure_budget": meta.get("exposure_budget"),
            "software": meta.get("software"),
        }
    have_black = "B1" in data and "B2" in data
    tcrit = stats.norm.ppf(1 - 0.05 / 2)
    rows = []
    for h in range(1, 17):
        for det in ("ingaas", "opt101"):
            row = {
                "hole": h,
                "source": SOURCE[h],
                "detector": det,
                "role": (ING_ROLE if det == "ingaas" else OPT_ROLE)[h],
            }
            per = {t: summ(data[t].get((h, det))) for t in ("W1", "B1", "W2", "B2") if t in data}
            row["runs"] = per
            reasons = []
            if any(per.get(t) is None or per[t]["n"] < 12 for t in per) or len(per) < (
                4 if have_black else 2
            ):
                status = "refused/not measured"
                reasons.append("missing run or N<12")
            else:
                status = None
            # target effect
            if have_black and status is None:
                W = [per["W1"], per["W2"]]
                Bk = [per["B1"], per["B2"]]
                D = (W[0]["mean"] + W[1]["mean"]) / 2 - (Bk[0]["mean"] + Bk[1]["mean"]) / 2
                comps = [x["sd"] ** 2 / x["n"] for x in W + Bk]
                se = 0.5 * math.sqrt(sum(comps))
                if se > 0:
                    df = (
                        (sum(comps) ** 2)
                        / sum(
                            c**2 / (x["n"] - 1) for c, x in zip(comps, W + Bk, strict=True) if c > 0
                        )
                        if any(comps)
                        else float("inf")
                    )
                else:
                    df = float("inf")
                t95 = stats.t.ppf(0.975, df) if math.isfinite(df) else tcrit
                tb = (
                    stats.t.ppf(1 - 0.05 / 64, df)
                    if math.isfinite(df)
                    else stats.norm.ppf(1 - 0.05 / 64)
                )
                d1 = per["W1"]["mean"] - per["B1"]["mean"]
                d2 = per["W2"]["mean"] - per["B2"]["mean"]
                dW = per["W2"]["mean"] - per["W1"]["mean"]
                dB = per["B2"]["mean"] - per["B1"]["mean"]
                row["target"] = {
                    "D": D,
                    "se_technical": se,
                    "df": df,
                    "ci95": [D - t95 * se, D + t95 * se],
                    "bonf32": [D - tb * se, D + tb * se],
                    "W1_minus_B1": d1,
                    "W2_minus_B2": d2,
                }
                row["placement"] = {
                    "W2_minus_W1": dW,
                    "B2_minus_B1": dB,
                    "max_abs_placement_diff": max(abs(dW), abs(dB)),
                }
            else:
                row["target"] = None if not have_black else row.get("target")
                row["placement"] = (
                    {"W2_minus_W1": per["W2"]["mean"] - per["W1"]["mean"]}
                    if status is None and "W2" in per
                    else None
                )
            if status is None and any(
                x["sd"] is not None and x["sd"] > max(5.0, 0.10 * abs(x["mean"]))
                for x in per.values()
            ):
                status = "unstable"
                reasons.append("a run SD > max(5, 10% |mean|)")
            if status is None and have_black:
                tg, pl = row["target"], row["placement"]
                lo, hi = tg["bonf32"]
                same_sign = (
                    math.copysign(1, tg["W1_minus_B1"])
                    == math.copysign(1, tg["W2_minus_B2"])
                    == math.copysign(1, tg["D"])
                )
                if (
                    (lo > 0 or hi < 0)
                    and same_sign
                    and min(abs(tg["W1_minus_B1"]), abs(tg["W2_minus_B2"]))
                    > pl["max_abs_placement_diff"]
                ):
                    status = "repeatable target-associated response"
            if status is None:
                resolved = [
                    t
                    for t, x in per.items()
                    if x["sd"] is not None
                    and abs(x["mean"]) >= 5
                    and (x["sd"] == 0 or abs(x["mean"]) / (x["sd"] / math.sqrt(x["n"])) > 3)
                ]
                if resolved:
                    status = "drive response with unresolved target dependence"
                    reasons.append("resolved in " + ",".join(resolved))
                else:
                    status = "unresolved"
                    reasons.append("no run mean resolved >= 5 counts (not evidence of a dead LED)")
            row["status"], row["status_reasons"] = status, reasons
            rows.append(row)
    out = {
        "rules_frozen_in": "analyse_all16.py docstring",
        "script_sha256": sha(Path(__file__)),
        "have_black": have_black,
        "fallback": None if have_black else "white-only: B1/B2 and white-minus-black unavailable",
        "provenance": provenance,
        "rows": rows,
    }
    (HERE / "channel_response_32.json").write_text(json.dumps(out, indent=1))
    for r in rows:
        tg = r["target"]
        s = " ".join(
            f"{t}={x['mean']:8.2f}±{(x['sd'] or 0):5.2f}" for t, x in r["runs"].items() if x
        )
        d = tg["D"] if tg else float("nan")
        print(f"h{r['hole']:>2} {r['detector']:7s} {s}  D={d:8.2f}  {r['status']}")


if __name__ == "__main__":
    sys.exit(main())
