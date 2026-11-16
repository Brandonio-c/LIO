"""Scan analysis (plan §6): optics and electrical health, ambient light, mechanics,
the system matrix with the verdict, and trend against baselines.

    analyse(folder, cfg, reference=None, baselines_root=None) -> Analysis
    (written to <run>/analysis.json)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lio.config import HwConfig
from lio.results import Status
from lio.scan.analysis import ambient, electrical, mechanics, optics, system, trend
from lio.scan.analysis.data import Cube, Finding

__all__ = ["Analysis", "Cube", "Finding", "analyse"]


@dataclass
class Analysis:
    run_id: str
    sample_id: str
    mode: str
    status: str  # COMPLETE | INCOMPLETE
    findings: list[Finding] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    verdict: dict[str, Any] = field(default_factory=dict)
    health: list[dict[str, Any]] = field(default_factory=list)
    explanations: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get(self, fid: str) -> Finding:
        for f in self.findings:
            if f.id == fid:
                return f
        raise KeyError(fid)

    def flagged(self) -> list[Finding]:
        return [f for f in self.findings if f.status in (Status.WARN, Status.FAIL)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "sample_id": self.sample_id,
            "mode": self.mode,
            "status": self.status,
            "verdict": self.verdict,
            "health": self.health,
            "findings": [
                f.to_dict()
                | ({"explanation": self.explanations[f.id]} if f.id in self.explanations else {})
                for f in self.findings
            ],
            "context": self.context,
        }

    def summary(self) -> str:
        lines = [f"{self.run_id}  sample {self.sample_id}  mode {self.mode}  {self.status}"]
        if self.verdict:
            lines.append(
                f"VERDICT {self.verdict['verdict']}: " + "; ".join(self.verdict["reasons"])
            )
        for h in self.health:
            lines.append(f"  {h['health']:<5} {h['title']:<24} {h['reason'][:110]}")
        for f in self.findings:
            v = "" if f.value is None else f"{f.value:g} {f.unit}"
            lines.append(f"  {f.status.value:<5} {f.id:<34} {v:<18} {f.detail}")
            e = self.explanations.get(f.id)
            if e:
                lines.append(f"        why:   {e['cause']}")
                lines.append(f"        parts: {', '.join(e['parts'])}; next: {e['check']}")
        return "\n".join(lines)


def analyse(
    folder: Path, cfg: HwConfig, reference: Path | None = None, baselines_root: Path | None = None
) -> Analysis:
    cube = Cube.open(folder)
    ref = Cube.open(reference) if reference is not None else None
    a = Analysis(cube.store.run_id, cube.sample_id, cube.mode, str(cube.meta.get("status")))
    ectx, ef = electrical.analyse(cube, cfg)
    octx, of = optics.analyse(cube, cfg, ectx, ref)
    af = ambient.analyse(cube, cfg, ectx, octx)
    mf = mechanics.analyse(cube, cfg, octx)
    sf = system.findings(cube, cfg, octx)
    a.findings = sf + of + ef + af + mf
    a.context = {"electrical": ectx, "optics": octx,
                 "reference": None if ref is None else ref.store.run_id}  # fmt: skip
    if a.status != "COMPLETE":  # metrics needing the missing data are marked SKIP (§5.3)
        a.context["incomplete_note"] = "run INCOMPLETE: metrics computed from the steps completed"
    if baselines_root is not None:
        snap = trend.snapshot(a.to_dict())
        base = trend.load_baselines(baselines_root, a.sample_id)
        prior = [b for b in base if b["run_id"] != a.run_id]
        if prior:
            a.findings += trend.compare(prior[-1], snap, cfg)
        a.findings += trend.control(snap, base, cfg)
    from lio.scan.explain import explain_all

    a.explanations = {k: e.to_dict() for k, e in explain_all(a.findings).items()}
    a.health = system.health_table(a.findings)
    a.verdict = system.verdict(cfg, a.findings)
    (Path(folder) / "analysis.json").write_text(
        json.dumps(a.to_dict(), indent=1, default=float) + "\n"
    )
    return a
