"""T11 system acceptance: comparison with a saved baseline (plan §5.3, §6).

The logic lives in lio.suite.checks; each catalogue ID maps to one test here.
The overall verdict of T11 is computed for every run (lio.results).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lio.results import TestResult

pytestmark = [pytest.mark.sim, pytest.mark.hw]


def test_T11_1_comparison_with_the_baseline(run_suite: Callable[[str], TestResult]) -> None:
    """Comparison with the baseline (skipped without --lio-baseline)."""
    run_suite("T11.1")
