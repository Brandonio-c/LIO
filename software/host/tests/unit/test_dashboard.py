"""The dashboard: twin mapping, session (runs, prompts, stop, manual tools), HTTP safety."""

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
from lio.dashboard import twin
from lio.dashboard.server import DashboardServer
from lio.dashboard.session import Busy, Refused, Session
from lio.device import Cancelled, LIODevice
from lio.results import Status, SubResult, TestResult
from lio.sim import Faults, SimulatedLIO
from lio.transport import SimTransport, TransportError

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
        assert twin.parts([], cfg)["holes"]["10"]["fitted"]  # LED fitted, wavelength TBD


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


@pytest.fixture
def budget_session(cfg: HwConfig, tmp_path: Path) -> Iterator[Session]:
    """A session whose LEDs tab keeps the duty budget (dashboard.ring_duty_budget)."""
    data = copy.deepcopy(cfg.data)
    data["dashboard"]["ring_duty_budget"] = True
    s = Session(parse_config(data, cfg.path), tmp_path / "results")
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


class SilentBoard(SimTransport):
    """A board running some other sketch: it prints ``lines`` (or nothing) at boot."""

    def __init__(self, cfg: HwConfig, lines: list[str]) -> None:
        super().__init__(SimulatedLIO(cfg))
        self.lines = list(lines)

    def read_line(self, timeout: float) -> str | None:
        if self.lines:
            return self.lines.pop(0)
        self.sim.advance(timeout)
        return None


class TestOtherFirmware:
    def test_silent_board(self, cfg: HwConfig, tmp_path: Path) -> None:
        s = Session(cfg, tmp_path, transport_factory=lambda port: SilentBoard(cfg, []))
        with pytest.raises(Refused, match=r"sent nothing.*flash firmware v2"):
            s.connect("/dev/cu.fake")
        assert not s.connected

    def test_board_printing_something_else(self, cfg: HwConfig, tmp_path: Path) -> None:
        board = SilentBoard(cfg, ["LIO Z controller ready", "POSL=0 POSR=0"])
        s = Session(cfg, tmp_path, transport_factory=lambda port: board)
        with pytest.raises(Refused, match=r"other text instead \(LIO Z controller ready \| POSL"):
            s.connect("/dev/cu.fake")


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


class TestPersistence:
    def test_board_survives_a_restart(self, cfg: HwConfig, tmp_path: Path) -> None:
        s1 = Session(cfg, tmp_path)
        s1.connect("sim", "dead_channel:5")
        s1.start(["T05.2"])
        wait_for(lambda: not s1.running)
        s1.start(["link"])
        wait_for(lambda: not s1.running)
        s1.shutdown()

        s2 = Session(cfg, tmp_path)  # a new dashboard session
        assert s2.snapshot()["overall"]["verdict"] == twin.NOT_RUN  # hardware board: empty
        s2.connect("sim")
        snap = s2.snapshot()
        assert snap["parts"]["holes"]["5"]["status"] == "FAIL"  # from the earlier session
        assert snap["board"]["kind"] == "sim" and snap["board"]["runs"] == 2
        t052 = next(t for s in snap["subsystems"] for t in s["tests"] if t["id"] == "T05.2")
        assert t052["run_id"].endswith("_sim") and t052["started"]
        assert snap["last_run"] is not None
        s2.shutdown()

    def test_latest_result_wins_and_clear_is_remembered(
        self, cfg: HwConfig, tmp_path: Path
    ) -> None:
        s1 = Session(cfg, tmp_path)
        s1.connect("sim", "dead_channel:5")
        s1.start(["T05.2"])
        wait_for(lambda: not s1.running)
        s1.connect("sim")  # healthy now
        assert s1.board["T05.2"].status == Status.FAIL  # restored from disk
        s1.start(["T05.2"])
        wait_for(lambda: not s1.running)
        s1.shutdown()
        s2 = Session(cfg, tmp_path)
        s2.connect("sim")
        assert s2.board["T05.2"].status == Status.PASS
        s2.clear_results()
        s2.shutdown()
        s3 = Session(cfg, tmp_path)
        s3.connect("sim")
        assert s3.board == {} and s3.snapshot()["board"]["cleared"]
        s3.shutdown()

    def test_hardware_and_simulator_are_kept_apart(self, cfg: HwConfig, tmp_path: Path) -> None:
        s = Session(cfg, tmp_path, transport_factory=lambda port: SimTransport(SimulatedLIO(cfg)))
        s.connect("/dev/cu.fake")  # counts as hardware
        s.start(["T02.1"])
        wait_for(lambda: not s.running)
        s.connect("sim")
        assert "T02.1" not in s.board
        s.connect("/dev/cu.fake")
        assert "T02.1" in s.board
        s.shutdown()


class TestWakeButton:
    def test_wake_finds_the_adc(self, cfg: HwConfig, tmp_path: Path) -> None:
        s = Session(cfg, tmp_path)
        s.connect("sim", "bank_a_asleep")  # opening the port already wakes it
        assert s.sim is not None and s.sim.wakes == 1
        s.dev.sleep(cfg.sim.num("bank_awake_s") + 1)  # type: ignore[union-attr]
        assert s.dev.info(refresh=True).as_int("adc_ok") == 0  # type: ignore[union-attr]
        out = s.wake()
        assert out["adc_ok"] and out["wake_ms"] == cfg.section.integer("dashboard.wake_button_ms")
        s.shutdown()


# ------------------------------------------------------------- motors tab


class TestMotorsTab:
    def test_status_before_connecting(self, session: Session) -> None:
        assert session.motor_status() == {"connected": False}

    def test_moves_need_arming_then_move_both_up(self, session: Session) -> None:
        session.connect("sim")
        st = session.motor_status()
        assert st["connected"] and not st["armed"]
        assert st["motors"]["1"] == {"state": "idle", "pos": 0}
        with pytest.raises(Refused, match="not armed"):
            session.motor_move("both", "up", 64, 5)
        assert session.motor_arm()["armed_ms"] > 0
        session.motor_move("both", "up", 64, 5)
        wait_for(
            lambda: all(m["state"] == "idle" for m in session.motor_status()["motors"].values())
        )
        st = session.motor_status()
        assert st["motors"]["1"]["pos"] == 64 and st["motors"]["2"]["pos"] == 64  # + is up
        session.motor_move("1", "down", 32, 5)
        wait_for(lambda: session.motor_status()["motors"]["1"]["state"] == "idle")
        st = session.motor_status()
        assert st["motors"]["1"]["pos"] == 32 and st["motors"]["2"]["pos"] == 64

    def test_stop_and_release(self, session: Session) -> None:
        session.connect("sim")
        session.motor_arm()
        session.motor_move("2", "up", 2048, 1)
        assert session.motor_status()["motors"]["2"]["state"] == "run"
        assert session.motor_stop() == {"stopped": "motors"}
        assert session.motor_status()["motors"]["2"]["state"] == "idle"
        assert session.motor_release() == {"released": True}

    def test_arguments_are_checked(self, session: Session) -> None:
        session.connect("sim")
        session.motor_arm()
        for args in (
            ("3", "up", 64, 5),
            ("1", "sideways", 64, 5),
            ("1", "up", 0, 5),
            ("1", "up", 4096, 5),
            ("1", "up", 64, 99),
        ):
            with pytest.raises(Refused):
                session.motor_move(*args)

    def test_refused_while_an_led_is_on(self, session: Session) -> None:
        session.connect("sim")
        session.motor_arm()
        assert session.dev is not None
        session.dev.ch_on(3, 2000)
        with pytest.raises(Refused, match="refused"):
            session.motor_move("1", "up", 64, 5)
        session.all_off()

    def test_over_http(self, server: DashboardServer) -> None:
        assert call(server, "/api/motor")[1] == {"connected": False}
        assert call(server, "/api/connect", {"target": "sim"})[0] == 200
        assert (
            call(
                server, "/api/motor/move", {"motor": "1", "direction": "up", "steps": 64, "rpm": 5}
            )[0]
            == 400
        )
        assert call(server, "/api/motor/arm", {})[0] == 200
        code, out = call(
            server, "/api/motor/move", {"motor": "both", "direction": "up", "steps": 64, "rpm": 5}
        )
        assert code == 200 and out["motor"] == "both"
        assert call(server, "/api/motor/stop", {})[0] == 200
        assert call(server, "/api/motor")[1]["connected"] is True


def test_wake_button_refused_when_wake_is_disabled(
    cfg: HwConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(cfg.section._data["power"], "wake", False)
    s = Session(cfg, tmp_path / "results")
    try:
        assert s.static_info()["wake"] is False
        s.connect("sim")
        with pytest.raises(Refused, match="disabled"):
            s.wake()
    finally:
        s.shutdown(timeout_s=30)


class TestContinuousJog:
    def test_runs_past_the_firmware_bound_until_stopped(self, session: Session) -> None:
        session.connect("sim")
        out = session.jog_start("both", "up", 1000)
        assert out == {"jog": "both", "direction": "up", "speed": 1000}
        jog_max = session.cfg.limits["jog_max"]

        def far() -> bool:
            st = session.motor_status()  # also the page's heartbeat
            return st["motors"]["1"]["pos"] > jog_max + 200

        wait_for(far, timeout=30)
        st = session.motor_status()
        assert st["jog"] == {"motor": "both", "direction": "up", "speed": 1000}
        assert st["motors"]["1"]["state"] == "run" and st["motors"]["2"]["state"] == "run"
        assert session.jog_stop()["stopped"] is True
        st = session.motor_status()
        assert st["jog"] is None
        assert {m["state"] for m in st["motors"].values()} == {"idle"}

    def test_single_motor_down_and_no_arming_needed(self, session: Session) -> None:
        session.connect("sim")
        session.jog_start("2", "down", 400)
        wait_for(lambda: session.motor_status()["motors"]["2"]["pos"] < -50)
        st = session.motor_status()
        assert st["motors"]["1"]["state"] == "idle" and st["motors"]["2"]["state"] == "run"
        session.motor_stop()  # the big STOP ends a continuous move too
        st = session.motor_status()
        assert st["jog"] is None and st["motors"]["2"]["state"] == "idle"

    def test_dead_man_stops_it_when_the_page_goes_quiet(
        self, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(session.cfg.section._data["dashboard"], "jog_deadman_s", 0.5)
        session.connect("sim")
        session.jog_start("both", "down", 500)
        assert session.sim is not None
        wait_for(lambda: session._jog is None, timeout=10)  # no status polls: dead-man
        st = session.motor_status()
        assert {m["state"] for m in st["motors"].values()} == {"idle"}
        assert any("stopped checking in" in line for line in session._log)

    def test_without_dead_man_it_runs_until_stop(
        self, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(session.cfg.section._data["dashboard"], "jog_deadman_s", 0)
        session.connect("sim")
        session.jog_start("both", "up", 1000)
        jog_max = session.cfg.limits["jog_max"]
        assert session.sim is not None
        assert session._jog is not None
        session._jog["heartbeat"] = -1e9  # the page went away long ago

        def renewed() -> bool:  # plain device reads move the simulator's clock on
            with session._dev_lock:
                assert session.dev is not None
                session.dev.ping()
            return session.sim is not None and session.sim.motors[0].renewals >= 3

        wait_for(renewed)
        assert session._jog is not None
        st = session.motor_status()
        assert st["motors"]["1"]["state"] == "run" and st["motors"]["1"]["pos"] > jog_max
        session.jog_stop()
        assert session.motor_status()["jog"] is None

    def test_refused_while_an_led_is_on_and_runs_refused_while_jogging(
        self, session: Session
    ) -> None:
        session.connect("sim")
        assert session.dev is not None
        session.dev.ch_on(3, 2000)
        with pytest.raises(Refused, match="LED on"):
            session.jog_start("both", "up", 500)
        session.all_off()
        session.jog_start("both", "up", 500)
        with pytest.raises(Busy, match="continuously"):
            session.start(["T03.1"], interactive=False)
        session.all_off()
        assert session.motor_status()["jog"] is None

    def test_arguments_are_checked(self, session: Session) -> None:
        session.connect("sim")
        for args in (("3", "up", 500), ("1", "left", 500), ("1", "up", 10), ("1", "up", 5000)):
            with pytest.raises(Refused):
                session.jog_start(*args)

    def test_over_http(self, server: DashboardServer) -> None:
        assert call(server, "/api/connect", {"target": "sim"})[0] == 200
        code, out = call(server, "/api/motor/jog", {"motor": "1", "direction": "up", "speed": 300})
        assert code == 200 and out["jog"] == "1"
        assert call(server, "/api/motor")[1]["jog"]["motor"] == "1"
        assert call(server, "/api/motor/jog_stop", {})[1] == {"stopped": True}


class TestLedRing:
    def test_minimum_step_keeps_rail_a_within_budget(self, budget_session: Session) -> None:
        session = budget_session
        holes = session.ring_holes(include_unfitted=False)
        assert holes == list(range(1, 17))  # holes 10-11 are fitted too
        step = session.ring_min_step_ms(100, holes)
        # per hole: 100 ms on once per lap, at most 1000 ms per 60 s on RAIL A
        assert 100 * 60_000 / (step * len(holes)) <= 1000
        assert session.ring_min_step_ms(10, holes) >= 10 + 20  # never shorter than on + gap

    def test_ring_goes_round_one_hole_at_a_time_until_stop(self, session: Session) -> None:
        session.connect("sim")
        out = session.ring_start(50, 0, include_unfitted=False)
        assert out["active"] and out["step_ms"] == out["min_step_ms"]  # raised to the minimum

        def offs() -> list[int]:
            assert session.dev is not None
            return [e.fields.as_int("ch") for _, e in session.dev.events if e.name == "OFF"]

        def lapped() -> bool:
            assert session.sim is not None and len(session.sim._light_since) <= 1
            return len(offs()) >= 16  # the lap's last hole has turned off again

        wait_for(lapped, timeout=60)
        lit = offs()
        assert lit[:16] == list(range(1, 17))  # in order, one each
        assert session.ring_stop() == {"stopped": True}
        assert session.ring_status() == {"active": False}
        assert session.sim is not None and not session.sim._light_since

    def test_timing_changes_while_running_and_tools_are_locked(self, session: Session) -> None:
        session.connect("sim")
        session.ring_start(50, 0, include_unfitted=False)
        out = session.ring_start(100, 5000, include_unfitted=True)
        assert out["on_ms"] == 100 and out["step_ms"] == 5000 and 10 in out["holes"]
        with pytest.raises(Busy, match="ring"):
            session.measure(8)
        with pytest.raises(Busy, match="ring"):
            session.jog_start("both", "up", 500)
        with pytest.raises(Busy, match="ring"):
            session.start(["T03.1"], interactive=False)
        session.all_off()
        assert session.ring_status() == {"active": False}

    def test_on_time_is_checked(self, session: Session) -> None:
        session.connect("sim")
        for on in (0, 5, 5000):
            with pytest.raises(Refused):
                session.ring_start(on, 0, include_unfitted=False)

    def test_over_http(self, server: DashboardServer) -> None:
        assert call(server, "/api/connect", {"target": "sim"})[0] == 200
        code, out = call(server, "/api/ring/min_step?on_ms=100&unfitted=0")
        assert code == 200 and out["min_step_ms"] > 100
        code, out = call(server, "/api/ring/start", {"on_ms": 100, "step_ms": 0})
        assert code == 200 and out["active"]
        assert call(server, "/api/ring")[1]["active"] is True
        assert call(server, "/api/ring/stop", {})[1] == {"stopped": True}


class UnpluggedBoard(SimTransport):
    """A board whose USB link dies (Errno 6) once ``pull()`` is called."""

    def __init__(self, cfg: HwConfig) -> None:
        super().__init__(SimulatedLIO(cfg))
        self.dead = False

    def write_line(self, line: str) -> None:
        if self.dead:
            raise TransportError("write failed: [Errno 6] Device not configured")
        super().write_line(line)


class TestHoldOneHole:
    def test_click_a_hole_holds_it_within_its_duty_budget(self, budget_session: Session) -> None:
        session = budget_session
        session.connect("sim")
        out = session.ring_start(100, 0, include_unfitted=False, holes=[7])
        assert out["holes"] == [7]
        # RAIL A: 1000 ms per 60 s -> a 100 ms flash at most every 6 s
        assert out["step_ms"] == out["min_step_ms"] == 6000

        def flashed_twice() -> bool:
            return bool(session.ring_status().get("laps", 0) >= 2)

        wait_for(flashed_twice, timeout=60)
        assert session.dev is not None
        lit = {e.fields.as_int("ch") for _, e in session.dev.events if e.name == "OFF"}
        assert lit == {7}  # only the held hole ever lights
        out = session.ring_start(100, 0, include_unfitted=False, holes=[13])  # switch
        assert out["holes"] == [13] and out["min_step_ms"] == 1200  # RAIL B: 5000 ms / 60 s
        session.ring_stop()
        assert session.sim is not None and not session.sim._light_since

    def test_without_budget_a_held_hole_is_relit_straight_away(self, session: Session) -> None:
        assert not session.cfg.section.raw("dashboard.ring_duty_budget")
        session.connect("sim")
        out = session.ring_start(1000, 0, include_unfitted=False, holes=[7])
        gap = session.cfg.section.integer("dashboard.ring_gap_ms")
        assert out["step_ms"] == out["min_step_ms"] == 1000 + gap  # no cool-down

        def relit() -> bool:
            assert session.sim is not None and len(session.sim._light_since) <= 1
            return bool(session.ring_status().get("laps", 0) >= 3)

        wait_for(relit, timeout=60)
        assert session.ring_status()["state"] != "cooling"
        session.ring_stop()
        assert session.sim is not None and not session.sim._light_since

    def test_bad_hole_is_refused(self, session: Session) -> None:
        session.connect("sim")
        with pytest.raises(Refused, match="1-16"):
            session.ring_start(100, 0, include_unfitted=False, holes=[17])


class TestUsbLinkLost:
    def test_ring_drops_the_stale_port_and_page_says_reconnect(
        self, cfg: HwConfig, tmp_path: Path
    ) -> None:
        boards = [UnpluggedBoard(cfg), UnpluggedBoard(cfg)]
        board = boards[0]
        s = Session(cfg, tmp_path, transport_factory=lambda port: boards.pop(0))
        s.connect("/dev/cu.fake")
        board.dead = True
        s.ring_start(50, 0, include_unfitted=False)
        wait_for(lambda: not s.connected, timeout=10)
        assert s.ring_status() == {"active": False}
        assert "USB link lost" in s.error
        assert s.ring_stop() == {"stopped": False}  # no traceback on a dead link
        s.connect("/dev/cu.fake")  # the re-enumerated port: reconnect works
        assert s.connected

    def test_server_answers_503_and_disconnects(self, cfg: HwConfig, tmp_path: Path) -> None:
        board = UnpluggedBoard(cfg)
        s = Session(cfg, tmp_path, transport_factory=lambda port: board)
        s.connect("/dev/cu.fake")
        board.dead = True
        with pytest.raises(TransportError):
            s.measure(1)
        s.link_lost(TransportError("gone"))
        assert not s.connected
