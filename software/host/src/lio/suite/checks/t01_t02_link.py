"""T01 host environment and discovery; T02 link and protocol (plan §6)."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import sys

from lio.analysis import percentile, stats
from lio.config import ConfigError, load_config
from lio.device import NoResponse
from lio.protocol import ErrCode, encode, fw_compatible
from lio.results import Status
from lio.suite.core import Recorder, SuiteContext, register
from lio.transport import list_ports, pick_port

DEPENDENCIES = ("pyserial", "pyyaml", "numpy", "matplotlib", "jinja2")


# ------------------------------------------------------------------------ T01


@register("T01.1", "Python and dependency versions")
def t01_1(ctx: SuiteContext, rec: Recorder) -> None:
    versions: dict[str, str | None] = {}
    for dist in DEPENDENCIES:
        try:
            versions[dist] = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            versions[dist] = None
    rec.measure(python=platform.python_version(), platform=platform.platform(), **versions)
    rec.check(
        "python",
        "Python version",
        sys.version_info >= (3, 10),
        platform.python_version(),
        ">= 3.10",
    )
    for dist, v in versions.items():
        rec.check(dist, f"{dist} installed", v is not None, v or "missing", "importable")


@register("T01.2", "Serial port discovery")
def t01_2(ctx: SuiteContext, rec: Recorder) -> None:
    usb_ids = [tuple(x) for x in ctx.cfg.section.raw("link.usb_ids")]
    ports = list_ports([(int(v), int(p), str(label)) for v, p, label in usb_ids])
    found = [{"device": p.device, "vid": p.vid, "pid": p.pid, "chip": p.label} for p in ports]
    rec.measure(ports=found)
    if ctx.is_sim:
        rec.add(
            "discovery",
            "Port discovery",
            Status.PASS,
            f"simulator target; {len(ports)} serial port(s) on this host recorded only",
        )
        return
    chosen = next((p for p in ports if p.device == ctx.target), None)
    auto = pick_port(ports)
    rec.measure(auto_pick=auto.device if auto else None)
    exists = chosen is not None or os.path.exists(ctx.target)
    rec.check(
        "port",
        "Selected port is present",
        exists,
        f"{ctx.target}: " + ("present" if exists else "not found"),
        "--lio-port names an existing serial port",
    )
    if exists:
        rec.check(
            "chip",
            "USB-serial chip recognised",
            chosen is not None and chosen.likely_lio,
            (
                f"VID:PID {chosen.vid or 0:04X}:{chosen.pid or 0:04X} ({chosen.label or 'unknown'})"
                if chosen is not None
                else "not a USB serial adapter (e.g. a pseudo-terminal)"
            ),
            "one of link.usb_ids",
            warn=True,
        )


@register("T01.3", "Configuration loads and is self-consistent")
def t01_3(ctx: SuiteContext, rec: Recorder) -> None:
    rec.measure(config=str(ctx.cfg.path), sha256=ctx.cfg.sha256, provisional=ctx.cfg.provisional)
    try:
        again = load_config(ctx.cfg.path)
    except ConfigError as e:
        rec.check("load", "Config validates", False, str(e))
        return
    rec.check("load", "Config validates", True, f"{ctx.cfg.path.name} sha256 {again.sha256[:12]}")
    rec.check("holes", "16 holes", len(again.channels) == 16, f"{len(again.channels)} entries")
    rails = {r: again.rail_holes(r) for r in ("A", "B")}
    rec.check(
        "rails",
        "Rails split A = 1-9, B = 10-16",
        rails["A"] == tuple(range(1, 10)) and rails["B"] == tuple(range(10, 17)),
        f"A={list(rails['A'])} B={list(rails['B'])}",
    )
    # Provisional thresholds are expected until M6; recorded, not judged.
    rec.measure(thresholds_provisional=again.provisional)


# ------------------------------------------------------------------------ T02


@register("T02.1", "Port open and boot banner")
def t02_1(ctx: SuiteContext, rec: Recorder) -> None:
    dev = ctx.dev
    timeout = ctx.cfg.section.num("link.boot_timeout_s")
    banner = dev.banner
    if banner is None:
        rec.check("banner", "Boot banner received", False, "no banner recorded at open")
        return
    boot_s = dev.boot_s if dev.boot_s is not None else float("nan")
    rec.measure(boot_s=boot_s, banner=banner.raw)
    rec.check(
        "banner",
        "Boot banner within the timeout",
        boot_s <= timeout,
        f"{boot_s:.2f} s",
        f"<= {timeout:g} s",
        boot_s=boot_s,
    )
    f = banner.fields
    rec.check(
        "identity",
        "Banner identifies LIO firmware",
        f.as_str("name") == ctx.cfg.fw_name and "fw" in f and "proto" in f,
        banner.raw,
        f"name={ctx.cfg.fw_name}, fw and proto present",
    )


@register("T02.2", "PING round-trip latency")
def t02_2(ctx: SuiteContext, rec: Recorder) -> None:
    count = ctx.th.integer("link.ping_count")
    p99_max = ctx.th.num("link.ping_p99_ms")
    rtts: list[float] = []
    lost = 0
    for _ in range(count):
        try:
            rtts.append(ctx.dev.ping() * 1000.0)
        except NoResponse:
            lost += 1
    rec.check(
        "answered",
        "Every PING answered",
        lost == 0,
        f"{count - lost}/{count} answered",
        "all",
        lost=lost,
    )
    if not rtts:
        return
    p50, p99 = percentile(rtts, 50), percentile(rtts, 99)
    s = stats(rtts)
    rec.measure(rtt_ms=[round(r, 3) for r in rtts])
    rec.check(
        "p99",
        "p99 round trip",
        p99 < p99_max,
        f"median {p50:.2f} ms, p99 {p99:.2f} ms, max {s.max:.2f} ms",
        f"p99 < {p99_max:g} ms",
        median_ms=p50,
        p99_ms=p99,
        max_ms=s.max,
    )


INFO_KEYS = (
    "fw",
    "proto",
    "build",
    "adc_addr",
    "adc_ok",
    "gain",
    "rate",
    "settle_ms",
    "wdt_a_ms",
    "wdt_b_ms",
    "wdt_a_cap_ms",
    "wdt_b_cap_ms",
    "comms_ms",
    "arm_ms",
    "step_max",
    "jog_max",
    "jog_v_max",
    "jog_acc_max",
    "motion_armed",
    "arm_token",
    "hw_wdt",
)
# INFO field -> limits key in lio_hw.yaml
INFO_LIMITS = {
    "settle_ms": "settle_ms",
    "wdt_a_ms": "wdt_a_ms",
    "wdt_b_ms": "wdt_b_ms",
    "wdt_a_cap_ms": "wdt_a_cap_ms",
    "wdt_b_cap_ms": "wdt_b_cap_ms",
    "comms_ms": "comms_ms",
    "arm_ms": "arm_ms",
    "step_max": "step_max",
    "jog_max": "jog_max",
    "jog_v_max": "jog_v_max",
    "jog_acc_max": "jog_acc_max",
}


@register("T02.3", "INFO fields, versions and safety limits")
def t02_3(ctx: SuiteContext, rec: Recorder) -> None:
    f = ctx.dev.info(refresh=True)
    rec.measure(info=dict(f.values))
    missing = [k for k in INFO_KEYS if k not in f]
    rec.check(
        "fields",
        "INFO fields present",
        not missing,
        f"missing: {missing}" if missing else f"{len(INFO_KEYS)} fields",
        "all protocol-1 INFO fields",
    )
    if "fw" in f and "proto" in f:
        ok = fw_compatible(
            f.as_str("fw"), f.as_int("proto"), ctx.cfg.fw_min_version, ctx.cfg.fw_proto
        )
        rec.check(
            "version",
            "Firmware compatible with this host package",
            ok,
            f"fw {f.as_str('fw')} proto {f.as_int('proto')}",
            f">= {ctx.cfg.fw_min_version}, proto {ctx.cfg.fw_proto}",
        )
    for key, limit in INFO_LIMITS.items():
        if key not in f:
            continue
        want = ctx.cfg.limits[limit]
        got = f.as_int(key)
        rec.check(f"limit/{key}", f"{key} matches lio_hw.yaml", got == want, f"{got}", f"{want}")
    sec = ctx.cfg.section
    if "adc_addr" in f:
        addr = int(f.as_str("adc_addr"), 16)
        want_addr = sec.integer("adc.address")
        rec.check(
            "adc/addr",
            "ADC address matches lio_hw.yaml",
            addr == want_addr,
            f"0x{addr:02X}",
            f"0x{want_addr:02X}",
        )
    for key, setting in (("gain", "adc.gain"), ("rate", "adc.rate_sps")):
        if key in f:
            expected = str(sec.raw(setting))
            rec.check(
                f"adc/{key}",
                f"ADC {key} matches lio_hw.yaml",
                f.as_str(key) == expected,
                f.as_str(key),
                expected,
            )


@register("T02.4", "Robustness to bad input")
def t02_4(ctx: SuiteContext, rec: Recorder) -> None:
    dev = ctx.dev
    cases = (
        ("unknown", "Unknown command", "FROBNICATE", ErrCode.UNKNOWN),
        ("badarg", "Bad argument", "MEAS 99", ErrCode.BAD_ARG),
        ("missing", "Missing argument", "CH", ErrCode.BAD_ARG),
    )
    for sub, name, cmd, code in cases:
        r = dev.command(cmd, check=False).response
        rec.check(sub, name, (not r.ok) and r.code == int(code), r.raw, f"ERR code={int(code)}")
    line_max = ctx.cfg.limits["line_max"]
    long_line = "@0 PING " + "X" * line_max  # encode() refuses this, so build it by hand
    r2 = dev.send_raw((long_line + "\n").encode("ascii"), timeout=1.0)
    rec.check(
        "overflow",
        f"Line over {line_max} characters",
        r2 is not None and not r2.ok and r2.code == int(ErrCode.OVERFLOW),
        r2.raw if r2 else "no response",
        f"ERR code={int(ErrCode.OVERFLOW)}",
    )
    garbage = bytes(range(1, 32)).replace(b"\n", b"") + b"\xff\xfe\x80garbage\x00\r\n"
    dev.send_raw(garbage, timeout=0.5)  # any answer (or none) is acceptable
    dev.drain(0.1)
    try:
        dev.ping()
        alive = True
    except NoResponse:
        alive = False
    rec.check(
        "garbage",
        "Garbage bytes, then PING",
        alive,
        "PING OK" if alive else "no PING response after garbage",
        "PING still answered",
    )


@register("T02.5", "Sequence numbers and interleaved events")
def t02_5(ctx: SuiteContext, rec: Recorder) -> None:
    dev = ctx.dev
    seqs = (1, 4242, 99999)
    for s in seqs:
        r = dev.send_raw((encode("PING", s) + "\n").encode("ascii"), timeout=1.0)
        rec.check(
            f"seq/{s}",
            f"@{s} echoed",
            r is not None and r.ok and r.seq == s,
            r.raw if r else "no response",
            f"@{s} OK PING",
        )
    r0 = dev.send_raw(b"PING\n", timeout=1.0)
    rec.check(
        "noseq",
        "No @seq, none echoed",
        r0 is not None and r0.ok and r0.seq is None,
        r0.raw if r0 else "no response",
        "OK PING",
    )
    # Events between a command and its response (ADC STREAM emits "# S" lines).
    ctx.require_adc()
    n = 20
    reply = dev.command(f"ADC STREAM {ctx.adc_channel('opt101')} {n} 0", timeout=5.0)
    got = [e for e in reply.events if e.name == "S"]
    rec.check(
        "stream",
        "Response found after interleaved events",
        len(got) == n,
        f"{len(got)} '# S' events then OK",
        f"{n} events",
    )
    # Asynchronous event arriving between later commands (CH ON timer expiry).
    hole = ctx.th.ints("settling.holes")[0]
    dev.ch_on(hole, ms=ctx.cfg.limits["wdt_min_ms"])
    ok_pings = 0
    events_before = len(dev.events)
    for _ in range(10):
        dev.ping()
        ok_pings += 1
        dev.sleep(0.01)
    async_events = [e for _, e in dev.events[events_before:] if e.name in ("OFF", "WDT")]
    rec.check(
        "async",
        "Asynchronous '# OFF' does not desynchronise",
        ok_pings == 10 and len(async_events) == 1,
        f"{ok_pings}/10 PINGs matched; {len(async_events)} timer event(s) seen",
        "all PINGs answered in order, one '# OFF'",
    )


@register("T02.6", "RESET restores the boot state")
def t02_6(ctx: SuiteContext, rec: Recorder) -> None:
    dev = ctx.dev
    probe_ms = ctx.cfg.limits["wdt_min_ms"] * 4
    dev.wdt_cfg("A", probe_ms)
    t0 = dev.now()
    banner = dev.reset()
    dt = dev.now() - t0
    timeout = ctx.cfg.section.num("link.boot_timeout_s")
    rec.check(
        "banner",
        "Banner after RESET",
        banner.is_boot and dt <= timeout,
        f"{dt:.2f} s",
        f"<= {timeout:g} s",
    )
    st = dev.status()
    safe = (
        st.as_int("ch") == 0
        and st.as_int("ce1") == 0
        and st.as_int("ce2") == 0
        and st.as_int("mask") == 0
        and st.as_int("armed") == 0
        and st.as_str("motor1") == "idle"
        and st.as_str("motor2") == "idle"
    )
    shown = " ".join(f"{k}={st.as_str(k)}" for k in ("ch", "ce1", "ce2", "mask", "armed"))
    rec.check(
        "safe",
        "STATUS shows the safe state",
        safe,
        shown,
        "ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle",
    )
    wdt = dev.info(refresh=True).as_int("wdt_a_ms")
    rec.check(
        "defaults",
        "Settings back to defaults",
        wdt == ctx.cfg.wdt_ms("A"),
        f"wdt_a_ms={wdt} (was set to {probe_ms})",
        f"{ctx.cfg.wdt_ms('A')}",
    )
