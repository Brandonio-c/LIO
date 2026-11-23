"""Versioned derived analyses under a dedicated root (M0/M6).

Historical run folders stay untouched. New products are content-addressed under
``derived-out`` with analysis identity (source hashes, calibration, estimator).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lio.config import HwConfig
from lio.food_profiles.runs import file_sha256
from lio.scan.analysis.coupling import estimate_coupling, leave_one_control_out
from lio.scan.analysis.data import Cube
from lio.scan.analysis.uncertainty import drive_response_tau
from lio.scan.calibration import resolve_calibration
from lio.scan.provenance import build_analysis_identity, content_hash
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
    # Surface which holes have estimates without promoting control PASS to SWIR OK.
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
        },
        "coupling": coupling,
        "eligibility_notes": eligibility_notes,
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
    path.write_text(json.dumps(payload, indent=1, default=float) + "\n", encoding="utf-8")
    return path


def analyse_model(
    run_folder: Path | str,
    cfg: HwConfig,
    *,
    model: str,
    derived_out: Path | str,
) -> dict[str, Any]:
    """Offline analysis. ``legacy`` reproduces old analyse(); ``qualified-v2`` uses M2/M3."""
    run_folder = Path(run_folder)
    derived_out = Path(derived_out)
    store = ScanStore.open(run_folder)
    cube_sha = file_sha256(run_folder / "cube.csv.gz")
    scan_sha = file_sha256(run_folder / "scan.json")
    cal = resolve_calibration(gain="1", cfg=cfg, detector="ingaas")

    if model == "legacy":
        from lio.scan.analysis import analyse as legacy_analyse

        # Write legacy into the run folder as today, then copy identity-stamped product.
        a = legacy_analyse(run_folder, cfg, None, None)
        payload = a.to_dict()
        payload["model"] = "legacy"
    elif model in ("qualified-v2", "qualified_v2"):
        cube = Cube.open(run_folder)
        coupling = estimate_coupling(cube, cfg, model="validated_control")
        sens = {
            det: leave_one_control_out(cube, cfg, det, rail="B")
            for det in ("ingaas", "opt101")
        }
        # Fixed-N example on P2/P3 lit nets per hole (signed; no max-over-heights qualify).
        hole_estimates: dict[str, Any] = {}
        for det in ("ingaas", "opt101"):
            holes, _hs, net = cube.lit_all(det)
            for hole in sorted(set(int(h) for h in holes)):
                vals = net[holes == hole]
                # Treat each reading as a block with dark=0 reference for synthetic tau
                # of already dark-subtracted nets: tau = mean(net - 0).
                est = drive_response_tau(vals, [0.0] * len(vals))
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
        estimator_version=f"model:{model}",
        coupling_model_version="m2-coupling-1",
        protocol_hash=store.meta.get("protocol_hash"),
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
    _write_derived(audit_dir, audit)
    # Rename file for clarity
    (audit_dir / "analysis.json").replace(audit_dir / "audit.json")
    audit["_path"] = str(audit_dir / "audit.json")
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
        # Also match folder suffix
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
    return out
