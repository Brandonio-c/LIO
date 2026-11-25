"""M2 coupling models, roles, and §12 sensitivity regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from lio.config import load_config
from lio.scan.analysis.coupling import (
    MODEL_UNIDENTIFIED,
    estimate_coupling,
    leave_one_control_out,
    optical_amplitude,
    primary_1850_feature_holes,
    primary_1850_feature_id,
    proxy_unassigned_feature_id,
)
from lio.scan.analysis.data import Cube

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
RESULTS = REPO / "test_results"
CFG = REPO / "software" / "config" / "lio_hw.yaml"


@pytest.fixture()
def cfg():
    return load_config(CFG)


def test_unidentified_when_no_controls_never_c_zero(cfg) -> None:
    # Empty cube → no blinds measured → unidentified, C is None not 0.
    folder = RESULTS / "20261123-003133_scan_quick"
    if not (folder / "cube.csv.gz").exists():
        pytest.skip("missing cube")
    cube = Cube.open(folder)
    # Exclude every blind candidate for InGaAs.
    r = estimate_coupling(
        cube,
        cfg,
        model="validated_control",
        exclude_holes=set(range(1, 17)),
    )
    assert r["ingaas"].model == MODEL_UNIDENTIFIED
    assert r["ingaas"].C["A"] is None and r["ingaas"].C["B"] is None
    o, reason = optical_amplitude(22.0, r["ingaas"], "B")
    assert o is None and reason == "coupling_unidentified"
    assert 0.0 not in (r["ingaas"].C["A"], r["ingaas"].C["B"])


def test_h16_excluded_from_primary_1850_feature_namespace() -> None:
    assert 16 not in primary_1850_feature_holes("opt101")
    assert 16 not in primary_1850_feature_holes("ingaas")
    assert primary_1850_feature_id("opt101", 16) is None
    assert primary_1850_feature_id("ingaas", 16) is None
    assert proxy_unassigned_feature_id("opt101", 16).startswith("proxy_unassigned:")


def test_section12_ingaas_rail_b_sensitivity(cfg) -> None:
    cases = {
        "20261123-003133_scan_quick": (16.0, 10.0),
        "20261120-012619_scan_quick": (11.0, 5.5),
        "20261119-152512_scan_quick": (7.0, 4.5),
    }
    for name, (full, no16) in cases.items():
        folder = RESULTS / name
        if not (folder / "cube.csv.gz").exists():
            pytest.skip(f"missing {name}")
        cube = Cube.open(folder)
        sens = leave_one_control_out(cube, cfg, "ingaas", rail="B")
        assert sens["C_full"] == pytest.approx(full)
        assert sens["exclude_h16"] == pytest.approx(no16)
        assert sens["exclude_h10_h11_h16"] is None
        assert sens["exclude_h10_h11_h16_model"] == MODEL_UNIDENTIFIED
        assert sens["never_zero_when_unidentified"] is True


def test_section12_opt101_rail_b_sensitivity(cfg) -> None:
    cases = {
        "20261123-003133_scan_quick": (2.0, 1.5),
        "20261120-012619_scan_quick": (13.0, 12.0),
        "20261119-152512_scan_quick": (15.0, 15.0),
    }
    for name, (full, no16) in cases.items():
        folder = RESULTS / name
        if not (folder / "cube.csv.gz").exists():
            pytest.skip(f"missing {name}")
        cube = Cube.open(folder)
        sens = leave_one_control_out(cube, cfg, "opt101", rail="B")
        assert sens["C_full"] == pytest.approx(full)
        assert sens["exclude_h16"] == pytest.approx(no16)


def test_h12_o_sensitivity_nov23(cfg) -> None:
    folder = RESULTS / "20261123-003133_scan_quick"
    if not (folder / "cube.csv.gz").exists():
        pytest.skip("missing cube")
    import copy

    from lio.config import parse_config

    # Judge h13/h14 as signal holes, as the 23 Nov analysis did (expected-weak since
    # the 2026-11-25 owner calibration, which skips their response findings).
    data = copy.deepcopy(cfg.data)
    for ch in data["channels"]:
        if int(ch["hole"]) in (13, 14):
            ch["expect"] = {"ingaas": "signal"}
    cfg = parse_config(data, cfg.path)
    from lio.scan.analysis import optics

    cube = Cube.open(folder)
    # Reproduce optics channel_stats O shift 12.3333 → 18.3333 for C 16 → 10.
    ectx_full, _ = __import__("lio.scan.analysis.electrical", fromlist=["analyse"]).analyse(
        cube, cfg
    )
    # Monkey with C via leave-one-out values
    sens = leave_one_control_out(cube, cfg, "ingaas", rail="B")
    assert sens["C_full"] == pytest.approx(16.0)
    assert sens["exclude_h16"] == pytest.approx(10.0)
    # Use optics curve peak: saved O uses C=16 → ~12.3333; with C=10 → +6.
    _octx, findings = optics.analyse(cube, cfg, ectx_full, None)
    h12 = next(f for f in findings if f.id == "optics/ingaas/h12/response")
    assert h12.data["O"] == pytest.approx(12.3333, rel=0, abs=0.01)
    o_alt = float(h12.data["O"]) + (16.0 - 10.0)
    assert o_alt == pytest.approx(18.3333, rel=0, abs=0.01)
    # h13/h14 remain negative in that sensitivity case
    for hid in ("optics/ingaas/h13/response", "optics/ingaas/h14/response"):
        f = next(x for x in findings if x.id == hid)
        assert float(f.data["O"]) + 6.0 < 0


def test_light_returning_blind_holes_do_not_inflate_coupling(cfg) -> None:
    """Owner 2026-11-25: Citrucel reflects h11/h16 onto the InGaAs (height-dependent
    light). Those blind holes are excluded, so rail B C is not inflated (+44 -> +13)."""
    folder = RESULTS / "20261125-141952_scan_fine"
    if not (folder / "cube.csv.gz").exists():
        pytest.skip("missing cube")
    from lio.scan.analysis import electrical

    cube = Cube.open(folder)
    ctx, _ = electrical.coupling(cube, cfg)
    assert ctx["ingaas"]["optical_blind"] == [11, 16]
    assert ctx["ingaas"]["C"]["B"] == pytest.approx(13.0)
    legacy, _ = electrical.coupling(cube, cfg, exclude_optical=False)
    assert legacy["ingaas"]["C"]["B"] == pytest.approx(44.0)  # the documented old method
