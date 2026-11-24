"""Pure analysis functions for the test catalogue (no I/O, no device).

Thresholds are always passed in by the caller (from ``lio_hw.yaml``); nothing
here encodes hardware constants.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Stats:
    n: int
    mean: float
    std: float  # sample standard deviation (n - 1); 0 for n < 2
    min: float
    max: float

    @property
    def cv(self) -> float:
        """Coefficient of variation; inf if the mean is zero."""
        return self.std / abs(self.mean) if self.mean else math.inf


def stats(values: Sequence[float]) -> Stats:
    if not values:
        raise ValueError("stats() of an empty sequence")
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1) if n > 1 else 0.0
    return Stats(n, mean, math.sqrt(var), min(values), max(values))


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile, q in [0, 100]."""
    if not values:
        raise ValueError("percentile() of an empty sequence")
    if not 0 <= q <= 100:
        raise ValueError("q must be within 0-100")
    s = sorted(values)
    pos = (len(s) - 1) * q / 100.0
    lo = math.floor(pos)
    hi = math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def linear_slope(t: Sequence[float], y: Sequence[float]) -> float:
    """Least-squares slope dy/dt; 0 if t has no spread."""
    if len(t) != len(y) or len(t) < 2:
        raise ValueError("need two or more (t, y) pairs of equal length")
    mt = sum(t) / len(t)
    my = sum(y) / len(y)
    sxx = sum((a - mt) ** 2 for a in t)
    if sxx == 0:
        return 0.0
    return sum((a - mt) * (b - my) for a, b in zip(t, y, strict=True)) / sxx


# ----------------------------------------------------------------- channels


class Level:
    SIGNAL = "signal"
    WEAK = "weak"
    NONE = "none"


@dataclass(frozen=True)
class Detection:
    level: str  # signal | weak | none (what was observed)
    net: float
    sigma: float
    signal_threshold: float
    weak_threshold: float


def detect_level(
    net: float,
    sigma: float,
    *,
    detect_sigma: float,
    detect_min: float,
    weak_sigma: float,
    weak_min: float,
) -> Detection:
    """Classify a dark-subtracted net signal as signal / weak / none.

    ``signal`` needs net >= max(detect_sigma x sigma, detect_min);
    ``weak`` needs net >= max(weak_sigma x sigma, weak_min).
    """
    sig_thr = max(detect_sigma * sigma, detect_min)
    weak_thr = max(weak_sigma * sigma, weak_min)
    if net >= sig_thr:
        level = Level.SIGNAL
    elif net >= weak_thr:
        level = Level.WEAK
    else:
        level = Level.NONE
    return Detection(level, net, sigma, sig_thr, weak_thr)


@dataclass(frozen=True)
class Verdict:
    status: str  # PASS | WARN | FAIL
    reason: str


def judge_expectation(expect: str, observed: Detection, *, never_fail_absence: bool) -> Verdict:
    """Compare an observed level with the configured expectation for one detector."""
    o = observed.level
    if expect == Level.SIGNAL:
        if o == Level.SIGNAL:
            return Verdict("PASS", "signal as expected")
        if o == Level.WEAK:
            return Verdict("WARN", "weaker than expected")
        if never_fail_absence:
            return Verdict("WARN", "no signal (absence allowed for this channel)")
        return Verdict("FAIL", "expected signal, none seen")
    if expect == Level.WEAK:
        if o in (Level.SIGNAL, Level.WEAK):
            return Verdict("PASS", f"{o} (weak expected)")
        return Verdict("WARN", "weak channel below the weak threshold")
    # expect none
    if o == Level.NONE:
        return Verdict("PASS", "no signal, as expected")
    if never_fail_absence:
        return Verdict("WARN", f"unexpected {o} on a channel expected to show none")
    return Verdict("FAIL", f"unexpected {o}: possible stuck-on, swapped or misrouted channel")


def polarity_reversed(net: float, sigma: float, polarity_sigma: float) -> bool:
    """True if the InGaAs net is significantly negative (photodiode reversed)."""
    return net < polarity_sigma * max(sigma, 1.0)


def saturated(lit: float, limit: float) -> bool:
    return lit >= limit


def off_returned(reading: float, dark_mean: float, dark_sigma: float, k: float) -> bool:
    """After OFF + settle, the reading is back within dark +- k sigma."""
    return abs(reading - dark_mean) <= k * max(dark_sigma, 1.0)


# --------------------------------------------------------------- signatures


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)


def duplicate_signatures(
    signatures: dict[int, tuple[float, ...]],
    *,
    similarity: float,
    min_total: float,
    rel_amplitude: float = 0.05,
) -> list[list[int]]:
    """Groups of channels whose responses are indistinguishable.

    Two channels match if their direction (cosine) is above ``similarity`` and
    their amplitudes agree within ``rel_amplitude``. Distinct emitters almost
    never match on both, so a group suggests a stuck-on or misrouted channel.
    Channels with less than ``min_total`` total signal are not compared.
    """
    keys = [h for h, s in signatures.items() if sum(abs(x) for x in s) >= min_total]
    parent = {h: h for h in keys}

    def find(h: int) -> int:
        while parent[h] != h:
            parent[h] = parent[parent[h]]
            h = parent[h]
        return h

    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            sa, sb = signatures[a], signatures[b]
            amp_a = math.sqrt(sum(x * x for x in sa))
            amp_b = math.sqrt(sum(x * x for x in sb))
            same_amp = abs(amp_a - amp_b) <= rel_amplitude * max(amp_a, amp_b)
            if same_amp and cosine(sa, sb) >= similarity:
                parent[find(a)] = find(b)
    groups: dict[int, list[int]] = {}
    for h in keys:
        groups.setdefault(find(h), []).append(h)
    return sorted((sorted(g) for g in groups.values() if len(g) > 1), key=lambda g: g[0])


# ----------------------------------------------------------------- settling


MIN_FIT_SAMPLES = 3  # unsettled samples needed before a first-order fit is attempted


@dataclass(frozen=True)
class Settling:
    baseline: float
    plateau: float
    step: float
    t_settle_ms: float  # time from LED on to within (1 - fraction) of the step
    first_sample_ms: float  # time of the first sample after LED on
    within_first_sample: bool
    tau_ms: float | None  # fitted first-order time constant, if resolvable

    @property
    def upper_bound_ms(self) -> float:
        """On hardware the true settle time is <= this (sample-limited)."""
        return self.t_settle_ms


def settling(
    t_us: Sequence[int],
    raw: Sequence[int],
    on_idx: int,
    off_idx: int,
    *,
    fraction: float,
) -> Settling:
    """Step-response analysis of an ADC stream with an LED lit on [on_idx, off_idx).

    The LED switches on just before sample ``on_idx``; the switch-on instant is
    taken as halfway between samples ``on_idx - 1`` and ``on_idx``. Baseline is
    the mean before ``on_idx``.

    If every lit sample is already within ``1 - fraction`` of the final level (or within
    4 robust sigmas of the plateau noise, if that is wider),
    the response settled within the first sample (the hardware case: settling
    is far faster than one conversion) and the settle time is an upper bound.
    If it settles within fewer than ``MIN_FIT_SAMPLES`` samples, the time of
    the first settled sample is reported, again as an upper bound. Otherwise a
    first-order model is fitted, which also estimates the plateau when the
    stream ends before the signal has flattened.
    """
    if not 0 < on_idx < off_idx <= len(raw) or len(t_us) != len(raw):
        raise ValueError("need samples before the LED turns on and at least one lit sample")
    base = sum(raw[:on_idx]) / on_idx
    lit = list(raw[on_idx:off_idx])
    tail = lit[-max(1, len(lit) // 3) :]
    plateau = sum(tail) / len(tail)
    t_on_us = (t_us[on_idx - 1] + t_us[on_idx]) / 2.0
    first_ms = (t_us[on_idx] - t_on_us) / 1000.0

    # The band cannot be tighter than the noise on the plateau: 4 robust sigmas of the
    # tail's scatter (else one noisy sample late in the stream reads as "not settled").
    tail_med = sorted(tail)[len(tail) // 2]
    mad = sorted(abs(r - tail_med) for r in tail)[len(tail) // 2]
    noise_tol = 4.0 * 1.4826 * mad

    def settled_index(level: float) -> int | None:
        tol = max(abs(level - base) * (1.0 - fraction), noise_tol)
        for i in range(on_idx, off_idx):
            if all(abs(r - level) <= tol for r in raw[i:off_idx]):
                return i
        return None

    idx = settled_index(plateau)
    if idx == on_idx:
        return Settling(base, plateau, plateau - base, first_ms, first_ms, True, None)
    if idx is not None and idx - on_idx < MIN_FIT_SAMPLES:
        # Too few samples on the transition for a meaningful fit: the settle
        # time is known only to lie before sample idx (an upper bound).
        t_settle = (t_us[idx] - t_on_us) / 1000.0
        return Settling(base, plateau, plateau - base, t_settle, first_ms, False, None)

    fit = _fit_first_order(t_us[on_idx:off_idx], lit)
    if fit is not None:
        tau_ms, plateau = fit
        t_model = tau_ms * math.log(1.0 / (1.0 - fraction))
        return Settling(base, plateau, plateau - base, t_model, first_ms, False, tau_ms)

    idx = idx if idx is not None else off_idx - 1
    t_settle = (t_us[idx] - t_on_us) / 1000.0
    return Settling(base, plateau, plateau - base, t_settle, first_ms, False, None)


def _fit_first_order(t_us: Sequence[int], raw: Sequence[int]) -> tuple[float, float] | None:
    """Fit r[i+1] - r[i] = a (P - r[i]) on equally spaced samples.

    For a first-order response, a = 1 - exp(-dt / tau) and P is the plateau.
    Returns (tau_ms, plateau), or None if the data do not support a fit.
    """
    if len(raw) < 4:
        return None
    dts = [b - a for a, b in itertools.pairwise(t_us)]
    dt = sorted(dts)[len(dts) // 2]
    if dt <= 0 or any(abs(d - dt) > 0.25 * dt for d in dts):
        return None
    x = [float(r) for r in raw[:-1]]
    d = [float(b - a) for a, b in itertools.pairwise(raw)]
    if max(x) - min(x) == 0:
        return None
    slope = linear_slope(x, d)
    a = -slope
    if not 0.0 < a < 1.0:
        return None
    intercept = sum(d) / len(d) - slope * sum(x) / len(x)
    plateau = intercept / a
    tau_ms = -dt / math.log(1.0 - a) / 1000.0
    return tau_ms, plateau


def recommend_settle_ms(settle_times_ms: Sequence[float], margin: float) -> int:
    """max(settle time) x margin, rounded up to a whole millisecond (at least 1)."""
    if not settle_times_ms:
        raise ValueError("no settle times")
    return max(1, math.ceil(max(settle_times_ms) * margin))


# ------------------------------------------------------------------- motion


def move_duration_s(steps: int, vmax: float, acc: float) -> float:
    """Duration of a symmetric trapezoidal (or triangular) move of ``steps``."""
    n = abs(steps)
    if n == 0:
        return 0.0
    if vmax <= 0 or acc <= 0:
        raise ValueError("vmax and acc must be positive")
    s_acc = vmax * vmax / (2 * acc)
    if 2 * s_acc >= n:
        return 2 * math.sqrt(n / acc)
    return 2 * vmax / acc + (n - 2 * s_acc) / vmax


# 95 % two-sided Student-t quantiles (df 1..30); larger df use 1.96.
_T95 = (12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179,
        2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064,
        2.060, 2.056, 2.052, 2.048, 2.045, 2.042)  # fmt: skip


def precision_summary(
    values: Sequence[float | None],
    *,
    sd_max: float,
    cv_max: float,
    cv_min_mean: float,
    saturated: bool = False,
    missing_reasons: Sequence[str] = (),
    noise_floor: float = 0.0,
) -> dict[str, object]:
    """Repeatability of fixed-N signed nets at the instrument's real signal level (S1).

    ``values`` are the planned attempts in acquisition order; ``None`` is a
    missing/dropped record (a genuine 0 or negative net is a value). Precision is
    judged on absolute dispersion (sample SD <= ``sd_max`` counts). CV is reported
    only when the mean is resolved (positive, >= ``cv_min_mean`` and > 2 SE);
    otherwise it is unavailable with a reason, never computed on a near-zero or
    negative denominator. A stable near-zero result is precise, not a detection.

    ``status``: stable | unstable | dropouts | saturated | insufficient.
    """
    obs = [float(v) for v in values if v is not None]
    out: dict[str, object] = {
        "n_planned": len(values),
        "n_observed": len(obs),
        "dropouts": len(values) - len(obs),
        "missing_reasons": list(missing_reasons),
        "values": [None if v is None else float(v) for v in values],
        "sd_max": sd_max,
    }
    if saturated:
        out.update(status="saturated", reason="saturated reading: precision unavailable")
        return out
    if len(obs) < 2:
        out.update(status="insufficient", reason=f"{len(obs)} observed value(s); need >= 2")
        return out
    s = stats(obs)
    se = s.std / math.sqrt(s.n)
    t = _T95[s.n - 2] if s.n - 1 <= len(_T95) else 1.96
    # Order drift: least-squares slope of value vs acquisition index (counts/repeat).
    idx = [i for i, v in enumerate(values) if v is not None]
    mi = sum(idx) / len(idx)
    sxx = sum((i - mi) ** 2 for i in idx)
    slope = sum((i - mi) * (v - s.mean) for i, v in zip(idx, obs, strict=True)) / sxx
    resolved = s.mean > 0 and s.mean >= cv_min_mean and s.mean > 2 * se
    out.update(
        mean=s.mean, sd=s.std, se=se, ci95=(s.mean - t * se, s.mean + t * se),
        min=s.min, max=s.max, drift_per_repeat=slope, signal_resolved=resolved,
    )  # fmt: skip
    if resolved:
        out["cv"] = s.std / s.mean
    else:
        out["cv"] = None
        out["cv_reason"] = (
            "mean not resolved above zero" if s.mean <= 2 * se or s.mean <= 0
            else f"mean below {cv_min_mean:g} counts: CV not meaningful"
        )  # fmt: skip
    if out["dropouts"]:
        out.update(status="dropouts", reason=f"{out['dropouts']} of {len(values)} records missing")
    else:
        # Low counts: absolute dispersion, never below what the measured dark
        # noise of a lit-dark net explains (noise_floor). Resolved large signals:
        # also stable when the relative spread is within cv_max (proportional noise).
        limit = max(sd_max, noise_floor)
        out["sd_limit"] = limit
        out["sd_limit_basis"] = f"max({sd_max:g} counts, dark-noise floor {noise_floor:.2f})"
        cv = out.get("cv")
        if s.std <= limit:
            out.update(status="stable", reason=f"SD {s.std:.2f} <= {limit:.2f} counts")
        elif isinstance(cv, float) and cv <= cv_max:
            out.update(status="stable", reason=f"CV {cv * 100:.2f} % <= {cv_max * 100:g} %")
        else:
            out.update(status="unstable", reason=f"SD {s.std:.2f} > {limit:.2f} counts"
                       + ("" if cv is None else f" and CV > {cv_max * 100:g} %"))  # fmt: skip
    return out
