"""T05 LED drivers, rails and channels (plan §6).

The logic lives in lio.suite.checks; each catalogue ID maps to one test here.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lio.results import TestResult

pytestmark = [pytest.mark.sim, pytest.mark.hw]


def test_T05_1_rail_gating_by_ce1_ce2(run_suite: Callable[[str], TestResult]) -> None:
    """Rail gating by CE1 / CE2."""
    run_suite("T05.1")


def test_T05_2_per_channel_response(run_suite: Callable[[str], TestResult]) -> None:
    """Per-channel response."""
    run_suite("T05.2")


def test_T05_3_channel_address_and_isolation(run_suite: Callable[[str], TestResult]) -> None:
    """Channel address and isolation."""
    run_suite("T05.3")


def test_T05_4_off_state_return_after_each_meas(run_suite: Callable[[str], TestResult]) -> None:
    """Off-state return after each MEAS."""
    run_suite("T05.4")


def test_T05_5_repeatability_interleaved_meas(run_suite: Callable[[str], TestResult]) -> None:
    """Repeatability (interleaved MEAS)."""
    run_suite("T05.5")
