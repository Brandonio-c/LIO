"""Shared pytest options and fixtures for the LIO test suite (plan §5.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lio.config import HwConfig, load_config


def pytest_addoption(parser: pytest.Parser) -> None:
    g = parser.getgroup("lio")
    g.addoption("--lio-port", default=None, help="serial port of a real LIO (hardware tests)")
    g.addoption("--lio-sim", action="store_true", help="run system tests against the simulator")
    g.addoption(
        "--lio-fault", default=None, help="simulator faults, e.g. reversed_ingaas,stuck_on:5"
    )
    g.addoption("--interactive", action="store_true", help="allow tests that need an operator")
    g.addoption("--allow-motion", action="store_true", help="allow tests that move the motors")
    g.addoption("--lio-config", default=None, help="path to lio_hw.yaml")
    g.addoption("--results-dir", default=None, help="where to write the run record")


@pytest.fixture(scope="session")
def cfg(request: pytest.FixtureRequest) -> HwConfig:
    path = request.config.getoption("--lio-config")
    return load_config(Path(path) if path else None)
