"""Channel classification shared by T05, T06 and T08 (thresholds from the YAML)."""

from __future__ import annotations

from dataclasses import dataclass

from lio.analysis import Detection, Level, Verdict, detect_level, judge_expectation
from lio.config import ConfigError
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


def out_of_range(ctx: SuiteContext, hole: int, det: str) -> bool:
    """True if ``det`` is not meant to see this hole and such readings are not judged.

    With ``channel.judge_out_of_range: false`` a fitted hole is judged only by the
    detector(s) its ``expect`` names. Unfitted holes stay strict: light there means a
    stuck-on or misrouted channel.
    """
    ch = ctx.cfg.channel(hole)
    try:
        strict = bool(ctx.th.raw("channel.judge_out_of_range"))
    except ConfigError:
        strict = True  # older configs: the previous behaviour
    return ch.fitted and not strict and ch.expect_for(det) == Level.NONE


def unresolvable_limit(ctx: SuiteContext) -> float | None:
    """Detection limit (counts) above which a missing signal is "not resolved", not FAIL.

    ``channel.unresolvable_limit_counts`` (owner calibration 2026-11-25): a reading whose
    detection threshold is this high cannot tell a weak channel from a dead one (the
    raw, non-integrated InGaAs MEAS: sigma_net ~17 counts -> limit ~175 counts, while an
    empty chamber returns 5-40 counts). Absent key: every absence is judged (old rule).
    """
    try:
        return float(ctx.th.num("channel.unresolvable_limit_counts"))
    except ConfigError:
        return None


def unstable_is_warn(ctx: SuiteContext) -> bool:
    """``repeatability.unstable_status: warn`` (owner 2026-11-25): excess dispersion in
    T05.5 / T08.2 is a quality WARN (the channel still responds), not a FAIL."""
    try:
        return str(ctx.th.raw("repeatability.unstable_status")) == "warn"
    except ConfigError:
        return False


def absence_unresolved(ctx: SuiteContext, detection: Detection) -> bool:
    lim = unresolvable_limit(ctx)
    return lim is not None and detection.weak_threshold > lim


def judge(ctx: SuiteContext, hole: int, det: str, net: float, n: int) -> Judgement:
    expect = ctx.cfg.channel(hole).expect_for(det)
    detection = classify(ctx, det, net, n, expect=expect)
    verdict = judge_expectation(expect, detection, never_fail_absence=never_fail_absence(ctx, hole))
    if (
        verdict.status == "FAIL"
        and expect != Level.NONE
        and detection.level == Level.NONE
        and absence_unresolved(ctx, detection)
    ):
        verdict = Verdict(
            "WARN",
            f"not resolved by this reading: detection limit {detection.weak_threshold:.0f} "
            f"counts (noise sigma {detection.sigma:.1f}); the integrated height scan (T13.1) "
            "and the baseline judge this channel",
        )
    return Judgement(hole, det, expect, detection, verdict)


def observed_pattern(ctx: SuiteContext, hole: int, nets: dict[str, float], n: int) -> set[str]:
    """Detectors that see this hole, with the same thresholds as :func:`judge`.

    An expected detector counts from the weak threshold; an unexpected one only
    above the (higher) unexpected-light threshold.
    """
    out: set[str] = set()
    ch = ctx.cfg.channel(hole)
    for det, net in nets.items():
        if out_of_range(ctx, hole, det):
            continue
        d = classify(ctx, det, net, n, expect=ch.expect_for(det))
        if d.level != Level.NONE:
            out.add(det)
    return out
