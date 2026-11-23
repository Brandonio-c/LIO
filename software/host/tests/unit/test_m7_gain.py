"""M7 opt-in gain / STREAM / GLS stubs — offline and synthetic only."""

from __future__ import annotations

import pytest

from lio.scan.m7_gain import (
    CORE_DEFAULT_GAIN,
    SERIAL_LIMITED_STREAM_SPS,
    M7Error,
    StreamObservation,
    account_stream_exposure_ms,
    block_calibration_identity,
    execute_off_on_off_stream,
    gls_or_sequential_estimate,
    load_gain_profile,
    plan_off_on_off_stream,
    validate_gain_readback,
)

pytestmark = pytest.mark.unit


def test_core_default_gain_profile() -> None:
    p = load_gain_profile("1")
    assert p.gain == CORE_DEFAULT_GAIN
    assert p.lsb_mv == 0.125
    assert p.synthetic is False


def test_synthetic_gain_requires_flag() -> None:
    with pytest.raises(M7Error, match="synthetic"):
        load_gain_profile("2")
    p = load_gain_profile("2", allow_synthetic=True)
    assert p.synthetic is True
    assert p.lsb_mv == 0.0625


def test_reject_unexpected_gain_on_non_m7() -> None:
    with pytest.raises(M7Error, match="non-M7"):
        validate_gain_readback("2", "2", m7_enabled=False)
    validate_gain_readback("1", "1", m7_enabled=False)
    validate_gain_readback("2", "2", m7_enabled=True)


def test_missing_readback_never_defaults_to_one() -> None:
    with pytest.raises(M7Error, match="missing"):
        validate_gain_readback("1", None, m7_enabled=False)
    with pytest.raises(M7Error, match="missing"):
        validate_gain_readback("1", "  ", m7_enabled=True)


def test_block_calibration_identity() -> None:
    p = load_gain_profile("1")
    ident = block_calibration_identity(p, block_index=3, detector="ingaas")
    assert ident.gain == "1"
    assert ident.block_index == 3
    assert ident.input_range == "unverified"


def test_off_on_off_plan_documents_serial_limit() -> None:
    plan = plan_off_on_off_stream(
        detector="ingaas",
        hole=12,
        n_samples=100,
        on_start=20,
        on_end=80,
        interval_ms=0,
        gain="1",
    )
    assert plan.on_samples == 60
    assert any("860" in n for n in plan.notes)
    assert plan.serial_limited_sps == SERIAL_LIMITED_STREAM_SPS
    assert plan.estimated_on_ms > 0


def test_non_default_gain_needs_m7() -> None:
    with pytest.raises(M7Error, match="m7_enabled"):
        plan_off_on_off_stream(
            detector="ingaas",
            hole=12,
            n_samples=10,
            on_start=2,
            on_end=8,
            gain="2",
            allow_synthetic_gain=True,
            m7_enabled=False,
        )


def test_synthetic_stream_execution_and_exposure() -> None:
    plan = plan_off_on_off_stream(
        detector="opt101",
        hole=8,
        n_samples=10,
        on_start=3,
        on_end=7,
        interval_ms=10,
        gain="1",
    )
    # Synthetic timestamps at 10 ms spacing (labelled synthetic).
    t_us = [i * 10_000 for i in range(10)]
    raw = list(range(10))
    obs = StreamObservation(
        t_us=t_us,
        raw=raw,
        hole=8,
        detector="opt101",
        on_start=3,
        on_end=7,
        gain="1",
        synthetic=True,
    )
    out = execute_off_on_off_stream(plan, synthetic_samples=obs)
    assert out.synthetic is True
    ms = account_stream_exposure_ms(plan, out)
    assert abs(ms - 30.0) < 1e-6  # indices 3→6 inclusive → 30 ms


def test_gls_stub_not_identifiable_low_rank() -> None:
    # Rank-deficient design: second column is duplicate of first.
    design = [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]]
    y = [1.0, 2.0, 3.0]
    r = gls_or_sequential_estimate(design, y, min_rank=2)
    assert r.identifiable is False
    assert "not identifiable" in r.reason or "rank" in r.reason


def test_gls_stub_never_claims_qualified() -> None:
    design = [[1.0, 0.0], [1.0, 1.0], [1.0, 2.0]]
    y = [1.0, 2.0, 3.0]
    r = gls_or_sequential_estimate(design, y, min_rank=2)
    assert r.identifiable is False
    assert "not qualified" in r.reason
