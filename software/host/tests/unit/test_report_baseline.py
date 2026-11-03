"""Reports, CSV and baselines, built from simulator runs."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lio import baseline
from lio.config import HwConfig
from lio.csvout import sweep_csv_text
from lio.report import rebuild, write_run
from lio.results import RunRecord, Status
from lio.suite.runner import everything, new_record, run_catalogue, sim_context

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def healthy(cfg: HwConfig) -> tuple[RunRecord, list[tuple[str, object]]]:
    ctx = sim_context(cfg)
    try:
        record = run_catalogue(ctx, new_record(ctx, {"sample_id": "s1"}), everything)
    finally:
        ctx.dev.close()
    return record, list(ctx.meas_log)


def test_report_files_and_rebuild(
    healthy: tuple[RunRecord, list], cfg: HwConfig, tmp_path: Path
) -> None:
    record, log = healthy
    out = write_run(record, tmp_path, cfg=cfg, meas_log=log)
    assert {p.name for p in (tmp_path / "plots").iterdir()} == {
        "channels.png",
        "crosstalk.png",
        "noise.png",
        "settling.png",
        "sweeps.png",
    }
    html = out["html"].read_text()
    assert "FUNCTIONAL" in html and "T05.2" in html and "plots/channels.png" in html
    md = out["md"].read_text()
    assert md.startswith("# LIO test report") and "| T10.3 |" in md
    assert out["csv"].read_text().startswith("test,hole,label")
    again = rebuild(out["json"], cfg)
    assert again["html"].read_text().count("<h3") == html.count("<h3")
    loaded = RunRecord.load(out["json"])
    assert loaded.result("T05.2").status == Status.PASS
    assert loaded.verdict == record.verdict


def test_report_without_plot_data(tmp_path: Path) -> None:
    rec = RunRecord(
        "r", "sim", "now", verdict={"verdict": "FUNCTIONAL", "reasons": [], "counts": {}}
    )
    out = write_run(rec, tmp_path)
    assert out["html"].exists() and not list((tmp_path / "plots").iterdir())


def test_baseline_roundtrip(healthy: tuple[RunRecord, list], tmp_path: Path) -> None:
    record, _ = healthy
    path = baseline.save(record, tmp_path / "baseline_x.yaml")
    data = baseline.load(path)
    assert data["sample_id"] == "s1" and data["channels"][8]["opt101"] > 1000
    assert set(data["dark"]) >= {"a0", "a1"} and 8 in data["ingaas_over_opt101"]
    assert baseline.latest(tmp_path) == path
    assert baseline.default_path(tmp_path).name.startswith("baseline_")


def test_baseline_default_path_does_not_overwrite(tmp_path: Path) -> None:
    import datetime as dt

    day = dt.date(2026, 11, 3)
    first = baseline.default_path(tmp_path, day)
    first.write_text("x")
    assert baseline.default_path(tmp_path, day).name == "baseline_20261103_2.yaml"
    assert baseline.latest(tmp_path / "none") is None


def test_baseline_rejects_other_files(tmp_path: Path) -> None:
    p = tmp_path / "x.yaml"
    p.write_text(yaml.safe_dump({"schema": 99}))
    with pytest.raises(ValueError, match="not an LIO baseline"):
        baseline.load(p)
    with pytest.raises(ValueError, match="no channel matrix"):
        baseline.build(RunRecord("r", "sim", "now"))


def test_t11_compares_against_baseline(
    healthy: tuple[RunRecord, list], cfg: HwConfig, tmp_path: Path
) -> None:
    from lio.suite.core import REGISTRY, catalogue, run_test

    record, _ = healthy
    data = baseline.load(baseline.save(record, tmp_path / "b.yaml"))
    catalogue()
    for faults, status in ((None, Status.PASS), ("tia_saturated", Status.FAIL)):
        ctx = sim_context(cfg, faults)
        ctx.baseline = data
        ctx.cache["sample_id"] = "s1"
        try:
            r = run_test(ctx, REGISTRY["T11.1"])
        finally:
            ctx.dev.close()
        assert r.status == status, r.summary()


def test_sweep_csv_matches_legacy_arithmetic(cfg: HwConfig) -> None:
    from lio.device import Meas

    text = sweep_csv_text([Meas(1, 40, 200, 48, 1119, 24)], cfg)
    # the original logger: round((ig - di) * 4.096 / 32768, 5) at GAIN_ONE
    assert text == (
        "hole,label,dark_ingaas,dark_opt101,ingaas,opt101,net_ingaas_V,net_opt101_V\r\n"
        f"1,395,40,200,48,1119,{round(8 * 4.096 / 32768, 5)},{round(919 * 4.096 / 32768, 5)}\r\n"
    )
