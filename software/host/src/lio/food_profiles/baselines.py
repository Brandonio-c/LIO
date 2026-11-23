"""Baseline selection for quantitative reuse vs raw comparison (M6).

Rejects incompatible geometry/calibration/model/reference or incomplete runs for
quantitative reuse, while still allowing raw comparison of saved cubes.
Suite YAML, scan baseline, empty-holder response and calibrated white reference
remain distinct kinds.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class BaselineKind(str, Enum):
    SUITE_YAML = "suite_yaml"
    SCAN_BASELINE = "scan_baseline"
    EMPTY_HOLDER = "empty_holder"
    WHITE_REFERENCE = "white_reference"
    UNKNOWN = "unknown"


class BaselineUse(str, Enum):
    QUANTITATIVE = "quantitative"
    RAW_COMPARE = "raw_compare"


@dataclass(frozen=True)
class BaselineCandidate:
    run_id: str
    folder: str
    kind: BaselineKind
    status: str
    config_sha256: str | None = None
    calibration_id: str | None = None
    model: str | None = None
    geometry_key: str | None = None
    reference_protocol: str | None = None
    incomplete: bool = False
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["notes"] = list(self.notes)
        return d


@dataclass
class BaselineDecision:
    ok: bool
    use: BaselineUse
    reason: str
    candidate: BaselineCandidate | None = None
    rejects: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "use": self.use.value,
            "reason": self.reason,
            "candidate": None if self.candidate is None else self.candidate.to_dict(),
            "rejects": list(self.rejects),
        }


def _meta_from_folder(folder: Path) -> dict[str, Any]:
    path = folder / "scan.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def candidate_from_run_folder(
    folder: Path | str,
    *,
    kind: BaselineKind = BaselineKind.SCAN_BASELINE,
) -> BaselineCandidate:
    folder = Path(folder)
    meta = _meta_from_folder(folder)
    status = str(meta.get("status") or "UNKNOWN")
    incomplete = status != "COMPLETE"
    snap = meta.get("acquisition_snapshot") or {}
    cal = None
    if isinstance(snap, dict):
        cal = (snap.get("adc") or {}).get("gain")
    geom = None
    stage = meta.get("stage") or {}
    if isinstance(stage, dict) and stage:
        geom = f"top={stage.get('top')}|bottom={stage.get('bottom')}"
    return BaselineCandidate(
        run_id=str(meta.get("run_id") or folder.name),
        folder=str(folder),
        kind=kind,
        status=status,
        config_sha256=meta.get("config_sha256"),
        calibration_id=None if cal is None else f"gain:{cal}",
        model=(
            (meta.get("analysis") or {}).get("model")
            if isinstance(meta.get("analysis"), dict)
            else None
        ),
        geometry_key=geom,
        reference_protocol=str((meta.get("protocol") or {}).get("id") or "") or None,
        incomplete=incomplete,
        notes=tuple(
            n
            for n in (
                "incomplete" if incomplete else "",
                "no_snapshot" if not snap else "",
            )
            if n
        ),
    )


def select_baseline(
    candidates: list[BaselineCandidate],
    *,
    use: BaselineUse = BaselineUse.QUANTITATIVE,
    require_kind: BaselineKind | None = None,
    require_config_sha256: str | None = None,
    require_calibration_id: str | None = None,
    require_model: str | None = None,
    require_geometry_key: str | None = None,
    require_reference_protocol: str | None = None,
    allow_incomplete_for_raw: bool = True,
) -> BaselineDecision:
    """Pick a baseline for quantitative reuse or raw comparison.

    Quantitative reuse rejects incomplete runs and incompatible
    geometry/calibration/model/reference. Raw comparison may keep incomplete
    runs when ``allow_incomplete_for_raw`` is True.
    """
    rejects: list[str] = []
    for c in candidates:
        if require_kind is not None and c.kind is not require_kind:
            rejects.append(f"{c.run_id}: kind {c.kind.value} ≠ {require_kind.value}")
            continue
        if use is BaselineUse.QUANTITATIVE and c.incomplete:
            rejects.append(f"{c.run_id}: incomplete status={c.status}")
            continue
        if (
            use is BaselineUse.RAW_COMPARE
            and c.incomplete
            and not allow_incomplete_for_raw
        ):
            rejects.append(f"{c.run_id}: incomplete (raw compare disallowed)")
            continue
        if require_config_sha256 and c.config_sha256 and c.config_sha256 != require_config_sha256:
            rejects.append(f"{c.run_id}: config_sha256 mismatch")
            continue
        if require_config_sha256 and not c.config_sha256:
            rejects.append(f"{c.run_id}: missing config_sha256")
            continue
        if require_calibration_id and c.calibration_id != require_calibration_id:
            why = "missing calibration_id" if not c.calibration_id else "calibration mismatch"
            if not c.calibration_id and use is not BaselineUse.QUANTITATIVE:
                pass  # raw compare may proceed without calibration id
            else:
                rejects.append(f"{c.run_id}: {why}")
                continue
        if require_model and c.model and c.model != require_model:
            rejects.append(f"{c.run_id}: model mismatch")
            continue
        if require_geometry_key and c.geometry_key and c.geometry_key != require_geometry_key:
            rejects.append(f"{c.run_id}: geometry mismatch")
            continue
        if (
            require_reference_protocol
            and c.reference_protocol
            and c.reference_protocol != require_reference_protocol
        ):
            rejects.append(f"{c.run_id}: reference protocol mismatch")
            continue
        return BaselineDecision(True, use, "selected", c, rejects)
    return BaselineDecision(
        False,
        use,
        "no compatible baseline",
        None,
        rejects or ["empty candidate list"],
    )
