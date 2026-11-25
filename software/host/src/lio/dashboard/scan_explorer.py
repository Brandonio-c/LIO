"""Dashboard adapters for offline food-profile Explore / Compare / gallery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lio.food_profiles.metadata import (
    RunAnnotation,
    create_dataset,
    list_datasets,
    load_dataset,
)
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


REFERENCE_SAMPLES = {
    "empty": "empty chamber",
    "white_ptfe": "white reference (PTFE)",
    "black_cup": "black reference (cup)",
}


def label_run(run: dict[str, Any], food_names: dict[str, str] | None = None) -> dict[str, Any]:
    """What a run measured, in words (owner 2026-11-25).

    ``kind``: ``food`` (sample is a food-library code), ``reference`` (empty chamber,
    white or black reference), ``protocol`` (stationary fixed-N run) or ``other``.
    ``food_label``: the library name for a food code ("Citrucel orange"), the
    reference's name, or the sample id. A run's own ``food_label`` (if recorded) wins.
    """
    sid = str(run.get("sample_id") or "")
    names = food_names or {}
    if str(run.get("mode") or "") == "protocol":
        kind = "protocol"
    elif sid.startswith("LIO-F-"):
        kind = "food"
    elif sid in REFERENCE_SAMPLES:
        kind = "reference"
    else:
        kind = "other"
    if run.get("food_label"):
        label = str(run["food_label"])
    elif kind == "food":
        label = names.get(sid) or sid
    elif sid in REFERENCE_SAMPLES:
        label = REFERENCE_SAMPLES[sid]
    else:
        label = sid or "unlabelled"
    return {
        **run,
        "kind": kind,
        "food_label": label,
        "sample_code": sid if kind == "food" else None,
    }


def api_list_runs(results_root: Path, food_names: dict[str, str] | None = None) -> dict[str, Any]:
    runs = [label_run(r, food_names) for r in discover_runs(results_root)]
    return {"runs": runs, "datasets": list_datasets(results_root)}


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


def api_init_dataset(
    results_root: Path,
    run_ids: list[str] | None = None,
    food_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """A dataset of height scans, each annotated with what it measured.

    Stationary protocol runs are left out (a different acquisition, not a height
    profile). Food runs get ``food_label`` = the library name and ``sample_code``;
    references keep their reference label, so the Food Map groups by food.
    """
    runs = [label_run(r, food_names) for r in discover_runs(results_root)]
    if run_ids:
        want = set(run_ids)
        runs = [r for r in runs if r["run_id"] in want or r["folder"] in want]
    runs = [r for r in runs if r["kind"] != "protocol" and r.get("status") == "COMPLETE"]
    if not runs:
        raise FileNotFoundError("no complete height scans to put in a dataset")
    folders = [Path(results_root) / r["folder"] for r in runs]
    annotations = {
        str(r["run_id"]): RunAnnotation(
            run_id=str(r["run_id"]),
            food_label=str(r["food_label"]),
            product_id=r.get("sample_code"),  # the food-library code (LIO-F-...)
            notes=f"kind={r['kind']}; label from the food library",
        )
        for r in runs
    }
    ds = create_dataset(
        results_root,
        folders,
        annotations=annotations,
        synthetic=any(r.get("synthetic") for r in runs),
        notes="dashboard-created; labels from the food library",
    )
    foods = sorted({r["food_label"] for r in runs if r["kind"] == "food"})
    return {
        "dataset_id": ds.dataset_id,
        "n_runs": len(ds.run_ids),
        "foods": foods,
        "references": sum(1 for r in runs if r["kind"] == "reference"),
    }
