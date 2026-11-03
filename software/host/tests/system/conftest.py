"""System-test fixtures: one device per session (simulator or hardware) and a run record.

    pytest -m "unit or sim" --lio-sim                         # simulator
    pytest -m "sim" --lio-sim --lio-fault reversed_ingaas     # simulator with a fault
    pytest -m "hw and not interactive and not motion" --lio-port /dev/cu.usbserial-1120

Each catalogue test runs through :func:`lio.suite.core.run_test`, which always
restores the dark, idle state afterwards. FAIL/ERROR fail the pytest test,
WARN passes with a warning, SKIP skips. The run record is written to
``--results-dir`` (default ``test_results/<run id>/results.json`` at the repo root).
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from lio.config import HwConfig
from lio.results import RunRecord, Status, TestResult
from lio.suite.core import REGISTRY, SuiteContext, catalogue, run_test
from lio.suite.runner import finish, new_record, serial_context, sim_context

REPO_ROOT = Path(__file__).resolve().parents[4]
RECORD_KEY = pytest.StashKey[RunRecord]()


class LIOWarning(UserWarning):
    """A catalogue test ended in WARN."""


@pytest.fixture(scope="session")
def suite_ctx(request: pytest.FixtureRequest, cfg: HwConfig) -> Iterator[SuiteContext]:
    opt = request.config.getoption
    port, use_sim = opt("--lio-port"), opt("--lio-sim")
    if port and use_sim:
        raise pytest.UsageError("give either --lio-sim or --lio-port, not both")
    if not port and not use_sim:
        pytest.skip("system tests need --lio-sim or --lio-port")
    if port:
        ctx = serial_context(
            cfg, port, interactive=opt("--interactive"), allow_motion=opt("--allow-motion")
        )
    else:
        ctx = sim_context(
            cfg,
            opt("--lio-fault"),
            interactive=opt("--interactive"),
            allow_motion=opt("--allow-motion"),
        )
    meta = {
        "sample_id": opt("--lio-sample-id"),
        "operator": opt("--lio-operator"),
        "notes": opt("--lio-notes"),
    }
    record = new_record(ctx, {k: v for k, v in meta.items() if v})
    request.config.stash[RECORD_KEY] = record
    try:
        yield ctx
    finally:
        finish(record, ctx)
        ctx.dev.close()
        out = opt("--results-dir")
        folder = Path(out) if out else REPO_ROOT / "test_results" / record.run_id
        path = record.write_json(folder / "results.json")
        print(f"\nLIO run record: {path}  verdict: {record.verdict.get('verdict')}")


@pytest.fixture
def run_suite(
    request: pytest.FixtureRequest, suite_ctx: SuiteContext
) -> Callable[[str], TestResult]:
    record = request.config.stash[RECORD_KEY]
    catalogue()  # make sure every entry is registered

    def run(test_id: str) -> TestResult:
        result = run_test(suite_ctx, REGISTRY[test_id])
        record.results.append(result)
        if result.status in (Status.FAIL, Status.ERROR):
            pytest.fail(result.summary(), pytrace=False)
        if result.status == Status.SKIP:
            pytest.skip(f"{test_id}: {result.message}")
        if result.status == Status.WARN:
            warnings.warn(LIOWarning(result.summary()), stacklevel=2)
        return result

    return run
