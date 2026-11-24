"""Identity of the code THIS process loaded (S7).

Computed once, when the process first imports LIO: the git commit, whether the
host package differed from it, a SHA-256 over the actual ``lio`` source files
as read at startup, the PID and the start time. Later edits to the files on
disk, or a later ``git checkout``, do not change it: a long-running dashboard
therefore reports the build it is really running, and ``deployment_changed()``
says when the disk has moved on so a verified restart is needed.
``Session.version`` is a UI refresh token, not a software version.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from pathlib import Path
from typing import Any

_PKG = Path(__file__).resolve().parent


def _source_sha256() -> str:
    h = hashlib.sha256()
    for path in sorted(_PKG.rglob("*")):
        if path.is_file() and path.suffix in (".py", ".html", ".js", ".css", ".json"):
            h.update(path.relative_to(_PKG).as_posix().encode() + b"\0")
            try:
                h.update(path.read_bytes())
            except OSError:
                h.update(b"<unreadable>")
    return h.hexdigest()


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(_PKG), *args], capture_output=True, text=True, timeout=5,
            check=True,
        ).stdout.strip()  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None


def _startup_identity() -> dict[str, Any]:
    status = _git("status", "--porcelain", "--", str(_PKG))
    return {
        "loaded_source_sha256": _source_sha256(),
        "git_commit_at_start": _git("rev-parse", "HEAD"),
        "host_package_dirty_at_start": None if status is None else bool(status),
        "pid": os.getpid(),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "note": "identity of the code loaded at process start, not of the disk now",
    }


_STARTUP: dict[str, Any] = _startup_identity()


def loaded_build_identity() -> dict[str, Any]:
    return dict(_STARTUP)


def deployment_changed() -> dict[str, Any]:
    """Compare the files on disk now with what this process loaded."""
    now = _source_sha256()
    changed = now != _STARTUP["loaded_source_sha256"]
    return {
        "changed": changed,
        "loaded_source_sha256": _STARTUP["loaded_source_sha256"],
        "disk_source_sha256": now,
        "action": (
            "files on disk differ from the running code: disconnect, stop, restart and "
            "verify the new PID before relying on new behaviour"
            if changed
            else "running code matches disk"
        ),
    }
