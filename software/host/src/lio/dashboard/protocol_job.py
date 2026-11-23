"""Targeted stationary protocol runs from the dashboard (M6 / R5).

Reuses ScanJob Control patterns for pause/abort/heartbeat. Offline plan preview
stays on ``plan_protocol`` (no device). Emission still requires ``allow_light``.
Progress updates during acquisition; each checkpoint needs a fresh linked answer
(D13/D14/D19) — a start checkbox cannot confirm later interventions.
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
        self._answers: dict[str, bool] = {}
        self._answer_events: dict[str, threading.Event] = {}
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
                "pending_prompts": list(self._answer_events.keys()),
            }

    def answer_checkpoint(self, occurrence_id: str, confirmed: bool) -> None:
        """Fresh linked answer for one checkpoint occurrence (D13).

        Rejects unknown/stale IDs and duplicate answers — never invents confirmation.
        """
        occ = str(occurrence_id or "").strip()
        if not occ:
            raise ValueError("occurrence_id required")
        with self._lock:
            ev = self._answer_events.get(occ)
            if ev is None:
                raise ValueError(f"unknown or stale occurrence_id {occ!r}")
            if occ in self._answers:
                raise ValueError(f"duplicate answer for occurrence_id {occ!r}")
            self._answers[occ] = bool(confirmed)
            ev.set()

    def _run(self) -> None:
        s = self.s
        if not s._dev_lock.acquire(timeout=5):
            self.error = "the device is busy"
            return
        try:
            cancel_check = lambda: bool(self.control.abort_reason)  # noqa: E731

            occurrence = {"n": 0}

            def _confirm(msg: str) -> bool:
                # D13: never reuse the start checkbox for later interventions.
                occurrence["n"] += 1
                occ_id = f"dashboard:{occurrence['n']}:{msg[:40]}"
                if occurrence["n"] == 1 and self.operator_checkpoint_flag:
                    # First protocol-level confirm may use the start flag.
                    return bool(self.operator_checkpoint_flag)
                ev = threading.Event()
                with self._lock:
                    self._answer_events[occ_id] = ev
                    self.progress = {
                        **self.progress,
                        "status": "awaiting_checkpoint",
                        "prompt": msg,
                        "occurrence_id": occ_id,
                    }
                # Wait until answered or aborted; abort releases without inventing OK.
                while not ev.wait(timeout=0.2):
                    if self.control.abort_reason:
                        with self._lock:
                            self._answer_events.pop(occ_id, None)
                        return False
                    self.control.beat()  # keep view responsive; UI must call beat too
                with self._lock:
                    self._answer_events.pop(occ_id, None)
                    return bool(self._answers.pop(occ_id, False))

            def _on_progress(p: dict[str, Any]) -> None:
                with self._lock:
                    self.progress = dict(p)

            if self.resume is not None:
                result = resume_protocol(
                    self.resume,
                    cfg=s.cfg,
                    allow_light=self.allow_light,
                    device=s._device(),
                    cancel_check=cancel_check,
                    operator_confirm=_confirm,
                    control=self.control,
                    on_progress=_on_progress,
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
                    control=self.control,
                    on_progress=_on_progress,
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
