"""Versioned board/firmware timing capability profile (remediation R1 / D05).

Documents supported assumptions for conservative pulse bounds. Does **not**
invent numeric latency margins or alter firmware.

Firmware facts (lio_firmware):
- WDT settings are integer milliseconds with a 50 ms minimum (config.h WDT_MIN_MS).
- The optics watchdog is checked by cooperative ``service()``, not a proven
  zero-latency interrupt (safety.cpp / optics.cpp).
- Firmware MEAS uses the rail watchdog, not the host's nominal duration estimate.

Conservative host policy:
1. Quantize any planned on-time up to the firmware 50 ms minimum step.
2. Bound possible exposure by the **active rail WDT** that will cover the
   operation (read back / configure before send).
3. Reserve that conservative bound (not the optimistic nominal) before
   transmission. Overrun, malformed, stale, or partial responses abort and
   retain the worst-case reserved charge.
4. If no finite conservative bound fits remaining approved budgets for the
   current capability, refuse the emitting operation before light.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Firmware constants mirrored for host planning (do not change firmware values).
FW_WDT_MIN_MS = 50
FW_WDT_A_DEFAULT_MS = 2000
FW_WDT_B_DEFAULT_MS = 5000
FW_WDT_A_CAP_MS = 5000
FW_WDT_B_CAP_MS = 10000

TIMING_CAPABILITY_VERSION = "lio-timing-1"


@dataclass(frozen=True)
class TimingCapability:
    """Supported board/firmware/mode timing assumptions (evidence-backed)."""

    version: str = TIMING_CAPABILITY_VERSION
    board: str = "lio-v3"
    firmware_min: str = "2.5.1"
    wdt_min_ms: int = FW_WDT_MIN_MS
    wdt_a_default_ms: int = FW_WDT_A_DEFAULT_MS
    wdt_b_default_ms: int = FW_WDT_B_DEFAULT_MS
    wdt_a_cap_ms: int = FW_WDT_A_CAP_MS
    wdt_b_cap_ms: int = FW_WDT_B_CAP_MS
    # Cooperative service() polling — not interrupt-proven zero latency.
    wdt_check: str = "cooperative_service"
    # No invented service/transaction latency margin is applied.
    invented_latency_margin_ms: float | None = None
    notes: tuple[str, ...] = (
        "WDT integer ms, minimum 50 ms",
        "watchdog checked by cooperative service(), not proven IRQ",
        "MEAS exposure bounded by rail WDT, not host nominal estimate",
        "no invented latency margin; refuse when bound unsupported",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "board": self.board,
            "firmware_min": self.firmware_min,
            "wdt_min_ms": self.wdt_min_ms,
            "wdt_a_default_ms": self.wdt_a_default_ms,
            "wdt_b_default_ms": self.wdt_b_default_ms,
            "wdt_a_cap_ms": self.wdt_a_cap_ms,
            "wdt_b_cap_ms": self.wdt_b_cap_ms,
            "wdt_check": self.wdt_check,
            "invented_latency_margin_ms": self.invented_latency_margin_ms,
            "notes": list(self.notes),
        }


DEFAULT_TIMING_CAPABILITY = TimingCapability()


def quantize_wdt_ms(ms: float, *, capability: TimingCapability | None = None) -> int:
    """Ceil ``ms`` to firmware WDT integer ms with the 50 ms minimum."""
    cap = capability or DEFAULT_TIMING_CAPABILITY
    if ms <= 0:
        return int(cap.wdt_min_ms)
    q = int(ms) if float(ms) == int(ms) else int(ms) + 1
    return max(int(cap.wdt_min_ms), q)


def rail_wdt_cap_ms(rail: str, *, capability: TimingCapability | None = None) -> int:
    cap = capability or DEFAULT_TIMING_CAPABILITY
    r = rail.upper()
    if r == "A":
        return int(cap.wdt_a_cap_ms)
    if r == "B":
        return int(cap.wdt_b_cap_ms)
    raise ValueError(f"unknown rail {rail!r}")


def conservative_pulse_bound_ms(
    *,
    nominal_on_ms: float,
    active_wdt_ms: int,
    rail: str,
    capability: TimingCapability | None = None,
) -> tuple[float, str | None]:
    """Return ``(bound_ms, refuse_reason)``.

    Bound is the active rail WDT (quantized), which is what can actually keep
    light on. If the active WDT cannot cover the nominal operation, or exceeds
    the rail cap, refuse — do not invent a latency margin.
    """
    cap = capability or DEFAULT_TIMING_CAPABILITY
    need = quantize_wdt_ms(nominal_on_ms, capability=cap)
    wdt = quantize_wdt_ms(float(active_wdt_ms), capability=cap)
    rail_cap = rail_wdt_cap_ms(rail, capability=cap)
    if wdt > rail_cap:
        return 0.0, f"active WDT {wdt} ms exceeds rail {rail} cap {rail_cap} ms"
    if wdt < need:
        return (
            0.0,
            f"active WDT {wdt} ms cannot cover quantized operation need {need} ms",
        )
    # Conservative bound == active WDT (firmware may keep light until WDT trips).
    return float(wdt), None


def validate_reported_on_ms(
    reserved_ms: float,
    reported_ms: float | None,
    *,
    complete: bool = True,
) -> str | None:
    """Return abort reason if reported on-time is overrun/malformed/stale/partial."""
    if not complete:
        return "partial_response"
    if reported_ms is None:
        return "missing_reported_on_ms"
    try:
        r = float(reported_ms)
    except (TypeError, ValueError):
        return "malformed_reported_on_ms"
    if r != r or r < 0:  # NaN / negative
        return "malformed_reported_on_ms"
    if r > reserved_ms + 1e-6:
        return f"overrun_reported_{r:.3f}_gt_reserved_{reserved_ms:.3f}"
    return None
