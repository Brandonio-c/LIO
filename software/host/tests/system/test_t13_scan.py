"""T13 diagnostic height sweep (plan LIO-SW-SCAN-001 §5). Operator present and
--allow-motion on hardware (it moves the chamber top through its travel).

The logic lives in lio.scan and lio.suite.checks.t13_scan; the catalogue ID maps to
one test here.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lio.results import TestResult

pytestmark = [pytest.mark.sim, pytest.mark.hw, pytest.mark.motion]


def test_T13_1_diagnostic_height_sweep(run_suite: Callable[[str], TestResult]) -> None:
    """Diagnostic height sweep (scan.suite_mode)."""
    run_suite("T13.1")
