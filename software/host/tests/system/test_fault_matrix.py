"""Fault-injection matrix (plan §5.2, §8): every simulator fault is detected by its test.

Each row injects one fault into a fresh simulator, runs the intended catalogue
entry on its own, and requires the intended sub-result to report the fault.
The same sub-result must PASS on a healthy simulator (the control), so the
detection is caused by the fault and not by the test.

Known blind spot (documented, not a row): ``stuck_on`` on the hole with the
highest forward voltage of its rail (e.g. hole 1) never takes the rail's
current, so it is optically invisible, and harmless.

``motor_stall`` is detected by the operator in T09.2 (M4, motion tests).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from lio.config import HwConfig
from lio.results import Status, TestResult, Verdict
from lio.sim import FAULT_NAMES
from lio.suite.core import REGISTRY, catalogue, run_test
from lio.suite.runner import new_record, run_catalogue, sim_context

pytestmark = pytest.mark.sim

MOTION_FAULTS = {"motor_stall"}  # M4 (T09)


@dataclass(frozen=True)
class Row:
    fault: str
    test: str
    sub: str  # sub-result id that must report the fault
    status: Status = Status.FAIL
    loop_jumper: bool = False

    @property
    def id(self) -> str:
        return f"{self.fault}{'+jumper' if self.loop_jumper else ''}->{self.sub}"


MATRIX = (
    Row("no_adc", "T03.1", "T03.1/adc"),
    Row("stuck_on:5", "T05.3", "T05.3/h05/unique"),
    Row("stuck_on:8", "T05.3", "T05.3/h08/unique"),
    Row("stuck_on:13", "T05.3", "T05.3/B/stuck_via_10"),
    Row("dead_channel:3", "T05.2", "T05.2/h03/opt101"),
    Row("dead_channel:13", "T05.2", "T05.2/h13/ingaas"),
    Row("swapped:3,8", "T05.3", "T05.3/h03/pattern"),
    Row("swapped:3,13", "T05.2", "T05.2/h13/ingaas"),
    Row("rail_a_dead", "T05.1", "T05.1/A/h08/ce_high"),
    Row("rail_b_dead", "T05.1", "T05.1/B/h12/ce_high"),
    Row("ce_inverted", "T04.1", "T04.1/w1/07"),
    Row("ce_inverted", "T05.1", "T05.1/A/h08/ce_low"),
    Row("reversed_ingaas", "T06.2", "T06.2/polarity/gate"),
    Row("no_neg_rail", "T06.2", "T06.2/erratic"),
    Row("tia_saturated", "T06.2", "T06.2/h13/saturation", Status.WARN),
    Row("opt101_no_feedback", "T06.1", "T06.1/dark"),
    Row("noisy_adc", "T03.2", "T03.2/a1"),
    Row("slow_settle", "T07.2", "T07.2/settle", Status.WARN),
    Row("slow_settle", "T05.4", "T05.4/h03/opt101"),
    Row("chain_break", "T05.3", "T05.3/chain"),
    Row("chain_break", "T04.2", "T04.2/loop", loop_jumper=True),
    Row("comms_drop", "T02.2", "T02.2/answered"),
)


def _run_one(cfg: HwConfig, test_id: str, faults: str | None, loop_jumper: bool) -> TestResult:
    catalogue()
    ctx = sim_context(cfg, faults, loop_jumper=loop_jumper)
    try:
        return run_test(ctx, REGISTRY[test_id])
    finally:
        ctx.dev.close()


def _find(result: TestResult, sub: str) -> Status | None:
    for s in result.subs:
        if s.id == sub:
            return s.status
    return None


@pytest.mark.parametrize("row", MATRIX, ids=[r.id for r in MATRIX])
def test_fault_is_detected(cfg: HwConfig, row: Row) -> None:
    result = _run_one(cfg, row.test, row.fault, row.loop_jumper)
    got = _find(result, row.sub)
    assert got == row.status, (
        f"{row.fault}: expected {row.sub} = {row.status.value}, got "
        f"{got.value if got else 'no such sub-result'}\n{result.summary()}"
    )
    assert result.status.rank >= row.status.rank


@pytest.mark.parametrize("row", MATRIX, ids=[f"control:{r.id}" for r in MATRIX])
def test_healthy_control_passes(cfg: HwConfig, row: Row) -> None:
    """Without the fault the same test passes, and the sub-result passes or is absent.

    Some sub-results (duplicate groups, saturation, the chain and stuck-on
    diagnoses) are only emitted when something is wrong.
    """
    result = _run_one(cfg, row.test, None, row.loop_jumper)
    assert result.status == Status.PASS, result.summary()
    assert _find(result, row.sub) in (Status.PASS, None), result.summary()


def test_every_fault_has_a_row() -> None:
    covered = {r.fault.split(":")[0] for r in MATRIX}
    missing = set(FAULT_NAMES) - MOTION_FAULTS - covered
    assert not missing, f"faults without a detecting test: {sorted(missing)}"


# ------------------------------------------------------------- whole catalogue


def _full_run(cfg: HwConfig, faults: str | None) -> dict[str, object]:
    ctx = sim_context(cfg, faults)
    try:
        record = run_catalogue(ctx, new_record(ctx))
    finally:
        ctx.dev.close()
    return record.verdict


def test_healthy_simulator_is_functional(cfg: HwConfig) -> None:
    ctx = sim_context(cfg)
    try:
        record = run_catalogue(ctx, new_record(ctx))
    finally:
        ctx.dev.close()
    bad = [r.summary() for r in record.results if r.status not in (Status.PASS, Status.SKIP)]
    assert not bad, "\n".join(bad)
    skipped = {r.id for r in record.results if r.status == Status.SKIP}
    assert skipped == {"T04.2", "T04.3", "T08.4"}  # no jumper; covered by T05.3; M5
    assert record.verdict["verdict"] == Verdict.FUNCTIONAL.value
    assert not ctx.dev.duty or not ctx.dev.duty.over_budget


@pytest.mark.parametrize(
    ("fault", "verdict"),
    [
        ("dead_channel:3", Verdict.DEGRADED),
        ("tia_saturated", Verdict.DEGRADED),
        ("stuck_on:5", Verdict.NOT_FUNCTIONAL),
        ("stuck_on:13", Verdict.NOT_FUNCTIONAL),
        ("reversed_ingaas", Verdict.NOT_FUNCTIONAL),
        ("no_adc", Verdict.NOT_FUNCTIONAL),
    ],
)
def test_verdict(cfg: HwConfig, fault: str, verdict: Verdict) -> None:
    assert _full_run(cfg, fault)["verdict"] == verdict.value
