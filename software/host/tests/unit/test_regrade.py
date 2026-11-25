"""Re-grading a saved run under the current thresholds (owner 2026-11-25)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from lio.config import HwConfig
from lio.regrade import latest_hardware_run, regrade_record
from lio.results import RunRecord, Status, SubResult, TestResult

pytestmark = pytest.mark.unit


def _rec(cfg: HwConfig) -> RunRecord:
    a0 = cfg.detectors["ingaas"].adc_channel
    a1 = cfg.detectors["opt101"].adc_channel
    t03 = TestResult("T03.2", "Dark ADC noise", "T03", "A", Status.FAIL, subs=[
        SubResult(f"T03.2/a{a0}", "ingaas", Status.FAIL, "", "sigma <= 20 counts",
                  {"mean": -328.1, "sigma": 24.75}),
        SubResult(f"T03.2/a{a1}", "opt101", Status.PASS, "", "sigma <= 20 counts",
                  {"mean": 58.1, "sigma": 0.35}),
    ])  # fmt: skip
    t052 = TestResult("T05.2", "Per-channel response", "T05", "A", Status.FAIL, subs=[
        SubResult("T05.2/h12/ingaas", "h12", Status.FAIL, "net +8 (none)", "",
                  {"net": 8, "expect": "signal"}),
        SubResult("T05.2/h03/opt101", "h3", Status.PASS, "net +43", "", {"net": 43}),
    ])  # fmt: skip
    t055 = TestResult("T05.5", "Repeatability", "T05", "A", Status.FAIL, subs=[
        SubResult("T05.5/h07/opt101", "h7", Status.FAIL, "SD 38", "SD <= 5 counts", {}),
    ])  # fmt: skip
    return RunRecord(
        run_id="20261125-125629_host", target="/dev/cu.usbmodem101", started="2026-11-25T12:56:29",
        results=[t03, t052, t055],
    )  # fmt: skip


def test_regrade_uses_current_thresholds_and_keeps_the_original(cfg: HwConfig) -> None:
    src = _rec(cfg)
    before = copy.deepcopy(src.to_dict())
    rec, changes = regrade_record(src, cfg)
    assert src.to_dict() == before  # the saved run is never modified
    subs = {s.id: s for r in rec.results for s in r.subs}
    a0 = cfg.detectors["ingaas"].adc_channel
    assert subs[f"T03.2/a{a0}"].status == Status.WARN  # 24.75 <= ingaas fail level 50
    h12 = subs["T05.2/h12/ingaas"]
    assert h12.status == Status.WARN and "not resolved" in h12.message
    assert "re-graded" in h12.message and "was FAIL" in h12.message
    assert subs["T05.2/h03/opt101"].status == Status.PASS  # untouched
    assert subs["T05.5/h07/opt101"].status == Status.WARN
    assert rec.verdict["verdict"] == "FUNCTIONAL"
    assert rec.metadata["regraded_from"] == "20261125-125629_host"
    assert rec.run_id.endswith("_regrade_of_20261125-125629_host")
    assert changes == {"T03.2": 1, "T05.2": 1, "T05.5": 1}


def test_a_dead_visible_channel_still_fails(cfg: HwConfig) -> None:
    src = _rec(cfg)
    src.results[1].subs[1] = SubResult("T05.2/h03/opt101", "h3", Status.PASS, "", "",
                                       {"net": 0})  # fmt: skip
    rec, _ = regrade_record(src, cfg)
    sub = next(s for r in rec.results for s in r.subs if s.id == "T05.2/h03/opt101")
    assert sub.status == Status.FAIL  # the OPT101 resolves it: absence is a real failure


def test_latest_hardware_run_skips_regrades(tmp_path: Path) -> None:
    for name in ("20261125-125629_host", "20261125-140418_regrade_of_20261125-125629_host"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "results.json").write_text("{}")
    found = latest_hardware_run(tmp_path)
    assert found is not None and found.name == "20261125-125629_host"
