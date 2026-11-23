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
import re
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
        # Incomplete raw ingress across send_raw calls (cross-call CH assembly).
        self._raw_open_fragment: bytes = b""
        # Set when OFF/CE state could not be verified: no new light until a
        # verified OFF on this connection (D04 / A03 / A24).
        self._light_blocked: str | None = None
        # Light-capable commands written to the transport (CH/CE/MEAS/SWEEP/DBG).
        self.light_sends = 0
        self.last_charge_ms = 0.0
        if isinstance(transport, SerialTransport):
            root = state_root if state_root is not None else default_state_root()
            self._state_root = root
            rig = rig_identity_from_port(transport.port)
            if self.device_lock is None:
                self.device_lock = DeviceLock(rig, root)
            # Attach journal object only — no reload/recovery/write until open()
            # acquires the canonical lease (D03 / CE02).
            if self.journal is None:
                self.journal = DutyJournal.for_rig(
                    normalize_port_identity(transport.port),
                    state_root=root,
                    window_s=th.num("duty.window_s"),
                    budget_ms=cfg.duty_budgets_ms(),
                    rail_of=cfg.duty_key,
                    mono_now=self.transport.now,
                    defer_load=True,
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
        """Acquire ownership, recover the journal, open the port, wait for BOOT.

        Ownership is taken BEFORE journal reload / serial open / POWER WAKE (D03).
        Every failure after the lease is acquired (journal reload/parse/recovery,
        transport open, banner, first wake) closes whatever transport was opened
        and then releases the lease, so a failed open never blocks the next
        owner (A02). A failed ``__enter__`` does not run ``__exit__``.
        """
        if self.device_lock is not None:
            self.device_lock.acquire()
        try:
            if self.journal is not None:
                # Reload durable state under the lease so stale objects cannot erase.
                self.journal.reload()
            t0 = self.transport.now()
            self._expect_boot = True
            try:
                self.transport.open()
                banner = self.wait_banner(self.cfg.section.num("link.boot_timeout_s"))
            finally:
                self._expect_boot = False
            self.boot_s = self.transport.now() - t0
            self.keep_awake(force=True)
        except BaseException:
            try:
                if self.transport.is_open:
                    with contextlib.suppress(Exception):
                        self.transport.close()
            finally:
                if self.device_lock is not None:
                    self.device_lock.release()
            raise
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
        """Same-owner OFF/STOP: cancellation- and ledger-independent (D04).

        Accounting is released only after a successful ``OK OFF`` AND a STATUS
        read showing both CE lines low. ``ERR OFF``, a missing reply or an
        unreadable/contradictory STATUS retains the full pending charge and
        marks the journal uncertain (A24): it never becomes safe/COMPLETE.
        """
        off_ok = False
        try:
            off_ok = self._command_unguarded("OFF", timeout=1.0, check=False).response.ok
        except Exception as e:  # must not mask the original error
            log.warning("safe_off: OFF failed: %s", e)
        try:
            self._command_unguarded("MOTOR STOP", timeout=1.0, check=False)
        except Exception as e:
            log.warning("safe_off: MOTOR STOP failed: %s", e)
        dark, why = self._verify_dark() if off_ok else (False, "OFF not acknowledged")
        if dark:
            self._light_blocked = None
            with contextlib.suppress(Exception):
                self._close_lit(self.now())
        else:
            self._retain_uncertain_if_emitting(reason=f"safe_off unverified: {why}")

    def _verify_dark(self) -> tuple[bool, str]:
        """STATUS proves both CE lines low (no rail can drive an LED)."""
        try:
            st = self._command_unguarded("STATUS", timeout=1.0).fields
            ce1, ce2 = st.as_int("ce1"), st.as_int("ce2")
        except Exception as e:
            return False, f"STATUS unavailable ({e})"
        if ce1 != 0 or ce2 != 0:
            return False, f"CE still high after OFF (ce1={ce1} ce2={ce2})"
        return True, ""

    @property
    def light_blocked(self) -> str | None:
        """Why new emission is refused (unverified OFF/CE), or None."""
        return self._light_blocked

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
        if self._raw_command_kind(cmd).startswith("light"):
            # Counted BEFORE the write: a caller comparing counts can tell a
            # pre-transmission refusal from a failure after possible emission.
            self.light_sends += 1
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
    def _firmware_tokens(cmd: str) -> list[str]:
        """Tokens exactly as firmware ``protocol.cpp`` sees one line (A01 / D01).

        The firmware drops every CR, upper-cases, splits on runs of spaces AND
        tabs, and removes a first token starting with ``@`` (numeric or not) as
        the sequence wrapper. The gate must classify the same command the board
        will execute: ``@123<TAB>CH 1 ON`` is ``CH 1 ON``.
        """
        text = cmd.replace("\r", "").upper()
        tokens = [t for t in re.split(r"[ \t]+", text) if t]
        if tokens and tokens[0].startswith("@"):
            tokens = tokens[1:]
        return tokens

    @staticmethod
    def _strip_wire_prefix(cmd: str) -> str:
        """Strip the ``@seq`` wrapper exactly as firmware does; '' if nothing remains."""
        return " ".join(LIODevice._firmware_tokens(cmd))

    @staticmethod
    def _raw_command_kind(cmd: str) -> str:
        """Classify a protocol command for the emission gate."""
        parts = LIODevice._firmware_tokens(cmd)
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
        # Cross-call fragment assembly (b'C' then b'H 1 ON ...\\n') is refused:
        # an incomplete prior write is never forwarded, so sticky host state is
        # only a belt-and-braces check if a caller cleared the exception.
        if self._raw_open_fragment:
            prior = bytes(self._raw_open_fragment)
            self._raw_open_fragment = b""
            raise OwnershipError(
                "refusing cross-call raw fragment assembly "
                f"(prior {prior!r} + {data!r}): "
                "one complete LF-terminated command per send_raw"
            )
        if not data:
            return
        # Lone CR (not part of CRLF) is refused on every path.
        if b"\r" in data.replace(b"\r\n", b""):
            raise OwnershipError(
                "refusing raw payload containing CR: use a single LF-terminated command"
            )
        # Incomplete write without a newline: never forward (blocks b'C' + b'H...').
        if b"\n" not in data:
            raise OwnershipError(
                f"refusing incomplete raw fragment {data!r}: "
                "cross-call assembly blocked; one LF-terminated command per write"
            )
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
        stripped = line.strip(" \t")
        if stripped.startswith("@"):
            # External @seq wrappers: allow non-emitting (PING/INFO) so T02.5 can
            # exercise sequence echo; refuse light-capable bodies on every path.
            body = self._strip_wire_prefix(stripped)
            kind = self._raw_command_kind(body)
            if kind not in ("safe", "other", "read", "empty"):
                raise OwnershipError(
                    f"refusing @-prefixed light-capable raw command {stripped!r}: use typed helpers"
                )
            return
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
        try:
            reply = self._command_unguarded(cmd, timeout=2.0 + n * per * 1.5)
        except Exception:
            if led is not None:
                self._abort_pending()
            raise
        if led is not None:
            # The LED edges inside a stream are not reported: keep the full
            # reserved bound, anchored at the reply (no estimated refund).
            self._record_duty(led[0], reply.t_done - bound / 1000.0, reply.t_done)
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
        """Drive one rail's CE line (D04 / A03).

        CE high can light the selected hole, so the conservative bound is reserved
        first. Release of that reservation is allowed only for a DEFINITE
        pre-emission refusal (``ERR code=3``) with STATUS proving the rail low.
        Any other error, a transport fault, a malformed ACK, or an ACK followed by
        STATUS that contradicts it (wrong/no selected hole, CE not high) keeps the
        full charge, marks the journal uncertain and blocks new light.
        """
        if not on:
            reply = self._command_unguarded(f"CE {rail} 0")
            self._close_lit(self.now())
            return reply
        hole = self._single_hole(self.status().as_int("mask"))
        if hole:
            bound = self._conservative_bound_for_hole(hole)
            self._duty_gate(hole, bound)
        elif not self._is_sim() and self.journal is not None:
            # Ambiguous mask: refuse rather than emit unaccounted light.
            raise OwnershipError("CE on refused: no single selected hole to reserve duty against")
        reserved = bool(self._pending_reservations)
        try:
            reply = self._command_unguarded(f"CE {rail} 1")
        except DeviceError as e:
            low, why = self._rail_low(rail)
            if e.code == ErrCode.REFUSED and low:
                # Firmware refused before setting CE, and STATUS agrees: no emission.
                self._drop_pending()
            else:
                self._retain_uncertain_if_emitting(
                    reason=f"CE {rail} 1 failed (code {e.code}) and rail state unverified: {why}"
                )
            raise
        except Exception as e:
            self._retain_uncertain_if_emitting(reason=f"CE {rail} 1 transport fault: {e}")
            raise
        problem = self._check_ce_ack(reply, rail, hole)
        if problem:
            if reserved or not self._is_sim():
                self._retain_uncertain_if_emitting(reason=f"CE {rail} 1 contradictory: {problem}")
            raise OwnershipError(f"CE {rail} 1 not verified: {problem}; charge retained")
        until = reply.fields.as_int("until_ms") / 1000.0
        self._lit = (hole, self.now(), self.now() + until)
        return reply

    def _rail_low(self, rail: int) -> tuple[bool, str]:
        try:
            st = self._command_unguarded("STATUS", timeout=1.0).fields
            v = st.as_int(f"ce{rail}")
        except Exception as e:
            return False, f"STATUS unavailable ({e})"
        return (v == 0), f"ce{rail}={v}"

    def _check_ce_ack(self, reply: Reply, rail: int, hole: int) -> str:
        """'' if the ACK and a fresh STATUS agree that ``hole`` is lit on ``rail``."""
        f = reply.fields
        try:
            if reply.response.word != "CE" or f.as_int("rail") != rail or f.as_int("on") != 1:
                return f"unexpected ACK {reply.response.raw!r}"
            f.as_int("until_ms")
        except Exception:
            return f"malformed ACK {reply.response.raw!r}"
        try:
            st = self._command_unguarded("STATUS", timeout=1.0).fields
            ce_hi = st.as_int(f"ce{rail}")
            sel = self._single_hole(st.as_int("mask"))
        except Exception as e:
            return f"STATUS unavailable after ACK ({e})"
        if ce_hi != 1:
            return f"ACK said on but STATUS ce{rail}={ce_hi}"
        if not hole or sel != hole:
            return f"reserved hole {hole} but STATUS selects {sel or 'none/several'}"
        return ""

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
        try:
            reply = self._command_unguarded(cmd)
        except DeviceError as e:
            if e.code in (ErrCode.REFUSED, ErrCode.BAD_ARG, ErrCode.BUSY):
                low, _why = self._rail_low(1 if rail == "A" else 2)
                if low:
                    self._drop_pending()  # definite refusal before light, verified
                    raise
            self._retain_uncertain_if_emitting(reason=f"CH {hole} failed: {e}")
            raise
        except Exception as e:
            self._retain_uncertain_if_emitting(reason=f"CH {hole} transport fault: {e}")
            raise
        f = reply.fields
        try:
            until = f.as_int("until_ms")
            bad = (
                reply.response.word != "CH"
                or f.as_int("ch") != hole
                or f.as_str("rail").upper() != rail
            )
        except ProtocolError:
            bad, until = True, -1
        if bad:
            self._retain_uncertain_if_emitting(reason=f"CH {hole} malformed ACK")
            raise DutyBudgetError(
                f"CH {hole} ACK does not match the request ({reply.response.raw!r}); "
                "worst-case charge retained"
            )
        abort = validate_reported_on_ms(bound, float(until))
        if abort:
            self._retain_uncertain_if_emitting(reason=f"CH {hole}: {abort}")
            raise DutyBudgetError(f"CH abort retaining worst-case: {abort}")
        self._close_lit(self.now())
        self._lit = (hole, self.now(), self.now() + until / 1000.0)
        return until

    def off(self) -> None:
        """OFF, then verify both CE lines low before releasing accounting (D04).

        A failed OFF or an unverified STATUS keeps the full charge, marks the
        journal uncertain, blocks new light on this connection and raises.
        """
        try:
            self._command_unguarded("OFF")
        except Exception:
            self._retain_uncertain_if_emitting(reason="OFF failed")
            raise
        dark, why = self._verify_dark()
        if not dark:
            self._retain_uncertain_if_emitting(reason=f"OFF unverified: {why}")
            raise OwnershipError(f"OFF not verified: {why}; charge retained, light blocked")
        self._light_blocked = None
        self._close_lit(self.now())

    def _retain_uncertain_if_emitting(self, *, reason: str) -> None:
        """Failed/unverified OFF or CE state: keep worst-case charge, block light.

        Pending reservations (including the one behind a lit CH/CE) are absorbed
        at their full reserved bound; the journal goes uncertain with a full
        cooldown, and this connection refuses new emission until a verified
        OFF (``_verify_dark``) clears the block.
        """
        self._lit = None
        self._light_blocked = reason
        if self.journal is None:
            self._pending_reservations = []
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
        try:
            reply = self._command_unguarded(f"MEAS {hole} {s} {k}", timeout=self.meas_timeout(s, k))
            m = Meas.from_fields(reply.fields)
        except DeviceError as e:
            # Firmware ERR after MEAS: it may have lit (watchdog fired mid-read).
            self._abort_pending()
            log.info("MEAS %d refused/failed (code %s): charge retained", hole, e.code)
            raise
        except Exception:
            self._abort_pending()
            raise
        f = reply.fields
        try:
            mismatch = (
                reply.response.word != "MEAS"
                or m.hole != hole
                or f.as_int("settle_ms") != s
                or f.as_int("n") != k
            )
        except ProtocolError:
            mismatch = True
        if mismatch:
            self._abort_pending()
            raise DutyBudgetError(
                f"MEAS {hole} reply does not match the request ({reply.response.raw!r}); "
                "worst-case charge retained"
            )
        abort = validate_reported_on_ms(bound, float(m.t_on_ms))
        if abort:
            self._abort_pending()
            raise DutyBudgetError(f"MEAS abort retaining worst-case: {abort}")
        # The firmware reports how long the LED was on; the edges are only known
        # to end by the reply, so the span is anchored there (later = conservative).
        t_end = reply.t_done
        self._record_duty(hole, t_end - m.t_on_ms / 1000.0, t_end)
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
        try:
            reply = self._command_unguarded(f"SWEEP {s} {k}", timeout=16 * self.meas_timeout(s, k))
            records = [Meas.from_fields(e.fields) for e in reply.events if e.name == "M"]
        except Exception:
            self._abort_pending()
            raise
        f = reply.fields
        try:
            header_ok = (
                reply.response.word == "SWEEP"
                and f.as_int("n") == 16
                and f.as_int("settle_ms") == s
                and f.as_int("samples") == k
            )
            dur_ms = f.as_int("dur_ms")
        except ProtocolError:
            header_ok, dur_ms = False, -1
        holes = [m.hole for m in records]
        if not header_ok or holes != list(range(1, 17)):
            self._abort_pending()
            raise DutyBudgetError(
                f"SWEEP partial/malformed ({len(records)} records, holes {holes}); "
                "retaining all charges"
            )
        for (_hole, bound), m in zip(charges, records, strict=True):
            abort = validate_reported_on_ms(bound, float(m.t_on_ms))
            if abort:
                self._abort_pending()
                raise DutyBudgetError(f"SWEEP abort retaining worst-case: {abort}")
        # Per-hole edges inside a SWEEP are not reported, so no timeline is
        # invented and nothing is refunded: every hole keeps its full reserved
        # bound, anchored at the reply (A24).
        t_end = reply.t_done
        for hole, bound in charges:
            self._record_duty(hole, t_end - bound / 1000.0, t_end)
        return Sweep(records, dur_ms)

    def dbg_state(self, state: str, arg: int, settle_ms: int, n: int) -> Fields:
        """Firmware >= 2.5.0 coupling states (``debug_states=1`` in INFO), atomic like MEAS:
        ``ce_only`` (rail ``arg``: CE high, nothing selected) or ``wrong_rail`` (hole
        ``arg`` selected, the other rail's CE high). A wrong-rail LED should stay dark;
        it is counted against the hole's duty budget anyway, in case it is miswired."""
        word = {"ce_only": "CE_ONLY", "wrong_rail": "WRONG_RAIL"}[state]
        on_ms = float(settle_ms + 2 * self._mean_ms_fw(n) + 10)
        energized_n = arg
        if state == "wrong_rail":
            hole_rail = self.cfg.channel(arg).rail
            energized = "B" if hole_rail == "A" else "A"
            energized_n = 1 if energized == "A" else 2
            # Bound by the ENERGIZED rail's verified WDT (A23), charge the hole.
            bound = self._conservative_bound_for_hole(
                arg, nominal_on_ms=on_ms, energized_rail=energized
            )
            self._duty_gate(arg, bound)
        try:
            reply = self._command_unguarded(
                f"DBG STATE {word} {arg} {settle_ms} {n}",
                timeout=self.meas_timeout(settle_ms, n),
            )
        except Exception:
            if state == "wrong_rail":
                self._abort_pending()
            raise
        f = reply.fields
        try:
            mismatch = (
                reply.response.word != "DBG"
                or f.as_str("state") != state
                or f.as_int("ce") != energized_n
                or f.as_int("ch") != (arg if state == "wrong_rail" else 0)
                or f.as_int("settle_ms") != settle_ms
                or f.as_int("n") != n
            )
            t_on = f.as_int("t_on_ms")
        except ProtocolError:
            mismatch, t_on = True, -1
        if state == "wrong_rail":
            if mismatch or validate_reported_on_ms(bound, float(t_on)):
                self._abort_pending()
                raise DutyBudgetError(
                    f"DBG {state} reply does not match the request ({reply.response.raw!r}); "
                    "worst-case charge retained"
                )
            t_end = reply.t_done
            self._record_duty(arg, t_end - t_on / 1000.0, t_end)
        elif mismatch:
            raise ProtocolError(
                f"DBG {state} reply does not match the request: {reply.response.raw!r}"
            )
        return f

    def loop_test(self) -> Fields:
        return self.command("LOOP TEST", timeout=3.0).fields

    def _set_wdt_verified(self, rail: str, ms: int) -> int:
        """WDT CFG with BOTH the ACK fields and a fresh INFO readback verified (A23).

        The firmware ACK is ``OK WDT rail=<A|B> ms=<applied> cap_ms=<cap>``. A
        missing, malformed or contradictory ACK/readback never defaults to the
        request: refuse before light.
        """
        try:
            ack = self.wdt_cfg(rail, ms)
            ack_rail = ack.as_str("rail").upper()
            ack_ms = ack.as_int("ms")
        except (KeyError, ValueError, ProtocolError) as e:
            raise DutyBudgetError(f"refuse before light: WDT CFG ACK malformed ({e})") from e
        try:
            rb = int(self.info(refresh=True).as_int(f"wdt_{rail.lower()}_ms"))
        except Exception as e:
            raise DutyBudgetError(f"refuse before light: WDT readback unavailable ({e})") from e
        if ack_rail != rail.upper() or ack_ms != ms or rb != ms:
            raise DutyBudgetError(
                f"refuse before light: WDT {rail} request {ms} ms but ACK rail={ack_rail} "
                f"ms={ack_ms}, readback {rb} ms"
            )
        return ms

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
        energized_rail: str | None = None,
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

        # The rail whose CE is driven bounds the exposure (wrong-rail DBG energizes
        # the OTHER rail); the hole's own budget is still what gets charged.
        rail = energized_rail or self.cfg.channel(hole).rail
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
            # Raise to covering need (2→8→8→2); ACK and readback must both agree.
            wdt = self._set_wdt_verified(rail, int(need))
        elif wdt > need and may_lower:
            wdt = self._set_wdt_verified(rail, int(need))
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

    @property
    def exposure_bound(self) -> str:
        """How LED on-time is bounded on this connection (recorded with every run).

        ``simulated``: virtual board. ``hardware_watchdog``: the board reports a
        hardware watchdog (INFO hw_wdt=1) that resets it, dropping CE, if the
        firmware stops servicing. ``cooperative_unproven``: real board without a
        hardware watchdog whose owner acknowledged, in lio_hw.yaml
        ``timing.real_port_admission``, that the cooperative firmware watchdog is
        accepted WITHOUT a proven bound on a firmware hang. ``refused``: none of
        these; every emission on this port is refused before transmission.
        """
        if self._is_sim():
            return "simulated"
        try:
            hw = int(self.info().as_int("hw_wdt"))
        except Exception:
            hw = 0
        if hw == 1:
            return "hardware_watchdog"
        timing = self.cfg.data.get("timing") or {}
        policy = str(timing.get("real_port_admission") or "refuse")
        if policy == "cooperative_unproven_acknowledged":
            return "cooperative_unproven"
        return "refused"

    def _require_real_port_timing(self) -> None:
        """Refuse emission on a real port without a supported exposure bound (D05/M1).

        No timing margin is invented: without a hardware watchdog the bound on a
        firmware hang is unproven, and light is admitted only under the owner's
        explicit, recorded acknowledgement.
        """
        if self.exposure_bound == "refused":
            raise DutyBudgetError(
                "refuse before light: no finite exposure bound on this real port "
                "(INFO hw_wdt=0, and lio_hw.yaml timing.real_port_admission is not "
                "'cooperative_unproven_acknowledged')"
            )

    def _duty_gate(self, hole: int, on_ms: float) -> None:
        """Gate light through the durable journal when present; else DutyTracker.

        Over-budget requests (``on_ms`` greater than the absolute budget) are
        rejected before any transport write. Window-full cases wait, then reserve.
        """
        self._duty_gate_many([(hole, on_ms)])

    def _duty_gate_many(self, charges: list[tuple[int, float]]) -> None:
        if not charges:
            return
        if self._light_blocked:
            raise OwnershipError(f"light blocked until a verified OFF: {self._light_blocked}")
        self._require_real_port_timing()
        # The conservative charge about to be reserved (callers record it as
        # permanent run cost, also when the operation then fails).
        self.last_charge_ms = float(sum(on for _h, on in charges))
        if self.journal is not None:
            # Wait until the whole charge set fits (same-rail siblings accumulate),
            # then atomic multi-reserve. Per-hole waits alone miss SWEEP x16.
            wait = self.journal.wait_needed_many(charges, self.now())
            if wait > 0:
                hole0, on0 = charges[0]
                log.info(
                    "duty journal: cooling %.1f s before %d-charge set (first hole %d, %.0f ms)",
                    wait,
                    len(charges),
                    hole0,
                    on0,
                )
                if self.duty is not None:
                    self.duty.note_cooldown(hole0, wait, f"{len(charges)}-charge set")
                self.sleep(wait)
            # A refused reservation leaves any existing pending tracking intact.
            self._pending_reservations = self.journal.reserve_many(charges)
            return
        if self.duty is None:
            return
        for hole, on_ms in charges:
            wait = self.duty.wait_needed(hole, on_ms, self.now())
            if wait > 0:
                log.info("duty: cooling hole %d for %.1f s before %.0f ms on", hole, wait, on_ms)
                self.duty.note_cooldown(hole, wait, f"{on_ms:.0f} ms requested")
                self.sleep(wait)

    def _drop_pending(self) -> None:
        """Clear in-memory and durable pending without uncertain cooldown."""
        self._pending_reservations = []
        if self.journal is not None:
            with contextlib.suppress(Exception):
                self.journal.drop_pending()

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
