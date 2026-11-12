"""M1 of the verifiable composition work: exact intervals, rounding rules, rule tables, schema."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

hypothesis = pytest.importorskip("hypothesis")
jsonschema = pytest.importorskip("jsonschema")

from hypothesis import assume, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from lio_verify.chem import mass_fraction, parse_mf, parse_row, parse_weight  # noqa: E402
from lio_verify.interval import (  # noqa: E402
    Interval,
    IntervalError,
    format_rational,
    parse_rational,
    subtract,
    union,
)
from lio_verify.rounding import Declaration, RoundingError, RoundingRules  # noqa: E402

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
COMP = REPO / "composition"


def rules(name: str) -> dict[str, Any]:
    return dict(json.loads((COMP / "rules" / f"{name}.json").read_text()))


# ---------------------------------------------------------------- strategies

fracs = st.fractions(min_value=-50, max_value=50, max_denominator=12)


@st.composite
def intervals(draw: st.DrawFn) -> Interval:
    a, b = sorted((draw(fracs), draw(fracs)))
    lc, hc = draw(st.booleans()), draw(st.booleans())
    if a == b:
        lc = hc = True
    return Interval(a, b, lc, hc)


@st.composite
def member(draw: st.DrawFn, iv: Interval) -> F:
    choices = []
    if iv.lo_closed:
        choices.append(iv.lo)
    if iv.hi_closed:
        choices.append(iv.hi)
    if iv.lo < iv.hi:
        t = draw(st.fractions(min_value=0, max_value=1, max_denominator=50))
        assume(0 < t < 1)
        choices.append(iv.lo + t * (iv.hi - iv.lo))
    return draw(st.sampled_from(choices))


# ------------------------------------------------------------ rational strings


def test_rational_strings_are_canonical() -> None:
    assert parse_rational("55/4") == F(55, 4)
    assert format_rational(F(-6, 8)) == "-3/4"
    for bad in ["2/4", "+1", "01", "-0", "1/1", "0.5", " 1", 1, 1.5, None]:
        with pytest.raises(IntervalError):
            parse_rational(bad)


def test_empty_intervals_are_refused() -> None:
    with pytest.raises(IntervalError):
        Interval(F(1), F(1), True, False)
    with pytest.raises(IntervalError):
        Interval(F(2), F(1))


# --------------------------------------------------- interval soundness (spec §8)

OPS = {
    "add": (lambda a, b: a + b, lambda x, y: x + y),
    "sub": (lambda a, b: a - b, lambda x, y: x - y),
    "mul": (lambda a, b: a * b, lambda x, y: x * y),
    "min": (lambda a, b: a.min(b), min),
    "max": (lambda a, b: a.max(b), max),
}


@settings(max_examples=400, deadline=None)
@given(st.data(), intervals(), intervals(), st.sampled_from(sorted(OPS)))
def test_interval_ops_are_sound(data: st.DataObject, a: Interval, b: Interval, op: str) -> None:
    f_iv, f_pt = OPS[op]
    x, y = data.draw(member(a)), data.draw(member(b))
    assert f_iv(a, b).contains(f_pt(x, y))


@settings(max_examples=400, deadline=None)
@given(st.data(), intervals(), intervals())
def test_division_is_sound(data: st.DataObject, a: Interval, b: Interval) -> None:
    if b.lo <= 0 <= b.hi:
        with pytest.raises(IntervalError):
            _ = a / b
        return
    x, y = data.draw(member(a)), data.draw(member(b))
    assert (a / b).contains(x / y)


@settings(max_examples=300, deadline=None)
@given(intervals(), intervals(), st.sampled_from(["add", "sub", "mul"]))
def test_closed_ends_are_attained(a: Interval, b: Interval, op: str) -> None:
    """A closed end of a result is reached by some pair of points (tightness). For these
    operators the extremes lie at the ends of the operands (or at 0 for a product)."""
    f_iv, f_pt = OPS[op]
    r = f_iv(a, b)
    pts_a = [p for p in (a.lo, a.hi, F(0), (a.lo + a.hi) / 2) if a.contains(p)]
    pts_b = [p for p in (b.lo, b.hi, F(0), (b.lo + b.hi) / 2) if b.contains(p)]
    vals = {f_pt(x, y) for x in pts_a for y in pts_b}
    if r.lo_closed:
        assert r.lo in vals
    if r.hi_closed:
        assert r.hi in vals


@settings(max_examples=300, deadline=None)
@given(st.data(), intervals(), intervals())
def test_subtract_and_union(data: st.DataObject, a: Interval, cut: Interval) -> None:
    x = data.draw(member(a))
    parts = subtract(a, cut)
    assert any(p.contains(x) for p in parts) == (not cut.contains(x))
    merged = union([*parts, cut])
    assert any(p.contains(x) for p in merged)


def test_json_round_trip() -> None:
    iv = Interval(F(55, 4), F(65, 4), True, False)
    d = iv.to_json("g")
    assert d == {"lo": "55/4", "hi": "65/4", "lo_closed": True, "hi_closed": False, "unit": "g"}
    assert Interval.from_json(d) == (iv, "g")


# ------------------------------------------------------------ FDA rounding


@pytest.fixture(scope="module")
def fda() -> RoundingRules:
    return RoundingRules(rules("fda_rounding_101_9"))


@pytest.fixture(scope="module")
def otc() -> RoundingRules:
    return RoundingRules(rules("fda_otc_rounding_201"))


def inv(r: RoundingRules, nutrient: str, text: str) -> Interval:
    return r.inverse(nutrient, Declaration.parse(text))


def test_fda_guide_tie_examples(fda: RoundingRules) -> None:
    """FDA Food Labeling Guide (2013), Appendix H: "2.5 to 2.99 g ... round up (e.g., 3 g)",
    "2.01 g to 2.49 g ... round down (e.g., 2 g)"."""
    for x, shown in [("5/2", 3), ("299/100", 3), ("201/100", 2), ("249/100", 2)]:
        assert Declaration("eq", F(shown)) in fda.forward("total_carbohydrate", F(x))
    assert inv(fda, "total_carbohydrate", "3") == Interval(F(5, 2), F(7, 2), True, False)


def test_cfr_percent_dv_examples(fda: RoundingRules) -> None:
    """21 CFR 101.9(c)(8): "Vitamin D 2 mcg 10%, Calcium 260 mg 20%, Iron 8 mg 45%,
    Potassium 235 mg 6%", with the RDIs of 101.9(c)(8)(iv): 20 mcg, 1300 mg, 18 mg, 4700 mg."""
    for amount, rdi, shown in [(2, 20, 10), (260, 1300, 20), (8, 18, 45), (235, 4700, 6)]:
        pct = F(amount, rdi) * 100
        assert fda.forward("vitamin_mineral_percent_dv", pct) == {Declaration("eq", F(shown))}


def test_fda_inverse_values(fda: RoundingRules) -> None:
    assert inv(fda, "calories", "60") == Interval(F(55), F(65), True, False)  # spec §8
    assert inv(fda, "calories", "50") == Interval(F(95, 2), F(55), True, False)
    assert inv(fda, "calories", "0") == Interval(F(0), F(5), True, False)
    assert inv(fda, "total_fat", "0") == Interval(F(0), F(1, 2), True, False)
    assert inv(fda, "total_fat", "5") == Interval(F(19, 4), F(11, 2), True, False)
    assert inv(fda, "sodium", "140") == Interval(F(275, 2), F(145), True, False)
    assert inv(fda, "cholesterol", "<5") == Interval(F(2), F(5))
    assert inv(fda, "protein", "<1") == Interval(F(0), F(1), True, False)
    with pytest.raises(RoundingError):
        inv(fda, "total_fat", "3/10")  # not a 0.5 g step
    with pytest.raises(RoundingError):
        inv(fda, "potassium", "235")  # no CFR increment rule for mineral amounts


def test_otc_mineral_rounding(otc: RoundingRules) -> None:
    """21 CFR 201.70(b): calcium "rounded-off to the nearest 5 milligrams"; ties unstated."""
    assert inv(otc, "calcium", "80") == Interval(F(155, 2), F(165, 2))
    assert inv(otc, "sodium", "10") == Interval(F(19, 2), F(21, 2))
    assert otc.forward("calcium", F(155, 2)) == {Declaration("eq", F(75)), Declaration("eq", F(80))}


@settings(max_examples=500, deadline=None)
@given(
    st.fractions(min_value=0, max_value=2000, max_denominator=40),
    st.sampled_from(["fda_rounding_101_9", "fda_otc_rounding_201"]),
    st.data(),
)
def test_rounding_inverse_contains_original(x: F, table: str, data: st.DataObject) -> None:
    """Spec §8: inverse(forward(x)) contains x, for every nutrient and every allowed display."""
    r = RoundingRules(rules(table))
    nutrient = data.draw(st.sampled_from(sorted(r.bands)))
    decls = r.forward(nutrient, x)
    assert decls
    for d in decls:
        assert r.inverse(nutrient, d).contains(x)


# ------------------------------------------------------------- chemistry


def test_atomic_weight_parsing() -> None:
    assert parse_weight("&nbsp;&nbsp;40.078(4)") == Interval(F("40.074"), F("40.082"))
    assert parse_weight("[1.007&nbsp;84,&nbsp;1.008&nbsp;11]") == Interval(
        F("1.00784"), F("1.00811")
    )
    assert parse_weight("22.989\u00a0769\u00a028(2)") == Interval(
        F("22.98976926"), F("22.98976930")
    )


def test_unii_formulas() -> None:
    assert parse_mf("C6H5O7.3K.H2O") == {"C": 6, "H": 7, "K": 3, "O": 8}
    assert parse_mf("3Ca.2O4P") == {"Ca": 3, "O": 8, "P": 2}


def test_calcium_mass_fractions_bracket_conventional_values() -> None:
    t = rules("atomic_masses")
    w = {el: Interval.from_json(e["weight"])[0] for el, e in t["elements"].items()}
    dcp = mass_fraction("Ca", parse_mf("Ca.HO4P"), w)
    tcp = mass_fraction("Ca", parse_mf("3Ca.2O4P"), w)
    assert dcp.contains(F("40.078") / F("136.055"))
    assert tcp.contains(3 * F("40.078") / F("310.174"))
    assert dcp.hi < tcp.lo  # tricalcium phosphate is richer in calcium


# --------------------------------------------------------------- rule tables


def _source_text(sha: str) -> str | None:
    p = COMP / "sources" / "sha256" / sha[:2] / sha
    if not p.exists():
        return None
    data = p.read_bytes()
    assert hashlib.sha256(data).hexdigest() == sha
    return data.decode("utf-8")


def _citations(obj: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        if "locator" in obj and "sha256" in obj:
            out.append(obj)
        for v in obj.values():
            out.extend(_citations(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_citations(v))
    return out


@pytest.mark.parametrize("path", sorted((COMP / "rules").glob("*.json")), ids=lambda p: p.stem)
def test_rule_citations_match_snapshots(path: Path) -> None:
    table = json.loads(path.read_text())
    assert {"id", "version", "effective_date"} <= set(table)
    cites = _citations(table)
    for c in cites:
        loc = c["locator"]
        if loc["type"] != "char_span":
            continue  # pdf_text: a human-checked citation of an untracked document
        text = _source_text(c["sha256"])
        assert text is not None, f"{c['source']} is not in composition/sources"
        assert text[loc["start"] : loc["end"]] == loc["text"]


def test_atomic_mass_rows_reparse() -> None:
    for el, e in rules("atomic_masses")["elements"].items():
        sym, w = parse_row(e["citation"]["locator"]["text"])
        assert sym == el and w.to_json("1") == e["weight"]


def test_compound_counts_come_from_formulas() -> None:
    for c in rules("compounds")["compounds"].values():
        assert parse_mf(c["unii_mf"]) == c["counts"]


# --------------------------------------------------------------------- schema


def _minimal_record() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "record_id": "example",
        "gtin": "00300680418301",
        "product_name": "x",
        "variant_note": "",
        "physical_sample": {"sample_code": "", "lot": "", "photos": [], "attestation": None,
                            "assumptions": []},
        "variables": [],
        "sources": [],
        "assumptions": [],
        "substances": [],
        "ingredients": [],
        "facts": [],
        "derivations": [
            {
                "id": "D1",
                "quantity": "q",
                "basis": "per_serving",
                "expr": ["div", "F2", "C:atwater.constants.carbohydrate"],
                "assumptions": [],
                "value": {"lo": "55/4", "hi": "65/4", "lo_closed": True, "hi_closed": False,
                          "unit": "g"},
            }
        ],
        "constraints": [],
        "bounds": [],
        "attestations": [],
        "unverified_layer": {"estimates": [], "notes": []},
        "toolchain": {"extractor_version": "", "deriver_version": "", "rules_versions": {}},
    }  # fmt: skip


def test_schema_accepts_rationals_and_rejects_numbers() -> None:
    schema = json.loads((COMP / "schema" / "record.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    v = jsonschema.Draft202012Validator(schema)
    rec = _minimal_record()
    assert not list(v.iter_errors(rec))
    rec["derivations"][0]["value"]["lo"] = 13.75  # a JSON number, not a rational string
    assert list(v.iter_errors(rec))
    rec["derivations"][0]["value"]["lo"] = "2/4"  # not in lowest terms: the schema allows
    assert not list(v.iter_errors(rec))  # it; parse_rational (the verifier) refuses it
