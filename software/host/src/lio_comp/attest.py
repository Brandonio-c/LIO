"""Operator attestations for golden records: proposals, then signatures.

The software proposes what a label photo says (Apple Vision rows, an ingredient
list); a proposal is never evidence. The operator compares it with the photo and
the pack, and signs:

    python -m lio_comp.attest list
    python -m lio_comp.attest sign <proposal id> --operator "Your Name"

Signed rows are appended to ``composition/attestations/signed.jsonl`` (never
rewritten); golden builders turn them into ATTESTED facts. Rows the operator
corrects can be edited in the proposal before signing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

DIR = Path(__file__).resolve().parents[4] / "composition" / "attestations"
PROPOSALS = DIR / "proposals.jsonl"
SIGNED = DIR / "signed.jsonl"
PATHS = {"proposals": PROPOSALS, "signed": SIGNED}  # tests point these elsewhere


def read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def signed_for(record: str) -> list[dict[str, Any]]:
    """The latest signature of each proposal for a record."""
    rows: dict[str, dict[str, Any]] = {}
    for r in read(PATHS["signed"]):
        if r.get("record") == record:
            rows[r["proposal"]] = r
    return [rows[k] for k in sorted(rows)]


def sign(proposal: str, operator: str, now: str | None = None) -> dict[str, Any]:
    operator = " ".join(operator.split())
    if not operator:
        raise ValueError("the operator's name is required")
    props = [p for p in read(PATHS["proposals"]) if p.get("id") == proposal]
    if not props:
        raise ValueError(f"no proposal {proposal!r}")
    p = props[-1]
    row = {k: v for k, v in p.items() if k not in ("id", "proposed_by")}
    row["proposal"] = proposal
    row["operator"] = operator
    row["signed_at"] = now or dt.datetime.now(dt.timezone.utc).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")
    PATHS["signed"].parent.mkdir(parents=True, exist_ok=True)
    with PATHS["signed"].open("a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sg = sub.add_parser("sign")
    sg.add_argument("proposal")
    sg.add_argument("--operator", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "list":
        done = {r["proposal"] for r in read(PATHS["signed"])}
        for p in read(PATHS["proposals"]):
            state = "signed" if p["id"] in done else "awaiting signature"
            print(f"{p['id']}  [{state}]  {p['kind']} of {p['record']} from {p['photo_source']}")
            for r in p.get("rows", []):
                print(f"    {r['nutrient']:20} {r['text']}")
            if p.get("text"):
                print(f"    {p['text']}")
        return 0
    print(json.dumps(sign(a.proposal, a.operator), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
