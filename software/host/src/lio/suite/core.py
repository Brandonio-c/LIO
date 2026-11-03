"""Test-catalogue machinery: registry, recorder, shared context and runner.

Each catalogue entry (plan §6) is a function ``fn(ctx, rec)`` registered with
:func:`register`. It talks to the device only through ``ctx.dev`` and records
sub-results through ``rec``. Thresholds come from ``ctx.th`` (``lio_hw.yaml``).

Expensive shared measurements (dark statistics, the 16-channel matrix, the
polarity gate) are computed once per run on first use, so every test can also
run on its own.
"""

from __future__ import annotations

import logging
import math
import time
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, NoReturn

from lio.analysis import Stats, detect_level
from lio.config import HwConfig, Section
from lio.device import DeviceError, LIODevice, Meas, NoResponse
from lio.operator import Abort, Operator
from lio.results import Status, SubResult, TestResult, worst
from lio.sim import SimulatedLIO

log = logging.getLogger(__name__)

DETECTORS = ("ingaas", "opt101")


class Skip(Exception):
    """Raised by a test (or a shared measurement) to skip the whole test."""


# ------------------------------------------------------------------- registry


@dataclass(frozen=True)
class TestDef:
    __test__ = False  # not a pytest test class

    id: str
    name: str
    kind: str  # A automatic | I interactive | M motion
    fn: Callable[[SuiteContext, Recorder], None]

    @property
    def module(self) -> str:
        return self.id.split(".")[0]


REGISTRY: dict[str, TestDef] = {}


def register(test_id: str, name: str, kind: str = "A") -> Callable[[Any], Any]:
    def deco(
        fn: Callable[[SuiteContext, Recorder], None],
    ) -> Callable[[SuiteContext, Recorder], None]:
        if test_id in REGISTRY:
            raise ValueError(f"duplicate test id {test_id}")
        REGISTRY[test_id] = TestDef(test_id, name, kind, fn)
        return fn

    return deco


def catalogue() -> list[TestDef]:
    """All registered tests in catalogue order (T01.1, T01.2, ..., T10.5)."""
    import lio.suite.checks  # noqa: F401  (registers the catalogue)

    def key(t: TestDef) -> tuple[int, int]:
        mod, sub = t.id[1:].split(".")
        return int(mod), int(sub)

    return sorted(REGISTRY.values(), key=key)


# ------------------------------------------------------------------- recorder


class Recorder:
    """Collects the sub-results and measurements of one test."""

    def __init__(self, result: TestResult) -> None:
        self.result = result

    def add(
        self,
        sub_id: str,
        name: str,
        status: Status,
        message: str = "",
        criteria: str = "",
        **measured: Any,
    ) -> SubResult:
        sub = SubResult(f"{self.result.id}/{sub_id}", name, status, message, criteria, measured)
        self.result.subs.append(sub)
        return sub

    def check(
        self,
        sub_id: str,
        name: str,
        ok: bool,
        message: str = "",
        criteria: str = "",
        *,
        warn: bool = False,
        **measured: Any,
    ) -> bool:
        """PASS if ``ok``, otherwise FAIL (or WARN with ``warn=True``)."""
        status = Status.PASS if ok else (Status.WARN if warn else Status.FAIL)
        self.add(sub_id, name, status, message, criteria, **measured)
        return ok

    def measure(self, **values: Any) -> None:
        self.result.measured.update(values)

    def note(self, message: str) -> None:
        self.result.message = (
            f"{self.result.message}; {message}" if self.result.message else message
        )

    def artefact(self, path: str) -> None:
        self.result.artefacts.append(path)

    @staticmethod
    def skip(reason: str) -> NoReturn:
        raise Skip(reason)


def hole_id(hole: int) -> str:
    return f"h{hole:02d}"


def skip_unusable(ctx: SuiteContext, rec: Recorder, det: str, sub: str, name: str) -> bool:
    """Record a SKIP for a judgment on an unusable detector; True if skipped."""
    why = ctx.unusable(det)
    if why:
        rec.add(sub, name, Status.SKIP, f"{why} (see T06)")
    return bool(why)


# -------------------------------------------------------------------- context


@dataclass(frozen=True)
class DarkStats:
    """Everything-off ADC statistics (T03.2), single-reading sigma per detector."""

    by_detector: dict[str, Stats]

    def mean(self, det: str) -> float:
        return self.by_detector[det].mean

    def sigma(self, det: str) -> float:
        return max(self.by_detector[det].std, 1.0)

    def net_sigma(self, det: str, n: int) -> float:
        """Sigma of (mean of n lit) - (mean of n dark)."""
        return self.sigma(det) * math.sqrt(2.0 / n)


@dataclass(frozen=True)
class ChannelData:
    """One hole of the channel matrix: MEAS plus the off-state reading after it."""

    meas: Meas
    after: dict[str, float]  # detector -> mean reading after OFF + settle (T05.4)


@dataclass(frozen=True)
class Gate:
    """Result of the hole-8 InGaAs polarity gate (approved M0 proposal 6)."""

    ok: bool
    hole: int
    net: int
    sigma: float
    message: str


@dataclass
class SuiteContext:
    dev: LIODevice
    cfg: HwConfig
    target: str  # "sim" or the serial port
    sim: SimulatedLIO | None = None
    interactive: bool = False
    allow_motion: bool = False
    operator: Operator | None = None
    baseline: dict[str, Any] | None = None  # lio.baseline.load(), for T11.1
    cache: dict[str, Any] = field(default_factory=dict)
    meas_log: list[tuple[str, Meas]] = field(default_factory=list)  # (test id, record)
    current: str = ""

    @property
    def th(self) -> Section:
        return self.cfg.thresholds

    @property
    def is_sim(self) -> bool:
        return self.sim is not None

    def adc_channel(self, det: str) -> int:
        return self.cfg.detectors[det].adc_channel

    # ------------------------------------------------------- measurements

    def log_meas(self, m: Meas) -> Meas:
        self.meas_log.append((self.current, m))
        return m

    def meas(self, hole: int, n: int | None = None, settle_ms: int | None = None) -> Meas:
        return self.log_meas(self.dev.meas(hole, settle_ms=settle_ms, n=n))

    def has_adc(self) -> bool:
        if "adc_ok" not in self.cache:
            self.cache["adc_ok"] = self.dev.info().as_int("adc_ok") == 1
        ok: bool = self.cache["adc_ok"]
        return ok

    def require_adc(self) -> None:
        if not self.has_adc():
            raise Skip("the ADS1115 is not responding (see T03.1)")

    def dark(self) -> DarkStats:
        """Everything-off statistics on both detectors (measured once, by T03.2)."""
        if "dark" not in self.cache:
            self.require_adc()
            self.dev.off()
            n = self.th.integer("adc.dark_samples")
            out: dict[str, Stats] = {}
            for det in DETECTORS:
                r = self.dev.adc_read(self.adc_channel(det), n)
                std = r.std if r.std is not None else 0.0
                out[det] = Stats(r.n, r.mean, std, r.mean - 3 * std, r.mean + 3 * std)
            self.cache["dark"] = DarkStats(out)
        dark: DarkStats = self.cache["dark"]
        return dark

    def is_dark(self, det: str, reading: float, n: int = 1) -> bool:
        """Reading (mean of n) is within dark +- off_return_sigma."""
        d = self.dark()
        k = self.th.num("channel.off_return_sigma")
        return abs(reading - d.mean(det)) <= k * d.sigma(det) / math.sqrt(n)

    def is_lit(self, det: str, reading: float, n: int = 1) -> bool:
        """Reading (mean of n) is above dark by the signal detection threshold."""
        d = self.dark()
        det_ = detect_level(
            reading - d.mean(det),
            d.sigma(det) / math.sqrt(n),
            detect_sigma=self.th.num("channel.detect_sigma"),
            detect_min=self.th.num("channel.detect_min_counts"),
            weak_sigma=self.th.num("channel.detect_sigma"),
            weak_min=self.th.num("channel.detect_min_counts"),
        )
        return det_.level == "signal"

    def gate(self) -> Gate:
        """InGaAs polarity check on the gate hole, before any InGaAs judgment."""
        if "gate" not in self.cache:
            self.require_adc()
            hole = self.cfg.section.integer("polarity_gate_hole")
            n = self.th.integer("channel.meas_n")
            m = self.meas(hole, n=n)
            sigma = self.dark().net_sigma("ingaas", n)
            k = self.th.num("channel.polarity_sigma")
            net = m.net("ingaas")
            if net < k * sigma:
                g = Gate(
                    False,
                    hole,
                    net,
                    sigma,
                    f"InGaAs net on hole {hole} is {net} counts (< {k:g} sigma): the photodiode "
                    "is reversed",
                )
            else:
                g = Gate(True, hole, net, sigma, f"InGaAs polarity OK on hole {hole} ({net:+d})")
            self.cache["gate"] = g
        gate: Gate = self.cache["gate"]
        return gate

    def unusable(self, det: str) -> str:
        """Why a detector's readings cannot be judged, or "" if they can (cached).

        A detector whose dark output is erratic or pinned at a rail, or an
        InGaAs that fails the polarity gate, makes every later judgment on it
        meaningless: those are skipped and the cause is reported once (T06).
        """
        reasons: dict[str, str] = self.cache.setdefault("unusable", {})
        if det not in reasons:
            th = self.th
            s = self.dark().by_detector[det]
            erratic = th.num("dark.erratic_sigma_factor") * th.num("adc.dark_sigma_max_counts")
            why = ""
            if s.std > erratic:
                why = f"{det} dark signal is erratic (sigma {s.std:.0f} counts)"
            elif s.mean >= th.num(f"saturation.{det}_counts"):
                why = f"{det} output is pinned high ({s.mean:.0f} counts)"
            elif det == "ingaas" and s.mean < th.num("dark.negative_rail_counts"):
                why = f"{det} output is pinned negative ({s.mean:.0f} counts)"
            elif det == "ingaas" and not self.gate().ok:
                why = "InGaAs polarity gate failed (photodiode reversed)"
            reasons[det] = why
        reason: str = reasons[det]
        return reason

    def usable(self, det: str) -> bool:
        return not self.unusable(det)

    def channels(self) -> dict[int, ChannelData]:
        """The 16-channel matrix (T05.2-T05.4): MEAS each hole, then read after OFF."""
        if "channels" not in self.cache:
            self.require_adc()
            for det in DETECTORS:
                self.unusable(det)  # runs the polarity gate before the matrix
            n = self.th.integer("channel.meas_n")
            settle_s = self.cfg.limits["settle_ms"] / 1000.0
            out: dict[int, ChannelData] = {}
            for hole in range(1, 17):
                m = self.meas(hole, n=n)
                self.dev.sleep(settle_s)
                after = {det: self.dev.adc_read(self.adc_channel(det), n).mean for det in DETECTORS}
                out[hole] = ChannelData(m, after)
            self.cache["channels"] = out
        chans: dict[int, ChannelData] = self.cache["channels"]
        return chans

    # ------------------------------------------------------------ state

    def restore(self) -> None:
        """Back to the safe default state after a test: dark, idle, default config.

        Each command is retried once, so that a single lost line on a flaky link
        (reported by T02) does not leave the device in a test state.
        """
        dev, sec = self.dev, self.cfg.section
        dev.drain()
        steps: list[Callable[[], object]] = [
            lambda: dev.command("OFF"),
            lambda: dev.command("MOTOR STOP"),
            lambda: dev.adc_gain(str(sec.raw("adc.gain"))),
            lambda: dev.adc_rate(sec.integer("adc.rate_sps")),
            lambda: dev.wdt_cfg("A", self.cfg.wdt_ms("A")),
            lambda: dev.wdt_cfg("B", self.cfg.wdt_ms("B")),
        ]
        for step in steps:
            try:
                step()
            except NoResponse:
                step()

    @contextmanager
    def adc_rate(self, sps: int) -> Iterator[None]:
        self.dev.adc_rate(sps)
        try:
            yield
        finally:
            self.dev.adc_rate(self.cfg.section.integer("adc.rate_sps"))


# --------------------------------------------------------------------- runner


def new_result(t: TestDef) -> TestResult:
    return TestResult(t.id, t.name, t.module, t.kind)


def _gate_kind(ctx: SuiteContext, t: TestDef) -> None:
    """Interactive tests need an operator; motion tests also need --allow-motion."""
    if t.kind in ("I", "M") and ctx.operator is None:
        raise Skip("needs an operator at the bench (--interactive)")
    if t.kind == "M" and not ctx.allow_motion:
        raise Skip("moves the motors: needs --allow-motion with an operator present")


def run_test(ctx: SuiteContext, t: TestDef) -> TestResult:
    """Run one catalogue entry; never raises (errors become ERROR results)."""
    result = new_result(t)
    rec = Recorder(result)
    ctx.current = t.id
    t0 = time.monotonic()
    try:
        _gate_kind(ctx, t)
        t.fn(ctx, rec)
        result.status = worst([s.status for s in result.subs])
        if not result.subs:
            result.status = Status.PASS
    except Skip as s:
        result.status = Status.SKIP
        rec.note(str(s))
    except Abort as a:
        result.status = Status.SKIP
        rec.note(str(a))
    except (DeviceError, NoResponse, TimeoutError, OSError) as e:
        result.status = Status.ERROR
        rec.note(f"{type(e).__name__}: {e}")
    except Exception as e:  # a bug in the test must not stop the run
        result.status = Status.ERROR
        rec.note(f"{type(e).__name__}: {e}")
        log.error("%s raised:\n%s", t.id, traceback.format_exc())
    finally:
        try:
            ctx.restore()
        except Exception as e:
            result.status = Status.ERROR
            rec.note(f"could not restore the safe state afterwards: {e}")
        result.duration_s = time.monotonic() - t0
        ctx.current = ""
    return result
