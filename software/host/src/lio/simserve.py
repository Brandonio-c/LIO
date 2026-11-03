"""Serve the simulator on a pseudo-terminal, in real time (``lio sim-serve``).

Anything that opens a serial port (``lio --port``, ``pytest --lio-port``, the
logger, a terminal program) can then talk to a simulated LIO through the real
:class:`~lio.transport.SerialTransport` code path, with real timing. Opening
the port reboots the simulated Nano, like the DTR reset on the real board.

POSIX only (macOS, Linux).
"""

from __future__ import annotations

import collections
import errno
import fcntl
import os
import select
import struct
import termios
import threading
import time

from lio.config import HwConfig
from lio.sim import Faults, SimulatedLIO

# A flush within this long of noticing an open belongs to that same open.
REOPEN_GAP_S = 0.5


class PtyBridge:
    def __init__(self, cfg: HwConfig, faults: Faults | None = None, *, seed: int | None = None):
        import pty
        import tty

        self.sim = SimulatedLIO(cfg, faults, seed=seed)
        self._master, slave = pty.openpty()
        tty.setraw(slave)
        # Packet mode: a client flushing its input (pyserial does on every open)
        # arrives here as a control packet, a reliable "port opened" signal.
        fcntl.ioctl(self._master, termios.TIOCPKT, struct.pack("i", 1))
        self.port = os.ttyname(slave)
        os.close(slave)  # only clients hold the slave: EOF on the master = no client
        self._t0 = time.monotonic()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="lio-sim-serve", daemon=True)
        self.client_open = False
        self.opens = 0
        self._opened_at = 0.0
        # what the bridge saw, for diagnosing timing problems: (seconds since start, what)
        self.trace: collections.deque[tuple[float, str]] = collections.deque(maxlen=200)

    def _note(self, what: str) -> None:
        self.trace.append((round(self._sim_now(), 4), what))

    def trace_text(self) -> str:
        return "; ".join(f"{t:.3f}s {w}" for t, w in self.trace)

    def start(self) -> PtyBridge:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        os.close(self._master)

    def __enter__(self) -> PtyBridge:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    def wait_client(self, is_open: bool, timeout: float = 5.0) -> bool:
        """Wait until the bridge has seen a client open (or close) the port.

        The close is only noticed on the bridge's next read, so a client that
        closes and reopens at once could reopen without the simulated reset;
        tests call this between the two, as any real gap between uses would.
        """
        end = time.monotonic() + timeout
        while self.client_open != is_open:
            if time.monotonic() > end:
                return False
            time.sleep(0.005)
        return True

    def _client_opened(self, how: str) -> None:
        """A client opened the port: reset the simulated Nano, as DTR would."""
        now = self._sim_now()
        if self.client_open:
            # The flush that follows an open already noticed: the same open.
            if now - self._opened_at < REOPEN_GAP_S:
                return
            self._note("client reopened")
            self.sim.port_closed()
        self.client_open = True
        self._opened_at = now
        self.opens += 1
        self._note(f"client opened (#{self.opens}, {how})")
        self.sim.port_opened()  # the DTR reset

    def _sim_now(self) -> float:
        return time.monotonic() - self._t0

    def _run(self) -> None:
        sim = self.sim
        while not self._stop.is_set():
            now = self._sim_now()
            if now > sim.clock:
                sim.advance(now - sim.clock)
            readable, _, _ = select.select([self._master], [], [], 0.001)
            data: bytes | None = None
            if readable:
                try:
                    data = os.read(self._master, 1024)
                except OSError as e:
                    if e.errno != errno.EIO:  # Linux reports "no client" as EIO
                        raise
                    data = b""
                if data == b"":  # no client has the port open
                    if self.client_open:
                        self.client_open = False
                        self._note("client closed")
                        sim.port_closed()
                    time.sleep(0.005)
                    continue
                flags, data = data[0], data[1:]
                if flags != termios.TIOCPKT_DATA:  # a control packet, no data
                    if flags & termios.TIOCPKT_FLUSHREAD:
                        self._client_opened("input flush")
                    continue
            if not self.client_open:
                # A client that does not flush on open: no read error any more
                self._client_opened("no read error")
            if data:
                sim.receive_bytes(data)
            while (line := sim.next_output(0.0)) is not None:
                try:
                    os.write(self._master, (line + "\r\n").encode("latin-1"))
                except OSError as e:
                    self._note(f"write failed ({e.errno}): {line[:30]}")
                    break
                if line.startswith("# BOOT"):
                    self._note("banner sent")
