from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from lio.results import (
    RunRecord,
    Status,
    SubResult,
    TestResult,
    Verdict,
    hole_of,
    overall_verdict,
    worst,
)

pytestmark = pytest.mark.unit


def _r(test_id: str, *subs: tuple[str, Status]) -> TestResult:
    r = TestResult(test_id, "x", test_id.split(".")[0], "A")
    r.subs = [SubResult(f"{test_id}/{sid}", sid, st) for sid, st in subs]
    r.status = worst([s.status for s in r.subs])
    return r


def _verdict(*results: TestResult) -> tuple[Verdict, list[str]]:
    v = overall_verdict(list(results), max_channel_fails=2, limited_holes=(10, 11, 15, 16))
    return v.verdict, v.reasons


class TestStatus:
    def test_worst(self) -> None:
        assert worst([Status.PASS, Status.WARN]) == Status.WARN
        assert worst([Status.SKIP, Status.PASS]) == Status.PASS
        assert worst([Status.FAIL, Status.ERROR, Status.WARN]) == Status.ERROR
        assert worst([]) == Status.SKIP

    def test_hole_of(self) -> None:
        assert hole_of("T05.2/h08/ingaas") == 8
        assert hole_of("T05.3/B/stuck_via_10") is None
        assert hole_of("T03.2/a1") is None

    def test_result_helpers(self) -> None:
        r = _r("T05.2", ("h01/opt101", Status.PASS), ("h02/opt101", Status.FAIL))
        assert r.sub("T05.2/h02/opt101").status == Status.FAIL
        assert [s.id for s in r.subs_with(Status.FAIL)] == ["T05.2/h02/opt101"]
        assert "FAIL" in r.summary() and "h02" in r.summary()
        with pytest.raises(KeyError):
            r.sub("nope")


class TestVerdict:
    def test_functional(self) -> None:
        assert _verdict(_r("T02.2", ("p99", Status.PASS)))[0] == Verdict.FUNCTIONAL

    def test_critical_module(self) -> None:
        v, reasons = _verdict(_r("T10.2", ("A/h03/off", Status.FAIL)))
        assert v == Verdict.NOT_FUNCTIONAL and "T10.2" in reasons[0]

    def test_error_counts_as_failure(self) -> None:
        r = TestResult("T03.1", "x", "T03", "A", status=Status.ERROR)
        assert _verdict(r)[0] == Verdict.NOT_FUNCTIONAL

    def test_unattributed_failure(self) -> None:
        v, reasons = _verdict(_r("T06.2", ("polarity/gate", Status.FAIL)))
        assert v == Verdict.NOT_FUNCTIONAL and "not tied to a channel" in reasons[0]

    def test_few_channel_fails_degraded(self) -> None:
        v, reasons = _verdict(_r("T05.2", ("h03/opt101", Status.FAIL), ("h08/ingaas", Status.FAIL)))
        assert v == Verdict.DEGRADED and "3, 8" in reasons[0]

    def test_many_channel_fails(self) -> None:
        r = _r("T05.2", *((f"h0{h}/opt101", Status.FAIL) for h in (1, 2, 3)))
        assert _verdict(r)[0] == Verdict.NOT_FUNCTIONAL

    def test_limited_channels_do_not_count(self) -> None:
        r = _r("T05.2", *((f"h{h}/ingaas", Status.FAIL) for h in (10, 11, 15, 16)))
        v, reasons = _verdict(r)
        assert v == Verdict.DEGRADED and "expected-limited" in reasons[0]

    def test_warnings_degraded(self) -> None:
        assert _verdict(_r("T07.2", ("settle", Status.WARN)))[0] == Verdict.DEGRADED


class TestRunRecord:
    def test_json_roundtrip(self, tmp_path: Path) -> None:
        rec = RunRecord("20261103-120000_sim", "sim", "2026-11-03T12:00:00")
        r = _r("T07.1", ("h03", Status.PASS))
        r.subs[0].measured = {"tau_ms": None, "bad": math.inf, "pair": (1, 2)}
        rec.results.append(r)
        path = rec.write_json(tmp_path / "x" / "results.json")
        d = json.loads(path.read_text())
        assert d["results"][0]["status"] == "PASS"
        assert d["results"][0]["subs"][0]["measured"] == {
            "tau_ms": None,
            "bad": None,
            "pair": [1, 2],
        }
        assert rec.counts()["PASS"] == 1
        assert rec.result("T07.1") is r
        with pytest.raises(KeyError):
            rec.result("T99.9")
