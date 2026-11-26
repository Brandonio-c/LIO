"""Resume across a config edit (owner 2026-11-26): compare what changed, not the hash."""

from __future__ import annotations

from pathlib import Path

import pytest

from lio.config import load_config
from lio.config_snapshots import resume_config_check, save_snapshot

pytestmark = pytest.mark.unit
SHIPPED = Path(__file__).resolve().parents[3] / "config" / "lio_hw.yaml"
RESULTS = Path(__file__).resolve().parents[4] / "test_results"


def _copy(tmp: Path) -> Path:
    p = tmp / "lio_hw.yaml"
    p.write_text(SHIPPED.read_text())
    return p


def test_grading_only_change_allows_resume(tmp_path: Path) -> None:
    p = _copy(tmp_path)
    old = load_config(p)
    assert save_snapshot(old) is not None
    p.write_text(p.read_text().replace("range_steps: 0", "range_steps: 331073", 1))
    new = load_config(p)
    ok, why, allowed = resume_config_check(new, old.sha256)
    assert ok and why == "" and allowed == ["thresholds.motion.travel.range_steps"]


def test_acquisition_change_refuses_resume(tmp_path: Path) -> None:
    p = _copy(tmp_path)
    old = load_config(p)
    save_snapshot(old)
    p.write_text(p.read_text().replace("  jog_speed: 300", "  jog_speed: 250", 1))
    ok, why, _ = resume_config_check(load_config(p), old.sha256)
    assert not ok and "scan.jog_speed" in why


def test_unknown_config_refuses_with_a_clear_reason(tmp_path: Path) -> None:
    cfg = load_config(_copy(tmp_path))
    ok, why, _ = resume_config_check(cfg, "0" * 64)
    assert not ok and "start a new scan" in why
    assert resume_config_check(cfg, cfg.sha256)[0]
    assert not resume_config_check(cfg, "")[0]  # nothing recorded: nothing to compare


def test_run_that_measured_nothing_is_not_judged() -> None:
    folder = RESULTS / "20261126-004656_scan_full"  # refused at step 0, never resumed
    if not (folder / "scan.json").exists():
        pytest.skip("missing run")
    from lio.scan.analysis import NOT_JUDGED, analyse

    a = analyse(folder, load_config(), write=False)
    assert a.verdict["verdict"] == NOT_JUDGED
    assert "before measuring any height" in a.verdict["reasons"][0]
