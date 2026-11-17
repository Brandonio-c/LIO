"""System functionality matrix and verdict (plan §6.5).

Every subsystem gets a health (OK / WATCH / ACT) with its dominant reason. The
verdict reuses the T11 rules (lio.results.overall_verdict) unchanged: the findings
are grouped into the catalogue modules they test (T02 link, T03 ADC, T04 shift
registers, T05 channels and rails, T06 detectors, T09 motion, T10 safety, T13 the
optical path and the run), so a critical-module failure, a failure not tied to a
channel, or too many failing channels give NOT FUNCTIONAL exactly as in the suite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from lio.config import HwConfig
from lio.results import Status, SubResult, TestResult, overall_verdict
from lio.scan.analysis.data import DETECTORS, Cube, Finding, pair

HOLE_RE = re.compile(r"/h\d\d/")


@dataclass(frozen=True)
class Subsystem:
    key: str
    title: str
    parts: str


SUBSYSTEMS = (
    Subsystem("link", "Link / firmware", "Nano R4, USB, firmware"),
    Subsystem("adc", "ADC / I²C", "ADS1115, software I²C D11/D12"),
    Subsystem("shift_registers", "Shift registers", "U1, U2"),
    Subsystem("drivers", "LED drivers / rails", "DRV1 (RAIL A), DRV2 (RAIL B)"),
    Subsystem("channels", "LED / MOSFET channels", "LED1-16, Q1-16"),
    Subsystem("opt101", "OPT101", "OPT101 (A1)"),
    Subsystem("ingaas", "InGaAs TIA", "D1, U5, Rf, Cf (A0)"),
    Subsystem("motors", "Motors / lead screws", "M1, M2, ULN2003, couplers, M6 rods"),
    Subsystem("stage", "Stage tracking", "lio.stage, soft limits"),
    Subsystem("safety", "Safety", "interlocks, duty budget"),
    Subsystem("power", "Power / earthing", "supplies, GND, earth bond"),
    Subsystem("optical_path", "Optical path / ambient", "window, shroud, lid, sample"),
    Subsystem("run", "Run", "the scan itself"),
)


def subsystem_of(fid: str) -> str:
    if fid.startswith("system/link"):
        return "link"
    if fid.startswith("system/adc"):
        return "adc"
    if fid.startswith("system/addressing"):
        return "shift_registers"
    if fid.startswith(("system/rail", "elec/coupling_states")) or fid.endswith("/ce_only"):
        return "drivers"
    if HOLE_RE.search(fid + "/"):
        return "channels"
    if fid.endswith(("/hum", "/ground_shift")) or fid.startswith("elec/rails"):
        return "power"
    for det in DETECTORS:
        if fid.startswith((f"elec/{det}/", f"optics/{det}/")):
            return det
    if fid.startswith("mech/"):
        return "motors"
    if fid.startswith("system/stage"):
        return "stage"
    if fid.startswith(("system/interlocks", "system/duty")):
        return "safety"
    if fid.startswith(("ambient/", "optics/", "trend/")):
        return "optical_path"
    return "run"


MODULE_OF = {
    "link": "T02", "adc": "T03", "shift_registers": "T04", "drivers": "T05", "channels": "T05",
    "opt101": "T06", "ingaas": "T06", "power": "T06", "motors": "T09", "stage": "T09",
    "safety": "T10", "optical_path": "T13", "run": "T13",
}  # fmt: skip


def _aborts(cube: Cube) -> list[str]:
    return [str(a.get("reason", "")) for a in cube.meta.get("aborts") or []]


def findings(cube: Cube, cfg: HwConfig, optics_ctx: dict[str, Any]) -> list[Finding]:
    """The system-level findings that come from the run record, not from a metric."""
    out = []
    ab = _aborts(cube)
    h = cube.meta.get("health") or {}
    boots = max(int(h.get("unexpected_boots", 0)), int(any("BOOT" in a for a in ab)))
    lost = [a for a in ab if a.startswith("lost contact")]
    out.append(Finding(
        "system/link", "link and firmware (no unexpected reset, no lost replies)",
        Status.FAIL if boots or lost else Status.PASS, float(boots), "unexpected boots",
        "; ".join(ab) if (boots or lost) else
        f"firmware {(cube.meta.get('firmware') or {}).get('fw', '?')}, no unexpected # BOOT",
    ))  # fmt: skip
    drop = [a for a in ab if a.startswith("ADC dropout")]
    out.append(Finding(
        "system/adc", "ADC / I²C (every reading answered)", Status.FAIL if drop else Status.PASS,
        float(cube.n), "readings", drop[0] if drop else f"{cube.n} readings, no dropout",
    ))  # fmt: skip
    out += _addressing(cfg, optics_ctx)
    out += _rails(cfg, optics_ctx)
    il = cube.meta.get("interlocks") or {}
    if il:
        bad = {k: v for k, v in il.items() if str(v).startswith("FAIL")}
        out.append(Finding("system/interlocks", "P4 interlock re-checks",
                           Status.FAIL if bad else Status.PASS, float(len(bad)), "failed",
                           "; ".join(f"{k}: {v}" for k, v in il.items())))  # fmt: skip
    else:
        out.append(Finding("system/interlocks", "P4 interlock re-checks", Status.SKIP,
                           detail="P4 not reached"))  # fmt: skip
    duty = h.get("duty")
    if duty:
        over = duty.get("over_budget") or []
        hi = float(duty.get("max_rail_a_ms_per_min", 0.0))
        budget = float(duty.get("budget_a_ms", 1000.0))
        st = Status.FAIL if over or hi > budget * 1.001 else Status.PASS
        out.append(Finding(
            "system/duty", "LED duty (RAIL A <= budget per LED per minute)", st, hi, "ms/min",
            f"max {hi:.0f} ms of {budget:.0f} ms; {duty.get('cooldowns', 0)} cool-down waits, "
            f"{duty.get('cooldown_s', 0)} s in all" + (f"; over budget: {over}" if over else ""),
        ))  # fmt: skip
    else:
        out.append(Finding("system/duty", "LED duty", Status.SKIP, detail="no duty record"))
    stage = h.get("stage_end") or {}
    limit = [a for a in ab if a.startswith("stage / soft limit")]
    if stage or limit:
        bad_pos = stage.get("valid") is False
        out.append(Finding(
            "system/stage", "stage tracking (position trusted, soft limits respected)",
            Status.FAIL if bad_pos or limit else Status.PASS, None, "",
            ("position not trusted: " + str(stage.get("invalid_reason")) if bad_pos else
             limit[0] if limit else f"position {stage.get('abs')}, limits respected"),
        ))  # fmt: skip
    status = str(cube.meta.get("status"))
    out.append(Finding(
        "system/run", "run complete", Status.PASS if status == "COMPLETE" else Status.WARN,
        None, "", status + ("" if status == "COMPLETE" else ": " + "; ".join(ab)),
    ))  # fmt: skip
    return out


def _addressing(cfg: HwConfig, octx: dict[str, Any]) -> list[Finding]:
    """Each hole addressable and isolated. A stuck or doubled select lights the same LED
    for two holes: their whole response, every height on both detectors, then agrees
    within noise. Two different LEDs never do (the height shapes differ slightly)."""
    ch = octx.get("channels") or {}
    _, f_sig = pair(cfg, "optics.min_signal_counts")
    tol = float(cfg.section.raw("scan.health.addressing_match_frac"))
    sig: dict[int, list[list[float]]] = {}
    for hole in range(1, 17):
        curves = [list(ch.get(d, {}).get(hole, {}).get("net", [])) for d in DETECTORS]
        o = [float(ch.get(d, {}).get(hole, {}).get("O", 0.0)) for d in DETECTORS]
        if max(o) >= f_sig and all(curves):
            sig[hole] = curves
    if not sig:
        return [Finding("system/addressing", "addressing (each hole distinct)", Status.SKIP,
                        detail="no optical response to compare")]  # fmt: skip

    def same(a: list[list[float]], b: list[list[float]]) -> bool:
        for ca, cb in zip(a, b, strict=True):
            if len(ca) != len(cb):
                return False
            for x, y in zip(ca, cb, strict=True):
                if abs(x - y) > tol * max(abs(x), abs(y), f_sig):
                    return False
        return True

    holes = sorted(sig)
    dup = [(a, b) for i, a in enumerate(holes) for b in holes[i + 1 :] if same(sig[a], sig[b])]
    return [Finding(
        "system/addressing", "addressing (each hole lights its own LED)",
        Status.WARN if dup else Status.PASS, float(len(dup)), "pairs",
        (f"identical responses at every height: {dup} (stuck or doubled select?)" if dup
         else f"{len(sig)} responding holes, all distinct"),
    )]  # fmt: skip


def _rails(cfg: HwConfig, octx: dict[str, Any]) -> list[Finding]:
    ch = octx.get("channels") or {}
    if not any(ch.values()):
        return []
    _, f_sig = pair(cfg, "optics.min_signal_counts")
    out = []
    for rail in ("A", "B"):
        holes = [h for h in range(1, 17) if cfg.channel(h).rail == rail and cfg.channel(h).fitted]
        live = [h for h in holes
                if any(ch.get(d, {}).get(h, {}).get("O", 0.0) >= f_sig
                       for d in cfg.channel(h).expected_detectors)]  # fmt: skip
        out.append(Finding(
            f"system/rail/{rail}", f"RAIL {rail} (driver gates the LEDs)",
            Status.FAIL if holes and not live else Status.PASS, float(len(live)), "holes",
            f"{len(live)}/{len(holes)} holes respond" + ("" if live else ": rail dead?"),
        ))  # fmt: skip
    return out


def health_table(all_findings: list[Finding]) -> list[dict[str, Any]]:
    by: dict[str, list[Finding]] = {s.key: [] for s in SUBSYSTEMS}
    for f in all_findings:
        by[subsystem_of(f.id)].append(f)
    rows = []
    for s in SUBSYSTEMS:
        fs = by[s.key]
        judged = [f for f in fs if f.status != Status.SKIP]
        worst = max(judged, key=lambda f: f.status.rank, default=None)
        if worst is None:
            health, reason = "n/a", "not measured: " + "; ".join({f.detail for f in fs})[:200]
        elif worst.status.rank >= Status.FAIL.rank:
            health, reason = "ACT", f"{worst.id}: {worst.detail}"
        elif worst.status == Status.WARN:
            health, reason = "WATCH", f"{worst.id}: {worst.detail}"
        else:
            health, reason = "OK", f"{len(judged)} checks pass"
        rows.append({"key": s.key, "title": s.title, "parts": s.parts, "health": health,
                     "reason": reason, "findings": [f.id for f in fs]})  # fmt: skip
    return rows


def verdict(cfg: HwConfig, all_findings: list[Finding]) -> dict[str, Any]:
    by: dict[str, list[Finding]] = {}
    for f in all_findings:
        by.setdefault(MODULE_OF[subsystem_of(f.id)], []).append(f)
    results = []
    for module, fs in sorted(by.items()):
        r = TestResult(id=f"T13.{module}", name=f"scan: {module}", module=module, kind="A")
        r.subs = [SubResult(f.id, f.title, f.status, f.detail) for f in fs]
        judged = [f.status for f in fs if f.status != Status.SKIP]
        r.status = max(judged, key=lambda s: s.rank) if judged else Status.SKIP
        results.append(r)
    v = cfg.thresholds.mapping("verdict")
    ov = overall_verdict(results, max_channel_fails=int(v["max_channel_fails"]),
                         limited_holes=tuple(int(h) for h in v["limited_holes"]))  # fmt: skip
    return {"verdict": ov.verdict.value, "reasons": ov.reasons,
            "modules": {r.module: r.status.value for r in results}}  # fmt: skip


def count_flags(fs: list[Finding]) -> dict[str, int]:
    out = {s.value: 0 for s in Status}
    for f in fs:
        out[f.status.value] += 1
    return out


__all__ = ["SUBSYSTEMS", "count_flags", "findings", "health_table", "verdict"]
