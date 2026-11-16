"""Scan planning and the run folder (LIO-SW-SCAN-001 §3, §4; milestone S2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lio.config import HwConfig
from lio.scan.plan import PlanError, ScanPlan, ScanSettings, build
from lio.scan.store import CUBE_FIELDS, ScanStore

pytestmark = [pytest.mark.unit]

TOP, BOTTOM, MARGIN = 0, -420017, 4096


def _plan(cfg: HwConfig, mode: str, **kw: object) -> ScanPlan:
    return build(cfg, mode, top_limit=TOP, bottom_limit=BOTTOM, top_margin=MARGIN, **kw)  # type: ignore[arg-type]


def test_every_configured_mode_plans(cfg: HwConfig) -> None:
    for mode in cfg.section.mapping("scan.modes"):
        p = _plan(cfg, mode, current=-1000)
        assert p.steps and p.steps[0].phase == "P1" and p.steps[-1].phase == "P4"
        assert [s.index for s in p.steps] == list(range(len(p.steps)))
        assert p.eta_s > 0
        for s in p.steps:  # the soft limits: never above the measured top, never below the bottom
            assert BOTTOM <= s.height <= TOP - MARGIN or p.static


def test_quick_down_and_back(cfg: HwConfig) -> None:
    p = _plan(cfg, "quick")
    down = [s for s in p.steps if s.phase == "P2"]
    up = [s for s in p.steps if s.phase == "P3"]
    assert [s.height for s in down] == p.heights_down
    assert down[0].height == TOP - MARGIN and down[-1].height == BOTTOM
    assert [s.height for s in up] == sorted(s.height for s in up)  # bottom first, going up
    assert {s.direction for s in down} == {"down"} and {s.direction for s in up} == {"up"}
    assert sum(s.hum for s in down) == len(range(0, len(down), p.settings.hum_every_k))
    assert p.steps[-1].height == TOP - MARGIN  # return_top


def test_reference_repeats_ride_the_up_pass(cfg: HwConfig) -> None:
    """Repeats at each reference height, from both sides, merged in height order."""
    p = _plan(cfg, "full")
    p3 = [s for s in p.steps if s.phase == "P3"]
    assert [s.height for s in p3] == sorted(s.height for s in p3)
    for h in p.ref_heights:
        reps = [(s.rep, s.direction) for s in p3 if s.height == h and s.rep]
        assert sorted(reps) == sorted(
            (r, d) for r in range(1, p.repeats + 1) for d in ("down", "up")
        )


def test_static_mode_needs_no_limits(cfg: HwConfig) -> None:
    p = build(cfg, "electrical", top_limit=None, bottom_limit=None, current=-5000)
    assert p.static and {s.height for s in p.steps} == {-5000}
    with pytest.raises(PlanError, match="limits"):
        build(cfg, "quick", top_limit=None, bottom_limit=-1000)


def test_overrides_are_typed_and_checked(cfg: HwConfig) -> None:
    s = ScanSettings.from_config(cfg, {"sweep_n": "4", "abort_on_saturation": "false"})
    assert s.sweep_n == 4 and s.abort_on_saturation is False
    assert ScanSettings.from_config(cfg).sweep_n == 2  # the default (S0 D5)
    assert ScanSettings.from_config(cfg).heartbeat_timeout_s == 90
    with pytest.raises(PlanError, match="unknown"):
        ScanSettings.from_config(cfg, {"nonsense": 1})
    with pytest.raises(PlanError, match="bad value"):
        ScanSettings.from_config(cfg, {"sweep_n": "many"})
    with pytest.raises(PlanError, match="unknown mode"):
        _plan(cfg, "nope")


def test_duty_prediction_within_budget(cfg: HwConfig) -> None:
    for mode in ("quick", "full", "fine"):
        p = _plan(cfg, mode)
        assert p.duty["max_on_ms_per_min_A"] <= p.duty["budget_A"]


def test_mm_from_the_lead_screw(cfg: HwConfig) -> None:
    p = _plan(cfg, "quick")
    assert p.mm(-4096) == pytest.approx(-1.0)  # M6 x 1.0, direct drive
    assert p.mm(BOTTOM) == pytest.approx(-102.5, abs=0.1)


def test_plan_round_trip(cfg: HwConfig) -> None:
    p = _plan(cfg, "fine")
    q = ScanPlan.from_dict(p.to_dict())
    assert q == p


def test_store_round_trip(tmp_path: Path) -> None:
    st = ScanStore.create(tmp_path, "quick", {"sample_id": "empty"})
    assert st.meta["status"] == "RUNNING" and st.meta["completed_step"] == -1
    st.append_rows([{"step": 0, "hole": 1, "state": "lit", "net_counts": 12.5, "extra": "x"}],
                   completed_step=0)  # fmt: skip
    st.append_rows([{"step": 1, "hole": 2, "state": "dark", "dark_counts": -3}], completed_step=1)
    st.save_stream("hum", t_us=[0, 2500, 5000], raw=[1, 2, 3], state="coils_off")
    st.abort("test abort", step=2)
    again = ScanStore.open(st.folder)
    rows = list(again.rows())
    assert [r["step"] for r in rows] == ["0", "1"] and list(rows[0]) == list(CUBE_FIELDS)
    assert rows[0]["net_counts"] == "12.5" and rows[1]["lit_counts"] == ""
    assert again.meta["completed_step"] == 1 and again.meta["status"] == "INCOMPLETE"
    assert again.meta["aborts"][0]["reason"] == "test abort"
    assert list(again.load_stream("hum")["raw"]) == [1, 2, 3]
    st2 = ScanStore.create(tmp_path, "quick", {})  # same second: a distinct folder
    assert st2.folder != st.folder
