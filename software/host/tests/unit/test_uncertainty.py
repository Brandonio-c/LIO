"""M3 fixed-N block estimators and shared-control covariance."""

from __future__ import annotations

import numpy as np
import pytest

from lio.scan.analysis.uncertainty import (
    ValueKind,
    classify_value,
    drive_response_tau,
    paired_optical_contrast,
    shared_control_corrected,
    scipy_available,
)

pytestmark = pytest.mark.unit


def test_synthetic_signed_recovery() -> None:
    rng = np.random.default_rng(0)
    true_tau = -3.5
    dark = rng.normal(0.0, 0.5, size=20)
    lit = dark + true_tau + rng.normal(0.0, 0.3, size=20)
    est = drive_response_tau(lit, dark)
    assert est.value is not None
    assert est.value == pytest.approx(true_tau, abs=0.5)
    assert est.kind is ValueKind.NEGATIVE
    assert est.n_blocks == 20
    if scipy_available():
        assert est.interval is not None and est.interval.available
        assert est.interval.low is not None and est.interval.high is not None
        assert est.interval.low < true_tau < est.interval.high
    else:
        assert est.interval is not None and not est.interval.available
        assert "scipy" in (est.interval.reason or "")


def test_paired_blocked_unblocked() -> None:
    unblocked = [10.0, 11.0, 9.5, 10.5]
    blocked = [2.0, 2.5, 1.5, 2.0]
    est = paired_optical_contrast(unblocked, blocked)
    assert est.value == pytest.approx(8.25)
    assert est.kind is ValueKind.POSITIVE


def test_shared_control_covariance_nonzero() -> None:
    rng = np.random.default_rng(1)
    # Shared control fluctuation appears in both S and C.
    shared = rng.normal(5.0, 2.0, size=30)
    optical = rng.normal(3.0, 0.5, size=30)
    s = shared + optical
    c = shared
    est = shared_control_corrected(s, c)
    assert est.value == pytest.approx(float(np.mean(optical)), abs=0.3)
    assert est.extras["shared_control_covariance_nonzero"] is True
    assert abs(est.extras["cov_sc"]) > 0.5
    # Independent duplicate rows must not invent extra N beyond shared length.
    assert est.n_blocks == 30


def test_value_kinds_distinguishable() -> None:
    assert classify_value(-1.0) is ValueKind.NEGATIVE
    assert classify_value(0.0) is ValueKind.ZERO
    assert classify_value(1.0) is ValueKind.POSITIVE
    assert classify_value(None, missing=True) is ValueKind.MISSING
    assert classify_value(99.0, saturated=True) is ValueKind.SATURATED
    assert classify_value(0.1, unresolved=True) is ValueKind.UNRESOLVED


def test_no_qualify_by_max_over_heights() -> None:
    # Noise-only height curve: max is positive but estimator on fixed blocks stays near 0.
    rng = np.random.default_rng(2)
    heights = np.linspace(0, 1, 50)
    noise = rng.normal(0.0, 1.0, size=50)
    # Selecting max would "detect"; fixed-N paired diffs should not.
    lit = noise
    dark = np.zeros_like(noise)
    est = drive_response_tau(lit[:10], dark[:10])  # fixed first 10, not argmax
    assert abs(est.value or 0) < 2.0
    assert float(np.max(noise)) > 2.0  # max would look like a hit
    _ = heights
