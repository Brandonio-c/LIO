"""M3 fixed-N block estimators and shared-control covariance."""

from __future__ import annotations

import numpy as np
import pytest

from lio.scan.analysis.uncertainty import (
    ValueKind,
    classify_value,
    drive_response_tau,
    paired_optical_contrast,
    scipy_available,
    shared_control_corrected,
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


def test_predeclared_null_family_coverage_fwer() -> None:
    """≥2000 predeclared 32-channel null families: coverage/FWER with MC uncertainty.

    Skips cleanly when SciPy precision extra is absent.
    """
    from lio.scan.analysis.uncertainty import bonferroni_level, familywise_intervals

    if not scipy_available():
        pytest.skip("scipy precision extra absent — interval FWER check unavailable")

    rng = np.random.default_rng(20261123)
    n_families = 2000
    n_channels = 32
    n_blocks = 8
    alpha = 0.05
    # Predeclared tolerances (binomial MC uncertainty ~sqrt(p(1-p)/N)).
    se_fwer = float(np.sqrt(alpha * (1 - alpha) / n_families))
    fwer_tol = alpha + 3.0 * se_fwer
    coverage_tol_lo = 0.90

    false_family = 0
    cover_hits = 0
    cover_total = 0
    level = bonferroni_level(n_channels, alpha)
    for _ in range(n_families):
        estimates = {}
        for ch in range(n_channels):
            diffs = rng.normal(0.0, 1.0, size=n_blocks)
            dark = np.zeros(n_blocks)
            lit = diffs
            est = drive_response_tau(lit, dark, level=level)
            estimates[f"ch{ch}"] = est
        fw = familywise_intervals(estimates, family_size=n_channels, alpha=alpha)
        family_reject = False
        for est in fw.values():
            if est.interval is None or not est.interval.available:
                continue
            assert est.interval.low is not None and est.interval.high is not None
            if est.interval.low > 0 or est.interval.high < 0:
                family_reject = True
            cover_total += 1
            if est.interval.low <= 0 <= est.interval.high:
                cover_hits += 1
        if family_reject:
            false_family += 1

    fwer = false_family / n_families
    coverage = cover_hits / max(cover_total, 1)
    assert fwer <= fwer_tol, f"FWER {fwer:.4f} exceeds tol {fwer_tol:.4f}"
    assert coverage >= coverage_tol_lo, f"coverage {coverage:.4f} below {coverage_tol_lo}"
