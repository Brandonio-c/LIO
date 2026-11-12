"""Structured ingredient tables: label text and records -> rows, N/A where unstated."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_foods import EAN, FakeWeb

from lio.foods import barcode as bc
from lio.foods import structure as S
from lio.foods.intake import Intake
from lio.foods.lookup import Lookup, LookupSettings, parse_dsld, parse_openfda
from lio.foods.store import FoodLibrary, LibraryError

NA = S.NA
REPO = Path(__file__).resolve().parents[4]
SWANSON = (
    REPO
    / "composition/sources/sha256/c4/c48e3797307e4469445d83453e4dede448d1d370f43e01a3e4f0e3f53913dd4f"
)

CAPLET = {  # openFDA, the Citrucel caplet label (abridged)
    "openfda": {"brand_name": ["CITRUCEL"], "generic_name": ["METHYLCELLULOSE"]},
    "set_id": "00000000-0000-0000-0000-000000000001",
    "active_ingredient": [
        "Active ingredient (in each caplet) Methylcellulose (a non-allergenic fiber) 500mg"
    ],
    "inactive_ingredient": [
        "Inactive ingredients crospovidone, dibasic calcium phosphate, FD&C yellow no. 6 "
        "aluminum lake, magnesium stearate, maltodextrin, povidone, sodium lauryl sulfate"
    ],
    "other_information": [
        "Other information • each caplet contains : calcium 10mg • store below 77 o F "
        "(25 o C) • protect contents from humidity • keep tightly closed"
    ],
}
POWDER = {  # openFDA, the Citrucel powder label: two variants in one SPL
    "openfda": {"brand_name": ["CITRUCEL"], "generic_name": ["METHYLCELLULOSE"]},
    "set_id": "9d5f2244-0000-0000-0000-000000000000",
    "active_ingredient": [
        "Active ingredient (in each heaping tablespoon) CITRUCEL Orange Methylcellulose "
        "(a non-allergenic fiber) 2 g",
        "Active ingredient (in each rounded tablespoon) CITRUCEL Sugar Free Methylcellulose "
        "(a non-allergenic fiber) 2 g",
    ],
    "inactive_ingredient": [
        "Inactive ingredients (Citrucel Orange) citric acid, dibasic calcium phosphate, "
        "orange flavors (natural and artificial), sucrose, tricalcium phosphate",
        "Inactive ingredients (Citrucel Sugar Free) aspartame, dibasic calcium phosphate, "
        "malic acid",
    ],
    "other_information": [
        "Other information (Citrucel Orange) each heaping tablespoon contains: calcium 80 mg, "
        "potassium 105 mg, sodium 10 mg each heaping tablespoon contributes 60 calories from "
        "sucrose and maltodextrin store below 25°C (77°F)",
        "Other information (Citrucel Sugar Free) each rounded tablespoon contains: calcium "
        "70 mg, potassium 105 mg, sodium 10 mg",
    ],
}


def by(rows: list[dict[str, str]], name: str) -> dict[str, str]:
    return next(r for r in rows if r["name"] == name)


def test_caplet_label_is_laid_out() -> None:
    out = S.structure_record("openfda", parse_openfda(CAPLET), CAPLET)
    (st,) = out["options"]
    act = by(st["ingredients"], "Methylcellulose")
    assert (act["role"], act["amount"], act["basis"]) == ("active", "500 mg", "per caplet")
    assert act["note"] == "a non-allergenic fiber"
    inact = [r for r in st["ingredients"] if r["role"] == "inactive"]
    assert [r["name"] for r in inact][2] == "FD&C yellow no. 6 aluminum lake"
    assert len(inact) == 7 and all(r["amount"] == NA and r["basis"] == NA for r in inact)
    assert st["contains"] == [
        {"name": "calcium", "amount": "10 mg", "basis": "per caplet", "variant": NA, "note": NA}
    ]
    assert st["serving"] == "1 caplet"
    for r in st["ingredients"]:
        assert set(r) == set(S.FIELDS) and all(v for v in r.values())


def test_variants_are_separate_and_the_query_picks_one() -> None:
    out = S.structure_record("openfda", parse_openfda(POWDER), POWDER, "citrucel sugar free")
    names = [o["variant"] for o in out["options"]]
    assert names == ["Citrucel Orange", "Citrucel Sugar Free"]
    assert out["default"] == 1
    orange, sf = out["options"]
    a = [r for r in orange["ingredients"] if r["role"] == "active"]
    assert len(a) == 1 and a[0]["name"] == "Methylcellulose"
    assert a[0]["basis"] == "per heaping tablespoon"
    assert "sucrose" in [r["name"] for r in orange["ingredients"]]
    assert "aspartame" not in [r["name"] for r in orange["ingredients"]]
    assert by(orange["ingredients"], "orange flavors")["sub"] == "natural and artificial"
    cal = by(orange["contains"], "calories")
    assert cal["amount"] == "60 kcal" and cal["note"] == "from sucrose and maltodextrin"
    assert by(sf["contains"], "calcium")["amount"] == "70 mg"


def test_food_list_amounts_sub_ingredients_and_less_than_groups() -> None:
    sec = S.section(
        "SUGAR, HAZELNUTS 13%, SKIM MILK (7.5%), LECITHIN [SOY], ENRICHED FLOUR (WHEAT "
        "FLOUR, NIACIN), VANILLIN. CONTAINS 2% OR LESS OF: SALT, MOLASSES"
    )
    rows = sec["ingredients"]
    assert [r["name"] for r in rows] == [
        "SUGAR", "HAZELNUTS", "SKIM MILK", "LECITHIN", "ENRICHED FLOUR", "VANILLIN", "SALT",
        "MOLASSES",
    ]  # fmt: skip
    assert by(rows, "SUGAR")["amount"] == NA
    assert (by(rows, "HAZELNUTS")["amount"], by(rows, "HAZELNUTS")["basis"]) == (
        "13%",
        "of product",
    )
    assert by(rows, "SKIM MILK")["amount"] == "7.5%"
    assert by(rows, "LECITHIN")["sub"] == "SOY"
    assert by(rows, "ENRICHED FLOUR")["sub"] == "WHEAT FLOUR, NIACIN"
    assert by(rows, "SALT")["amount"] == "≤ 2%" and by(rows, "MOLASSES")["amount"] == "≤ 2%"


def test_web_sections_with_unii() -> None:
    st = S.structure_sections(
        [{"heading": "Ingredient", "text": "Name Strength CITRIC ACID MONOHYDRATE (UNII: 2968PHW8QP)"},
         {"heading": "Inactive ingredients (Citrucel Orange)", "text": "citric acid, sucrose"}]
    )  # fmt: skip
    a, b, c = st["ingredients"]
    assert a["name"] == "CITRIC ACID MONOHYDRATE" and a["note"] == "UNII 2968PHW8QP"
    assert (b["role"], b["variant"], c["name"]) == ("inactive", "Citrucel Orange", "sucrose")


@pytest.mark.skipif(not SWANSON.exists(), reason="composition snapshot not present")
def test_dsld_blend_members_dv_and_forms() -> None:
    raw: dict[str, Any] = json.loads(SWANSON.read_bytes())
    (st,) = S.structure_record("dsld", parse_dsld(raw), raw)["options"]
    blend = by(st["ingredients"], "LOWAT Proprietary Blend")
    assert blend["amount"] == "300 mg" and blend["basis"] == "per 1 Veggie Capsule"
    assert blend["dv"] == "Daily Value not established"
    member = by(st["ingredients"], "Dolichos biflorus (seed) extract")
    assert member["amount"] == NA and "in LOWAT Proprietary Blend" in member["note"]
    assert any(r["role"] == "other" for r in st["ingredients"])
    assert st["serving"].startswith("1 Veggie Capsule")


def test_clean_and_text() -> None:
    st = S.section("Active ingredient (in each caplet) Methylcellulose 500mg")
    table = S.clean({**S._empty("openfda", "X"), **st})
    assert S.to_text(table) == "Active ingredients (per caplet): Methylcellulose 500 mg"
    with pytest.raises(ValueError):
        S.clean({"ingredients": [{"name": "x", "role": "bogus"}]})
    with pytest.raises(ValueError):
        S.clean({"ingredients": [{"name": "x"}] * (S.MAX_ROWS + 1)})
    edited = S.clean({"ingredients": [{"name": " sugar ", "role": "ingredient", "amount": ""}]})
    assert edited["ingredients"][0]["name"] == "sugar" and edited["ingredients"][0]["amount"] == NA


@pytest.fixture
def lib(tmp_path: Path) -> Iterator[FoodLibrary]:
    lb = FoodLibrary(tmp_path / "foods", Lookup(LookupSettings(), fetch=FakeWeb()))
    lb._download_image = lambda gtin14, url: ""  # type: ignore[method-assign]
    yield lb
    lb.close()


def test_saved_table_and_hand_edit_drops_it(lib: FoodLibrary) -> None:
    it = Intake(lib)
    s = lib.create_sample(bc.normalise(EAN))
    st = S.section("Inactive ingredients citric acid, sucrose")
    table = {**S._empty("web", ""), **st}
    p = it.confirm_ingredients(
        s["gtin14"], {"ingredients_text": "", "ingredients_structured": table}
    )
    info = p["info"]
    assert info["ingredients_text"] == "Inactive ingredients: citric acid, sucrose"
    assert [r["name"] for r in info["ingredients_structured"]["ingredients"]] == [
        "citric acid",
        "sucrose",
    ]
    p = lib.set_product_info(s["gtin14"], {"ingredients_text": "citric acid"})
    assert "ingredients_structured" not in p["info"]
    with pytest.raises(LibraryError):
        it.confirm_ingredients(
            s["gtin14"], {"ingredients_structured": {"ingredients": [{"name": "x", "role": "?"}]}}
        )


def test_preview_fetches_the_full_record(lib: FoodLibrary) -> None:
    out = Intake(lib).preview_record("dsld", "64567", "fish oil")
    (st,) = out["options"]
    assert st["source"] == "dsld" and st["ingredients"]
    assert all(set(r) == set(S.FIELDS) for r in st["ingredients"])
