"""T09 motors (plan §6). Operator present and --allow-motion on hardware.

The logic lives in lio.suite.checks; each catalogue ID maps to one test here.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lio.results import TestResult

pytestmark = [pytest.mark.sim, pytest.mark.hw, pytest.mark.motion]


def test_T09_1_motion_arming(run_suite: Callable[[str], TestResult]) -> None:
    """Motion arming."""
    run_suite("T09.1")


def test_T09_2_each_motor_moves_both_ways(run_suite: Callable[[str], TestResult]) -> None:
    """Each motor moves both ways."""
    run_suite("T09.2")


def test_T09_3_motor_stop_latency(run_suite: Callable[[str], TestResult]) -> None:
    """MOTOR STOP latency."""
    run_suite("T09.3")


def test_T09_4_detector_noise_while_a_motor_moves(run_suite: Callable[[str], TestResult]) -> None:
    """Detector noise while a motor moves."""
    run_suite("T09.4")
