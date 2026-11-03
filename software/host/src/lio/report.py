"""Run reports (plan §5.3): plots, ``report.md`` and ``report.html``.

Everything is rebuilt from the run record alone, so ``lio report results.json``
regenerates a report later. Plots use matplotlib's object API (no pyplot, no
display needed). Colours follow one fixed identity per detector (OPT101 blue,
InGaAs orange; validated for colour-vision deficiency), and every plot sits
next to a table in the report, so nothing is conveyed by colour alone.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import jinja2
from matplotlib.axes import Axes
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure

from lio.config import HwConfig
from lio.csvout import write_meas_csv
from lio.device import Meas
from lio.results import RunRecord, TestResult

DETECTOR_COLOR = {"opt101": "#2a78d6", "ingaas": "#eb6834"}
DETECTOR_LABEL = {"opt101": "OPT101 (silicon)", "ingaas": "InGaAs (SWIR)"}
DETECTORS = ("opt101", "ingaas")
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
STATUS_STYLE = {  # colour + icon + word: never colour alone
    "PASS": ("#0ca30c", "✓"),
    "WARN": ("#fab219", "!"),
    "FAIL": ("#d03b3b", "✕"),
    "ERROR": ("#d03b3b", "✕"),
    "SKIP": ("#8a8984", "-"),
}
VERDICT_STYLE = {"FUNCTIONAL": "#0ca30c", "DEGRADED": "#fab219", "NOT FUNCTIONAL": "#d03b3b"}


# -------------------------------------------------------------------- plots


def _figure(w: float, h: float) -> Figure:
    fig = Figure(figsize=(w, h), dpi=110, facecolor=SURFACE, layout="constrained")
    return fig


def _style(ax: Axes) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_2)
    ax.tick_params(colors=INK_2, labelsize=8)
    ax.title.set_color(INK)
    ax.xaxis.label.set_color(INK_2)
    ax.yaxis.label.set_color(INK_2)


def _sub(result: TestResult | None, measured_key: str) -> dict[str, Any]:
    return (
        {}
        if result is None
        else {
            s.id.split("/", 1)[1]: s.measured[measured_key]
            for s in result.subs
            if measured_key in s.measured
        }
    )


def _result(record: RunRecord, test_id: str) -> TestResult | None:
    try:
        return record.result(test_id)
    except KeyError:
        return None


def _hole_labels(cfg: HwConfig | None, holes: Sequence[int]) -> list[str]:
    if cfg is None:
        return [str(h) for h in holes]
    return [f"{h}\n{cfg.channel(h).label}" for h in holes]


def _matrix(record: RunRecord) -> dict[int, dict[str, float]]:
    """T05.3 matrix with integer hole keys (they are strings after a JSON round trip)."""
    r = _result(record, "T05.3")
    raw = r.measured.get("matrix") if r else None
    return {int(h): {d: float(v) for d, v in nets.items()} for h, nets in (raw or {}).items()}


def plot_channels(record: RunRecord, path: Path, cfg: HwConfig | None) -> Path | None:
    matrix = _matrix(record)
    if not matrix:
        return None
    holes = sorted(matrix)
    fig = _figure(10, 3.8)
    ax = fig.add_subplot()
    width = 0.38
    for i, det in enumerate(DETECTORS):
        vals = [matrix[h].get(det, 0.0) for h in holes]
        xs = [h + (i - 0.5) * (width + 0.02) for h in holes]
        ax.bar(xs, vals, width=width, color=DETECTOR_COLOR[det], label=DETECTOR_LABEL[det])
    ax.axhline(0, color=INK_2, linewidth=0.8)
    ax.set_xticks(holes, _hole_labels(cfg, holes))
    ax.set_ylabel("net signal (counts, lit - dark)")
    ax.set_title("Per-channel response (T05.2 / T05.3)", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    fig.savefig(path)
    return path


def plot_crosstalk(record: RunRecord, path: Path, cfg: HwConfig | None) -> Path | None:
    matrix = _matrix(record)
    if not matrix:
        return None
    holes = sorted(matrix)
    data = [[matrix[h].get(det, 0.0) for h in holes] for det in DETECTORS]
    norm = [[max(v, 0.0) / (max(row) or 1.0) for v in row] for row in data]
    fig = _figure(10, 2.2)
    ax = fig.add_subplot()
    cmap = LinearSegmentedColormap.from_list("lio_blue", SEQUENTIAL)
    im = ax.imshow(norm, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for y, row in enumerate(data):
        for x, v in enumerate(row):
            ax.text(
                x,
                y,
                f"{v:.0f}",
                ha="center",
                va="center",
                fontsize=7,
                color=SURFACE if norm[y][x] > 0.55 else INK,
            )
    ax.set_xticks(range(len(holes)), _hole_labels(cfg, holes))
    ax.set_yticks(range(2), [DETECTOR_LABEL[d] for d in DETECTORS])
    ax.set_title(
        "Response matrix: hole x detector (fraction of each detector's maximum)",
        loc="left",
        fontsize=10,
    )
    fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01)
    ax.tick_params(labelsize=8, colors=INK_2)
    fig.savefig(path)
    return path


def plot_noise(record: RunRecord, path: Path) -> Path | None:
    raw = _sub(_result(record, "T03.5"), "raw")
    if not raw:
        return None
    fig = _figure(10, 3.0)
    for i, det in enumerate(d for d in DETECTORS if d in raw):
        ax = fig.add_subplot(1, 2, i + 1)
        ax.hist(raw[det], bins=30, color=DETECTOR_COLOR[det], edgecolor=SURFACE, linewidth=1)
        ax.set_title(f"{DETECTOR_LABEL[det]}: dark readings (T03.5)", loc="left", fontsize=10)
        ax.set_xlabel("counts")
        ax.set_ylabel("readings")
        _style(ax)
    fig.savefig(path)
    return path


def plot_settling(record: RunRecord, path: Path) -> Path | None:
    r = _result(record, "T07.1")
    subs = [s for s in r.subs if "raw" in s.measured] if r else []
    if not subs:
        return None
    fig = _figure(10, 3.0)
    for i, s in enumerate(subs):
        m = s.measured
        ax = fig.add_subplot(1, len(subs), i + 1)
        t_ms = [t / 1000.0 for t in m["t_us"]]
        on, off = m["on_idx"], m["off_idx"]
        ax.axvspan(t_ms[on - 1], t_ms[off - 1], color=GRID, linewidth=0)
        ax.plot(
            t_ms,
            m["raw"],
            color=DETECTOR_COLOR[m["detector"]],
            linewidth=2,
            marker="o",
            markersize=3,
        )
        ax.set_title(
            f"{s.id.split('/')[1]}: {m['detector']} (LED on shaded)", loc="left", fontsize=9
        )
        ax.set_xlabel("time (ms)")
        if i == 0:
            ax.set_ylabel("counts")
        _style(ax)
    fig.savefig(path)
    return path


def plot_sweeps(record: RunRecord, path: Path, cfg: HwConfig | None) -> Path | None:
    r = _result(record, "T08.2")
    sweeps = r.measured.get("sweeps") if r else None
    if not sweeps:
        return None
    holes = sorted(int(h) for h in sweeps[0])
    fig = _figure(10, 3.2)
    for i, det in enumerate(DETECTORS):
        ax = fig.add_subplot(1, 2, i + 1)
        for k, sw in enumerate(sweeps):
            ax.plot(
                holes,
                [sw[str(h)][det] for h in holes],
                color=DETECTOR_COLOR[det],
                linewidth=1.2,
                alpha=0.6,
                marker="o",
                markersize=3,
                label=f"{len(sweeps)} sweeps" if k == 0 else None,
            )
        ax.set_xticks(holes, [str(h) for h in holes])
        ax.set_title(f"{DETECTOR_LABEL[det]}: repeated sweeps (T08.2)", loc="left", fontsize=10)
        ax.set_xlabel("hole")
        ax.set_ylabel("net (counts)")
        ax.legend(frameon=False, fontsize=8)
        _style(ax)
    fig.savefig(path)
    return path


def plot_sweep(path: Path, records: Iterable[Meas], cfg: HwConfig) -> Path:
    """Single-sweep plot in volts (logger and ``lio sweep --plot``)."""
    recs = list(records)
    vpc = cfg.lsb_mv / 1000.0
    holes = [m.hole for m in recs]
    fig = _figure(10, 4.5)
    ax = fig.add_subplot()
    for det, marker in (("opt101", "o"), ("ingaas", "s")):
        ax.plot(
            holes,
            [m.net(det) * vpc for m in recs],
            color=DETECTOR_COLOR[det],
            marker=marker,
            markersize=5,
            linewidth=2,
            label=DETECTOR_LABEL[det],
        )
    ax.set_xticks(holes, [cfg.channel(h).label for h in holes], rotation=45)
    ax.set_xlabel("channel / wavelength (nm)")
    ax.set_ylabel("net signal (V, dark-subtracted)")
    ax.set_title("LIO sweep", loc="left", fontsize=10)
    ax.legend(frameon=False)
    _style(ax)
    fig.savefig(path)
    return path


def make_plots(record: RunRecord, folder: Path, cfg: HwConfig | None) -> dict[str, str]:
    folder.mkdir(parents=True, exist_ok=True)
    made = {
        "channels": plot_channels(record, folder / "channels.png", cfg),
        "crosstalk": plot_crosstalk(record, folder / "crosstalk.png", cfg),
        "noise": plot_noise(record, folder / "noise.png"),
        "settling": plot_settling(record, folder / "settling.png"),
        "sweeps": plot_sweeps(record, folder / "sweeps.png", cfg),
    }
    return {k: f"{folder.name}/{p.name}" for k, p in made.items() if p is not None}


# ------------------------------------------------------------------ documents


PLOT_TITLES = {
    "channels": "Per-channel response",
    "crosstalk": "Response matrix",
    "noise": "Dark noise",
    "settling": "Step responses",
    "sweeps": "Repeated sweeps",
}


def _modules(record: RunRecord) -> list[tuple[str, list[TestResult]]]:
    out: dict[str, list[TestResult]] = {}
    for r in record.results:
        out.setdefault(r.module, []).append(r)
    return list(out.items())


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(record: RunRecord, plots: dict[str, str]) -> str:
    v = record.verdict
    lines = [
        f"# LIO test report: {record.run_id}",
        "",
        f"**Verdict: {v.get('verdict', '?')}**"
        + (f": {'; '.join(v.get('reasons', []))}" if v.get("reasons") else ""),
        "",
        f"- Target: `{record.target}`"
        + (f" (faults: {', '.join(record.faults)})" if record.faults else ""),
        f"- Started {record.started}, finished {record.finished}",
        f"- Sample: `{record.metadata.get('sample_id')}`, operator: "
        f"{record.metadata.get('operator')}"
        + (f", notes: {record.metadata['notes']}" if record.metadata.get("notes") else ""),
        f"- Firmware {record.firmware.get('fw', '?')} (proto {record.firmware.get('proto', '?')}"
        f", build {record.firmware.get('build', '?')})",
        f"- Config `{record.config.get('path')}` sha256 {str(record.config.get('sha256'))[:12]}"
        + (" (thresholds provisional)" if record.config.get("provisional") else ""),
        f"- Host: {record.environment.get('os')}, Python {record.environment.get('python')}, "
        f"lio {record.environment.get('lio_package')}, git "
        f"{str(record.environment.get('git_commit'))[:10]}"
        + (" (dirty)" if record.environment.get("git_dirty") else ""),
        "- Counts: " + ", ".join(f"{k} {n}" for k, n in v.get("counts", {}).items() if n),
    ]
    duty = record.duty
    if duty:
        lines.append(
            f"- LED duty budget: {duty.get('total_cooldown_s', 0):.1f} s of cool-down waits, "
            f"{len(duty.get('over_budget', []))} over-budget on-time(s)"
        )
    lines += ["", "## Summary", "", "| Test | Name | Status | Note |", "|---|---|---|---|"]
    for r in record.results:
        lines.append(
            f"| {r.id} | {r.name} | {STATUS_STYLE[r.status.value][1]} {r.status.value} "
            f"| {_md_escape(r.message)} |"
        )
    for key, rel in plots.items():
        lines += ["", f"### {PLOT_TITLES[key]}", "", f"![{PLOT_TITLES[key]}]({rel})"]
    for module, results in _modules(record):
        lines += ["", f"## {module}"]
        for r in results:
            lines += ["", f"### {r.id} {r.name}: {r.status.value}"]
            if r.message:
                lines += ["", _md_escape(r.message)]
            if r.subs:
                lines += ["", "| Check | Status | Result | Criterion |", "|---|---|---|---|"]
                order = sorted(r.subs, key=lambda s: -s.status.rank)
                for s in order:
                    lines.append(
                        f"| {s.name} | {STATUS_STYLE[s.status.value][1]} "
                        f"{s.status.value} | {_md_escape(s.message)} | "
                        f"{_md_escape(s.criteria)} |"
                    )
    return "\n".join(lines) + "\n"


_TEMPLATE = jinja2.Environment(
    loader=jinja2.PackageLoader("lio", "templates"),
    autoescape=jinja2.select_autoescape(["html", "j2"]),
)


def render_html(record: RunRecord, plots: dict[str, str]) -> str:
    template = _TEMPLATE.get_template("report.html.j2")
    return template.render(
        r=record,
        modules=_modules(record),
        plots=[(PLOT_TITLES[k], rel) for k, rel in plots.items()],
        status_style=STATUS_STYLE,
        verdict_color=VERDICT_STYLE.get(str(record.verdict.get("verdict")), INK_2),
    )


def write_run(
    record: RunRecord,
    folder: Path,
    *,
    cfg: HwConfig | None = None,
    meas_log: Iterable[tuple[str, Meas]] | None = None,
) -> dict[str, Path]:
    """Write results.json, meas.csv, plots/, report.md and report.html into ``folder``."""
    folder.mkdir(parents=True, exist_ok=True)
    out = {"json": record.write_json(folder / "results.json")}
    if meas_log is not None and cfg is not None:
        out["csv"] = write_meas_csv(folder / "meas.csv", meas_log, cfg)
    plots = make_plots(record, folder / "plots", cfg)
    md = folder / "report.md"
    md.write_text(render_markdown(record, plots))
    html = folder / "report.html"
    html.write_text(render_html(record, plots))
    out.update(md=md, html=html)
    return out


def rebuild(results_json: Path, cfg: HwConfig | None = None) -> dict[str, Path]:
    """Regenerate the reports of an earlier run from its results.json."""
    record = RunRecord.load(results_json)
    return write_run(record, results_json.parent, cfg=cfg)
