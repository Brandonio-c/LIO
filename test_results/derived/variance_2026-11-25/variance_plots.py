"""Figures for the 25 Nov sample-variance assessment (reads shape_results.json)."""

from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
FIG = HERE.parents[2] / "docs" / "research" / "figures"
r = json.loads((HERE / "shape_results.json").read_text())

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
SERIES = {"empty": "#2a78d6", "citrucel": "#eb6834", "whey": "#1baf7a"}
NAMES = {
    "empty": "Empty chamber",
    "citrucel": "Citrucel (LIO-F-00001)",
    "whey": "Whey (LIO-F-00002)",
}
plt.rcParams.update(
    {
        "font.size": 10,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK2,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "axes.titlecolor": INK,
    }
)


def fingerprints() -> None:
    fp = r["fingerprint_rel_h8"]
    chans = list(fp["citrucel"])
    labels = [c.replace("/opt101", "").replace("/ingaas", "") for c in chans]
    nm = {
        "h1": "395",
        "h2": "405",
        "h3": "465",
        "h4": "525",
        "h5": "590",
        "h6": "605",
        "h7": "630",
        "h8": "850",
        "h9": "940",
        "h10": "white",
        "h11": "pink",
        "h12": "1450",
        "h15": "1760",
    }
    ticks = [f"{nm.get(lb, lb)}" for lb in labels]
    fig, ax = plt.subplots(figsize=(11, 4.6), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    w = 0.26
    for i, k in enumerate(("empty", "citrucel", "whey")):
        xs = [j + (i - 1) * w for j in range(len(chans))]
        ax.bar(
            xs,
            [fp[k][c] for c in chans],
            width=w - 0.03,
            color=SERIES[k],
            label=NAMES[k],
            edgecolor=SURFACE,
            linewidth=1.0,
        )
    n_opt = sum(c.endswith("opt101") for c in chans)
    ax.axvline(n_opt - 0.5, color=MUTED, linewidth=1, linestyle=(0, (3, 3)))
    ax.text(n_opt / 2 - 0.5, 2.2, "OPT101 (silicon)", ha="center", color=INK2)
    ax.text(n_opt + (len(chans) - n_opt) / 2 - 0.5, 2.2, "InGaAs", ha="center", color=INK2)
    ax.set_yscale("log")
    ax.set_ylim(0.015, 3)
    ax.set_xticks(range(len(chans)))
    ax.set_xticklabels(ticks)
    ax.set_xlabel("LED (nm, or broadband colour)")
    ax.set_ylabel("signal ÷ OPT101 850 nm (log)")
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.set_title(
        "Spectral fingerprint at the same head height (63 mm below the top), brightness removed",
        loc="left",
        fontsize=11,
    )
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=3)
    fig.tight_layout()
    fig.savefig(FIG / "variance_2026-11-25_fingerprints.png", facecolor=SURFACE)


def distances() -> None:
    mean = lambda xs: st.fmean([x["d"][0] for x in xs])  # noqa: E731
    items = [
        ("between", "Citrucel vs whey (5 matched heights)", mean(r["citrucel_vs_whey"])),
        ("between", "Citrucel vs whey (near the top)", mean(r["citrucel_vs_whey_near_top"])),
        ("between", "White paper vs black card (24 Nov bench)", r["bench_white_vs_black"][0]),
        ("within", "Black card, re-placed (24 Nov)", r["bench_B1_vs_B2"][0]),
        ("within", "Citrucel, start vs end of its scan", r["citrucel_P1_vs_P4"][0]),
        ("within", "White paper, re-placed (24 Nov)", r["bench_W1_vs_W2"][0]),
        ("within", "Whey, start vs end of its scan", r["whey_P1_vs_P4"][0]),
        ("within", "Whey, two separate runs (near the top)", mean(r["whey_vs_whey_b_near_top"])),
        ("within", "Whey, 6 mm head-height difference", r["whey_height_effect"][-1]["d"][0]),
    ]
    color = {"between": "#2a78d6", "within": "#eb6834"}
    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ys = list(range(len(items)))[::-1]
    for y, (g, _lab, v) in zip(ys, items, strict=True):
        ax.barh(y, v, height=0.62, color=color[g], edgecolor=SURFACE)
        ax.text(v + 0.006, y, f"{v:.3f}", va="center", color=INK, fontsize=9)
    ax.set_yticks(ys)
    ax.set_yticklabels([i[1] for i in items])
    ax.set_xlabel("shape distance (RMS log-ratio per channel, brightness removed)")
    ax.set_xlim(0, 0.45)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    from matplotlib.patches import Patch

    ax.legend(
        handles=[
            Patch(color=color["between"], label="different materials"),
            Patch(color=color["within"], label="same material (re-placed, drift, height)"),
        ],
        frameon=False,
        loc="lower right",
    )
    ax.set_title(
        "How different the two foods look vs how much one material varies", loc="left", fontsize=11
    )
    fig.tight_layout()
    fig.savefig(FIG / "variance_2026-11-25_shape_distances.png", facecolor=SURFACE)


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    fingerprints()
    distances()
    print("figures ->", FIG)
