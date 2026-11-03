"""The real serial code path, in real time, against the simulator on a pseudo-terminal.

This exercises SerialTransport (pyserial, timeouts, line buffering) and the
reset-on-open behaviour exactly as on hardware, without hardware.
"""

from __future__ import annotations

import os
import time

import pytest

from lio.config import HwConfig
from lio.results import Status
from lio.suite.core import REGISTRY, catalogue, run_test
from lio.suite.runner import serial_context

pytestmark = [
    pytest.mark.sim,
    pytest.mark.skipif(os.name != "posix", reason="pseudo-terminals need POSIX"),
]


def test_catalogue_over_a_real_serial_port(cfg: HwConfig) -> None:
    from lio.simserve import PtyBridge

    catalogue()
    with PtyBridge(cfg) as bridge:
        t0 = time.monotonic()
        ctx = serial_context(cfg, bridge.port)
        try:
            assert ctx.dev.boot_s is not None and ctx.dev.boot_s < 3.0
            for tid in ("T02.1", "T02.2", "T02.4", "T02.5", "T05.1", "T10.4"):
                r = run_test(ctx, REGISTRY[tid])
                assert r.status == Status.PASS, r.summary()
        finally:
            ctx.dev.close()
        # reopening the port reboots the simulated Nano, like DTR on the real board
        ctx2 = serial_context(cfg, bridge.port)
        try:
            assert ctx2.dev.banner is not None and bridge.opens == 2
        finally:
            ctx2.dev.close()
    assert time.monotonic() - t0 < 30
