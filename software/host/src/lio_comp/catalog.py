"""The documents that rule tables and golden records cite, by name.

``python -m lio_comp.catalog --store composition/sources`` snapshots each one
and writes ``catalog.json`` (name -> SHA-256) next to the store. Re-running
adds new retrievals; changed upstream bytes become new documents, and the
catalog then names the new hash (the old one stays in the store).
"""

from __future__ import annotations

import argparse
import json
import os
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
    secret: str | None = None  # name of a key the request needs (never recorded)


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


GSRS = "https://gsrs.ncats.nih.gov/api/v1/substances/search"


def _gsrs(unii: str, name: str) -> Doc:
    return Doc(
        f"gsrs_unii_{unii}",
        f"{GSRS}?q=root_approvalID:{unii}&top=1",
        {"unii": unii, "name": name},
        "application/json",
    )


# Golden records (spec §8): the documents their facts cite.
GOLDEN: tuple[Doc, ...] = (
    Doc(
        "dailymed_spl_citrucel_9d5f2244",
        "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/"
        "9d5f2244-a610-4d45-b6e8-e79bb17a558f.xml",
        {"spl_setid": "9d5f2244-a610-4d45-b6e8-e79bb17a558f"},
        "application/xml",
    ),
    Doc(
        "fdc_food_2770309_jif_creamy_16oz",
        "https://api.nal.usda.gov/fdc/v1/food/2770309",
        {"fdc_id": "2770309", "gtin": "00051500255162"},
        "application/json",
        secret="api_key",
    ),
    Doc(
        "dsld_label_223424_nutricost_mgo",
        "https://api.ods.od.nih.gov/dsld/v9/label/223424",
        {"dsld_id": "223424", "upc": "7 02669 93439 8"},
        "application/json",
    ),
    Doc(
        "off_product_3017620422003_nutella",
        "https://world.openfoodfacts.org/api/v2/product/3017620422003.json",
        {"gtin": "3017620422003"},
        "application/json",
    ),
    Doc(
        "dailymed_spl_careone_ibuprofen_016299ef",
        "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/"
        "016299ef-ad40-46fd-acfc-e74ffee3d9b4.xml",
        {"spl_setid": "016299ef-ad40-46fd-acfc-e74ffee3d9b4"},
        "application/xml",
    ),
    Doc(
        "dailymed_image_careone_ibuprofen_carton",
        "https://dailymed.nlm.nih.gov/dailymed/image.cfm?setid=016299ef-ad40-46fd-acfc-e74ffee3d9b4"
        "&name=ibuprofen-200-mg-softgels-pur-1.jpg",
        {
            "spl_setid": "016299ef-ad40-46fd-acfc-e74ffee3d9b4",
            "image": "ibuprofen-200-mg-softgels-pur-1.jpg",
        },
        "image/jpeg",
    ),
    Doc(
        "dailymed_ndcs_careone_016299ef",
        "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/016299ef-ad40-46fd-acfc-e74ffee3d9b4/ndcs.json",
        {"spl_setid": "016299ef-ad40-46fd-acfc-e74ffee3d9b4"},
        "application/json",
    ),
    Doc(
        "dailymed_spls_ndc_41520-745-18",
        "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?ndc=41520-745-18",
        {"ndc": "41520-745-18"},
        "application/json",
    ),
    Doc(
        "dailymed_spls_ndc_0135-0089-71",
        "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?ndc=0135-0089-71",
        {"ndc": "0135-0089-71"},
        "application/json",
    ),
    Doc(
        "dailymed_history_careone_016299ef",
        "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/016299ef-ad40-46fd-acfc-e74ffee3d9b4/history.json",
        {"spl_setid": "016299ef-ad40-46fd-acfc-e74ffee3d9b4"},
        "application/json",
    ),
    _gsrs("L11K75P92J", "ANHYDROUS DIBASIC CALCIUM PHOSPHATE"),
    _gsrs("K4C08XP666", "TRICALCIUM PHOSPHATE"),
    _gsrs("EE90ONI6FF", "POTASSIUM CITRATE"),
    _gsrs("3A3U0GI71G", "MAGNESIUM OXIDE"),
    _gsrs("451W47IQ8X", "SODIUM CHLORIDE"),
)


def _secret(name: str) -> tuple[str, str]:
    if name != "api_key":
        raise KeyError(name)
    key = os.environ.get("LIO_USDA_API_KEY", "")
    if not key:
        f = Path(__file__).resolve().parents[4] / "data" / "foods" / "usda_api_key.txt"
        key = f.read_text().strip() if f.exists() else "DEMO_KEY"
    return ("api_key", key)


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
    for d in (*DOCS, *GOLDEN):
        if a.names and d.name not in a.names:
            continue
        secret = _secret(d.secret) if d.secret else None
        cat[d.name] = snapshot(
            a.store, d.url, d.identifiers, media_type=d.media_type, secret=secret
        )
        print(f"{d.name}: {cat[d.name]}")
    catalog_path(a.store).parent.mkdir(parents=True, exist_ok=True)
    catalog_path(a.store).write_bytes(canonical_json(dict(sorted(cat.items()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
