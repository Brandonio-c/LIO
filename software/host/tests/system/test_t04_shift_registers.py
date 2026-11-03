"""T04 channel selection and the shift registers (plan §6).

The logic lives in lio.suite.checks; each catalogue ID maps to one test here.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lio.results import TestResult

pytestmark = [pytest.mark.sim, pytest.mark.hw]


def test_T04_1_shift_register_patterns_with_ce_low(run_suite: Callable[[str], TestResult]) -> None:
    """Shift-register patterns with CE low."""
    run_suite("T04.1")


def test_T04_2_shift_register_loopback_optional_jumper(
    run_suite: Callable[[str], TestResult],
) -> None:
    """Shift-register loopback (optional jumper)."""
    run_suite("T04.2")


def test_T04_3_optical_address_verification(run_suite: Callable[[str], TestResult]) -> None:
    """Optical address verification."""
    run_suite("T04.3")
