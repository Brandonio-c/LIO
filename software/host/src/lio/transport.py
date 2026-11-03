"""Byte transports: real USB serial, or the in-process simulator.

A transport moves whole lines and owns the clock. On real hardware the clock is
``time.monotonic``; with the simulator it is the simulator's virtual clock, so
long tests (60 s stability runs, 11 s comms-loss waits) finish instantly in CI.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    import serial

    from lio.sim import SimulatedLIO


class TransportError(Exception):
    """The link could not be opened, or failed while in use."""


class Transport(abc.ABC):
    """Line-oriented link to an LIO controller."""

    name: str = "transport"

    def __init__(self, transcript: TextIO | None = None) -> None:
        self.transcript = transcript

    @abc.abstractmethod
    def open(self) -> None:
        """Open the link. Opening resets the controller (DTR) on real hardware."""

    @abc.abstractmethod
    def close(self) -> None: ...

    @property
    @abc.abstractmethod
    def is_open(self) -> bool: ...

    @abc.abstractmethod
    def write_raw(self, data: bytes) -> None:
        """Write bytes exactly as given (robustness tests send garbage)."""

    @abc.abstractmethod
    def read_line(self, timeout: float) -> str | None:
        """Return the next complete line without its terminator, or None on timeout."""

    @abc.abstractmethod
    def now(self) -> float:
        """Seconds on this transport's clock (monotonic or virtual)."""

    @abc.abstractmethod
    def sleep(self, seconds: float) -> None: ...

    def write_line(self, line: str) -> None:
        self._log(">", line)
        self.write_raw((line + "\n").encode("ascii"))

    def _log(self, direction: str, line: str) -> None:
        if self.transcript is not None:
            self.transcript.write(f"{self.now():12.6f} {direction} {line}\n")

    def __enter__(self) -> Transport:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class SerialTransport(Transport):
    """pyserial link. Opening the port pulses DTR, which resets the Nano."""

    def __init__(self, port: str, baud: int = 115200, transcript: TextIO | None = None) -> None:
        super().__init__(transcript)
        self.port = port
        self.baud = baud
        self.name = port
        self._ser: serial.Serial | None = None
        self._buf = bytearray()

    def open(self) -> None:
        import serial  # imported lazily so the simulator works without pyserial

        try:
            # serial_for_url accepts device paths and pyserial URLs (loop://, socket://)
            self._ser = serial.serial_for_url(self.port, self.baud, timeout=0.05)
        except serial.SerialException as e:
            raise TransportError(f"cannot open {self.port}: {e}") from e
        self._buf.clear()

    def close(self) -> None:
        ser = self._ser
        self._ser = None
        if ser is not None:
            ser.close()

    @property
    def is_open(self) -> bool:
        return self._ser is not None

    def _serial(self) -> serial.Serial:
        if self._ser is None:
            raise TransportError("port is not open")
        return self._ser

    def write_raw(self, data: bytes) -> None:
        import serial

        ser = self._serial()
        try:
            ser.write(data)
            ser.flush()
        except serial.SerialException as e:
            raise TransportError(f"write failed on {self.port}: {e}") from e

    def read_line(self, timeout: float) -> str | None:
        import serial

        ser = self._serial()
        deadline = time.monotonic() + timeout
        while True:
            nl = self._buf.find(b"\n")
            if nl >= 0:
                raw = bytes(self._buf[:nl])
                del self._buf[: nl + 1]
                line = raw.decode("ascii", errors="replace").rstrip("\r")
                self._log("<", line)
                return line
            if time.monotonic() >= deadline:
                return None
            try:
                chunk = ser.read(256)
            except serial.SerialException as e:
                raise TransportError(f"read failed on {self.port}: {e}") from e
            if chunk:
                self._buf.extend(chunk)

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class SimTransport(Transport):
    """In-process link to :class:`lio.sim.SimulatedLIO` on its virtual clock."""

    name = "sim"

    def __init__(self, sim: SimulatedLIO, transcript: TextIO | None = None) -> None:
        super().__init__(transcript)
        self.sim = sim
        self._open = False

    def open(self) -> None:
        self.sim.port_opened()
        self._open = True

    def close(self) -> None:
        self._open = False
        self.sim.port_closed()

    @property
    def is_open(self) -> bool:
        return self._open

    def write_raw(self, data: bytes) -> None:
        if not self._open:
            raise TransportError("sim port is not open")
        self.sim.receive_bytes(data)

    def read_line(self, timeout: float) -> str | None:
        if not self._open:
            raise TransportError("sim port is not open")
        line = self.sim.next_output(timeout)
        if line is not None:
            self._log("<", line)
        return line

    def now(self) -> float:
        return self.sim.clock

    def sleep(self, seconds: float) -> None:
        self.sim.advance(seconds)


@dataclass(frozen=True)
class PortInfo:
    device: str
    vid: int | None
    pid: int | None
    description: str
    label: str | None  # matched USB-serial chip, e.g. "CH340"

    @property
    def likely_lio(self) -> bool:
        return self.label is not None


def list_ports(usb_ids: list[tuple[int, int, str]]) -> list[PortInfo]:
    """Serial ports, best LIO candidates first (T01.2)."""
    from serial.tools import list_ports as lp

    known = {(v, p): label for v, p, label in usb_ids}
    out: list[PortInfo] = []
    for p in lp.comports():
        label = known.get((p.vid, p.pid)) if p.vid is not None else None
        out.append(PortInfo(p.device, p.vid, p.pid, p.description or "", label))
    return sorted(out, key=lambda pi: (not pi.likely_lio, pi.device))


def pick_port(ports: list[PortInfo]) -> PortInfo | None:
    """The single likely LIO port, or None if there are zero or several."""
    likely = [p for p in ports if p.likely_lio]
    # On macOS each device appears as /dev/cu.* and /dev/tty.*; prefer cu.
    cu = [p for p in likely if "/cu." in p.device] or likely
    return cu[0] if len(cu) == 1 else None
