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
from lio.scan.analysis import analyse, electrical, optics
from lio.scan.analysis.data import Cube
from lio.scan.store import ScanStore

pytestmark = [pytest.mark.unit]

HEIGHTS = [round(-4000 - i * 4000) for i in range(9)]  # -4000 ... -36000
AMP = 6000.0  # optical amplitude of a healthy channel (shape = 1 at its peak)


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
) -> Path:
    """A synthetic run: net = O·g(h) + k·I_rail on the channels each detector sees."""
    rng = np.random.default_rng(1)
    o = o or {}
    c_per_ma = c_per_ma or {"opt101": 0.0, "ingaas": 0.0}
    dark = dark or {"opt101": 200.0, "ingaas": 40.0}
    st = ScanStore.create(root, "test", {"sample_id": sample, "status": "COMPLETE"})
    heights = HEIGHTS + (list(reversed(HEIGHTS[:-1])) if both_ways else [])
    t = 0.0
    for step, h in enumerate(heights):
        phase = "P2" if step < len(HEIGHTS) else "P3"
        rows: list[dict[str, Any]] = []
        for det in ("opt101", "ingaas"):
            d = dark[det] + drift_per_h * t / 3600 + rng.normal(0, 0.5)
            rows.append({"step": step, "phase": phase, "height_hs": h, "direction": "down",
                         "rep": 0, "hole": 0, "state": "dark", "detector": det,
                         "dark_counts": d, "t_s": t})  # fmt: skip
            for hole in range(1, 17):
                ch = cfg.channel(hole)
                cur = float(cfg.section.num(f"rails.{ch.rail}.current_ma"))
                amp = o.get((hole, det))
                if amp is None:
                    amp = AMP if ch.expect_for(det) == "signal" else 0.0
                net = amp * shape(h) + c_per_ma[det] * cur + rng.normal(0, 1)
                rows.append({"step": step, "phase": phase, "height_hs": h, "direction": "down",
                             "rep": 0, "hole": hole, "state": "lit", "detector": det,
                             "dark_counts": d, "lit_counts": d + net, "net_counts": net,
                             "t_s": t})  # fmt: skip
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
    assert st["O"] == pytest.approx(AMP * shape(st["h_opt"]), rel=0.01)
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
    assert st["O"] == pytest.approx(AMP * shape(st["h_opt"]), rel=0.01)


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
    assert f.status == Status.FAIL and f.value == pytest.approx(2000, rel=0.05)


def test_dark_offset_and_equivalent_current(cfg: HwConfig, tmp_path: Path) -> None:
    a = analyse(write_run(tmp_path, cfg, dark={"opt101": 200.0, "ingaas": -168.0}), cfg)
    f = a.get("elec/ingaas/dark_offset")  # the bench state: -21 mV, ~21 nA into pin 2
    assert f.status == Status.FAIL and f.value == pytest.approx(-21, abs=0.2)
    assert f.data["i_eq_na"] == pytest.approx(21, abs=0.3)


@pytest.mark.parametrize("both_ways", [True, False])
def test_drift_estimate(cfg: HwConfig, tmp_path: Path, both_ways: bool) -> None:
    """80 counts/h = 10 mV/h; a down-only run (time and height collinear) too."""
    a = analyse(write_run(tmp_path, cfg, drift_per_h=80.0, both_ways=both_ways), cfg)
    f = a.get("elec/opt101/drift")
    assert f.value == pytest.approx(10, abs=0.6) and f.status == Status.FAIL
    assert f.data["height_separated"] is both_ways


def test_hum_and_coil_emi(cfg: HwConfig, tmp_path: Path) -> None:
    a = analyse(write_run(tmp_path, cfg, hum_counts=40.0, emi_sigma=30.0), cfg)
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
