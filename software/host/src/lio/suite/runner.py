"""Build a suite context (simulator or serial) and run the catalogue into a RunRecord."""

from __future__ import annotations

import datetime as dt
import getpass
import platform
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import lio
from lio.config import HwConfig
from lio.device import LIODevice
from lio.operator import Operator, SimOperator
from lio.results import RunRecord, TestResult, overall_verdict
from lio.sim import Faults, SimulatedLIO
from lio.suite.core import SuiteContext, TestDef, catalogue, run_test
from lio.transport import SerialTransport, SimTransport, Transport


def sim_context(
    cfg: HwConfig,
    faults: str | Iterable[str] | Faults | None = None,
    *,
    seed: int | None = None,
    loop_jumper: bool = False,
    answers: dict[str, object] | None = None,
) -> SuiteContext:
    """An opened device on a fresh simulator, with a simulated operator.

    Nothing real can move or light, so interactive and motion tests always run;
    ``answers`` overrides individual operator answers (by key).
    """
    f = faults if isinstance(faults, Faults) else Faults.parse(faults)
    sim = SimulatedLIO(cfg, f, seed=seed, loop_jumper=loop_jumper)
    dev = LIODevice(SimTransport(sim), cfg)
    dev.open()
    return SuiteContext(
        dev,
        cfg,
        "sim",
        sim,
        interactive=True,
        allow_motion=True,
        operator=SimOperator(sim, answers),
    )


def serial_context(
    cfg: HwConfig,
    port: str,
    *,
    operator: Operator | None = None,
    allow_motion: bool = False,
    transport: Transport | None = None,
) -> SuiteContext:
    """An opened device on real hardware (opening the port resets the Nano).

    Interactive tests run only with an ``operator``; motion tests also need
    ``allow_motion``.
    """
    t = transport or SerialTransport(port, cfg.section.integer("link.baud"))
    dev = LIODevice(t, cfg)
    dev.open()
    return SuiteContext(
        dev,
        cfg,
        port,
        interactive=operator is not None,
        allow_motion=allow_motion,
        operator=operator,
    )


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).resolve().parent,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def environment() -> dict[str, Any]:
    status = _git("status", "--porcelain")
    return {
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "lio_package": lio.__version__,
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(status) if status is not None else None,
        "host": platform.node(),
        "user": getpass.getuser(),
    }


def metadata(cfg: HwConfig, given: dict[str, str] | None = None) -> dict[str, str]:
    """Run metadata with the YAML defaults; required keys always present."""
    sec = cfg.section
    out = {str(k): str(v) for k, v in sec.mapping("run_metadata.defaults").items()}
    out.update({k: v for k, v in (given or {}).items() if v})
    for key in sec.raw("run_metadata.required"):
        if not out.get(str(key)):
            raise ValueError(f"run metadata {key!r} is required")
    return out


def new_record(ctx: SuiteContext, meta: dict[str, str] | None = None) -> RunRecord:
    now = dt.datetime.now().astimezone()
    kind = "sim" if ctx.is_sim else "host"
    rec = RunRecord(
        run_id=f"{now:%Y%m%d-%H%M%S}_{kind}",
        target=ctx.target,
        started=now.isoformat(timespec="seconds"),
        environment=environment(),
        config={
            "path": str(ctx.cfg.path),
            "sha256": ctx.cfg.sha256,
            "provisional": ctx.cfg.provisional,
        },
        metadata=metadata(ctx.cfg, meta),
        faults=ctx.sim.faults.active if ctx.sim is not None else [],
    )
    ctx.cache["sample_id"] = rec.metadata.get("sample_id")
    if ctx.dev.banner is not None:
        rec.firmware["banner"] = ctx.dev.banner.raw
    try:
        rec.firmware.update(ctx.dev.info().values)
    except Exception as e:  # identity is best effort; T02 reports the failure
        rec.firmware["error"] = str(e)
    return rec


def finish(record: RunRecord, ctx: SuiteContext) -> RunRecord:
    record.finished = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    duty = ctx.dev.duty
    if duty is not None:
        record.duty = {
            "window_s": duty.window_s,
            "budget_ms": duty.budget_ms,
            "total_cooldown_s": duty.total_cooldown_s,
            "cooldowns": [{"hole": h, "wait_s": w, "reason": r} for h, w, r in duty.cooldowns],
            "over_budget": [{"hole": h, "on_ms": ms} for h, ms in duty.over_budget],
        }
    th = ctx.th
    v = overall_verdict(
        record.results,
        max_channel_fails=th.integer("verdict.max_channel_fails"),
        limited_holes=th.ints("verdict.limited_holes"),
    )
    record.verdict = {"verdict": v.verdict.value, "reasons": v.reasons, "counts": record.counts()}
    return record


def automatic(t: TestDef) -> bool:
    return t.kind == "A"


def everything(t: TestDef) -> bool:
    return True


def run_catalogue(
    ctx: SuiteContext,
    record: RunRecord,
    select: Callable[[TestDef], bool] = automatic,
    on_result: Callable[[TestResult], None] | None = None,
) -> RunRecord:
    for t in catalogue():
        if not select(t):
            continue
        result = run_test(ctx, t)
        record.results.append(result)
        if on_result is not None:
            on_result(result)
    return finish(record, ctx)
