"""Precision/profiles extras: skip cleanly without scipy; run intervals when present.

Install: ``pip install -e '.[precision]'`` or ``.[profiles]`` (both pull scipy>=1.11).
"""

from __future__ import annotations

import pytest

from lio.scan.analysis import uncertainty as U

pytestmark = pytest.mark.unit


def test_interval_unavailable_without_scipy_or_runs_with_it() -> None:
    lit = [10.0, 12.0, 11.0, 13.0]
    dark = [0.0, 0.0, 0.0, 0.0]
    est = U.drive_response_tau(lit, dark)
    assert est.value is not None
    assert est.interval is not None
    if U.scipy_available():
        assert est.interval.available is True
        assert est.interval.low is not None and est.interval.high is not None
        assert est.interval.low < est.value < est.interval.high
    else:
        assert est.interval.available is False
        assert "scipy" in (est.interval.reason or "")
        pytest.skip("scipy not installed; interval path skipped (install lio[precision])")


def test_paired_contrast_respects_extras_gate() -> None:
    a = [5.0, 6.0, 7.0]
    b = [1.0, 1.0, 1.0]
    est = U.paired_optical_contrast(a, b)
    assert est.value is not None
    assert abs(est.value - 5.0) < 1e-9
    if not U.scipy_available():
        assert est.interval is not None and est.interval.available is False
        pytest.skip("scipy not installed; contrast interval skipped")
    assert est.interval is not None and est.interval.available is True
