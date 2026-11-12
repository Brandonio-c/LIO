"""M3: derivations (exact intervals with units) and z3 bounds with certificates."""

from __future__ import annotations

import copy
import json
from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("lxml")
pytest.importorskip("lxml")

from lio_verify.expr import Context, ExprError, evaluate, unit_mul
from lio_verify.interpret import load_tables
from lio_verify.interval import Interval
from lio_verify.lp import LpError, check_bound, linear

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
COMP = REPO / "composition"
TABLES = load_tables(COMP / "rules")


def record(name: str) -> dict[str, Any]:
    return dict(json.loads((COMP / "records" / f"{name}.json").read_text()))


def ctx_of(rec: dict[str, Any]) -> Context:
    values = {x["id"]: Interval.from_json(x["value"]) for x in rec["facts"] + rec["derivations"]}
    formulas = {s["id"]: s["formula"] for s in rec["substances"] if "formula" in s}
    return Context(values, TABLES, rec["toolchain"]["rules_versions"], formulas)


def units_of(rec: dict[str, Any]) -> dict[str, str]:
    return {v["name"]: v["unit"] for v in rec["variables"]}


def deriv(rec: dict[str, Any], did: str) -> tuple[Interval, str]:
    return Interval.from_json(next(d for d in rec["derivations"] if d["id"] == did)["value"])


def bound(rec: dict[str, Any], bid: str) -> dict[str, Any]:
    return next(b for b in rec["bounds"] if b["id"] == bid)


CITRUCEL = "citrucel_orange_300680418301"
RECORDS = ["citrucel_orange_300680418301", "jif_creamy_16oz_051500255162", "nutella_fr_3017620422003",
           "nutricost_magnesium_oxide_702669934398", "swanson_lowat_blend_087614040622"]  # fmt: skip


# ------------------------------------------------------------- spec §8 values


def test_energy_to_sugars_spec_value() -> None:
    assert deriv(record(CITRUCEL), "D1") == (Interval(F(55, 4), F(65, 4), True, False), "g")


def test_calcium_phosphates_contain_the_spec_cross_check() -> None:
    """Spec §8 gives the calcium-phosphate range with 4-figure molar masses and calcium
    exactly 80 mg: 80*310.18/(3*40.08) .. 80*136.06/40.08 (the spec prints the ends the other
    way round). Our interval also allows for 80 mg being rounded (21 CFR 201.70(b): nearest
    5 mg) and for the IUPAC uncertainty of the atomic weights, so it must contain that range."""
    iv, unit = deriv(record(CITRUCEL), "D2")
    assert unit == "mg"
    spec_lo = 80 * F("310.18") / (3 * F("40.08"))
    spec_hi = 80 * F("136.06") / F("40.08")
    assert spec_lo < spec_hi
    assert iv.contains(spec_lo) and iv.contains(spec_hi)
    assert F(199) < iv.lo < F(200) and F(280) < iv.hi < F(281)


def test_per_100g_rescale() -> None:
    assert deriv(record(CITRUCEL), "D4") == (Interval.point(F(200, 19)), "g")


def test_nutricost_data_are_consistent() -> None:
    rec = record("nutricost_magnesium_oxide_702669934398")
    assert next(c for c in rec["constraints"] if c["id"] == "C1")["status"] == "entailed"
    purity, _ = deriv(rec, "D2")
    assert F("0.9285") < purity.lo <= purity.hi < F("0.9287")


# ---------------------------------------------------------------- expressions


def test_units_algebra() -> None:
    assert unit_mul("kcal", "kcal/g", -1) == "g"
    assert unit_mul("g", "%/g") == "%"
    assert unit_mul("mg", "1") == "mg"


def test_expression_errors_fail_closed() -> None:
    ctx = ctx_of(record(CITRUCEL))
    with pytest.raises(ExprError):
        evaluate(["add", "F1", "F3"], ctx)  # g + mg
    with pytest.raises(ExprError):
        evaluate(["div", "F1", "N:0"], ctx)
    with pytest.raises(ExprError):
        evaluate("F99", ctx)
    with pytest.raises(LpError):
        linear(["mul", "V:sucrose", "V:maltodextrin"], {"sucrose": "g", "maltodextrin": "g"})


def test_derivations_recompute_exactly() -> None:
    for name in RECORDS:
        rec = record(name)
        ctx = ctx_of(rec)
        for d in rec["derivations"]:
            iv, unit = evaluate(d["expr"], ctx)
            assert iv.to_json(unit) == d["value"], (name, d["id"])


# -------------------------------------------------------------------- bounds


@pytest.mark.parametrize("name", RECORDS)
def test_bound_certificates_check(name: str) -> None:
    rec = record(name)
    for b in rec["bounds"]:
        assert check_bound(b, rec["constraints"], units_of(rec), ctx_of(rec)) == [], b["id"]


def test_citrucel_bounds() -> None:
    rec = record(CITRUCEL)
    assert Interval.from_json(bound(rec, "B1")["result"]) == (
        Interval(F(0), F(65, 4), False, False),
        "g",
    )
    others, _ = Interval.from_json(bound(rec, "B3")["result"])
    assert F("0.17") < others.lo < F("0.18") and F("2.76") < others.hi < F("2.77")


def test_tampered_witness_fails() -> None:
    rec = record(CITRUCEL)
    b = copy.deepcopy(bound(rec, "B3"))
    b["certificate"]["max"]["witness"]["sucrose"] = "1"
    assert check_bound(b, rec["constraints"], units_of(rec), ctx_of(rec))


def test_narrower_than_proven_fails() -> None:
    rec = record("swanson_lowat_blend_087614040622")
    b = copy.deepcopy(bound(rec, "B1"))
    b["result"]["hi"] = "299"  # proven: below 300 mg
    b["certificate"]["max"]["value"] = "299"
    assert check_bound(b, rec["constraints"], units_of(rec), ctx_of(rec))


def test_wider_than_proven_is_reported_too() -> None:
    """A looser bound is sound but its witness no longer reaches the stated end."""
    rec = record("swanson_lowat_blend_087614040622")
    b = copy.deepcopy(bound(rec, "B1"))
    b["result"]["hi"] = "301"
    b["certificate"]["max"]["value"] = "301"
    assert check_bound(b, rec["constraints"], units_of(rec), ctx_of(rec))
