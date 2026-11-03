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
import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from lio import baseline as bl
from lio.config import HwConfig
from lio.device import BootTimeout, LIODevice
from lio.operator import Abort, Operator, SimOperator
from lio.results import RunRecord, Status, TestResult, Verdict
from lio.sim import FAULT_NAMES, Faults, SimulatedLIO
from lio.suite.core import REGISTRY, SuiteContext, TestDef, catalogue, run_test
from lio.suite.runner import finish, new_record
from lio.transport import SerialTransport, SimTransport, Transport, list_ports, pick_port

from . import twin

log = logging.getLogger(__name__)

LOG_LINES = 400
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
        self.board: dict[str, TestResult] = {}  # latest result per test id, this connection
        self.job: dict[str, Any] | None = None
        self.last_run: dict[str, Any] | None = None
        self.prompt: _Prompt | None = None
        self.manual: dict[str, Any] | None = None
        self.error = ""
        self._log: collections.deque[str] = collections.deque(maxlen=LOG_LINES)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.catalogue = catalogue()

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
            self.board = {}
            self.last_run = None
            self.manual = None
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
        if dev is not None:
            dev.close()  # LEDs off, motors stopped and released
            self.log("disconnected (everything off)")
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

    def flash(self, hole: int, ms: int) -> dict[str, Any]:
        """Light one hole for ``ms`` (clamped by the firmware watchdog), then off."""

        def go(dev: LIODevice) -> dict[str, Any]:
            n0 = len(dev.events)
            until = dev.ch_on(hole, ms)
            dev.drain(until / 1000.0 + 0.5)
            ended = [e.name for _, e in dev.events[n0:] if e.name in ("OFF", "WDT")]
            dev.off()
            self.log(f"flash hole {hole}: on {until} ms, ended by {ended[0] if ended else 'OFF'}")
            return {"action": "flash", "hole": hole, "on_ms": until}

        return self._manual(go)

    def all_off(self) -> None:
        """LEDs off and motors stopped; during a run, stop the run (it restores the safe state)."""
        if self.running:
            self.stop()
            return

        def go(dev: LIODevice) -> dict[str, Any]:
            dev.off()
            dev.motor_stop()
            return {"action": "off"}

        self._manual(go)
        self.log("all off: LEDs off, motors stopped")

    def clear_results(self) -> None:
        with self._lock:
            if self.running:
                raise Busy("a run is in progress")
            self.board = {}
            self.last_run = None
        self.log("results cleared")

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
                "subsystems": twin.subsystems(results, self._planned()),
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
            "poll_ms": cfg.section.integer("dashboard.poll_ms"),
            "rails": {r: {"holes": list(cfg.rail_holes(r))} for r in ("A", "B")},
            "statuses": [s.value for s in Status] + [twin.NOT_RUN],
            "baseline": str(bl.latest()) if bl.latest() is not None else None,
        }
