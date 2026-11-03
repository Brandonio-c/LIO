"""T11.1 comparison with a saved baseline (plan §5.3, §6 T11).

Skipped unless a baseline is given (``--baseline`` / ``--lio-baseline``).
Drift beyond ``thresholds.baseline`` is a WARN, beyond the fail fraction a
FAIL. A different sample is flagged: the comparison is then only indicative.
"""

from __future__ import annotations

from lio.results import Status
from lio.suite.core import DETECTORS, Recorder, Skip, SuiteContext, hole_id, register


@register("T11.1", "Comparison with the baseline")
def t11_1(ctx: SuiteContext, rec: Recorder) -> None:
    base = ctx.baseline
    if base is None:
        raise Skip("no baseline given (--baseline <file>); save one with --save-baseline")
    th = ctx.th
    warn_f, fail_f = th.num("baseline.drift_warn_frac"), th.num("baseline.drift_fail_frac")
    min_counts = th.num("baseline.min_counts")
    rec.measure(baseline=base.get("_path"), baseline_run=base.get("run_id"))
    sample = ctx.cache.get("sample_id")
    same = sample is None or sample == base.get("sample_id")
    rec.check(
        "sample",
        "Same sample as the baseline",
        same,
        f"now {sample}, baseline {base.get('sample_id')}"
        + ("" if same else ": differences may be the sample, not the instrument"),
        "same sample_id",
        warn=True,
    )
    fw_now = ctx.dev.info().as_str("fw")
    fw_base = (base.get("firmware") or {}).get("fw")
    if fw_base and fw_base != fw_now:
        rec.note(f"firmware changed: baseline {fw_base}, now {fw_now}")
    chans = ctx.channels()
    for hole, nets in sorted((int(h), v) for h, v in base["channels"].items()):
        for det in DETECTORS:
            ref = float(nets.get(det, 0))
            if abs(ref) < min_counts or not ctx.usable(det):
                continue
            now = float(chans[hole].meas.net(det))
            rel = (now - ref) / abs(ref)
            a = abs(rel)
            status = Status.PASS if a <= warn_f else Status.WARN if a <= fail_f else Status.FAIL
            rec.add(
                f"{hole_id(hole)}/{det}",
                f"Hole {hole} {det} vs baseline",
                status,
                f"{now:.0f} vs {ref:.0f} ({rel * 100:+.1f} %)",
                f"within {warn_f * 100:g} % (WARN to {fail_f * 100:g} %)",
                rel=rel,
            )
    k = th.num("baseline.dark_shift_sigma")
    dark_base = base.get("dark", {})
    for det in DETECTORS:
        b = dark_base.get(f"a{ctx.adc_channel(det)}")
        if not b:
            continue
        now = ctx.dark().mean(det)
        limit = k * max(float(b["sigma"]), 1.0)
        rec.check(
            f"dark/{det}",
            f"{det} dark offset vs baseline",
            abs(now - float(b["mean"])) <= limit,
            f"{now:.1f} vs {float(b['mean']):.1f}",
            f"within {limit:.1f} counts",
            warn=True,
        )
