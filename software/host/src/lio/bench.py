"""Coverage benchmark tooling (plan WP7; protocol: docs/COVERAGE_BENCHMARK_PROTOCOL.md).

    lio bench plan   --store "Kroger, Bethesda" --format grocery --n 40 --seed 7 --out sheet.csv
    lio bench ingest --sheet sheet.csv --photos photos/ --out ingest.jsonl
    lio bench report --ingest ingest.jsonl --out report.md

``plan`` draws random (aisle, shelf, facing) slots per stratum before the visit
(seeded; the seed and parameters are written next to the sheet). In the store the
operator takes the product at each slot (nearest to the right if the slot is empty,
logging any substitution), photographs barcode, front, facts panel and, for OTC
drugs, the printed NDC, and fills in the sheet. ``ingest`` runs the full pipeline on
each item; ``report`` computes the metrics with Wilson 95% intervals, by stratum
and by source.

The statistics here use ordinary floats: they describe the benchmark, they are not
values of the verified layer.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STRATA = ("foods", "supplements", "otc")
RULE = "nearest product to the right if the facing is empty; log a substitution"
SHEET_COLUMNS = [
    "slot",
    "stratum",
    "store",
    "aisle",
    "shelf",
    "facing",
    "rule",
    "substituted",
    "barcode",
    "photo_barcode",
    "photo_front",
    "photo_facts",
    "photo_ndc",
    "variant_correct",
    "seconds",
    "notes",
]
SOURCES = ("crosswalk", "usda", "dsld", "openfda", "ndc", "smartlabel", "openfoodfacts")
VERIFIABLE = {"crosswalk", "dsld", "openfda", "ndc"}  # structured label documents (SPL, DSLD)


# ------------------------------------------------------------------- statistics
def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float, float]:
    """Proportion k/n with its Wilson score 95% interval."""
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def fmt_wilson(k: int, n: int) -> str:
    if n == 0:
        return "n/a (0 items)"
    p, lo, hi = wilson(k, n)
    return f"{k}/{n} = {p:.0%} (95% CI {lo:.0%} to {hi:.0%})"


# ------------------------------------------------------------------------- plan
@dataclass
class Layout:
    aisles: dict[str, tuple[int, int]]  # stratum -> aisle range in this store
    shelves: tuple[int, int]
    facings: tuple[int, int]


def parse_range(text: str) -> tuple[int, int]:
    a, _, b = text.partition("-")
    lo, hi = int(a), int(b or a)
    if lo > hi:
        raise ValueError(f"bad range {text!r}")
    return lo, hi


def plan(
    store: str, fmt: str, n: int, seed: int, layout: Layout, shares: dict[str, float] | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The sampling sheet for one store visit: equal thirds by default."""
    shares = shares or {s: 1 / len(STRATA) for s in STRATA}
    rng = random.Random(seed)
    counts = {s: round(n * shares.get(s, 0)) for s in STRATA}
    while sum(counts.values()) != n:  # fix rounding on the largest stratum
        big = max(counts, key=lambda k: shares.get(k, 0))
        counts[big] += 1 if sum(counts.values()) < n else -1
    rows: list[dict[str, Any]] = []
    for stratum in STRATA:
        lo, hi = layout.aisles[stratum]
        seen: set[tuple[int, int, int]] = set()
        while sum(1 for r in rows if r["stratum"] == stratum) < counts[stratum]:
            slot = (rng.randint(lo, hi), rng.randint(*layout.shelves), rng.randint(*layout.facings))
            if slot in seen:
                continue
            seen.add(slot)
            rows.append(
                {c: "" for c in SHEET_COLUMNS}
                | {
                    "stratum": stratum,
                    "store": store,
                    "aisle": slot[0],
                    "shelf": slot[1],
                    "facing": slot[2],
                    "rule": RULE,
                }
            )
    rng.shuffle(rows)  # visiting order
    for i, r in enumerate(rows, start=1):
        r["slot"] = i
    meta = {
        "store": store,
        "format": fmt,
        "n": n,
        "seed": seed,
        "strata": counts,
        "aisles": {k: list(v) for k, v in layout.aisles.items()},
        "shelves": list(layout.shelves),
        "facings": list(layout.facings),
        "planned_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    return rows, meta


def write_sheet(rows: list[dict[str, Any]], meta: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    out.with_suffix(".plan.json").write_text(json.dumps(meta, indent=1) + "\n")


# ----------------------------------------------------------------------- ingest
def _norm(s: str) -> str:
    return " ".join(re.sub(r"\([^)]*\)", " ", s.lower()).replace(",", " ").split())


def completeness(db_items: list[str], photo_items: list[str]) -> float | None:
    """Share of the photo's ingredients that the database list names (None if either is missing)."""
    if not db_items or not photo_items:
        return None
    db = {_norm(x) for x in db_items}
    hit = sum(1 for p in photo_items if any(_norm(p) in d or d in _norm(p) for d in db if d))
    return hit / len(photo_items)


def ingest_item(row: dict[str, str], photos: Path, lookup: Any) -> dict[str, Any]:
    from lio.foods import barcode as bc
    from lio.foods import ocr
    from lio.foods.panels import parse

    t0 = time.monotonic()
    out: dict[str, Any] = {
        "slot": row["slot"],
        "stratum": row["stratum"],
        "store": row["store"],
        "substituted": row.get("substituted", ""),
        "errors": [],
    }
    code = (row.get("barcode") or "").strip()
    if not code and row.get("photo_barcode"):
        try:
            best = bc.best_code(bc.decode_image((photos / row["photo_barcode"]).read_bytes()))
            code = best[0].gtin14 if best else ""
        except (OSError, bc.BarcodeError) as e:
            out["errors"].append(f"barcode photo: {e}")
    if not code:
        out["errors"].append("no barcode")
        return out
    try:
        g = bc.normalise(code)
    except bc.BarcodeError as e:
        out["errors"].append(str(e))
        return out
    out["gtin14"] = g.gtin14
    res = lookup.lookup(g)
    info = res.info
    out["sources"] = res.sources
    out["matched_forms"] = info.get("matched_forms", {})
    parts = info.get("ingredient_parts") or []
    out["has_list"] = bool(parts)
    db_items: list[str] = []
    for p in parts:
        if p["role"] in ("active", "inactive", "food", "dietary", "other"):
            db_items += re.split(
                r",\s*",
                re.sub(r"(?i)^(active|inactive|other)\s+ingredients?[^:]*:?", "", p["text"]),
            )
    out["truncation_flags"] = info.get("truncation_flags", [])
    out["needs_printed_ndc"] = bool((info.get("drug_resolution") or {}).get("needs_printed_ndc"))
    badge = {"VERIFIED": 0, "ATTESTED": 0, "UNVERIFIED": 0}
    for p in parts:
        badge["VERIFIED" if p["source"] in VERIFIABLE else "UNVERIFIED"] += 1
    if row.get("photo_facts"):
        try:
            img = (photos / row["photo_facts"]).read_bytes()
            lines, engine = ocr.recognise_any(img)
            kind = {"otc": "drug_facts", "supplements": "supplement_facts"}.get(row["stratum"])
            photo_items: list[str] = []
            if kind:
                panel = parse(kind, lines, ocr.upright_size(img)) or {}
                inact = (panel.get("inactive") or panel.get("other_ingredients") or {}).get(
                    "items", []
                )
                photo_items = [a["text"] for a in panel.get("actives", [])] + list(inact)
                photo_items += [r["name"] for r in panel.get("rows", [])]
            else:
                rows = ocr.panel_rows(lines, ocr.upright_size(img))
                badge["ATTESTED"] += len(rows)
                photo_items = []
            badge["ATTESTED"] += len(photo_items)
            out["photo"] = {"engine": engine, "fields": len(photo_items)}
            out["completeness"] = completeness(db_items, photo_items)
        except (OSError, ocr.OcrError) as e:
            out["errors"].append(f"facts photo: {e}")
    if row.get("photo_ndc") and out["needs_printed_ndc"]:
        try:
            from lio.foods.drugid import DrugResolver

            img = (photos / row["photo_ndc"]).read_bytes()
            lines, _ = ocr.recognise_any(img)
            cands = ocr.ndc_candidates(lines, ocr.upright_size(img))
            hit = DrugResolver(lookup).resolve_printed(cands[0]["ndc"]) if cands else None
            out["printed_ndc"] = {
                "candidates": [c["ndc"] for c in cands],
                "setid": (hit or {}).get("setid"),
            }
        except (OSError, ocr.OcrError) as e:
            out["errors"].append(f"NDC photo: {e}")
    out["badge_fields"] = badge
    vc = (row.get("variant_correct") or "").strip().lower()
    out["variant_correct"] = None if vc == "" else vc in ("y", "yes", "true", "1")
    out["operator_seconds"] = float(row["seconds"]) if (row.get("seconds") or "").strip() else None
    out["pipeline_seconds"] = round(time.monotonic() - t0, 2)
    return out


def ingest(sheet: Path, photos: Path, out: Path, lookup: Any) -> list[dict[str, Any]]:
    with sheet.open(newline="") as f:
        rows = list(csv.DictReader(f))
    items = [ingest_item(r, photos, lookup) for r in rows]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(i, sort_keys=True) + "\n" for i in items))
    return items


# ----------------------------------------------------------------------- report
def report(items: list[dict[str, Any]], title: str = "Coverage benchmark") -> str:
    buf = io.StringIO()
    w = buf.write
    w(f"# {title}\n\n{len(items)} items. Proportions with Wilson 95% confidence intervals.\n\n")
    groups = [("all", items)] + [(s, [i for i in items if i["stratum"] == s]) for s in STRATA]
    w("| Measure | " + " | ".join(g for g, _ in groups) + " |\n|---|" + "---|" * len(groups) + "\n")

    def row(label: str, pred: Any, base: Any = None) -> None:
        cells = []
        for _, its in groups:
            pool = [i for i in its if (base(i) if base else "gtin14" in i)]
            cells.append(fmt_wilson(sum(1 for i in pool if pred(i)), len(pool)))
        w(f"| {label} | " + " | ".join(cells) + " |\n")

    row("Any source found the product", lambda i: bool(i.get("sources")))
    for s in SOURCES:
        row(f"Source hit: {s}", lambda i, s=s: s in (i.get("sources") or []))
    row("Ingredient list from some source", lambda i: i.get("has_list"))
    row(
        "List complete vs the facts photo",
        lambda i: i.get("completeness") == 1.0,
        base=lambda i: i.get("completeness") is not None,
    )
    row(
        "Variant correct (operator)",
        lambda i: i.get("variant_correct") is True,
        base=lambda i: i.get("variant_correct") is not None,
    )
    row("Truncation flag raised", lambda i: bool(i.get("truncation_flags")))
    row(
        "OTC: needs the printed NDC",
        lambda i: i.get("needs_printed_ndc"),
        base=lambda i: i["stratum"] == "otc" and "gtin14" in i,
    )
    w(
        "\n**Badge mix by source class** (fields from SPL/DSLD/crosswalk: VERIFIED-capable; "
        "FDC and Open Food Facts: "
        "UNVERIFIED; photo fields: ATTESTED once signed):\n\n"
    )
    for g, its in groups:
        tot = {
            k: sum(i.get("badge_fields", {}).get(k, 0) for i in its)
            for k in ("VERIFIED", "ATTESTED", "UNVERIFIED")
        }
        n = sum(tot.values())
        w(
            f"- {g}: "
            + ", ".join(f"{k} {fmt_wilson(v, n)}" for k, v in tot.items())
            + " (fields are not independent: intervals are indicative)\n"
        )
    times = sorted(i["operator_seconds"] for i in items if i.get("operator_seconds") is not None)
    ptimes = sorted(i["pipeline_seconds"] for i in items if i.get("pipeline_seconds") is not None)
    op = (
        f"median {times[len(times) // 2]:.0f} s over {len(times)} items"
        if times
        else "not recorded"
    )
    pt = f"median {ptimes[len(ptimes) // 2]:.1f} s" if ptimes else "n/a"
    w(f"\n**Operator time** per item: {op}. Pipeline time: {pt}.\n")
    errs = [f"slot {i['slot']}: {e}" for i in items for e in i.get("errors", [])]
    if errs:
        w("\n**Errors**\n\n" + "".join(f"- {e}\n" for e in errs))
    return buf.getvalue()
