"""Dashboard --no-food-library and profiles API smoke."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from lio.config import HwConfig
from lio.dashboard.server import DashboardServer
from lio.dashboard.session import Session
from lio.food_profiles.fixtures import build_fixture_library

pytestmark = pytest.mark.unit


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"X-LIO-Token": token, "Host": "127.0.0.1"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


def test_profiles_api_without_foods(cfg: HwConfig, tmp_path: Path) -> None:
    build_fixture_library(tmp_path)
    session = Session(cfg, tmp_path)
    server = DashboardServer(session, "127.0.0.1", 0, foods=None)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        # Static JS MIME
        req = urllib.request.Request(
            f"{base}/static/profiles/explorer.js", headers={"Host": "127.0.0.1"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            assert "javascript" in r.headers.get("Content-Type", "")
            body = r.read().decode()
            assert "drawHeatmap" in body
        runs = _get(f"{base}/api/profiles/runs", server.token)
        assert runs["runs"]
        rid = runs["runs"][0]["run_id"]
        hm = _get(f"{base}/api/profiles/run/{rid}/heatmap?detector=opt101", server.token)
        assert "net" in hm and "heights_hs" in hm
        # Food library endpoints refused
        with pytest.raises(urllib.error.HTTPError) as ei:
            _get(f"{base}/api/foods/status", server.token)
        assert ei.value.code in (400, 404, 500)
    finally:
        server.shutdown()
        server.server_close()
        session.shutdown()
