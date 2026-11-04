"""Simulator behaviour: protocol fidelity, safety rules, and the physical effect of
every injectable fault. (Detection of each fault by the test catalogue is the
fault matrix in M3; here we check that each fault does what it claims.)"""

from __future__ import annotations

import itertools
from collections.abc import Iterator

import pytest

from lio.config import HwConfig
from lio.device import DeviceError, LIODevice, NoResponse
from lio.protocol import ErrCode
from lio.sim import FAULT_NAMES, Faults, FaultSpecError, SimulatedLIO, loop_patterns
from lio.transport import SimTransport, TransportError

pytestmark = pytest.mark.unit


def make(cfg: HwConfig, faults: str | None = None, **kw: bool) -> LIODevice:
    sim = SimulatedLIO(cfg, Faults.parse(faults), **kw)
    return LIODevice(SimTransport(sim), cfg)


@pytest.fixture
def dev(cfg: HwConfig) -> Iterator[LIODevice]:
    with make(cfg) as d:
        yield d


def sim_of(d: LIODevice) -> SimulatedLIO:
    t = d.transport
    assert isinstance(t, SimTransport)
    return t.sim


# ------------------------------------------------------------- fault specs


class TestFaultSpec:
    def test_all_names_parse(self) -> None:
        for name in FAULT_NAMES:
            spec = {"stuck_on": "stuck_on:5", "dead_channel": "dead_channel:3"}.get(name, name)
            if name == "swapped":
                spec = "swapped:3,8"
            assert Faults.parse(spec).active

    def test_combined(self) -> None:
        f = Faults.parse("reversed_ingaas,stuck_on:5,swapped:3,8,noisy_adc")
        assert f.reversed_ingaas and f.noisy_adc
        assert f.stuck_on == {5} and f.swapped == {3: 8, 8: 3}
        assert f.active == ["stuck_on:5", "swapped:3,8", "reversed_ingaas", "noisy_adc"]

    def test_list_input_and_none(self) -> None:
        assert Faults.parse(["chain_break", "dead_channel:2"]).active == [
            "dead_channel:2",
            "chain_break",
        ]
        assert Faults.parse(None).active == []

    @pytest.mark.parametrize(
        "bad",
        [
            "nonsense",
            "stuck_on",
            "stuck_on:0",
            "stuck_on:x",
            "swapped:3",
            "swapped:4,4",
            "no_adc:1",
        ],
    )
    def test_bad(self, bad: str) -> None:
        with pytest.raises(FaultSpecError):
            Faults.parse(bad)


# ----------------------------------------------------------------- protocol


class TestLink:
    def test_boot_banner_and_compat(self, dev: LIODevice) -> None:
        assert dev.banner is not None and dev.banner.fields.as_str("fw") == "2.1.0"
        assert dev.boot_s is not None and dev.boot_s < 3.0
        dev.check_compatible()

    def test_ping_latency(self, dev: LIODevice) -> None:
        rtts = [dev.ping() for _ in range(20)]
        assert max(rtts) < 0.05

    def test_unknown_bad_overflow(self, dev: LIODevice) -> None:
        with pytest.raises(DeviceError) as e:
            dev.command("FROB")
        assert e.value.code == ErrCode.UNKNOWN
        with pytest.raises(DeviceError) as e:
            dev.command("CH 99 ON")
        assert e.value.code == ErrCode.BAD_ARG
        dev.transport.write_raw(b"X" * 80 + b"\n")
        assert dev.drain(0.1) == []
        assert any("code=6" in n for n in dev.noise) is False  # parsed as Response, not noise
        dev.transport.write_raw(b"\x00\xff\xfe garbage \x01\n")
        dev.ping()

    def test_overflow_response(self, dev: LIODevice) -> None:
        dev.transport.write_raw(b"Y" * 70 + b"\n")
        line = dev.transport.read_line(0.5)
        assert line == "ERR ? code=6 msg=line too long"

    def test_bytes_before_boot_are_lost(self, cfg: HwConfig) -> None:
        sim = SimulatedLIO(cfg)
        t = SimTransport(sim)
        t.open()
        t.write_line("PING")  # sent during the bootloader
        lines = [t.read_line(3.0), t.read_line(3.0), t.read_line(0.5)]
        assert lines[1] is not None and lines[1].startswith("# BOOT")
        assert lines[2] is None

    def test_closed_transport(self, cfg: HwConfig) -> None:
        t = SimTransport(SimulatedLIO(cfg))
        with pytest.raises(TransportError):
            t.write_line("PING")
        with pytest.raises(TransportError):
            t.read_line(0.1)

    def test_reset(self, dev: LIODevice) -> None:
        dev.ch_on(3, 500)
        banner = dev.reset()
        assert banner.is_boot
        st = dev.status()
        assert st.as_int("ch") == 0 and st.as_int("mask") == 0

    def test_info_mirrors_config(self, dev: LIODevice, cfg: HwConfig) -> None:
        f = dev.info()
        for key in ("wdt_a_ms", "wdt_b_ms", "comms_ms", "arm_ms", "step_max", "jog_max"):
            assert f.as_int(key) == cfg.limits[key]

    def test_legacy_commands(self, dev: LIODevice) -> None:
        assert dev.command("VA5000").fields.as_int("clamped") == 1
        assert dev.command("VS300").fields.as_int("value") == 300
        assert dev.command("ACC10").fields.as_int("value") == 25
        assert dev.command("?").response.ok
        r = dev.command("U")
        assert r.fields.as_int("steps") == 2048
        assert dev.status().as_str("motor1") == "run"
        with pytest.raises(DeviceError) as e:
            dev.meas(3)
        assert e.value.code == ErrCode.BUSY
        dev.command("S")
        assert dev.status().as_str("motor1") == "idle"
        dev.command("POSL0")
        assert dev.status().as_int("pos1") == 0
        with pytest.raises(DeviceError):
            dev.command("VAX")

    def test_jog_is_bounded(self, dev: LIODevice) -> None:
        dev.command("VA1000")
        dev.command("LU")
        ev = dev.wait_motor_done(1, timeout=30)
        assert ev is not None and ev.fields.as_int("steps") == 2048

    def test_slow_silent_jog_ends_at_failsafe(self, dev: LIODevice, cfg: HwConfig) -> None:
        # Default VA 200 half-steps/s: 2048 steps take ~11 s, longer than the
        # 10 s comms timeout, so with no further bytes the failsafe ends it first.
        dev.command("LU")
        ev = dev.wait_event("FAILSAFE", timeout=cfg.limits["comms_ms"] / 1000 + 2)
        assert ev is not None
        assert dev.status().as_str("motor1") == "idle"

    def test_jog_refused_while_lit(self, dev: LIODevice) -> None:
        dev.ch_on(8, 300)
        with pytest.raises(DeviceError) as e:
            dev.command("U")
        assert e.value.code == ErrCode.REFUSED


class TestOptics:
    def test_signatures(self, dev: LIODevice) -> None:
        m3, m8, m13, m15, m16 = (dev.meas(h, n=4) for h in (3, 8, 13, 15, 16))
        assert m3.net("opt101") > 1000 and abs(m3.net("ingaas")) < 30
        assert m8.net("opt101") > 1000 and m8.net("ingaas") > 1000
        assert m13.net("ingaas") > 1000 and abs(m13.net("opt101")) < 30
        assert 15 < m15.net("ingaas") < 100
        assert abs(m16.net("ingaas")) < 30
        assert m3.t_on_ms > 0

    def test_unfitted_hole_is_dark(self, dev: LIODevice) -> None:
        m = dev.meas(10, n=4)
        assert abs(m.net("ingaas")) < 30 and abs(m.net("opt101")) < 30

    def test_watchdog_clamp_and_event(self, dev: LIODevice, cfg: HwConfig) -> None:
        until = dev.ch_on(3, 60000)
        assert until == cfg.limits["wdt_a_ms"]
        ev = dev.wait_event("WDT", timeout=3)
        assert ev is not None and ev.fields.as_int("ch") == 3
        assert dev.status().as_int("wdt_trips") == 1

    def test_timer_off_event(self, dev: LIODevice) -> None:
        dev.ch_on(12, 300)
        ev = dev.wait_event("OFF", timeout=1)
        assert ev is not None and ev.fields.as_int("on_ms") == 300

    def test_single_channel_invariant(self, dev: LIODevice) -> None:
        dev.sr_raw(0x0081)
        with pytest.raises(DeviceError) as e:
            dev.ce(1, True)
        assert e.value.code == ErrCode.REFUSED
        dev.sr_raw(0x0080)
        with pytest.raises(DeviceError):
            dev.ce(2, True)  # hole 8 is RAIL A
        dev.ce(1, True)
        assert dev.status().as_int("ch") == 8
        dev.ce(1, False)
        assert dev.status().as_int("ce1") == 0

    def test_sr_raw_keeps_ce_low(self, dev: LIODevice) -> None:
        dark = dev.adc_read(1, 8).mean
        dev.ch_on(8, 1000)
        dev.sr_raw(0xFFFF)
        st = dev.status()
        assert st.as_int("ce1") == 0 and st.as_int("mask") == 0xFFFF
        assert abs(dev.adc_read(1, 8).mean - dark) < 20

    def test_sweep(self, dev: LIODevice) -> None:
        sw = dev.sweep()
        assert [m.hole for m in sw.records] == list(range(1, 17))
        assert sw.dur_ms < 2500

    def test_meas_refused_beyond_watchdog(self, dev: LIODevice) -> None:
        dev.meas(3, settle_ms=500, n=64)  # ~1.7 s estimated: inside the 2 s limit
        dev.wdt_cfg("A", 500)
        with pytest.raises(DeviceError) as e:
            dev.meas(3, settle_ms=200, n=32)  # ~0.8 s estimated > 0.5 s
        assert e.value.code == ErrCode.REFUSED

    def test_adc_cfg_and_stream(self, dev: LIODevice) -> None:
        assert dev.adc_gain("2") == pytest.approx(0.0625)
        dev.adc_gain("1")
        dev.adc_rate(860)
        s = dev.adc_stream(1, 40, 0, led=(3, 4, 28))
        assert len(s) == 40
        lit = [x.raw for x in s[5:28]]
        dark = [x.raw for x in s[:4]]
        assert min(lit) > max(dark) + 1000
        with pytest.raises(DeviceError):
            dev.adc_gain("3")
        with pytest.raises(DeviceError):
            dev.adc_rate(100)

    def test_short_stream_samples_at_the_adc_rate(self, dev: LIODevice) -> None:
        """n <= stream_buf_n is captured first (firmware STREAM_BUF_N): no serial pacing."""
        dev.adc_rate(860)
        n = dev.cfg.limits["stream_buf_n"]
        s = dev.adc_stream(1, n)
        dts = sorted(b.t_us - a.t_us for a, b in itertools.pairwise(s))
        conv_us = 1e6 / 860 + dev.cfg.sim.num("i2c_overhead_s") * 1e6
        assert dts[len(dts) // 2] == pytest.approx(conv_us, rel=0.02)

    def test_long_stream_is_paced_by_the_serial_line(self, dev: LIODevice) -> None:
        """A live stream at 860 SPS cannot print a ~32-byte line per 1.36 ms at 115200."""
        dev.adc_rate(860)
        n = dev.cfg.limits["stream_buf_n"] + 52
        s = dev.adc_stream(1, n)
        assert len(s) == n
        late = sorted(b.t_us - a.t_us for a, b in itertools.pairwise(s[60:]))
        line_us = (len("# S i=99 t_us=123456 raw=200") + 2) * 10 / 115200 * 1e6
        assert late[len(late) // 2] == pytest.approx(line_us, rel=0.1)

    def test_send_raw_returns_unsequenced_response(self, dev: LIODevice) -> None:
        r = dev.send_raw(b"@7 PING\n", 1.0)
        assert r is not None and r.ok and r.seq == 7
        r = dev.send_raw(("X" * 80 + "\n").encode(), 1.0)
        assert r is not None and r.code == ErrCode.OVERFLOW and r.seq is None
        assert dev.send_raw(b"", 0.1) is None

    def test_stream_led_schedule_checked(self, dev: LIODevice) -> None:
        with pytest.raises(DeviceError) as e:
            dev.adc_stream(1, 400, 10, led=(3, 0, 300))  # 3 s > RAIL A watchdog
        assert e.value.code == ErrCode.REFUSED

    def test_i2c_and_loop(self, dev: LIODevice) -> None:
        assert dev.i2c_scan() == [0x48]
        f = dev.loop_test()
        assert f.as_int("fitted") == 0 and f.as_str("status") == "not_fitted"

    def test_wdt_cfg(self, dev: LIODevice) -> None:
        assert dev.wdt_cfg("A", 1000).as_int("ms") == 1000
        with pytest.raises(DeviceError):
            dev.wdt_cfg("A", 6000)
        assert dev.ch_on(3) == 1000


class TestMotors:
    def test_arm_rules(self, dev: LIODevice) -> None:
        with pytest.raises(DeviceError) as e:
            dev.motor_step(1, 64)
        assert e.value.code == ErrCode.REFUSED
        with pytest.raises(DeviceError):
            dev.command("MOTOR ARM 0001" if dev.info().as_int("arm_token") != 1 else "MOTOR ARM 2")
        dev.motor_arm()
        dev.motor_step(1, 64, 3)
        ev = dev.wait_motor_done(1, 5)
        assert ev is not None and ev.fields.as_int("pos") == 64
        with pytest.raises(DeviceError):
            dev.motor_step(1, 5000)

    def test_arm_expires(self, dev: LIODevice, cfg: HwConfig) -> None:
        dev.motor_arm()
        for _ in range(7):  # keep the link alive so the failsafe does not fire
            dev.sleep(cfg.limits["arm_ms"] / 1000 / 6)
            dev.ping()
        with pytest.raises(DeviceError):
            dev.motor_step(1, 10)

    def test_stop_is_fast(self, dev: LIODevice) -> None:
        dev.motor_arm()
        dev.motor_step(2, 2048, 5)
        dev.sleep(0.5)
        t0 = dev.now()
        f = dev.motor_stop()
        assert dev.now() - t0 < 0.05
        assert 0 < f.as_int("pos2") < 2048
        assert dev.status().as_str("motor2") == "idle"

    def test_motor_refused_while_lit(self, dev: LIODevice) -> None:
        dev.motor_arm()
        dev.ch_on(8, 500)
        with pytest.raises(DeviceError) as e:
            dev.motor_step(1, 10)
        assert e.value.code == ErrCode.REFUSED

    def test_release(self, dev: LIODevice) -> None:
        dev.motor_release(1)
        dev.motor_release()


class TestSafety:
    def test_comms_failsafe(self, dev: LIODevice, cfg: HwConfig) -> None:
        dev.ch_on(12, 5000)
        dev.motor_arm()  # armed + lit, then silence
        ev = dev.wait_event("FAILSAFE", timeout=cfg.limits["comms_ms"] / 1000 + 1)
        assert ev is not None
        st = dev.status()
        assert st.as_int("armed") == 0 and st.as_int("ch") == 0
        assert st.as_int("failsafe_trips") == 1

    def test_no_failsafe_when_idle(self, dev: LIODevice) -> None:
        dev.sleep(30)
        assert dev.status().as_int("failsafe_trips") == 0

    def test_context_manager_turns_off_on_error(self, cfg: HwConfig) -> None:
        d = make(cfg)
        sim = sim_of(d)
        with pytest.raises(RuntimeError), d:
            d.ch_on(3, 1500)
            d.motor_arm()
            raise RuntimeError("boom")
        assert sim.lit_hole() == 0 and not sim._any_ce()

    def test_no_response_timeout(self, cfg: HwConfig) -> None:
        with make(cfg, "comms_drop") as d, pytest.raises(NoResponse):
            for _ in range(30):
                d.ping()


# --------------------------------------------------------- fault physics


def meas(cfg: HwConfig, faults: str, hole: int, **kw: bool) -> tuple[int, int]:
    with make(cfg, faults, **kw) as d:
        m = d.meas(hole, n=4)
        return m.net("opt101"), m.net("ingaas")


class TestFaultPhysics:
    def test_no_adc(self, cfg: HwConfig) -> None:
        with make(cfg, "no_adc") as d:
            assert d.banner is not None and d.banner.fields.as_int("adc_ok") == 0
            assert d.i2c_scan() == []
            with pytest.raises(DeviceError) as e:
                d.meas(3)
            assert e.value.code == ErrCode.ADC
            assert d.status().as_int("faults") & 0x01

    def test_dead_channel(self, cfg: HwConfig) -> None:
        opt, _ = meas(cfg, "dead_channel:3", 3)
        assert abs(opt) < 30

    def test_swapped_same_rail_shows_other_signature(self, cfg: HwConfig) -> None:
        opt, ing = meas(cfg, "swapped:3,8", 3)
        assert ing > 1000 and opt > 1000  # hole 3 now looks like 850 nm

    def test_swapped_across_rails_is_dark(self, cfg: HwConfig) -> None:
        # the swapped MOSFET's LED sits on the other rail, whose driver is off
        assert all(abs(x) < 30 for x in meas(cfg, "swapped:3,13", 3))
        assert all(abs(x) < 30 for x in meas(cfg, "swapped:3,13", 13))

    def test_stuck_on_low_vf_steals_current(self, cfg: HwConfig) -> None:
        with make(cfg, "stuck_on:5") as d:
            m1, m5 = d.meas(1, n=4), d.meas(5, n=4)
        assert m1.net("opt101") == pytest.approx(m5.net("opt101"), rel=0.05)

    def test_stuck_on_rail_b_lights_empty_hole(self, cfg: HwConfig) -> None:
        _, ing = meas(cfg, "stuck_on:12", 10)
        assert ing > 1000

    @pytest.mark.parametrize(("fault", "hole"), [("rail_a_dead", 3), ("rail_b_dead", 13)])
    def test_dead_rail(self, cfg: HwConfig, fault: str, hole: int) -> None:
        opt, ing = meas(cfg, fault, hole)
        assert abs(opt) < 30 and abs(ing) < 30

    def test_ce_inverted(self, cfg: HwConfig) -> None:
        with make(cfg, "ce_inverted") as d:
            dark = d.adc_read(1, 8).mean
            d.sr_raw(0x0004)  # hole 3 selected, CE low -> lit when inverted
            assert d.adc_read(1, 8).mean > dark + 1000

    def test_reversed_ingaas(self, cfg: HwConfig) -> None:
        _, ing = meas(cfg, "reversed_ingaas", 13)
        assert ing < -1000

    def test_no_neg_rail_erratic(self, cfg: HwConfig) -> None:
        with make(cfg, "no_neg_rail") as d:
            r = d.adc_read(0, 64)
            assert r.std is not None and r.std > 500

    def test_tia_saturated(self, cfg: HwConfig) -> None:
        with make(cfg, "tia_saturated") as d:
            assert d.meas(12, n=2).lit0 == d.meas(13, n=2).lit0 == 28000

    def test_opt101_no_feedback(self, cfg: HwConfig) -> None:
        with make(cfg, "opt101_no_feedback") as d:
            assert d.adc_read(1, 8).mean > 29000
            assert abs(d.meas(3, n=2).net("opt101")) < 10

    def test_noisy_adc(self, cfg: HwConfig) -> None:
        with make(cfg, "noisy_adc") as d:
            r = d.adc_read(1, 64)
            assert r.std is not None and r.std > 40

    def test_slow_settle(self, cfg: HwConfig) -> None:
        with make(cfg, "slow_settle") as d:
            fast = d.meas(3, settle_ms=200, n=1).net("opt101")
            slow = d.meas(3, settle_ms=0, n=1).net("opt101")
            assert slow < 0.95 * fast

    def test_chain_break(self, cfg: HwConfig) -> None:
        with make(cfg, "chain_break", loop_jumper=True) as d:
            assert abs(d.meas(13, n=2).net("ingaas")) < 30
            assert d.meas(3, n=2).net("opt101") > 1000
            f = d.loop_test()
            assert f.as_int("fitted") == 1 and f.as_int("pass") == 0

    def test_loop_jumper_healthy(self, cfg: HwConfig) -> None:
        with make(cfg, loop_jumper=True) as d:
            f = d.loop_test()
            assert f.as_int("pass") == 1 and f.as_int("bits_bad") == 0
        assert len(loop_patterns()) == 32

    def test_motor_stall(self, cfg: HwConfig) -> None:
        with make(cfg, "motor_stall") as d:
            d.motor_arm()
            d.motor_step(1, 64)
            d.wait_motor_done(1, 5)
            sim = sim_of(d)
            assert d.status().as_int("pos1") == 64  # open loop: firmware thinks it moved
            assert sim.motors[0].physical == 0

    def test_chamber_open_raises_dark(self, cfg: HwConfig) -> None:
        with make(cfg) as d:
            closed = d.adc_read(1, 8).mean
            sim_of(d).chamber_open = True
            assert d.adc_read(1, 8).mean > closed + 1000

    def test_unconnected_adc_input(self, dev: LIODevice) -> None:
        r = dev.adc_read(2, 4)
        assert r.ch == 2


class TestDuty:
    def test_cooldown_inserted(self, cfg: HwConfig) -> None:
        with make(cfg) as d:
            assert d.duty is not None
            for _ in range(60):  # 60 x ~25 ms = 1.5 s on hole 3 > 1 s / min budget
                d.meas(3)
            assert d.duty.cooldowns and d.duty.total_cooldown_s > 0
            assert d.duty.used_ms(3, d.now()) <= 1000 + 50

    def test_over_budget_recorded(self, cfg: HwConfig) -> None:
        with make(cfg) as d:
            assert d.duty is not None
            d.ch_on(3, 1500)
            d.wait_event("OFF", 3)
            assert d.duty.over_budget and d.duty.over_budget[0][0] == 3
            d.ch_on(3, 200)  # must wait for the window to clear
            assert d.duty.cooldowns

    def test_ch_on_budgets_the_clamped_time(self, cfg: HwConfig) -> None:
        """Asking for 60 s plans only what the watchdog allows (here 100 ms)."""
        with make(cfg) as d:
            assert d.duty is not None
            d.meas(3)
            d.wdt_cfg("A", 100)
            d.ch_on(3, 60000)
            assert not d.duty.cooldowns

    def test_duty_disabled(self, cfg: HwConfig) -> None:
        d = LIODevice(SimTransport(SimulatedLIO(cfg)), cfg, duty=False)
        with d:
            for _ in range(50):
                d.meas(3)
            assert d.duty is None


class TestPowerWake:
    def test_wake_on_open_and_at_most_once_per_interval(self, cfg: HwConfig) -> None:
        sim = SimulatedLIO(cfg)
        with LIODevice(SimTransport(sim), cfg) as d:
            assert sim.wakes == 1  # opening the port
            assert not d.keep_awake()  # too soon
            d.sleep(cfg.section.num("power.interval_s") + 0.1)
            assert d.keep_awake() and sim.wakes == 2

    def test_no_motion_and_coils_released(self, cfg: HwConfig) -> None:
        sim = SimulatedLIO(cfg)
        with LIODevice(SimTransport(sim), cfg) as d:
            assert d.power_wake(500) == 500
            st = d.status()
            assert (st.as_int("pos1"), st.as_int("pos2")) == (0, 0)
            assert st.as_str("motor1") == "idle" and st.as_str("motor2") == "idle"

    def test_refused_while_lit_and_bounded(self, cfg: HwConfig) -> None:
        sim = SimulatedLIO(cfg)
        with LIODevice(SimTransport(sim), cfg) as d:
            d.ch_on(3, 1000)
            with pytest.raises(DeviceError) as e:
                d.power_wake()
            assert e.value.code == 3
            d.off()
            d.sleep(cfg.section.num("power.interval_s") + 0.1)
            d.ch_on(3, 1000)
            assert not d.keep_awake()  # skipped while lit, never raises
            d.off()
            with pytest.raises(DeviceError) as e:
                d.power_wake(cfg.limits["wake_ms_max"] + 1)
            assert e.value.code == 2

    def test_firmware_without_power_wake(self, cfg: HwConfig) -> None:
        d = LIODevice(SimTransport(SimulatedLIO(cfg)), cfg)

        def unknown(ms: int | None = None) -> int:
            raise DeviceError("POWER WAKE", 1, "unknown command")

        d.power_wake = unknown  # type: ignore[method-assign]
        with d:  # opening still works
            assert not d.keep_awake(force=True)
            assert not d._wake_supported  # never asked again

    def test_bank_a_asleep_until_woken(self, cfg: HwConfig) -> None:
        sim = SimulatedLIO(cfg, Faults.parse("bank_a_asleep"))
        d = LIODevice(SimTransport(sim), cfg)
        d._wake_supported = False
        with d:
            assert d.info().as_int("adc_ok") == 0
            d._wake_supported = True
            assert d.keep_awake(force=True)
            assert d.info().as_int("adc_ok") == 1  # found again without a reset
            assert d.adc_read(1, 4).n == 4
