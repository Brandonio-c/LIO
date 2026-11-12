"""Training export (spec §9): one row per value, with its interval, badge and assumptions.

    python -m lio_comp.export composition/records/*.json --sources composition/sources \
        --rules composition/rules > composition_values.csv

Badges come from running the independent verifier, never from the record itself.
Point estimates from the unverified layer are exported as UNVERIFIED rows.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

from lio_verify.verify import Verifier, effective_assumptions

COLUMNS = [
    "record_id", "gtin14", "sample_code", "kind", "id", "quantity", "basis",
    "lo", "hi", "lo_closed", "hi_closed", "unit", "badge", "assumptions", "method",
]  # fmt: skip


def rows(paths: list[Path], verifier: Verifier) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in paths:
        rec = json.loads(p.read_text())
        rep = verifier.verify(p)
        eff = effective_assumptions(rec)
        meta = {x["id"]: x for x in rec["facts"] + rec["derivations"] + rec["bounds"]}
        head = {"record_id": rec["record_id"], "gtin14": rec["gtin"],
                "sample_code": rec["physical_sample"].get("sample_code", "")}  # fmt: skip
        for f in rep.fields:
            if f.kind not in ("fact", "derivation", "bound") or f.value is None:
                continue
            m = meta.get(f.id, {})
            out.append({
                **head, "kind": f.kind, "id": f.id, "quantity": m.get("quantity", ""),
                "basis": m.get("basis", ""), "lo": f.value["lo"], "hi": f.value["hi"],
                "lo_closed": f.value["lo_closed"], "hi_closed": f.value["hi_closed"],
                "unit": f.value["unit"],
                # a record that fails as a whole verifies none of its values (fail closed)
                "badge": f.status if rep.ok or f.status != "VERIFIED" else "UNVERIFIED",
                "assumptions": ";".join(eff.get(f.id, [])), "method": "",
            })  # fmt: skip
        for e in rec["unverified_layer"]["estimates"]:
            out.append({
                **head, "kind": "estimate", "id": "", "quantity": e["quantity"],
                "basis": e["basis"], "lo": e["value"], "hi": e["value"], "lo_closed": True,
                "hi_closed": True, "unit": e["unit"], "badge": "UNVERIFIED", "assumptions": "",
                "method": e["method"],
            })  # fmt: skip
    return out


def to_csv(table: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in table:
        w.writerow({k: str(v).lower() if isinstance(v, bool) else v for k, v in r.items()})
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)  # fmt: skip
    ap.add_argument("records", nargs="+", type=Path)
    ap.add_argument("--sources", type=Path, required=True)
    ap.add_argument("--rules", type=Path, required=True)
    a = ap.parse_args(argv)
    sys.stdout.write(to_csv(rows(a.records, Verifier(a.sources, a.rules))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
