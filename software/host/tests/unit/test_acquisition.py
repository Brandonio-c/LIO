"""M4 targeted stationary acquisition — offline plan and fake meas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lio.config import load_config
from lio.scan.acquisition import (
    APPROVED_FIXED_GAIN,
    ProtocolError,
    allocate_pilot_frozen,
    allocation_objective,
    load_protocol,
    plan_protocol,
    run_protocol,
)

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
EXAMPLE = (
    REPO
    / "software"
    / "host"
    / "src"
    / "lio"
    / "scan"
    / "examples"
    / "stationary_targeted_h12.json"
)
CFG = REPO / "software" / "config" / "lio_hw.yaml"


@pytest.fixture()
def cfg():
    return load_config(CFG)


def test_offline_plan_example(cfg) -> None:
    plan = plan_protocol(EXAMPLE, cfg)
    assert plan.protocol.gain == APPROVED_FIXED_GAIN
    assert plan.to_dict()["arms_motors"] is False
    assert all(s.hole in plan.protocol.holes for s in plan.steps)
    assert plan.predicted_on_ms <= float(plan.protocol.budgets["max_total_on_ms"])


def test_reject_bad_gain(cfg) -> None:
    raw = json.loads(EXAMPLE.read_text())
    raw["gain"] = "2"
    with pytest.raises(ProtocolError, match="gain"):
        load_protocol(raw)


def test_reject_unknown_keys_and_nan() -> None:
    raw = json.loads(EXAMPLE.read_text())
    raw["extra_field"] = 1
    with pytest.raises(ProtocolError, match="unknown"):
        load_protocol(raw)
    raw = json.loads(EXAMPLE.read_text())
    raw["budgets"]["max_wall_s"] = float("nan")
    with pytest.raises(ProtocolError, match="NaN"):
        load_protocol(raw)


def test_fake_transport_only_intended_holes(cfg, tmp_path: Path) -> None:
    plan = plan_protocol(EXAMPLE, cfg)
    seen: list[int] = []

    def meas(hole: int, settle: int, n: int) -> dict:
        seen.append(hole)
        return {
            "hole": hole,
            "t_on_ms": 10,
            "dark_ingaas": 0,
            "lit_ingaas": 5,
            "net_ingaas": 5,
            "dark_opt101": 0,
            "lit_opt101": 3,
            "net_opt101": 3,
        }

    result = run_protocol(
        plan,
        cfg=cfg,
        root=tmp_path,
        sample_id="empty",
        allow_light=True,
        meas=meas,
        simulated=True,
        operator_checkpoint_flag=True,
    )
    assert result.status == "COMPLETE"
    assert set(seen) <= set(plan.protocol.holes)
    assert (result.folder / "cube.csv.gz").exists()
    assert "terminal_source_seal" in result.store.meta
    assert "acquisition_snapshot" in result.store.meta
    assert result.store.meta.get("operator_checkpoints")


def test_pilot_frozen_improves_synthetic_objective(cfg) -> None:
    raw = json.loads(EXAMPLE.read_text())
    raw["allocation"]["policy"] = "pilot_frozen"
    raw["blocks"] = {
        "n_pilot": 2,
        "n_production_min": 1,
        "n_production_max": 12,
    }
    raw["budgets"]["max_total_on_ms"] = 500000
    proto = load_protocol(raw)
    variance = {8: 1.0, 9: 1.0, 12: 100.0, 13: 4.0, 14: 4.0, 15: 4.0}
    weights = {h: float(proto.allocation["target_weights"].get(str(h), 1.0)) for h in proto.holes}
    frozen = allocate_pilot_frozen(proto, pilot_variance=variance)
    n_fr = {int(k): int(v) for k, v in frozen["n_production_per_hole"].items()}
    total = sum(n_fr.values())
    # Equal split of the same total production count.
    base, rem = divmod(total, len(proto.holes))
    n_eq = {h: base + (1 if i < rem else 0) for i, h in enumerate(proto.holes)}
    obj_eq = allocation_objective(n_eq, variance, weights)
    obj_fr = allocation_objective(n_fr, variance, weights)
    assert n_fr[12] >= max(n_fr[h] for h in (13, 14, 15))
    assert obj_fr <= obj_eq + 1e-9


def test_partial_cancel_keeps_unresolved(cfg, tmp_path: Path) -> None:
    plan = plan_protocol(EXAMPLE, cfg)
    n = {"i": 0}

    def meas(hole: int, settle: int, n_avg: int) -> dict:
        n["i"] += 1
        return {
            "hole": hole,
            "dark_ingaas": 0,
            "lit_ingaas": 1,
            "net_ingaas": 1,
            "dark_opt101": 0,
            "lit_opt101": 1,
            "net_opt101": 1,
        }

    result = run_protocol(
        plan,
        cfg=cfg,
        root=tmp_path,
        sample_id="empty",
        allow_light=True,
        meas=meas,
        cancel_check=lambda: n["i"] >= 3,
        simulated=True,
        operator_checkpoint_flag=True,
    )
    assert result.status == "INCOMPLETE"
    assert result.cancel_reason == "cancelled"
    assert result.store.meta.get("unresolved") is True
    assert result.store.meta.get("status") == "INCOMPLETE"
    assert result.store.meta.get("duty_journal_policy") == "retain_charges_on_incomplete"


def test_run_requires_allow_light(cfg, tmp_path: Path) -> None:
    plan = plan_protocol(EXAMPLE, cfg)
    with pytest.raises(ProtocolError, match="allow-light"):
        run_protocol(
            plan,
            cfg=cfg,
            root=tmp_path,
            sample_id="empty",
            allow_light=False,
            meas=lambda *a: {},
        )


def test_checkpoint_requires_explicit_flag(cfg, tmp_path: Path) -> None:
    plan = plan_protocol(EXAMPLE, cfg)
    with pytest.raises(ProtocolError, match="checkpoint"):
        run_protocol(
            plan,
            cfg=cfg,
            root=tmp_path,
            sample_id="empty",
            allow_light=True,
            meas=lambda *a: {},
        )


def test_checkpoint_refused_keeps_incomplete(cfg, tmp_path: Path) -> None:
    plan = plan_protocol(EXAMPLE, cfg)
    result = run_protocol(
        plan,
        cfg=cfg,
        root=tmp_path,
        sample_id="empty",
        allow_light=True,
        meas=lambda *a: {},
        operator_checkpoint_flag=False,
        simulated=True,
    )
    assert result.status == "INCOMPLETE"
    assert result.cancel_reason == "checkpoint_refused"
    assert result.store.meta["status"] == "INCOMPLETE"
    assert result.store.meta.get("unresolved") is True
    ck = result.store.meta.get("operator_checkpoints") or []
    assert ck and ck[0]["operator_confirmed"] is False
    assert ck[0]["human_confirmation_invented"] is False


def test_resume_protocol_from_incomplete(cfg, tmp_path: Path) -> None:
    from lio.scan.acquisition import resume_protocol

    plan = plan_protocol(EXAMPLE, cfg)
    n = {"i": 0}

    def meas(hole: int, settle: int, n_avg: int) -> dict:
        n["i"] += 1
        return {
            "hole": hole,
            "dark_ingaas": 0,
            "lit_ingaas": 1,
            "net_ingaas": 1,
            "dark_opt101": 0,
            "lit_opt101": 1,
            "net_opt101": 1,
        }

    partial = run_protocol(
        plan,
        cfg=cfg,
        root=tmp_path,
        sample_id="empty",
        allow_light=True,
        meas=meas,
        cancel_check=lambda: n["i"] >= 2,
        simulated=True,
        operator_checkpoint_flag=True,
    )
    assert partial.status == "INCOMPLETE"
    # Resume must not silently promote; continue with remaining steps.
    done = resume_protocol(
        partial.folder,
        cfg=cfg,
        allow_light=True,
        meas=meas,
        operator_checkpoint_flag=True,
    )
    assert done.status in ("COMPLETE", "INCOMPLETE")
    assert done.store.meta["status"] == done.status
    if done.status == "COMPLETE":
        assert done.store.meta.get("unresolved") is not True


def test_resume_refuses_complete(cfg, tmp_path: Path) -> None:
    from lio.scan.acquisition import resume_protocol

    plan = plan_protocol(EXAMPLE, cfg)

    def meas(hole: int, settle: int, n_avg: int) -> dict:
        return {
            "hole": hole,
            "dark_ingaas": 0,
            "lit_ingaas": 1,
            "net_ingaas": 1,
            "dark_opt101": 0,
            "lit_opt101": 1,
            "net_opt101": 1,
        }

    full = run_protocol(
        plan,
        cfg=cfg,
        root=tmp_path,
        sample_id="empty",
        allow_light=True,
        meas=meas,
        simulated=True,
        operator_checkpoint_flag=True,
    )
    assert full.status == "COMPLETE"
    with pytest.raises(ProtocolError, match="COMPLETE"):
        resume_protocol(
            full.folder,
            cfg=cfg,
            allow_light=True,
            meas=meas,
            operator_checkpoint_flag=True,
        )
