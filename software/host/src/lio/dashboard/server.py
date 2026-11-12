"""A small local HTTP server for the dashboard page (standard library only).

Safety of the HTTP side: the page can light LEDs and move motors, so

- the server listens on 127.0.0.1 only (``dashboard.host`` in ``lio_hw.yaml``);
- every ``/api`` request must carry the random token embedded in the page
  (header ``X-LIO-Token``), which other web sites cannot read or send, so a
  page open in another tab cannot drive the instrument;
- the ``Host`` header must name this machine, which defeats DNS rebinding.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import mimetypes
import secrets
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from lio.foods import structure
from lio.foods.barcode import normalise
from lio.foods.intake import Intake, data_url_bytes
from lio.foods.phone import PhoneServer, qr_svg, vpn_active
from lio.foods.scans import build_scan
from lio.foods.store import FoodLibrary, LibraryError
from lio.transport import TransportError

from .session import Busy, Refused, Session

log = logging.getLogger(__name__)

LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
RESULT_TYPES = {".html", ".png", ".csv", ".json", ".md", ".svg"}
MAX_BODY = 64 * 1024
MAX_PHOTO_BODY = 24 * 1024 * 1024  # food photos (base64)
PHOTO_PATHS = ("/api/foods/identify", "/api/foods/save", "/api/foods/photo", "/api/foods/label")


@dataclass
class Foods:
    """The food library as the dashboard sees it (Database tab)."""

    lib: FoodLibrary
    intake: Intake
    repeats_default: int = 3
    repeats_max: int = 10
    phone: PhoneServer | None = None
    phone_error: str = ""


def page_html(token: str) -> str:
    text = resources.files("lio.dashboard").joinpath("static/index.html").read_text("utf-8")
    return text.replace("__LIO_TOKEN__", token)


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, session: Session, host: str, port: int, foods: Foods | None = None) -> None:
        self.session = session
        self.foods = foods
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

    def _body(self, limit: int = MAX_BODY) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
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
        if url.path.startswith("/foods/"):
            return self._foods_file(url.path[len("/foods/") :])
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
            if url.path == "/api/motor":
                return self._json(s.motor_status())
            if url.path == "/api/ring":
                return self._json(s.ring_status())
            if url.path.startswith("/api/foods/"):
                return self._foods_get(url.path[len("/api/foods/") :], parse_qs(url.query))
            if url.path == "/api/ring/min_step":
                q = parse_qs(url.query)
                on_ms = int(q.get("on_ms", ["0"])[0])
                hole = int(q.get("hole", ["0"])[0])
                holes = [hole] if hole else s.ring_holes(q.get("unfitted", ["0"])[0] == "1")
                return self._json({"min_step_ms": s.ring_min_step_ms(on_ms, holes)})
        except TransportError as e:
            s.link_lost(e)
            return self._error(HTTPStatus.SERVICE_UNAVAILABLE, f"USB link lost: {e}. Reconnect.")
        except (Refused, ValueError) as e:  # LibraryError, BarcodeError: shown to the user
            return self._error(HTTPStatus.BAD_REQUEST, str(e))
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

    # -------------------------------------------------------------- foods

    def _foods(self) -> Foods:
        if self.server.foods is None:
            raise Refused("the food library is not enabled")
        return self.server.foods

    def _foods_file(self, rel: str) -> None:
        """Photos (``/foods/files/...``) and downloads (``/foods/export/...``)."""
        f = self.server.foods
        if f is None:
            return self._error(HTTPStatus.NOT_FOUND, "not found")
        try:
            if rel.startswith("files/"):
                p = f.lib.file_path(rel[len("files/") :])
                if p is None:
                    return self._error(HTTPStatus.NOT_FOUND, "not found")
                ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
                return self._send(HTTPStatus.OK, p.read_bytes(), ctype)
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            if rel == "export/samples.csv":
                body, ctype, name = f.lib.samples_csv(), "text/csv", f"lio_samples_{stamp}.csv"
            elif rel == "export/library.json":
                body = json.dumps(f.lib.export(), indent=1)
                ctype, name = "application/json", f"lio_food_library_{stamp}.json"
            elif rel == "export/composition.csv":
                comp = f.intake.composition
                if comp is None:
                    return self._error(HTTPStatus.NOT_FOUND, "the composition layer is not enabled")
                from lio_comp.export import rows, to_csv
                from lio_verify.verify import Verifier

                paths = sorted(comp.records.glob("*.json")) if comp.records.exists() else []
                body = to_csv(rows(paths, Verifier(comp.store, comp.rules, comp.schema)))
                ctype, name = "text/csv", f"lio_composition_{stamp}.csv"
            elif rel.startswith("export/scan/") and rel.endswith(".csv"):
                uid = rel[len("export/scan/") : -len(".csv")]
                sc = f.lib.scan(uid)
                body, ctype = f.lib.scan_csv(uid), "text/csv"
                name = f"{sc['sample_code']}_scan_{sc['created_at'][:19].replace(':', '')}.csv"
            else:
                return self._error(HTTPStatus.NOT_FOUND, "not found")
        except LibraryError as e:
            return self._error(HTTPStatus.NOT_FOUND, str(e))
        self._send(
            HTTPStatus.OK,
            body.encode(),
            ctype + "; charset=utf-8",
            {"Content-Disposition": f'attachment; filename="{name}"'},
        )

    def _foods_get(self, path: str, q: dict[str, list[str]]) -> None:
        f = self._foods()

        def arg(k: str) -> str:
            return q.get(k, [""])[0]

        if path == "status":
            phone: dict[str, Any] = {"enabled": f.phone is not None, "error": f.phone_error}
            if f.phone is not None:
                urls = f.phone.urls()
                tun = f.phone.tunnel
                phone.update(
                    urls=urls,
                    qr_svg=qr_svg(urls[0]) if urls else "",
                    vpn=vpn_active(),
                    tunnel=tun.status() if tun is not None else {"state": "off"},
                )
            return self._json(
                {
                    "counts": f.lib.counts(),
                    "decoder": f.intake.can_decode(),
                    "online_lookup": f.lib.lookup is not None,
                    "usda_key": (
                        "none"
                        if f.lib.lookup is None or not f.lib.lookup.s.usda_api_key
                        else "demo"
                        if f.lib.lookup.s.usda_api_key == "DEMO_KEY"
                        else "personal"
                    ),
                    "db_path": str(f.lib.db_path),
                    "repeats_default": f.repeats_default,
                    "repeats_max": f.repeats_max,
                    "phone": phone,
                }
            )
        if path == "samples":
            return self._json(
                {
                    "samples": f.lib.samples(
                        arg("q"),
                        archived=arg("archived") == "1",
                        scanned=arg("scanned"),
                        found=arg("found"),
                        ingredients=arg("ingredients"),
                        source=arg("source"),
                        sort=arg("sort") or "newest",
                    )
                }
            )
        if path == "sample":
            return self._json(f.lib.sample(arg("code"), raw=arg("raw") == "1"))
        if path == "scan":
            return self._json(f.lib.scan(arg("uuid")))
        if path == "composition":
            return self._json(f.intake.composition_report(arg("code")))
        if path == "find":
            return self._json(f.intake.find_online(arg("gtin14"), arg("q")))
        if path == "preview":
            return self._json(f.intake.preview_record(arg("source"), arg("id"), arg("q")))
        if path == "candidates":
            if f.lib.lookup is None:
                raise Refused("online lookup is off (foods.online_lookup)")
            name = arg("q").strip()
            if len(name) < 2:
                raise Refused("type a product name to search for")
            return self._json({"candidates": f.lib.lookup.search_by_name(name)})
        return self._error(HTTPStatus.NOT_FOUND, "not found")

    def _foods_post(self, path: str, b: dict[str, Any]) -> None:
        f = self._foods()
        code = str(b.get("sample_code") or "")
        if path == "identify":
            return self._json(
                f.intake.identify(data_url_bytes(b.get("photo")), str(b.get("code") or ""))
            )
        if path == "label":
            return self._json(
                f.intake.read_label(data_url_bytes(b.get("photo")), str(b.get("kind") or ""))
            )
        if path == "ingredients":
            return self._json(f.intake.confirm_ingredients(str(b.get("gtin14") or ""), b))
        if path == "label/apply":
            return self._json(f.intake.apply_label(code, b))
        if path == "structure":
            return self._json(f.intake.structure_sections(b.get("sections")))
        if path == "adopt":
            if f.lib.lookup is None:
                raise Refused("online lookup is off (foods.online_lookup)")
            src, ident = str(b.get("source") or ""), str(b.get("id") or "")
            picked, raw = f.lib.lookup.fetch(src, ident)
            table = None
            if b.get("structured"):
                try:
                    table = structure.clean(b["structured"])
                except ValueError as e:
                    raise Refused(str(e)) from e
            return self._json(
                f.lib.adopt(
                    str(b.get("gtin14") or ""),
                    picked,
                    raw,
                    source=src,
                    query=str(b.get("query") or ""),
                    structured=table,
                )
            )
        if path == "save":
            return self._json(f.intake.commit(str(b.get("draft") or ""), b, source="dashboard"))
        if path == "update":
            return self._json(f.lib.update_sample(code, b))
        if path == "photo":
            photo = data_url_bytes(b.get("photo"))
            if not photo:
                raise Refused("no photo")
            return self._json(f.lib.set_photo(code, str(b.get("kind") or ""), photo))
        if path == "product":
            return self._json(
                f.lib.set_product_info(str(b.get("gtin14") or ""), dict(b.get("fields") or {}))
            )
        if path == "refresh":
            return self._json(f.lib.product(normalise(str(b.get("gtin14") or "")), refresh=True))
        if path == "scan":
            repeats = int(b.get("repeats") or f.repeats_default)
            if not 1 <= repeats <= f.repeats_max:
                raise Refused(f"repeats must be 1-{f.repeats_max}")
            f.lib.sample(code)  # the sample must exist before the LEDs are used
            s = self.server.session
            sweeps, meta = s.sample_sweeps(repeats)
            scan = build_scan(s.cfg, sweeps, notes=str(b.get("notes") or ""), **meta)
            return self._json(f.lib.add_scan(code, scan))
        if path in ("tunnel/start", "tunnel/stop"):
            if f.phone is None or f.phone.tunnel is None:
                raise Refused("the phone app is off (foods.phone_enabled)")
            if path == "tunnel/start":
                f.phone.tunnel.start()
            else:
                f.phone.tunnel.stop()
            return self._json(f.phone.tunnel.status())
        if path == "phone/rekey":
            if f.phone is None:
                raise Refused("the phone app is off (foods.phone_enabled)")
            f.phone.key.renew()
            return self._json({"ok": True})
        return self._error(HTTPStatus.NOT_FOUND, "not found")

    # --------------------------------------------------------------- POST

    def do_POST(self) -> None:
        if not self._host_ok():
            return self._error(HTTPStatus.FORBIDDEN, "bad Host header")
        if not self._token_ok():
            return self._error(HTTPStatus.FORBIDDEN, "missing or wrong token")
        path = urlparse(self.path).path
        s = self.server.session
        try:
            b = self._body(MAX_PHOTO_BODY if path in PHOTO_PATHS else MAX_BODY)
            if path.startswith("/api/foods/"):
                return self._foods_post(path[len("/api/foods/") :], b)
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
            elif path == "/api/wake":
                return self._json(s.wake())
            elif path == "/api/motor/arm":
                return self._json(s.motor_arm())
            elif path == "/api/motor/move":
                return self._json(
                    s.motor_move(
                        str(b.get("motor") or ""),
                        str(b.get("direction") or ""),
                        int(b.get("steps", 0)),
                        int(b.get("rpm", 0)),
                    )
                )
            elif path == "/api/motor/jog":
                return self._json(
                    s.jog_start(
                        str(b.get("motor") or ""),
                        str(b.get("direction") or ""),
                        int(b.get("speed", 0)),
                    )
                )
            elif path == "/api/motor/jog_stop":
                return self._json(s.jog_stop())
            elif path == "/api/ring/start":
                return self._json(
                    s.ring_start(
                        int(b.get("on_ms", 0)),
                        int(b.get("step_ms", 0)),
                        bool(b.get("include_unfitted")),
                        [int(h) for h in b.get("holes") or []],
                    )
                )
            elif path == "/api/ring/stop":
                return self._json(s.ring_stop())
            elif path == "/api/motor/stop":
                return self._json(s.motor_stop())
            elif path == "/api/motor/release":
                return self._json(s.motor_release())
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
        except TransportError as e:
            s.link_lost(e)
            return self._error(HTTPStatus.SERVICE_UNAVAILABLE, f"USB link lost: {e}. Reconnect.")
        except Exception as e:  # device errors: tell the page why
            log.exception("POST %s", path)
            return self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(e).__name__}: {e}")
        self._json({"ok": True})


def _hole(b: dict[str, Any]) -> int:
    hole = int(b.get("hole", 0))
    if not 1 <= hole <= 16:
        raise Refused("hole must be 1-16")
    return hole


def serve(session: Session, host: str, port: int, foods: Foods | None = None) -> DashboardServer:
    """Create the server (not yet serving); raises OSError if the port is taken."""
    return DashboardServer(session, host, port, foods)


def results_root_default(repo_root: Path) -> Path:
    return repo_root / "test_results"
