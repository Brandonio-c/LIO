"""T05 LED drivers, rails and channels (plan §6)."""

from __future__ import annotations

import math

from lio.analysis import duplicate_signatures, off_returned, saturated, stats
from lio.device import DeviceError
from lio.protocol import ErrCode
from lio.results import Status
from lio.suite.core import DETECTORS, Recorder, SuiteContext, hole_id, register, skip_unusable
from lio.suite.judge import judge, never_fail_absence, observed_pattern

U2_HOLES = range(9, 17)  # bits 8-15: the U2 byte (LIO-ELEC-001 §5.2)


# --------------------------------------------------------------------- T05.1


@register("T05.1", "Rail gating by CE1 / CE2")
def t05_1(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    dev = ctx.dev
    n = ctx.th.integer("channel.meas_n")
    cases = (("A", 1, 2, 8, "opt101"), ("B", 2, 1, 12, "ingaas"))
    for rail, ce, other_ce, hole, det in cases:
        pre = f"{rail}/{hole_id(hole)}"
        if skip_unusable(ctx, rec, det, pre, f"RAIL {rail} gating"):
            continue
        adc = ctx.adc_channel(det)
        dev.sr_raw(1 << (hole - 1))
        dev.sleep(ctx.cfg.limits["settle_ms"] / 1000.0)
        low = dev.adc_read(adc, n).mean
        rec.check(
            f"{pre}/ce_low",
            f"Hole {hole} selected, CE{ce} low",
            ctx.is_dark(det, low, n),
            f"{det} {low:.0f} (dark {ctx.dark().mean(det):.0f})"
            + (
                ""
                if ctx.is_dark(det, low, n)
                else "; light without CE: CE logic inverted, or slow decay of the previous "
                "step (T07)"
            ),
            "dark",
        )
        dev.ce(ce, True)
        try:
            dev.sleep(ctx.cfg.limits["settle_ms"] / 1000.0)
            high = dev.adc_read(adc, n).mean
        finally:
            dev.ce(ce, False)
        lit = ctx.is_lit(det, high, n)
        rec.check(
            f"{pre}/ce_high",
            f"Hole {hole} selected, CE{ce} high",
            lit,
            f"{det} {high:.0f}"
            + ("" if lit else f"; no light: RAIL {rail} driver, CE{ce} or the LED is dead"),
            "light above the detection threshold",
        )
        dev.sr_raw(1 << (hole - 1))
        try:
            dev.ce(other_ce, True)
            refused, msg = False, "accepted"
        except DeviceError as e:
            refused, msg = e.code == int(ErrCode.REFUSED), f"ERR code={e.code} {e.msg}"
        rec.check(
            f"{pre}/wrong_ce",
            f"Hole {hole} with CE{other_ce} (wrong rail)",
            refused,
            msg,
            "refused (code 3)",
        )
        dev.off()


# --------------------------------------------------------------------- T05.2


@register("T05.2", "Per-channel response")
def t05_2(ctx: SuiteContext, rec: Recorder) -> None:
    chans = ctx.channels()
    n = ctx.th.integer("channel.meas_n")
    sat = {d: ctx.th.num(f"saturation.{d}_counts") for d in DETECTORS}
    for hole, data in chans.items():
        m = data.meas
        ch = ctx.cfg.channel(hole)
        for det in DETECTORS:
            sub = f"{hole_id(hole)}/{det}"
            label = f"Hole {hole} ({ch.label}) on {det}"
            if skip_unusable(ctx, rec, det, sub, label):
                continue
            j = judge(ctx, hole, det, m.net(det), n)
            msg = f"net {m.net(det):+d} ({j.detection.level}); {j.verdict.reason}"
            if not ch.fitted:
                msg += " (no emitter fitted)"
            status = Status(j.verdict.status)
            rec.add(
                sub,
                label,
                status,
                msg,
                f"expect {j.expect}: signal >= {j.detection.signal_threshold:.0f}",
                net=m.net(det),
                dark=m.dark(det),
                lit=m.lit(det),
                expect=j.expect,
                observed=j.detection.level,
            )
            if saturated(m.lit(det), sat[det]):
                advice = (
                    "reduce the TIA gain (Rf 1 MOhm -> 100 kOhm)"
                    if det == "ingaas"
                    else "reduce the LED drive or the OPT101 gain"
                )
                rec.add(
                    f"{sub}/sat",
                    f"{label} saturation",
                    Status.WARN,
                    f"lit {m.lit(det)} >= {sat[det]:.0f}: {advice}",
                    f"< {sat[det]:.0f}",
                )


# --------------------------------------------------------------------- T05.3


@register("T05.3", "Channel address and isolation")
def t05_3(ctx: SuiteContext, rec: Recorder) -> None:
    chans = ctx.channels()
    n = ctx.th.integer("channel.meas_n")
    dets = tuple(d for d in DETECTORS if ctx.usable(d))
    for d in DETECTORS:
        if not ctx.usable(d):
            rec.note(f"{d} excluded: {ctx.unusable(d)} (see T06)")
    seen: dict[int, set[str]] = {}
    for hole, data in chans.items():
        ch = ctx.cfg.channel(hole)
        nets = {d: float(data.meas.net(d)) for d in dets}
        observed = observed_pattern(ctx, hole, nets, n)
        seen[hole] = observed
        expected = {d for d in ch.expected_detectors if d in dets}
        unexpected = sorted(observed - expected)
        missing = sorted(expected - observed)
        if not unexpected and not missing:
            status, msg = Status.PASS, f"seen by {sorted(observed) or 'nothing'} as expected"
        else:
            parts = []
            if unexpected:
                parts.append(f"unexpected response on {unexpected}")
            if missing:
                parts.append(f"no response on {missing}")
            msg = "; ".join(parts) + ": possible swapped, misrouted or stuck-on channel"
            status = Status.WARN if never_fail_absence(ctx, hole) else Status.FAIL
        rec.add(
            f"{hole_id(hole)}/pattern",
            f"Hole {hole} ({ch.label}) detector pattern",
            status,
            msg,
            f"expected {sorted(expected) or 'none'}",
            **{f"net_{d}": nets[d] for d in dets},
        )

    # Distinct wavelengths never give identical signatures: a group means two
    # gates drive the same LED (stuck-on MOSFET stealing the current, or a swap).
    # Saturated readings are clamped, hence identical by construction: excluded
    # here (T05.2 / T06 report the saturation).
    sat = {d: ctx.th.num(f"saturation.{d}_counts") for d in dets}
    sigs = {
        h: tuple(float(d.meas.net(det)) for det in dets)
        for h, d in chans.items()
        if ctx.cfg.channel(h).fitted
        and not any(saturated(d.meas.lit(det), sat[det]) for det in dets)
    }
    frac = ctx.th.num("channel.signature_amplitude_frac")
    groups = duplicate_signatures(
        sigs,
        similarity=ctx.th.num("channel.signature_similarity"),
        min_total=ctx.th.num("channel.signature_min_counts"),
        rel_amplitude=frac,
    )
    fail_size = ctx.th.integer("channel.duplicate_fail_group")
    grouped = {h for g in groups for h in g}
    for g in groups:
        big = len(g) >= fail_size
        for h in g:
            rec.add(
                f"{hole_id(h)}/unique",
                f"Hole {h} signature unique",
                Status.FAIL if big else Status.WARN,
                f"holes {g} give the same response within {frac * 100:g} %: one emitter "
                "lit for all of them (stuck-on MOSFET, or gate wiring)"
                + (
                    ""
                    if big
                    else "; a pair can also match by coincidence: confirm with the T04.4 walk test"
                ),
                "distinct per hole",
            )
    if not groups:
        rec.add(
            "unique",
            "Signatures unique",
            Status.PASS,
            "no two channels look the same",
            f"cosine < {ctx.th.num('channel.signature_similarity')} or amplitude differs "
            f"by more than {frac * 100:g} %",
        )
    rec.measure(
        duplicate_groups=groups,
        matrix={h: {det: d.meas.net(det) for det in DETECTORS} for h, d in chans.items()},
    )

    # Light from an unfitted hole means another channel on that rail conducts
    # without being selected (stuck-on MOSFET): name the closest signature.
    for hole, observed in seen.items():
        ch = ctx.cfg.channel(hole)
        if ch.fitted or not observed:
            continue
        sig = tuple(float(chans[hole].meas.net(d)) for d in dets)
        same_rail = [h for h in sigs if ctx.cfg.channel(h).rail == ch.rail]
        best = min(same_rail, key=lambda h: math.dist(sigs[h], sig), default=None)
        culprit = f"; closest match: hole {best}" if best is not None else ""
        rec.add(
            f"{ch.rail}/stuck_via_{hole}",
            f"RAIL {ch.rail} channels off when not selected",
            Status.FAIL,
            f"unfitted hole {hole} gives light {dict(zip(dets, sig, strict=True))}: a RAIL "
            f"{ch.rail} channel conducts without being selected (stuck-on MOSFET){culprit}",
            "no light from unfitted holes",
        )

    # Diagnosis: every expected-signal hole of the U2 byte dark while U1 works
    # points at the register chain rather than at the LEDs.
    u2 = [
        h
        for h in U2_HOLES
        if ctx.cfg.channel(h).expected_detectors
        and any(d in dets for d in ctx.cfg.channel(h).expected_detectors)
    ]
    u1 = [h for h in range(1, 9) if ctx.cfg.channel(h).expected_detectors]
    u2_dark = all(not seen[h] for h in u2) and bool(u2)
    u1_ok = all(seen[h] for h in u1 if h not in grouped)
    if u2_dark and u1_ok:
        rec.add(
            "chain",
            "U2 holes respond",
            Status.FAIL,
            f"no response on any U2 hole {u2} while U1 holes work: U2 receives no data; "
            "check U1 pin 9 (Q7') -> U2 pin 14 (SER), and U2 power",
            "U2 holes respond",
        )


# --------------------------------------------------------------------- T05.4


@register("T05.4", "Off-state return after each MEAS")
def t05_4(ctx: SuiteContext, rec: Recorder) -> None:
    chans = ctx.channels()
    n = ctx.th.integer("channel.meas_n")
    k = ctx.th.num("channel.off_return_sigma")
    dark = ctx.dark()
    for hole, data in chans.items():
        for det in DETECTORS:
            sub = f"{hole_id(hole)}/{det}"
            label = f"Hole {hole} {det} back to dark"
            if skip_unusable(ctx, rec, det, sub, label):
                continue
            after = data.after[det]
            ref = float(data.meas.dark(det))
            sigma = dark.sigma(det) * math.sqrt(2.0 / n)
            ok = off_returned(after, ref, sigma, k)
            rec.check(
                sub,
                label,
                ok,
                f"{after:.1f} after OFF vs dark {ref:.0f}"
                + ("" if ok else ": light persists after OFF (slow decay, or the LED stays on)"),
                f"within {k:g} sigma ({k * sigma:.1f} counts)",
                after=after,
                dark=ref,
            )


# --------------------------------------------------------------------- T05.5


@register("T05.5", "Repeatability (interleaved MEAS)")
def t05_5(ctx: SuiteContext, rec: Recorder) -> None:
    chans = ctx.channels()
    repeats = ctx.th.integer("repeatability.repeats")
    cv_max = ctx.th.num("repeatability.cv_max")
    min_net = ctx.th.num("repeatability.min_net_counts")
    n = ctx.th.integer("channel.meas_n")
    judged: list[tuple[int, str]] = []
    for hole, data in chans.items():
        for det in ctx.cfg.channel(hole).expected_detectors:
            if not ctx.usable(det):
                continue
            if data.meas.net(det) >= min_net:
                judged.append((hole, det))
    holes = sorted({h for h, _ in judged})
    nets: dict[tuple[int, str], list[float]] = {k: [] for k in judged}
    for _ in range(repeats):  # interleaved: spreads the heating, respects the duty budget
        for hole in holes:
            m = ctx.meas(hole, n=n)
            for det in DETECTORS:
                if (hole, det) in nets:
                    nets[(hole, det)].append(float(m.net(det)))
    for (hole, det), values in nets.items():
        s = stats(values)
        rec.check(
            f"{hole_id(hole)}/{det}",
            f"Hole {hole} {det} CV over {repeats}",
            s.cv <= cv_max,
            f"mean {s.mean:.0f}, CV {s.cv * 100:.2f} %",
            f"CV <= {cv_max * 100:g} %",
            mean=s.mean,
            cv=s.cv,
        )
    skipped = [
        f"{h}/{d}"
        for h in chans
        for d in ctx.cfg.channel(h).expected_detectors
        if (h, d) not in nets
    ]
    if skipped:
        rec.note(
            f"not judged (net < {min_net:g} counts or detector unusable): {', '.join(skipped)}"
        )
    if ctx.dev.duty is not None:
        rec.measure(duty_cooldown_s=ctx.dev.duty.total_cooldown_s)
