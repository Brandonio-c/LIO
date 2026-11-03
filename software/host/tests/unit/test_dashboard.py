"""The dashboard: twin mapping, session (runs, prompts, stop, manual tools), HTTP safety."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from lio.config import HwConfig
from lio.dashboard import twin
from lio.dashboard.server import DashboardServer
from lio.dashboard.session import Busy, Refused, Session
from lio.device import Cancelled, LIODevice
from lio.results import Status, SubResult, TestResult
from lio.sim import Faults, SimulatedLIO
from lio.transport import SimTransport

pytestmark = pytest.mark.unit


def result(test_id: str, *subs: tuple[str, Status], kind: str = "A") -> TestResult:
    r = TestResult(test_id, test_id, test_id.split(".")[0], kind)
    r.subs = [SubResult(f"{test_id}/{sid}", sid, st) for sid, st in subs]
    r.status = max((st for _, st in subs), key=lambda s: s.rank, default=Status.PASS)
    return r


def wait_for(cond: Callable[[], bool], timeout: float = 30.0) -> None:
    end = time.monotonic() + timeout
    while not cond():
        if time.monotonic() > end:
            raise AssertionError("timed out")
        time.sleep(0.01)


# --------------------------------------------------------------------- twin


class TestTwin:
    def test_nothing_run(self, cfg: HwConfig) -> None:
        p = twin.parts([], cfg)
        assert {h["status"] for h in p["holes"].values()} == {twin.NOT_RUN}
        assert p["nano"]["status"] == twin.NOT_RUN
        assert twin.overall([], cfg, 45)["verdict"] == twin.NOT_RUN

    def test_hole_rail_and_detector_mapping(self, cfg: HwConfig) -> None:
        rs = [
            result("T05.1", ("A/h08/ce_high", Status.FAIL), ("B/h12/ce_high", Status.PASS)),
            result("T05.2", ("h05/opt101", Status.FAIL), ("h12/ingaas", Status.PASS)),
            result("T03.2", ("a0", Status.WARN), ("a1", Status.PASS)),
            result("T09.2", ("1/up", Status.PASS), ("2/up", Status.FAIL), kind="M"),
        ]
        p = twin.parts(rs, cfg)
        assert p["holes"]["8"]["status"] == "FAIL"
        assert p["holes"]["5"]["status"] == "FAIL"
        assert p["holes"]["12"]["status"] == "PASS"
        assert p["rails"]["A"]["status"] == "FAIL" and p["rails"]["B"]["status"] == "PASS"
        assert p["detectors"]["ingaas"]["status"] == "WARN"  # a0 is the InGaAs input
        assert p["detectors"]["opt101"]["status"] == "PASS"
        assert p["motors"]["1"]["status"] == "PASS" and p["motors"]["2"]["status"] == "FAIL"
        assert p["adc"]["status"] == "WARN"
        assert p["holes"]["5"]["items"][0]["id"] == "T05.2/h05/opt101"  # worst first

    def test_one_dark_led_does_not_condemn_the_detector(self, cfg: HwConfig) -> None:
        r = result(
            "T06.1",
            ("dark", Status.PASS),
            ("h05/visible", Status.FAIL),
            ("h06/visible", Status.PASS),
        )
        p = twin.parts([r], cfg)
        assert p["detectors"]["opt101"]["status"] == "PASS"
        assert any(i["id"] == "T06.1/h05/visible" for i in p["detectors"]["opt101"]["items"])
        assert p["holes"]["5"]["status"] == "FAIL"

    def test_many_dark_leds_do(self, cfg: HwConfig) -> None:
        n = cfg.thresholds.integer("verdict.max_channel_fails") + 1
        subs = [(f"h{h:02d}/visible", Status.FAIL) for h in range(1, n + 1)]
        p = twin.parts([result("T06.1", ("dark", Status.PASS), *subs)], cfg)
        assert p["detectors"]["opt101"]["status"] == "FAIL"

    def test_walk_test_on_one_hole_leaves_the_shift_registers_green(self, cfg: HwConfig) -> None:
        rs = [
            result("T04.1", ("zero", Status.PASS)),
            result("T04.4", ("h05/visible", Status.FAIL), ("camera", Status.PASS), kind="I"),
        ]
        p = twin.parts(rs, cfg)
        assert p["sr"]["status"] == "PASS"
        tiles = {t["module"]: t for t in twin.subsystems(rs, {"T04": ["T04.1", "T04.4"]})}
        assert tiles["T04"]["status"] == "FAIL"  # the tile stays faithful to the tests
        assert tiles["T04"]["fail_holes"] == [5] and tiles["T04"]["fail_only_holes"]

    def test_safety_watchdog_failure_on_one_rail_is_not_excused(self, cfg: HwConfig) -> None:
        r = result("T10.2", ("A/h03/off", Status.FAIL), ("B/h13/off", Status.PASS))
        assert twin.parts([r], cfg)["safety"]["status"] == "FAIL"

    def test_subsystem_tiles_and_partial_verdict(self, cfg: HwConfig) -> None:
        rs = [
            result("T02.1", ("banner", Status.PASS)),
            result("T05.2", ("h05/opt101", Status.FAIL)),
        ]
        tiles = {
            t["module"]: t
            for t in twin.subsystems(rs, {"T02": ["T02.1", "T02.2"], "T05": ["T05.2"]})
        }
        assert tiles["T02"]["status"] == "PASS" and (
            tiles["T02"]["run"],
            tiles["T02"]["total"],
        ) == (1, 2)
        assert [t["status"] for t in tiles["T02"]["tests"]] == ["PASS", twin.NOT_RUN]
        assert tiles["T09"]["status"] == twin.NOT_RUN
        o = twin.overall(rs, cfg, 45)
        assert o["verdict"] == "DEGRADED" and not o["complete"] and o["run"] == 2

    def test_hole_facts(self, cfg: HwConfig) -> None:
        r = TestResult("T05.2", "x", "T05", "A", Status.PASS)
        r.subs = [SubResult("T05.2/h08/ingaas", "x", Status.PASS, measured={"net": 1998})]
        h8 = twin.parts([r], cfg)["holes"]["8"]
        assert h8["net"] == {"ingaas": 1998} and h8["register"] == "U1 Q7" and h8["rail"] == "A"
        assert twin.parts([], cfg)["holes"]["9"]["register"] == "U2 Q0"
        assert not twin.parts([], cfg)["holes"]["10"]["fitted"]


# -------------------------------------------------------------- cancel hook


class TestCancel:
    def test_cancel_is_one_shot_and_only_when_cancellable(self, cfg: HwConfig) -> None:
        dev = LIODevice(SimTransport(SimulatedLIO(cfg)), cfg)
        dev.open()
        dev.request_cancel()
        dev.ping()  # not cancellable: ignored (the CLI path)
        dev.cancellable = True
        with pytest.raises(Cancelled):
            dev.sleep(1.0)
        dev.ping()  # consumed: the restore afterwards works
        dev.request_cancel()
        with pytest.raises(Cancelled):
            dev.ping()
        dev.close()


# ------------------------------------------------------------------ session


@pytest.fixture
def session(cfg: HwConfig, tmp_path: Path) -> Iterator[Session]:
    s = Session(cfg, tmp_path / "results")
    yield s
    s.shutdown(timeout_s=30)


class TestSession:
    def test_connect_run_and_accumulate(self, session: Session) -> None:
        session.connect("sim")
        assert session.snapshot()["firmware"]["fw"].startswith("2.")
        session.start(["link"])
        wait_for(lambda: not session.running)
        snap = session.snapshot()
        assert snap["parts"]["nano"]["status"] == "PASS"
        assert snap["last_run"]["verdict"]["verdict"] == "FUNCTIONAL"
        assert Path(snap["last_run"]["folder"], "report.html").is_file()
        session.start(["T05.2"])
        wait_for(lambda: not session.running)
        tiles = {t["module"]: t for t in session.snapshot()["subsystems"]}
        assert tiles["T02"]["run"] == 6 and tiles["T05"]["run"] == 1  # the board accumulates
        assert len(session.past_runs()) == 2

    def test_faults_show_on_the_twin(self, session: Session) -> None:
        session.connect("sim", "dead_channel:5")
        session.start(["channels"])
        wait_for(lambda: not session.running)
        snap = session.snapshot()
        assert snap["parts"]["holes"]["5"]["status"] == "FAIL"
        assert snap["parts"]["holes"]["4"]["status"] == "PASS"
        assert snap["overall"]["verdict"] == "DEGRADED"

    def test_selection(self, session: Session) -> None:
        assert session.select(["channels"], interactive=False, allow_motion=False) == [
            "T05.1", "T05.2", "T05.3", "T05.4", "T05.5"
        ]  # fmt: skip
        assert "T05.6" in session.select(["T05"], interactive=True, allow_motion=False)
        assert session.select(["motors"], interactive=False, allow_motion=False) == []
        assert len(session.select([], interactive=True, allow_motion=True)) == len(
            session.catalogue
        )

    def test_guards(self, session: Session) -> None:
        with pytest.raises(Refused, match="not connected"):
            session.start(["link"])
        session.connect("sim")
        with pytest.raises(Refused, match="confirmation"):
            session.start(["motors"], allow_motion=True)
        with pytest.raises(Refused, match="no tests"):
            session.start(["motors"])

    def test_web_operator_prompts(self, session: Session) -> None:
        session.connect("sim")
        session.start(["T05.6"], interactive=True, sim_operator=False)
        answered = []
        for _ in range(4):  # rail A: ready, mA; rail B: ready, mA
            wait_for(lambda: session.prompt is not None)
            p = session.snapshot()["prompt"]
            value = None if p["kind"] == "act" else (30 if p["key"].endswith(":A") else 45)
            session.answer(p["id"], value)
            answered.append(p["key"])
            wait_for(lambda pid=p["id"]: session.prompt is None or session.prompt.id != pid)
        wait_for(lambda: not session.running)
        assert answered == ["meter_ready:A", "meter_ma:A", "meter_ready:B", "meter_ma:B"]
        assert session.board["T05.6"].status == Status.PASS
        with pytest.raises(Refused):
            session.answer(999, 1)

    def test_stop_during_a_prompt_skips_and_restores(self, session: Session) -> None:
        session.connect("sim")
        session.start(["T05.6", "T07"], interactive=True, sim_operator=False)
        wait_for(lambda: session.prompt is not None)
        session.stop()
        wait_for(lambda: not session.running)
        r = session.board["T05.6"]
        assert r.status == Status.SKIP and "aborted" in r.message
        assert "restore" not in r.message
        assert "T07.1" not in session.board
        assert session.snapshot()["last_run"]["stopped"]

    def test_manual_tools(self, session: Session) -> None:
        session.connect("sim")
        m = session.measure(8)
        assert m["net"]["opt101"] > 0 and m["net"]["ingaas"] > 0
        assert session.flash(13, 300)["on_ms"] == 300
        session.all_off()
        assert session.sim is not None and not session.sim._light_since

    def test_manual_tools_refused_while_running(self, session: Session) -> None:
        session.connect("sim")
        session.start(["T05.6"], interactive=True, sim_operator=False)
        wait_for(lambda: session.prompt is not None)
        with pytest.raises(Busy):
            session.measure(8)
        with pytest.raises(Busy):
            session.disconnect()
        session.stop()
        wait_for(lambda: not session.running)

    def test_load_earlier_run(self, session: Session) -> None:
        session.connect("sim", "dead_channel:5")
        session.start(["T05.2"])
        wait_for(lambda: not session.running)
        run_id = session.snapshot()["last_run"]["run_id"]
        session.clear_results()
        assert session.snapshot()["overall"]["verdict"] == twin.NOT_RUN
        session.load_run(run_id)
        assert session.snapshot()["parts"]["holes"]["5"]["status"] == "FAIL"
        with pytest.raises(Refused):
            session.load_run("../etc")

    def test_serial_needs_firmware_v2(self, cfg: HwConfig, tmp_path: Path) -> None:
        class OldFirmware(SimulatedLIO):
            FW_VERSION = "1.4.0"

        sim = OldFirmware(cfg, Faults())
        s = Session(cfg, tmp_path, transport_factory=lambda port: SimTransport(sim))
        with pytest.raises(Refused, match="Flash firmware v2"):
            s.connect("/dev/cu.fake")
        assert not s.connected


# ------------------------------------------------------------------- server


@pytest.fixture
def server(session: Session) -> Iterator[DashboardServer]:
    srv = DashboardServer(session, "127.0.0.1", 0)
    srv.serve_in_thread()
    yield srv
    srv.shutdown()
    srv.server_close()


def call(
    srv: DashboardServer,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    token: str | None = "default",
    host: str | None = None,
) -> tuple[int, Any]:
    req = urllib.request.Request(
        srv.url.rstrip("/") + path, method="GET" if body is None else "POST"
    )
    if token is not None:
        req.add_header("X-LIO-Token", srv.token if token == "default" else token)
    if host is not None:
        req.add_header("Host", host)
    if body is not None:
        req.data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw.decode()


class TestServer:
    def test_page_carries_the_token(self, server: DashboardServer) -> None:
        status, page = call(server, "/", token=None)
        assert status == 200 and server.token in page and "__LIO_TOKEN__" not in page

    def test_api_needs_token_and_local_host(self, server: DashboardServer) -> None:
        assert call(server, "/api/state", token=None)[0] == 403
        assert call(server, "/api/state", token="wrong")[0] == 403
        assert call(server, "/api/connect", {"target": "sim"}, token=None)[0] == 403
        assert call(server, "/api/state", host="evil.example:80")[0] == 403
        assert call(server, "/api/state")[0] == 200

    def test_end_to_end(self, server: DashboardServer) -> None:
        assert call(server, "/api/connect", {"target": "sim"}) == (200, {"ok": True})
        status, out = call(server, "/api/run", {"modules": ["adc"]})
        assert status == 200 and out["tests"][0] == "T03.1"
        assert call(server, "/api/run", {"modules": ["adc"]})[0] in (200, 409)
        wait_for(lambda: not call(server, "/api/state")[1]["running"])
        _, st = call(server, "/api/state")
        assert st["parts"]["adc"]["status"] == "PASS"
        unchanged = call(server, f"/api/state?v={st['version']}")[1]
        assert unchanged == {"unchanged": True, "version": st["version"]}
        report = st["last_run"]["report"]
        assert call(server, report, token=None)[0] == 200
        assert call(server, "/api/measure", {"hole": 99})[0] == 400
        assert call(server, "/api/measure", {"hole": 3})[1]["net"]["opt101"] > 0
        assert call(server, "/api/static")[1]["flash_ms"] > 0
        assert call(server, "/api/nope", {})[0] == 404

    def test_results_files_stay_inside_the_results_folder(self, server: DashboardServer) -> None:
        root = server.session.results_root
        root.mkdir(parents=True, exist_ok=True)
        (root.parent / "secret.json").write_text("{}")
        assert call(server, "/results/../secret.json", token=None)[0] == 404
        assert call(server, "/results/%2e%2e/secret.json", token=None)[0] == 404

    def test_motion_needs_confirmation_over_http(self, server: DashboardServer) -> None:
        call(server, "/api/connect", {"target": "sim"})
        status, out = call(server, "/api/run", {"modules": ["motors"], "allow_motion": True})
        assert status == 400 and "confirmation" in out["error"]


def test_threads_do_not_leak(session: Session) -> None:
    session.connect("sim")
    session.start(["link"])
    wait_for(lambda: not session.running)
    assert not [t for t in threading.enumerate() if t.name == "lio-dashboard-run"]
