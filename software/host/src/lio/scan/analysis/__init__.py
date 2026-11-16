"""Scan analysis (plan §6): optics, electrical health (S3); ambient, mechanics,
system matrix and trend follow (S4).

    analyse(folder, cfg, reference=None) -> Analysis; written to <run>/analysis.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lio.config import HwConfig
from lio.results import Status
from lio.scan.analysis import electrical, optics
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
            "findings": [f.to_dict() for f in self.findings],
            "context": self.context,
        }

    def summary(self) -> str:
        lines = [f"{self.run_id}  sample {self.sample_id}  mode {self.mode}  {self.status}"]
        for f in self.findings:
            v = "" if f.value is None else f"{f.value:g} {f.unit}"
            lines.append(f"  {f.status.value:<5} {f.id:<34} {v:<18} {f.detail}")
        return "\n".join(lines)


def analyse(folder: Path, cfg: HwConfig, reference: Path | None = None) -> Analysis:
    cube = Cube.open(folder)
    ref = Cube.open(reference) if reference is not None else None
    a = Analysis(cube.store.run_id, cube.sample_id, cube.mode, str(cube.meta.get("status")))
    ectx, ef = electrical.analyse(cube, cfg)
    octx, of = optics.analyse(cube, cfg, ectx, ref)
    a.findings = of + ef
    a.context = {"electrical": ectx, "optics": octx,
                 "reference": None if ref is None else ref.store.run_id}  # fmt: skip
    if a.status != "COMPLETE":  # metrics needing the missing data are marked SKIP (§5.3)
        a.context["incomplete_note"] = "run INCOMPLETE: metrics computed from the steps completed"
    (Path(folder) / "analysis.json").write_text(
        json.dumps(a.to_dict(), indent=1, default=float) + "\n"
    )
    return a
