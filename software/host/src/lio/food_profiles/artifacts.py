"""Safe model bundles, hashing, reports (no pickle/joblib)."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, cast

import numpy as np

from lio.food_profiles import PACKAGE_VERSION, SCHEMA_VERSION
from lio.food_profiles.schema import Recipe, finite_json


@dataclass
class BundleMeta:
    bundle_id: str
    kind: str
    recipe: dict[str, Any]
    created: str
    schema: int = SCHEMA_VERSION
    package_version: str = PACKAGE_VERSION
    synthetic: bool = False
    notes: str = ""
    extras: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "bundle_id": self.bundle_id,
            "kind": self.kind,
            "recipe": self.recipe,
            "created": self.created,
            "schema": self.schema,
            "package_version": self.package_version,
            "synthetic": self.synthetic,
            "notes": self.notes,
        }
        if self.extras:
            d["extras"] = self.extras
        return d


def write_bundle(
    out_dir: Path,
    *,
    kind: str,
    recipe: Recipe | dict[str, Any],
    arrays: dict[str, Any],
    payload: dict[str, Any] | None = None,
    bundle_id: str | None = None,
    synthetic: bool = False,
    notes: str = "",
    extras: dict[str, Any] | None = None,
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bid = bundle_id or out_dir.name
    recipe_dict = recipe.to_dict() if isinstance(recipe, Recipe) else recipe
    meta = BundleMeta(
        bundle_id=bid,
        kind=kind,
        recipe=recipe_dict,
        created=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        synthetic=synthetic,
        notes=notes,
        extras=extras,
    )
    (out_dir / "bundle.json").write_text(json.dumps(finite_json(meta.to_dict()), indent=2) + "\n")
    if payload is not None:
        (out_dir / "payload.json").write_text(json.dumps(finite_json(payload), indent=2) + "\n")
    # Flatten nested dicts of arrays into NPZ (allow_pickle=False)
    flat: dict[str, np.ndarray] = {}
    for k, v in arrays.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                flat[f"{k}__{kk}"] = np.asarray(vv)
        else:
            flat[k] = np.asarray(v)
    # NumPy stubs type **kwargs as bool|…; values here are arrays only.
    np.savez_compressed(out_dir / "arrays.npz", **cast(Any, flat))
    return out_dir


def load_bundle(path: Path) -> tuple[dict[str, Any], dict[str, np.ndarray], dict[str, Any] | None]:
    path = Path(path)
    meta = json.loads((path / "bundle.json").read_text())
    with np.load(path / "arrays.npz", allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    payload = None
    pp = path / "payload.json"
    if pp.exists():
        payload = json.loads(pp.read_text())
    return meta, arrays, payload


def verify_bundle(path: Path) -> dict[str, Any]:
    meta, arrays, payload = load_bundle(path)
    ok = True
    issues: list[str] = []
    if int(meta.get("schema", -1)) != SCHEMA_VERSION:
        issues.append(f"schema {meta.get('schema')} != {SCHEMA_VERSION}")
    if not (path / "arrays.npz").exists():
        ok = False
        issues.append("missing arrays.npz")
    # Spot-check no object arrays
    for k, v in arrays.items():
        if v.dtype == object:
            ok = False
            issues.append(f"object array {k}")
    return {
        "ok": ok and not issues,
        "bundle_id": meta.get("bundle_id"),
        "kind": meta.get("kind"),
        "n_arrays": len(arrays),
        "has_payload": payload is not None,
        "issues": issues,
        "synthetic": meta.get("synthetic"),
    }


def write_portable_report(
    out_dir: Path,
    *,
    title: str,
    sections: list[dict[str, Any]],
    embedded: dict[str, Any],
    synthetic: bool = False,
) -> Path:
    """Self-contained HTML: embedded JSON + inline JS, no localhost fetches."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data_json = json.dumps(finite_json(embedded), ensure_ascii=True)
    # Escape </script> in JSON
    data_json = data_json.replace("<", "\\u003c")
    syn = " [SYNTHETIC FIXTURE]" if synthetic else ""
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{escape(title)}{syn}</title>",
        "<style>",
        "body{font-family:ui-sans-serif,system-ui,sans-serif;margin:2rem;background:#f7f5f1;color:#1a1a1a}",
        "h1{font-size:1.4rem} h2{font-size:1.1rem;margin-top:1.5rem}",
        "pre{background:#fff;border:1px solid #ddd;padding:1rem;overflow:auto;font-size:12px}",
        ".banner{background:#fff3cd;border:1px solid #ffc107;"
        "padding:.5rem 1rem;margin-bottom:1rem}",
        "table{border-collapse:collapse} td,th{border:1px solid #ccc;padding:4px 8px}",
        "</style></head><body>",
    ]
    if synthetic:
        parts.append(
            "<div class='banner'><strong>SYNTHETIC</strong> - algorithm demonstration only; "
            "not measured LIO food-discrimination performance.</div>"
        )
    parts.append(f"<h1>{escape(title)}{syn}</h1>")
    parts.append("<p>Offline portable report - no network or dashboard API required.</p>")
    for sec in sections:
        parts.append(f"<h2>{escape(str(sec.get('heading', '')))}</h2>")
        if sec.get("html"):
            parts.append(str(sec["html"]))
        if sec.get("text"):
            parts.append(f"<p>{escape(str(sec['text']))}</p>")
    parts.append("<h2>Embedded data</h2><pre id='out'></pre>")
    parts.append(f"<script type='application/json' id='data'>{data_json}</script>")
    parts.append(
        "<script>"
        "const d=JSON.parse(document.getElementById('data').textContent);"
        "document.getElementById('out').textContent=JSON.stringify(d,null,2);"
        "</script>"
    )
    parts.append("</body></html>")
    html_path = out_dir / "report.html"
    html_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps(finite_json(embedded), indent=2) + "\n")
    return html_path


def export_zip(bundle_dir: Path, zip_path: Path) -> Path:
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in Path(bundle_dir).rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(bundle_dir).as_posix())
    return zip_path
