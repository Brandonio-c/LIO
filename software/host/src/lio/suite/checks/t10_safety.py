"""T10 safety behaviours (plan §6).

Deviations from the plan text, both to limit LED stress (RAIL A runs above the
LEDs' rating):

- T10.2 checks the clamp to the default watchdog from the ``CH`` reply and
  turns the LED off at once; the cut-off itself is timed with the watchdog
  lowered to ``thresholds.watchdog.test_ms``.
- T10.3 cannot hold an LED on until the comms failsafe: the watchdog caps
  (5 s / 10 s) are never longer than the 10 s comms timeout, so the watchdog
  always fires first. The failsafe is observed with motion *armed* (no motor
  command is sent, nothing moves) and the off state is checked afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass

from lio.device import DeviceError
from lio.protocol import ErrCode, Event, Fields
from lio.results import Status
from lio.suite.checks.t07_t08_timing_sweep import step_response
from lio.suite.core import DETECTORS, Recorder, SuiteContext, hole_id, register


def _safe_state(st: Fields) -> tuple[bool, str]:
    keys = ("ch", "ce1", "ce2", "mask", "armed")
    shown = " ".join(f"{k}={st.as_str(k)}" for k in keys)
    ok = (
        all(st.as_int(k) == 0 for k in keys)
        and st.as_str("motor1") == st.as_str("motor2") == "idle"
    )
    return ok, shown


def _dark_now(ctx: SuiteContext) -> tuple[bool, str]:
    n = ctx.th.integer("channel.meas_n")
    vals = {d: ctx.dev.adc_read(ctx.adc_channel(d), n).mean for d in DETECTORS}
    ok = all(ctx.is_dark(d, v, n) for d, v in vals.items())
    return ok, ", ".join(f"{d} {v:.0f}" for d, v in vals.items())


def _check_off(ctx: SuiteContext, rec: Recorder, sub: str, when: str) -> None:
    ok, shown = _safe_state(ctx.dev.status())
    rec.check(
        f"{sub}/status",
        f"STATUS safe {when}",
        ok,
        shown,
        "ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle",
    )
    if ctx.has_adc():
        dark, readings = _dark_now(ctx)
        rec.check(f"{sub}/dark", f"Detectors dark {when}", dark, readings, "dark +- k sigma")


@register("T10.1", "Power-up dark state")
def t10_1(ctx: SuiteContext, rec: Recorder) -> None:
    dev = ctx.dev
    probe = 1 << (ctx.th.ints("settling.holes")[0] - 1)
    dev.sr_raw(probe)  # a non-default state (CE stays low: no light)
    dev.reset()
    _check_off(ctx, rec, "reset", "after RESET")
    dev.sr_raw(probe)
    dev.close()
    dev.open()
    _check_off(ctx, rec, "reopen", "after a port reopen")


def _working_hole(ctx: SuiteContext, preferred: int) -> tuple[int, str] | None:
    """A hole on the preferred hole's rail whose light a usable detector sees.

    The preferred hole comes first; a dead LED there must not turn into a
    safety failure, so another channel on the same rail is used instead.
    """
    rail = ctx.cfg.channel(preferred).rail
    chans = ctx.channels()
    for hole in [preferred] + [h for h in ctx.cfg.rail_holes(rail) if h != preferred]:
        for det in ctx.cfg.channel(hole).expected_detectors:
            if ctx.usable(det) and ctx.is_lit(
                det, chans[hole].meas.lit(det), ctx.th.integer("channel.meas_n")
            ):
                return hole, det
    return None


@register("T10.2", "On-time watchdog")
def t10_2(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    dev = ctx.dev
    test_ms = ctx.th.integer("watchdog.test_ms")
    tol_ms = ctx.th.num("watchdog.tolerance_ms")
    ask_ms = ctx.th.integer("watchdog.request_ms")
    for preferred in ctx.th.ints("watchdog.holes"):
        rail = ctx.cfg.channel(preferred).rail
        pick = _working_hole(ctx, preferred)
        if pick is None:
            rec.add(
                rail,
                f"RAIL {rail} watchdog",
                Status.SKIP,
                f"no working channel on RAIL {rail} to observe (see T05.2)",
            )
            continue
        hole, det = pick
        pre = f"{rail}/{hole_id(hole)}"
        default = ctx.cfg.wdt_ms(rail)
        # Raw command: the LED is turned off again within a round trip, so the
        # duty tracker need not reserve the full clamped on-time.
        reply = dev.command(f"CH {hole} ON {ask_ms}")
        dev.off()
        until, clamped = reply.fields.as_int("until_ms"), reply.fields.as_int("clamped")
        rec.check(
            f"{pre}/clamp",
            f"CH {hole} ON {ask_ms} clamped to RAIL {rail} limit",
            until == default and clamped == 1,
            f"until_ms={until} clamped={clamped}",
            f"until_ms={default} clamped=1",
        )
        dev.wdt_cfg(rail, test_ms)
        n_ev = len(dev.events)
        until = dev.ch_on(hole, ask_ms)  # may first wait out the duty budget
        t_on = dev.now()  # the CH reply: the LED has been on for about one round trip
        adc = ctx.adc_channel(det)
        seen_lit = False
        t_dark: float | None = None
        deadline = t_on + (test_ms + tol_ms) / 1000.0 + 1.0
        while dev.now() < deadline:
            v = float(dev.adc_read(adc).raw)
            if ctx.is_lit(det, v):
                seen_lit = True
            elif seen_lit and ctx.is_dark(det, v):
                t_dark = dev.now() - t_on
                break
        dev.drain(0.05)
        wdt = [e for _, e in dev.events[n_ev:] if e.name == "WDT"]
        # The detector needs its own settling time (T07.1) to show the LED off.
        step = step_response(ctx, hole)
        detector_ms = step[1].t_settle_ms if step is not None else 0.0
        limit_s = (test_ms + tol_ms + detector_ms) / 1000.0
        rec.check(
            f"{pre}/lit",
            f"Hole {hole} lit before the watchdog",
            seen_lit,
            "light seen" if seen_lit else f"no light on {det}",
            "light seen",
        )
        rec.check(
            f"{pre}/off",
            "Light gone after the watchdog limit",
            t_dark is not None and t_dark <= limit_s,
            f"dark after {t_dark * 1000:.0f} ms" if t_dark is not None else "never dark",
            f"<= {limit_s * 1000:.0f} ms: limit {until} + tolerance {tol_ms:g} + detector "
            f"settling {detector_ms:.1f} ms",
            t_dark_ms=None if t_dark is None else t_dark * 1000,
        )
        on_ms = wdt[0].fields.as_int("on_ms") if wdt else None
        rec.check(
            f"{pre}/event",
            "'# WDT' received",
            bool(wdt) and on_ms is not None and on_ms <= test_ms + tol_ms,
            wdt[0].raw if wdt else "no '# WDT' event",
            f"'# WDT' with on_ms <= {test_ms + tol_ms:g}",
        )
        dev.wdt_cfg(rail, default)


@dataclass(frozen=True)
class FailsafeObservation:
    armed_before: bool
    event: Event | None
    status_after: Fields
    idle_s: float


def _failsafe(ctx: SuiteContext) -> FailsafeObservation:
    """Arm (no motion), go silent past the comms timeout, then look (cached)."""
    if "failsafe" not in ctx.cache:
        dev = ctx.dev
        comms_s = ctx.cfg.limits["comms_ms"] / 1000.0
        idle_s = comms_s + ctx.th.num("safety.failsafe_margin_s")
        dev.motor_arm()
        armed = dev.status().as_int("armed") == 1
        n_ev = len(dev.events)
        dev.sleep(idle_s)  # send nothing
        dev.drain(0.1)
        ev = next((e for _, e in dev.events[n_ev:] if e.name == "FAILSAFE"), None)
        ctx.cache["failsafe"] = FailsafeObservation(armed, ev, dev.status(), idle_s)
    obs: FailsafeObservation = ctx.cache["failsafe"]
    return obs


@register("T10.3", "Comms-loss failsafe")
def t10_3(ctx: SuiteContext, rec: Recorder) -> None:
    obs = _failsafe(ctx)
    comms_ms = ctx.cfg.limits["comms_ms"]
    tol = ctx.th.num("watchdog.tolerance_ms")
    idle = obs.event.fields.as_int("idle_ms") if obs.event is not None else None
    rec.check(
        "event",
        "'# FAILSAFE' after the comms timeout",
        idle is not None and comms_ms <= idle <= comms_ms + tol,
        obs.event.raw if obs.event else f"no event after {obs.idle_s:g} s of silence",
        f"idle_ms {comms_ms}-{comms_ms + tol:g}",
    )
    ok, shown = _safe_state(obs.status_after)
    rec.check(
        "status",
        "Everything off after the failsafe",
        ok,
        shown,
        "ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle",
    )
    trips = obs.status_after.as_int("failsafe_trips")
    rec.check("trips", "Failsafe counted", trips >= 1, f"failsafe_trips={trips}", ">= 1")


@register("T10.4", "Single-channel invariant")
def t10_4(ctx: SuiteContext, rec: Recorder) -> None:
    dev = ctx.dev
    for mask in ctx.th.ints("safety.multi_masks"):
        holes = [b + 1 for b in range(16) if mask & (1 << b)]
        rails = sorted({ctx.cfg.channel(h).rail for h in holes} or {"A"})
        for rail in rails:
            ce = 1 if rail == "A" else 2
            dev.sr_raw(mask)
            try:
                dev.ce(ce, True)
                refused, msg = False, "accepted"
            except DeviceError as e:
                refused, msg = e.code == int(ErrCode.REFUSED), f"ERR code={e.code} {e.msg}"
            st = dev.status()
            low = st.as_int("ce1") == 0 and st.as_int("ce2") == 0
            rec.check(
                f"m{mask:04X}/ce{ce}",
                f"SR RAW 0x{mask:04X} then CE {ce} 1",
                refused and low,
                f"{msg}; ce1={st.as_int('ce1')} ce2={st.as_int('ce2')}",
                "refused (code 3), CE stays low",
            )
            dev.off()


@register("T10.5", "Motion disarmed after comms loss")
def t10_5(ctx: SuiteContext, rec: Recorder) -> None:
    obs = _failsafe(ctx)
    rec.check(
        "before",
        "Armed before the silence",
        obs.armed_before,
        f"armed={int(obs.armed_before)}",
        "armed=1",
    )
    armed = obs.status_after.as_int("armed")
    rec.check(
        "after",
        "Disarmed after the failsafe",
        armed == 0,
        f"armed={armed} armed_ms={obs.status_after.as_int('armed_ms')}",
        "armed=0",
    )
