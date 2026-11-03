"""Baselines (plan §5.3): save a run's per-channel values, compare later runs with them.

A baseline is a YAML file in ``software/config/`` (``baseline_<YYYYmmdd>.yaml``)
holding the values that characterise a healthy instrument: per-channel net
signal on both detectors, dark offsets and noise, InGaAs/OPT101 ratios, settle
times and repeatability. It also records the sample, firmware and config, so a
comparison can tell when like is not being compared with like.

This is how the provisional thresholds become real ones: the first good
hardware run (M6, empty closed chamber) is saved as the reference.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import yaml

from lio.config import default_config_path
from lio.results import RunRecord, Status

SCHEMA = 1


def _sub_measured(record: RunRecord, test_id: str) -> dict[str, dict[str, Any]]:
    try:
        r = record.result(test_id)
    except KeyError:
        return {}
    return {s.id.split("/", 1)[1]: s.measured for s in r.subs if s.status != Status.SKIP}


def build(record: RunRecord) -> dict[str, Any]:
    """Baseline content from a finished run record."""
    try:
        matrix = record.result("T05.3").measured.get("matrix", {})
    except KeyError:
        matrix = {}
    if not matrix:
        raise ValueError("the run has no channel matrix (T05.3): nothing to save")
    dark = {
        sid.split("/")[0]: {"mean": m["mean"], "sigma": m["sigma"]}
        for sid, m in _sub_measured(record, "T03.2").items()
        if "mean" in m and m.get("sigma") is not None
    }
    try:
        ratios = record.result("T06.3").measured.get("ingaas_over_opt101", {})
    except KeyError:
        ratios = {}
    settle = {
        k: m["t_settle_ms"] for k, m in _sub_measured(record, "T07.1").items() if "t_settle_ms" in m
    }
    cv = {k: m["cv"] for k, m in _sub_measured(record, "T05.5").items() if "cv" in m}
    return {
        "schema": SCHEMA,
        "created": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "run_id": record.run_id,
        "target": record.target,
        "sample_id": record.metadata.get("sample_id"),
        "operator": record.metadata.get("operator"),
        "firmware": {k: record.firmware.get(k) for k in ("fw", "proto", "build")},
        "config_sha256": record.config.get("sha256"),
        "verdict": record.verdict.get("verdict"),
        "channels": {int(h): {d: int(v) for d, v in nets.items()} for h, nets in matrix.items()},
        "dark": dark,
        "ingaas_over_opt101": {int(h): float(v) for h, v in ratios.items()},
        "settle_ms": {k: float(v) for k, v in settle.items()},
        "repeatability_cv": {k: float(v) for k, v in cv.items()},
    }


def default_path(folder: Path | None = None, today: dt.date | None = None) -> Path:
    """A new file name in ``software/config/`` that does not overwrite an older baseline."""
    folder = folder or default_config_path().parent
    stem = f"baseline_{(today or dt.date.today()):%Y%m%d}"
    path = folder / f"{stem}.yaml"
    n = 2
    while path.exists():
        path = folder / f"{stem}_{n}.yaml"
        n += 1
    return path


def save(record: RunRecord, path: Path | None = None) -> Path:
    data = build(record)
    out = path or default_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# LIO baseline from run {record.run_id} (sample {data['sample_id']}).\n"
        "# Written by 'lio selftest --save-baseline'; compare with --baseline <this file>.\n"
    )
    out.write_text(header + yaml.safe_dump(data, sort_keys=False))
    return out


def load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or "channels" not in data:
        raise ValueError(f"{path} is not an LIO baseline (schema {SCHEMA})")
    data["_path"] = str(path)
    return data


def latest(folder: Path | None = None) -> Path | None:
    folder = folder or default_config_path().parent
    files = sorted(folder.glob("baseline_*.yaml"))
    return files[-1] if files else None
