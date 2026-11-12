# ruff: noqa: E501  (fixture JSON and one-line calls are kept whole)
"""Ingredient coverage: barcode forms, NDC decoding, field merging, fallbacks, ingredient photos."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from lio.foods import barcode as bc
from lio.foods.intake import retailer_links
from lio.foods.lookup import Lookup, LookupSettings, part, possibly_truncated, redact

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
CITRUCEL_SETID = "9d5f2244-a610-4d45-b6e8-e79bb17a558f"


def http404(url: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, 404, "not found", {}, None)  # type: ignore[arg-type]


class Web:
    """A fake network: ``routes`` maps a URL fragment to an answer (first match wins)."""

    def __init__(self, routes: list[tuple[str, Any]]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self, url: str, headers: dict[str, str], timeout: float) -> Any:
        self.calls.append(url)
        for frag, ans in self.routes:
            if frag in url:
                if isinstance(ans, Exception):
                    raise ans
                return ans
        if "nal.usda.gov" in url:
            return {"totalHits": 0, "foods": []}
        if "ods.od.nih.gov" in url:
            return {"hits": []}
        raise http404(url)


def lookup(routes: list[tuple[str, Any]]) -> tuple[Lookup, Web]:
    w = Web(routes)
    return Lookup(LookupSettings(usda_api_key="k"), fetch=w), w


# ------------------------------------------------------------------ barcodes


def test_every_form_with_one_check_digit() -> None:
    g = bc.normalise("049000006346")
    assert g.forms == {"UPC-A": "049000006346", "EAN-13": "0049000006346",
                       "GTIN-14": "00049000006346", "UPC-E": "04963406"}  # fmt: skip
    assert bc.normalise("04963406", "UPCE").forms == g.forms
    assert g.matches("04963406") and g.matches("0049000006346") and not g.matches("049000006347")
    assert bc.normalise("5453003821090").form_of("5 453003 821090") == "EAN-13"
    with pytest.raises(bc.BarcodeError):
        bc.normalise("049000006347")  # wrong check digit


def test_ndc_candidates_from_a_drug_upc() -> None:
    c = bc.ndc_candidates(bc.normalise("300680418301"))
    assert [(x.pattern, x.ndc, x.ndc11) for x in c] == [
        ("4-4-2", "0068-0418-30", "00068-0418-30"),
        ("5-3-2", "00680-418-30", "00680-0418-30"),
        ("5-4-1", "00680-4183-0", "00680-4183-00"),
    ]
    assert bc.ndc_candidates(bc.normalise("051500255162")) == []


# ------------------------------------------------------------ source matching


def test_fdc_found_under_the_form_it_stored() -> None:
    food = {
        "fdcId": 1,
        "gtinUpc": "021000037377",
        "description": "MAC",
        "ingredients": "PASTA, CHEESE.",
    }
    lk, w = lookup([("query=021000037377", {"totalHits": 1, "foods": [food]})])
    info, _ = lk.usda(bc.normalise("021000037377"))
    assert info is not None
    assert info["matched_forms"]["usda"] == {
        "form": "UPC-A",
        "code": "021000037377",
        "stored": "021000037377",
    }
    assert any("query=00021000037377" in c for c in w.calls)  # GTIN-14 was tried first


def test_dsld_finds_an_ean13_supplement() -> None:
    label = {"id": 332395, "fullName": "Melatonin 2 mg", "brandName": "SuperSmart",
             "upcSku": "5 453003 821090", "ingredientRows": [{"name": "Melatonin", "quantity": [{"quantity": 2, "unit": "mg"}]}],
             "otheringredients": {"ingredients": [{"name": "Cellulose"}]}}  # fmt: skip
    lk, _ = lookup([("search-filter?q=%225%20453003%20821090%22", {"hits": [{"_id": 332395}]}),
                    ("/label/332395", label)])  # fmt: skip
    info, _ = lk.dsld(bc.normalise("5453003821090"))
    assert info is not None and info["matched_forms"]["dsld"]["form"] == "EAN-13 spaced"
    assert [p["role"] for p in info["ingredient_parts"]] == ["dietary", "other"]
    assert info["ingredient_parts"][1]["origin"] == "dsld.otheringredients.ingredients"


def test_off_keeps_every_language_and_uses_the_longest() -> None:
    product = {"product_name": "Nutella", "lang": "en", "ingredients_text": "sugar, palm oil",
               "ingredients_text_en": "sugar, palm oil",
               "ingredients_text_fr": "Sucre, huile de palme, NOISETTES 13%, cacao maigre 7,4%, LAIT écrémé en poudre 6,6%",
               "ingredients_text_de": "Zucker, Palmöl, HASELNÜSSE 13 %"}  # fmt: skip
    lk, _ = lookup(
        [("3017620422003.json", {"status": 1, "code": "3017620422003", "product": product})]
    )
    info, _ = lk.openfoodfacts(bc.normalise("3017620422003"))
    assert info is not None
    assert info["ingredients_text"].startswith("Sucre, huile de palme")
    assert info["ingredients_text_origin"] == "openfoodfacts.ingredients_text_fr"
    origins = [p["origin"] for p in info["ingredient_parts"]]
    assert origins == [
        "openfoodfacts.ingredients_text",
        "openfoodfacts.ingredients_text_de",
        "openfoodfacts.ingredients_text_fr",
    ]


SPL_LABEL = {
    "set_id": CITRUCEL_SETID,
    "openfda": {
        "brand_name": ["CITRUCEL"],
        "generic_name": ["METHYLCELLULOSE"],
        "manufacturer_name": ["Haleon"],
    },
    "active_ingredient": ["Active ingredient (in each heaping tablespoon) Methylcellulose 2 g"],
    "inactive_ingredient": ["Inactive ingredients citric acid, maltodextrin, sucrose"],
    "spl_unclassified_section": [
        "Other information each heaping tablespoon contains: calcium 80 mg, potassium 105 mg"
    ],
}


def test_drug_label_parts_keep_their_fields() -> None:
    lk, _ = lookup(
        [
            (
                "openfda.upc",
                {
                    "results": [
                        {**SPL_LABEL, "openfda": {**SPL_LABEL["openfda"], "upc": ["0300680418301"]}}
                    ]
                },
            )
        ]
    )
    info, _ = lk.openfda(bc.normalise("300680418301"))
    assert info is not None
    assert [(p["role"], p["origin"]) for p in info["ingredient_parts"]] == [
        ("active", "openfda.active_ingredient[0]"),
        ("inactive", "openfda.inactive_ingredient[0]"),
        ("other_information", "openfda.spl_unclassified_section[0]"),
    ]
    assert info["matched_forms"]["openfda"]["form"] == "EAN-13"


def test_ndc_path_finds_the_label() -> None:
    lk, w = lookup([("openfda.product_ndc%3A%2241520-314", {"results": [SPL_LABEL]})])
    info, _ = lk.ndc(bc.normalise("341520314643"))
    assert info is not None and info["ndc_match"]["pattern"] == "5-3-2"
    assert "confirm" in info["ndc_match"]["note"]
    assert any("package_ndc" in c for c in w.calls)  # package NDC first


def test_citrucel_retired_ndc_falls_back_to_dailymed_by_name() -> None:
    """Citrucel Orange's UPC carries the retired Merrell Dow NDC 0068-0418-30: no NDC route
    reaches set 9d5f2244, so DailyMed by name offers it for the user to confirm."""
    dm = {
        "data": [
            {
                "setid": CITRUCEL_SETID,
                "title": "CITRUCEL (METHYLCELLULOSE) POWDER",
                "published_date": "Mar 20, 2026",
            }
        ]
    }
    lk, _ = lookup([("spls.json?drug_name=citrucel", dm), ("spls.json?ndc=", {"data": []})])
    info, raw = lk.ndc(bc.normalise("300680418301"))
    assert info is None and "dailymed ndc=0068-0418-30" in raw["ndc_tried"]
    cands = lk.search_by_name("Citrucel orange")
    assert CITRUCEL_SETID in [c["id"] for c in cands]


def test_merge_keeps_every_part() -> None:
    from lio.foods.lookup import merge

    a = {
        "ingredients_text": "A",
        "ingredient_parts": [part("food", "A", "usda", "usda.ingredients")],
        "matched_forms": {"usda": {}},
    }
    b = {
        "ingredients_text": "B",
        "ingredient_parts": [part("food", "B", "openfoodfacts", "openfoodfacts.ingredients_text")],
        "matched_forms": {"openfoodfacts": {}},
    }
    m = merge(a, b)
    assert m["ingredients_text"] == "A"
    assert [p["source"] for p in m["ingredient_parts"]] == ["usda", "openfoodfacts"]
    assert set(m["matched_forms"]) == {"usda", "openfoodfacts"}


def test_truncation_flag() -> None:
    assert not possibly_truncated("TOMATO PUREE, SALT, CELERY EXTRACT. CONTAINS: WHEAT")
    assert not possibly_truncated("WATER, SUGAR (CANE).")
    assert possibly_truncated("WATER, SUGAR, MODIFIED CORN STA")


def test_evidence_is_stored_with_the_key_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    import lio.foods.lookup as L

    stored: list[tuple[str, bytes]] = []
    monkeypatch.setattr(
        L,
        "_http_bytes",
        lambda url, h, t: (json.dumps({"totalHits": 0, "foods": []}).encode(), "application/json"),
    )
    lk = Lookup(
        LookupSettings(usda_api_key="SECRET"),
        evidence=lambda u, d, m: stored.append((u, d)) or "ab" * 32,
    )
    res = lk.lookup(bc.normalise("051500255162"))
    assert stored and all("SECRET" not in u for u, _ in stored)
    assert all(e["sha256"] == "ab" * 32 for e in res.info["evidence"])
    assert redact("https://x/y?api_key=SECRET&q=1") == "https://x/y?api_key=REDACTED&q=1"


def test_retailers_are_links_only() -> None:
    links = retailer_links("051500255162", "Jif creamy")
    assert {lk["name"] for lk in links} >= {"Walmart", "Target", "Amazon"}
    assert all(lk["url"].startswith("https://") for lk in links)


def test_smartlabel_needs_a_key() -> None:
    lk, w = lookup([])
    info, why = lk.smartlabel(bc.normalise("051500255162"))
    assert info is None and "key" in why and not w.calls
    lk2, _ = lookup(
        [
            (
                "labelinsight.com",
                {"content": [{"productName": "Jif", "ingredients": "Peanuts, sugar."}]},
            )
        ]
    )
    lk2.s.smartlabel_key = "K"
    info2, _ = lk2.smartlabel(bc.normalise("051500255162"))
    assert info2 is not None and info2["ingredient_parts"][0]["origin"] == "smartlabel.ingredients"


# ---------------------------------------------------------- ingredient panel


def test_ingredient_region_from_ocr_lines() -> None:
    from lio.foods.ocr import Line, ingredient_region

    lines = [Line("INGREDIENTS: ROASTED PEANUTS, SUGAR,", 1, 0.1, 0.6, 0.6, 0.03),
             Line("MOLASSES, SALT.", 1, 0.1, 0.56, 0.3, 0.03),
             Line("DISTRIBUTED BY ACME", 1, 0.1, 0.50, 0.4, 0.03)]  # fmt: skip
    box = ingredient_region(lines, (1000, 1000))
    assert box == {"x": 100, "y": 370, "w": 600, "h": 70}


def test_attested_ingredient_panel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("z3")
    pytest.importorskip("PIL")
    from PIL import Image

    import lio.foods.intake as intake_mod
    from lio.foods.intake import Intake
    from lio.foods.store import FoodLibrary, LibraryError
    from lio_comp.samples import SampleComposition

    monkeypatch.setattr(intake_mod, "read_label", lambda data: {
        "lines": ["INGREDIENTS: OATS, SUGAR, SALT."], "text": "INGREDIENTS: OATS, SUGAR, SALT.", "ingredients": "OATS, SUGAR, SALT", "contains": "",
        "heading": "INGREDIENTS", "nutrition": {"per_100g": {}, "serving": "", "serving_g": None},
        "image_size": [800, 600], "panel_rows": [], "ingredient_box": {"x": 40, "y": 50, "w": 500, "h": 60}})  # fmt: skip
    lib = FoodLibrary(tmp_path / "foods", Lookup(LookupSettings(), fetch=Web([])))
    lib._download_image = lambda gtin14, url: ""  # type: ignore[method-assign]
    it = Intake(
        lib, SampleComposition(tmp_path / "foods" / "composition", REPO / "composition" / "rules")
    )
    s = lib.create_sample(bc.normalise("96385074"))
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buf, "JPEG")
    r = it.read_label(buf.getvalue(), "ingredients")
    assert r["can_attest"]
    with pytest.raises(LibraryError):
        it.apply_label(
            s["sample_code"],
            {
                "label_draft": r["label_draft"],
                "ingredients_text": "Oats, sugar, salt",
                "attest": {"signer": " "},
            },
        )
    r = it.read_label(buf.getvalue(), "ingredients")
    out = it.apply_label(
        s["sample_code"],
        {
            "label_draft": r["label_draft"],
            "ingredients_text": "Oats, sugar, salt",
            "attest": {"signer": "B. C."},
        },
    )
    rep = out["composition"]["report"]
    assert rep["result"] == "PASS", rep
    ings = [f for f in rep["fields"] if f["kind"] == "ingredient"]
    assert [f["status"] for f in ings] == ["ATTESTED"] * 3
    rec = it.composition_report(s["sample_code"])["record"]
    assert [i["name_verbatim"] for i in rec["ingredients"]] == ["Oats", "sugar", "salt"]
    assert rec["ingredients"][0]["name_locator"]["type"] == "image_bbox"
    assert rec["attestations"][0]["subjects"] == ["P1_I1", "P1_I2", "P1_I3"]
    lib.close()


def test_multi_variant_label_keeps_variants_apart() -> None:
    from lio.foods.lookup import parse_openfda

    r = {**SPL_LABEL,
         "inactive_ingredient": ["Inactive ingredients (Citrucel Orange) citric acid, sucrose",
                                 "Inactive ingredients (Citrucel Sugar Free) aspartame, malic acid"],
         "spl_unclassified_section": ["Other information (Citrucel Orange) each heaping tablespoon contains: calcium 80 mg",
                                      "Other information (Citrucel Sugar Free) each rounded tablespoon contains: calcium 80 mg"]}  # fmt: skip
    info = parse_openfda(r)
    assert info["variants"] == ["Citrucel Orange", "Citrucel Sugar Free"]
    assert (
        "aspartame" not in info["ingredients_text"] and "Sugar Free" not in info["ingredients_text"]
    )
    assert len(info["ingredient_parts"]) == 5  # nothing dropped
