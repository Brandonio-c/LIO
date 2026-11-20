"""Dashboard adapters for offline food-profile Explore / Compare / gallery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lio.food_profiles.metadata import create_dataset, list_datasets, load_dataset
from lio.food_profiles.pipeline import compare_runs_payload, gallery_payload
from lio.food_profiles.runs import (
    curve_payload,
    discover_runs,
    findings_payload,
    heatmap_payload,
    load_stream,
    open_run,
    stream_index,
)
from lio.food_profiles.schema import BUILTIN_RECIPES, DEFAULT_SELECTION


def _resolve_folder(results_root: Path, run_id: str) -> Path:
    root = Path(results_root)
    direct = root / run_id
    if (direct / "scan.json").exists():
        return direct
    for p in root.iterdir():
        if not p.is_dir():
            continue
        sj = p / "scan.json"
        if not sj.exists():
            continue
        import json

        meta = json.loads(sj.read_text())
        if meta.get("run_id") == run_id or p.name == run_id:
            return p
    raise FileNotFoundError(run_id)


def api_list_runs(results_root: Path) -> dict[str, Any]:
    return {"runs": discover_runs(results_root), "datasets": list_datasets(results_root)}


def api_run_summary(results_root: Path, run_id: str) -> dict[str, Any]:
    run = open_run(_resolve_folder(results_root, run_id))
    return {
        "run_id": run.run_id,
        "sample_id": run.sample_id,
        "status": run.meta.get("status"),
        "mode": run.meta.get("mode"),
        "synthetic": bool(run.meta.get("synthetic")),
        "channel_map_verified": run.channel_map_verified,
        "analysis_ok": run.analysis_ok,
        "analysis_reason": run.analysis_reason,
        "n_rows": len(run.rows),
        "streams": stream_index(run),
        "selection_default": dict(DEFAULT_SELECTION),
        "recipes": list(BUILTIN_RECIPES),
    }


def api_heatmap(results_root: Path, run_id: str, detector: str) -> dict[str, Any]:
    run = open_run(_resolve_folder(results_root, run_id))
    return heatmap_payload(run, detector)


def api_curve(results_root: Path, run_id: str, hole: int, detector: str) -> dict[str, Any]:
    run = open_run(_resolve_folder(results_root, run_id))
    return curve_payload(run, hole, detector)


def api_findings(results_root: Path, run_id: str) -> dict[str, Any]:
    run = open_run(_resolve_folder(results_root, run_id))
    return findings_payload(run)


def api_stream(results_root: Path, run_id: str, stream_id: str) -> dict[str, Any]:
    run = open_run(_resolve_folder(results_root, run_id))
    return load_stream(run, stream_id)


def api_compare(results_root: Path, dataset_id: str, a: str, b: str) -> dict[str, Any]:
    ds = load_dataset(results_root, dataset_id)
    return compare_runs_payload(results_root, ds, a, b)


def api_gallery(results_root: Path, dataset_id: str) -> dict[str, Any]:
    ds = load_dataset(results_root, dataset_id)
    return gallery_payload(results_root, ds)


def api_init_dataset(results_root: Path, run_ids: list[str] | None = None) -> dict[str, Any]:
    runs = discover_runs(results_root)
    if run_ids:
        want = set(run_ids)
        runs = [r for r in runs if r["run_id"] in want or r["folder"] in want]
    folders = [Path(results_root) / r["folder"] for r in runs]
    ds = create_dataset(
        results_root,
        folders,
        synthetic=any(r.get("synthetic") for r in runs),
        notes="dashboard-created",
    )
    return {"dataset_id": ds.dataset_id, "n_runs": len(ds.run_ids)}
