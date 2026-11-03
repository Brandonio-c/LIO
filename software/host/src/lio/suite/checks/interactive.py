"""Interactive steps (plan §6): T04.4 walk test, T05.6 driver current, T06.4 ambient.

They need an operator (``--interactive``); on the simulator a simulated
operator answers from the simulator's physical truth. Answering ``a`` at any
prompt aborts the test with everything off.
"""

from __future__ import annotations

import re

from lio.config import HwConfig
from lio.operator import Operator
from lio.results import Status
from lio.suite.core import (
    DETECTORS,
    Recorder,
    SuiteContext,
    hole_id,
    register,
    skip_unusable,
)


def walk_groups(cfg: HwConfig) -> tuple[list[int], list[int], list[int]]:
    """Fitted holes seen by eye, by a phone camera, and not at all (SWIR)."""
    th = cfg.thresholds
    vis_max, cam_max = th.num("interactive.visible_max_nm"), th.num("interactive.camera_max_nm")
    eye, camera, unseen = [], [], []
    for ch in cfg.channels:
        if not ch.fitted or ch.wavelength_nm is None:
            continue
        if ch.wavelength_nm < vis_max:
            eye.append(ch.hole)
        elif ch.wavelength_nm < cam_max:
            camera.append(ch.hole)
        else:
            unseen.append(ch.hole)
    return eye, camera, unseen


def _labels(cfg: HwConfig, holes: list[int]) -> str:
    return ", ".join(f"{h} ({cfg.channel(h).label})" for h in holes)


def _operator(ctx: SuiteContext) -> Operator:
    assert ctx.operator is not None  # guaranteed by the runner for kind I
    return ctx.operator


def _cool_down(ctx: SuiteContext, holes: list[int], on_ms: float) -> None:
    """Respect the LED duty budget before the operator is told to watch."""
    need = ctx.dev.duty.wait_needed if ctx.dev.duty is not None else None
    if need is not None:
        now = ctx.dev.now()
        wait = max(need(h, on_ms, now) for h in holes)
        if wait > 0:
            _operator(ctx).inform(f"Waiting {wait:.0f} s for the LED duty budget to recover...")
    ctx.dev.wait_for_duty(holes, on_ms)


@register("T04.4", "Walk test (operator)", "I")
def t04_4(ctx: SuiteContext, rec: Recorder) -> None:
    op, dev, cfg = _operator(ctx), ctx.dev, ctx.cfg
    walk_ms = ctx.th.integer("interactive.walk_ms")
    eye, camera, unseen = walk_groups(cfg)
    _cool_down(ctx, list(range(1, 17)), walk_ms)
    op.act(
        "walk_start",
        f"Walk test: holes 1-16 light one at a time for {walk_ms} ms each. "
        f"Watch holes {eye[0]}-{eye[-1]} by eye and hold a phone camera on holes "
        f"{_labels(cfg, camera)}.",
    )
    for hole in range(1, 17):
        until = dev.ch_on(hole, walk_ms)
        dev.wait_event("OFF", until / 1000.0 + 0.5)
    dev.off()
    for key, holes, how in (
        ("walk_visible", eye, "by eye"),
        ("walk_camera", camera, "through the camera"),
    ):
        seen = op.confirm(
            key, f"Did holes {_labels(cfg, holes)} light {how}, one at a time, in that order?"
        )
        group = key.split("_")[1]
        if seen:
            rec.check(
                group,
                f"Holes {holes[0]}-{holes[-1]} seen {how} in order",
                True,
                "confirmed",
                "operator confirms the order",
            )
            continue
        note = op.text(
            f"{key}_note",
            "Which hole number(s) were missing, out of order, or lit "
            "together with another? (e.g. 3 4)",
        )
        named = sorted({int(t) for t in re.findall(r"\d+", note) if int(t) in holes})
        for h in named:  # attributed to channels, so the verdict can count them
            rec.add(
                f"{hole_id(h)}/{group}",
                f"Hole {h} in the walk test",
                Status.FAIL,
                f"operator: {note}; possible swapped gate wiring, dead or stuck-on channel",
                "seen in order",
            )
        if not named:
            rec.check(
                group,
                f"Holes {holes[0]}-{holes[-1]} seen {how} in order",
                False,
                f"not as expected{': ' + note if note else ''}; possible swapped gate "
                "wiring, dead or stuck-on channel",
                "operator confirms the order",
            )
    rec.add(
        "swir",
        f"Holes {unseen[0]}-{unseen[-1]}",
        Status.SKIP,
        "n/a: SWIR emitters cannot be seen; covered optically by T05.2/T05.3",
    )


@register("T05.6", "Driver current with a meter (operator)", "I")
def t05_6(ctx: SuiteContext, rec: Recorder) -> None:
    op, dev, th = _operator(ctx), ctx.dev, ctx.th
    attempts = th.integer("interactive.meter_attempts")
    warn_f, fail_f = (
        th.num("interactive.current_warn_frac"),
        th.num("interactive.current_fail_frac"),
    )
    for rail in ("A", "B"):
        hole = th.integer(f"interactive.meter_holes.{rail}")
        flash = th.integer(f"interactive.meter_flash_ms.{rail}")
        nominal = ctx.cfg.section.num(f"rails.{rail}.current_ma")
        driver = ctx.cfg.section.raw(f"rails.{rail}.driver")
        op.inform(
            f"RAIL {rail}: put the multimeter (mA range) in series with the {driver} "
            f"output to the LEDs. Hole {hole} will flash for {flash} ms per attempt."
        )
        value: float | None = None
        for k in range(1, attempts + 1):
            _cool_down(ctx, [hole], flash)
            op.act(
                f"meter_ready:{rail}",
                f"Attempt {k}/{attempts}: get ready to read the meter during the flash.",
            )
            until = dev.ch_on(hole, flash)
            dev.wait_event("OFF", until / 1000.0 + 1.0)
            value = op.number(f"meter_ma:{rail}", f"Current on RAIL {rail} during the flash", "mA")
            if value is not None:
                break
        if value is None:
            rec.add(
                f"{rail}/{hole_id(hole)}",
                f"RAIL {rail} driver current",
                Status.SKIP,
                "no reading entered",
            )
            continue
        frac = abs(value - nominal) / nominal
        status = Status.PASS if frac <= warn_f else Status.WARN if frac <= fail_f else Status.FAIL
        rec.add(
            f"{rail}/{hole_id(hole)}",
            f"RAIL {rail} driver current (hole {hole})",
            status,
            f"{value:g} mA vs nominal {nominal:g} mA ({frac * 100:.0f} % off)"
            + ("" if status == Status.PASS else f"; check the {driver} current setting"),
            f"within {warn_f * 100:g} % (WARN to {fail_f * 100:g} %)",
            ma=value,
            nominal_ma=nominal,
        )


@register("T06.4", "Ambient light sensitivity (operator)", "I")
def t06_4(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    op, dev = _operator(ctx), ctx.dev
    n = ctx.th.integer("adc.dark_samples")
    dets = [d for d in DETECTORS if not skip_unusable(ctx, rec, d, d, f"{d} ambient")]
    if not dets:
        return
    dev.off()

    def read() -> dict[str, float]:
        return {d: dev.adc_read(ctx.adc_channel(d), n).mean for d in dets}

    closed = read()
    op.act("open_chamber", "Open the chamber lid, with the room lights as normal.")
    opened = read()
    op.act("close_chamber", "Close the chamber lid fully.")
    again = read()
    for d in dets:
        delta = opened[d] - closed[d]
        rec.add(
            d,
            f"{d} change with the lid open",
            Status.PASS,
            f"recorded: {delta:+.0f} counts ({closed[d]:.0f} -> {opened[d]:.0f})",
            "recorded only (quantifies light-tightness)",
            delta_counts=delta,
        )
        back = ctx.is_dark(d, again[d], n)
        rec.check(
            f"{d}/closed",
            f"{d} back to dark after closing",
            back,
            f"{again[d]:.0f} vs dark {ctx.dark().mean(d):.0f}"
            + ("" if back else ": lid not fully closed, or a light leak"),
            "dark +- k sigma",
            warn=True,
        )
