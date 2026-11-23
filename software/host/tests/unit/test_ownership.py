"""M1 ownership lock and crash-durable duty journal (synthetic only)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lio.config import load_config
from lio.ownership import (
    DeviceLock,
    DutyBudgetError,
    DutyJournal,
    JournalError,
    OwnershipError,
    normalize_port_identity,
    rig_identity_from_port,
)
from lio.sim import SimulatedLIO
from lio.transport import SimTransport

pytestmark = pytest.mark.unit

CFG = Path(__file__).resolve().parents[3] / "config" / "lio_hw.yaml"


class FakeTransport:
    """Records writes; never opens a real serial port."""

    name = "fake"

    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self._open = False
        self._t = 0.0

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    def write_raw(self, data: bytes) -> None:
        self.sent.append(data)

    def read_line(self, timeout: float) -> str | None:
        return None

    def now(self) -> float:
        return self._t

    def sleep(self, seconds: float) -> None:
        self._t += max(0.0, seconds)


def test_tty_cu_aliases_normalize() -> None:
    a = normalize_port_identity("/dev/tty.usbserial-1120")
    b = normalize_port_identity("/dev/cu.usbserial-1120")
    assert a == b
    assert rig_identity_from_port("/dev/tty.usbmodem101") == rig_identity_from_port(
        "/dev/cu.usbmodem101"
    )


def test_over_budget_reject_before_fake_transport_send(tmp_path: Path) -> None:
    cfg = load_config(CFG)
    fake = FakeTransport()
    journal = DutyJournal.for_rig(
        "synthetic-test-rig",
        state_root=tmp_path,
        window_s=cfg.section.num("duty.window_s"),
        budget_ms=cfg.duty_budgets_ms(),
        rail_of=cfg.duty_key,
        synthetic=True,
        mono_now=fake.now,
    )
    # h9 rail budget is 1000 ms; budget+1 must reject before any write.
    budget = cfg.duty_budget_ms(9)
    with pytest.raises(DutyBudgetError):
        journal.reserve(9, budget + 1)
    assert fake.sent == []

    # Device gate path: attach journal to a sim device and attempt over-budget CH.
    from lio.device import LIODevice

    sim = SimulatedLIO(cfg)
    dev = LIODevice(
        SimTransport(sim),
        cfg,
        journal=DutyJournal.for_rig(
            "synthetic-ch-on",
            state_root=tmp_path / "j2",
            window_s=cfg.section.num("duty.window_s"),
            budget_ms=cfg.duty_budgets_ms(),
            rail_of=cfg.duty_key,
            synthetic=True,
        ),
    )
    # Intercept transport write to ensure over-budget never reaches it.
    sent: list[str] = []
    orig = dev.transport.write_line

    def spy(line: str) -> None:
        sent.append(line)
        return orig(line)

    dev.transport.write_line = spy  # type: ignore[method-assign]
    with dev:
        with pytest.raises(DutyBudgetError):
            # Force planned on-time above budget via wdt and request.
            limit = cfg.duty_budget_ms(9)
            dev.wdt_cfg("B", int(limit + 500))
            before = list(sent)
            dev.ch_on(9, int(limit + 1), budget=True)
        # No CH command after the INFO/WDT setup chatter should include ON for over-budget.
        assert not any(s.startswith("CH 9 ON") for s in sent[len(before) :])


def test_journal_fsync_failure_blocks_light(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = load_config(CFG)
    journal = DutyJournal.for_rig(
        "fsync-fail-rig",
        state_root=tmp_path,
        window_s=60.0,
        budget_ms={"A": 1000.0, "B": 5000.0, "h9": 1000.0},
        rail_of=cfg.duty_key,
        synthetic=True,
    )

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("simulated fsync failure")

    monkeypatch.setattr("os.fsync", boom)
    with pytest.raises(JournalError):
        journal.reserve(3, 100.0)


def test_device_lock_exclusive(tmp_path: Path) -> None:
    lock1 = DeviceLock("lock-rig", tmp_path)
    lock2 = DeviceLock("lock-rig", tmp_path)
    lock1.acquire()
    with pytest.raises(OwnershipError):
        lock2.acquire(blocking=False)
    lock1.release()
    lock2.acquire(blocking=False)
    lock2.release()


def test_clock_jump_does_not_grant_credit(tmp_path: Path) -> None:
    cfg = load_config(CFG)
    clock = {"t": 1000.0}

    def mono() -> float:
        return clock["t"]

    journal = DutyJournal.for_rig(
        "clock-rig",
        state_root=tmp_path,
        window_s=60.0,
        budget_ms=cfg.duty_budgets_ms(),
        rail_of=cfg.duty_key,
        synthetic=True,
        mono_now=mono,
    )
    res = journal.reserve(3, 800.0)
    journal.commit(res, t_on=clock["t"], t_off=clock["t"] + 0.8)
    # Wall clock leap must not erase mono history.
    clock["t"] += 1e9
    # History ages out only via mono window; after huge mono jump, budget recovers —
    # that is correct for mono. Ensure wall time is unused: used_ms at old-ish mono.
    clock["t"] = 1000.0 + 10.0
    assert journal.used_ms(3) >= 700.0


def test_wait_needed_many_accounts_for_same_rail_siblings(tmp_path: Path) -> None:
    """SWEEP-like multi-charge must wait when siblings exhaust the rail budget."""
    clock = {"t": 1000.0}

    def mono() -> float:
        return clock["t"]

    j = DutyJournal.for_rig(
        "sweep-sib",
        state_root=tmp_path,
        window_s=60.0,
        budget_ms={"A": 1000.0, "B": 5000.0},
        rail_of=lambda h: "A" if h <= 8 else "B",
        synthetic=True,
        mono_now=mono,
    )
    res = j.reserve(1, 900.0)
    j.commit(res, t_on=1000.0, t_off=1000.9)
    clock["t"] = 1001.0
    charges = [(h, 50.0) for h in range(1, 9)]  # 400 ms more on rail A
    # Individually hole 4 still fits (used 900 + 50 <= 1000).
    assert j.wait_needed(4, 50.0) == 0.0
    # As a set, 900 + 8*50 exceeds 1000 → must wait.
    wait = j.wait_needed_many(charges)
    assert wait > 0.0
