"""T05 LED drivers, rails and channels (plan §6)."""

from __future__ import annotations

import math
from typing import cast

from lio.analysis import duplicate_signatures, off_returned, precision_summary, saturated
from lio.device import DeviceError
from lio.protocol import ErrCode
from lio.results import Status
from lio.suite.core import DETECTORS, Recorder, SuiteContext, hole_id, register, skip_unusable
from lio.suite.judge import (
    absence_unresolved,
    classify,
    judge,
    never_fail_absence,
    observed_pattern,
    out_of_range,
    unstable_is_warn,
)

U2_HOLES = range(9, 17)  # bits 8-15: the U2 byte (LIO-ELEC-001 §5.2)


# --------------------------------------------------------------------- T05.1


@register("T05.1", "Rail gating by CE1 / CE2")
def t05_1(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    dev = ctx.dev
    n = ctx.th.integer("channel.meas_n")
    # RAIL B gating is judged on hole 11 (pink) with the OPT101: a strong RAIL B source in
    # any chamber. Hole 12 on the InGaAs returned too little light from an empty chamber
    # to prove the CE line (owner calibration 2026-11-25).
    cases = (("A", 1, 2, 8, "opt101"), ("B", 2, 1, 11, "opt101"))
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
            if out_of_range(ctx, hole, det):
                judged_by = ", ".join(ch.expected_detectors) or "no detector"
                rec.add(
                    sub,
                    label,
                    Status.SKIP,
                    f"not judged: {ch.label} is outside the {det} range (judged by {judged_by}); "
                    f"recorded net {m.net(det):+d}",
                    "out-of-range readings are not judged (channel.judge_out_of_range: false)",
                    net=m.net(det),
                    dark=m.dark(det),
                    lit=m.lit(det),
                    expect="not judged",
                )
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
        ignored = sorted(d for d in dets if out_of_range(ctx, hole, d))
        unexpected = sorted(observed - expected)
        missing = sorted(expected - observed)
        # A detector whose reading cannot resolve this channel is "not resolved", not missing.
        unresolved = [
            d
            for d in missing
            if absence_unresolved(ctx, classify(ctx, d, nets[d], n, expect=ch.expect_for(d)))
        ]
        missing = [d for d in missing if d not in unresolved]
        if not unexpected and not missing:
            status, msg = Status.PASS, f"seen by {sorted(observed) or 'nothing'} as expected"
            if ignored:
                msg += f" ({', '.join(ignored)} not judged: outside its range)"
            if unresolved:
                status = Status.WARN
                msg += (
                    f"; {unresolved} not resolved by this reading (detection limit above "
                    "the channel's level; T13.1 judges it)"
                )
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
    """Fixed-N low-count precision, frozen before acquisition (S1, rule set precision-2).

    Every expected hole x detector pair on a usable detector is selected BEFORE any
    repeat (no first-reading prefilter), measured ``repeats`` times interleaved
    under the shared duty gate. Every attempt is kept: signed nets, dark/lit and
    missing records with reasons. Judgement is absolute dispersion (SD counts);
    CV only where the mean is resolved; zero evaluated channels is SKIP.
    """
    repeats = ctx.th.integer("repeatability.repeats")
    sd_max = ctx.th.num("repeatability.sd_max_counts")
    cv_max = ctx.th.num("repeatability.cv_max")
    cv_min_mean = ctx.th.num("repeatability.cv_min_mean_counts")
    k_sig = ctx.th.num("repeatability.noise_floor_sigma")
    n = ctx.th.integer("channel.meas_n")
    sat = {d: float(ctx.cfg.detectors[d].saturation_counts) for d in DETECTORS}
    pairs = [
        (h, d) for h in range(1, 17) for d in ctx.cfg.channel(h).expected_detectors if ctx.usable(d)
    ]
    holes = sorted({h for h, _ in pairs})
    raw: dict[tuple[int, str], list[float | None]] = {k: [] for k in pairs}
    lits: dict[tuple[int, str], list[float]] = {k: [] for k in pairs}
    why: dict[tuple[int, str], list[str]] = {k: [] for k in pairs}
    rec.measure(precision_rules="precision-2", planned={"repeats": repeats, "n": n,
                "pairs": [f"{h}/{d}" for h, d in pairs], "order": "interleaved"})  # fmt: skip
    for r in range(repeats):  # interleaved: spreads the heating, respects the duty budget
        for hole in holes:
            try:
                m = ctx.meas(hole, n=n)
            except Exception as e:  # keep the attempt as a missing record
                for d in DETECTORS:
                    if (hole, d) in raw:
                        raw[(hole, d)].append(None)
                        why[(hole, d)].append(f"repeat {r}: {type(e).__name__}: {e}")
                continue
            for d in DETECTORS:
                if (hole, d) in raw:
                    raw[(hole, d)].append(float(m.net(d)))
                    lits[(hole, d)].append(float(m.lit(d)))
    evaluated = 0
    summaries = {}
    for (hole, det), values in raw.items():
        ps = precision_summary(
            values, sd_max=sd_max, cv_max=cv_max, cv_min_mean=cv_min_mean,
            saturated=any(v >= sat[det] for v in lits[(hole, det)]),
            missing_reasons=why[(hole, det)],
            noise_floor=k_sig * math.sqrt(2.0) * ctx.dark().sigma(det),
        )  # fmt: skip
        summaries[f"{hole}/{det}"] = ps
        sub, name = f"{hole_id(hole)}/{det}", f"Hole {hole} {det} repeatability, N={repeats}"
        status = str(ps["status"])
        if status in ("saturated", "insufficient"):
            rec.add(sub, name, Status.SKIP, str(ps["reason"]), f"SD <= {sd_max:g} counts",
                    summary=ps)  # fmt: skip
            continue
        evaluated += 1
        sig = (
            f"CV {float(ps['cv']) * 100:.1f} %"  # type: ignore[arg-type]
            if ps.get("cv") is not None
            else f"no CV ({ps.get('cv_reason')})"
        )
        lo, hi = cast("tuple[float, float]", ps["ci95"])
        rec.check(
            sub,
            name,
            status == "stable",
            f"mean {ps['mean']:+.1f} (95% {lo:+.1f}..{hi:+.1f}), SD {ps['sd']:.2f}, "
            f"n {ps['n_observed']}/{ps['n_planned']}; {sig}; {ps['reason']}",
            f"SD <= {sd_max:g} counts, every record present",
            warn=unstable_is_warn(ctx),
            summary=ps,
        )
    rec.measure(repeats=summaries)
    if evaluated == 0:
        rec.skip("no channel could be evaluated for precision (none usable, all saturated or "
                 "too few records): not a precision PASS")  # fmt: skip
    if ctx.dev.duty is not None:
        rec.measure(duty_cooldown_s=ctx.dev.duty.total_cooldown_s)
