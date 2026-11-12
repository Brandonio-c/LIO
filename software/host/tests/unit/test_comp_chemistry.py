"""M4 (plan WP5): compendial assay intervals replace the tricalcium phosphate formula."""

from __future__ import annotations

import json
import shutil
from fractions import Fraction as F
from pathlib import Path

import pytest

pytest.importorskip("lxml")

from snapweb import STORE

from lio_verify.expr import Context, evaluate
from lio_verify.interpret import (
    InterpretError,
    additive_fraction,
    assay_percent,
    load_tables,
)
from lio_verify.interval import Interval
from lio_verify.verify import Verifier

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
RULES = REPO / "composition" / "rules"
CITRUCEL = REPO / "composition" / "records" / "citrucel_orange_300680418301.json"
TABLES = load_tables(RULES)
VERSIONS = {t: TABLES[t]["version"] for t in TABLES}


def test_assay_quote_rule() -> None:
    assert assay_percent(
        "It contains not less than 34.0 percent and not more than 40.0 percent of calcium (Ca)."
    ) == Interval(F(17, 50), F(2, 5))
    with pytest.raises(InterpretError):
        assay_percent("at least 90% of Ca3(PO4)2")


def test_fractions_from_the_cited_monographs() -> None:
    assert additive_fraction("tricalcium_phosphate", TABLES, VERSIONS) == Interval(
        F(17, 50), F(2, 5)
    )
    dcp = additive_fraction("anhydrous_dibasic_calcium_phosphate", TABLES, VERSIONS)
    ca = F("40.078") / F("136.055")  # conventional Ca fraction of CaHPO4
    assert dcp.contains(F(98, 100) * ca) and dcp.contains(F(103, 100) * ca)
    assert F("0.288") < dcp.lo < F("0.289") and F("0.303") < dcp.hi < F("0.304")


def test_plan_values_with_calcium_exactly_80_mg() -> None:
    """Plan WP5: if all calcium is from TCP, TCP is [200, 235.3] mg as-is (Ca exactly 80 mg)."""
    ctx = Context({"Ca": (Interval.point(80), "mg")}, TABLES, VERSIONS, {})
    iv, unit = evaluate(["div", "Ca", "A:additive_assays.tricalcium_phosphate"], ctx)
    assert unit == "mg" and iv == Interval(F(200), F(4000, 17))  # 4000/17 = 235.29...


def test_citrucel_uses_the_assay_rules_and_not_the_formula() -> None:
    rec = json.loads(CITRUCEL.read_text())
    assert "M:Ca:SUB_tcp" not in json.dumps(rec)
    d2 = next(d for d in rec["derivations"] if d["id"] == "D2")
    assert Interval.from_json(d2["value"])[0].lo == F(775, 4)  # 77.5 mg Ca / 0.40
    a6 = next(a for a in rec["assumptions"] if a["id"] == "A6")
    assert a6["rule_ref"] == "additive_assays@1" and "USP 32" in a6["text"]
    assert Verifier(STORE, RULES).verify(CITRUCEL).ok


def test_a_table_that_disagrees_with_its_quote_fails(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    shutil.copytree(RULES, rules)
    shutil.copytree(REPO / "composition" / "schema", tmp_path / "schema")
    p = rules / "additive_assays.json"
    t = json.loads(p.read_text())
    t["entries"]["tricalcium_phosphate"]["interval"]["hi"] = "21/50"  # 42 %: not what USP says
    p.write_text(json.dumps(t))
    rep = Verifier(STORE, rules).verify(CITRUCEL)
    assert not rep.ok
