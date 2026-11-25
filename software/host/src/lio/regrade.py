"""Re-grade a saved whole-system run under the CURRENT thresholds (owner 2026-11-25).

The thresholds are provisional and get calibrated after hardware runs. A saved run keeps
the measurements its tests recorded, so the tests whose judgment depends only on those
numbers can be judged again without new light or motion:

- T03.2 dark noise (per-detector WARN band), from the recorded sigmas;
- T05.2 per-channel response and T05.3 detector pattern, from the recorded nets and the
  run's own T03.2 dark sigmas, with the same judge code the live suite uses;
- T05.1 RAIL B gating, when the configured gating hole changed since the run (the new
  hole was not measured: the old sub is graded "superseded", never invented);
- T05.5 / T08.2 repeatability, from the recorded stability outcome;
- T13.1, by re-analysing its saved height-scan folder (read-only).

Every other result is copied unchanged. The re-graded record is written as a NEW run
(``<now>_regrade_of_<run>``) with ``metadata.regraded_from`` and the config hash; the
original run folder is never modified. Every changed sub-result says so in its message.
"""

from __future__ import annotations

import copy
import datetime as dt
import math
from dataclasses import dataclass
from pathlib import Path

from lio.config import ConfigError, HwConfig
from lio.results import RunRecord, Status, SubResult, TestResult, overall_verdict, worst

NOTE = "re-graded {date} under the current thresholds; was {old}"


@dataclass(frozen=True)
class _Sigma:
    std: float


class _Dark:
    """The run's own dark statistics (T03.2), shaped like :class:`DarkStats`."""

    def __init__(self, sigmas: dict[str, float]) -> None:
        self._s = sigmas

    def sigma(self, det: str) -> float:
        return max(self._s.get(det, 1.0), 1.0)

    def net_sigma(self, det: str, n: int) -> float:
        return self.sigma(det) * math.sqrt(2.0 / n)


class _Ctx:
    """Just enough of :class:`SuiteContext` for the judge helpers."""

    def __init__(self, cfg: HwConfig, sigmas: dict[str, float]) -> None:
        self.cfg = cfg
        self.th = cfg.thresholds
        self._dark = _Dark(sigmas)

    def dark(self) -> _Dark:
        return self._dark


def _hole(sub_id: str) -> int | None:
    for part in sub_id.split("/"):
        if len(part) == 3 and part[0] == "h" and part[1:].isdigit():
            return int(part[1:])
    return None


def _mark(sub: SubResult, status: Status, message: str, date: str) -> bool:
    """Apply a new grade; an unchanged grade leaves the sub-result exactly as recorded."""
    if status == sub.status:
        return False
    old = sub.status.value
    sub.status = status
    sub.message = f"{message} [{NOTE.format(date=date, old=old)}]"
    return True


def _dark_sigmas(record: RunRecord, cfg: HwConfig) -> dict[str, float]:
    out: dict[str, float] = {}
    t032 = next((r for r in record.results if r.id == "T03.2"), None)
    if t032 is None:
        return out
    for det, d in cfg.detectors.items():
        sub = next((s for s in t032.subs if s.id == f"T03.2/a{d.adc_channel}"), None)
        if sub is not None and "sigma" in sub.measured:
            out[det] = float(sub.measured["sigma"])
    return out


def _t03_2(r: TestResult, cfg: HwConfig, date: str) -> int:
    th = cfg.thresholds
    sigma_max = th.num("adc.dark_sigma_max_counts")
    changed = 0
    for det, d in cfg.detectors.items():
        sub = next((s for s in r.subs if s.id == f"T03.2/a{d.adc_channel}"), None)
        if sub is None or "sigma" not in sub.measured:
            continue
        sd = float(sub.measured["sigma"])
        try:
            fail_at = float(th.num(f"adc.dark_sigma_fail_counts.{det}"))
        except ConfigError:
            fail_at = sigma_max
        st = Status.PASS if sd <= sigma_max else Status.WARN if sd <= fail_at else Status.FAIL
        msg = f"mean {float(sub.measured.get('mean', 0)):.1f}, sigma {sd:.2f} counts" + (
            "; raw (non-integrated) noise above the limit" if st == Status.WARN else ""
        )
        if _mark(sub, st, msg, date):
            sub.criteria = f"sigma <= {sigma_max:g} counts" + (
                f" (WARN up to {fail_at:g})" if fail_at > sigma_max else ""
            )
            changed += 1
    return changed


def _t05_2(r: TestResult, ctx: _Ctx, date: str) -> int:
    from lio.analysis import Level
    from lio.suite.judge import judge, out_of_range

    n = ctx.th.integer("channel.meas_n")
    changed = 0
    for sub in r.subs:
        hole = _hole(sub.id)
        det = sub.id.rsplit("/", 1)[-1]
        if hole is None or "net" not in sub.measured or det not in ctx.cfg.detectors:
            continue
        if out_of_range(ctx, hole, det):  # type: ignore[arg-type]
            continue
        j = judge(ctx, hole, det, float(sub.measured["net"]), n)  # type: ignore[arg-type]
        st = Status(j.verdict.status)
        msg = f"net {float(sub.measured['net']):+.0f} ({j.detection.level}); {j.verdict.reason}"
        if _mark(sub, st, msg, date):
            sub.criteria = (
                f"expect {j.expect}: signal >= {j.detection.signal_threshold:.0f}"
                if j.expect != Level.WEAK
                else f"expect weak: >= {j.detection.weak_threshold:.0f}"
            )
            sub.measured = {**sub.measured, "expect": j.expect, "observed": j.detection.level}
            changed += 1
    return changed


def _t05_3(r: TestResult, ctx: _Ctx, date: str) -> int:
    from lio.suite.judge import (
        absence_unresolved,
        classify,
        never_fail_absence,
        observed_pattern,
        out_of_range,
    )

    n = ctx.th.integer("channel.meas_n")
    changed = 0
    for sub in r.subs:
        if not sub.id.endswith("/pattern"):
            continue
        hole = _hole(sub.id)
        nets = {k[len("net_") :]: float(v) for k, v in sub.measured.items() if k.startswith("net_")}
        if hole is None or not nets:
            continue
        ch = ctx.cfg.channel(hole)
        dets = list(nets)
        observed = observed_pattern(ctx, hole, nets, n)  # type: ignore[arg-type]
        expected = {d for d in ch.expected_detectors if d in dets}
        unexpected = sorted(observed - expected)
        missing = sorted(expected - observed)
        unresolved = [
            d
            for d in missing
            if absence_unresolved(
                ctx,  # type: ignore[arg-type]
                classify(ctx, d, nets[d], n, expect=ch.expect_for(d)),  # type: ignore[arg-type]
            )
        ]
        missing = [d for d in missing if d not in unresolved]
        ignored = sorted(d for d in dets if out_of_range(ctx, hole, d))  # type: ignore[arg-type]
        if not unexpected and not missing:
            st, msg = Status.PASS, f"seen by {sorted(observed) or 'nothing'} as expected"
            if ignored:
                msg += f" ({', '.join(ignored)} not judged: outside its range)"
            if unresolved:
                st = Status.WARN
                msg += (
                    f"; {unresolved} not resolved by this reading (detection limit above "
                    "the channel's level; T13.1 judges it)"
                )
        else:
            parts = []
            if unexpected:
                parts.append(f"unexpected response on {unexpected}")
            if missing:
                parts.append(f"no response on {missing}")
            msg = "; ".join(parts) + ": possible swapped, misrouted or stuck-on channel"
            st = Status.WARN if never_fail_absence(ctx, hole) else Status.FAIL  # type: ignore[arg-type]
        if _mark(sub, st, msg, date):
            changed += 1
    return changed


def _t06_3(r: TestResult, ctx: _Ctx, nets: dict[tuple[int, str], float], date: str) -> int:
    """Re-judge 'no response' on the shared holes with the unresolvable rule."""
    from lio.analysis import Level
    from lio.suite.judge import absence_unresolved, classify

    n = ctx.th.integer("channel.meas_n")
    changed = 0
    for sub in r.subs:
        hole = _hole(sub.id)
        if hole is None or sub.status.rank < Status.FAIL.rank:
            continue
        missing: list[tuple[str, bool]] = []
        for d in ("opt101", "ingaas"):
            if (hole, d) not in nets:
                missing = []
                break
            x = classify(ctx, d, nets[(hole, d)], n, expect=Level.SIGNAL)  # type: ignore[arg-type]
            if x.level == Level.NONE:
                missing.append((d, absence_unresolved(ctx, x)))  # type: ignore[arg-type]
        if missing and all(u for _, u in missing):
            dets = [d for d, _ in missing]
            if _mark(
                sub,
                Status.WARN,
                f"{dets} not resolved by this reading (detection limit above the channel's "
                "level; T13.1 judges it)",
                date,
            ):
                changed += 1
    return changed


def _t05_1(r: TestResult, cfg: HwConfig, date: str) -> int:
    """The live T05.1 now judges RAIL B on hole 11 (OPT101). A run that judged it on
    hole 12 (InGaAs) cannot be re-measured: its RAIL B result is graded superseded."""
    changed = 0
    for sub in r.subs:
        if (
            sub.id.startswith("T05.1/B/h12/")
            and sub.status.rank >= Status.FAIL.rank
            and _mark(
                sub,
                Status.WARN,
                f"{sub.message.split(' [')[0]} — superseded: RAIL B gating is now judged on "
                "hole 11 with the OPT101 (an empty chamber returns too little light to hole 12 "
                "for the InGaAs to resolve); not re-measured here",
                date,
            )
        ):
            changed += 1
    return changed


def _repeatability(r: TestResult, cfg: HwConfig, date: str) -> int:
    try:
        warn = str(cfg.thresholds.raw("repeatability.unstable_status")) == "warn"
    except ConfigError:
        warn = False
    if not warn:
        return 0
    changed = 0
    for sub in r.subs:
        if (
            sub.status == Status.FAIL
            and "SD" in sub.criteria
            and _mark(sub, Status.WARN, sub.message.split(" [")[0], date)
        ):
            changed += 1
    return changed


def _t13_1(r: TestResult, cfg: HwConfig, date: str) -> TestResult | None:
    from lio.scan.analysis import analyse
    from lio.suite.checks.t13_scan import scan_result

    folder = Path(str(r.measured.get("run") or ""))
    if not (folder / "cube.csv.gz").exists():
        return None
    a = analyse(folder, cfg)
    new = scan_result(a, folder)
    new.duration_s = r.duration_s
    old = {s.id: s.status for s in r.subs}
    for s in new.subs:
        was = old.get(s.id)
        if was is not None and was != s.status:
            s.message = f"{s.message} [{NOTE.format(date=date, old=was.value)}]"
    return new


def regrade_record(record: RunRecord, cfg: HwConfig) -> tuple[RunRecord, dict[str, int]]:
    """A copy of ``record`` with the affected tests judged again (see module doc)."""
    date = dt.date.today().isoformat()
    rec = copy.deepcopy(record)
    ctx = _Ctx(cfg, _dark_sigmas(rec, cfg))
    nets: dict[tuple[int, str], float] = {}
    for r0 in rec.results:
        if r0.id == "T05.2":
            for s0 in r0.subs:
                h0 = _hole(s0.id)
                if h0 is not None and "net" in s0.measured:
                    nets[(h0, s0.id.rsplit("/", 1)[-1])] = float(s0.measured["net"])
    changes: dict[str, int] = {}
    out: list[TestResult] = []
    for r in rec.results:
        n = 0
        if r.id == "T03.2":
            n = _t03_2(r, cfg, date)
        elif r.id == "T05.1":
            n = _t05_1(r, cfg, date)
        elif r.id == "T05.2":
            n = _t05_2(r, ctx, date)
        elif r.id == "T05.3":
            n = _t05_3(r, ctx, date)
        elif r.id == "T06.3":
            n = _t06_3(r, ctx, nets, date)
        elif r.id in ("T05.5", "T08.2"):
            n = _repeatability(r, cfg, date)
        elif r.id == "T13.1":
            new = _t13_1(r, cfg, date)
            if new is not None:
                n = sum(
                    1
                    for a, b in zip(
                        sorted(r.subs, key=lambda s: s.id),
                        sorted(new.subs, key=lambda s: s.id),
                        strict=False,
                    )
                    if a.status != b.status
                )
                r = new
        if n and r.subs:
            r.status = worst([s.status for s in r.subs])
        if n:
            changes[r.id] = n
        out.append(r)
    rec.results = out
    th = cfg.thresholds
    v = overall_verdict(
        rec.results,
        max_channel_fails=th.integer("verdict.max_channel_fails"),
        limited_holes=th.ints("verdict.limited_holes"),
    )
    rec.verdict = {"verdict": v.verdict.value, "reasons": v.reasons, "counts": rec.counts()}
    stamp = dt.datetime.now().astimezone()
    rec.metadata = {
        **dict(rec.metadata or {}),
        "regraded_from": record.run_id,
        "regraded_at": stamp.isoformat(timespec="seconds"),
        "regraded_config_sha256": cfg.sha256,
        "regraded_tests": ",".join(sorted(changes)),
    }
    rec.run_id = f"{stamp:%Y%m%d-%H%M%S}_regrade_of_{record.run_id}"
    return rec, changes


def regrade_run(run_folder: Path, cfg: HwConfig, results_root: Path) -> tuple[Path, RunRecord]:
    """Re-grade ``run_folder/results.json`` into a new run folder; returns (folder, record)."""
    from lio.report import write_run

    src = RunRecord.load(run_folder / "results.json")
    rec, _ = regrade_record(src, cfg)
    folder = results_root / rec.run_id
    if folder.exists():
        raise FileExistsError(folder)
    write_run(rec, folder, cfg=cfg, meas_log=None)
    return folder, rec


def latest_hardware_run(results_root: Path) -> Path | None:
    """The newest whole-system hardware run that is not itself a re-grade."""
    for f in sorted(results_root.glob("*_host/results.json"), reverse=True):
        if "_regrade_of_" not in f.parent.name:
            return f.parent
    return None


def changed_summary(changes: dict[str, int]) -> str:
    return ", ".join(f"{k} ({v})" for k, v in sorted(changes.items())) or "nothing"


__all__ = ["changed_summary", "latest_hardware_run", "regrade_record", "regrade_run"]
