"""T09 motors (plan §6): motion tests, operator present, ``--allow-motion``.

Every move is short (``thresholds.motion.test_steps`` half-steps at
``test_rpm``) and is undone before the test ends. The operator confirms the
chamber is clear before the first move of a run. T09.5 (integration with
``lio_control.py``) waits for the user's approval of the reconciliation.
"""

from __future__ import annotations

from lio.analysis import move_duration_s, stats
from lio.protocol import ErrCode
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
        st.as_int("armed") == 0 and st.as_int("failsafe_trips") == 0,
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
