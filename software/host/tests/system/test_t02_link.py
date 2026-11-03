"""T02 link and protocol (plan §6).

The logic lives in lio.suite.checks; each catalogue ID maps to one test here.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lio.results import TestResult

pytestmark = [pytest.mark.sim, pytest.mark.hw]


def test_T02_1_port_open_and_boot_banner(run_suite: Callable[[str], TestResult]) -> None:
    """Port open and boot banner."""
    run_suite("T02.1")


def test_T02_2_ping_round_trip_latency(run_suite: Callable[[str], TestResult]) -> None:
    """PING round-trip latency."""
    run_suite("T02.2")


def test_T02_3_info_fields_versions_and_safety_limits(
    run_suite: Callable[[str], TestResult],
) -> None:
    """INFO fields, versions and safety limits."""
    run_suite("T02.3")


def test_T02_4_robustness_to_bad_input(run_suite: Callable[[str], TestResult]) -> None:
    """Robustness to bad input."""
    run_suite("T02.4")


def test_T02_5_sequence_numbers_and_interleaved_events(
    run_suite: Callable[[str], TestResult],
) -> None:
    """Sequence numbers and interleaved events."""
    run_suite("T02.5")


def test_T02_6_reset_restores_the_boot_state(run_suite: Callable[[str], TestResult]) -> None:
    """RESET restores the boot state."""
    run_suite("T02.6")
