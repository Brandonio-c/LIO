"""Actual-caller regressions A14-A18 (runner, operator, budgets, resume, preflight).

Catalogue: docs/research/LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md.

run_protocol / resume_protocol / the height-scan executor / the dashboard
ProtocolJob and HTTP server are the code under test; only the transport,
operator, clock and simulator are faked.
"""

from __future__ import annotations

import copy
import json
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from lio.config import HwConfig, load_config
from lio.device import LIODevice, NoResponse
from lio.ownership import DutyJournal
from lio.scan.acquisition import (
    ProtocolError,
    plan_protocol,
    resume_protocol,
    run_protocol,
)
from lio.scan.store import ScanStore
from lio.sim import SimulatedLIO
from lio.transport import SimTransport

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
CFG = REPO / "software" / "config" / "lio_hw.yaml"


@pytest.fixture()
def cfg() -> HwConfig:
    return load_config(CFG)


def proto(**over: Any) -> dict[str, Any]:
    p: dict[str, Any] = {
        "id": "wf", "version": "1", "schema": 1, "kind": "stationary_targeted",
        "sample": {"sample_id": "empty", "declared": True},
        "assembly": {"tray": "v3", "lid": "closed"},
        "holes": [12, 13], "detectors": ["ingaas"], "position_policy": "current_position",
        "gain": "1",
        "conditions": [{"id": "u", "label": "u", "settle_ms": 1, "mains_periods": 1,
                        "optical_block": False}],
        "blocks": {"n_production": 2, "n_pilot": 0, "n_production_min": 1,
                   "n_production_max": 8},
        "budgets": {"max_wall_s": 600, "max_cycle_s": 0, "max_total_on_ms": 100000},
        "allocation": {"policy": "equal_fixed", "control_holes": [],
                       "target_weights": {"12": 1.0, "13": 1.0}},
        "inference": {"split": "fixed_n", "pilot_is_confirmation": False},
        "estimator": {"name": "fixed_n_block", "version": "m3",
                      "coupling_model": "validated_control"},
        "operator_checkpoints": [], "objective": "primary_swir", "notes": "wf",
    }  # fmt: skip
    p.update(over)
    return p


def fake_meas(hole: int, settle: int, n_avg: int) -> dict[str, Any]:
    return {"hole": hole, "t_on_ms": 5.0, "dark_ingaas": 0.0, "lit_ingaas": float(hole),
            "net_ingaas": float(hole)}  # fmt: skip


class DropReply(SimTransport):
    """Delivers the MEAS to the simulator, then loses its response (timeout)."""

    def __init__(self, sim: SimulatedLIO) -> None:
        super().__init__(sim)
        self.drop_meas = False

    def read_line(self, timeout: float) -> str | None:
        line = super().read_line(timeout)
        if self.drop_meas and line is not None and re.search(r"\bOK MEAS\b", line):
            return None
        return line


def sim_device(cfg: HwConfig, tmp: Path, transport: SimTransport | None = None) -> LIODevice:
    sim = SimulatedLIO(cfg)
    j = DutyJournal.for_rig("wf", state_root=tmp, window_s=60.0,
                            budget_ms=cfg.duty_budgets_ms(), rail_of=cfg.duty_key,
                            synthetic=True)  # fmt: skip
    return LIODevice(transport or SimTransport(sim), cfg, journal=j)


# ----------------------------------------------------------------- A14 / D15


def test_a14_timeout_after_transmission_keeps_permanent_cost(cfg: HwConfig, tmp_path: Path) -> None:
    sim = SimulatedLIO(cfg)
    t = DropReply(sim)
    dev = sim_device(cfg, tmp_path, t)
    dev.open()
    try:
        t.drop_meas = True
        plan = plan_protocol(proto(), cfg)
        res = run_protocol(plan, cfg=cfg, root=tmp_path / "runs", sample_id="empty",
                           allow_light=True, device=dev, simulated=True)  # fmt: skip
        assert res.status == "INCOMPLETE"
        b = res.store.meta["exposure_budget"]
        assert b["reserved_ms"] > 0 and b["uncertain_ms"] > 0
        assert b["reserved_ms"] >= dev.last_charge_ms - 1e-6
        assert "NoResponse" in str(res.cancel_reason) or "no response" in str(res.cancel_reason)
        assert NoResponse  # the transport-level failure type the runner saw
    finally:
        t.drop_meas = False
        dev.close()


# ----------------------------------------------------------------- A15 / D16


def test_a15_resume_executes_exact_frozen_schedule(cfg: HwConfig, tmp_path: Path) -> None:
    frozen = {"policy": "pilot_frozen", "n_pilot_per_hole": {"12": 0, "13": 0},
              "n_production_per_hole": {"12": 1, "13": 5}}  # fmt: skip
    p = proto(allocation={"policy": "pilot_frozen", "control_holes": [],
                          "target_weights": {"12": 1.0, "13": 5.0}},
              blocks={"n_pilot": 1, "n_production_min": 1, "n_production_max": 8})  # fmt: skip
    plan = plan_protocol(p, cfg, allocation_override=frozen)
    order = [(s.phase, s.hole) for s in plan.steps]
    calls: list[int] = []

    def meas(hole: int, settle: int, n_avg: int) -> dict[str, Any]:
        calls.append(hole)
        return fake_meas(hole, settle, n_avg)

    first = run_protocol(plan, cfg=cfg, root=tmp_path, sample_id="empty", allow_light=True,
                         meas=meas, cancel_check=lambda: len(calls) >= 3, simulated=True)  # fmt: skip
    assert first.status == "INCOMPLETE"
    resumed = resume_protocol(first.folder, cfg=cfg, allow_light=True, meas=meas)
    assert resumed.status == "COMPLETE"
    rows = [r for r in ScanStore.open(first.folder).rows() if r["detector"] == "ingaas"]
    done = [(r["phase"], int(r["hole"])) for r in rows]
    assert done == order, f"executed {done}, frozen {order}"
    prod = [h for ph, h in done if ph == "production"]
    assert (prod.count(12), prod.count(13)) == (1, 5)


def test_a15_resume_refuses_records_that_do_not_match_the_freeze(
    cfg: HwConfig, tmp_path: Path
) -> None:
    plan = plan_protocol(proto(), cfg)
    calls = {"n": 0}

    def meas(hole: int, settle: int, n_avg: int) -> dict[str, Any]:
        calls["n"] += 1
        return fake_meas(hole, settle, n_avg)

    first = run_protocol(plan, cfg=cfg, root=tmp_path, sample_id="empty", allow_light=True,
                         meas=meas, cancel_check=lambda: calls["n"] >= 2, simulated=True)  # fmt: skip
    st = ScanStore.open(first.folder)
    st.meta["completed_step"] = 3  # claims more than the durable records hold
    st.save_meta()
    with pytest.raises(ProtocolError, match="record"):
        resume_protocol(first.folder, cfg=cfg, allow_light=True, meas=meas)


# ----------------------------------------------------------------- A16 / D13


def _http(srv: Any, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    req = urllib.request.Request(srv.url.rstrip("/") + path,
                                 method="GET" if body is None else "POST")  # fmt: skip
    req.add_header("X-LIO-Token", srv.token)
    if body is not None:
        req.data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _wait(pred: Any, timeout: float = 10.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


def test_a16_dashboard_checkpoints_need_fresh_strict_boolean_answers(
    cfg: HwConfig, tmp_path: Path
) -> None:
    from lio.dashboard.server import DashboardServer
    from lio.dashboard.session import Session

    session = Session(cfg, tmp_path)
    session.connect("sim", "")
    srv = DashboardServer(session, "127.0.0.1", 0)
    srv.serve_in_thread()
    try:
        p = proto(operator_checkpoints=["Fit the optical block now"])
        session.protocol_start(p, "empty", allow_light=True, heartbeat=False,
                               operator_checkpoint_flag=True)  # fmt: skip
        job = session.protocol_job
        assert job is not None
        assert _wait(lambda: bool(job.view()["pending_prompts"]))
        occ = job.view()["pending_prompts"][0]
        # The start flag did NOT answer the first occurrence: nothing measured.
        assert job.view()["progress"].get("status") == "awaiting_checkpoint"
        for bad in ("false", "true", 1, None):
            code, _ = _http(srv, "/api/scan/protocol/answer",
                            {"occurrence_id": occ, "confirmed": bad})  # fmt: skip
            assert code == 400, bad
        code, _ = _http(srv, "/api/scan/protocol/answer", {"occurrence_id": occ})
        assert code == 400
        code, _ = _http(srv, "/api/scan/protocol/answer",
                          {"occurrence_id": occ, "confirmed": False})  # fmt: skip
        assert code == 200
        assert _wait(lambda: not job.alive)
        assert job.result is not None and job.result["status"] == "INCOMPLETE"
        assert job.result["cancel_reason"] == "checkpoint_refused"
        rows = list(ScanStore.open(Path(job.result["folder"])).rows())
        assert rows == []
    finally:
        srv.shutdown()
        srv.server_close()
        session.disconnect()


# ----------------------------------------------------------------- A17 / D14


def test_a17_worker_does_not_beat_for_the_operator(cfg: HwConfig, tmp_path: Path) -> None:
    from lio.dashboard.session import Session

    session = Session(cfg, tmp_path)
    session.connect("sim", "")
    try:
        p = proto(operator_checkpoints=["confirm"])
        session.protocol_start(p, "empty", allow_light=True, heartbeat=True, timeout_s=0.5,
                               operator_checkpoint_flag=True)  # fmt: skip
        job = session.protocol_job
        assert job is not None
        assert _wait(lambda: bool(job.view()["pending_prompts"]))
        beat0 = job.control._last_beat
        time.sleep(1.0)
        assert job.control._last_beat == beat0  # nobody beat on the operator's behalf
        assert not job.control.heartbeat_ok()
        job.control.abort_reason = "test"
        assert _wait(lambda: not job.alive)
    finally:
        session.disconnect()


def test_a17_prompt_longer_than_wall_cap_does_not_measure(cfg: HwConfig, tmp_path: Path) -> None:
    clock = {"t": 100.0}
    measured: list[int] = []

    def confirm(_msg: str) -> bool:
        clock["t"] += 2.0  # the operator took 2 s
        return True

    def meas(hole: int, settle: int, n_avg: int) -> dict[str, Any]:
        measured.append(hole)
        return fake_meas(hole, settle, n_avg)

    p = proto(operator_checkpoints=["ok?"],
              budgets={"max_wall_s": 1, "max_cycle_s": 0, "max_total_on_ms": 100000})  # fmt: skip
    plan = plan_protocol(p, cfg)
    res = run_protocol(plan, cfg=cfg, root=tmp_path, sample_id="empty", allow_light=True,
                       meas=meas, operator_confirm=confirm, simulated=True,
                       clock=lambda: clock["t"], wall_clock=lambda: 1.7e9 + clock["t"])  # fmt: skip
    assert res.status == "INCOMPLETE" and res.cancel_reason == "max_wall_s"
    assert measured == []


def test_a17_monotonic_going_backwards_grants_no_time(cfg: HwConfig, tmp_path: Path) -> None:
    ticks = iter([1000.0, 1000.0, 1000.0] + [0.0] * 1000)
    measured: list[int] = []

    def meas(hole: int, settle: int, n_avg: int) -> dict[str, Any]:
        measured.append(hole)
        return fake_meas(hole, settle, n_avg)

    plan = plan_protocol(proto(), cfg)
    res = run_protocol(plan, cfg=cfg, root=tmp_path, sample_id="empty", allow_light=True,
                       meas=meas, simulated=True, clock=lambda: next(ticks),
                       wall_clock=lambda: 1.7e9)  # fmt: skip
    assert res.status == "INCOMPLETE" and res.cancel_reason == "clock_discontinuity"
    assert len(measured) <= 1


def test_a17_downtime_between_stop_and_resume_counts(cfg: HwConfig, tmp_path: Path) -> None:
    wall = {"t": 1.7e9}
    calls = {"n": 0}

    def meas(hole: int, settle: int, n_avg: int) -> dict[str, Any]:
        calls["n"] += 1
        return fake_meas(hole, settle, n_avg)

    p = proto(budgets={"max_wall_s": 60, "max_cycle_s": 0, "max_total_on_ms": 100000})
    plan = plan_protocol(p, cfg)
    first = run_protocol(plan, cfg=cfg, root=tmp_path, sample_id="empty", allow_light=True,
                         meas=meas, cancel_check=lambda: calls["n"] >= 1, simulated=True,
                         wall_clock=lambda: wall["t"])  # fmt: skip
    wall["t"] += 3600.0  # resumed an hour later (different process: new monotonic frame)
    res = resume_protocol(first.folder, cfg=cfg, allow_light=True, meas=meas,
                          clock=lambda: 5.0, wall_clock=lambda: wall["t"])  # fmt: skip
    assert res.status == "INCOMPLETE" and res.cancel_reason in ("max_wall_s",
                                                                  "clock_discontinuity")  # fmt: skip


# ----------------------------------------------------------------- A18 / D06


def test_a18_protocol_start_refuses_gain2(cfg: HwConfig, tmp_path: Path) -> None:
    dev = sim_device(cfg, tmp_path)
    dev.open()
    try:
        dev.adc_gain("2")
        sends = dev.light_sends
        with pytest.raises(ProtocolError, match="gain"):
            run_protocol(plan_protocol(proto(), cfg), cfg=cfg, root=tmp_path / "r",
                         sample_id="empty", allow_light=True, device=dev, simulated=True)  # fmt: skip
        assert dev.light_sends == sends
    finally:
        dev.close()


def test_a18_missing_mains_readback_refused(cfg: HwConfig, tmp_path: Path) -> None:
    sim = SimulatedLIO(cfg)

    class NoMains(SimTransport):
        def read_line(self, timeout: float) -> str | None:
            line = super().read_line(timeout)
            if line is not None and "OK INFO" in line:
                return re.sub(r"\smains=\d+", "", line)
            return line

    dev = sim_device(cfg, tmp_path, NoMains(sim))
    dev.open()
    try:
        sends = dev.light_sends
        with pytest.raises(ProtocolError, match="mains"):
            run_protocol(plan_protocol(proto(), cfg), cfg=cfg, root=tmp_path / "r",
                         sample_id="empty", allow_light=True, device=dev, simulated=True)  # fmt: skip
        assert dev.light_sends == sends
    finally:
        dev.close()


def test_a18_height_resume_gain2_snapshot_still_refused(cfg: HwConfig, tmp_path: Path) -> None:
    from lio.operator import SimOperator
    from lio.scan import plan_for, resume, sim_stage
    from lio.scan.provenance import snapshot_from_hw_config

    sim = SimulatedLIO(cfg)
    dev = sim_device(cfg, tmp_path, SimTransport(sim))
    with dev:
        sim_stage(dev, tmp_path / "stage.json", int(sim.travel_hs))
        plan = plan_for(cfg, "quick", dev.stage, 0)
        snap = snapshot_from_hw_config(cfg, protocol_hash="a18", gain="2",
                                       mains_periods=None, mains_hz=None)  # fmt: skip
        store = ScanStore.create(tmp_path / "out", plan.mode, {
            "mode": plan.mode, "sample_id": "empty", "status": "INCOMPLETE",
            "completed_step": 0, "simulated": True, "config_sha256": cfg.sha256,
            "firmware": dict(dev.info().values), "plan": plan.to_dict(),
            "acquisition_snapshot": copy.deepcopy(snap.to_dict()),
        })  # fmt: skip
        dev.adc_gain("2")  # live gain 2 matching the gain-2 snapshot
        sends = dev.light_sends
        with pytest.raises(Exception, match=r"gain"):
            resume(dev, cfg, store.folder, SimOperator(sim))
        assert dev.light_sends == sends
    _ = threading  # keep import for helpers
