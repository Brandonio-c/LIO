"""Targeted stationary protocol runs from the dashboard (M6).

Reuses ScanJob Control patterns for pause/abort/heartbeat. Offline plan preview
stays on ``plan_protocol`` (no device). Emission still requires ``allow_light``.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lio.scan.acquisition import ProtocolPlan, resume_protocol, run_protocol
from lio.scan.executor import Control

if TYPE_CHECKING:
    from lio.dashboard.session import Session


class ProtocolJob:
    def __init__(
        self,
        session: Session,
        plan: ProtocolPlan,
        *,
        sample_id: str,
        allow_light: bool,
        heartbeat: bool,
        timeout_s: float,
        operator_checkpoint_flag: bool,
        resume: Path | None = None,
    ) -> None:
        self.s = session
        self.plan = plan
        self.sample_id = sample_id
        self.allow_light = allow_light
        self.operator_checkpoint_flag = operator_checkpoint_flag
        self.resume = resume
        self.control = Control(heartbeat_required=heartbeat, timeout_s=timeout_s)
        self.control.beat()
        self.progress: dict[str, Any] = {
            "status": "starting",
            "done": 0,
            "of": len(plan.steps),
            "kind": "protocol",
        }
        self.folder: Path | None = None
        self.result: dict[str, Any] | None = None
        self.error = ""
        self.started = time.time()
        self._lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, name="lio-protocol", daemon=True)

    @property
    def alive(self) -> bool:
        return self.thread.is_alive()

    def view(self) -> dict[str, Any]:
        with self._lock:
            return {
                "alive": self.alive,
                "running": self.alive,
                "progress": dict(self.progress),
                "folder": None if self.folder is None else str(self.folder),
                "result": self.result,
                "error": self.error,
                "pause_requested": self.control.pause_requested,
                "paused": self.control.paused,
                "heartbeat": self.control.heartbeat_required,
                "timeout_s": self.control.timeout_s,
                "kind": "protocol",
                "protocol_id": self.plan.protocol.id,
                "n_steps": len(self.plan.steps),
                "predicted_duration_s": self.plan.predicted_duration_s,
                "unresolved": list(self.plan.unresolved),
            }

    def _run(self) -> None:
        s = self.s
        if not s._dev_lock.acquire(timeout=5):
            self.error = "the device is busy"
            return
        try:
            cancel_check = lambda: bool(self.control.abort_reason)  # noqa: E731

            def _confirm(msg: str) -> bool:
                return bool(self.operator_checkpoint_flag)

            if self.resume is not None:
                result = resume_protocol(
                    self.resume,
                    cfg=s.cfg,
                    allow_light=self.allow_light,
                    device=s._device(),
                    cancel_check=cancel_check,
                    operator_confirm=_confirm,
                )
            else:
                result = run_protocol(
                    self.plan,
                    cfg=s.cfg,
                    root=s.results_root,
                    sample_id=self.sample_id,
                    allow_light=self.allow_light,
                    device=s._device(),
                    simulated=s.sim is not None,
                    rig_identity="sim" if s.sim is not None else "host",
                    cancel_check=cancel_check,
                    operator_confirm=_confirm,
                )
            self.folder = result.folder
            with self._lock:
                self.progress = {
                    "status": result.status.lower(),
                    "done": len(result.observations),
                    "of": len(self.plan.steps) * len(self.plan.protocol.detectors),
                    "kind": "protocol",
                    "cancel_reason": result.cancel_reason,
                }
                self.result = {
                    "status": result.status,
                    "cancel_reason": result.cancel_reason,
                    "run_id": result.store.run_id,
                    "unresolved": bool(result.store.meta.get("unresolved")),
                    "folder": str(result.folder),
                }
            s.log(f"protocol {result.status}: {result.folder.name}")
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            s.log(f"protocol error: {self.error}")
        finally:
            s._dev_lock.release()
            s._changed()
