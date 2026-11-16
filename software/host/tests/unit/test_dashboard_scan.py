"""The dashboard's Scan tab (LIO-SW-SCAN-001 §5, S6): plan preview, start, live progress
and heat-map, heartbeat pause, abort and resume, the result on the twin, the HTTP API."""

from __future__ import annotations

import copy
import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from lio.config import HwConfig, parse_config
from lio.dashboard.server import DashboardServer
from lio.dashboard.session import Busy, Refused, Session

pytestmark = pytest.mark.unit


def call(srv: DashboardServer, path: str, body: Any = None, *,
         token: str | None = "default") -> tuple[int, Any]:  # fmt: skip
    req = urllib.request.Request(srv.url.rstrip("/") + path,
                                 method="GET" if body is None else "POST")  # fmt: skip
    if token is not None:
        req.add_header("X-LIO-Token", srv.token)
    if body is not None:
        req.data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw.decode()


def wait_for(cond: Callable[[], bool], timeout: float = 60.0) -> None:
    end = time.monotonic() + timeout
    while not cond():
        if time.monotonic() > end:
            raise AssertionError("timed out")
        time.sleep(0.01)


@pytest.fixture
def scfg(cfg: HwConfig) -> HwConfig:
    data = copy.deepcopy(cfg.data)
    data["sim"]["height"].update(travel_hs=40000, peak_hs=-30000, width_hs=9000,
                                 peak_shift_hs=250)  # fmt: skip
    data["scan"].update(long_dark_s=2, hum_bursts=3)
    data["scan"]["modes"]["tiny"] = {"heights": 4, "up": "same", "return_top": True,
                                     "repeats": 1, "ref_heights": 0, "label": "test"}  # fmt: skip
    return parse_config(data, cfg.path)


@pytest.fixture
def session(scfg: HwConfig, tmp_path: Path) -> Iterator[Session]:
    s = Session(scfg, tmp_path / "results")
    s.connect("sim")
    yield s
    if s.scanning:
        s.scan_abort("test teardown")
        wait_for(lambda: not s.scanning)
    s.shutdown(timeout_s=30)


def test_plan_preview(session: Session) -> None:
    p = session.scan_plan("tiny", {"sweep_n": 4})
    assert p["mode"] == "tiny" and p["steps"] == 1 + 4 + 3 + 1
    assert p["settings"]["sweep_n"] == 4 and p["eta_s"] > 0 and "LED duty" in p["summary"]
    with pytest.raises(Refused):
        session.scan_plan("nope")
    st = session.static_info()["scan"]
    assert "M6" in st["hardware"]["lead_screw"] and st["settings"]["heartbeat_timeout_s"] == 90


def test_scan_runs_to_the_twin(session: Session) -> None:
    session.scan_start("tiny", "empty", heartbeat=False)
    assert session.running and session.scanning
    with pytest.raises(Busy):
        session.measure(8)  # the scan holds the device
    with pytest.raises(Busy):
        session.scan_start("tiny", "empty")
    wait_for(lambda: not session.scanning)
    v = session.scan_view()
    job = v["job"]
    assert job["result"]["verdict"]["verdict"] == "FUNCTIONAL", job["result"]
    assert job["progress"]["status"] == "complete"
    assert len(job["grid"]["opt101"]["8"]) >= 4  # live heat-map points
    run = job["result"]["run_id"]
    folder = session.results_root / run
    assert (folder / "report.html").exists() and (folder / "results.json").exists()
    assert session.board["T13.1"].status.value == "PASS"
    snap = session.snapshot()
    tiles = {t["module"]: t for t in snap["subsystems"]}
    assert tiles["T13"]["status"] == "PASS"
    assert snap["last_run"]["report"] == f"/results/{run}/report.html"
    assert v["runs"][0]["run_id"] == run and v["runs"][0]["status"] == "COMPLETE"
    assert any(r["run_id"] == run for r in session.past_runs())  # with the other runs


def test_heartbeat_missing_pauses_then_continues(session: Session) -> None:
    session.scan_start("tiny", "empty", heartbeat=True, overrides={"heartbeat_timeout_s": 0.3})
    wait_for(lambda: session.scan_job is not None and session.scan_job.control.paused)
    assert session.sim is not None and not session.sim._light_since  # paused safely
    stop = threading.Event()

    def beat() -> None:
        while not stop.is_set():
            session.scan_beat()
            time.sleep(0.02)

    t = threading.Thread(target=beat, daemon=True)
    t.start()
    try:
        wait_for(lambda: not session.scanning)
    finally:
        stop.set()
        t.join()
    job = session.scan_view()["job"]
    assert job["result"]["status"] == "COMPLETE"
    meta = json.loads((session.results_root / job["result"]["run_id"] / "scan.json").read_text())
    assert any(e.get("reason") == "operator heartbeat missing" for e in meta["events"])


def test_pause_abort_and_resume(session: Session) -> None:
    session.scan_start("tiny", "empty", heartbeat=False)
    wait_for(lambda: (session.scan_job is not None
                      and session.scan_job.progress.get("done", 0) >= 2))  # fmt: skip
    session.scan_pause(True)
    wait_for(lambda: session.scan_job is not None and session.scan_job.control.paused)
    session.all_off()  # All off during a scan aborts it
    wait_for(lambda: not session.scanning)
    runs = session.scan_view()["runs"]
    assert runs[0]["status"] == "INCOMPLETE" and "All off" in runs[0]["aborts"][-1]
    session.scan_start("", "", resume=runs[0]["run_id"], heartbeat=False)
    wait_for(lambda: not session.scanning)
    assert session.scan_view()["runs"][0]["status"] == "COMPLETE"
    with pytest.raises(Refused):
        session.scan_start("", "", resume="../etc")
    with pytest.raises(Refused):
        session.scan_pause(True)  # nothing running


def test_http_api(scfg: HwConfig, tmp_path: Path) -> None:
    s = Session(scfg, tmp_path / "results")
    srv = DashboardServer(s, "127.0.0.1", 0)
    srv.serve_in_thread()
    try:
        assert call(srv, "/api/connect", {"target": "sim"})[0] == 200
        status, p = call(srv, "/api/scan/plan", {"mode": "tiny", "overrides": {"sweep_n": 3}})
        assert status == 200 and p["settings"]["sweep_n"] == 3
        assert call(srv, "/api/scan/plan", {"mode": "tiny", "overrides": [1]})[0] == 400
        status, out = call(srv, "/api/scan/start", {"mode": "tiny", "sample_id": "empty",
                                                     "heartbeat": True})  # fmt: skip
        assert status == 200 and out["steps"] == 9
        assert call(srv, "/api/scan/beat", {})[1]["ok"]
        wait_for(lambda: not call(srv, "/api/scan")[1]["job"]["running"])
        view = call(srv, "/api/scan")[1]
        assert view["job"]["result"]["verdict"]["verdict"] == "FUNCTIONAL"
        assert call(srv, view["job"]["result"]["report"], token=None)[0] == 200
        assert call(srv, "/api/scan/abort", {})[0] == 400  # nothing running
        _, page = call(srv, "/", token=None)
        assert 'data-tab="scan"' in page and "Lead screw" in page
    finally:
        srv.shutdown()
        srv.server_close()
        s.shutdown(timeout_s=30)
