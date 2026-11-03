"""The dashboard's digital twin: a status for every part of the instrument.

Pure functions from test results to what the dashboard draws, so the mapping
is testable without a browser. A part's status is the worst status of the
sub-results that concern it:

- **holes 1-16**: every sub-result whose id names the hole (``.../h08/...``)
- **rails A, B**: sub-results whose id starts with the rail (``T05.1/A/...``)
- **detectors**: T06.1 (OPT101) and T06.2 (InGaAs), plus any sub-result not
  tied to a hole whose id names the detector (``T03.5/ingaas``) or its ADC
  input (``T03.2/a0``)

Per-hole checks that judge a shared part through the LEDs (the walk test
T04.4 for the shift registers, T06.1/T06.2 for the detectors) are shown as
evidence on the part but count against it only when they fail on more than
``verdict.max_channel_fails`` holes, the same rule as the overall verdict: a
dark LED or two is the LEDs' fault, many dark holes point at the shared part.
- **motors 1, 2**: T09.2 sub-results starting with the motor number
- everything else by catalogue module (T02 link, T03 ADC, T04 shift
  registers, T10 safety)

``NOT_RUN`` means no test has looked at the part yet.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from lio.config import HwConfig
from lio.results import Status, TestResult, hole_of, overall_verdict, worst

NOT_RUN = "NOT_RUN"
DETECTORS = ("opt101", "ingaas")


@dataclass(frozen=True)
class Subsystem:
    key: str  # also accepted by ``lio selftest --modules``
    module: str  # catalogue module, e.g. "T05"
    name: str
    what: str  # one line: what the tests check


SUBSYSTEMS: tuple[Subsystem, ...] = (
    Subsystem("env", "T01", "Host environment", "Python, libraries, port discovery, config"),
    Subsystem("link", "T02", "USB link and firmware", "banner, latency, INFO limits, bad input"),
    Subsystem("adc", "T03", "ADC (ADS1115, I²C)", "I²C scan, dark noise, gains, rates, drift"),
    Subsystem("sr", "T04", "Shift registers", "74HC595 patterns, walk test"),
    Subsystem("channels", "T05", "LED channels", "rail gating, response, isolation, current"),
    Subsystem("detectors", "T06", "Detectors", "OPT101, InGaAs polarity, ambient light"),
    Subsystem("timing", "T07", "Settling timing", "step response, settle time, MEAS timing"),
    Subsystem("sweep", "T08", "Sweep", "16-hole sweep, repeatability, CSV"),
    Subsystem("motors", "T09", "Motors", "arming, both directions, stop, EMI"),
    Subsystem("safety", "T10", "Safety interlocks", "power-up, watchdogs, failsafe, one channel"),
    Subsystem("baseline", "T11", "Baseline comparison", "drift against a saved healthy run"),
)

# Parts judged by whole catalogue modules.
MODULE_PARTS = {"nano": ("T02",), "adc": ("T03",), "sr": ("T04",), "safety": ("T10",)}
# Tests that judge a shared part through individual LEDs (see the module docstring).
VIA_LEDS = ("T04.4", "T06.1", "T06.2")


def _status(statuses: Iterable[Status]) -> str:
    s = list(statuses)
    return worst(s).value if s else NOT_RUN


def _item(r: TestResult, sub_id: str, status: Status, message: str) -> dict[str, Any]:
    return {
        "test": r.id,
        "test_name": r.name,
        "id": sub_id,
        "status": status.value,
        "message": message,
    }


class _Part:
    def __init__(self) -> None:
        self.statuses: list[Status] = []
        self.items: list[dict[str, Any]] = []

    def add(
        self, r: TestResult, sub_id: str, status: Status, message: str, *, counts: bool = True
    ) -> None:
        if counts:
            self.statuses.append(status)
        self.items.append(_item(r, sub_id, status, message))

    def add_test(self, r: TestResult, max_channel_fails: int | None = None) -> None:
        """The whole test, or its sub-results if it has any.

        With ``max_channel_fails``, per-hole sub-results count only if more
        than that many holes fail (a test in ``VIA_LEDS``).
        """
        if not r.subs:
            self.add(r, r.id, r.status, r.message)
            return
        systemic = True
        if max_channel_fails is not None:
            systemic = len(failing_holes([r])) > max_channel_fails
        for s in r.subs:
            on_hole = hole_of(s.id) is not None
            self.add(r, s.id, s.status, s.message, counts=systemic or not on_hole)

    def out(self) -> dict[str, Any]:
        bad = sorted(self.items, key=lambda i: -Status(i["status"]).rank)
        return {"status": _status(self.statuses), "items": bad}


def failing_holes(results: Iterable[TestResult]) -> list[int]:
    """Holes named by FAIL/ERROR sub-results."""
    holes = {
        h
        for r in results
        for s in r.subs
        if s.status.rank >= Status.FAIL.rank and (h := hole_of(s.id)) is not None
    }
    return sorted(holes)


def _detector_of(parts: list[str], cfg: HwConfig) -> str | None:
    for p in parts:
        if p in DETECTORS:
            return p
        if len(p) == 2 and p[0] == "a" and p[1].isdigit():
            return cfg.detector_for_adc(int(p[1]))
    return None


def parts(results: Iterable[TestResult], cfg: HwConfig) -> dict[str, Any]:
    """Status and evidence for every drawn part: holes, rails, detectors, motors, boards."""
    holes = {h: _Part() for h in range(1, 17)}
    rails = {r: _Part() for r in ("A", "B")}
    dets = {d: _Part() for d in DETECTORS}
    motors = {m: _Part() for m in ("1", "2")}
    boards = {k: _Part() for k in MODULE_PARTS}
    nets: dict[int, dict[str, int]] = {}
    max_fails = cfg.thresholds.integer("verdict.max_channel_fails")
    for r in results:
        tolerance = max_fails if r.id in VIA_LEDS else None
        for key, modules in MODULE_PARTS.items():
            if r.module in modules:
                boards[key].add_test(r, tolerance)
        if r.id == "T06.1":
            dets["opt101"].add_test(r, tolerance)
        elif r.id == "T06.2":
            dets["ingaas"].add_test(r, tolerance)
        for s in r.subs:
            path = s.id.split("/")[1:]
            hole = hole_of(s.id)
            if hole is not None:
                holes[hole].add(r, s.id, s.status, s.message)
                if r.id == "T05.2" and path[-1] in DETECTORS and "net" in s.measured:
                    nets.setdefault(hole, {})[path[-1]] = int(s.measured["net"])
            if path and path[0] in rails:
                rails[path[0]].add(r, s.id, s.status, s.message)
            if r.module == "T09" and path and path[0] in motors:
                motors[path[0]].add(r, s.id, s.status, s.message)
            if hole is None and r.id not in ("T06.1", "T06.2"):
                det = _detector_of(path, cfg)
                if det is not None:
                    dets[det].add(r, s.id, s.status, s.message)
    hole_out = {}
    for h, part in holes.items():
        ch = cfg.channel(h)
        hole_out[str(h)] = {
            **part.out(),
            "hole": h,
            "label": ch.label,
            "wavelength_nm": ch.wavelength_nm,
            "rail": ch.rail,
            "fitted": ch.fitted,
            "expect": {d: ch.expect_for(d) for d in DETECTORS},
            "net": nets.get(h, {}),
            "register": f"U{1 + (h - 1) // 8} Q{(h - 1) % 8}",
        }
    return {
        "holes": hole_out,
        "rails": {k: v.out() for k, v in rails.items()},
        "detectors": {k: v.out() for k, v in dets.items()},
        "motors": {k: v.out() for k, v in motors.items()},
        **{k: v.out() for k, v in boards.items()},
    }


def subsystems(
    results: Iterable[TestResult], planned: dict[str, list[str]]
) -> list[dict[str, Any]]:
    """One tile per catalogue module: status, counts and each test's outcome.

    ``planned`` maps a module to the ids of all its catalogue tests, so a tile
    can say how much of it has been run.
    """
    by_module: dict[str, list[TestResult]] = {}
    for r in results:
        by_module.setdefault(r.module, []).append(r)
    out = []
    for s in SUBSYSTEMS:
        rs = by_module.get(s.module, [])
        done = {r.id: r for r in rs}
        tests = [
            {
                "id": tid,
                "status": done[tid].status.value if tid in done else NOT_RUN,
                "name": done[tid].name if tid in done else "",
                "message": done[tid].message if tid in done else "",
                "duration_s": round(done[tid].duration_s, 1) if tid in done else None,
                "bad": [
                    {"id": x.id, "status": x.status.value, "message": x.message}
                    for x in done[tid].subs
                    if x.status.rank >= Status.WARN.rank
                ]
                if tid in done
                else [],
            }
            for tid in planned.get(s.module, [])
        ]
        counts = {st.value: sum(1 for r in rs if r.status == st) for st in Status}
        bad = [r for r in rs if r.status.rank >= Status.FAIL.rank]
        unattributed = [
            r.id
            for r in bad
            if any(x.status.rank >= Status.FAIL.rank and hole_of(x.id) is None for x in r.subs)
            or not r.subs
        ]
        out.append(
            {
                "key": s.key,
                "module": s.module,
                "name": s.name,
                "what": s.what,
                "status": _status(r.status for r in rs),
                "run": len(rs),
                "total": len(tests),
                "counts": counts,
                # failures that are all on named holes point at those LEDs/channels
                "fail_holes": failing_holes(bad),
                "fail_only_holes": bool(bad) and not unattributed,
                "tests": tests,
            }
        )
    return out


def overall(results: list[TestResult], cfg: HwConfig, total_tests: int) -> dict[str, Any]:
    """The T11 verdict over the results so far, and how complete it is."""
    if not results:
        return {"verdict": NOT_RUN, "reasons": ["no tests run yet"], "run": 0, "total": total_tests}
    th = cfg.thresholds
    v = overall_verdict(
        results,
        max_channel_fails=th.integer("verdict.max_channel_fails"),
        limited_holes=th.ints("verdict.limited_holes"),
    )
    judged = [r for r in results if r.status != Status.SKIP]
    return {
        "verdict": v.verdict.value,
        "reasons": v.reasons,
        "run": len(results),
        "judged": len(judged),
        "total": total_tests,
        "complete": len(results) >= total_tests,
    }
