"""A run folder as arrays, and the finding type every metric returns."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from lio.config import HwConfig
from lio.results import Status
from lio.scan.store import MV_PER_COUNT, ScanStore

DETECTORS = ("opt101", "ingaas")
Array = np.ndarray[Any, np.dtype[np.float64]]


@dataclass
class Finding:
    """One metric's verdict. ``id`` is stable (it becomes a T13 sub-result id):
    ``<area>/<detector or scope>/<metric>[/hNN]``."""

    id: str
    title: str
    status: Status
    value: float | None = None
    unit: str = ""
    detail: str = ""
    criteria: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "value": self.value,
            "unit": self.unit,
            "detail": self.detail,
            "criteria": self.criteria,
            "data": self.data,
        }


def _f(v: str) -> float:
    return float(v) if v not in ("", None) else float("nan")


@dataclass
class Curve:
    """S(h) of one hole on one detector: heights ascending (half-steps), net counts."""

    h: Array
    net: Array

    def __len__(self) -> int:
        return len(self.h)


class Cube:
    """The rows of cube.csv.gz with typed accessors, plus scan.json and the streams."""

    def __init__(self, store: ScanStore) -> None:
        self.store = store
        self.meta = store.meta
        rows = list(store.rows())
        self.n = len(rows)
        cols = (
            "step",
            "height_hs",
            "rep",
            "hole",
            "dark_counts",
            "lit_counts",
            "net_counts",
            "t_s",
        )
        self.num: dict[str, Array] = {
            c: np.array([_f(r[c]) for r in rows], dtype=np.float64) for c in cols
        }
        self.str: dict[str, np.ndarray[Any, np.dtype[np.str_]]] = {
            c: np.array([r[c] for r in rows], dtype=np.str_)
            for c in ("phase", "direction", "state", "detector")
        }

    @classmethod
    def open(cls, folder: Path) -> Cube:
        return cls(ScanStore.open(folder))

    @property
    def sample_id(self) -> str:
        return str(self.meta.get("sample_id", ""))

    @property
    def mode(self) -> str:
        return str(self.meta.get("mode", ""))

    def mask(self, **eq: str) -> np.ndarray[Any, np.dtype[np.bool_]]:
        m = np.ones(self.n, dtype=bool)
        for k, v in eq.items():
            m &= self.str[k] == v
        return m

    def curve(
        self, hole: int, det: str, *, phase: str = "P2", direction: str | None = None
    ) -> Curve:
        """Lit net vs height for one channel (first visits only; duplicates: median)."""
        m = self.mask(state="lit", detector=det, phase=phase)
        if direction is not None:
            m &= self.str["direction"] == direction
        m &= (self.num["hole"] == hole) & (self.num["rep"] == 0)
        h = self.num["height_hs"][m]
        v = self.num["net_counts"][m]
        if not len(h):
            return Curve(np.zeros(0), np.zeros(0))
        uh = np.unique(h)
        med = np.array([float(np.median(v[h == x])) for x in uh])
        return Curve(uh, med)

    def lit_all(self, det: str) -> tuple[Array, Array, Array]:
        """(hole, height, net) of every stop-measure-move lit reading on ``det``."""
        m = self.mask(state="lit", detector=det) & (self.str["phase"] != "P1")
        m &= self.str["phase"] != "P4"
        return self.num["hole"][m], self.num["height_hs"][m], self.num["net_counts"][m]

    def darks(self, det: str) -> tuple[Array, Array, Array, np.ndarray[Any, np.dtype[np.str_]]]:
        """(t_s, height, dark counts, phase) of every dark frame on ``det``."""
        m = self.mask(state="dark", detector=det)
        return (self.num["t_s"][m], self.num["height_hs"][m], self.num["dark_counts"][m],
                self.str["phase"][m])  # fmt: skip

    def state_rows(self, state: str, det: str) -> tuple[Array, Array, Array]:
        """(hole, dark, net) of rows in ``state`` (select_only, ce_only, ...)."""
        m = self.mask(state=state, detector=det)
        return self.num["hole"][m], self.num["dark_counts"][m], self.num["net_counts"][m]

    def streams(self, state: str, det: str) -> list[tuple[Array, Array]]:
        """Timestamped raw streams (t in s, counts) in ``state`` on ``det``."""
        out = []
        for s in self.meta.get("streams", []):
            if s.get("state") == state and s.get("detector") == det:
                z = self.store.load_stream(s["name"])
                out.append((z["t_us"].astype(np.float64) / 1e6, z["raw"].astype(np.float64)))
        return out


def mv(counts: float) -> float:
    return counts * MV_PER_COUNT


def health(cfg: HwConfig, path: str) -> Any:
    """A provisional threshold from ``scan.health`` in lio_hw.yaml."""
    return cfg.section.raw(f"scan.health.{path}")


def pair(cfg: HwConfig, path: str) -> tuple[float, float]:
    """[warn, fail] thresholds."""
    v = health(cfg, path)
    return float(v[0]), float(v[1])


def grade(value: float, warn: float, fail: float) -> Status:
    """Larger is worse."""
    if value >= fail:
        return Status.FAIL
    if value >= warn:
        return Status.WARN
    return Status.PASS


def grade_low(value: float, warn: float, fail: float) -> Status:
    """Smaller is worse."""
    if value <= fail:
        return Status.FAIL
    if value <= warn:
        return Status.WARN
    return Status.PASS
