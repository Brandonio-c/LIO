"""Channel roles and explicit coupling models (M2).

Models:
- ``legacy_blind_median``: exact frozen legacy (including current-ratio scaling).
- ``validated_control``: load-preserving controls with estimate/uncertainty.
- ``unidentified``: insufficient evidence — null + reason, never C=0.

H16 is spectrally unassigned: excluded from primary-1850 chemistry and from
guaranteed-blind control defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from lio.config import HwConfig
from lio.scan.analysis import electrical
from lio.scan.analysis.data import DETECTORS, Cube

MODEL_LEGACY = "legacy_blind_median"
MODEL_VALIDATED = "validated_control"
MODEL_UNIDENTIFIED = "unidentified"

# Spectrally unassigned; not a primary-1850 chemistry channel.
H16_SPECTRAL_STATUS = "unassigned"


@dataclass(frozen=True)
class ChannelRole:
    hole: int
    detector: str
    nominal_band: str | None
    primary_eligible: bool
    electrical_control_eligible: bool
    diagnostic_role: str  # primary | control | proxy | none | unassigned
    evidence_source: str = "config.expect"
    calibration_epoch: str | None = None


@dataclass
class CouplingResult:
    model: str
    detector: str
    C: dict[str, float | None]  # rail -> estimate; None when unidentified
    units: str = "counts"
    reason: str | None = None
    inferred: list[str] = field(default_factory=list)
    controls_used: dict[str, list[int]] = field(default_factory=dict)
    covariance: dict[str, Any] = field(default_factory=dict)
    support: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "detector": self.detector,
            "C": self.C,
            "units": self.units,
            "reason": self.reason,
            "inferred": list(self.inferred),
            "controls_used": {k: list(v) for k, v in self.controls_used.items()},
            "covariance": self.covariance,
            "support": self.support,
            "warnings": list(self.warnings),
        }


def channel_role(cfg: HwConfig, hole: int, detector: str) -> ChannelRole:
    """Independent role metadata (expect remains for diagnostic policy only)."""
    ch = cfg.channel(hole)
    expect = ch.expect_for(detector)
    wl = ch.wavelength_nm
    broadband = (ch.label or "").lower() in ("white", "pink")
    if hole == 16:
        return ChannelRole(
            hole=16,
            detector=detector,
            nominal_band="1850_nominal" if wl else None,
            primary_eligible=False,  # OPT101/InGaAs h16 not primary-1850 chemistry
            electrical_control_eligible=False,  # not guaranteed-blind
            diagnostic_role="unassigned",
            evidence_source="plan.m2.h16_unassigned",
        )
    primary = expect in ("signal", "weak") and not broadband
    # Guaranteed-blind defaults exclude h16 and broadband.
    control = expect == "none" and ch.fitted and wl is not None and not broadband and hole != 16
    if detector in cfg.detectors and wl is not None:
        lo, hi = cfg.detectors[detector].range_nm
        if control and lo <= wl <= hi:
            control = False
    proxy = broadband or (hole == 15 and detector == "ingaas")
    role = "primary" if primary else ("control" if control else ("proxy" if proxy else "none"))
    return ChannelRole(
        hole=hole,
        detector=detector,
        nominal_band=None if wl is None else str(int(wl)),
        primary_eligible=primary and hole != 16,
        electrical_control_eligible=control,
        diagnostic_role=role,
    )


def primary_1850_feature_holes(detector: str) -> list[int]:
    """Holes allowed in a primary-1850 chemistry feature namespace.

    H16 is always excluded (spectrally unassigned; OPT101 is not 1850 nm).
    """
    _ = detector
    return []  # no primary-1850 channel on current hardware


def primary_1850_feature_id(detector: str, hole: int, kind: str = "net") -> str | None:
    """Return a primary-1850 feature id, or None if the hole is excluded (e.g. h16)."""
    if hole == 16 or hole not in primary_1850_feature_holes(detector):
        return None
    return f"primary1850:{detector}:h{hole:02d}:{kind}"


def proxy_unassigned_feature_id(detector: str, hole: int, kind: str = "net") -> str:
    """Proxy features use an unassigned proxy namespace, never primary-1850."""
    return f"proxy_unassigned:{detector}:h{hole:02d}:{kind}"


def guaranteed_blind_holes(cfg: HwConfig, detector: str) -> list[int]:
    """Default guaranteed-blind control set: legacy blinds minus h16 and broadband."""
    out = []
    for h in electrical.blind_holes(cfg, detector):
        role = channel_role(cfg, h, detector)
        if role.electrical_control_eligible:
            out.append(h)
        elif h != 16 and (cfg.channel(h).label or "").lower() not in ("white", "pink"):
            # Keep non-broadband expect=none fitted blinds that pass wavelength gate.
            ch = cfg.channel(h)
            wl = ch.wavelength_nm
            if ch.fitted and ch.expect_for(detector) == "none" and wl is not None:
                lo, hi = cfg.detectors[detector].range_nm
                if not lo <= wl <= hi:
                    out.append(h)
    # Explicit h16 exclusion even if somehow listed.
    return [h for h in out if h != 16]


def candidate_control_holes(cfg: HwConfig, detector: str) -> list[int]:
    """Legacy blind pool including broadband/h16 candidates (for sensitivity only)."""
    return list(electrical.blind_holes(cfg, detector))


def legacy_blind_median(cube: Cube, cfg: HwConfig) -> dict[str, CouplingResult]:
    """Exact frozen legacy method, including inferred current-ratio scaling.

    Wraps ``electrical.coupling`` so the legacy path remains callable and bit-
    compatible for reproduction. When no blinds exist, legacy historically set
    C=0; that behaviour is preserved here under ``model=legacy_blind_median``
    with an explicit warning. New analyses should call ``estimate_coupling``.
    """
    ctx, _findings = electrical.coupling(cube, cfg)
    out: dict[str, CouplingResult] = {}
    for det in DETECTORS:
        raw = ctx.get(det) or {}
        c = raw.get("C") or {}
        inferred = list(raw.get("inferred") or [])
        blind = list(raw.get("blind") or electrical.blind_holes(cfg, det))
        # Legacy zero-fill when no blinds (electrical.coupling sets A/B to 0).
        if not c and "C" not in raw:
            c = {"A": 0.0, "B": 0.0}
            inferred = ["A", "B"]
        controls: dict[str, list[int]] = {"A": [], "B": []}
        for h in blind:
            controls[cfg.channel(h).rail].append(h)
        warnings = []
        if inferred:
            warnings.append("legacy inferred current-ratio scaling")
        if all(v == 0.0 for v in c.values()) and inferred == ["A", "B"]:
            warnings.append("legacy zero-fill when no blinds; prefer unidentified model")
        out[det] = CouplingResult(
            model=MODEL_LEGACY,
            detector=det,
            C={k: float(v) for k, v in c.items()},
            inferred=inferred,
            controls_used=controls,
            support={"blind_holes": blind, "legacy": True},
            warnings=warnings,
            reason="legacy_blind_median",
        )
    return out


def _rail_median(cube: Cube, detector: str, holes: list[int]) -> tuple[float | None, int]:
    if not holes:
        return None, 0
    h_arr, _, net = cube.lit_all(detector)
    m = np.isin(h_arr, holes)
    if not m.any():
        return None, 0
    return float(np.median(net[m])), len(holes)


def estimate_coupling(
    cube: Cube,
    cfg: HwConfig,
    *,
    model: str = MODEL_VALIDATED,
    exclude_holes: set[int] | frozenset[int] | None = None,
    allow_current_scaling: bool = False,
) -> dict[str, CouplingResult]:
    """Estimate C per detector/rail under the requested model."""
    if model == MODEL_LEGACY and not exclude_holes:
        return legacy_blind_median(cube, cfg)

    exclude = set(exclude_holes or ())
    out: dict[str, CouplingResult] = {}
    for det in DETECTORS:
        if model == MODEL_LEGACY:
            # Leave-one-out style on the legacy blind pool.
            blinds = [h for h in electrical.blind_holes(cfg, det) if h not in exclude]
        else:
            blinds = [h for h in guaranteed_blind_holes(cfg, det) if h not in exclude]
            # For sensitivity studies on real records, also allow candidate pool
            # when explicitly using legacy membership via exclude on candidates.
            if model == MODEL_VALIDATED and not blinds:
                # Fall through to unidentified rather than inventing C=0.
                pass

        per_rail: dict[str, float | None] = {}
        controls: dict[str, list[int]] = {"A": [], "B": []}
        n_rail: dict[str, int] = {}
        for rail in ("A", "B"):
            hs = [h for h in blinds if cfg.channel(h).rail == rail]
            controls[rail] = hs
            med, n = _rail_median(cube, det, hs)
            n_rail[rail] = n
            if med is not None:
                per_rail[rail] = med

        inferred: list[str] = []
        warnings: list[str] = []

        if model == MODEL_LEGACY and allow_current_scaling is not False:
            # Match electrical.coupling scaling when exactly one rail has blinds.
            measured = {r: v for r, v in per_rail.items() if v is not None}
            if len(measured) == 1:
                (r0, c0), r1 = next(iter(measured.items())), "B" if "A" in measured else "A"
                per_rail[r1] = (
                    float(c0) * electrical.rail_current(cfg, r1) / electrical.rail_current(cfg, r0)
                )
                inferred.append(r1)
                warnings.append("legacy inferred current-ratio scaling")

        if model == MODEL_VALIDATED and allow_current_scaling:
            measured = {r: v for r, v in per_rail.items() if v is not None}
            if len(measured) == 1:
                warnings.append("current scaling requested but currents may be unverified")

        measured = {r: v for r, v in per_rail.items() if v is not None}
        if not measured:
            out[det] = CouplingResult(
                model=MODEL_UNIDENTIFIED,
                detector=det,
                C={"A": None, "B": None},
                reason="no eligible controls measured",
                controls_used=controls,
                warnings=warnings,
            )
            continue

        if model == MODEL_VALIDATED:
            # No silent zero; missing rail stays None (unidentified for that rail).
            c_out: dict[str, float | None] = {"A": per_rail.get("A"), "B": per_rail.get("B")}
            if all(v is None for v in c_out.values()):
                out[det] = CouplingResult(
                    model=MODEL_UNIDENTIFIED,
                    detector=det,
                    C=c_out,
                    reason="no eligible controls measured",
                    controls_used=controls,
                )
            else:
                # If a rail has no controls, mark unidentified for that rail only.
                missing = [r for r, v in c_out.items() if v is None]
                reason = None
                m = MODEL_VALIDATED
                if missing:
                    warnings.append(f"rails unidentified: {missing}")
                out[det] = CouplingResult(
                    model=m,
                    detector=det,
                    C=c_out,
                    reason=reason,
                    inferred=inferred,
                    controls_used=controls,
                    support={"n_rail": n_rail},
                    warnings=warnings,
                    covariance=_control_covariance_stub(cube, det, controls),
                )
            continue

        # Legacy with excludes: optional current-ratio fill (electrical.coupling).
        if allow_current_scaling is not False and len(measured) == 1:
            (r0, c0), r1 = next(iter(measured.items())), "B" if "A" in measured else "A"
            if r1 not in per_rail or per_rail[r1] is None:
                per_rail[r1] = (
                    float(c0) * electrical.rail_current(cfg, r1) / electrical.rail_current(cfg, r0)
                )
                inferred.append(r1)
                warnings.append("legacy inferred current-ratio scaling")
        if not measured and not any(v is not None for v in per_rail.values()):
            out[det] = CouplingResult(
                model=MODEL_UNIDENTIFIED,
                detector=det,
                C={"A": None, "B": None},
                reason="no eligible controls measured",
                controls_used=controls,
                warnings=warnings,
            )
            continue
        # Missing rail without scaling → None (never invent C=0).
        a_c = per_rail.get("A")
        b_c = per_rail.get("B")
        c_legacy: dict[str, float | None] = {
            "A": float(a_c) if a_c is not None else None,
            "B": float(b_c) if b_c is not None else None,
        }
        if all(v is None for v in c_legacy.values()):
            out[det] = CouplingResult(
                model=MODEL_UNIDENTIFIED,
                detector=det,
                C=c_legacy,
                reason="no eligible controls measured",
                controls_used=controls,
                warnings=warnings,
            )
            continue
        out[det] = CouplingResult(
            model=MODEL_LEGACY,
            detector=det,
            C=c_legacy,
            inferred=inferred,
            controls_used=controls,
            warnings=warnings,
            reason="legacy_blind_median",
        )
    return out


def _control_covariance_stub(
    cube: Cube, detector: str, controls: dict[str, list[int]]
) -> dict[str, Any]:
    """Simple within-rail variance of control nets (shared-control awareness)."""
    cov: dict[str, Any] = {}
    h_arr, _, net = cube.lit_all(detector)
    for rail, hs in controls.items():
        if len(hs) < 1:
            continue
        m = np.isin(h_arr, hs)
        if m.sum() < 2:
            cov[rail] = {"var": 0.0, "n": int(m.sum())}
            continue
        cov[rail] = {"var": float(np.var(net[m], ddof=1)), "n": int(m.sum())}
    return cov


def leave_one_control_out(
    cube: Cube, cfg: HwConfig, detector: str, *, rail: str = "B"
) -> dict[str, Any]:
    """Sensitivity: C with full candidate pool vs excluding each candidate.

    Reproduces plan §12 table numbers on real records without calling alternative
    C calibrated. Removing all rail-B candidates (h10/h11/h16 for InGaAs) yields
    unidentified C, never zero.
    """
    candidates = [h for h in candidate_control_holes(cfg, detector) if cfg.channel(h).rail == rail]
    full = estimate_coupling(cube, cfg, model=MODEL_LEGACY)
    c_full = full[detector].C.get(rail)

    per_exclude: dict[str, float | None] = {}
    for h in candidates:
        r = estimate_coupling(cube, cfg, model=MODEL_LEGACY, exclude_holes={h})
        per_exclude[f"exclude_h{h}"] = r[detector].C.get(rail)

    # Remove all broadband + h16 style candidates on that rail.
    # Also: validated with only guaranteed blinds (excludes h16/broadband by default).
    validated = estimate_coupling(cube, cfg, model=MODEL_VALIDATED)

    # Explicit: exclude h10,h11,h16 from legacy pool → unidentified for rail B InGaAs.
    no_bb = estimate_coupling(
        cube, cfg, model=MODEL_LEGACY, exclude_holes={10, 11, 16}, allow_current_scaling=False
    )
    # Force unidentified when no rail controls remain (override legacy scaling).
    blinds_left = [
        h
        for h in electrical.blind_holes(cfg, detector)
        if h not in {10, 11, 16} and cfg.channel(h).rail == rail
    ]
    if not blinds_left:
        c_no_bb: float | None = None
        model_no_bb = MODEL_UNIDENTIFIED
    else:
        c_no_bb = no_bb[detector].C.get(rail)
        model_no_bb = no_bb[detector].model

    return {
        "detector": detector,
        "rail": rail,
        "C_full": c_full,
        "exclude_h16": per_exclude.get("exclude_h16"),
        "per_exclude": per_exclude,
        "exclude_h10_h11_h16": c_no_bb,
        "exclude_h10_h11_h16_model": model_no_bb,
        "validated_C": validated[detector].C.get(rail),
        "validated_model": validated[detector].model,
        "never_zero_when_unidentified": c_no_bb is None,
        "candidates": candidates,
        "note": "sensitivity only; alternative C is not calibrated",
    }


def optical_amplitude(S: float, coupling: CouplingResult, rail: str) -> tuple[float | None, str]:
    """O = S - C when C is identified; else unavailable (never assume C=0)."""
    c = coupling.C.get(rail)
    if coupling.model == MODEL_UNIDENTIFIED or c is None:
        return None, "coupling_unidentified"
    return float(S) - float(c), "ok"
