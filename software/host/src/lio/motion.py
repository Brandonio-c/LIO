"""Moving the chamber top: both motors together, continuously, ending exactly on target.

Shared by the motion tests (T09.6, T09.7) and the diagnostic sweep (lio.scan). The
settings come from ``thresholds.motion.travel`` in ``lio_hw.yaml``.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass

from lio.analysis import move_duration_s
from lio.config import HwConfig
from lio.device import LIODevice


@dataclass(frozen=True)
class MotionSettings:
    jog_speed: int  # half-steps/s for long moves
    renew_steps: int  # renew the jog this often (its bound is jog_max)
    rearm_s: float  # re-arm while moving (an arm lasts 60 s)
    poll_s: float  # position checks while moving without a callback
    stop_extra_steps: int
    rpm: int  # exact finishing moves
    done_margin_s: float

    @classmethod
    def from_config(cls, cfg: HwConfig, *, jog_speed: int | None = None) -> MotionSettings:
        th = cfg.thresholds
        return cls(
            jog_speed=jog_speed or th.integer("motion.travel.jog_speed"),
            renew_steps=th.integer("motion.travel.renew_steps"),
            rearm_s=th.num("motion.travel.rearm_s"),
            poll_s=th.num("motion.travel.poll_s"),
            stop_extra_steps=th.integer("motion.travel.stop_extra_steps"),
            rpm=th.integer("motion.travel.rpm"),
            done_margin_s=th.num("motion.done_margin_s"),
        )

    @property
    def stop_window(self) -> int:
        """Half-steps before the target at which a continuous jog is stopped."""
        return int(self.jog_speed * self.poll_s * 3) + self.stop_extra_steps


def positions(dev: LIODevice) -> tuple[int, int, bool]:
    """Firmware positions of both motors and whether either is running."""
    st = dev.status()
    running = st.as_str("motor1") == "run" or st.as_str("motor2") == "run"
    return st.as_int("pos1"), st.as_int("pos2"), running


def step_timeout(cfg: HwConfig, steps: int, rpm: int, margin_s: float) -> float:
    lim = cfg.limits
    v = rpm * lim["half_steps_per_rev"] / 60.0
    return move_duration_s(steps, v, float(lim["step_acc"])) + margin_s


def step_and_wait(
    dev: LIODevice, cfg: HwConfig, motor: int, steps: int, rpm: int, margin_s: float
) -> tuple[bool, str]:
    """One MOTOR STEP and wait for its done event; stops the motor if it never comes."""
    dev.motor_step(motor, steps, rpm)
    ev = dev.wait_motor_done(motor, step_timeout(cfg, steps, rpm, margin_s))
    if ev is None:
        dev.motor_stop()
        return False, "no '# MOTOR ... done' event in time (stopped)"
    return ev.fields.as_int("steps") == abs(steps), ev.raw


def exact(
    dev: LIODevice, cfg: HwConfig, motor: int, steps: int, s: MotionSettings
) -> tuple[bool, str]:
    """An exact move of one motor (chunks of at most step_max), waited for."""
    step_max = int(cfg.limits["step_max"])
    left = steps
    while left:
        n = max(-step_max, min(step_max, left))
        dev.motor_arm()
        ok, msg = step_and_wait(dev, cfg, motor, n, s.rpm, s.done_margin_s)
        if not ok:
            return False, msg
        left -= n
    return True, ""


def move_both(
    dev: LIODevice,
    cfg: HwConfig,
    steps: int,
    *,
    light: bool = False,
    during: Callable[[int, int], None] | None = None,
    settings: MotionSettings | None = None,
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
    both motors. The soft limits (lio.stage) apply.
    """
    s = settings or MotionSettings.from_config(cfg)
    stop_window = s.stop_window
    positive = str(cfg.section.raw("motors.positive"))
    sign = 1 if steps > 0 else -1
    cmd = "U" if (sign > 0) == (positive == "up") else "D"
    a1, a2, _ = positions(dev)
    target = (a1 + steps, a2 + steps)
    if steps == 0:
        return True, "already there"
    if dev.stage is not None:  # the soft limits apply to jogs too
        for m in (1, 2):
            dev.stage.check_move(m, steps, dev.stage_top_margin())
    try:
        if abs(steps) > stop_window + s.renew_steps:
            dev.motor_arm()
            if light:
                dev.motor_light(True)
            t_arm = dev.now()
            dev.command(f"VS{s.jog_speed}")
            dev.command(cmd)
            renewed_at = a1
            # generous: the whole distance at speed, twice, plus a minute
            deadline = dev.now() + 2 * abs(steps) / s.jog_speed + 60
            while True:
                p1, p2, running = positions(dev)
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
                if abs(p1 - renewed_at) >= s.renew_steps:
                    dev.command(cmd)  # a fresh 2048-step bound, no new ramp
                    renewed_at = p1
                if dev.now() - t_arm >= s.rearm_s:
                    dev.motor_arm()
                    if light:
                        dev.motor_light(True)
                    t_arm = dev.now()
                if during is not None:
                    during(p1, p2)
                else:
                    dev.sleep(s.poll_s)
            for _ in range(50):  # S stops at once; wait for STATUS to agree
                if not positions(dev)[2]:
                    break
                dev.sleep(0.05)
        p1, p2, _ = positions(dev)
        for m, rest in ((1, target[0] - p1), (2, target[1] - p2)):
            ok, msg = exact(dev, cfg, m, rest, s)
            if not ok:
                return False, f"motor {m} final approach: {msg}"
        p1, p2, _ = positions(dev)
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


def move_to(
    dev: LIODevice,
    cfg: HwConfig,
    height: int,
    *,
    settings: MotionSettings | None = None,
    during: Callable[[int, int], None] | None = None,
) -> tuple[bool, str]:
    """Move the top to absolute ``height`` (half-steps from the top, tracked stage).

    Both sides must be level (equal tracked positions); refuses otherwise."""
    if dev.stage is None or dev.stage.abs is None:
        raise RuntimeError("move_to needs a tracked stage position (lio.stage)")
    dev.status()
    a = dev.stage.abs
    assert a is not None
    if a[0] != a[1]:
        raise RuntimeError(f"the two sides are not level (M1/right {a[0]}, M2/left {a[1]})")
    return move_both(dev, cfg, height - a[0], settings=settings, during=during)
