"""M7 opt-in PGA profiles, off-on-off STREAM planner, and GLS interface stubs.

Deferred / incomplete experimental helpers - not part of core M0-M6 acceptance.
Missing gain readback is never silently defaulted to 1.

Core acquisition remains gain 1. Non-M7 protocols reject unexpected gain.
Different-gain fixtures used in tests must be labelled ``synthetic``.

Serial-limited STREAM rates are documented honestly — not a uniform 860 SPS claim.
Bench A0 / Rf / ammeter qualification remains owner-deferred.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from lio.scan.provenance import content_hash

SCHEMA_VERSION = 1
CORE_DEFAULT_GAIN = "1"
# Documented serial-limited effective rate ceiling for long buffered streams.
# Firmware conversion capability is higher; USB/event framing limits sustained rate.
SERIAL_LIMITED_STREAM_SPS = 120.0  # order-of-magnitude host-limited; not 860 SPS
NOMINAL_ADC_SPS_CLAIM = 860.0  # firmware conversion capability — not STREAM delivery rate


class M7Error(ValueError):
    """Invalid or unsupported M7 gain / STREAM request."""


@dataclass(frozen=True)
class GainProfile:
    """Opt-in shared PGA profile (both detectors; no per-detector auto-ranging)."""

    id: str
    gain: str
    fsr_v: float
    lsb_mv: float
    schema: int = SCHEMA_VERSION
    notes: str = ""
    synthetic: bool = False  # True for offline different-gain fixtures only

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def profile_hash(self) -> str:
        return content_hash(self.to_dict())


# Supported opt-in profiles (ADS1115 PGA). Core default remains gain 1.
GAIN_PROFILES: dict[str, GainProfile] = {
    "1": GainProfile("gain_1", "1", 4.096, 0.125, notes="core default / owner-approved fixed"),
    "2": GainProfile(
        "gain_2",
        "2",
        2.048,
        0.0625,
        notes="opt-in M7; synthetic fixtures only until bench-qualified",
        synthetic=True,
    ),
    "4": GainProfile(
        "gain_4",
        "4",
        1.024,
        0.03125,
        notes="opt-in M7; synthetic fixtures only until bench-qualified",
        synthetic=True,
    ),
}


def load_gain_profile(gain: str | GainProfile, *, allow_synthetic: bool = False) -> GainProfile:
    if isinstance(gain, GainProfile):
        profile = gain
    else:
        key = str(gain).replace("GAIN_", "").lstrip("0") or "0"
        if key not in GAIN_PROFILES:
            raise M7Error(f"unsupported gain profile {gain!r}")
        profile = GAIN_PROFILES[key]
    if profile.synthetic and not allow_synthetic:
        raise M7Error(
            f"gain profile {profile.id} is synthetic-labelled; pass allow_synthetic=True "
            "for offline fixtures only (not bench authorization)"
        )
    return profile


def validate_gain_readback(
    requested: str | GainProfile,
    readback: str | None,
    *,
    m7_enabled: bool = False,
) -> GainProfile:
    """Validate device gain readback against request.

    Non-M7: only core default gain 1 is accepted.
    M7 opt-in: requested profile must match readback.
    """
    req = load_gain_profile(requested, allow_synthetic=True)
    if not m7_enabled and req.gain != CORE_DEFAULT_GAIN:
        raise M7Error(
            f"unexpected gain {req.gain!r} on non-M7 protocol; core default is {CORE_DEFAULT_GAIN}"
        )
    # D20 / R8: missing readback is never silently defaulted to gain 1.
    if readback is None or str(readback).strip() == "":
        raise M7Error("gain readback missing; refuse (missing ≠ 1; no silent default)")
    rb = str(readback).replace("GAIN_", "")
    if rb not in (req.gain, f"GAIN_{req.gain}", req.gain.lstrip("0") or "0"):
        # Normalise "1" vs "GAIN_ONE" style
        aliases = {CORE_DEFAULT_GAIN, "1", "GAIN_ONE", "GAIN_1"}
        if not (req.gain == CORE_DEFAULT_GAIN and rb in aliases):
            raise M7Error(f"gain readback {readback!r} ≠ requested {req.gain!r}")
    return req


@dataclass(frozen=True)
class BlockCalibrationIdentity:
    """Per-block calibration identity tying gain profile to a STREAM/MEAS block."""

    profile_id: str
    profile_hash: str
    gain: str
    lsb_mv: float
    block_index: int
    detector: str
    input_range: str = "unverified"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def block_calibration_identity(
    profile: GainProfile, *, block_index: int, detector: str
) -> BlockCalibrationIdentity:
    return BlockCalibrationIdentity(
        profile_id=profile.id,
        profile_hash=profile.profile_hash(),
        gain=profile.gain,
        lsb_mv=profile.lsb_mv,
        block_index=block_index,
        detector=detector,
        input_range="unverified",
    )


@dataclass
class OffOnOffPlan:
    """Single-detector buffered off-on-off STREAM schedule (one contiguous pulse)."""

    detector: str
    hole: int
    n_samples: int
    interval_ms: int
    off_pre: int
    on_samples: int
    off_post: int
    gain: str
    estimated_on_ms: float
    notes: list[str] = field(default_factory=list)
    serial_limited_sps: float = SERIAL_LIMITED_STREAM_SPS
    ownership_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_off_on_off_stream(
    *,
    detector: str,
    hole: int,
    n_samples: int,
    on_start: int,
    on_end: int,
    interval_ms: int = 0,
    gain: str = CORE_DEFAULT_GAIN,
    m7_enabled: bool = False,
    allow_synthetic_gain: bool = False,
) -> OffOnOffPlan:
    """Plan a single contiguous STREAM pulse with real index bounds.

    Firmware supports one contiguous scheduled STREAM pulse. ``interval_ms=0``
    means as-fast-as-serial-allows — **not** uniform 860 SPS delivery.
    """
    if n_samples < 3:
        raise M7Error("n_samples must be >= 3 for off-on-off")
    if not (0 <= on_start < on_end <= n_samples):
        raise M7Error(f"invalid on window [{on_start}, {on_end}) for n={n_samples}")
    profile = load_gain_profile(gain, allow_synthetic=allow_synthetic_gain)
    if not m7_enabled and profile.gain != CORE_DEFAULT_GAIN:
        raise M7Error("non-default gain requires m7_enabled=True")
    on_n = on_end - on_start
    # Effective spacing: max(requested, serial-limited floor).
    eff_ms = 1000.0 / SERIAL_LIMITED_STREAM_SPS if interval_ms <= 0 else float(interval_ms)
    est_on = on_n * eff_ms
    notes = [
        f"serial-limited sustained rate ≈{SERIAL_LIMITED_STREAM_SPS:.0f} SPS "
        f"(not uniform {NOMINAL_ADC_SPS_CLAIM:.0f} SPS claim)",
        "one contiguous STREAM pulse; no periodic lock-in via host flags",
        "strict exposure via ownership journal at execute time",
        "timestamps must come from STREAM t_us fields, not wall-clock invent",
    ]
    if profile.synthetic:
        notes.append("synthetic gain fixture — not bench-qualified")
    return OffOnOffPlan(
        detector=detector,
        hole=hole,
        n_samples=n_samples,
        interval_ms=interval_ms,
        off_pre=on_start,
        on_samples=on_n,
        off_post=n_samples - on_end,
        gain=profile.gain,
        estimated_on_ms=est_on,
        notes=notes,
    )


@dataclass
class StreamObservation:
    """STREAM samples with real firmware timestamps (t_us)."""

    t_us: list[int]
    raw: list[int]
    hole: int
    detector: str
    on_start: int
    on_end: int
    gain: str
    synthetic: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def account_stream_exposure_ms(plan: OffOnOffPlan, samples: StreamObservation) -> float:
    """Strict on-time from STREAM timestamps within the on window (ownership journal input)."""
    if len(samples.t_us) != len(samples.raw):
        raise M7Error("t_us/raw length mismatch")
    if len(samples.t_us) < plan.n_samples:
        # Partial stream: account only observed on samples.
        pass
    i0 = samples.on_start
    i1 = min(samples.on_end, len(samples.t_us)) - 1
    if i1 <= i0 or i0 < 0:
        return 0.0
    return max(0.0, (samples.t_us[i1] - samples.t_us[i0]) / 1000.0)


def execute_off_on_off_stream(
    plan: OffOnOffPlan,
    *,
    stream_fn: Any | None = None,
    device: Any | None = None,
    adc_channel: int = 0,
    synthetic_samples: StreamObservation | None = None,
) -> StreamObservation:
    """Execute via injected STREAM callback or labelled synthetic samples.

    Never opens USB itself. Ownership journal gating is the caller's duty.
    """
    if synthetic_samples is not None:
        if not synthetic_samples.synthetic:
            raise M7Error("injected samples must set synthetic=True when not from device")
        return synthetic_samples
    if stream_fn is not None:
        rows = stream_fn(
            adc_channel,
            plan.n_samples,
            plan.interval_ms,
            (plan.hole, plan.off_pre, plan.off_pre + plan.on_samples),
        )
        t_us = [int(r.t_us if hasattr(r, "t_us") else r["t_us"]) for r in rows]
        raw = [int(r.raw if hasattr(r, "raw") else r["raw"]) for r in rows]
        return StreamObservation(
            t_us=t_us,
            raw=raw,
            hole=plan.hole,
            detector=plan.detector,
            on_start=plan.off_pre,
            on_end=plan.off_pre + plan.on_samples,
            gain=plan.gain,
            synthetic=False,
        )
    if device is not None:
        rows = device.adc_stream(
            adc_channel,
            plan.n_samples,
            plan.interval_ms,
            led=(plan.hole, plan.off_pre, plan.off_pre + plan.on_samples),
        )
        return StreamObservation(
            t_us=[int(r.t_us) for r in rows],
            raw=[int(r.raw) for r in rows],
            hole=plan.hole,
            detector=plan.detector,
            on_start=plan.off_pre,
            on_end=plan.off_pre + plan.on_samples,
            gain=plan.gain,
            synthetic=False,
        )
    raise M7Error("no stream_fn, device, or synthetic_samples")


@dataclass
class GlsResult:
    identifiable: bool
    estimate: float | None
    reason: str
    design_rank: int | None = None
    version: str = "m7-gls-stub-1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def gls_or_sequential_estimate(
    design: Sequence[Sequence[float]] | Any,
    observations: Sequence[float] | Any,
    *,
    min_rank: int = 1,
) -> GlsResult:
    """Versioned GLS/sequential interface stub.

    Returns not-identifiable when design rank / telemetry is insufficient.
    Never fabricates a qualified estimate.
    """
    try:
        import numpy as np

        X = np.asarray(design, dtype=float)
        y = np.asarray(observations, dtype=float)
        if X.ndim != 2 or y.ndim != 1 or X.shape[0] != y.shape[0]:
            return GlsResult(False, None, "design/observations shape mismatch", None)
        if X.shape[0] < min_rank or X.shape[1] < min_rank:
            return GlsResult(
                False, None, "insufficient design size for identification", int(X.shape[1])
            )
        rank = int(np.linalg.matrix_rank(X, tol=1e-9))
        if rank < min(X.shape[1], min_rank):
            return GlsResult(
                False,
                None,
                f"design rank {rank} < required {min_rank}; not identifiable",
                rank,
            )
        # Sufficient rank still returns not-qualified: stub does not invent GLS fit
        # as bench-qualified science. Offline numerical path may compute OLS for tests.
        try:
            coef, *_ = np.linalg.lstsq(X, y, rcond=None)
            est = float(coef[0]) if coef.size else None
        except np.linalg.LinAlgError:
            return GlsResult(False, None, "linear algebra failure", rank)
        if est is None or not math.isfinite(est):
            return GlsResult(False, None, "non-finite estimate", rank)
        return GlsResult(
            False,
            est,
            "numerical OLS available offline; GLS/sequential not qualified — "
            "insufficient telemetry/assumptions for M7 qualification claim",
            rank,
        )
    except ImportError:
        return GlsResult(False, None, "numpy unavailable", None)
