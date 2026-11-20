"""Chamber-top position tracking (lio.stage) and its soft limits, on the simulator."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from lio.config import HwConfig, parse_config
from lio.device import LIODevice
from lio.results import Status
from lio.sim import Faults, SimulatedLIO
from lio.stage import StageError, StageTracker
from lio.suite.core import REGISTRY, SuiteContext, catalogue, run_test
from lio.suite.runner import sim_context
from lio.transport import SimTransport

pytestmark = [pytest.mark.sim]


@pytest.fixture
def cfg(cfg: HwConfig) -> HwConfig:
    """The repo config with a small top margin, to suit the short simulated travel."""
    data = copy.deepcopy(cfg.data)
    data["stage"]["top_margin_steps"] = 64
    return parse_config(data, cfg.path)


def _dev(cfg: HwConfig, path: Path, sim: SimulatedLIO | None = None) -> LIODevice:
    sim = sim or SimulatedLIO(cfg, Faults.parse(None))
    dev = LIODevice(SimTransport(sim), cfg, stage=StageTracker(path))
    dev.open()
    return dev


def _move(dev: LIODevice, motor: int, steps: int) -> None:
    dev.motor_arm()
    dev.motor_step(motor, steps, 15)
    ev = dev.wait_motor_done(motor, 30)
    assert ev is not None


def test_tracker_basics(tmp_path: Path) -> None:
    tr = StageTracker(tmp_path / "s.json")
    assert not tr.known
    tr.rebase(0, 0)
    tr.observe(10, 10)  # unknown position: nothing recorded
    assert tr.abs is None
    tr.set_top((5, 7))
    tr.observe(5 - 300, 7 - 300)
    assert tr.abs == (-300, -300)
    tr.mark_bottom()
    assert tr.limits.bottom == (-300, -300)
    with pytest.raises(StageError):
        tr.check_move(1, -1)  # below the bottom
    with pytest.raises(StageError):
        tr.check_move(1, 300, margin_top=64)  # into the top margin
    tr.check_move(1, 236, margin_top=64)  # exactly to top - margin
    again = StageTracker(tmp_path / "s.json")  # persisted
    assert again.abs == (-300, -300) and again.summary()["range"] == [300, 300]


def test_set_top_rebases_bottom_to_keep_physical_height(tmp_path: Path) -> None:
    """Redefining top lower (e.g. after light leaked at the old top) must shorten
    the marked travel, not leave the old bottom and invent extra downward range."""
    tr = StageTracker(tmp_path / "s.json")
    tr.set_top((0, 0))
    tr.observe(-400000, -400000)
    tr.mark_bottom()
    assert tr.limits.bottom == (-400000, -400000)
    # Operator lowers to a light-tight height and sets top there.
    tr.observe(-90000, -90000)
    tr.set_top((10, 10))
    assert tr.abs == (0, 0)
    assert tr.limits.bottom == (-310000, -310000)
    assert tr.summary()["range"] == [310000, 310000]


def test_position_survives_reconnect_and_reset(cfg: HwConfig, tmp_path: Path) -> None:
    path = tmp_path / "stage.json"
    sim = SimulatedLIO(cfg, Faults.parse(None))
    dev = _dev(cfg, path, sim)
    dev.stage_set_top()
    _move(dev, 1, -400)
    _move(dev, 2, -400)
    dev.status()
    assert dev.stage is not None and dev.stage.abs == (-400, -400)
    dev.reset()  # firmware counters back to 0
    assert dev.status().as_int("pos1") == 0
    _move(dev, 1, -100)
    dev.status()
    assert dev.stage.abs == (-500, -400)
    dev.close()
    dev2 = LIODevice(SimTransport(SimulatedLIO(cfg, Faults.parse(None))), cfg,
                     stage=StageTracker(path))  # fmt: skip
    dev2.open()  # a new session: counters 0, position carried on
    _move(dev2, 2, -100)
    dev2.status()
    assert dev2.stage is not None and dev2.stage.abs == (-500, -500)
    dev2.close()


def test_soft_limits_refuse_before_sending(cfg: HwConfig, tmp_path: Path) -> None:
    dev = _dev(cfg, tmp_path / "stage.json")
    dev.stage_set_top()
    dev.motor_arm()
    with pytest.raises(StageError):
        dev.motor_step(1, +100, 15)  # above the top (margin 64)
    _move(dev, 1, -300)
    _move(dev, 2, -300)
    dev.stage_mark_bottom()
    with pytest.raises(StageError):
        dev.motor_step(1, -1, 15)
    assert dev.status().as_str("motor1") == "idle"
    dev.close()


def test_full_travel_uses_tracked_limits(cfg: HwConfig, tmp_path: Path) -> None:
    catalogue()
    sim = SimulatedLIO(cfg, Faults.parse(None))
    ctx = sim_context(cfg)
    ctx.dev.close()
    dev = _dev(cfg, tmp_path / "stage.json", sim)
    dev.stage_set_top()
    _move(dev, 1, -1500)
    _move(dev, 2, -1500)
    dev.stage_mark_bottom()
    _move(dev, 1, +700)  # start somewhere in the middle: the test must go down first
    _move(dev, 2, +700)
    tctx = SuiteContext(dev, cfg, "sim", interactive=True, allow_motion=True,
                        operator=ctx.operator)  # fmt: skip
    renewals0 = [m.renewals for m in sim.motors]
    r = run_test(tctx, REGISTRY["T09.6"])
    assert r.status in (Status.PASS, Status.WARN), r.summary()
    assert next(s for s in r.subs if s.id == "T09.6/top").status == Status.PASS
    # long moves are one continuous jog, renewed without stopping
    assert all(m.renewals > r0 for m, r0 in zip(sim.motors, renewals0, strict=True))
    dev.status()
    assert dev.stage is not None and dev.stage.abs == (-1500, -1500)  # back at the bottom
    dev.close()


def test_bottom_not_marked_skips(cfg: HwConfig, tmp_path: Path) -> None:
    catalogue()
    ctx = sim_context(cfg)
    ctx.dev.close()
    dev = _dev(cfg, tmp_path / "stage.json")
    dev.stage_set_top()
    tctx = SuiteContext(dev, cfg, "sim", interactive=True, allow_motion=True, operator=ctx.operator)
    r = run_test(tctx, REGISTRY["T09.6"])
    assert r.status == Status.SKIP and "bottom of travel not marked" in r.message
    dev.close()
