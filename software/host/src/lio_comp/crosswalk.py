"""The GTIN -> NDC -> SPL crosswalk (plan WP1): proposals and operator signatures.

``software/host/data/crosswalk/proposals.jsonl`` holds links the software proposes
(e.g. Apple Vision reading "NDC 41520-745-18" on a label image). A proposal is not
evidence. The operator compares it with the carton and signs it:

    python -m lio_comp.crosswalk list
    python -m lio_comp.crosswalk sign 00341520314643 --operator "Your Name"

which appends an attested row to ``gtin_links.jsonl`` (never rewriting earlier
rows). Golden records are then rebuilt with ``python -m lio_comp.golden``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

DIR = Path(__file__).resolve().parents[2] / "data" / "crosswalk"
LINKS = DIR / "gtin_links.jsonl"
PROPOSALS = DIR / "proposals.jsonl"


def read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def link_for(gtin14: str, path: Path = LINKS) -> dict[str, Any] | None:
    rows = [r for r in read(path) if r.get("gtin") == gtin14]
    return rows[-1] if rows else None


def sign(gtin14: str, operator: str, *, proposals: Path = PROPOSALS, links: Path = LINKS,
         now: str | None = None) -> dict[str, Any]:  # fmt: skip
    operator = " ".join(operator.split())
    if not operator:
        raise ValueError("the operator's name is required")
    props = [r for r in read(proposals) if r.get("gtin") == gtin14]
    if not props:
        raise ValueError(f"no proposal for {gtin14}")
    p = props[-1]
    row = {k: v for k, v in p.items() if k not in ("proposed_by",)}
    row["attestation"] = {
        "operator": operator,
        "timestamp": now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "statement": (f"I checked that the {row['method'].replace('_', ' ')} {row['evidence'].get('ndc_text', '')!s} "
                      f"belongs to the product with barcode {gtin14}, and that it is the NDC printed on its carton."),
        "signature": "",
    }  # fmt: skip
    links.parent.mkdir(parents=True, exist_ok=True)
    with links.open("a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sg = sub.add_parser("sign")
    sg.add_argument("gtin")
    sg.add_argument("--operator", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "list":
        signed = {r["gtin"] for r in read(LINKS)}
        for r in read(PROPOSALS):
            state = "signed" if r["gtin"] in signed else "awaiting signature"
            print(
                f"{r['gtin']}  NDC {r['ndc']}  set {r['setid']} v{r['spl_version']}  [{state}]  {r.get('proposed_by', '')}"
            )
        return 0
    print(json.dumps(sign(a.gtin.zfill(14), a.operator), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
