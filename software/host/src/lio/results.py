"""Test results and the run record (plan §5.3).

A :class:`TestResult` holds one catalogue entry (for example ``T05.2``) with
its sub-results (one per channel, detector or step). The test's status is the
worst of its sub-results. A :class:`RunRecord` is one suite run: environment,
firmware identity, metadata, every result, the duty-cycle log and the overall
verdict. It serialises to ``results.json``.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Status(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"  # the test could not complete (exception, device error)

    @property
    def rank(self) -> int:
        return _RANK[self]


_RANK = {Status.SKIP: 0, Status.PASS: 1, Status.WARN: 2, Status.FAIL: 3, Status.ERROR: 4}


def worst(statuses: list[Status]) -> Status:
    """The most severe status; SKIP only if everything was skipped (or nothing ran)."""
    return max(statuses, key=lambda s: s.rank, default=Status.SKIP)


@dataclass
class SubResult:
    id: str  # e.g. "T05.2/h08/ingaas"
    name: str
    status: Status
    message: str = ""
    criteria: str = ""
    measured: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    __test__ = False  # not a pytest test class

    id: str  # catalogue id, e.g. "T05.2"
    name: str
    module: str  # "T05"
    kind: str  # A | I | M
    status: Status = Status.SKIP
    message: str = ""
    duration_s: float = 0.0
    subs: list[SubResult] = field(default_factory=list)
    measured: dict[str, Any] = field(default_factory=dict)
    artefacts: list[str] = field(default_factory=list)

    def sub(self, sub_id: str) -> SubResult:
        for s in self.subs:
            if s.id == sub_id:
                return s
        raise KeyError(f"{self.id} has no sub-result {sub_id!r}")

    def subs_with(self, status: Status) -> list[SubResult]:
        return [s for s in self.subs if s.status == status]

    def summary(self) -> str:
        bad = [s for s in self.subs if s.status in (Status.FAIL, Status.ERROR, Status.WARN)]
        lines = [
            f"{self.id} {self.name}: {self.status.value}"
            + (f" ({self.message})" * bool(self.message))
        ]
        lines += [f"  {s.status.value:5} {s.id}: {s.message}" for s in bad]
        return "\n".join(lines)


# --------------------------------------------------------------------- verdict


class Verdict(str, Enum):
    FUNCTIONAL = "FUNCTIONAL"
    DEGRADED = "DEGRADED"
    NOT_FUNCTIONAL = "NOT FUNCTIONAL"


CRITICAL_MODULES = ("T02", "T03", "T04", "T10")


def hole_of(sub_id: str) -> int | None:
    """Hole number encoded in a sub-result id as ``/hNN``, if any."""
    for part in sub_id.split("/"):
        if len(part) == 3 and part[0] == "h" and part[1:].isdigit():
            return int(part[1:])
    return None


@dataclass(frozen=True)
class OverallVerdict:
    verdict: Verdict
    reasons: list[str]


def overall_verdict(
    results: list[TestResult], *, max_channel_fails: int, limited_holes: tuple[int, ...]
) -> OverallVerdict:
    """T11 verdict (plan §6 T11).

    - NOT FUNCTIONAL: any FAIL/ERROR in T02, T03, T04 or T10; any FAIL that is
      not tied to a channel (e.g. InGaAs polarity); or more than
      ``max_channel_fails`` failing channels outside ``limited_holes``.
    - DEGRADED: only WARNs, failures on the expected-limited channels, or at
      most ``max_channel_fails`` other failing channels (interpretation of the
      plan, which leaves 1-2 channel FAILs unclassified).
    - FUNCTIONAL: no FAILs and no WARNs.
    """
    reasons: list[str] = []
    failing = [r for r in results if r.status.rank >= Status.FAIL.rank]
    critical = [r.id for r in failing if r.module in CRITICAL_MODULES]
    holes: set[int] = set()
    unattributed: list[str] = []
    for r in failing:
        if r.module in CRITICAL_MODULES:
            continue
        bad = [hole_of(s.id) for s in r.subs if s.status.rank >= Status.FAIL.rank]
        if bad and all(h is not None for h in bad):
            holes |= {h for h in bad if h is not None}
        else:
            unattributed.append(r.id)
    real = sorted(h for h in holes if h not in limited_holes)
    limited = sorted(h for h in holes if h in limited_holes)
    warns = [r.id for r in results if r.status == Status.WARN]
    if critical:
        reasons.append(f"failure in a critical module: {', '.join(critical)}")
    if unattributed:
        reasons.append(f"failures not tied to a channel: {', '.join(unattributed)}")
    if len(real) > max_channel_fails:
        reasons.append(
            f"{len(real)} failing channels (more than {max_channel_fails}): "
            + ", ".join(map(str, real))
        )
    if reasons:
        return OverallVerdict(Verdict.NOT_FUNCTIONAL, reasons)
    if real:
        reasons.append(f"failing channels: {', '.join(map(str, real))}")
    if limited:
        reasons.append(f"failures on expected-limited channels: {', '.join(map(str, limited))}")
    if warns:
        reasons.append(f"warnings: {', '.join(warns)}")
    if reasons:
        return OverallVerdict(Verdict.DEGRADED, reasons)
    return OverallVerdict(Verdict.FUNCTIONAL, ["no failures or warnings"])


# ------------------------------------------------------------------ run record


@dataclass
class RunRecord:
    run_id: str
    target: str  # "sim" or the serial port
    started: str  # ISO 8601
    environment: dict[str, Any] = field(default_factory=dict)
    firmware: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    faults: list[str] = field(default_factory=list)
    results: list[TestResult] = field(default_factory=list)
    duty: dict[str, Any] = field(default_factory=dict)
    finished: str = ""
    verdict: dict[str, Any] = field(default_factory=dict)

    def result(self, test_id: str) -> TestResult:
        for r in self.results:
            if r.id == test_id:
                return r
        raise KeyError(test_id)

    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in Status}
        for r in self.results:
            out[r.status.value] += 1
        return out

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = _jsonable(asdict(self))
        return out

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=False) + "\n")
        return path


def _jsonable(x: Any) -> Any:
    if isinstance(x, Enum):
        return x.value
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_jsonable(v) for v in x]
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x
