"""The lio command line against the simulator (no hardware)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lio import cli
from lio.config import HwConfig
from lio.csvout import SWEEP_HEADER

pytestmark = pytest.mark.unit


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    code = cli.main(list(argv))
    out = capsys.readouterr()
    return code, out.out + out.err


def test_info_status_ping(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys, "--sim", "info")
    assert code == 0 and "arm_token" in out and "# BOOT" in out
    code, out = run(capsys, "--sim", "status")
    assert code == 0 and "mask" in out
    code, out = run(capsys, "--sim", "ping", "-n", "5")
    assert code == 0 and "5 pings" in out


def test_ch_meas_off(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys, "--sim", "ch", "3", "on", "--ms", "100")
    assert code == 0 and "on for 100 ms" in out and "# OFF ch=3" in out
    code, out = run(capsys, "--sim", "ch", "13", "on")
    assert code == 0 and "on for 5000 ms" in out and "# WDT ch=13" in out
    code, out = run(capsys, "--sim", "meas", "8")
    assert code == 0 and "opt101" in out and "ingaas" in out
    assert run(capsys, "--sim", "off")[0] == 0


def test_sweep_csv_and_plot(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    csv_path, png = tmp_path / "s.csv", tmp_path / "s.png"
    code, _ = run(capsys, "--sim", "sweep", "--csv", str(csv_path), "--plot", str(png))
    assert code == 0 and png.stat().st_size > 1000
    text = csv_path.read_bytes().decode()
    assert text.startswith(",".join(SWEEP_HEADER) + "\r\n") and text.count("\r\n") == 17
    code, out = run(capsys, "--sim", "sweep")
    assert out.startswith("hole,label")


def test_motor(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys, "--sim", "-y", "motor", "2", "step", "-32", "--rpm", "10")
    assert code == 0 and "# MOTOR m=2 steps=32 pos=-32 done" in out
    assert run(capsys, "--sim", "motor", "stop")[0] == 0
    assert run(capsys, "--sim", "motor", "release")[0] == 0
    assert "armed for" in run(capsys, "--sim", "motor", "arm")[1]
    code, out = run(capsys, "--sim", "motor", "1", "spin")
    assert code == cli.EXIT_ERROR and "usage" in out


def test_motor_asks_first(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    code, out = run(capsys, "--sim", "motor", "1", "step", "64")
    assert code == 0 and "not moved" in out


def test_selftest_modules_report_and_baseline(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    base = tmp_path / "baseline.yaml"
    code, out = run(
        capsys,
        "--sim",
        "selftest",
        "--modules",
        "channels,T03.2",
        "--results-dir",
        str(tmp_path / "a"),
        "--save-baseline",
        str(base),
    )
    assert code == 0 and "FUNCTIONAL" in out and base.exists()
    assert (tmp_path / "a" / "report.html").exists() and (tmp_path / "a" / "meas.csv").exists()
    code, out = run(
        capsys,
        "--sim",
        "--fault",
        "dead_channel:3",
        "selftest",
        "--modules",
        "channels",
        "--baseline",
        str(base),
        "--results-dir",
        str(tmp_path / "b"),
    )
    assert code == 1 and "T11.1" in out and "-100.0 %" in out
    code, out = run(capsys, "report", str(tmp_path / "b" / "results.json"))
    assert code == 0 and "report.html" in out


def test_selftest_not_functional_exit_code(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code, out = run(
        capsys,
        "--sim",
        "--fault",
        "no_adc",
        "selftest",
        "--modules",
        "adc",
        "--results-dir",
        str(tmp_path),
        "--save-baseline",
        str(tmp_path / "x.yaml"),
    )
    assert code == 2 and "not saving a baseline" in out


def test_selftest_selection(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code, out = run(
        capsys, "--sim", "selftest", "--modules", "nonsense", "--results-dir", str(tmp_path)
    )
    assert code == cli.EXIT_ERROR and "aliases" in out
    code, out = run(
        capsys,
        "--sim",
        "selftest",
        "--modules",
        "motors",
        "--allow-motion",
        "--results-dir",
        str(tmp_path),
    )
    assert code == 0 and "T09.2" in out


def test_errors(capsys: pytest.CaptureFixture[str], cfg: HwConfig) -> None:
    code, out = run(capsys, "--sim", "--fault", "bogus", "info")
    assert code == cli.EXIT_ERROR and "unknown fault" in out
    code, out = run(capsys, "--port", "/dev/does-not-exist", "info")
    assert code == cli.EXIT_ERROR and "cannot open" in out


def test_ports(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from lio.transport import PortInfo

    fake = [PortInfo("/dev/cu.usbserial-1120", 0x1A86, 0x7523, "USB Serial", "CH340")]
    monkeypatch.setattr(cli, "list_ports", lambda ids: fake)
    code, out = run(capsys, "ports")
    assert code == 0 and "* /dev/cu.usbserial-1120" in out and "CH340" in out


def test_shell(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    lines = iter(["help", "PING", "", "FROB", "quit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(lines))
    code, out = run(capsys, "--sim", "shell")
    assert code == 0 and "OK PING" in out and "ERR FROB code=1" in out
