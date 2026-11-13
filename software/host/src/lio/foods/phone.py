"""The phone intake app: a small web app served on the local network.

Phones open ``http://<this Mac>:8766/?k=<key>`` (the dashboard's Database tab
shows it as a QR code), photograph a barcode and save the sample. It works
in Safari on iPhone and Chrome on Android, and can be added to the home
screen like an app.

Safety: this server is reachable from the LAN, so it serves **only** the food
intake: it has no access to the instrument (LEDs, motors, tests), which stays
on the dashboard's local-only server. Every API call needs the pairing key,
kept in ``<foods dir>/phone_key.txt``; "New key" on the dashboard revokes
every phone paired before.
"""

from __future__ import annotations

import collections
import ipaddress
import json
import logging
import mimetypes
import os
import re
import secrets
import socket
import subprocess
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from .barcode import BarcodeError, best_code, decode_image
from .intake import Intake, data_url_bytes
from .store import FoodLibrary, LibraryError
from .tunnel import CloudflareTunnel

log = logging.getLogger(__name__)

MAX_BODY = 24 * 1024 * 1024  # two base64 photos
UNPAIRED = "not paired: scan the QR code on the dashboard"
FAIL_LIMIT = 30  # wrong-key requests per window before everyone without the key gets 429
FAIL_WINDOW_S = 60.0
STATIC = {
    "/icon-192.png": "icon-192.png",
    "/icon-512.png": "icon-512.png",
    "/icon.svg": "icon.svg",
}


def static_bytes(name: str) -> bytes:
    return resources.files("lio.foods").joinpath(f"static/{name}").read_bytes()


TUNNEL_PREFIXES = ("utun", "tun", "tap", "ppp", "ipsec", "gpd", "wg", "zt")


def _ifconfig_ipv4() -> list[tuple[str, str]]:
    """(interface, IPv4 address) pairs from ``ifconfig`` (macOS, most Linux)."""
    try:
        out = subprocess.run(
            ["ifconfig"], capture_output=True, text=True, timeout=3, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    pairs, iface = [], ""
    for line in out.splitlines():
        if line and not line[0].isspace():
            iface = line.split(":", 1)[0]
        else:
            m = re.match(r"\s+inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                pairs.append((iface, m.group(1)))
    return pairs


def lan_addresses() -> list[str]:
    """IPv4 addresses a phone on the same Wi-Fi may reach, best first.

    Private (RFC 1918) addresses on real interfaces come first; loopback and
    VPN tunnels (utun, ppp, ...) are left out, since phones cannot reach them.
    """
    found: list[str] = []
    for iface, ip in _ifconfig_ipv4():
        if ip.startswith("127.") or iface.startswith(TUNNEL_PREFIXES) or ip.startswith("169.254."):
            continue
        found.append(ip)
    if not found:
        try:  # the address of the default route (no packet is sent)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                found.append(s.getsockname()[0])
        except OSError:
            pass
    found.sort(key=lambda ip: 0 if ipaddress.ip_address(ip).is_private else 1)
    return list(dict.fromkeys(found))


def vpn_active() -> bool:
    """True if a VPN tunnel has an IPv4 address (it may block the local network)."""
    return any(iface.startswith(TUNNEL_PREFIXES) for iface, _ in _ifconfig_ipv4())


class PhoneKey:
    """The pairing key, kept on disk so a phone stays paired across restarts."""

    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            self.value = path.read_text().strip()
        except OSError:
            self.value = ""
        if len(self.value) < 16:
            self.renew()

    def renew(self) -> str:
        self.value = secrets.token_urlsafe(12)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(self.value + "\n")
        return self.value

    def ok(self, given: str) -> bool:
        return bool(given) and secrets.compare_digest(given, self.value)


class PhoneServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, lib: FoodLibrary, intake: Intake, key: PhoneKey, host: str, port: int):
        self.lib, self.intake, self.key = lib, intake, key
        self.tunnel: CloudflareTunnel | None = None
        self._fails: collections.deque[float] = collections.deque()
        self._fails_lock = threading.Lock()
        super().__init__((host, port), _Handler)

    def throttled(self, failed: bool) -> bool:
        """True while too many wrong-key requests arrived (the tunnel address is public)."""
        now = time.monotonic()
        with self._fails_lock:
            while self._fails and now - self._fails[0] > FAIL_WINDOW_S:
                self._fails.popleft()
            if failed:
                self._fails.append(now)
            return len(self._fails) > FAIL_LIMIT

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    def urls(self) -> list[str]:
        """Pairing links, best first: the tunnel (any network), then the local network."""
        k = quote(self.key.value)
        out = [f"http://{ip}:{self.port}/?k={k}" for ip in lan_addresses()]
        if self.tunnel is not None and self.tunnel.state == "up" and self.tunnel.url:
            out.insert(0, f"{self.tunnel.url}/?k={k}")
        return out

    def serve_in_thread(self) -> threading.Thread:
        t = threading.Thread(target=self.serve_forever, name="lio-phone-http", daemon=True)
        t.start()
        return t


def qr_svg(text: str) -> str:
    """The QR code as inline SVG (needs ``segno``); empty if it is not installed."""
    try:
        import segno
    except ImportError:
        return ""
    # omitsize: a viewBox instead of fixed width/height, so CSS can scale it without cropping
    svg: str = segno.make(text, error="m").svg_inline(
        omitsize=True, border=2, dark="#0b0b0b", light="#ffffff"
    )
    return svg


class _Handler(BaseHTTPRequestHandler):
    server: PhoneServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        log.debug("phone %s %s", self.address_string(), format % args)

    def _send(self, status: int, body: bytes, ctype: str, cache: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(data).encode(), "application/json")

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def _key(self, url: Any) -> bool:
        given = self.headers.get("X-LIO-Phone-Key") or parse_qs(url.query).get("k", [""])[0]
        ok = self.server.key.ok(given)
        self.server.throttled(failed=not ok)
        return ok

    def _refuse(self) -> None:
        if self.server.throttled(failed=False):
            return self._error(HTTPStatus.TOO_MANY_REQUESTS, "too many attempts: wait a minute")
        return self._error(HTTPStatus.FORBIDDEN, UNPAIRED)

    def _body(self) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise LibraryError("upload too large")
        data = json.loads(self.rfile.read(n)) if n else {}
        if not isinstance(data, dict):
            raise LibraryError("expected a JSON object")
        return data

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            csp = (
                "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                "img-src 'self' data: blob:; frame-ancestors 'none'"
            )
            self.send_response(HTTPStatus.OK)
            body = static_bytes("phone.html")
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", csp)
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)
            return None
        if url.path in STATIC:
            name = STATIC[url.path]
            ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
            return self._send(HTTPStatus.OK, static_bytes(name), ctype, cache=True)
        if not self._key(url):
            return self._refuse()
        if url.path == "/manifest.webmanifest":
            k = quote(self.server.key.value)
            manifest = {
                "name": "LIO food intake",
                "short_name": "LIO intake",
                "start_url": f"/?k={k}",
                "scope": "/",
                "display": "standalone",
                "background_color": "#f9f9f7",
                "theme_color": "#2a78d6",
                "icons": [
                    {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                    {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
                ],
            }
            return self._send(
                HTTPStatus.OK, json.dumps(manifest).encode(), "application/manifest+json"
            )
        if url.path.startswith("/files/"):
            p = self.server.lib.file_path(url.path[len("/files/") :])
            if p is None:
                return self._error(HTTPStatus.NOT_FOUND, "not found")
            ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            return self._send(HTTPStatus.OK, p.read_bytes(), ctype)
        try:
            if url.path == "/api/status":
                return self._json(
                    {
                        "ok": True,
                        "decoder": self.server.intake.can_decode(),
                        "online_lookup": self.server.lib.lookup is not None,
                        "counts": self.server.lib.counts(),
                    }
                )
            if url.path == "/api/find":
                q = parse_qs(url.query)
                return self._json(
                    self.server.intake.find_online(q.get("gtin14", [""])[0], q.get("q", [""])[0])
                )
            if url.path == "/api/preview":
                q = parse_qs(url.query)
                return self._json(
                    self.server.intake.preview_record(
                        q.get("source", [""])[0], q.get("id", [""])[0], q.get("q", [""])[0]
                    )
                )
            if url.path == "/api/recent":
                return self._json({"samples": self.server.lib.samples(limit=15)})
        except (BarcodeError, LibraryError, ValueError) as e:
            return self._error(HTTPStatus.BAD_REQUEST, str(e))
        except Exception as e:
            log.exception("phone GET %s", url.path)
            return self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(e).__name__}: {e}")
        return self._error(HTTPStatus.NOT_FOUND, "not found")

    def _decode_live(self, photo: bytes | None) -> dict[str, Any]:
        if not photo:
            raise LibraryError("no frame")
        t0 = time.monotonic()
        # Keep the last frame (overwritten each time) so a failing scan can be inspected.
        debug = self.server.lib.root / "debug"
        debug.mkdir(exist_ok=True)
        (debug / "last_live_frame.jpg").write_bytes(photo)
        found = decode_image(photo, retail_only=True)
        best = best_code(found)
        out: dict[str, Any] = {
            "found": best is not None,
            "ms": round(1000 * (time.monotonic() - t0)),
        }
        if best is not None:
            g, d = best
            out.update(code=g.code, kind=g.kind, format=d.format)
        elif found:
            out["seen"] = [f"{d.format} {d.text}" for d in found]
        return out

    def do_POST(self) -> None:
        url = urlparse(self.path)
        if not self._key(url):
            return self._refuse()
        intake, lib = self.server.intake, self.server.lib
        try:
            b = self._body()
            if url.path == "/api/decode":  # live camera frames: decode only, no lookup
                return self._json(self._decode_live(data_url_bytes(b.get("photo"))))
            if url.path == "/api/identify":
                return self._json(
                    intake.identify(data_url_bytes(b.get("photo")), str(b.get("code") or ""))
                )
            if url.path == "/api/label":
                return self._json(
                    intake.read_label(data_url_bytes(b.get("photo")), str(b.get("kind") or ""))
                )
            if url.path == "/api/fuse":
                return self._json(
                    intake.fuse_sources(
                        b.get("records"),
                        b.get("sections"),
                        str(b.get("query") or ""),
                        all_variants=bool(b.get("all")),
                    )
                )
            if url.path == "/api/structure":
                return self._json(intake.structure_sections(b.get("sections")))
            if url.path == "/api/ingredients":
                return self._json(intake.confirm_ingredients(str(b.get("gtin14") or ""), b))
            if url.path == "/api/label/apply":
                return self._json(intake.apply_label(str(b.get("sample_code") or ""), b))
            if url.path == "/api/save":
                return self._json(intake.commit(str(b.get("draft") or ""), b, source="phone"))
            if url.path == "/api/archive":
                return self._json(
                    lib.update_sample(str(b.get("sample_code") or ""), {"archived": True})
                )
            if url.path == "/api/photo":
                photo = data_url_bytes(b.get("photo"))
                if not photo:
                    raise LibraryError("no photo")
                return self._json(
                    lib.set_photo(str(b.get("sample_code") or ""), str(b.get("kind")), photo)
                )
        except (BarcodeError, LibraryError, ValueError) as e:
            return self._error(HTTPStatus.BAD_REQUEST, str(e))
        except Exception as e:
            log.exception("phone POST %s", url.path)
            return self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(e).__name__}: {e}")
        return self._error(HTTPStatus.NOT_FOUND, "not found")
