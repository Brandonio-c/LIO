"""High-level API to an LIO controller (firmware v2, protocol 1).

Every hardware interaction goes through :class:`LIODevice`. Used as a context
manager it always turns the LEDs off and stops/releases the motors on exit,
including on exceptions and Ctrl-C::

    with LIODevice(SerialTransport("/dev/cu.usbserial-1120"), cfg) as dev:
        m = dev.meas(8)
        print(m.net("opt101"), m.net("ingaas"))
"""

from __future__ import annotations

import contextlib
import logging
import math
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from lio.config import HwConfig
from lio.ownership import (
    DeviceLock,
    DutyBudgetError,
    DutyJournal,
    JournalError,
    OwnershipError,
    Reservation,
    default_state_root,
    normalize_port_identity,
    rig_identity_from_port,
)
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
from lio.stage import StageError, StageTracker
from lio.timing_capability import (
    DEFAULT_TIMING_CAPABILITY,
    conservative_pulse_bound_ms,
    validate_reported_on_ms,
)
from lio.transport import SerialTransport, SimTransport, Transport

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


class Cancelled(Exception):
    """A run was stopped from outside (the dashboard's Stop button).

    Raised by the device's next command or sleep after :meth:`LIODevice.request_cancel`.
    """


# How often a cancellable sleep checks for a stop request (seconds).
CANCEL_POLL_S = 0.1
I2C_DIAG_KEYS = (
    "sda",
    "scl",
    "sda_pu",
    "scl_pu",
    "bridge",
    "ack_slow",
    "ack_fast",
    "slow_hz",
    "fast_hz",
    "hz",
    "present",
)


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

    Each channel may be lit for at most ``budget_ms[rail_of(hole)]`` within any
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

    def __init__(
        self,
        transport: Transport,
        cfg: HwConfig,
        *,
        duty: bool = True,
        stage: StageTracker | None = None,
        journal: DutyJournal | None = None,
        device_lock: DeviceLock | None = None,
        state_root: Path | None = None,
    ) -> None:
        self.transport = transport
        self.cfg = cfg
        # Absolute stage position across sessions (lio.stage); None = not tracked.
        self.stage = stage
        # A # BOOT is expected after opening the port and after RESET; any other one
        # (a brown-out mid-move) means steps may have been lost: the position is
        # then marked not trusted (plan LIO-SW-SCAN-001 §3.2, D3).
        self._expect_boot = False
        self.unexpected_boots = 0
        self.mains_hz = 0  # ADC CFG MAINS in force (firmware >= 2.5.1)
        self.events: list[tuple[float, Event]] = []
        self.noise: list[str] = []
        self.banner: Event | None = None
        self.boot_s: float | None = None
        self._seq = 0
        self._info: Fields | None = None
        self._listeners: list[Callable[[Event], None]] = []
        self._lit: tuple[int, float, float] | None = None  # (hole, t_on, planned t_off)
        # Set by another thread to stop the running test at its next command or
        # sleep; one-shot, so the safe-state restore afterwards still works.
        self.cancellable = False
        self._cancel = threading.Event()
        self._wake_supported = True
        self._last_wake = -math.inf
        th = cfg.section
        self.duty: DutyTracker | None = (
            DutyTracker(
                window_s=th.num("duty.window_s"),
                budget_ms=cfg.duty_budgets_ms(),
                rail_of=cfg.duty_key,
            )
            if duty
            else None
        )
        # M1 / R1: real serial always gets exclusive lock + durable journal.
        # Real duty=False / budget=False cannot disable accounting (D01).
        self.device_lock = device_lock
        self.journal = journal
        self._pending_reservations: list[Reservation] = []
        self._timing = DEFAULT_TIMING_CAPABILITY
        self._state_root = state_root
        if isinstance(transport, SerialTransport):
            root = state_root if state_root is not None else default_state_root()
            self._state_root = root
            rig = rig_identity_from_port(transport.port)
            if self.device_lock is None:
                self.device_lock = DeviceLock(rig, root)
            # Always attach a journal on real hardware — duty=False is not an escape.
            if self.journal is None:
                self.journal = DutyJournal.for_rig(
                    normalize_port_identity(transport.port),
                    state_root=root,
                    window_s=th.num("duty.window_s"),
                    budget_ms=cfg.duty_budgets_ms(),
                    rail_of=cfg.duty_key,
                    mono_now=self.transport.now,
                )
            # Keep in-memory tracker for operator UX even when journal is primary.
            if self.duty is None:
                self.duty = DutyTracker(
                    window_s=th.num("duty.window_s"),
                    budget_ms=cfg.duty_budgets_ms(),
                    rail_of=cfg.duty_key,
                )
        # Journal mono clock must match transport time (sim or serial), else
        # commits at t≈0 are pruned against wall monotonic.
        if self.journal is not None:
            self.journal.mono_now = self.transport.now

    # ------------------------------------------------------------ lifecycle

    def _is_sim(self) -> bool:
        return isinstance(self.transport, SimTransport)

    def open(self) -> Event:
        # Ownership lock BEFORE journal reload / serial open / POWER WAKE (D03).
        if self.device_lock is not None:
            self.device_lock.acquire()
        if self.journal is not None:
            # Reload durable state under the lease so stale objects cannot erase.
            self.journal.reload()
        t0 = self.transport.now()
        self._expect_boot = True
        try:
            self.transport.open()
            try:
                banner = self.wait_banner(self.cfg.section.num("link.boot_timeout_s"))
            except BaseException:
                self.transport.close()
                raise
            finally:
                self._expect_boot = False
        except BaseException:
            if self.device_lock is not None:
                self.device_lock.release()
            raise
        self.boot_s = self.transport.now() - t0
        self.keep_awake(force=True)
        return banner

    # ------------------------------------------------------- power bank A

    def power_wake(self, ms: int | None = None) -> int:
        """POWER WAKE: hold both motors' coils (no steps) to wake power bank A."""
        ms = ms if ms is not None else self.cfg.section.integer("power.wake_ms")
        reply = self.command(f"POWER WAKE {ms}", timeout=ms / 1000.0 + 1.0)
        return reply.fields.as_int("wake_ms")

    def keep_awake(self, *, force: bool = False) -> bool:
        """Wake power bank A if it may have gone to sleep; True if a wake was sent.

        Sent when the port opens (``force``) and, through the test runner and
        the dashboard, before tests and manual measurements, at most once per
        ``power.interval_s``. Never raises: firmware without POWER WAKE, an LED
        that is on, or a moving motor just skip it.
        """
        sec = self.cfg.section
        if not sec.raw("power.wake") or not self._wake_supported:
            return False
        now = self.now()
        if not force and now - self._last_wake < sec.num("power.interval_s"):
            return False
        try:
            self.power_wake()
        except DeviceError as e:
            if e.code == ErrCode.UNKNOWN:
                self._wake_supported = False  # an older firmware build
                log.info("firmware has no POWER WAKE: power bank A is not woken")
            else:
                log.info("POWER WAKE skipped: %s", e.msg)
            return False
        self._last_wake = self.now()
        self.sleep(sec.num("power.settle_ms") / 1000.0)
        self._info = None  # adc_ok may have changed
        return True

    def close(self) -> None:
        """Always close transport before releasing ownership (D04)."""
        try:
            if self.transport.is_open:
                try:
                    self.safe_off()
                except Exception as e:
                    log.warning("close: safe_off failed: %s", e)
                finally:
                    with contextlib.suppress(Exception):
                        self.transport.close()
        finally:
            if self.device_lock is not None:
                with contextlib.suppress(Exception):
                    self.device_lock.release()

    def __enter__(self) -> LIODevice:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def safe_off(self) -> None:
        """Same-owner OFF/STOP: cancellation- and ledger-independent (D04)."""
        off_ok = False
        for cmd in ("OFF", "MOTOR STOP"):
            try:
                self._command_unguarded(cmd, timeout=1.0, check=False)
                if cmd == "OFF":
                    off_ok = True
            except Exception as e:  # must not mask the original error
                log.warning("safe_off: %s failed: %s", cmd, e)
                if cmd == "OFF":
                    self._retain_uncertain_if_emitting(reason=f"safe_off OFF failed: {e}")
        with contextlib.suppress(Exception):
            self._close_lit(self.now())
        if off_ok:
            with contextlib.suppress(Exception):
                st = self.status()
                if st.as_int("ce1") != 0 or st.as_int("ce2") != 0:
                    self._retain_uncertain_if_emitting(reason="CE remains high after safe_off OFF")

    # ------------------------------------------------------------- clock

    def now(self) -> float:
        return self.transport.now()

    def sleep(self, seconds: float) -> None:
        if not self.cancellable:
            self.transport.sleep(seconds)
            return
        end = self.now() + seconds
        while True:
            self._check_cancel()
            left = end - self.now()
            if left <= 0:
                return
            self.transport.sleep(min(left, CANCEL_POLL_S))

    # ------------------------------------------------------------ cancel

    def request_cancel(self) -> None:
        """Ask the running test to stop (thread-safe); it raises :class:`Cancelled`."""
        self._cancel.set()

    def clear_cancel(self) -> None:
        self._cancel.clear()

    def _check_cancel(self) -> None:
        if self.cancellable and self._cancel.is_set():
            self._cancel.clear()
            raise Cancelled("stopped by the operator")

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
            self.mains_hz = 0  # the firmware boots with mains integration off
            self._info = None
            self._close_lit(self.now())
            if self.stage is not None:  # the firmware's counters restart at 0
                self.stage.rebase(0, 0, "boot" if self._expect_boot else "unexpected boot")
            if not self._expect_boot:
                self.unexpected_boots += 1
                if self.stage is not None and self.stage.known:
                    self.stage.invalidate("unexpected # BOOT: the board reset by itself")
        if (
            self.stage is not None
            and ev.name == "MOTOR"
            and "m" in ev.fields
            and "pos" in ev.fields
        ):
            m, pos = ev.fields.as_int("m"), ev.fields.as_int("pos")
            self.stage.observe(pos if m == 1 else None, pos if m == 2 else None)

    def wait_banner(self, timeout: float) -> Event:
        deadline = self.now() + timeout
        n_noise = len(self.noise)
        while True:
            remaining = deadline - self.now()
            if remaining <= 0:
                raise BootTimeout(self._no_banner(timeout, self.noise[n_noise:]))
            raw = self.transport.read_line(remaining)
            if raw is None:
                continue
            line = self._dispatch(raw)
            if isinstance(line, Event) and line.is_boot:
                self.banner = line
                return line

    @staticmethod
    def _no_banner(timeout: float, seen: list[str]) -> str:
        """Why there was no banner, with what the board did send: the usual cause is
        other firmware on the Nano (an earlier sketch), which ``lio`` cannot talk to."""
        msg = f"no '# BOOT' banner within {timeout:.1f} s"
        if seen:
            sample = " | ".join(line.strip()[:60] for line in seen[:3])
            return (
                f"{msg}; the board sent other text instead ({sample}): it is running "
                "different firmware, not LIO firmware v2. Flash it (docs/TESTING.md §7.2)"
            )
        return (
            f"{msg}; the board sent nothing. It is most likely running a sketch other than "
            "LIO firmware v2 (one that prints nothing at start-up): flash firmware v2 "
            "(docs/TESTING.md §7.2). Otherwise check that nothing else has the port open"
        )

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
        """Send one command; light-capable raw/shell cmds are gated or refused (D01)."""
        self._check_cancel()
        routed = self._try_route_light_command(cmd)
        if routed is not None:
            return routed
        # Simulator robustness probes (T02.4) use check=False with deliberate
        # bad light-capable strings; real transports still refuse.
        if self._is_sim() and not check:
            return self._command_unguarded(cmd, timeout=timeout, check=check)
        self._gate_or_refuse_raw_command(cmd)
        return self._command_unguarded(cmd, timeout=timeout, check=check)

    def _try_route_light_command(self, cmd: str) -> Reply | None:
        """Map shell CH/CE/MEAS/SWEEP/OFF/SR onto typed gated operations."""
        parts = cmd.strip().split()
        if not parts:
            return None
        head = parts[0].upper()
        try:
            if head == "OFF":
                self.off()
                return self._synthetic_ok_reply("OFF", "")
            if head == "CH" and len(parts) >= 3 and parts[2].upper() == "ON":
                hole = int(parts[1])
                ms = int(parts[3]) if len(parts) >= 4 else None
                until = self.ch_on(hole, ms)
                clamped = int(ms is not None and ms > until)
                return self._synthetic_ok_reply("CH", f"until_ms={until} clamped={clamped}")
            if head == "CE" and len(parts) >= 3:
                return self.ce(int(parts[1]), bool(int(parts[2])))
            if head == "MEAS" and len(parts) >= 2:
                hole = int(parts[1])
                settle = int(parts[2]) if len(parts) >= 3 else None
                n = int(parts[3]) if len(parts) >= 4 else None
                m = self.meas(hole, settle_ms=settle, n=n)
                return self._synthetic_ok_reply("MEAS", f"hole={m.hole} t_on_ms={m.t_on_ms}")
            if head == "SWEEP":
                settle = int(parts[1]) if len(parts) >= 2 else None
                n = int(parts[2]) if len(parts) >= 3 else None
                sw = self.sweep(settle_ms=settle, n=n)
                return self._synthetic_ok_reply("SWEEP", f"dur_ms={sw.dur_ms} n={len(sw.records)}")
            if head == "SR" and len(parts) >= 3 and parts[1].upper() == "RAW":
                raw_mask = parts[2]
                mask = int(raw_mask, 16)
                got = self.sr_raw(mask)
                return self._synthetic_ok_reply("SR", f"mask={got}")
        except (ValueError, IndexError, TypeError):
            return None
        return None

    def _synthetic_ok_reply(self, word: str, fields: str) -> Reply:
        """Local OK after a typed op already performed the transport write."""
        vals = {k: v for k, v in (p.split("=", 1) for p in fields.split() if "=" in p)}
        resp = Response(
            ok=True,
            word=word,
            fields=Fields(vals),
            seq=self._seq,
            raw=f"OK {word}" + (f" {fields}" if fields else ""),
        )
        return Reply(resp, [], self.now(), self.now())

    def _command_unguarded(
        self, cmd: str, *, timeout: float | None = None, check: bool = True
    ) -> Reply:
        """Transport write without cancel check or raw light re-gate (safe_off / typed)."""
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
                f = reply.fields
                if self.stage is not None and "pos1" in f and "pos2" in f:
                    self.stage.observe(f.as_int("pos1"), f.as_int("pos2"))
                return reply

    def send_raw(self, data: bytes, timeout: float) -> Response | None:
        """Write raw bytes and return the first response of any sequence number.

        Light-capable / exposure-altering payloads are refused (D01 / CE01).
        Multiline, ``@seq``-prefixed, and fragment payloads that can emit are
        refused before any transport write. Suite robustness probes must use
        non-emitting garbage or typed helpers.
        """
        self._gate_or_refuse_raw_payload(data)
        self.transport.write_raw(data)
        deadline = self.now() + timeout
        while True:
            remaining = deadline - self.now()
            if remaining <= 0:
                return None
            raw = self.transport.read_line(remaining)
            if raw is None:
                continue
            line = self._dispatch(raw)
            if isinstance(line, Response):
                return line

    @staticmethod
    def _strip_wire_prefix(cmd: str) -> str:
        """Strip optional ``@seq`` wire prefix; empty after strip → empty command."""
        text = cmd.strip()
        if text.startswith("@"):
            _head, _, rest = text.partition(" ")
            return rest.strip()
        return text

    @staticmethod
    def _raw_command_kind(cmd: str) -> str:
        """Classify a protocol command for the emission gate."""
        parts = LIODevice._strip_wire_prefix(cmd).split()
        if not parts:
            return "empty"
        head = parts[0].upper()
        if head in ("OFF", "MOTOR") and (
            head == "OFF" or (len(parts) > 1 and parts[1].upper() in ("STOP", "RELEASE"))
        ):
            return "safe"
        if head == "CH":
            return "light_ch"
        if head == "CE":
            return "light_ce"
        if head == "SR":
            return "select"
        if head in ("MEAS", "SWEEP"):
            return "light_meas"
        if head == "DBG" and len(parts) > 1 and parts[1].upper() == "STATE":
            return "light_dbg"
        if head == "ADC" and len(parts) > 1 and parts[1].upper() == "STREAM":
            # STREAM with LED schedule args is light-capable.
            return "light_stream" if len(parts) >= 7 else "read"
        if head in ("WDT",) or (head == "ADC" and len(parts) > 1 and parts[1].upper() == "CFG"):
            return "config_exposure"
        return "other"

    def _gate_or_refuse_raw_command(self, cmd: str) -> None:
        """Public raw/shell paths must not bypass typed light accounting (D01)."""
        kind = self._raw_command_kind(cmd)
        if kind in ("safe", "other", "read", "empty"):
            return
        if kind == "config_exposure":
            # WDT / ADC CFG can alter exposure limits — require ownership context.
            if self.journal is None and not self._is_sim():
                raise OwnershipError(
                    f"refusing {cmd!r}: real hardware requires duty journal for "
                    "exposure-limit changes"
                )
            return
        # Light / select / CE: refuse raw path — callers must use typed ops.
        raise OwnershipError(
            f"refusing ungated light-capable command {cmd!r}: use typed "
            "ch_on/ce/meas/sweep/sr_raw (or shell guarded helpers)"
        )

    def _gate_or_refuse_raw_payload(self, data: bytes) -> None:
        """Refuse multiline / @-prefixed / fragment payloads that can emit (CE01)."""
        text = data.decode("ascii", errors="replace")
        # Real-path transports reject multiline payloads entirely: a PING line
        # must not smuggle a trailing CH/CE/MEAS.
        lines = [
            ln for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if ln.strip()
        ]
        if len(lines) > 1:
            for ln in lines:
                kind = self._raw_command_kind(ln)
                if kind not in ("safe", "other", "read", "empty"):
                    raise OwnershipError(
                        f"refusing multiline raw payload containing light-capable "
                        f"command {ln!r}: use typed helpers"
                    )
            # Non-emitting multiline garbage is simulator robustness only (T02.4).
            if self._is_sim():
                return
            raise OwnershipError(
                "refusing multiline raw payload on real-path transport: one command per write"
            )
        if not lines:
            return
        line = lines[0]
        stripped = line.strip()
        if stripped.startswith("@"):
            # @seq prefixes belong to encode(); public send_raw must not accept them
            # as a bypass around typed gating on real transports.
            body = self._strip_wire_prefix(stripped)
            kind = self._raw_command_kind(body)
            if kind not in ("safe", "other", "read", "empty"):
                raise OwnershipError(
                    f"refusing @-prefixed light-capable raw command {stripped!r}: use typed helpers"
                )
            # Simulator-only probes may use @seq for non-emitting commands.
            if self._is_sim():
                return
            raise OwnershipError(
                f"refusing @-prefixed raw command {stripped!r}: "
                "use typed command()/helpers (seq is assigned by the device)"
            )
        self._gate_or_refuse_raw_command(stripped)

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
        if "rail_b_first" in f and f.as_int("rail_b_first") != self.cfg.rail_b_first:
            raise ProtocolError(
                f"firmware puts holes {f.as_int('rail_b_first')}-16 on RAIL B but the config "
                f"puts holes {self.cfg.rail_b_first}-16 there: re-flash or fix lio_hw.yaml rails"
            )

    def reset(self) -> Event:
        self._expect_boot = True
        try:
            self.command("RESET")
            return self.wait_banner(self.cfg.section.num("link.boot_timeout_s"))
        finally:
            self._expect_boot = False

    # ------------------------------------------------------------------- ADC

    def i2c_scan(self) -> list[int]:
        # A stuck bus costs the firmware's I2C timeout on each of 126 addresses.
        f = self.command("I2C SCAN", timeout=self.cfg.section.num("link.i2c_scan_timeout_s")).fields
        addrs = f.as_str("addrs")
        return [] if addrs == "none" else [int(a, 16) for a in addrs.split(",")]

    def i2c_diag(self) -> dict[str, int] | None:
        """Line-level I2C checks (``I2C DIAG``); None on firmware without them.

        Keys: ``sda``/``scl`` idle high with the Nano's pull-up, ``sda_pu``/
        ``scl_pu`` rise with it off (an external pull-up to a powered VDD),
        ``bridge`` (SDA and SCL joined), ``ack_slow``/``ack_fast`` (the Wire
        result for 0x48 at ``slow_hz``/``fast_hz``: 0 ack, 2 no answer, 4 bus
        error, 5 timeout), ``hz`` (the clock now in use) and ``present``.
        """
        try:
            timeout = self.cfg.section.num("link.i2c_scan_timeout_s")
            f = self.command("I2C DIAG", timeout=timeout).fields
        except DeviceError as e:
            if e.code == ErrCode.BAD_ARG:  # firmware before 2.1.0: "usage: I2C SCAN"
                return None
            raise
        self._info = None  # adc_ok may have changed
        return {k: f.as_int(k) for k in I2C_DIAG_KEYS}

    def _conv_s(self) -> float:
        """Host timeout helper (seconds). Prefer ``_mean_ms_fw`` for WDT admission."""
        rate = self.info().as_int("rate") if self._info is not None else 128
        return 1.0 / rate + 0.0005

    def _mean_ms_fw(self, n: int) -> int:
        """Firmware/sim integer mean duration (ms) — must match ``SimulatedLIO._mean_ms``."""
        if self.mains_hz:
            return int(n) * 1000 // int(self.mains_hz) + 4
        rate = self.info().as_int("rate") if self._info is not None else 128
        conv_us = 1_000_000 // int(rate)
        return int(n) * (conv_us // 1000 + 2)

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
            # Match firmware STREAM LED estimate (sim/firmware adc_stream).
            rate = self.info().as_int("rate") if self._info is not None else 128
            conv_us = 1_000_000 // int(rate)
            per_us = max(int(interval_ms) * 1000, conv_us + 500)
            nominal = float((off_i - on_i) * per_us // 1000 + 20)
            # STREAM must not silently raise WDT past the active setting.
            bound = self._conservative_bound_for_hole(
                hole, nominal_on_ms=nominal, may_raise_wdt=False
            )
            self._duty_gate(hole, bound)
        per = max(interval_ms / 1000.0, self._conv_s())
        t0 = self.now()
        reply = self._command_unguarded(cmd, timeout=2.0 + n * per * 1.5)
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
        # Selection alone does not light, but with CE it can — require journal
        # presence on real HW so SR+CE cannot escape accounting (D01).
        if not self._is_sim() and self.journal is None:
            raise OwnershipError("SR RAW refused: real hardware requires duty journal")
        return self._command_unguarded(f"SR RAW {mask:04X}").fields.as_int("mask")

    def ce(self, rail: int, on: bool) -> Reply:
        if on:
            # CE high can light a selected hole — reserve conservative WDT bound.
            hole = self._single_hole(self.status().as_int("mask"))
            if hole:
                bound = self._conservative_bound_for_hole(hole)
                self._duty_gate(hole, bound)
            elif not self._is_sim() and self.journal is not None:
                # Ambiguous mask: refuse rather than emit unaccounted light.
                raise OwnershipError(
                    "CE on refused: no single selected hole to reserve duty against"
                )
        reply = self._command_unguarded(f"CE {rail} {int(on)}")
        if on:
            hole = self._single_hole(self.status().as_int("mask"))
            until = reply.fields.as_int("until_ms") / 1000.0
            if hole:
                self._lit = (hole, self.now(), self.now() + until)
        else:
            self._close_lit(self.now())
        return reply

    def ch_on(self, hole: int, ms: int | None = None, *, budget: bool = True) -> int:
        """Light one hole; returns the firmware's (possibly clamped) on-time in ms.

        Real hardware always goes through the duty journal (M1): ``budget=False``
        is not an escape hatch. Simulation without a journal may still skip.
        The firmware watchdog still ends the flash.
        """
        rail = self.cfg.channel(hole).rail
        default_wdt = int(self.cfg.wdt_ms(rail))
        current_wdt = int(self.info().as_int(f"wdt_{rail.lower()}_ms"))
        # Real duty/budget knobs cannot disable accounting (D01).
        if not budget and not (self._is_sim() and self.journal is None):
            budget = True
        # Over-default requests: restore configured default when a prior short
        # pulse left WDT below default (T10.2 clamp). If the operator already
        # set a deliberate sub-default WDT, clamp to that active setting.
        # Finite timed pulses keep WDT strictly above on-time (timer OFF path).
        if ms is None:
            # Hold until the active WDT (honour a prior wdt_cfg).
            nominal = float(current_wdt)
        elif ms >= default_wdt:
            # Firmware clamps to the active WDT. Callers that need the
            # configured default after short pulses must wdt_cfg(default) first.
            nominal = float(current_wdt)
        else:
            nominal = float(ms + 1)
        bound = self._conservative_bound_for_hole(hole, nominal_on_ms=nominal)
        if budget:
            self._duty_gate(hole, bound)
        cmd = f"CH {hole} ON" + (f" {ms}" if ms is not None else "")
        until = self._command_unguarded(cmd).fields.as_int("until_ms")
        abort = validate_reported_on_ms(bound, float(until))
        if abort:
            self._abort_pending()
            raise DutyBudgetError(f"CH abort retaining worst-case: {abort}")
        self._close_lit(self.now())
        self._lit = (hole, self.now(), self.now() + until / 1000.0)
        return until

    def off(self) -> None:
        try:
            self._command_unguarded("OFF")
        except Exception:
            self._retain_uncertain_if_emitting(reason="OFF failed")
            raise
        self._close_lit(self.now())
        # Verify CE low; retain uncertainty if still high (CE04).
        with contextlib.suppress(Exception):
            st = self.status()
            if st.as_int("ce1") != 0 or st.as_int("ce2") != 0:
                self._retain_uncertain_if_emitting(reason="CE remains high after OFF")

    def _retain_uncertain_if_emitting(self, *, reason: str) -> None:
        """Failed/unverified OFF with possible emission → uncertain + full charge."""
        if self.journal is None:
            return
        try:
            if self._pending_reservations:
                self.journal.abort_conservative(reservations=list(self._pending_reservations))
                self._pending_reservations = []
            self.journal.mark_uncertain(reason=reason)
        except Exception as e:
            log.warning("retain uncertain after %s: %s", reason, e)

    def _mean_s(self, n: int) -> float:
        """Duration of one firmware mean of n (seconds); WDT uses ``_mean_ms_fw``."""
        return self._mean_ms_fw(n) / 1000.0

    def adc_mains(self, hz: int) -> None:
        """ADC CFG MAINS: MEAS/SWEEP/DBG means integrate whole mains periods (2.5.1)."""
        self.command(f"ADC CFG MAINS {hz}")
        self.mains_hz = hz
        self._info = None

    def meas_timeout(self, settle_ms: int, n: int) -> float:
        return 1.0 + (2 * settle_ms / 1000.0 + 4 * self._mean_s(n)) * 1.5

    def meas(self, hole: int, settle_ms: int | None = None, n: int | None = None) -> Meas:
        s = settle_ms if settle_ms is not None else self.cfg.limits["settle_ms"]
        k = n if n is not None else 1
        # Match firmware/sim MEAS WDT check exactly: settle + 2*mean_ms + 10.
        nominal = float(s + 2 * self._mean_ms_fw(k) + 10)
        bound = self._conservative_bound_for_hole(hole, nominal_on_ms=nominal)
        self._duty_gate(hole, bound)
        t0 = self.now()
        try:
            reply = self._command_unguarded(f"MEAS {hole} {s} {k}", timeout=self.meas_timeout(s, k))
            m = Meas.from_fields(reply.fields)
        except Exception:
            self._abort_pending()
            raise
        abort = validate_reported_on_ms(bound, float(m.t_on_ms))
        if abort:
            self._abort_pending()
            raise DutyBudgetError(f"MEAS abort retaining worst-case: {abort}")
        self._record_duty(hole, t0, t0 + m.t_on_ms / 1000.0)
        return m

    def sweep(self, settle_ms: int | None = None, n: int | None = None) -> Sweep:
        s = settle_ms if settle_ms is not None else self.cfg.limits["settle_ms"]
        k = n if n is not None else 1
        per_nominal = float(s + 2 * self._mean_ms_fw(k) + 10)  # match firmware MEAS/SWEEP est
        # D02: atomically reserve ALL 16 hole charges before send.
        charges: list[tuple[int, float]] = []
        for hole in range(1, 17):
            bound = self._conservative_bound_for_hole(hole, nominal_on_ms=per_nominal)
            charges.append((hole, bound))
        self._duty_gate_many(charges)
        t0 = self.now()
        try:
            reply = self._command_unguarded(f"SWEEP {s} {k}", timeout=16 * self.meas_timeout(s, k))
            records = [Meas.from_fields(e.fields) for e in reply.events if e.name == "M"]
        except Exception:
            self._abort_pending()
            raise
        if len(records) != 16:
            self._abort_pending()
            raise DutyBudgetError(
                f"SWEEP partial/malformed: {len(records)} records; retaining all charges"
            )
        t = t0
        by_hole = {m.hole: m for m in records}
        for hole, bound in charges:
            m = by_hole.get(hole)
            if m is None:
                self._abort_pending()
                raise DutyBudgetError("SWEEP missing hole; retaining remaining charges")
            abort = validate_reported_on_ms(bound, float(m.t_on_ms))
            if abort:
                self._abort_pending()
                raise DutyBudgetError(f"SWEEP abort retaining worst-case: {abort}")
            dur_s = max(m.t_on_ms, 0) / 1000.0
            self._record_duty(m.hole, t, t + dur_s)
            t += dur_s if dur_s > 0 else bound / 1000.0
        return Sweep(records, reply.fields.as_int("dur_ms"))

    def dbg_state(self, state: str, arg: int, settle_ms: int, n: int) -> Fields:
        """Firmware >= 2.5.0 coupling states (``debug_states=1`` in INFO), atomic like MEAS:
        ``ce_only`` (rail ``arg``: CE high, nothing selected) or ``wrong_rail`` (hole
        ``arg`` selected, the other rail's CE high). A wrong-rail LED should stay dark;
        it is counted against the hole's duty budget anyway, in case it is miswired."""
        word = {"ce_only": "CE_ONLY", "wrong_rail": "WRONG_RAIL"}[state]
        # Match firmware DBG estimate; charge the hole, bound the energized rail.
        on_ms = float(settle_ms + 2 * self._mean_ms_fw(n) + 10)
        if state == "wrong_rail":
            hole_rail = self.cfg.channel(arg).rail
            energized = "B" if hole_rail == "A" else "A"
            # Ensure energized-rail WDT covers before send (wrong-rail CE).
            need = int(on_ms) if float(on_ms) == int(on_ms) else int(on_ms) + 1
            need = max(50, need)
            wdt_e = int(self.info().as_int(f"wdt_{energized.lower()}_ms"))
            if wdt_e < need:
                self.wdt_cfg(energized, need)
            bound = self._conservative_bound_for_hole(arg, nominal_on_ms=on_ms)
            self._duty_gate(arg, bound)
        t0 = self.now()
        f = self._command_unguarded(
            f"DBG STATE {word} {arg} {settle_ms} {n}",
            timeout=self.meas_timeout(settle_ms, n),
        ).fields
        if state == "wrong_rail":
            self._record_duty(arg, t0, t0 + f.as_int("t_on_ms") / 1000.0)
        return f

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

    def motor_step(
        self, motor: int, steps: int, rpm: int | None = None, *, soft_limits: bool = True
    ) -> Fields:
        """Half-step move; by default refused if it would leave the marked travel.

        Pass ``soft_limits=False`` for operator leveling on the Motors tab (scans and
        suite motion still use the default)."""
        if soft_limits and self.stage is not None:
            self.status()  # bring the tracked position up to date
            self.stage.check_move(motor, steps, self.stage_top_margin())
        cmd = f"MOTOR {motor} STEP {steps:+d}" + (f" {rpm}" if rpm is not None else "")
        return self.command(cmd).fields

    def motor_light(self, on: bool) -> Fields:
        """MOTOR LIGHT 0|1 (firmware >= 2.4.0): allow LEDs and MEAS while a motor moves.

        Only while armed; the firmware drops it when the arm lapses, on disarm, RESET
        and the comms failsafe."""
        return self.command(f"MOTOR LIGHT {int(on)}").fields

    # ------------------------------------------------------------ stage position

    def stage_top_margin(self) -> int:
        try:
            return self.cfg.section.integer("stage.top_margin_steps")
        except Exception:  # older configs
            return 0

    def stage_set_top(self) -> dict[str, object]:
        """The chamber top is at its physical upper end now: position 0 on both motors."""
        if self.stage is None:
            raise StageError("stage tracking is off for this connection")
        st = self.status()
        if st.as_str("motor1") == "run" or st.as_str("motor2") == "run":
            raise StageError("a motor is moving: stop it first")
        self.stage.set_top((st.as_int("pos1"), st.as_int("pos2")))
        return self.stage.summary()

    def stage_mark_bottom(self) -> dict[str, object]:
        """The chamber top is at its lowest safe position now."""
        if self.stage is None:
            raise StageError("stage tracking is off for this connection")
        st = self.status()
        if st.as_str("motor1") == "run" or st.as_str("motor2") == "run":
            raise StageError("a motor is moving: stop it first")
        self.stage.mark_bottom()
        return self.stage.summary()

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

    def wait_for_duty(self, holes: list[int], on_ms: float) -> float:
        """Wait until each hole may be lit for ``on_ms``; returns the seconds waited.

        For operator steps: cool down *before* asking the operator to watch, so
        that the LEDs then light when announced. All windows age together, so
        the longest single wait covers every hole.
        """
        if self.duty is None:
            return 0.0
        now = self.now()
        wait = max((self.duty.wait_needed(h, on_ms, now) for h in holes), default=0.0)
        if wait > 0:
            self.duty.note_cooldown(holes[0], wait, f"before an operator step ({len(holes)} holes)")
            self.sleep(wait)
        return wait

    def _conservative_bound_for_hole(
        self,
        hole: int,
        *,
        nominal_on_ms: float | None = None,
        may_raise_wdt: bool = True,
    ) -> float:
        """Conservative pulse bound (D05).

        - Active WDT < need → raise with ACK/readback when ``may_raise_wdt``
          (MEAS 2→8→8→2); otherwise refuse before light (STREAM over-cap).
        - Active WDT > need → lower to covering need with ACK/readback so the
          reserved charge matches possible exposure (CE03 / duty budgets).
        Firmware-matched ``need`` prevents the old host 52 vs firmware 54 miss.
        """
        from lio.timing_capability import (
            FW_WDT_MIN_MS,
            quantize_wdt_ms,
            rail_wdt_cap_ms,
        )

        rail = self.cfg.channel(hole).rail
        try:
            wdt = int(self.info().as_int(f"wdt_{rail.lower()}_ms"))
        except Exception as e:
            raise DutyBudgetError(
                f"cannot read WDT for hole {hole}: refuse before light ({e})"
            ) from e
        # CE / unknown duration: lower to firmware minimum so duty budgets fit;
        # typed MEAS/DBG always pass an explicit firmware-matched nominal and
        # raise the energized rail as needed afterward.
        nominal = float(FW_WDT_MIN_MS) if nominal_on_ms is None else float(nominal_on_ms)
        may_lower = True
        need = quantize_wdt_ms(nominal, capability=self._timing)
        rail_cap = rail_wdt_cap_ms(rail, capability=self._timing)
        if need > rail_cap:
            raise DutyBudgetError(
                f"refuse before light: need {need} ms exceeds rail {rail} cap {rail_cap} ms"
            )
        if wdt < need:
            if not may_raise_wdt:
                raise DutyBudgetError(
                    f"refuse before light: active WDT {wdt} ms cannot cover "
                    f"need {need} ms (raise not permitted for this operation)"
                )
            # Raise to covering need (2→8→8→2); verify ACK/readback.
            applied = self.wdt_cfg(rail, int(need))
            try:
                ack = int(applied.as_int(f"wdt_{rail.lower()}_ms"))
            except Exception:
                ack = int(need)
            rb = int(self.info(refresh=True).as_int(f"wdt_{rail.lower()}_ms"))
            if min(ack, rb) < need:
                raise DutyBudgetError(
                    f"refuse before light: WDT ACK/readback {ack}/{rb} ms < need {need} ms"
                )
            wdt = int(rb if rb >= need else ack)
        elif wdt > need and may_lower:
            applied = self.wdt_cfg(rail, int(need))
            try:
                ack = int(applied.as_int(f"wdt_{rail.lower()}_ms"))
            except Exception:
                ack = int(need)
            rb = int(self.info(refresh=True).as_int(f"wdt_{rail.lower()}_ms"))
            if max(ack, rb) < need or (ack != need and rb != need):
                raise DutyBudgetError(
                    f"refuse before light: WDT lower ACK/readback {ack}/{rb} ms != need {need} ms"
                )
            wdt = int(need)
        bound, refuse = conservative_pulse_bound_ms(
            nominal_on_ms=nominal,
            active_wdt_ms=wdt,
            rail=rail,
            capability=self._timing,
        )
        if refuse:
            raise DutyBudgetError(f"refuse before light: {refuse}")
        use_bound = float(bound)
        if self.journal is not None:
            try:
                self.journal.wait_needed(hole, use_bound, self.now())
            except DutyBudgetError as e:
                raise DutyBudgetError(
                    f"refuse before light: conservative bound {use_bound} ms "
                    f"unsupported by budget ({e})"
                ) from e
        return use_bound

    def _duty_gate(self, hole: int, on_ms: float) -> None:
        """Gate light through the durable journal when present; else DutyTracker.

        Over-budget requests (``on_ms`` greater than the absolute budget) are
        rejected before any transport write. Window-full cases wait, then reserve.
        """
        self._duty_gate_many([(hole, on_ms)])

    def _duty_gate_many(self, charges: list[tuple[int, float]]) -> None:
        if not charges:
            return
        if self.journal is not None:
            # Wait until every charge fits, then atomic multi-reserve.
            for hole, on_ms in charges:
                try:
                    wait = self.journal.wait_needed(hole, on_ms, self.now())
                except DutyBudgetError:
                    raise
                if wait > 0:
                    log.info(
                        "duty journal: cooling hole %d for %.1f s before %.0f ms on",
                        hole,
                        wait,
                        on_ms,
                    )
                    if self.duty is not None:
                        self.duty.note_cooldown(hole, wait, f"{on_ms:.0f} ms requested")
                    self.sleep(wait)
            try:
                self._pending_reservations = self.journal.reserve_many(charges)
            except (DutyBudgetError, JournalError, OwnershipError):
                self._pending_reservations = []
                raise
            return
        if self.duty is None:
            return
        for hole, on_ms in charges:
            wait = self.duty.wait_needed(hole, on_ms, self.now())
            if wait > 0:
                log.info("duty: cooling hole %d for %.1f s before %.0f ms on", hole, wait, on_ms)
                self.duty.note_cooldown(hole, wait, f"{on_ms:.0f} ms requested")
                self.sleep(wait)

    def _abort_pending(self) -> None:
        if self.journal is None or not self._pending_reservations:
            self._pending_reservations = []
            return
        try:
            self.journal.abort_conservative(reservations=list(self._pending_reservations))
        finally:
            self._pending_reservations = []

    def _record_duty(self, hole: int, t_on: float, t_off: float) -> None:
        if self.duty is not None:
            self.duty.record(hole, t_on, t_off)
        if not self._pending_reservations or self.journal is None:
            return
        # Commit the matching hole reservation (SWEEP retains siblings until done).
        match_i = next(
            (i for i, r in enumerate(self._pending_reservations) if r.hole == hole),
            None,
        )
        if match_i is None:
            return
        res = self._pending_reservations.pop(match_i)
        try:
            self.journal.commit(res, t_on=t_on, t_off=t_off)
        except JournalError:
            # Accounting failure after light: retain conservative charge for all pending.
            remaining = [res, *self._pending_reservations]
            self._pending_reservations = []
            self.journal.abort_conservative(reservations=remaining)
            raise

    def _close_lit(self, now: float) -> None:
        if self._lit is None:
            return
        hole, t_on, planned = self._lit
        self._lit = None
        self._record_duty(hole, t_on, min(now, planned))
