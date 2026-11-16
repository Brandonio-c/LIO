"""Where the chamber top is: absolute motor positions kept across sessions.

The firmware's position counters (``pos1``/``pos2`` in STATUS) start at 0 every time
the port is opened or the board is RESET, and the rig has no limit switches. So the
host keeps the real position in a small JSON file and carries it from one connection
to the next:

- **Reference:** half-steps from the top of the travel, which is the stage's physical
  upper end. Top = 0, lower positions are negative (+steps = up, ``motors.positive``).
- **Tracking:** :class:`lio.device.LIODevice` rebases the tracker whenever the counters
  restart (open, RESET) and reports every position the firmware gives (STATUS, MOTOR
  STOP, ``# MOTOR ... done``). A move made while no host is connected (e.g. by hand,
  or by ``lio_motor_control.py`` on another computer) is not seen: set the top again
  (``lio stage set-top``) after one.
- **Limits:** ``top`` is set where the stage cannot go higher; ``bottom`` is marked by
  the operator at the lowest safe position. Once both are known, moves that would
  leave the range are refused (:meth:`StageTracker.check_move`).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

MOTORS = (1, 2)
LOG_MAX = 300


REPO_ROOT = Path(__file__).resolve().parents[4]


def state_path(cfg: Any) -> Path | None:
    """The position file named by ``stage.state_file`` (None if the config has none)."""
    try:
        rel = str(cfg.section.raw("stage.state_file"))
    except Exception:
        return None
    p = Path(rel)
    return p if p.is_absolute() else REPO_ROOT / p


def tracker_for(cfg: Any) -> StageTracker | None:
    p = state_path(cfg)
    return StageTracker(p) if p is not None else None


class StageError(Exception):
    """A move refused by the soft limits, or a stage operation that is not possible."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True)
class Limits:
    top: tuple[int, int] | None
    bottom: tuple[int, int] | None


class StageTracker:
    """Absolute positions of both motors, persisted in ``path``."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._fw_base: tuple[int, int] | None = None  # firmware counters at the rebase
        self._abs_base: tuple[int, int] | None = None  # absolute position at the rebase
        self.data: dict[str, Any] = self._load()

    # ------------------------------------------------------------ storage

    def _load(self) -> dict[str, Any]:
        try:
            d = json.loads(self.path.read_text())
            if isinstance(d, dict):
                return d
        except (OSError, ValueError):
            pass
        return {"reference": "half-steps from the top of travel (top = 0, down < 0)",
                "abs": None, "top": None, "bottom": None, "updated": None, "log": []}  # fmt: skip

    def _save(self) -> None:
        self.data["updated"] = _now()
        self.data["log"] = self.data.get("log", [])[-LOG_MAX:]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1) + "\n")
        tmp.replace(self.path)

    def _log(self, event: str, **extra: Any) -> None:
        self.data.setdefault("log", []).append({"at": _now(), "event": event, **extra})

    # ------------------------------------------------------------ state

    @property
    def known(self) -> bool:
        return self.data.get("abs") is not None

    @property
    def abs(self) -> tuple[int, int] | None:
        a = self.data.get("abs")
        return (int(a[0]), int(a[1])) if a is not None else None

    @property
    def limits(self) -> Limits:
        t, b = self.data.get("top"), self.data.get("bottom")
        return Limits(
            (int(t[0]), int(t[1])) if t is not None else None,
            (int(b[0]), int(b[1])) if b is not None else None,
        )

    def summary(self) -> dict[str, Any]:
        lim = self.limits
        out: dict[str, Any] = {
            "known": self.known,
            "abs": list(self.abs) if self.abs else None,
            "top": list(lim.top) if lim.top else None,
            "bottom": list(lim.bottom) if lim.bottom else None,
            "updated": self.data.get("updated"),
            "file": str(self.path),
        }
        if lim.top and lim.bottom:
            out["range"] = [lim.top[i] - lim.bottom[i] for i in range(2)]
        if self.abs and lim.top:
            out["below_top"] = [lim.top[i] - self.abs[i] for i in range(2)]
        if self.abs and lim.bottom:
            out["above_bottom"] = [self.abs[i] - lim.bottom[i] for i in range(2)]
        return out

    # ------------------------------------------------------------ tracking

    def rebase(self, fw1: int, fw2: int, why: str = "counters restarted") -> None:
        """The firmware counters read (fw1, fw2) now: carry the absolute position on."""
        with self._lock:
            self._fw_base = (fw1, fw2)
            self._abs_base = self.abs
            if self.known:
                self._log("rebase", why=why, fw=[fw1, fw2], abs=list(self.abs or ()))
                self._save()

    def observe(self, fw1: int | None = None, fw2: int | None = None) -> None:
        """New firmware positions (either may be None when only one is reported)."""
        with self._lock:
            if self._fw_base is None or self._abs_base is None:
                return
            cur = list(self.abs or self._abs_base)
            for i, fw in enumerate((fw1, fw2)):
                if fw is not None:
                    cur[i] = self._abs_base[i] + (fw - self._fw_base[i])
            if tuple(cur) != self.abs:
                self.data["abs"] = cur
                self._save()

    # ------------------------------------------------------------ operator marks

    def set_top(self, fw: tuple[int, int]) -> None:
        """The stage is at the top of its travel now: position 0 on both motors.

        ``fw`` is the firmware's current counters. A bottom mark that would now lie
        above the top is cleared."""
        with self._lock:
            self.data["abs"] = [0, 0]
            self.data["top"] = [0, 0]
            b = self.data.get("bottom")
            if b is not None and (b[0] >= 0 or b[1] >= 0):
                self.data["bottom"] = None
            self._fw_base, self._abs_base = fw, (0, 0)
            self._log("set_top", fw=list(fw))
            self._save()

    def mark_bottom(self) -> None:
        """The stage is at its lowest safe position now."""
        with self._lock:
            if not self.known:
                raise StageError("position unknown: set the top first (lio stage set-top)")
            a = self.abs
            assert a is not None
            t = self.data.get("top")
            if t is not None and (a[0] >= t[0] or a[1] >= t[1]):
                raise StageError(f"the stage is not below the top (at {list(a)}, top {t})")
            self.data["bottom"] = list(a)
            self._log("mark_bottom", abs=list(a))
            self._save()

    def forget(self) -> None:
        """Position no longer trusted (moved by hand, steps lost): limits are kept."""
        with self._lock:
            self.data["abs"] = None
            self._abs_base = None
            self._log("forget")
            self._save()

    # ------------------------------------------------------------ soft limits

    def check_move(self, motor: int, steps: int, margin_top: int = 0) -> None:
        """Raise StageError if moving ``motor`` by ``steps`` leaves the marked range.

        The top is a hard physical end, so moves stay ``margin_top`` below it. With a
        limit not yet marked, that side is not limited; with the position unknown,
        nothing is (the operator is in charge)."""
        a = self.abs
        if a is None:
            return
        lim = self.limits
        i = motor - 1
        target = a[i] + steps
        if steps > 0 and lim.top is not None and target > lim.top[i] - margin_top:
            raise StageError(
                f"motor {motor}: {steps:+d} would end at {target}, above the top limit "
                f"({lim.top[i]} - margin {margin_top}); at most {lim.top[i] - margin_top - a[i]:+d}"
            )
        if steps < 0 and lim.bottom is not None and target < lim.bottom[i]:
            raise StageError(
                f"motor {motor}: {steps:+d} would end at {target}, below the bottom limit "
                f"({lim.bottom[i]}); at most {lim.bottom[i] - a[i]:+d}"
            )

    def room(self, motor: int, sign: int, margin_top: int = 0) -> int | None:
        """Half-steps left before the limit in direction ``sign`` (None: no limit)."""
        a = self.abs
        if a is None:
            return None
        lim = self.limits
        i = motor - 1
        if sign > 0:
            return None if lim.top is None else lim.top[i] - margin_top - a[i]
        return None if lim.bottom is None else a[i] - lim.bottom[i]
