"""T03 I2C and ADC (plan §6).

The logic lives in lio.suite.checks; each catalogue ID maps to one test here.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lio.results import TestResult

pytestmark = [pytest.mark.sim, pytest.mark.hw]


def test_T03_1_i2c_scan_finds_the_ads1115(run_suite: Callable[[str], TestResult]) -> None:
    """I2C scan finds the ADS1115."""
    run_suite("T03.1")


def test_T03_2_dark_adc_noise_all_inputs(run_suite: Callable[[str], TestResult]) -> None:
    """Dark ADC noise, all inputs."""
    run_suite("T03.2")


def test_T03_3_gain_sweep_on_dark_inputs(run_suite: Callable[[str], TestResult]) -> None:
    """Gain sweep on dark inputs."""
    run_suite("T03.3")


def test_T03_4_adc_data_rate(run_suite: Callable[[str], TestResult]) -> None:
    """ADC data rate."""
    run_suite("T03.4")


def test_T03_5_long_term_dark_stability(run_suite: Callable[[str], TestResult]) -> None:
    """Long-term dark stability."""
    run_suite("T03.5")
