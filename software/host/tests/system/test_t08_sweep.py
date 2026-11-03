"""T08 sweep and data path (plan §6).

The logic lives in lio.suite.checks; each catalogue ID maps to one test here.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lio.results import TestResult

pytestmark = [pytest.mark.sim, pytest.mark.hw]


def test_T08_1_sweep_completes_with_a_valid_schema(run_suite: Callable[[str], TestResult]) -> None:
    """SWEEP completes with a valid schema."""
    run_suite("T08.1")


def test_T08_2_repeated_sweeps(run_suite: Callable[[str], TestResult]) -> None:
    """Repeated sweeps."""
    run_suite("T08.2")


def test_T08_3_sweep_agrees_with_meas(run_suite: Callable[[str], TestResult]) -> None:
    """Sweep agrees with MEAS."""
    run_suite("T08.3")


def test_T08_4_csv_output_format(run_suite: Callable[[str], TestResult]) -> None:
    """CSV output format."""
    run_suite("T08.4")
