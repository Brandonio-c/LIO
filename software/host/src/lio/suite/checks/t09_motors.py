"""T09 motors (plan §6): motion tests, operator present, ``--allow-motion``.

Every move is short (``thresholds.motion.test_steps`` half-steps at
``test_rpm``) and is undone before the test ends. The operator confirms the
chamber is clear before the first move of a run. T09.5 (integration with
``lio_motor_control.py``) waits for the user's approval of the reconciliation.
"""

from __future__ import annotations

import contextlib
from typing import Any

from lio.analysis import move_duration_s, stats
from lio.device import DeviceError
from lio.protocol import ErrCode
from lio.results import Status
from lio.suite.core import DETECTORS, Recorder, Skip, SuiteContext, register

SHAFT_DEG_PER_HALF_STEP = 360.0


def _op_chamber_clear(ctx: SuiteContext) -> None:
    if not ctx.cache.get("chamber_clear"):
        assert ctx.operator is not None  # guaranteed by the runner for kind M
        if not ctx.operator.confirm(
            "chamber_clear",
            "Motion test: is the chamber clear, with nothing that a stage could hit or trap?",
        ):
            raise Skip("operator: chamber not clear, no motion attempted")
        ctx.cache["chamber_clear"] = True


def _name(ctx: SuiteContext, motor: int) -> str:
    return str(ctx.cfg.section.raw(f"motors.{motor}.name"))


def _timeout(ctx: SuiteContext, steps: int, rpm: int) -> float:
    lim = ctx.cfg.limits
    v = rpm * lim["half_steps_per_rev"] / 60.0
    return move_duration_s(steps, v, float(lim["step_acc"])) + ctx.th.num("motion.done_margin_s")


def _pos(ctx: SuiteContext, motor: int) -> int:
    return ctx.dev.status().as_int(f"pos{motor}")


def _move(ctx: SuiteContext, motor: int, steps: int, rpm: int) -> tuple[bool, str]:
    """Step and wait for the done event; stops the motor if it never arrives."""
    dev = ctx.dev
    dev.motor_step(motor, steps, rpm)
    ev = dev.wait_motor_done(motor, _timeout(ctx, steps, rpm))
    if ev is None:
        dev.motor_stop()
        return False, "no '# MOTOR ... done' event in time (stopped)"
    return ev.fields.as_int("steps") == abs(steps), ev.raw


@register("T09.1", "Motion arming", "M")
def t09_1(ctx: SuiteContext, rec: Recorder) -> None:
    _op_chamber_clear(ctx)
    dev = ctx.dev
    if dev.status().as_int("armed"):
        dev.reset()  # start disarmed

    def step_refused(sub: str, name: str) -> None:
        r = dev.command("MOTOR 1 STEP +1", check=False).response
        if r.ok:
            dev.motor_stop()
        rec.check(
            sub, name, not r.ok and r.code == int(ErrCode.REFUSED), r.raw, "ERR code=3 (not armed)"
        )

    step_refused("unarmed", "MOTOR STEP without ARM is refused")
    token = dev.info(refresh=True).as_int("arm_token")
    wrong = (token ^ 0x5A5A) or 0x0001
    r = dev.command(f"MOTOR ARM {wrong:04X}", check=False).response
    rec.check(
        "wrong_token",
        "ARM with the wrong token is refused",
        not r.ok and r.code == int(ErrCode.REFUSED),
        r.raw,
        "ERR code=3",
    )
    dev.motor_arm()
    st = dev.status()
    trips_before = st.as_int("failsafe_trips")  # counted since boot
    arm_ms = ctx.cfg.limits["arm_ms"]
    rec.check(
        "armed",
        "ARM with the INFO token",
        st.as_int("armed") == 1 and 0 < st.as_int("armed_ms") <= arm_ms,
        f"armed={st.as_int('armed')} armed_ms={st.as_int('armed_ms')}",
        f"armed=1, armed_ms <= {arm_ms}",
    )
    # Wait out the arming window, keeping the link alive (else the comms
    # failsafe would disarm first and prove nothing about the expiry).
    keepalive = ctx.cfg.limits["comms_ms"] / 1000.0 / 5
    end = dev.now() + arm_ms / 1000.0 + ctx.th.num("safety.failsafe_margin_s")
    while dev.now() < end:
        dev.ping()
        dev.sleep(min(keepalive, max(0.0, end - dev.now())))
    st = dev.status()
    rec.check(
        "expired",
        f"Arming expires after {arm_ms / 1000:g} s",
        st.as_int("armed") == 0 and st.as_int("failsafe_trips") == trips_before,
        f"armed={st.as_int('armed')} failsafe_trips={st.as_int('failsafe_trips')}",
        "armed=0 without a failsafe",
    )
    step_refused("after_expiry", "MOTOR STEP after expiry is refused")


@register("T09.2", "Each motor moves both ways", "M")
def t09_2(ctx: SuiteContext, rec: Recorder) -> None:
    _op_chamber_clear(ctx)
    assert ctx.operator is not None
    dev, op = ctx.dev, ctx.operator
    steps = ctx.th.integer("motion.test_steps")
    rpm = ctx.th.integer("motion.test_rpm")
    deg = steps * SHAFT_DEG_PER_HALF_STEP / ctx.cfg.limits["half_steps_per_rev"]
    for m in (1, 2):
        name = _name(ctx, m).upper()
        dev.motor_arm()
        pos0 = _pos(ctx, m)
        done, msg = _move(ctx, m, +steps, rpm)
        rec.check(
            f"{m}/plus",
            f"Motor {m} +{steps} half-steps completes",
            done,
            msg,
            f"'# MOTOR m={m} steps={steps} ... done'",
        )
        up = op.confirm(
            f"motor_up:{m}",
            f"Did the {name} stage (motor {m}) just move UP "
            f"a little (about {deg:.0f} degrees of the motor shaft)?",
        )
        rec.check(
            f"{m}/up",
            f"Operator saw motor {m} ({name}) move up",
            up,
            "confirmed"
            if up
            else "not seen: if it moved DOWN the +steps convention is "
            f"reversed; if it did not move, check the driver, coils, pins and supply "
            f"(motor {m}: {ctx.cfg.section.raw(f'motors.{m}.pins')})",
            "+steps = up (legacy U direction)",
        )
        done, msg = _move(ctx, m, -steps, rpm)
        rec.check(
            f"{m}/minus",
            f"Motor {m} -{steps} half-steps completes",
            done,
            msg,
            f"'# MOTOR m={m} steps={steps} ... done'",
        )
        down = op.confirm(
            f"motor_down:{m}", f"Did the {name} stage move back DOWN by the same amount?"
        )
        rec.check(
            f"{m}/down",
            f"Operator saw motor {m} ({name}) move back down",
            down,
            "confirmed" if down else "not seen",
            "returned",
        )
        st = dev.status()
        idle = st.as_str(f"motor{m}") == "idle"
        rec.check(
            f"{m}/released",
            f"Motor {m} idle, coils released, back at start",
            idle and st.as_int(f"pos{m}") == pos0,
            f"motor{m}={st.as_str(f'motor{m}')} pos{m}={st.as_int(f'pos{m}')}",
            f"idle, pos{m}={pos0}",
        )


@register("T09.3", "MOTOR STOP latency", "M")
def t09_3(ctx: SuiteContext, rec: Recorder) -> None:
    _op_chamber_clear(ctx)
    dev = ctx.dev
    rpm = ctx.th.integer("motion.test_rpm")
    full = ctx.cfg.limits["step_max"]
    limit_ms = ctx.th.num("motion.stop_latency_ms")
    m = 1
    dev.motor_arm()
    pos0 = _pos(ctx, m)
    dev.motor_step(m, +full, rpm)
    dev.sleep(ctx.th.num("motion.stop_after_s"))
    reply = dev.command("MOTOR STOP")
    latency_ms = reply.rtt_s * 1000.0
    st1 = dev.status()
    dev.sleep(0.1)
    st2 = dev.status()
    moved = st2.as_int(f"pos{m}") - pos0
    rec.check(
        "latency",
        "MOTOR STOP answered",
        latency_ms < limit_ms,
        f"{latency_ms:.1f} ms",
        f"< {limit_ms:g} ms",
        latency_ms=latency_ms,
    )
    rec.check(
        "stopped",
        "Motor stopped and stays stopped",
        st2.as_str(f"motor{m}") == "idle"
        and st1.as_int(f"pos{m}") == st2.as_int(f"pos{m}")
        and 0 < moved < full,
        f"moved {moved} of {full} half-steps; motor{m}={st2.as_str(f'motor{m}')}",
        "idle, position frozen, move cut short",
    )
    if moved:
        done, msg = _move(ctx, m, -moved, rpm)
        rec.check(
            "returned",
            f"Motor {m} returned to the start",
            done and _pos(ctx, m) == pos0,
            msg,
            f"pos{m}={pos0}",
        )


@register("T09.4", "Detector noise while a motor moves", "M")
def t09_4(ctx: SuiteContext, rec: Recorder) -> None:
    _op_chamber_clear(ctx)
    ctx.require_adc()
    dev = ctx.dev
    n = ctx.th.integer("motion.emi_samples")
    iv = ctx.th.integer("motion.emi_interval_ms")
    steps = ctx.th.integer("motion.emi_steps")  # long enough to cover the streams
    rpm = ctx.th.integer("motion.test_rpm")
    warn = ctx.th.num("motion.emi_sigma_ratio_warn")
    dets = [d for d in DETECTORS if ctx.usable(d)]
    if not dets:
        raise Skip("no usable detector (see T06)")

    def sigma(det: str) -> float:
        raw = [float(s.raw) for s in dev.adc_stream(ctx.adc_channel(det), n, iv)]
        return stats(raw).std

    rest = {d: sigma(d) for d in dets}
    dev.motor_arm()
    pos0 = _pos(ctx, 1)
    dev.motor_step(1, +steps, rpm)
    moving = {d: sigma(d) for d in dets}  # ADC STREAM is allowed while moving
    still_moving = dev.status().as_str("motor1") == "run"
    dev.wait_motor_done(1, _timeout(ctx, steps, rpm))
    back = pos0 - _pos(ctx, 1)
    if back:
        _move(ctx, 1, back, rpm)
    rec.check(
        "during",
        "Streams taken while the motor was moving",
        still_moving,
        "motor still running after both streams"
        if still_moving
        else "the move ended before the streams did",
        "motor1=run",
        warn=True,
    )
    for d in dets:
        ratio = moving[d] / max(rest[d], 1.0)
        rec.check(
            d,
            f"{d} noise during motion",
            ratio <= warn,
            f"sigma {moving[d]:.2f} moving vs {rest[d]:.2f} at rest (x{ratio:.2f})"
            + ("" if ratio <= warn else ": never measure while moving"),
            f"ratio <= {warn:g}",
            warn=True,
            ratio=ratio,
            sigma_rest=rest[d],
            sigma_moving=moving[d],
        )


# ------------------------------------------------- T09.6 / T09.7: full travel


def _travel(ctx: SuiteContext) -> dict[str, float]:
    """The travel to test: from the tracked limits (lio.stage) when both are marked,
    else thresholds.motion.travel.range_steps; Skip when neither is known."""
    st = ctx.dev.stage
    if st is not None and st.known and st.limits.top is not None:
        lim = st.limits
        if lim.bottom is None:
            raise Skip(
                "bottom of travel not marked: lower the top to its lowest safe position and "
                "press 'Mark bottom here' (Motors tab) or run 'lio stage mark-bottom'"
            )
        assert lim.top is not None
        rng = min(lim.top[i] - lim.bottom[i] for i in range(2))
        margin = ctx.dev.stage_top_margin()
        if rng - margin <= 0:
            raise Skip("marked travel is shorter than the top margin")
        return {"range": rng, "margin": margin, "tracked": 1}
    rng = ctx.th.integer("motion.travel.range_steps")
    if rng <= 0:
        raise Skip(
            "travel not measured: mark the top and bottom (Motors tab, or lio stage "
            "set-top / mark-bottom), or set thresholds.motion.travel.range_steps"
        )
    margin = ctx.th.integer("motion.travel.margin_steps")
    if rng - margin <= 0:
        raise Skip("travel.margin_steps leaves no travel")
    return {"range": rng, "margin": margin, "tracked": 0}


def _start_at_bottom(ctx: SuiteContext, tr: dict[str, float]) -> None:
    """Bring the top to the bottom of the travel before the test moves it up.

    With tracked limits the host knows where it is and drives there itself (both
    motors together; refused if the two sides are not level). Without them the
    operator must confirm, since there are no limit switches."""
    if ctx.cache.get("at_bottom"):
        return
    st = ctx.dev.stage
    if tr.get("tracked") and st is not None:
        ctx.dev.status()
        a, bot = st.abs, st.limits.bottom
        assert a is not None and bot is not None
        d1, d2 = bot[0] - a[0], bot[1] - a[1]
        if d1 != d2:
            raise Skip(
                f"the two sides are not level (left {a[0]}, right {a[1]}): level them "
                "with single-motor moves first"
            )
        if d1:
            ok, msg = _lockstep(ctx, d1)
            if not ok:
                raise Skip(f"could not reach the bottom of travel: {msg}")
        ctx.cache["at_bottom"] = True
        return
    assert ctx.operator is not None
    if not ctx.operator.confirm(
        "chamber_bottom",
        "Full-travel test: is the chamber top at its LOWEST position on both sides, "
        "level, and is the chamber clear? Both motors will lift it to near the top "
        "and bring it back down.",
    ):
        raise Skip("operator: the top is not at its lowest position, no motion attempted")
    ctx.cache["at_bottom"] = True


def _positions(ctx: SuiteContext) -> tuple[int, int, bool]:
    st = ctx.dev.status()
    running = st.as_str("motor1") == "run" or st.as_str("motor2") == "run"
    return st.as_int("pos1"), st.as_int("pos2"), running


def _exact(ctx: SuiteContext, motor: int, steps: int) -> tuple[bool, str]:
    """An exact short move of one motor (chunks of at most step_max), waited for."""
    dev = ctx.dev
    rpm = ctx.th.integer("motion.travel.rpm")
    step_max = int(ctx.cfg.limits["step_max"])
    left = steps
    while left:
        n = max(-step_max, min(step_max, left))
        dev.motor_arm()
        ok, msg = _move(ctx, motor, n, rpm)
        if not ok:
            return False, msg
        left -= n
    return True, ""


def _lockstep(
    ctx: SuiteContext,
    steps: int,
    *,
    light: bool = False,
    during: Any = None,
) -> tuple[bool, str]:
    """Move both motors by ``steps`` together, continuously.

    A long move is one continuous jog of both motors (the legacy ``U``/``D``: one
    command, synchronised speed, so the two sides stay in lockstep). It is renewed
    every ``renew_steps`` before its 2048-step bound runs out (firmware >= 2.2.1
    renews a same-direction jog without a new ramp, so the motion never pauses),
    re-armed every ``rearm_s`` so ``MOTOR LIGHT`` stays in force, and stopped
    ``stop_window`` half-steps before the target. Each motor then finishes with an
    exact step move, so both end exactly on the target. ``during(p1, p2)`` is
    called repeatedly while the jog runs. Returns (ok, message); any error stops
    both motors.
    """
    dev = ctx.dev
    th = ctx.th
    speed = th.integer("motion.travel.jog_speed")
    renew = th.integer("motion.travel.renew_steps")
    rearm_s = th.num("motion.travel.rearm_s")
    poll_s = th.num("motion.travel.poll_s")
    stop_window = int(speed * poll_s * 3) + th.integer("motion.travel.stop_extra_steps")
    positive = str(ctx.cfg.section.raw("motors.positive"))
    sign = 1 if steps > 0 else -1
    up = sign > 0
    cmd = "U" if up == (positive == "up") else "D"
    a1, a2, _ = _positions(ctx)
    target = (a1 + steps, a2 + steps)
    if dev.stage is not None:  # the soft limits apply to jogs too
        for m in (1, 2):
            dev.stage.check_move(m, steps, dev.stage_top_margin())
    try:
        if abs(steps) > stop_window + renew:
            dev.motor_arm()
            if light:
                dev.motor_light(True)
            t_arm = dev.now()
            dev.command(f"VS{speed}")
            dev.command(cmd)
            renewed_at = a1
            # generous: the whole distance at speed, twice, plus a minute
            deadline = dev.now() + 2 * abs(steps) / speed + 60
            while True:
                p1, p2, running = _positions(ctx)
                if sign * (target[0] - p1) <= stop_window or sign * (target[1] - p2) <= stop_window:
                    dev.command("S")  # stop both at once
                    break
                if not running:
                    return (
                        False,
                        f"the continuous move ended early at {p1}/{p2} (bound or failsafe)",
                    )
                if dev.now() > deadline:
                    dev.command("S")
                    return False, "the continuous move took too long (stopped)"
                if abs(p1 - renewed_at) >= renew:
                    dev.command(cmd)  # a fresh 2048-step bound, no new ramp
                    renewed_at = p1
                if dev.now() - t_arm >= rearm_s:
                    dev.motor_arm()
                    if light:
                        dev.motor_light(True)
                    t_arm = dev.now()
                if during is not None:
                    during(p1, p2)
                else:
                    dev.sleep(poll_s)
            for _ in range(50):  # S stops at once; wait for STATUS to agree
                if not _positions(ctx)[2]:
                    break
                dev.sleep(0.05)
        p1, p2, _ = _positions(ctx)
        for m, rest in ((1, target[0] - p1), (2, target[1] - p2)):
            ok, msg = _exact(ctx, m, rest)
            if not ok:
                return False, f"motor {m} final approach: {msg}"
        p1, p2, _ = _positions(ctx)
        if (p1, p2) != target:
            return False, f"ended at {p1}/{p2}, target {target[0]}/{target[1]}"
    except Exception:
        dev.motor_stop()
        raise
    finally:
        if light:
            # best effort: the arm lapsing clears it anyway
            with contextlib.suppress(Exception):
                dev.motor_light(False)
    return True, f"moved {steps:+d} half-steps on both motors"


def _ref_reading(ctx: SuiteContext, holes: list[int]) -> dict[str, float]:
    """Net response of each reference hole on its expected detector(s)."""
    n = ctx.th.integer("channel.meas_n")
    out: dict[str, float] = {}
    for h in holes:
        m = ctx.dev.meas(h, None, n)
        for det in ctx.cfg.channel(h).expected_detectors:
            if ctx.usable(det):
                out[f"h{h:02d}/{det}"] = float(m.net(det))
    return out


@register("T09.6", "Full travel, both motors in lockstep", "M")
def t09_6(ctx: SuiteContext, rec: Recorder) -> None:
    """Lift the top from its lowest position to near the top and back.

    Proves both ends of the travel: every chunk moves both motors by exactly the
    commanded steps, the top end is reached, the bottom is returned to, and the
    detectors confirm the geometry really changed and came back.
    """
    tr = _travel(ctx)
    _op_chamber_clear(ctx)
    _start_at_bottom(ctx, tr)
    ctx.require_adc()
    holes = list(ctx.th.ints("motion.travel.ref_holes"))
    up = int(tr["range"] - tr["margin"])
    p0 = _positions(ctx)[:2]
    bottom = _ref_reading(ctx, holes)
    ok_up, msg_up = _lockstep(ctx, +up)
    p_top = _positions(ctx)[:2]
    rec.check(
        "top",
        "Top of travel reached",
        ok_up and p_top == (p0[0] + up, p0[1] + up),
        f"{msg_up}; positions {p_top} (start {p0})",
        f"both motors at start + {up} (range {int(tr['range'])} - margin {int(tr['margin'])})",
        pos_top=list(p_top),
    )
    if not ok_up:
        back = p0[0] - _positions(ctx)[0]
        if back:
            _lockstep(ctx, back)
        return
    top = _ref_reading(ctx, holes)
    ok_dn, msg_dn = _lockstep(ctx, -up)
    p_end = _positions(ctx)[:2]
    rec.check(
        "bottom",
        "Back at the bottom of travel",
        ok_dn and p_end == p0,
        f"{msg_dn}; positions {p_end} (start {p0})",
        "both motors back at the start position",
        pos_end=list(p_end),
    )
    again = _ref_reading(ctx, holes)
    tol = ctx.th.num("motion.travel.return_tol_frac")
    moved = ctx.th.num("motion.travel.moved_min_frac")
    floor = ctx.th.num("channel.detect_min_counts")
    for key, b in bottom.items():
        t, a = top[key], again[key]
        scale = max(abs(b), floor)
        rec.check(
            f"{key}/moved",
            f"{key}: response changes between bottom and top",
            abs(t - b) >= moved * scale,
            f"bottom {b:+.0f}, top {t:+.0f}",
            f"|top - bottom| >= {moved:g} x max(|bottom|, {floor:g})",
            warn=True,
            bottom=b,
            top=t,
        )
        rec.check(
            f"{key}/return",
            f"{key}: same response back at the bottom",
            abs(a - b) <= tol * scale,
            f"first {b:+.0f}, after the round trip {a:+.0f}",
            f"within {tol:.0%} of the first reading",
            warn=True,
            bottom=b,
            again=a,
        )
    assert ctx.operator is not None
    rec.check(
        "observed",
        "Operator: top back at its lowest position and level",
        ctx.operator.confirm(
            "travel_back", "Is the chamber top back at its lowest position, level on both sides?"
        ),
        "",
        "operator confirms",
    )


@register("T09.7", "Detectors while the chamber moves", "M")
def t09_7(ctx: SuiteContext, rec: Recorder) -> None:
    """Measure the scan holes continuously while the top travels up and back down.

    Needs firmware >= 2.4.0 (MOTOR LIGHT): MEAS is otherwise refused while a motor
    moves. Records each reading with the position, so the report has the response of
    every channel against height.
    """
    tr = _travel(ctx)
    if "light_in_motion" not in ctx.dev.info(refresh=True).values:
        raise Skip(
            "firmware has no MOTOR LIGHT (needs 2.4.0): measurements are refused while moving"
        )
    _op_chamber_clear(ctx)
    _start_at_bottom(ctx, tr)
    ctx.require_adc()
    dev = ctx.dev
    holes = list(ctx.th.ints("motion.travel.scan_holes"))
    settle = ctx.th.integer("motion.travel.scan_settle_ms")
    n = ctx.th.integer("motion.travel.scan_n")
    up = int(tr["range"] - tr["margin"])
    wdt0 = dev.status().as_int("wdt_trips")
    p0 = _positions(ctx)[:2]
    rows: list[dict[str, Any]] = []
    refused: list[str] = []
    idx = [0]
    direction = ["up"]

    def during(p1: int, p2: int) -> None:
        # Never let the LED duty budget block: a wait here would let the move run on
        # unwatched. Take the next hole that may be lit now, or none this time.
        on_ms = settle + 2 * n * 9 + 10
        for _ in range(len(holes)):
            h = holes[idx[0] % len(holes)]
            idx[0] += 1
            if dev.duty is None or dev.duty.wait_needed(h, on_ms, dev.now()) <= 0:
                break
        else:
            dev.sleep(0.05)
            return
        try:
            m = dev.meas(h, settle, n)
        except DeviceError as e:
            refused.append(f"hole {h} at {p1}: {e.msg} (code {e.code})")
            dev.sleep(0.05)
            return
        q1, q2, _ = _positions(ctx)
        rows.append({"dir": direction[0], "pos": (p1 + q1) / 2, "skew": q1 - q2, "hole": h,
                     **{f"net_{d}": m.net(d) for d in DETECTORS}})  # fmt: skip

    ok_up, msg_up = _lockstep(ctx, +up, light=True, during=during)
    direction[0] = "down"
    ok_dn, msg_dn = _lockstep(ctx, -(_positions(ctx)[0] - p0[0]), light=True, during=during)
    p_end = _positions(ctx)[:2]
    rec.measure(scan=rows)
    rec.check(
        "motion",
        "Up and back down with measurements running",
        ok_up and ok_dn and p_end == p0,
        f"{msg_up}; {msg_dn}; end {p_end} (start {p0})",
        "both chunks complete, back at the start",
    )
    rec.check(
        "accepted",
        "MEAS accepted while moving",
        not refused and len(rows) > 0,
        f"{len(rows)} readings while moving, {len(refused)} refused"
        + (f": {refused[0]}" if refused else ""),
        "no refusals (MOTOR LIGHT 1)",
    )
    skew = max((abs(r["skew"]) for r in rows), default=0)
    rec.check(
        "lockstep",
        "Motors stay together while measuring",
        skew <= 2,
        f"largest motor 1 - motor 2 difference during the run: {skew} half-steps",
        "<= 2 half-steps",
        skew=skew,
    )
    rec.check(
        "watchdog",
        "No LED watchdog trips",
        dev.status().as_int("wdt_trips") == wdt0,
        "",
        "wdt_trips unchanged",
    )
    detect = ctx.th.num("channel.detect_min_counts")
    for h in holes:
        for det in ctx.cfg.channel(h).expected_detectors:
            if not ctx.usable(det):
                continue
            vals = [r[f"net_{det}"] for r in rows if r["hole"] == h]
            if not vals:
                rec.add(f"h{h:02d}/{det}", f"Hole {h} on {det} while moving", Status.WARN,
                        "no reading taken", "")  # fmt: skip
                continue
            best = max(vals)
            at = next(r["pos"] for r in rows if r["hole"] == h and r[f"net_{det}"] == best)
            rec.check(
                f"h{h:02d}/{det}",
                f"Hole {h} ({ctx.cfg.channel(h).label}) on {det} while moving",
                best >= detect,
                f"{len(vals)} readings; best {best:+.0f} at position {at:.0f}, "
                f"range {min(vals):+.0f} to {best:+.0f}",
                f"best >= {detect:g} counts somewhere in the travel",
                warn=True,
                best=best,
                best_pos=at,
            )
