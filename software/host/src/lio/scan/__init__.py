"""The full-system diagnostic height sweep (plan LIO-SW-SCAN-001).

    plan.py      mode + travel limits -> ordered steps, ETA, duty prediction
    executor.py  P0-P4 on a device, checkpoints, aborts, pause/heartbeat
    store.py     scan.json, cube.csv.gz, streams/*.npz

``plan_for`` and ``start`` are shared by the CLI (``lio scan``) and the dashboard.
"""

from __future__ import annotations

import platform
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lio import __version__
from lio.config import HwConfig
from lio.device import LIODevice
from lio.operator import Operator
from lio.scan.executor import Control, ScanAbort, ScanExecutor
from lio.scan.plan import PlanError, ScanPlan, ScanSettings, build
from lio.scan.store import ScanStore
from lio.stage import StageTracker

__all__ = [
    "Control",
    "PlanError",
    "ScanAbort",
    "ScanExecutor",
    "ScanPlan",
    "ScanSettings",
    "ScanStore",
    "build",
    "plan_for",
    "resume",
    "sim_run",
    "sim_stage",
    "start",
]


def plan_for(
    cfg: HwConfig,
    mode: str,
    stage: StageTracker | None,
    top_margin: int,
    overrides: dict[str, Any] | None = None,
) -> ScanPlan:
    """The plan for ``mode`` between the stage's tracked limits."""
    lim = stage.limits if stage is not None else None
    cur = None
    if stage is not None and stage.abs is not None:
        cur = round(sum(stage.abs) / 2)
    return build(
        cfg,
        mode,
        top_limit=None if lim is None or lim.top is None else min(lim.top),
        bottom_limit=None if lim is None or lim.bottom is None else max(lim.bottom),
        current=cur,
        top_margin=top_margin,
        overrides=overrides,
    )


def sim_stage(dev: LIODevice, path: Path, travel_hs: int | None = None) -> StageTracker:
    """A tracked stage for the simulator: top here (the sim starts at the top), bottom
    ``travel_hs`` below. Attached to ``dev``."""
    tr = StageTracker(path)
    dev.stage = tr
    st = dev.status()
    tr.set_top((st.as_int("pos1"), st.as_int("pos2")))
    travel = travel_hs or int(dev.cfg.section.raw("sim.height.travel_hs"))
    tr.data["bottom"] = [-travel, -travel]
    tr._save()
    return tr


def sim_run(
    cfg: HwConfig,
    mode: str,
    root: Path,
    *,
    faults: str | None = None,
    sample: str = "empty",
    overrides: dict[str, Any] | None = None,
    control: Control | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[ScanStore, str]:
    """A whole scan on a fresh simulator (top at the start, bottom = sim travel)."""
    import tempfile

    from lio.operator import SimOperator
    from lio.sim import Faults, SimulatedLIO
    from lio.transport import SimTransport

    sim = SimulatedLIO(cfg, Faults.parse(faults))
    sim.sample = "food" if sample.startswith("LIO-F-") else sample
    dev = LIODevice(SimTransport(sim), cfg)
    dev.open()
    try:
        sim_stage(dev, Path(tempfile.mkdtemp(prefix="lio_sim_stage_")) / "stage.json",
                  int(sim.travel_hs))  # fmt: skip
        plan = plan_for(cfg, mode, dev.stage, dev.stage_top_margin(), overrides)
        return start(dev, cfg, plan, root, SimOperator(sim), sample_id=sample, control=control,
                     on_progress=on_progress, sim=True)  # fmt: skip
    finally:
        dev.close()


def start(
    dev: LIODevice,
    cfg: HwConfig,
    plan: ScanPlan,
    root: Path,
    operator: Operator,
    *,
    sample_id: str,
    control: Control | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    sim: bool = False,
) -> tuple[ScanStore, str]:
    """Create the run folder and execute the plan; returns (store, status)."""
    info = dev.info(refresh=True)
    meta = {
        "mode": plan.mode,
        "sample_id": sample_id,
        "simulated": sim,
        "host": {"lio": __version__, "python": platform.python_version()},
        "firmware": dict(info.values),
        "config_sha256": cfg.sha256,
        "plan": plan.to_dict(),
        "stage": dev.stage.summary() if dev.stage is not None else None,
    }
    store = ScanStore.create(root, plan.mode, meta)
    ex = ScanExecutor(dev, cfg, plan, store, operator, sample_id=sample_id,
                      control=control, on_progress=on_progress)  # fmt: skip
    return store, ex.run()


def resume(
    dev: LIODevice,
    cfg: HwConfig,
    folder: Path,
    operator: Operator,
    *,
    control: Control | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[ScanStore, str]:
    """Carry on an INCOMPLETE run from its next step (same firmware and config)."""
    store = ScanStore.open(folder)
    if store.meta.get("status") == "COMPLETE":
        raise PlanError(f"{folder} is already complete")
    plan = ScanPlan.from_dict(store.meta["plan"])
    store.meta["status"] = "RUNNING"
    store.save_meta()
    ex = ScanExecutor(dev, cfg, plan, store, operator, sample_id=str(store.meta["sample_id"]),
                      control=control, on_progress=on_progress)  # fmt: skip
    return store, ex.run(resume=True)
