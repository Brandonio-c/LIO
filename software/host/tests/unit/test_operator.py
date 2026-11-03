from __future__ import annotations

from collections.abc import Iterator

import pytest

from lio.config import HwConfig
from lio.operator import Abort, ConsoleOperator, SimOperator
from lio.results import Status
from lio.sim import SimulatedLIO
from lio.suite.core import REGISTRY, SuiteContext, catalogue, run_test
from lio.suite.runner import serial_context, sim_context
from lio.transport import SimTransport

pytestmark = pytest.mark.unit


def scripted(*answers: str) -> tuple[ConsoleOperator, list[str]]:
    said: list[str] = []
    it = iter(answers)
    return ConsoleOperator(lambda prompt: next(it), said.append), said


class TestConsoleOperator:
    def test_confirm_retries_until_yes_or_no(self) -> None:
        op, said = scripted("maybe", "Y")
        assert op.confirm("k", "ok?") is True
        assert any("y or n" in s for s in said)
        assert scripted("no")[0].confirm("k", "ok?") is False

    def test_number(self) -> None:
        op, _ = scripted("thirty", "29.5")
        assert op.number("k", "current", "mA") == 29.5
        assert scripted("")[0].number("k", "current", "mA") is None

    @pytest.mark.parametrize("call", ["act", "confirm", "number", "text"])
    def test_abort_everywhere(self, call: str) -> None:
        op, _ = scripted("a")
        with pytest.raises(Abort):
            if call == "number":
                op.number("k", "p", "mA")
            else:
                getattr(op, call)("k", "p")

    def test_inform_and_text(self) -> None:
        op, said = scripted("hole 4 dim")
        op.inform("hello")
        assert said == ["\n[LIO] hello"]
        assert op.text("k", "remark") == "hole 4 dim"


@pytest.fixture
def ctx(cfg: HwConfig) -> Iterator[SuiteContext]:
    c = sim_context(cfg)
    yield c
    c.dev.close()


class TestGating:
    def test_hardware_without_operator_skips_interactive_and_motion(self, cfg: HwConfig) -> None:
        catalogue()
        sim = SimulatedLIO(cfg)
        c = serial_context(cfg, "sim", transport=SimTransport(sim))
        try:
            for tid in ("T04.4", "T09.2"):
                r = run_test(c, REGISTRY[tid])
                assert r.status == Status.SKIP and "operator" in r.message
            assert sim.motors[0].physical == 0
        finally:
            c.dev.close()

    def test_motion_needs_allow_motion_even_with_operator(self, cfg: HwConfig) -> None:
        catalogue()
        sim = SimulatedLIO(cfg)
        c = serial_context(cfg, "sim", transport=SimTransport(sim), operator=SimOperator(sim))
        try:
            r = run_test(c, REGISTRY["T09.3"])
            assert r.status == Status.SKIP and "--allow-motion" in r.message
            assert sim.motors[0].physical == 0
        finally:
            c.dev.close()

    def test_abort_skips_and_leaves_everything_off(self, cfg: HwConfig) -> None:
        catalogue()
        c = sim_context(cfg, answers={"meter_ready:A": "abort"})
        try:
            r = run_test(c, REGISTRY["T05.6"])
            assert r.status == Status.SKIP and "aborted" in r.message
            st = c.dev.status()
            assert st.as_int("ch") == 0 and st.as_int("ce1") == 0
        finally:
            c.dev.close()

    def test_chamber_not_clear_means_no_motion(self, cfg: HwConfig) -> None:
        catalogue()
        c = sim_context(cfg, answers={"chamber_clear": False})
        try:
            r = run_test(c, REGISTRY["T09.2"])
            assert r.status == Status.SKIP and "chamber" in r.message
            assert c.sim is not None and c.sim.motors[0].physical == 0
        finally:
            c.dev.close()

    def test_wrong_meter_reading_fails(self, cfg: HwConfig) -> None:
        catalogue()
        c = sim_context(cfg, answers={"meter_ma:A": 12.0, "meter_ma:B": 47.0})
        try:
            r = run_test(c, REGISTRY["T05.6"])
            assert r.sub("T05.6/A/h08").status == Status.FAIL
            assert r.sub("T05.6/B/h12").status == Status.PASS
        finally:
            c.dev.close()

    def test_skipped_reading(self, cfg: HwConfig) -> None:
        catalogue()
        c = sim_context(cfg, answers={"meter_ma:A": None, "meter_ma:B": None})
        try:
            r = run_test(c, REGISTRY["T05.6"])
            assert r.status == Status.SKIP
        finally:
            c.dev.close()

    def test_ambient_recorded(self, ctx: SuiteContext) -> None:
        catalogue()
        r = run_test(ctx, REGISTRY["T06.4"])
        assert r.status == Status.PASS
        assert r.sub("T06.4/opt101").measured["delta_counts"] > 1000
        assert ctx.sim is not None and not ctx.sim.chamber_open
