"""S5: connected paired / shared-control / familywise inference through the real
saved-record path: run_protocol -> ScanStore -> `lio scan analyse` (CLI) ->
analysis.json -> `lio scan report` -> dashboard summary. Labelled synthetic
fixtures only; numerical truth is software truth, not rig calibration.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
from pathlib import Path
from typing import Any

import pytest

from lio.cli import main as cli_main
from lio.config import HwConfig, load_config
from lio.scan.acquisition import plan_protocol, run_protocol
from lio.scan.derived import summarize_derived
from lio.scan.store import ScanStore

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
CFG = REPO / "software" / "config" / "lio_hw.yaml"

# Per-block nets (blocks 0, 1, 2) for the unblocked condition "u" and the
# optical-block condition "b" (settle 8 vs 9 ms identifies the condition).
NETS = {
    ("u", 12): [10, 12, 14], ("u", 13): [3, 6, 3], ("u", 5): [1, 2, 3],
    ("b", 12): [4, 5, 9], ("b", 13): [3, 6, 3], ("b", 5): [1, 2, 3],
}  # fmt: skip


@pytest.fixture()
def cfg() -> HwConfig:
    return load_config(CFG)


def _protocol() -> dict[str, Any]:
    p = json.loads((REPO / "software/host/src/lio/scan/examples/stationary_targeted_h12.json")
                   .read_text())  # fmt: skip
    p.update(
        id="s5_fixture", holes=[5, 12, 13], detectors=["ingaas"], operator_checkpoints=[],
        conditions=[
            {"id": "u", "label": "unblocked", "settle_ms": 8, "mains_periods": 2,
             "optical_block": False},
            {"id": "b", "label": "blocked", "settle_ms": 9, "mains_periods": 2,
             "optical_block": False},
        ],
        blocks={"n_production": 3, "n_pilot": 0, "n_production_min": 1, "n_production_max": 8},
        allocation={"policy": "equal_fixed", "control_holes": [5],
                    "target_weights": {"5": 1.0, "12": 1.0, "13": 1.0}},
    )  # fmt: skip
    return p


def _run(cfg: HwConfig, tmp: Path) -> Path:
    plan = plan_protocol(_protocol(), cfg)
    seen: dict[tuple[str, int], int] = {}

    def meas(hole: int, settle: int, n: int) -> dict[str, Any]:
        cond = "u" if settle == 8 else "b"
        i = seen.get((cond, hole), 0)
        seen[(cond, hole)] = i + 1
        net = float(NETS[(cond, hole)][i])
        return {"hole": hole, "t_on_ms": 5.0, "dark_ingaas": 0.0, "lit_ingaas": net,
                "net_ingaas": net}  # fmt: skip

    res = run_protocol(plan, cfg=cfg, root=tmp, sample_id="empty", allow_light=True,
                       meas=meas, simulated=True)  # fmt: skip
    assert res.status == "COMPLETE"
    return res.folder


def _evidence(tmp: Path, run: Path) -> Path:
    f = tmp / "evidence.json"
    f.write_text(json.dumps([{
        "hole": 5, "detector": "ingaas", "source_run_id": ScanStore.open(run).run_id,
        "load_id": "fixture-load", "condition_id": "u", "setting_id": "settle8:n2",
        "calibration_id": "gain:1", "assembly_epoch": "fixture-epoch",
        "method": "unchanged_load_optical_block",
    }]))  # fmt: skip
    return f


def _analyse(run: Path, derived: Path, evidence: Path | None) -> dict[str, Any]:
    args = ["scan", "analyse", str(run), "--model", "qualified-v2", "--derived-out", str(derived)]
    if evidence is not None:
        args += ["--control-evidence", str(evidence)]
    assert cli_main(args) == 0
    path = next(derived.rglob("analysis.json"))
    return json.loads(path.read_text())


def test_paired_control_contrast_truth_through_cli(cfg: HwConfig, tmp_path: Path) -> None:
    run = _run(cfg, tmp_path / "runs")
    meta = ScanStore.open(run).meta
    fam = meta["inference_family"]
    assert (
        fam["frozen"] and fam["size"] == 7
    )  # 3 holes x (b-u) + 2 targets x 2 conditions x minus-control
    a = _analyse(run, tmp_path / "derived", _evidence(tmp_path, run))
    c = a["contrasts"]
    e12 = c["estimates"]["ingaas:h12:u:minus-control"]
    assert e12["extras"]["diffs"] == [9.0, 10.0, 11.0]
    assert e12["value"] == pytest.approx(10.0)
    assert e12["extras"]["var_of_mean"] == pytest.approx(1 / 3)  # not 5/3
    assert e12["n_blocks"] == 3
    # Shared control -> nonzero covariance between the two control-corrected means.
    cov = c["covariance_of_means"]["ingaas:h12:u:minus-control|ingaas:h13:u:minus-control"]
    assert cov == pytest.approx(-1 / 3)
    # Paired optical-block contrast b - u on hole 12: [-6, -7, -5].
    cb = c["estimates"]["ingaas:h12:b-minus-u"]
    assert cb["value"] == pytest.approx(-6.0) and cb["extras"]["var_of_mean"] == pytest.approx(
        1 / 3
    )
    # Familywise: Bonferroni over the frozen family of 5.
    assert e12["interval"]["method"] in ("bonferroni-t", "t")
    if e12["interval"]["available"]:
        assert e12["interval"]["level"] == pytest.approx(1 - 0.05 / 7)
    assert a["verdict"]["verdict"] == "NUMERICAL_RESULTS"
    assert "not established" in a["verdict"]["physical_qualification"]
    # Report and dashboard consumers carry the same numbers.
    aid = a["analysis_id"]
    assert cli_main(["scan", "report", str(run), "--analysis", aid,
                     "--derived-out", str(tmp_path / "derived")]) == 0  # fmt: skip
    rep = next((tmp_path / "derived").rglob("report.md")).read_text()
    assert "ingaas:h12:u:minus-control | +10" in rep
    rows = summarize_derived(a)["signed_summary"]["contrasts"]
    assert {r["contrast"] for r in rows} == set(fam["members"])


def test_without_evidence_control_stays_null(cfg: HwConfig, tmp_path: Path) -> None:
    run = _run(cfg, tmp_path / "runs")
    a = _analyse(run, tmp_path / "derived", None)
    c = a["contrasts"]
    assert "ingaas:h12:u:minus-control" not in c["estimates"]
    assert "C stays null" in c["unavailable"]["ingaas:h12:u:minus-control"]
    # Paired condition contrasts need no control and stay available.
    assert c["estimates"]["ingaas:h12:b-minus-u"]["value"] == pytest.approx(-6.0)
    assert c["family"]["size"] == 7  # the family does not shrink


def _drop_row(run: Path, hole: int, cond: str) -> None:
    with gzip.open(run / "cube.csv.gz", "rt", newline="") as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0])
    kept, dropped = [], False
    for r in rows:
        if not dropped and r["hole"] == str(hole) and r["condition_id"] == cond:
            dropped = True
            continue
        kept.append(r)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(kept)
    with gzip.open(run / "cube.csv.gz", "wt", newline="") as f:
        f.write(buf.getvalue())


def test_missing_pair_member_refuses_dependent_inference(cfg: HwConfig, tmp_path: Path) -> None:
    run = _run(cfg, tmp_path / "runs")
    _drop_row(run, 5, "u")  # one control reading lost
    a = _analyse(run, tmp_path / "derived", _evidence(tmp_path, run))
    c = a["contrasts"]
    assert "unmatched" in c["unavailable"]["ingaas:h12:u:minus-control"]
    assert c["family"]["size"] == 7
    # Raw rows remain inspectable through the saved reader.
    assert len(list(ScanStore.open(run).rows())) == 17


def test_evidence_from_another_run_or_h8_monitor_is_not_a_control(
    cfg: HwConfig, tmp_path: Path
) -> None:
    run = _run(cfg, tmp_path / "runs")
    f = _evidence(tmp_path, run)
    ev = json.loads(f.read_text())
    ev[0]["source_run_id"] = "another-run"
    f.write_text(json.dumps(ev))
    a = _analyse(run, tmp_path / "derived", f)
    assert "C stays null" in a["contrasts"]["unavailable"]["ingaas:h12:u:minus-control"]
