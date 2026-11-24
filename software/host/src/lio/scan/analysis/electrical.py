"""Electrical health (plan §6.2): coupling and ground shift, dark offset and leakage,
drift, noise, mains hum, coil EMI, select-only coupling.

Coupling anchor (S3 note): the optical response never vanishes inside the travel (the
far-field floor), so the height-invariant term C cannot come from a dark plateau.
It comes from the *blind* channels: holes whose wavelength the detector cannot see
(InGaAs on holes 1-7, 10, 11, 16; OPT101 on 12-16). There the lit-minus-dark signal
is purely electrical: coupling plus ground shift, both proportional to the rail
current. ``C[det][rail]`` is their median; a rail without blind holes is inferred
from the other rail by the current ratio.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from lio.config import HwConfig
from lio.results import Status
from lio.scan.analysis.data import DETECTORS, Array, Cube, Finding, grade, mv, pair

MAINS_HZ = (60.0, 120.0, 180.0)


def rail_current(cfg: HwConfig, rail: str) -> float:
    return float(cfg.section.num(f"rails.{rail}.current_ma"))


def blind_holes(cfg: HwConfig, det: str) -> list[int]:
    """Fitted holes whose wavelength ``det`` cannot see."""
    lo, hi = cfg.detectors[det].range_nm
    out = []
    for hole in range(1, 17):
        ch = cfg.channel(hole)
        wl = ch.wavelength_nm
        if ch.fitted and ch.expect_for(det) == "none" and wl is not None and not lo <= wl <= hi:
            out.append(hole)
    return out


def mains_rejected(cube: Cube) -> bool:
    """Readings integrated whole mains periods (firmware >= 2.5.1, ADC CFG MAINS)."""
    return bool((cube.meta.get("capabilities") or {}).get("mains_rejection"))


def coupling(cube: Cube, cfg: HwConfig) -> tuple[dict[str, dict[str, Any]], list[Finding]]:
    """C per detector and rail from the blind channels; the coupling and ground-shift
    findings."""
    ctx: dict[str, dict[str, Any]] = {}
    out: list[Finding] = []
    w_c, f_c = pair(cfg, "coupling_counts")
    _, f_g = pair(cfg, "ground_shift_mv_per_ma")
    for det in DETECTORS:
        holes, _, net = cube.lit_all(det)
        per_rail: dict[str, float] = {}
        n_rail: dict[str, int] = {}
        blind = blind_holes(cfg, det)
        for rail in ("A", "B"):
            hs = [h for h in blind if cfg.channel(h).rail == rail]
            m = np.isin(holes, hs)
            if m.sum():
                per_rail[rail] = float(np.median(net[m]))
                n_rail[rail] = len(hs)
        inferred: list[str] = []
        if len(per_rail) == 1:  # scale by the rail current
            (r0, c0), r1 = next(iter(per_rail.items())), "B" if "A" in per_rail else "A"
            per_rail[r1] = c0 * rail_current(cfg, r1) / rail_current(cfg, r0)
            inferred.append(r1)
        if not per_rail:
            ctx[det] = {"C": {"A": 0.0, "B": 0.0}, "inferred": ["A", "B"]}
            out.append(Finding(f"elec/{det}/coupling", f"{det}: electrical coupling", Status.SKIP,
                               detail="no blind channels measured"))  # fmt: skip
            continue
        ctx[det] = {"C": per_rail, "inferred": inferred, "blind": blind}
        worst = max(abs(v) for r, v in per_rail.items() if r not in inferred)
        # subtracted from every hole of its rail (optics: O = S - C), so it costs nothing
        # below the FAIL limit; beyond it the coupling itself points at a wiring fault
        st = Status.FAIL if worst >= f_c else Status.PASS
        out.append(Finding(
            f"elec/{det}/coupling", f"{det}: electrical coupling (height-invariant, LED on)", st,
            round(worst, 1), "counts",
            ", ".join(f"rail {r}: {v:+.1f} counts ({mv(v):+.2f} mV)"
                      + (" inferred" if r in inferred else f" from {n_rail[r]} blind holes")
                      for r, v in sorted(per_rail.items())),
            f"corrected in software below {f_c:g} counts (FAIL at or above)",
            {"C_counts": per_rail, "blind_holes": blind, "inferred": inferred},
        ))  # fmt: skip
        # ground shift: C proportional to the rail current (through the origin)
        meas = [(rail_current(cfg, r), v) for r, v in per_rail.items() if r not in inferred]
        num = sum(i * c for i, c in meas)
        den = sum(i * i for i, _ in meas)
        k = num / den if den else 0.0  # counts per mA
        scales = None
        if len(meas) == 2 and all(abs(c) > w_c / 2 for _, c in meas):
            (ia, ca), (ib, cb) = meas
            ratio = (cb / ib) / (ca / ia)
            scales = 0.6 <= ratio <= 1.6
        k_mv = mv(k)
        st = Status.FAIL if abs(k_mv) >= f_g else Status.PASS  # corrected below FAIL
        if scales is False and st != Status.PASS:
            st = Status.WARN  # coupling, but not in proportion to the current
        out.append(Finding(
            f"elec/{det}/ground_shift", f"{det}: ground shift (coupling vs rail current)", st,
            round(k_mv, 4), "mV/mA",
            f"{k:+.3f} counts/mA" + ("" if scales is None else
                                     ("; scales with the rail current" if scales else
                                      "; does not scale with the rail current")),
            f"corrected in software below {f_g:g} mV/mA (FAIL at or above)",
            {"counts_per_ma": k, "scales_with_current": scales},
        ))  # fmt: skip
    return ctx, out


def _rf_ohm(cfg: HwConfig, det: str) -> float | None:
    """The TIA feedback resistor, where the config gives one (detectors.<det>.rf_ohm)."""
    try:
        return float(cfg.section.raw(f"detectors.{det}.rf_ohm"))
    except Exception:
        return None


def _eq_current_eligibility(cube: Cube, cfg: HwConfig, det: str) -> tuple[Any, float | None]:
    """Quantity gate for a physical input current from the run's FROZEN facts."""
    from lio.scan.provenance import Quantity, RfProvenance, quantity_eligibility

    snap = cube.meta.get("acquisition_snapshot") if isinstance(cube.meta, dict) else None
    snap = snap if isinstance(snap, dict) else {}
    rf_raw = (snap.get("rf") or {}).get(det)
    rf = None
    if isinstance(rf_raw, dict):
        rf = RfProvenance(rf_raw.get("value_ohm"), str(rf_raw.get("state", "unknown")),
                          str(rf_raw.get("note", "")))  # fmt: skip
    rng = str((snap.get("input_range") or {}).get(det) or "unverified")
    elig = quantity_eligibility(
        Quantity.EQ_CURRENT, detector=det, lsb_mv=mv(1.0), rf=rf,
        input_range=rng,
    )  # fmt: skip
    return elig, (None if rf is None else rf.value_ohm)


def dark_offset(cube: Cube, cfg: HwConfig) -> list[Finding]:
    """TIA dark offset and its equivalent input current (the T06 dark ranges)."""
    out = []
    for det in DETECTORS:
        _, _, d, _ = cube.darks(det)
        d = d[np.isfinite(d)]
        if not len(d):
            out.append(Finding(f"elec/{det}/dark_offset", f"{det}: dark offset", Status.SKIP,
                               detail="no dark frames"))  # fmt: skip
            continue
        lo, hi = (float(x) for x in cfg.thresholds.raw(f"dark.{det}_counts"))
        m = float(np.median(d))
        st = Status.PASS if lo <= m <= hi else Status.FAIL
        data: dict[str, Any] = {"counts": m, "mv": mv(m), "range_counts": [lo, hi]}
        detail = f"{m:+.1f} counts ({mv(m):+.2f} mV)"
        # S2: an input current needs a verified A0 operating range and a known,
        # run-frozen Rf. Today's config Rf is never substituted into a run, and an
        # unverified A0 blocks the physical-current label (counts/mV stay valid).
        elig, rf_used = _eq_current_eligibility(cube, cfg, det)
        if elig.eligible and rf_used:
            i_na = -mv(m) * 1e-3 / rf_used * 1e9
            data["i_eq_na"] = i_na
            detail += f"; equivalent input current {i_na:+.1f} nA (Rf {rf_used / 1e6:g} MΩ)"
        else:
            data["i_eq_unavailable"] = elig.reason
            detail += f"; equivalent input current not computed ({elig.reason})"
        out.append(Finding(f"elec/{det}/dark_offset", f"{det}: dark offset (ADC)", st,
                           round(mv(m), 3), "mV", detail,
                           f"{lo:g} to {hi:g} counts (thresholds.dark)", data))  # fmt: skip
    return out


def drift(cube: Cube, cfg: HwConfig) -> list[Finding]:
    """Dark level vs time, separated from height (both passes decorrelate them)."""
    out = []
    for det in DETECTORS:
        t, h, d, ph = cube.darks(det)
        ok = np.isfinite(d)
        t, h, d, ph = t[ok], h[ok], d[ok], ph[ok]
        min_s = float(cfg.section.raw("scan.health.drift_min_span_s"))
        if len(d) < 6 or float(np.ptp(t)) < min_s:
            out.append(Finding(f"elec/{det}/drift", f"{det}: dark drift", Status.SKIP,
                               detail=f"under {min_s / 60:.0f} min of dark frames: "
                               "too short for a drift estimate"))  # fmt: skip
            continue
        th = t / 3600.0
        cols = [np.ones_like(th), th]
        span = float(np.ptp(h))
        sep = False
        if span > 0 and float(np.ptp(th)) > 0:
            # A smooth height term, so a leak at the bottom is not read as drift. Only
            # when time and height are not collinear (a run with only a down pass is):
            # then the two cannot be told apart and the dark is taken as height-free.
            corr = abs(float(np.corrcoef(th, h)[0, 1]))
            if corr < 0.9:
                hn = (h - h.mean()) / span
                cols += [hn, hn * hn]
                sep = True
        x = np.stack(cols, axis=1)
        coef, *_ = np.linalg.lstsq(x, d, rcond=None)
        slope = float(coef[1])  # counts per hour
        resid = d - x @ coef
        dof = max(1, len(d) - x.shape[1])
        s2 = float(resid @ resid) / dof
        cov = s2 * np.linalg.pinv(x.T @ x)
        se = float(math.sqrt(max(0.0, float(cov[1, 1]))))
        w, f = pair(cfg, f"drift_mv_per_h.{det}")
        st = grade(abs(mv(slope)), w, f)
        if st != Status.PASS and abs(slope) < 3 * se:
            st = Status.PASS  # not significant
        p1 = d[ph == "P1"]
        p4 = d[ph == "P4"]
        data: dict[str, Any] = {"counts_per_h": slope, "se_counts_per_h": se,
                                "height_separated": sep}  # fmt: skip
        detail = f"{mv(slope):+.2f} ± {mv(se):.2f} mV/h"
        if det == "ingaas":
            rf = _rf_ohm(cfg, det) or 1e6
            na_h = -mv(slope) * 1e-3 / rf * 1e9
            data["na_per_h"] = na_h
            detail += f" ({na_h:+.1f} nA/h)"
        if len(p1) and len(p4):
            data["p4_minus_p1_counts"] = float(np.mean(p4) - np.mean(p1))
            detail += f"; P4 - P1 {mv(data['p4_minus_p1_counts']):+.2f} mV"
        out.append(Finding(f"elec/{det}/drift", f"{det}: dark drift over the run", st,
                           round(mv(slope), 3), "mV/h", detail,
                           f"|slope| < {w:g} mV/h (WARN), < {f:g} (FAIL)", data))  # fmt: skip
    return out


def _burst_fit(t: Array, v: Array) -> tuple[float, dict[float, float], float]:
    """Per-burst least squares: mean + sin/cos at the mains harmonics.
    Returns (total variance, amplitude per frequency, residual sigma)."""
    v = v - v.mean()
    cols = [np.ones_like(t)]
    for f in MAINS_HZ:
        cols += [np.cos(2 * math.pi * f * t), np.sin(2 * math.pi * f * t)]
    x = np.stack(cols, axis=1)
    coef, *_ = np.linalg.lstsq(x, v, rcond=None)
    amps = {f: float(math.hypot(coef[1 + 2 * i], coef[2 + 2 * i])) for i, f in enumerate(MAINS_HZ)}
    resid = v - x @ coef
    return float(v.var()), amps, float(resid.std())


def _split_bursts(t: Array, v: Array) -> list[tuple[Array, Array]]:
    """The buffered 48-sample bursts of one record (a gap > 20 ms starts a new one)."""
    if len(t) < 8:
        return []
    cut = np.where(np.diff(t) > 0.02)[0] + 1
    return [(a, b) for a, b in zip(np.split(t, cut), np.split(v, cut), strict=True) if len(a) >= 16]


def noise_spectrum(cube: Cube, state: str, det: str) -> dict[str, Any] | None:
    """Mains amplitudes (counts, RMS over bursts), mains variance fraction, broadband sigma."""
    bursts = [b for t, v in cube.streams(state, det) for b in _split_bursts(t, v)]
    if not bursts:
        return None
    var_tot = 0.0
    var_mains = 0.0
    a2 = dict.fromkeys(MAINS_HZ, 0.0)
    sig = []
    for t, v in bursts:
        vt, amps, rs = _burst_fit(t, v)
        var_tot += vt
        var_mains += sum(a * a / 2 for a in amps.values())
        for f, a in amps.items():
            a2[f] += a * a
        sig.append(rs)
    n = len(bursts)
    return {
        "amp_counts": {f"{int(f)}": math.sqrt(a2[f] / n) for f in MAINS_HZ},
        "mains_fraction": var_mains / var_tot if var_tot > 0 else 0.0,
        "sigma_counts": float(np.median(sig)),
        "bursts": n,
    }


def hum(cube: Cube, cfg: HwConfig) -> tuple[dict[str, Any], list[Finding]]:
    out = []
    spectra: dict[str, Any] = {}
    for det in DETECTORS:
        sp = noise_spectrum(cube, "coils_off", det)
        spectra[det] = sp
        if sp is None:
            out.append(Finding(f"elec/{det}/hum", f"{det}: mains hum", Status.SKIP,
                               detail="no hum records"))  # fmt: skip
            continue
        a60 = mv(sp["amp_counts"]["60"])
        w, f = pair(cfg, f"hum_mv.{det}")
        st = grade(a60, w, f)
        frac = sp["mains_fraction"]
        fw = float(cfg.section.raw("scan.health.hum_fraction_warn"))
        if st == Status.PASS and frac > fw and a60 > w / 4:
            st = Status.WARN
        rejected = mains_rejected(cube)
        if rejected and st == Status.WARN:
            st = Status.PASS  # integrated over whole mains periods: cancels in the readings
        out.append(Finding(
            f"elec/{det}/hum", f"{det}: mains hum (coils off)", st, round(a60, 4), "mV",
            "60/120/180 Hz: "
            + " / ".join(f"{mv(sp['amp_counts'][k]):.3f}" for k in ("60", "120", "180"))
            + f" mV; {100 * frac:.0f}% of the variance at mains harmonics; broadband sigma "
            f"{mv(sp['sigma_counts']):.3f} mV"
            + ("; readings integrate whole mains periods, so it cancels in the measurements"
               if rejected else ""),
            f"60 Hz amplitude < {w:g} mV (WARN; not when the readings reject it), "
            f"< {f:g} (FAIL); mains fraction < {fw:g}",
            sp,
        ))  # fmt: skip
    return spectra, out


def coil_emi(cube: Cube, cfg: HwConfig, spectra: dict[str, Any]) -> list[Finding]:
    out = []
    w, f = pair(cfg, "coil_emi_ratio")
    for det in DETECTORS:
        mov = noise_spectrum(cube, "coils_moving", det)
        off = spectra.get(det)
        if mov is None or off is None:
            out.append(Finding(f"elec/{det}/coil_emi", f"{det}: coil interference", Status.SKIP,
                               detail="needs hum records, coils off and moving"))  # fmt: skip
            continue
        floor = float(cfg.section.raw(f"scan.health.noise_floor_counts.{det}"))
        ratio = max(mov["sigma_counts"], floor) / max(off["sigma_counts"], floor)
        st = grade(ratio, w, f)
        moving = bool((cube.meta.get("plan") or {}).get("continuous"))
        if not moving:
            st = Status.PASS  # stop-measure-move: no reading is taken while the coils switch
        out.append(Finding(
            f"elec/{det}/coil_emi", f"{det}: coil interference (moving vs coils off)", st,
            round(ratio, 2), "x",
            f"sigma {mv(mov['sigma_counts']):.3f} mV moving vs "
            f"{mv(off['sigma_counts']):.3f} mV off "
            "(measured while moving, S0 D2)"
            + ("" if moving else "; judged only when measuring while moving (continuous mode): "
               "every other reading is taken with the motors stopped"),
            f"ratio < {w:g} (WARN), < {f:g} (FAIL)",
            {"moving": mov, "off": off},
        ))  # fmt: skip
    return out


def select_only(cube: Cube, cfg: HwConfig) -> list[Finding]:
    """MOSFET selected, CE low: gate-drive coupling into each detector."""
    out = []
    w, f = pair(cfg, "coupling_counts")
    for det in DETECTORS:
        holes, _, net = cube.state_rows("select_only", det)
        ok = np.isfinite(net)
        if not ok.sum():
            out.append(Finding(f"elec/{det}/select_only", f"{det}: select-only coupling",
                               Status.SKIP, detail="no select-only readings"))  # fmt: skip
            continue
        holes, net = holes[ok], net[ok]
        i = int(np.argmax(np.abs(net)))
        worst = float(abs(net[i]))
        hole = int(holes[i])
        # Gate-drive pickup with CE low: the LED is not on. Cap at WARN so a few
        # tens of counts of coupling do not paint a working hole red / fail the rig.
        status = grade(worst, w, f)
        if status == Status.FAIL:
            status = Status.WARN
        # Name the worst hole so the twin/verdict attribute it (not "untied").
        out.append(Finding(
            f"elec/{det}/h{hole:02d}/select_only",
            f"{det}: select-only coupling (MOSFET on, CE low)",
            status, round(worst, 1), "counts",
            f"largest on hole {hole}: {net[i]:+.1f} counts",
            f"< {w:g} counts (WARN); FAIL capped to WARN (gate coupling, LED off)",
            {"per_hole": {int(h): float(v) for h, v in zip(holes, net, strict=True)}},
        ))  # fmt: skip
    return out


def coupling_states(cube: Cube, cfg: HwConfig) -> list[Finding]:
    """Firmware 2.5.0 DBG STATE readings (P1): CE-only per rail (driver enable with no
    LED path) and wrong-rail per hole (the hole selected, the other rail enabled: its
    LED must stay dark, light means it is wired to the other rail)."""
    out: list[Finding] = []
    w_c, f_c = pair(cfg, "coupling_counts")
    w_p, f_p = pair(cfg, "optics.plausibility_counts")
    for det in DETECTORS:
        m = cube.mask(state="ce_only", detector=det)
        if not m.any():
            continue
        rails = cube.num["rep"][m]
        net = cube.num["net_counts"][m]
        worst = float(np.max(np.abs(net)))
        out.append(Finding(
            f"elec/{det}/ce_only", f"{det}: CE-only coupling (driver enabled, no LED)",
            grade(worst, w_c, f_c), round(worst, 1), "counts",
            ", ".join(f"CE{int(r)}: {v:+.1f}" for r, v in zip(rails, net, strict=True)),
            f"< {w_c:g} counts (WARN), < {f_c:g} (FAIL)",
        ))  # fmt: skip
    if not cube.mask(state="wrong_rail").any():
        return out
    for hole in range(1, 17):
        ch = cfg.channel(hole)
        vals = []
        for det in DETECTORS:
            m = cube.mask(state="wrong_rail", detector=det) & (cube.num["hole"] == hole)
            if m.any() and ch.expect_for(det) != "none":
                vals.append((det, float(np.max(cube.num["net_counts"][m]))))
        if not vals:
            continue
        det, v = max(vals, key=lambda x: x[1])
        other = "B" if ch.rail == "A" else "A"
        out.append(Finding(
            f"optics/wrong_rail/h{hole:02d}", f"hole {hole} dark with only RAIL {other} enabled",
            grade(v, w_p, f_p), round(v, 1), "counts",
            f"{v:+.0f} counts on {det} with the hole selected and RAIL {other} enabled"
            + ("; it lights: wired to the other rail" if v >= w_p else ""),
            f"< {w_p:g} counts (WARN), < {f_p:g} (FAIL)",
        ))  # fmt: skip
    return out


def capability_skips(cube: Cube) -> list[Finding]:
    titles = {
        "coupling_states": ("elec/coupling_states", "CE-only and wrong-rail coupling states"),
        "rail_monitor": ("elec/rails", "supply rails and ground (A2/A3)"),
        "home_sensors": ("mech/home_sensors", "home sensors"),
    }
    out = []
    for key, reason in (cube.meta.get("skipped_checks") or {}).items():
        fid, title = titles.get(key, (f"cap/{key}", key))
        out.append(Finding(fid, title, Status.SKIP, detail=str(reason)))
    return out


def analyse(cube: Cube, cfg: HwConfig) -> tuple[dict[str, Any], list[Finding]]:
    ctx, out = coupling(cube, cfg)
    out += dark_offset(cube, cfg)
    out += drift(cube, cfg)
    spectra, f_hum = hum(cube, cfg)
    out += f_hum
    out += coil_emi(cube, cfg, spectra)
    out += select_only(cube, cfg)
    out += coupling_states(cube, cfg)
    out += capability_skips(cube)
    return {"coupling": ctx, "spectra": spectra}, out
