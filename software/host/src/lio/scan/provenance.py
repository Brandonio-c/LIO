"""Immutable acquisition provenance, terminal source seals, and quantity eligibility.

M0 of the sensor-readings upgrade (docs/SENSOR_READINGS_UPGRADE_PLAN.md §4).
An initial acquisition snapshot freezes facts before the first reading. A terminal
source seal hashes the frozen manifest plus actual raw bytes after acquisition
ends (kept separate to avoid self-referential hashing). Analysis identity and a
shared validity resolver gate quantitative reuse without rewriting historical files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ESTIMATOR_VERSION = "m3-fixed-n-block-1"
COUPLING_MODEL_VERSION = "m2-coupling-1"

ProvenanceState = str  # measured | declared | inferred | conflicting | unknown
InputRangeEvidence = str  # unverified | verified-in-range | observed-outside-range


class ValidityReason(str, Enum):
    VERIFIED = "verified"
    LEGACY_UNVERIFIED = "legacy-unverified"
    SOURCE_CHANGED = "source-changed"
    CALIBRATION_INCOMPATIBLE = "calibration-incompatible"
    UNREADABLE = "unreadable"


class Quantity(str, Enum):
    COUNTS = "counts"
    VOLTS = "volts"
    EQ_CURRENT = "eq_current"
    MATCHED_RATIO = "matched_ratio"
    PRIMARY_CHEMISTRY = "primary_chemistry"


def _canon(obj: Any) -> bytes:
    """Canonical JSON bytes for hashing (sorted keys, finite numbers only)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_hash(obj: Any) -> str:
    return hashlib.sha256(_canon(obj)).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class RfProvenance:
    value_ohm: float | None
    state: ProvenanceState = "unknown"
    note: str = ""


@dataclass(frozen=True)
class CurrentProvenance:
    value_ma: float | None
    state: ProvenanceState = "unknown"
    note: str = ""


@dataclass(frozen=True)
class AdcProvenance:
    gain: str | None
    fsr_v: float | None
    lsb_mv: float | None
    mux_map: dict[str, Any] = field(default_factory=dict)
    configured_rate_sps: float | None = None
    effective_mode: str | None = None  # e.g. mains | ordinary
    mains_hz: float | None = None
    mains_periods: int | None = None
    settle_ms: float | None = None
    detector_order: tuple[str, ...] = ()


@dataclass(frozen=True)
class AcquisitionSnapshot:
    """Immutable facts frozen after preflight, before the first reading."""

    schema_version: int
    protocol_hash: str
    acquisition_version: str
    processing_version: str
    simulated: bool
    rig_identity: str
    config_snapshot: dict[str, Any]
    config_sha256: str
    channel_map_snapshot: dict[str, Any]
    channel_map_sha256: str
    adc: AdcProvenance
    rf: dict[str, RfProvenance]  # detector -> Rf
    rail_current: dict[str, CurrentProvenance]  # rail -> current
    assembly: dict[str, Any] = field(default_factory=dict)
    planned: dict[str, Any] = field(default_factory=dict)
    input_range: dict[str, InputRangeEvidence] = field(default_factory=dict)
    # detector -> unverified | verified-in-range | observed-outside-range

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["adc"]["detector_order"] = list(self.adc.detector_order)
        return d

    def manifest_hash(self) -> str:
        return content_hash(self.to_dict())


def build_acquisition_snapshot(
    *,
    protocol_hash: str,
    config_snapshot: dict[str, Any],
    config_sha256: str,
    channel_map_snapshot: dict[str, Any],
    adc: AdcProvenance,
    rf: dict[str, RfProvenance] | None = None,
    rail_current: dict[str, CurrentProvenance] | None = None,
    simulated: bool = False,
    rig_identity: str = "unknown",
    acquisition_version: str = "m0",
    processing_version: str = "m0",
    assembly: dict[str, Any] | None = None,
    planned: dict[str, Any] | None = None,
    input_range: dict[str, InputRangeEvidence] | None = None,
) -> AcquisitionSnapshot:
    cmap = dict(channel_map_snapshot)
    return AcquisitionSnapshot(
        schema_version=SCHEMA_VERSION,
        protocol_hash=protocol_hash,
        acquisition_version=acquisition_version,
        processing_version=processing_version,
        simulated=simulated,
        rig_identity=rig_identity,
        config_snapshot=config_snapshot,
        config_sha256=config_sha256,
        channel_map_snapshot=cmap,
        channel_map_sha256=content_hash(cmap),
        adc=adc,
        rf=dict(rf or {}),
        rail_current=dict(rail_current or {}),
        assembly=dict(assembly or {}),
        planned=dict(planned or {}),
        input_range=dict(input_range or {}),
    )


@dataclass(frozen=True)
class TerminalSourceSeal:
    """Hash of frozen manifest + actual raw/terminal metadata bytes (post-acquisition)."""

    manifest_hash: str
    raw_sha256: str
    terminal_meta_sha256: str
    combined_sha256: str
    revision: str = "complete"
    status: str = "COMPLETE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def seal_terminal_source(
    snapshot: AcquisitionSnapshot,
    *,
    raw_bytes: bytes,
    terminal_meta: dict[str, Any] | None = None,
    revision: str = "complete",
    status: str = "COMPLETE",
) -> TerminalSourceSeal:
    manifest_hash = snapshot.manifest_hash()
    raw_sha = hashlib.sha256(raw_bytes).hexdigest()
    meta = dict(terminal_meta or {})
    meta_sha = content_hash(meta)
    combined = hashlib.sha256(
        (manifest_hash + raw_sha + meta_sha).encode("ascii")
    ).hexdigest()
    return TerminalSourceSeal(
        manifest_hash=manifest_hash,
        raw_sha256=raw_sha,
        terminal_meta_sha256=meta_sha,
        combined_sha256=combined,
        revision=revision,
        status=status,
    )


@dataclass(frozen=True)
class AnalysisIdentity:
    """Content-addressed identity of a derived analysis product."""

    source_cube_sha256: str
    source_scan_sha256: str
    terminal_seal_sha256: str | None
    calibration_id: str
    channel_map_sha256: str
    estimator_version: str
    coupling_model_version: str
    protocol_hash: str | None = None
    reference_sources: tuple[str, ...] = ()
    numerical_settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["reference_sources"] = list(self.reference_sources)
        return d

    def identity_hash(self) -> str:
        return content_hash(self.to_dict())


def build_analysis_identity(
    *,
    cube_sha256: str,
    scan_sha256: str,
    calibration_id: str,
    channel_map_sha256: str,
    terminal_seal_sha256: str | None = None,
    estimator_version: str = ESTIMATOR_VERSION,
    coupling_model_version: str = COUPLING_MODEL_VERSION,
    protocol_hash: str | None = None,
    reference_sources: tuple[str, ...] | list[str] | None = None,
    numerical_settings: dict[str, Any] | None = None,
) -> AnalysisIdentity:
    return AnalysisIdentity(
        source_cube_sha256=cube_sha256,
        source_scan_sha256=scan_sha256,
        terminal_seal_sha256=terminal_seal_sha256,
        calibration_id=calibration_id,
        channel_map_sha256=channel_map_sha256,
        estimator_version=estimator_version,
        coupling_model_version=coupling_model_version,
        protocol_hash=protocol_hash,
        reference_sources=tuple(reference_sources or ()),
        numerical_settings=dict(numerical_settings or {}),
    )


def resolve_analysis_validity(
    analysis: dict[str, Any] | None,
    *,
    cube_sha256: str,
    scan_sha256: str,
    run_id: str | None = None,
    sample_id: str | None = None,
    expected_calibration_id: str | None = None,
    expected_estimator_version: str | None = None,
) -> tuple[bool, ValidityReason, str]:
    """Shared validity resolver for report/profile readers.

    Returns ``(ok_for_quantitative_reuse, reason, detail)``. Rejected products
    remain inspectable; ``ok`` False means quarantine from quantitative reuse.
    """
    if analysis is None:
        return False, ValidityReason.UNREADABLE, "missing"
    try:
        identity = analysis.get("identity") or analysis.get("provenance") or {}
        if not isinstance(identity, dict):
            identity = {}
        has_source = bool(identity.get("source_cube_sha256") or identity.get("cube_sha256"))
        if not has_source:
            # Weak legacy: run/sample names alone are insufficient for acceptance.
            rid_ok = str(analysis.get("run_id", "")) in ("", run_id or "",)
            sid_ok = str(analysis.get("sample_id", sample_id)) == str(sample_id)
            if rid_ok and sid_ok and (run_id or sample_id):
                return False, ValidityReason.LEGACY_UNVERIFIED, "no source/calibration identity"
            return False, ValidityReason.UNREADABLE, "identity_mismatch"

        stored_cube = str(identity.get("source_cube_sha256") or identity.get("cube_sha256") or "")
        stored_scan = str(identity.get("source_scan_sha256") or identity.get("scan_sha256") or "")
        if stored_cube and stored_cube != cube_sha256:
            return False, ValidityReason.SOURCE_CHANGED, "cube hash mismatch"
        if stored_scan and stored_scan != scan_sha256:
            return False, ValidityReason.SOURCE_CHANGED, "scan hash mismatch"

        cal = str(identity.get("calibration_id") or "")
        if expected_calibration_id is not None and cal and cal != expected_calibration_id:
            return False, ValidityReason.CALIBRATION_INCOMPATIBLE, "calibration_id mismatch"

        est = str(identity.get("estimator_version") or "")
        if expected_estimator_version is not None and est and est != expected_estimator_version:
            return False, ValidityReason.CALIBRATION_INCOMPATIBLE, "estimator_version mismatch"

        return True, ValidityReason.VERIFIED, "ok"
    except (TypeError, ValueError, KeyError) as e:
        return False, ValidityReason.UNREADABLE, f"unreadable:{e}"


@dataclass(frozen=True)
class QuantityEligibility:
    quantity: Quantity
    eligible: bool
    reason: str
    detector: str | None = None


def quantity_eligibility(
    quantity: Quantity,
    *,
    detector: str,
    lsb_mv: float | None,
    rf: RfProvenance | None = None,
    input_range: InputRangeEvidence = "unverified",
    geometry_compatible: bool = False,
    spectral_calibrated: bool = False,
    control_evidence: bool = False,
) -> QuantityEligibility:
    """Per-quantity gates. Unverified A0 blocks InGaAs physical current/optical
    qualification but not raw counts or independently valid OPT101 quantities.
    """
    if quantity is Quantity.COUNTS:
        return QuantityEligibility(quantity, True, "counts require no calibration", detector)

    if quantity is Quantity.VOLTS:
        if lsb_mv is None or not (lsb_mv > 0):
            return QuantityEligibility(
                quantity, False, "unknown LSB disables physical units", detector
            )
        return QuantityEligibility(quantity, True, "supported LSB", detector)

    if quantity is Quantity.EQ_CURRENT:
        if lsb_mv is None or not (lsb_mv > 0):
            return QuantityEligibility(quantity, False, "unknown LSB", detector)
        if rf is None or rf.value_ohm is None or rf.state in ("unknown", "conflicting"):
            return QuantityEligibility(quantity, False, "Rf unsupported or unknown", detector)
        if detector == "ingaas" and input_range != "verified-in-range":
            return QuantityEligibility(
                quantity,
                False,
                f"InGaAs physical current blocked: input_range={input_range}",
                detector,
            )
        if input_range == "observed-outside-range":
            return QuantityEligibility(
                quantity, False, "input observed outside operating range", detector
            )
        return QuantityEligibility(quantity, True, f"Rf {rf.state}", detector)

    if quantity is Quantity.MATCHED_RATIO:
        if not geometry_compatible:
            return QuantityEligibility(
                quantity, False, "geometry/acquisition incompatible", detector
            )
        if not control_evidence:
            return QuantityEligibility(
                quantity, False, "control evidence missing", detector
            )
        if detector == "ingaas" and input_range != "verified-in-range":
            return QuantityEligibility(
                quantity,
                False,
                f"InGaAs optical/reference blocked: input_range={input_range}",
                detector,
            )
        return QuantityEligibility(quantity, True, "compatible matched ratio", detector)

    if quantity is Quantity.PRIMARY_CHEMISTRY:
        if not spectral_calibrated:
            return QuantityEligibility(
                quantity, False, "spectral/optical calibration missing", detector
            )
        if detector == "ingaas" and input_range != "verified-in-range":
            return QuantityEligibility(
                quantity,
                False,
                f"InGaAs primary chemistry blocked: input_range={input_range}",
                detector,
            )
        return QuantityEligibility(quantity, True, "primary chemistry calibrated", detector)

    return QuantityEligibility(quantity, False, "unknown quantity", detector)
