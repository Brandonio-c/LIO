"""S1: realistic low-count repeatability through the actual T05.5 / T08.2 callers.

Labelled synthetic fixtures are injected at the transport (firmware reply lines
rewritten per hole and repeat); the test runner, Recorder and judgement run
unmocked. Synthetic results exercise the software path only.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import pytest

from lio.analysis import precision_summary
from lio.config import HwConfig, load_config
from lio.device import LIODevice
from lio.operator import SimOperator
from lio.results import Status
from lio.sim import SimulatedLIO
from lio.suite.core import REGISTRY, SuiteContext, catalogue, run_test
from lio.transport import SimTransport

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
CFG = REPO / "software" / "config" / "lio_hw.yaml"

STABLE = [50, 51, 49, 50, 52, 48, 50, 51, 49, 50]
UNSTABLE = [50, 90, 10, 70, 30, 85, 15, 60, 40, 55]


@pytest.fixture()
def cfg() -> HwConfig:
    return load_config(CFG)


class Fixture(SimTransport):
    """Rewrites OPT101 MEAS replies for labelled holes (dark 100 + net)."""

    def __init__(self, sim: SimulatedLIO, cfg: HwConfig) -> None:
        super().__init__(sim)
        self.count: dict[int, int] = defaultdict(int)
        self.sat = int(cfg.detectors["opt101"].saturation_counts)
        self.active = False

    def read_line(self, timeout: float) -> str | None:
        line = super().read_line(timeout)
        if not self.active or line is None:
            return line
        m = re.match(r"^(@\d+ )OK MEAS ch=(\d+) (.*)$", line)
        if not m:
            return line
        hole, rest = int(m.group(2)), m.group(3)
        i = self.count[hole]
        self.count[hole] += 1
        if hole == 2 and i == 3:
            return f"{m.group(1)}ERR MEAS code=4 msg=fixture-dropout"
        net = {4: STABLE[i % 10], 5: UNSTABLE[i % 10], 6: 0, 7: -5}.get(hole)
        lit = None if net is None else 100 + net
        if hole == 11:
            lit = self.sat
        if lit is None:
            return line
        rest = re.sub(r"dark1=-?\d+", "dark1=100", rest)
        rest = re.sub(r"lit1=-?\d+", f"lit1={lit}", rest)
        return f"{m.group(1)}OK MEAS ch={hole} {rest}"


def _ctx(cfg: HwConfig) -> tuple[SuiteContext, Fixture]:
    sim = SimulatedLIO(cfg)
    t = Fixture(sim, cfg)
    dev = LIODevice(t, cfg)
    dev.open()
    return SuiteContext(dev, cfg, "sim", sim, interactive=True, allow_motion=True,
                        operator=SimOperator(sim)), t  # fmt: skip


def test_t05_5_low_count_precision_fixtures(cfg: HwConfig) -> None:
    catalogue()
    ctx, t = _ctx(cfg)
    try:
        t.active = True
        r = run_test(ctx, REGISTRY["T05.5"])
    finally:
        t.active = False
        ctx.dev.close()
    sub = {s.id.split("/", 1)[1]: s for s in r.subs}
    stable = sub["h04/opt101"]
    assert stable.status == Status.PASS
    ps = stable.measured["summary"]
    assert ps["n_observed"] == 10 and ps["mean"] == pytest.approx(50.0)
    assert ps["cv"] == pytest.approx(ps["sd"] / 50.0)
    assert sub["h05/opt101"].status == Status.FAIL  # unstable detected
    zero = sub["h06/opt101"]
    assert zero.status == Status.PASS and zero.measured["summary"]["cv"] is None
    assert "not resolved" in zero.measured["summary"]["cv_reason"]
    neg = sub["h07/opt101"]
    assert neg.measured["summary"]["mean"] == pytest.approx(-5.0)
    assert neg.measured["summary"]["signal_resolved"] is False
    drop = sub["h02/opt101"]
    assert drop.status == Status.FAIL and drop.measured["summary"]["dropouts"] == 1
    assert drop.measured["summary"]["values"][3] is None
    assert sub["h11/opt101"].status == Status.SKIP  # saturated: precision unavailable
    # No first-reading preselection: every expected pair was attempted N times.
    planned = r.measured["planned"]
    assert planned["repeats"] == 10 and "4/opt101" in planned["pairs"]
    # Survives serialisation (save/reopen/report use this dict form).
    from dataclasses import asdict

    back = json.loads(json.dumps(asdict(r), default=str))
    assert back["measured"]["repeats"]["4/opt101"]["status"] == "stable"


def test_zero_evaluated_channels_is_skip_not_pass(cfg: HwConfig) -> None:
    catalogue()
    ctx, _t = _ctx(cfg)
    ctx.cfg.data["thresholds"]["repeatability"]["repeats"] = 1  # too few to evaluate
    try:
        r = run_test(ctx, REGISTRY["T05.5"])
    finally:
        ctx.cfg.data["thresholds"]["repeatability"]["repeats"] = 10
        ctx.dev.close()
    assert r.status == Status.SKIP and "not a precision PASS" in r.message


def test_t08_2_variable_nets_cannot_pass_on_dark_stability(cfg: HwConfig) -> None:
    catalogue()
    sim = SimulatedLIO(cfg)

    class Wild(SimTransport):
        k = 0

        def read_line(self, timeout: float) -> str | None:
            line = super().read_line(timeout)
            if line and line.startswith("# M ch=8 "):
                Wild.k += 1
                line = re.sub(r"lit0=-?\d+", f"lit0={[100, 400, -300, 250, -150][Wild.k % 5]}",
                              line)  # fmt: skip
            return line

    dev = LIODevice(Wild(sim), cfg)
    dev.open()
    ctx = SuiteContext(dev, cfg, "sim", sim)
    try:
        r = run_test(ctx, REGISTRY["T08.2"])
    finally:
        dev.close()
    subs = {s.id: s for s in r.subs}
    assert subs["T08.2/net/h08/ingaas"].status == Status.FAIL
    assert all(s.status != Status.FAIL for k, s in subs.items() if "/dark/" in k)
    assert r.status == Status.FAIL


def test_precision_summary_distinguishes_states() -> None:
    kw = {"sd_max": 5.0, "cv_max": 0.02, "cv_min_mean": 20.0}
    assert precision_summary([1.0], **kw)["status"] == "insufficient"
    assert precision_summary([50.0, None, 51.0], **kw)["status"] == "dropouts"
    assert precision_summary([50.0, 51.0], saturated=True, **kw)["status"] == "saturated"
    neg = precision_summary([-5.0, -5.0, -6.0], **kw)
    assert neg["status"] == "stable" and neg["cv"] is None
