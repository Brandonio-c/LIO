"""The dashboard's Scan tab (plan LIO-SW-SCAN-001 §5, S6): a diagnostic sweep run from
the page, with plan preview, Start / Pause / Abort, an operator heartbeat, live
progress and a live hole x height heat-map.

The scan runs in its own thread and holds the device for its whole duration (no
manual LED or motor action meanwhile). Operator questions (chamber clear, lid
closed, ...) go to the page's prompt. The heartbeat is sent by a Web Worker in the
page (timers in a hidden tab still run there); when it stops for longer than the
timeout, the scan pauses at its next safe point (everything off) and carries on when
the beats come back. When the scan ends it is analysed, its report written, and its
result (T13.1) put on the twin and saved as results.json in the run folder, so it
appears with the other runs and survives a restart.
"""

from __future__ import annotations

import datetime as dt
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lio import scan
from lio.operator import Operator, SimOperator
from lio.results import RunRecord, overall_verdict
from lio.scan import report as scan_report
from lio.scan.analysis import analyse
from lio.scan.executor import Control
from lio.suite.checks.t13_scan import scan_result

if TYPE_CHECKING:
    from lio.dashboard.session import Session


class ScanJob:
    def __init__(self, session: Session, plan: scan.ScanPlan, *, sample_id: str,
                 heartbeat: bool, timeout_s: float, operator: Operator,
                 resume: Path | None = None) -> None:  # fmt: skip
        self.s = session
        self.resume = resume
        self.plan = plan
        self.sample_id = sample_id
        self.operator = operator
        self.control = Control(heartbeat_required=heartbeat, timeout_s=timeout_s)
        self.control.beat()
        self.progress: dict[str, Any] = {"status": "starting", "done": 0, "of": len(plan.steps)}
        self.grid: dict[str, dict[int, list[list[float]]]] = {"opt101": {}, "ingaas": {}}
        self.folder: Path | None = None
        self.result: dict[str, Any] | None = None
        self.error = ""
        self.started = time.time()
        self._lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, name="lio-scan", daemon=True)

    # ------------------------------------------------------------ thread

    def _on_progress(self, p: dict[str, Any]) -> None:
        with self._lock:
            self.progress = {k: v for k, v in p.items() if k != "last"}
            for r in p.get("last") or []:
                if r.get("net") is None:
                    continue
                row = self.grid.setdefault(r["detector"], {}).setdefault(int(r["hole"]), [])
                row.append(
                    [float(r["height_hs"]), float(r["net"]), 1.0 if p.get("phase") == "P3" else 0.0]
                )
        self.s._changed()

    def _run(self) -> None:
        s = self.s
        dev = s._device()
        if not s._dev_lock.acquire(timeout=5):
            self.error = "the device is busy"
            return
        try:
            if self.resume is not None:
                store, status = scan.resume(dev, s.cfg, self.resume, self.operator,
                                            control=self.control,
                                            on_progress=self._on_progress)  # fmt: skip
            else:
                store, status = scan.start(
                    dev, s.cfg, self.plan, s.results_root, self.operator,
                    sample_id=self.sample_id, control=self.control,
                    on_progress=self._on_progress, sim=s.sim is not None,
                )  # fmt: skip
            self.folder = store.folder
            s.log(f"scan {status}: {store.folder.name}")
            a = analyse(store.folder, s.cfg, None, s.results_root)
            scan_report.write(store.folder, s.cfg)
            res = scan_result(a, store.folder)
            self._save_record(store, res, status)
            with s._lock:
                s.board[res.id] = res
                s.provenance[res.id] = {"run_id": store.folder.name,
                                        "started": str(store.meta.get("started", ""))}  # fmt: skip
                s.last_run = {
                    "run_id": store.folder.name,
                    "verdict": {"verdict": a.verdict["verdict"], "reasons": a.verdict["reasons"]},
                    "report": f"/results/{store.folder.name}/report.html",
                    "folder": str(store.folder),
                }
            with self._lock:
                self.result = {
                    "status": status,
                    "verdict": a.verdict,
                    "health": a.health,
                    "flagged": [
                        {
                            "id": f.id,
                            "status": f.status.value,
                            "title": f.title,
                            "detail": f.detail,
                            "explanation": a.explanations.get(f.id),
                        }
                        for f in a.flagged()
                    ],
                    "report": f"/results/{store.folder.name}/report.html",
                    "run_id": store.folder.name,
                }
            s.log(f"scan verdict {a.verdict['verdict']}: report {store.folder.name}/report.html")
        except Exception as e:  # the executor has already made the rig safe
            self.error = f"{type(e).__name__}: {e}"
            s.log(f"scan error: {self.error}")
        finally:
            s._dev_lock.release()
            s._changed()

    def _save_record(self, store: scan.ScanStore, res: Any, status: str) -> None:
        s = self.s
        rec = RunRecord(
            run_id=store.folder.name,
            target=s.target,
            started=str(store.meta.get("started", "")),
            firmware=dict(s.firmware),
            config={
                "path": str(s.cfg.path),
                "sha256": s.cfg.sha256,
                "provisional": s.cfg.provisional,
            },
            metadata={
                "sample_id": self.sample_id,
                "kind": "scan",
                "mode": self.plan.mode,
                "scan_status": status,
            },
            faults=s.sim.faults.active if s.sim is not None else [],
            results=[res],
            finished=dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        th = s.cfg.thresholds
        v = overall_verdict(rec.results, max_channel_fails=th.integer("verdict.max_channel_fails"),
                            limited_holes=th.ints("verdict.limited_holes"))  # fmt: skip
        rec.verdict = {"verdict": v.verdict.value, "reasons": v.reasons, "counts": rec.counts()}
        rec.write_json(store.folder / "results.json")

    # ------------------------------------------------------------ view

    @property
    def alive(self) -> bool:
        return self.thread.is_alive()

    def view(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self.alive,
                "paused": self.control.paused,
                "pause_requested": self.control.pause_requested,
                "heartbeat": self.control.heartbeat_required,
                "timeout_s": self.control.timeout_s,
                "progress": dict(self.progress),
                "grid": {d: {str(h): list(v) for h, v in g.items()} for d, g in self.grid.items()},
                "plan": {
                    "mode": self.plan.mode,
                    "label": self.plan.label,
                    "top": self.plan.top,
                    "bottom": self.plan.bottom,
                    "heights_down": self.plan.heights_down,
                    "eta_s": self.plan.eta_s,
                },
                "sample_id": self.sample_id,
                "result": self.result,
                "error": self.error,
                "elapsed_s": round(time.time() - self.started, 1),
            }


def sim_stage_if_needed(session: Session) -> None:
    """On the simulator the stage is not tracked: track it from the current position
    (taken as the top) down the simulated travel."""
    dev = session._device()
    if session.sim is not None and dev.stage is None:
        path = Path(tempfile.mkdtemp(prefix="lio_dash_stage_")) / "stage.json"
        scan.sim_stage(dev, path, int(session.sim.travel_hs))


def make_operator(session: Session, sim_operator: bool) -> Operator:
    from lio.dashboard.session import WebOperator

    if session.sim is not None and sim_operator:
        return SimOperator(session.sim)
    return WebOperator(session)
