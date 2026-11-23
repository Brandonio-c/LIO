"""Single calibration resolver for ADC counts ↔ volts ↔ equivalent current.

Replaces global MV_PER_COUNT assumptions in new acquisition/analysis paths.
Historical gain-1 LSB of 0.125 mV/count is preserved when justified; unknown LSB
disables physical units rather than inventing 0.125. Do not invent Rf=2 MΩ for
historical records.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lio.config import HwConfig
from lio.scan.provenance import ProvenanceState, RfProvenance

# Documented gain-1 legacy LSB (ADS1115 GAIN_ONE). Prefer CalibrationResolver;
# this constant remains for gain-1-only historical arithmetic when justified.
LEGACY_GAIN1_LSB_MV = 0.125


@dataclass(frozen=True)
class CalibrationResolver:
    """Resolved acquisition calibration for one detector reading context."""

    gain: str | None
    lsb_mv: float | None
    rf: RfProvenance
    calibration_id: str
    justified_legacy_gain1: bool = False

    @property
    def volts_supported(self) -> bool:
        return self.lsb_mv is not None and self.lsb_mv > 0

    @property
    def current_supported(self) -> bool:
        return (
            self.volts_supported
            and self.rf.value_ohm is not None
            and self.rf.value_ohm > 0
            and self.rf.state not in ("unknown", "conflicting")
        )

    def counts_to_mv(self, counts: float) -> float | None:
        if not self.volts_supported or self.lsb_mv is None:
            return None
        return float(counts) * float(self.lsb_mv)

    def mv_to_eq_current_na(self, mv: float) -> float | None:
        """ADC-referred mV → equivalent input current (nA) using Rf provenance.

        Sign convention matches electrical.dark_offset: i_na = -mv * 1e-3 / Rf * 1e9.
        """
        if not self.current_supported or self.rf.value_ohm is None:
            return None
        return -float(mv) * 1e-3 / float(self.rf.value_ohm) * 1e9

    def counts_to_eq_current_na(self, counts: float) -> float | None:
        mv = self.counts_to_mv(counts)
        if mv is None:
            return None
        return self.mv_to_eq_current_na(mv)


def _lsb_for_gain(cfg: HwConfig | None, gain: str | None) -> float | None:
    if gain is None:
        return None
    if cfg is not None:
        table = cfg.data.get("adc", {}).get("lsb_mv") or {}
        if str(gain) in table:
            return float(table[str(gain)])
    # Justified gain-1 legacy only.
    if str(gain) == "1":
        return LEGACY_GAIN1_LSB_MV
    return None


def _rf_from_cfg(cfg: HwConfig | None, detector: str) -> RfProvenance:
    if cfg is None:
        return RfProvenance(None, "unknown", "no config")
    try:
        raw = cfg.section.raw(f"detectors.{detector}.rf_ohm")
    except Exception:
        return RfProvenance(None, "unknown", "rf_ohm missing")
    if raw is None:
        return RfProvenance(None, "unknown", "rf_ohm missing")
    try:
        return RfProvenance(float(raw), "declared", "config detectors.*.rf_ohm")
    except (TypeError, ValueError):
        return RfProvenance(None, "conflicting", f"unreadable rf_ohm={raw!r}")


def resolve_calibration(
    *,
    gain: str | int | float | None = None,
    lsb_mv: float | None = None,
    detector: str = "ingaas",
    cfg: HwConfig | None = None,
    rf: RfProvenance | None = None,
    rf_ohm: float | None = None,
    rf_state: ProvenanceState | None = None,
    calibration_id: str | None = None,
    allow_legacy_gain1: bool = True,
) -> CalibrationResolver:
    """Resolve LSB/Rf for physical-unit conversion.

    - Explicit ``lsb_mv`` wins.
    - Else look up gain in config (or justified gain-1 legacy 0.125).
    - Unknown LSB → volts/current disabled.
    - Rf: explicit provenance preferred; else declared from config; never invent 2 MΩ.
    """
    g = None if gain is None else str(gain)
    justified = False
    resolved_lsb = lsb_mv
    if resolved_lsb is None:
        resolved_lsb = _lsb_for_gain(cfg, g)
        if (
            resolved_lsb is not None
            and g == "1"
            and (cfg is None or str(g) not in (cfg.data.get("adc", {}).get("lsb_mv") or {}))
        ):
            justified = allow_legacy_gain1
        elif resolved_lsb is not None and g == "1" and allow_legacy_gain1:
            # Config agrees with legacy gain-1 constant.
            justified = abs(float(resolved_lsb) - LEGACY_GAIN1_LSB_MV) < 1e-12
    if resolved_lsb is None and g is None and cfg is not None:
        try:
            resolved_lsb = float(cfg.lsb_mv)
            g = str(cfg.data.get("adc", {}).get("gain", ""))
            justified = allow_legacy_gain1 and g == "1"
        except Exception:
            resolved_lsb = None

    if rf is not None:
        rf_p = rf
    elif rf_ohm is not None:
        rf_p = RfProvenance(float(rf_ohm), rf_state or "declared", "explicit")
    else:
        rf_p = _rf_from_cfg(cfg, detector)

    cid = calibration_id or (
        f"gain={g or 'unknown'}:lsb={resolved_lsb if resolved_lsb is not None else 'unknown'}"
        f":rf={rf_p.value_ohm if rf_p.value_ohm is not None else 'unknown'}:{rf_p.state}"
        f":det={detector}"
    )
    return CalibrationResolver(
        gain=g,
        lsb_mv=resolved_lsb,
        rf=rf_p,
        calibration_id=cid,
        justified_legacy_gain1=justified,
    )


def calibration_from_meta(
    meta: dict[str, Any],
    *,
    detector: str = "ingaas",
    cfg: HwConfig | None = None,
) -> CalibrationResolver:
    """Build a resolver from a run's scan.json (or acquisition snapshot) fields."""
    snap = meta.get("acquisition_snapshot") or meta.get("provenance") or {}
    adc = snap.get("adc") or meta.get("adc") or {}
    gain = adc.get("gain")
    if gain is None:
        gain = (meta.get("adc") or {}).get("gain")
    lsb = adc.get("lsb_mv")
    rf_map = snap.get("rf") or {}
    rf_raw = rf_map.get(detector)
    rf: RfProvenance | None = None
    if isinstance(rf_raw, dict):
        rf = RfProvenance(
            float(rf_raw["value_ohm"]) if rf_raw.get("value_ohm") is not None else None,
            str(rf_raw.get("state") or "unknown"),
            str(rf_raw.get("note") or ""),
        )
    return resolve_calibration(gain=gain, lsb_mv=lsb, detector=detector, cfg=cfg, rf=rf)


def counts_to_mv(counts: float, cal: CalibrationResolver) -> float | None:
    return cal.counts_to_mv(counts)


def mv_to_eq_current_na(mv: float, cal: CalibrationResolver) -> float | None:
    return cal.mv_to_eq_current_na(mv)
