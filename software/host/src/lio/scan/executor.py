"""Running a scan: P0 preflight, P1 static characterisation, P2/P3 height scans,
P4 closing checks (plan LIO-SW-SCAN-001 §3).

Safety rules (§3.3), all enforced here or below:

- one LED at a time, selected before CE is raised (the firmware's SWEEP/MEAS);
- the RAIL A duty budget (the device's duty tracker; waits are logged per step);
- stop-measure-move: no light while moving, except the labelled continuous mode;
- the soft limits always apply (lio.stage, via lio.motion);
- any abort sends OFF, MOTOR STOP and MOTOR RELEASE, records the reason and marks the
  run INCOMPLETE. An unexpected # BOOT aborts and leaves the position not trusted.

Each completed step is checkpointed (its rows appended, the index saved), so an
interrupted run resumes from the next step (§5.3).
"""

from __future__ import annotations

import contextlib
import json
import math
import statistics
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from lio import motion
from lio.config import HwConfig
from lio.device import DeviceError, LIODevice, NoResponse
from lio.operator import Abort, Operator
from lio.ownership import OwnershipError
from lio.scan.calibration import resolve_calibration
from lio.scan.plan import ScanPlan, Step
from lio.scan.store import ScanStore
from lio.stage import StageError

MIN_FIRMWARE = (2, 4, 0)
DETECTORS = ("opt101", "ingaas")
ADC_OF = {"ingaas": 0, "opt101": 1}


class ScanAbort(Exception):
    """Stop the run now (safely); the message is the recorded reason."""


def select_primary_swir_height(
    rows: Iterable[dict[str, str]],
) -> tuple[int, dict[str, Any]]:
    """One frozen primary-SWIR target-selection result (D17).

    Shared by fine placement, report and UI. Not the legacy all-channel noise max.
    H16 residuals cannot change the primary-SWIR optimum.
    """
    from lio.scan.provenance import content_hash
    from lio.scan.targets import primary_swir_objective, scout_height

    by_h: dict[float, dict[int, float]] = {}
    for r in rows:
        if r.get("state") != "lit" or r.get("phase") != "P2" or not r.get("net_counts"):
            continue
        if r.get("detector") not in (None, "", "ingaas"):
            continue
        try:
            height = float(r["height_hs"])
            hole = int(r["hole"])
            net = float(r["net_counts"])
        except (KeyError, TypeError, ValueError):
            continue
        by_h.setdefault(height, {})[hole] = net
    if not by_h:
        raise ScanAbort("fine mode: no down-pass data to place the points around the optimum")
    obj = primary_swir_objective()
    scout = scout_height(sorted(by_h.keys()), by_h, objective=obj)
    if scout.status != "selected" or scout.frozen_height_hs is None:
        raise ScanAbort(
            f"fine mode: primary-SWIR scout {scout.status}: {scout.detail or 'unresolved'}"
        )
    height = round(float(scout.frozen_height_hs))
    payload = scout.to_dict()
    payload["selection_id"] = content_hash(
        {
            "objective": obj.version,
            "frozen_height_hs": height,
            "status": scout.status,
            "exclusions": scout.exclusions,
        }
    )
    payload["consumed_by"] = ["planner", "fine_placement", "report", "ui"]
    return height, payload


def overall_optimum(rows: Iterable[dict[str, str]]) -> int:
    """Fine-mode height from the shared primary-SWIR objective (D17)."""
    height, _ = select_primary_swir_height(rows)
    return height


def overall_optimum_legacy_all_channel(rows: Iterable[dict[str, str]]) -> int:
    """Labelled legacy reproduction only — all-channel normalised peak (not qualified)."""
    by: dict[tuple[str, str], dict[int, float]] = {}
    for r in rows:
        if r.get("state") != "lit" or r.get("phase") != "P2" or not r.get("net_counts"):
            continue
        by.setdefault((r["hole"], r["detector"]), {})[int(r["height_hs"])] = float(r["net_counts"])
    score: dict[int, float] = {}
    for per_h in by.values():
        peak = max((abs(v) for v in per_h.values()), default=0.0)
        if peak <= 0:
            continue
        for h, v in per_h.items():
            score[h] = score.get(h, 0.0) + v / peak
    if not score:
        raise ScanAbort("fine mode: no down-pass data to place the points around the optimum")
    return max(score, key=lambda h: score[h])


@dataclass
class Control:
    """Shared with whoever started the run (dashboard, CLI): abort, pause, heartbeat.

    With ``heartbeat_required`` the run pauses at the next safe point when no beat
    has come for ``timeout_s`` (operator present), and carries on when beats return.
    """

    heartbeat_required: bool = False
    timeout_s: float = 90.0
    abort_reason: str | None = None
    pause_requested: bool = False
    paused: bool = False
    progress: dict[str, Any] = field(default_factory=dict)
    clock: Callable[[], float] = time.monotonic  # the browser beats in wall-clock time
    _last_beat: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def beat(self) -> None:
        with self._lock:
            self._last_beat = self.clock()

    def abort(self, reason: str = "operator abort") -> None:
        with self._lock:
            self.abort_reason = reason

    def pause(self, on: bool = True) -> None:
        with self._lock:
            self.pause_requested = on

    def heartbeat_ok(self) -> bool:
        if not self.heartbeat_required:
            return True
        with self._lock:
            if self._last_beat is None:  # counted from the first check
                self._last_beat = self.clock()
            return self.clock() - self._last_beat <= self.timeout_s


def _version(s: str) -> tuple[int, ...]:
    out = []
    for p in s.split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


class ScanExecutor:
    def __init__(
        self,
        dev: LIODevice,
        cfg: HwConfig,
        plan: ScanPlan,
        store: ScanStore,
        operator: Operator,
        *,
        sample_id: str,
        control: Control | None = None,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.dev = dev
        self.cfg = cfg
        self.plan = plan
        self.store = store
        self.operator = operator
        self.sample_id = sample_id
        self.control = control or Control()
        self.on_progress = on_progress
        self.s = plan.settings
        self.motion = motion.MotionSettings.from_config(cfg, jog_speed=self.s.jog_speed)
        self._boots0 = dev.unexpected_boots
        self._emi_pending = False
        self._t_start = 0.0
        self._rows: list[dict[str, Any]] = []
        self._moves = 0
        self._unlevel: list[list[int]] = []
        self.capabilities: dict[str, Any] = {}

    def _seal_terminal(self, status: str, *, cancel_reason: str | None = None) -> None:
        """Seal NEW runs that carry an acquisition_snapshot; historical no-op."""
        from lio.scan.provenance import seal_store_terminal

        seal_store_terminal(self.store, status=status, cancel_reason=cancel_reason)

    # ================================================================ running

    def run(self, *, resume: bool = False) -> str:
        """Execute the plan (or the rest of it); returns COMPLETE or INCOMPLETE."""
        self._t_start = self.dev.now()
        start = int(self.store.meta.get("completed_step", -1)) + 1 if resume else 0
        try:
            t0 = self.dev.now()
            self._preflight(resume=resume)
            self.store.phase_time("P0", self.dev.now() - t0)
            if start == 0 and not resume:
                self.store.event("start", mode=self.plan.mode, sample_id=self.sample_id)
            else:
                self.store.event("resume", from_step=start)
            for st in self.plan.steps[start:]:
                self._between_steps()
                self._progress(st, "running")
                t0 = self.dev.now()
                self._rows = []
                self._run_step(st)
                self._check_link()
                self.store.append_rows(self._rows, completed_step=st.index)
                self.store.phase_time(st.phase, self.dev.now() - t0)
            self._safe_stop()
            self._record_health()
            self.store.finish("COMPLETE")
            self._seal_terminal("COMPLETE")
            self.store.event("complete")
            self._progress(None, "complete")
            return "COMPLETE"
        except (ScanAbort, Abort, StageError, DeviceError, NoResponse, KeyboardInterrupt) as e:
            reason = self._reason(e)
            if self.dev.unexpected_boots > self._boots0 and "BOOT" not in reason:
                reason = f"unexpected # BOOT: the board reset during the run ({reason})"
            self._safe_stop()
            with contextlib.suppress(Exception):
                self._record_health()
            self.store.abort(reason, step=self.store.meta.get("completed_step", -1) + 1)
            self._seal_terminal("INCOMPLETE", cancel_reason=reason)
            self._progress(None, "aborted", reason=reason)
            if isinstance(e, KeyboardInterrupt):
                raise
            return "INCOMPLETE"
        except BaseException as e:
            # Anything unexpected (a full disk, a bug): make the rig safe first, then record
            # what we can and let the error through.
            self._safe_stop()
            with contextlib.suppress(Exception):
                self.store.abort(f"unexpected error: {type(e).__name__}: {e}",
                                 step=self.store.meta.get("completed_step", -1) + 1)  # fmt: skip
            with contextlib.suppress(Exception):
                self._seal_terminal("INCOMPLETE", cancel_reason=f"{type(e).__name__}: {e}")
            with contextlib.suppress(Exception):
                self._progress(None, "aborted", reason=f"{type(e).__name__}: {e}")
            raise

    @staticmethod
    def _reason(e: BaseException) -> str:
        if isinstance(e, KeyboardInterrupt):
            return "interrupted (Ctrl-C)"
        if isinstance(e, Abort):
            return f"operator abort: {e}"
        if isinstance(e, StageError):
            return f"stage / soft limit: {e}"
        if isinstance(e, DeviceError):
            if e.code == 4:
                return f"ADC dropout: {e}"
            return f"device refused: {e}"
        if isinstance(e, NoResponse):
            return f"lost contact with the board: {e}"
        return str(e)

    def _safe_stop(self) -> None:
        """OFF, MOTOR STOP, MOTOR RELEASE, MOTOR LIGHT 0: best effort, never raises.
        Mains integration back off too, so other tests see the boot behaviour."""
        for cmd in ("OFF", "MOTOR STOP", "MOTOR ALL RELEASE", "MOTOR LIGHT 0"):
            with contextlib.suppress(Exception):
                self.dev.command(cmd, timeout=1.5)
        if self.dev.mains_hz:
            with contextlib.suppress(Exception):
                self.dev.adc_mains(0)

    @property
    def _n(self) -> int:
        """Samples (or, with mains integration, mains periods) per reading."""
        return self.s.mains_periods if self.dev.mains_hz else self.s.sweep_n

    # ================================================================ checks

    def _check_link(self) -> None:
        if self.dev.unexpected_boots > self._boots0:
            raise ScanAbort(
                "unexpected # BOOT: the board reset during the run; position not trusted"
            )
        if self.control.abort_reason:
            raise ScanAbort(self.control.abort_reason)

    def _between_steps(self) -> None:
        self._check_link()
        if self.control.pause_requested or not self.control.heartbeat_ok():
            self._pause()

    def _pause(self) -> None:
        why = "pause requested" if self.control.pause_requested else "operator heartbeat missing"
        self._safe_stop()
        self.control.paused = True
        self.store.event("pause", reason=why)
        self._progress(None, "paused", reason=why)
        last_status = self.dev.now()
        while self.control.pause_requested or not self.control.heartbeat_ok():
            if self.control.abort_reason:
                self.control.paused = False
                raise ScanAbort(self.control.abort_reason)
            self.dev.sleep(0.5)
            if self.dev.now() - last_status > 5:
                self.dev.status()  # keep the link alive
                last_status = self.dev.now()
                self._check_link()
        self.control.paused = False
        self.store.event("continue")

    def _preflight(self, *, resume: bool) -> None:
        """P0: anything wrong here aborts before any motion."""
        dev = self.dev
        info = dev.info(refresh=True)
        fw = info.as_str("fw")
        if _version(fw) < MIN_FIRMWARE:
            raise ScanAbort(f"firmware {fw} is older than 2.4.0")
        if info.as_int("adc_ok") != 1:
            raise ScanAbort("ADS1115 not present (adc_ok=0)")
        st = dev.status()
        if st.as_int("ch") != 0 or st.as_str("motor1") == "run" or st.as_str("motor2") == "run":
            raise ScanAbort("the board is not in its safe state (an LED on or a motor moving)")
        self.capabilities = {
            "coupling_states": "debug_states" in info.values,  # firmware 2.5.0
            "mains_rejection": "mains" in info.values and self.s.mains_hz > 0,  # 2.5.1
            "rail_monitor": False,
            "home_sensors": False,
        }
        if resume:
            meta = self.store.meta
            was = meta.get("firmware", {}).get("fw")
            if was != fw:
                raise ScanAbort(f"cannot resume: firmware changed ({was} -> {fw})")
            if meta.get("config_sha256") != self.cfg.sha256:
                raise ScanAbort("cannot resume: lio_hw.yaml changed since the run started")
            # CE05: gain must still match frozen snapshot before any light.
            from lio.scan.provenance import read_info_gain

            live_gain = read_info_gain(info)
            snap = meta.get("acquisition_snapshot") or {}
            snap_gain = (snap.get("adc") or {}).get("gain") if isinstance(snap, dict) else None
            expected = str(snap_gain if snap_gain is not None else "1")
            exp_n = "1" if expected in ("1", "GAIN_ONE", "1.0") else expected
            live_n = None if live_gain is None else str(live_gain)
            live_n = "1" if live_n in ("1", "GAIN_ONE", "1.0") else live_n
            if live_n != exp_n:
                raise ScanAbort(
                    f"cannot resume: device gain {live_gain!r} ≠ snapshot gain {expected!r}"
                )
        moving = not self.plan.static
        stage = dev.stage
        if moving:
            if stage is None or not stage.known:
                raise ScanAbort("stage position unknown: set the top first")
            if not stage.valid:
                raise ScanAbort("stage position not trusted (unexpected boot): set the top again")
            lim = stage.limits
            if lim.top is None or lim.bottom is None:
                raise ScanAbort("travel limits not marked (top and bottom)")
        vocab = [str(x) for x in self.cfg.section.raw("scan.sample_ids")]
        if self.sample_id not in vocab and not self.sample_id.startswith("LIO-F-"):
            raise ScanAbort(
                f"sample_id {self.sample_id!r} not in {vocab} (or a food code LIO-F-...)"
            )
        self.store.answer("sample_id", self.sample_id)
        asks = [
            ("scan_lid_closed", "Is the chamber lid closed?"),
            ("scan_earth_bond", "Is the earth bond connected (circuit GND to mains earth)?"),
        ]
        if moving:
            asks.insert(
                0,
                (
                    "chamber_clear",
                    "Is the chamber clear, with nothing a moving top could hit or trap?",
                ),
            )
        if not resume:
            asks.append(("scan_sample", f"Is the sample in place: {self.sample_id}?"))
        for key, prompt in asks:
            ok = self.operator.confirm(key, prompt)
            self.store.answer(key, ok)
            if not ok:
                raise ScanAbort(f"preflight: operator answered no to {prompt!r}")
        # Core ADC profile on start AND resume (A18): gain 1 read back, mains
        # applied and read back. Refused before any light otherwise.
        from lio.scan.provenance import CorePreflightError, core_adc_preflight

        try:
            facts = core_adc_preflight(
                dev, mains_hz=self.s.mains_hz if self.capabilities["mains_rejection"] else 0
            )
        except CorePreflightError as e:
            raise ScanAbort(f"preflight: {e}") from e
        self.store.meta.setdefault("adc_preflight", []).append({"resume": resume, **facts})
        self.store.meta["capabilities"] = self.capabilities
        self.store.meta["skipped_checks"] = {
            k: reason
            for k, ok, reason in (
                ("coupling_states", self.capabilities["coupling_states"],
                 "firmware without CE-only / wrong-rail debug states (2.5.0 proposal)"),
                ("rail_monitor", False, "A2/A3 not wired for rail and ground monitoring"),
                ("home_sensors", False, "no home sensors fitted"),
            )
            if not ok
        }  # fmt: skip
        self.store.save_meta()
        if moving:
            dev.motor_arm()

    # ================================================================ steps

    def _run_step(self, st: Step) -> None:
        if st.kind == "static":
            if not self.plan.static:
                self._move_to(st.height)
            self._static(st)
        elif st.kind == "measure":
            self._approach(st)
            self._measure_here(st)
        elif st.kind == "extra":
            h = self._extra_height(st)
            self._approach(Step(st.index, st.phase, st.kind, h, st.direction, 0, st.hum, st.label))
            self._measure_here(
                Step(st.index, st.phase, st.kind, h, st.direction, st.rep, st.hum, st.label)
            )
        elif st.kind == "continuous":
            self._continuous(st)
        elif st.kind == "closing":
            if not self.plan.static:
                self._move_to(st.height)
            self._closing(st)
        else:  # pragma: no cover - plan and executor are built together
            raise ScanAbort(f"unknown step kind {st.kind!r}")

    def _height(self) -> int:
        st = self.dev.stage
        if st is not None and st.abs is not None:
            a = st.abs
            return round((a[0] + a[1]) / 2)
        p1, p2, _ = motion.positions(self.dev)
        return round((p1 + p2) / 2)

    def _move_to(self, h: int) -> None:
        during = self._emi_during if self._emi_pending else None
        ok, msg = motion.move_to(self.dev, self.cfg, h, settings=self.motion, during=during)
        self._emi_pending = False
        if not ok:
            raise ScanAbort(f"move to {h}: {msg}")
        self._check_link()
        a = self.dev.stage.abs if self.dev.stage is not None else None
        self._moves += 1
        if a is not None and a[0] != a[1]:
            self._unlevel.append([a[0], a[1]])

    def _record_health(self) -> None:
        """What the system matrix needs (plan §6.5): duty, boots, levels, positions."""
        duty = self.dev.duty
        out: dict[str, Any] = {"unexpected_boots": self.dev.unexpected_boots - self._boots0}
        if duty is not None:
            # Max rolling-window on-time per RAIL A hole (same clock as the gate).
            worst = 0.0
            for hole, spans in duty.history.items():
                if self.cfg.channel(hole).rail != "A":
                    continue
                for _t0, t1 in spans:
                    worst = max(worst, duty.used_ms(hole, t1))
            out["duty"] = {
                "max_rail_a_ms_per_min": round(worst, 1),
                "budget_a_ms": float(duty.budget_ms["A"]),
                "over_budget": [[h, round(ms, 1)] for h, ms in duty.over_budget],
                "cooldown_s": round(duty.total_cooldown_s, 2),
                "cooldowns": len(duty.cooldowns),
            }
        out["moves"] = self._moves
        out["unlevel"] = self._unlevel
        st = self.dev.stage
        out["stage_end"] = st.summary() if st is not None else None
        self.store.meta["health"] = out
        self.store.save_meta()

    def _approach(self, st: Step) -> None:
        """Reach the height from the stated side (repeats: from an offset first)."""
        if st.rep:
            off = self.s.ref_offset_steps
            away = st.height + (off if st.direction == "down" else -off)
            lim = self.dev.stage.limits if self.dev.stage else None
            if lim is not None and lim.top is not None and lim.bottom is not None:
                away = max(lim.bottom[0], min(lim.top[0] - self.dev.stage_top_margin(), away))
            self._move_to(away)
        self._move_to(st.height)

    # ---------------------------------------------------------------- readings

    def _row(self, st: Step, **kw: Any) -> dict[str, Any]:
        h = self._height()
        mm = self.plan.mm(h)
        net = kw.get("net_counts")
        net_mv = None
        if net is not None:
            cal = resolve_calibration(cfg=self.cfg, detector=str(kw.get("detector") or "ingaas"))
            mv = cal.counts_to_mv(float(net))
            net_mv = None if mv is None else round(mv, 4)
        return {
            "run_id": self.store.run_id,
            "step": st.index,
            "phase": st.phase,
            "height_hs": h,
            "height_mm": None if mm is None else round(mm, 4),
            "direction": st.direction,
            "rep": st.rep,
            "t_s": round(self.dev.now() - self._t_start, 3),
            "net_mv": net_mv,
            **kw,
        }

    def _dark_frame(self, st: Step, *, label: str = "dark") -> dict[str, float]:
        n = self.s.dark_n
        out: dict[str, float] = {}
        for det in DETECTORS:
            r = self.dev.adc_read(ADC_OF[det], n)
            out[det] = r.mean
            self._rows.append(self._row(st, hole=0, state="dark", detector=det,
                                        dark_counts=round(r.mean, 2), n=n))  # fmt: skip
        return out

    def _settle(self, st: Step) -> float:
        """Mechanical settle, then two dark reads agreeing within k sigma (ms taken)."""
        dev = self.dev
        t0 = dev.now()
        dev.sleep(self.s.settle_ms_mech / 1000.0)
        n = self.s.dark_n
        for _ in range(max(1, self.s.dark_agree_tries)):
            a = {d: dev.adc_read(ADC_OF[d], n) for d in DETECTORS}
            b = {d: dev.adc_read(ADC_OF[d], n) for d in DETECTORS}
            ok = True
            for d in DETECTORS:
                sd = max(a[d].std or 0.0, b[d].std or 0.0, 1.0)
                if abs(a[d].mean - b[d].mean) > self.s.dark_agree_sigma * sd * math.sqrt(2.0 / n):
                    ok = False
            if ok:
                break
        return (dev.now() - t0) * 1000.0

    def _sweep(self, st: Step, settle_ms: float) -> None:
        dev = self.dev
        cool0 = dev.duty.total_cooldown_s if dev.duty else 0.0
        sw = dev.sweep(self.s.optical_settle_ms, self._n)
        wait_ms = ((dev.duty.total_cooldown_s if dev.duty else 0.0) - cool0) * 1000.0
        for m in sw.records:
            for det in DETECTORS:
                lit, dark = m.lit(det), m.dark(det)
                self._rows.append(self._row(
                    st, hole=m.hole, state="lit", detector=det, dark_counts=dark, lit_counts=lit,
                    net_counts=lit - dark, duty_wait_ms=round(wait_ms, 1),
                    settle_ms=round(settle_ms, 1), n=self._n,
                ))  # fmt: skip
                sat = self.cfg.detectors[det].saturation_counts
                if self.s.abort_on_saturation and lit >= sat:
                    raise ScanAbort(f"saturation: hole {m.hole} on {det} read {lit} (limit {sat})")

    def _measure_here(self, st: Step) -> None:
        settle_ms = self._settle(st)
        self._dark_frame(st)
        self._sweep(st, settle_ms)
        self._dark_frame(st)
        if st.hum:
            self._hum(st, "coils_off")
            self._emi_pending = True  # coil EMI on the way to the next height (D2)
        self._progress(st, "measured")

    def _rate(self, sps: int) -> None:
        """Set the ADC rate and re-read INFO, so the device's timeouts follow it (a 30 s
        stream at 8 SPS must not time out on the 128 SPS default)."""
        self.dev.adc_rate(sps)
        self.dev.info(refresh=True)

    def _bursts(self, ch: int, n_bursts: int) -> tuple[list[int], list[int]]:
        """Buffered 48-sample bursts at the fastest rate, on one time axis (µs)."""
        dev = self.dev
        old = self.cfg.section.integer("adc.rate_sps")
        self._rate(860)
        t_all: list[int] = []
        v_all: list[int] = []
        try:
            for _ in range(n_bursts):
                t0 = round((dev.now() - self._t_start) * 1e6)
                s = dev.adc_stream(ch, 48, 0)
                t_all += [t0 + x.t_us for x in s]
                v_all += [x.raw for x in s]
        finally:
            self._rate(old)
        return t_all, v_all

    def _hum(self, st: Step, state: str, n_bursts: int | None = None) -> None:
        h = self._height()
        for det in DETECTORS:
            t, v = self._bursts(ADC_OF[det], n_bursts or self.s.hum_bursts)
            name = f"s{st.index:03d}_{state}_{det}"
            self.store.save_stream(name, t_us=t, raw=v, step=st.index, state=state, detector=det,
                                   height_hs=h, rate_setting=860)  # fmt: skip
            if v:
                m = statistics.fmean(v)
                self._rows.append(self._row(st, hole=0, state=state, detector=det,
                                            dark_counts=round(m, 2), n=len(v)))  # fmt: skip

    def _emi_during(self, p1: int, p2: int) -> None:
        """While the top moves (coils switching): a few bursts per input, once."""
        if self._emi_pending:
            self._emi_pending = False
            st = Step(-1, "P2", "emi", round((p1 + p2) / 2))
            for det in DETECTORS:
                t, v = self._bursts(ADC_OF[det], 4)
                self.store.save_stream(f"emi_{len(self.store.meta.get('streams', []))}_{det}",
                                       t_us=t, raw=v, state="coils_moving", detector=det,
                                       height_hs=st.height, rate_setting=860)  # fmt: skip
        else:
            self.dev.sleep(self.motion.poll_s)

    # ---------------------------------------------------------------- P1 / P4

    def _static(self, st: Step) -> None:
        """P1: noise and hum, a long dark record, coupling states, one SWEEP here."""
        dev = self.dev
        self._hum(st, "coils_off")
        old = self.cfg.section.integer("adc.rate_sps")
        self._rate(8)
        try:
            n = max(8, round(self.s.long_dark_s * 8))
            for det in DETECTORS:
                t0 = round((dev.now() - self._t_start) * 1e6)
                s = dev.adc_stream(ADC_OF[det], n, 0)
                self.store.save_stream(f"long_dark_{det}", t_us=[t0 + x.t_us for x in s],
                                       raw=[x.raw for x in s], state="dark", detector=det,
                                       height_hs=self._height(), rate_setting=8)  # fmt: skip
        finally:
            self._rate(old)
        self._coupling_states(st)
        settle_ms = self._settle(st)
        self._dark_frame(st)
        self._sweep(st, settle_ms)
        self._dark_frame(st)

    def _coupling_states(self, st: Step) -> None:
        """Select-only on every hole (MOSFET on, CE low: SR RAW forces CE low); with
        firmware 2.5.0 also CE-only per rail and wrong-rail per hole (DBG STATE)."""
        dev = self.dev
        n = self.s.dark_n
        for hole in range(1, 17):
            dev.off()
            base = {d: dev.adc_read(ADC_OF[d], n).mean for d in DETECTORS}
            dev.sr_raw(1 << (hole - 1))
            try:
                for det in DETECTORS:
                    v = dev.adc_read(ADC_OF[det], n).mean
                    b = base[det]
                    self._rows.append(self._row(
                        st, hole=hole, state="select_only", detector=det, dark_counts=round(b, 2),
                        lit_counts=round(v, 2), net_counts=round(v - b, 2), n=n,
                    ))  # fmt: skip
            finally:
                dev.off()
        if not self.capabilities.get("coupling_states"):
            return  # recorded as SKIP in P0 (firmware without DBG STATE)
        settle, n = self.s.optical_settle_ms, self._n
        for state, args in (("ce_only", (1, 2)), ("wrong_rail", range(1, 17))):
            for arg in args:
                f = dev.dbg_state(state, arg, settle, n)
                for det in DETECTORS:
                    i = ADC_OF[det]
                    dark, lit = f.as_int(f"dark{i}"), f.as_int(f"lit{i}")
                    self._rows.append(self._row(
                        st, hole=0 if state == "ce_only" else arg, state=state, detector=det,
                        dark_counts=dark, lit_counts=lit, net_counts=lit - dark, n=n,
                        rep=arg if state == "ce_only" else 0,
                    ))  # fmt: skip

    def _closing(self, st: Step) -> None:
        """P4: re-measure here (drift vs P1), then the interlocks, then everything off."""
        settle_ms = self._settle(st)
        self._dark_frame(st)
        self._sweep(st, settle_ms)
        self._dark_frame(st)
        results: dict[str, str] = {}
        dev = self.dev
        if not self.plan.static:
            # a measurement while a motor moves must be refused (no MOTOR LIGHT)
            h = self._height()
            dev.command("VS200")
            dev.command("D")
            try:
                dev.meas(8, 8, 1)
                results["light_while_moving"] = "FAIL: MEAS accepted while moving"
            except DeviceError as e:
                results["light_while_moving"] = "PASS" if e.code == 5 else f"FAIL: code {e.code}"
            finally:
                dev.command("S")
            for _ in range(20):
                if not motion.positions(dev)[2]:
                    break
                dev.sleep(0.05)
            self._move_to(h)
        else:
            results["light_while_moving"] = "SKIP: static mode (no motion)"
        dev.sr_raw(0x0003)  # two holes selected: raising CE must be refused
        sends = dev.light_sends
        try:
            dev.command("CE 1 1")
            results["single_channel"] = "FAIL: CE accepted with two holes selected"
        except DeviceError as e:
            results["single_channel"] = "PASS" if e.code == 3 else f"FAIL: code {e.code}"
        except OwnershipError as e:
            # A managed real port refuses an ambiguous mask BEFORE transmission, so
            # the firmware interlock is not exercised here (as in T10.4).
            if dev.light_sends != sends:
                raise
            results["single_channel"] = (
                f"SKIP: host refused before transmission ({e}); firmware interlock not exercised"
            )
        finally:
            dev.off()
        self.store.meta["interlocks"] = results
        self.store.save_meta()

    # ---------------------------------------------------------------- continuous

    def _continuous(self, st: Step) -> None:
        """Measure while moving (labelled sub-mode; MOTOR LIGHT 1). Holes whose duty
        budget would force a wait are skipped for that pass, so the move is watched."""
        dev = self.dev
        holes = list(range(1, 17))
        idx = [0]
        on_ms = self.s.optical_settle_ms + 2 * self.dev._mean_s(self._n) * 1000 + 10

        recorded = [False]

        def during(p1: int, p2: int) -> None:
            if not recorded[0]:  # coil interference, as the measurements below will see it
                recorded[0] = True
                for det in DETECTORS:
                    t, v = self._bursts(ADC_OF[det], 4)
                    self.store.save_stream(f"s{st.index:03d}_coils_moving_{det}", t_us=t, raw=v,
                                           state="coils_moving", detector=det,
                                           height_hs=round((p1 + p2) / 2),
                                           rate_setting=860)  # fmt: skip
                return
            for _ in range(len(holes)):
                h = holes[idx[0] % len(holes)]
                idx[0] += 1
                if dev.duty is None or dev.duty.wait_needed(h, on_ms, dev.now()) <= 0:
                    break
            else:
                dev.sleep(0.05)
                return
            m = dev.meas(h, self.s.optical_settle_ms, self._n)
            for det in DETECTORS:
                self._rows.append(self._row(st, hole=h, state="lit", detector=det,
                                            dark_counts=m.dark(det), lit_counts=m.lit(det),
                                            net_counts=m.net(det), n=self._n))  # fmt: skip

        a = self._height()
        ok, msg = motion.move_both(
            dev, self.cfg, st.height - a, light=True, during=during, settings=self.motion
        )
        if not ok:
            raise ScanAbort(f"continuous move: {msg}")

    # ---------------------------------------------------------------- fine mode

    def _extra_height(self, st: Step) -> int:
        """Points around the optimum: computed once after the down pass, then kept in
        scan.json so a resumed run uses the same heights."""
        extra = self.store.meta.get("extra_heights")
        if extra is None:
            extra = self._plan_extras()
            self.store.meta["extra_heights"] = extra
            self.store.save_meta()
        return int(extra[st.rep % len(extra)])

    def _plan_extras(self) -> list[int]:
        opt, selection = select_primary_swir_height(self.store.rows())
        # D17: one frozen target-selection drives fine placement / report / UI.
        self.store.meta["target_selection"] = selection
        self.store.meta["target_selection_id"] = selection.get("selection_id")
        (self.store.folder / "target_selection.json").write_text(
            json.dumps(selection, indent=1) + "\n", encoding="utf-8"
        )
        self.store.save_meta()
        hd = self.plan.heights_down
        step = abs(hd[1] - hd[0]) if len(hd) > 1 else 4096
        n = self.plan.extra_near_optimum
        lo = max(self.plan.bottom, opt - step)
        hi = min(self.plan.top, opt + step)
        pts = [round(lo + (hi - lo) * (i + 0.5) / n) for i in range(n)]
        return sorted(pts)  # measured on the way up

    # ---------------------------------------------------------------- progress

    def _progress(self, st: Step | None, status: str, **extra: Any) -> None:
        total = len(self.plan.steps)
        done = int(self.store.meta.get("completed_step", -1)) + 1
        frac = done / total if total else 1.0
        elapsed = self.dev.now() - self._t_start
        eta = self.plan.eta_s * (1 - frac) if frac < 1 else 0.0
        p = {
            "run_id": self.store.run_id,
            "status": status,
            "step": None if st is None else st.index,
            "of": total,
            "done": done,
            "phase": None if st is None else st.phase,
            "kind": None if st is None else st.kind,
            "label": None if st is None else st.label,
            "target_hs": None if st is None else st.height,
            "elapsed_s": round(elapsed, 1),
            "eta_s": round(eta, 1),
            **extra,
        }
        if status == "measured":
            p["last"] = [
                {
                    "hole": r["hole"],
                    "detector": r["detector"],
                    "net": r["net_counts"],
                    "height_hs": r["height_hs"],
                }
                for r in self._rows
                if r.get("state") == "lit"
            ]
        self.control.progress = p
        if self.on_progress is not None:
            with contextlib.suppress(Exception):
                self.on_progress(p)
