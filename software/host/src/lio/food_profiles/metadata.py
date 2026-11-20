"""Dataset manifests and preparation / lot annotations."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lio.food_profiles import PACKAGE_VERSION, SCHEMA_VERSION
from lio.food_profiles.runs import file_sha256


@dataclass
class RunAnnotation:
    run_id: str
    food_label: str | None = None
    product_id: str | None = None
    parent_material_id: str | None = None
    lot_id: str | None = None
    preparation_id: str | None = None
    repeat_type: str | None = None  # same_cup | reload | repack | independent
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Dataset:
    dataset_id: str
    results_root: str
    run_ids: list[str]
    run_hashes: dict[str, dict[str, str]]
    annotations: dict[str, dict[str, Any]] = field(default_factory=dict)
    created: str = ""
    schema: int = SCHEMA_VERSION
    package_version: str = PACKAGE_VERSION
    synthetic: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Dataset:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def new_dataset_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def profile_sets_root(results_root: Path) -> Path:
    return Path(results_root) / "profile_sets"


def profile_analyses_root(results_root: Path) -> Path:
    return Path(results_root) / "profile_analyses"


def create_dataset(
    results_root: Path,
    run_folders: list[Path],
    *,
    annotations: dict[str, RunAnnotation] | None = None,
    notes: str = "",
    synthetic: bool = False,
    dataset_id: str | None = None,
) -> Dataset:
    """Immutable snapshot of selected runs + hashes (content identity)."""
    results_root = Path(results_root)
    ds_id = dataset_id or new_dataset_id()
    run_ids: list[str] = []
    hashes: dict[str, dict[str, str]] = {}
    for folder in run_folders:
        folder = Path(folder)
        scan = folder / "scan.json"
        cube = folder / "cube.csv.gz"
        if not scan.exists() or not cube.exists():
            raise FileNotFoundError(f"incomplete run folder: {folder}")
        meta = json.loads(scan.read_text())
        rid = str(meta.get("run_id", folder.name))
        run_ids.append(rid)
        entry = {"scan": file_sha256(scan), "cube": file_sha256(cube), "folder": folder.name}
        ap = folder / "analysis.json"
        if ap.exists():
            entry["analysis"] = file_sha256(ap)
        hashes[rid] = entry
    ann = {
        k: (v.to_dict() if isinstance(v, RunAnnotation) else v)
        for k, v in (annotations or {}).items()
    }
    ds = Dataset(
        dataset_id=ds_id,
        results_root=str(results_root.resolve()),
        run_ids=run_ids,
        run_hashes=hashes,
        annotations=ann,
        created=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        synthetic=synthetic,
        notes=notes,
    )
    out = profile_sets_root(results_root) / ds_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "dataset.json").write_text(json.dumps(ds.to_dict(), indent=2) + "\n")
    (out / "annotations.json").write_text(json.dumps(ann, indent=2) + "\n")
    return ds


def load_dataset(results_root: Path, dataset_id: str) -> Dataset:
    path = profile_sets_root(results_root) / dataset_id / "dataset.json"
    return Dataset.from_dict(json.loads(path.read_text()))


def list_datasets(results_root: Path) -> list[dict[str, Any]]:
    root = profile_sets_root(results_root)
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.iterdir()):
        dj = p / "dataset.json"
        if dj.exists():
            d = json.loads(dj.read_text())
            out.append(
                {
                    "dataset_id": d.get("dataset_id", p.name),
                    "n_runs": len(d.get("run_ids") or []),
                    "created": d.get("created"),
                    "synthetic": d.get("synthetic"),
                    "notes": d.get("notes"),
                }
            )
    return out


def annotate_run(dataset: Dataset, results_root: Path, annotation: RunAnnotation) -> Dataset:
    """Create a new dataset version with updated annotations (immutable)."""
    ann = dict(dataset.annotations)
    ann[annotation.run_id] = annotation.to_dict()
    folders = []
    for rid in dataset.run_ids:
        folder_name = dataset.run_hashes[rid]["folder"]
        folders.append(Path(results_root) / folder_name)
    return create_dataset(
        results_root,
        folders,
        annotations={k: RunAnnotation(**v) if isinstance(v, dict) else v for k, v in ann.items()},
        notes=dataset.notes,
        synthetic=dataset.synthetic,
    )


def resolve_run_folder(results_root: Path, dataset: Dataset, run_id: str) -> Path:
    info = dataset.run_hashes.get(run_id)
    if not info:
        raise KeyError(run_id)
    folder = Path(results_root) / info["folder"]
    if not folder.exists():
        # Content may have moved; search by run_id
        for p in Path(results_root).iterdir():
            if p.is_dir() and (p / "scan.json").exists():
                meta = json.loads((p / "scan.json").read_text())
                if meta.get("run_id") == run_id:
                    return p
        raise FileNotFoundError(run_id)
    return folder
