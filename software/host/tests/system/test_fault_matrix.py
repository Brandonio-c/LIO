"""Fault-injection matrix (plan §5.2, §8): every simulator fault is detected by its test.

Each row injects one fault into a fresh simulator, runs the intended catalogue
entry on its own, and requires the intended sub-result to report the fault.
The same sub-result must PASS on a healthy simulator (the control), so the
detection is caused by the fault and not by the test.

Interactive and motion rows use the simulated operator, which answers from
the simulator's physical truth (what really lit, whether a motor turned).

Known blind spot (documented, not a row): ``stuck_on`` on the hole with the
highest forward voltage of its rail (e.g. hole 1) never takes the rail's
current, so it is optically invisible, and harmless.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from lio import scan
from lio.config import HwConfig, parse_config
from lio.device import LIODevice
from lio.results import Status, TestResult, Verdict
from lio.scan.analysis import Analysis, analyse
from lio.sim import FAULT_NAMES, Faults, SimulatedLIO
from lio.suite.core import REGISTRY, SuiteContext, catalogue, run_test
from lio.suite.runner import everything, new_record, run_catalogue, sim_context
from lio.transport import SimTransport

pytestmark = pytest.mark.sim


@dataclass(frozen=True)
class Row:
    fault: str
    test: str
    sub: str  # sub-result id that must report the fault
    status: Status = Status.FAIL
    loop_jumper: bool = False
    unfitted: tuple[int, ...] = ()  # run on a config with these holes empty

    @property
    def id(self) -> str:
        empty = f"+empty{','.join(map(str, self.unfitted))}" if self.unfitted else ""
        return f"{self.fault}{'+jumper' if self.loop_jumper else ''}{empty}->{self.sub}"


def _with_unfitted(cfg: HwConfig, holes: tuple[int, ...]) -> HwConfig:
    """The same config with ``holes`` marked as having no emitter fitted."""
    if not holes:
        return cfg
    data = copy.deepcopy(cfg.data)
    for c in data["channels"]:
        if c["hole"] in holes:
            c.update(fitted=False, expect={}, wavelength_nm=None)
    return parse_config(data, cfg.path)


MATRIX = (
    Row("no_adc", "T03.1", "T03.1/adc"),
    Row("i2c_bridged", "T03.1", "T03.1/bus"),
    Row("i2c_slow", "T03.1", "T03.1/adc", Status.WARN),
    Row("i2c_slow", "T03.1", "T03.1/bus", Status.WARN),
    Row("stuck_on:5", "T05.3", "T05.3/h05/unique"),
    Row("stuck_on:8", "T05.3", "T05.3/h08/unique"),
    # Holes 10-11 have LEDs fitted, so a stuck-on RAIL B channel shows as holes
    # 10, 11 and 13 sharing one signature; with empty holes it is the stuck_via probe.
    Row("stuck_on:13", "T05.3", "T05.3/h13/unique"),
    Row("stuck_on:13", "T05.3", "T05.3/B/stuck_via_10", unfitted=(10, 11)),
    Row("dead_channel:3", "T05.2", "T05.2/h03/opt101"),
    Row("dead_channel:13", "T05.2", "T05.2/h13/ingaas"),
    # Caught at hole 8 (blue LED: no InGaAs signal where one is expected). Hole 3 now
    # lights 850 nm, which the OPT101 also sees; the InGaAs is not judged on hole 3
    # (channel.judge_out_of_range: false), so hole 3 alone no longer shows the swap.
    Row("swapped:3,8", "T05.3", "T05.3/h08/pattern"),
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
    Row("motor_stall", "T09.2", "T09.2/1/up"),
    Row("swapped:3,4", "T04.4", "T04.4/h03/visible"),  # same detector: only the eye sees it
    Row("dead_channel:8", "T04.4", "T04.4/h08/camera"),
    Row("rail_a_dead", "T05.6", "T05.6/A/h08"),
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
    result = _run_one(_with_unfitted(cfg, row.unfitted), row.test, row.fault, row.loop_jumper)
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
    result = _run_one(_with_unfitted(cfg, row.unfitted), row.test, None, row.loop_jumper)
    assert result.status == Status.PASS, result.summary()
    assert _find(result, row.sub) in (Status.PASS, None), result.summary()


# Faults the host is designed to repair rather than report (tested below).
HEALED = ("bank_a_asleep",)


# Diagnostic-sweep faults (LIO-SW-SCAN-001 §9) whose detecting metric is still to be
# built. Each milestone S3-S5 moves its faults from here into SCAN_MATRIX; at the end of
# S5 this set is empty. Their simulated physics is tested in tests/unit/test_sim_height.py.
PENDING_SCAN_METRIC: set[str] = set()


# ------------------------------------------------- diagnostic sweep (lio.scan)


@dataclass(frozen=True)
class ScanRow:
    """A scan on a faulted simulator; the analysis finding ``finding`` must report it.

    ``reference``: the sample of a reference run on the same (faulted) rig, e.g. the
    white tile for stray light measured with the black cup."""

    fault: str
    finding: str
    status: Status = Status.FAIL
    sample: str = "empty"
    reference: str | None = None
    incomplete: bool = False  # the fault aborts the run (the analysis still runs)
    part: str = ""  # the explanation must name this part
    mode: str = "matrix"
    healthy_reference: bool = False  # the reference run is on a healthy rig (a baseline)

    @property
    def id(self) -> str:
        ref = f"+ref:{self.reference}" if self.reference else ""
        ref += "+baseline" if self.healthy_reference else ""
        return f"{self.fault}@{self.sample}{ref}->{self.finding}"


SCAN_MATRIX = (
    # S3: optics and electrical health
    ScanRow("pd_disconnected", "optics/ingaas/electrical_only", part="D1"),
    ScanRow("ground_shift:0.2", "elec/ingaas/ground_shift", part="GND star point"),
    ScanRow("leakage:60", "elec/ingaas/dark_offset", part="U5 pin-2 node"),
    ScanRow("leakage_drift:10", "elec/ingaas/drift", part="U5 pin-2 node"),
    ScanRow("mains_hum:8", "elec/ingaas/hum", part="earth bond"),
    # judged in continuous mode only (stop-measure-move readings never see it)
    ScanRow("coil_emi", "elec/ingaas/coil_emi", part="motor wiring", mode="matrix_cont"),
    ScanRow("coil_emi", "elec/opt101/coil_emi", part="motor wiring", mode="matrix_cont"),
    ScanRow("led_swapped:9,16", "optics/opt101/h16/plausibility", part="LED16", status=Status.WARN),
    ScanRow("led_swapped:9,16", "optics/opt101/h09/response", part="LED9"),
    ScanRow("wrong_led:16=630", "optics/opt101/h16/plausibility", part="LED16", status=Status.WARN),
    ScanRow("rail_miswired:12", "optics/ingaas/h12/response", part="rail wiring"),
    ScanRow("rail_miswired:12", "optics/wrong_rail/h12", part="rail wiring"),  # fw 2.5.0
    # a partial loss of light is judged against a baseline of the same sample (absolute
    # floors are set from the rig, whose levels are ~100x below the simulator's)
    ScanRow(
        "window_blocked:0.1", "optics/ingaas/effectiveness", part="window", healthy_reference=True
    ),
    # no white tile on the rig: the empty chamber as the reference
    ScanRow(
        "stray_light:0.05",
        "optics/stray",
        sample="black_cup",
        reference="empty",
        part="chamber walls",
    ),
    ScanRow(
        "stray_light:0.05",
        "optics/stray",
        sample="black_cup",
        reference="white_ptfe",
        part="chamber walls",
    ),
    ScanRow(
        "intermittent:6", "optics/h06/intermittent", part="LED6", status=Status.WARN
    ),  # seen on the rig; flaky contact, not a dead LED
    # S4: ambient, mechanics, the run itself
    ScanRow("ambient_leak:-20000", "ambient/opt101/leak", part="shroud"),
    ScanRow("ambient_leak:-20000", "ambient/ingaas/leak", part="shroud"),
    ScanRow("room_flicker", "ambient/opt101/flicker", part="lid"),
    ScanRow("backlash:2000", "mech/backlash", part="5-6 mm couplers"),
    ScanRow("step_loss:2,4200", "mech/step_loss", part="M2"),
    ScanRow("mid_run_boot:120", "system/link", incomplete=True, part="5 V supply"),
    ScanRow("mid_run_boot:120", "system/stage", incomplete=True, part="lio.stage"),
    ScanRow("adc_dropout:30", "system/adc", incomplete=True, part="ADS1115"),
)


@pytest.fixture(scope="module")
def scan_cfg(cfg: HwConfig) -> HwConfig:
    """Scaled geometry (a tenth of the travel) and short records: a run in ~1 s."""
    data = copy.deepcopy(cfg.data)
    data["sim"]["height"].update(travel_hs=40000, peak_hs=-30000, width_hs=9000,
                                 peak_shift_hs=250, ambient_leak_scale_hs=6000)  # fmt: skip
    data["thresholds"]["motion"]["travel"]["range_steps"] = 40000
    data["scan"].update(long_dark_s=4, hum_bursts=5)
    data["scan"]["modes"]["matrix_cont"] = {"heights": 0, "up": 0, "return_top": True,
                                            "repeats": 1, "ref_heights": 0, "continuous": True,
                                            "label": "matrix, continuous"}  # fmt: skip
    data["scan"]["modes"]["matrix"] = {"heights": 9, "up": "same", "return_top": True,
                                       "repeats": 1, "ref_heights": 1, "label": "matrix"}  # fmt: skip
    return parse_config(data, cfg.path)


@pytest.fixture(scope="module")
def scan_analysis(
    scan_cfg: HwConfig, tmp_path_factory: pytest.TempPathFactory
) -> Callable[..., Analysis]:
    cache: dict[tuple[str | None, str, str | None, bool, str], Analysis] = {}
    root = tmp_path_factory.mktemp("scans")

    def get(faults: str | None, sample: str, reference: str | None,
            baseline: bool = False, mode: str = "matrix") -> Analysis:  # fmt: skip
        key = (faults, sample, reference, baseline, mode)
        if baseline:
            reference = sample
        if key not in cache:
            ref = None
            if reference is not None:
                ref, st = scan.sim_run(scan_cfg, mode, root,
                                       faults=None if baseline else faults,
                                       sample=reference)  # fmt: skip
                assert st == "COMPLETE", ref.meta["aborts"]
            store, _ = scan.sim_run(scan_cfg, mode, root, faults=faults, sample=sample)
            cache[key] = analyse(store.folder, scan_cfg, None if ref is None else ref.folder)
        return cache[key]

    return get


@pytest.mark.parametrize("row", SCAN_MATRIX, ids=[r.id for r in SCAN_MATRIX])
def test_scan_fault_is_detected(scan_analysis: Any, row: ScanRow) -> None:
    a = scan_analysis(row.fault, row.sample, row.reference, row.healthy_reference, row.mode)
    assert (a.status == "INCOMPLETE") is row.incomplete, a.summary()
    f = a.get(row.finding)
    assert f.status == row.status, f"{row.finding}: {f.status.value}: {f.detail}\n{a.summary()}"
    e = a.explanations.get(row.finding)
    assert e is not None, f"no explanation for {row.finding}"
    assert row.part in e["parts"], f"{row.finding}: explanation names {e['parts']}, not {row.part}"
    assert e["check"], "an explanation gives the next manual check"


@pytest.mark.parametrize(
    ("sample", "reference"),
    [("empty", None), ("white_ptfe", None), ("black_cup", "white_ptfe"), ("black_cup", "empty")],
)
def test_scan_healthy_control(scan_analysis: Any, sample: str, reference: str | None) -> None:
    """A healthy rig: no finding flagged, and every matrix finding for this sample computed."""
    a = scan_analysis(None, sample, reference)
    assert a.status == "COMPLETE"
    flagged = [f"{f.id}: {f.status.value} {f.detail}" for f in a.flagged()]
    assert not flagged, "\n".join(flagged)
    assert a.verdict["verdict"] == Verdict.FUNCTIONAL.value, a.verdict
    assert {h["health"] for h in a.health} <= {"OK", "n/a"}
    for row in SCAN_MATRIX:
        if (row.sample == sample and row.reference == reference and not row.healthy_reference
                and row.mode == "matrix"):  # fmt: skip
            assert a.get(row.finding).status == Status.PASS, row.finding
    if sample == "empty" and reference is None:  # continuous-mode rows: a healthy control
        c = scan_analysis(None, sample, None, False, "matrix_cont")
        for row in SCAN_MATRIX:
            if row.mode == "matrix_cont":
                assert c.get(row.finding).status == Status.PASS, row.finding
    for row in SCAN_MATRIX:  # baseline rows: a healthy run against a healthy baseline
        if row.healthy_reference and row.sample == sample and reference is None:
            b = scan_analysis(None, sample, None, True)
            assert b.get(row.finding).status == Status.PASS, row.finding


def test_every_fault_has_a_row() -> None:
    rows = {r.fault.split(":")[0] for r in MATRIX} | {r.fault.split(":")[0] for r in SCAN_MATRIX}
    covered = rows | set(HEALED) | PENDING_SCAN_METRIC
    missing = set(FAULT_NAMES) - covered
    assert not missing, f"faults without a detecting test: {sorted(missing)}"
    stale = PENDING_SCAN_METRIC & rows
    assert not stale, f"faults with a row are no longer pending: {sorted(stale)}"


# ------------------------------------------------- power bank A asleep (healed)


def _asleep_context(cfg: HwConfig, *, wake: bool) -> SuiteContext:
    sim = SimulatedLIO(cfg, Faults.parse("bank_a_asleep"))
    dev = LIODevice(SimTransport(sim), cfg)
    dev._wake_supported = wake  # as with firmware that has no POWER WAKE
    dev.open()
    return SuiteContext(dev, cfg, "sim", sim)


def test_bank_a_asleep_is_woken_before_the_tests(cfg: HwConfig) -> None:
    catalogue()
    ctx = _asleep_context(cfg, wake=True)
    try:
        assert ctx.sim is not None and ctx.sim.wakes == 1  # on opening the port
        assert run_test(ctx, REGISTRY["T03.1"]).status == Status.PASS
        # the bank falls asleep again; the next test wakes it before measuring
        ctx.dev.sleep(cfg.sim.num("bank_awake_s") + 1)
        assert run_test(ctx, REGISTRY["T03.2"]).status == Status.PASS
        assert ctx.sim.wakes == 2
    finally:
        ctx.dev.close()


def test_bank_a_asleep_without_wake_is_reported(cfg: HwConfig) -> None:
    catalogue()
    ctx = _asleep_context(cfg, wake=False)
    try:
        r = run_test(ctx, REGISTRY["T03.1"])
        assert _find(r, "T03.1/adc") == Status.FAIL
        assert "power bank A" in r.sub("T03.1/adc").message
    finally:
        ctx.dev.close()


# ------------------------------------------------------------- whole catalogue


def _full_run(cfg: HwConfig, faults: str | None) -> dict[str, object]:
    ctx = sim_context(cfg, faults)
    try:
        record = run_catalogue(ctx, new_record(ctx), everything)
    finally:
        ctx.dev.close()
    return record.verdict


def test_healthy_simulator_is_functional(cfg: HwConfig) -> None:
    ctx = sim_context(cfg)
    try:
        record = run_catalogue(ctx, new_record(ctx), everything)
    finally:
        ctx.dev.close()
    bad = [r.summary() for r in record.results if r.status not in (Status.PASS, Status.SKIP)]
    assert not bad, "\n".join(bad)
    skipped = {r.id for r in record.results if r.status == Status.SKIP}
    # no loopback jumper; covered by T05.3; no baseline given
    assert skipped == {"T04.2", "T04.3", "T09.6", "T09.7", "T11.1"}  # T09.6/7: travel not measured
    assert record.verdict["verdict"] == Verdict.FUNCTIONAL.value
    assert not ctx.dev.duty or not ctx.dev.duty.over_budget


@pytest.mark.parametrize(
    ("fault", "verdict"),
    [
        ("dead_channel:3", Verdict.DEGRADED),
        ("tia_saturated", Verdict.DEGRADED),
        ("stuck_on:5", Verdict.NOT_FUNCTIONAL),
        # A stuck-on hole 13 (lowest Vf but one on RAIL B) takes the current from
        # the white/pink holes 10-11 and from 12, so 3 counted channels fail:
        # NOT FUNCTIONAL. With 10-11 empty the stuck_via probe flags the rail.
        ("stuck_on:13", Verdict.NOT_FUNCTIONAL),
        ("reversed_ingaas", Verdict.NOT_FUNCTIONAL),
        ("no_adc", Verdict.NOT_FUNCTIONAL),
        ("motor_stall", Verdict.NOT_FUNCTIONAL),
        ("dead_channel:12", Verdict.DEGRADED),
        ("swapped:3,4", Verdict.DEGRADED),
    ],
)
def test_verdict(cfg: HwConfig, fault: str, verdict: Verdict) -> None:
    assert _full_run(cfg, fault)["verdict"] == verdict.value


def test_verdict_stuck_on_rail_b_with_empty_probe_holes(cfg: HwConfig) -> None:
    assert _full_run(_with_unfitted(cfg, (10, 11)), "stuck_on:13")["verdict"] == (
        Verdict.NOT_FUNCTIONAL.value
    )


@pytest.mark.parametrize("mode", ["quick", "full"])
def test_scan_full_size_healthy(cfg: HwConfig, tmp_path: Any, mode: str) -> None:
    """The real geometry and settings (lio_hw.yaml as shipped): nothing flagged."""
    store, status = scan.sim_run(cfg, mode, tmp_path, sample="empty")
    assert status == "COMPLETE", store.meta["aborts"]
    a = analyse(store.folder, cfg)
    flagged = [f"{f.id}: {f.status.value} {f.detail}" for f in a.flagged()]
    assert not flagged, "\n".join(flagged)
    assert a.verdict["verdict"] == Verdict.FUNCTIONAL.value, a.verdict


@pytest.mark.parametrize(
    ("fault", "verdict"),
    [
        ("pd_disconnected", Verdict.NOT_FUNCTIONAL),  # the InGaAs signal is not light
        ("rail_miswired:12", Verdict.DEGRADED),  # one failing channel
        ("led_swapped:9,16", Verdict.DEGRADED),  # two channels
        ("mid_run_boot:120", Verdict.NOT_FUNCTIONAL),  # link: a critical module
        ("backlash:2000", Verdict.NOT_FUNCTIONAL),  # a failure not tied to a channel
    ],
)
def test_scan_verdict(scan_analysis: Any, fault: str, verdict: Verdict) -> None:
    a = scan_analysis(fault, "empty", None)
    assert a.verdict["verdict"] == verdict.value, a.summary()
    assert any(h["health"] == "ACT" for h in a.health)
