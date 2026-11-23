"""Interactive LD06AJSA pot tuning with OPT101 light as live feedback.

The drivers are constant-current modules with a trim pot — firmware cannot
clamp mA. This tool holds an easy-to-replace LED solid (green on RAIL A, white
on RAIL B by default) and streams OPT101 intensity so you can turn the pot
while watching optical return. Ammeter mA entry is optional for absolute
checks against ``rails.<X>.safe_max_ma``.

Example::

    lio --port /dev/cu.usbmodem101 drive-tune A
    lio drive-tune B --hole 10
"""

from __future__ import annotations

import contextlib
import json
import select
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from lio.config import HwConfig
from lio.device import LIODevice


@dataclass(frozen=True)
class RailTune:
    rail: str
    driver: str
    hole: int
    label: str
    target_ma: float
    led_rating_ma: float
    safe_max_ma: float
    wdt_cap_ms: int


def rail_tune(cfg: HwConfig, rail: str, hole: int | None = None) -> RailTune:
    rail = rail.upper()
    if rail not in ("A", "B"):
        raise ValueError(f"rail must be A or B, got {rail!r}")
    sec = cfg.section
    key = rail.lower()
    default_hole = 4 if rail == "A" else 11  # pink; white is the first to cook on B
    raw_hole = sec.raw(f"rails.{rail}.tune_hole")
    h = int(hole if hole is not None else (raw_hole if raw_hole is not None else default_hole))
    if h not in cfg.rail_holes(rail):
        raise ValueError(f"hole {h} is not on rail {rail}")
    ch = cfg.channel(h)
    target = float(sec.num(f"rails.{rail}.current_ma"))
    rating_raw = sec.raw(f"rails.{rail}.led_rating_ma")
    rating = float(rating_raw if rating_raw is not None else 20)
    safe_raw = sec.raw(f"rails.{rail}.safe_max_ma")
    safe = float(safe_raw if safe_raw is not None else target)
    driver = str(sec.raw(f"rails.{rail}.driver") or f"DRV{1 if rail == 'A' else 2}")
    return RailTune(
        rail=rail,
        driver=driver,
        hole=h,
        label=ch.label,
        target_ma=target,
        led_rating_ma=rating,
        safe_max_ma=safe,
        wdt_cap_ms=int(cfg.limits[f"wdt_{key}_cap_ms"]),
    )


def _judge_ma(ma: float, t: RailTune) -> str:
    if ma > t.safe_max_ma:
        return "STOP — above safe_max; turn the pot DOWN"
    if abs(ma - t.target_ma) / max(t.target_ma, 1e-6) <= 0.10:
        note = ""
        if ma > t.led_rating_ma:
            note = f" (above {t.led_rating_ma:.0f} mA LED rating — OK at sweep duty)"
        return f"GOOD — within 10% of target; type 'ok' to save{note}"
    if ma > t.led_rating_ma * 1.25 and ma > t.target_ma:
        return "WARN — above LED rating and above target; ease DOWN"
    if ma < t.target_ma * 0.7:
        return "LOW — turn the pot UP slowly"
    if ma > t.target_ma:
        return "A bit high — ease DOWN toward target"
    return "A bit low — ease UP toward target"


def _judge_opt(net: float, sat: float, *, last_ma: float | None = None, t: RailTune | None = None) -> str:
    """Optical coach. Never tells you to turn UP once ammeter says you're at/above target."""
    if last_ma is not None and t is not None:
        if last_ma > t.safe_max_ma:
            return "STOP — ammeter above safe_max; turn pot DOWN now"
        if last_ma >= t.target_ma * 0.9:
            if net < 80:
                return "CURRENT OK, LIGHT WEAK — LED damaged/optics; do NOT raise mA"
            return "CURRENT OK — type ok (do not chase more mA for OPT)"
        if last_ma > t.led_rating_ma and net < 80:
            return "mA already > LED rating but dim — stop raising; LED likely hurt"
    if net < 30:
        return "DARK — pot too low / LED out / open meter loop"
    if net >= sat * 0.90:
        return "SAT — turn DOWN (detector clipping)"
    if net >= sat * 0.70:
        return "HIGH — strong; ease DOWN if still climbing"
    if net < 150:
        return "WEAK optically — raise pot only if ammeter is still below target"
    return "LIT — watching; type ok when stable / ammeter near target"


def _bar(net: float, sat: float, width: int = 28) -> str:
    frac = max(0.0, min(1.0, net / max(sat, 1.0)))
    n = int(round(frac * width))
    return "#" * n + "-" * (width - n)


# Keep the old name for unit tests that imported _judge.
_judge = _judge_ma


def run_tune(
    dev: LIODevice,
    cfg: HwConfig,
    rail: str,
    *,
    hole: int | None = None,
    out_path: Path | None = None,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    poll_s: float = 0.35,
) -> dict[str, object]:
    """Hold the tune LED solid and stream OPT101 while the pot is adjusted."""
    t = rail_tune(cfg, rail, hole)
    key = t.rail.lower()
    info = dev.info()
    prev_wdt = info.as_int(f"wdt_{key}_ms")
    # Long holds only via reserved renewals within WDT and the duty budget (M1).
    # Never bypass the journal with budget=False on real hardware.
    duty_cap = int(cfg.duty_budget_ms(t.hole))
    on_ms = min(
        t.wdt_cap_ms,
        int(cfg.section.integer("dashboard.ring_on_ms_max")),
        duty_cap,
    )
    opt_ch = cfg.detectors["opt101"].adc_channel
    sat = float(cfg.detectors["opt101"].saturation_counts)
    lsb = float(cfg.lsb_mv)

    dev.keep_awake()
    if getattr(dev, "mains_hz", 0):
        with contextlib.suppress(Exception):
            dev.adc_mains(0)
    dark = float(dev.adc_read(opt_ch, 8).mean)
    dev.wdt_cfg(t.rail, on_ms)

    print(
        f"\n=== Drive tune · rail {t.rail} ({t.driver}) ===\n"
        f"Sacrificial LED: hole {t.hole} ({t.label}) — held solid\n"
        f"Primary feedback: live OPT101 (dark={dark:.0f})\n"
        f"Optional ammeter: target {t.target_ma:.0f} mA · rating {t.led_rating_ma:.0f} · "
        f"HARD MAX {t.safe_max_ma:.0f} mA\n"
        f"\nTurn the {t.driver} pot slowly. Prefer the AMMETER for the stop point:\n"
        f"  stop near {t.target_ma:.0f} mA — never above {t.safe_max_ma:.0f} mA.\n"
        f"OPT101 is secondary (a dim LED at high mA means the LED is hurt, not 'needs more').\n"
        f"Commands:  ok  |  q  |  <mA number>  (type readings often)\n"
        f"Firmware cannot clamp current — the pot is the only limit.\n",
        file=stdout,
        flush=True,
    )

    readings: list[dict[str, object]] = []
    opt_trace: list[dict[str, object]] = []
    accepted_ma: float | None = None
    accepted_opt: float | None = None
    last_opt_net = 0.0
    last_ma: float | None = None
    lit_until = 0.0
    use_select = hasattr(stdin, "fileno")

    try:
        while True:
            now = time.monotonic()
            if now >= lit_until - 0.4:
                until = dev.ch_on(t.hole, on_ms, budget=True)
                lit_until = now + max(until, on_ms) / 1000.0

            lit = float(dev.adc_read(opt_ch, 4).mean)
            net = lit - dark
            last_opt_net = net
            verdict = _judge_opt(net, sat, last_ma=last_ma, t=t)
            opt_trace.append(
                {
                    "net": round(net, 1),
                    "lit": round(lit, 1),
                    "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
            # Keep the trace short in memory.
            if len(opt_trace) > 600:
                opt_trace = opt_trace[-300:]
            line = (
                f"\r  OPT101 net {net:+7.0f}  ({net * lsb:+7.1f} mV)  "
                f"[{_bar(net, sat)}]  {verdict}   "
            )
            print(line, end="", file=stdout, flush=True)

            cmd: str | None = None
            if use_select:
                try:
                    ready, _, _ = select.select([stdin], [], [], poll_s)
                except (ValueError, OSError):
                    use_select = False
                    ready = []
                if ready:
                    raw_line = stdin.readline()
                    if raw_line == "":
                        break
                    cmd = raw_line.strip().lower()
            else:
                # Tests / non-TTY: one blocking read per poll (no live redraw needed).
                time.sleep(poll_s)
                raw_line = stdin.readline()
                if raw_line == "":
                    break
                cmd = raw_line.strip().lower()

            if cmd is None:
                continue
            print(file=stdout, flush=True)  # end the \r status line
            if not cmd:
                continue
            if cmd in ("q", "quit", "exit"):
                break
            if cmd in ("ok", "accept", "save"):
                if last_opt_net < 30:
                    print("  REFUSED: OPT101 still dark — turn pot UP or check the LED", file=stdout, flush=True)
                    continue
                if last_opt_net >= sat * 0.90:
                    print("  REFUSED: OPT101 saturating — turn pot DOWN first", file=stdout, flush=True)
                    continue
                if readings:
                    last_ma = float(readings[-1]["ma"])  # type: ignore[arg-type]
                    if last_ma > t.safe_max_ma:
                        print(
                            f"  REFUSED: last ammeter {last_ma:.1f} mA > safe_max "
                            f"{t.safe_max_ma:.0f} — turn DOWN",
                            file=stdout,
                            flush=True,
                        )
                        continue
                    accepted_ma = last_ma
                accepted_opt = last_opt_net
                print(
                    f"  accepted OPT101 net {accepted_opt:.0f}"
                    + (f" · {accepted_ma:.1f} mA" if accepted_ma is not None else " (optical only)"),
                    file=stdout,
                    flush=True,
                )
                break
            try:
                ma = float(cmd.replace("ma", "").strip())
            except ValueError:
                print("  commands: ok | q | <mA from ammeter>", file=stdout, flush=True)
                continue
            if ma < 0 or ma > 2000:
                print("  nonsense mA — check meter range/jacks", file=stdout, flush=True)
                continue
            j = _judge_ma(ma, t)
            last_ma = ma
            readings.append(
                {
                    "ma": ma,
                    "opt_net": round(last_opt_net, 1),
                    "verdict": j,
                    "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
            print(f"  ammeter {ma:6.1f} mA  →  {j}", file=stdout, flush=True)
            if ma > t.safe_max_ma:
                print("  *** TURN THE POT DOWN NOW — do not chase OPT101 with more mA ***", file=stdout, flush=True)
            elif ma >= t.target_ma and last_opt_net < 150:
                print(
                    "  Current is already on target but OPT is weak: LED/optics, not the pot.",
                    file=stdout,
                    flush=True,
                )
    except KeyboardInterrupt:
        print("\ninterrupted", file=stdout, flush=True)
    finally:
        with contextlib.suppress(Exception):
            dev.off()
        with contextlib.suppress(Exception):
            dev.wdt_cfg(t.rail, prev_wdt)

    result: dict[str, object] = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rail": t.rail,
        "driver": t.driver,
        "hole": t.hole,
        "label": t.label,
        "target_ma": t.target_ma,
        "led_rating_ma": t.led_rating_ma,
        "safe_max_ma": t.safe_max_ma,
        "dark_opt101": dark,
        "readings": readings,
        "opt_trace_tail": opt_trace[-40:],
        "accepted_ma": accepted_ma,
        "accepted_opt101_net": accepted_opt,
    }
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2) + "\n")
        print(f"wrote {out_path}", file=stdout, flush=True)
    return result
