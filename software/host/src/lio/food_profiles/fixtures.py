"""Labeled synthetic scan folders for algorithm tests (not measured LIO data)."""

from __future__ import annotations

import gzip
import io
import json
from pathlib import Path
from typing import Any

import numpy as np

from lio.scan.store import CUBE_FIELDS

# Approximate current map: OPT101 signal 1-11; InGaAs 8,9,12-14 signal, 15 weak.
OPT101_SIGNAL = set(range(1, 12))
INGAAS_SIGNAL = {8, 9, 12, 13, 14}
INGAAS_WEAK = {15}


def _expect(hole: int, det: str) -> str:
    if det == "opt101":
        return "signal" if hole in OPT101_SIGNAL else "none"
    if hole in INGAAS_SIGNAL:
        return "signal"
    if hole in INGAAS_WEAK:
        return "weak"
    return "none"


def _channel_snapshot() -> dict[str, Any]:
    holes = {}
    for h in range(1, 17):
        label = {1: "white", 2: "pink"}.get(h, f"λ{h}")
        holes[str(h)] = {
            "label": label,
            "wavelength_nm": 400 + 20 * h if h > 2 else None,
            "broadband": h in (1, 2),
            "expect": {"opt101": _expect(h, "opt101"), "ingaas": _expect(h, "ingaas")},
        }
    return {"holes": holes, "verified": True, "source": "synthetic_fixture"}


def _net(food: str, hole: int, det: str, height: float, prep: int, noise: float) -> float:
    """Deterministic foodxholexheight response with preparation offset."""
    if _expect(hole, det) == "none":
        return 0.0
    base = {"A": 120.0, "B": 80.0, "C": 160.0}.get(food, 100.0)
    spectral = 10.0 * np.sin(0.4 * hole + (0.2 if det == "ingaas" else 0.0))
    # Distinct height modes for fPCA recovery
    mode = 25.0 * np.sin(2 * np.pi * height / 40000.0 + (0.5 if food == "B" else 0.0))
    if food == "C":
        mode += 15.0 * np.cos(2 * np.pi * height / 20000.0)
    prep_off = 5.0 * prep
    return float(base + spectral + mode + prep_off + noise)


def write_synthetic_run(
    root: Path,
    *,
    run_name: str,
    food: str,
    preparation: int,
    heights: list[float] | None = None,
    with_analysis: bool = True,
    irregular: bool = False,
    n_gzip_members: int = 2,
    seed: int = 0,
) -> Path:
    """Create one labeled synthetic ``*_scan_*`` folder."""
    root = Path(root)
    folder = root / run_name
    folder.mkdir(parents=True, exist_ok=True)
    # Dense enough for fPCA with default max_gap_hs=5000
    heights = list(
        heights or [0.0, 5000.0, 10000.0, 15000.0, 20000.0, 25000.0, 30000.0, 35000.0, 40000.0]
    )
    if irregular:
        heights = [0.0, 5000.0, 12000.0, 20000.0, 40000.0]
    rng = np.random.default_rng(seed)
    steps = []
    step_i = 0
    for h in heights:
        steps.append(
            {
                "index": step_i,
                "kind": "measure",
                "phase": "P2",
                "height_hs": h,
                "direction": "down",
                "rep": 0,
            }
        )
        step_i += 1
    # Extra non-measure step so kind filtering is exercised
    steps.append({"index": step_i, "kind": "settle", "phase": "P2", "height_hs": heights[-1]})

    meta = {
        "run_id": run_name,
        "sample_id": f"SYN-{food}-P{preparation}",
        "mode": "quick_down",
        "status": "COMPLETE",
        "started": "2026-01-01T12:00:00+00:00",
        "finished": "2026-01-01T12:05:00+00:00",
        "completed_step": len(steps) - 1,
        "synthetic": True,
        "synthetic_label": "LIO food_profiles algorithm fixture - not measured data",
        "food_label": food,
        "preparation_id": f"prep-{food}-{preparation}",
        "lot_id": f"lot-{food}",
        "channel_map_snapshot": _channel_snapshot(),
        "plan": {"mode": "quick_down", "steps": steps},
        "streams": [],
        "events": [],
        "aborts": [],
        "answers": {},
        "phases": {},
        "rows": 0,
    }
    (folder / "scan.json").write_text(json.dumps(meta, indent=1) + "\n")

    rows: list[dict[str, Any]] = []
    for st in steps:
        if st["kind"] != "measure":
            continue
        h = float(st["height_hs"])  # type: ignore[arg-type]
        for hole in range(1, 17):
            for det in ("opt101", "ingaas"):
                noise = float(rng.normal(0, 1.0))
                net = _net(food, hole, det, h, preparation, noise)
                dark = 50.0
                lit = dark + net
                rows.append(
                    {
                        "run_id": run_name,
                        "step": st["index"],
                        "phase": "P2",
                        "height_hs": h,
                        "height_mm": h / 1000.0,
                        "direction": "down",
                        "rep": 0,
                        "hole": hole,
                        "state": "lit",
                        "detector": det,
                        "dark_counts": dark,
                        "lit_counts": lit,
                        "net_counts": net,
                        "net_mv": net * 0.125,
                        "t_s": 0.0,
                        "duty_wait_ms": 0,
                        "settle_ms": 10,
                        "n": 4,
                    }
                )

    # Multi-member gzip: split rows across members
    n_members = max(1, n_gzip_members)
    chunk = max(1, len(rows) // n_members)
    cube = folder / "cube.csv.gz"
    with open(cube, "wb") as out_f:
        for mi in range(n_members):
            part = rows[mi * chunk : (mi + 1) * chunk] if mi < n_members - 1 else rows[mi * chunk :]
            if not part and mi > 0:
                continue
            buf = io.StringIO()
            # header only on first member
            if mi == 0:
                buf.write(",".join(CUBE_FIELDS) + "\n")
            for r in part:
                buf.write(",".join(str(r.get(k, "")) for k in CUBE_FIELDS) + "\n")
            with gzip.GzipFile(fileobj=out_f, mode="wb", mtime=0) as gz:
                gz.write(buf.getvalue().encode("utf-8"))

    meta["rows"] = len(rows)
    (folder / "scan.json").write_text(json.dumps(meta, indent=1) + "\n")

    if with_analysis:
        findings = []
        for det in ("opt101", "ingaas"):
            findings.append(
                {
                    "id": f"elec/{det}/coupling",
                    "data": {"C": 2.0 if det == "opt101" else 1.5},
                }
            )
            for hole in range(1, 17):
                if _expect(hole, det) == "none":
                    continue
                o_val = _net(food, hole, det, float(heights[len(heights) // 2]), preparation, 0.0)
                findings.append(
                    {
                        "id": f"optics/{det}/h{hole:02d}/response",
                        "data": {"O": o_val},
                    }
                )
        analysis = {
            "run_id": run_name,
            "sample_id": meta["sample_id"],
            "mode": "quick_down",
            "status": "COMPLETE",
            "synthetic": True,
            "findings": findings,
            "health": [],
            "verdict": None,
            "context": {"electrical": {"coupling": {"opt101": {"C": 2.0}, "ingaas": {"C": 1.5}}}},
        }
        (folder / "analysis.json").write_text(json.dumps(analysis, indent=1) + "\n")

    # Compact stream for lazy inspection
    streams = folder / "streams"
    streams.mkdir(exist_ok=True)
    t_us = np.arange(0, 1000, 10, dtype=np.int64)
    raw = (100 + rng.integers(-5, 5, size=t_us.shape)).astype(np.int32)
    np.savez_compressed(streams / "dark_long.npz", t_us=t_us, raw=raw)
    meta["streams"] = [{"name": "dark_long", "file": "streams/dark_long.npz", "synthetic": True}]
    (folder / "scan.json").write_text(json.dumps(meta, indent=1) + "\n")
    return folder


def build_fixture_library(root: Path) -> dict[str, Any]:
    """Multi-food, multi-prep synthetic library with known modes."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    # Foods A/B/C x 2 preparations x 2 technical repeats
    seed = 1
    for food in ("A", "B", "C"):
        for prep in (1, 2):
            for _rep in (1, 2):
                name = f"20260101-12000{seed}_scan_quick_down"
                write_synthetic_run(
                    root,
                    run_name=name,
                    food=food,
                    preparation=prep,
                    with_analysis=True,
                    n_gzip_members=2,
                    seed=seed,
                )
                created.append(name)
                seed += 1
    # One run missing analysis
    write_synthetic_run(
        root,
        run_name="20260101-12999_scan_quick_down",
        food="A",
        preparation=1,
        with_analysis=False,
        seed=99,
    )
    created.append("20260101-12999_scan_quick_down")
    # Irregular heights
    write_synthetic_run(
        root,
        run_name="20260101-12998_scan_quick_down",
        food="B",
        preparation=1,
        irregular=True,
        seed=98,
    )
    created.append("20260101-12998_scan_quick_down")
    manifest = {
        "synthetic": True,
        "label": "LIO food_profiles synthetic fixture library",
        "n_runs": len(created),
        "runs": created,
        "note": "Not measured instrument data; for algorithm/regression tests only.",
    }
    (root / "SYNTHETIC_README.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
