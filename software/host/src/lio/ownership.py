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
    """Best-effort boot identity. Never treat AppleSetupDone/root ctime as proof.

    Linux: ``/proc/sys/kernel/random/boot_id``. Elsewhere: conservative
    ``unknown-boot`` so discontinuities fail closed rather than inventing credit.
    """
    try:
        path = Path("/proc/sys/kernel/random/boot_id")
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace").strip()[:64]
    except OSError:
        pass
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
    # Constructors must not rewrite a live owner's journal (CE02). When False,
    # load read-only: no absorb/persist side effects until reload()/reserve().
    mutate_on_construct: bool = True
    # When True with mutate_on_construct=False: construct with empty in-memory
    # state and touch neither disk nor live journal until reload() under a lease.
    defer_load: bool = False

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.defer_load:
            self._data = self._empty()
            return
        if self.mutate_on_construct:
            self._load_or_init()
        else:
            self._load_readonly()

    def _load_readonly(self) -> None:
        """Load durable state without mutating disk (CE02)."""
        if not self.path.exists():
            self._data = self._empty()
            return
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise JournalError("journal root is not an object")
        except (OSError, json.JSONDecodeError, JournalError) as e:
            raise JournalError(f"cannot read duty journal {self.path}: {e}") from e
        self._data = data
        self.owner_generation = str(data.get("owner_generation") or self.owner_generation)

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
        mutate_on_construct: bool = True,
        defer_load: bool = False,
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
            mutate_on_construct=mutate_on_construct and not defer_load,
            defer_load=defer_load,
        )

    def _empty(self) -> dict[str, Any]:
        return {
            "schema": 1,
            "rig_identity": self.rig_identity,
            "boot_id": self._boot_id,
            "owner_generation": self.owner_generation,
            "history": {},  # rail_key -> list[{t0, t1, hole, reserved_ms, status}]
            # pending: None | single dict (legacy) | {"items": [dict, ...]} atomic set
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

    def _pending_items(self) -> list[dict[str, Any]]:
        pending = self._data.get("pending")
        if pending is None:
            return []
        if isinstance(pending, dict) and isinstance(pending.get("items"), list):
            return [p for p in pending["items"] if isinstance(p, dict)]
        if isinstance(pending, dict):
            return [pending]
        return []

    def _absorb_pending_conservative(self) -> None:
        pending = self._data.get("pending")
        if pending is None:
            return
        items = self._pending_items()
        hist = self._data.setdefault("history", {})
        for item in items:
            key = str(item.get("rail_key") or "")
            t0 = float(item.get("reserved_at_mono") or self.mono_now())
            on_s = float(item.get("on_ms") or 0.0) / 1000.0
            hole = int(item.get("hole") or 0)
            spans = hist.setdefault(key, [])
            spans.append(
                {
                    "t0": t0,
                    "t1": t0 + on_s,
                    "hole": hole,
                    "reserved_ms": float(item.get("on_ms") or 0.0),
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

    def reload(self) -> None:
        """Reload durable journal from disk under the current owner lease.

        Stale preconstructed journal objects must call this after lock acquire
        so prior charges cannot be erased from outdated in-memory state.
        """
        if not self.path.exists():
            self._data = self._empty()
            self._persist()
            return
        self._load_or_init()

    def used_ms(self, hole: int, now: float | None = None) -> float:
        now = self.mono_now() if now is None else now
        key = self.rail_of(hole)
        lo = now - self.window_s
        total = 0.0
        for span in self._data.get("history", {}).get(key, []):
            t0, t1 = float(span["t0"]), float(span["t1"])
            total += max(0.0, min(t1, now) - max(t0, lo))
        # Pending reservations count fully against remaining budget.
        for item in self._pending_items():
            if str(item.get("rail_key") or "") != key:
                continue
            total += float(item.get("on_ms") or 0.0) / 1000.0
        return total * 1000.0

    def budget_for(self, hole: int) -> float:
        return float(self.budget_ms[self.rail_of(hole)])

    def remaining_ms(self, hole: int, now: float | None = None) -> float:
        return self.budget_for(hole) - self.used_ms(hole, now)

    def wait_needed(self, hole: int, on_ms: float, now: float | None = None) -> float:
        """Seconds to wait until ``on_ms`` fits; raises if ``on_ms`` exceeds the budget."""
        return self.wait_needed_many([(hole, on_ms)], now=now)

    def wait_needed_many(self, charges: list[tuple[int, float]], now: float | None = None) -> float:
        """Seconds to wait until the whole charge set fits under rail budgets.

        Sibling charges on the same rail accumulate (SWEEP x16). Per-hole
        ``wait_needed`` alone under-counts and can report 0 s while
        ``reserve_many`` still refuses.
        """
        if not charges:
            return 0.0
        now = self.mono_now() if now is None else now
        for hole, on_ms in charges:
            budget = self.budget_for(hole)
            if on_ms > budget + 1e-9:
                raise DutyBudgetError(
                    f"request {on_ms:.3f} ms exceeds budget {budget:.3f} ms for hole {hole}"
                )
        cool = self._data.get("cooldown_until_mono")
        cool_wait = 0.0
        if cool is not None and now < float(cool):
            cool_wait = float(cool) - now

        def fits(at: float) -> bool:
            extra: dict[str, float] = {}
            for hole, on_ms in charges:
                key = self.rail_of(hole)
                budget = self.budget_for(hole)
                used = self.used_ms(hole, at) + extra.get(key, 0.0)
                if used + on_ms > budget + 1e-9:
                    return False
                extra[key] = extra.get(key, 0.0) + float(on_ms)
            return True

        if cool_wait <= 0 and fits(now):
            return 0.0
        keys = {self.rail_of(h) for h, _ in charges}
        candidates = sorted(
            {
                float(span["t1"]) + self.window_s - now
                for key in keys
                for span in self._data.get("history", {}).get(key, [])
            }
            | ({cool_wait} if cool_wait > 0 else set())
        )
        for wait in candidates:
            if wait > 0 and fits(now + wait):
                return wait
        return max(cool_wait, self.window_s)

    def _clear_uncertain_if_cooled(self) -> None:
        if self._data.get("uncertain") and self._data.get("cooldown_until_mono"):
            now = self.mono_now()
            if now < float(self._data["cooldown_until_mono"]):
                raise DutyBudgetError(
                    "uncertain recovery: conservative cooldown active; no auto-resume emit"
                )
            self._data["uncertain"] = False
            self._data["cooldown_until_mono"] = None

    def _reservation_dict(self, res: Reservation) -> dict[str, Any]:
        return {
            "id": res.id,
            "hole": res.hole,
            "on_ms": res.on_ms,
            "rail_key": res.rail_key,
            "reserved_at_mono": res.reserved_at_mono,
            "owner_generation": res.owner_generation,
        }

    def reserve(
        self, hole: int, on_ms: float, *, owner_generation: str | None = None
    ) -> Reservation:
        """Atomically persist a reservation before light. Never clamps.

        Caller must have already waited so the request fits *now*. Raises
        ``DutyBudgetError`` if ``on_ms`` exceeds the absolute budget or still
        does not fit after waiting.
        """
        return self.reserve_many([(hole, on_ms)], owner_generation=owner_generation)[0]

    def reserve_many(
        self,
        charges: list[tuple[int, float]],
        *,
        owner_generation: str | None = None,
    ) -> list[Reservation]:
        """Atomically reserve every potential exposure before send (e.g. SWEEP).

        All charges are validated against remaining budget (including prior
        pending items), then persisted as one pending set. Partial overwrite of
        a single pending slot is not permitted.
        """
        if not charges:
            raise DutyBudgetError("reserve_many requires at least one charge")
        if self._pending_items():
            raise DutyBudgetError(
                "cannot reserve while another pending set exists; commit or abort first"
            )
        self._clear_uncertain_if_cooled()
        now = self.mono_now()
        gen = owner_generation or self.owner_generation
        # Validate generation: stale owners cannot spend.
        if owner_generation is not None and owner_generation != self.owner_generation:
            raise OwnershipError(
                f"stale owner_generation {owner_generation!r} ≠ journal {self.owner_generation!r}"
            )
        # Check each charge fits; accumulate provisional pending for multi-rail.
        provisional: list[Reservation] = []
        # Simulate pending contribution for sequential same-rail checks.
        extra_used: dict[str, float] = {}
        for hole, on_ms in charges:
            budget = self.budget_for(hole)
            if on_ms > budget + 1e-9:
                raise DutyBudgetError(
                    f"request {on_ms:.3f} ms exceeds budget {budget:.3f} ms for hole {hole}"
                )
            key = self.rail_of(hole)
            used = self.used_ms(hole, now) + extra_used.get(key, 0.0)
            if used + on_ms > budget + 1e-9:
                wait = self.wait_needed(hole, on_ms, now)
                raise DutyBudgetError(
                    f"insufficient remaining duty for {on_ms:.3f} ms on hole {hole}; "
                    f"need wait {wait:.3f} s first (request never auto-clamped)"
                )
            res = Reservation(
                id=uuid.uuid4().hex,
                hole=int(hole),
                on_ms=float(on_ms),
                rail_key=key,
                reserved_at_mono=now,
                owner_generation=gen,
            )
            provisional.append(res)
            extra_used[key] = extra_used.get(key, 0.0) + float(on_ms)

        items = [self._reservation_dict(r) for r in provisional]
        if len(items) == 1:
            self._data["pending"] = items[0]
        else:
            self._data["pending"] = {"items": items}
        self._persist()
        return provisional

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
        items = self._pending_items()
        remaining = [p for p in items if p.get("id") != reservation.id]
        if not remaining:
            self._data["pending"] = None
        elif len(remaining) == 1:
            self._data["pending"] = remaining[0]
        else:
            self._data["pending"] = {"items": remaining}
        self._persist()

    def mark_uncertain(self, *, reason: str = "") -> None:
        """Retain uncertainty after failed/unverified OFF (CE04)."""
        self._data["uncertain"] = True
        self._data["cooldown_until_mono"] = max(
            float(self._data.get("cooldown_until_mono") or 0.0),
            self.mono_now() + self.window_s,
        )
        if reason:
            notes = self._data.setdefault("uncertain_reasons", [])
            if isinstance(notes, list):
                notes.append({"reason": reason, "mono": self.mono_now()})
        self._persist()

    def drop_pending(self) -> None:
        """Clear pending without absorbing charge or uncertain cooldown.

        Use when the firmware refused before any emission (e.g. wrong-rail CE):
        the reservation must not stick, and the suite must not be locked for a
        full duty window.
        """
        self._data["pending"] = None
        self._persist()

    def abort_conservative(
        self,
        reservation: Reservation | None = None,
        *,
        reservations: list[Reservation] | None = None,
    ) -> None:
        """Retain worst-case charge on crash/timeout/partial acknowledgement."""
        if reservations:
            self._data["pending"] = {"items": [self._reservation_dict(r) for r in reservations]}
        elif reservation is not None:
            # Merge into existing pending set rather than erasing siblings.
            existing = {p.get("id"): p for p in self._pending_items() if isinstance(p, dict)}
            existing[reservation.id] = self._reservation_dict(reservation)
            items = list(existing.values())
            self._data["pending"] = items[0] if len(items) == 1 else {"items": items}
        self._absorb_pending_conservative()
        self._data["pending"] = None
        self._data["uncertain"] = True
        self._data["cooldown_until_mono"] = self.mono_now() + self.window_s
        self._persist()

    def history_entries(self) -> list[dict[str, Any]]:
        """Flat list of committed/retained history spans (for tests/inspection)."""
        out: list[dict[str, Any]] = []
        for key, spans in (self._data.get("history") or {}).items():
            for span in spans:
                row = dict(span)
                row["rail_key"] = key
                out.append(row)
        return out
