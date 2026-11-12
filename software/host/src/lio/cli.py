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

Opening the serial port resets the Nano (about 2 s), so each one-shot command
starts from the safe power-up state and leaves everything off when it exits.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
import time
from collections.abc import Iterator
from pathlib import Path

from lio import __version__
from lio.config import ConfigError, HwConfig, load_config
from lio.device import DeviceError, LIODevice, NoResponse
from lio.operator import ConsoleOperator
from lio.results import Status, TestResult, Verdict
from lio.sim import Faults, FaultSpecError, SimulatedLIO
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
    with LIODevice(_transport(args, cfg), cfg) as dev:
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


def cmd_dashboard(args: argparse.Namespace, cfg: HwConfig) -> int:
    import webbrowser

    from lio import foods as food_lib
    from lio.dashboard.server import Foods, serve
    from lio.dashboard.session import Session
    from lio.foods.intake import Intake
    from lio.foods.phone import PhoneKey, PhoneServer
    from lio.foods.tunnel import CloudflareTunnel

    results = Path(args.results_dir) if args.results_dir else REPO_ROOT / "test_results"
    session = Session(cfg, results)
    host = str(cfg.section.raw("dashboard.host"))
    port = args.http_port if args.http_port is not None else cfg.section.integer("dashboard.port")
    fs = food_lib.settings(cfg, REPO_ROOT)
    if args.foods_dir:
        fs.dir = Path(args.foods_dir)
    lib = food_lib.open_library(fs)
    foods = Foods(lib, Intake(lib), fs.scan_repeats, fs.scan_repeats_max)
    if fs.phone_enabled and not args.no_phone:
        try:
            foods.phone = PhoneServer(
                lib, foods.intake, PhoneKey(fs.dir / "phone_key.txt"), fs.phone_host, fs.phone_port
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
        if foods.phone is not None:
            if foods.phone.tunnel is not None:
                foods.phone.tunnel.stop()
            foods.phone.shutdown()
            foods.phone.server_close()
        lib.close()
    return 0


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
                reply = dev.command(line, timeout=30.0, check=False)
            except NoResponse as e:
                print(f"no response: {e}")
                continue
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
    s.set_defaults(fn=cmd_dashboard)
    return p


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
