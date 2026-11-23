"""Scan data on disk: one folder per run (plan LIO-SW-SCAN-001 §4).

    test_results/<YYYYmmdd-HHMMSS>_scan_<mode>/
        scan.json        metadata, plan, phase timings, events, aborts, operator answers,
                         the resume index (last completed step)
        cube.csv.gz      one row per reading (appended per completed step)
        streams/*.npz    raw timestamped streams (hum, coil EMI, long dark)

``cube.csv.gz`` is a sequence of gzip members (one per append), which the standard
library reads as one file. Rows are written only when a step completes, so a resume
never sees a half-written step.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import time
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

CUBE_FIELDS = (
    "run_id", "step", "phase", "height_hs", "height_mm", "direction", "rep", "hole", "state",
    "detector", "dark_counts", "lit_counts", "net_counts", "net_mv", "t_s", "duty_wait_ms",
    "settle_ms", "n",
)  # fmt: skip

# Reading states (plan §4.1); "coils_moving" stands in for "coils_on" on firmware
# without a hold-coils command (S0 deviation D2).
STATES = ("dark", "lit", "select_only", "ce_only", "wrong_rail", "coils_off", "coils_moving")

# Legacy gain-1 LSB only (ADS1115 GAIN_ONE). New writers should use
# ``lio.scan.calibration.resolve_calibration`` / ``CalibrationResolver.counts_to_mv``.
# Do not rewrite historical cubes; unknown LSB must disable physical units.
MV_PER_COUNT = 0.125  # see lio.scan.calibration.LEGACY_GAIN1_LSB_MV


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class ScanStore:
    """Writer and reader of one run folder."""

    def __init__(self, folder: Path) -> None:
        self.folder = Path(folder)
        self.meta_path = self.folder / "scan.json"
        self.cube_path = self.folder / "cube.csv.gz"
        self.streams = self.folder / "streams"
        self.meta: dict[str, Any] = {}

    # ------------------------------------------------------------ create / open

    @classmethod
    def create(cls, root: Path, mode: str, meta: dict[str, Any]) -> ScanStore:
        run_id = time.strftime("%Y%m%d-%H%M%S") + f"_scan_{mode}"
        folder = Path(root) / run_id
        n = 1
        while folder.exists():  # two runs in the same second
            n += 1
            folder = Path(root) / f"{run_id}-{n}"
        folder.mkdir(parents=True)
        st = cls(folder)
        st.meta = {
            "run_id": folder.name,
            "status": "RUNNING",
            "started": _now_iso(),
            "finished": None,
            "completed_step": -1,
            "events": [],
            "aborts": [],
            "answers": {},
            "phases": {},
            "streams": [],
            **meta,
        }
        st.save_meta()
        return st

    @classmethod
    def open(cls, folder: Path) -> ScanStore:
        st = cls(Path(folder))
        if not st.meta_path.exists():
            raise FileNotFoundError(f"no scan.json in {folder}")
        st.meta = json.loads(st.meta_path.read_text())
        return st

    @property
    def run_id(self) -> str:
        return str(self.meta.get("run_id", self.folder.name))

    # ------------------------------------------------------------ metadata

    def save_meta(self) -> None:
        tmp = self.meta_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.meta, indent=1, default=str) + "\n")
        tmp.replace(self.meta_path)

    def event(self, kind: str, **fields: Any) -> None:
        self.meta.setdefault("events", []).append({"at": _now_iso(), "kind": kind, **fields})
        self.save_meta()

    def answer(self, key: str, value: Any) -> None:
        self.meta.setdefault("answers", {})[key] = value
        self.save_meta()

    def abort(self, reason: str, **fields: Any) -> None:
        self.meta.setdefault("aborts", []).append({"at": _now_iso(), "reason": reason, **fields})
        self.meta["status"] = "INCOMPLETE"
        self.save_meta()

    def finish(self, status: str = "COMPLETE") -> None:
        self.meta["status"] = status
        self.meta["finished"] = _now_iso()
        self.save_meta()

    def phase_time(self, phase: str, seconds: float) -> None:
        ph = self.meta.setdefault("phases", {})
        ph[phase] = round(ph.get(phase, 0.0) + seconds, 3)

    # ------------------------------------------------------------ cube

    def append_rows(self, rows: Iterable[dict[str, Any]], *, completed_step: int) -> None:
        """Append one completed step's readings and move the resume index on."""
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=CUBE_FIELDS, extrasaction="ignore")
        new = not self.cube_path.exists()
        if new:
            w.writeheader()
        n = 0
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in CUBE_FIELDS})
            n += 1
        with gzip.open(self.cube_path, "at", encoding="utf-8", newline="") as f:
            f.write(buf.getvalue())
        self.meta["completed_step"] = completed_step
        self.meta["rows"] = int(self.meta.get("rows", 0)) + n
        self.save_meta()

    def rows(self) -> Iterator[dict[str, str]]:
        if not self.cube_path.exists():
            return
        with gzip.open(self.cube_path, "rt", encoding="utf-8", newline="") as f:
            yield from csv.DictReader(f)

    # ------------------------------------------------------------ streams

    def save_stream(self, name: str, *, t_us: list[int], raw: list[int], **info: Any) -> str:
        self.streams.mkdir(exist_ok=True)
        path = self.streams / f"{name}.npz"
        np.savez_compressed(
            path, t_us=np.asarray(t_us, dtype=np.int64), raw=np.asarray(raw, dtype=np.int32)
        )
        rel = str(path.relative_to(self.folder))
        self.meta.setdefault("streams", []).append({"name": name, "file": rel, **info})
        self.save_meta()
        return rel

    def load_stream(self, name: str) -> dict[str, Any]:
        with np.load(self.streams / f"{name}.npz") as z:
            return {"t_us": z["t_us"], "raw": z["raw"]}
