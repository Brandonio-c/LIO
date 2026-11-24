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
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lio.buildinfo import loaded_build_identity
from lio.config import HwConfig
from lio.scan.calibration import resolve_calibration
from lio.scan.provenance import (
    AcquisitionSnapshot,
    AdcProvenance,
    CorePreflightError,
    RfProvenance,
    build_acquisition_snapshot,
    compute_store_seal,
    content_hash,
    core_adc_preflight,
)
from lio.scan.store import ScanStore

# Software-asserted checkpoint events (all-off / no-motion); never invents human OK.
CHECKPOINT_ALL_OFF = "all_off"
CHECKPOINT_NO_MOTION = "no_motion"

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
    production_budget_ms: float | None = None,
) -> dict[str, Any]:
    """Freeze production allocation from measured pilot variance + weights + costs (D16).

    Minimizes ``sum w * sigma / sqrt(n)`` under the on-time cap by greedy marginal
    improvement (depends on current N). Equal costs/weights/variances therefore
    balance (e.g. 3,3 not 5,1). Includes an equal-allocation comparator under the
    same total cost. Pilot observations are never confirmation.
    """
    weights = {
        int(k): float(v) for k, v in (protocol.allocation.get("target_weights") or {}).items()
    }
    for h in protocol.holes:
        weights.setdefault(h, 1.0)
    n_pilot = int(protocol.blocks.get("n_pilot", 2))
    min_prod = int(protocol.blocks.get("n_production_min", 1))
    max_prod = int(protocol.blocks.get("n_production_max", 16))
    cond0 = protocol.conditions[0]
    default_cost = _on_ms_for(cond0) * len(protocol.conditions)
    costs = {h: float((pilot_cost_ms or {}).get(h, default_cost)) for h in protocol.holes}
    max_on = float(protocol.budgets["max_total_on_ms"])
    pilot_on = sum(n_pilot * costs[h] for h in protocol.holes)
    remaining = (
        float(production_budget_ms)
        if production_budget_ms is not None
        else max(0.0, max_on - pilot_on)
    )
    controls = {int(h) for h in (protocol.allocation.get("control_holes") or [8, 9])}
    sigma = {}
    for h in protocol.holes:
        v = float(pilot_variance.get(h, 1.0))
        if not math.isfinite(v) or v < 0:
            v = 1.0
        sigma[h] = math.sqrt(max(v, 1e-12))

    def objective(alloc: dict[int, int]) -> float:
        return allocation_objective(alloc, {h: sigma[h] ** 2 for h in alloc}, weights)

    def marginal_gain(h: int, n: int) -> float:
        """Reduction in objective from n -> n+1, per unit cost."""
        before = float("inf") if n < 1 else weights[h] * sigma[h] / math.sqrt(n)
        after = weights[h] * sigma[h] / math.sqrt(n + 1)
        return (before - after) / max(costs[h], 1e-9)

    alloc = {h: min_prod for h in protocol.holes}
    for h in controls:
        if h in alloc:
            alloc[h] = max(alloc[h], min_prod)
    used = sum(alloc[h] * costs[h] for h in protocol.holes)
    while True:
        candidates = [
            h for h in protocol.holes if alloc[h] < max_prod and used + costs[h] <= remaining + 1e-9
        ]
        if not candidates:
            break
        # Marginal improvement; ties break toward lower current n then hole id.
        h_best = max(
            candidates,
            key=lambda h: (marginal_gain(h, alloc[h]), -alloc[h], -h),
        )
        alloc[h_best] += 1
        used += costs[h_best]

    # Equal-allocation comparator under identical total production cost.
    total_prod_slots = sum(alloc.values())
    n_holes = len(protocol.holes)
    base, rem = divmod(total_prod_slots, n_holes) if n_holes else (0, 0)
    equal = {h: base + (1 if i < rem else 0) for i, h in enumerate(protocol.holes)}
    return {
        "policy": "pilot_frozen",
        "n_pilot_per_hole": {str(h): n_pilot for h in protocol.holes},
        "n_production_per_hole": {str(h): int(alloc[h]) for h in protocol.holes},
        "equal_allocation_comparator": {str(h): int(equal[h]) for h in protocol.holes},
        "objective_value": objective(alloc),
        "equal_objective_value": objective(equal),
        "pilot_variance": {str(k): float(v) for k, v in pilot_variance.items()},
        "weights": {str(k): float(v) for k, v in weights.items()},
        "costs_ms": {str(k): float(v) for k, v in costs.items()},
        "remaining_on_ms": remaining,
        "used_production_on_ms": used,
        "reason": "frozen from measured pilot variance; pilot excluded from confirmation",
        "objective": "minimize sum_i w_i * sigma_i / sqrt(n_i) under on-time cap",
        "measured_pilot": True,
    }


def write_production_freeze(
    store: Any,
    *,
    pilot_observations: list[dict[str, Any]],
    allocation: dict[str, Any],
    protocol_hash: str,
) -> dict[str, Any]:
    """Immutable production-freeze artifact after pilot (D16). Does not mutate snapshot."""
    from lio.scan.provenance import content_hash as _ch

    freeze = {
        "schema": 1,
        "kind": "production_freeze",
        "protocol_hash": protocol_hash,
        "pilot_observation_ids": [
            f"{o.get('step')}:{o.get('hole')}:{o.get('condition_id')}:{o.get('block')}"
            for o in pilot_observations
        ],
        "pilot_n": len(pilot_observations),
        "allocation": dict(allocation),
        "schedule_hash": _ch(allocation),
        "pilot_excluded_from_confirmation": True,
    }
    store.meta["production_freeze"] = freeze
    store.save_meta()
    path = store.folder / "production_freeze.json"
    path.write_text(json.dumps(freeze, indent=1) + "\n", encoding="utf-8")
    return freeze


def measure_pilot_variance(
    observations: list[dict[str, Any]], *, detector: str = "ingaas"
) -> dict[int, float]:
    """Sample variance of pilot nets per hole (measured, not prior=1)."""
    by_hole: dict[int, list[float]] = {}
    for o in observations:
        if o.get("phase") != "pilot":
            continue
        if o.get("detector") and o.get("detector") != detector:
            continue
        try:
            h = int(o["hole"])
            raw_net = o.get("net_counts")
            if raw_net is None:
                continue
            net = float(raw_net)
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(net):
            continue
        by_hole.setdefault(h, []).append(net)
    out: dict[int, float] = {}
    for h, vals in by_hole.items():
        if len(vals) < 2:
            out[h] = 1.0  # insufficient — explicit unit default, labelled by caller
        else:
            mean = sum(vals) / len(vals)
            out[h] = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return out


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
    allocation_override: dict[str, Any] | None = None,
) -> ProtocolPlan:
    """Fully offline protocol plan. Never constructs a device or opens serial.

    ``allocation_override`` freezes an immutable production schedule (CE10) so
    hole→N mappings cannot be silently rebuilt or swapped.
    """
    protocol = load_protocol(source)
    policy = str(protocol.allocation.get("policy") or "equal_fixed")
    if allocation_override is not None:
        allocation = dict(allocation_override)
        # Preserve explicit per-hole production counts immutably.
        if "n_production_per_hole" in allocation:
            allocation["n_production_per_hole"] = {
                str(k): int(v) for k, v in allocation["n_production_per_hole"].items()
            }
    elif policy == "equal_fixed":
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
        # Soft calibration caveats (D19): do not block authorized sim/gated runs.
        "A0 input-range unverified until bench qualification",
        "Rf/current provenance may be declared-only",
    ]
    unresolved: list[str] = []
    if protocol.position_policy == "current_position":
        assumptions.append("stage coordinate unknown/current; geometry compatibility limited")
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
            # Applied mains_hz is filled after device configure/readback (D06).
            effective_mode="mains_pending_apply",
            mains_hz=None,
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


def record_operator_checkpoint(
    store: ScanStore,
    *,
    checkpoint_id: str,
    message: str,
    operator_confirmed: bool,
    all_off: bool,
    no_motion: bool,
    condition_id: str | None = None,
    step_index: int | None = None,
    occurrence_id: str | None = None,
    safe_state_verified: bool | None = None,
) -> dict[str, Any]:
    """Record a checkpoint event from software-visible state + explicit operator flag.

    Does **not** invent human confirmation: ``operator_confirmed`` must be supplied
    by the caller for *this occurrence*. ``all_off`` / ``no_motion`` are software
    assertions only. A start checkbox must not confirm later interventions (D13).
    """
    verified = (
        bool(safe_state_verified)
        if safe_state_verified is not None
        else (bool(all_off) and bool(no_motion))
    )
    event = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checkpoint_id": checkpoint_id,
        "occurrence_id": occurrence_id or checkpoint_id,
        "message": message,
        "operator_confirmed": bool(operator_confirmed),
        "safe_state_verified": verified,
        "software_state": {
            CHECKPOINT_ALL_OFF: bool(all_off),
            CHECKPOINT_NO_MOTION: bool(no_motion),
        },
        "condition_id": condition_id,
        "step_index": step_index,
        "human_confirmation_invented": False,
    }
    store.meta.setdefault("operator_checkpoints", []).append(event)
    store.event(
        "operator_checkpoint",
        checkpoint_id=checkpoint_id,
        occurrence_id=event["occurrence_id"],
        operator_confirmed=bool(operator_confirmed),
        all_off=bool(all_off),
        no_motion=bool(no_motion),
        safe_state_verified=verified,
    )
    return event


def _software_all_off(device: Any | None) -> bool | None:
    """True/False when known; None when state cannot be verified (D13 fail-closed)."""
    if device is None:
        return True  # offline/fake meas: no lit channel asserted
    try:
        st = device.status()
        ch = st.values.get("ch", "0")
        if str(ch).lower() in ("none", ""):
            return True
        return int(st.as_int("ch")) == 0
    except Exception:
        return None


def _software_no_motion(device: Any | None) -> bool | None:
    if device is None:
        return True
    try:
        if getattr(device, "_motor_armed", False):
            return False
        st = device.status()
        idle = st.as_str("motor1") != "run" and st.as_str("motor2") != "run"
        return bool(idle)
    except Exception:
        return None


def _establish_safe_state(device: Any | None) -> tuple[bool, bool | None, bool | None]:
    """OFF then re-read. Returns (ok, all_off, no_motion). Unknown → not ok (D13)."""
    if device is not None:
        with contextlib.suppress(Exception):
            device.off()
            if hasattr(device, "motor_stop"):
                device.motor_stop()
    all_off = _software_all_off(device)
    no_motion = _software_no_motion(device)
    ok = all_off is True and no_motion is True
    return ok, all_off, no_motion


def _finalize_protocol(
    store: ScanStore,
    snap: AcquisitionSnapshot,
    *,
    status: str,
    cancel_reason: str | None,
    observations: list[dict[str, Any]],
) -> None:
    """Durable terminal status: never silently promote incomplete → complete."""
    # Seal cube + streams + their interpretation mapping (D10 / A11).
    store.meta.setdefault("acquisition_snapshot", snap.to_dict())
    seal = compute_store_seal(store, status=status, cancel_reason=cancel_reason)
    if seal is None:  # pragma: no cover - snapshot set just above
        raise RuntimeError("terminal seal could not be computed")
    store.meta["terminal_source_seal"] = seal.to_dict()
    store.meta["terminal_source_seal_inputs"] = {"status": status, "cancel_reason": cancel_reason}
    store.meta["observations"] = observations
    # Duty journal charges are retained by the ownership journal independently;
    # never clear them here on cancel.
    store.meta["duty_journal_policy"] = "retain_charges_on_incomplete"
    if status == "COMPLETE":
        # Successful finish clears prior incomplete markers (e.g. after resume).
        store.meta.pop("cancel_reason", None)
        store.meta.pop("unresolved", None)
        store.finish("COMPLETE")
    else:
        # Explicit durable incomplete — never auto-promote.
        if cancel_reason:
            store.meta["cancel_reason"] = cancel_reason
        store.meta["status"] = "INCOMPLETE"
        store.meta["unresolved"] = True
        store.save_meta()


def frozen_inference_family(protocol: ProtocolSpec, alpha: float = 0.05) -> dict[str, Any]:
    """Detector x hole x contrast family declared from the protocol (S5).

    Condition contrasts (each later condition minus the first, same hole, paired
    by ``pair_id``) for every target hole and detector, plus target-minus-control
    contrasts for every non-control hole when control holes are declared. Frozen
    at run creation; missing or failed members stay in the family.
    """
    conds = [c.id for c in protocol.conditions]
    controls = [int(h) for h in (protocol.allocation or {}).get("control_holes") or []]
    members: list[str] = []
    for det in protocol.detectors:
        for hole in protocol.holes:
            for c in conds[1:]:
                members.append(f"{det}:h{hole}:{c}-minus-{conds[0]}")
            if controls and hole not in controls:
                for c in conds:  # one control contrast per condition: never pooled
                    members.append(f"{det}:h{hole}:{c}:minus-control")
    return {"members": members, "size": len(members), "alpha": alpha,
            "method": "bonferroni", "frozen": True}  # fmt: skip


class RunClock:
    """Persistent elapsed time for a run's wall/cycle limits (D14 / D15 / A17).

    Elapsed time accumulates while measuring, paused, prompting AND between a
    stop and a resume (downtime counted by the wall clock). Monotonic time going
    backwards, or a resume whose wall clock went backwards across an unknown
    boot, grants no time: the run expires with ``clock_discontinuity``.
    """

    def __init__(
        self,
        exposure: dict[str, Any],
        *,
        mono: Callable[[], float],
        wall: Callable[[], float],
    ) -> None:
        from lio.ownership import UNKNOWN_BOOT, _boot_id

        self.e = exposure
        self.mono = mono
        self.wall = wall
        self.boot = _boot_id()
        self.expired_reason: str | None = None
        now_m, now_w = mono(), wall()
        elapsed = float(exposure.get("elapsed_s") or 0.0)
        last_m, last_w = exposure.get("last_mono"), exposure.get("last_wall")
        if last_w is not None:
            exposure["deadlines_retained"] = True
            prev_m = None if last_m is None else float(last_m)
            same_frame = (
                exposure.get("clock_boot") == self.boot
                and self.boot != UNKNOWN_BOOT
                and prev_m is not None
                and now_m >= prev_m
            )
            if same_frame and prev_m is not None:
                elapsed += now_m - prev_m
            else:
                downtime = now_w - float(last_w)
                if downtime < 0:
                    self.expired_reason = "clock_discontinuity"
                else:
                    elapsed += downtime
        self.elapsed = elapsed
        self.last_m = now_m
        self.save()

    def tick(self) -> None:
        now = self.mono()
        if now < self.last_m:
            self.expired_reason = "clock_discontinuity"
            return
        self.elapsed += now - self.last_m
        self.last_m = now

    def save(self) -> None:
        self.e.update(
            elapsed_s=self.elapsed,
            last_mono=self.last_m,
            last_wall=self.wall(),
            clock_boot=self.boot,
        )


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
    operator_checkpoint_flag: bool | None = None,
    store: ScanStore | None = None,
    start_step: int = 0,
    control: Any | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    clock: Callable[[], float] | None = None,
    wall_clock: Callable[[], float] | None = None,
) -> AcquisitionResult:
    """Execute a stationary protocol through typed MEAS only.

    Requires ``allow_light``. Never arms motors. Checkpoints require verified
    all_off AND no_motion before prompting; each occurrence needs a fresh answer
    (D13). Pause/heartbeat hold at verified OFF with no MEAS (D14). Cumulative
    total/cycle/wall exposure budgets are enforced (D15).
    """
    if not allow_light:
        raise ProtocolError("run requires --allow-light (no silent emission)")
    if device is not None and getattr(device, "_motor_armed", False):
        raise ProtocolError("stationary protocol must not run while motors armed")

    step_checkpoints = any(s.optical_block or s.checkpoint for s in plan.steps)
    proto_checkpoints = tuple(plan.protocol.operator_checkpoints)
    needs_checkpoint = bool(proto_checkpoints) or step_checkpoints
    if needs_checkpoint and operator_confirm is None and operator_checkpoint_flag is None:
        raise ProtocolError(
            "protocol requires operator checkpoint: pass operator_confirm callback "
            "or operator_checkpoint_flag=True (explicit; never invented)"
        )

    # Occurrence-scoped answers: start checkbox alone cannot confirm later prompts.
    _answered: set[str] = set()

    def _operator_says_ok(msg: str, *, occurrence_id: str) -> bool:
        if occurrence_id in _answered:
            return False  # stale reuse rejected
        if operator_confirm is not None:
            ok = bool(operator_confirm(msg))
        elif operator_checkpoint_flag is not None and occurrence_id.startswith("protocol:"):
            # Start/protocol flags may confirm protocol:* only — never step:* (D13).
            ok = bool(operator_checkpoint_flag)
        else:
            ok = False
        if ok:
            _answered.add(occurrence_id)
        return ok

    if store is None:
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
            "exposure_bound": (
                str(getattr(device, "exposure_bound", "unknown (device does not report it)"))
                if device is not None
                else ("simulated" if simulated else "offline-callback")
            ),
            "software": loaded_build_identity(),
            "stationary": True,
            "arms_motors": False,
            "exposure_budget": {
                "reserved_ms": 0.0,
                "actual_ms": 0.0,
                "uncertain_ms": 0.0,
                "max_total_on_ms": float(plan.protocol.budgets["max_total_on_ms"]),
                "max_cycle_s": float(plan.protocol.budgets.get("max_cycle_s") or 0),
                "max_wall_s": float(plan.protocol.budgets["max_wall_s"]),
                "wall_deadline_mono": None,
                "cycle_deadline_mono": None,
                "deadlines_retained": False,
            },
        }
        meta["schedule_sha256"] = content_hash(plan.to_dict()["steps"])
        # S5: the inference family is frozen BEFORE any confirmation data.
        meta["inference_family"] = frozen_inference_family(plan.protocol)
        store = ScanStore.create(root, "protocol", meta)
    else:
        raw = store.meta.get("acquisition_snapshot")
        if not raw:
            raise ProtocolError("resume store missing acquisition_snapshot")
        snap = AcquisitionSnapshot.from_dict(raw)

    if store.meta.get("status") == "COMPLETE":
        raise ProtocolError(f"{store.folder} is already COMPLETE; refuse silent re-run")
    store.meta["status"] = "RUNNING"
    store.save_meta()

    observations: list[dict[str, Any]] = list(store.meta.get("observations") or [])
    cal = resolve_calibration(gain=APPROVED_FIXED_GAIN, cfg=cfg, detector="ingaas")
    status = "COMPLETE"
    cancel_reason = None
    max_wall = float(plan.protocol.budgets["max_wall_s"])
    max_cycle = float(plan.protocol.budgets.get("max_cycle_s") or 0)
    max_total_on = float(plan.protocol.budgets["max_total_on_ms"])
    exposure = dict(
        store.meta.get("exposure_budget")
        or {
            "reserved_ms": 0.0,
            "actual_ms": 0.0,
            "uncertain_ms": 0.0,
            "max_total_on_ms": max_total_on,
            "max_cycle_s": max_cycle,
            "max_wall_s": max_wall,
        }
    )
    # CE09 / D15: spent costs persist across resume and are never reset.
    actual_on_ms = float(exposure.get("actual_ms") or 0.0)
    run_clock = RunClock(exposure, mono=clock or time.monotonic, wall=wall_clock or time.time)
    t0 = run_clock.mono()  # this process's start (for row timestamps only)
    store.meta["exposure_budget"] = dict(exposure)
    store.save_meta()

    def _persist_exposure() -> None:
        exposure["actual_ms"] = actual_on_ms
        run_clock.save()
        store.meta["exposure_budget"] = dict(exposure)
        store.save_meta()

    def _budget_stop(next_on: float) -> str | None:
        """Re-check every persistent limit for the NEXT operation (after any wait)."""
        run_clock.tick()
        if run_clock.expired_reason:
            return run_clock.expired_reason
        dur_s = next_on / 1000.0
        if run_clock.elapsed + dur_s > max_wall:
            return "max_wall_s"
        if max_cycle > 0 and run_clock.elapsed + dur_s > max_cycle:
            return "max_cycle_s"
        if float(exposure.get("reserved_ms") or 0.0) + next_on > max_total_on + 1e-9:
            return "max_total_on_ms"
        return None

    def _progress(step: PlannedStep | None, state: str) -> None:
        if on_progress is None and control is None:
            return
        payload = {
            "status": state,
            "done": int(store.meta.get("completed_step", -1)) + 1,
            "of": len(plan.steps),
            "kind": "protocol",
            "paused": bool(getattr(control, "paused", False)) if control else False,
            "step": None if step is None else step.index,
            "phase": None if step is None else step.phase,
            "actual_on_ms": actual_on_ms,
        }
        if control is not None:
            with contextlib.suppress(Exception):
                control.progress = dict(payload)
                paused_now = bool(getattr(control, "pause_requested", False))
                control.paused = paused_now and state == "paused"
        if on_progress is not None:
            on_progress(payload)

    def _await_running(step: PlannedStep | None) -> str | None:
        """Honor pause/heartbeat; return cancel reason or None. No MEAS while paused."""
        if control is None and cancel_check is None:
            return None
        while True:
            if cancel_check and cancel_check():
                return "cancelled"
            if control is not None and getattr(control, "abort_reason", None):
                return str(control.abort_reason)
            expired = _budget_stop(0.0)  # a pause still spends the run's time
            if expired:
                return expired
            pause = False
            if control is not None:
                pause = bool(getattr(control, "pause_requested", False))
                if getattr(control, "heartbeat_required", False) and not control.heartbeat_ok():
                    pause = True
            if not pause:
                if control is not None:
                    control.paused = False
                if _paused_logged["on"]:
                    _paused_logged["on"] = False
                    store.event("unpaused", step=None if step is None else step.index)
                return None
            # D14: pause at verified OFF; no MEAS while paused/prompting.
            _establish_safe_state(device)
            if not _paused_logged["on"]:
                _paused_logged["on"] = True
                store.event("paused", step=None if step is None else step.index)
            if control is not None:
                control.paused = True
            _progress(step, "paused")
            time.sleep(0.05)

    def _checkpoint(msg: str, *, occurrence_id: str, step: PlannedStep | None = None) -> str | None:
        """Returns cancel_reason or None. Refuses MEAS on failed/unknown safe state."""
        ok, all_off, no_motion = _establish_safe_state(device)
        if not ok:
            record_operator_checkpoint(
                store,
                checkpoint_id=occurrence_id.split(":")[0],
                occurrence_id=occurrence_id,
                message=msg,
                operator_confirmed=False,
                all_off=bool(all_off),
                no_motion=bool(no_motion),
                condition_id=None if step is None else step.condition_id,
                step_index=None if step is None else step.index,
                safe_state_verified=False,
            )
            return "unsafe_state_before_checkpoint"
        # Prompt only after verified safe state (D13).
        confirmed = _operator_says_ok(msg, occurrence_id=occurrence_id)
        # Re-verify after prompt (operator may have intervened).
        ok2, all_off2, no_motion2 = _establish_safe_state(device)
        record_operator_checkpoint(
            store,
            checkpoint_id=occurrence_id.split(":")[0],
            occurrence_id=occurrence_id,
            message=msg,
            operator_confirmed=confirmed,
            all_off=bool(all_off2) if all_off2 is not None else False,
            no_motion=bool(no_motion2) if no_motion2 is not None else False,
            condition_id=None if step is None else step.condition_id,
            step_index=None if step is None else step.index,
            safe_state_verified=ok2,
        )
        if not ok2:
            return "unsafe_state_after_checkpoint"
        if not confirmed:
            return "checkpoint_refused"
        return None

    # Protocol-level checkpoints at start.
    if start_step == 0 and proto_checkpoints:
        for i, msg in enumerate(proto_checkpoints):
            reason = _checkpoint(msg, occurrence_id=f"protocol:{i}")
            if reason:
                status = "INCOMPLETE"
                cancel_reason = reason
                _finalize_protocol(
                    store,
                    snap,
                    status=status,
                    cancel_reason=cancel_reason,
                    observations=observations,
                )
                return AcquisitionResult(
                    store=store,
                    status=status,
                    plan=plan,
                    observations=observations,
                    cancel_reason=cancel_reason,
                )

    # A18: core ADC profile verified on START and RESUME before any light.
    core_facts: dict[str, Any] = {}
    if device is not None and meas is None:
        mains_req = int(cfg.section.integer("scan.mains_hz"))
        try:
            core_facts = core_adc_preflight(device, mains_hz=mains_req)
        except CorePreflightError as e:
            store.abort(f"preflight:{e}")
            raise ProtocolError(f"preflight refused: {e}") from e
        store.meta.setdefault("adc_preflight", []).append({"resume": start_step > 0, **core_facts})
        snap_adc = (store.meta.get("acquisition_snapshot") or {}).get("adc")
        if isinstance(snap_adc, dict) and start_step == 0:
            snap_adc["mains_hz"] = float(core_facts["mains_hz"])
            snap_adc["effective_mode"] = "mains" if core_facts["mains_hz"] else "ordinary"
        store.save_meta()

    def _meas(hole: int, settle: int, n: int) -> dict[str, Any]:
        if meas is not None:
            return meas(hole, settle, n)
        if device is None:
            raise ProtocolError("no meas callback or device")
        if getattr(device, "mains_hz", 0) != core_facts.get("mains_hz"):
            # The ADC profile changed under us (reset/reboot): never measure on it.
            raise ProtocolError("ADC mains state changed since preflight; refusing MEAS")
        m = device.meas(hole, settle_ms=settle, n=n)
        out: dict[str, Any] = {"hole": hole, "t_on_ms": m.t_on_ms}
        for det in plan.protocol.detectors:
            out[f"dark_{det}"] = m.dark(det) if hasattr(m, "dark") else None
            out[f"lit_{det}"] = m.lit(det) if hasattr(m, "lit") else None
            try:
                out[f"net_{det}"] = m.net(det)
            except Exception:
                out[f"net_{det}"] = None
        return out

    # Append-only chronology (S2): each process run is a numbered segment; row
    # times (t_s) restart per segment, so (segment, step) orders the record.
    segment_n = len(store.meta.get("segments") or [])
    segment = f"stationary:s{segment_n}"
    store.meta.setdefault("segments", []).append(
        {
            "segment": segment,
            "start_step": start_step,
            "resume": start_step > 0,
            "started_wall": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "clock": "row t_s is seconds since this segment's start",
        }
    )
    store.event("segment_start", segment=segment, start_step=start_step)
    _paused_logged = {"on": False}

    # The stationary position is unknown (no height): one instance per run, kept
    # across resume, never comparable to another run's unknown position.
    position_instance_id = str(
        store.meta.get("position_instance_id") or f"{store.run_id}:pos:{uuid.uuid4().hex[:12]}"
    )
    if store.meta.get("position_instance_id") != position_instance_id:
        store.meta["position_instance_id"] = position_instance_id
        store.save_meta()

    try:
        # Index loop so D16 can extend plan.steps after measured pilot freeze.
        step_i = start_step
        while step_i < len(plan.steps):
            step = plan.steps[step_i]
            reason = _await_running(step)
            if reason:
                status = "INCOMPLETE"
                cancel_reason = reason
                break
            next_on = float(step.estimated_on_ms)
            reason = _budget_stop(next_on)
            if reason:
                status = "INCOMPLETE"
                cancel_reason = reason
                break

            if step.optical_block or step.checkpoint:
                msg = step.checkpoint or f"optical_block condition {step.condition_id}"
                occ = f"step:{step.index}:{step.condition_id}:{step.block}"
                reason = _checkpoint(msg, occurrence_id=occ, step=step)
                if reason:
                    status = "INCOMPLETE"
                    cancel_reason = reason
                    break
                # Re-check pause after prompting.
                reason = _await_running(step)
                if reason:
                    status = "INCOMPLETE"
                    cancel_reason = reason
                    break

            # A17: prompts/pauses take time - re-check every limit right before MEAS.
            reason = _budget_stop(next_on)
            if reason:
                status = "INCOMPLETE"
                cancel_reason = reason
                break
            # A14 / D15: the permanent run cost is reserved and persisted BEFORE the
            # MEAS is sent; a timeout after transmission keeps it (and counts as
            # uncertain at the device's conservative charge).
            exposure["reserved_ms"] = float(exposure.get("reserved_ms") or 0.0) + next_on
            _persist_exposure()
            _progress(step, "measuring")
            try:
                raw = _meas(step.hole, step.settle_ms, step.mains_periods)
            except Exception:
                charge = float(getattr(device, "last_charge_ms", 0.0) or 0.0)
                exposure["reserved_ms"] = float(exposure["reserved_ms"]) + max(
                    0.0, charge - next_on
                )
                exposure["uncertain_ms"] = float(exposure.get("uncertain_ms") or 0.0) + max(
                    next_on, charge
                )
                _persist_exposure()
                raise
            charge = float(getattr(device, "last_charge_ms", 0.0) or 0.0)
            if charge > next_on:
                exposure["reserved_ms"] = float(exposure["reserved_ms"]) + (charge - next_on)
            reported = float(raw.get("t_on_ms") or next_on)
            actual_on_ms += reported
            _persist_exposure()

            rows = []
            # One firmware MEAS = one operation/reading shared by both detector
            # rows; a reacquisition after resume gets fresh ids (D12 / D16).
            op_id = f"{store.run_id}:op:{uuid.uuid4().hex[:12]}"
            ident = {
                "operation_id": op_id,
                "reading_id": op_id,
                "block_id": f"{step.phase}:{step.condition_id}:h{step.hole}:b{step.block}",
                "attempt_id": f"s{step.index}:{op_id.rsplit(':', 1)[-1]}",
                "condition_id": step.condition_id,
                "setting_id": f"settle{step.settle_ms}:n{step.mains_periods}",
                "segment": segment,
                "position_instance_id": position_instance_id,
                "pair_id": f"{step.phase}:h{step.hole}:b{step.block}",
                "control_group_id": f"{step.phase}:{step.condition_id}:b{step.block}",
            }
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
                    "t_s": round(run_clock.mono() - t0, 3),
                    "duty_wait_ms": 0,
                    "settle_ms": step.settle_ms,
                    "n": step.mains_periods,
                    **ident,
                }
                rows.append(row)
                observations.append(
                    {
                        **row,
                        "condition_id": step.condition_id,
                        "optical_block": step.optical_block,
                        "block": step.block,
                        "t_on_ms": reported,
                    }
                )
            store.append_rows(rows, completed_step=step.index)
            _progress(step, "measured")

            # Hard stop if reported exposure crossed the cap (D15) — do not continue.
            if max(actual_on_ms, float(exposure["reserved_ms"])) > max_total_on + 1e-9:
                status = "INCOMPLETE"
                cancel_reason = "max_total_on_ms"
                break

            # D16: after last pilot block, freeze production from MEASURED variance.
            if (
                str(plan.allocation_detail.get("policy") or "") == "pilot_frozen"
                and step.phase == "pilot"
                and not store.meta.get("production_freeze")
            ):
                nxt = plan.steps[step_i + 1] if step_i + 1 < len(plan.steps) else None
                if nxt is None or nxt.phase != "pilot":
                    pilot_obs = [o for o in observations if o.get("phase") == "pilot"]
                    measured = measure_pilot_variance(pilot_obs)
                    frozen = allocate_pilot_frozen(
                        plan.protocol,
                        pilot_variance=measured,
                    )
                    freeze = write_production_freeze(
                        store,
                        pilot_observations=pilot_obs,
                        allocation=frozen,
                        protocol_hash=plan.protocol.protocol_hash(),
                    )
                    prod_only = {
                        "policy": "pilot_frozen",
                        "n_pilot_per_hole": {str(h): 0 for h in plan.protocol.holes},
                        "n_production_per_hole": frozen["n_production_per_hole"],
                    }
                    prod_steps = _build_steps(plan.protocol, prod_only)
                    base = step.index + 1
                    for i, ps in enumerate(prod_steps):
                        ps.index = base + i
                    # Keep completed prefix; replace any prior-variance production.
                    plan.steps = list(plan.steps[: step_i + 1]) + prod_steps
                    plan.allocation_detail = frozen
                    store.meta["protocol_plan"] = plan.to_dict()
                    store.meta["schedule_sha256"] = content_hash(plan.to_dict()["steps"])
                    store.meta["production_freeze"] = freeze
                    store.save_meta()

            step_i += 1
    except Exception as e:
        status = "INCOMPLETE"
        cancel_reason = f"error:{type(e).__name__}:{e}"
        store.abort(cancel_reason)
    finally:
        if device is not None:
            with contextlib.suppress(Exception):
                device.off()
        _persist_exposure()

    store.event("segment_end", segment=segment, status=status, reason=cancel_reason)
    _finalize_protocol(
        store, snap, status=status, cancel_reason=cancel_reason, observations=observations
    )
    _progress(None, status.lower())

    return AcquisitionResult(
        store=store,
        status=status,
        plan=plan,
        observations=observations,
        cancel_reason=cancel_reason,
    )


def _validate_resume_records(store: ScanStore, plan: ProtocolPlan, start: int) -> None:
    """Semantic validation of the durable prefix before any resume (S2 / A15).

    Refuses (before any device use) when: an existing terminal seal no longer
    matches the live bytes/interpretation; the committed steps are not exactly
    0..start-1; any step lacks or duplicates a detector row; a row's hole, phase,
    condition, settings or block differs from the frozen step; a step's detector
    rows do not share ONE reading/operation identity; a reading identity repeats
    across steps; or rows leave the run's single stationary position instance.
    A RUNNING crash may legitimately have no seal: it is recorded as an explicit
    unsealed crash recovery, never silently resealed over a bad seal.
    """
    from lio.scan.provenance import verify_store_seal

    if store.meta.get("terminal_source_seal"):
        ok, why = verify_store_seal(store)
        if not ok:
            raise ProtocolError(f"resume refuses: existing terminal seal invalid ({why})")
    elif start > 0:
        store.meta.setdefault("recovery", []).append(
            {
                "kind": "unsealed_crash_recovery",
                "validated_steps": start,
                "note": "no terminal seal; durable rows validated semantically",
            }
        )
    detectors = list(plan.protocol.detectors)
    pos = store.meta.get("position_instance_id")
    by_step: dict[int, list[dict[str, str]]] = {}
    for r in store.rows():
        try:
            by_step.setdefault(int(r["step"]), []).append(r)
        except (KeyError, TypeError, ValueError) as e:
            raise ProtocolError(f"resume refuses an unreadable durable record: {e}") from e
    if sorted(by_step) != list(range(start)):
        raise ProtocolError(
            f"resume refuses: durable records cover steps {sorted(by_step)} but the run claims "
            f"0..{start - 1} complete"
        )
    seen_readings: set[str] = set()
    for idx, rows in sorted(by_step.items()):
        st = plan.steps[idx] if idx < len(plan.steps) else None
        if st is None:
            raise ProtocolError(f"resume refuses: step {idx} is not in the frozen schedule")
        dets = sorted(str(r.get("detector") or "") for r in rows)
        if dets != sorted(detectors):
            raise ProtocolError(
                f"resume refuses: step {idx} has detector rows {dets}, expected exactly "
                f"{sorted(detectors)}"
            )
        want = {
            "hole": str(st.hole), "phase": st.phase, "condition_id": st.condition_id,
            "setting_id": f"settle{st.settle_ms}:n{st.mains_periods}",
            "settle_ms": str(st.settle_ms), "n": str(st.mains_periods),
            "block_id": f"{st.phase}:{st.condition_id}:h{st.hole}:b{st.block}",
        }  # fmt: skip
        readings = set()
        for r in rows:
            for k, v in want.items():
                if str(r.get(k) or "") != v:
                    raise ProtocolError(
                        f"resume refuses: step {idx} row {k}={r.get(k)!r} does not match the "
                        f"frozen schedule ({v!r})"
                    )
            if pos and str(r.get("position_instance_id") or "") != str(pos):
                raise ProtocolError(f"resume refuses: step {idx} left the run's position instance")
            readings.add(str(r.get("reading_id") or ""))
        if len(readings) != 1 or "" in readings:
            raise ProtocolError(
                f"resume refuses: step {idx} detector rows do not share one reading identity"
            )
        rid = next(iter(readings))
        if rid in seen_readings:
            raise ProtocolError(f"resume refuses: reading {rid} appears in more than one step")
        seen_readings.add(rid)


def resume_protocol(
    folder: Path | str,
    *,
    cfg: HwConfig,
    allow_light: bool,
    meas: Callable[[int, int, int], dict[str, Any]] | None = None,
    device: Any | None = None,
    cancel_check: Callable[[], bool] | None = None,
    operator_confirm: Callable[[str], bool] | None = None,
    operator_checkpoint_flag: bool | None = None,
    control: Any | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    protocol_override: dict[str, Any] | Path | str | None = None,
    clock: Callable[[], float] | None = None,
    wall_clock: Callable[[], float] | None = None,
) -> AcquisitionResult:
    """Resume an INCOMPLETE protocol run from a completed-block boundary (D15).

    Refuses COMPLETE folders, changed frozen facts, and partial condition blocks.
    Preserves spent exposure budgets and ownership journal charges.
    """
    store = ScanStore.open(Path(folder))
    status = store.meta.get("status")
    if status == "COMPLETE":
        raise ProtocolError(f"{folder} is already COMPLETE; refuse silent promote/resume")
    if (
        status not in ("INCOMPLETE", "RUNNING", "ABORTED")
        and store.meta.get("unresolved") is not True
    ):
        raise ProtocolError(f"cannot resume protocol with status={status!r}")
    proto_plan = store.meta.get("protocol_plan")
    if not proto_plan:
        raise ProtocolError("store missing protocol_plan")
    frozen_proto = store.meta.get("protocol")
    if not frozen_proto:
        raise ProtocolError("store missing frozen protocol")
    # D15: changed protocol/config facts cannot resume as valid.
    if protocol_override is not None:
        raise ProtocolError("resume refuses protocol overrides; use frozen protocol only")
    if str(store.meta.get("config_sha256") or "") and str(store.meta.get("config_sha256")) != str(
        cfg.sha256
    ):
        raise ProtocolError("resume refuses changed config_sha256 / calibration facts")
    frozen_hash = store.meta.get("protocol_hash")
    plan = plan_protocol(frozen_proto, cfg)
    if frozen_hash and plan.protocol.protocol_hash() != frozen_hash:
        raise ProtocolError("resume refuses changed protocol hash")
    # D16 / A15: execute the EXACT frozen, ordered schedule - never a re-plan.
    frozen_steps = proto_plan.get("steps")
    if not frozen_steps:
        raise ProtocolError("resume refuses a run without its frozen step schedule")
    want = store.meta.get("schedule_sha256")
    if want and content_hash(frozen_steps) != want:
        raise ProtocolError("resume refuses: frozen schedule changed since it was recorded")
    plan.allocation_detail = dict(proto_plan.get("allocation_detail") or plan.allocation_detail)
    plan.steps = [
        PlannedStep(**{k: s[k] for k in PlannedStep.__dataclass_fields__ if k in s})
        for s in frozen_steps
    ]

    start = int(store.meta.get("completed_step", -1)) + 1
    _validate_resume_records(store, plan, start)
    # Completed-block boundary: if the next step continues a partial condition
    # pair (same block, later condition) after interruption mid-block, reject.
    if start > 0 and start < len(plan.steps):
        prev = plan.steps[start - 1]
        nxt = plan.steps[start]
        # A complete block means all conditions for (phase, hole, block) finished.
        # If prev and nxt share hole/block but we're mid-condition list after a
        # cancel, that is only OK when prev completed the last condition of the set.
        n_cond = len(plan.protocol.conditions)
        if n_cond > 1:
            # Index within the condition cycle for this hole/block.
            # Steps are ordered condition-major within each block.
            cond_ids = [c.id for c in plan.protocol.conditions]
            same_block = (
                prev.hole == nxt.hole and prev.block == nxt.block and prev.phase == nxt.phase
            )
            # Still inside the same block - only legal if prev was last condition.
            if same_block and prev.condition_id != cond_ids[-1]:
                raise ProtocolError(
                    "resume refuses partial condition block; "
                    "acquire a whole new block with a new id"
                )

    return run_protocol(
        plan,
        cfg=cfg,
        root=store.folder.parent,
        sample_id=str(store.meta.get("sample_id") or "unknown"),
        allow_light=allow_light,
        meas=meas,
        device=device,
        simulated=bool(store.meta.get("simulated")),
        rig_identity=str(
            (store.meta.get("acquisition_snapshot") or {}).get("rig_identity", "offline")
        ),
        cancel_check=cancel_check,
        operator_confirm=operator_confirm,
        operator_checkpoint_flag=operator_checkpoint_flag,
        store=store,
        start_step=start,
        control=control,
        on_progress=on_progress,
        clock=clock,
        wall_clock=wall_clock,
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
