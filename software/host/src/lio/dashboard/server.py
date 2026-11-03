"""A small local HTTP server for the dashboard page (standard library only).

Safety of the HTTP side: the page can light LEDs and move motors, so

- the server listens on 127.0.0.1 only (``dashboard.host`` in ``lio_hw.yaml``);
- every ``/api`` request must carry the random token embedded in the page
  (header ``X-LIO-Token``), which other web sites cannot read or send, so a
  page open in another tab cannot drive the instrument;
- the ``Host`` header must name this machine, which defeats DNS rebinding.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .session import Busy, Refused, Session

log = logging.getLogger(__name__)

LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
RESULT_TYPES = {".html", ".png", ".csv", ".json", ".md", ".svg"}
MAX_BODY = 64 * 1024


def page_html(token: str) -> str:
    text = resources.files("lio.dashboard").joinpath("static/index.html").read_text("utf-8")
    return text.replace("__LIO_TOKEN__", token)


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, session: Session, host: str, port: int) -> None:
        self.session = session
        self.token = secrets.token_urlsafe(24)
        super().__init__((host, port), _Handler)

    @property
    def url(self) -> str:
        host, port = self.server_address[:2]
        return f"http://{host if isinstance(host, str) else host.decode()}:{port}/"

    def serve_in_thread(self) -> threading.Thread:
        t = threading.Thread(target=self.serve_forever, name="lio-dashboard-http", daemon=True)
        t.start()
        return t


class _Handler(BaseHTTPRequestHandler):
    server: DashboardServer
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------ plumbing

    def log_message(self, format: str, *args: Any) -> None:
        log.debug("%s %s", self.address_string(), format % args)

    def _send(
        self, status: int, body: bytes, ctype: str, extra: dict[str, str] | None = None
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(data).encode(), "application/json")

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in LOCAL_HOSTS

    def _token_ok(self) -> bool:
        given = self.headers.get("X-LIO-Token") or ""
        return secrets.compare_digest(given, self.server.token)

    def _body(self) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise Refused("request too large")
        if n == 0:
            return {}
        data = json.loads(self.rfile.read(n))
        if not isinstance(data, dict):
            raise Refused("expected a JSON object")
        return data

    # ---------------------------------------------------------------- GET

    def do_GET(self) -> None:
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "bad Host header")
        url = urlparse(self.path)
        s = self.server.session
        if url.path in ("/", "/index.html"):
            body = page_html(self.server.token).encode()
            csp = (
                "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                "img-src 'self' data:; frame-ancestors 'none'"
            )
            return self._send(
                HTTPStatus.OK, body, "text/html; charset=utf-8", {"Content-Security-Policy": csp}
            )
        if url.path.startswith("/results/"):
            return self._result_file(url.path[len("/results/") :])
        if not url.path.startswith("/api/"):
            return self._error(HTTPStatus.NOT_FOUND, "not found")
        if not self._token_ok():
            return self._error(HTTPStatus.FORBIDDEN, "missing or wrong token")
        try:
            if url.path == "/api/state":
                since = parse_qs(url.query).get("v", [""])[0]
                if since == str(s.version) and not s.running:
                    return self._json({"unchanged": True, "version": s.version})
                return self._json(s.snapshot())
            if url.path == "/api/static":
                return self._json(s.static_info())
            if url.path == "/api/ports":
                return self._json({"ports": s.ports()})
            if url.path == "/api/runs":
                return self._json({"runs": s.past_runs()})
        except Exception as e:
            log.exception("GET %s", url.path)
            return self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(e).__name__}: {e}")
        return self._error(HTTPStatus.NOT_FOUND, "not found")

    def _result_file(self, rel: str) -> None:
        root = self.server.session.results_root.resolve()
        path = (root / rel).resolve()
        if root not in path.parents or path.suffix not in RESULT_TYPES or not path.is_file():
            return self._error(HTTPStatus.NOT_FOUND, "not found")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if ctype.startswith("text/"):
            ctype += "; charset=utf-8"
        self._send(HTTPStatus.OK, path.read_bytes(), ctype)

    # --------------------------------------------------------------- POST

    def do_POST(self) -> None:
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "bad Host header")
        if not self._token_ok():
            return self._error(HTTPStatus.FORBIDDEN, "missing or wrong token")
        path = urlparse(self.path).path
        s = self.server.session
        try:
            b = self._body()
            if path == "/api/connect":
                s.connect(str(b.get("target") or ""), str(b.get("faults") or ""))
            elif path == "/api/disconnect":
                s.disconnect()
            elif path == "/api/run":
                meta = {k: str(b.get(k) or "") for k in ("sample_id", "operator", "notes")}
                return self._json(
                    s.start(
                        [str(m) for m in b.get("modules") or []],
                        interactive=bool(b.get("interactive")),
                        allow_motion=bool(b.get("allow_motion")),
                        motion_confirmed=bool(b.get("motion_confirmed")),
                        sim_operator=bool(b.get("sim_operator", True)),
                        metadata=meta,
                        compare_baseline=bool(b.get("compare_baseline")),
                        save_baseline=bool(b.get("save_baseline")),
                    )
                )
            elif path == "/api/stop":
                s.stop()
            elif path == "/api/answer":
                s.answer(int(b["id"]), b.get("value"), bool(b.get("abort")))
            elif path == "/api/measure":
                return self._json(s.measure(_hole(b)))
            elif path == "/api/flash":
                return self._json(s.flash(_hole(b), s.cfg.section.integer("dashboard.flash_ms")))
            elif path == "/api/off":
                s.all_off()
            elif path == "/api/clear":
                s.clear_results()
            elif path == "/api/load":
                s.load_run(str(b.get("run_id") or ""))
            else:
                return self._error(HTTPStatus.NOT_FOUND, "not found")
        except Busy as e:
            return self._error(HTTPStatus.CONFLICT, str(e))
        except (Refused, KeyError, ValueError) as e:
            return self._error(HTTPStatus.BAD_REQUEST, str(e))
        except Exception as e:  # device / transport errors: tell the page why
            log.exception("POST %s", path)
            return self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(e).__name__}: {e}")
        self._json({"ok": True})


def _hole(b: dict[str, Any]) -> int:
    hole = int(b.get("hole", 0))
    if not 1 <= hole <= 16:
        raise Refused("hole must be 1-16")
    return hole


def serve(session: Session, host: str, port: int) -> DashboardServer:
    """Create the server (not yet serving); raises OSError if the port is taken."""
    return DashboardServer(session, host, port)


def results_root_default(repo_root: Path) -> Path:
    return repo_root / "test_results"
