"""The scan executor on the simulator (LIO-SW-SCAN-001 §3, §5.3; milestone S2).

Healthy runs complete; every abort path stops safely and records its reason; an
interrupted run resumes from its next step; an unexpected boot invalidates the
position; the safety rules (one LED at a time, the duty budget, no light while
moving) hold throughout.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from lio import scan
from lio.config import HwConfig, parse_config
from lio.device import LIODevice
from lio.operator import SimOperator
from lio.scan.executor import Control
from lio.sim import Faults, SimulatedLIO
from lio.transport import SimTransport

pytestmark = [pytest.mark.sim]

TINY = {"heights": 3, "up": "same", "return_top": True, "repeats": 1, "ref_heights": 1,
        "label": "test"}  # fmt: skip


@pytest.fixture
def scfg(cfg: HwConfig) -> HwConfig:
    """A short travel and short records, so a whole run takes seconds."""
    data = copy.deepcopy(cfg.data)
    data["sim"]["height"]["travel_hs"] = 40000
    data["sim"]["height"]["peak_hs"] = -30000
    data["sim"]["height"]["width"] = 9000
    sc = data["scan"]
    sc["long_dark_s"] = 2
    sc["hum_bursts"] = 3
    sc["modes"]["tiny"] = dict(TINY)
    sc["modes"]["tiny_fine"] = {**TINY, "up": 2, "extra_near_optimum": 3}
    return parse_config(data, cfg.path)


class Rig:
    def __init__(self, cfg: HwConfig, tmp: Path, faults: str | None, sample: str) -> None:
        self.cfg = cfg
        self.tmp = tmp
        self.sim = SimulatedLIO(cfg, Faults.parse(faults))
        self.sim.sample = sample
        self.dev = LIODevice(SimTransport(self.sim), cfg)
        self.dev.open()
        self.stage = scan.sim_stage(self.dev, tmp / "stage.json", 40000)
        self.light_while_moving: list[tuple[float, set[int]]] = []
        self.overlaps: list[tuple[float, set[int]]] = []
        self._watch()

    def _watch(self) -> None:
        """Record any light that starts while a motor turns, and two LEDs at once."""
        sim = self.sim
        orig = sim._light_changed

        def hooked(t: float) -> None:
            orig(t)
            lit = set(sim._light_since)
            if len(lit) > 1:
                self.overlaps.append((t, lit))
            if lit and any(m.speed_at(t) > 0 for m in sim.motors) and not sim.light_req:
                self.light_while_moving.append((t, lit))

        sim._light_changed = hooked  # type: ignore[method-assign]

    def plan(self, mode: str, **over: Any) -> scan.ScanPlan:
        return scan.plan_for(self.cfg, mode, self.dev.stage, self.dev.stage_top_margin(), over)

    def run(self, mode: str, *, control: Control | None = None, on_progress: Any = None,
            sample_id: str = "empty", **over: Any) -> tuple[scan.ScanStore, str]:  # fmt: skip
        return scan.start(self.dev, self.cfg, self.plan(mode, **over), self.tmp,
                          SimOperator(self.sim), sample_id=sample_id, control=control,
                          on_progress=on_progress, sim=True)  # fmt: skip

    def safe(self) -> None:
        """Everything off: no LED, no motor running, coils released, MOTOR LIGHT off."""
        st = self.dev.status()
        assert st.as_int("ch") == 0 and st.as_int("mask") == 0
        assert st.as_str("motor1") != "run" and st.as_str("motor2") != "run"
        assert not self.sim._light_since
        assert not self.sim.light_req

    def max_rail_a_ms_per_min(self) -> float:
        duty = self.dev.duty
        assert duty is not None
        worst = 0.0
        for hole, spans in duty.history.items():
            if self.cfg.channel(hole).rail != "A":
                continue
            for t0, _ in spans:
                on = sum(min(b, t0 + 60) - max(a, t0) for a, b in spans if a < t0 + 60 and b > t0)
                worst = max(worst, on * 1000)
        return worst


@pytest.fixture
def rig(scfg: HwConfig, tmp_path: Path) -> Iterator[Any]:
    rigs: list[Rig] = []

    @contextmanager
    def make(faults: str | None = None, sample: str = "empty") -> Iterator[Rig]:
        r = Rig(scfg, tmp_path, faults, sample)
        rigs.append(r)
        yield r

    yield make
    for r in rigs:
        r.dev.close()


def _steps_in_cube(store: scan.ScanStore) -> list[int]:
    return sorted({int(r["step"]) for r in store.rows()})


# ------------------------------------------------------------------ healthy runs


@pytest.mark.parametrize("mode", ["tiny", "tiny_fine", "electrical", "continuous"])
def test_healthy_run_completes_safely(rig: Any, mode: str) -> None:
    with rig() as r:
        store, status = r.run(mode)
        assert status == "COMPLETE", store.meta["aborts"]
        r.safe()
        meta = store.meta
        assert meta["completed_step"] == len(meta["plan"]["steps"]) - 1
        assert _steps_in_cube(store) == list(range(len(meta["plan"]["steps"])))
        assert not r.overlaps, "two LEDs lit at once"
        assert r.max_rail_a_ms_per_min() <= 1000.0
        assert r.dev.duty is not None and not r.dev.duty.over_budget
        assert meta["interlocks"]["single_channel"] == "PASS"
        if mode != "electrical":
            assert meta["interlocks"]["light_while_moving"] == "PASS"
        if mode != "continuous":
            assert not r.light_while_moving, "an LED lit while the top moved"
        # capability checks without firmware support are SKIP with a reason (plan §8)
        assert set(meta["skipped_checks"]) == {"rail_monitor", "home_sensors"}
        assert meta["capabilities"]["mains_rejection"] is True
        assert r.dev.mains_hz == 0  # turned off again for the other tests
        states = {row["state"] for row in store.rows()}
        assert {"dark", "lit"} <= states
        if mode != "continuous":
            assert {"select_only", "ce_only", "wrong_rail", "coils_off"} <= states
        if mode == "tiny":
            assert any(s["state"] == "coils_moving" for s in meta["streams"])  # coil EMI (D2)


def test_rows_carry_height_and_net(rig: Any) -> None:
    with rig() as r:
        store, _ = r.run("tiny")
        lit = [row for row in store.rows() if row["state"] == "lit" and row["phase"] == "P2"]
        assert len(lit) == 3 * 16 * 2  # heights x holes x detectors
        heights = sorted({int(row["height_hs"]) for row in lit})
        assert heights == sorted(store.meta["plan"]["heights_down"])
        row = lit[0]
        assert float(row["net_mv"]) == pytest.approx(float(row["net_counts"]) * 0.125, abs=1e-3)
        assert float(row["height_mm"]) == pytest.approx(int(row["height_hs"]) / 4096, abs=1e-3)


def test_fine_mode_extras_bracket_the_optimum(rig: Any) -> None:
    with rig() as r:
        store, status = r.run("tiny_fine")
        assert status == "COMPLETE"
        extra = store.meta["extra_heights"]
        assert len(extra) == 3
        hd = store.meta["plan"]["heights_down"]
        step = abs(hd[1] - hd[0])
        assert max(extra) - min(extra) <= 2 * step


# ------------------------------------------------------------------ aborts


def test_operator_abort_while_paused(rig: Any) -> None:
    ctl = Control()

    def prog(p: dict[str, Any]) -> None:
        if p["status"] == "measured" and p["done"] >= 2:
            ctl.pause(True)
        if p["status"] == "paused":
            ctl.abort("operator abort (test)")

    with rig() as r:
        store, status = r.run("tiny", control=ctl, on_progress=prog)
        assert status == "INCOMPLETE"
        r.safe()
        assert store.meta["aborts"][-1]["reason"] == "operator abort (test)"
        assert store.meta["status"] == "INCOMPLETE"
        assert any(e["kind"] == "pause" for e in store.meta["events"])


def test_heartbeat_missing_pauses_then_continues(rig: Any) -> None:
    with rig() as r:
        ctl = Control(heartbeat_required=True, timeout_s=90, clock=r.dev.now)
        ctl.beat()

        def prog(p: dict[str, Any]) -> None:
            if p["status"] == "paused":
                r.safe()  # paused safely: everything off
                ctl.beat()  # the operator is back

        store, status = r.run("tiny", control=ctl, on_progress=prog)
        assert status == "COMPLETE"
        kinds = [e["kind"] for e in store.meta["events"]]
        assert "pause" in kinds and "continue" in kinds
        assert any(e.get("reason") == "operator heartbeat missing" for e in store.meta["events"])


def test_keyboard_interrupt_stops_safely(rig: Any) -> None:
    def prog(p: dict[str, Any]) -> None:
        if p["status"] == "measured" and p["done"] >= 1:
            raise KeyboardInterrupt

    with rig() as r:
        with pytest.raises(KeyboardInterrupt):
            r.run("tiny", on_progress=prog)
        r.safe()
        folder = next(r.tmp.glob("*_scan_tiny"))
        meta = scan.ScanStore.open(folder).meta
        assert meta["status"] == "INCOMPLETE" and "Ctrl-C" in meta["aborts"][-1]["reason"]


def test_adc_dropout_aborts(rig: Any) -> None:
    with rig("adc_dropout:30") as r:
        store, status = r.run("tiny")
        assert status == "INCOMPLETE"
        assert store.meta["aborts"][-1]["reason"].startswith("ADC dropout")
        r.safe()


def test_saturation_aborts(rig: Any, scfg: HwConfig, tmp_path: Path) -> None:
    data = copy.deepcopy(scfg.data)
    data["detectors"]["opt101"]["saturation_counts"] = 50
    low = parse_config(data, scfg.path)
    r = Rig(low, tmp_path, None, "white_ptfe")
    try:
        store, status = r.run("tiny")
        assert status == "INCOMPLETE" and "saturation" in store.meta["aborts"][-1]["reason"]
        r.safe()
        store2, status2 = r.run("tiny", abort_on_saturation="false")
        assert status2 == "COMPLETE", store2.meta["aborts"]
    finally:
        r.dev.close()


def test_preflight_refusals(rig: Any) -> None:
    with rig() as r:
        _, status = r.run("tiny", sample_id="banana")
        assert status == "INCOMPLETE"
        r.stage.forget()
        store, status = r.run("tiny")
        assert status == "INCOMPLETE" and "unknown" in store.meta["aborts"][-1]["reason"]
        assert store.meta["completed_step"] == -1  # nothing ran, nothing moved
    with rig() as r:
        sim = r.sim
        op = SimOperator(sim, {"chamber_clear": False})
        store, status = scan.start(r.dev, r.cfg, r.plan("tiny"), r.tmp, op, sample_id="empty")
        assert status == "INCOMPLETE" and "chamber" in store.meta["aborts"][-1]["reason"]
        assert all(m.physical == 0 for m in sim.motors)


# ------------------------------------------------------------------ resume and boots


def test_resume_after_abort(rig: Any) -> None:
    ctl = Control()

    def prog(p: dict[str, Any]) -> None:
        if p["status"] == "measured" and p["done"] >= 3:
            ctl.abort("stop for the resume test")

    with rig() as r:
        store, status = r.run("tiny", control=ctl, on_progress=prog)
        assert status == "INCOMPLETE"
        done = store.meta["completed_step"]
        assert 0 <= done < len(store.meta["plan"]["steps"]) - 1
        store2, status2 = scan.resume(r.dev, r.cfg, store.folder, SimOperator(r.sim))
        assert status2 == "COMPLETE", store2.meta["aborts"]
        n = len(store2.meta["plan"]["steps"])
        assert _steps_in_cube(store2) == list(range(n))
        # each step's rows were written exactly once
        per_step: dict[int, int] = {}
        for row in store2.rows():
            if row["state"] == "lit":
                per_step[int(row["step"])] = per_step.get(int(row["step"]), 0) + 1
        assert all(v == 32 for k, v in per_step.items() if k > 0 and k < n - 1)
        assert any(e["kind"] == "resume" for e in store2.meta["events"])
        r.safe()


def test_resume_refuses_a_changed_config(rig: Any, scfg: HwConfig) -> None:
    ctl = Control()
    ctl.abort("stop at once")
    with rig() as r:
        store, _ = r.run("tiny", control=ctl)
        data = copy.deepcopy(scfg.data)
        data["scan"]["sweep_n"] = 4
        changed = parse_config(data, scfg.path, "different-sha")
        _, status = scan.resume(r.dev, changed, store.folder, SimOperator(r.sim))
        assert status == "INCOMPLETE"
        assert "changed" in scan.ScanStore.open(store.folder).meta["aborts"][-1]["reason"]


def test_mid_run_boot_aborts_and_invalidates_the_position(rig: Any) -> None:
    with rig("mid_run_boot:120") as r:
        store, status = r.run("tiny")
        assert status == "INCOMPLETE"
        assert "BOOT" in store.meta["aborts"][-1]["reason"]
        assert not r.stage.valid  # the position is no longer trusted
        r.safe()
        # resuming is refused until the top is set again
        _, status2 = scan.resume(r.dev, r.cfg, store.folder, SimOperator(r.sim))
        assert status2 == "INCOMPLETE"
        assert "not trusted" in scan.ScanStore.open(store.folder).meta["aborts"][-1]["reason"]


def test_firmware_without_debug_states_skips_them(scfg: HwConfig, tmp_path: Path) -> None:
    """On 2.4.0 (no DBG STATE) the CE-only and wrong-rail states are SKIP with the reason."""
    data = copy.deepcopy(scfg.data)
    data["sim"]["firmware"] = "2.4.0"
    old = parse_config(data, scfg.path)
    r = Rig(old, tmp_path, None, "empty")
    try:
        store, status = r.run("electrical")
        assert status == "COMPLETE"
        assert "coupling_states" in store.meta["skipped_checks"]
        states = {row["state"] for row in store.rows()}
        assert "select_only" in states and not states & {"ce_only", "wrong_rail"}
    finally:
        r.dev.close()


def test_unexpected_error_stops_safely(rig: Any) -> None:
    """A full disk (or any bug) mid-run: everything off and stopped before it propagates."""
    with rig() as r:
        calls = {"n": 0}
        orig = scan.ScanStore.append_rows

        def failing(self: scan.ScanStore, rows: Any, *, completed_step: int) -> None:
            calls["n"] += 1
            if calls["n"] == 3:
                raise OSError(28, "No space left on device")
            orig(self, rows, completed_step=completed_step)

        scan.ScanStore.append_rows = failing  # type: ignore[method-assign]
        try:
            with pytest.raises(OSError):
                r.run("tiny")
        finally:
            scan.ScanStore.append_rows = orig  # type: ignore[method-assign]
        r.safe()
        folder = next(r.tmp.glob("*_scan_tiny"))
        meta = scan.ScanStore.open(folder).meta
        assert meta["status"] == "INCOMPLETE" and "No space left" in meta["aborts"][-1]["reason"]
