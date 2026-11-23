"""Versioned derived analyses under a dedicated root (M0/M6 / remediation R2-R4).

Historical run folders stay untouched. New products are content-addressed under
``derived-out`` with analysis identity (source hashes, calibration, estimator).
Same-ID/different-content is a conflict error, never an overwrite (D08).
Legacy ``--derived-out`` must not rewrite source ``analysis.json`` (D09).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lio.config import HwConfig
from lio.food_profiles.runs import file_sha256
from lio.scan.analysis.coupling import estimate_coupling, leave_one_control_out
from lio.scan.analysis.data import Cube
from lio.scan.analysis.uncertainty import (
    block_drive_response,
    group_fixed_position_blocks,
)
from lio.scan.calibration import resolve_calibration
from lio.scan.provenance import (
    AnalysisIdentityConflict,
    build_analysis_identity,
    content_hash,
)
from lio.scan.provenance import (
    file_sha256 as prov_file_sha256,
)
from lio.scan.store import ScanStore
from lio.scan.targets import named_objective, primary_swir_objective


def derived_root(path: Path | str) -> Path:
    return Path(path)


def list_derived(root: Path | str, run_id: str | None = None) -> list[dict[str, Any]]:
    """List derived analyses. Never opens USB; saved-data views only."""
    root = Path(root)
    if not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(root.glob("**/analysis.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if run_id and str(data.get("run_id")) != run_id and run_id not in str(p):
            continue
        out.append(summarize_derived(data, path=p))
    return out


def summarize_derived(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    """Signed summary for dashboard/CLI: model, coupling, eligibility notes.

    Explicitly separates historical recorded verdict vs current model output vs
    quantitative eligibility. An h8/h9 SNR PASS must not imply h12-h15 OK.
    """
    verdict = data.get("verdict") or {}
    coupling = data.get("coupling") or {}
    estimates = data.get("estimates") or {}
    eligibility_notes = [
        "h8/h9 SNR PASS (if present) does not certify h12-h15",
        "historical recorded verdict ≠ current model output ≠ quantitative eligibility",
        "saved-data view: no USB / device open",
    ]
    holes_with_estimates = sorted(
        {k.split(":h")[-1] for k in estimates if ":h" in k}
    )
    recorded = data.get("recorded_verdict") or data.get("historical_verdict")
    return {
        "analysis_id": data.get("analysis_id") or (path.parent.name if path else None),
        "path": None if path is None else str(path),
        "model": data.get("model"),
        "run_id": data.get("run_id"),
        "status": data.get("status"),
        "identity": data.get("identity"),
        "target_selection_id": data.get("target_selection_id")
        or (data.get("target_selection") or {}).get("selection_id"),
        "signed_summary": {
            "model_verdict": verdict.get("verdict"),
            "model_reasons": list(verdict.get("reasons") or []),
            "historical_recorded_verdict": recorded,
            "coupling_models": {
                det: (c.get("model") if isinstance(c, dict) else None)
                for det, c in coupling.items()
            },
            "holes_with_estimates": holes_with_estimates,
            "eligibility_notes": eligibility_notes,
            "c_sensitivity": data.get("c_sensitivity") or coupling.get("sensitivity"),
        },
        "coupling": coupling,
        "eligibility_notes": eligibility_notes,
    }


def numerical_observations(
    run_folder: Path | str,
    *,
    hole: int | None = None,
    detector: str | None = None,
    phase: str | None = None,
    block: int | None = None,
    condition_id: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Signed dark/lit/net rows with filters for CLI/report/UI (D19). Offline only."""
    from lio.scan.store import ScanStore

    store = ScanStore.open(Path(run_folder))
    rows_out: list[dict[str, Any]] = []
    for r in store.rows():
        try:
            if hole is not None and int(r.get("hole") or -1) != int(hole):
                continue
            if detector is not None and str(r.get("detector") or "") != detector:
                continue
            if phase is not None and str(r.get("phase") or "") != phase:
                continue
            if block is not None:
                rep = r.get("rep")
                rep_i = -1 if rep in ("", None) else int(rep)
                if rep_i != int(block):
                    continue
            if condition_id is not None and str(r.get("condition_id") or "") != condition_id:
                continue
            dark = r.get("dark_counts")
            lit = r.get("lit_counts")
            net_raw = r.get("net_counts")
            net_f: float | None
            if net_raw in ("", None) and dark not in ("", None) and lit not in ("", None):
                net_f = float(lit) - float(dark)
            elif net_raw in ("", None):
                net_f = None
            else:
                net_f = float(net_raw)
            rows_out.append(
                {
                    "hole": r.get("hole"),
                    "detector": r.get("detector"),
                    "phase": r.get("phase"),
                    "block": r.get("rep"),
                    "condition_id": r.get("condition_id"),
                    "dark_counts": None if dark in ("", None) else float(dark),
                    "lit_counts": None if lit in ("", None) else float(lit),
                    "net_counts": net_f,
                    "signed": True,
                }
            )
        except (TypeError, ValueError):
            continue
        if len(rows_out) >= limit:
            break
    # Paired contrasts: mean lit-dark when both present.
    contrasts: dict[str, float] = {}
    by_key: dict[str, list[float]] = {}
    for row in rows_out:
        if row["net_counts"] is None:
            continue
        key = f"{row['detector']}:h{row['hole']}"
        by_key.setdefault(key, []).append(float(row["net_counts"]))
    for key, vals in by_key.items():
        contrasts[key] = float(sum(vals) / len(vals))
    meta = store.meta
    return {
        "run_id": store.run_id,
        "n": len(rows_out),
        "rows": rows_out,
        "contrasts": contrasts,
        "filters": {
            "hole": hole,
            "detector": detector,
            "phase": phase,
            "block": block,
            "condition_id": condition_id,
        },
        "target_selection_id": meta.get("target_selection_id"),
        "eligibility_notes": [
            "h8/h9 SNR scope does not certify h12-h15",
            "historical recorded verdict ≠ current model ≠ quantitative eligibility",
        ],
        "usb": False,
        "analysis_writes": False,
    }


def get_derived(root: Path | str, analysis_id: str) -> dict[str, Any] | None:
    """Load one derived analysis by id under derived-out (offline)."""
    root = Path(root)
    matches = list(root.glob(f"**/*{analysis_id}*/analysis.json"))
    if not matches:
        matches = list(root.glob(f"**/{analysis_id}/analysis.json"))
    if not matches:
        return None
    data = json.loads(matches[0].read_text(encoding="utf-8"))
    summary = summarize_derived(data, path=matches[0])
    summary["payload"] = data
    return summary


def _write_derived(folder: Path, payload: dict[str, Any]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "analysis.json"
    body = json.dumps(payload, indent=1, default=float) + "\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing != body:
            raise AnalysisIdentityConflict(
                f"analysis identity conflict at {path}: same path, different content"
            )
        return path
    path.write_text(body, encoding="utf-8")
    return path


def _consumed_stream_hashes(run_folder: Path) -> dict[str, str]:
    streams = run_folder / "streams"
    out: dict[str, str] = {}
    if not streams.is_dir():
        return out
    for p in sorted(streams.rglob("*")):
        if p.is_file():
            out[p.relative_to(run_folder).as_posix()] = prov_file_sha256(p)
    return out


def analyse_model(
    run_folder: Path | str,
    cfg: HwConfig,
    *,
    model: str,
    derived_out: Path | str,
    analysis_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Offline analysis. ``legacy`` reproduces old analyse(); ``qualified-v2`` uses M2/M3."""
    run_folder = Path(run_folder)
    derived_out = Path(derived_out)
    store = ScanStore.open(run_folder)
    cube_sha = file_sha256(run_folder / "cube.csv.gz")
    scan_sha = file_sha256(run_folder / "scan.json")
    stream_hashes = _consumed_stream_hashes(run_folder)
    raw_bundle_sha = content_hash({"cube": cube_sha, "streams": stream_hashes})
    analysis_cfg = dict(analysis_config or {})
    cal = resolve_calibration(gain="1", cfg=cfg, detector="ingaas")
    seal = store.meta.get("terminal_source_seal") or {}
    seal_sha = seal.get("combined_sha256") if isinstance(seal, dict) else None

    if model == "legacy":
        from lio.scan.analysis import analyse as legacy_analyse

        # D09: never rewrite source analysis.json when writing under derived-out.
        a = legacy_analyse(run_folder, cfg, None, None, write=False)
        payload = a.to_dict()
        payload["model"] = "legacy"
    elif model in ("qualified-v2", "qualified_v2"):
        cube = Cube.open(run_folder)
        coupling = estimate_coupling(cube, cfg, model="validated_control")
        sens = {
            det: leave_one_control_out(cube, cfg, det, rail="B")
            for det in ("ingaas", "opt101")
        }
        # D12: fixed-position blocks — do NOT pool heights/directions as independent N.
        hole_estimates: dict[str, Any] = {}
        for det in ("ingaas", "opt101"):
            blocks = group_fixed_position_blocks(cube, detector=det)
            for hole, hole_blocks in blocks.items():
                est = block_drive_response(hole_blocks)
                hole_estimates[f"{det}:h{hole:02d}"] = est.to_dict()
        obj = primary_swir_objective()
        payload = {
            "run_id": store.run_id,
            "sample_id": store.meta.get("sample_id"),
            "mode": store.meta.get("mode"),
            "status": store.meta.get("status"),
            "model": "qualified-v2",
            "objective": obj.to_dict(),
            "coupling": {k: v.to_dict() for k, v in coupling.items()},
            "sensitivity": sens,
            "estimates": hole_estimates,
            "verdict": {
                "verdict": "UNRESOLVED",
                "reasons": [
                    "qualified-v2 is offline software product; not bench-qualified",
                    "does not claim SNR or SWIR chemistry improvement",
                ],
            },
            "findings": [],
            "health": [],
            "context": {"calibration_id": cal.calibration_id},
        }
    else:
        raise ValueError(f"unknown model {model!r}; use legacy|qualified-v2")

    identity = build_analysis_identity(
        cube_sha256=cube_sha,
        scan_sha256=scan_sha,
        calibration_id=cal.calibration_id,
        channel_map_sha256=str(store.meta.get("config_sha256") or cfg.sha256),
        terminal_seal_sha256=seal_sha,
        estimator_version=f"model:{model}",
        coupling_model_version="m2-coupling-1",
        protocol_hash=store.meta.get("protocol_hash"),
        numerical_settings=analysis_cfg,
        consumed_inputs={
            "stream_sha256": stream_hashes,
            "raw_bundle_sha256": raw_bundle_sha,
            "analysis_config": analysis_cfg,
            "config_sha256": cfg.sha256,
        },
    )
    payload["identity"] = identity.to_dict()
    analysis_id = identity.identity_hash()[:16]
    payload["analysis_id"] = analysis_id
    out_dir = derived_out / store.run_id / f"{model}_{analysis_id}"
    path = _write_derived(out_dir, payload)
    payload["_path"] = str(path)
    return payload


def audit_run(
    run_folder: Path | str,
    cfg: HwConfig,
    *,
    model: str,
    derived_out: Path | str,
) -> dict[str, Any]:
    """Read-only audit: provenance, eligibility, model product under derived-out."""
    run_folder = Path(run_folder)
    store = ScanStore.open(run_folder)
    cube = Cube.open(run_folder)
    product = analyse_model(run_folder, cfg, model=model, derived_out=derived_out)
    audit = {
        "run_id": store.run_id,
        "rows": cube.n,
        "status": store.meta.get("status"),
        "config_sha256": store.meta.get("config_sha256"),
        "acquisition_snapshot": store.meta.get("acquisition_snapshot"),
        "terminal_source_seal": store.meta.get("terminal_source_seal"),
        "model": model,
        "analysis_id": product.get("analysis_id"),
        "analysis_path": product.get("_path"),
        "objective": named_objective("primary_swir").to_dict(),
        "notes": [
            "audit is offline; no device, light or motion",
            "historical bytes not rewritten",
        ],
    }
    audit_dir = Path(derived_out) / store.run_id / f"audit_{model}_{product.get('analysis_id')}"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / "audit.json"
    audit_path.write_text(json.dumps(audit, indent=1, default=float) + "\n", encoding="utf-8")
    audit["_path"] = str(audit_path)
    return audit


def report_derived(
    run_folder: Path | str,
    *,
    analysis_id: str,
    derived_out: Path | str,
) -> Path:
    """Write a short markdown report for a derived analysis id."""
    run_folder = Path(run_folder)
    derived_out = Path(derived_out)
    matches = [
        p
        for p in derived_out.glob(f"**/{analysis_id}/analysis.json")
        if analysis_id in str(p)
    ]
    if not matches:
        matches = list(derived_out.glob(f"**/*{analysis_id}/analysis.json"))
    if not matches:
        raise FileNotFoundError(f"analysis_id {analysis_id!r} not under {derived_out}")
    data = json.loads(matches[0].read_text(encoding="utf-8"))
    lines = [
        f"# Derived analysis `{analysis_id}`",
        "",
        f"- Run: `{data.get('run_id')}`",
        f"- Model: `{data.get('model')}`",
        f"- Status: `{data.get('status')}`",
        "",
        "This report is a software product. It does **not** claim measured SNR or",
        "SWIR chemistry improvement. Bench qualification is separate.",
        "",
    ]
    verdict = data.get("verdict") or {}
    if verdict:
        lines.append(f"**Verdict (model):** {verdict.get('verdict')}")
        for r in verdict.get("reasons") or []:
            lines.append(f"- {r}")
        lines.append("")
    out = matches[0].parent / "report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _ = content_hash  # keep import used for future stamping
    _ = run_folder
    return out
