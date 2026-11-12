"""M3 (plan WP2 + WP3): variant-correct structured ingredients, demoted database values."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("lxml")
pytest.importorskip("jsonschema")

from snapweb import STORE

from lio.foods.lookup import flag_truncation, truncation_flags
from lio_comp import attest, golden
from lio_verify import textrules
from lio_verify.interval import Interval
from lio_verify.verify import Verifier

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
COMP = REPO / "composition"
RULES = COMP / "rules"
RECORDS = sorted((COMP / "records").glob("*.json"))


def rec(name: str) -> dict[str, Any]:
    return dict(json.loads((COMP / "records" / f"{name}.json").read_text()))


def verify_obj(r: dict[str, Any], tmp: Path) -> Any:
    p = tmp / "r.json"
    p.write_text(json.dumps(r))
    return Verifier(STORE, RULES).verify(p)


# ------------------------------------------------------------------ WP3 demotion


@pytest.mark.parametrize("path", RECORDS, ids=lambda p: p.stem)
def test_no_fdc_or_off_number_is_a_fact(path: Path) -> None:
    r = json.loads(path.read_text())
    srcs = {s["source_id"]: s["identifiers"].get("catalog_name", "") for s in r["sources"]}
    for f in r["facts"]:
        assert not srcs.get(f["source_id"], "").startswith(("fdc_", "off_product_")), f["id"]
    rep = Verifier(STORE, RULES).verify(path)
    assert rep.ok
    for fld in rep.fields:
        if fld.kind in ("corroboration", "candidate"):
            assert fld.status == "UNVERIFIED"


def test_a_fact_from_fdc_fails(tmp_path: Path) -> None:
    r = rec("jif_creamy_16oz_051500255162")
    c = r["corroboration"][1]  # an FDC labelNutrients value
    r["facts"].append({"id": "F_bad", "quantity": c["quantity"], "value_raw": c["value_raw"], "basis": "per_serving",
                       "source_id": c["source_id"], "locator": c["locator"], "rule": c["rule"],
                       "interpretation": {"kind": "rounded", "rule": f"fda_rounding_101_9@1:{c['quantity']}"},
                       "value": {"lo": "0", "hi": "1", "lo_closed": True, "hi_closed": False, "unit": "g"},
                       "evidence_class": "document", "assumptions": []})  # fmt: skip
    rep = verify_obj(r, tmp_path)
    assert not rep.ok
    assert any("never facts" in p for f in rep.fields if f.id == "F_bad" for p in f.problems)


def test_an_ingredient_from_off_text_fails(tmp_path: Path) -> None:
    r = rec("nutella_fr_3017620422003")
    cand = r["candidates"][0]
    r["ingredients"].append({"id": "I_bad", "list_id": "off", "position": 1, "role": "food", "source_id": cand["source_id"],
                             "name_locator": cand["locator"], "list_rule": "list_item@1:1", "name_verbatim": "Sucre"})  # fmt: skip
    assert not verify_obj(r, tmp_path).ok


@pytest.fixture
def jif_signed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    props, signed = tmp_path / "proposals.jsonl", tmp_path / "signed.jsonl"
    props.write_text((COMP / "attestations" / "proposals.jsonl").read_text())
    monkeypatch.setitem(attest.PATHS, "proposals", props)
    monkeypatch.setitem(attest.PATHS, "signed", signed)
    return props


def test_signed_photo_gives_attested_label_facts_and_corroboration(
    jif_signed: Path, tmp_path: Path
) -> None:
    attest.sign(
        "jif_nutrition_en_209",
        "test-fixture (not an operator attestation)",
        now="2026-11-12T00:00:00Z",
    )
    p = golden.build(STORE, RULES, "jif_creamy_16oz_051500255162").write(tmp_path)
    rep = Verifier(STORE, RULES).verify(p)
    assert rep.ok, rep.errors
    st = {f.id: f.status for f in rep.fields}
    assert st["P1_total_fat"] == "ATTESTED" and st["P1_dietary_fiber"] == "ATTESTED"
    fat = {c["id"]: c for c in rep.corroboration}
    assert fat["CR_label_total_fat"]["result"] == "consistent"
    assert fat["CR_label_dietary_fiber"]["result"] == "consistent"  # FDC 2.01 vs label "Fiber 2g"
    assert fat["CR_100g_total_fat"]["result"] == "consistent"  # per 100 g x 33 g / 100, rounded


def test_mistranscription_shows_as_a_corroboration_mismatch(
    jif_signed: Path, tmp_path: Path
) -> None:
    rows = [json.loads(x) for x in jif_signed.read_text().splitlines()]
    for r in rows[0]["rows"]:
        if r["nutrient"] == "total_fat":
            r["text"] = "Total Fat 19g 25%"
    jif_signed.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    attest.sign("jif_nutrition_en_209", "test-fixture", now="2026-11-12T00:00:00Z")
    rep = Verifier(STORE, RULES).verify(
        golden.build(STORE, RULES, "jif_creamy_16oz_051500255162").write(tmp_path)
    )
    assert rep.ok  # a mismatch is reported, not "fixed" and not a failure
    assert {c["id"]: c["result"] for c in rep.corroboration}["CR_label_total_fat"] == "mismatch"


# ------------------------------------------------------------------ WP2 identity


def test_citrucel_structured_ingredients_are_orange_only() -> None:
    r = rec("citrucel_orange_300680418301")
    structured = {i["name_verbatim"] for i in r["ingredients"] if i["list_id"] == "spl_inactive"}
    assert (
        "SUCROSE" in structured and "ASPARTAME" not in structured and "MALIC ACID" not in structured
    )
    attributed = [f["id"] for f in r["facts"] if "A11" in f["assumptions"]]
    assert attributed == [
        "F3",
        "F4",
        "F5",
        "F6",
    ]  # the text-section facts carry text_variant_attribution


def test_structured_vs_text_conflict_is_reported() -> None:
    rep = Verifier(STORE, RULES).verify(COMP / "records" / "citrucel_orange_300680418301.json")
    assert rep.ok
    assert rep.conflicts == [
        "text list names 'orange flavors (natural and artificial)', which is not in the structured list"
    ]


def test_proprietary_blend_bounds() -> None:
    r = rec("swanson_lowat_blend_087614040622")
    assert [b["id"] for b in r["bounds"]] == ["B1", "B2"]
    for b in r["bounds"]:
        assert Interval.from_json(b["result"]) == (
            Interval(Interval.point(0).lo, Interval.point(300).lo, False, False),
            "mg",
        )
    assert any("not on the label" in n for n in r["unverified_layer"]["notes"])


def test_dsld_quantity_rule() -> None:
    assert textrules.apply("dsld_quantity@1", "0.5 Gram(s)") == "0.5 g"
    assert textrules.apply("dsld_quantity@1", "115 Calorie(s)") == "115 kcal"
    for bad in ("0 NP", "400 IU", "0 mg"):
        with pytest.raises(textrules.RuleError):
            textrules.apply("dsld_quantity@1", bad)


def test_list_item_v2_keeps_abbreviation_dots() -> None:
    t = "citric acid, FD&C yellow no. 6 lake, sucrose"
    assert textrules.apply("list_item@2:2", t) == "FD&C yellow no. 6 lake"
    assert (
        textrules.apply("list_item@1:2", t) != "FD&C yellow no. 6 lake"
    )  # @1 unchanged (stops at "no.")


def test_truncation_flags_reach_the_operator() -> None:
    info: dict[str, Any] = {"ingredient_parts": [
        {"role": "food", "text": "WATER, SUGAR, MODIFIED CORN STA", "origin": "usda.ingredients"},
        {"role": "food", "text": "WATER, SUGAR, MODIFIED CORN STARCH, SALT, CITRIC ACID.", "origin": "openfoodfacts.ingredients_text"},
    ]}  # fmt: skip
    flag_truncation(info)
    assert len(info["ingredient_parts"][0]["truncation_flags"]) == 2
    assert "truncation_flags" not in info["ingredient_parts"][1]
    assert truncation_flags("A" * 1024) and any("1024" in f for f in truncation_flags("A" * 1024))
