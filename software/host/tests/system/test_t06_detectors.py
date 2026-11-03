"""T06 detectors (plan §6).

The logic lives in lio.suite.checks; each catalogue ID maps to one test here.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lio.results import TestResult

pytestmark = [pytest.mark.sim, pytest.mark.hw]


def test_T06_1_opt101(run_suite: Callable[[str], TestResult]) -> None:
    """OPT101."""
    run_suite("T06.1")


def test_T06_2_ingaas_tia(run_suite: Callable[[str], TestResult]) -> None:
    """InGaAs TIA."""
    run_suite("T06.2")


def test_T06_3_cross_calibration_on_the_shared_holes(
    run_suite: Callable[[str], TestResult],
) -> None:
    """Cross-calibration on the shared holes."""
    run_suite("T06.3")
