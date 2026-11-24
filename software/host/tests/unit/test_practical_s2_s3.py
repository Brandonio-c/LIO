"""S2/S3 practical-upgrade regressions through actual callers (offline only).

Height producer identities, exposure/build provenance, semantic protocol resume
(including the audit's all-steps-present INCOMPLETE copies), legal unsealed crash
recovery, effective mains-period settings and the physical stage-write guard.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from lio.config import HwConfig, load_config
from lio.device import LIODevice
from lio.operator import SimOperator
from lio.ownership import DutyJournal
from lio.scan import plan_for, sim_stage, start
from lio.scan.acquisition import ProtocolError, plan_protocol, resume_protocol, run_protocol
from lio.scan.plan import PlanError, ScanSettings
from lio.scan.store import IDENTITY_FIELDS, ScanStore
from lio.sim import SimulatedLIO
from lio.stage import PhysicalStageWriteError, StageTracker
from lio.transport import SimTransport

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
CFG = REPO / "software" / "config" / "lio_hw.yaml"
P2 = REPO / "test_results" / "20261123-180942_scan_protocol"


@pytest.fixture()
def cfg() -> HwConfig:
    return load_config(CFG)


def sim_dev(cfg: HwConfig, tmp: Path) -> tuple[LIODevice, SimulatedLIO, list[str]]:
    sim = SimulatedLIO(cfg)
    j = DutyJournal.for_rig("s2", state_root=tmp, window_s=60.0, budget_ms=cfg.duty_budgets_ms(),
                            rail_of=cfg.duty_key, synthetic=True)  # fmt: skip
    t = SimTransport(sim)
    sent: list[str] = []
    orig = t.write_line

    def spy(line: str) -> None:
        sent.append(line)
        orig(line)

    t.write_line = spy  # type: ignore[method-assign]
    return LIODevice(t, cfg, journal=j), sim, sent


def _electrical(cfg: HwConfig, tmp: Path, periods: int) -> tuple[ScanStore, list[str], Any]:
    dev, sim, sent = sim_dev(cfg, tmp)
    with dev:
        sim_stage(dev, tmp / "stage.json", int(sim.travel_hs))
        plan = plan_for(cfg, "electrical", dev.stage, 0, {"mains_periods": periods})
        store, _status = start(dev, cfg, plan, tmp / "runs", SimOperator(sim), sample_id="empty",
                               sim=True)  # fmt: skip
    return store, sent, plan


# ------------------------------------------------------------------- S2 height


def test_height_rows_have_complete_identities_and_provenance(cfg: HwConfig, tmp_path: Path) -> None:
    store, _sent, _plan = _electrical(cfg, tmp_path, 2)
    rows = list(store.rows())
    assert rows
    for k in ("operation_id", "reading_id", "block_id", "attempt_id", "condition_id",
              "segment", "position_instance_id"):  # fmt: skip
        assert all(r.get(k) for r in rows), k
    assert set(IDENTITY_FIELDS) <= set(rows[0])
    # Detector rows from one operation share a reading; readings are not inflated.
    by_reading: dict[str, list[str]] = {}
    for r in rows:
        by_reading.setdefault(r["reading_id"], []).append(r["detector"])
    assert all(len(v) == len(set(v)) for v in by_reading.values())
    assert any(sorted(v) == ["ingaas", "opt101"] for v in by_reading.values())
    meta = ScanStore.open(store.folder).meta
    assert meta["exposure_bound"] == "simulated"
    assert meta["software"]["loaded_source_sha256"]
    assert meta["segments"][0]["segment"] == "height:s0"


# ------------------------------------------------------------------- S3 settings


def _ns(sent: list[str], word: str) -> set[str]:
    out = set()
    for line in sent:
        toks = line.split()
        body = toks[1:] if toks and toks[0].startswith("@") else toks
        if body and body[0] == word:
            out.add(body[-1])
    return out


def test_height_mains_periods_change_actual_sweep(cfg: HwConfig, tmp_path: Path) -> None:
    _s1, sent1, plan1 = _electrical(cfg, tmp_path / "p1", 1)
    s2, sent2, plan2 = _electrical(cfg, tmp_path / "p2", 2)
    assert plan2.eta_s > plan1.eta_s
    assert _ns(sent1, "SWEEP") == {"1"} and _ns(sent2, "SWEEP") == {"2"}
    assert ScanStore.open(s2.folder).meta["plan"]["settings"]["mains_periods"] == 2


def test_height_infeasible_integration_refused_before_light(cfg: HwConfig, tmp_path: Path) -> None:
    """3+ periods x 8 RAIL A holes cannot fit 1000 ms/min under conservative SWEEP
    charges: refused before any SWEEP is sent, never 'wait 0 s', abort recorded."""
    from lio.ownership import DutyBudgetError

    with pytest.raises(DutyBudgetError, match="infeasible"):
        _electrical(cfg, tmp_path, 8)
    runs = list((tmp_path / "runs").iterdir())
    meta = ScanStore.open(runs[0]).meta
    assert meta["aborts"] and "infeasible" in meta["aborts"][-1]["reason"]
    assert not any(r for r in ScanStore.open(runs[0]).rows() if r.get("state") == "lit")


def test_protocol_mains_periods_2_to_8_change_meas(cfg: HwConfig, tmp_path: Path) -> None:
    proto = json.loads((REPO / "software/host/src/lio/scan/examples/stationary_targeted_h12.json")
                       .read_text())  # fmt: skip
    proto.update(holes=[8], detectors=["opt101"], operator_checkpoints=[],
                 blocks={"n_production": 1, "n_pilot": 0, "n_production_min": 1,
                         "n_production_max": 8},
                 allocation={"policy": "equal_fixed", "control_holes": [],
                             "target_weights": {"8": 1.0}})  # fmt: skip
    got = {}
    for periods in (2, 8):
        proto["conditions"][0]["mains_periods"] = periods
        plan = plan_protocol(proto, cfg)
        dev, _sim, sent = sim_dev(cfg, tmp_path / f"d{periods}")
        with dev:
            res = run_protocol(plan, cfg=cfg, root=tmp_path / f"r{periods}", sample_id="empty",
                               allow_light=True, device=dev, simulated=True)  # fmt: skip
        assert res.status == "COMPLETE"
        got[periods] = (_ns(sent, "MEAS"), plan.predicted_on_ms,
                        {r["setting_id"] for r in ScanStore.open(res.folder).rows()})  # fmt: skip
    assert got[2][0] == {"2"} and got[8][0] == {"8"}
    assert got[8][1] > got[2][1]
    assert got[2][2] == {"settle8:n2"} and got[8][2] == {"settle8:n8"}


def test_ignored_setting_is_refused(cfg: HwConfig) -> None:
    assert float(ScanSettings.from_config(cfg).mains_hz or 0) > 0
    with pytest.raises(PlanError, match="no effect"):
        ScanSettings.from_config(cfg, {"sweep_n": 8})


# ------------------------------------------------------------------- S2 resume


def _incomplete_copy(tmp: Path, cfg: HwConfig, *, unsealed: bool = False) -> Path:
    """COPY of P2 put into an INCOMPLETE end state (all 12 steps, completed_step=11).

    The copy's config hash is set to today's config so the semantic checks (not
    the config-change refusal) are what is exercised; ``unsealed`` also drops the
    seal so row validation itself is reached."""
    dst = tmp / P2.name
    shutil.copytree(P2, dst)
    meta = json.loads((dst / "scan.json").read_text())
    meta["status"] = "INCOMPLETE"
    meta["config_sha256"] = cfg.sha256
    if unsealed:
        meta.pop("terminal_source_seal", None)
        meta.pop("terminal_source_seal_inputs", None)
    (dst / "scan.json").write_text(json.dumps(meta))
    return dst


def _rewrite_cube(run: Path, edit: Any) -> None:
    with gzip.open(run / "cube.csv.gz", "rt", newline="") as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0])
    rows = edit(rows)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    with gzip.open(run / "cube.csv.gz", "wt", newline="") as f:
        f.write(buf.getvalue())


def _meas_never(*_a: Any) -> dict[str, Any]:
    raise AssertionError("resume must refuse before any MEAS")


def _corrupt(run: Path, case: str) -> None:
    if case == "missing_detector":
        _rewrite_cube(run, lambda rows: rows[:-1])
    elif case == "changed_condition":

        def edit(rows: list[dict[str, str]]) -> list[dict[str, str]]:
            rows[3]["condition_id"] = "blocked"
            return rows

        _rewrite_cube(run, edit)
    else:
        _rewrite_cube(run, lambda rows: rows + rows[-2:])


@pytest.mark.parametrize("case", ["missing_detector", "changed_condition", "duplicate"])
def test_resume_refuses_bad_existing_seal(cfg: HwConfig, tmp_path: Path, case: str) -> None:
    if not P2.is_dir():
        pytest.skip("P2 archive not present")
    run = _incomplete_copy(tmp_path, cfg)
    _corrupt(run, case)
    with pytest.raises(ProtocolError, match="terminal seal invalid"):
        resume_protocol(run, cfg=cfg, allow_light=True, meas=_meas_never)
    meta = json.loads((run / "scan.json").read_text())
    assert meta["status"] == "INCOMPLETE" and meta.get("terminal_source_seal")  # not resealed


@pytest.mark.parametrize(
    "case,msg",
    [("missing_detector", "detector rows"), ("changed_condition", "condition_id"),
     ("duplicate", "detector rows")],
)  # fmt: skip
def test_resume_validates_rows_when_unsealed(
    cfg: HwConfig, tmp_path: Path, case: str, msg: str
) -> None:
    if not P2.is_dir():
        pytest.skip("P2 archive not present")
    run = _incomplete_copy(tmp_path, cfg, unsealed=True)
    _corrupt(run, case)
    with pytest.raises(ProtocolError, match=msg):
        resume_protocol(run, cfg=cfg, allow_light=True, meas=_meas_never)
    assert json.loads((run / "scan.json").read_text())["status"] == "INCOMPLETE"


def test_legal_unsealed_crash_resumes_remaining_steps(cfg: HwConfig, tmp_path: Path) -> None:
    proto = json.loads((REPO / "software/host/src/lio/scan/examples/stationary_targeted_h12.json")
                       .read_text())  # fmt: skip
    proto.update(holes=[8, 12], detectors=["ingaas", "opt101"],
                 blocks={"n_production": 2, "n_pilot": 0, "n_production_min": 1,
                         "n_production_max": 8},
                 allocation={"policy": "equal_fixed", "control_holes": [],
                             "target_weights": {"8": 1.0, "12": 1.0}},
                 operator_checkpoints=[])  # fmt: skip
    plan = plan_protocol(proto, cfg)
    calls = {"n": 0}

    def meas(hole: int, settle: int, n: int) -> dict[str, Any]:
        calls["n"] += 1
        return {
            "hole": hole,
            "t_on_ms": 5.0,
            "dark_ingaas": 0.0,
            "lit_ingaas": 3.0,
            "net_ingaas": 3.0,
            "dark_opt101": 0.0,
            "lit_opt101": 9.0,
            "net_opt101": 9.0,
        }

    first = run_protocol(plan, cfg=cfg, root=tmp_path, sample_id="empty", allow_light=True,
                         meas=meas, cancel_check=lambda: calls["n"] >= 2, simulated=True)  # fmt: skip
    # Simulate a crash: process died while RUNNING, so no terminal seal exists.
    meta = json.loads((first.folder / "scan.json").read_text())
    meta["status"] = "RUNNING"
    meta.pop("terminal_source_seal", None)
    meta.pop("terminal_source_seal_inputs", None)
    (first.folder / "scan.json").write_text(json.dumps(meta))
    before = calls["n"]
    res = resume_protocol(first.folder, cfg=cfg, allow_light=True, meas=meas)
    assert res.status == "COMPLETE"
    assert calls["n"] - before == len(plan.steps) - 2  # only the remaining steps
    meta = json.loads((first.folder / "scan.json").read_text())
    assert meta["recovery"][0]["kind"] == "unsealed_crash_recovery"
    segs = [s["segment"] for s in meta["segments"]]
    assert segs == ["stationary:s0", "stationary:s1"]
    kinds = [e["kind"] for e in meta["events"]]
    assert kinds.count("segment_start") == 2 and "segment_end" in kinds
    rows = list(ScanStore.open(first.folder).rows())
    assert {r["segment"] for r in rows} == {"stationary:s0", "stationary:s1"}
    assert len({r["reading_id"] for r in rows}) == len(plan.steps)


# ------------------------------------------------------------------- S7 guard


def test_physical_stage_write_is_guarded(tmp_path: Path) -> None:
    assert os.environ.get("LIO_GUARD_PHYSICAL_STAGE") == "1"
    phys = REPO / "test_results" / "stage_position.json"
    before = phys.read_bytes() if phys.exists() else None
    tr = StageTracker(phys)
    with pytest.raises(PhysicalStageWriteError):
        tr.set_top((0, 0))
    assert (phys.read_bytes() if phys.exists() else None) == before
    ok = StageTracker(tmp_path / "stage_position.json")
    ok.set_top((0, 0))  # synthetic state still works
