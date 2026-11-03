"""T01 host environment and discovery (plan §6).

The logic lives in lio.suite.checks; each catalogue ID maps to one test here.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lio.results import TestResult

pytestmark = [pytest.mark.sim, pytest.mark.hw]


def test_T01_1_python_and_dependency_versions(run_suite: Callable[[str], TestResult]) -> None:
    """Python and dependency versions."""
    run_suite("T01.1")


def test_T01_2_serial_port_discovery(run_suite: Callable[[str], TestResult]) -> None:
    """Serial port discovery."""
    run_suite("T01.2")


def test_T01_3_configuration_loads_and_is_self_consistent(
    run_suite: Callable[[str], TestResult],
) -> None:
    """Configuration loads and is self-consistent."""
    run_suite("T01.3")
