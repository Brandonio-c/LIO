"""The catalogue machinery: registry, recorder, runner error handling, metadata."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from lio.config import HwConfig
from lio.device import DeviceError
from lio.results import Status
from lio.suite import core
from lio.suite.core import Recorder, Skip, SuiteContext, TestDef, catalogue, run_test
from lio.suite.runner import metadata, sim_context

pytestmark = pytest.mark.unit

SYSTEM_TESTS = Path(__file__).resolve().parents[1] / "system"


@pytest.fixture
def ctx(cfg: HwConfig) -> Iterator[SuiteContext]:
    c = sim_context(cfg)
    yield c
    c.dev.close()


def _def(fn: object, test_id: str = "T99.1") -> TestDef:
    return TestDef(test_id, "probe", "A", fn)  # type: ignore[arg-type]


class TestRegistry:
    def test_catalogue_order_and_ids(self) -> None:
        ids = [t.id for t in catalogue()]
        assert ids[0] == "T01.1" and ids[-1] == "T10.5"
        assert ids == sorted(ids, key=lambda i: tuple(int(x) for x in i[1:].split(".")))
        assert {t.kind for t in catalogue()} == {"A"}  # I and M arrive in M4

    def test_every_id_has_one_pytest_function(self) -> None:
        """Plan §6: every test ID maps to one pytest function."""
        src = "\n".join(p.read_text() for p in SYSTEM_TESTS.glob("test_t*.py"))
        called = re.findall(r'run_suite\("(T\d\d\.\d)"\)', src)
        assert sorted(called) == sorted(t.id for t in catalogue())
        assert len(called) == len(set(called))

    def test_duplicate_id_rejected(self) -> None:
        catalogue()
        with pytest.raises(ValueError, match="duplicate"):
            core.register("T01.1", "again")(lambda ctx, rec: None)


class TestRunner:
    def test_pass_and_restore(self, ctx: SuiteContext) -> None:
        def fn(c: SuiteContext, rec: Recorder) -> None:
            c.dev.wdt_cfg("A", 100)
            c.dev.sr_raw(0x0004)
            rec.check("x", "probe", True, "ok")

        r = run_test(ctx, _def(fn))
        assert r.status == Status.PASS and r.subs[0].id == "T99.1/x"
        st = ctx.dev.status()
        assert st.as_int("mask") == 0
        assert ctx.dev.info(refresh=True).as_int("wdt_a_ms") == ctx.cfg.wdt_ms("A")

    def test_no_subs_is_pass(self, ctx: SuiteContext) -> None:
        assert run_test(ctx, _def(lambda c, rec: None)).status == Status.PASS

    def test_skip(self, ctx: SuiteContext) -> None:
        def fn(c: SuiteContext, rec: Recorder) -> None:
            rec.skip("not today")

        r = run_test(ctx, _def(fn))
        assert r.status == Status.SKIP and r.message == "not today"

    def test_warn(self, ctx: SuiteContext) -> None:
        def fn(c: SuiteContext, rec: Recorder) -> None:
            rec.check("a", "a", True)
            rec.check("b", "b", False, warn=True)

        assert run_test(ctx, _def(fn)).status == Status.WARN

    @pytest.mark.parametrize(
        "exc", [DeviceError("X", 3, "no"), TimeoutError("slow"), RuntimeError("bug")]
    )
    def test_exceptions_become_error(self, ctx: SuiteContext, exc: Exception) -> None:
        def fn(c: SuiteContext, rec: Recorder) -> None:
            raise exc

        r = run_test(ctx, _def(fn))
        assert r.status == Status.ERROR and type(exc).__name__ in r.message

    def test_restore_failure_is_error(
        self, ctx: SuiteContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def broken() -> None:
            raise OSError("port gone")

        monkeypatch.setattr(ctx, "restore", broken)
        r = run_test(ctx, _def(lambda c, rec: None))
        assert r.status == Status.ERROR and "restore" in r.message

    def test_recorder_measure_note_artefact(self, ctx: SuiteContext) -> None:
        def fn(c: SuiteContext, rec: Recorder) -> None:
            rec.measure(a=1)
            rec.note("first")
            rec.note("second")
            rec.artefact("plots/x.png")

        r = run_test(ctx, _def(fn))
        assert r.measured == {"a": 1} and r.message == "first; second"
        assert r.artefacts == ["plots/x.png"]


class TestContext:
    def test_shared_measurements_are_cached(self, ctx: SuiteContext) -> None:
        assert ctx.dark() is ctx.dark()
        assert ctx.channels() is ctx.channels()
        assert ctx.gate().ok and ctx.usable("ingaas") and ctx.usable("opt101")
        assert len(ctx.meas_log) == 17  # gate + 16 holes

    def test_no_adc_skips(self, cfg: HwConfig) -> None:
        c = sim_context(cfg, "no_adc")
        try:
            assert not c.has_adc()
            with pytest.raises(Skip, match="ADS1115"):
                c.dark()
        finally:
            c.dev.close()

    @pytest.mark.parametrize(
        ("fault", "det", "why"),
        [
            ("reversed_ingaas", "ingaas", "polarity"),
            ("no_neg_rail", "ingaas", "erratic"),
            ("opt101_no_feedback", "opt101", "pinned high"),
        ],
    )
    def test_unusable_detector(self, cfg: HwConfig, fault: str, det: str, why: str) -> None:
        c = sim_context(cfg, fault)
        try:
            assert why in c.unusable(det)
            other = "opt101" if det == "ingaas" else "ingaas"
            assert c.usable(other)
        finally:
            c.dev.close()


class TestMetadata:
    def test_defaults(self, cfg: HwConfig) -> None:
        m = metadata(cfg)
        assert m["sample_id"] == "none-empty-chamber" and m["operator"] == "unknown"

    def test_given_values_win(self, cfg: HwConfig) -> None:
        assert metadata(cfg, {"sample_id": "ref-1", "operator": ""})["sample_id"] == "ref-1"

    def test_required(self, cfg: HwConfig, monkeypatch: pytest.MonkeyPatch) -> None:
        sec = cfg.section
        real = sec.mapping

        def no_defaults(path: str) -> dict[str, object]:
            return {} if path == "run_metadata.defaults" else real(path)

        monkeypatch.setattr(sec, "mapping", no_defaults)
        monkeypatch.setattr(type(cfg), "section", property(lambda self: sec))
        with pytest.raises(ValueError, match="sample_id"):
            metadata(cfg)
