"""Baseline selection and proxy_unassigned held-out ablation helpers."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from lio.food_profiles.ablation import (
    drop_proxy_unassigned,
    held_out_proxy_ablation,
    proxy_unassigned_mask,
)
from lio.food_profiles.baselines import (
    BaselineCandidate,
    BaselineKind,
    BaselineUse,
    candidate_from_run_folder,
    select_baseline,
)
from lio.food_profiles.features import FeatureBatch
from lio.food_profiles.schema import Recipe

pytestmark = pytest.mark.unit


def _batch_with_proxy() -> FeatureBatch:
    recipe = Recipe(name="amplitude_raw")
    return FeatureBatch(
        row_ids=["r0", "r1"],
        run_ids=["a", "b"],
        preparation_ids=[None, None],
        feature_ids=[
            "opt101:h08:net",
            "proxy_unassigned:opt101:h16:net",
            "ingaas:h12:net",
        ],
        X=np.array([[1.0, 10.0, 2.0], [1.5, 11.0, 2.5]], dtype=float),
        reasons=np.array([["ok", "ok", "ok"], ["ok", "ok", "ok"]], dtype=object),
        source_links=[{}, {}],
        recipe=recipe,
    )


def test_proxy_mask_and_drop() -> None:
    batch = _batch_with_proxy()
    mask = proxy_unassigned_mask(batch.feature_ids)
    assert mask.tolist() == [False, True, False]
    ablated, removed = drop_proxy_unassigned(batch)
    assert removed == ["proxy_unassigned:opt101:h16:net"]
    assert ablated.n_features == 2
    assert ablated.X.shape == (2, 2)


def test_held_out_ablation_metric() -> None:
    result = held_out_proxy_ablation(_batch_with_proxy())
    assert result.removed
    assert result.metric_full is not None
    assert result.metric_ablated is not None
    d = result.to_dict()
    assert "delta_metric" in d
    assert any("proxy_unassigned" in n for n in result.notes) or result.removed


def test_select_baseline_rejects_incomplete_for_quantitative() -> None:
    good = BaselineCandidate(
        "r1",
        "/tmp/r1",
        BaselineKind.SCAN_BASELINE,
        "COMPLETE",
        config_sha256="abc",
        calibration_id="gain:1",
        incomplete=False,
    )
    bad = BaselineCandidate(
        "r2",
        "/tmp/r2",
        BaselineKind.SCAN_BASELINE,
        "INCOMPLETE",
        config_sha256="abc",
        calibration_id="gain:1",
        incomplete=True,
    )
    d = select_baseline([bad, good], use=BaselineUse.QUANTITATIVE)
    assert d.ok and d.candidate is not None and d.candidate.run_id == "r1"
    raw = select_baseline([bad], use=BaselineUse.RAW_COMPARE)
    assert raw.ok and raw.candidate is not None and raw.candidate.run_id == "r2"


def test_select_baseline_rejects_calibration_mismatch() -> None:
    c = BaselineCandidate(
        "r1",
        "/tmp/r1",
        BaselineKind.EMPTY_HOLDER,
        "COMPLETE",
        config_sha256="abc",
        calibration_id="gain:1",
        incomplete=False,
    )
    d = select_baseline(
        [c],
        use=BaselineUse.QUANTITATIVE,
        require_calibration_id="gain:2",
    )
    assert d.ok is False
    assert any("calibration" in r for r in d.rejects)


def test_select_baseline_fail_closed_missing_required_facts() -> None:
    c = BaselineCandidate(
        "r1",
        "/tmp/r1",
        BaselineKind.SCAN_BASELINE,
        "COMPLETE",
        config_sha256="abc",
        calibration_id="gain:1",
        model=None,
        geometry_key=None,
        reference_protocol=None,
        incomplete=False,
    )
    d = select_baseline(
        [c],
        use=BaselineUse.QUANTITATIVE,
        require_geometry_key="top=0|bottom=-1",
        require_model="qualified-v2",
        require_reference_protocol="white",
    )
    assert d.ok is False
    text = " ".join(d.rejects).lower()
    assert "missing" in text


def test_candidate_from_run_folder(tmp_path: Path) -> None:
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "scan.json").write_text(
        json.dumps(
            {
                "run_id": "run",
                "status": "INCOMPLETE",
                "config_sha256": "deadbeef",
                "acquisition_snapshot": {"adc": {"gain": "1"}},
            }
        )
    )
    c = candidate_from_run_folder(folder)
    assert c.incomplete is True
    assert c.calibration_id == "gain:1"
