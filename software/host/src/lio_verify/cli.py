"""``lio-verify``: check composition record bundles (spec §6).

    lio-verify composition/records/<id>.json --sources composition/sources \\
        --rules composition/rules [--refetch] [--json report.json]

Exit code 0 when every record passes, 1 when any field FAILED or the record is
malformed, 2 for usage errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lio_verify.verify import FAILED, Report, Verifier


def render(rep: Report) -> str:
    j = rep.to_json()
    lines = [
        f"{j['result']}  {rep.record}",
        "  " + "  ".join(f"{k} {v}" for k, v in j["counts"].items()),
    ]
    for e in rep.errors:
        lines.append(f"  ERROR {e}")
    for f in rep.fields:
        v = f.value
        val = ""
        if v:
            left = "[" if v["lo_closed"] else "("
            right = "]" if v["hi_closed"] else ")"
            val = f"  {left}{v['lo']}, {v['hi']}{right} {v['unit']}"
        line = f"  {f.status:<10} {f.kind:<11} {f.id}{val}"
        if f.assumptions:
            line += f"  assumes {','.join(f.assumptions)}"
        if f.rests_on:
            line += f"  via {' -> '.join(f.rests_on)}"
        lines.append(line)
        if f.status == FAILED or (f.problems and f.kind == "attestation"):
            lines.extend(f"      - {p}" for p in f.problems)
    lines.append("  Assumptions:")
    for a in rep.assumptions:
        ref = f" [{a['rule_ref']}]" if a.get("rule_ref") else ""
        lines.append(f"    {a['id']} ({a['kind']}){ref}: {a['text']}")
    lines.append("  Rules: " + ", ".join(f"{k}@{v}" for k, v in sorted(rep.rules_versions.items())))
    for r in rep.refetch:
        lines.append(f"  refetch {r}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lio-verify", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)  # fmt: skip
    ap.add_argument("records", nargs="+", type=Path)
    ap.add_argument("--sources", type=Path, required=True)
    ap.add_argument("--rules", type=Path, required=True)
    ap.add_argument("--schema", type=Path, default=None)
    ap.add_argument("--refetch", action="store_true", help="re-download sources (informational)")
    ap.add_argument("--json", type=Path, default=None, help="write the report(s) as JSON")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    try:
        v = Verifier(a.sources, a.rules, a.schema)
    except (OSError, ValueError) as e:
        print(f"lio-verify: {e}", file=sys.stderr)
        return 2
    reports = [v.verify(p, refetch=a.refetch) for p in a.records]
    for rep in reports:
        if not a.quiet:
            print(render(rep))
        else:
            print(f"{rep.to_json()['result']}  {rep.record}")
    if a.json:
        a.json.write_text(
            json.dumps([r.to_json() for r in reports], indent=1, sort_keys=True) + "\n"
        )
    return 0 if all(r.ok for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
