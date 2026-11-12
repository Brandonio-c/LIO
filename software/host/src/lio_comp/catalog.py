"""The documents that rule tables and golden records cite, by name.

``python -m lio_comp.catalog --store composition/sources`` snapshots each one
and writes ``catalog.json`` (name -> SHA-256) next to the store. Re-running
adds new retrievals; changed upstream bytes become new documents, and the
catalog then names the new hash (the old one stays in the store).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from lio_comp.evidence import canonical_json
from lio_comp.fetch import snapshot

ECFR = "https://www.ecfr.gov/api/versioner/v1/full/2026-11-01/title-21.xml"


@dataclass(frozen=True)
class Doc:
    name: str
    url: str
    identifiers: dict[str, str]
    media_type: str | None = None
    tracked: bool = True  # False: too large for git; kept in the local store only


def _ecfr(part: str, section: str) -> Doc:
    return Doc(
        f"ecfr_21cfr{section.replace('.', '_')}",
        f"{ECFR}?part={part}&section={section}",
        {"cfr": f"21 CFR {section}", "ecfr_date": "2026-11-01"},
        "application/xml",
    )


DOCS: tuple[Doc, ...] = (
    _ecfr("101", "101.9"),
    _ecfr("101", "101.4"),
    _ecfr("201", "201.64"),
    _ecfr("201", "201.66"),
    _ecfr("201", "201.70"),
    _ecfr("201", "201.72"),
    Doc(
        "ciaaw_standard_atomic_weights",
        "https://www.ciaaw.org/atomic-weights.htm",
        {"publisher": "IUPAC CIAAW", "table": "standard atomic weights"},
        "text/html",
    ),
    Doc(
        "eu_reg_1169_2011_consolidated_20180101",
        "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02011R1169-20180101",
        {"celex": "02011R1169-20180101"},
        "text/html",
    ),
    Doc(
        "fda_food_labeling_guide_2013",
        "https://www.fda.gov/media/81606/download",
        {"title": "Guidance for Industry: A Food Labeling Guide (January 2013)"},
        "application/pdf",
        tracked=False,
    ),
)


def catalog_path(store: Path) -> Path:
    return store / "catalog.json"


def load(store: Path) -> dict[str, str]:
    p = catalog_path(store)
    return dict(json.loads(p.read_text())) if p.exists() else {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("names", nargs="*", help="only these documents")
    a = ap.parse_args(argv)
    cat = load(a.store)
    for d in DOCS:
        if a.names and d.name not in a.names:
            continue
        cat[d.name] = snapshot(a.store, d.url, d.identifiers, media_type=d.media_type)
        print(f"{d.name}: {cat[d.name]}")
    catalog_path(a.store).parent.mkdir(parents=True, exist_ok=True)
    catalog_path(a.store).write_bytes(canonical_json(dict(sorted(cat.items()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
