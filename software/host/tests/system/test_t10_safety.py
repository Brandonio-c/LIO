"""T10 safety behaviours (plan §6).

The logic lives in lio.suite.checks; each catalogue ID maps to one test here.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lio.results import TestResult

pytestmark = [pytest.mark.sim, pytest.mark.hw]


def test_T10_1_power_up_dark_state(run_suite: Callable[[str], TestResult]) -> None:
    """Power-up dark state."""
    run_suite("T10.1")


def test_T10_2_on_time_watchdog(run_suite: Callable[[str], TestResult]) -> None:
    """On-time watchdog."""
    run_suite("T10.2")


def test_T10_3_comms_loss_failsafe(run_suite: Callable[[str], TestResult]) -> None:
    """Comms-loss failsafe."""
    run_suite("T10.3")


def test_T10_4_single_channel_invariant(run_suite: Callable[[str], TestResult]) -> None:
    """Single-channel invariant."""
    run_suite("T10.4")


def test_T10_5_motion_disarmed_after_comms_loss(run_suite: Callable[[str], TestResult]) -> None:
    """Motion disarmed after comms loss."""
    run_suite("T10.5")
