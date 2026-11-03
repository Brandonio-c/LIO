"""Serve the simulator on a pseudo-terminal, in real time (``lio sim-serve``).

Anything that opens a serial port (``lio --port``, ``pytest --lio-port``, the
logger, a terminal program) can then talk to a simulated LIO through the real
:class:`~lio.transport.SerialTransport` code path, with real timing. Opening
the port reboots the simulated Nano, like the DTR reset on the real board.

POSIX only (macOS, Linux).
"""

from __future__ import annotations

import errno
import os
import select
import threading
import time

from lio.config import HwConfig
from lio.sim import Faults, SimulatedLIO


class PtyBridge:
    def __init__(self, cfg: HwConfig, faults: Faults | None = None, *, seed: int | None = None):
        import pty
        import tty

        self.sim = SimulatedLIO(cfg, faults, seed=seed)
        self._master, slave = pty.openpty()
        tty.setraw(slave)
        self.port = os.ttyname(slave)
        os.close(slave)  # only clients hold the slave: EOF on the master = no client
        self._t0 = time.monotonic()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="lio-sim-serve", daemon=True)
        self.client_open = False
        self.opens = 0

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
                        sim.port_closed()
                    time.sleep(0.005)
                    continue
            if not self.client_open:
                self.client_open = True
                self.opens += 1
                sim.port_opened()  # the DTR reset
            if data:
                sim.receive_bytes(data)
            while (line := sim.next_output(0.0)) is not None:
                try:
                    os.write(self._master, (line + "\r\n").encode("latin-1"))
                except OSError:
                    break
