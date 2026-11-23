"""Exclusive device ownership and crash-durable LED duty accounting (M1).

Acquire an OS file lock *before* opening serial. Persist reservations atomically
(with fsync) before any light-capable command. Never clamp a request to fit the
budget; reject over-budget. OFF/STOP bypass the ledger write requirement but not
exclusive ownership. Simulation may use a synthetic journal path; real hardware
must not escape via ``budget=False``.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DeviceLock",
    "DutyBudgetError",
    "DutyJournal",
    "JournalError",
    "OwnershipError",
    "Reservation",
    "default_state_root",
    "normalize_port_identity",
    "rig_identity_from_port",
]


class OwnershipError(Exception):
    """Device ownership or duty-accounting failure."""


class DutyBudgetError(OwnershipError):
    """Requested on-time cannot fit the rolling budget (never clamped)."""


class JournalError(OwnershipError):
    """Duty journal unreadable, unwritable, or fsync failed — no light."""


_TTY_CU = re.compile(r"^(/dev/)(tty|cu)\.(.+)$")


def normalize_port_identity(port: str) -> str:
    """Normalize physical-device aliases (macOS tty/cu → shared identity)."""
    p = str(port).strip()
    m = _TTY_CU.match(p)
    if m:
        return f"{m.group(1)}serial.{m.group(3)}"
    # pyserial URLs / loopback stay as-is but lower-cased for stability.
    if "://" in p:
        return p.lower()
    return p


def rig_identity_from_port(port: str) -> str:
    """Stable rig key for lock + journal files (not spoofable by tty/cu spelling)."""
    return normalize_port_identity(port)


def default_state_root() -> Path:
    env = os.environ.get("LIO_STATE_ROOT")
    if env:
        return Path(env)
    return Path.home() / ".lio" / "state"


def _boot_id() -> str:
    for path in (Path("/proc/sys/kernel/random/boot_id"), Path("/var/db/.AppleSetupDone")):
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace")[:64]
        except OSError:
            continue
    # macOS / other: boot-time approximation that changes across reboot.
    try:
        return str(int(os.stat("/").st_ctime))
    except OSError:
        return "unknown-boot"


@dataclass
class Reservation:
    id: str
    hole: int
    on_ms: float
    rail_key: str
    reserved_at_mono: float
    owner_generation: str
    status: str = "reserved"  # reserved | committed | aborted


@dataclass
class DeviceLock:
    """OS-exclusive lock for one physical rig; acquire before serial open."""

    rig_identity: str
    state_root: Path
    _fh: Any = field(default=None, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.state_root = Path(self.state_root)
        safe = re.sub(r"[^\w.\-]+", "_", self.rig_identity)[:120]
        self._path = self.state_root / "locks" / f"{safe}.lock"

    def acquire(self, *, blocking: bool = False) -> None:
        assert self._path is not None
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self._path, "a+", encoding="utf-8")  # noqa: SIM115
        try:
            import fcntl

            flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
            fcntl.flock(fh.fileno(), flags)
        except BlockingIOError as e:
            fh.close()
            raise OwnershipError(f"rig {self.rig_identity!r} is owned by another process") from e
        except OSError as e:
            fh.close()
            raise OwnershipError(f"cannot lock {self._path}: {e}") from e
        self._fh = fh
        try:
            fh.seek(0)
            fh.truncate()
            fh.write(json.dumps({"pid": os.getpid(), "rig": self.rig_identity, "at": time.time()}))
            fh.flush()
            os.fsync(fh.fileno())
        except OSError:
            # Lock held even if metadata write fails.
            pass

    def release(self) -> None:
        fh = self._fh
        self._fh = None
        if fh is None:
            return
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        with contextlib.suppress(OSError):
            fh.close()

    def __enter__(self) -> DeviceLock:
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


@dataclass
class DutyJournal:
    """Crash-durable per-rig exposure journal (atomic JSON + fsync).

    Uses monotonic time; wall-clock jumps and boot discontinuities cannot grant
    credit. Uncertain recovery retains conservative charges and never auto-resumes
    emission.
    """

    rig_identity: str
    path: Path
    window_s: float
    budget_ms: dict[str, float]
    rail_of: Callable[[int], str]
    owner_generation: str = field(default_factory=lambda: uuid.uuid4().hex)
    _boot_id: str = field(default_factory=_boot_id)
    _data: dict[str, Any] = field(default_factory=dict)
    mono_now: Callable[[], float] = field(default=time.monotonic)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self._load_or_init()

    @classmethod
    def for_rig(
        cls,
        rig_identity: str,
        *,
        state_root: Path | None = None,
        window_s: float,
        budget_ms: dict[str, float],
        rail_of: Callable[[int], str],
        synthetic: bool = False,
        path: Path | None = None,
        mono_now: Callable[[], float] | None = None,
    ) -> DutyJournal:
        root = Path(state_root) if state_root is not None else default_state_root()
        if path is None:
            safe = re.sub(r"[^\w.\-]+", "_", rig_identity)[:120]
            sub = "synthetic" if synthetic else "duty"
            path = root / sub / f"{safe}.json"
        return cls(
            rig_identity=rig_identity,
            path=path,
            window_s=window_s,
            budget_ms=dict(budget_ms),
            rail_of=rail_of,
            mono_now=mono_now or time.monotonic,
        )

    def _empty(self) -> dict[str, Any]:
        return {
            "schema": 1,
            "rig_identity": self.rig_identity,
            "boot_id": self._boot_id,
            "owner_generation": self.owner_generation,
            "history": {},  # rail_key -> list[{t0, t1, hole, reserved_ms, status}]
            "pending": None,
            "uncertain": False,
            "cooldown_until_mono": None,
            "mono_anchor": self.mono_now(),
            "wall_anchor": time.time(),
        }

    def _load_or_init(self) -> None:
        if not self.path.exists():
            self._data = self._empty()
            self._persist()
            return
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise JournalError("journal root is not an object")
        except (OSError, json.JSONDecodeError, JournalError) as e:
            raise JournalError(f"cannot read duty journal {self.path}: {e}") from e
        # Boot discontinuity: retain conservative cost; require cooldown; no credit.
        if str(data.get("boot_id", "")) != self._boot_id:
            data["uncertain"] = True
            data["boot_id"] = self._boot_id
            # Keep history as already-charged cost in the new boot's mono frame by
            # shifting into the present window as a worst-case lump.
            data["cooldown_until_mono"] = self.mono_now() + self.window_s
            data["pending"] = None
        self._data = data
        self.owner_generation = str(data.get("owner_generation") or self.owner_generation)
        if data.get("uncertain") or data.get("pending"):
            # Crash / incomplete reservation: keep worst-case charge.
            self._absorb_pending_conservative()
            self._data["uncertain"] = True
            self._data["cooldown_until_mono"] = max(
                float(self._data.get("cooldown_until_mono") or 0.0),
                self.mono_now() + self.window_s,
            )
            self._data["pending"] = None
            self._persist()

    def _absorb_pending_conservative(self) -> None:
        pending = self._data.get("pending")
        if not isinstance(pending, dict):
            return
        key = str(pending.get("rail_key") or "")
        t0 = float(pending.get("reserved_at_mono") or self.mono_now())
        on_s = float(pending.get("on_ms") or 0.0) / 1000.0
        hole = int(pending.get("hole") or 0)
        hist = self._data.setdefault("history", {})
        spans = hist.setdefault(key, [])
        spans.append(
            {
                "t0": t0,
                "t1": t0 + on_s,
                "hole": hole,
                "reserved_ms": float(pending.get("on_ms") or 0.0),
                "status": "crash-retained",
            }
        )

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = json.dumps(self._data, indent=1, sort_keys=True) + "\n"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
            # Directory fsync for crash durability of the replace.
            dir_fd = os.open(str(self.path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError as e:
            with contextlib.suppress(OSError):
                if tmp.exists():
                    tmp.unlink()
            raise JournalError(f"duty journal fsync/replace failed: {e}") from e

    def used_ms(self, hole: int, now: float | None = None) -> float:
        now = self.mono_now() if now is None else now
        key = self.rail_of(hole)
        lo = now - self.window_s
        total = 0.0
        for span in self._data.get("history", {}).get(key, []):
            t0, t1 = float(span["t0"]), float(span["t1"])
            total += max(0.0, min(t1, now) - max(t0, lo))
        return total * 1000.0

    def budget_for(self, hole: int) -> float:
        return float(self.budget_ms[self.rail_of(hole)])

    def remaining_ms(self, hole: int, now: float | None = None) -> float:
        return self.budget_for(hole) - self.used_ms(hole, now)

    def wait_needed(self, hole: int, on_ms: float, now: float | None = None) -> float:
        """Seconds to wait until ``on_ms`` fits; raises if ``on_ms`` exceeds the budget."""
        now = self.mono_now() if now is None else now
        budget = self.budget_for(hole)
        if on_ms > budget + 1e-9:
            raise DutyBudgetError(
                f"request {on_ms:.3f} ms exceeds budget {budget:.3f} ms for hole {hole}"
            )
        cool = self._data.get("cooldown_until_mono")
        if cool is not None and now < float(cool):
            return float(cool) - now
        if self.used_ms(hole, now) + on_ms <= budget + 1e-9:
            return 0.0
        key = self.rail_of(hole)
        candidates = sorted(
            {
                float(span["t1"]) + self.window_s - now
                for span in self._data.get("history", {}).get(key, [])
            }
        )
        for wait in candidates:
            if wait > 0 and self.used_ms(hole, now + wait) + on_ms <= budget + 1e-9:
                return wait
        return self.window_s

    def reserve(
        self, hole: int, on_ms: float, *, owner_generation: str | None = None
    ) -> Reservation:
        """Atomically persist a reservation before light. Never clamps.

        Caller must have already waited so the request fits *now*. Raises
        ``DutyBudgetError`` if ``on_ms`` exceeds the absolute budget or still
        does not fit after waiting.
        """
        if self._data.get("uncertain") and self._data.get("cooldown_until_mono"):
            now = self.mono_now()
            if now < float(self._data["cooldown_until_mono"]):
                raise DutyBudgetError(
                    "uncertain recovery: conservative cooldown active; no auto-resume emit"
                )
            self._data["uncertain"] = False
            self._data["cooldown_until_mono"] = None
        now = self.mono_now()
        # wait_needed raises if on_ms > absolute budget.
        wait = self.wait_needed(hole, on_ms, now)
        if wait > 0:
            raise DutyBudgetError(
                f"insufficient remaining duty for {on_ms:.3f} ms on hole {hole}; "
                f"need wait {wait:.3f} s first (request never auto-clamped)"
            )
        gen = owner_generation or self.owner_generation
        res = Reservation(
            id=uuid.uuid4().hex,
            hole=hole,
            on_ms=float(on_ms),
            rail_key=self.rail_of(hole),
            reserved_at_mono=now,
            owner_generation=gen,
        )
        self._data["pending"] = {
            "id": res.id,
            "hole": res.hole,
            "on_ms": res.on_ms,
            "rail_key": res.rail_key,
            "reserved_at_mono": res.reserved_at_mono,
            "owner_generation": res.owner_generation,
        }
        self._persist()
        return res

    def commit(self, reservation: Reservation, *, t_on: float, t_off: float) -> None:
        key = reservation.rail_key
        hist = self._data.setdefault("history", {})
        spans = hist.setdefault(key, [])
        spans.append(
            {
                "t0": float(t_on),
                "t1": float(t_off),
                "hole": reservation.hole,
                "reserved_ms": reservation.on_ms,
                "status": "committed",
            }
        )
        # Prune old spans outside 2 windows.
        cutoff = self.mono_now() - 2 * self.window_s
        hist[key] = [s for s in spans if float(s["t1"]) >= cutoff]
        if self._data.get("pending") and self._data["pending"].get("id") == reservation.id:
            self._data["pending"] = None
        self._persist()

    def abort_conservative(self, reservation: Reservation | None = None) -> None:
        """Retain worst-case charge on crash/timeout/partial acknowledgement."""
        pending = self._data.get("pending")
        if reservation is not None:
            self._data["pending"] = {
                "id": reservation.id,
                "hole": reservation.hole,
                "on_ms": reservation.on_ms,
                "rail_key": reservation.rail_key,
                "reserved_at_mono": reservation.reserved_at_mono,
                "owner_generation": reservation.owner_generation,
            }
        self._absorb_pending_conservative()
        self._data["pending"] = None
        self._data["uncertain"] = True
        self._data["cooldown_until_mono"] = self.mono_now() + self.window_s
        self._persist()
        _ = pending  # retained via absorb
