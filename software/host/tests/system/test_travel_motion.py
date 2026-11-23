"""T09.6 / T09.7 and MOTOR LIGHT on the simulator (firmware 2.4.0 behaviour)."""

from __future__ import annotations

import copy

import pytest

from lio.config import HwConfig, parse_config
from lio.device import DeviceError
from lio.results import Status
from lio.suite.core import REGISTRY, catalogue, run_test
from lio.suite.runner import sim_context

pytestmark = [pytest.mark.sim]


def _with_travel(cfg: HwConfig, steps: int) -> HwConfig:
    data = copy.deepcopy(cfg.data)
    data["thresholds"]["motion"]["travel"]["range_steps"] = steps
    return parse_config(data, cfg.path)


def _sub(result, sub_id):  # type: ignore[no-untyped-def]
    return next(s for s in result.subs if s.id == sub_id)


def test_travel_unmeasured_skips(cfg: HwConfig) -> None:
    catalogue()
    ctx = sim_context(cfg)
    try:
        for tid in ("T09.6", "T09.7"):
            r = run_test(ctx, REGISTRY[tid])
            assert r.status == Status.SKIP and "range_steps" in r.message
    finally:
        ctx.dev.close()


def test_full_travel_lockstep(cfg: HwConfig) -> None:
    catalogue()
    # Production margin_steps is 16384: travel must exceed 2*margin to move.
    margin = cfg.thresholds.integer("motion.travel.margin_steps")
    ctx = sim_context(_with_travel(cfg, margin * 2 + 4096))
    try:
        r = run_test(ctx, REGISTRY["T09.6"])
        assert r.status in (Status.PASS, Status.WARN), r.summary()
        assert _sub(r, "T09.6/top").status == Status.PASS
        assert _sub(r, "T09.6/bottom").status == Status.PASS
        st = ctx.dev.status()
        assert (st.as_int("pos1"), st.as_int("pos2")) == (0, 0)
    finally:
        ctx.dev.close()


def test_measurements_while_moving(cfg: HwConfig) -> None:
    catalogue()
    margin = cfg.thresholds.integer("motion.travel.margin_steps")
    ctx = sim_context(_with_travel(cfg, margin * 2 + 4096))
    try:
        r = run_test(ctx, REGISTRY["T09.7"])
        assert r.status in (Status.PASS, Status.WARN), r.summary()
        assert _sub(r, "T09.7/accepted").status == Status.PASS
        assert _sub(r, "T09.7/motion").status == Status.PASS
        assert _sub(r, "T09.7/lockstep").status == Status.PASS
        scan = r.measured["scan"]
        assert scan and {row["dir"] for row in scan} == {"up", "down"}
    finally:
        ctx.dev.close()


def test_short_travel_skips_when_margin_consumes_range(cfg: HwConfig) -> None:
    """1500 < margin 16384: truthful SKIP, not a forced PASS."""
    catalogue()
    ctx = sim_context(_with_travel(cfg, 1500))
    try:
        for tid in ("T09.6", "T09.7"):
            r = run_test(ctx, REGISTRY[tid])
            assert r.status == Status.SKIP and "margin" in r.message
    finally:
        ctx.dev.close()


def test_motor_light_gates_meas_during_motion(cfg: HwConfig) -> None:
    ctx = sim_context(cfg)
    dev = ctx.dev
    try:
        with pytest.raises(DeviceError) as e:
            dev.motor_light(True)  # not armed
        assert e.value.code == 3
        dev.motor_arm()
        dev.motor_step(1, 1500, 5)
        with pytest.raises(DeviceError) as e:
            dev.meas(1, 8, 1)  # interlock still on
        assert e.value.code == 5
        dev.motor_light(True)
        assert dev.info(refresh=True).as_int("light_in_motion") == 1
        dev.meas(1, 8, 1)  # now allowed while moving
        dev.motor_light(False)
        with pytest.raises(DeviceError) as e:
            dev.meas(1, 8, 1)
        assert e.value.code == 5
        dev.motor_stop()
    finally:
        dev.close()


def test_long_travel_is_continuous_and_exact(cfg: HwConfig) -> None:
    """A long travel: continuous jog (renewed, no stops), readings all the way, exact ends."""
    catalogue()
    # Soft top = range - margin (16384). 30000 -> ~13616 safe upward target;
    # do not require >25000 inside that bound (margin preserved).
    travel = 30000
    margin = cfg.thresholds.integer("motion.travel.margin_steps")
    safe_end = travel - margin
    ctx = sim_context(_with_travel(cfg, travel))
    try:
        sim = ctx.dev.transport.sim  # type: ignore[attr-defined]
        r0 = [m.renewals for m in sim.motors]
        r = run_test(ctx, REGISTRY["T09.7"])
        assert r.status in (Status.PASS, Status.WARN), r.summary()
        assert _sub(r, "T09.7/motion").status == Status.PASS
        assert all(m.renewals - a >= 20 for m, a in zip(sim.motors, r0, strict=True))
        scan = r.measured["scan"]
        ups = sorted(row["pos"] for row in scan if row["dir"] == "up")
        assert len(scan) > 200 and ups[0] < 2000
        assert ups[-1] > 0.9 * safe_end  # continuous readings near the safe end
        assert ups[-1] <= safe_end + 256  # stay within soft-limit bound
        st = ctx.dev.status()
        assert (st.as_int("pos1"), st.as_int("pos2")) == (0, 0)
    finally:
        ctx.dev.close()


def test_motor_tests_make_room_when_parked_at_the_top(cfg: HwConfig, tmp_path: object) -> None:
    """17 Nov on the rig: a scan left the top at its upper limit and T09.2-T09.4 errored
    (the soft limits refused their first move up). They now lower the top first."""
    from pathlib import Path

    from lio import scan

    catalogue()
    ctx = sim_context(cfg)
    try:
        assert ctx.sim is not None
        st = scan.sim_stage(ctx.dev, Path(str(tmp_path)) / "stage.json", int(ctx.sim.travel_hs))
        margin = ctx.dev.stage_top_margin()
        from lio import motion

        ok, _ = motion.move_both(ctx.dev, ctx.cfg, -margin)  # parked exactly at the top limit
        assert ok and st.room(1, +1, margin) == 0
        for tid in ("T09.2", "T09.3", "T09.4"):
            r = run_test(ctx, REGISTRY[tid])
            assert r.status in (Status.PASS, Status.WARN), r.summary()
    finally:
        ctx.dev.close()
