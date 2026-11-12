"""A Cloudflare quick tunnel to the phone app (works with a VPN on, and on cellular).

``cloudflared tunnel --url http://127.0.0.1:<phone port>`` opens an *outbound*
connection to Cloudflare and gets a random ``https://<words>.trycloudflare.com``
address that forwards to the phone app. Nothing listens for incoming
connections on this Mac, which is why it works while a VPN refuses them.

- The address is public. Every API call still needs the pairing key, and the
  phone app can only add food samples (no LEDs, motors or tests).
- A quick tunnel gets a new address each time it starts; phones then scan the
  new QR code. A fixed address needs a Cloudflare account and a named tunnel.
- HTTPS also lets the phone use a live camera viewfinder.
"""

from __future__ import annotations

import collections
import logging
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
SEARCH_PATHS = ("/opt/homebrew/bin/cloudflared", "/usr/local/bin/cloudflared")
START_TIMEOUT_S = 45.0


def find_cloudflared(configured: str = "") -> str | None:
    if configured:
        return configured if Path(configured).is_file() else None
    found = shutil.which("cloudflared")
    if found:
        return found
    return next((p for p in SEARCH_PATHS if Path(p).is_file()), None)


class CloudflareTunnel:
    def __init__(self, local_port: int, binary: str = "") -> None:
        self.local_port = local_port
        self.binary = binary
        self.url = ""
        self.state = "off"  # off | starting | up | error
        self.error = ""
        self.started_at = 0.0
        self.log: collections.deque[str] = collections.deque(maxlen=60)
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    def status(self) -> dict[str, object]:
        if self.state == "starting" and time.monotonic() - self.started_at > START_TIMEOUT_S:
            self.state, self.error = "error", "no tunnel address from Cloudflare (see the log)"
        if self._proc is not None and self._proc.poll() is not None and self.state != "off":
            self.state = "error"
            self.error = self.error or f"cloudflared exited ({self._proc.returncode})"
        return {"state": self.state, "url": self.url, "error": self.error}

    def start(self) -> None:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return
            exe = find_cloudflared(self.binary)
            if exe is None:
                self.state = "error"
                self.error = "cloudflared is not installed (brew install cloudflared)"
                return
            self.url, self.error, self.state = "", "", "starting"
            self.started_at = time.monotonic()
            cmd = [
                exe, "tunnel", "--no-autoupdate",
                "--url", f"http://127.0.0.1:{self.local_port}",
            ]  # fmt: skip
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    text=True,
                )
            except OSError as e:
                self.state, self.error = "error", f"cannot start cloudflared: {e}"
                return
            threading.Thread(target=self._read, name="lio-tunnel-log", daemon=True).start()

    def _read(self) -> None:
        proc = self._proc
        assert proc is not None and proc.stderr is not None
        for line in proc.stderr:
            line = line.rstrip()
            self.log.append(line)
            m = URL_RE.search(line)
            if m and not self.url:
                self.url = m.group(0)
            if "Registered tunnel connection" in line and self.url:
                self.state = "up"
                log.info("phone app tunnel up: %s", self.url)
        if self.state != "off":
            self.state = "error"
            self.error = self.error or "cloudflared stopped"

    def stop(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
            self.state, self.url, self.error = "off", "", ""
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
