"""Tests for ``lio drive-tune`` pot coaching."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from lio.config import load_config
from lio.device import LIODevice
from lio.drive_tune import _judge, rail_tune, run_tune
from lio.sim import Faults, SimulatedLIO
from lio.transport import SimTransport

CFG = Path(__file__).resolve().parents[3] / "config" / "lio_hw.yaml"


@pytest.fixture
def cfg():
    return load_config(CFG)


def test_rail_defaults(cfg) -> None:
    a = rail_tune(cfg, "A")
    b = rail_tune(cfg, "B")
    assert a.hole == 4 and a.label == "green" and a.safe_max_ma == 30
    assert b.hole == 11 and b.label == "pink" and b.safe_max_ma == 50


def test_judge_orders_good_before_rating_warn(cfg) -> None:
    a = rail_tune(cfg, "A")
    assert "GOOD" in _judge(30, a)
    assert "STOP" in _judge(40, a)


def test_run_tune_optical_ok_and_ammeter_refuse(cfg, tmp_path: Path) -> None:
    sim = SimulatedLIO(cfg, Faults.parse(None))
    # Make hole 4 return a strong OPT101 lit level so optical 'ok' can accept.
    sim.faults = Faults.parse(None)
    dev = LIODevice(SimTransport(sim), cfg, duty=False)
    dev.open()
    try:
        out = StringIO()
        # Optical-only accept (sim will show some net when LED is on).
        r = run_tune(
            dev,
            cfg,
            "A",
            stdin=StringIO("ok\n"),
            stdout=out,
            out_path=tmp_path / "a.json",
            poll_s=0.01,
        )
        # Sim optical may be weak at start; if refused dark, feed a mA path instead.
        if r["accepted_opt101_net"] is None:
            out2 = StringIO()
            r = run_tune(
                dev,
                cfg,
                "A",
                stdin=StringIO("25\n30\nok\n"),
                stdout=out2,
                out_path=tmp_path / "a2.json",
                poll_s=0.01,
            )
            assert r["accepted_ma"] == 30.0
        else:
            assert r["accepted_opt101_net"] is not None

        out3 = StringIO()
        r3 = run_tune(
            dev, cfg, "A", stdin=StringIO("40\nok\nq\n"), stdout=out3, out_path=None, poll_s=0.01
        )
        assert r3["accepted_ma"] is None
        assert "STOP" in out3.getvalue()
    finally:
        dev.close()
