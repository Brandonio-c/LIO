"""Content-addressed archive of every loaded lio_hw.yaml (owner 2026-11-26).

A scan records the SHA-256 of the config it ran with. Without the content, a later
edit (even a comment or a grading threshold) made the run impossible to resume. Each
loaded config is now kept as ``software/config/snapshots/<sha256>.yaml``, so a resume
can see exactly WHAT changed and refuse only changes that affect acquisition.

A snapshot is trusted only if its bytes hash to its file name.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from lio.config import HwConfig

# Settings that decide how light is measured or where the head goes. A change here
# makes the two halves of a resumed run not comparable: refused.
ACQUISITION = (
    "schema_version",
    "firmware",
    "link",
    "pins",
    "adc",
    "detectors",
    "rails",
    "channels",
    "motors",
    "duty",
    "timing",
    "power",
    "stage",
    "scan",
    "polarity_gate_hole",
    "thresholds.motion.travel",
)
# ...except these, which only grade results or are fallbacks unused on a tracked stage.
NOT_ACQUISITION = (
    "scan.health",
    "scan.sample_aliases",
    "thresholds.motion.travel.range_steps",
    "thresholds.motion.travel.margin_steps",
)


def snapshot_dir(cfg: HwConfig) -> Path:
    return Path(cfg.path).resolve().parent / "snapshots"


def save_snapshot(cfg: HwConfig) -> Path | None:
    """Keep the loaded config's bytes under its hash (no-op if the file changed since)."""
    try:
        blob = Path(cfg.path).read_bytes()
    except OSError:
        return None
    if hashlib.sha256(blob).hexdigest() != cfg.sha256:
        return None  # the file on disk is no longer what was loaded
    d = snapshot_dir(cfg)
    p = d / f"{cfg.sha256}.yaml"
    if not p.exists():
        d.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
    return p


def load_snapshot(cfg: HwConfig, sha256: str) -> dict[str, Any] | None:
    """The config content with this hash, or None (missing or not matching its name)."""
    if not sha256:
        return None
    p = snapshot_dir(cfg) / f"{sha256}.yaml"
    try:
        blob = p.read_bytes()
    except OSError:
        return None
    if hashlib.sha256(blob).hexdigest() != sha256:
        return None
    data = yaml.safe_load(blob)
    return data if isinstance(data, dict) else None


def _flatten(d: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(d, dict):
        out: dict[str, Any] = {}
        for k, v in d.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
        return out
    return {prefix: d}


def _under(key: str, prefixes: tuple[str, ...]) -> bool:
    return any(key == p or key.startswith(p + ".") for p in prefixes)


def config_changes(old: dict[str, Any], new: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(changes that affect acquisition, changes that do not), as dotted keys."""
    a, b = _flatten(old), _flatten(new)
    changed = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    blocking = [k for k in changed if _under(k, ACQUISITION) and not _under(k, NOT_ACQUISITION)]
    allowed = [k for k in changed if k not in blocking]
    return blocking, allowed


def resume_config_check(cfg: HwConfig, run_sha256: str) -> tuple[bool, str, list[str]]:
    """May a run recorded with ``run_sha256`` resume under ``cfg``?

    Returns (ok, reason, allowed_changes). Same hash: ok. Different hash with the run's
    config on file: ok when nothing acquisition-related changed. Otherwise refused.
    """
    if run_sha256 == cfg.sha256:
        return True, "", []
    if not run_sha256:
        return False, "lio_hw.yaml changed since the run started (no fingerprint recorded)", []
    old = load_snapshot(cfg, run_sha256)
    if old is None:
        return (False, "lio_hw.yaml changed since the run started and the run's config is "
                       "not on file to compare: start a new scan", [])  # fmt: skip
    blocking, allowed = config_changes(old, cfg.data)
    if blocking:
        shown = ", ".join(blocking[:6]) + (" …" if len(blocking) > 6 else "")
        return False, f"acquisition settings changed since the run started: {shown}", allowed
    return True, "", allowed
