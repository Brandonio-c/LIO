"""Actual-caller regressions A04-A12 (saved records, provenance, reuse, CLI).

Catalogue: docs/research/LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md.

Fixtures go through ScanStore.append_rows / Cube / the derived and numerical
readers, and through the real ``lio`` CLI ``main``. Historical runs are only
ever COPIED into tmp_path; the originals are hashed before and after.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from lio.cli import main as cli_main
from lio.config import HwConfig, load_config
from lio.food_profiles.runs import open_run
from lio.scan.derived import analyse_model, numerical_observations
from lio.scan.provenance import (
    AdcProvenance,
    build_acquisition_snapshot,
    compute_store_seal,
    seal_store_terminal,
    verify_store_seal,
)
from lio.scan.store import IDENTITY_FIELDS, ScanStore

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
CFG = REPO / "software" / "config" / "lio_hw.yaml"
QUICK = REPO / "test_results" / "20261123-003133_scan_quick"
ANCHOR_B = REPO / "test_results" / "20261120-012619_scan_quick"


@pytest.fixture()
def cfg() -> HwConfig:
    return load_config(CFG)


def tree_hash(folder: Path) -> dict[str, str]:
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


@pytest.fixture(scope="module", autouse=True)
def _historical_runs_unchanged() -> Any:
    before = {r: tree_hash(r) for r in (QUICK, ANCHOR_B) if r.is_dir()}
    yield
    after = {r: tree_hash(r) for r in before}
    assert before == after, "a historical run was modified by these tests"


def copy_run(src: Path, dst: Path) -> Path:
    shutil.copytree(src, dst)
    return dst


# ------------------------------------------------------------- A04 - A06 / D12


def stationary_run(
    tmp: Path, *, heights: list[str] | None = None, one_position: bool = True
) -> Path:
    """Pilot 100 + production 0/1/2 on h12 InGaAs, condition u, settings0."""
    st = ScanStore.create(tmp, "protocol", {"mode": "protocol", "sample_id": "empty"})
    pos = f"{st.run_id}:pos:fixture"
    rows = []
    for i, (phase, net) in enumerate([("pilot", 100.0), ("production", 0.0),
                                      ("production", 1.0), ("production", 2.0)]):  # fmt: skip
        op = f"{st.run_id}:op:{i}"
        rows.append({
            "run_id": st.run_id, "step": i, "phase": phase,
            "height_hs": "" if heights is None else heights[i], "height_mm": "",
            "direction": "none", "rep": i, "hole": 12, "state": "lit", "detector": "ingaas",
            "dark_counts": 0, "lit_counts": net, "net_counts": net, "net_mv": "",
            "t_s": i, "duty_wait_ms": 0, "settle_ms": 8, "n": 1,
            "operation_id": op, "reading_id": op, "block_id": f"{phase}:u:h12:b{i}",
            "attempt_id": f"s{i}:a", "condition_id": "u", "setting_id": "settle8:n1",
            "segment": "stationary",
            "position_instance_id": pos if one_position else f"{pos}{i}",
        })  # fmt: skip
    st.append_rows(rows, completed_step=3)
    st.finish("COMPLETE")
    return st.folder


def test_a04_saved_reader_excludes_pilot(cfg: HwConfig, tmp_path: Path) -> None:
    run = stationary_run(tmp_path / "runs", heights=["-100"] * 4)
    out = analyse_model(run, cfg, model="qualified-v2", derived_out=tmp_path / "derived")
    est = out["estimates"]["ingaas:h12"]
    assert est["n_blocks"] == 3
    assert est["value"] == pytest.approx(1.0)
    assert est["extras"]["includes_pilot"] is False


def test_a05_unknown_height_one_position_instance(cfg: HwConfig, tmp_path: Path) -> None:
    run = stationary_run(tmp_path / "runs")
    out = analyse_model(run, cfg, model="qualified-v2", derived_out=tmp_path / "derived")
    est = out["estimates"]["ingaas:h12"]
    assert est["n_blocks"] == 3 and est["value"] == pytest.approx(1.0)


def test_a05_unknown_positions_from_different_instances_not_pooled(
    cfg: HwConfig, tmp_path: Path
) -> None:
    run = stationary_run(tmp_path / "runs", one_position=False)
    out = analyse_model(run, cfg, model="qualified-v2", derived_out=tmp_path / "derived")
    est = out["estimates"]["ingaas:h12"]
    assert est["value"] is None and est["extras"]["mixed_unknown_position"] is True


def test_a06_writer_keeps_identities_and_condition_filter(tmp_path: Path) -> None:
    run = stationary_run(tmp_path / "runs")
    rows = list(ScanStore.open(run).rows())
    assert all(k in rows[0] for k in IDENTITY_FIELDS)
    assert {r["condition_id"] for r in rows} == {"u"}
    got = numerical_observations(run, condition_id="u")
    assert got["n"] == 4
    assert {r["reading_id"] for r in got["rows"]} == {r["reading_id"] for r in rows}


def test_a06_old_cube_resume_refuses_to_drop_identities(tmp_path: Path) -> None:
    run = copy_run(QUICK, tmp_path / "old")
    st = ScanStore.open(run)
    assert "reading_id" not in st.cube_fields()
    with pytest.raises(ValueError, match="identit"):
        st.append_rows([{"run_id": "x", "reading_id": "r1"}], completed_step=999)


# ------------------------------------------------------------- A07 / A08 / D08


def _install_product(cfg: HwConfig, run: Path, derived: Path) -> dict[str, Any]:
    out = analyse_model(run, cfg, model="qualified-v2", derived_out=derived)
    product = json.loads(Path(out["_path"]).read_text())
    (run / "analysis.json").write_text(json.dumps(product))
    return product


def test_a07_open_run_invalidates_reuse_after_npz_change(cfg: HwConfig, tmp_path: Path) -> None:
    run = copy_run(QUICK, tmp_path / "copy")
    _install_product(cfg, run, tmp_path / "derived")
    assert open_run(run, cfg).analysis_ok
    npz = sorted((run / "streams").glob("*.npz"))[0]
    with np.load(npz) as z:
        data = {k: z[k].copy() for k in z.files}
    data["raw"][0] += 1
    np.savez_compressed(npz, **data)
    r = open_run(run, cfg)
    assert not r.analysis_ok and "stream" in r.analysis_reason


def test_a08_minimal_identity_is_not_verified(cfg: HwConfig, tmp_path: Path) -> None:
    run = copy_run(QUICK, tmp_path / "copy")
    cube_sha = hashlib.sha256((run / "cube.csv.gz").read_bytes()).hexdigest()
    (run / "analysis.json").write_text(json.dumps({
        "run_id": ScanStore.open(run).run_id,
        "identity": {"source_cube_sha256": cube_sha},
    }))  # fmt: skip
    r = open_run(run, cfg)
    assert not r.analysis_ok and "incomplete identity" in r.analysis_reason


# ------------------------------------------------------------- A09 / A10 / D09


def test_a09_cli_rejects_derived_inside_acquisition(tmp_path: Path) -> None:
    run = copy_run(QUICK, tmp_path / "copy")
    before = tree_hash(run)
    rc = cli_main(["scan", "analyse", str(run), "--model", "qualified-v2",
                   "--derived-out", str(run / "derived")])  # fmt: skip
    assert rc != 0
    link = tmp_path / "sneaky"
    link.symlink_to(run, target_is_directory=True)
    rc2 = cli_main(["scan", "analyse", str(run), "--model", "qualified-v2",
                    "--derived-out", str(link / "derived")])  # fmt: skip
    assert rc2 != 0
    assert tree_hash(run) == before


def test_a09_cli_refuses_silent_legacy_rewrite(tmp_path: Path) -> None:
    run = copy_run(QUICK, tmp_path / "copy")
    before = tree_hash(run)
    assert cli_main(["scan", "analyse", str(run), "--no-baselines"]) != 0
    assert cli_main(["scan", "report", str(run), "--no-baselines"]) != 0
    assert tree_hash(run) == before


def test_a09_external_derived_out_works(tmp_path: Path) -> None:
    run = copy_run(QUICK, tmp_path / "copy")
    before = tree_hash(run)
    rc = cli_main(["scan", "analyse", str(run), "--model", "qualified-v2",
                   "--derived-out", str(tmp_path / "derived")])  # fmt: skip
    assert rc == 0
    assert tree_hash(run) == before


def test_a10_cli_report_checks_requested_run(cfg: HwConfig, tmp_path: Path) -> None:
    if not ANCHOR_B.is_dir():
        pytest.skip("second historical anchor not tracked in this checkout")
    run_a = copy_run(QUICK, tmp_path / "a")
    run_b = copy_run(ANCHOR_B, tmp_path / "b")
    derived = tmp_path / "derived"
    out = analyse_model(run_a, cfg, model="qualified-v2", derived_out=derived)
    aid = out["analysis_id"]
    ok = cli_main(["scan", "report", str(run_a), "--analysis", aid, "--derived-out", str(derived)])
    assert ok == 0
    bad = cli_main(["scan", "report", str(run_b), "--analysis", aid, "--derived-out", str(derived)])
    assert bad != 0
    # Stale: run A's live cube changed after the product was made.
    (run_a / "cube.csv.gz").write_bytes((run_a / "cube.csv.gz").read_bytes() + b"\x00")
    stale = cli_main(["scan", "report", str(run_a), "--analysis", aid,
                      "--derived-out", str(derived)])  # fmt: skip
    assert stale != 0


# ------------------------------------------------------------- A11 / D10


def test_a11_seal_covers_stream_interpretation(tmp_path: Path) -> None:
    st = ScanStore.create(tmp_path, "protocol", {"mode": "protocol", "sample_id": "empty"})
    snap = build_acquisition_snapshot(
        protocol_hash="p", config_snapshot={"a": 1}, config_sha256="c",
        channel_map_snapshot={"12": {"label": "1450"}},
        adc=AdcProvenance(gain="1", fsr_v=4.096, lsb_mv=0.125, mux_map={"0": "ingaas"},
                          configured_rate_sps=128, effective_mode="mean", mains_hz=0,
                          mains_periods=None, settle_ms=8, detector_order=("ingaas", "opt101")),
    )  # fmt: skip
    st.meta["acquisition_snapshot"] = snap.to_dict()
    st.save_stream("audit", t_us=[0, 1], raw=[5, 6], detector="ingaas", adc=0)
    seal = seal_store_terminal(st, status="COMPLETE")
    assert seal is not None and verify_store_seal(st)[0]
    st.meta["streams"][0]["detector"] = "opt101"  # reinterpret the same bytes
    live = compute_store_seal(st, status="COMPLETE")
    assert live is not None and live.combined_sha256 != seal.combined_sha256
    assert not verify_store_seal(st)[0]
    assert "terminal_source_seal" not in json.dumps(st.meta["streams"])


# ------------------------------------------------------------- A12 / M0, D06


def test_a12_snapshot_defensive_freeze() -> None:
    nested = {"rails": {"A": {"current_ma": 1}}}
    snap = build_acquisition_snapshot(
        protocol_hash="p", config_snapshot=nested, config_sha256="c",
        channel_map_snapshot={"1": {"label": "395"}},
        adc=AdcProvenance(gain="1", fsr_v=4.096, lsb_mv=0.125, mux_map={},
                          configured_rate_sps=128, effective_mode="mean", mains_hz=0,
                          mains_periods=None, settle_ms=8, detector_order=()),
    )  # fmt: skip
    h0, d0 = snap.manifest_hash(), snap.to_dict()
    nested["rails"]["A"]["current_ma"] = 2
    assert snap.manifest_hash() == h0
    assert snap.to_dict() == d0
    assert snap.to_dict()["config_snapshot"]["rails"]["A"]["current_ma"] == 1
