"""M5 (plan WP4): Drug Facts and Supplement Facts parsers and photo attestation."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("lark")
pytest.importorskip("lxml")

from lio.foods import barcode as bc
from lio.foods import panels
from lio.foods.ocr import Line
from lio_verify import textrules

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
RULES = REPO / "composition" / "rules"
SIZE = (1000, 2000)


def L(t: str, y: float) -> Line:
    return Line(t, 1.0, 0.05, y, 0.9, 0.02)


DRUG = [L("Drug Facts", 0.95), L("Active ingredient (in each capsule)", 0.92),
        L("Solubilized ibuprofen equal to 200 mg ibuprofen (NSAID)*", 0.89), L("Purpose", 0.86),
        L("Pain reliever/fever reducer", 0.84), L("Uses", 0.81), L("temporarily relieves minor aches", 0.79),
        L("Warnings", 0.76), L("Allergy alert: ibuprofen may cause a severe allergic reaction", 0.74),
        L("Directions", 0.70), L("adults: take 1 capsule every 4 to 6 hours", 0.68), L("Other information", 0.64),
        L("each capsule contains: potassium 20 mg", 0.62), L("store at 20-25C", 0.60),
        L("Inactive ingredients FD&C green no. 3, gelatin, medium-chain triglycerides,", 0.56),
        L("sorbitol, white ink", 0.54), L("Questions? Call 1-877-753-3935", 0.50)]  # fmt: skip
SUPP = [L("Supplement Facts", 0.95), L("Serving Size 1 Veggie Capsule", 0.92), L("Servings Per Container 60", 0.90),
        L("Amount Per Serving % Daily Value", 0.87), L("Vitamin C (as ascorbic acid) 60 mg 67%", 0.84),
        L("LOWAT Proprietary Blend 300 mg †", 0.81), L("Dolichos biflorus (seed) extract", 0.79),
        L("Piper betle (leaf) extract", 0.77), L("† Daily Value not established.", 0.74),
        L("Other ingredients: hypromellose (capsule), rice flour.", 0.70)]  # fmt: skip


def test_drug_facts_sections_and_fields() -> None:
    p = panels.drug_facts(DRUG, SIZE)
    assert p["sections"] == [
        "active",
        "purpose",
        "uses",
        "warnings",
        "directions",
        "other_information",
        "inactive",
        "questions",
    ]
    assert p["complete"]
    assert [a["value_raw"] for a in p["actives"]] == ["200 mg"]
    assert p["contains"][0]["items"] == {"potassium": "20 mg"}
    assert p["inactive"]["items"] == [
        "FD&C green no. 3",
        "gelatin",
        "medium-chain triglycerides",
        "sorbitol",
        "white ink",
    ]
    assert "alphabetical" in p["inactive"]["order"]


def test_supplement_facts_rows_blends_and_other() -> None:
    p = panels.supplement_facts(SUPP, SIZE)
    assert p["serving"]["value_raw"] == "1 veggie capsule"
    assert p["servings_per_container"]["value"] == "60"
    assert [(r["name"], r["value_raw"], r["dv"]) for r in p["rows"]] == [
        ("Vitamin C (as ascorbic acid)", "60 mg", "67%"),
        ("LOWAT Proprietary Blend", "300 mg", ""),
    ]
    assert [m["text"] for m in p["blends"][0]["members"]] == [
        "Dolichos biflorus (seed) extract",
        "Piper betle (leaf) extract",
    ]
    assert p["other_ingredients"]["items"] == ["hypromellose (capsule)", "rice flour"]


def test_rules() -> None:
    assert textrules.apply("sfp_row@1", "Magnesium (from Magnesium Oxide) 420 mg 100%") == "420 mg"
    assert textrules.apply("drug_active@1", "Ibuprofen 200 mg (NSAID)*") == "200 mg"
    for rule, bad in (
        ("sfp_row@1", "Vitamin D 400 IU 100%"),
        ("drug_active@1", "Purpose"),
        ("sfp_row@1", "Calories 10"),
    ):
        with pytest.raises(textrules.RuleError):
            textrules.apply(rule, bad)


def test_flatten_gives_indexed_fields() -> None:
    f = panels.flatten("drug_facts", panels.drug_facts(DRUG, SIZE))
    assert [x["field"] for x in f] == ["active", "contains", "inactive_list"]
    assert [x["index"] for x in f] == [0, 1, 2]
    s = panels.flatten("supplement_facts", panels.supplement_facts(SUPP, SIZE))
    assert [x["field"] for x in s] == ["row", "row", "blend_member", "blend_member", "other_list"]


@pytest.mark.parametrize("kind,lines", [("drug_facts", DRUG), ("supplement_facts", SUPP)])
def test_panel_attestation_end_to_end(
    kind: str, lines: list[Line], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    import lio.foods.intake as intake_mod
    from lio.foods.intake import Intake
    from lio.foods.lookup import Lookup, LookupSettings
    from lio.foods.store import FoodLibrary, LibraryError
    from lio_comp.samples import SampleComposition

    def fake_read(data: bytes, k: str = "") -> dict[str, Any]:
        return {"lines": [ln.text for ln in lines], "text": "\n".join(ln.text for ln in lines), "ingredients": "",
                "contains": "", "heading": "", "nutrition": {"per_100g": {}, "serving": "", "serving_g": None},
                "image_size": list(SIZE), "panel_rows": [], "ingredient_box": None, "ndc_candidates": [],
                "panel": panels.parse(k, lines, SIZE), "ocr_engine": "test"}  # fmt: skip

    class NoWeb:
        def __call__(self, *a: Any, **k: Any) -> Any:
            raise OSError("offline")

    monkeypatch.setattr(intake_mod, "read_label", fake_read)
    lib = FoodLibrary(tmp_path / "foods", Lookup(LookupSettings(), fetch=NoWeb()))
    lib._download_image = lambda gtin14, url: ""  # type: ignore[method-assign]
    it = Intake(lib, SampleComposition(tmp_path / "foods" / "composition", RULES))
    s = lib.create_sample(bc.normalise("96385074"))
    buf = io.BytesIO()
    Image.new("RGB", SIZE, "white").save(buf, "JPEG")
    r = it.read_label(buf.getvalue(), kind)
    assert r["can_attest"]
    fields = [{"index": f["index"], "text": f["text"]} for f in r["panel_fields"]]
    with pytest.raises(LibraryError):  # a corrected text that no longer parses is refused
        bad = [{**fields[0], "text": "no amount here"}]
        it.apply_label(s["sample_code"], {"label_draft": it.read_label(buf.getvalue(), kind)["label_draft"],
                                          "attest": {"signer": "test-fixture", "fields": bad}})  # fmt: skip
    r = it.read_label(buf.getvalue(), kind)
    out = it.apply_label(
        s["sample_code"],
        {"label_draft": r["label_draft"], "attest": {"signer": "test-fixture", "fields": fields}},
    )
    rep = out["composition"]["report"]
    assert rep["result"] == "PASS", rep
    statuses = {f["status"] for f in rep["fields"] if f["kind"] in ("fact", "ingredient")}
    assert statuses == {"ATTESTED"}
    rec = it.composition_report(s["sample_code"])["record"]
    if kind == "drug_facts":
        pot = next(f for f in rec["facts"] if f["quantity"] == "potassium")
        assert pot["interpretation"]["rule"] == "fda_otc_rounding_201@1:potassium"
        assert [i["role"] for i in rec["ingredients"]] == ["inactive"] * 5
    else:
        assert {i["role"] for i in rec["ingredients"]} == {"dietary", "other"}
    lib.close()
