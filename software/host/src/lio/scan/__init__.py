"""The full-system diagnostic height sweep (plan LIO-SW-SCAN-001).

    plan.py      mode + travel limits -> ordered steps, ETA, duty prediction
    executor.py  P0-P4 on a device, checkpoints, aborts, pause/heartbeat
    store.py     scan.json, cube.csv.gz, streams/*.npz

``plan_for`` and ``start`` are shared by the CLI (``lio scan``) and the dashboard.
"""

from __future__ import annotations

import contextlib
import platform
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lio import __version__
from lio.config import HwConfig
from lio.device import LIODevice
from lio.operator import Operator
from lio.scan.executor import Control, ScanAbort, ScanExecutor, realign_problem
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
    "realign_problem",
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
    """Create the run folder and execute the plan; returns (store, status).

    NEW runs freeze an ``acquisition_snapshot`` before the first reading and
    receive a terminal source seal on finish/abort. Historical folders without
    those fields stay untouched.
    """
    from lio.buildinfo import loaded_build_identity
    from lio.config_snapshots import save_snapshot

    with contextlib.suppress(Exception):  # the run's config, kept so a resume can compare
        save_snapshot(cfg)
    from lio.scan.provenance import content_hash, read_info_gain, snapshot_from_hw_config

    info = dev.info(refresh=True)
    gain = read_info_gain(info)
    # D06: core new acquisition rejects non-1 / missing gain before light.
    if gain is None or str(gain) not in ("1", "GAIN_ONE"):
        raise PlanError(
            f"unexpected or missing device gain {gain!r}: core height acquisition "
            "requires INFO gain=1 before light (missing ≠ 1)"
        )
    # Apply/read back mains when the plan requests periods (D06).
    mains_periods = getattr(plan.settings, "mains_periods", None)
    mains_hz_applied: float | None = None
    if mains_periods:
        requested_hz = int(getattr(plan.settings, "mains_hz", 0) or 0)
        if requested_hz not in (50, 60):
            raise PlanError(
                f"height plan requests mains_periods={mains_periods} but mains_hz="
                f"{requested_hz!r}; refuse inventing 60 Hz"
            )
        from lio.device import DeviceError

        try:
            dev.adc_mains(requested_hz)
        except DeviceError as e:
            # Firmware < 2.5.1 has no ADC CFG MAINS — continue without inventing.
            if getattr(e, "code", None) in (2, "2") or "bad" in str(e).lower():
                mains_periods = None
                mains_hz_applied = None
            else:
                raise
        else:
            info = dev.info(refresh=True)
            if "mains" not in info.values:  # never fill a missing readback (D06)
                raise PlanError("mains readback missing after ADC CFG MAINS")
            mains_hz_applied = float(info.as_int("mains"))
            if int(mains_hz_applied) != requested_hz:
                raise PlanError(f"mains readback {mains_hz_applied} ≠ requested {requested_hz}")
    plan_dict = plan.to_dict()
    snap = snapshot_from_hw_config(
        cfg,
        protocol_hash=content_hash({"kind": "height_scan", "mode": plan.mode, "plan": plan_dict}),
        planned={
            "mode": plan.mode,
            "n_steps": len(plan.steps),
            "heights_down": plan_dict.get("heights_down"),
        },
        simulated=sim,
        rig_identity="sim" if sim else "host",
        gain=str(gain),
        mains_periods=mains_periods,
        mains_hz=mains_hz_applied,
        settle_ms=float(getattr(plan.settings, "optical_settle_ms", 0) or 0),
        acquisition_version="m0-height-scan",
    )
    meta = {
        "mode": plan.mode,
        "sample_id": sample_id,
        "simulated": sim,
        "host": {"lio": __version__, "python": platform.python_version()},
        "firmware": dict(info.values),
        "config_sha256": cfg.sha256,
        "plan": plan_dict,
        "stage": dev.stage.summary() if dev.stage is not None else None,
        "acquisition_snapshot": snap.to_dict(),
        # S2/S7: how LED on-time is bounded, and the code that actually ran.
        "exposure_bound": dev.exposure_bound,
        "software": loaded_build_identity(),
    }
    store = ScanStore.create(root, plan.mode, meta)
    ex = ScanExecutor(dev, cfg, plan, store, operator, sample_id=sample_id,
                      control=control, on_progress=on_progress)  # fmt: skip
    return store, ex.run()


def _assert_gain_matches_snapshot(dev: LIODevice, store: ScanStore) -> None:
    """Shared start/resume preflight: reject gain mismatch before light (CE05)."""
    from lio.scan.provenance import read_info_gain

    info = dev.info(refresh=True)
    gain = read_info_gain(info)
    snap = store.meta.get("acquisition_snapshot") or {}
    snap_gain = None
    if isinstance(snap, dict):
        snap_gain = (snap.get("adc") or {}).get("gain")
    expected = str(snap_gain) if snap_gain is not None else "1"
    expected_norm = "1" if expected in ("1", "GAIN_ONE", "1.0") else expected
    live = None if gain is None else str(gain)
    live_norm = "1" if live in ("1", "GAIN_ONE", "1.0") else live
    # A18 / D06: the core height acquisition is gain 1 on start AND resume. A gain-2
    # device matching a gain-2 snapshot is still refused (M7 stays isolated).
    if live_norm != "1" or expected_norm != "1":
        raise PlanError(
            f"resume/start preflight: core acquisition requires ADC gain 1 (device {live!r}, "
            f"snapshot {expected!r}); reject before light"
        )


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
    # CE05: shared preflight before any light — gain must match frozen snapshot.
    _assert_gain_matches_snapshot(dev, store)
    plan = ScanPlan.from_dict(store.meta["plan"])
    store.meta["status"] = "RUNNING"
    store.save_meta()
    ex = ScanExecutor(dev, cfg, plan, store, operator, sample_id=str(store.meta["sample_id"]),
                      control=control, on_progress=on_progress)  # fmt: skip
    return store, ex.run(resume=True)
