"""T07 timing and settling; T08 sweep and data path (plan §6)."""

from __future__ import annotations

import math

from lio.analysis import Settling, recommend_settle_ms, settling, stats
from lio.csvout import SWEEP_HEADER, sweep_csv_text
from lio.device import Sweep
from lio.protocol import ProtocolError
from lio.results import Status
from lio.suite.core import DETECTORS, Recorder, Skip, SuiteContext, hole_id, register

# ------------------------------------------------------------------------ T07


def step_response(ctx: SuiteContext, hole: int) -> tuple[str, Settling] | None:
    """Step response of one hole at the settling rate (cached). None if gated."""
    cache: dict[int, tuple[str, Settling] | None] = ctx.cache.setdefault("steps", {})
    if hole in cache:
        return cache[hole]
    det = ctx.cfg.channel(hole).expected_detectors[0]
    if not ctx.usable(det):
        cache[hole] = None
        return None
    th = ctx.th
    pre, on, post = (th.integer(f"settling.{k}_samples") for k in ("pre", "on", "post"))
    with ctx.adc_rate(th.integer("settling.stream_rate_sps")):
        samples = ctx.dev.adc_stream(
            ctx.adc_channel(det), pre + on + post, 0, led=(hole, pre, pre + on)
        )
    result = settling(
        [s.t_us for s in samples],
        [s.raw for s in samples],
        pre,
        pre + on,
        fraction=th.num("settling.fraction"),
    )
    cache[hole] = (det, result)
    ctx.cache.setdefault("step_samples", {})[hole] = [(s.t_us, s.raw) for s in samples]
    return cache[hole]


@register("T07.1", "Step response and settling time")
def t07_1(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    frac = ctx.th.num("settling.fraction")
    for hole in ctx.th.ints("settling.holes"):
        sub = hole_id(hole)
        got = step_response(ctx, hole)
        if got is None:
            det = ctx.cfg.channel(hole).expected_detectors[0]
            rec.add(
                sub, f"Hole {hole} step response", Status.SKIP, f"{ctx.unusable(det)} (see T06)"
            )
            continue
        det, s = got
        if not ctx.is_lit(det, s.plateau):
            rec.check(
                sub,
                f"Hole {hole} step response",
                False,
                f"no step on {det} (baseline {s.baseline:.0f}, plateau {s.plateau:.0f})",
                "a step above the detection threshold",
            )
            continue
        if s.within_first_sample:
            msg = (
                f"settled within one sample: t{frac * 100:g} <= {s.upper_bound_ms:.2f} ms "
                "(upper bound, limited by the sample interval)"
            )
        elif s.tau_ms is None:
            msg = (
                f"settled within a few samples: t{frac * 100:g} <= {s.t_settle_ms:.2f} ms "
                "(upper bound, limited by the sample interval)"
            )
        else:
            msg = f"t{frac * 100:g} = {s.t_settle_ms:.2f} ms" + (
                f", tau {s.tau_ms:.2f} ms" if s.tau_ms is not None else ""
            )
        rec.add(
            sub,
            f"Hole {hole} ({det}) step response",
            Status.PASS,
            msg,
            f"time to {frac * 100:g} % recorded",
            detector=det,
            step=s.step,
            t_settle_ms=s.t_settle_ms,
            tau_ms=s.tau_ms,
            within_first_sample=s.within_first_sample,
            t_us=[t for t, _ in ctx.cache["step_samples"][hole]],
            raw=[r for _, r in ctx.cache["step_samples"][hole]],
            on_idx=ctx.th.integer("settling.pre_samples"),
            off_idx=ctx.th.integer("settling.pre_samples") + ctx.th.integer("settling.on_samples"),
        )


@register("T07.2", "Recommended settle time")
def t07_2(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    times = []
    for hole in ctx.th.ints("settling.holes"):
        got = step_response(ctx, hole)
        if got is not None and ctx.is_lit(got[0], got[1].plateau):
            times.append(got[1].t_settle_ms)
    if not times:
        raise Skip("no usable step response (see T07.1)")
    margin = ctx.th.num("settling.margin_factor")
    rec_ms = recommend_settle_ms(times, margin)
    configured = ctx.cfg.limits["settle_ms"]
    rec.measure(recommended_settle_ms=rec_ms, configured_settle_ms=configured)
    rec.check(
        "settle",
        "Configured settle_ms is long enough",
        rec_ms <= configured,
        f"recommended {rec_ms} ms (max {max(times):.2f} ms x {margin:g}), configured "
        f"{configured} ms"
        + ("" if rec_ms <= configured else f": raise firmware.limits.settle_ms to {rec_ms}"),
        f"recommended <= {configured} ms",
        warn=True,
    )


@register("T07.3", "MEAS timing")
def t07_3(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    hole = ctx.th.ints("settling.holes")[0]
    rate = ctx.cfg.section.integer("adc.rate_sps")
    conv_ms = 1000.0 / rate
    tol = ctx.th.num("adc.rate_tolerance_frac")
    overhead = ctx.th.num("adc.conv_overhead_max_ms")
    slack = ctx.th.num("settling.meas_slack_ms")
    wdt = ctx.cfg.wdt_ms(ctx.cfg.channel(hole).rail)
    for settle, n in ctx.th.raw("settling.meas_points"):
        m = ctx.meas(hole, n=int(n), settle_ms=int(settle))
        lo = settle + 2 * n * conv_ms * (1 - tol)
        hi = settle + 2 * n * (conv_ms * (1 + tol) + overhead) + slack
        rec.check(
            f"s{settle}n{n}",
            f"MEAS {hole} {settle} {n} on-time",
            lo <= m.t_on_ms <= hi and m.t_on_ms <= wdt,
            f"t_on_ms {m.t_on_ms}",
            f"{lo:.1f}-{hi:.1f} ms and <= watchdog {wdt} ms",
            t_on_ms=m.t_on_ms,
        )


# ------------------------------------------------------------------------ T08


def _sweeps(ctx: SuiteContext, count: int) -> list[Sweep]:
    """At least ``count`` sweeps at the default settle time, n = 1 (cached)."""
    got: list[Sweep] = ctx.cache.setdefault("sweeps", [])
    while len(got) < count:
        sw = ctx.dev.sweep()
        for m in sw.records:
            ctx.log_meas(m)
        got.append(sw)
    return got


@register("T08.1", "SWEEP completes with a valid schema")
def t08_1(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    limit_s = ctx.th.num("sweep.max_duration_s")
    t0 = ctx.dev.now()
    try:
        sw = _sweeps(ctx, 1)[0]
    except (ProtocolError, KeyError, ValueError) as e:
        rec.check("schema", "Sweep records parse", False, str(e), "every '# M' field present")
        return
    host_s = ctx.dev.now() - t0
    holes = [m.hole for m in sw.records]
    rec.check(
        "records",
        "16 records, holes 1-16 in order",
        holes == list(range(1, 17)),
        f"{len(holes)} records: {holes}",
        "holes 1..16",
    )
    rec.check("schema", "Sweep records parse", True, "all '# M' fields present and integer")
    rec.check(
        "duration",
        "Sweep duration",
        sw.dur_ms / 1000.0 <= limit_s,
        f"{sw.dur_ms} ms (host {host_s * 1000:.0f} ms)",
        f"<= {limit_s:g} s",
        dur_ms=sw.dur_ms,
    )


def _judged_pairs(ctx: SuiteContext) -> list[tuple[int, str]]:
    return [
        (h, d) for h in range(1, 17) for d in ctx.cfg.channel(h).expected_detectors if ctx.usable(d)
    ]


@register("T08.2", "Repeated sweeps")
def t08_2(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    repeats = ctx.th.integer("sweep.repeats")
    cv_max = ctx.th.num("repeatability.cv_max")
    min_net = ctx.th.num("repeatability.min_net_counts")
    sweeps = _sweeps(ctx, repeats)[:repeats]
    rec.measure(
        sweeps=[
            {str(m.hole): {d: m.net(d) for d in DETECTORS} for m in sw.records} for sw in sweeps
        ]
    )
    for h, d in _judged_pairs(ctx):
        nets = [float(m.net(d)) for sw in sweeps for m in sw.records if m.hole == h]
        if len(nets) < 2:
            rec.check(
                f"{hole_id(h)}/{d}",
                f"Hole {h} {d} sweep-to-sweep CV",
                False,
                f"hole {h} present in only {len(nets)} of {len(sweeps)} sweeps",
                "a record in every sweep",
            )
            continue
        s = stats(nets)
        if s.mean < min_net:
            continue
        rec.check(
            f"{hole_id(h)}/{d}",
            f"Hole {h} {d} sweep-to-sweep CV",
            s.cv <= cv_max,
            f"mean {s.mean:.0f}, CV {s.cv * 100:.2f} %",
            f"CV <= {cv_max * 100:g} %",
            cv=s.cv,
        )
    k = ctx.th.num("channel.off_return_sigma")
    for d in DETECTORS:
        means = [stats([float(m.dark(d)) for m in sw.records]).mean for sw in sweeps]
        spread = max(means) - min(means)
        limit = k * ctx.dark().sigma(d) / 4.0  # mean of 16 dark readings
        rec.check(
            f"dark/{d}",
            f"{d} dark stable between sweeps",
            spread <= limit,
            f"per-sweep dark means span {spread:.2f} counts",
            f"<= {limit:.2f} counts",
            warn=True,
            spread=spread,
        )


@register("T08.3", "Sweep agrees with MEAS")
def t08_3(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    chans = ctx.channels()
    sweeps = _sweeps(ctx, ctx.th.integer("sweep.repeats"))
    frac = ctx.th.num("sweep.agreement_frac")
    k = ctx.th.num("sweep.agreement_sigma")
    min_counts = ctx.th.num("sweep.agreement_min_counts")
    n = ctx.th.integer("channel.meas_n")
    dark = ctx.dark()
    for h, d in _judged_pairs(ctx):
        ref = float(chans[h].meas.net(d))
        if abs(ref) < min_counts:
            continue
        nets = [float(m.net(d)) for sw in sweeps for m in sw.records if m.hole == h]
        if not nets:
            continue  # T08.1 / T08.2 report the missing record
        mean = stats(nets).mean
        # noise of the MEAS net (n samples) and of the mean of the sweep nets (n = 1)
        sigma = math.hypot(dark.net_sigma(d, n), dark.net_sigma(d, 1) / math.sqrt(len(sweeps)))
        tol = max(frac * abs(ref), k * sigma)
        rel = abs(mean - ref) / abs(ref)
        rec.check(
            f"{hole_id(h)}/{d}",
            f"Hole {h} {d} sweep vs MEAS",
            abs(mean - ref) <= tol,
            f"sweep {mean:.0f} vs MEAS {ref:.0f} ({rel * 100:.1f} %)",
            f"within {tol:.0f} counts (max of {frac * 100:g} %, {k:g} sigma)",
            rel=rel,
        )


@register("T08.4", "CSV output format")
def t08_4(ctx: SuiteContext, rec: Recorder) -> None:
    """The sweep CSV (logger and ``lio sweep --csv``) matches the documented format."""
    ctx.require_adc()
    sw = _sweeps(ctx, 1)[0]
    text = sweep_csv_text(sw.records, ctx.cfg)
    lines = text.split("\r\n")
    rec.check(
        "header", "Header", lines[0] == ",".join(SWEEP_HEADER), lines[0], ",".join(SWEEP_HEADER)
    )
    rows = [ln for ln in lines[1:] if ln]
    rec.check(
        "rows",
        "One CRLF-terminated row per hole",
        len(rows) == len(sw.records) and text.endswith("\r\n"),
        f"{len(rows)} rows",
        f"{len(sw.records)} rows, CRLF",
    )
    # Independent re-statement of the original logger's arithmetic (TEST_MODE 5 era).
    vpc = ctx.cfg.lsb_mv / 1000.0
    bad = []
    for m, row in zip(sw.records, rows, strict=False):
        want = ",".join(
            str(v)
            for v in (
                m.hole,
                ctx.cfg.channel(m.hole).label,
                m.dark0,
                m.dark1,
                m.lit0,
                m.lit1,
                round((m.lit0 - m.dark0) * vpc, 5),
                round((m.lit1 - m.dark1) * vpc, 5),
            )
        )
        if row != want:
            bad.append(f"hole {m.hole}: {row!r} != {want!r}")
    rec.check(
        "values",
        "Rows byte-identical to the original logger's format",
        not bad,
        "; ".join(bad[:3]) or "all rows identical",
        "same columns, rounding, labels",
    )
