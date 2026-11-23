"""Actual-caller regressions A01-A03, A13, A23, A24 (managed device boundary).

Catalogue: docs/research/LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md.

The device under test runs the REAL serial branch: :class:`FakeSerial` subclasses
:class:`SerialTransport` (so LIODevice takes its managed-serial path: canonical
lease, durable journal, real-port exposure admission) and delegates only the OS
I/O to the simulator. Faults are injected at the transport boundary by
rewriting firmware reply lines; the gate, journal and checks being proved run
unmocked. Physical serial opens are trapped.
"""

from __future__ import annotations

import contextlib
import json
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from lio.config import HwConfig, load_config, parse_config
from lio.device import LIODevice
from lio.ownership import (
    DeviceLock,
    DutyBudgetError,
    JournalError,
    OwnershipError,
    rig_identity_from_port,
)
from lio.results import Status, TestResult
from lio.sim import SimulatedLIO
from lio.suite.core import REGISTRY, SuiteContext, catalogue, run_test
from lio.transport import SerialTransport, SimTransport

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
CFG = REPO / "software" / "config" / "lio_hw.yaml"


@pytest.fixture(autouse=True)
def _no_physical_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    import serial

    def trap(*_a: object, **_k: object) -> None:
        raise AssertionError("a physical serial port was opened by a unit test")

    monkeypatch.setattr(serial, "serial_for_url", trap)
    monkeypatch.setattr(serial, "Serial", trap)


@pytest.fixture()
def cfg() -> HwConfig:
    return load_config(CFG)


class FakeSerial(SerialTransport):
    """Managed serial branch; OS I/O delegated to the simulator.

    ``rewrite`` may replace or drop (return None) any line the board sends.
    ``writes`` records every byte string actually transmitted.
    """

    def __init__(self, sim: SimulatedLIO, port: str) -> None:
        super().__init__(port)
        self.sim_t = SimTransport(sim)
        self.writes: list[bytes] = []
        self.rewrite: Callable[[str], str | None] | None = None

    def open(self) -> None:
        self.sim_t.open()

    def close(self) -> None:
        if self.sim_t.is_open:
            self.sim_t.close()

    @property
    def is_open(self) -> bool:
        return self.sim_t.is_open

    def write_raw(self, data: bytes) -> None:
        self.writes.append(bytes(data))
        self.sim_t.write_raw(data)

    def read_line(self, timeout: float) -> str | None:
        line = self.sim_t.read_line(timeout)
        if line is not None and self.rewrite is not None:
            return self.rewrite(line)
        return line

    def now(self) -> float:
        return self.sim_t.now()

    def sleep(self, seconds: float) -> None:
        self.sim_t.sleep(seconds)

    def sent(self, word: str) -> list[str]:
        out = []
        for w in self.writes:
            text = w.decode("ascii", "replace")
            if re.search(rf"(^|[\s@\d])\b{word}\b", text.upper()):
                out.append(text)
        return out


def managed(
    cfg: HwConfig, tmp_path: Path, name: str = "rig"
) -> tuple[LIODevice, FakeSerial, SimulatedLIO]:
    sim = SimulatedLIO(cfg)
    port = str(tmp_path / f"ttyFAKE-{name}")  # unique synthetic identity
    t = FakeSerial(sim, port)
    dev = LIODevice(t, cfg, state_root=tmp_path / "state")
    assert dev.journal is not None and dev.device_lock is not None  # real serial branch
    return dev, t, sim


@contextlib.contextmanager
def opened(
    cfg: HwConfig, tmp_path: Path, name: str = "rig"
) -> Iterator[tuple[LIODevice, FakeSerial, SimulatedLIO]]:
    dev, t, sim = managed(cfg, tmp_path, name)
    dev.open()
    try:
        yield dev, t, sim
    finally:
        t.rewrite = None
        dev.close()


def journal_json(dev: LIODevice) -> dict:
    assert dev.journal is not None
    return json.loads(dev.journal.path.read_text())


def charged_ms(dev: LIODevice, key: str) -> float:
    """Total retained/committed charge for a rail key in the durable journal."""
    spans = (journal_json(dev).get("history") or {}).get(key, [])
    return sum((float(s["t1"]) - float(s["t0"])) * 1000.0 for s in spans)


# ------------------------------------------------------------------ A01 / D01


@pytest.mark.parametrize(
    "payload",
    [
        b"@123\tCH 1 ON 1500\n",
        b"@123 \t CH 1 ON 1500\n",
        b"@x\tCH 1 ON 1500\n",
        b"\t@7\tch\t1\ton\n",
        b"@1\tCE 1 1\n",
        b"@9\tMEAS 1\n",
    ],
)
def test_a01_tab_sequence_prefix_refused_before_emission(
    cfg: HwConfig, tmp_path: Path, payload: bytes
) -> None:
    with opened(cfg, tmp_path) as (dev, t, sim):
        n = len(t.writes)
        with pytest.raises(OwnershipError):
            dev.send_raw(payload, 0.1)
        assert t.writes[n:] == []  # nothing transmitted at all
        st = dev.status()
        assert st.as_int("ce1") == 0 and st.as_int("ce2") == 0
        assert not sim.ce[1] and not sim.ce[2]


def test_a01_positive_controls_preserved(cfg: HwConfig, tmp_path: Path) -> None:
    with opened(cfg, tmp_path) as (dev, t, _sim):
        # Non-emitting sequence-wrapped PING still reaches firmware (T02.5).
        r = dev.send_raw(b"@42\tPING\n", 1.0)
        assert r is not None and r.ok and r.seq == 42
        # Literal fragments still refuse.
        with pytest.raises(OwnershipError):
            dev.send_raw(b"C", 0.01)
        # The refused b'C' was never forwarded, so the board only sees 'H ...'.
        with contextlib.suppress(OwnershipError):
            dev.send_raw(b"H 1 ON 1500\n", 0.01)
        assert not t.sent("CH")


# ------------------------------------------------------------------ A02 / D03


def test_a02_failed_open_releases_lease(cfg: HwConfig, tmp_path: Path) -> None:
    dev, t, _sim = managed(cfg, tmp_path)
    assert dev.journal is not None and dev.device_lock is not None
    path = dev.journal.path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json")
    with pytest.raises(JournalError):
        dev.open()
    assert not t.is_open
    # The leaked-lease bug blocked any next owner of the same rig identity.
    nxt = DeviceLock(dev.device_lock.rig_identity, tmp_path / "state")
    nxt.acquire()
    nxt.release()


def test_a02_aliases_share_one_lease(cfg: HwConfig, tmp_path: Path) -> None:
    real = tmp_path / "ttyREAL"
    real.write_text("")
    alias = tmp_path / "by-id-alias"
    alias.symlink_to(real)
    a = DeviceLock(rig_identity_from_port(str(real)), tmp_path / "state")
    b_id = rig_identity_from_port(str(alias))
    assert a.rig_identity == b_id
    a.acquire()
    try:
        with pytest.raises(OwnershipError):
            DeviceLock(b_id, tmp_path / "state").acquire()
    finally:
        a.release()


def test_a02_fresh_generation_rejects_stale_completion(cfg: HwConfig, tmp_path: Path) -> None:
    dev, _t, _sim = managed(cfg, tmp_path)
    assert dev.journal is not None
    dev.journal.reload()
    res = dev.journal.reserve(3, 50.0)
    gen1 = dev.journal.owner_generation
    dev.journal.reload()  # a new lease: pending absorbed, new generation
    assert dev.journal.owner_generation != gen1
    with pytest.raises(OwnershipError):
        dev.journal.commit(res, t_on=0.0, t_off=0.05)


def test_a02_clock_discontinuity_grants_no_credit(cfg: HwConfig, tmp_path: Path) -> None:
    from lio.ownership import DutyJournal

    clock = {"t": 5000.0}
    path = tmp_path / "j.json"

    def make() -> DutyJournal:
        return DutyJournal.for_rig(
            "synthetic-disc",
            state_root=tmp_path,
            window_s=60.0,
            budget_ms={"A": 1000.0, "B": 5000.0},
            rail_of=lambda h: "A" if h <= 8 else "B",
            path=path,
            mono_now=lambda: clock["t"],
        )

    j = make()
    res = j.reserve(3, 800.0)
    j.commit(res, t_on=clock["t"], t_off=clock["t"] + 0.8)
    clock["t"] = 10.0  # monotonic went backwards: reboot / unknown continuity
    j2 = make()
    j2.reload()
    # The 800 ms is still charged in the new frame: only 200 ms remain.
    assert j2.remaining_ms(3) == pytest.approx(200.0, abs=1.0)
    with pytest.raises(DutyBudgetError):
        j2.reserve(3, 500.0)


# ------------------------------------------------------------------ A03 / D04


def test_a03_ce_ack_then_contradictory_status_retains_charge(cfg: HwConfig, tmp_path: Path) -> None:
    with opened(cfg, tmp_path) as (dev, t, sim):
        dev.sr_raw(1 << 0)  # select hole 1 (RAIL A)
        sent_ce = {"done": False}

        def rewrite(line: str) -> str | None:
            if "OK CE" in line:
                sent_ce["done"] = True
            if sent_ce["done"] and "OK STATUS" in line:
                return re.sub(r"mask=0x[0-9A-Fa-f]+", "mask=0x0000", line)
            return line

        t.rewrite = rewrite
        with pytest.raises(OwnershipError):
            dev.ce(1, True)
        assert sim.ce[1]  # the board really did drive CE1 high
        j = journal_json(dev)
        assert j["uncertain"] is True and j["pending"] is None
        assert charged_ms(dev, "A") >= 50.0 - 1e-6  # full conservative charge retained
        t.rewrite = None
        # New light is blocked on this connection until a verified OFF.
        n = len(t.writes)
        with pytest.raises(OwnershipError, match="blocked"):
            dev.meas(2)
        assert not any(b"MEAS" in w for w in t.writes[n:])
        dev.off()  # verified OFF clears the block (journal cooldown still applies)
        assert dev.light_blocked is None


def test_a03_unknown_ce_error_retains_charge(cfg: HwConfig, tmp_path: Path) -> None:
    with opened(cfg, tmp_path) as (dev, t, sim):
        dev.sr_raw(1 << 0)

        def rewrite(line: str) -> str | None:
            m = re.match(r"^(@\d+ )OK CE\b.*$", line)
            return f"{m.group(1)}ERR CE code=99 msg=injected" if m else line

        t.rewrite = rewrite
        with pytest.raises(Exception):  # noqa: B017 - any error; state is what matters
            dev.ce(1, True)
        assert sim.ce[1]
        assert journal_json(dev)["uncertain"] is True
        assert charged_ms(dev, "A") >= 50.0 - 1e-6


def test_a03_known_wrong_rail_refusal_does_not_poison(cfg: HwConfig, tmp_path: Path) -> None:
    """Positive control: definite firmware refusal with CE verified low."""
    with opened(cfg, tmp_path) as (dev, _t, sim):
        dev.sr_raw(1 << 0)  # hole 1 is RAIL A
        with pytest.raises(Exception):  # noqa: B017
            dev.ce(2, True)  # wrong rail: firmware refuses before setting CE
        assert not sim.ce[2]
        j = journal_json(dev)
        assert j["uncertain"] is False and j["pending"] is None
        dev.sr_raw(0)
        m = dev.meas(4)  # following MEAS works
        assert m.hole == 4


# ------------------------------------------------------------------ A13 / T10.2


def test_a13_t10_2_post_emission_off_failure_is_fail_not_skip(
    cfg: HwConfig, tmp_path: Path
) -> None:
    catalogue()
    dev, t, sim = managed(cfg, tmp_path)
    dev.open()
    try:
        ctx = SuiteContext(dev, cfg, "fake-serial", sim)
        seen_ch = {"b": False}

        def rewrite(line: str) -> str | None:
            if re.search(r"OK CH ch=1[0-6]\b|OK CH ch=9\b", line):
                seen_ch["b"] = True
            m = re.match(r"^(@\d+ )OK OFF\s*$", line)
            if seen_ch["b"] and m:
                return f"{m.group(1)}ERR OFF code=4 msg=injected"
            return line

        t.rewrite = rewrite
        r: TestResult = run_test(ctx, REGISTRY["T10.2"])
        t.rewrite = None
        subs = {s.id: s for s in r.subs}
        b_fail = [
            s for s in subs.values() if s.id.startswith("T10.2/B/") and s.status == Status.FAIL
        ]
        assert b_fail, r.summary()
        assert "after the pulse was transmitted" in b_fail[0].message
        assert not [
            s for s in subs.values() if s.id.startswith("T10.2/B/") and s.status == Status.SKIP
        ]
        assert r.status in (Status.FAIL, Status.ERROR)
        assert journal_json(dev)["uncertain"] is True
    finally:
        t.rewrite = None
        dev.close()


def test_a13_pre_send_budget_refusal_is_skip(cfg: HwConfig, tmp_path: Path) -> None:
    """Positive control: RAIL A default 2000 ms WDT vs 1000 ms budget refuses before send."""
    catalogue()
    dev, _t, sim = managed(cfg, tmp_path)
    dev.open()
    try:
        ctx = SuiteContext(dev, cfg, "fake-serial", sim)
        r = run_test(ctx, REGISTRY["T10.2"])
        a = [s for s in r.subs if s.id.startswith("T10.2/A/")]
        assert a and a[0].status == Status.SKIP
        assert "before transmission" in a[0].message
    finally:
        dev.close()


# ------------------------------------------------------------------ A23 / D05


def test_a23_wrong_wdt_ack_refuses_before_light(cfg: HwConfig, tmp_path: Path) -> None:
    with opened(cfg, tmp_path) as (dev, t, _sim):

        def rewrite(line: str) -> str | None:
            return re.sub(r"(OK WDT rail=A ms=)\d+", r"\g<1>2000", line)

        t.rewrite = rewrite
        n = len(t.writes)
        with pytest.raises(DutyBudgetError, match="WDT"):
            dev.meas(3)
        assert not any(b"MEAS" in w for w in t.writes[n:])
        j = journal_json(dev)
        assert j["pending"] is None


def test_a23_missing_wdt_readback_refuses(cfg: HwConfig, tmp_path: Path) -> None:
    with opened(cfg, tmp_path) as (dev, t, _sim):

        def rewrite(line: str) -> str | None:
            return re.sub(r"wdt_a_ms=\d+", "wdt_a_ms=xx", line)

        t.rewrite = rewrite
        n = len(t.writes)
        with pytest.raises(DutyBudgetError):
            dev.meas(3)
        assert not any(b"MEAS" in w for w in t.writes[n:])


@pytest.mark.parametrize(
    "pattern,repl",
    [(r"OK MEAS ch=3\b", "OK MEAS ch=4"), (r"^(@\d+ )OK MEAS", r"\g<1>OK MEAZ"),
     (r"settle_ms=8\b", "settle_ms=9")],
)  # fmt: skip
def test_a23_wrong_meas_reply_retains_charge(
    cfg: HwConfig, tmp_path: Path, pattern: str, repl: str
) -> None:
    with opened(cfg, tmp_path) as (dev, t, _sim):
        t.rewrite = lambda line: re.sub(pattern, repl, line) if "MEAS" in line else line
        with pytest.raises(DutyBudgetError, match="does not match"):
            dev.meas(3)
        j = journal_json(dev)
        assert j["uncertain"] is True and charged_ms(dev, "A") >= 50.0 - 1e-6


def test_a23_wrong_rail_debug_bounds_energized_rail(cfg: HwConfig, tmp_path: Path) -> None:
    with opened(cfg, tmp_path) as (dev, t, _sim):
        n = len(t.writes)
        dev.dbg_state("wrong_rail", 3, 8, 1)  # hole 3 on A: CE2 (rail B) is energized
        cfgs = [w for w in t.writes[n:] if b"WDT CFG" in w]
        assert any(b"WDT CFG B" in w for w in cfgs)  # energized rail set to the need
        info = dev.info(refresh=True)
        assert info.as_int("wdt_b_ms") <= 50


def test_a23_real_port_without_bound_refuses(cfg: HwConfig, tmp_path: Path) -> None:
    data = dict(cfg.data)
    data["timing"] = {"real_port_admission": "refuse"}
    strict = parse_config(data, cfg.path)
    with opened(strict, tmp_path) as (dev, t, _sim):
        assert dev.exposure_bound == "refused"
        n = len(t.writes)
        with pytest.raises(DutyBudgetError, match="no finite exposure bound"):
            dev.meas(3)
        assert not any(b"MEAS" in w for w in t.writes[n:])


def test_a23_acknowledged_real_port_is_labelled(cfg: HwConfig, tmp_path: Path) -> None:
    with opened(cfg, tmp_path) as (dev, _t, _sim):
        assert dev.exposure_bound == "cooperative_unproven"


# ------------------------------------------------------------------ A24 / D02, D04


def test_a24_sweep_keeps_full_reserved_charge(cfg: HwConfig, tmp_path: Path) -> None:
    with opened(cfg, tmp_path) as (dev, _t, _sim):
        before = {k: charged_ms(dev, k) for k in ("A", "B", "h9")}
        sw = dev.sweep()
        assert len(sw.records) == 16
        a = charged_ms(dev, "A") - before["A"]
        reported = sum(m.t_on_ms for m in sw.records if m.hole <= 8)
        assert a >= 8 * 50.0 - 1e-6  # every hole keeps its reserved 50 ms bound
        assert a > reported  # no refund down to reported/invented edges


def test_a24_safe_off_err_and_missing_status_retains(cfg: HwConfig, tmp_path: Path) -> None:
    dev, t, sim = managed(cfg, tmp_path)
    dev.open()
    try:
        dev.ch_on(4, 40)
        assert sim.ce[1]

        def rewrite(line: str) -> str | None:
            m = re.match(r"^(@\d+ )OK OFF\s*$", line)
            if m:
                return f"{m.group(1)}ERR OFF code=4 msg=injected"
            if "OK STATUS" in line:
                return None  # STATUS never arrives
            return line

        t.rewrite = rewrite
        dev.safe_off()
        j = journal_json(dev)
        assert j["uncertain"] is True and j["pending"] is None
        assert charged_ms(dev, "A") >= 40.0 - 1e-6
        assert dev.light_blocked
    finally:
        t.rewrite = None
        dev.close()
