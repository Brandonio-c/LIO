"""T07 timing and settling (plan §6).

The logic lives in lio.suite.checks; each catalogue ID maps to one test here.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lio.results import TestResult

pytestmark = [pytest.mark.sim, pytest.mark.hw]


def test_T07_1_step_response_and_settling_time(run_suite: Callable[[str], TestResult]) -> None:
    """Step response and settling time."""
    run_suite("T07.1")


def test_T07_2_recommended_settle_time(run_suite: Callable[[str], TestResult]) -> None:
    """Recommended settle time."""
    run_suite("T07.2")


def test_T07_3_meas_timing(run_suite: Callable[[str], TestResult]) -> None:
    """MEAS timing."""
    run_suite("T07.3")
