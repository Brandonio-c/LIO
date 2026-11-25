"""T13 Diagnostic height sweep (plan LIO-SW-SCAN-001 §5): the whole-system scan as a
catalogue test (kind M: it moves the chamber top, so it needs --allow-motion).

Runs ``scan.suite_mode`` (lio_hw.yaml), analyses it, writes its report, and reports
every finding as a sub-result whose id is the finding id, so the digital twin and
the T11 verdict read it unchanged: ``.../hNN/...`` on the holes, a detector name on
the detectors, ``A/...`` and ``B/...`` on the rails.

On the hardware the stage must be tracked with both limits marked; the run folder
goes to test_results/ beside the other runs. On the simulator a stage is set up
(top at the start) and the run goes to a temporary folder.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from lio import scan
from lio.results import Status, TestResult, worst
from lio.scan import report as scan_report
from lio.scan.analysis import Analysis, analyse
from lio.suite.core import Recorder, Skip, SuiteContext, register

CAPABILITY_IDS = ("elec/rails", "mech/home", "elec/coupling_states")


def sub_id(fid: str) -> str:
    """The finding id, with the rail findings rooted at the rail (twin convention)."""
    if fid.startswith("system/rail/"):
        return f"{fid.rsplit('/', 1)[1]}/rail"
    return fid


@register("T13.1", "Diagnostic height sweep", kind="M")
def t13_1(ctx: SuiteContext, rec: Recorder) -> None:
    cfg = ctx.cfg
    mode = str(cfg.section.raw("scan.suite_mode"))
    if ctx.operator is None:
        raise Skip("needs an operator (the scan asks before moving)")
    dev = ctx.dev
    if ctx.sim is not None:
        if dev.stage is None:
            tmp = Path(tempfile.mkdtemp(prefix="lio_t13_"))
            scan.sim_stage(dev, tmp / "stage.json", int(ctx.sim.travel_hs))
        root = Path(tempfile.mkdtemp(prefix="lio_t13_runs_"))
    else:
        st = dev.stage
        if st is None or not st.known or st.limits.top is None or st.limits.bottom is None:
            raise Skip("stage travel not tracked: set the top and mark the bottom first")
        root = Path(cfg.path).resolve().parents[2] / "test_results"
    sample = str(ctx.cache.get("sample_id") or "empty")
    aliases = cfg.section.raw("scan.sample_aliases") or {}
    sample = str(aliases.get(sample, sample))
    vocab = [str(x) for x in cfg.section.raw("scan.sample_ids")]
    if sample not in vocab and not sample.startswith("LIO-F-"):
        raise Skip(f"sample {sample!r} is not a scan sample id ({vocab}, LIO-F-...): "
                   "add it to scan.sample_aliases")  # fmt: skip
    if ctx.sim is not None:
        ctx.sim.sample = "food" if sample.startswith("LIO-F-") else sample
    try:
        plan = scan.plan_for(cfg, mode, dev.stage, dev.stage_top_margin())
    except scan.PlanError as e:
        raise Skip(str(e)) from e
    # The dashboard passes its run Control so Pause / Realign reach this sweep.
    control = ctx.cache.get("scan_control")
    store, _ = scan.start(dev, cfg, plan, root, ctx.operator, sample_id=sample,
                               sim=ctx.sim is not None, control=control)  # fmt: skip
    a = analyse(store.folder, cfg)
    out = scan_report.write(store.folder, cfg)
    rec.artefact(str(out["html"]))
    fill(rec, a, store.folder)


def fill(rec: Recorder, a: Analysis, folder: Path) -> None:
    """Every finding as a sub-result (with its explanation), the run in ``measured``."""
    rec.measure(run=str(folder), mode=a.mode, status=a.status, verdict=a.verdict["verdict"],
                health={h["key"]: h["health"] for h in a.health})  # fmt: skip
    for f in a.findings:
        if f.status == Status.SKIP and f.id.startswith(CAPABILITY_IDS):
            continue  # capabilities not fitted: listed once in the scan report
        ex = a.explanations.get(f.id)
        msg = f.detail + (f" | why: {ex['cause']} | parts: {', '.join(ex['parts'])}" if ex else "")
        rec.add(sub_id(f.id), f.title, f.status, msg, f.criteria,
                **({"value": f.value, "unit": f.unit} if f.value is not None else {}))  # fmt: skip
    rec.note(f"{a.mode} scan {a.status}: {a.verdict['verdict']} ({Path(folder).name})")


def scan_result(a: Analysis, folder: Path) -> TestResult:
    """A finished scan as the T13.1 result (for the dashboard's twin)."""
    r = TestResult("T13.1", "Diagnostic height sweep", "T13", "M")
    rec = Recorder(r)
    fill(rec, a, folder)
    rec.artefact(str(Path(folder) / "report.html"))
    r.status = worst([x.status for x in r.subs])
    return r
