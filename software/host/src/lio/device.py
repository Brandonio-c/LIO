"""High-level API to an LIO controller (firmware v2, protocol 1).

Every hardware interaction goes through :class:`LIODevice`. Used as a context
manager it always turns the LEDs off and stops/releases the motors on exit,
including on exceptions and Ctrl-C::

    with LIODevice(SerialTransport("/dev/cu.usbserial-1120"), cfg) as dev:
        m = dev.meas(8)
        print(m.net("opt101"), m.net("ingaas"))
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from lio.config import HwConfig
from lio.protocol import (
    ErrCode,
    Event,
    Fields,
    Noise,
    ProtocolError,
    Response,
    encode,
    fw_compatible,
    parse_line,
)
from lio.transport import Transport

log = logging.getLogger(__name__)

ADC_INGAAS = 0
ADC_OPT101 = 1


class DeviceError(Exception):
    """The device answered ``ERR``."""

    def __init__(self, command: str, code: int, msg: str) -> None:
        super().__init__(f"{command!r} -> ERR code={code} ({_code_name(code)}): {msg}")
        self.command = command
        self.code = code
        self.msg = msg


class NoResponse(TimeoutError):
    """No response arrived for a command within its timeout."""


class BootTimeout(TimeoutError):
    """The boot banner did not arrive after opening or resetting."""


def _code_name(code: int) -> str:
    try:
        return ErrCode(code).name.lower()
    except ValueError:
        return "unknown"


@dataclass(frozen=True)
class Reply:
    response: Response
    events: list[Event]
    t_sent: float
    t_done: float

    @property
    def fields(self) -> Fields:
        return self.response.fields

    @property
    def rtt_s(self) -> float:
        return self.t_done - self.t_sent


@dataclass(frozen=True)
class Meas:
    hole: int
    dark0: int  # ADS A0 = InGaAs TIA
    dark1: int  # ADS A1 = OPT101
    lit0: int
    lit1: int
    t_on_ms: int

    @classmethod
    def from_fields(cls, f: Fields) -> Meas:
        return cls(
            f.as_int("ch"),
            f.as_int("dark0"),
            f.as_int("dark1"),
            f.as_int("lit0"),
            f.as_int("lit1"),
            f.as_int("t_on_ms"),
        )

    def dark(self, detector: str) -> int:
        return self.dark0 if detector == "ingaas" else self.dark1

    def lit(self, detector: str) -> int:
        return self.lit0 if detector == "ingaas" else self.lit1

    def net(self, detector: str) -> int:
        return self.lit(detector) - self.dark(detector)


@dataclass(frozen=True)
class AdcReading:
    ch: int
    raw: int
    mv: float
    n: int
    mean: float
    std: float | None

    @classmethod
    def from_fields(cls, f: Fields) -> AdcReading:
        std = f.as_float("std") if "std" in f else None
        return cls(
            f.as_int("ch"),
            f.as_int("raw"),
            f.as_float("mv"),
            f.as_int("n"),
            f.opt_float("mean", float(f.as_int("raw"))),
            std,
        )


@dataclass(frozen=True)
class StreamSample:
    i: int
    t_us: int
    raw: int


@dataclass(frozen=True)
class Sweep:
    records: list[Meas]
    dur_ms: int


@dataclass
class DutyTracker:
    """Host-side LED duty budget (approved M0 proposal 7).

    Each channel may be lit for at most ``budget_ms[rail]`` within any
    ``window_s``. Before an LED action the device asks how long to cool down;
    the waits are recorded for the report. A single request longer than the
    budget is allowed after the window clears and recorded as over-budget.
    """

    window_s: float
    budget_ms: dict[str, float]
    rail_of: Callable[[int], str]
    history: dict[int, list[tuple[float, float]]] = field(default_factory=dict)
    cooldowns: list[tuple[int, float, str]] = field(default_factory=list)
    over_budget: list[tuple[int, float]] = field(default_factory=list)

    def used_ms(self, hole: int, now: float) -> float:
        lo = now - self.window_s
        total = 0.0
        for t0, t1 in self.history.get(hole, []):
            total += max(0.0, min(t1, now) - max(t0, lo))
        return total * 1000.0

    def wait_needed(self, hole: int, on_ms: float, now: float) -> float:
        budget = self.budget_ms[self.rail_of(hole)]
        need = min(on_ms, budget)
        if self.used_ms(hole, now) + need <= budget:
            return 0.0
        # Earliest time at which enough history has left the window.
        candidates = sorted({t1 + self.window_s - now for _, t1 in self.history.get(hole, [])})
        for wait in candidates:
            if wait > 0 and self.used_ms(hole, now + wait) + need <= budget:
                return wait
        return self.window_s

    def record(self, hole: int, t_on: float, t_off: float) -> None:
        self.history.setdefault(hole, []).append((t_on, t_off))
        if (t_off - t_on) * 1000.0 > self.budget_ms[self.rail_of(hole)]:
            self.over_budget.append((hole, (t_off - t_on) * 1000.0))

    def note_cooldown(self, hole: int, wait_s: float, reason: str) -> None:
        self.cooldowns.append((hole, wait_s, reason))

    @property
    def total_cooldown_s(self) -> float:
        return sum(w for _, w, _ in self.cooldowns)


class LIODevice:
    """Typed, safe access to an LIO controller over any :class:`Transport`."""

    def __init__(self, transport: Transport, cfg: HwConfig, *, duty: bool = True) -> None:
        self.transport = transport
        self.cfg = cfg
        self.events: list[tuple[float, Event]] = []
        self.noise: list[str] = []
        self.banner: Event | None = None
        self.boot_s: float | None = None
        self._seq = 0
        self._info: Fields | None = None
        self._listeners: list[Callable[[Event], None]] = []
        self._lit: tuple[int, float, float] | None = None  # (hole, t_on, planned t_off)
        th = cfg.section
        self.duty: DutyTracker | None = (
            DutyTracker(
                window_s=th.num("duty.window_s"),
                budget_ms={r: th.num(f"duty.max_on_ms_per_channel.{r}") for r in ("A", "B")},
                rail_of=lambda h: cfg.channel(h).rail,
            )
            if duty
            else None
        )

    # ------------------------------------------------------------ lifecycle

    def open(self) -> Event:
        t0 = self.transport.now()
        self.transport.open()
        try:
            banner = self.wait_banner(self.cfg.section.num("link.boot_timeout_s"))
        except BaseException:
            self.transport.close()
            raise
        self.boot_s = self.transport.now() - t0
        return banner

    def close(self) -> None:
        if self.transport.is_open:
            self.safe_off()
            self.transport.close()

    def __enter__(self) -> LIODevice:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def safe_off(self) -> None:
        """Best effort: LEDs off and motors stopped/released. Never raises."""
        for cmd in ("OFF", "MOTOR STOP"):
            try:
                self.command(cmd, timeout=1.0)
            except Exception as e:  # must not mask the original error
                log.warning("safe_off: %s failed: %s", cmd, e)
        self._close_lit(self.now())

    # ------------------------------------------------------------- clock

    def now(self) -> float:
        return self.transport.now()

    def sleep(self, seconds: float) -> None:
        self.transport.sleep(seconds)

    # ----------------------------------------------------------- line I/O

    def add_listener(self, fn: Callable[[Event], None]) -> None:
        self._listeners.append(fn)

    def _dispatch(self, raw: str) -> Response | Event | None:
        line = parse_line(raw)
        if isinstance(line, Noise):
            if raw.strip():
                self.noise.append(raw)
                log.debug("noise: %r", raw)
            return None
        if isinstance(line, Event):
            self.events.append((self.now(), line))
            self._on_event(line)
            for fn in self._listeners:
                fn(line)
        return line

    def _on_event(self, ev: Event) -> None:
        if ev.name in ("WDT", "OFF", "FAILSAFE"):
            self._close_lit(self.now())
        if ev.is_boot:
            self._info = None
            self._close_lit(self.now())

    def wait_banner(self, timeout: float) -> Event:
        deadline = self.now() + timeout
        while True:
            remaining = deadline - self.now()
            if remaining <= 0:
                raise BootTimeout(f"no '# BOOT' banner within {timeout:.1f} s")
            raw = self.transport.read_line(remaining)
            if raw is None:
                continue
            line = self._dispatch(raw)
            if isinstance(line, Event) and line.is_boot:
                self.banner = line
                return line

    def wait_event(self, name: str, timeout: float) -> Event | None:
        """Read lines until event ``name`` arrives (returned) or the timeout expires."""
        deadline = self.now() + timeout
        while True:
            remaining = deadline - self.now()
            if remaining <= 0:
                return None
            raw = self.transport.read_line(remaining)
            if raw is None:
                return None
            line = self._dispatch(raw)
            if isinstance(line, Event) and line.name == name:
                return line

    def drain(self, timeout: float = 0.0) -> list[Event]:
        """Collect any lines already waiting (events), for up to ``timeout``."""
        got: list[Event] = []
        deadline = self.now() + timeout
        while True:
            raw = self.transport.read_line(max(0.0, deadline - self.now()))
            if raw is None:
                return got
            line = self._dispatch(raw)
            if isinstance(line, Event):
                got.append(line)

    def command(self, cmd: str, *, timeout: float | None = None, check: bool = True) -> Reply:
        """Send one command and return its response plus the events seen meanwhile."""
        self._seq = (self._seq + 1) % 100000
        seq = self._seq
        wire = encode(cmd, seq)
        t_sent = self.now()
        self.transport.write_line(wire)
        to = timeout if timeout is not None else self.cfg.section.num("link.response_timeout_s")
        deadline = t_sent + to
        events: list[Event] = []
        while True:
            remaining = deadline - self.now()
            if remaining <= 0:
                raise NoResponse(f"no response to {cmd!r} within {to:.2f} s")
            raw = self.transport.read_line(remaining)
            if raw is None:
                continue
            line = self._dispatch(raw)
            if isinstance(line, Event):
                events.append(line)
            elif isinstance(line, Response):
                if line.seq != seq:
                    log.warning("discarding response with seq %s (waiting for %s)", line.seq, seq)
                    continue
                reply = Reply(line, events, t_sent, self.now())
                if check and not line.ok:
                    raise DeviceError(cmd, line.code or 0, line.msg or "")
                return reply

    # -------------------------------------------------------------- identity

    def ping(self) -> float:
        """Round-trip time in seconds."""
        return self.command("PING").rtt_s

    def info(self, refresh: bool = False) -> Fields:
        if self._info is None or refresh:
            self._info = self.command("INFO").fields
        return self._info

    def status(self) -> Fields:
        return self.command("STATUS").fields

    def check_compatible(self) -> None:
        f = self.info()
        if not fw_compatible(
            f.as_str("fw"), f.as_int("proto"), self.cfg.fw_min_version, self.cfg.fw_proto
        ):
            raise ProtocolError(
                f"firmware {f.as_str('fw')} proto {f.as_int('proto')} is not compatible "
                f"(need >= {self.cfg.fw_min_version}, proto {self.cfg.fw_proto})"
            )

    def reset(self) -> Event:
        self.command("RESET")
        return self.wait_banner(self.cfg.section.num("link.boot_timeout_s"))

    # ------------------------------------------------------------------- ADC

    def i2c_scan(self) -> list[int]:
        f = self.command("I2C SCAN", timeout=3.0).fields
        addrs = f.as_str("addrs")
        return [] if addrs == "none" else [int(a, 16) for a in addrs.split(",")]

    def _conv_s(self) -> float:
        rate = self.info().as_int("rate") if self._info is not None else 128
        return 1.0 / rate + 0.0005

    def adc_read(self, ch: int, n: int = 1) -> AdcReading:
        timeout = 1.0 + n * self._conv_s() * 1.5
        return AdcReading.from_fields(self.command(f"ADC READ {ch} {n}", timeout=timeout).fields)

    def adc_gain(self, gain: str) -> float:
        """Set the PGA; returns mV per count."""
        f = self.command(f"ADC CFG GAIN {gain}").fields
        self._info = None
        return f.as_float("lsb_mv")

    def adc_rate(self, sps: int) -> None:
        self.command(f"ADC CFG RATE {sps}")
        self._info = None

    def adc_stream(
        self,
        ch: int,
        n: int,
        interval_ms: int = 0,
        led: tuple[int, int, int] | None = None,
    ) -> list[StreamSample]:
        """Stream ``n`` samples; ``led=(hole, on_idx, off_idx)`` adds an LED schedule."""
        cmd = f"ADC STREAM {ch} {n} {interval_ms}"
        if led is not None:
            hole, on_i, off_i = led
            cmd += f" {hole} {on_i} {off_i}"
            self._duty_gate(hole, (off_i - on_i) * max(interval_ms, 2.0))
        per = max(interval_ms / 1000.0, self._conv_s())
        t0 = self.now()
        reply = self.command(cmd, timeout=2.0 + n * per * 1.5)
        if led is not None:
            # On-time estimated from the schedule; recorded for the duty budget.
            self._record_duty(led[0], t0, t0 + (led[2] - led[1]) * per)
        return [
            StreamSample(e.fields.as_int("i"), e.fields.as_int("t_us"), e.fields.as_int("raw"))
            for e in reply.events
            if e.name == "S"
        ]

    # ------------------------------------------------------------ channels

    def sr_raw(self, mask: int) -> int:
        return self.command(f"SR RAW {mask:04X}").fields.as_int("mask")

    def ce(self, rail: int, on: bool) -> Reply:
        reply = self.command(f"CE {rail} {int(on)}")
        if on:
            hole = self._single_hole(self.status().as_int("mask"))
            until = reply.fields.as_int("until_ms") / 1000.0
            if hole:
                self._lit = (hole, self.now(), self.now() + until)
        else:
            self._close_lit(self.now())
        return reply

    def ch_on(self, hole: int, ms: int | None = None) -> int:
        """Light one hole; returns the firmware's (possibly clamped) on-time in ms."""
        planned = ms if ms is not None else self.cfg.wdt_ms(self.cfg.channel(hole).rail)
        self._duty_gate(hole, planned)
        cmd = f"CH {hole} ON" + (f" {ms}" if ms is not None else "")
        until = self.command(cmd).fields.as_int("until_ms")
        self._close_lit(self.now())
        self._lit = (hole, self.now(), self.now() + until / 1000.0)
        return until

    def off(self) -> None:
        self.command("OFF")
        self._close_lit(self.now())

    def meas_timeout(self, settle_ms: int, n: int) -> float:
        return 1.0 + (2 * settle_ms / 1000.0 + 4 * n * self._conv_s()) * 1.5

    def meas(self, hole: int, settle_ms: int | None = None, n: int | None = None) -> Meas:
        s = settle_ms if settle_ms is not None else self.cfg.limits["settle_ms"]
        k = n if n is not None else 1
        self._duty_gate(hole, s + 2 * k * self._conv_s() * 1000)
        t0 = self.now()
        reply = self.command(f"MEAS {hole} {s} {k}", timeout=self.meas_timeout(s, k))
        m = Meas.from_fields(reply.fields)
        self._record_duty(hole, t0, t0 + m.t_on_ms / 1000.0)
        return m

    def sweep(self, settle_ms: int | None = None, n: int | None = None) -> Sweep:
        s = settle_ms if settle_ms is not None else self.cfg.limits["settle_ms"]
        k = n if n is not None else 1
        per_ms = s + 2 * k * self._conv_s() * 1000
        for hole in range(1, 17):
            self._duty_gate(hole, per_ms)
        t0 = self.now()
        reply = self.command(f"SWEEP {s} {k}", timeout=16 * self.meas_timeout(s, k))
        records = [Meas.from_fields(e.fields) for e in reply.events if e.name == "M"]
        for m in records:
            self._record_duty(m.hole, t0, t0 + m.t_on_ms / 1000.0)
        return Sweep(records, reply.fields.as_int("dur_ms"))

    def loop_test(self) -> Fields:
        return self.command("LOOP TEST", timeout=3.0).fields

    def wdt_cfg(self, rail: str, ms: int) -> Fields:
        f = self.command(f"WDT CFG {rail} {ms}").fields
        self._info = None
        return f

    # ---------------------------------------------------------------- motors

    def motor_arm(self) -> Fields:
        token = self.info(refresh=True).as_int("arm_token")
        return self.command(f"MOTOR ARM {token:04X}").fields

    def motor_step(self, motor: int, steps: int, rpm: int | None = None) -> Fields:
        cmd = f"MOTOR {motor} STEP {steps:+d}" + (f" {rpm}" if rpm is not None else "")
        return self.command(cmd).fields

    def motor_release(self, motor: int | str = "ALL") -> None:
        self.command(f"MOTOR {motor} RELEASE")

    def motor_stop(self) -> Fields:
        return self.command("MOTOR STOP").fields

    def wait_motor_done(self, motor: int, timeout: float) -> Event | None:
        deadline = self.now() + timeout
        while self.now() < deadline:
            ev = self.wait_event("MOTOR", deadline - self.now())
            if ev is None:
                return None
            if ev.fields.as_int("m") == motor:
                return ev
        return None

    # ------------------------------------------------------------ duty budget

    @staticmethod
    def _single_hole(mask: int) -> int:
        return mask.bit_length() if mask and not mask & (mask - 1) else 0

    def _duty_gate(self, hole: int, on_ms: float) -> None:
        if self.duty is None:
            return
        wait = self.duty.wait_needed(hole, on_ms, self.now())
        if wait > 0:
            log.info("duty: cooling hole %d for %.1f s before %.0f ms on", hole, wait, on_ms)
            self.duty.note_cooldown(hole, wait, f"{on_ms:.0f} ms requested")
            self.sleep(wait)

    def _record_duty(self, hole: int, t_on: float, t_off: float) -> None:
        if self.duty is not None:
            self.duty.record(hole, t_on, t_off)

    def _close_lit(self, now: float) -> None:
        if self._lit is None:
            return
        hole, t_on, planned = self._lit
        self._lit = None
        self._record_duty(hole, t_on, min(now, planned))
