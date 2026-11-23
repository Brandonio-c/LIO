"""Targeted stationary acquisition protocols (M4).

``plan_protocol`` is fully offline: no Device, serial, POWER WAKE or light.
Execution uses typed MEAS only when ``allow_light`` is set and the ownership/
duty journal gates the pulse. Stationary protocols never arm motors.
"""

from __future__ import annotations

import contextlib
import json
import math
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lio.config import HwConfig
from lio.scan.calibration import resolve_calibration
from lio.scan.provenance import (
    AcquisitionSnapshot,
    AdcProvenance,
    RfProvenance,
    build_acquisition_snapshot,
    content_hash,
    seal_terminal_source,
)
from lio.scan.store import ScanStore

PROTOCOL_SCHEMA_VERSION = 1
APPROVED_FIXED_GAIN = "1"
KNOWN_TOP_KEYS = frozenset(
    {
        "id",
        "version",
        "schema",
        "kind",
        "sample",
        "assembly",
        "holes",
        "detectors",
        "position_policy",
        "gain",
        "conditions",
        "blocks",
        "budgets",
        "allocation",
        "inference",
        "estimator",
        "operator_checkpoints",
        "objective",
        "notes",
    }
)
KNOWN_KINDS = frozenset({"stationary_targeted", "stationary_confirm"})
POSITION_POLICIES = frozenset({"current_position", "verified_position"})
ALLOCATION_POLICIES = frozenset({"equal_fixed", "pilot_frozen"})


class ProtocolError(ValueError):
    """Invalid or unsupported protocol document."""


@dataclass(frozen=True)
class Condition:
    id: str
    settle_ms: int
    mains_periods: int
    label: str = ""
    optical_block: bool = False  # operator checkpoint when True
    checkpoint: str | None = None


@dataclass(frozen=True)
class ProtocolSpec:
    id: str
    version: str
    kind: str
    sample: dict[str, Any]
    assembly: dict[str, Any]
    holes: tuple[int, ...]
    detectors: tuple[str, ...]
    position_policy: str
    gain: str
    conditions: tuple[Condition, ...]
    blocks: dict[str, Any]
    budgets: dict[str, Any]
    allocation: dict[str, Any]
    inference: dict[str, Any]
    estimator: dict[str, Any]
    operator_checkpoints: tuple[str, ...]
    objective: str | None = None
    notes: str = ""
    schema: int = PROTOCOL_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["holes"] = list(self.holes)
        d["detectors"] = list(self.detectors)
        d["conditions"] = [asdict(c) for c in self.conditions]
        d["operator_checkpoints"] = list(self.operator_checkpoints)
        return d

    def protocol_hash(self) -> str:
        return content_hash(self.to_dict())


@dataclass
class PlannedStep:
    index: int
    hole: int
    condition_id: str
    settle_ms: int
    mains_periods: int
    phase: str  # pilot | production | fixed
    block: int
    optical_block: bool
    checkpoint: str | None
    estimated_on_ms: float


@dataclass
class ProtocolPlan:
    protocol: ProtocolSpec
    steps: list[PlannedStep]
    predicted_duration_s: float
    predicted_on_ms: float
    cooldowns_s: float
    assumptions: list[str]
    unresolved: list[str]
    allocation_detail: dict[str, Any]
    physical_prerequisites: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_id": self.protocol.id,
            "protocol_version": self.protocol.version,
            "protocol_hash": self.protocol.protocol_hash(),
            "kind": self.protocol.kind,
            "gain": self.protocol.gain,
            "holes": list(self.protocol.holes),
            "steps": [asdict(s) for s in self.steps],
            "n_steps": len(self.steps),
            "predicted_duration_s": self.predicted_duration_s,
            "predicted_on_ms": self.predicted_on_ms,
            "cooldowns_s": self.cooldowns_s,
            "assumptions": list(self.assumptions),
            "unresolved": list(self.unresolved),
            "allocation": self.allocation_detail,
            "physical_prerequisites": list(self.physical_prerequisites),
            "stationary": True,
            "arms_motors": False,
        }


def _finite(name: str, v: Any) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError) as e:
        raise ProtocolError(f"{name}: not a number ({v!r})") from e
    if not math.isfinite(x):
        raise ProtocolError(f"{name}: NaN/Inf not allowed")
    return x


def _reject_unknown(data: dict[str, Any], known: frozenset[str], where: str) -> None:
    unknown = sorted(set(data) - known)
    if unknown:
        raise ProtocolError(f"{where}: unknown keys {unknown}")


def load_protocol(source: Path | str | dict[str, Any]) -> ProtocolSpec:
    """Parse and validate a protocol document. Rejects unknown keys and bad gain."""
    if isinstance(source, dict):
        data = dict(source)
    else:
        path = Path(source)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ProtocolError(f"cannot read protocol: {e}") from e
    if not isinstance(data, dict):
        raise ProtocolError("protocol root must be an object")
    _reject_unknown(data, KNOWN_TOP_KEYS, "protocol")

    pid = str(data.get("id") or "").strip()
    if not pid:
        raise ProtocolError("protocol.id required")
    version = str(data.get("version") or "1")
    kind = str(data.get("kind") or "stationary_targeted")
    if kind not in KNOWN_KINDS:
        raise ProtocolError(f"unsupported kind {kind!r}")
    gain = str(data.get("gain", APPROVED_FIXED_GAIN))
    if gain != APPROVED_FIXED_GAIN:
        raise ProtocolError(
            f"gain={gain!r} rejected: approved fixed acquisition gain is {APPROVED_FIXED_GAIN} "
            "(PGA changes are M7)"
        )
    holes_raw = data.get("holes")
    if not isinstance(holes_raw, list) or not holes_raw:
        raise ProtocolError("holes: non-empty list required")
    holes: list[int] = []
    for h in holes_raw:
        hi = int(_finite("hole", h))
        if hi < 1 or hi > 16:
            raise ProtocolError(f"invalid hole {hi}")
        holes.append(hi)
    dets = tuple(str(d) for d in (data.get("detectors") or ["ingaas", "opt101"]))
    for d in dets:
        if d not in ("ingaas", "opt101"):
            raise ProtocolError(f"unknown detector {d!r}")
    pos = str(data.get("position_policy") or "current_position")
    if pos not in POSITION_POLICIES:
        raise ProtocolError(f"position_policy {pos!r} unsupported")

    conds_raw = data.get("conditions")
    if not isinstance(conds_raw, list) or not conds_raw:
        raise ProtocolError("conditions: non-empty list required")
    conditions: list[Condition] = []
    for i, c in enumerate(conds_raw):
        if not isinstance(c, dict):
            raise ProtocolError(f"conditions[{i}] must be object")
        _reject_unknown(
            c,
            frozenset({"id", "settle_ms", "mains_periods", "label", "optical_block", "checkpoint"}),
            f"conditions[{i}]",
        )
        cid = str(c.get("id") or f"c{i}")
        conditions.append(
            Condition(
                id=cid,
                settle_ms=int(_finite(f"conditions[{i}].settle_ms", c.get("settle_ms", 8))),
                mains_periods=int(
                    _finite(f"conditions[{i}].mains_periods", c.get("mains_periods", 2))
                ),
                label=str(c.get("label") or cid),
                optical_block=bool(c.get("optical_block", False)),
                checkpoint=None if c.get("checkpoint") is None else str(c["checkpoint"]),
            )
        )

    blocks = dict(data.get("blocks") or {})
    budgets = dict(data.get("budgets") or {})
    for key in ("max_wall_s", "max_cycle_s", "max_total_on_ms"):
        if key in budgets:
            _finite(f"budgets.{key}", budgets[key])
    if "max_total_on_ms" not in budgets:
        raise ProtocolError("budgets.max_total_on_ms required")
    if "max_wall_s" not in budgets:
        raise ProtocolError("budgets.max_wall_s required")

    allocation = dict(data.get("allocation") or {"policy": "equal_fixed"})
    policy = str(allocation.get("policy") or "equal_fixed")
    if policy not in ALLOCATION_POLICIES:
        raise ProtocolError(f"allocation.policy {policy!r} unsupported")

    checkpoints = tuple(str(x) for x in (data.get("operator_checkpoints") or []))
    return ProtocolSpec(
        id=pid,
        version=version,
        kind=kind,
        sample=dict(data.get("sample") or {}),
        assembly=dict(data.get("assembly") or {}),
        holes=tuple(holes),
        detectors=dets,
        position_policy=pos,
        gain=gain,
        conditions=tuple(conditions),
        blocks=blocks,
        budgets=budgets,
        allocation=allocation,
        inference=dict(data.get("inference") or {}),
        estimator=dict(data.get("estimator") or {"name": "fixed_n_block", "version": "m3"}),
        operator_checkpoints=checkpoints,
        objective=None if data.get("objective") is None else str(data["objective"]),
        notes=str(data.get("notes") or ""),
        schema=int(data.get("schema") or PROTOCOL_SCHEMA_VERSION),
    )


def _on_ms_for(cond: Condition, mains_hz: float = 60.0) -> float:
    # MEAS: settle + 2 * (mains periods / Hz) roughly, both detectors sequential.
    mean_s = cond.mains_periods / mains_hz + 0.004
    return float(cond.settle_ms) + 2.0 * mean_s * 1000.0


def allocate_equal_fixed(protocol: ProtocolSpec, *, n_blocks: int | None = None) -> dict[str, Any]:
    n = int(n_blocks if n_blocks is not None else protocol.blocks.get("n_production", 4))
    if n < 1:
        raise ProtocolError("blocks.n_production must be >= 1")
    per_hole = {str(h): n for h in protocol.holes}
    return {
        "policy": "equal_fixed",
        "n_production_per_hole": per_hole,
        "n_pilot_per_hole": {str(h): 0 for h in protocol.holes},
        "reason": "predeclared equal allocation",
    }


def allocate_pilot_frozen(
    protocol: ProtocolSpec,
    *,
    pilot_variance: dict[int, float],
    pilot_cost_ms: dict[int, float] | None = None,
) -> dict[str, Any]:
    """Freeze production allocation from pilot variance + weights + costs.

    Optimizes absolute uncertainty (weight * sigma / sqrt(n)), not relative error.
    Pilot observations do not count as confirmation.
    """
    weights = {
        int(k): float(v) for k, v in (protocol.allocation.get("target_weights") or {}).items()
    }
    for h in protocol.holes:
        weights.setdefault(h, 1.0)
    n_pilot = int(protocol.blocks.get("n_pilot", 2))
    min_prod = int(protocol.blocks.get("n_production_min", 1))
    max_prod = int(protocol.blocks.get("n_production_max", 16))
    # Remaining on-time after pilot.
    cond0 = protocol.conditions[0]
    default_cost = _on_ms_for(cond0) * len(protocol.conditions)
    costs = {h: float((pilot_cost_ms or {}).get(h, default_cost)) for h in protocol.holes}
    max_on = float(protocol.budgets["max_total_on_ms"])
    pilot_on = sum(n_pilot * costs[h] for h in protocol.holes)
    remaining = max(0.0, max_on - pilot_on)
    # Control holes get a minimum floor.
    controls = set(int(h) for h in (protocol.allocation.get("control_holes") or [8, 9]))
    # Score ∝ w * sigma (absolute SE focus); allocate proportional under remaining budget.
    scores = {}
    for h in protocol.holes:
        sig = float(pilot_variance.get(h, 1.0))
        if not math.isfinite(sig) or sig < 0:
            sig = 1.0
        scores[h] = max(1e-6, weights[h] * math.sqrt(max(sig, 1e-12)))
    # Greedy integer allocation.
    alloc = {h: min_prod for h in protocol.holes}
    for h in controls:
        if h in alloc:
            alloc[h] = max(alloc[h], min_prod)
    used = sum(alloc[h] * costs[h] for h in protocol.holes)
    # Fill remaining by highest score/cost efficiency.
    while True:
        candidates = [
            h for h in protocol.holes if alloc[h] < max_prod and used + costs[h] <= remaining + 1e-9
        ]
        if not candidates:
            break
        h_best = max(candidates, key=lambda h: scores[h] / max(costs[h], 1e-9))
        alloc[h_best] += 1
        used += costs[h_best]

    return {
        "policy": "pilot_frozen",
        "n_pilot_per_hole": {str(h): n_pilot for h in protocol.holes},
        "n_production_per_hole": {str(h): int(alloc[h]) for h in protocol.holes},
        "pilot_variance": {str(k): float(v) for k, v in pilot_variance.items()},
        "weights": {str(k): float(v) for k, v in weights.items()},
        "costs_ms": {str(k): float(v) for k, v in costs.items()},
        "remaining_on_ms": remaining,
        "used_production_on_ms": used,
        "reason": "frozen from pilot variance; pilot excluded from confirmation",
        "objective": "minimize sum_i w_i * sigma_i / sqrt(n_i) under on-time cap",
    }


def _build_steps(protocol: ProtocolSpec, allocation: dict[str, Any]) -> list[PlannedStep]:
    steps: list[PlannedStep] = []
    idx = 0
    pilot_n = allocation.get("n_pilot_per_hole") or {}
    prod_n = allocation.get("n_production_per_hole") or {}
    for phase, bag in (("pilot", pilot_n), ("production", prod_n)):
        for hole in protocol.holes:
            n = int(bag.get(str(hole), bag.get(hole, 0)))
            for b in range(n):
                for cond in protocol.conditions:
                    steps.append(
                        PlannedStep(
                            index=idx,
                            hole=int(hole),
                            condition_id=cond.id,
                            settle_ms=cond.settle_ms,
                            mains_periods=cond.mains_periods,
                            phase="fixed" if allocation["policy"] == "equal_fixed" else phase,
                            block=b,
                            optical_block=cond.optical_block,
                            checkpoint=cond.checkpoint,
                            estimated_on_ms=_on_ms_for(cond),
                        )
                    )
                    idx += 1
    return steps


def plan_protocol(
    source: Path | str | dict[str, Any],
    cfg: HwConfig | None = None,
    *,
    pilot_variance: dict[int, float] | None = None,
) -> ProtocolPlan:
    """Fully offline protocol plan. Never constructs a device or opens serial."""
    protocol = load_protocol(source)
    policy = str(protocol.allocation.get("policy") or "equal_fixed")
    if policy == "equal_fixed":
        allocation = allocate_equal_fixed(protocol)
    else:
        # Offline plan: use declared pilot_variance or unit defaults.
        pv = dict(pilot_variance or {})
        for h in protocol.holes:
            pv.setdefault(
                h, float((protocol.allocation.get("prior_variance") or {}).get(str(h), 1.0))
            )
        allocation = allocate_pilot_frozen(protocol, pilot_variance=pv)

    steps = _build_steps(protocol, allocation)
    on_ms = sum(s.estimated_on_ms for s in steps)
    max_on = float(protocol.budgets["max_total_on_ms"])
    if on_ms > max_on + 1e-6:
        raise ProtocolError(
            f"planned on-time {on_ms:.1f} ms exceeds budget max_total_on_ms={max_on}"
        )
    # Cooldown estimate: rough duty window waits (offline; journal is authoritative at run).
    window_s = 60.0
    if cfg is not None:
        with contextlib.suppress(Exception):
            window_s = float(cfg.section.num("duty.window_s"))
    cooldowns = 0.0
    # Naive: if cumulative on per hole exceeds budget, add window.
    if cfg is not None:
        used: dict[int, float] = {}
        for s in steps:
            bud = float(cfg.duty_budget_ms(s.hole))
            u = used.get(s.hole, 0.0)
            if u + s.estimated_on_ms > bud:
                cooldowns += window_s
                used[s.hole] = 0.0
            used[s.hole] = used.get(s.hole, 0.0) + s.estimated_on_ms

    wall = float(protocol.budgets["max_wall_s"])
    duration = on_ms / 1000.0 + cooldowns + 0.05 * len(steps)
    assumptions = [
        f"approved fixed gain={APPROVED_FIXED_GAIN}",
        "MEAS dark-then-lit (not optical off-on-on-off firmware)",
        "stationary: no MOTOR ARM",
        f"allocation={policy}",
        "pilot blocks are not confirmation" if policy == "pilot_frozen" else "fixed allocation",
    ]
    unresolved = [
        "A0 input-range unverified until bench qualification",
        "Rf/current provenance may be declared-only",
    ]
    if protocol.position_policy == "current_position":
        unresolved.append("stage coordinate unknown/current; geometry compatibility limited")
    prereq = [
        "single device owner + duty journal",
        "--allow-light for emission",
        "operator checkpoints with all light off before optical_block conditions",
    ]
    if duration > wall:
        unresolved.append(f"predicted duration {duration:.1f}s exceeds max_wall_s={wall}")

    return ProtocolPlan(
        protocol=protocol,
        steps=steps,
        predicted_duration_s=duration,
        predicted_on_ms=on_ms,
        cooldowns_s=cooldowns,
        assumptions=assumptions,
        unresolved=unresolved,
        allocation_detail=allocation,
        physical_prerequisites=prereq,
    )


def _snapshot_for_plan(
    plan: ProtocolPlan, cfg: HwConfig, *, simulated: bool, rig_identity: str
) -> AcquisitionSnapshot:
    rf: dict[str, RfProvenance] = {}
    for d in plan.protocol.detectors:
        try:
            raw_rf = cfg.section.raw(f"detectors.{d}.rf_ohm")
            rf[d] = RfProvenance(float(raw_rf), "declared", "config")
        except Exception:
            rf[d] = RfProvenance(None, "unknown", "rf_ohm missing")
    return build_acquisition_snapshot(
        protocol_hash=plan.protocol.protocol_hash(),
        config_snapshot={"sha256": cfg.sha256, "path": str(cfg.path)},
        config_sha256=cfg.sha256,
        channel_map_snapshot={"source": "config", "holes": list(plan.protocol.holes)},
        adc=AdcProvenance(
            gain=APPROVED_FIXED_GAIN,
            fsr_v=4.096,
            lsb_mv=0.125,
            effective_mode="mains",
            mains_hz=60.0,
            mains_periods=plan.protocol.conditions[0].mains_periods,
            settle_ms=float(plan.protocol.conditions[0].settle_ms),
            detector_order=plan.protocol.detectors,
        ),
        rf=rf,
        simulated=simulated,
        rig_identity=rig_identity,
        planned={
            "n_steps": len(plan.steps),
            "allocation": plan.allocation_detail,
            "budgets": plan.protocol.budgets,
        },
        input_range={d: "unverified" for d in plan.protocol.detectors},
        assembly=plan.protocol.assembly,
    )


@dataclass
class AcquisitionResult:
    store: ScanStore
    status: str
    plan: ProtocolPlan
    observations: list[dict[str, Any]] = field(default_factory=list)
    cancel_reason: str | None = None

    @property
    def folder(self) -> Path:
        return self.store.folder


def run_protocol(
    plan: ProtocolPlan,
    *,
    cfg: HwConfig,
    root: Path,
    sample_id: str,
    allow_light: bool,
    meas: Callable[[int, int, int], dict[str, Any]] | None = None,
    device: Any | None = None,
    simulated: bool = False,
    rig_identity: str = "offline",
    cancel_check: Callable[[], bool] | None = None,
    operator_confirm: Callable[[str], bool] | None = None,
) -> AcquisitionResult:
    """Execute a stationary protocol through typed MEAS only.

    Requires ``allow_light``. Never arms motors. ``meas(hole, settle_ms, n)`` may
    be injected for tests; otherwise ``device.meas`` is used (must already be open
    and journal-gated).
    """
    if not allow_light:
        raise ProtocolError("run requires --allow-light (no silent emission)")
    # Stationary: refuse if something tried to arm.
    if device is not None and getattr(device, "_motor_armed", False):
        raise ProtocolError("stationary protocol must not run while motors armed")

    snap = _snapshot_for_plan(plan, cfg, simulated=simulated, rig_identity=rig_identity)
    meta = {
        "mode": "protocol",
        "protocol": plan.protocol.to_dict(),
        "protocol_hash": plan.protocol.protocol_hash(),
        "protocol_plan": plan.to_dict(),
        "sample_id": sample_id,
        "simulated": simulated,
        "acquisition_snapshot": snap.to_dict(),
        "config_sha256": cfg.sha256,
        "stationary": True,
        "arms_motors": False,
    }
    store = ScanStore.create(root, "protocol", meta)
    store.meta["status"] = "RUNNING"
    store.save_meta()

    observations: list[dict[str, Any]] = []
    cal = resolve_calibration(gain=APPROVED_FIXED_GAIN, cfg=cfg, detector="ingaas")
    status = "COMPLETE"
    cancel_reason = None
    t0 = time.monotonic()
    max_wall = float(plan.protocol.budgets["max_wall_s"])

    def _meas(hole: int, settle: int, n: int) -> dict[str, Any]:
        if meas is not None:
            return meas(hole, settle, n)
        if device is None:
            raise ProtocolError("no meas callback or device")
        # Enforce gain readback if available.
        info = device.info(refresh=True)
        gain_read = str(
            info.values.get("adc_gain") or info.values.get("gain") or APPROVED_FIXED_GAIN
        )
        if gain_read not in (APPROVED_FIXED_GAIN, "1", "GAIN_ONE"):
            raise ProtocolError(
                f"device gain readback {gain_read!r} ≠ approved {APPROVED_FIXED_GAIN}"
            )
        m = device.meas(hole, settle_ms=settle, n=n)
        out: dict[str, Any] = {"hole": hole, "t_on_ms": m.t_on_ms}
        for det in plan.protocol.detectors:
            out[f"dark_{det}"] = m.dark(det) if hasattr(m, "dark") else None
            out[f"lit_{det}"] = m.lit(det) if hasattr(m, "lit") else None
            # Meas API uses .net(det)
            try:
                out[f"net_{det}"] = m.net(det)
            except Exception:
                out[f"net_{det}"] = None
        return out

    try:
        for step in plan.steps:
            if cancel_check and cancel_check():
                status = "INCOMPLETE"
                cancel_reason = "cancelled"
                break
            if time.monotonic() - t0 > max_wall:
                status = "INCOMPLETE"
                cancel_reason = "max_wall_s"
                break
            if step.optical_block or step.checkpoint:
                msg = step.checkpoint or f"optical_block condition {step.condition_id}"
                if operator_confirm is not None and not operator_confirm(msg):
                    status = "INCOMPLETE"
                    cancel_reason = "checkpoint_refused"
                    break
                # Light must be off at checkpoint; best-effort if device present.
                if device is not None:
                    with contextlib.suppress(Exception):
                        device.off()

            raw = _meas(step.hole, step.settle_ms, step.mains_periods)
            rows = []
            for det in plan.protocol.detectors:
                dark = raw.get(f"dark_{det}")
                lit = raw.get(f"lit_{det}")
                net = raw.get(f"net_{det}")
                if net is None and dark is not None and lit is not None:
                    net = float(lit) - float(dark)
                mv = None if net is None else cal.counts_to_mv(float(net))
                row = {
                    "run_id": store.run_id,
                    "step": step.index,
                    "phase": step.phase,
                    "height_hs": "",
                    "height_mm": "",
                    "direction": "none",
                    "rep": step.block,
                    "hole": step.hole,
                    "state": "lit",
                    "detector": det,
                    "dark_counts": dark,
                    "lit_counts": lit,
                    "net_counts": net,
                    "net_mv": None if mv is None else round(mv, 4),
                    "t_s": round(time.monotonic() - t0, 3),
                    "duty_wait_ms": 0,
                    "settle_ms": step.settle_ms,
                    "n": step.mains_periods,
                }
                rows.append(row)
                observations.append(
                    {
                        **row,
                        "condition_id": step.condition_id,
                        "optical_block": step.optical_block,
                        "block": step.block,
                    }
                )
            store.append_rows(rows, completed_step=step.index)
    except Exception as e:
        status = "INCOMPLETE"
        cancel_reason = f"error:{type(e).__name__}:{e}"
        store.abort(cancel_reason)
        # Still seal partial.
    finally:
        if device is not None:
            with contextlib.suppress(Exception):
                device.off()

    # Terminal seal over frozen manifest + raw cube bytes.
    raw_bytes = b""
    if store.cube_path.exists():
        raw_bytes = store.cube_path.read_bytes()
    seal = seal_terminal_source(
        snap,
        raw_bytes=raw_bytes,
        terminal_meta={"status": status, "cancel_reason": cancel_reason},
        revision="complete" if status == "COMPLETE" else "partial",
        status=status,
    )
    store.meta["terminal_source_seal"] = seal.to_dict()
    store.meta["observations"] = observations
    if cancel_reason:
        store.meta["cancel_reason"] = cancel_reason
        store.meta["unresolved"] = True
    if status == "COMPLETE":
        store.finish("COMPLETE")
    else:
        store.meta["status"] = "INCOMPLETE"
        store.meta["finished"] = store.meta.get("finished")
        store.save_meta()

    return AcquisitionResult(
        store=store,
        status=status,
        plan=plan,
        observations=observations,
        cancel_reason=cancel_reason,
    )


def allocation_objective(
    n_per_hole: dict[int, int],
    variance: dict[int, float],
    weights: dict[int, float],
) -> float:
    """Declared absolute-uncertainty objective: sum w * sigma / sqrt(n). Lower is better."""
    total = 0.0
    for h, n in n_per_hole.items():
        if n <= 0:
            return float("inf")
        sig = math.sqrt(max(float(variance.get(h, 1.0)), 0.0))
        total += float(weights.get(h, 1.0)) * sig / math.sqrt(n)
    return total
