from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from lio.transport import PortInfo, SerialTransport, TransportError, list_ports, pick_port

pytestmark = pytest.mark.unit


class TestSerialLoopback:
    def test_round_trip_and_transcript(self) -> None:
        log = io.StringIO()
        t = SerialTransport("loop://", transcript=log)
        assert not t.is_open
        with t:
            assert t.is_open
            t.write_line("PING")
            assert t.read_line(1.0) == "PING"
            t.write_raw(b"a\r\nb")
            assert t.read_line(1.0) == "a"
            assert t.read_line(0.1) is None  # "b" has no newline yet
            t.write_raw(b"\n")
            assert t.read_line(1.0) == "b"
            t0 = t.now()
            t.sleep(0.01)
            t.sleep(0)
            assert t.now() >= t0
        assert not t.is_open
        assert "> PING" in log.getvalue() and "< PING" in log.getvalue()

    def test_not_open(self) -> None:
        t = SerialTransport("loop://")
        with pytest.raises(TransportError):
            t.write_line("PING")
        with pytest.raises(TransportError):
            t.read_line(0.1)
        t.close()  # closing a closed port is harmless

    def test_open_failure(self) -> None:
        with pytest.raises(TransportError, match="cannot open"):
            SerialTransport("/dev/does-not-exist-lio").open()


USB = [(0x1A86, 0x7523, "CH340"), (0x0403, 0x6001, "FTDI FT232R")]


def _fake(device: str, vid: int | None, pid: int | None, desc: str = "") -> SimpleNamespace:
    return SimpleNamespace(device=device, vid=vid, pid=pid, description=desc)


class TestPorts:
    def test_list_and_pick(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from serial.tools import list_ports as lp

        fakes = [
            _fake("/dev/cu.Bluetooth-Incoming-Port", None, None, "n/a"),
            _fake("/dev/tty.usbserial-1120", 0x1A86, 0x7523, "USB Serial"),
            _fake("/dev/cu.usbserial-1120", 0x1A86, 0x7523, "USB Serial"),
        ]
        monkeypatch.setattr(lp, "comports", lambda: fakes)
        ports = list_ports(USB)
        assert ports[0].likely_lio and ports[0].label == "CH340"
        assert not ports[-1].likely_lio
        picked = pick_port(ports)
        assert picked is not None and picked.device == "/dev/cu.usbserial-1120"

    def test_pick_ambiguous_or_none(self) -> None:
        a = PortInfo("/dev/cu.usbserial-1", 0x1A86, 0x7523, "", "CH340")
        b = PortInfo("/dev/cu.usbserial-2", 0x0403, 0x6001, "", "FTDI FT232R")
        n = PortInfo("/dev/cu.debug-console", None, None, "", None)
        assert pick_port([a, b]) is None
        assert pick_port([n]) is None
        assert pick_port([a, n]) == a
