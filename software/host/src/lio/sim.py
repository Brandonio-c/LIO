"""Simulated LIO controller speaking firmware protocol 1 on a virtual clock.

The simulator mirrors ``software/firmware/lio_firmware`` command by command
(docs/PROTOCOL.md), including its safety rules, and adds a physics-lite optical
model so that test logic can be developed and verified without hardware.

Time is virtual: :attr:`SimulatedLIO.clock` only advances when the host reads,
sleeps, or a command takes time. Output lines are timestamped at the moment
they would arrive at the host (USB latency + 115200-baud line time).

Faults (plan §5.2) are injected by name; see :data:`FAULT_NAMES` and
:meth:`Faults.parse`.
"""

from __future__ import annotations

import heapq
import itertools
import math
import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from lio.analysis import move_duration_s
from lio.config import HwConfig

FAULT_NAMES = (
    "no_adc",
    "stuck_on",  # stuck_on:<hole>   MOSFET drain-source short
    "dead_channel",  # dead_channel:<hole>  LED open circuit
    "swapped",  # swapped:<a>,<b>  gate wiring of two channels exchanged
    "rail_a_dead",
    "rail_b_dead",
    "ce_inverted",  # drivers enabled when CE is LOW
    "reversed_ingaas",
    "no_neg_rail",  # -5 V missing (bank B asleep)
    "tia_saturated",
    "opt101_no_feedback",
    "noisy_adc",
    "slow_settle",
    "chain_break",  # U1 Q7' -> U2 SER open: U2 receives nothing
    "motor_stall",
    "comms_drop",  # every Nth output line is lost
    "bank_a_asleep",  # +5 V bank switched off at low load: no ADC until POWER WAKE
    "i2c_bridged",  # SDA and SCL joined (solder bridge, shared breadboard row): no ADC
    "i2c_slow",  # lines rise too slowly (no external pull-ups): ADC answers at 100 kHz only
)

_PARAM_FAULTS = {"stuck_on", "dead_channel", "swapped"}

BAUD_CHAR_S = 10.0 / 115200.0  # 8N1
TX_BUFFER_BYTES = 64
I2C_FAST_HZ = 400000  # firmware I2C_CLOCK_HZ
I2C_SLOW_HZ = 100000  # firmware I2C_SLOW_HZ fallback  # AVR HardwareSerial transmit ring buffer


class FaultSpecError(ValueError):
    pass


@dataclass
class Faults:
    no_adc: bool = False
    stuck_on: set[int] = field(default_factory=set)
    dead_channel: set[int] = field(default_factory=set)
    swapped: dict[int, int] = field(default_factory=dict)
    rail_a_dead: bool = False
    rail_b_dead: bool = False
    ce_inverted: bool = False
    reversed_ingaas: bool = False
    no_neg_rail: bool = False
    tia_saturated: bool = False
    opt101_no_feedback: bool = False
    noisy_adc: bool = False
    slow_settle: bool = False
    chain_break: bool = False
    motor_stall: bool = False
    comms_drop: bool = False
    bank_a_asleep: bool = False
    i2c_bridged: bool = False
    i2c_slow: bool = False

    @classmethod
    def parse(cls, specs: str | Iterable[str] | None) -> Faults:
        """Parse ``"reversed_ingaas,stuck_on:5"`` or a list of such items."""
        f = cls()
        if specs is None:
            return f
        items: list[str] = []
        for s in [specs] if isinstance(specs, str) else list(specs):
            # "swapped:3,13" contains a comma, so split carefully
            items.extend(_split_fault_list(s))
        for item in items:
            name, _, arg = item.partition(":")
            name = name.strip().lower()
            if name not in FAULT_NAMES:
                raise FaultSpecError(f"unknown fault {name!r}; known: {', '.join(FAULT_NAMES)}")
            if name in _PARAM_FAULTS:
                nums = _hole_args(name, arg)
                if name == "swapped":
                    if len(nums) != 2 or nums[0] == nums[1]:
                        raise FaultSpecError("swapped needs two different holes: swapped:<a>,<b>")
                    a, b = nums
                    f.swapped[a] = b
                    f.swapped[b] = a
                else:
                    if len(nums) != 1:
                        raise FaultSpecError(f"{name} needs one hole: {name}:<n>")
                    getattr(f, name).add(nums[0])
            else:
                if arg:
                    raise FaultSpecError(f"{name} takes no argument")
                setattr(f, name, True)
        return f

    @property
    def active(self) -> list[str]:
        out: list[str] = []
        for name in FAULT_NAMES:
            v = getattr(self, name)
            if name == "swapped" and v:
                pairs = sorted({tuple(sorted(p)) for p in v.items()})
                out += [f"swapped:{a},{b}" for a, b in pairs]
            elif isinstance(v, set):
                out += [f"{name}:{h}" for h in sorted(v)]
            elif v is True:
                out.append(name)
        return out


def loop_patterns() -> list[int]:
    """The 32 LOOP TEST patterns, identical to optics.cpp cmd_loop()."""
    pats = [0x0000, 0xFFFF, 0xAAAA, 0x5555]
    lfsr = 0xACE1
    while len(pats) < 32:
        lfsr = (lfsr >> 1) ^ (0xB400 if lfsr & 1 else 0)
        pats.append(lfsr)
    return pats


def _split_fault_list(s: str) -> list[str]:
    out: list[str] = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if out and part.isdigit() and out[-1].lower().startswith("swapped:") and "," not in out[-1]:
            out[-1] += "," + part
        else:
            out.append(part)
    return out


def _hole_args(name: str, arg: str) -> list[int]:
    try:
        nums = [int(x) for x in arg.split(",") if x.strip()]
    except ValueError as e:
        raise FaultSpecError(f"{name}: holes must be integers, got {arg!r}") from e
    if any(not 1 <= n <= 16 for n in nums):
        raise FaultSpecError(f"{name}: holes must be 1-16")
    return nums


def _interp(table: list[list[float]], x: float) -> float:
    if x <= table[0][0] or x >= table[-1][0]:
        return 0.0
    for (x0, y0), (x1, y1) in itertools.pairwise(table):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return 0.0


class _Filter:
    """First-order response of a detector channel to step changes of light."""

    def __init__(self) -> None:
        self.t_ref = 0.0
        self.level_ref = 0.0
        self.target = 0.0

    def value(self, t: float, tau: float) -> float:
        if tau <= 0 or t <= self.t_ref:
            return self.target if t > self.t_ref or tau <= 0 else self.level_ref
        return self.target + (self.level_ref - self.target) * math.exp(-(t - self.t_ref) / tau)

    def set_target(self, t: float, target: float, tau: float) -> None:
        self.level_ref = self.value(t, tau)
        self.t_ref = t
        self.target = target


@dataclass
class _Motor:
    pos: int = 0  # reported (open-loop) half-steps
    physical: float = 0.0  # where the shaft actually is (motor_stall freezes it)
    start_pos: int = 0
    steps: int = 0  # signed
    t_start: float = 0.0
    t_end: float = 0.0
    moving: bool = False
    jog: bool = False

    def pos_at(self, t: float) -> int:
        if not self.moving or self.t_end <= self.t_start:
            return self.pos
        frac = min(1.0, max(0.0, (t - self.t_start) / (self.t_end - self.t_start)))
        return self.start_pos + round(self.steps * frac)


class _Refusal(Exception):
    def __init__(self, code: int, msg: str) -> None:
        super().__init__(msg)
        self.code = code
        self.msg = msg


_FAULT_ADC_MISSING = 0x01
_FAULT_I2C_ERROR = 0x02
_FAULT_WDT_TRIP = 0x04
_FAULT_FAILSAFE = 0x08

_GAIN_NAMES = ("2/3", "1", "2", "4", "8", "16")


class SimulatedLIO:
    """A simulated LIO V3 controller (firmware v2 behaviour + optics physics)."""

    FW_VERSION = "2.2.0"
    BUILD = "2026-11-03"

    def __init__(
        self,
        cfg: HwConfig,
        faults: Faults | None = None,
        *,
        seed: int | None = None,
        loop_jumper: bool = False,
    ) -> None:
        self.cfg = cfg
        self.faults = faults or Faults()
        self.loop_jumper = loop_jumper
        self.chamber_open = False  # operator action for T06.4
        sim = cfg.sim
        self._rng = random.Random(sim.integer("seed") if seed is None else seed)
        self.clock = 0.0
        self._seq = itertools.count()
        self._out: list[tuple[float, int, str]] = []  # (arrival time, order, line)
        self._tx_free = 0.0
        self._rx_buf = bytearray()
        self._lines_out = 0
        self.light_log: list[tuple[float, float, int]] = []  # (t_on, t_off, physical hole)
        self._light_since: dict[int, float] = {}
        self._powered = False
        self._boot_done = 0.0
        # Bank A (the +5 V bus) is independent of the Nano: a reset does not wake it.
        self.bank_awake_until = -math.inf
        self.wakes = 0
        self._reset_state()

    # ------------------------------------------------------------------ state

    def _reset_state(self) -> None:
        lim = self.cfg.limits
        self.mask = 0
        self.ce = {1: False, 2: False}
        self.lit_at = 0.0
        self.lit_for = 0.0
        self.lit_by_wdt = False
        self.wdt_ms = {1: lim["wdt_a_ms"], 2: lim["wdt_b_ms"]}
        self.gain_idx = 1
        self.rate = self.cfg.section.integer("adc.rate_sps")
        self.motors = [_Motor(), _Motor()]
        self.armed_until = -1.0
        self.token = self._rng.randrange(1, 0x10000)
        self.last_rx = self.clock
        self.fault_bits = 0
        self.wdt_trips = 0
        self.failsafe_trips = 0
        self.va = lim["jog_va_default"]
        self.vs = lim["jog_vs_default"]
        self.acc = lim["jog_acc_default"]
        self.busy_until = self.clock
        self._filters = {"opt101": _Filter(), "ingaas": _Filter()}
        self._end_all_light(self.clock)
        if self.adc_missing(self.clock):
            self.fault_bits |= _FAULT_ADC_MISSING

    # ------------------------------------------------------- link (host side)

    def port_opened(self) -> None:
        """DTR pulse: the board resets and runs the bootloader before setup()."""
        self._power_on(self.clock + self.cfg.sim.num("boot_s"))

    def port_closed(self) -> None:
        self._rx_buf.clear()

    def _power_on(self, banner_at: float) -> None:
        self._advance_to(self.clock)
        self._out.clear()  # anything not yet read is lost with the reset
        self._tx_free = banner_at
        self._reset_state()
        self._powered = True
        self._boot_done = banner_at
        self.busy_until = banner_at
        self.last_rx = banner_at
        self._emit_at(banner_at, "")
        self._emit_at(
            banner_at,
            f"# BOOT name=lio fw={self.FW_VERSION} proto=1 build={self.BUILD} "
            f"adc_ok={0 if self.adc_missing(banner_at) else 1} hw_wdt=0",
        )

    def receive_bytes(self, data: bytes) -> None:
        t = self.clock + self.cfg.sim.num("link_latency_s") + len(data) * BAUD_CHAR_S
        if t < self._boot_done:
            return  # the bootloader discards bytes sent before setup() runs
        self._advance_to(t)
        self.last_rx = t
        self._rx_buf.extend(data)
        while b"\n" in self._rx_buf:
            raw, _, rest = bytes(self._rx_buf).partition(b"\n")
            self._rx_buf = bytearray(rest)
            self._handle_raw_line(raw, t)

    def next_output(self, timeout: float) -> str | None:
        deadline = self.clock + max(0.0, timeout)
        while True:
            t_timer = self._next_timer_time()
            t_out = self._out[0][0] if self._out else math.inf
            if t_out <= deadline and t_out <= t_timer:
                t, _, line = heapq.heappop(self._out)
                self.clock = max(self.clock, t)
                return line
            if t_timer <= deadline:
                self._advance_to(t_timer)
                continue
            self.clock = deadline
            self._advance_to(deadline)
            return None

    def advance(self, seconds: float) -> None:
        """Host sleep: move the clock forward, running any timers that fall due."""
        self._advance_to(self.clock + max(0.0, seconds))

    # ---------------------------------------------------------------- output

    def _emit_at(self, t: float, line: str) -> None:
        start = max(t, self._tx_free)
        self._tx_free = start + (len(line) + 2) * BAUD_CHAR_S
        arrival = self._tx_free + self.cfg.sim.num("link_latency_s")
        self._lines_out += 1
        every = self.cfg.sim.integer("comms_drop_every")
        if self.faults.comms_drop and line and self._lines_out % every == 0:
            return
        heapq.heappush(self._out, (arrival, next(self._seq), line))

    # ---------------------------------------------------------------- timers

    def _armed(self, t: float) -> bool:
        return t < self.armed_until

    def _any_ce(self) -> bool:
        return self.ce[1] or self.ce[2]

    def _active(self, t: float) -> bool:
        return self._any_ce() or self._moving(t) or self._armed(t)

    def _moving(self, t: float) -> bool:
        return any(m.moving and t < m.t_end for m in self.motors)

    def _timers(self) -> list[tuple[float, int, Callable[[float], None]]]:
        """Pending firmware timers: LED off, motor done, comms-loss failsafe.

        The failsafe is scheduled only if something will still be active at its
        deadline (timers are run in time order, so earlier ones fire first).
        """
        out: list[tuple[float, int, Callable[[float], None]]] = []
        if self._any_ce():
            out.append((self.lit_at + self.lit_for, 0, self._timer_led))
        for i, m in enumerate(self.motors):
            if m.moving:
                out.append((m.t_end, 1 + i, self._timer_motor(i)))
        fs = self.last_rx + self.cfg.limits["comms_ms"] / 1000.0
        if self._any_ce() or any(m.moving for m in self.motors) or self.armed_until > fs:
            out.append((fs, 3, self._timer_failsafe))
        return out

    def _next_timer_time(self) -> float:
        return min((t for t, _, _ in self._timers()), default=math.inf)

    def _advance_to(self, t: float, move_clock: bool = True) -> None:
        """Run every timer due at or before ``t`` in time order.

        Command execution runs ahead of the host (``move_clock=False``): the host
        clock only advances when it reads, sleeps or writes.
        """
        while True:
            due = [d for d in self._timers() if d[0] <= t]
            if not due:
                break
            when, _, fn = min(due, key=lambda d: (d[0], d[1]))
            fn(when)
        if move_clock:
            self.clock = max(self.clock, t)

    def _timer_led(self, t: float) -> None:
        hole = self._single_hole(self.mask)
        on_ms = round((t - self.lit_at) * 1000)
        self._optics_off(t)
        if self.lit_by_wdt:
            self.wdt_trips += 1
            self.fault_bits |= _FAULT_WDT_TRIP
            self._emit_at(t, f"# WDT ch={hole} on_ms={on_ms} off")
        else:
            self._emit_at(t, f"# OFF ch={hole} on_ms={on_ms} off")

    def _timer_motor(self, i: int) -> Callable[[float], None]:
        def fire(t: float) -> None:
            m = self.motors[i]
            m.pos = m.start_pos + m.steps
            if not self.faults.motor_stall:
                m.physical += m.steps
            m.moving = False
            self._emit_at(t, f"# MOTOR m={i + 1} steps={abs(m.steps)} pos={m.pos} done")

        return fire

    def _timer_failsafe(self, t: float) -> None:
        idle = round((t - self.last_rx) * 1000)
        self._optics_off(t)
        self._stop_motors(t)
        self.armed_until = -1.0
        self.failsafe_trips += 1
        self.fault_bits |= _FAULT_FAILSAFE
        self.last_rx = t
        self._emit_at(t, f"# FAILSAFE reason=comms idle_ms={idle}")

    # ---------------------------------------------------------------- optics

    @staticmethod
    def _single_hole(mask: int) -> int:
        if mask == 0 or mask & (mask - 1):
            return 0
        return mask.bit_length()

    @staticmethod
    def rail_of(hole: int) -> int:
        return 2 if hole >= 10 else 1

    def _physical_mask(self) -> int:
        """Gate drive actually reaching the MOSFETs (chain/swap faults applied)."""
        m = self.mask
        if self.faults.chain_break:
            m &= 0x00FF
        out = 0
        for bit in range(16):
            if m & (1 << bit):
                hole = bit + 1
                out |= 1 << (self.faults.swapped.get(hole, hole) - 1)
        for hole in self.faults.stuck_on:
            out |= 1 << (hole - 1)
        return out

    def _driver_on(self, rail: int) -> bool:
        if (rail == 1 and self.faults.rail_a_dead) or (rail == 2 and self.faults.rail_b_dead):
            return False
        return (not self.ce[rail]) if self.faults.ce_inverted else self.ce[rail]

    def _emitting(self) -> dict[int, float]:
        """Physical hole -> fraction of its rail's current (lowest Vf takes it)."""
        emitters = self.cfg.sim.mapping("emitters")
        pm = self._physical_mask()
        out: dict[int, float] = {}
        for rail in (1, 2):
            if not self._driver_on(rail):
                continue
            cands = [
                h
                for h in range(1, 17)
                if pm & (1 << (h - 1))
                and self.rail_of(h) == rail
                and str(h) in emitters
                and h not in self.faults.dead_channel
            ]
            if not cands:
                continue
            vmin = min(float(emitters[str(h)]["vf"]) for h in cands)
            winners = [h for h in cands if float(emitters[str(h)]["vf"]) <= vmin + 0.05]
            for h in winners:
                out[h] = 1.0 / len(winners)
        return out

    def _tau(self, det: str) -> float:
        if self.faults.slow_settle:
            return self.cfg.sim.num("slow_settle_tau_ms") / 1000.0
        return self.cfg.sim.num(f"tau_ms.{det}") / 1000.0

    def _light_changed(self, t: float) -> None:
        emitters = self.cfg.sim.mapping("emitters")
        resp = self.cfg.sim.mapping("responsivity")
        k = self.cfg.sim.num("counts_per_uA")
        em = self._emitting()
        for det, flt in self._filters.items():
            total = 0.0
            for hole, frac in em.items():
                wl = self.cfg.channel(hole).wavelength_nm or 0.0
                power = float(emitters[str(hole)]["power_uw"]) * frac
                total += power * _interp(resp[det], wl) * k
            flt.set_target(t, total, self._tau(det))
        for hole in list(self._light_since):
            if hole not in em:
                self.light_log.append((self._light_since.pop(hole), t, hole))
        for hole in em:
            self._light_since.setdefault(hole, t)

    def _end_all_light(self, t: float) -> None:
        for hole, t0 in self._light_since.items():
            self.light_log.append((t0, t, hole))
        self._light_since.clear()
        for flt in self._filters.values():
            flt.set_target(t, 0.0, 0.0)

    def _latch(self, t: float, mask: int) -> None:
        self.mask = mask & 0xFFFF
        self._light_changed(t)

    def _set_ce(self, t: float, rail: int, on: bool) -> None:
        self.ce[rail] = on
        self._light_changed(t)

    def _optics_off(self, t: float) -> None:
        self._set_ce(t, 1, False)
        self._set_ce(t, 2, False)
        self._latch(t, 0)

    def _start_timer(self, t: float, req_ms: int, rail: int) -> None:
        lim = self.wdt_ms[rail]
        self.lit_by_wdt = req_ms == 0 or req_ms >= lim
        self.lit_for = (lim if self.lit_by_wdt else req_ms) / 1000.0
        self.lit_at = t

    def _ch_on(self, t: float, hole: int, ms: int) -> int:
        if self._moving(t):
            raise _Refusal(5, "motor moving")
        rail = self.rail_of(hole)
        self._set_ce(t, 1, False)
        self._set_ce(t, 2, False)
        self._latch(t, 1 << (hole - 1))
        self._start_timer(t, ms, rail)
        self._set_ce(t, rail, True)
        return round(self.lit_for * 1000)

    def adc_missing(self, t: float) -> bool:
        """No ADS1115 on the bus at time t: absent, or bank A (its supply) asleep."""
        return (
            self.faults.no_adc
            or self.faults.i2c_bridged
            or (self.faults.bank_a_asleep and t >= self.bank_awake_until)
        )

    def lit_hole(self) -> int:
        h = self._single_hole(self.mask)
        return h if h and self.ce[self.rail_of(h)] else 0

    # ------------------------------------------------------------------- ADC

    @property
    def conv_s(self) -> float:
        return 1.0 / self.rate

    def _conv_us_fw(self) -> int:
        return 1000000 // self.rate

    def _counts(self, ch: int, t: float) -> int:
        """ADS1115 reading of input ``ch`` at time ``t`` (GAIN_ONE counts, scaled)."""
        sim = self.cfg.sim
        det = self.cfg.detector_for_adc(ch)
        rng = self._rng
        if det is None:
            # floating input: wanders around a few hundred mV
            base = 1800.0 + 400.0 * math.sin(t * 0.7 + ch)
            return self._scale(base + rng.gauss(0, 60))
        photo = self._filters[det].value(t, self._tau(det))
        ambient = sim.num(f"ambient_{'open_' if self.chamber_open else ''}counts.{det}")
        offset = sim.num(f"dark_offset_counts.{det}")
        sigma = sim.num(f"dark_sigma_counts.{det}")
        if self.faults.noisy_adc:
            sigma = sim.num("noisy_adc_sigma_counts")
        noise = rng.gauss(0, math.hypot(sigma, sim.num("lit_noise_frac") * photo))
        sat = self.cfg.detectors[det].saturation_counts
        if det == "ingaas":
            if self.faults.no_neg_rail:
                mean = sim.num("no_neg_rail.mean_counts")
                return self._scale(rng.gauss(mean, sim.num("no_neg_rail.sigma_counts")))
            if self.faults.tia_saturated and photo > 1.0:
                photo *= 50.0
            value = offset + ambient + photo + noise
            if self.faults.reversed_ingaas:
                value = offset - (photo + ambient) + noise
            value = max(sim.num("reversed_clamp_counts"), min(float(sat), value))
        else:
            if self.faults.opt101_no_feedback:
                return self._scale(sim.num("opt101_no_feedback_counts") + rng.gauss(0, 1.0))
            value = max(0.0, min(float(sat), offset + ambient + photo + noise))
        return self._scale(value)

    def _scale(self, counts_gain_one: float) -> int:
        lsb = self.cfg.section.num(f"adc.lsb_mv.{_GAIN_NAMES[self.gain_idx]}")
        c = counts_gain_one * self.cfg.section.num("adc.lsb_mv.1") / lsb
        return int(max(-32768, min(32767, round(c))))

    # ----------------------------------------------------------------- motors

    @staticmethod
    def _move_duration(steps: int, vmax: float, acc: float) -> float:
        return move_duration_s(steps, vmax, acc)

    def _start_move(self, t: float, i: int, steps: int, vmax: float, acc: float, jog: bool) -> None:
        m = self.motors[i]
        if m.moving:
            self._stop_motor(t, i)
        m.start_pos = m.pos
        m.steps = steps
        m.t_start = t
        m.t_end = t + self._move_duration(steps, vmax, acc)
        m.moving = steps != 0
        m.jog = jog

    def _stop_motor(self, t: float, i: int) -> None:
        m = self.motors[i]
        if m.moving:
            new = m.pos_at(t)
            if not self.faults.motor_stall:
                m.physical += new - m.start_pos
            m.pos = new
        m.moving = False

    def _stop_motors(self, t: float) -> None:
        self._stop_motor(t, 0)
        self._stop_motor(t, 1)

    # ----------------------------------------------------- command execution

    def _handle_raw_line(self, raw: bytes, t_arrive: float) -> None:
        text = raw.decode("latin-1").replace("\r", "").replace("\0", "?")
        t = max(t_arrive, self.busy_until)
        self._advance_to(t, move_clock=False)
        if len(text) > self.cfg.limits["line_max"]:
            self._emit_at(t, "ERR ? code=6 msg=line too long")
            return
        tokens = text.upper().split()
        seq: int | None = None
        if tokens and tokens[0].startswith("@"):
            digits = tokens[0][1:]
            if digits.isdigit():
                seq = int(digits)
            tokens = tokens[1:]
        if not tokens:
            return
        ex = _Exec(self, t, tokens, seq)
        try:
            ex.dispatch()
        except _Refusal as r:
            ex.err(r.code, r.msg)
        self.busy_until = ex.t
        self._advance_to(ex.t, move_clock=False)


class _Exec:
    """One command executing on the simulated controller."""

    def __init__(self, sim: SimulatedLIO, t: float, tok: list[str], seq: int | None) -> None:
        self.sim = sim
        self.t = t + 0.0001  # parse + dispatch time
        self.tok = tok
        self.seq = seq
        self.word = tok[0]

    # -- helpers
    def _prefix(self) -> str:
        return f"@{self.seq} " if self.seq is not None else ""

    def ok(self, fields: str = "") -> None:
        sep = " " if fields else ""
        self.sim._emit_at(self.t, f"{self._prefix()}OK {self.word}{sep}{fields}")

    def err(self, code: int, msg: str) -> None:
        self.sim._emit_at(self.t, f"{self._prefix()}ERR {self.word} code={code} msg={msg}")

    def event(self, line: str) -> None:
        # Serial.print blocks while the TX buffer is full, so a command that
        # prints faster than the line drains is slowed down (live streams).
        queued_s = self.sim._tx_free - self.t
        room_s = (TX_BUFFER_BYTES - len(line) - 2) * BAUD_CHAR_S
        if queued_s > room_s:
            self.wait(queued_s - room_s)
        self.sim._emit_at(self.t, line)

    def wait(self, seconds: float) -> None:
        self.t += max(0.0, seconds)
        self.sim._advance_to(self.t, move_clock=False)

    def arg(self, i: int, lo: int, hi: int) -> int | None:
        if i >= len(self.tok):
            return None
        s = self.tok[i]
        body = s[1:] if s[:1] in "+-" else s
        if not body.isdigit():
            return None
        v = int(s)
        return v if lo <= v <= hi else None

    def need(self, i: int, lo: int, hi: int, usage: str) -> int:
        v = self.arg(i, lo, hi)
        if v is None:
            raise _Refusal(2, usage)
        return v

    def adc_read(self, ch: int) -> int:
        s = self.sim
        if s.adc_missing(self.t):
            s.fault_bits |= _FAULT_I2C_ERROR
            raise _Refusal(4, "adc read failed")
        self.wait(s.conv_s + s.cfg.sim.num("i2c_overhead_s"))
        return s._counts(ch, self.t - s.conv_s / 2)

    def adc_mean(self, ch: int, n: int) -> int:
        total = sum(self.adc_read(ch) for _ in range(n))
        # C-style rounding of (sum +/- n/2) / n with truncation toward zero
        adj = n // 2 if total >= 0 else -(n // 2)
        return int((total + adj) / n)

    # -- dispatch
    def dispatch(self) -> None:
        handlers: dict[str, Callable[[], None]] = {
            "PING": self.c_ping,
            "INFO": self.c_info,
            "STATUS": self.c_status,
            "I2C": self.c_i2c,
            "ADC": self.c_adc,
            "SR": self.c_sr,
            "CE": self.c_ce,
            "CH": self.c_ch,
            "OFF": self.c_off,
            "MEAS": self.c_meas,
            "SWEEP": self.c_sweep,
            "LOOP": self.c_loop,
            "MOTOR": self.c_motor,
            "WDT": self.c_wdt,
            "RESET": self.c_reset,
            "POWER": self.c_power,
        }
        h = handlers.get(self.word)
        if h is not None:
            h()
        elif not self.legacy():
            raise _Refusal(1, "unknown command")

    def c_power(self) -> None:
        s, lim = self.sim, self.sim.cfg.limits
        usage = f"usage: POWER WAKE [ms<={lim['wake_ms_max']}]"
        if len(self.tok) < 2 or self.tok[1] != "WAKE":
            raise _Refusal(2, usage)
        ms = lim["wake_ms_default"]
        if len(self.tok) > 2:
            ms = self.need(2, 1, lim["wake_ms_max"], usage)
        if s._any_ce():
            raise _Refusal(3, "LED on")
        if any(m.moving and self.t < m.t_end for m in s.motors):
            raise _Refusal(5, "motor moving")
        self.wait(ms / 1000.0)  # coils held at their phase: no steps, no motion
        s.wakes += 1
        s.bank_awake_until = self.t + s.cfg.sim.num("bank_awake_s")
        self.ok(f"wake_ms={ms}")

    def c_ping(self) -> None:
        self.ok(f"uptime_ms={round((self.t - self.sim._boot_done) * 1000)}")

    def c_info(self) -> None:
        s, lim = self.sim, self.sim.cfg.limits
        self.ok(
            f"fw={s.FW_VERSION} proto=1 build={s.BUILD} adc_addr=0x48 "
            f"adc_ok={0 if s.adc_missing(self.t) else 1} "
            f"gain={_GAIN_NAMES[s.gain_idx]} rate={s.rate} "
            f"settle_ms={lim['settle_ms']} wdt_a_ms={s.wdt_ms[1]} wdt_b_ms={s.wdt_ms[2]} "
            f"wdt_a_cap_ms={lim['wdt_a_cap_ms']} wdt_b_cap_ms={lim['wdt_b_cap_ms']} "
            f"comms_ms={lim['comms_ms']} arm_ms={lim['arm_ms']} step_max={lim['step_max']} "
            f"jog_max={lim['jog_max']} jog_v_max={lim['jog_v_max']} "
            f"jog_acc_max={lim['jog_acc_max']} wake_ms_max={lim['wake_ms_max']} "
            f"motion_armed={int(s._armed(self.t))} "
            f"arm_token=0x{s.token:04X} hw_wdt=0"
        )

    def c_status(self) -> None:
        s = self.sim
        m1, m2 = s.motors
        armed_ms = max(0, round((s.armed_until - self.t) * 1000)) if s._armed(self.t) else 0
        self.ok(
            f"ch={s.lit_hole()} ce1={int(s.ce[1])} ce2={int(s.ce[2])} mask=0x{s.mask:04X} "
            f"motor1={'run' if m1.moving else 'idle'} motor2={'run' if m2.moving else 'idle'} "
            f"pos1={m1.pos_at(self.t)} pos2={m2.pos_at(self.t)} armed={int(s._armed(self.t))} "
            f"armed_ms={armed_ms} va={s.va} vs={s.vs} acc={s.acc} faults=0x{s.fault_bits:02X} "
            f"wdt_trips={s.wdt_trips} failsafe_trips={s.failsafe_trips}"
        )

    def c_i2c(self) -> None:
        if len(self.tok) >= 2 and self.tok[1] == "DIAG":
            self.i2c_diag()
            return
        if len(self.tok) < 2 or self.tok[1] != "SCAN":
            raise _Refusal(2, "usage: I2C SCAN|DIAG")
        self.wait(0.02)
        if self.sim.adc_missing(self.t):
            self.ok("n=0 addrs=none")
        else:
            self.ok("n=1 addrs=0x48")

    def i2c_diag(self) -> None:
        f = self.sim.faults
        self.wait(0.01)
        powered = not (f.bank_a_asleep and self.t >= self.sim.bank_awake_until)
        missing = self.sim.adc_missing(self.t)
        pu = int(powered and not f.i2c_slow)
        ack_fast = 2 if missing or f.i2c_slow else 0
        ack_slow = 2 if missing else 0
        self.ok(
            f"sda=1 scl=1 sda_pu={pu} scl_pu={pu} bridge={int(f.i2c_bridged)} "
            f"ack_slow={ack_slow} ack_fast={ack_fast} slow_hz={I2C_SLOW_HZ} "
            f"fast_hz={I2C_FAST_HZ} hz={I2C_SLOW_HZ if f.i2c_slow else I2C_FAST_HZ} "
            f"present={int(not missing)}"
        )

    def c_adc(self) -> None:
        usage = "usage: ADC READ|CFG|STREAM ..."
        if len(self.tok) < 2:
            raise _Refusal(2, usage)
        sub = self.tok[1]
        if sub == "CFG":
            self.adc_cfg()
            return
        if self.sim.adc_missing(self.t):
            raise _Refusal(4, "ADS1115 not present")
        if sub == "READ":
            self.adc_read_cmd()
        elif sub == "STREAM":
            self.adc_stream()
        else:
            raise _Refusal(2, usage)

    def adc_read_cmd(self) -> None:
        ch = self.need(2, 0, 3, "usage: ADC READ <0-3> [n]")
        n = 1
        if len(self.tok) > 3:
            n = self.need(3, 1, 256, "n out of range")
        vals = [self.adc_read(ch) for _ in range(n)]
        mean = sum(vals) / n
        lsb = self.sim.cfg.section.num(f"adc.lsb_mv.{_GAIN_NAMES[self.sim.gain_idx]}")
        fields = f"ch={ch} raw={round(mean)} mv={mean * lsb:.3f} n={n}"
        if n > 1:
            var = sum((v - mean) ** 2 for v in vals) / (n - 1)
            fields += f" mean={mean:.2f} std={math.sqrt(var):.2f}"
        self.ok(fields)

    def adc_cfg(self) -> None:
        if len(self.tok) < 4:
            raise _Refusal(2, "usage: ADC CFG GAIN|RATE <v>")
        what, val = self.tok[2], self.tok[3]
        s = self.sim
        if what == "GAIN" and val in _GAIN_NAMES:
            s.gain_idx = _GAIN_NAMES.index(val)
            lsb = s.cfg.section.num(f"adc.lsb_mv.{val}")
            self.ok(f"gain={val} lsb_mv={lsb:.7f}")
            return
        if what == "RATE" and val.isdigit() and int(val) in s.cfg.section.ints("adc.rates_sps"):
            s.rate = int(val)
            self.ok(f"rate={s.rate}")
            return
        raise _Refusal(2, "bad gain or rate")

    def adc_stream(self) -> None:
        usage = "usage: ADC STREAM <ch> <n> <interval_ms> [hole on off]"
        ch = self.need(2, 0, 3, usage)
        n = self.need(3, 1, 2000, usage)
        iv = self.need(4, 0, 1000, usage)
        hole = on_i = off_i = 0
        s = self.sim
        if len(self.tok) > 5:
            h, a = self.arg(5, 1, 16), self.arg(6, 0, n - 1)
            b = self.arg(7, (a or 0) + 1, n) if a is not None else None
            if h is None or a is None or b is None:
                raise _Refusal(2, "bad LED schedule")
            hole, on_i, off_i = h, a, b
            if s._moving(self.t):
                raise _Refusal(5, "motor moving")
            per_us = max(iv * 1000, s._conv_us_fw() + 500)
            est_ms = (off_i - on_i) * per_us // 1000 + 20
            if est_ms > s.wdt_ms[s.rail_of(hole)]:
                raise _Refusal(3, "LED time exceeds watchdog")
        # Short streams are captured first and printed afterwards (firmware
        # STREAM_BUF_N); longer ones print live and are paced by the serial line.
        buffered = n <= s.cfg.limits["stream_buf_n"]
        captured: list[str] = []
        s._optics_off(self.t)
        t0 = self.t
        for i in range(n):
            if iv > 0 and self.t < t0 + i * iv / 1000.0:
                self.wait(t0 + i * iv / 1000.0 - self.t)
            if hole and i == on_i:
                s._ch_on(self.t, hole, 0)
            if hole and i == off_i:
                s._optics_off(self.t)
            ts = round((self.t - t0) * 1e6)
            r = self.adc_read(ch)
            line = f"# S i={i} t_us={ts} raw={r}"
            if buffered:
                captured.append(line)
            else:
                self.event(line)
        s._optics_off(self.t)
        for line in captured:
            self.event(line)
        self.ok(f"ch={ch} n={n} dur_ms={round((self.t - t0) * 1000)}")

    def c_sr(self) -> None:
        if len(self.tok) < 3 or self.tok[1] != "RAW":
            raise _Refusal(2, "usage: SR RAW <hex16>")
        h = self.tok[2]
        h = h[2:] if h.startswith("0X") else h
        if not (1 <= len(h) <= 4) or any(c not in "0123456789ABCDEF" for c in h):
            raise _Refusal(2, "usage: SR RAW <hex16>")
        s = self.sim
        s._set_ce(self.t, 1, False)
        s._set_ce(self.t, 2, False)
        s._latch(self.t, int(h, 16))
        self.ok(f"mask=0x{s.mask:04X}")

    def c_ce(self) -> None:
        rail = self.need(1, 1, 2, "usage: CE <1|2> <0|1>")
        on = self.need(2, 0, 1, "usage: CE <1|2> <0|1>")
        s = self.sim
        if on:
            h = s._single_hole(s.mask)
            if s._moving(self.t):
                raise _Refusal(5, "motor moving")
            if not h or s.rail_of(h) != rail:
                raise _Refusal(3, "needs exactly one selected hole on this rail")
            s._start_timer(self.t, 0, rail)
            s._set_ce(self.t, rail, True)
            self.ok(f"rail={rail} on=1 until_ms={round(s.lit_for * 1000)}")
        else:
            s._set_ce(self.t, rail, False)
            self.ok(f"rail={rail} on=0")

    def c_ch(self) -> None:
        usage = "usage: CH <1-16> ON [ms]"
        hole = self.need(1, 1, 16, usage)
        if len(self.tok) < 3 or self.tok[2] != "ON":
            raise _Refusal(2, usage)
        ms = 0
        if len(self.tok) > 3:
            ms = self.need(3, 1, 600000, usage)
        until = self.sim._ch_on(self.t, hole, ms)
        rail = "A" if self.sim.rail_of(hole) == 1 else "B"
        self.ok(f"ch={hole} rail={rail} until_ms={until} clamped={int(ms > 0 and ms > until)}")

    def c_off(self) -> None:
        self.sim._optics_off(self.t)
        self.ok()

    def _meas_args(self, first: int) -> tuple[int, int]:
        lim = self.sim.cfg.limits
        settle, n = lim["settle_ms"], 1
        if len(self.tok) > first:
            v = self.arg(first, 0, lim["settle_ms_max"])
            if v is None:
                raise _Refusal(2, "bad settle_ms")
            settle = v
        if len(self.tok) > first + 1:
            v = self.arg(first + 1, 1, lim["meas_n_max"])
            if v is None:
                raise _Refusal(2, "bad n")
            n = v
        return settle, n

    def _do_meas(self, hole: int, settle: int, n: int) -> str:
        s = self.sim
        if s._moving(self.t):
            raise _Refusal(5, "motor moving")
        est = settle + 2 * n * (s._conv_us_fw() // 1000 + 2) + 10
        if est > s.wdt_ms[s.rail_of(hole)]:
            raise _Refusal(3, "on-time exceeds watchdog")
        s._optics_off(self.t)
        self.wait(settle / 1000.0)
        d0, d1 = self.adc_mean(0, n), self.adc_mean(1, n)
        s._ch_on(self.t, hole, 0)
        t_on = self.t
        self.wait(settle / 1000.0)
        try:
            l0, l1 = self.adc_mean(0, n), self.adc_mean(1, n)
        finally:
            still = s.lit_hole() == hole
            t_on_ms = int((self.t - t_on) * 1000)
            s._optics_off(self.t)
        if not still:
            raise _Refusal(3, "watchdog fired during measurement")
        return f"ch={hole} dark0={d0} dark1={d1} lit0={l0} lit1={l1} t_on_ms={t_on_ms}"

    def c_meas(self) -> None:
        hole = self.need(1, 1, 16, "usage: MEAS <1-16> [settle_ms] [n]")
        settle, n = self._meas_args(2)
        self.ok(f"{self._do_meas(hole, settle, n)} settle_ms={settle} n={n}")

    def c_sweep(self) -> None:
        settle, n = self._meas_args(1)
        t0 = self.t
        for hole in range(1, 17):
            self.event(f"# M {self._do_meas(hole, settle, n)}")
        self.ok(f"n=16 settle_ms={settle} samples={n} dur_ms={round((self.t - t0) * 1000)}")

    def c_loop(self) -> None:
        if len(self.tok) < 2 or self.tok[1] != "TEST":
            raise _Refusal(2, "usage: LOOP TEST")
        s = self.sim
        s._optics_off(self.t)
        self.wait(0.01)
        # Same pattern set as the firmware; D11 has its pull-up enabled, so an
        # absent jumper reads 1, and a broken chain (U2 SER open) reads 0.
        ok = bad = 0
        saw_low = False
        for pat in loop_patterns():
            for b in range(15, -1, -1):
                expected = (pat >> b) & 1
                if not s.loop_jumper:
                    read = 1
                elif s.faults.chain_break:
                    read = expected if b < 8 else 0
                else:
                    read = expected
                saw_low |= read == 0
                ok += read == expected
                bad += read != expected
        passed = saw_low and bad == 0
        fields = f"fitted={int(saw_low)} pass={int(passed)} bits_ok={ok} bits_bad={bad}"
        self.ok(fields + ("" if saw_low else " status=not_fitted"))

    def c_wdt(self) -> None:
        usage = "usage: WDT CFG A|B <ms> within the hard cap"
        if len(self.tok) < 4 or self.tok[1] != "CFG" or self.tok[2] not in ("A", "B"):
            raise _Refusal(2, usage)
        rail = 1 if self.tok[2] == "A" else 2
        lim = self.sim.cfg.limits
        cap = lim["wdt_a_cap_ms"] if rail == 1 else lim["wdt_b_cap_ms"]
        ms = self.need(3, lim["wdt_min_ms"], cap, usage)
        self.sim.wdt_ms[rail] = ms
        self.ok(f"rail={self.tok[2]} ms={ms} cap_ms={cap}")

    def c_reset(self) -> None:
        s = self.sim
        s._optics_off(self.t)
        s._stop_motors(self.t)
        self.ok()
        # jmp 0: no bootloader, setup() runs again almost immediately
        boot = self.t + 0.05
        s._reset_state()
        s._boot_done = boot
        s.busy_until = boot
        s.last_rx = boot
        s._emit_at(boot, "")
        s._emit_at(
            boot,
            f"# BOOT name=lio fw={s.FW_VERSION} proto=1 build={s.BUILD} "
            f"adc_ok={0 if s.adc_missing(boot) else 1} hw_wdt=0",
        )
        self.t = boot

    # -- motors
    def c_motor(self) -> None:
        usage = "usage: MOTOR ARM|STOP|<m> STEP|<m> RELEASE"
        s = self.sim
        lim = s.cfg.limits
        if len(self.tok) < 2:
            raise _Refusal(2, usage)
        sub = self.tok[1]
        if sub == "ARM":
            if len(self.tok) < 3:
                raise _Refusal(2, "usage: MOTOR ARM <token>")
            h = self.tok[2][2:] if self.tok[2].startswith("0X") else self.tok[2]
            try:
                tok = int(h, 16)
            except ValueError:
                raise _Refusal(2, "usage: MOTOR ARM <token>") from None
            if tok != s.token:
                raise _Refusal(3, "wrong token")
            s.armed_until = self.t + lim["arm_ms"] / 1000.0
            self.ok(f"armed_ms={lim['arm_ms']}")
            return
        if sub == "STOP":
            s._stop_motors(self.t)
            self.ok(f"pos1={s.motors[0].pos} pos2={s.motors[1].pos}")
            return
        if sub not in ("1", "2", "ALL") or len(self.tok) < 3:
            raise _Refusal(2, usage)
        idx = [0, 1] if sub == "ALL" else [int(sub) - 1]
        if self.tok[2] == "RELEASE":
            for i in idx:
                s._stop_motor(self.t, i)
            self.ok()
            return
        step_usage = "usage: MOTOR <1|2> STEP <+-n<=2048> [rpm<=15]"
        if self.tok[2] != "STEP" or sub == "ALL":
            raise _Refusal(2, step_usage)
        steps = self.need(3, -lim["step_max"], lim["step_max"], step_usage)
        rpm = lim["rpm_default"]
        if len(self.tok) > 4:
            rpm = self.need(4, 1, lim["rpm_max"], step_usage)
        i = idx[0]
        if not s._armed(self.t):
            raise _Refusal(3, "not armed")
        if s._any_ce():
            raise _Refusal(3, "LED on")
        if s.motors[i].moving and self.t < s.motors[i].t_end:
            raise _Refusal(5, "motor moving")
        v = rpm * lim["half_steps_per_rev"] / 60.0
        s._start_move(self.t, i, steps, v, float(lim["step_acc"]), jog=False)
        self.ok(f"m={i + 1} steps={steps} rpm={rpm}")

    def legacy(self) -> bool:
        if len(self.tok) != 1:
            return False
        w = self.word
        s = self.sim
        lim = s.cfg.limits
        jogs = {"U": (3, 1), "D": (3, -1), "LU": (1, 1), "LD": (1, -1), "RU": (2, 1), "RD": (2, -1)}
        if w == "S":
            s._stop_motors(self.t)
            self.ok()
            return True
        if w in jogs:
            mask, direction = jogs[w]
            if s._any_ce():
                raise _Refusal(3, "LED on")
            steps = direction * lim["jog_max"]
            v = s.vs if mask == 3 else s.va
            for i in (0, 1):
                if mask & (1 << i):
                    s._start_move(self.t, i, steps, v, s.acc, jog=True)
            self.ok(f"steps={steps} v={v}")
            return True
        if w in ("POSL0", "POSR0"):
            m = s.motors[0 if w == "POSL0" else 1]
            m.pos = 0
            m.start_pos = 0
            self.ok()
            return True
        if w == "?":
            self.ok("legacy=U,D,LU,LD,RU,RD,S,VA<n>,VS<n>,ACC<n>,POSL0,POSR0 see=docs/PROTOCOL.md")
            return True
        limits = (
            ("ACC", lim["jog_acc_min"], lim["jog_acc_max"]),
            ("VA", lim["jog_v_min"], lim["jog_v_max"]),
            ("VS", lim["jog_v_min"], lim["jog_v_max"]),
        )
        for prefix, lo, hi in limits:
            if w.startswith(prefix):
                num = w[len(prefix) :]
                body = num[1:] if num[:1] in "+-" else num
                if not body.isdigit():
                    raise _Refusal(2, "expects a number")
                v = int(num)
                value = max(lo, min(hi, v))
                if prefix == "ACC":
                    s.acc = value
                elif prefix == "VA":
                    s.va = value
                else:
                    s.vs = value
                self.ok(f"value={value} clamped={int(value != v)}")
                return True
        return False
