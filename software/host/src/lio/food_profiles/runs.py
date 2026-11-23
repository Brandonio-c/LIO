"""Read-only adapters over saved scan run folders."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from lio.config import HwConfig, load_config
from lio.food_profiles.schema import (
    BROADBAND_LABELS,
    DEFAULT_SELECTION,
    DETECTORS,
    CellReason,
)
from lio.scan.provenance import (
    ValidityReason,
    collect_stream_sha256,
    resolve_analysis_validity,
    verify_store_seal,
)
from lio.scan.store import ScanStore


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def discover_runs(results_root: Path) -> list[dict[str, Any]]:
    """Paginated-friendly summaries of ``*_scan_*`` folders under results_root."""
    root = Path(results_root)
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for folder in sorted(root.iterdir(), key=lambda p: p.name, reverse=True):
        if not folder.is_dir() or "_scan_" not in folder.name:
            continue
        meta_path = folder / "scan.json"
        if not meta_path.exists() or not (folder / "cube.csv.gz").exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        out.append(
            {
                "run_id": meta.get("run_id", folder.name),
                "folder": folder.name,
                "sample_id": meta.get("sample_id"),
                "mode": meta.get("mode"),
                "status": meta.get("status"),
                "started": meta.get("started"),
                "finished": meta.get("finished"),
                "has_analysis": (folder / "analysis.json").exists(),
                "has_streams": (folder / "streams").is_dir(),
                "synthetic": bool(meta.get("synthetic")),
            }
        )
    return out


@dataclass
class ChannelInfo:
    hole: int
    label: str
    wavelength_nm: float | None
    expect: dict[str, str]
    broadband: bool
    verified: bool


@dataclass
class RunData:
    """Immutable view of one run folder (required: scan.json + cube.csv.gz)."""

    folder: Path
    meta: dict[str, Any]
    rows: list[dict[str, str]]
    step_kinds: list[str]
    channel_map: dict[int, ChannelInfo]
    channel_map_verified: bool
    analysis: dict[str, Any] | None
    analysis_ok: bool
    analysis_reason: str
    cube_sha256: str
    scan_sha256: str
    cfg: HwConfig

    @property
    def run_id(self) -> str:
        return str(self.meta.get("run_id", self.folder.name))

    @property
    def sample_id(self) -> str:
        return str(self.meta.get("sample_id", ""))

    def row_id(self, index: int) -> str:
        return f"{self.run_id}:row:{index}"

    def iter_selected(
        self, selection: dict[str, Any] | None = None
    ) -> Iterator[tuple[int, dict[str, str]]]:
        sel = {**DEFAULT_SELECTION, **(selection or {})}
        for i, r in enumerate(self.rows):
            if r.get("state") != sel["state"]:
                continue
            if r.get("phase") != sel["phase"]:
                continue
            if r.get("direction") != sel["direction"]:
                continue
            try:
                rep = int(float(r.get("rep") or 0))
            except ValueError:
                continue
            if rep != int(sel["rep"]):
                continue
            step_s = r.get("step") or "0"
            try:
                step = int(float(step_s))
            except ValueError:
                continue
            kind = self.step_kinds[step] if 0 <= step < len(self.step_kinds) else ""
            want_kind = str(sel.get("kind") or "measure")
            if want_kind and kind and kind != want_kind:
                continue
            if want_kind and not kind:
                # Unknown kind: do not silently qualify (plan §4.1).
                continue
            yield i, r

    def expect(self, hole: int, detector: str) -> str:
        ch = self.channel_map.get(hole)
        if ch is None:
            return "none"
        return ch.expect.get(detector, "none")

    def is_blind(self, hole: int, detector: str) -> bool:
        return self.expect(hole, detector) == "none"


def _resolve_channel_map(
    cfg: HwConfig, meta: dict[str, Any]
) -> tuple[dict[int, ChannelInfo], bool]:
    snap = meta.get("channel_map_snapshot")
    verified = True
    if snap and isinstance(snap, dict) and "holes" in snap:
        out: dict[int, ChannelInfo] = {}
        for h_s, info in snap["holes"].items():
            h = int(h_s)
            out[h] = ChannelInfo(
                hole=h,
                label=str(info.get("label", h)),
                wavelength_nm=info.get("wavelength_nm"),
                expect={d: str(info.get("expect", {}).get(d, "none")) for d in DETECTORS},
                broadband=bool(info.get("broadband")),
                verified=True,
            )
        return out, True
    # Legacy: config hash only - use current config but mark unverified if hash differs.
    # HwConfig.sha256 is a string attribute (not a callable); compare as string.
    cfg_hash = str(getattr(cfg, "sha256", "") or "")
    stored = str(meta.get("config_sha256") or "")
    if (stored and cfg_hash and stored != cfg_hash) or not stored:
        verified = False
    out = {}
    for h in range(1, 17):
        ch = cfg.channel(h)
        out[h] = ChannelInfo(
            hole=h,
            label=ch.label,
            wavelength_nm=ch.wavelength_nm,
            expect={d: ch.expect_for(d) for d in DETECTORS},
            broadband=ch.label.lower() in BROADBAND_LABELS,
            verified=verified,
        )
    return out, verified


def open_run(folder: Path | str, cfg: HwConfig | None = None) -> RunData:
    folder = Path(folder)
    store = ScanStore.open(folder)
    meta = store.meta
    rows = list(store.rows())
    steps = (meta.get("plan") or {}).get("steps") or []
    step_kinds = [str(s.get("kind", "")) for s in steps]
    cfg = cfg or load_config()
    channel_map, verified = _resolve_channel_map(cfg, meta)
    cube_sha = file_sha256(folder / "cube.csv.gz")
    scan_sha = file_sha256(folder / "scan.json")
    analysis = None
    analysis_ok = False
    analysis_reason = "missing"
    ap = folder / "analysis.json"
    if ap.exists():
        try:
            analysis = json.loads(ap.read_text())
            # A07: hash the LIVE streams/NPZs and re-verify the terminal seal; a
            # saved product is reusable only if every consumed source still matches.
            ok, reason, detail = resolve_analysis_validity(
                analysis,
                cube_sha256=cube_sha,
                scan_sha256=scan_sha,
                run_id=str(meta.get("run_id", folder.name)),
                sample_id=str(meta.get("sample_id")),
                stream_sha256=collect_stream_sha256(folder),
            )
            if ok:
                seal_ok, seal_detail = verify_store_seal(store)
                if not seal_ok:
                    ok, detail = False, seal_detail
                    reason = ValidityReason.SOURCE_CHANGED
            analysis_ok = ok
            analysis_reason = reason.value if ok else f"{reason.value}:{detail}"
        except (OSError, json.JSONDecodeError) as e:
            analysis_reason = f"unreadable:{e}"
    return RunData(
        folder=folder,
        meta=meta,
        rows=rows,
        step_kinds=step_kinds,
        channel_map=channel_map,
        channel_map_verified=verified,
        analysis=analysis,
        analysis_ok=analysis_ok,
        analysis_reason=analysis_reason,
        cube_sha256=cube_sha,
        scan_sha256=scan_sha,
        cfg=cfg,
    )


def heatmap_payload(
    run: RunData, detector: str, selection: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Hole x height net grid for Explore (display reducer: mean of duplicates)."""
    heights: dict[float, None] = {}
    cells: dict[tuple[int, float], list[float]] = {}
    links: dict[str, list[str]] = {}
    for i, r in run.iter_selected(selection):
        if r.get("detector") != detector:
            continue
        try:
            hole = int(float(r["hole"]))
            h = float(r["height_hs"])
            net = float(r["net_counts"])
        except (KeyError, ValueError):
            continue
        if hole < 1 or hole > 16:
            continue
        heights[h] = None
        cells.setdefault((hole, h), []).append(net)
        links.setdefault(f"{hole}:{h:g}", []).append(run.row_id(i))
    h_list = sorted(heights)
    grid: list[list[float | None]] = []
    reasons: list[list[str]] = []
    for hole in range(1, 17):
        row: list[float | None] = []
        rr: list[str] = []
        blind = run.is_blind(hole, detector)
        for h in h_list:
            vals = cells.get((hole, h))
            if blind:
                row.append(None)
                rr.append(CellReason.BLIND.value)
            elif not vals:
                row.append(None)
                rr.append(CellReason.MISSING.value)
            else:
                row.append(float(np.mean(vals)))
                rr.append(CellReason.OK.value)
        grid.append(row)
        reasons.append(rr)
    return {
        "run_id": run.run_id,
        "detector": detector,
        "selection": {**DEFAULT_SELECTION, **(selection or {})},
        "heights_hs": h_list,
        "holes": list(range(1, 17)),
        "net": grid,
        "reasons": reasons,
        "reducer": "mean",
        "source_links": links,
        "channel_map_verified": run.channel_map_verified,
        "channels": {
            str(h): {
                "label": c.label,
                "wavelength_nm": c.wavelength_nm,
                "expect": c.expect[detector],
                "broadband": c.broadband,
            }
            for h, c in run.channel_map.items()
        },
    }


def curve_payload(
    run: RunData, hole: int, detector: str, selection: dict[str, Any] | None = None
) -> dict[str, Any]:
    pts: list[dict[str, Any]] = []
    for i, r in run.iter_selected(selection):
        if r.get("detector") != detector:
            continue
        try:
            if int(float(r["hole"])) != hole:
                continue
            pts.append(
                {
                    "height_hs": float(r["height_hs"]),
                    "height_mm": float(r["height_mm"])
                    if r.get("height_mm") not in ("", None)
                    else None,
                    "net_counts": float(r["net_counts"]),
                    "dark_counts": float(r["dark_counts"])
                    if r.get("dark_counts") not in ("", None)
                    else None,
                    "lit_counts": float(r["lit_counts"])
                    if r.get("lit_counts") not in ("", None)
                    else None,
                    "row_id": run.row_id(i),
                }
            )
        except (KeyError, ValueError):
            continue
    pts.sort(key=lambda p: p["height_hs"])
    reason = CellReason.OK.value
    if run.is_blind(hole, detector):
        reason = CellReason.BLIND.value
    elif not pts:
        reason = CellReason.MISSING.value
    return {
        "run_id": run.run_id,
        "hole": hole,
        "detector": detector,
        "points": pts,
        "reason": reason,
        "processed_note": "cube net_counts are dark-subtracted once; not Cube.curve() despike",
    }


def findings_payload(run: RunData) -> dict[str, Any]:
    """Rejected analyses remain inspectable; ``available`` gates quantitative reuse."""
    if not run.analysis:
        return {
            "available": False,
            "reason": run.analysis_reason,
            "findings": [],
            "health": [],
            "verdict": None,
        }
    return {
        "available": run.analysis_ok,
        "reason": run.analysis_reason,
        "findings": run.analysis.get("findings") or [],
        "health": run.analysis.get("health") or [],
        "verdict": run.analysis.get("verdict"),
    }


def stream_index(run: RunData) -> list[dict[str, Any]]:
    return list(run.meta.get("streams") or [])


def load_stream(run: RunData, stream_id: str) -> dict[str, Any]:
    """Load one manifest-selected stream by name (scoped to run folder)."""
    entries = stream_index(run)
    match = next(
        (
            e
            for e in entries
            if e.get("name") == stream_id or e.get("file", "").endswith(f"{stream_id}.npz")
        ),
        None,
    )
    if match is None:
        raise FileNotFoundError(f"stream {stream_id!r} not in manifest")
    rel = str(match.get("file") or "")
    path = (run.folder / rel).resolve()
    if not str(path).startswith(str(run.folder.resolve())):
        raise PermissionError("stream path escapes run folder")
    if not path.exists():
        raise FileNotFoundError(rel)
    with np.load(path, allow_pickle=False) as z:
        t = z["t_us"].astype(np.int64)
        raw = z["raw"].astype(np.int32)
    # Bound display payload
    max_n = 5000
    if len(t) > max_n:
        idx = np.linspace(0, len(t) - 1, max_n).astype(int)
        t, raw = t[idx], raw[idx]
    gaps = np.diff(t.astype(np.float64))
    return {
        "name": match.get("name"),
        "file": rel,
        "n": len(t),
        "t_us": t.tolist(),
        "raw": raw.tolist(),
        "dt_us_median": float(np.median(gaps)) if len(gaps) else None,
        "meta": {k: v for k, v in match.items() if k not in ("file",)},
    }
