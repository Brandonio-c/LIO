"""Analytical job queue: never blocks acquisition / device locks / heartbeat."""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Job:
    job_id: str
    kind: str
    status: str = "queued"  # queued | running | done | cancelled | error
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    result: Any = None
    error: str | None = None
    cancel_requested: bool = False


class ProfileJobQueue:
    """Single worker; acquisition hooks can request cancel/requeue."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._cv = threading.Condition(self._lock)
        self._worker: threading.Thread | None = None
        self._stop = False
        self._acquisition_active = False

    def notify_acquisition(self, active: bool) -> None:
        with self._cv:
            self._acquisition_active = active
            if active:
                for j in self._jobs.values():
                    if j.status == "running":
                        j.cancel_requested = True
            self._cv.notify_all()

    def submit(self, kind: str, fn: Callable[[Job], Any]) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id=job_id, kind=kind)
        with self._cv:
            self._jobs[job_id] = job
            self._pending: list[tuple[Job, Callable[[Job], Any]]]
            if not hasattr(self, "_pending"):
                self._pending = []
            self._pending.append((job, fn))
            if self._worker is None or not self._worker.is_alive():
                self._stop = False
                self._worker = threading.Thread(target=self._run, name="profile-jobs", daemon=True)
                self._worker.start()
            self._cv.notify_all()
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            j = self._jobs.get(job_id)
            if j is None:
                return None
            return {
                "job_id": j.job_id,
                "kind": j.kind,
                "status": j.status,
                "error": j.error,
                "result": j.result if j.status == "done" else None,
                "cancel_requested": j.cancel_requested,
            }

    def _run(self) -> None:
        while True:
            with self._cv:
                pending = getattr(self, "_pending", [])
                while not self._stop and (self._acquisition_active or not pending):
                    if self._stop:
                        return
                    self._cv.wait(timeout=0.5)
                if self._stop:
                    return
                if self._acquisition_active or not self._pending:
                    continue
                job, fn = self._pending.pop(0)
                job.status = "running"
                job.started = time.time()
            try:
                if job.cancel_requested:
                    raise InterruptedError("cancelled before start")
                result = fn(job)
                with self._lock:
                    if job.cancel_requested:
                        job.status = "cancelled"
                    else:
                        job.result = result
                        job.status = "done"
            except InterruptedError:
                with self._lock:
                    job.status = "cancelled"
            except Exception as e:
                with self._lock:
                    job.status = "error"
                    job.error = f"{type(e).__name__}: {e}"
            finally:
                with self._lock:
                    job.finished = time.time()

    def shutdown(self) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify_all()


# Process-wide queue (dashboard process only; not shared with acquisition locks)
QUEUE = ProfileJobQueue()
