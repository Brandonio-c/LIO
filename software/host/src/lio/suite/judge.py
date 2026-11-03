"""Channel classification shared by T05, T06 and T08 (thresholds from the YAML)."""

from __future__ import annotations

from dataclasses import dataclass

from lio.analysis import Detection, Level, Verdict, detect_level, judge_expectation
from lio.suite.core import SuiteContext


@dataclass(frozen=True)
class Judgement:
    hole: int
    detector: str
    expect: str
    detection: Detection
    verdict: Verdict


def classify(ctx: SuiteContext, det: str, net: float, n: int, *, expect: str) -> Detection:
    """Observed level of a net signal (mean of n lit minus mean of n dark)."""
    th = ctx.th
    sigma = ctx.dark().net_sigma(det, n)
    if expect == Level.NONE:
        # Unexpected light uses its own (single) threshold: present or not.
        thr_sigma, thr_min = th.num("channel.none_max_sigma"), th.num("channel.none_min_counts")
        return detect_level(
            net,
            sigma,
            detect_sigma=thr_sigma,
            detect_min=thr_min,
            weak_sigma=thr_sigma,
            weak_min=thr_min,
        )
    return detect_level(
        net,
        sigma,
        detect_sigma=th.num("channel.detect_sigma"),
        detect_min=th.num("channel.detect_min_counts"),
        weak_sigma=th.num("channel.weak_sigma"),
        weak_min=th.num("channel.weak_min_counts"),
    )


def never_fail_absence(ctx: SuiteContext, hole: int) -> bool:
    """Fitted expected-limited channels (15, 16) only WARN.

    Unfitted holes (10, 11) are deliberately *not* lenient: light there means a
    stuck-on or misrouted channel on RAIL B.
    """
    ch = ctx.cfg.channel(hole)
    return ch.fitted and hole in ctx.th.ints("verdict.limited_holes")


def judge(ctx: SuiteContext, hole: int, det: str, net: float, n: int) -> Judgement:
    expect = ctx.cfg.channel(hole).expect_for(det)
    detection = classify(ctx, det, net, n, expect=expect)
    verdict = judge_expectation(expect, detection, never_fail_absence=never_fail_absence(ctx, hole))
    return Judgement(hole, det, expect, detection, verdict)


def observed_pattern(ctx: SuiteContext, hole: int, nets: dict[str, float], n: int) -> set[str]:
    """Detectors that see this hole, with the same thresholds as :func:`judge`.

    An expected detector counts from the weak threshold; an unexpected one only
    above the (higher) unexpected-light threshold.
    """
    out: set[str] = set()
    ch = ctx.cfg.channel(hole)
    for det, net in nets.items():
        d = classify(ctx, det, net, n, expect=ch.expect_for(det))
        if d.level != Level.NONE:
            out.add(det)
    return out
