"""Simulator height model for the diagnostic sweep (LIO-SW-SCAN-001 §9, milestone S1).

The physics each sweep metric will rely on: optics vs height, sample reflectance,
electrical coupling, leakage, hum, ambient light, mechanics, and every new fault.
Detection by the sweep's metrics is tested in later milestones (fault matrix).
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from lio.config import HwConfig
from lio.device import DeviceError, LIODevice
from lio.sim import Faults, SimulatedLIO
from lio.transport import SimTransport

pytestmark = [pytest.mark.unit]
LSB = 0.125  # mV per count at GAIN_ONE


@contextmanager
def rig(
    cfg: HwConfig, faults: str | None = None, sample: str = "empty"
) -> Iterator[tuple[LIODevice, SimulatedLIO]]:
    sim = SimulatedLIO(cfg, Faults.parse(faults))
    sim.sample = sample
    dev = LIODevice(SimTransport(sim), cfg)
    dev.open()
    try:
        yield dev, sim
    finally:
        dev.close()


def move_both(dev: LIODevice, steps: int) -> None:
    """Both motors by ``steps`` with exact step moves (chunks of 2048)."""
    left = steps
    while left:
        n = max(-2048, min(2048, left))
        dev.motor_arm()
        dev.motor_step(1, n, 15)
        dev.motor_step(2, n, 15)
        for m in (1, 2):
            assert dev.wait_motor_done(m, 60) is not None
        left -= n


def jog_to(dev: LIODevice, target: int, speed: int = 1000) -> None:
    """Continuous jog of both motors (renewed) to within a few hundred half-steps of
    ``target`` (firmware positions), then exact finish: fast on the virtual clock."""
    pos = dev.status().as_int("pos1")
    if target == pos:
        return
    cmd = "U" if target > pos else "D"
    dev.command(f"VS{speed}")
    dev.command(cmd)
    renewed = pos
    while True:
        p = dev.status().as_int("pos1")
        if abs(target - p) <= 600:
            dev.command("S")
            break
        if abs(p - renewed) >= 1024:
            dev.command(cmd)
            renewed = p
        dev.sleep(0.2)
    dev.sleep(0.1)
    st = dev.status()
    for m in (1, 2):
        rest = target - st.as_int(f"pos{m}")
        if rest:
            dev.motor_arm()
            dev.motor_step(m, rest, 15)
            assert dev.wait_motor_done(m, 30) is not None


def net(dev: LIODevice, hole: int, det: str, n: int = 4) -> float:
    return float(dev.meas(hole, 8, n).net(det))


def tone(dev: LIODevice, ch: int, f: float, n: int = 48) -> float:
    """Amplitude (counts) at frequency f in a buffered stream at the fastest rate."""
    dev.adc_rate(860)
    s = dev.adc_stream(ch, n, 0)
    t = [x.t_us / 1e6 for x in s]
    v = [float(x.raw) for x in s]
    m = sum(v) / len(v)
    a = sum((x - m) * math.cos(2 * math.pi * f * ti) for x, ti in zip(v, t, strict=True))
    b = sum((x - m) * math.sin(2 * math.pi * f * ti) for x, ti in zip(v, t, strict=True))
    return 2 * math.hypot(a, b) / len(v)


def dark(dev: LIODevice, ch: int, n: int = 16) -> float:
    dev.adc_rate(128)
    return dev.adc_read(ch, n).mean


class TestMotionProfile:
    def test_renewed_jog_keeps_cruising(self, cfg: HwConfig) -> None:
        """D4: a renewed jog does not slow down (firmware >= 2.2.1)."""
        with rig(cfg) as (dev, _):
            dev.command("VS500")
            dev.command("D")
            t0 = dev.now()
            for _ in range(20):  # renew every ~1 s: 20 s at about 500 half-steps/s
                dev.sleep(1.0)
                dev.command("D")
            p = dev.status().as_int("pos1")
            dev.command("S")
            elapsed = dev.now() - t0
            # ramp 2 s to 500 (500 half-steps lost vs cruise), then cruise
            assert abs(-p - (500 * elapsed - 500)) < 0.03 * 500 * elapsed, (p, elapsed)

    def test_reset_keeps_the_physical_position(self, cfg: HwConfig) -> None:
        with rig(cfg) as (dev, sim):
            move_both(dev, -3000)
            dev.reset()
            assert dev.status().as_int("pos1") == 0
            assert sim.motors[0].physical == -3000 and sim.height_at(sim.clock) == -3000


class TestOptics:
    def test_response_follows_height(self, cfg: HwConfig) -> None:
        with rig(cfg) as (dev, sim):
            top = net(dev, 8, "opt101")
            jog_to(dev, -330000)
            low = net(dev, 8, "opt101")
            assert low / top == pytest.approx(sim.g_rel(8, -330000), rel=0.05)
            assert low / top > 2.5

    def test_sample_reflectance(self, cfg: HwConfig) -> None:
        with rig(cfg, sample="empty") as (dev, _):
            empty = net(dev, 4, "opt101")
        with rig(cfg, sample="white_ptfe") as (dev, _):
            white = net(dev, 4, "opt101")
        with rig(cfg, sample="black_cup") as (dev, _):
            black = net(dev, 4, "opt101")
        assert white / empty == pytest.approx(1.5 + 0.01, rel=0.05)
        assert black / empty < 0.1  # 0.05 reflectance + 0.01 stray

    def test_window_blocked_and_stray_light(self, cfg: HwConfig) -> None:
        with rig(cfg) as (dev, _):
            ok = net(dev, 13, "ingaas")
        with rig(cfg, "window_blocked:0.1") as (dev, _):
            blocked = net(dev, 13, "ingaas")
        assert blocked / ok == pytest.approx((0.1 + 0.01) / 1.01, rel=0.1)
        with rig(cfg, "stray_light:0.2", sample="black_cup") as (dev, _):
            stray = net(dev, 4, "opt101")
        with rig(cfg, sample="black_cup") as (dev, _):
            clean = net(dev, 4, "opt101")
        assert stray > 3 * clean

    def test_wrong_and_swapped_leds(self, cfg: HwConfig) -> None:
        with rig(cfg) as (dev, _):
            assert net(dev, 16, "opt101") < 20  # 1850 nm: silicon is blind
            base9 = net(dev, 9, "opt101")
        with rig(cfg, "wrong_led:16=630") as (dev, _):
            assert net(dev, 16, "opt101") > 200
        with rig(cfg, "led_swapped:9,16") as (dev, _):
            assert net(dev, 9, "opt101") < 20  # the 1850 nm LED now sits in hole 9
            assert net(dev, 16, "opt101") == pytest.approx(base9, rel=0.1)


class TestElectrical:
    def test_pd_disconnected(self, cfg: HwConfig) -> None:
        """15 Nov: flat ~70-90 counts on every hole, no wavelength or height dependence."""
        with rig(cfg, "pd_disconnected") as (dev, _):
            a = net(dev, 1, "ingaas")  # 395 nm: the InGaAs cannot see it
            b = net(dev, 13, "ingaas")  # 1550 nm
            assert 50 < a < 100 and 80 < b < 110  # rail A 30 mA, rail B 45 mA x 2 counts/mA
            jog_to(dev, -330000)
            assert net(dev, 13, "ingaas") == pytest.approx(b, abs=12)  # no height dependence
            assert dark(dev, 0) < -100  # -22 nA x 1 MΩ = -22 mV, plus the healthy +5 mV

    def test_ground_shift_scales_with_rail_current(self, cfg: HwConfig) -> None:
        with rig(cfg) as (dev, _):
            a0, b0 = net(dev, 1, "ingaas"), net(dev, 12, "ingaas")
        with rig(cfg, "ground_shift:0.2") as (dev, _):
            a1, b1 = net(dev, 1, "ingaas"), net(dev, 12, "ingaas")
        assert a1 - a0 == pytest.approx(0.2 * 30 / LSB, rel=0.15)  # rail A 30 mA -> 48 counts
        assert b1 - b0 == pytest.approx(0.2 * 45 / LSB, rel=0.15)  # rail B 45 mA -> 72 counts

    def test_leakage_and_drift(self, cfg: HwConfig) -> None:
        with rig(cfg) as (dev, _):
            d0 = dark(dev, 0)
        with rig(cfg, "leakage:20") as (dev, _):
            assert dark(dev, 0) - d0 == pytest.approx(-20 / LSB, abs=6)
        with rig(cfg, "leakage_drift:10") as (dev, _):
            first = dark(dev, 0)
            dev.sleep(1800)  # half an hour: -5 nA
            assert dark(dev, 0) - first == pytest.approx(-5 / LSB, abs=6)

    def test_mains_hum_and_flicker(self, cfg: HwConfig) -> None:
        with rig(cfg) as (dev, _):
            quiet = tone(dev, 0, 60)
        with rig(cfg, "mains_hum:8") as (dev, _):
            loud = tone(dev, 0, 60)
        assert quiet < 6 and loud == pytest.approx(8 / LSB, rel=0.35)
        with rig(cfg, "room_flicker") as (dev, _):
            assert tone(dev, 1, 120) > 15  # OPT101 sees 120 Hz room light

    def test_coil_emi_only_while_moving(self, cfg: HwConfig) -> None:
        with rig(cfg, "coil_emi") as (dev, _):
            dev.adc_rate(860)
            rest = [x.raw for x in dev.adc_stream(0, 48, 0)]
            dev.command("VS500")
            dev.command("D")
            moving = [x.raw for x in dev.adc_stream(0, 48, 0)]
            dev.command("S")

        def sd(v: list[int]) -> float:
            m = sum(v) / len(v)
            return math.sqrt(sum((x - m) ** 2 for x in v) / len(v))

        assert sd(moving) > 5 * sd(rest)


class TestAmbient:
    def test_leak_below_onset(self, cfg: HwConfig) -> None:
        with rig(cfg, "ambient_leak:-200000") as (dev, _):
            top = dark(dev, 1)
            jog_to(dev, -400000)
            low = dark(dev, 1)
        assert low - top > 300  # ~400 counts at full leak on the OPT101


class TestMechanics:
    def test_backlash_on_reversal(self, cfg: HwConfig) -> None:
        with rig(cfg, "backlash:400") as (dev, sim):
            move_both(dev, -10000)
            move_both(dev, +10000)  # reversal: 400 half-steps of slack first
            assert dev.status().as_int("pos1") == 0
            assert sim.height_at(sim.clock) == pytest.approx(-400)

    def test_step_loss_on_one_side_moving_up(self, cfg: HwConfig) -> None:
        with rig(cfg, "step_loss:2,4200") as (dev, sim):
            move_both(dev, -42000)
            move_both(dev, +42000)  # 1/10 of the travel up: side 2 loses 420
            assert sim.motors[0].physical == pytest.approx(0)
            assert sim.motors[1].physical == pytest.approx(-420, abs=0.5)


class TestLinkFaults:
    def test_mid_run_boot(self, cfg: HwConfig) -> None:
        with rig(cfg, "mid_run_boot:30") as (dev, sim):
            move_both(dev, -2000)
            boots = []
            dev.add_listener(lambda e: boots.append(e) if e.is_boot else None)
            dev.sleep(40)
            dev.status()
            assert boots, "no # BOOT after the mid-run reset"
            assert dev.status().as_int("pos1") == 0  # counters restarted
            assert sim.height_at(sim.clock) == -2000  # the stage did not move

    def test_adc_dropout(self, cfg: HwConfig) -> None:
        with rig(cfg, "adc_dropout:10") as (dev, _), pytest.raises(DeviceError) as e:
            for _ in range(10):
                dev.meas(4, 8, 4)
        assert e.value.code == 4

    def test_rail_miswired(self, cfg: HwConfig) -> None:
        with rig(cfg) as (dev, _):
            ok = net(dev, 12, "ingaas")
        with rig(cfg, "rail_miswired:12") as (dev, _):
            bad = net(dev, 12, "ingaas")  # CE2 raised, but the LED hangs on rail A
        assert ok > 1000 and bad < 0.05 * ok


class TestDebugStates:
    """Firmware 2.5.0 DBG STATE: atomic, one CE, bounded, refused while moving."""

    def test_wrong_rail_is_dark_unless_miswired(self, cfg: HwConfig) -> None:
        with rig(cfg) as (dev, sim):
            f = dev.dbg_state("wrong_rail", 12, 8, 2)
            assert f.as_int("ce") == 1 and abs(f.as_int("lit0") - f.as_int("dark0")) < 30
            assert not sim._light_since and dev.status().as_int("mask") == 0  # all off after
        with rig(cfg, "rail_miswired:12") as (dev, _):
            f = dev.dbg_state("wrong_rail", 12, 8, 2)
            assert f.as_int("lit0") - f.as_int("dark0") > 1000

    def test_ce_only_and_refusals(self, cfg: HwConfig) -> None:
        with rig(cfg) as (dev, _):
            f = dev.dbg_state("ce_only", 2, 8, 2)
            assert f.as_int("ch") == 0 and f.as_str("state") == "ce_only"
            with pytest.raises(DeviceError) as e:
                # Simulator fault injection: bypass public light gate (D01).
                dev._command_unguarded("DBG STATE CE_ONLY 3")
            assert e.value.code == 2
            dev.wdt_cfg("B", 50)  # hole 4 is on RAIL A: its wrong-rail state raises CE2
            with pytest.raises(DeviceError) as e:
                # Typed dbg_state would raise WDT; unguarded proves firmware refuse.
                dev._command_unguarded("DBG STATE WRONG_RAIL 4 45 4")
            assert e.value.code == 3 and "watchdog" in str(e.value)
            dev.command("VS500")
            dev.command("D")
            with pytest.raises(DeviceError) as e:
                dev._command_unguarded("DBG STATE CE_ONLY 1")
            assert e.value.code == 5
            dev.command("S")

    def test_older_firmware_has_no_dbg(self, cfg: HwConfig) -> None:
        import copy as _copy

        from lio.config import parse_config

        data = _copy.deepcopy(cfg.data)
        data["sim"]["firmware"] = "2.4.0"
        with rig(parse_config(data, cfg.path)) as (dev, _):
            assert "debug_states" not in dev.info(refresh=True).values
            with pytest.raises(DeviceError) as e:
                # Simulator fault injection: public command() refuses light-capable DBG.
                dev._command_unguarded("DBG STATE CE_ONLY 1")
            assert e.value.code == 1


class TestMainsIntegration:
    """Firmware 2.5.1 ADC CFG MAINS: readings integrate whole mains periods."""

    def test_hum_cancels_in_readings(self, cfg: HwConfig) -> None:
        def spread(mains: int) -> float:
            with rig(cfg, "mains_hum:8") as (dev, _):
                if mains:
                    dev.adc_mains(mains)
                v = []
                for i in range(30):
                    v.append(dev.meas(13, 8, 1 if mains else 2).net("ingaas"))
                    dev.sleep(0.137 * (i % 7))
                m = sum(v) / len(v)
                return math.sqrt(sum((x - m) ** 2 for x in v) / len(v))

        assert spread(60) < 0.5 * spread(0)

    def test_info_reset_and_old_firmware(self, cfg: HwConfig) -> None:
        import copy as _copy

        from lio.config import parse_config

        with rig(cfg) as (dev, _):
            dev.adc_mains(60)
            assert dev.info(refresh=True).as_int("mains") == 60 and dev.mains_hz == 60
            dev.reset()
            assert dev.mains_hz == 0 and dev.info(refresh=True).as_int("mains") == 0
            with pytest.raises(DeviceError):
                dev.command("ADC CFG MAINS 55")
        data = _copy.deepcopy(cfg.data)
        data["sim"]["firmware"] = "2.5.0"
        with rig(parse_config(data, cfg.path)) as (dev, _):
            assert "mains" not in dev.info(refresh=True).values
            with pytest.raises(DeviceError):
                dev.adc_mains(60)
