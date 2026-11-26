"""Figures for the three-food variance assessment (reads results3.json)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
FIG = HERE.parents[2] / "docs" / "research" / "figures"
r = json.loads((HERE / "results3.json").read_text())
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
COL = {"empty": "#2a78d6", "citrucel": "#eb6834", "whey": "#1baf7a", "rub": "#eda100"}
NAME = {
    "empty": "Empty chamber",
    "citrucel": "Citrucel (F-00001)",
    "whey": "Whey (F-00002)",
    "rub": "Barbecue Rub (F-00003)",
}
NM = {
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


def _ax(w: float, h: float):
    fig, ax = plt.subplots(figsize=(w, h), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    return fig, ax


def fingerprints() -> None:
    fp = r["fingerprint_rel_h8"]
    chans = list(fp["citrucel"])
    fig, ax = _ax(12, 4.8)
    order = ("empty", "citrucel", "whey", "rub")
    w = 0.2
    for i, k in enumerate(order):
        xs = [j + (i - 1.5) * w for j in range(len(chans))]
        ax.bar(
            xs,
            [fp[k][c] for c in chans],
            width=w - 0.03,
            color=COL[k],
            label=NAME[k],
            edgecolor=SURFACE,
            linewidth=1.0,
        )
    n_opt = sum(c.endswith("opt101") for c in chans)
    ax.axvline(n_opt - 0.5, color=MUTED, linewidth=1, linestyle=(0, (3, 3)))
    ax.text(1.5, 2.2, "OPT101 (silicon)", ha="center", color=INK2)
    ax.text(n_opt + (len(chans) - n_opt) / 2 - 0.5, 2.2, "InGaAs", ha="center", color=INK2)
    ax.axvspan(3.5, 6.5, color=GRID, alpha=0.35, zorder=0)
    ax.text(
        5,
        1.15,
        "h5-h7: unstable in the\nRub run, see text",
        ha="center",
        va="bottom",
        color=MUTED,
        fontsize=8,
    )
    ax.set_yscale("log")
    ax.set_ylim(0.01, 3)
    ax.set_xticks(range(len(chans)))
    ax.set_xticklabels([NM.get(c.split("/")[0], c) for c in chans])
    ax.set_xlabel("LED (nm, or broadband colour)")
    ax.set_ylabel("signal ÷ OPT101 850 nm (log)")
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_title(
        "Spectral fingerprints at the same head height (63 mm), brightness removed",
        loc="left",
        fontsize=11,
    )
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=4)
    fig.tight_layout()
    fig.savefig(FIG / "variance_2026-11-26_fingerprints.png", facecolor=SURFACE)


def distances() -> None:
    wo, wi = r["without_h5_h7"], r["within"]
    items = [
        ("between", "Whey vs Barbecue Rub", wo["pairs"]["whey|rub"]),
        ("between", "Citrucel vs Barbecue Rub", wo["pairs"]["citrucel|rub"]),
        ("between", "Citrucel vs whey", wo["pairs"]["citrucel|whey"]),
        ("within", "Black card, re-placed (24 Nov)", wi["black card re-placed (24 Nov)"]),
        ("within", "Barbecue Rub, start vs end", wo["start_vs_end"]["rub"]),
        ("within", "White paper, re-placed (24 Nov)", wi["white paper re-placed (24 Nov)"]),
        ("within", "Citrucel, start vs end", wo["start_vs_end"]["citrucel"]),
        ("within", "Whey, start vs end", wo["start_vs_end"]["whey"]),
        ("within", "Whey, two separate runs", wi["whey two runs (near top)"]),
    ]
    color = {"between": "#2a78d6", "within": "#eb6834"}
    fig, ax = _ax(10, 4.8)
    ys = list(range(len(items)))[::-1]
    for y, (g, _lab, v) in zip(ys, items, strict=True):
        ax.barh(y, v, height=0.62, color=color[g], edgecolor=SURFACE)
        ax.text(v + 0.008, y, f"{v:.3f}", va="center", color=INK, fontsize=9)
    ax.set_yticks(ys)
    ax.set_yticklabels([i[1] for i in items])
    ax.set_xlabel("shape distance (RMS log-ratio per channel, brightness removed; h5-h7 excluded)")
    ax.set_xlim(0, 0.72)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(
        handles=[
            Patch(color=color["between"], label="different foods"),
            Patch(color=color["within"], label="same material"),
        ],
        frameon=False,
        loc="lower right",
    )
    ax.set_title(
        "Differences between the three foods vs variation within one material",
        loc="left",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(FIG / "variance_2026-11-26_shape_distances.png", facecolor=SURFACE)


def pca() -> None:
    pts = defaultdict(list)
    for q in r["pca"]["points"]:
        pts[q["sample"]].append((q["pc1"], q["pc2"]))
    ev = r["pca"]["explained"]
    fig, ax = _ax(7.5, 5.2)
    for k in ("empty", "citrucel", "whey", "rub"):
        xs, ys = zip(*pts[k], strict=True)
        ax.scatter(
            xs, ys, s=46, color=COL[k], edgecolor=SURFACE, linewidth=1.5, label=NAME[k], zorder=3
        )
        ax.annotate(
            NAME[k],
            (sum(xs) / len(xs), max(ys)),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            color=INK2,
            fontsize=9,
        )
    ax.axhline(0, color=GRID, linewidth=0.8, zorder=1)
    ax.axvline(0, color=GRID, linewidth=0.8, zorder=1)
    ax.set_xlabel(f"PC1 ({100 * ev[0]:.0f} %): violet/blue  ↔  near-infrared")
    ax.set_ylabel(f"PC2 ({100 * ev[1]:.0f} %): SWIR 1450/1760  ↔  yellow-green")
    ax.set_title(
        "Each sample at 5 head heights (brightness-removed fingerprints)", loc="left", fontsize=11
    )
    ax.legend(frameon=False, loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "variance_2026-11-26_pca.png", facecolor=SURFACE)


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    fingerprints()
    distances()
    pca()
    print("figures ->", FIG)
