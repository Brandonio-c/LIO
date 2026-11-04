"""T03 I²C and ADC; T04 channel selection and the shift registers (plan §6)."""

from __future__ import annotations

import itertools
import math

from lio.analysis import linear_slope, stats
from lio.results import Status
from lio.suite.core import DETECTORS, Recorder, Skip, SuiteContext, register

I2C_WIRING_HINT = (
    "first check that power bank A is on: it alone powers the +5 V bus (ADS1115, LEDs, "
    "shift registers), and USB banks switch off when the load is small (measure about 5 V "
    "between +5 V and GND); then the ADS1115 wiring: SDA -> A4, SCL -> A5, ADDR -> GND "
    "(0x48), VDD 5 V and GND; both lines should idle near 5 V"
)


# ------------------------------------------------------------------------ T03


# Wire.endTransmission() results reported by I2C DIAG.
ACK_RESULTS = {
    0: "answers",
    1: "too long",
    2: "no answer",
    3: "no answer to data",
    4: "bus error",
    5: "bus timeout",
}


def _khz(hz: int) -> str:
    return f"{hz / 1000:g} kHz"


def diagnose_i2c(d: dict[str, int], addr: int) -> tuple[bool, str]:
    """(lines healthy, explanation) from ``I2C DIAG`` fields."""
    stuck = [n for n in ("sda", "scl") if not d[n]]
    if stuck:
        names = " and ".join(n.upper() for n in stuck)
        return False, (
            f"{names} held low even with the Nano's pull-up on: a short to GND, a chip "
            f"without power clamping the line, or the wrong pin (SDA = A4, SCL = A5); "
            f"with power on, measure each line to GND, it should idle near 5 V"
        )
    if d["bridge"]:
        return False, (
            "SDA and SCL are joined: pulling one low pulls the other low; look for a solder "
            "bridge between the header pins, both wires in one breadboard row, or a stray "
            "lead touching both (with power off they should not read low ohms to each other)"
        )
    parts = []
    no_pu = [n.upper() for n in ("sda", "scl") if not d[f"{n}_pu"]]
    if no_pu:
        parts.append(
            f"{' and '.join(no_pu)} do not rise without the Nano's weak internal pull-up: "
            "either the ADS1115 module has no pull-ups (add 4.7 kOhm from each line to "
            "+5 V) or its VDD is off (power bank A)"
        )
    slow, fast = d["ack_slow"], d["ack_fast"]
    at = f"0x{addr:02X}"
    if slow == 0 and fast != 0:
        parts.append(
            f"{at} answers at {_khz(d['slow_hz'])} but not {_khz(d['fast_hz'])}: the lines "
            f"rise too slowly, so the firmware fell back to {_khz(d['hz'])}; add 4.7 kOhm "
            "pull-ups to run at full speed"
        )
    elif slow != 0:
        what = ACK_RESULTS.get(slow, f"result {slow}")
        hint = (
            "the lines look healthy, so check ADDR -> GND, VDD and GND measured at the "
            "chip's own pins, SDA (A4) and SCL (A5) not swapped, and the Nano GND joined "
            "to the bus GND"
            if not no_pu and slow == 2
            else "see above"
        )
        parts.append(f"{at}: {what} at {_khz(d['slow_hz'])} or {_khz(d['fast_hz'])}; {hint}")
    ok = not no_pu
    return ok, "; ".join(parts) or (
        f"lines idle high with pull-ups, not bridged; {at} answers at {_khz(d['hz'])}"
    )


@register("T03.1", "I2C scan finds the ADS1115")
def t03_1(ctx: SuiteContext, rec: Recorder) -> None:
    want = ctx.cfg.section.integer("adc.address")
    # The line checks first: they also re-attach the ADC, at the slow clock if
    # only that works, so the scan below sees it.
    diag = ctx.dev.i2c_diag()
    found = ctx.dev.i2c_scan()
    rec.measure(addresses=[f"0x{a:02X}" for a in found])
    slow_only = diag is not None and want in found and diag["hz"] != diag["fast_hz"]
    if want in found and slow_only:
        assert diag is not None
        rec.add(
            "adc",
            f"ADS1115 at 0x{want:02X}",
            Status.WARN,
            f"answers only at {_khz(diag['hz'])}, not {_khz(diag['fast_hz'])}: the lines rise "
            "too slowly (no or weak pull-ups); add 4.7 kOhm from SDA and SCL to +5 V",
            f"0x{want:02X} acknowledges at {_khz(diag['fast_hz'])}",
        )
    else:
        rec.check(
            "adc",
            f"ADS1115 at 0x{want:02X}",
            want in found,
            f"found {[f'0x{a:02X}' for a in found] or 'nothing'}"
            + ("" if want in found else f"; {I2C_WIRING_HINT}"),
            f"0x{want:02X} acknowledges",
        )
    if diag is not None:
        rec.measure(i2c_diag=diag)
        ok, why = diagnose_i2c(diag, want)
        rec.check(
            "bus",
            "I2C lines (SDA, SCL)",
            ok,
            why,
            "both idle high, rise on external pull-ups, not joined",
            warn=want in found,
        )
    extra = [a for a in found if a != want]
    rec.check(
        "only",
        "No unexpected I2C devices",
        not extra,
        f"unexpected: {[f'0x{a:02X}' for a in extra]}" if extra else "none",
        "only the ADS1115",
        warn=True,
    )


@register("T03.2", "Dark ADC noise, all inputs")
def t03_2(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    dark = ctx.dark()
    sigma_max = ctx.th.num("adc.dark_sigma_max_counts")
    for det in DETECTORS:
        s = dark.by_detector[det]
        ch = ctx.adc_channel(det)
        rec.check(
            f"a{ch}",
            f"ADS A{ch} ({det}) dark noise",
            s.std <= sigma_max,
            f"mean {s.mean:.1f}, sigma {s.std:.2f} counts (n={s.n})",
            f"sigma <= {sigma_max:g} counts",
            mean=s.mean,
            sigma=s.std,
        )
    n = ctx.th.integer("adc.dark_samples")
    used = {ctx.adc_channel(d) for d in DETECTORS}
    for ch in range(4):
        if ch in used:
            continue
        r = ctx.dev.adc_read(ch, n)
        rec.add(
            f"a{ch}",
            f"ADS A{ch} (unconnected)",
            Status.PASS,
            f"recorded only: mean {r.mean:.1f}, sigma {r.std or 0:.2f}",
            "floating input",
            mean=r.mean,
            sigma=r.std,
        )


@register("T03.3", "Gain sweep on dark inputs")
def t03_3(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    lsb_by_gain = {str(k): float(v) for k, v in ctx.cfg.section.mapping("adc.lsb_mv").items()}
    full_scale = ctx.cfg.section.integer("adc.full_scale_counts")
    tol_mv = ctx.th.num("adc.gain_consistency_mv")
    n = 16
    ref_gain = str(ctx.cfg.section.raw("adc.gain"))
    for det in DETECTORS:
        ch = ctx.adc_channel(det)
        readings: dict[str, tuple[float, float]] = {}
        for gain, lsb in lsb_by_gain.items():
            reported = ctx.dev.adc_gain(gain)
            rec.check(
                f"{det}/g{gain}/lsb",
                f"GAIN {gain} accepted",
                math.isclose(reported, lsb),
                f"lsb {reported:g} mV",
                f"{lsb:g} mV",
            )
            r = ctx.dev.adc_read(ch, n)
            readings[gain] = (r.mean * lsb, (r.std or 0.0) * lsb)
        ref_mv, ref_sd = readings[ref_gain]
        for gain, (mv, sd) in readings.items():
            fs_mv = full_scale * lsb_by_gain[gain]
            if abs(ref_mv) > 0.95 * fs_mv:
                rec.add(
                    f"{det}/g{gain}",
                    f"{det} at GAIN {gain}",
                    Status.PASS,
                    f"{ref_mv:.1f} mV is beyond this gain's +-{fs_mv:.0f} mV range: "
                    "clipping expected",
                    mv=mv,
                )
                continue
            limit = tol_mv + 3 * max(sd, ref_sd)
            rec.check(
                f"{det}/g{gain}",
                f"{det} at GAIN {gain} agrees with GAIN {ref_gain}",
                abs(mv - ref_mv) <= limit,
                f"{mv:.2f} mV vs {ref_mv:.2f} mV",
                f"within {limit:.2f} mV",
                mv=mv,
            )


@register("T03.4", "ADC data rate")
def t03_4(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    tol = ctx.th.num("adc.rate_tolerance_frac")
    overhead_ms = ctx.th.num("adc.conv_overhead_max_ms")
    duration_s = ctx.th.num("adc.rate_check_duration_s")
    n_max = ctx.cfg.limits["stream_buf_n"]  # buffered: not slowed by the serial line
    ch = ctx.adc_channel("opt101")
    for sps in ctx.cfg.section.ints("adc.rates_sps"):
        n = max(8, min(n_max, round(sps * duration_s)))
        with ctx.adc_rate(sps):
            samples = ctx.dev.adc_stream(ch, n)
        dts = sorted((b.t_us - a.t_us) / 1000.0 for a, b in itertools.pairwise(samples))
        if not dts:
            rec.check(f"r{sps}", f"{sps} SPS", False, "no samples")
            continue
        interval = dts[len(dts) // 2]
        nominal = 1000.0 / sps
        lo, hi = nominal * (1 - tol), nominal * (1 + tol) + overhead_ms
        rec.check(
            f"r{sps}",
            f"{sps} SPS conversion interval",
            lo <= interval <= hi,
            f"{interval:.3f} ms (nominal {nominal:.3f} ms, overhead {interval - nominal:+.3f} ms)",
            f"{lo:.3f}-{hi:.3f} ms",
            interval_ms=interval,
            nominal_ms=nominal,
        )


@register("T03.5", "Long-term dark stability")
def t03_5(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    duration = ctx.th.num("adc.stability_duration_s")
    period = 1.0 / ctx.th.num("adc.stability_rate_hz")
    warn_pct = ctx.th.num("adc.drift_warn_pct_fs_per_min")
    full_scale = ctx.cfg.section.integer("adc.full_scale_counts")
    ctx.dev.off()
    series: dict[str, tuple[list[float], list[float]]] = {d: ([], []) for d in DETECTORS}
    t0 = ctx.dev.now()
    k = 0
    while True:
        target = t0 + k * period
        if target - t0 > duration:
            break
        wait = target - ctx.dev.now()
        if wait > 0:
            ctx.dev.sleep(wait)
        for det in DETECTORS:
            r = ctx.dev.adc_read(ctx.adc_channel(det))
            ts, ys = series[det]
            ts.append(ctx.dev.now() - t0)
            ys.append(float(r.raw))
        k += 1
    for det, (ts, ys) in series.items():
        slope_per_min = linear_slope(ts, ys) * 60.0
        pct = abs(slope_per_min) / full_scale * 100.0
        s = stats(ys)
        rec.check(
            det,
            f"{det} drift over {duration:g} s",
            pct <= warn_pct,
            f"{slope_per_min:+.1f} counts/min ({pct:.3f} % FS/min), sigma {s.std:.2f}",
            f"<= {warn_pct:g} % FS/min",
            warn=True,
            drift_counts_per_min=slope_per_min,
            sigma=s.std,
            samples=len(ys),
            t_s=[round(t, 3) for t in ts],
            raw=ys,
        )


# ------------------------------------------------------------------------ T04


def _patterns() -> list[tuple[str, int]]:
    out = [("zero", 0x0000), ("ones", 0xFFFF)]
    out += [(f"w1/{b:02d}", 1 << b) for b in range(16)]
    out += [(f"w0/{b:02d}", 0xFFFF ^ (1 << b)) for b in range(16)]
    return out


@register("T04.1", "Shift-register patterns with CE low")
def t04_1(ctx: SuiteContext, rec: Recorder) -> None:
    ctx.require_adc()
    dev = ctx.dev
    ctx.dark()
    for name, mask in _patterns():
        echoed = dev.sr_raw(mask)
        st = dev.status()
        readings = {d: float(dev.adc_read(ctx.adc_channel(d)).raw) for d in DETECTORS}
        dark = {d: ctx.is_dark(d, v) for d, v in readings.items()}
        problems = []
        if echoed != mask or st.as_int("mask") != mask:
            problems.append(f"mask echoed 0x{echoed:04X}, STATUS 0x{st.as_int('mask'):04X}")
        if st.as_int("ce1") or st.as_int("ce2"):
            problems.append("CE not low after SR RAW")
        lit = [d for d, ok in dark.items() if not ok]
        if lit:
            problems.append(
                "light with CE low on "
                + ", ".join(f"{d} ({readings[d]:.0f})" for d in lit)
                + ": CE logic inverted or a driver enabled without CE?"
            )
        rec.check(
            name,
            f"SR RAW 0x{mask:04X}",
            not problems,
            "; ".join(problems) or "echoed, CE low, detectors dark",
            "mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark",
            ingaas_raw=readings["ingaas"],
            opt101_raw=readings["opt101"],
        )
    dev.off()


@register("T04.2", "Shift-register loopback (optional jumper)")
def t04_2(ctx: SuiteContext, rec: Recorder) -> None:
    f = ctx.dev.loop_test()
    rec.measure(**f.values)
    if f.as_int("fitted") == 0:
        raise Skip(
            "loopback jumper not fitted (optional: U2 pin 9 Q7' -> Nano D11, plan §6.3); "
            "the shift registers are verified optically by T05.3"
        )
    bad = f.as_int("bits_bad")
    rec.check(
        "loop",
        "32 patterns shift through U1 and U2 intact",
        f.as_int("pass") == 1,
        f"{f.as_int('bits_ok')} bits OK, {bad} bad"
        + ("" if bad == 0 else "; check DATA (A0), CLOCK (A1) and U1 pin 9 -> U2 pin 14 (SER)"),
        "0 bad bits",
    )


@register("T04.3", "Optical address verification")
def t04_3(ctx: SuiteContext, rec: Recorder) -> None:
    raise Skip("covered by T05.3 (each hole must light only its own expected response)")
