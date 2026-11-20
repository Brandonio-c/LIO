"""Scan analysis on synthetic data with known answers (LIO-SW-SCAN-001 §11; S3).

Runs are written through the real store (cube.csv.gz, npz streams) so the loader
is exercised too.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from lio.config import HwConfig
from lio.results import Status
from lio.scan.analysis import analyse, electrical, optics, system, trend
from lio.scan.analysis.data import Cube, Finding
from lio.scan.store import ScanStore

pytestmark = [pytest.mark.unit]

HEIGHTS = [round(-4000 - i * 4000) for i in range(9)]  # -4000 ... -36000
AMP = 6000.0  # optical amplitude of a healthy channel (shape = 1 at its peak)


def amp_of(hole: int) -> float:
    """Distinct LEDs: every hole a little brighter than the one before."""
    return AMP * (1 + 0.04 * hole)


def shape(h: float, peak: float = -30000, width: float = 9000, floor: float = 0.33) -> float:
    return floor + (1 - floor) * math.exp(-(((h - peak) / width) ** 2))


def write_run(
    root: Path,
    cfg: HwConfig,
    *,
    o: dict[tuple[int, str], float] | None = None,
    c_per_ma: dict[str, float] | None = None,
    dark: dict[str, float] | None = None,
    drift_per_h: float = 0.0,
    sample: str = "empty",
    both_ways: bool = True,
    hum_counts: float = 0.0,
    emi_sigma: float = 0.0,
    backlash: float = 0.0,
    step_loss: float = 0.0,
    leak: float = 0.0,
    gain: float = 1.0,
) -> Path:
    """A synthetic run: net = O·g(h_phys) + k·I_rail on the channels each detector sees.

    On the way up the stage sits ``backlash`` lower, and falls ``step_loss`` further
    behind over a full upward travel. ``leak``: dark rise at the bottom (linear below
    -20000). ``gain``: every optical amplitude scaled (a later, changed run)."""
    rng = np.random.default_rng(1)
    o = o or {}
    c_per_ma = c_per_ma or {"opt101": 0.0, "ingaas": 0.0}
    dark = dark or {"opt101": 200.0, "ingaas": 40.0}
    up = list(reversed(HEIGHTS[:-1])) if both_ways else []
    heights = HEIGHTS + up
    top, bottom = HEIGHTS[0], HEIGHTS[-1]
    steps = [{"index": i, "phase": "P2" if i < len(HEIGHTS) else "P3", "kind": "measure",
              "height": h, "direction": "down" if i < len(HEIGHTS) else "up", "rep": 0,
              "hum": False, "label": ""} for i, h in enumerate(heights)]  # fmt: skip
    plan = {"mode": "test", "top": top, "bottom": bottom, "heights_down": HEIGHTS,
            "heights_up": up, "steps": steps, "static": False, "continuous": False}  # fmt: skip
    st = ScanStore.create(root, "test", {"sample_id": sample, "status": "COMPLETE", "plan": plan})
    t = 0.0
    for step, h in enumerate(heights):
        phase = steps[step]["phase"]
        direction = steps[step]["direction"]
        hp = float(h)
        if direction == "up":
            hp -= backlash + step_loss * (h - bottom) / (top - bottom)
        rows: list[dict[str, Any]] = []
        for det in ("opt101", "ingaas"):
            rise = leak * min(1.0, max(0.0, (-20000 - h) / 16000))
            d = dark[det] + drift_per_h * t / 3600 + rise + rng.normal(0, 0.5)
            rows.append({"step": step, "phase": phase, "height_hs": h, "direction": direction,
                         "rep": 0, "hole": 0, "state": "dark", "detector": det,
                         "dark_counts": d, "t_s": t})  # fmt: skip
            for hole in range(1, 17):
                ch = cfg.channel(hole)
                cur = float(cfg.section.num(f"rails.{ch.rail}.current_ma"))
                amp = o.get((hole, det))
                if amp is None:
                    amp = amp_of(hole) if ch.expect_for(det) == "signal" else 0.0
                net = gain * amp * shape(hp) + c_per_ma[det] * cur + rng.normal(0, 1)
                rows.append({"step": step, "phase": phase, "height_hs": h,
                             "direction": direction, "rep": 0, "hole": hole, "state": "lit",
                             "detector": det, "dark_counts": d, "lit_counts": d + net,
                             "net_counts": net, "t_s": t, "settle_ms": 320})  # fmt: skip
        st.append_rows(rows, completed_step=step)
        t += 120
    for det in ("opt101", "ingaas"):  # hum: 3 bursts of 48 at 400 SPS, coils off and moving
        for state, extra in (("coils_off", 0.0), ("coils_moving", emi_sigma)):
            tt: list[int] = []
            vv: list[int] = []
            for b in range(3):
                t0 = b * 1.0 + 0.0037 * b
                for i in range(48):
                    ts = t0 + i * 0.0025
                    v = 100 + hum_counts * math.sin(2 * math.pi * 60 * ts + 0.3)
                    v += rng.normal(0, 2) + (rng.normal(0, extra) if extra else 0.0)
                    tt.append(round(ts * 1e6))
                    vv.append(round(v))
            st.save_stream(f"{state}_{det}", t_us=tt, raw=vv, state=state, detector=det)
    st.finish()
    return st.folder


def test_smooth_and_fwhm_on_a_known_peak() -> None:
    h = np.linspace(-60000, 0, 31)
    v = np.array([1000 * math.exp(-(((x + 30000) / 9000) ** 2) * math.log(2)) for x in h])
    s = optics.smooth(h, v)
    assert float(h[np.argmax(s)]) == pytest.approx(-30000, abs=2100)
    width, complete = optics.fwhm(h, s, 0.0)
    assert complete and width == pytest.approx(18000, rel=0.08)  # FWHM = 2 x 9000 by design
    w2, c2 = optics.fwhm(h[:12], s[:12], 0.0)  # cut before the far side
    assert not c2 and w2 is not None


def test_burst_fit_recovers_mains_amplitude() -> None:
    t = np.arange(48) * 0.0025
    v = 5 + 7 * np.sin(2 * math.pi * 60 * t + 1.0) + 2 * np.sin(2 * math.pi * 180 * t)
    _, amps, rs = electrical._burst_fit(t, v)
    assert amps[60.0] == pytest.approx(7, rel=0.02) and amps[180.0] == pytest.approx(2, rel=0.05)
    assert rs < 0.01


def test_blind_holes(cfg: HwConfig) -> None:
    assert electrical.blind_holes(cfg, "ingaas") == [1, 2, 3, 4, 5, 6, 7, 10, 11, 16]
    assert electrical.blind_holes(cfg, "opt101") == [12, 13, 14, 15, 16]


def test_healthy_synthetic_run_passes(cfg: HwConfig, tmp_path: Path) -> None:
    a = analyse(write_run(tmp_path, cfg), cfg)
    assert not a.flagged(), a.summary()
    st = a.context["optics"]["channels"]["ingaas"][13]
    assert st["h_opt"] in (-28000, -32000)  # the grid points either side of the -30000 peak
    assert st["O"] == pytest.approx(amp_of(13) * shape(st["h_opt"]), rel=0.01)
    assert (tmp_path / a.run_id / "analysis.json").exists()


def test_coupling_and_ground_shift_amplitude(cfg: HwConfig, tmp_path: Path) -> None:
    """k = 1.6 counts/mA on the InGaAs: C = 48 (rail A, 30 mA) and 72 (rail B, 45 mA)."""
    a = analyse(write_run(tmp_path, cfg, c_per_ma={"opt101": 0.0, "ingaas": 1.6}), cfg)
    c = a.context["electrical"]["coupling"]["ingaas"]["C"]
    assert c["A"] == pytest.approx(48, abs=1) and c["B"] == pytest.approx(72, abs=1)
    gs = a.get("elec/ingaas/ground_shift")
    assert gs.value == pytest.approx(1.6 * 0.125, rel=0.03) and gs.status == Status.FAIL
    assert gs.data["scales_with_current"] is True
    # the optical amplitude is still recovered on top of the coupling
    st = a.context["optics"]["channels"]["ingaas"][13]
    assert st["O"] == pytest.approx(amp_of(13) * shape(st["h_opt"]), rel=0.01)


def test_electrical_only_signature(cfg: HwConfig, tmp_path: Path) -> None:
    """15 Nov: flat ~60-90 counts on every InGaAs hole, no light."""
    o = {(h, "ingaas"): 0.0 for h in range(1, 17)}
    a = analyse(write_run(tmp_path, cfg, o=o, c_per_ma={"opt101": 0.0, "ingaas": 2.0}), cfg)
    assert a.get("optics/ingaas/electrical_only").status == Status.FAIL
    assert a.get("optics/ingaas/h13/response").status == Status.FAIL
    assert a.get("optics/opt101/electrical_only").status == Status.PASS


def test_plausibility_flags_a_visible_hole_on_the_wrong_detector(
    cfg: HwConfig, tmp_path: Path
) -> None:
    a = analyse(write_run(tmp_path, cfg, o={(16, "opt101"): 2000.0}), cfg)
    f = a.get("optics/opt101/h16/plausibility")
    # Hole 16 has no in-range detector: wrong LED is WARN (known, no spare part yet).
    assert f.status == Status.WARN and f.value == pytest.approx(2000, rel=0.05)


def test_dark_offset_and_equivalent_current(cfg: HwConfig, tmp_path: Path) -> None:
    # the rig's steady -21 mV (U5's own offset, 17 Nov) is within the range ...
    a = analyse(write_run(tmp_path / "rig", cfg, dark={"opt101": 200.0, "ingaas": -168.0}), cfg)
    f = a.get("elec/ingaas/dark_offset")
    assert f.status == Status.PASS and f.value == pytest.approx(-21, abs=0.2)
    assert f.data["i_eq_na"] == pytest.approx(21, abs=0.3)
    # ... a real leak (60 nA: -60 mV) is not
    a = analyse(write_run(tmp_path / "leak", cfg, dark={"opt101": 200.0, "ingaas": -480.0}), cfg)
    assert a.get("elec/ingaas/dark_offset").status == Status.FAIL


@pytest.mark.parametrize("both_ways", [True, False])
def test_drift_estimate(cfg: HwConfig, tmp_path: Path, both_ways: bool) -> None:
    """80 counts/h = 10 mV/h; a down-only run (time and height collinear) too."""
    a = analyse(write_run(tmp_path, cfg, drift_per_h=80.0, both_ways=both_ways), cfg)
    f = a.get("elec/opt101/drift")
    assert f.value == pytest.approx(10, abs=0.6) and f.status == Status.FAIL
    assert f.data["height_separated"] is both_ways


def test_hum_and_coil_emi(cfg: HwConfig, tmp_path: Path) -> None:
    folder = write_run(tmp_path, cfg, hum_counts=40.0, emi_sigma=30.0)
    a = analyse(folder, cfg)
    assert a.get("elec/opt101/coil_emi").status == Status.PASS  # stop-measure-move: no effect
    st = ScanStore.open(folder)
    st.meta["plan"]["continuous"] = True  # measuring while moving: it matters
    st.save_meta()
    a = analyse(folder, cfg)
    hum = a.get("elec/ingaas/hum")
    assert hum.value == pytest.approx(40 * 0.125, rel=0.1) and hum.status == Status.FAIL
    assert hum.data["mains_fraction"] > 0.9
    assert a.get("elec/opt101/coil_emi").status == Status.FAIL


def test_incomplete_and_static_runs_skip_what_they_lack(cfg: HwConfig, tmp_path: Path) -> None:
    st = ScanStore.create(tmp_path, "electrical", {"sample_id": "empty"})
    st.append_rows([{"step": 0, "phase": "P1", "height_hs": 0, "hole": 0, "state": "dark",
                     "detector": "ingaas", "dark_counts": 40, "t_s": 1, "rep": 0}],
                   completed_step=0)  # fmt: skip
    st.abort("test")
    a = analyse(st.folder, cfg)
    assert a.get("optics/curves").status == Status.SKIP
    assert a.get("elec/ingaas/drift").status == Status.SKIP
    assert a.get("elec/ingaas/dark_offset").status == Status.PASS
    assert a.status == "INCOMPLETE" and "incomplete_note" in a.context


def test_cube_curve_takes_first_visits_only(cfg: HwConfig, tmp_path: Path) -> None:
    c = Cube.open(write_run(tmp_path, cfg))
    cur = c.curve(13, "ingaas")
    assert list(cur.h) == sorted(HEIGHTS)
    up = c.curve(13, "ingaas", phase="P3")
    assert len(up) == len(HEIGHTS) - 1


# ------------------------------------------------------------------ S4


def test_backlash_and_step_loss_are_separated(cfg: HwConfig, tmp_path: Path) -> None:
    a = analyse(write_run(tmp_path / "b", cfg, backlash=1500), cfg)
    b, sl = a.get("mech/backlash"), a.get("mech/step_loss")
    assert b.value == pytest.approx(1500, abs=150) and b.status != Status.PASS
    assert abs(sl.value) < 300
    a = analyse(write_run(tmp_path / "s", cfg, step_loss=1600), cfg)
    b, sl = a.get("mech/backlash"), a.get("mech/step_loss")
    assert sl.value == pytest.approx(1600, abs=250) and sl.status != Status.PASS
    assert abs(b.value) < 300


def test_healthy_mechanics_read_zero(cfg: HwConfig, tmp_path: Path) -> None:
    a = analyse(write_run(tmp_path, cfg), cfg)
    assert abs(a.get("mech/backlash").value) < 3 * a.get("mech/backlash").data["se_d0"] + 50
    assert a.get("mech/repeatability").status == Status.SKIP  # no repeated visits here
    assert a.get("mech/settle").value == 320


def test_light_leak_onset(cfg: HwConfig, tmp_path: Path) -> None:
    a = analyse(write_run(tmp_path, cfg, leak=100.0), cfg)
    f = a.get("ambient/opt101/leak")
    assert f.status == Status.FAIL and f.value == pytest.approx(100, abs=5)
    assert -24000 <= f.data["onset_hs"] <= -20000  # the first height below -20000


def test_compare_localises_the_change(cfg: HwConfig, tmp_path: Path) -> None:
    def snap(**kw: Any) -> dict[str, Any]:
        root = tmp_path / str(len(list(tmp_path.iterdir())))
        a = analyse(write_run(root, cfg, **kw), cfg)
        return trend.snapshot(a.to_dict())

    base = snap()
    one = snap(o={(13, "ingaas"): amp_of(13) * 0.6})
    det = snap(o={(h, "ingaas"): amp_of(h) * 0.5 for h in (8, 9, 12, 13, 14)})
    allx = snap(gain=0.7)
    same = snap()
    f = trend.compare(base, one, cfg)[0]
    assert f.status == Status.FAIL and "holes [13]" in f.detail
    assert "every hole on ingaas" in trend.compare(base, det, cfg)[0].detail
    assert "both detectors" in trend.compare(base, allx, cfg)[0].detail
    assert trend.compare(base, same, cfg)[0].status == Status.PASS


def test_control_charts(cfg: HwConfig, tmp_path: Path) -> None:
    rng = np.random.default_rng(3)
    base = [{"run_id": f"r{i}", "sample_id": "empty",
             "metrics": {"elec/ingaas/dark_offset": 5.0 + rng.normal(0, 0.1)}} for i in range(6)]  # fmt: skip
    ok = {"run_id": "x", "sample_id": "empty", "metrics": {"elec/ingaas/dark_offset": 5.05}}
    bad = {"run_id": "y", "sample_id": "empty", "metrics": {"elec/ingaas/dark_offset": 7.0}}
    assert trend.control(ok, base, cfg)[0].status == Status.PASS
    f = trend.control(bad, base, cfg)[0]
    assert f.status == Status.WARN and "elec/ingaas/dark_offset" in f.data["out_of_limits"]
    assert trend.control(ok, base[:3], cfg)[0].status == Status.SKIP


def test_baseline_save_and_load(cfg: HwConfig, tmp_path: Path) -> None:
    folder = write_run(tmp_path / "runs", cfg)
    analyse(folder, cfg)
    out = trend.save_baseline(folder, tmp_path, cfg)
    loaded = trend.load_baselines(tmp_path, "empty")
    assert out.exists() and len(loaded) == 1
    assert (
        loaded[0]["O"]["ingaas"]["13"] > 1000 and "elec/ingaas/dark_offset" in loaded[0]["metrics"]
    )


def test_verdict_uses_the_t11_rules(cfg: HwConfig) -> None:
    def f(fid: str, st: Status) -> Finding:
        return Finding(fid, fid, st)

    ok = [f("system/link", Status.PASS), f("optics/ingaas/h13/response", Status.PASS)]
    assert system.verdict(cfg, ok)["verdict"] == "FUNCTIONAL"
    one = [*ok, f("optics/ingaas/h12/response", Status.FAIL)]
    assert system.verdict(cfg, one)["verdict"] == "DEGRADED"  # one channel
    link = [*ok, f("system/link", Status.FAIL)]
    assert system.verdict(cfg, link)["verdict"] == "NOT FUNCTIONAL"  # critical module
    unatt = [*ok, f("elec/ingaas/dark_offset", Status.FAIL)]
    assert system.verdict(cfg, unatt)["verdict"] == "NOT FUNCTIONAL"  # not tied to a channel
    table = {r["key"]: r["health"] for r in system.health_table(unatt)}
    assert table["ingaas"] == "ACT" and table["link"] == "OK" and table["motors"] == "n/a"
