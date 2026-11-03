"""T06 detectors: OPT101 and the InGaAs TIA (plan §6)."""

from __future__ import annotations

from lio.analysis import Level, polarity_reversed, saturated
from lio.results import Status
from lio.suite.core import Recorder, Skip, SuiteContext, hole_id, register, skip_unusable
from lio.suite.judge import classify

REVERSED_ADVICE = (
    "the InGaAs photodiode is reversed: swap its two leads at the TIA input (anode <-> "
    "cathode), then rerun T06.2"
)
NEG_RAIL_ADVICE = (
    "the -5 V rail looks missing (bank B asleep?): check the -5 V supply at the TIA op-amp "
    "and that bank B stays powered"
)


def _dark_range(ctx: SuiteContext, rec: Recorder, det: str, hint: str) -> bool:
    lo, hi = ctx.th.span(f"dark.{det}_counts")
    mean = ctx.dark().mean(det)
    ok = lo <= mean <= hi
    rec.check(
        "dark",
        f"{det} dark offset",
        ok,
        f"{mean:.1f} counts" + ("" if ok else f"; {hint}"),
        f"{lo:g} to {hi:g} counts",
        mean=mean,
    )
    return ok


@register("T06.1", "OPT101")
def t06_1(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    det = "opt101"
    sat = ctx.th.num("saturation.opt101_counts")
    _dark_range(
        ctx,
        rec,
        det,
        "output pinned high: OPT101 feedback (pins 4-5) open?"
        if ctx.dark().mean(det) >= sat
        else "check the OPT101 supply and output wiring",
    )
    chans = ctx.channels()
    n = ctx.th.integer("channel.meas_n")
    # Holes seen only by the OPT101: the visible emitters.
    visible = [h for h in chans if ctx.cfg.channel(h).expected_detectors == (det,)]
    rec.measure(visible_net={h: chans[h].meas.net(det) for h in visible})
    for h in visible:
        sub, name = f"{hole_id(h)}/visible", f"Responds to hole {h} ({ctx.cfg.channel(h).label})"
        if skip_unusable(ctx, rec, det, sub, name):
            continue
        net = chans[h].meas.net(det)
        seen = classify(ctx, det, net, n, expect=Level.SIGNAL).level != Level.NONE
        rec.check(sub, name, seen, f"net {net:+d}", "no zeros where light is expected", net=net)
    peak = max([ctx.dark().mean(det)] + [float(d.meas.lit(det)) for d in chans.values()])
    rec.check(
        "saturation",
        "Not saturated",
        not saturated(peak, sat),
        f"peak {peak:.0f}",
        f"< {sat:.0f} counts",
    )


@register("T06.2", "InGaAs TIA")
def t06_2(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    det = "ingaas"
    dark = ctx.dark()
    sigma = dark.by_detector[det].std
    erratic_sigma = ctx.th.num("dark.erratic_sigma_factor") * ctx.th.num(
        "adc.dark_sigma_max_counts"
    )
    pinned = ctx.th.num("dark.negative_rail_counts")
    erratic = sigma > erratic_sigma or dark.mean(det) < pinned
    rec.check(
        "erratic",
        "Dark signal steady",
        not erratic,
        f"dark mean {dark.mean(det):.0f}, sigma {sigma:.1f}"
        + (f"; {NEG_RAIL_ADVICE}" if erratic else ""),
        f"sigma <= {erratic_sigma:g} and mean >= {pinned:g}",
        sigma=sigma,
    )
    _dark_range(ctx, rec, det, NEG_RAIL_ADVICE if erratic else "check the TIA offset")
    if erratic:
        rec.add(
            "polarity", "Photodiode polarity", Status.SKIP, "not judged: the TIA output is erratic"
        )
        return

    gate = ctx.gate()
    rec.check(
        "polarity/gate",
        f"Polarity gate (hole {gate.hole})",
        gate.ok,
        f"net {gate.net:+d}" + ("" if gate.ok else f"; {REVERSED_ADVICE}"),
        f"net >= {ctx.th.num('channel.polarity_sigma'):g} sigma",
        net=gate.net,
    )
    if not gate.ok:
        return
    chans = ctx.channels()
    n = ctx.th.integer("channel.meas_n")
    k = ctx.th.num("channel.polarity_sigma")
    sat = ctx.th.num("saturation.ingaas_counts")
    for h, data in chans.items():
        if ctx.cfg.channel(h).expect_for(det) != Level.SIGNAL or h == gate.hole:
            continue
        net = data.meas.net(det)
        rev = polarity_reversed(net, dark.net_sigma(det, n), k)
        rec.check(
            f"{hole_id(h)}/polarity",
            f"Hole {h} InGaAs polarity",
            not rev,
            f"net {net:+d}" + (f"; {REVERSED_ADVICE}" if rev else ""),
            "net not negative",
            net=net,
        )
    for h, data in chans.items():
        lit = data.meas.lit(det)
        if saturated(lit, sat):
            rec.add(
                f"{hole_id(h)}/saturation",
                f"Hole {h} InGaAs saturation",
                Status.WARN,
                f"lit {lit} >= {sat:.0f}: reduce the TIA gain (Rf 1 MOhm -> 100 kOhm)",
                f"< {sat:.0f} counts",
                lit=lit,
            )
    if not any(s.id.endswith("/saturation") for s in rec.result.subs):
        rec.add(
            "saturation",
            "InGaAs not saturated",
            Status.PASS,
            "no hole saturates",
            f"< {sat:.0f} counts",
        )


@register("T06.3", "Cross-calibration on the shared holes")
def t06_3(ctx: SuiteContext, rec: Recorder) -> None:
    for det in ("opt101", "ingaas"):
        if not ctx.usable(det):
            raise Skip(f"{ctx.unusable(det)} (see T06)")
    chans = ctx.channels()
    n = ctx.th.integer("channel.meas_n")
    shared = [h for h in chans if len(ctx.cfg.channel(h).expected_detectors) == 2]
    ratios: dict[int, float] = {}
    for h in shared:
        m = chans[h].meas
        both = all(
            classify(ctx, d, m.net(d), n, expect=Level.SIGNAL).level == Level.SIGNAL
            for d in ("opt101", "ingaas")
        )
        ratio = m.net("ingaas") / m.net("opt101") if m.net("opt101") else float("nan")
        if both:
            ratios[h] = ratio
        rec.check(
            f"{hole_id(h)}",
            f"Hole {h} seen by both detectors",
            both,
            f"InGaAs/OPT101 = {ratio:.3f}" if both else "one detector does not respond",
            "both above the detection threshold",
            ratio=ratio,
        )
    rec.measure(ingaas_over_opt101=ratios)
