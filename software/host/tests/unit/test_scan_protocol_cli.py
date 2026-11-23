"""CLI protocol paths must stay offline (no serial / POWER WAKE / MOTOR ARM)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lio.cli import build_parser
from lio.config import load_config

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
EXAMPLE = (
    REPO
    / "software"
    / "host"
    / "src"
    / "lio"
    / "scan"
    / "examples"
    / "stationary_targeted_h12.json"
)
CFG = REPO / "software" / "config" / "lio_hw.yaml"


def test_plan_protocol_does_not_open_serial_or_wake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    opened = {"serial": 0, "wake": 0, "arm": 0, "device": 0}

    class BoomSerial:
        def __init__(self, *a, **k):
            opened["serial"] += 1
            raise AssertionError("SerialTransport must not be constructed for protocol plan")

        def open(self):
            opened["serial"] += 1
            raise AssertionError("SerialTransport.open")

    def boom_device(*a, **k):
        opened["device"] += 1
        raise AssertionError("LIODevice must not be constructed for protocol plan")

    monkeypatch.setattr("lio.transport.SerialTransport", BoomSerial)
    monkeypatch.setattr("lio.cli.SerialTransport", BoomSerial)
    monkeypatch.setattr("lio.cli.LIODevice", boom_device)

    # Also patch device module in case of alternate imports.
    import lio.device as device_mod

    real_power_wake = device_mod.LIODevice.power_wake
    real_motor_arm = device_mod.LIODevice.motor_arm

    def wake(self, *a, **k):
        opened["wake"] += 1
        return real_power_wake(self, *a, **k)

    def arm(self, *a, **k):
        opened["arm"] += 1
        return real_motor_arm(self, *a, **k)

    monkeypatch.setattr(device_mod.LIODevice, "power_wake", wake)
    monkeypatch.setattr(device_mod.LIODevice, "motor_arm", arm)

    out = tmp_path / "plan.json"
    parser = build_parser()
    args = parser.parse_args(
        ["--config", str(CFG), "scan", "plan", "--protocol", str(EXAMPLE), "--json", str(out)]
    )
    # Invoke command function directly (same as main routing).
    cfg = load_config(CFG)
    rc = args.fn(args, cfg)
    assert rc == 0
    assert opened["serial"] == 0
    assert opened["device"] == 0
    assert opened["wake"] == 0
    assert opened["arm"] == 0
    data = json.loads(out.read_text())
    assert data["stationary"] is True
    assert data["arms_motors"] is False


def test_legacy_plan_offline_no_device(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def boom_device(*a, **k):
        raise AssertionError("LIODevice must not be constructed for legacy offline plan")

    monkeypatch.setattr("lio.cli.LIODevice", boom_device)
    parser = build_parser()
    args = parser.parse_args(
        ["--config", str(CFG), "scan", "plan", "--mode", "quick_down", "--json", str(tmp_path / "p.json")]
    )
    cfg = load_config(CFG)
    assert args.fn(args, cfg) == 0


def test_protocol_mutex_with_mode() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["--config", str(CFG), "scan", "plan", "--protocol", str(EXAMPLE), "--mode", "quick"]
    )
    cfg = load_config(CFG)
    from lio.cli import CliError

    with pytest.raises(CliError, match="mutually exclusive"):
        args.fn(args, cfg)
