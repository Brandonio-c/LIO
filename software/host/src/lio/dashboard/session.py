"""The dashboard's state: one connection, one test job at a time, operator prompts.

A :class:`Session` owns the device. Tests run on a background thread (the
same :func:`lio.suite.core.run_test` as ``lio selftest``) while the web page
polls :meth:`Session.snapshot`. Operator questions from interactive and motion
tests go to the page through :class:`WebOperator` and block until answered.

The session keeps the latest result of every test across runs, so subsystems
can be tested one at a time and the twin and overall verdict build up. Each
run also writes its own report folder, exactly as ``lio selftest`` does.
"""

from __future__ import annotations

import collections
import contextlib
import datetime as dt
import itertools
import json
import logging
import math
import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from lio import baseline as bl
from lio.config import HwConfig
from lio.device import BootTimeout, DeviceError, LIODevice, Sweep
from lio.operator import Abort, Operator, SimOperator
from lio.results import RunRecord, Status, TestResult, Verdict
from lio.sim import FAULT_NAMES, Faults, SimulatedLIO
from lio.suite.core import REGISTRY, SuiteContext, TestDef, catalogue, run_test
from lio.suite.runner import finish, new_record
from lio.transport import (
    SerialTransport,
    SimTransport,
    Transport,
    TransportError,
    list_ports,
    pick_port,
)

from . import twin

log = logging.getLogger(__name__)

LOG_LINES = 400
STATE_FILE = "dashboard_state.json"  # in results_root: when results were last cleared
RESTORE_RUNS = 300  # the board is rebuilt from at most this many recent runs
KINDS = {"A": "automatic", "I": "operator", "M": "motion"}


class Busy(Exception):
    """The request needs the device, which a run is using."""


class Refused(Exception):
    """The request is not allowed in the current state (shown to the user)."""


# ------------------------------------------------------------------ operator


class WebOperator(Operator):
    """Puts each question on the page and waits for the answer."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def inform(self, message: str) -> None:
        self._s.log(f"[operator] {message}")

    def act(self, key: str, prompt: str) -> None:
        self._s.ask("act", key, prompt)

    def confirm(self, key: str, prompt: str) -> bool:
        return bool(self._s.ask("confirm", key, prompt))

    def number(self, key: str, prompt: str, unit: str) -> float | None:
        v = self._s.ask("number", key, prompt, unit)
        return None if v is None or v == "" else float(v)

    def text(self, key: str, prompt: str) -> str:
        v = self._s.ask("text", key, prompt)
        return "" if v is None else str(v)


class _Prompt:
    def __init__(self, pid: int, kind: str, key: str, text: str, unit: str) -> None:
        self.id, self.kind, self.key, self.text, self.unit = pid, kind, key, text, unit
        self.done = threading.Event()
        self.answer: Any = None
        self.aborted = False

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "key": self.key,
            "text": self.text,
            "unit": self.unit,
        }


# ------------------------------------------------------------------- session


class Session:
    def __init__(
        self,
        cfg: HwConfig,
        results_root: Path,
        *,
        transport_factory: Callable[[str], Transport] | None = None,
    ) -> None:
        self.cfg = cfg
        self.results_root = results_root
        self._transport_factory = transport_factory
        self._lock = threading.RLock()  # protects the fields below
        self._dev_lock = threading.Lock()  # one user of the device at a time
        self._version = itertools.count(1)
        self.version = next(self._version)
        self._prompt_ids = itertools.count(1)
        self.dev: LIODevice | None = None
        self.sim: SimulatedLIO | None = None
        self.target = ""
        self.firmware: dict[str, Any] = {}
        # Latest result per test id, rebuilt from the saved runs in results_root
        # (hardware and simulator kept apart) so it survives restarts.
        self.board: dict[str, TestResult] = {}
        self.provenance: dict[str, dict[str, str]] = {}  # test id -> run_id, started
        self.board_kind = "hardware"
        self.job: dict[str, Any] | None = None
        self.last_run: dict[str, Any] | None = None
        self.prompt: _Prompt | None = None
        self.manual: dict[str, Any] | None = None
        self._jog: dict[str, Any] | None = None  # continuous jog in progress (Motors tab)
        self._jog_thread: threading.Thread | None = None
        self._ring: dict[str, Any] | None = None  # LED ring in progress (LEDs tab)
        self._ring_thread: threading.Thread | None = None
        self.error = ""
        self._log: collections.deque[str] = collections.deque(maxlen=LOG_LINES)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.catalogue = catalogue()
        self._state_path = results_root / STATE_FILE
        self.restore_board("hardware")

    # ----------------------------------------------------------- helpers

    def _changed(self) -> None:
        with self._lock:
            self.version = next(self._version)

    def log(self, line: str) -> None:
        stamp = dt.datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self._log.append(f"{stamp} {line}")
        self._changed()

    @property
    def connected(self) -> bool:
        return self.dev is not None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _planned(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for t in self.catalogue:
            out.setdefault(t.module, []).append(t.id)
        return out

    # ------------------------------------------------------------ ports

    def ports(self) -> list[dict[str, Any]]:
        usb = [(int(v), int(p), str(n)) for v, p, n in self.cfg.section.raw("link.usb_ids")]
        found = list_ports(usb)
        chosen = pick_port(found)
        return [
            {
                "device": p.device,
                "label": p.label or p.description,
                "likely": p.likely_lio,
                "chosen": chosen is not None and p.device == chosen.device,
            }
            for p in found
        ]

    # ------------------------------------------------------- connection

    def connect(self, target: str, faults: str = "") -> None:
        """Open the simulator (``sim``) or a serial port; opening resets the Nano."""
        with self._lock:
            if self.running:
                raise Busy("a run is in progress")
            if self.connected:
                self.disconnect()
            self.error = ""
        sim = None
        if target == "sim":
            sim = SimulatedLIO(self.cfg, Faults.parse(faults or None))
            transport: Transport = SimTransport(sim)
        elif self._transport_factory is not None:
            transport = self._transport_factory(target)
        else:
            transport = SerialTransport(target, self.cfg.section.integer("link.baud"))
        dev = LIODevice(transport, self.cfg)
        self.log(f"connecting to {target}" + (f" (faults: {faults})" if faults else ""))
        try:
            dev.open()  # nothing is kept if there is no banner
        except BootTimeout as e:
            self.log(f"connect failed: {e}")
            raise Refused(str(e)) from e
        dev.cancellable = True
        try:
            dev.check_compatible()
        except Exception as e:
            dev.close()
            raise Refused(
                f"{e}. Flash firmware v2 first (docs/TESTING.md §7.2)."
                if target != "sim"
                else str(e)
            ) from e
        with self._lock:
            self.dev, self.sim, self.target = dev, sim, target
            self.firmware = dict(dev.info().values)
            self.manual = None
        self.restore_board(_kind(target))
        fw = self.firmware
        ident = f"{fw.get('fw', '?')} proto {fw.get('proto', '?')}, adc_ok {fw.get('adc_ok', '?')}"
        self.log(f"connected: {ident}")

    def shutdown(self, timeout_s: float = 60.0) -> None:
        """Stop any run, wait for it to restore the safe state, then close the port."""
        self.stop()
        if self._thread is not None:
            self._thread.join(timeout_s)
        if not self.running:
            self.disconnect()

    def disconnect(self) -> None:
        with self._lock:
            if self.running:
                raise Busy("stop the run first")
            dev, self.dev, self.sim = self.dev, None, None
            self.target, self.firmware = "", {}
            self._jog = None
            self._ring = None
        if dev is not None:
            dev.close()  # LEDs off, motors stopped and released
            self.log("disconnected (everything off)")
        self._changed()

    def link_lost(self, err: Exception) -> None:
        """The USB link died (unplugged, Nano reset, re-enumerated): drop the stale port.

        Nothing can be sent to the Nano any more; its own watchdogs turn the LEDs
        off and a reset releases the coils. The page shows "not connected" so the
        operator reconnects (which re-opens the port and resets the Nano).
        """
        with self._lock:
            dev, self.dev, self.sim = self.dev, None, None
            self.target, self.firmware = "", {}
            self._jog = None
            self._ring = None
            self.error = f"USB link lost: {err}. Reconnect."
        if dev is not None:
            with contextlib.suppress(Exception):
                dev.transport.close()
            log.warning("USB link lost: %s", err)
            self.log(f"USB link to the Nano lost ({err}); reconnect to continue")
        self._changed()

    def _device(self) -> LIODevice:
        if self.dev is None:
            raise Refused("not connected")
        return self.dev

    # ------------------------------------------------------------- runs

    def select(self, modules: Iterable[str], *, interactive: bool, allow_motion: bool) -> list[str]:
        """Test ids for modules (``T05``), subsystem keys (``channels``) or test ids."""
        keys = {s.key: s.module for s in twin.SUBSYSTEMS}
        wanted = [keys.get(m.strip().lower(), m.strip().upper()) for m in modules if m.strip()]
        kinds = {"A"} | ({"I"} if interactive else set()) | ({"M"} if allow_motion else set())
        return [
            t.id
            for t in self.catalogue
            if t.kind in kinds and (not wanted or t.module in wanted or t.id in wanted)
        ]

    def start(
        self,
        modules: list[str],
        *,
        interactive: bool = False,
        allow_motion: bool = False,
        motion_confirmed: bool = False,
        sim_operator: bool = True,
        metadata: dict[str, str] | None = None,
        compare_baseline: bool = False,
        save_baseline: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            dev = self._device()
            if self.running:
                raise Busy("a run is already in progress")
            if self._jog is not None:
                raise Busy("the motors are running continuously: stop them first")
            if self._ring is not None:
                raise Busy("the LED ring is running: stop it first")
            if allow_motion and not motion_confirmed:
                raise Refused("motion tests need confirmation that someone is at the bench")
            ids = self.select(modules, interactive=interactive, allow_motion=allow_motion)
            if not ids:
                raise Refused("no tests match that selection")
            base = None
            if compare_baseline:
                path = bl.latest()
                if path is None:
                    raise Refused("no saved baseline in software/config yet")
                base = bl.load(path)
                if "T11.1" not in ids:
                    ids.append("T11.1")
            operator: Operator | None = None
            if self.sim is not None and sim_operator:
                operator = SimOperator(self.sim)
            elif interactive or allow_motion:
                operator = WebOperator(self)
            ctx = SuiteContext(
                dev,
                self.cfg,
                self.target,
                self.sim,
                interactive=operator is not None and interactive,
                allow_motion=allow_motion,
                operator=operator,
                baseline=base,
            )
            self._stop.clear()
            dev.clear_cancel()
            self.job = {
                "ids": ids,
                "done": [],
                "current": None,
                "started": time.time(),
                "modules": modules,
                "stopping": False,
            }
            self._thread = threading.Thread(
                target=self._run,
                args=(ctx, ids, metadata or {}, save_baseline),
                name="lio-dashboard-run",
                daemon=True,
            )
            self._thread.start()
        self._changed()
        return {"tests": ids}

    def stop(self) -> None:
        """Stop the run: the current test stops at its next command or wait."""
        with self._lock:
            if not self.running or self.job is None:
                return
            self.job["stopping"] = True
            self._stop.set()
            if self.dev is not None:
                self.dev.request_cancel()
            if self.prompt is not None:
                self.prompt.aborted = True
                self.prompt.done.set()
        self.log("stop requested: finishing safely")

    def _run(self, ctx: SuiteContext, ids: list[str], meta: dict[str, str], save: bool) -> None:
        from lio.report import write_run

        with self._dev_lock:
            record: RunRecord | None = None
            try:
                record = new_record(ctx, {k: v for k, v in meta.items() if v})
                self.log(f"run {record.run_id}: {len(ids)} tests on {ctx.target}")
                for tid in ids:
                    if self._stop.is_set():
                        break
                    t: TestDef = REGISTRY[tid]
                    with self._lock:
                        assert self.job is not None
                        self.job["current"] = {
                            "id": tid,
                            "name": t.name,
                            "kind": t.kind,
                            "t0": time.time(),
                        }
                    self._changed()
                    r = run_test(ctx, t)
                    record.results.append(r)
                    with self._lock:
                        self.board[tid] = r
                        self.provenance[tid] = {"run_id": record.run_id, "started": record.started}
                        assert self.job is not None
                        self.job["done"].append(tid)
                        self.job["current"] = None
                    note = f" ({r.message})" if r.message else ""
                    self.log(f"{tid} {r.status.value:5} {t.name}{note}")
                finish(record, ctx)
                # run ids have one-second resolution: never overwrite an earlier report
                base, n = record.run_id, 2
                while (self.results_root / record.run_id).exists():
                    record.run_id = f"{base}-{n}"
                    n += 1
                folder = self.results_root / record.run_id
                with self._lock:
                    for r in record.results:
                        if r.id in self.provenance:
                            self.provenance[r.id]["run_id"] = record.run_id
                out = write_run(record, folder, cfg=self.cfg, meas_log=ctx.meas_log)
                saved = None
                if save:
                    if record.verdict["verdict"] == Verdict.NOT_FUNCTIONAL.value:
                        self.log("baseline not saved: the run is NOT FUNCTIONAL")
                    elif self._stop.is_set():
                        self.log("baseline not saved: the run was stopped")
                    else:
                        saved = str(bl.save(record))
                        self.log(f"baseline saved: {saved}")
                with self._lock:
                    self.last_run = {
                        "run_id": record.run_id,
                        "verdict": record.verdict,
                        "report": f"/results/{record.run_id}/report.html",
                        "folder": str(out["html"].parent),
                        "baseline": saved,
                        "stopped": self._stop.is_set(),
                    }
                self.log(f"run {record.run_id}: {record.verdict['verdict']}; report {out['html']}")
            except Exception as e:  # keep the dashboard alive; report the cause
                log.exception("run failed")
                with self._lock:
                    self.error = f"run failed: {type(e).__name__}: {e}"
                self.log(self.error)
                with contextlib.suppress(Exception):
                    ctx.restore()
            finally:
                with self._lock:
                    self.job = None
                    self.prompt = None
                self._changed()

    # ---------------------------------------------------------- prompts

    def ask(self, kind: str, key: str, text: str, unit: str = "") -> Any:
        """Called by the run thread; blocks until the page answers. Abort raises."""
        p = _Prompt(next(self._prompt_ids), kind, key, text, unit)
        with self._lock:
            if self._stop.is_set():
                raise Abort("stopped by the operator")
            self.prompt = p
        self._changed()
        self.log(f"[operator] {text}")
        p.done.wait()
        with self._lock:
            self.prompt = None
        self._changed()
        if p.aborted:
            raise Abort("aborted by the operator")
        return p.answer

    def answer(self, prompt_id: int, value: Any, abort: bool = False) -> None:
        with self._lock:
            p = self.prompt
            if p is None or p.id != prompt_id:
                raise Refused("that question is no longer open")
            p.answer, p.aborted = value, abort
        self.log(f"[operator] answered {'abort' if abort else value!r}")
        p.done.set()

    # ----------------------------------------------------- manual tools

    def _manual(self, fn: Callable[[LIODevice], dict[str, Any]]) -> dict[str, Any]:
        dev = self._device()
        if self._ring is not None:
            raise Busy("the LED ring is running: stop it first")
        if self.running or not self._dev_lock.acquire(blocking=False):
            raise Busy("a run is using the device")
        try:
            out = fn(dev)
        finally:
            self._dev_lock.release()
        with self._lock:
            self.manual = {**out, "at": time.time()}
        self._changed()
        return out

    def measure(self, hole: int) -> dict[str, Any]:
        def go(dev: LIODevice) -> dict[str, Any]:
            dev.keep_awake()
            n = self.cfg.thresholds.integer("channel.meas_n")
            m = dev.meas(hole, n=n)
            nets = {d: m.net(d) for d in twin.DETECTORS}
            self.log(f"measure hole {hole}: " + ", ".join(f"{d} {v:+d}" for d, v in nets.items()))
            return {
                "action": "measure",
                "hole": hole,
                "net": nets,
                "dark": {d: m.dark(d) for d in twin.DETECTORS},
                "lit": {d: m.lit(d) for d in twin.DETECTORS},
                "lsb_mv": self.cfg.lsb_mv,
            }

        return self._manual(go)

    def sample_sweeps(self, repeats: int) -> tuple[list[Sweep], dict[str, Any]]:
        """``repeats`` full sweeps for a food sample (Database tab), with their context.

        The same rules as the manual tools: refused while a run or the LED ring
        uses the device. SWEEP lights one hole at a time and leaves all dark.
        """
        dev = self._device()
        if self._ring is not None:
            raise Busy("the LED ring is running: stop it first")
        if self.running or not self._dev_lock.acquire(blocking=False):
            raise Busy("a run is using the device")
        settle = self.cfg.limits["settle_ms"]
        n = self.cfg.thresholds.integer("channel.meas_n")
        t0 = time.monotonic()
        try:
            dev.keep_awake()
            sweeps = [dev.sweep(settle, n) for _ in range(repeats)]
        finally:
            self._dev_lock.release()
        meta = {
            "target": self.target,
            "kind": _kind(self.target),
            "firmware": str(self.firmware.get("fw", "")),
            "settle_ms": settle,
            "n": n,
            "duration_s": time.monotonic() - t0,
        }
        self.log(f"food scan: {repeats} sweep(s) on {self.target}")
        self._changed()
        return sweeps, meta

    def flash(self, hole: int, ms: int) -> dict[str, Any]:
        """Light one hole for ``ms`` (clamped by the firmware watchdog), then off."""

        def go(dev: LIODevice) -> dict[str, Any]:
            dev.keep_awake()
            n0 = len(dev.events)
            until = dev.ch_on(hole, ms)
            dev.drain(until / 1000.0 + 0.5)
            ended = [e.name for _, e in dev.events[n0:] if e.name in ("OFF", "WDT")]
            dev.off()
            self.log(f"flash hole {hole}: on {until} ms, ended by {ended[0] if ended else 'OFF'}")
            return {"action": "flash", "hole": hole, "on_ms": until}

        return self._manual(go)

    def wake(self) -> dict[str, Any]:
        """Hold the motor coils (no steps) to wake power bank A, then look for the ADC."""

        if not self.cfg.section.raw("power.wake"):
            raise Refused("power wake is disabled (power.wake: false)")

        def go(dev: LIODevice) -> dict[str, Any]:
            ms = self.cfg.section.integer("dashboard.wake_button_ms")
            dev.power_wake(ms)
            dev.sleep(self.cfg.section.num("power.settle_ms") / 1000.0)
            adc_ok = dev.info(refresh=True).as_int("adc_ok") == 1
            self.log(
                f"wake bank A: coils held {ms} ms; ADC "
                + ("found" if adc_ok else "still not answering")
            )
            return {"action": "wake", "wake_ms": ms, "adc_ok": adc_ok}

        return self._manual(go)

    def all_off(self) -> None:
        """LEDs off and motors stopped; during a run, stop the run (it restores the safe state)."""
        if self.running:
            self.stop()
            return

        with self._lock:
            self._jog = None
        if self._ring is not None:
            self.ring_stop()

        def go(dev: LIODevice) -> dict[str, Any]:
            dev.off()
            dev.motor_stop()
            return {"action": "off"}

        self._motor_call(go, wait_s=2.0)
        self.log("all off: LEDs off, motors stopped")

    # ----------------------------------------------------- motors tab

    def _motor_call(
        self, fn: Callable[[LIODevice], dict[str, Any]], wait_s: float = 0.0
    ) -> dict[str, Any]:
        """Run ``fn`` on the device outside a test run (like the manual tools)."""
        dev = self._device()
        if self.running:
            raise Busy("a run is using the device")
        got = (
            self._dev_lock.acquire(timeout=wait_s)
            if wait_s > 0
            else self._dev_lock.acquire(blocking=False)
        )
        if not got:
            raise Busy("the device is busy")
        try:
            return fn(dev)
        except DeviceError as e:
            raise Refused(f"the Nano refused: {e.msg}") from e
        finally:
            self._dev_lock.release()

    def motor_status(self) -> dict[str, Any]:
        """Position, run state and arming of both motors (polled by the Motors tab)."""
        if self.dev is None:
            return {"connected": False}

        def go(dev: LIODevice) -> dict[str, Any]:
            st = dev.status()
            return {
                "connected": True,
                "armed": st.as_int("armed") == 1,
                "armed_ms": st.as_int("armed_ms"),
                "lit": st.as_int("ch"),
                "motors": {
                    str(m): {"state": st.as_str(f"motor{m}"), "pos": st.as_int(f"pos{m}")}
                    for m in (1, 2)
                },
            }

        with self._lock:
            jog = self._jog
            if jog is not None:
                jog["heartbeat"] = time.monotonic()
        jog_info = {k: jog[k] for k in ("motor", "direction", "speed")} if jog is not None else None
        try:
            out = {**self._motor_call(go), "jog": jog_info}
        except Busy:
            last = getattr(self, "_motor_last", None)
            return {**last, "stale": True} if last else {"connected": True, "busy": True}
        self._motor_last = out
        return out

    # Continuous jog: the legacy jog commands (docs/PROTOCOL.md §7) each stop after
    # jog_max half-steps, so a jog is re-sent while the page keeps it latched. If the
    # page goes quiet for jog_deadman_s the motors are stopped.

    def jog_start(self, motor: str, direction: str, speed: int) -> dict[str, Any]:
        """Run one motor, or both, up or down until ``jog_stop`` (or the dead-man)."""
        lim = self.cfg.limits
        if motor not in ("1", "2", "both"):
            raise Refused("motor must be 1, 2 or both")
        if direction not in ("up", "down"):
            raise Refused("direction must be up or down")
        if not lim["jog_v_min"] <= speed <= lim["jog_v_max"]:
            raise Refused(f"speed must be {lim['jog_v_min']}-{lim['jog_v_max']} half-steps/s")
        positive = str(self.cfg.section.raw("motors.positive"))
        sign = 1 if direction == positive else -1  # firmware U/LU/RU step in +
        if self._ring is not None:
            raise Busy("the LED ring is running: stop it first")
        cmd = JOG_CMDS[(motor, sign)]
        targets = [1, 2] if motor == "both" else [int(motor)]

        def go(dev: LIODevice) -> dict[str, Any]:
            dev.command(f"{'VS' if motor == 'both' else 'VA'}{speed}")
            dev.command(cmd)
            st = dev.status()
            now = time.monotonic()
            with self._lock:
                self._jog = {
                    "motor": motor, "direction": direction, "speed": speed, "cmd": cmd,
                    "targets": targets, "pos0": {m: st.as_int(f"pos{m}") for m in targets},
                    "heartbeat": now, "started": now,
                }  # fmt: skip
            who = {"both": "both", "1": "left", "2": "right"}[motor]
            self.log(f"motor {who} running {direction} at {speed} half-steps/s (continuous)")
            return {"jog": motor, "direction": direction, "speed": speed}

        out = self._motor_call(go, wait_s=1.0)
        if self._jog_thread is None or not self._jog_thread.is_alive():
            self._jog_thread = threading.Thread(target=self._jog_loop, name="lio-jog", daemon=True)
            self._jog_thread.start()
        return out

    def jog_stop(self, reason: str = "stop pressed") -> dict[str, Any]:
        with self._lock:
            was, self._jog = self._jog, None
        if self.dev is None:
            return {"stopped": False}

        def go(dev: LIODevice) -> dict[str, Any]:
            dev.command("S")  # stop both at once, coils released
            return {"stopped": True}

        out = self._motor_call(go, wait_s=2.0)
        if was is not None:
            self.log(f"motors stopped ({reason})")
        return out

    def _jog_loop(self) -> None:
        sec = self.cfg.section
        check_s = sec.integer("dashboard.jog_check_ms") / 1000.0
        refresh = sec.integer("dashboard.jog_refresh_steps")
        deadman = sec.num("dashboard.jog_deadman_s")
        while True:
            time.sleep(check_s)
            with self._lock:
                jog = self._jog
            if jog is None or self.dev is None:
                return
            if deadman > 0 and time.monotonic() - jog["heartbeat"] > deadman:
                with contextlib.suppress(Exception):
                    self.jog_stop("the page stopped checking in")
                return
            if not self._dev_lock.acquire(timeout=1.0):
                continue
            try:
                st = self.dev.status()
                states = {m: st.as_str(f"motor{m}") for m in jog["targets"]}
                pos = {m: st.as_int(f"pos{m}") for m in jog["targets"]}
                if all(v == "idle" for v in states.values()):
                    with self._lock:
                        if self._jog is jog:
                            self._jog = None
                    self.log("continuous move ended by the Nano (bound, failsafe or stop)")
                    return
                if max(abs(pos[m] - jog["pos0"][m]) for m in jog["targets"]) >= refresh:
                    self.dev.command(jog["cmd"])  # a fresh bound of jog_max half-steps
                    jog["pos0"] = pos
            except Exception as e:  # the device went away or refused: stop trying
                log.warning("continuous jog: %s", e)
                with self._lock:
                    if self._jog is jog:
                        self._jog = None
                return
            finally:
                self._dev_lock.release()

    # ------------------------------------------------------- LEDs tab: ring

    @property
    def _ring_budget(self) -> bool:
        return bool(self.cfg.section.raw("dashboard.ring_duty_budget"))

    def ring_holes(self, include_unfitted: bool) -> list[int]:
        return [c.hole for c in self.cfg.channels if c.fitted or include_unfitted]

    def ring_min_step_ms(self, on_ms: int, holes: list[int]) -> int:
        """Shortest step that keeps every hole in the ring within its duty budget.

        With ``dashboard.ring_duty_budget: false`` only the dark gap is kept.
        """
        sec = self.cfg.section
        gap = on_ms + sec.integer("dashboard.ring_gap_ms")
        if not self._ring_budget:
            return gap
        window_ms = sec.num("duty.window_s") * 1000.0
        rails = {self.cfg.channel(h).rail for h in holes}
        budget = min(sec.num(f"duty.max_on_ms_per_channel.{r}") for r in rails)
        by_duty = on_ms * window_ms / (budget * len(holes))
        return math.ceil(max(by_duty, gap))

    def ring_start(
        self,
        on_ms: int,
        step_ms: int,
        include_unfitted: bool,
        holes: list[int] | None = None,
    ) -> dict[str, Any]:
        """Light the holes one at a time around the ring until ``ring_stop``.

        ``holes`` limits the ring to those holes; one hole "holds" it: that LED is
        pulsed again and again (as often as its duty budget allows, if enabled). While running, a
        new call changes the holes and timing in place. The step is raised to the
        duty-safe minimum when needed (the result says what was used).
        """
        sec = self.cfg.section
        lo, hi = sec.integer("dashboard.ring_on_ms_min"), sec.integer("dashboard.ring_on_ms_max")
        if not lo <= on_ms <= hi:
            raise Refused(f"on-time must be {lo}-{hi} ms")
        if holes:
            bad = [h for h in holes if not 1 <= h <= 16]
            if bad:
                raise Refused(f"holes must be 1-16, got {bad}")
            holes = list(dict.fromkeys(holes))
        else:
            holes = self.ring_holes(include_unfitted)
        min_step = self.ring_min_step_ms(on_ms, holes)
        step = max(step_ms, min_step)
        self._device()
        if self.running:
            raise Busy("a run is using the device")
        if self._jog is not None:
            raise Busy("the motors are running continuously: stop them first")
        with self._lock:
            if self._ring is not None:
                self._ring.update(on_ms=on_ms, step_ms=step, min_step_ms=min_step, holes=holes)
                self.log(f"LED ring: {on_ms} ms on, one hole every {step} ms, holes {holes}")
                return self._ring_view()
            self._ring = {
                "on_ms": on_ms, "step_ms": step, "min_step_ms": min_step, "holes": holes,
                "hole": 0, "state": "starting", "cooling_s": 0.0, "laps": 0,
            }  # fmt: skip
            ring = self._ring
        self.log(f"LED ring started: {on_ms} ms on, one hole every {step} ms, holes {holes}")
        self._ring_thread = threading.Thread(
            target=self._ring_loop, args=(ring,), name="lio-ring", daemon=True
        )
        self._ring_thread.start()
        return self.ring_status()

    def ring_stop(self) -> dict[str, Any]:
        with self._lock:
            was, self._ring = self._ring, None
        if was is not None and self._ring_thread is not None:
            self._ring_thread.join(timeout=5.0)
        if self.dev is not None and self._dev_lock.acquire(timeout=2.0):
            try:
                self.dev.off()
            except TransportError as e:
                self.link_lost(e)
            finally:
                self._dev_lock.release()
        if was is not None:
            self.log(f"LED ring stopped after {was['laps']} laps (everything off)")
        return {"stopped": was is not None}

    def _ring_view(self) -> dict[str, Any]:
        r = self._ring
        if r is None:
            return {"active": False}
        keys = ("on_ms", "step_ms", "min_step_ms", "holes", "hole", "state", "cooling_s", "laps")
        return {"active": True, **{k: r[k] for k in keys}}

    def ring_status(self) -> dict[str, Any]:
        with self._lock:
            return self._ring_view()

    def _ring_wait(self, dev: LIODevice, seconds: float) -> None:
        """Wait on the device's clock (real time on hardware, virtual on the simulator)."""
        with self._dev_lock:
            dev.sleep(seconds)

    def _ring_loop(self, ring: dict[str, Any]) -> None:
        i = 0
        try:
            while True:
                with self._lock:
                    if self._ring is not ring:
                        return
                    holes, on_ms, step_ms = ring["holes"], ring["on_ms"], ring["step_ms"]
                hole = holes[i % len(holes)]
                dev = self.dev
                if dev is None:
                    return
                t0 = dev.now()
                # Cool down here, in short sleeps, so Stop is never held up.
                while self._ring_budget and dev.duty is not None:
                    wait = dev.duty.wait_needed(hole, on_ms, dev.now())
                    if wait <= 0:
                        break
                    with self._lock:
                        if self._ring is not ring:
                            return
                        ring.update(state="cooling", cooling_s=round(wait, 1), hole=hole)
                    self._ring_wait(dev, min(wait, 0.2))
                with self._dev_lock:
                    with self._lock:
                        if self._ring is not ring:
                            return
                    # firmware turns it off after on_ms (and at its watchdog limit)
                    dev.ch_on(hole, on_ms, budget=self._ring_budget)
                with self._lock:
                    ring.update(state="lit", cooling_s=0.0, hole=hole)
                    if (i + 1) % len(holes) == 0:
                        ring["laps"] += 1
                i += 1
                end = t0 + step_ms / 1000.0
                while (left := end - dev.now()) > 0:
                    with self._lock:
                        if self._ring is not ring:
                            return
                    self._ring_wait(dev, min(0.02, left))
        except TransportError as e:
            self.link_lost(e)
        except Exception as e:  # refused by the firmware: stop and say why
            log.warning("LED ring: %s", e)
            self.log(f"LED ring stopped: {e}")
            with self._lock:
                if self._ring is ring:
                    self._ring = None
            if self.dev is not None and self._dev_lock.acquire(timeout=2.0):
                try:
                    with contextlib.suppress(Exception):
                        self.dev.off()
                finally:
                    self._dev_lock.release()

    def motor_arm(self) -> dict[str, Any]:
        def go(dev: LIODevice) -> dict[str, Any]:
            ms = dev.motor_arm().as_int("armed_ms")
            self.log(f"motors armed for {ms / 1000:g} s")
            return {"armed_ms": ms}

        return self._motor_call(go, wait_s=1.0)

    def motor_move(self, motor: str, direction: str, steps: int, rpm: int) -> dict[str, Any]:
        """Move one motor, or both together, by ``steps`` half-steps up or down."""
        lim = self.cfg.limits
        targets = {"1": [1], "2": [2], "both": [1, 2]}.get(motor)
        if targets is None:
            raise Refused("motor must be 1, 2 or both")
        if direction not in ("up", "down"):
            raise Refused("direction must be up or down")
        if not 1 <= steps <= lim["step_max"]:
            raise Refused(f"steps must be 1-{lim['step_max']}")
        if not 1 <= rpm <= lim["rpm_max"]:
            raise Refused(f"rpm must be 1-{lim['rpm_max']}")
        positive = str(self.cfg.section.raw("motors.positive"))
        sign = 1 if (direction == positive) else -1

        def go(dev: LIODevice) -> dict[str, Any]:
            started: list[int] = []
            try:
                for m in targets:
                    dev.motor_step(m, sign * steps, rpm)
                    started.append(m)
            except DeviceError:
                if started:
                    dev.motor_stop()  # never leave one side of the chamber moving alone
                raise
            names = {1: "left", 2: "right"}
            who = "both" if len(targets) == 2 else names[targets[0]]
            self.log(f"motor {who} {direction} {steps} half-steps at {rpm} rpm")
            return {"motor": motor, "direction": direction, "steps": steps, "rpm": rpm}

        return self._motor_call(go, wait_s=1.0)

    def motor_stop(self) -> dict[str, Any]:
        """Stop both motors and release the coils; during a run, stop the run."""
        if self.running:
            self.stop()
            return {"stopped": "run"}

        with self._lock:
            self._jog = None

        def go(dev: LIODevice) -> dict[str, Any]:
            f = dev.motor_stop()
            self.log(f"motors stopped at pos1={f.as_int('pos1')} pos2={f.as_int('pos2')}")
            return {"stopped": "motors"}

        return self._motor_call(go, wait_s=2.0)

    def motor_release(self) -> dict[str, Any]:
        def go(dev: LIODevice) -> dict[str, Any]:
            dev.motor_release("ALL")
            self.log("motor coils released")
            return {"released": True}

        return self._motor_call(go, wait_s=1.0)

    def clear_results(self) -> None:
        """Start the board afresh; earlier runs stay on disk but are no longer counted."""
        with self._lock:
            if self.running:
                raise Busy("a run is in progress")
            state = self._read_state()
            state.setdefault("cleared", {})[self.board_kind] = _now_iso()
            self._write_state(state)
            self.board, self.provenance = {}, {}
            self.last_run = None
        self.log(
            f"results cleared ({self.board_kind}); earlier reports stay in {self.results_root}"
        )

    # ------------------------------------------------------ persistence

    def _read_state(self) -> dict[str, Any]:
        try:
            data = json.loads(self._state_path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_state(self, state: dict[str, Any]) -> None:
        self.results_root.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(state, indent=2) + "\n")

    def restore_board(self, kind: str) -> None:
        """Rebuild the board from saved runs of this kind (``hardware`` or ``sim``).

        Runs are applied oldest first, so each test shows its latest result.
        Runs from before the last Clear results are ignored.
        """
        cleared = _parse_iso(self._read_state().get("cleared", {}).get(kind))
        board: dict[str, TestResult] = {}
        prov: dict[str, dict[str, str]] = {}
        last: RunRecord | None = None
        runs = sorted(self.results_root.glob("*/results.json"))[-RESTORE_RUNS:]
        for f in runs if self.results_root.is_dir() else []:
            try:
                record = RunRecord.load(f)
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue  # not a run record (e.g. another tool's results.json)
            if _kind(record.target) != kind:
                continue
            started = _parse_iso(record.started)
            if cleared is not None and (started is None or started <= cleared):
                continue
            for r in record.results:
                board[r.id] = r
                prov[r.id] = {"run_id": f.parent.name, "started": record.started}
            last = record
        with self._lock:
            self.board_kind, self.board, self.provenance = kind, board, prov
            self.last_run = (
                {
                    "run_id": last.run_id,
                    "verdict": last.verdict,
                    "report": f"/results/{last.run_id}/report.html",
                    "folder": str(self.results_root / last.run_id),
                }
                if last is not None
                else None
            )
        if board:
            n_runs = len({p["run_id"] for p in prov.values()})
            self.log(f"restored {len(board)} {kind} test results from {n_runs} earlier runs")
        self._changed()

    # -------------------------------------------------------- past runs

    def past_runs(self, limit: int = 30) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self.results_root.is_dir():
            return out
        for f in sorted(self.results_root.glob("*/results.json"), reverse=True)[:limit]:
            try:
                d = json.loads(f.read_text())
            except (OSError, ValueError):
                continue
            out.append(
                {
                    "run_id": d.get("run_id", f.parent.name),
                    "target": d.get("target", ""),
                    "verdict": (d.get("verdict") or {}).get("verdict", ""),
                    "tests": len(d.get("results", [])),
                    "sample_id": (d.get("metadata") or {}).get("sample_id", ""),
                    "report": f"/results/{f.parent.name}/report.html",
                }
            )
        return out

    def load_run(self, run_id: str) -> None:
        """Show an earlier run's results on the twin (they replace the current board)."""
        path = self.results_root / run_id / "results.json"
        if "/" in run_id or ".." in run_id or not path.is_file():
            raise Refused(f"no run {run_id!r}")
        record = RunRecord.load(path)
        with self._lock:
            if self.running:
                raise Busy("a run is in progress")
            self.board = {r.id: r for r in record.results}
            self.provenance = {
                r.id: {"run_id": run_id, "started": record.started} for r in record.results
            }
            self.last_run = {
                "run_id": record.run_id,
                "verdict": record.verdict,
                "report": f"/results/{run_id}/report.html",
                "folder": str(path.parent),
                "loaded": True,
            }
        self.log(f"showing earlier run {run_id} ({record.target})")

    # --------------------------------------------------------- snapshot

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            order = {t.id: i for i, t in enumerate(self.catalogue)}
            results = sorted(self.board.values(), key=lambda r: order.get(r.id, 999))
            job = None
            if self.job is not None:
                job = {
                    **{k: v for k, v in self.job.items() if k != "started"},
                    "elapsed_s": round(time.time() - self.job["started"], 1),
                }
                if job["current"] is not None:
                    job["current"] = {
                        **job["current"],
                        "elapsed_s": round(time.time() - job["current"]["t0"], 1),
                    }
            return {
                "version": self.version,
                "connected": self.connected,
                "target": self.target,
                "is_sim": self.sim is not None,
                "faults": self.sim.faults.active if self.sim is not None else [],
                "firmware": self.firmware,
                "running": self.running,
                "job": job,
                "prompt": self.prompt.public() if self.prompt is not None else None,
                "last_run": self.last_run,
                "manual": self.manual,
                "error": self.error,
                "log": list(self._log)[-120:],
                "parts": twin.parts(results, self.cfg),
                "subsystems": twin.subsystems(results, self._planned(), self.provenance),
                "board": {
                    "kind": self.board_kind,
                    "runs": len({p["run_id"] for p in self.provenance.values()}),
                    "since": min((p["started"] for p in self.provenance.values()), default=""),
                    "cleared": self._read_state().get("cleared", {}).get(self.board_kind, ""),
                },
                "overall": twin.overall(results, self.cfg, len(self.catalogue)),
                "provisional": self.cfg.provisional,
            }

    def static_info(self) -> dict[str, Any]:
        """What does not change while the dashboard runs: the catalogue and the hardware."""
        cfg = self.cfg
        return {
            "catalogue": [
                {"id": t.id, "name": t.name, "kind": t.kind, "module": t.module}
                for t in self.catalogue
            ],
            "kinds": KINDS,
            "subsystems": [
                {"key": s.key, "module": s.module, "name": s.name, "what": s.what}
                for s in twin.SUBSYSTEMS
            ],
            "faults": list(FAULT_NAMES),
            "flash_ms": cfg.section.integer("dashboard.flash_ms"),
            "wake": bool(cfg.section.raw("power.wake")),
            "poll_ms": cfg.section.integer("dashboard.poll_ms"),
            "rails": {r: {"holes": list(cfg.rail_holes(r))} for r in ("A", "B")},
            "statuses": [s.value for s in Status] + [twin.NOT_RUN],
            "baseline": str(bl.latest()) if bl.latest() is not None else None,
            "ring": {
                "on_ms": cfg.section.integer("dashboard.ring_on_ms"),
                "on_ms_min": cfg.section.integer("dashboard.ring_on_ms_min"),
                "on_ms_max": cfg.section.integer("dashboard.ring_on_ms_max"),
                "duty_budget": bool(cfg.section.raw("dashboard.ring_duty_budget")),
                "visible_max_nm": cfg.thresholds.num("interactive.visible_max_nm"),
                "camera_max_nm": cfg.thresholds.num("interactive.camera_max_nm"),
                "channels": [
                    {
                        "hole": c.hole,
                        "label": c.label,
                        "nm": c.wavelength_nm,
                        "rail": c.rail,
                        "fitted": c.fitted,
                    }
                    for c in cfg.channels
                ],
            },
            "motors": {
                "names": {str(m): str(cfg.section.raw(f"motors.{m}.name")) for m in (1, 2)},
                "step_max": cfg.limits["step_max"],
                "rpm_max": cfg.limits["rpm_max"],
                "rpm_default": cfg.limits["rpm_default"],
                "half_steps_per_rev": cfg.limits["half_steps_per_rev"],
                "arm_ms": cfg.limits["arm_ms"],
                "jog_v_min": cfg.limits["jog_v_min"],
                "jog_v_max": cfg.limits["jog_v_max"],
                "jog_vs_default": cfg.limits["jog_vs_default"],
                "jog_va_default": cfg.limits["jog_va_default"],
            },
        }


# Legacy jog commands by (motor, step sign); the firmware's U/LU/RU step in +.
JOG_CMDS = {
    ("both", 1): "U", ("both", -1): "D", ("1", 1): "LU", ("1", -1): "LD",
    ("2", 1): "RU", ("2", -1): "RD",
}  # fmt: skip


def _kind(target: str) -> str:
    return "sim" if target == "sim" else "hardware"


def _now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_iso(value: object) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None
