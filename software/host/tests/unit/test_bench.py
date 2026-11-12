"""M6 (plan WP7): benchmark plan / ingest / report tooling."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from lio import bench

pytestmark = pytest.mark.unit

LAYOUT = bench.Layout(
    aisles={"foods": (1, 20), "supplements": (21, 22), "otc": (23, 24)},
    shelves=(1, 6),
    facings=(1, 30),
)


def test_wilson_matches_known_values() -> None:
    p, lo, hi = bench.wilson(7, 10)
    assert p == 0.7 and round(lo, 4) == 0.3968 and round(hi, 4) == 0.8922
    _, lo0, hi0 = bench.wilson(0, 10)
    assert lo0 == 0.0 and round(hi0, 4) == 0.2775
    assert bench.fmt_wilson(0, 0).startswith("n/a")


def test_plan_is_seeded_stratified_and_written(tmp_path: Path) -> None:
    rows, meta = bench.plan("Store A", "grocery", 30, 7, LAYOUT)
    again, _ = bench.plan("Store A", "grocery", 30, 7, LAYOUT)
    assert rows == again
    assert meta["strata"] == {"foods": 10, "supplements": 10, "otc": 10}
    for r in rows:
        lo, hi = LAYOUT.aisles[r["stratum"]]
        assert lo <= r["aisle"] <= hi
    assert len({(r["stratum"], r["aisle"], r["shelf"], r["facing"]) for r in rows}) == 30
    out = tmp_path / "sheet.csv"
    bench.write_sheet(rows, meta, out)
    assert csv.DictReader(out.open()).fieldnames == bench.SHEET_COLUMNS
    assert (tmp_path / "sheet.plan.json").exists()
    other, _ = bench.plan("Store A", "grocery", 30, 8, LAYOUT)
    assert other != rows  # a different seed draws different slots


def test_uneven_shares() -> None:
    rows, meta = bench.plan(
        "S", "pharmacy", 10, 1, LAYOUT, {"foods": 0.2, "supplements": 0.3, "otc": 0.5}
    )
    assert meta["strata"] == {"foods": 2, "supplements": 3, "otc": 5} and len(rows) == 10


def test_completeness_and_report() -> None:
    assert bench.completeness(["sugar", "salt"], ["Sugar", "Salt", "Molasses"]) == 2 / 3
    assert bench.completeness([], ["x"]) is None
    items = [
        {"slot": 1, "stratum": "foods", "gtin14": "1", "sources": ["usda"], "has_list": True, "completeness": 1.0,
         "variant_correct": True, "truncation_flags": [], "badge_fields": {"VERIFIED": 0, "ATTESTED": 3, "UNVERIFIED": 1},
         "operator_seconds": 40.0, "pipeline_seconds": 3.0, "errors": []},
        {"slot": 2, "stratum": "otc", "gtin14": "2", "sources": [], "has_list": False, "needs_printed_ndc": True,
         "truncation_flags": ["x"], "badge_fields": {"VERIFIED": 2, "ATTESTED": 0, "UNVERIFIED": 0}, "errors": ["no list"]},
    ]  # fmt: skip
    md = bench.report(items, "T")
    assert "| Any source found the product | 1/2 = 50%" in md
    assert "OTC: needs the printed NDC" in md and "slot 2: no list" in md
    assert "median 40 s over 1 items" in md
