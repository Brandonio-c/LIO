"""Turn LIO sweeps into a stored spectral scan (raw readings + per-hole summary)."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Any

from lio.config import HwConfig
from lio.device import Sweep

DETECTORS = ("opt101", "ingaas")


def build_scan(
    cfg: HwConfig,
    sweeps: Sequence[Sweep],
    *,
    target: str,
    kind: str,
    firmware: str,
    settle_ms: int,
    n: int,
    duration_s: float,
    notes: str = "",
) -> dict[str, Any]:
    if not sweeps:
        raise ValueError("no sweeps")
    raw: list[dict[str, Any]] = []
    for sw in sweeps:
        recs = []
        for m in sw.records:
            ch = cfg.channel(m.hole)
            recs.append(
                {
                    "hole": m.hole,
                    "label": ch.label,
                    "nm": ch.wavelength_nm,
                    "dark": {d: m.dark(d) for d in DETECTORS},
                    "lit": {d: m.lit(d) for d in DETECTORS},
                    "net": {d: m.net(d) for d in DETECTORS},
                    "t_on_ms": m.t_on_ms,
                }
            )
        raw.append({"dur_ms": sw.dur_ms, "records": recs})

    spectrum = []
    for ch in cfg.channels:
        per = [r for sw in raw for r in sw["records"] if r["hole"] == ch.hole]
        row: dict[str, Any] = {
            "hole": ch.hole,
            "label": ch.label,
            "nm": ch.wavelength_nm,
            "rail": ch.rail,
            "fitted": ch.fitted,
            "expected": list(ch.expected_detectors),
            "n_sweeps": len(per),
        }
        for d in DETECTORS:
            nets = [r["net"][d] for r in per]
            darks = [r["dark"][d] for r in per]
            row[d] = {
                "net": round(statistics.fmean(nets), 2) if nets else None,
                "sd": round(statistics.stdev(nets), 2) if len(nets) > 1 else 0.0,
                "dark": round(statistics.fmean(darks), 2) if darks else None,
                "saturation": cfg.detectors[d].saturation_counts,
            }
        spectrum.append(row)
    spectrum.sort(key=lambda r: (r["nm"], r["hole"]))
    return {
        "target": target,
        "kind": kind,
        "firmware": firmware,
        "config_sha256": cfg.sha256,
        "settle_ms": settle_ms,
        "n": n,
        "repeats": len(sweeps),
        "lsb_mv": cfg.lsb_mv,
        "duration_s": round(duration_s, 2),
        "notes": notes,
        "spectrum": spectrum,
        "sweeps": raw,
    }
