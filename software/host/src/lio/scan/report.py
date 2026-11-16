"""The scan report (plan §5, S5): ``report.html`` and ``report.md`` with plots, in the
run folder. Rebuilt from scan.json, cube.csv.gz, the streams and analysis.json alone:

    lio scan report <run>

Plots: hole x height heat-maps per detector, response curves down/up per hole (small
multiples), dark level vs height, mains/noise spectra, control charts (with
baselines). Colours follow the suite report (OPT101 blue, InGaAs orange, status
colours with an icon and a word); every plot sits next to a table.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jinja2
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from lio.config import HwConfig
from lio.report import (
    DETECTOR_COLOR,
    DETECTOR_LABEL,
    INK_2,
    SEQUENTIAL,
    STATUS_STYLE,
    VERDICT_STYLE,
    _figure,
    _style,
)
from lio.scan.analysis import analyse
from lio.scan.analysis.data import DETECTORS, Cube

HEALTH_STYLE = {"OK": ("#0ca30c", "✓"), "WATCH": ("#fab219", "!"), "ACT": ("#d03b3b", "✕"),
                "n/a": ("#8a8984", "-")}  # fmt: skip
PLOT_TITLES = {
    "heatmap": "Response vs height, per hole (down pass; blind holes blank)",
    "curves": "Response curves: down pass (solid) and up pass (dashed)",
    "dark": "Dark level vs height (light leak) and over time (drift)",
    "spectra": "Dark noise: mains harmonics and broadband",
    "control": "Control charts against the baselines",
}


def _mm_label(cfg: HwConfig) -> tuple[float | None, str]:
    lead = cfg.section.raw("scan.lead_mm_per_rev")
    if lead in (None, ""):
        return None, "height (half-steps from the top)"
    return float(lead) / 4096.0, "height (mm from the top)"


def plot_heatmap(cube: Cube, cfg: HwConfig, path: Path) -> Path | None:
    k, xlab = _mm_label(cfg)
    fig = _figure(10, 4.2)
    axes = fig.subplots(1, 2)
    cmap = LinearSegmentedColormap.from_list("seq", SEQUENTIAL)
    any_data = False
    for ax, det in zip(axes, DETECTORS, strict=True):
        rows: list[np.ndarray[Any, Any] | None] = []
        heights: np.ndarray[Any, Any] | None = None
        for hole in range(1, 17):
            c = cube.curve(hole, det)
            if not len(c) or cfg.channel(hole).expect_for(det) == "none":
                rows.append(None)  # blind: noise only, normalising it would look like light
                if len(c):
                    heights = c.h
                continue
            heights = c.h
            rows.append(np.array(c.net, dtype=np.float64))
        if heights is None:
            ax.set_visible(False)
            continue
        any_data = True
        n = len(heights)
        img = np.array([r if r is not None and len(r) == n else np.full(n, np.nan) for r in rows])
        x = heights * k if k else heights
        top = float(np.nanmax(img)) if np.isfinite(img).any() else 1.0
        im = ax.imshow(img, aspect="auto", cmap=cmap, vmin=0, vmax=max(top, 1.0),
                       interpolation="nearest",
                       extent=(float(x[0]), float(x[-1]), 16.5, 0.5))  # fmt: skip
        cb = fig.colorbar(im, ax=ax, shrink=0.85)
        cb.set_label("net (counts)", fontsize=8, color=INK_2)
        cb.ax.tick_params(labelsize=7, colors=INK_2)
        ax.set_yticks(range(1, 17), [
            f"{h} {cfg.channel(h).label}" + (" (blind)" if rows[h - 1] is None else "")
            for h in range(1, 17)])  # fmt: skip
        ax.set_title(DETECTOR_LABEL[det], fontsize=10)
        ax.set_xlabel(xlab)
        _style(ax)
        ax.grid(False)
    if not any_data:
        return None
    fig.savefig(path)
    return path


def plot_curves(cube: Cube, cfg: HwConfig, path: Path) -> Path | None:
    k, xlab = _mm_label(cfg)
    fig = _figure(11, 9)
    axes = fig.subplots(4, 4, sharex=True)
    drawn = False
    for hole, ax in zip(range(1, 17), axes.flat, strict=True):
        _style(ax)
        ax.set_title(f"hole {hole} ({cfg.channel(hole).label})", fontsize=8)
        if not cfg.channel(hole).expected_detectors:
            ax.text(0.5, 0.5, "seen by neither detector\n(see plausibility)", ha="center",
                    va="center", transform=ax.transAxes, fontsize=8, color=INK_2)  # fmt: skip
            ax.set_yticks([])
        for det in DETECTORS:
            if cfg.channel(hole).expect_for(det) == "none":
                continue
            for phase, ls, direction in (("P2", "-", None), ("P3", "--", "up")):
                c = cube.curve(hole, det, phase=phase, direction=direction)
                if len(c):
                    drawn = True
                    x = c.h * k if k else c.h
                    ax.plot(x, c.net, ls, color=DETECTOR_COLOR[det], linewidth=1.6,
                            marker="o", markersize=3,
                            label=f"{det} {'down' if phase == 'P2' else 'up'}")  # fmt: skip
    if not drawn:
        return None
    handles, labels = [], []
    for ax in axes.flat:
        for h, lab in zip(*ax.get_legend_handles_labels(), strict=True):
            if lab not in labels:
                handles.append(h)
                labels.append(lab)
    fig.legend(handles, labels, loc="outside upper center", ncol=4, fontsize=8, frameon=False)
    fig.supxlabel(xlab, fontsize=9, color=INK_2)
    fig.supylabel("net (counts)", fontsize=9, color=INK_2)
    fig.savefig(path)
    return path


def plot_dark(cube: Cube, cfg: HwConfig, path: Path) -> Path | None:
    k, xlab = _mm_label(cfg)
    fig = _figure(10, 6)
    axes = fig.subplots(2, 2)
    drawn = False
    for col, det in enumerate(DETECTORS):
        t, h, d, _ = cube.darks(det)
        m = np.isfinite(d)
        if not m.any():
            continue
        drawn = True
        ax = axes[0][col]
        _style(ax)
        ax.plot(h[m] * k if k else h[m], d[m] * 0.125, "o", color=DETECTOR_COLOR[det],
                markersize=4)  # fmt: skip
        ax.set_title(f"{DETECTOR_LABEL[det]}: dark vs height", fontsize=9)
        ax.set_xlabel(xlab)
        ax.set_ylabel("dark (mV)")
        ax = axes[1][col]
        _style(ax)
        ax.plot(t[m] / 60, d[m] * 0.125, "o-", color=DETECTOR_COLOR[det], markersize=3,
                linewidth=1)  # fmt: skip
        ax.set_title(f"{DETECTOR_LABEL[det]}: dark over the run", fontsize=9)
        ax.set_xlabel("time (min)")
        ax.set_ylabel("dark (mV)")
    if not drawn:
        return None
    fig.savefig(path)
    return path


def plot_spectra(analysis: dict[str, Any], path: Path) -> Path | None:
    spectra = (analysis.get("context") or {}).get("electrical", {}).get("spectra") or {}
    if not any(spectra.values()):
        return None
    fig = _figure(10, 3.4)
    axes = fig.subplots(1, 2)
    keys = ["60", "120", "180"]
    for ax, det in zip(axes, DETECTORS, strict=True):
        _style(ax)
        sp = spectra.get(det)
        if not sp:
            ax.set_visible(False)
            continue
        vals = [sp["amp_counts"][x] * 0.125 for x in keys] + [sp["sigma_counts"] * 0.125]
        names = ["60 Hz", "120 Hz", "180 Hz", "broadband sigma"]
        ax.bar(names, vals, color=DETECTOR_COLOR[det], width=0.6)
        for i, v in enumerate(vals):
            ax.annotate(f"{v:.3f}", (i, v), ha="center", va="bottom", fontsize=8, color=INK_2)
        ax.set_ylabel("mV")
        ax.set_title(f"{DETECTOR_LABEL[det]}: {100 * sp['mains_fraction']:.0f}% of the variance "
                     "at mains harmonics", fontsize=9)  # fmt: skip
    fig.savefig(path)
    return path


def plot_control(analysis: dict[str, Any], path: Path) -> Path | None:
    f = next((x for x in analysis["findings"] if x["id"] == "trend/control"), None)
    data: dict[str, Any] = (f or {}).get("data") or {}
    charts = data.get("charts") or {}
    if not charts:
        return None
    out_of = data.get("out_of_limits") or {}
    names = sorted(charts, key=lambda m: m not in out_of)[:8]
    fig = _figure(10, 1.9 * ((len(names) + 1) // 2) + 0.4)
    axes = np.atleast_1d(fig.subplots((len(names) + 1) // 2, 2)).flat
    for ax, name in zip(axes, names, strict=False):
        c = charts[name]
        _style(ax)
        ys = [*c["history"], c["value"]]
        ax.plot(range(len(ys)), ys, "o-", color=INK_2, markersize=3, linewidth=1)
        ax.plot([len(ys) - 1], [c["value"]], "o", markersize=6,
                color="#d03b3b" if name in out_of else "#0ca30c")  # fmt: skip
        for v in (c["mean"] - 3 * c["sd"], c["mean"], c["mean"] + 3 * c["sd"]):
            ax.axhline(v, color=INK_2, linewidth=0.8, linestyle=":" if v != c["mean"] else "-")
        ax.set_title(name, fontsize=8)
    fig.savefig(path)
    return path


def make_plots(folder: Path, cube: Cube, analysis: dict[str, Any], cfg: HwConfig) -> dict[str, str]:
    pdir = folder / "plots"
    pdir.mkdir(exist_ok=True)
    out: dict[str, str] = {}
    makers: dict[str, Callable[[Path], Path | None]] = {
        "heatmap": lambda p: plot_heatmap(cube, cfg, p),
        "curves": lambda p: plot_curves(cube, cfg, p),
        "dark": lambda p: plot_dark(cube, cfg, p),
        "spectra": lambda p: plot_spectra(analysis, p),
        "control": lambda p: plot_control(analysis, p),
    }
    for key, fn in makers.items():
        p = fn(pdir / f"{key}.png")
        if p is not None:
            out[key] = str(p.relative_to(folder))
    return out


def _groups(analysis: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    titles = {"system": "System", "optics": "Optics", "elec": "Electrical", "ambient": "Ambient",
              "mech": "Mechanics", "trend": "Trend"}  # fmt: skip
    out: dict[str, list[dict[str, Any]]] = {}
    for f in analysis["findings"]:
        out.setdefault(titles.get(f["id"].split("/")[0], "Other"), []).append(f)
    return list(out.items())


def render_markdown(meta: dict[str, Any], a: dict[str, Any], plots: dict[str, str]) -> str:
    v = a.get("verdict") or {}
    lines = [
        f"# LIO diagnostic sweep {a['run_id']}",
        "",
        f"Mode **{a['mode']}**, sample **{a['sample_id']}**, status **{a['status']}**"
        + (" (simulator)" if meta.get("simulated") else ""),
        "",
        f"## Verdict: {v.get('verdict', '?')}",
        "",
        *[f"- {r}" for r in v.get("reasons", [])],
        "",
        "## Subsystem health",
        "",
        "| Subsystem | Parts | Health | Reason |",
        "|---|---|---|---|",
        *[f"| {h['title']} | {h['parts']} | {HEALTH_STYLE[h['health']][1]} {h['health']} | "
          f"{h['reason'].replace('|', '/')} |" for h in a.get("health", [])],
        "",
    ]  # fmt: skip
    flagged = [f for f in a["findings"] if f["status"] in ("WARN", "FAIL")]
    if flagged:
        lines += ["## Findings to act on", ""]
        for f in flagged:
            e = f.get("explanation") or {}
            lines += [f"### {STATUS_STYLE[f['status']][1]} {f['status']} `{f['id']}`: {f['title']}",
                      "", f"{f['detail']}", ""]  # fmt: skip
            if e:
                lines += [f"- **Why:** {e['cause']}", f"- **Parts:** {', '.join(e['parts'])}",
                          f"- **Next check:** {e['check']}", ""]  # fmt: skip
    for title, rel in ((PLOT_TITLES[k], r) for k, r in plots.items()):
        lines += [f"## {title}", "", f"![{title}]({rel})", ""]
    for group, fs in _groups(a):
        lines += [f"## {group}", "", "| Status | Metric | Value | Result | Criterion |",
                  "|---|---|---|---|---|"]  # fmt: skip
        for f in fs:
            val = "" if f["value"] is None else f"{f['value']:g} {f['unit']}"
            lines.append(f"| {STATUS_STYLE[f['status']][1]} {f['status']} | `{f['id']}` | {val} | "
                         f"{f['detail'].replace('|', '/')} | {f['criteria']} |")  # fmt: skip
        lines.append("")
    skipped = meta.get("skipped_checks") or {}
    if skipped:
        lines += ["## Not measured (capability)", ""]
        lines += [f"- {k}: {why}" for k, why in skipped.items()]
    return "\n".join(lines) + "\n"


_TEMPLATE = jinja2.Environment(
    loader=jinja2.PackageLoader("lio", "templates"),
    autoescape=jinja2.select_autoescape(["html", "j2"]),
)


def render_html(meta: dict[str, Any], a: dict[str, Any], plots: dict[str, str],
                cfg: HwConfig) -> str:  # fmt: skip
    return _TEMPLATE.get_template("scan_report.html.j2").render(
        m=meta, a=a, groups=_groups(a),
        plots=[(PLOT_TITLES[k], rel) for k, rel in plots.items()],
        status_style=STATUS_STYLE, health_style=HEALTH_STYLE,
        verdict_color=VERDICT_STYLE.get(str((a.get("verdict") or {}).get("verdict")), INK_2),
        hardware=cfg.section.raw("scan.hardware"),
        provisional=bool(cfg.section.raw("scan.health.provisional")),
    )  # fmt: skip


def write(folder: Path, cfg: HwConfig, *, reference: Path | None = None,
          baselines_root: Path | None = None) -> dict[str, Path]:  # fmt: skip
    """Analyse (if needed) and write plots/, report.md and report.html into the run folder."""
    folder = Path(folder)
    if (
        reference is not None
        or baselines_root is not None
        or not (folder / "analysis.json").exists()
    ):
        analyse(folder, cfg, reference, baselines_root)
    a = json.loads((folder / "analysis.json").read_text())
    cube = Cube.open(folder)
    plots = make_plots(folder, cube, a, cfg)
    md = folder / "report.md"
    md.write_text(render_markdown(cube.meta, a, plots))
    html = folder / "report.html"
    html.write_text(render_html(cube.meta, a, plots, cfg))
    return {"md": md, "html": html, **{k: folder / v for k, v in plots.items()}}
