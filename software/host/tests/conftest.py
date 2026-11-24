"""Shared pytest options and fixtures for the LIO test suite (plan §5.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
    g.addoption("--lio-sample-id", default=None, help="run metadata: sample in the chamber")
    g.addoption("--lio-operator", default=None, help="run metadata: who ran the suite")
    g.addoption("--lio-notes", default=None, help="run metadata: free text")
    g.addoption("--lio-baseline", default=None, help="baseline file for T11.1, or 'latest'")


@pytest.fixture(scope="session")
def cfg(request: pytest.FixtureRequest) -> HwConfig:
    path = request.config.getoption("--lio-config")
    return load_config(Path(path) if path else None)


@pytest.fixture(scope="session", autouse=True)
def _isolate_stage_and_state(tmp_path_factory: pytest.TempPathFactory) -> Any:
    """S7: every test process uses synthetic stage/journal state and may not write
    the physical ``test_results/stage_position.json`` (guarded, not restored)."""
    import os

    root = tmp_path_factory.mktemp("lio_isolated_state")
    saved = {k: os.environ.get(k) for k in
             ("LIO_STAGE_FILE", "LIO_GUARD_PHYSICAL_STAGE", "LIO_STATE_ROOT")}  # fmt: skip
    os.environ["LIO_STAGE_FILE"] = str(root / "stage_position.json")
    os.environ["LIO_GUARD_PHYSICAL_STAGE"] = "1"
    os.environ.setdefault("LIO_STATE_ROOT", str(root / "state"))
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
