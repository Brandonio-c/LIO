"""I2C DIAG: the diagnosis wording and the driver call."""

from __future__ import annotations

from typing import Any

import pytest

from lio.config import HwConfig
from lio.device import DeviceError, LIODevice
from lio.protocol import ErrCode
from lio.sim import Faults, SimulatedLIO
from lio.suite.checks.t03_t04_adc_sr import diagnose_i2c
from lio.transport import SimTransport

pytestmark = pytest.mark.unit

HEALTHY = {
    "sda": 1, "scl": 1, "sda_pu": 1, "scl_pu": 1, "bridge": 0,
    "ack_slow": 0, "ack_fast": 0, "slow_hz": 100000, "fast_hz": 400000,
    "hz": 400000, "present": 1,
}  # fmt: skip


def diag(**changes: int) -> dict[str, int]:
    return {**HEALTHY, **changes}


class TestDiagnosis:
    def test_healthy(self) -> None:
        ok, why = diagnose_i2c(HEALTHY, 0x48)
        assert ok and "answers at 400 kHz" in why

    def test_stuck_low(self) -> None:
        ok, why = diagnose_i2c(diag(scl=0, ack_slow=4, ack_fast=4, present=0), 0x48)
        assert not ok and why.startswith("SCL held low")

    def test_bridge(self) -> None:
        ok, why = diagnose_i2c(diag(bridge=1, ack_slow=2, ack_fast=2, present=0), 0x48)
        assert not ok and "SDA and SCL are joined" in why

    def test_no_pullups_and_no_answer(self) -> None:
        d = diag(sda_pu=0, scl_pu=0, ack_slow=2, ack_fast=2, present=0)
        ok, why = diagnose_i2c(d, 0x48)
        assert not ok and "SDA and SCL do not rise" in why and "no answer" in why

    def test_healthy_lines_no_answer_points_at_the_chip(self) -> None:
        ok, why = diagnose_i2c(diag(ack_slow=2, ack_fast=2, present=0), 0x48)
        assert ok and "ADDR -> GND" in why and "not swapped" in why

    def test_slow_only(self) -> None:
        ok, why = diagnose_i2c(diag(ack_fast=2, hz=100000), 0x48)
        assert ok and "fell back to 100 kHz" in why


class TestDriver:
    def test_sim_reports_bridge(self, cfg: HwConfig) -> None:
        sim = SimulatedLIO(cfg, Faults.parse("i2c_bridged"))
        with LIODevice(SimTransport(sim), cfg) as dev:
            d = dev.i2c_diag()
        assert d is not None and d["bridge"] == 1 and d["present"] == 0

    def test_older_firmware_returns_none(
        self, cfg: HwConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def old_firmware(self: LIODevice, line: str, **kw: Any) -> Any:
            raise DeviceError(line, ErrCode.BAD_ARG, "usage: I2C SCAN")

        sim = SimulatedLIO(cfg, Faults.parse(None))
        with LIODevice(SimTransport(sim), cfg) as dev:
            monkeypatch.setattr(LIODevice, "command", old_firmware)
            assert dev.i2c_diag() is None
            monkeypatch.undo()
