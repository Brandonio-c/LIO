"""Scan report, explanations and T13 in the catalogue (LIO-SW-SCAN-001 §5, §7; S5)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from lio import scan
from lio.config import HwConfig, parse_config
from lio.dashboard import twin
from lio.results import Status
from lio.scan import report as scan_report
from lio.scan.analysis import Finding, analyse
from lio.scan.explain import explain, explain_all
from lio.suite.core import REGISTRY, catalogue, run_test
from lio.suite.runner import sim_context

pytestmark = [pytest.mark.sim]


@pytest.fixture(scope="module")
def small(cfg: HwConfig) -> HwConfig:
    data = copy.deepcopy(cfg.data)
    data["sim"]["height"].update(travel_hs=40000, peak_hs=-30000, width_hs=9000,
                                 peak_shift_hs=250, ambient_leak_scale_hs=6000)  # fmt: skip
    data["thresholds"]["motion"]["travel"]["range_steps"] = 40000
    data["scan"].update(long_dark_s=4, hum_bursts=5, suite_mode="t")
    data["scan"]["modes"]["t"] = {"heights": 7, "up": "same", "return_top": True, "repeats": 1,
                                  "ref_heights": 0, "label": "test"}  # fmt: skip
    return parse_config(data, cfg.path)


def test_report_files(small: HwConfig, tmp_path: Path) -> None:
    store, status = scan.sim_run(small, "t", tmp_path, faults="pd_disconnected")
    assert status == "COMPLETE"
    out = scan_report.write(store.folder, small)
    for key in ("heatmap", "curves", "dark", "spectra"):
        assert out[key].exists() and out[key].stat().st_size > 5000, key
    html = out["html"].read_text()
    md = out["md"].read_text()
    assert "NOT FUNCTIONAL" in html and "plots/heatmap.png" in html
    assert "photodiode is not connected" in html  # the explanation, with parts
    assert "D1" in md and "Next check" in md
    assert "M6 x 1.0" in html  # the lead screw (scan.hardware)


def test_explanations_name_the_hole_parts() -> None:
    f = Finding("optics/opt101/h09/response", "x", Status.FAIL)
    e = explain(f, {f.id: f})
    assert e is not None and "LED9" in e.parts and "Q9" in e.parts and "lio ch 9" in e.check
    assert explain(Finding("optics/opt101/h09/response", "x", Status.PASS), {}) is None
    # context: a flat InGaAs hole is the disconnected photodiode when every hole is flat
    flat = Finding("optics/ingaas/electrical_only", "x", Status.FAIL)
    h13 = Finding("optics/ingaas/h13/response", "x", Status.FAIL)
    e = explain_all([flat, h13])["optics/ingaas/h13/response"]
    assert "D1" in e.parts


def test_every_finding_id_of_a_run_has_a_rule(small: HwConfig, tmp_path: Path) -> None:
    """Any finding that can be flagged has an explanation (forced to FAIL here)."""
    store, _ = scan.sim_run(small, "t", tmp_path)
    a = analyse(store.folder, small)
    forced = [Finding(f.id, f.title, Status.FAIL) for f in a.findings]
    got = explain_all(forced)
    missing = [f.id for f in forced if f.id not in got]
    assert not missing, missing


def test_t13_feeds_the_twin_and_verdict(small: HwConfig) -> None:
    catalogue()
    ctx = sim_context(small, "pd_disconnected,rail_miswired:12")
    try:
        r = run_test(ctx, REGISTRY["T13.1"])
    finally:
        ctx.dev.close()
    assert r.status == Status.FAIL and r.module == "T13" and r.artefacts
    ids = {s.id for s in r.subs}
    assert "T13.1/A/rail" in ids and "T13.1/optics/ingaas/h12/response" in ids
    p = twin.parts([r], small)
    assert p["holes"]["12"]["status"] == "FAIL"
    assert p["detectors"]["ingaas"]["status"] == "FAIL"
    assert p["rails"]["A"]["status"] == "PASS"
    tiles = {t["module"]: t for t in twin.subsystems([r], {"T13": ["T13.1"]})}
    assert tiles["T13"]["status"] == "FAIL"


def test_t13_skips_without_tracked_travel(small: HwConfig) -> None:
    catalogue()
    ctx = sim_context(small)
    ctx.sim = None  # as on the hardware: no simulator stage set-up
    try:
        r = run_test(ctx, REGISTRY["T13.1"])
    finally:
        ctx.dev.close()
    assert r.status == Status.SKIP and "travel" in r.message
