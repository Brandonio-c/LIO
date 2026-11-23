"""The ``lio`` command line (plan §7).

    lio ports
    lio [--port P | --sim] info | status | ping
    lio ch 8 on --ms 1000          # lights for 1 s, then off (one-shot: everything off on exit)
    lio off
    lio meas 8
    lio sweep --csv out.csv --plot out.png
    lio motor 1 step 64            # one call: arms, steps, waits, releases (asks first)
    lio selftest [--sim] [--modules t03,channels] [--interactive] [--allow-motion]
                 [--save-baseline] [--baseline FILE|latest] [--sample-id ID]
    lio report test_results/<run>/results.json
    lio shell                      # keep the port open and type protocol commands
    lio sim-serve                  # simulated LIO on a pseudo-terminal, for practice
    lio dashboard [--sim]          # web page: run the tests, digital twin, overall verdict
    lio drive-tune A|B             # hold green/white solid; coach LD06 pot via ammeter
    lio scan plan --mode full      # diagnostic height sweep: plan, run, resume
    lio scan plan --protocol protocol.json --json plan.json   # offline targeted plan
    lio scan run --mode quick --sample empty --allow-motion
    lio scan run --protocol protocol.json --allow-light --sim --sample empty
    lio scan audit RUN --model legacy|qualified-v2 --derived-out DIR
    lio scan analyse test_results/<ts>_scan_quick [--reference <white run>]
    lio scan analyse RUN --model qualified-v2 --derived-out DERIVED_ROOT
    lio scan report <run>; lio scan baseline save|list ...; lio scan compare <runA> <runB>

Opening the serial port resets the Nano (about 2 s), so each one-shot command
starts from the safe power-up state and leaves everything off when it exits.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from lio import __version__
from lio.config import ConfigError, HwConfig, load_config
from lio.device import DeviceError, LIODevice, NoResponse
from lio.operator import ConsoleOperator
from lio.results import Status, TestResult, Verdict
from lio.sim import Faults, FaultSpecError, SimulatedLIO
from lio.stage import StageError, tracker_for
from lio.transport import (
    SerialTransport,
    SimTransport,
    Transport,
    TransportError,
    list_ports,
    pick_port,
)

MODULE_ALIASES = {
    "env": "T01",
    "link": "T02",
    "adc": "T03",
    "sr": "T04",
    "shift": "T04",
    "channels": "T05",
    "leds": "T05",
    "detectors": "T06",
    "timing": "T07",
    "sweep": "T08",
    "motors": "T09",
    "safety": "T10",
    "baseline": "T11",
    "scan": "T13",
}
EXIT_FOR_VERDICT = {
    Verdict.FUNCTIONAL.value: 0,
    Verdict.DEGRADED.value: 1,
    Verdict.NOT_FUNCTIONAL.value: 2,
}
EXIT_ERROR = 3
REPO_ROOT = Path(__file__).resolve().parents[4]


class CliError(Exception):
    pass


# ------------------------------------------------------------------ helpers


def _usb_ids(cfg: HwConfig) -> list[tuple[int, int, str]]:
    return [(int(v), int(p), str(n)) for v, p, n in cfg.section.raw("link.usb_ids")]


def _resolve_port(args: argparse.Namespace, cfg: HwConfig) -> str:
    if args.port:
        return str(args.port)
    ports = list_ports(_usb_ids(cfg))
    chosen = pick_port(ports)
    if chosen is None:
        listing = "\n".join(f"  {p.device}  {p.label or p.description}" for p in ports) or "  none"
        raise CliError(f"cannot choose a port automatically; give --port. Serial ports:\n{listing}")
    print(f"using {chosen.device} ({chosen.label})", file=sys.stderr)
    return chosen.device


def _transport(args: argparse.Namespace, cfg: HwConfig) -> Transport:
    transcript = sys.stderr if args.verbose else None
    if args.sim:
        sim = SimulatedLIO(cfg, Faults.parse(args.fault))
        return SimTransport(sim, transcript=transcript)
    return SerialTransport(
        _resolve_port(args, cfg), cfg.section.integer("link.baud"), transcript=transcript
    )


@contextlib.contextmanager
def _device(args: argparse.Namespace, cfg: HwConfig) -> Iterator[LIODevice]:
    stage = None if args.sim else tracker_for(cfg)
    with LIODevice(_transport(args, cfg), cfg, stage=stage) as dev:
        try:
            dev.check_compatible()
        except Exception as e:  # report, but let the user look at what is there
            print(f"warning: {e}", file=sys.stderr)
        yield dev


def _print_fields(fields: dict[str, str]) -> None:
    width = max((len(k) for k in fields), default=0)
    for k, v in fields.items():
        print(f"{k:<{width}}  {v}")


def _confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    return input(f"{prompt} [y/N] ").strip().lower() in ("y", "yes")


# ----------------------------------------------------------------- commands


def cmd_ports(args: argparse.Namespace, cfg: HwConfig) -> int:
    ports = list_ports(_usb_ids(cfg))
    best = pick_port(ports)
    if not ports:
        print("no serial ports found")
    for p in ports:
        mark = "*" if best is not None and p.device == best.device else " "
        ids = f"{p.vid:04X}:{p.pid:04X}" if p.vid is not None and p.pid is not None else "-"
        print(f"{mark} {p.device:32} {ids:10} {p.label or p.description}")
    if best:
        print("\n* chosen automatically when --port is omitted")
    return 0


def cmd_info(args: argparse.Namespace, cfg: HwConfig) -> int:
    with _device(args, cfg) as dev:
        if dev.banner is not None:
            print(dev.banner.raw)
        _print_fields(dict(dev.info().values))
    return 0


def cmd_status(args: argparse.Namespace, cfg: HwConfig) -> int:
    with _device(args, cfg) as dev:
        _print_fields(dict(dev.status().values))
    return 0


def cmd_ping(args: argparse.Namespace, cfg: HwConfig) -> int:
    with _device(args, cfg) as dev:
        rtts = [dev.ping() * 1000 for _ in range(args.count)]
    rtts.sort()
    print(
        f"{len(rtts)} pings: min {rtts[0]:.2f} ms, median {rtts[len(rtts) // 2]:.2f} ms, "
        f"max {rtts[-1]:.2f} ms"
    )
    return 0


def cmd_ch(args: argparse.Namespace, cfg: HwConfig) -> int:
    with _device(args, cfg) as dev:
        n_events = len(dev.events)
        until = dev.ch_on(args.hole, args.ms)
        ch = cfg.channel(args.hole)
        print(f"hole {args.hole} ({ch.label}, RAIL {ch.rail}) on for {until} ms ...")
        dev.drain(until / 1000.0 + 0.5)  # '# OFF' (timer) or '# WDT' (watchdog limit)
        ended = [e for _, e in dev.events[n_events:] if e.name in ("OFF", "WDT")]
        print(ended[0].raw if ended else "off (turned off on exit)")
    return 0


def cmd_off(args: argparse.Namespace, cfg: HwConfig) -> int:
    with _device(args, cfg) as dev:
        dev.off()
        dev.motor_stop()
    print("LEDs off, motors stopped")
    return 0


def cmd_meas(args: argparse.Namespace, cfg: HwConfig) -> int:
    with _device(args, cfg) as dev:
        m = dev.meas(args.hole, settle_ms=args.settle, n=args.n)
    print(f"hole {m.hole} ({cfg.channel(m.hole).label})  t_on {m.t_on_ms} ms")
    for det in ("opt101", "ingaas"):
        print(
            f"  {det:7} dark {m.dark(det):6d}  lit {m.lit(det):6d}  net {m.net(det):+6d} "
            f"({m.net(det) * cfg.lsb_mv:+.2f} mV)"
        )
    return 0


def cmd_sweep(args: argparse.Namespace, cfg: HwConfig) -> int:
    from lio.csvout import sweep_csv_text, write_sweep_csv

    with _device(args, cfg) as dev:
        sweep = dev.sweep(settle_ms=args.settle, n=args.n)
    if args.csv:
        write_sweep_csv(Path(args.csv), sweep.records, cfg)
        print(f"saved {args.csv}")
    else:
        print(sweep_csv_text(sweep.records, cfg), end="")
    if args.plot:
        from lio.report import plot_sweep

        plot_sweep(Path(args.plot), sweep.records, cfg)
        print(f"saved {args.plot}")
    return 0


def cmd_watch(args: argparse.Namespace, cfg: HwConfig) -> int:
    """Live readout of both detector inputs (read-only: no LED, no motion). Ctrl-C stops."""
    lsb = 0.125
    with _device(args, cfg) as dev:
        if dev.mains_hz:
            dev.adc_mains(0)
        base: dict[str, float] = {}
        print(
            "InGaAs (A0) and OPT101 (A1): counts, mV, and change since the start. Ctrl-C to stop."
        )
        try:
            while True:
                out = []
                for name, ch in (("InGaAs", cfg.detectors["ingaas"].adc_channel),
                                 ("OPT101", cfg.detectors["opt101"].adc_channel)):  # fmt: skip
                    v = dev.adc_read(ch, args.n).mean
                    base.setdefault(name, v)
                    d = v - base[name]
                    bar = "#" * min(25, int(abs(d) / max(args.scale, 1)))
                    out.append(f"{name} {v:8.1f} ({v * lsb:+8.2f} mV) {d:+8.1f} {bar:<25}")
                print("  ".join(out), flush=True)
                dev.sleep(args.interval)
        except KeyboardInterrupt:
            print()
    return 0


def cmd_drive_tune(args: argparse.Namespace, cfg: HwConfig) -> int:
    """Hold a sacrificial LED solid and coach the LD06 pot from ammeter readings."""
    from lio.drive_tune import run_tune

    out = Path(args.out) if args.out else (
        REPO_ROOT / "test_results" / "tray_v3" / f"DRIVE_TUNE_{args.rail.upper()}.json"
    )
    print(
        "Stop the dashboard first if it has the port (or this will fail to open).\n"
        "Live OPT101 feedback while you turn the pot; optional ammeter mA. "
        "Firmware cannot clamp current.",
        file=sys.stderr,
    )
    with _device(args, cfg) as dev:
        result = run_tune(
            dev, cfg, args.rail, hole=args.hole, out_path=out, stdin=sys.stdin, stdout=sys.stdout
        )
    return 0 if result.get("accepted_ma") is not None else 1


def cmd_stage(args: argparse.Namespace, cfg: HwConfig) -> int:
    """Chamber-top position kept across sessions (lio.stage)."""
    if args.sim:
        print("stage tracking applies to the hardware only", file=sys.stderr)
        return 3
    if args.stage_command == "show":
        tr = tracker_for(cfg)
        if tr is None:
            print("no stage.state_file in the config", file=sys.stderr)
            return 3
        _print_fields({k: str(v) for k, v in tr.summary().items()})
        return 0
    with _device(args, cfg) as dev:
        try:
            if args.stage_command == "set-top":
                out = dev.stage_set_top()
            elif args.stage_command == "mark-bottom":
                out = dev.stage_mark_bottom()
            else:  # forget
                assert dev.stage is not None
                dev.stage.forget()
                out = dev.stage.summary()
        except StageError as e:
            print(f"refused: {e}", file=sys.stderr)
            return 3
    _print_fields({k: str(v) for k, v in out.items()})
    return 0


def cmd_motor(args: argparse.Namespace, cfg: HwConfig) -> int:
    with _device(args, cfg) as dev:
        if args.action == "stop":
            print(dev.motor_stop().values)
            return 0
        if args.action == "release":
            dev.motor_release(args.motor or "ALL")
            print("released")
            return 0
        if args.action == "arm":
            f = dev.motor_arm()
            print(
                f"armed for {f.as_int('armed_ms')} ms (only while this command runs: "
                "use 'lio motor M step N', which arms by itself, or 'lio shell')"
            )
            return 0
        if args.motor is None or args.steps is None:
            raise CliError("usage: lio motor <1|2> step <+-n> [--rpm R]")
        name = cfg.section.raw(f"motors.{args.motor}.name")
        direction = "up" if args.steps > 0 else "down"
        if not _confirm(
            f"Move motor {args.motor} ({name}) {abs(args.steps)} half-steps "
            f"{direction}? The chamber must be clear.",
            args.yes,
        ):
            print("not moved")
            return 0
        dev.motor_arm()
        f = dev.motor_step(args.motor, args.steps, args.rpm)
        print(f"moving: {dict(f.values)}")
        try:
            ev = dev.wait_motor_done(args.motor, timeout=args.timeout)
        except KeyboardInterrupt:
            dev.motor_stop()
            print("\nstopped")
            return 1
        print(ev.raw if ev else "no done event: stopping")
        if ev is None:
            dev.motor_stop()
    return 0


def _select_tests(args: argparse.Namespace) -> list[str]:
    from lio.suite.core import catalogue

    kinds = {"A"} | ({"I"} if args.interactive else set()) | ({"M"} if args.allow_motion else set())
    wanted: list[str] = []
    for item in (args.modules or "").split(","):
        item = item.strip()
        if not item:
            continue
        key = MODULE_ALIASES.get(item.lower(), item.upper())
        wanted.append(key)
    ids = []
    for t in catalogue():
        if t.kind not in kinds:
            continue
        if wanted and not any(t.id == w or t.module == w for w in wanted):
            continue
        ids.append(t.id)
    if wanted and not ids:
        raise CliError(
            f"no tests match --modules {args.modules!r} (aliases: "
            f"{', '.join(sorted(MODULE_ALIASES))}; or T05, T05.2)"
        )
    return ids


def cmd_selftest(args: argparse.Namespace, cfg: HwConfig) -> int:
    from lio import baseline as bl
    from lio.report import write_run
    from lio.suite.core import REGISTRY, run_test
    from lio.suite.runner import finish, new_record, serial_context, sim_context

    ids = _select_tests(args)
    base = None
    if args.baseline:
        path = bl.latest() if args.baseline == "latest" else Path(args.baseline)
        if path is None:
            raise CliError("--baseline latest: no baseline_*.yaml in software/config")
        base = bl.load(path)
        if "T11.1" not in ids:
            ids.append("T11.1")
    if args.sim:
        ctx = sim_context(cfg, args.fault, loop_jumper=args.loop_jumper)
    else:
        port = _resolve_port(args, cfg)
        operator = ConsoleOperator() if (args.interactive or args.allow_motion) else None
        if args.allow_motion and not _confirm(
            "Motion tests will move both stages by small amounts and back. Is someone at the "
            "bench, with the chamber clear?",
            args.yes,
        ):
            return EXIT_ERROR
        ctx = serial_context(cfg, port, operator=operator, allow_motion=args.allow_motion)
    ctx.baseline = base
    meta = {"sample_id": args.sample_id, "operator": args.operator, "notes": args.notes}
    record = new_record(ctx, {k: v for k, v in meta.items() if v})
    print(
        f"LIO selftest {record.run_id} on {ctx.target}: {len(ids)} tests "
        f"(sample {record.metadata['sample_id']})"
    )
    try:
        for tid in ids:
            print(f"  {tid} {REGISTRY[tid].name} ... ", end="", flush=True)
            r = run_test(ctx, REGISTRY[tid])
            record.results.append(r)
            print(_outcome(r))
    except KeyboardInterrupt:
        print("\ninterrupted: everything off")
    finally:
        finish(record, ctx)
        ctx.dev.close()
    folder = (
        Path(args.results_dir) if args.results_dir else (REPO_ROOT / "test_results" / record.run_id)
    )
    out = write_run(record, folder, cfg=cfg, meas_log=ctx.meas_log)
    v = record.verdict
    print(f"\nVerdict: {v['verdict']}" + (f" ({'; '.join(v['reasons'])})" if v["reasons"] else ""))
    print(f"Report: {out['html']}")
    if args.save_baseline:
        if record.verdict["verdict"] == Verdict.NOT_FUNCTIONAL.value and not args.yes:
            print("not saving a baseline from a NOT FUNCTIONAL run (use --yes to force)")
        else:
            target = None if args.save_baseline == "auto" else Path(args.save_baseline)
            print(f"Baseline saved: {bl.save(record, target)}")
    return EXIT_FOR_VERDICT.get(str(v["verdict"]), EXIT_ERROR)


def _composition(foods_dir: Path) -> object | None:
    """Verified composition records for samples (docs/COMPOSITION_VERIFICATION.md), when the
    ``comp`` extra is installed and the repository's rule tables are present."""
    try:
        from lio_comp.samples import SampleComposition
    except ImportError:
        return None
    comp = SampleComposition(foods_dir / "composition", REPO_ROOT / "composition" / "rules")
    return comp if comp.available() else None


def cmd_dashboard(args: argparse.Namespace, cfg: HwConfig) -> int:
    import webbrowser

    from lio.dashboard.server import Foods, serve
    from lio.dashboard.session import Session

    results = Path(args.results_dir) if args.results_dir else REPO_ROOT / "test_results"
    session = Session(cfg, results)
    host = str(cfg.section.raw("dashboard.host"))
    port = args.http_port if args.http_port is not None else cfg.section.integer("dashboard.port")
    foods: Foods | None = None
    lib = None
    if not getattr(args, "no_food_library", False):
        from lio import foods as food_lib
        from lio.foods.intake import Intake
        from lio.foods.phone import PhoneKey, PhoneServer
        from lio.foods.tunnel import CloudflareTunnel

        fs = food_lib.settings(cfg, REPO_ROOT)
        if args.foods_dir:
            fs.dir = Path(args.foods_dir)
        lib = food_lib.open_library(fs)
        foods = Foods(lib, Intake(lib, _composition(fs.dir)), fs.scan_repeats, fs.scan_repeats_max)
        if fs.phone_enabled and not args.no_phone:
            try:
                foods.phone = PhoneServer(
                    lib,
                    foods.intake,
                    PhoneKey(fs.dir / "phone_key.txt"),
                    fs.phone_host,
                    fs.phone_port,
                )
                foods.phone.serve_in_thread()
                foods.phone.tunnel = CloudflareTunnel(foods.phone.port, fs.cloudflared)
                if fs.tunnel == "cloudflare" and not args.no_tunnel:
                    foods.phone.tunnel.start()
            except OSError as e:
                foods.phone_error = f"cannot listen on {fs.phone_host}:{fs.phone_port} ({e})"
    try:
        server = serve(session, host, port, foods)
    except OSError as e:
        raise CliError(f"cannot listen on {host}:{port} ({e}); try --http-port") from e
    if args.sim:
        session.connect("sim", args.fault or "")
    elif args.port:
        session.connect(str(args.port))
    print(f"LIO dashboard: {server.url}")
    if foods is None:
        print("Food library: disabled (--no-food-library); food-profile Explore still available")
    else:
        assert lib is not None
        print(f"Food library: {lib.db_path}")
        if foods.phone is not None:
            tun = (
                " + Cloudflare tunnel"
                if foods.phone.tunnel and foods.phone.tunnel.state != "off"
                else ""
            )
            print(f"Phone app: port {foods.phone.port}{tun} (pair from the Database tab)")
        elif foods.phone_error:
            print(f"Phone app OFF: {foods.phone_error}")
    print("Ctrl-C to quit (stops any run and turns everything off).")
    if not args.no_browser:
        webbrowser.open(server.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down: everything off")
    finally:
        session.shutdown()
        server.server_close()
        if foods is not None and foods.phone is not None:
            if foods.phone.tunnel is not None:
                foods.phone.tunnel.stop()
            foods.phone.shutdown()
            foods.phone.server_close()
        if lib is not None:
            lib.close()
    return 0


def cmd_profiles(args: argparse.Namespace, cfg: HwConfig) -> int:
    from lio.food_profiles.cli import cmd_profiles as _cmd

    return _cmd(args)


def _outcome(r: TestResult) -> str:
    icon = {"PASS": "✓", "WARN": "!", "FAIL": "✕", "ERROR": "✕", "SKIP": "-"}[r.status.value]
    bad = [s for s in r.subs if s.status in (Status.FAIL, Status.ERROR, Status.WARN)]
    text = f"{icon} {r.status.value}"
    if r.message:
        text += f" ({r.message})"
    for s in bad[:4]:
        text += f"\n          {s.status.value}: {s.name}: {s.message}"
    if len(bad) > 4:
        text += f"\n          ... {len(bad) - 4} more (see the report)"
    return text


def cmd_report(args: argparse.Namespace, cfg: HwConfig) -> int:
    from lio.report import rebuild

    out = rebuild(Path(args.results), cfg)
    print(f"Report: {out['html']}")
    return 0


def cmd_shell(args: argparse.Namespace, cfg: HwConfig) -> int:
    with _device(args, cfg) as dev:
        print(
            f"{dev.banner.raw if dev.banner else ''}\nType protocol commands (docs/PROTOCOL.md), "
            "'help', or 'quit'. Everything is turned off when you leave."
        )
        while True:
            try:
                line = input("lio> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if line.lower() in ("quit", "exit"):
                break
            if not line:
                for ev in dev.drain(0.05):
                    print(ev.raw)
                continue
            if line.lower() == "help":
                print(
                    "PING INFO STATUS | I2C SCAN | ADC READ ch [n] | CH n ON [ms] | OFF | "
                    "MEAS n [settle n] | SWEEP | MOTOR ARM <token> | MOTOR m STEP +-n [rpm] | "
                    "MOTOR STOP | RESET   (INFO shows arm_token)"
                )
                continue
            try:
                # Light-capable lines are routed through guarded typed ops (D01)
                # or refused — never a raw transport bypass.
                reply = dev.command(line, timeout=30.0, check=False)
            except NoResponse as e:
                print(f"no response: {e}")
                continue
            except Exception as e:
                from lio.ownership import DutyBudgetError, OwnershipError

                if isinstance(e, (DutyBudgetError, OwnershipError, DeviceError)):
                    print(f"refused: {e}")
                    continue
                raise
            for ev in reply.events:
                print(ev.raw)
            print(reply.response.raw)
    return 0


def cmd_sim_serve(args: argparse.Namespace, cfg: HwConfig) -> int:
    from lio.simserve import PtyBridge

    with PtyBridge(cfg, Faults.parse(args.fault)) as bridge:
        print(
            f"Simulated LIO on {bridge.port}" + (f" with faults {args.fault}" if args.fault else "")
        )
        print(f"Try: lio --port {bridge.port} info     (Ctrl-C to stop)")
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print()
    return 0


def _scan_overrides(items: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise CliError(f"--set expects key=value, got {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def cmd_scan(args: argparse.Namespace, cfg: HwConfig) -> int:
    """Diagnostic height sweep and targeted protocol commands.

    Protocol plan/audit/analyse/report paths are offline (no device, serial,
    POWER WAKE or light). Legacy ``plan`` without ``--protocol`` also plans
    offline when stage limits are not required.
    """
    import tempfile

    from lio import scan
    from lio.operator import SimOperator

    protocol = getattr(args, "protocol", None)
    mode = getattr(args, "mode", None)
    if protocol and mode:
        raise CliError("--protocol is mutually exclusive with legacy --mode")

    # Truly offline commands — never construct LIODevice / open serial.
    if args.scan_command == "audit" or (
        args.scan_command in ("analyse", "report") and getattr(args, "derived_out", None)
    ):
        return _scan_protocol_offline(args, cfg)
    if args.scan_command == "plan" and protocol:
        return _scan_protocol_plan(args, cfg)
    if args.scan_command == "plan" and not protocol:
        return _scan_legacy_plan_offline(args, cfg)
    if args.scan_command in ("analyse", "baseline", "compare", "report"):
        return _scan_offline(args, cfg)
    if args.scan_command == "run" and protocol:
        return _scan_protocol_run(args, cfg)

    overrides = _scan_overrides(getattr(args, "set", None))
    mode = mode or str(cfg.section.raw("scan.default_mode"))
    out = getattr(args, "out", None)
    root = Path(out) if out else REPO_ROOT / "test_results"
    if args.sim:
        sim = SimulatedLIO(cfg, Faults.parse(args.fault))
        sample = getattr(args, "sample", None)
        if sample:
            sim.sample = "food" if sample.startswith("LIO-F-") else sample
        dev = LIODevice(SimTransport(sim, transcript=sys.stderr if args.verbose else None), cfg)
    else:
        sim = None
        dev = LIODevice(_transport(args, cfg), cfg, stage=tracker_for(cfg))
    with dev:
        if sim is not None:
            stage_dir = Path(tempfile.mkdtemp(prefix="lio_sim_stage_"))
            scan.sim_stage(dev, stage_dir / "stage.json", int(sim.travel_hs))
        else:
            dev.check_compatible()
        operator = SimOperator(sim) if sim is not None else ConsoleOperator()
        if args.scan_command == "resume":
            folder = Path(args.folder)
            meta = json.loads((folder / "scan.json").read_text())
            # D19: protocol runs resume through resume_protocol, not height-scan resume.
            if meta.get("mode") == "protocol" or meta.get("protocol_plan"):
                from lio.scan.acquisition import resume_protocol

                if not getattr(args, "allow_light", False):
                    raise CliError("protocol resume requires --allow-light")
                result = resume_protocol(
                    folder,
                    cfg=cfg,
                    allow_light=True,
                    device=dev,
                    operator_checkpoint_flag=True,
                )
                print(f"{result.status}: {result.folder}")
                if result.cancel_reason:
                    print(f"  unresolved: {result.cancel_reason}")
                return 0 if result.status == "COMPLETE" else 1
            mode_of = meta.get("plan", {})
            static = bool(mode_of.get("static"))
        else:
            plan = scan.plan_for(cfg, mode, dev.stage, dev.stage_top_margin(), overrides)
            static = plan.static
            print(plan.summary())
        if not static and sim is None and not getattr(args, "allow_motion", False):
            raise CliError(
                "this mode moves the chamber top: add --allow-motion (and stay with the rig)"
            )
        if not args.sample and args.scan_command == "run":
            raise CliError(f"--sample is required: one of {cfg.section.raw('scan.sample_ids')} "
                           "or a food code LIO-F-...")  # fmt: skip

        def show(p: dict[str, object]) -> None:
            if p.get("status") in ("measured", "paused", "aborted", "complete"):
                print(f"[{p.get('done')}/{p.get('of')}] {p.get('status')} {p.get('phase') or ''} "
                      f"{p.get('label') or ''} h={p.get('target_hs')} "
                      f"eta {float(str(p.get('eta_s') or 0)) / 60:.1f} min "
                      f"{p.get('reason') or ''}", file=sys.stderr)  # fmt: skip

        if args.scan_command == "resume":
            store, status = scan.resume(dev, cfg, Path(args.folder), operator, on_progress=show)
        else:
            store, status = scan.start(dev, cfg, plan, root, operator, sample_id=args.sample,
                                       on_progress=show, sim=sim is not None)  # fmt: skip
    print(f"{status}: {store.folder}")
    for a in store.meta.get("aborts", []):
        print(f"  abort: {a['reason']}")
    return 0 if status == "COMPLETE" else 1


def _scan_protocol_plan(args: argparse.Namespace, cfg: HwConfig) -> int:
    """``lio scan plan --protocol`` — offline; no device construction."""
    from lio.scan.acquisition import ProtocolError, plan_protocol

    try:
        plan = plan_protocol(Path(args.protocol), cfg)
    except ProtocolError as e:
        raise CliError(str(e)) from e
    d = plan.to_dict()
    print(
        f"protocol {plan.protocol.id} v{plan.protocol.version}  "
        f"{len(plan.steps)} steps  on≈{plan.predicted_on_ms:.0f} ms  "
        f"eta≈{plan.predicted_duration_s / 60:.1f} min  stationary (no motors)"
    )
    for u in plan.unresolved:
        print(f"  unresolved: {u}")
    if args.json:
        Path(args.json).write_text(json.dumps(d, indent=1) + "\n")
        print(f"plan -> {args.json}")
    return 0


def _scan_legacy_plan_offline(args: argparse.Namespace, cfg: HwConfig) -> int:
    """Legacy mode plan without opening a device (no POWER WAKE / serial)."""
    import contextlib

    from lio.scan.plan import PlanError, build

    overrides = _scan_overrides(getattr(args, "set", None))
    mode = args.mode or str(cfg.section.raw("scan.default_mode"))
    top_margin = 0
    with contextlib.suppress(Exception):
        top_margin = cfg.section.integer("stage.top_margin_steps")
    # Offline travel: use sim travel as a declared planning envelope (not a measured stage).
    try:
        travel = int(cfg.section.raw("sim.height.travel_hs"))
    except Exception:
        travel = 286884
    try:
        plan = build(
            cfg,
            mode,
            top_limit=0,
            bottom_limit=-travel,
            current=0,
            top_margin=top_margin,
            overrides=overrides,
        )
    except PlanError as e:
        raise CliError(str(e)) from e
    print(plan.summary())
    print("(offline plan: no device / POWER WAKE; travel from config sim envelope)")
    if args.json:
        Path(args.json).write_text(json.dumps(plan.to_dict(), indent=1) + "\n")
        print(f"plan -> {args.json}")
    return 0

def _scan_protocol_run(args: argparse.Namespace, cfg: HwConfig) -> int:
    """``lio scan run --protocol --allow-light`` — gated emission via journal (D19).

    Real CLI branch is offline-testable with fake transports. Hardware requires
    --allow-light plus ownership/duty journal (always attached on SerialTransport)
    and compatible firmware preflight — not a hard-coded session refusal.
    """
    import tempfile

    from lio import scan
    from lio.scan.acquisition import ProtocolError, plan_protocol, run_protocol

    if not getattr(args, "allow_light", False):
        raise CliError("protocol run requires --allow-light")
    if not args.sample:
        raise CliError("--sample is required for protocol run")
    try:
        pplan = plan_protocol(Path(args.protocol), cfg)
    except ProtocolError as e:
        raise CliError(str(e)) from e
    if pplan.unresolved:
        raise CliError("protocol plan unresolved: " + "; ".join(pplan.unresolved))
    root = Path(args.out) if args.out else REPO_ROOT / "test_results"
    if args.sim:
        sim = SimulatedLIO(cfg, Faults.parse(args.fault))
        sim.sample = "food" if args.sample.startswith("LIO-F-") else args.sample
        dev = LIODevice(SimTransport(sim, transcript=sys.stderr if args.verbose else None), cfg)
        with dev:
            stage_dir = Path(tempfile.mkdtemp(prefix="lio_sim_stage_"))
            scan.sim_stage(dev, stage_dir / "stage.json", int(sim.travel_hs))
            result = run_protocol(
                pplan,
                cfg=cfg,
                root=root,
                sample_id=args.sample,
                allow_light=True,
                device=dev,
                simulated=True,
                rig_identity="sim",
                operator_checkpoint_flag=True,
            )
    else:
        # Authorized runtime gates (D19): allow-light + ownership journal + preflight.
        # Offline tests inject a fake transport via LIODevice; never auto-emit.
        if not getattr(args, "port", None) and not getattr(args, "url", None):
            raise CliError(
                "hardware protocol run requires --port/--url (or --sim); "
                "ownership journal and --allow-light are mandatory gates"
            )
        dev = LIODevice(_transport(args, cfg), cfg, stage=tracker_for(cfg))
        if dev.journal is None:
            raise CliError("refusing hardware protocol run without duty journal")
        with dev:
            dev.check_compatible()
            result = run_protocol(
                pplan,
                cfg=cfg,
                root=root,
                sample_id=args.sample,
                allow_light=True,
                device=dev,
                simulated=False,
                rig_identity="host",
                operator_checkpoint_flag=True,
            )
    print(f"{result.status}: {result.folder}")
    if result.cancel_reason:
        print(f"  unresolved: {result.cancel_reason}")
    return 0 if result.status == "COMPLETE" else 1


def _scan_protocol_offline(args: argparse.Namespace, cfg: HwConfig) -> int:
    """audit / analyse / report with --derived-out (offline)."""
    from lio.scan.derived import analyse_model, audit_run, report_derived

    derived = Path(args.derived_out)
    model = getattr(args, "model", None) or "qualified-v2"
    folder = Path(getattr(args, "folder", None) or getattr(args, "run", None))
    if args.scan_command == "audit":
        out = audit_run(folder, cfg, model=model, derived_out=derived)
        print(json.dumps({k: out[k] for k in out if not k.startswith("_")}, indent=1))
        print(f"audit -> {out.get('_path')}")
        return 0
    if args.scan_command == "analyse":
        out = analyse_model(folder, cfg, model=model, derived_out=derived)
        print(f"model={out.get('model')} analysis_id={out.get('analysis_id')}")
        print(f"analysis -> {out.get('_path')}")
        return 0
    if args.scan_command == "report":
        aid = getattr(args, "analysis", None) or getattr(args, "analysis_id", None)
        if not aid:
            raise CliError("--analysis ANALYSIS_ID required with --derived-out")
        path = report_derived(folder, analysis_id=str(aid), derived_out=derived)
        print(f"report -> {path}")
        return 0
    raise CliError(f"unsupported offline scan command {args.scan_command}")


def _scan_offline(args: argparse.Namespace, cfg: HwConfig) -> int:
    """lio scan analyse / baseline / compare: on run folders, no connection."""
    from lio.scan.analysis import analyse, trend

    root = Path(getattr(args, "out", None) or REPO_ROOT / "test_results")

    def analysed(folder: Path) -> dict[str, Any]:
        if not (folder / "analysis.json").exists():
            analyse(folder, cfg, None, root)
        data: dict[str, Any] = json.loads((folder / "analysis.json").read_text())
        return data

    if args.scan_command == "analyse":
        # Optional derived-out path handled earlier; legacy writes analysis.json in-run.
        ref = Path(args.reference) if getattr(args, "reference", None) else None
        a = analyse(Path(args.folder), cfg, ref, None if args.no_baselines else root)
        print(a.summary())
        print(f"analysis -> {Path(args.folder) / 'analysis.json'}")
        return EXIT_FOR_VERDICT.get(a.verdict.get("verdict", ""), EXIT_ERROR)
    if args.scan_command == "report":
        from lio.scan import report as scan_report

        ref = Path(args.reference) if getattr(args, "reference", None) else None
        written = scan_report.write(Path(args.folder), cfg, reference=ref,
                                    baselines_root=None if args.no_baselines else root)  # fmt: skip
        print(f"report -> {written['html']}")
        return 0
    if args.scan_command == "baseline":
        if args.action == "list":
            d = root / "scan_baselines"
            for sd in sorted(p for p in d.glob("*") if p.is_dir()) if d.exists() else []:
                if args.sample and sd.name != args.sample:
                    continue
                runs = sorted(p.stem for p in sd.glob("*.json"))
                print(f"{sd.name}: {len(runs)} baseline(s)")
                for r in runs:
                    print(f"  {r}")
            return 0
        if not args.folder:
            raise CliError("usage: lio scan baseline save <run folder>")
        folder = Path(args.folder)
        analysed(folder)
        try:
            out = trend.save_baseline(folder, root, cfg)
        except ValueError as e:
            raise CliError(str(e)) from e
        print(f"baseline -> {out}")
        return 0
    snap_a = trend.snapshot(analysed(Path(args.run_a)))
    snap_b = trend.snapshot(analysed(Path(args.run_b)))
    for f in trend.compare(snap_a, snap_b, cfg):
        print(f"{f.status.value:<5} {f.title}: {f.detail} (furthest ratio {f.value:.2f})")
        for det, r in f.data["ratios"].items():
            print(f"  {det}: " + " ".join(f"h{h}={v:.2f}" for h, v in sorted(r.items())))
    return 0


# ------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lio", description="LIO V3 host tool (firmware v2).")
    p.add_argument("--version", action="version", version=f"lio {__version__}")
    p.add_argument("--port", help="serial port (default: the single likely LIO port)")
    p.add_argument("--sim", action="store_true", help="use the simulator instead of hardware")
    p.add_argument("--fault", help="simulator faults, e.g. reversed_ingaas,stuck_on:5")
    p.add_argument("--config", help="path to lio_hw.yaml")
    p.add_argument("-v", "--verbose", action="store_true", help="print the serial transcript")
    p.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("ports", help="list serial ports").set_defaults(fn=cmd_ports)
    sub.add_parser("info", help="firmware identity and limits").set_defaults(fn=cmd_info)
    sub.add_parser("status", help="current state").set_defaults(fn=cmd_status)
    s = sub.add_parser("ping", help="round-trip latency")
    s.add_argument("-n", "--count", type=int, default=20)
    s.set_defaults(fn=cmd_ping)

    s = sub.add_parser("ch", help="light one hole, wait, then off")
    s.add_argument("hole", type=int, choices=range(1, 17), metavar="HOLE")
    s.add_argument("state", choices=["on"])
    s.add_argument("--ms", type=int, default=None, help="on-time (default: rail watchdog)")
    s.set_defaults(fn=cmd_ch)
    sub.add_parser("off", help="LEDs off, motors stopped").set_defaults(fn=cmd_off)

    s = sub.add_parser("meas", help="dark + lit reading of one hole")
    s.add_argument("hole", type=int, choices=range(1, 17), metavar="HOLE")
    s.add_argument("--settle", type=int, default=None)
    s.add_argument("--n", type=int, default=None)
    s.set_defaults(fn=cmd_meas)

    s = sub.add_parser("sweep", help="all 16 holes")
    s.add_argument("--settle", type=int, default=None)
    s.add_argument("--n", type=int, default=None)
    s.add_argument("--csv", help="write the logger-format CSV here")
    s.add_argument("--plot", help="write a PNG plot here")
    s.set_defaults(fn=cmd_sweep)

    s = sub.add_parser("watch", help="live readout of both detectors (read-only)")
    s.add_argument("--interval", type=float, default=0.5, help="seconds between readings")
    s.add_argument("-n", type=int, default=8, help="samples averaged per reading")
    s.add_argument("--scale", type=float, default=10.0, help="counts per # in the bar")
    s.set_defaults(fn=cmd_watch)

    s = sub.add_parser(
        "drive-tune",
        help="hold green (A) / white (B) solid; coach LD06 pot from ammeter readings",
    )
    s.add_argument("rail", choices=["A", "B", "a", "b"], help="which constant-current driver")
    s.add_argument(
        "--hole",
        type=int,
        default=None,
        metavar="N",
        help="override tune LED (default: rails.*.tune_hole — 4 green / 11 pink)",
    )
    s.add_argument("--out", default=None, help="JSON log path (default test_results/tray_v3/...)")
    s.set_defaults(fn=cmd_drive_tune)

    s = sub.add_parser("stage", help="chamber-top position and travel limits")
    ssub = s.add_subparsers(dest="stage_command", required=True)
    ssub.add_parser("show", help="tracked position and limits (no connection)")
    ssub.add_parser("set-top", help="the top is at its physical upper end now (position 0)")
    ssub.add_parser("mark-bottom", help="the top is at its lowest safe position now")
    ssub.add_parser("forget", help="the position is no longer known (moved by hand)")
    s.set_defaults(fn=cmd_stage)
    s = sub.add_parser("motor", help="motor commands (asks before moving)")
    s.add_argument("motor_or_action", help="1, 2, arm, stop or release")
    s.add_argument("rest", nargs="*", help="step <+-n>")
    s.add_argument("--rpm", type=int, default=None)
    s.add_argument("--timeout", type=float, default=30.0)
    s.set_defaults(fn=cmd_motor)

    s = sub.add_parser("selftest", help="run the test catalogue and write a report")
    s.add_argument(
        "--modules", help="comma list: t03,t05,T05.2 or aliases " + ",".join(sorted(MODULE_ALIASES))
    )
    s.add_argument("--interactive", action="store_true", help="include operator steps")
    s.add_argument("--allow-motion", action="store_true", help="include motor tests")
    s.add_argument("--baseline", help="compare with this baseline file, or 'latest'")
    s.add_argument(
        "--save-baseline",
        nargs="?",
        const="auto",
        default=None,
        help="save this run as a baseline (default software/config/baseline_<date>.yaml)",
    )
    s.add_argument("--report", action="store_true", help="(reports are always written)")
    s.add_argument("--sample-id", default=None)
    s.add_argument("--operator", default=None)
    s.add_argument("--notes", default=None)
    s.add_argument("--results-dir", default=None)
    s.add_argument("--loop-jumper", action="store_true", help="simulator: loopback jumper fitted")
    s.set_defaults(fn=cmd_selftest)

    s = sub.add_parser("report", help="rebuild the report of an earlier run")
    s.add_argument("results", help="path to results.json")
    s.set_defaults(fn=cmd_report)
    sub.add_parser("shell", help="interactive protocol session").set_defaults(fn=cmd_shell)
    sub.add_parser("sim-serve", help="serve the simulator on a pseudo-terminal").set_defaults(
        fn=cmd_sim_serve
    )
    s = sub.add_parser("dashboard", help="web dashboard: run tests, digital twin, verdict")
    s.add_argument("--http-port", type=int, default=None, help="default: dashboard.port")
    s.add_argument("--no-browser", action="store_true", help="do not open a browser")
    s.add_argument("--results-dir", default=None, help="default: test_results/ in the repo")
    s.add_argument("--foods-dir", default=None, help="food library folder (default: foods.dir)")
    s.add_argument("--no-phone", action="store_true", help="do not serve the phone intake app")
    s.add_argument(
        "--no-tunnel", action="store_true", help="do not open the Cloudflare tunnel (foods.tunnel)"
    )
    s.add_argument(
        "--no-food-library",
        action="store_true",
        help="skip food DB/phone/tunnel; food-profile Explore remains enabled",
    )
    s.set_defaults(fn=cmd_dashboard)

    from lio.food_profiles.cli import build_profiles_parser

    build_profiles_parser(sub, fn=cmd_profiles)

    s = sub.add_parser(
        "scan",
        help="diagnostic height sweep / targeted protocol: plan / run / resume",
    )
    scsub = s.add_subparsers(dest="scan_command", required=True)
    for name, hlp in (("plan", "show the plan and its ETA (offline; no motion, no light)"),
                      ("run", "run a scan (asks first; --allow-motion for moving modes)"),
                      ("resume", "carry on an INCOMPLETE run from its next step")):  # fmt: skip
        c = scsub.add_parser(name, help=hlp)
        if name == "resume":
            c.add_argument("folder", help="the run folder (test_results/<ts>_scan_<mode>)")
        else:
            c.add_argument("--mode", help="legacy: quick_down, quick, full, fine, ... "
                           "(mutually exclusive with --protocol)")  # fmt: skip
            c.add_argument("--protocol", help="targeted stationary protocol JSON "
                           "(mutually exclusive with --mode)")  # fmt: skip
            c.add_argument("--set", action="append", metavar="KEY=VALUE",
                           help="override a scan setting, e.g. sweep_n=4")  # fmt: skip
        if name == "plan":
            c.add_argument("--json", help="also write the plan as JSON")
        else:
            c.add_argument("--allow-motion", action="store_true",
                           help="allow moving the chamber top (hardware)")  # fmt: skip
        if name == "run":
            c.add_argument("--sample", help="sample in the chamber: empty, white_ptfe, black_cup, "
                           "food, or LIO-F-...")  # fmt: skip
            c.add_argument("--out", help="results root (default test_results/)")
        if name in ("run", "resume"):
            c.add_argument("--allow-light", action="store_true",
                           help="required for protocol emission / protocol resume")  # fmt: skip
        c.set_defaults(fn=cmd_scan)
    c = scsub.add_parser("audit", help="offline provenance/model audit into --derived-out")
    c.add_argument("folder", help="the run folder")
    c.add_argument("--model", choices=["legacy", "qualified-v2"], default="qualified-v2")
    c.add_argument(
        "--derived-out",
        required=True,
        help="derived analysis root (not the run folder)",
    )
    c.set_defaults(fn=cmd_scan)
    c = scsub.add_parser("analyse", help="compute the metrics of a run (writes analysis.json)")
    c.add_argument("folder", help="the run folder")
    c.add_argument("--reference", help="a reference run: white_ptfe for stray light, or a "
                   "baseline of the same sample for effectiveness")  # fmt: skip
    c.add_argument("--no-baselines", action="store_true", help="skip trend and control charts")
    c.add_argument("--out", help="results root holding scan_baselines/ (default test_results/)")
    c.add_argument("--model", choices=["legacy", "qualified-v2"], default=None,
                   help="with --derived-out: write versioned product there")  # fmt: skip
    c.add_argument("--derived-out", help="derived analysis root (offline; leaves run folder raw)")
    c.set_defaults(fn=cmd_scan)
    c = scsub.add_parser("report", help="write report.html / report.md with plots")
    c.add_argument("folder", help="the run folder")
    c.add_argument("--reference", help="a reference run (as for analyse)")
    c.add_argument("--no-baselines", action="store_true", help="skip trend and control charts")
    c.add_argument("--out", help="results root holding scan_baselines/ (default test_results/)")
    c.add_argument("--analysis", help="derived analysis_id (with --derived-out)")
    c.add_argument("--derived-out", help="derived analysis root for --analysis report")
    c.set_defaults(fn=cmd_scan)
    c = scsub.add_parser("baseline", help="save a run as a baseline, or list baselines")
    c.add_argument("action", choices=["save", "list"])
    c.add_argument("folder", nargs="?", help="the run folder (save)")
    c.add_argument("--sample", help="list: only this sample id")
    c.add_argument("--out", help="results root holding scan_baselines/ (default test_results/)")
    c.set_defaults(fn=cmd_scan)
    c = scsub.add_parser("compare", help="compare two runs: per-hole ratios, where it changed")
    c.add_argument("run_a")
    c.add_argument("run_b")
    c.set_defaults(fn=cmd_scan)

    s = sub.add_parser("bench", help="coverage benchmark: plan / ingest / report")
    bsub = s.add_subparsers(dest="bench_command", required=True)
    b = bsub.add_parser("plan", help="seeded store-shelf sampling sheet for one visit")
    b.add_argument("--store", required=True)
    b.add_argument(
        "--format", default="grocery", help="store format (grocery, pharmacy, club, ...)"
    )
    b.add_argument("--n", type=int, default=40)
    b.add_argument("--seed", type=int, required=True)
    b.add_argument("--aisles-foods", default="1-20")
    b.add_argument("--aisles-supplements", default="21-22")
    b.add_argument("--aisles-otc", default="23-24")
    b.add_argument("--shelves", default="1-6")
    b.add_argument("--facings", default="1-30")
    b.add_argument("--out", required=True)
    b.set_defaults(fn=cmd_bench)
    b = bsub.add_parser("ingest", help="run the pipeline on a filled sheet and its photos")
    b.add_argument("--sheet", required=True)
    b.add_argument("--photos", default=".")
    b.add_argument("--out", required=True)
    b.set_defaults(fn=cmd_bench)
    b = bsub.add_parser("report", help="metrics with Wilson 95% intervals")
    b.add_argument("--ingest", required=True, nargs="+")
    b.add_argument("--title", default="Coverage benchmark")
    b.add_argument("--out", required=True)
    b.set_defaults(fn=cmd_bench)
    return p


def cmd_bench(args: argparse.Namespace, cfg: HwConfig) -> int:
    from lio import bench
    from lio import foods as food_lib

    if args.bench_command == "plan":
        layout = bench.Layout(
            aisles={
                "foods": bench.parse_range(args.aisles_foods),
                "supplements": bench.parse_range(args.aisles_supplements),
                "otc": bench.parse_range(args.aisles_otc),
            },
            shelves=bench.parse_range(args.shelves),
            facings=bench.parse_range(args.facings),
        )
        rows, meta = bench.plan(args.store, args.format, args.n, args.seed, layout)
        bench.write_sheet(rows, meta, Path(args.out))
        print(
            f"{len(rows)} slots -> {args.out} (seed {args.seed}; "
            f"plan in {Path(args.out).with_suffix('.plan.json')})"
        )
        return 0
    if args.bench_command == "ingest":
        fs = food_lib.settings(cfg, REPO_ROOT)
        lib = food_lib.open_library(fs)
        if lib.lookup is None:
            raise CliError("online lookup is off (foods.online_lookup)")
        items = bench.ingest(Path(args.sheet), Path(args.photos), Path(args.out), lib.lookup)
        print(f"{len(items)} items -> {args.out}")
        return 0
    items = [
        json.loads(ln) for p in args.ingest for ln in Path(p).read_text().splitlines() if ln.strip()
    ]
    Path(args.out).write_text(bench.report(items, args.title))
    print(f"report -> {args.out}")
    return 0


def _motor_args(args: argparse.Namespace) -> None:
    first = args.motor_or_action.lower()
    args.motor, args.steps, args.action = None, None, first
    if first in ("1", "2"):
        args.motor = int(first)
        args.action = "step"
        if len(args.rest) == 2 and args.rest[0].lower() == "step":
            args.steps = int(args.rest[1])
        elif args.rest and args.rest[0].lower() == "release":
            args.action = "release"
        else:
            raise CliError("usage: lio motor <1|2> step <+-n> [--rpm R]")
    elif first not in ("arm", "stop", "release"):
        raise CliError("usage: lio motor arm|stop|release|<1|2> step <+-n>")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        cfg = load_config(Path(args.config) if args.config else None)
        if args.command == "motor":
            _motor_args(args)
        result: int = args.fn(args, cfg)
        return result
    except (
        CliError,
        ConfigError,
        FaultSpecError,
        TransportError,
        DeviceError,
        NoResponse,
        TimeoutError,
        ValueError,
    ) as e:
        print(f"lio: {e}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
