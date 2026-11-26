"""Optical performance (plan §6.1) and the decomposition net = O·g(h) + C (§6.6).

Per hole and detector, from the down pass (P2): the response curve S(h), smoothed
(local quadratic, Savitzky-Golay style, works on uneven heights); the optical
amplitude O = S(h_opt) - C with C from the blind channels on the hole's rail
(electrical.coupling); the modulation (how much S changes with height, relative to
O: a flat curve is electrical, not light); FWHM; SNR; headroom.

Wavelength plausibility uses the channel map's ``expect`` (signal / weak / none):
a detector that responds optically to a hole it cannot see means a wrong or swapped
LED. (The responsivity-ratio form waits for cited tables in the config: S0 D15.)
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from lio.config import HwConfig
from lio.results import Status
from lio.scan.analysis.data import (
    DETECTORS,
    Array,
    Cube,
    Curve,
    Finding,
    grade,
    grade_low,
    health,
    mv,
    pair,
)
from lio.scan.analysis.electrical import blind_holes

KEEP = ("h_opt", "O", "C", "modulation", "fwhm_hs")


def smooth(h: Array, v: Array, half: int = 2) -> Array:
    """Local quadratic fit over 2*half+1 neighbours (linear with fewer points)."""
    n = len(v)
    if n < 5:
        return np.array(v, dtype=np.float64)
    out: Array = np.empty(n)
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        x = h[lo:hi] - h[i]
        deg = 2 if hi - lo >= 4 else 1
        c = np.polyfit(x, v[lo:hi], deg)
        out[i] = c[-1]
    return out


def fwhm(h: Array, s: Array, c: float) -> tuple[float | None, bool]:
    """Width where S - C >= half its peak. (width, complete): incomplete when the
    curve stays above half at an end of the travel (then the width is a lower bound)."""
    r = s - c
    i = int(np.argmax(r))
    half = r[i] / 2
    if r[i] <= 0:
        return None, False
    complete = True
    j = i
    while j > 0 and r[j - 1] >= half:
        j -= 1
    if j == 0:
        lo, complete = float(h[0]), False
    else:
        lo = float(np.interp(half, [r[j - 1], r[j]], [h[j - 1], h[j]]))
    k = i
    while k < len(r) - 1 and r[k + 1] >= half:
        k += 1
    if k == len(r) - 1:
        hi, complete = float(h[-1]), complete and False
    else:
        hi = float(np.interp(half, [r[k + 1], r[k]], [h[k + 1], h[k]]))
    return hi - lo, complete


def channel_stats(curve: Curve, c: float) -> dict[str, Any]:
    s = smooth(curve.h, curve.net)
    i = int(np.argmax(s - c))
    o = float(s[i] - c)
    span = float(np.max(s) - np.min(s))
    width, complete = fwhm(curve.h, s, c)
    return {
        "h_opt": float(curve.h[i]),
        "O": o,
        "S_opt": float(s[i]),
        "C": c,
        "modulation": span / max(abs(o), 1e-9),
        "fwhm_hs": width,
        "fwhm_complete": complete,
        "h": curve.h.tolist(),
        "net": curve.net.tolist(),
        "smooth": s.tolist(),
    }


def samples_per_reading(meta: dict[str, Any]) -> float:
    """Raw ADC samples averaged into one scan reading (1 when not mains-integrated)."""
    if not (meta.get("capabilities") or {}).get("mains_rejection"):
        return 1.0
    st = (meta.get("plan") or {}).get("settings") or {}
    hz = float(st.get("mains_hz") or 0)
    periods = float(st.get("mains_periods") or 0)
    pre = meta.get("adc_preflight") or [{}]
    rate = float((pre[-1] if isinstance(pre, list) and pre else {}).get("rate_sps") or 0)
    if hz <= 0 or periods <= 0 or rate <= 0:
        return 1.0
    return max(1.0, periods * rate / hz)


def signal_floors(
    cfg: HwConfig, elec: dict[str, Any], meta: dict[str, Any] | None = None
) -> dict[str, tuple[float, float]]:
    """[WARN, FAIL] for "this hole gives light", per detector: the configured counts, or
    8 / 4 times the noise of one net reading if that is larger (a noisy detector's flat
    curve must not pass for light). The dark-stream sigma is per raw sample; a
    mains-integrated reading averages ``samples_per_reading`` of them, and a net is a
    difference of two readings (owner calibration 2026-11-25)."""
    w, f = pair(cfg, "optics.min_signal_counts")
    k = samples_per_reading(meta or {})
    scale = math.sqrt(2.0 / k) if k > 1 else 1.0
    out = {}
    for det in DETECTORS:
        sp = (elec.get("spectra") or {}).get(det) or {}
        sig = float(sp.get("sigma_counts", 0.0)) * scale
        out[det] = (max(w, 8 * sig), max(f, 4 * sig))
    return out


def _judged(cube: Cube, cfg: HwConfig) -> bool:
    return cube.sample_id in [str(x) for x in health(cfg, "optics.judged_samples")]


def analyse(
    cube: Cube, cfg: HwConfig, elec: dict[str, Any], reference: Cube | None = None
) -> tuple[dict[str, Any], list[Finding]]:
    out: list[Finding] = []
    stats: dict[str, dict[int, dict[str, Any]]] = {d: {} for d in DETECTORS}
    coup = elec["coupling"]
    judged = _judged(cube, cfg)
    floors = signal_floors(cfg, elec, cube.meta)
    w_pl, f_pl = pair(cfg, "optics.plausibility_counts")
    mod_min = float(health(cfg, "optics.modulation_min"))
    if not cube.mask(state="lit", phase="P2").any():
        out.append(Finding("optics/curves", "response curves vs height", Status.SKIP,
                           detail="no down pass in this mode (no height data)"))  # fmt: skip
        return {"channels": stats, "floors": floors}, out
    for det in DETECTORS:
        w_sig, f_sig = floors[det]
        cmap = coup.get(det, {}).get("C", {})
        blind = set(blind_holes(cfg, det))
        for hole in range(1, 17):
            ch = cfg.channel(hole)
            cur = cube.curve(hole, det)
            if len(cur) < 2:
                continue
            c = float(cmap.get(ch.rail, 0.0))
            st = channel_stats(cur, c)
            stats[det][hole] = st
            exp = ch.expect_for(det)
            fid = f"optics/{det}/h{hole:02d}"
            if exp == "signal" and ch.fitted:
                if not judged:
                    status = Status.SKIP
                    why = f"sample {cube.sample_id!r} is not judged against absolute levels"
                else:
                    status = grade_low(st["O"], w_sig, f_sig)
                    why = ""
                flat = st["modulation"] < mod_min and abs(st["S_opt"]) > w_sig
                detail = (f"O {st['O']:.0f} counts at h {st['h_opt']:.0f}, C {c:+.1f}, "
                          f"modulation {st['modulation']:.2f}")  # fmt: skip
                if flat:
                    detail += "; flat in height: the signal is not light"
                    if judged:
                        status = Status.FAIL
                out.append(Finding(f"{fid}/response", f"hole {hole} ({ch.label}) on {det}",
                                   status, round(st["O"], 1), "counts", why or detail,
                                   f"O >= {w_sig:g} (WARN below), >= {f_sig:g} (FAIL below)",
                                   {k: st[k] for k in KEEP}))  # fmt: skip
            elif hole in blind:
                # a nominally blind channel: a response is unassigned (not proof of a wrong LED)
                r = st["O"]
                status = grade(r, w_pl, f_pl)
                optical = st["modulation"] >= mod_min and r >= w_pl
                if status != Status.PASS and not optical:
                    status = Status.WARN  # large, but flat: hole-specific coupling, not light
                # Hole 16 (1850 nm): beyond both detectors' range. A silicon response has an
                # unassigned spectrum (tail/secondary emission/pickup possible) - WARN only.
                beyond = not ch.expected_detectors
                # Broadband LEDs (white / pink: blue die + phosphor) emit a red/NIR tail the
                # InGaAs genuinely sees; a bright sample reflects it (owner 2026-11-26: whey
                # scan, h11 +121 counts). Unassigned light, not a fault: WARN at most.
                broadband = (ch.label or "").lower() in ("white", "pink")
                if (beyond or broadband) and status == Status.FAIL:
                    status = Status.WARN
                out.append(Finding(
                    f"{fid}/plausibility", f"hole {hole} ({ch.label}) seen by {det}?", status,
                    round(r, 1), "counts",
                    f"{det} cannot see {ch.wavelength_nm:g} nm; residual {r:+.0f} counts over "
                    f"C {c:+.1f}" + ("; height-dependent (optical)" if optical else ""),
                    f"< {w_pl:g} counts (WARN)"
                    + ("; FAIL capped to WARN: no in-range detector for this hole"
                       if beyond else f", < {f_pl:g} (FAIL)"),
                    {"O": r, "modulation": st["modulation"]},
                ))  # fmt: skip
        out += _detector_level(cube, cfg, det, stats[det], coup.get(det, {}), judged,
                               floors[det])  # fmt: skip
    out += _intermittent(cube, cfg, floors)
    planned = len((cube.meta.get("plan") or {}).get("heights_down") or [])
    got = len(np.unique(cube.num["height_hs"][cube.mask(state="lit", phase="P2")]))
    if got < planned:
        why = f"down pass incomplete ({got} of {planned} heights)"
        out.append(Finding("optics/optimum", "optimum height (all holes)", Status.SKIP, detail=why))
    else:
        out += _optimum(cfg, stats)
    out += _snr_headroom(cube, cfg, stats, elec)
    out += _stray(cube, cfg, stats, reference)
    out += _effectiveness(cube, cfg, stats, reference)
    return {"channels": stats, "floors": floors}, out


def _expected(cfg: HwConfig, det: str, stats: dict[int, dict[str, Any]]) -> list[int]:
    return [
        h for h in stats if cfg.channel(h).fitted and cfg.channel(h).expect_for(det) == "signal"
    ]


def _detector_level(cube: Cube, cfg: HwConfig, det: str, st: dict[int, dict[str, Any]],
                    coup: dict[str, Any], judged: bool,
                    floor: tuple[float, float]) -> list[Finding]:  # fmt: skip
    out: list[Finding] = []
    exp = _expected(cfg, det, st)
    if not exp:
        return out
    f_sig = floor[1]
    w_c, _ = pair(cfg, "coupling_counts")
    o = np.array([st[h]["O"] for h in exp])
    no_light = int((o < f_sig).sum())
    cvals = [abs(v) for v in (coup.get("C") or {}).values()]
    c_big = bool(cvals) and max(cvals) >= w_c
    frac = no_light / len(exp)
    status = Status.FAIL if (frac >= 0.75 and c_big) else Status.PASS
    out.append(Finding(
        f"optics/{det}/electrical_only", f"{det}: signal electrical only (no light)?", status,
        round(frac, 2), "fraction",
        f"{no_light}/{len(exp)} expected holes show no optical response; coupling "
        + ("present" if c_big else "small"),
        f"FAIL when >= 75% of expected holes have O < {f_sig:g} while |C| >= {w_c:g}",
        {"no_light_holes": [h for h in exp if st[h]["O"] < f_sig]},
    ))  # fmt: skip
    med = float(np.median(o))
    if judged:
        try:
            w, f = pair(cfg, f"optics.throughput_counts.{cube.sample_id}.{det}")
            ts = grade_low(med, w, f)
            crit = f"median O >= {w:g} (WARN below), >= {f:g} (FAIL below) for {cube.sample_id}"
        except Exception:
            ts, crit = Status.SKIP, "no throughput threshold for this sample"
    else:
        ts, crit = Status.SKIP, f"sample {cube.sample_id!r}: judged against its baseline only"
    cv = float(np.std(o) / abs(np.mean(o)) * 100) if np.mean(o) else float("nan")
    out.append(Finding(
        f"optics/{det}/throughput", f"{det}: optical throughput (window, alignment)", ts,
        round(med, 1), "counts",
        f"median O over {len(exp)} expected holes; spread (CV) {cv:.0f}% across holes",
        crit, {"O": {h: st[h]["O"] for h in exp}, "cv_pct": cv},
    ))  # fmt: skip
    return out


def _raw_by_height(cube: Cube, hole: int, det: str, phase: str,
                   direction: str) -> dict[float, float]:  # fmt: skip
    m = cube.mask(state="lit", detector=det, phase=phase, direction=direction)
    m &= (cube.num["hole"] == hole) & (cube.num["rep"] == 0) & (cube.str["kind"] == "measure")
    return {float(h): float(v) for h, v in zip(cube.num["height_hs"][m],
                                               cube.num["net_counts"][m], strict=True)}  # fmt: skip


def _intermittent(cube: Cube, cfg: HwConfig,
                  floors: dict[str, tuple[float, float]]) -> list[Finding]:  # fmt: skip
    """A hole whose readings jump on BOTH inputs at the same moment: an electrical event
    (a joint opening, an intermittent short), not light. Found by comparing the raw down
    and up readings at the same heights (raw: the despiked curves would hide it)."""
    out: list[Finding] = []
    if not cube.mask(state="lit", phase="P3", direction="up").any():
        return out
    frac = float(health(cfg, "optics.intermittent_frac"))
    for hole in range(1, 17):
        events = []
        per = {d: (_raw_by_height(cube, hole, d, "P2", "down"),
                   _raw_by_height(cube, hole, d, "P3", "up")) for d in DETECTORS}  # fmt: skip
        common = set(per["opt101"][0]) & set(per["opt101"][1])
        common &= set(per["ingaas"][0]) & set(per["ingaas"][1])
        for h in sorted(common):
            jumps = []
            for d in DETECTORS:
                a, b = per[d][0][h], per[d][1][h]
                tol = max(5 * floors[d][1], frac * max(abs(a), abs(b)))
                jumps.append(abs(a - b) > tol)
            if all(jumps):
                events.append(h)
        ch = cfg.channel(hole)
        if not common:
            continue
        if not events:
            ok = f"down and up agree at {len(common)} heights"
            out.append(Finding(f"optics/h{hole:02d}/intermittent",
                               f"hole {hole} ({ch.label}) intermittent", Status.PASS, 0.0,
                               "heights", ok))  # fmt: skip
        else:
            # WARN only: the LED usually still works; this flags a flaky joint to reseat,
            # not a dead channel that should paint the twin red / fail the system.
            out.append(Finding(
                f"optics/h{hole:02d}/intermittent", f"hole {hole} ({ch.label}) intermittent",
                Status.WARN, float(len(events)),
                "heights",
                f"down and up readings disagree on both detectors at once at {len(events)} "
                f"height(s): {', '.join(f'{h:.0f}' for h in events)}",
                f"both detectors within max(5 x noise floor, {frac:g} x reading) of each other",
                {"heights": events},
            ))  # fmt: skip
    return out


def _optimum(cfg: HwConfig, stats: dict[str, dict[int, dict[str, Any]]]) -> list[Finding]:
    """Overall optimum: the height maximising the weakest normalised expected response."""
    curves = []
    for det in DETECTORS:
        for h in _expected(cfg, det, stats[det]):
            s = stats[det][h]
            if s["O"] > 0:
                curves.append((np.array(s["h"]), (np.array(s["smooth"]) - s["C"]) / s["O"]))
    if not curves:
        return [Finding("optics/optimum", "optimum height", Status.SKIP,
                        detail="no optical response to place it")]  # fmt: skip
    grid = curves[0][0]
    worst = np.min(np.stack([np.interp(grid, h, n) for h, n in curves]), axis=0)
    i = int(np.argmax(worst))
    h_opt = float(grid[i])
    lead = cfg.section.raw("scan.lead_mm_per_rev")
    mm = None if lead in (None, "") else h_opt / 4096.0 * float(lead)
    at_end = i in (0, len(grid) - 1)
    return [Finding(
        "optics/optimum", "optimum height (all holes)", Status.WARN if at_end else Status.PASS,
        h_opt, "half-steps",
        f"{h_opt:.0f} half-steps" + (f" ({mm:.2f} mm)" if mm is not None else "")
        + f"; weakest normalised response there {worst[i]:.2f}"
        + ("; at an end of the travel: the true peak may lie beyond" if at_end else ""),
        "", {"h_opt": h_opt, "mm": mm, "per_hole": {
            f"{d}/h{h:02d}": stats[d][h]["h_opt"]
            for d in DETECTORS
            for h in _expected(cfg, d, stats[d])
        }},
    )]  # fmt: skip


def _snr_headroom(cube: Cube, cfg: HwConfig, stats: dict[str, dict[int, dict[str, Any]]],
                  elec: dict[str, Any]) -> list[Finding]:  # fmt: skip
    out = []
    snr_min = float(health(cfg, "optics.snr_db_min"))
    head_min = float(health(cfg, "optics.headroom_pct_min"))
    for det in DETECTORS:
        sp = (elec.get("spectra") or {}).get(det)
        exp = _expected(cfg, det, stats[det])
        if sp and exp:
            sig = max(float(sp["sigma_counts"]), 0.5)
            f_sig = signal_floors(cfg, elec, cube.meta)[det][1]
            live = [h for h in exp if stats[det][h]["O"] >= f_sig]  # dead holes: see response
            snr = {h: 20 * math.log10(stats[det][h]["O"] / sig) for h in live}
            if not snr:
                continue
            worst = min(snr, key=lambda h: snr[h])
            out.append(Finding(
                f"optics/{det}/snr", f"{det}: signal-to-noise at the optimum",
                Status.WARN if snr[worst] < snr_min and _judged(cube, cfg) else Status.PASS,
                round(snr[worst], 1), "dB",
                f"weakest hole {worst}: {snr[worst]:.1f} dB (noise sigma {mv(sig):.3f} mV)",
                f">= {snr_min:g} dB", {"per_hole_db": snr},
            ))  # fmt: skip
        m = cube.mask(state="lit", detector=det)
        lit = cube.num["lit_counts"][m]
        lit = lit[np.isfinite(lit)]
        if len(lit):
            sat = cfg.detectors[det].saturation_counts
            peak = float(lit.max())
            head = 100 * (1 - peak / sat)
            out.append(Finding(
                f"optics/{det}/headroom", f"{det}: saturation headroom",
                Status.WARN if head < head_min else Status.PASS, round(head, 1), "%",
                f"highest lit reading {peak:.0f} of {sat} counts", f">= {head_min:g}%",
            ))  # fmt: skip
    return out


def _ref_shape(
    ref: Cube, cfg: HwConfig, det: str, hole: int, rail_c: float
) -> tuple[Array, Array, float] | None:
    cur = ref.curve(hole, det)
    if len(cur) < 3:
        return None
    s = smooth(cur.h, cur.net)
    o = float(np.max(s - rail_c))
    if o <= 0:
        return None
    return cur.h, (s - rail_c) / o, o


def _stray(cube: Cube, cfg: HwConfig, stats: dict[str, dict[int, dict[str, Any]]],
           ref: Cube | None) -> list[Finding]:  # fmt: skip
    """With black_cup and a white_ptfe reference: the height-invariant optical part.

    Fit (S - C) = a·g_ref(h) + b, with g_ref the white run's normalised shape; b is
    light that reaches the detector without the sample (it does not change with
    height); stray % = b / O_white."""
    if cube.sample_id != "black_cup":
        return [Finding("optics/stray", "stray light", Status.SKIP,
                        detail="needs a black_cup run (with a white_ptfe reference)")]  # fmt: skip
    if ref is None or ref.sample_id not in ("white_ptfe", "empty"):
        return [Finding("optics/stray", "stray light", Status.SKIP,
                        detail="needs a white_ptfe or empty reference (--reference)")]  # fmt: skip
    from lio.scan.analysis.electrical import coupling

    ref_c, _ = coupling(ref, cfg)
    vals: dict[str, float] = {}
    ratio: dict[str, float] = {}  # black-cup response at the optimum / the reference's
    for det in DETECTORS:
        for hole in _expected(cfg, det, stats[det]):
            ch = cfg.channel(hole)
            r = _ref_shape(ref, cfg, det, hole, float(ref_c[det]["C"].get(ch.rail, 0.0)))
            if r is None:
                continue
            hr, gr, o_ref = r
            s = stats[det][hole]
            h = np.array(s["h"])
            y = np.array(s["net"]) - s["C"]
            g = np.interp(h, hr, gr)
            x = np.stack([g, np.ones_like(g)], axis=1)
            (_, b), *_ = np.linalg.lstsq(x, y, rcond=None)
            vals[f"{det}/h{hole:02d}"] = 100 * float(b) / o_ref
            ratio[f"{det}/h{hole:02d}"] = round(s["O"] / o_ref, 4)
    if not vals:
        return [Finding("optics/stray", "stray light", Status.SKIP, detail="no usable channels")]
    med = float(np.median(list(vals.values())))
    w, f = pair(cfg, "optics.stray_pct")
    rmed = float(np.median(list(ratio.values()))) if ratio else float("nan")
    return [Finding("optics/stray", "stray light (height-invariant optical)", grade(med, w, f),
                    round(med, 2), f"% of {ref.sample_id}",
                    f"median over {len(vals)} channels against {ref.sample_id} "
                    f"({ref.store.run_id}); the black cup keeps {100 * rmed:.1f}% of the "
                    "response at the optimum",
                    f"< {w:g}% (WARN), < {f:g}% (FAIL)",
                    {"per_channel_pct": vals, "black_over_ref": ratio})]  # fmt: skip


def _effectiveness(cube: Cube, cfg: HwConfig, stats: dict[str, dict[int, dict[str, Any]]],
                   ref: Cube | None) -> list[Finding]:  # fmt: skip
    """E = O / O_ref per hole against a reference run of the same sample (a baseline)."""
    if ref is None or ref.sample_id != cube.sample_id:
        return [Finding("optics/effectiveness", "effectiveness vs reference", Status.SKIP,
                        detail="needs a reference (baseline) of the same sample")]  # fmt: skip
    from lio.scan.analysis.electrical import coupling

    ref_c, _ = coupling(ref, cfg)
    out = []
    w, f = pair(cfg, "optics.effectiveness_ratio")
    for det in DETECTORS:
        e: dict[int, float] = {}
        for hole in _expected(cfg, det, stats[det]):
            r = _ref_shape(
                ref, cfg, det, hole, float(ref_c[det]["C"].get(cfg.channel(hole).rail, 0.0))
            )
            if r is not None:
                e[hole] = stats[det][hole]["O"] / r[2]
        if not e:
            continue
        med = float(np.median(list(e.values())))
        worst = min(e, key=lambda h: e[h])
        out.append(Finding(
            f"optics/{det}/effectiveness", f"{det}: response vs reference", grade_low(med, w, f),
            round(med, 3), "x", f"median {med:.2f}; lowest hole {worst}: {e[worst]:.2f}",
            f">= {w:g} (WARN below), >= {f:g} (FAIL below)", {"per_hole": e},
        ))  # fmt: skip
    return out
