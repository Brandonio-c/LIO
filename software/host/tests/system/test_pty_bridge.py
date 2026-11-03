"""The real serial code path, in real time, against the simulator on a pseudo-terminal.

This exercises SerialTransport (pyserial, timeouts, line buffering) and the
reset-on-open behaviour exactly as on hardware, without hardware.
"""

from __future__ import annotations

import os
import time

import pytest

from lio.config import HwConfig
from lio.device import BootTimeout
from lio.results import Status
from lio.simserve import PtyBridge
from lio.suite.core import REGISTRY, SuiteContext, catalogue, run_test
from lio.suite.runner import serial_context

pytestmark = [
    pytest.mark.sim,
    pytest.mark.skipif(os.name != "posix", reason="pseudo-terminals need POSIX"),
]


def _open(cfg: HwConfig, bridge: PtyBridge, which: str) -> SuiteContext:
    """serial_context, but a missing banner reports what the bridge saw (CI annotations)."""
    try:
        return serial_context(cfg, bridge.port)
    except BootTimeout as e:
        raise AssertionError(f"{which}: {e} | bridge trace: {bridge.trace_text()}") from e


def test_catalogue_over_a_real_serial_port(cfg: HwConfig) -> None:
    catalogue()
    with PtyBridge(cfg) as bridge:
        t0 = time.monotonic()
        ctx = _open(cfg, bridge, "first open")
        try:
            assert ctx.dev.boot_s is not None and ctx.dev.boot_s < 3.0
            for tid in ("T02.1", "T02.2", "T02.4", "T02.5", "T05.1", "T10.4"):
                r = run_test(ctx, REGISTRY[tid])
                assert r.status == Status.PASS, r.summary()
        finally:
            ctx.dev.close()
        assert bridge.wait_client(False), "the bridge did not see the port close"
        # reopening the port reboots the simulated Nano, like DTR on the real board
        ctx2 = _open(cfg, bridge, "reopen")
        try:
            assert ctx2.dev.banner is not None and bridge.opens == 2
        finally:
            ctx2.dev.close()
    assert time.monotonic() - t0 < 30
