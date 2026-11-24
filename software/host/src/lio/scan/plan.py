"""Scan planning: a mode and the travel limits -> an ordered list of steps, with ETA.

Heights are absolute half-steps from the top of travel (lio.stage: top = 0, down < 0).
The measured top is ``top_limit - stage.top_margin_steps`` (keep-out below the
light-tight top so the telescoping seal cannot open).
Everything comes from ``scan:`` in lio_hw.yaml, with per-run overrides.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from lio.analysis import move_duration_s
from lio.config import HwConfig
from lio.device import DutyTracker

PHASES = ("P0", "P1", "P2", "P3", "P4")


class PlanError(ValueError):
    """The requested scan cannot be planned (unknown mode, no limits, bad override)."""


@dataclass(frozen=True)
class ScanSettings:
    """Every tunable of a run (scan: in lio_hw.yaml, plus overrides)."""

    jog_speed: int = 500
    settle_ms_mech: int = 300
    dark_agree_sigma: float = 3.0
    dark_agree_tries: int = 5
    dark_n: int = 8
    optical_settle_ms: int = 8
    sweep_n: int = 2
    hum_every_k: int = 4
    hum_bursts: int = 17
    long_dark_s: float = 30.0
    ref_offset_steps: int = 4096
    arm_renew_s: float = 40.0
    heartbeat_timeout_s: float = 90.0
    abort_on_saturation: bool = True
    lead_mm_per_rev: float | None = 1.0
    mains_hz: int = 60  # firmware >= 2.5.1: readings integrate whole mains periods (0 = off)
    mains_periods: int = 2  # periods per reading in that mode (replaces sweep_n)

    @classmethod
    def from_config(cls, cfg: HwConfig, overrides: dict[str, Any] | None = None) -> ScanSettings:
        src: dict[str, Any] = {}
        try:
            sec = cfg.section.mapping("scan")
        except Exception:
            sec = {}
        names = {f for f in cls.__dataclass_fields__}
        for k in names:
            if k in sec:
                src[k] = sec[k]
        for k, v in (overrides or {}).items():
            if k not in names:
                raise PlanError(f"unknown scan setting {k!r}; known: {', '.join(sorted(names))}")
            src[k] = v
        # S3: an override that the acquisition would ignore is refused, not silently
        # recorded: with mains integration each reading uses mains_periods.
        mains_on = float(src.get("mains_hz") or 0) > 0
        ov = overrides or {}
        # Refuse a CHANGED value that the acquisition would ignore; an unchanged
        # echo of the configured value (older callers send every field) is harmless.
        if mains_on and "sweep_n" in ov and int(ov["sweep_n"]) != int(sec.get("sweep_n", 2)):
            raise PlanError(
                "sweep_n has no effect while mains integration is on (mains_hz > 0); "
                "set mains_periods instead"
            )
        if (
            not mains_on
            and "mains_periods" in ov
            and int(ov["mains_periods"]) != int(sec.get("mains_periods", 2))
        ):
            raise PlanError("mains_periods has no effect while mains integration is off")
        out: dict[str, Any] = {}
        for k, v in src.items():
            default = getattr(cls, k)
            try:
                if isinstance(default, bool):
                    out[k] = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes")
                elif isinstance(default, int):
                    out[k] = int(v)
                elif default is None or isinstance(default, float):
                    out[k] = None if v in (None, "", "none") else float(v)
                else:
                    out[k] = v
            except (TypeError, ValueError) as e:
                raise PlanError(f"scan setting {k}: bad value {v!r}") from e
        return cls(**out)


@dataclass(frozen=True)
class Step:
    """One unit of work, checkpointed when done.

    kind: ``static`` (P1 electrical characterisation, here), ``measure`` (move to
    ``height`` approaching from ``direction``, then measure), ``extra`` (P3: points
    around the optimum, resolved after the down pass), ``continuous`` (measure while
    moving to ``height``), ``closing`` (P4 at the top: re-measure and interlocks)."""

    index: int
    phase: str
    kind: str
    height: int
    direction: str = "none"  # down | up | none (the side the height is approached from)
    rep: int = 0
    hum: bool = False
    label: str = ""


@dataclass
class ScanPlan:
    mode: str
    label: str
    top: int  # measured top (top limit - margin)
    bottom: int
    settings: ScanSettings
    steps: list[Step] = field(default_factory=list)
    heights_down: list[int] = field(default_factory=list)
    heights_up: list[int] = field(default_factory=list)
    ref_heights: list[int] = field(default_factory=list)
    repeats: int = 1
    extra_near_optimum: int = 0
    static: bool = False
    continuous: bool = False
    return_top: bool = True
    eta_s: float = 0.0
    eta_parts: dict[str, float] = field(default_factory=dict)
    duty: dict[str, Any] = field(default_factory=dict)

    def mm(self, h: float) -> float | None:
        lead = self.settings.lead_mm_per_rev
        return None if lead is None else h / 4096.0 * lead

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["settings"] = asdict(self.settings)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScanPlan:
        d = dict(d)
        d["settings"] = ScanSettings(**d["settings"])
        d["steps"] = [Step(**s) for s in d["steps"]]
        return cls(**d)

    def summary(self) -> str:
        d = self.duty
        lines = [
            f"mode {self.mode}: {self.label}",
            f"travel measured: top {self.top} to bottom {self.bottom} half-steps"
            + (
                f" ({self.mm(self.top):.1f} to {self.mm(self.bottom):.1f} mm)"
                if self.mm(0) is not None
                else ""
            ),
            f"heights down {len(self.heights_down)}, up {len(self.heights_up)}, reference "
            f"{len(self.ref_heights)} x {self.repeats} each way"
            + (
                f", +{self.extra_near_optimum} around the optimum"
                if self.extra_near_optimum
                else ""
            )
            + (", static (no motion)" if self.static else "")
            + (", continuous (MOTOR LIGHT 1)" if self.continuous else ""),
            f"steps {len(self.steps)}; estimated duration {self.eta_s / 60:.1f} min ("
            + ", ".join(f"{k} {v / 60:.1f}" for k, v in self.eta_parts.items())
            + ")",
            f"LED duty: max rail A on-time {d.get('max_on_ms_per_min_A', 0):.0f} ms/min per LED "
            f"(budget {d.get('budget_A', 0):.0f}), predicted waits {d.get('waits_s', 0):.0f} s",
        ]
        return "\n".join(lines)


def _linspace(a: int, b: int, n: int) -> list[int]:
    if n <= 0:
        return []
    if n == 1:
        return [a]
    return [round(a + (b - a) * i / (n - 1)) for i in range(n)]


def conv_s(cfg: HwConfig) -> float:
    """Time per ADC conversion as measured on the rig: 1/rate + software-I2C overhead."""
    return 1.0 / cfg.section.integer("adc.rate_sps") + 0.0019


def read_s(cfg: HwConfig, s: ScanSettings) -> float:
    """One reading on one input: sweep_n conversions, or (firmware >= 2.5.1, assumed
    when mains_hz is set) mains_periods whole mains periods."""
    plain = s.sweep_n * conv_s(cfg)
    if s.mains_hz:
        return max(plain, s.mains_periods / s.mains_hz + 0.004)
    return plain


def sweep_on_ms(cfg: HwConfig, s: ScanSettings) -> float:
    """On-time per LED in one SWEEP: settle + lit reads on both inputs."""
    return s.optical_settle_ms + 2 * read_s(cfg, s) * 1000


def measure_s(cfg: HwConfig, s: ScanSettings, hum: bool) -> float:
    c = conv_s(cfg)
    sweep = 16 * (2 * s.optical_settle_ms / 1000 + 4 * read_s(cfg, s) + 0.004)
    darks = 2 * 2 * s.dark_n * c
    t = s.settle_ms_mech / 1000 + 2 * darks + sweep + 0.3
    if hum:
        t += 2 * s.hum_bursts * 48 * 0.0025
    return t


def move_s(cfg: HwConfig, s: ScanSettings, steps: int) -> float:
    """A continuous jog plus the exact finish (or an exact move if short)."""
    n = abs(steps)
    if n == 0:
        return 0.0
    acc = float(cfg.limits["step_acc"])
    rpm_v = cfg.thresholds.integer("motion.travel.rpm") * cfg.limits["half_steps_per_rev"] / 60.0
    if n < 1500:
        return move_duration_s(n, rpm_v, acc) + 0.3
    return n / s.jog_speed + s.jog_speed / (2 * acc) + move_duration_s(200, rpm_v, acc) + 0.5


def _ref_heights(top: int, bottom: int, n: int) -> list[int]:
    if n <= 0:
        return []
    return [round(top + (bottom - top) * (i + 1) / (n + 1)) for i in range(n)]


def build(
    cfg: HwConfig,
    mode: str,
    *,
    top_limit: int | None,
    bottom_limit: int | None,
    current: int | None = None,
    top_margin: int = 0,
    overrides: dict[str, Any] | None = None,
) -> ScanPlan:
    """The plan for ``mode`` between the tracked limits (absolute half-steps)."""
    settings = ScanSettings.from_config(cfg, overrides)
    try:
        modes = cfg.section.mapping("scan.modes")
    except Exception as e:
        raise PlanError("no scan.modes in the config") from e
    if mode not in modes:
        raise PlanError(f"unknown mode {mode!r}; known: {', '.join(modes)}")
    m = dict(modes[mode])
    static = bool(m.get("static", False))
    continuous = bool(m.get("continuous", False))
    if top_limit is None or bottom_limit is None:
        if not static:
            raise PlanError(
                "travel limits not marked: set the top and the bottom (Motors tab, or "
                "lio stage set-top / mark-bottom)"
            )
        top_limit = bottom_limit = current if current is not None else 0
    top = top_limit - top_margin
    bottom = bottom_limit
    if not static and top <= bottom:
        raise PlanError(f"no travel between top {top} and bottom {bottom}")
    plan = ScanPlan(
        mode=mode,
        label=str(m.get("label", mode)),
        top=top,
        bottom=bottom,
        settings=settings,
        repeats=int(m.get("repeats", 1)),
        extra_near_optimum=int(m.get("extra_near_optimum", 0)),
        static=static,
        continuous=continuous,
        return_top=bool(m.get("return_top", True)),
    )
    steps: list[Step] = []

    def add(phase: str, kind: str, h: int, direction: str = "none", rep: int = 0,
            hum: bool = False, label: str = "") -> None:  # fmt: skip
        steps.append(Step(len(steps), phase, kind, h, direction, rep, hum, label))

    here = current if (static and current is not None) else top
    add("P1", "static", here, label="electrical characterisation (no motion)")
    if static:
        add("P4", "closing", here, label="closing checks here (drift, interlocks)")
        plan.steps = steps
        _estimate(cfg, plan)
        return plan
    if continuous:
        add("P2", "continuous", bottom, "down", label="measure while moving down")
        add("P3", "continuous", top, "up", label="measure while moving up")
        add("P4", "closing", top, label="closing checks at the top")
        plan.steps = steps
        _estimate(cfg, plan)
        return plan
    n_down = int(m.get("heights", 0))
    plan.heights_down = _linspace(top, bottom, n_down)
    k = max(1, settings.hum_every_k)
    for i, h in enumerate(plan.heights_down):
        add("P2", "measure", h, "down", hum=(i % k == 0))
    up = m.get("up", 0)
    if up == "same":
        plan.heights_up = list(reversed(plan.heights_down[:-1]))
    elif int(up or 0) > 0:
        plan.heights_up = list(reversed(_linspace(top, bottom, int(up))))[1:]
    if plan.extra_near_optimum:
        # placed after the down pass (the optimum is known then), measured going up
        for i in range(plan.extra_near_optimum):
            add(
                "P3", "extra", bottom, "up", rep=i, label="around the optimum (after the down pass)"
            )
    # The up pass and the repeatability pairs, merged in height order (bottom first) so
    # each reference height is repeated as the top passes it: no extra strokes.
    plan.ref_heights = _ref_heights(top, bottom, int(m.get("ref_heights", 0)))
    up_items: list[tuple[int, int, Step]] = []
    for i, h in enumerate(plan.heights_up):
        up_items.append((h, 0, Step(0, "P3", "measure", h, "up", hum=(i % k == 0))))
    for h in plan.ref_heights:
        for r in range(plan.repeats):
            up_items.append((h, 1 + 2 * r, Step(0, "P3", "measure", h, "down", rep=r + 1,
                                                label="repeatability, from above")))  # fmt: skip
            up_items.append((h, 2 + 2 * r, Step(0, "P3", "measure", h, "up", rep=r + 1,
                                                label="repeatability, from below")))  # fmt: skip
    for _, _, st in sorted(up_items, key=lambda x: (x[0], x[1])):
        add(st.phase, st.kind, st.height, st.direction, st.rep, st.hum, st.label)
    if plan.return_top:
        add("P4", "closing", top, label="closing checks at the top")
    else:
        add("P4", "closing", bottom if plan.heights_down else top, label="closing checks here")
    plan.steps = steps
    _estimate(cfg, plan)
    return plan


def _estimate(cfg: HwConfig, plan: ScanPlan) -> None:
    """ETA by phase, and the LED duty the run will need (simulated duty tracker)."""
    s = plan.settings
    parts: dict[str, float] = {"P0": 30.0, "P1": 0.0, "P2": 0.0, "P3": 0.0, "P4": 0.0}
    c = conv_s(cfg)
    p1 = s.long_dark_s * 2 + 2 * s.hum_bursts * 48 * 0.0025 + 16 * 2 * 2 * s.dark_n * c
    th = cfg.section
    duty = DutyTracker(
        window_s=th.num("duty.window_s"),
        budget_ms=cfg.duty_budgets_ms(),
        rail_of=cfg.duty_key,
    )
    on_ms = sweep_on_ms(cfg, s)
    t = parts["P0"] + p1
    parts["P1"] = p1
    pos = plan.top
    waits = 0.0

    def sweep_at(t: float) -> float:
        nonlocal waits
        for hole in range(1, 17):
            w = duty.wait_needed(hole, on_ms, t)
            if w > 0:
                waits += w
                t += w
            duty.record(hole, t, t + on_ms / 1000)
        return t + 16 * (2 * s.optical_settle_ms / 1000 + 4 * read_s(cfg, s))

    for st in plan.steps:
        t0 = t
        if st.kind == "static":
            t = sweep_at(t)
        elif st.kind in ("measure", "extra"):
            if st.rep:  # approach from the other side first
                away = st.height + (
                    s.ref_offset_steps if st.direction == "down" else -s.ref_offset_steps
                )
                t += move_s(cfg, s, away - pos) + move_s(cfg, s, s.ref_offset_steps)
            else:
                t += move_s(cfg, s, st.height - pos)
            pos = st.height
            t += measure_s(cfg, s, st.hum) - 16 * (
                2 * s.optical_settle_ms / 1000 + 4 * read_s(cfg, s)
            )
            t = sweep_at(t)
        elif st.kind == "continuous":
            t += move_s(cfg, s, st.height - pos) * 1.1
            pos = st.height
        elif st.kind == "closing":
            t += move_s(cfg, s, st.height - pos)
            pos = st.height
            t += 20.0
            t = sweep_at(t)
        parts[st.phase] = parts.get(st.phase, 0.0) + (t - t0)
    plan.eta_s = t
    plan.eta_parts = parts
    worst = 0.0
    for hole in range(1, 17):
        if cfg.channel(hole).rail == "A":
            # densest minute: what the tracker held at its fullest
            spans = duty.history.get(hole, [])
            for t0, _ in spans:
                worst = max(
                    worst,
                    sum(min(t1, t0 + 60) - max(a, t0) for a, t1 in spans if a < t0 + 60 and t1 > t0)
                    * 1000,
                )
    plan.duty = {
        "on_ms_per_sweep": round(on_ms, 1),
        "max_on_ms_per_min_A": round(worst, 1),
        "budget_A": th.num("duty.max_on_ms_per_channel.A"),
        "waits_s": round(waits, 1),
    }
    if not math.isfinite(plan.eta_s):
        raise PlanError("could not estimate the duration")
