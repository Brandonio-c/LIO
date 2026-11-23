"""Immutable acquisition provenance, terminal source seals, and quantity eligibility.

M0 of the sensor-readings upgrade (docs/SENSOR_READINGS_UPGRADE_PLAN.md §4).
An initial acquisition snapshot freezes facts before the first reading. A terminal
source seal hashes the frozen manifest plus actual raw bytes after acquisition
ends (kept separate to avoid self-referential hashing). Analysis identity and a
shared validity resolver gate quantitative reuse without rewriting historical files.
"""

from __future__ import annotations

import contextlib
import copy
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

    def __post_init__(self) -> None:
        # Defensive freeze (A12 / M0): deep-copy every nested container so the
        # caller's dicts can change afterwards without touching these facts, and
        # keep the canonical bytes so to_dict()/manifest_hash() never drift.
        for name in ("config_snapshot", "channel_map_snapshot", "assembly", "planned",
                     "input_range", "rf", "rail_current"):  # fmt: skip
            object.__setattr__(self, name, copy.deepcopy(getattr(self, name)))
        d = asdict(self)
        d["adc"]["detector_order"] = list(self.adc.detector_order)
        object.__setattr__(self, "_frozen", _canon(d))

    def to_dict(self) -> dict[str, Any]:
        frozen: bytes = object.__getattribute__(self, "_frozen")
        out: dict[str, Any] = json.loads(frozen)
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AcquisitionSnapshot:
        adc_raw = dict(data.get("adc") or {})
        order = adc_raw.get("detector_order") or ()
        adc = AdcProvenance(
            gain=adc_raw.get("gain"),
            fsr_v=adc_raw.get("fsr_v"),
            lsb_mv=adc_raw.get("lsb_mv"),
            mux_map=dict(adc_raw.get("mux_map") or {}),
            configured_rate_sps=adc_raw.get("configured_rate_sps"),
            effective_mode=adc_raw.get("effective_mode"),
            mains_hz=adc_raw.get("mains_hz"),
            mains_periods=adc_raw.get("mains_periods"),
            settle_ms=adc_raw.get("settle_ms"),
            detector_order=tuple(order),
        )
        rf = {
            k: RfProvenance(
                v.get("value_ohm") if isinstance(v, dict) else None,
                str(v.get("state", "unknown")) if isinstance(v, dict) else "unknown",
                str(v.get("note", "")) if isinstance(v, dict) else "",
            )
            for k, v in dict(data.get("rf") or {}).items()
        }
        rail = {
            k: CurrentProvenance(
                v.get("value_ma") if isinstance(v, dict) else None,
                str(v.get("state", "unknown")) if isinstance(v, dict) else "unknown",
                str(v.get("note", "")) if isinstance(v, dict) else "",
            )
            for k, v in dict(data.get("rail_current") or {}).items()
        }
        return cls(
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            protocol_hash=str(data.get("protocol_hash", "")),
            acquisition_version=str(data.get("acquisition_version", "m0")),
            processing_version=str(data.get("processing_version", "m0")),
            simulated=bool(data.get("simulated", False)),
            rig_identity=str(data.get("rig_identity", "unknown")),
            config_snapshot=dict(data.get("config_snapshot") or {}),
            config_sha256=str(data.get("config_sha256", "")),
            channel_map_snapshot=dict(data.get("channel_map_snapshot") or {}),
            channel_map_sha256=str(data.get("channel_map_sha256", "")),
            adc=adc,
            rf=rf,
            rail_current=rail,
            assembly=dict(data.get("assembly") or {}),
            planned=dict(data.get("planned") or {}),
            input_range=dict(data.get("input_range") or {}),
        )

    def manifest_hash(self) -> str:
        frozen: bytes = object.__getattribute__(self, "_frozen")
        return hashlib.sha256(frozen).hexdigest()


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


class CorePreflightError(ValueError):
    """The device's ADC state is not the approved core acquisition profile."""


def core_adc_preflight(device: Any, *, mains_hz: int) -> dict[str, Any]:
    """Core profile on START and RESUME, before any light (D06 / A18).

    Gain must READ BACK as 1 (GAIN_ONE) whatever an old snapshot says; a gain-2
    device matching a gain-2 snapshot is still refused (M7 stays isolated).
    With mains integration requested, it is applied and INFO must report the
    same value; a missing field is never filled from the host cache.
    """
    info = device.info(refresh=True)
    gain = read_info_gain(info)
    if gain is None or str(gain) not in ("1", "GAIN_ONE", "1.0"):
        raise CorePreflightError(
            f"core acquisition requires ADC gain 1; device reports {gain!r} (refusing before light)"
        )
    try:
        rate = int(info.as_int("rate"))
    except Exception as e:
        raise CorePreflightError(f"ADC rate readback unavailable ({e})") from e
    applied = 0
    if mains_hz > 0:
        device.adc_mains(int(mains_hz))
        info = device.info(refresh=True)
        if "mains" not in info.values:
            raise CorePreflightError("ADC mains readback missing after ADC CFG MAINS")
        applied = int(info.as_int("mains"))
        if applied != int(mains_hz):
            raise CorePreflightError(f"ADC mains readback {applied} != requested {mains_hz}")
    return {"gain": "1", "rate_sps": rate, "mains_hz": applied, "source": "INFO readback"}


def read_info_gain(info: Any) -> str | None:
    """INFO field is ``gain`` (not ``adc_gain``). Missing gain is not gain 1 (D06)."""
    if info is None:
        return None
    values = getattr(info, "values", None)
    if isinstance(values, dict):
        if "gain" in values and values["gain"] not in (None, ""):
            return str(values["gain"])
        # adc_gain is not a real INFO field — ignore if present.
        return None
    if hasattr(info, "as_str"):
        try:
            if "gain" in info:
                return str(info.as_str("gain"))
        except Exception:
            return None
    return None


def snapshot_from_hw_config(
    cfg: Any,
    *,
    protocol_hash: str,
    planned: dict[str, Any] | None = None,
    simulated: bool = False,
    rig_identity: str = "unknown",
    gain: str | None = "1",
    detectors: tuple[str, ...] = ("opt101", "ingaas"),
    mains_periods: int | None = None,
    mains_hz: float | None = None,
    settle_ms: float | None = None,
    assembly: dict[str, Any] | None = None,
    acquisition_version: str = "m0-height-scan",
    input_range: dict[str, InputRangeEvidence] | None = None,
) -> AcquisitionSnapshot:
    """Build an initial snapshot from ``HwConfig`` for height-scan or protocol runs.

    Historical Nov23 (and earlier) runs are left untouched; only NEW runs that call
    this helper receive ``acquisition_snapshot`` / terminal seal fields.

    Applied mains/gain must be passed from acknowledged device facts — do not
    invent 60 Hz when the plan only supplies a period count (D06).
    """
    rf: dict[str, RfProvenance] = {}
    for d in detectors:
        try:
            raw_rf = cfg.section.raw(f"detectors.{d}.rf_ohm")
            rf[d] = RfProvenance(float(raw_rf), "declared", "config")
        except Exception:
            rf[d] = RfProvenance(None, "unknown", "rf_ohm missing")
    holes: list[int] = []
    try:
        holes = [int(ch.hole) for ch in cfg.channels]
    except Exception:
        holes = list(range(1, 17))
    gain_s = None if gain is None else str(gain)
    if mains_hz is not None and float(mains_hz) > 0:
        effective_mode = "mains"
        recorded_hz: float | None = float(mains_hz)
    elif mains_periods:
        # Periods requested but applied Hz unknown — do not invent 60.
        effective_mode = "mains_requested_hz_unknown"
        recorded_hz = None
    else:
        effective_mode = "ordinary"
        recorded_hz = None
    return build_acquisition_snapshot(
        protocol_hash=protocol_hash,
        config_snapshot={"sha256": cfg.sha256, "path": str(getattr(cfg, "path", ""))},
        config_sha256=cfg.sha256,
        channel_map_snapshot={"source": "config", "holes": holes},
        adc=AdcProvenance(
            gain=gain_s,
            fsr_v=4.096 if gain_s in ("1", "GAIN_ONE") else None,
            lsb_mv=0.125 if gain_s in ("1", "GAIN_ONE") else None,
            effective_mode=effective_mode,
            mains_hz=recorded_hz,
            mains_periods=mains_periods,
            settle_ms=settle_ms,
            detector_order=detectors,
        ),
        rf=rf,
        simulated=simulated,
        rig_identity=rig_identity,
        planned=dict(planned or {}),
        input_range=dict(input_range)
        if input_range is not None
        else {d: "unverified" for d in detectors},
        assembly=dict(assembly or {}),
        acquisition_version=acquisition_version,
    )


def collect_raw_artifact_bytes(folder: Path | str) -> bytes:
    """Concatenate cube + every streams/*.npz (+ sidecars) in stable path order (D10)."""
    root = Path(folder)
    parts: list[bytes] = []
    cube = root / "cube.csv.gz"
    if cube.exists():
        parts.append(b"cube:" + cube.read_bytes())
    streams = root / "streams"
    if streams.is_dir():
        for p in sorted(streams.rglob("*")):
            if p.is_file():
                rel = p.relative_to(root).as_posix()
                parts.append(rel.encode("utf-8") + b":" + p.read_bytes())
    return b"".join(parts)


def store_interpretation(store: Any) -> dict[str, Any]:
    """How the sealed raw bytes are to be READ (D10 / A11).

    The stream catalogue (which detector/ADC input/settings each NPZ holds), the
    cube's column schema and the run's channel/ADC mapping. Changing any of these
    changes what the same bytes mean, so they are part of the seal. The seal
    itself is never included (no self-reference).
    """
    meta = dict(getattr(store, "meta", {}) or {})
    streams = [
        {k: v for k, v in dict(e).items() if k != "terminal_source_seal"}
        for e in (meta.get("streams") or [])
        if isinstance(e, dict)
    ]
    cube_fields: list[str] = []
    fields_fn = getattr(store, "cube_fields", None)
    if callable(fields_fn):
        with contextlib.suppress(OSError, StopIteration):
            cube_fields = list(fields_fn())
    snap = meta.get("acquisition_snapshot") or {}
    adc = snap.get("adc") if isinstance(snap, dict) else {}
    return {
        "streams": streams,
        "cube_fields": cube_fields,
        "mux_map": (adc or {}).get("mux_map") if isinstance(adc, dict) else None,
        "detector_order": (adc or {}).get("detector_order") if isinstance(adc, dict) else None,
        "channel_map_sha256": snap.get("channel_map_sha256") if isinstance(snap, dict) else None,
        "config_sha256": meta.get("config_sha256"),
    }


def compute_store_seal(
    store: Any,
    *,
    status: str,
    cancel_reason: str | None = None,
) -> TerminalSourceSeal | None:
    """The terminal seal for the store's CURRENT bytes and interpretation (not saved)."""
    raw_snap = store.meta.get("acquisition_snapshot")
    if not raw_snap or not isinstance(raw_snap, dict):
        return None
    snap = AcquisitionSnapshot.from_dict(raw_snap)
    folder = getattr(store, "folder", None)
    raw_bytes = collect_raw_artifact_bytes(folder) if folder is not None else b""
    if not raw_bytes:
        cube = getattr(store, "cube_path", None)
        if cube is not None and Path(cube).exists():
            raw_bytes = Path(cube).read_bytes()
    return seal_terminal_source(
        snap,
        raw_bytes=raw_bytes,
        terminal_meta={
            "status": status,
            "cancel_reason": cancel_reason,
            "interpretation": store_interpretation(store),
        },
        revision="complete" if status == "COMPLETE" else "partial",
        status=status,
    )


def seal_store_terminal(
    store: Any,
    *,
    status: str,
    cancel_reason: str | None = None,
) -> TerminalSourceSeal | None:
    """Apply the terminal source seal to an open ``ScanStore`` if a snapshot exists.

    No-op (returns None) for historical runs without ``acquisition_snapshot``.
    The seal covers cube + all raw streams/NPZs/sidecars (D10) AND their
    interpretation mapping (A11).
    """
    seal = compute_store_seal(store, status=status, cancel_reason=cancel_reason)
    if seal is None:
        return None
    store.meta["terminal_source_seal"] = seal.to_dict()
    store.meta["terminal_source_seal_inputs"] = {"status": status, "cancel_reason": cancel_reason}
    store.save_meta()
    return seal


def verify_store_seal(store: Any) -> tuple[bool, str]:
    """Recompute the seal from live bytes + interpretation and compare (reuse gate)."""
    saved = store.meta.get("terminal_source_seal")
    if not isinstance(saved, dict):
        return True, "no seal (historical run)"
    inputs = store.meta.get("terminal_source_seal_inputs") or {
        "status": saved.get("status", "COMPLETE"),
        "cancel_reason": None,
    }
    live = compute_store_seal(
        store, status=str(inputs.get("status")), cancel_reason=inputs.get("cancel_reason")
    )
    if live is None:
        return False, "seal present but acquisition snapshot missing"
    if live.combined_sha256 != saved.get("combined_sha256"):
        return False, "terminal seal no longer matches live bytes/interpretation"
    return True, "ok"


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
    # Never hash the seal into itself — only caller-supplied terminal facts.
    meta = {k: v for k, v in dict(terminal_meta or {}).items() if k != "terminal_source_seal"}
    meta_sha = content_hash(meta)
    combined = hashlib.sha256((manifest_hash + raw_sha + meta_sha).encode("ascii")).hexdigest()
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
    # Extra consumed inputs (stream hashes, analysis config, control IDs, …).
    consumed_inputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["reference_sources"] = list(self.reference_sources)
        return d

    def identity_hash(self) -> str:
        return content_hash(self.to_dict())


class AnalysisIdentityConflict(ValueError):
    """Same analysis id already exists with different content (D08)."""


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
    consumed_inputs: dict[str, Any] | None = None,
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
        consumed_inputs=dict(consumed_inputs or {}),
    )


def collect_stream_sha256(run_folder: Path | str) -> dict[str, str]:
    """Per-stream file hashes under ``run_folder/streams`` (CE06)."""
    root = Path(run_folder)
    streams = root / "streams"
    out: dict[str, str] = {}
    if not streams.is_dir():
        return out
    for path in sorted(streams.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = file_sha256(path)
    return out


REQUIRED_IDENTITY_KEYS = (
    "source_cube_sha256",
    "source_scan_sha256",
    "calibration_id",
    "channel_map_sha256",
    "estimator_version",
    "coupling_model_version",
)


def software_identity() -> dict[str, Any]:
    """Code identity for derived products: commit plus dirty-tree CONTENT hash.

    ``dirty_content_sha256`` hashes the actual uncommitted diff of the host
    package (not just a 'dirty' flag), so two different dirty trees on the same
    commit get different identities. Unknown when git is unavailable.
    """
    import subprocess

    root = Path(__file__).resolve().parents[4]
    out: dict[str, Any] = {"package": "lio", "git_commit": None, "dirty": None,
                           "dirty_content_sha256": None}  # fmt: skip
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()  # fmt: skip
        diff = subprocess.run(
            ["git", "-C", str(root), "diff", "HEAD", "--binary", "--", "software/host/src"],
            capture_output=True, timeout=10, check=True,
        ).stdout  # fmt: skip
        untracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "-z",
             "--", "software/host/src"],
            capture_output=True, timeout=10, check=True,
        ).stdout  # fmt: skip
        h = hashlib.sha256(diff)
        for rel in sorted(x for x in untracked.split(b"\0") if x):
            h.update(rel + b"\0")
            with contextlib.suppress(OSError):
                h.update((root / rel.decode()).read_bytes())
        out.update(
            git_commit=head,
            dirty=bool(diff or untracked),
            dirty_content_sha256=h.hexdigest() if (diff or untracked) else None,
        )
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def resolve_analysis_validity(
    analysis: dict[str, Any] | None,
    *,
    cube_sha256: str,
    scan_sha256: str,
    run_id: str | None = None,
    sample_id: str | None = None,
    expected_calibration_id: str | None = None,
    expected_estimator_version: str | None = None,
    stream_sha256: dict[str, str] | None = None,
) -> tuple[bool, ValidityReason, str]:
    """Shared validity resolver for report/profile readers.

    Returns ``(ok_for_quantitative_reuse, reason, detail)``. Rejected products
    remain inspectable; ``ok`` False means quarantine from quantitative reuse.
    NPZ/stream mutations invalidate reuse when the analysis identity recorded
    stream hashes (CE06).
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
            rid_ok = str(analysis.get("run_id", "")) in (
                "",
                run_id or "",
            )
            sid_ok = str(analysis.get("sample_id", sample_id)) == str(sample_id)
            if rid_ok and sid_ok and (run_id or sample_id):
                return False, ValidityReason.LEGACY_UNVERIFIED, "no source/calibration identity"
            return False, ValidityReason.UNREADABLE, "identity_mismatch"

        # A08: a minimal identity is not verified. Every consumed source and the
        # estimator/model/calibration/mapping must be recorded.
        consumed = identity.get("consumed_inputs") or {}
        if not isinstance(consumed, dict):
            consumed = {}
        missing = [k for k in REQUIRED_IDENTITY_KEYS if not identity.get(k)]
        if "stream_sha256" not in consumed or not isinstance(consumed.get("stream_sha256"), dict):
            missing.append("consumed_inputs.stream_sha256")
        if missing:
            return False, ValidityReason.LEGACY_UNVERIFIED, f"incomplete identity: {missing}"
        if run_id is not None and str(analysis.get("run_id", "")) != str(run_id):
            return False, ValidityReason.SOURCE_CHANGED, "product belongs to a different run"

        stored_cube = str(identity.get("source_cube_sha256") or "")
        stored_scan = str(identity.get("source_scan_sha256") or "")
        if stored_cube != cube_sha256:
            return False, ValidityReason.SOURCE_CHANGED, "cube hash mismatch"
        if stored_scan != scan_sha256:
            return False, ValidityReason.SOURCE_CHANGED, "scan hash mismatch"

        # CE06 / A07: consumed stream/NPZ hashes must match the LIVE files; a
        # caller that did not hash the live streams cannot verify reuse.
        if stream_sha256 is None:
            return False, ValidityReason.UNREADABLE, "live stream hashes not supplied"
        stored_streams = consumed.get("stream_sha256") or {}
        if isinstance(stored_streams, dict):
            for rel, digest in stored_streams.items():
                live = stream_sha256.get(str(rel))
                if live is None:
                    return (
                        False,
                        ValidityReason.SOURCE_CHANGED,
                        f"stream missing after mutation: {rel}",
                    )
                if str(live) != str(digest):
                    return (
                        False,
                        ValidityReason.SOURCE_CHANGED,
                        f"stream/npz hash mismatch: {rel}",
                    )
            # Extra unexpected streams also invalidate sealed reuse.
            for rel in stream_sha256:
                if str(rel) not in {str(k) for k in stored_streams}:
                    return (
                        False,
                        ValidityReason.SOURCE_CHANGED,
                        f"unexpected stream file: {rel}",
                    )

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
        # A19: a ratio across runs only cancels Rf when the SAME known Rf applies;
        # an unknown/conflicting Rf cannot support it.
        if detector == "ingaas" and (
            rf is None or rf.value_ohm is None or rf.state in ("unknown", "conflicting")
        ):
            return QuantityEligibility(quantity, False, "Rf unknown: ratio not supported", detector)
        if not geometry_compatible:
            return QuantityEligibility(
                quantity, False, "geometry/acquisition incompatible", detector
            )
        if not control_evidence:
            return QuantityEligibility(quantity, False, "control evidence missing", detector)
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
