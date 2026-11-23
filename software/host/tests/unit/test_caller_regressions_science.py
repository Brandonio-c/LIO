"""Actual-caller regressions A19-A20 (quantity eligibility, scoped controls).

Catalogue: docs/research/LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md.
A21 (qualified shared selection + fresh confirmation) and A22 (h16 proxy opt-in
through batch/CLI with grouped held-out validation) are NOT closed by this
candidate; see docs/handoffs/2026-11-23_caller_remediation_acceptance.md.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from lio.config import HwConfig, load_config
from lio.food_profiles.baselines import candidate_from_run_folder
from lio.food_profiles.features import extract_run_vector
from lio.food_profiles.runs import open_run
from lio.scan.analysis.coupling import ControlEvidence, estimate_coupling
from lio.scan.analysis.data import Cube
from lio.scan.provenance import Quantity, RfProvenance, quantity_eligibility
from lio.scan.store import ScanStore

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
CFG = REPO / "software" / "config" / "lio_hw.yaml"
QUICK = REPO / "test_results" / "20261123-003133_scan_quick"


@pytest.fixture()
def cfg() -> HwConfig:
    return load_config(CFG)


def _with_snapshot(run: Path, *, rng: str, rf: dict | None) -> None:
    meta = json.loads((run / "scan.json").read_text())
    meta["acquisition_snapshot"] = {
        "input_range": {"ingaas": rng},
        "rf": {} if rf is None else {"ingaas": rf},
        "assembly": {"tray": "v3"},
        "adc": {"gain": "1"},
    }
    (run / "scan.json").write_text(json.dumps(meta))


# ----------------------------------------------------------------- A19 / D07


def test_a19_o_envelope_ingaas_ineligible_outside_a0_or_unknown_rf(
    cfg: HwConfig, tmp_path: Path
) -> None:
    run = tmp_path / "run"
    shutil.copytree(QUICK, run)
    _with_snapshot(run, rng="observed-outside-range", rf=None)
    data = open_run(run, cfg)
    # Pretend a verified product with O values exists (worst case for the gate).
    data.analysis_ok = True
    data.analysis = {"o_envelope": {"ingaas": {"12": 12.3333}, "opt101": {"4": 50.0}}}
    fb = extract_run_vector(data, "o_envelope")
    for j, key in enumerate(fb.feature_ids):
        if key.startswith("ingaas"):
            assert fb.reasons[0, j] == "excluded" and fb.X[0, j] != fb.X[0, j]  # NaN
    assert any(w.startswith("o_envelope_ingaas_ineligible") for w in fb.warnings)


def test_a19_unknown_rf_matched_ratio_ineligible() -> None:
    e = quantity_eligibility(Quantity.MATCHED_RATIO, detector="ingaas", lsb_mv=0.125,
                             rf=RfProvenance(None, "unknown", ""),
                             input_range="verified-in-range", geometry_compatible=True,
                             control_evidence=True)  # fmt: skip
    assert not e.eligible
    ok = quantity_eligibility(Quantity.MATCHED_RATIO, detector="opt101", lsb_mv=0.125,
                              geometry_compatible=True, control_evidence=True)  # fmt: skip
    assert ok.eligible  # valid OPT101 path preserved


def test_a19_baseline_adapter_keeps_nested_facts(tmp_path: Path) -> None:
    run = tmp_path / "run"
    shutil.copytree(QUICK, run)
    _with_snapshot(run, rng="unverified", rf={"value_ohm": 2e6, "state": "declared"})
    c = candidate_from_run_folder(run)
    assert c.rf_state == "declared:2000000.0"
    assert c.input_range_ingaas == "unverified"
    assert c.assembly_key and "v3" in c.assembly_key


# ----------------------------------------------------------------- A20 / D11


def test_a20_bare_hole_set_confers_no_control(cfg: HwConfig) -> None:
    cube = Cube.open(QUICK)
    res = estimate_coupling(cube, cfg, model="validated_control",
                            optical_control_evidence={8})  # fmt: skip
    for det in ("opt101", "ingaas"):
        assert res[det].C == {"A": None, "B": None}
        assert res[det].model != "validated_control"


def test_a20_scoped_evidence_from_another_run_confers_nothing(cfg: HwConfig) -> None:
    cube = Cube.open(QUICK)
    ev = ControlEvidence(8, "opt101", "some-other-run", "load1", "u", "settle8:n2", "gain:1",
                         "v3-2026-11-21", "unchanged_load_optical_block")  # fmt: skip
    res = estimate_coupling(cube, cfg, model="validated_control", optical_control_evidence=[ev])
    assert res["opt101"].C == {"A": None, "B": None}


def test_a20_applicable_evidence_has_real_estimator_variance(cfg: HwConfig) -> None:
    cube = Cube.open(QUICK)
    run_id = ScanStore.open(QUICK).run_id
    ev = ControlEvidence(8, "opt101", run_id, "load1", "u", "settle8:n2", "gain:1",
                         "v3-2026-11-21", "unchanged_load_optical_block")  # fmt: skip
    res = estimate_coupling(cube, cfg, model="validated_control", optical_control_evidence=[ev])
    r = res["opt101"]
    assert r.C["A"] is not None and r.C["B"] is None
    cov = r.covariance["A"]
    assert cov["n_readings"] >= 2 and cov["var_estimate"] == pytest.approx(
        cov["sample_var"] / cov["n_readings"]
    )
