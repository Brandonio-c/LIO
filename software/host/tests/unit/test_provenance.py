"""M0 provenance, calibration, and related regression fixtures."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from lio.config import HwConfig, load_config
from lio.food_profiles.runs import _resolve_channel_map, open_run
from lio.scan.calibration import LEGACY_GAIN1_LSB_MV, resolve_calibration
from lio.scan.provenance import (
    AdcProvenance,
    Quantity,
    RfProvenance,
    ValidityReason,
    build_acquisition_snapshot,
    build_analysis_identity,
    quantity_eligibility,
    resolve_analysis_validity,
    seal_terminal_source,
)

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
RESULTS = REPO / "test_results"
CFG_PATH = REPO / "software" / "config" / "lio_hw.yaml"
CUBES = (
    "20261123-003133_scan_quick",
    "20261120-012619_scan_quick",
    "20261119-152512_scan_quick",
)


@pytest.fixture()
def cfg() -> HwConfig:
    return load_config(CFG_PATH)


def test_config_hash_mismatch_detected_as_string(cfg: HwConfig) -> None:
    assert isinstance(cfg.sha256, str) and len(cfg.sha256) == 64
    meta = {"config_sha256": "0" * 64}  # differs from current config
    _cmap, verified = _resolve_channel_map(cfg, meta)
    assert verified is False


def test_config_hash_match_verified_without_snapshot(cfg: HwConfig) -> None:
    meta = {"config_sha256": cfg.sha256}
    _cmap, verified = _resolve_channel_map(cfg, meta)
    assert verified is True


def test_analysis_identity_rejection_when_cube_hash_changes(
    cfg: HwConfig, tmp_path: Path
) -> None:
    src = RESULTS / "20261123-003133_scan_quick"
    if not (src / "cube.csv.gz").exists():
        pytest.skip("historical cube not present")
    # Copy minimal run folder
    dest = tmp_path / src.name
    dest.mkdir()
    cube_bytes = (src / "cube.csv.gz").read_bytes()
    (dest / "cube.csv.gz").write_bytes(cube_bytes)
    scan = json.loads((src / "scan.json").read_text())
    (dest / "scan.json").write_text(json.dumps(scan))
    from lio.food_profiles.runs import file_sha256

    identity = build_analysis_identity(
        cube_sha256=file_sha256(dest / "cube.csv.gz"),
        scan_sha256=file_sha256(dest / "scan.json"),
        calibration_id="gain=1:lsb=0.125",
        channel_map_sha256="x",
    ).to_dict()
    analysis = {
        "run_id": dest.name,
        "sample_id": scan.get("sample_id"),
        "identity": identity,
        "findings": [],
    }
    (dest / "analysis.json").write_text(json.dumps(analysis))
    run = open_run(dest, cfg)
    assert run.analysis_ok is True

    # Change cube content (valid gzip) → source-changed; analysis remains inspectable.
    import csv
    import io

    rows = list(csv.DictReader(gzip.open(dest / "cube.csv.gz", "rt", encoding="utf-8", newline="")))
    touched = False
    for row in rows:
        if row.get("net_counts") not in ("", None):
            row["net_counts"] = str(float(row["net_counts"]) + 1.0)
            touched = True
            break
    assert touched
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    with gzip.open(dest / "cube.csv.gz", "wt", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())
    run2 = open_run(dest, cfg)
    assert run2.analysis_ok is False
    assert ValidityReason.SOURCE_CHANGED.value in run2.analysis_reason
    assert run2.analysis is not None  # still inspectable


def test_calibration_gain1_gain2_volts_agree() -> None:
    """Synthetic: 100 counts at gain 1 = 12.5 mV; at gain 2 = 6.25 mV; same volts agree."""
    g1 = resolve_calibration(gain="1", lsb_mv=0.125)
    g2 = resolve_calibration(gain="2", lsb_mv=0.0625)
    assert g1.counts_to_mv(100) == pytest.approx(12.5)
    assert g2.counts_to_mv(100) == pytest.approx(6.25)
    # Same physical voltage: 12.5 mV
    c1 = 12.5 / 0.125
    c2 = 12.5 / 0.0625
    assert g1.counts_to_mv(c1) == pytest.approx(g2.counts_to_mv(c2))
    assert LEGACY_GAIN1_LSB_MV == 0.125
    unknown = resolve_calibration(gain="99")
    assert unknown.counts_to_mv(10) is None


def test_rf_not_invented_for_historical() -> None:
    cal = resolve_calibration(gain="1", detector="ingaas", rf=RfProvenance(None, "unknown"))
    assert cal.mv_to_eq_current_na(-41.234375) is None
    cal2 = resolve_calibration(
        gain="1", rf=RfProvenance(1.0e6, "declared"), detector="ingaas"
    )
    # -329.875 counts = -41.234375 mV → 41.234375 nA at 1 MΩ
    mv = cal2.counts_to_mv(-329.875)
    assert mv == pytest.approx(-41.234375)
    assert cal2.mv_to_eq_current_na(mv) == pytest.approx(41.234375)


def test_quantity_eligibility_unverified_a0_blocks_ingaas_current() -> None:
    rf = RfProvenance(1e6, "declared")
    q = quantity_eligibility(
        Quantity.EQ_CURRENT,
        detector="ingaas",
        lsb_mv=0.125,
        rf=rf,
        input_range="unverified",
    )
    assert not q.eligible
    counts = quantity_eligibility(
        Quantity.COUNTS, detector="ingaas", lsb_mv=None, input_range="unverified"
    )
    assert counts.eligible
    opt = quantity_eligibility(
        Quantity.EQ_CURRENT,
        detector="opt101",
        lsb_mv=0.125,
        rf=rf,
        input_range="unverified",
    )
    assert opt.eligible  # OPT101 not blocked by InGaAs A0 gate


def test_three_cubes_764_rows() -> None:
    for name in CUBES:
        path = RESULTS / name / "cube.csv.gz"
        if not path.exists():
            pytest.skip(f"missing {name}")
        with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
            # header + 764 data rows
            n = sum(1 for _ in f) - 1
        assert n == 764, f"{name} has {n} rows"


def test_nov23_h16_opt101_p2_nets() -> None:
    path = RESULTS / "20261123-003133_scan_quick" / "cube.csv.gz"
    if not path.exists():
        pytest.skip("missing Nov23 cube")
    import csv

    nets_down: list[tuple[float, float]] = []
    nets_up: dict[float, float] = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["hole"] != "16" or r["detector"] != "opt101" or r["state"] != "lit":
                continue
            h = float(r["height_hs"])
            net = float(r["net_counts"])
            if r["phase"] == "P2" and r["direction"] == "down":
                nets_down.append((h, net))
            elif r["phase"] == "P3" and r["direction"] == "up":
                nets_up[h] = net
    nets_down.sort()
    assert [n for _, n in nets_down] == [391, 360, 329, 301, 280, 258, 238, 228, 217]
    diffs = []
    for h, n_down in nets_down:
        if h in nets_up:
            diffs.append(nets_up[h] - n_down)
    # eight exact-height up-minus-down (P3 up − P2 down)
    assert len(diffs) == 8
    assert diffs == [2, 0, 1, 1, -1, 0, -3, -5]
    import numpy as np

    assert float(np.median(np.abs(diffs))) == 1.0
    assert max(abs(d) for d in diffs) == 5


def test_snapshot_and_seal_separate() -> None:
    snap = build_acquisition_snapshot(
        protocol_hash="abc",
        config_snapshot={"x": 1},
        config_sha256="0" * 64,
        channel_map_snapshot={"holes": {}},
        adc=AdcProvenance(gain="1", fsr_v=4.096, lsb_mv=0.125),
    )
    seal = seal_terminal_source(snap, raw_bytes=b"cube", terminal_meta={"status": "COMPLETE"})
    assert seal.manifest_hash == snap.manifest_hash()
    assert seal.raw_sha256 != seal.manifest_hash


def test_legacy_analysis_not_accepted_by_names_alone() -> None:
    ok, reason, _ = resolve_analysis_validity(
        {"run_id": "r1", "sample_id": "s1"},
        cube_sha256="a" * 64,
        scan_sha256="b" * 64,
        run_id="r1",
        sample_id="s1",
    )
    assert ok is False
    assert reason is ValidityReason.LEGACY_UNVERIFIED
