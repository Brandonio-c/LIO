"""The golden records of spec §8, built from the snapshots in ``composition/sources``.

    python -m lio_comp.golden --store composition/sources --rules composition/rules \\
        --out composition/records

Each builder states its assumptions explicitly; the verifier lists them all.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lio_comp import crosswalk
from lio_comp import extract as X
from lio_comp.derive import add_derivations
from lio_comp.record import RecordBuilder
from lio_verify.interpret import load_tables

EXACT = {"kind": "exact"}


def _rounded(rule: str) -> dict[str, str]:
    return {"kind": "rounded", "rule": rule}


def _as_stated(assumption: str) -> dict[str, str]:
    return {"kind": "as_stated", "assumption": assumption}


# ------------------------------------------------------------------ Citrucel
CITRUCEL_ORANGE = "0135-0089"
CITRUCEL_INACTIVE = [  # SPL v17, product 0135-0089, IACT order (alphabetical by SPL)
    "citric_acid_monohydrate", "dibasic_calcium_phosphate", "fdc_yellow6_lake", "maltodextrin",
    "potassium_citrate", "riboflavin", "soy_lecithin", "sucrose", "titanium_dioxide",
    "tricalcium_phosphate",
]  # fmt: skip


def citrucel(b: RecordBuilder) -> None:
    b.source("S1", "dailymed_spl_citrucel_9d5f2244", {"ndc_product": CITRUCEL_ORANGE})
    b.source("S2", "gsrs_unii_L11K75P92J")
    b.source("S3", "gsrs_unii_K4C08XP666")
    b.source("S4", "gsrs_unii_EE90ONI6FF")

    b.assume("A1", "sample_identity",
             "The scanned tub (UPC 3 00680 41830 1, 'Citrucel Orange', 30 oz) is SPL product "
             "NDC 0135-0089 (850 g bottle, 0135-0089-71). The SPL does not carry the UPC; the "
             "link is the product name and size on the tub.")  # fmt: skip
    b.assume(
        "A2",
        "label_truth",
        "The SPL (set 9d5f2244, version 17) states the formulation of the physical sample.",
    )
    b.assume("A3", "rounding",
             "The OTC statement 'contributes 60 calories' is rounded like a Nutrition Facts "
             "calorie value (21 CFR 101.9(c)(1)); no rule for OTC calorie statements exists.",
             "fda_rounding_101_9@1:calories")  # fmt: skip
    b.assume("A4", "modelling",
             "Calories 'from sucrose and maltodextrin' use the general factor of 4 kcal/g for "
             "carbohydrate (21 CFR 101.9(c)(1)(i)(B)).", "atwater@1")  # fmt: skip
    b.assume("A5", "modelling",
             "All calcium comes from dibasic and tricalcium phosphate, in any proportion; no "
             "other listed ingredient contains calcium.")  # fmt: skip
    b.assume("A6", "modelling",
             "Tricalcium phosphate has its UNII formula Ca3(PO4)2. (Food/USP 'tribasic calcium "
             "phosphate' is a variable mixture close to hydroxyapatite, which has more calcium "
             "per gram: the true phosphate mass could be lower than this bound.)")  # fmt: skip
    b.assume(
        "A7", "modelling", "All potassium comes from potassium citrate (as the UNII monohydrate)."
    )
    b.assume(
        "A8",
        "interpretation",
        "A 'heaping tablespoon' dose is the 19 g in the SPL's strength denominator.",
    )

    row = crosswalk.link_for("00300680418301", CROSSWALK_PATH[0])
    if row is not None:
        apply_link(b, row, "S1", row["ndc"], CITRUCEL_ORANGE)
        b.head["variant_note"] = ""  # set below; the link selects the product
    v = "CITRUCEL_ORANGE"
    b.head["variant_note"] = (
        "SPL set 9d5f2244 covers CITRUCEL Orange (NDC 0135-0089) and Sugar Free (0135-0090). "
        "Product facts use the manufacturedProduct with code 0135-0089; text facts use the "
        "sections titled '(Citrucel Orange)'."
    )
    b.ingredient("I_active_1", "spl_active", 1, "active", "S1",
                 X.spl_ingredient(CITRUCEL_ORANGE, "ACTIB", 1, "name"),
                 unii_locator=X.spl_ingredient(CITRUCEL_ORANGE, "ACTIB", 1, "unii"))  # fmt: skip
    b.fact("F1", "methylcellulose", "per_serving", "S1",
           X.spl_active_quantity(CITRUCEL_ORANGE, "numerator"), "quantity@1", EXACT,
           substance={"ingredient": "I_active_1"}, assumptions=("A2",))  # fmt: skip
    b.fact("F2", "serving_mass", "per_serving", "S1",
           X.spl_active_quantity(CITRUCEL_ORANGE, "denominator"), "quantity@1", EXACT,
           assumptions=("A2", "A8"))  # fmt: skip
    other = "Other information (Citrucel Orange)"
    contains = X.spl_section_item(other, "each heaping tablespoon contains")
    for fid, el in (("F3", "calcium"), ("F4", "potassium"), ("F5", "sodium")):
        b.fact(fid, el, "per_serving", "S1", contains, f"otc_contains@1:{el}",
               _rounded(f"fda_otc_rounding_201@1:{el}"), assumptions=("A2",))  # fmt: skip
    b.fact("F6", "energy_from_sucrose_and_maltodextrin", "per_serving", "S1",
           X.spl_section_item(other, "each heaping tablespoon contributes"),
           "otc_calories_from@1", _rounded("fda_rounding_101_9@1:calories"),
           assumptions=("A2", "A3"))  # fmt: skip

    # Identity: every inactive ingredient of product 0135-0089 with the UNII the SPL gives it.
    for n, key in enumerate(CITRUCEL_INACTIVE, start=1):
        b.ingredient(f"I_{key}", "spl_inactive", n, "inactive", "S1",
                     X.spl_ingredient(CITRUCEL_ORANGE, "IACT", n, "name"),
                     unii_locator=X.spl_ingredient(CITRUCEL_ORANGE, "IACT", n, "unii"))  # fmt: skip
    for sid, src, unii in (("SUB_dcp", "S2", "L11K75P92J"), ("SUB_tcp", "S3", "K4C08XP666"),
                           ("SUB_kcit", "S4", "EE90ONI6FF")):  # fmt: skip
        b.substance(sid, unii, src, X.gsrs_first("approvalID"),
                    name_locator=X.gsrs_first("_name"),
                    formula_locator=X.gsrs_first("structure/formula"))  # fmt: skip
    for ing in b.ingredients:
        if ing.get("unii") == "L11K75P92J":
            ing["substance"] = "SUB_dcp"
        elif ing.get("unii") == "K4C08XP666":
            ing["substance"] = "SUB_tcp"
        elif ing.get("unii") == "EE90ONI6FF":
            ing["substance"] = "SUB_kcit"
    b.note(
        f"{v}: the SPL text list of inactive ingredients also names 'orange flavors (natural "
        "and artificial)', which has no structured entry or UNII in the SPL."
    )
    b.note(
        f"{v}: the SPL has no Nutrition Facts, so there is no declared total carbohydrate; "
        "consistency is checked by mass balance against the 19 g dose instead."
    )


# ---------------------------------------------------------------------- Jif
FDC_TO_101_9 = {
    "calories": "calories", "fat": "total_fat", "saturatedFat": "saturated_fat",
    "transFat": "trans_fat", "cholesterol": "cholesterol", "sodium": "sodium",
    "carbohydrates": "total_carbohydrate", "fiber": "dietary_fiber", "sugars": "total_sugars",
    "addedSugar": "added_sugars", "protein": "protein",
}  # fmt: skip


def jif(b: RecordBuilder) -> None:
    from lio_verify.interpret import InterpretError

    b.source("S1", "fdc_food_2770309_jif_creamy_16oz", {"fdc_id": "2770309"})
    b.source("S2", "gsrs_unii_451W47IQ8X")
    b.assume("J1", "sample_identity", "The sample is GTIN 00051500255162 (Jif Creamy, 16 oz).")
    b.assume("J2", "label_truth",
             "The FDC Branded record (manufacturer data via GDSN) reproduces the sample's "
             "label.")  # fmt: skip
    b.assume("J3", "interpretation",
             "An FDC labelNutrients value that is a valid 21 CFR 101.9(c) declaration is the "
             "label's declared value; FDC computes the others from per-100 g data, so they are "
             "not used (spec §7).")  # fmt: skip
    b.assume(
        "J4",
        "interpretation",
        "FDC labelNutrients units: g, mg for cholesterol and sodium, kcal for calories.",
    )
    b.assume("J5", "modelling", "'Salt' is sodium chloride.")
    b.assume("J6", "modelling", "'Sugar' is sucrose, which is all sugars.")
    b.head["variant_note"] = (
        "FDC 2770309 is the 16 oz jar (GTIN 00051500255162). Other Jif sizes in FDC list "
        "the ingredients in a different order or with mono- and diglycerides."
    )
    b.fact("F_serving", "serving_mass", "per_serving", "S1",
           X.pointer("", ["servingSize", "servingSizeUnit"]), "fdc_serving@1",
           _as_stated("J2"), assumptions=("J2",))  # fmt: skip
    data_keys = sorted(FDC_TO_101_9)
    for key in data_keys:
        nutrient = FDC_TO_101_9[key]
        try:
            b.fact(f"F_{nutrient}", nutrient, "per_serving", "S1", X.fdc_label(key),
                   f"fdc_label_nutrient@1:{key}",
                   _rounded(f"fda_rounding_101_9@1:{nutrient}"),
                   assumptions=("J2", "J3", "J4"))  # fmt: skip
        except InterpretError as e:
            b.note(f"FDC labelNutrients.{key} not used: {e} (FDC-computed, not a label value)")
    for n in range(1, 6):
        b.ingredient(f"I{n}", "fdc_ingredients", n, "food", "S1", X.pointer("/ingredients"),
                     list_rule=f"list_item@1:{n}")  # fmt: skip
    b.substance("SUB_nacl", "451W47IQ8X", "S2", X.gsrs_first("approvalID"),
                name_locator=X.gsrs_first("_name"),
                formula_locator=X.gsrs_first("structure/formula"))  # fmt: skip


# ----------------------------------------------------------------- Nutricost
def nutricost(b: RecordBuilder) -> None:
    b.source("S1", "dsld_label_223424_nutricost_mgo", {"dsld_id": "223424"})
    b.source("S2", "gsrs_unii_3A3U0GI71G")
    b.assume("N1", "sample_identity", "The sample is DSLD label 223424 (UPC 7 02669 93439 8).")
    b.assume("N2", "label_truth", "The DSLD record reproduces the sample's label.")
    b.assume("N3", "interpretation",
             "Supplement Facts mineral amounts have no increment rule (21 CFR "
             "101.36(b)(2)(ii)(B): 'levels of significance'); amounts are taken as stated.")  # fmt: skip
    b.assume("N4", "modelling", "All magnesium is from the magnesium oxide named as its source.")
    b.head["variant_note"] = "DSLD label 223424, the only Nutricost Magnesium Oxide label."
    b.fact("F_mg", "magnesium", "per_unit", "S1", X.dsld_row_quantity(0), "quantity@1",
           _as_stated("N3"), assumptions=("N2", "N3"))  # fmt: skip
    b.fact("F_mgo", "magnesium_oxide", "per_unit", "S1", X.pointer("/statements/7/notes"),
           "line_amount@1:3", _as_stated("N3"), assumptions=("N2", "N3"))  # fmt: skip
    b.ingredient("I_mg", "dsld_dietary", 1, "dietary", "S1", X.pointer("/ingredientRows/0/name"))
    b.ingredient("I_mg_form", "dsld_dietary_form", 1, "source_of_dietary", "S1",
                 X.pointer("/ingredientRows/0/forms/0/name"), substance="SUB_mgo")  # fmt: skip
    for n in range(4):
        b.ingredient(f"I_other_{n + 1}", "dsld_other", n + 1, "other", "S1",
                     X.pointer(f"/otheringredients/ingredients/{n}/name"))  # fmt: skip
    b.substance("SUB_mgo", "3A3U0GI71G", "S2", X.gsrs_first("approvalID"),
                name_locator=X.gsrs_first("_name"),
                formula_locator=X.gsrs_first("structure/formula"))  # fmt: skip


# -------------------------------------------------------------------- Nutella
OFF_NUTRIENTS = {
    "energy-kcal": "energy", "fat": "total_fat", "saturated-fat": "saturated_fat",
    "carbohydrates": "total_carbohydrate", "sugars": "total_sugars", "proteins": "protein",
    "salt": "salt",
}  # fmt: skip


def nutella(b: RecordBuilder) -> None:
    b.source("S1", "off_product_3017620422003_nutella", {"gtin": "3017620422003"})
    b.assume("E1", "sample_identity",
             "The sample is the French-market 400 g jar (GTIN 3017620422003); its label is the "
             "French ingredient text.")  # fmt: skip
    b.assume(
        "E2",
        "label_truth",
        "The Open Food Facts record (crowd-sourced) transcribes the French label.",
    )
    b.assume("E3", "interpretation",
             "QUID percentages (Reg. 1169/2011 Art. 22) have no rounding rule; taken as stated, "
             "as percent of the finished product at the time of use (Annex VIII 3).", "quid@1")  # fmt: skip
    b.assume("E4", "interpretation",
             "EU nutrition values per 100 g are taken as stated (no rounding rule in the "
             "regulation; EU guidance on tolerances is not law).")  # fmt: skip
    b.head["variant_note"] = (
        "Open Food Facts holds different ingredient texts per language (FR, DE, IT differ in "
        "milk powder % and whey); the FR text is used for the French jar. The EN text in the "
        "record is incomplete ('sugar, palm oil')."
    )
    text = X.pointer("/product/ingredients_text_fr")
    for n, q in ((3, "hazelnuts"), (4, "fat_reduced_cocoa"), (5, "skimmed_milk_powder")):
        b.fact(f"F_quid_{q}", q, "per_100g", "S1", text, f"ingredient_list@1:{n}",
               _as_stated("E3"), assumptions=("E2", "E3"))  # fmt: skip
    for key, q in OFF_NUTRIENTS.items():
        b.fact(f"F_{q}", q, "per_100g", "S1", X.off_nutrient(key), "quantity@1",
               _as_stated("E4"), assumptions=("E2", "E4"))  # fmt: skip
    for n in range(1, 9):
        b.ingredient(f"I{n}", "off_ingredients_fr", n, "food", "S1", text,
                     list_rule=f"list_item@1:{n}")  # fmt: skip


# ---------------------------------------------------------- crosswalk links
class NeedsSignature(RuntimeError):
    """A golden record that rests on an operator's attestation not yet signed."""


def apply_link(b: RecordBuilder, row: dict[str, Any], spl_source: str, package_ndc: str,
               product_code: str) -> None:  # fmt: skip
    """The attested barcode -> NDC link of a crosswalk row, and the SPL product it selects."""
    ev = row["evidence"]
    b.source_sha("P_ndc", ev["photo_sha256"], {"role": "printed NDC evidence"})
    att = row["attestation"]
    b.attestations.append({
        "id": "AT_ndc", "signer": att["operator"], "signed_at": att["timestamp"],
        "statement": att["statement"], "subjects": ["L1"],
    })  # fmt: skip
    b.link("L1", method=row["method"], ndc11=row["ndc11"], attestation_id="AT_ndc",
           source_id="P_ndc", box=ev["bbox"], span=ev["ndc_text"])  # fmt: skip
    b.select("SEL1", "L1", spl_source, package_ndc, product_code, X.HL7)


# ------------------------------------------------------------- Care One
CAREONE = "41520-745"
CAREONE_INACTIVE = 8


def careone(b: RecordBuilder) -> None:
    row = crosswalk.link_for("00341520314643", CROSSWALK_PATH[0])
    if row is None:
        raise NeedsSignature("Care One ibuprofen: sign the crosswalk proposal "
                             "(python -m lio_comp.crosswalk sign 00341520314643 --operator NAME)")  # fmt: skip
    b.source("S1", "dailymed_spl_careone_ibuprofen_016299ef", {"spl_setid": row["setid"]})
    b.assume("K1", "sample_identity", "The sample carries barcode 3 41520 31464 3.")
    b.assume(
        "K2", "label_truth", "The SPL (set 016299ef, version 3) states the product's formulation."
    )
    b.assume(
        "K3",
        "interpretation",
        "The 'Other information' section applies to product 41520-745, the only product in this SPL (text_variant_attribution).",
    )
    b.head["variant_note"] = (
        "The barcode carries NDC 41520-314-64, which is in no current SPL (RxNav: UNKNOWN). The "
        "carton prints NDC 41520-745-18; the attested link L1 selects SPL product 41520-745."
    )
    apply_link(b, row, "S1", row["ndc"], CAREONE)
    b.ingredient("I_active_1", "spl_active", 1, "active", "S1",
                 X.spl_ingredient(CAREONE, "ACTIB", 1, "name"),
                 unii_locator=X.spl_ingredient(CAREONE, "ACTIB", 1, "unii"))  # fmt: skip
    for n in range(1, CAREONE_INACTIVE + 1):
        b.ingredient(f"I_inactive_{n}", "spl_inactive", n, "inactive", "S1",
                     X.spl_ingredient(CAREONE, "IACT", n, "name"),
                     unii_locator=X.spl_ingredient(CAREONE, "IACT", n, "unii"))  # fmt: skip
    b.fact("F1", "ibuprofen", "per_unit", "S1", X.spl_active_quantity(CAREONE, "numerator"),
           "quantity@1", EXACT, substance={"ingredient": "I_active_1"}, assumptions=("K2",))  # fmt: skip
    b.fact("F2", "potassium", "per_unit", "S1",
           {"type": "xpath", "namespaces": X.HL7,
            "expr": "//v:section[normalize-space(v:title)='Other information']/v:text/v:list/v:item[starts-with(normalize-space(.), 'each capsule contains')]"},
           "otc_contains@1:potassium", _rounded("fda_otc_rounding_201@1:potassium"),
           assumptions=("K2", "K3"))  # fmt: skip
    b.note(
        "OTC inactive ingredients are listed alphabetically (21 CFR 201.66(c)(8)): no weight-order constraint."
    )


GOLDEN: dict[str, Callable[[RecordBuilder], None]] = {
    "careone_ibuprofen_341520314643": careone,
    "citrucel_orange_300680418301": citrucel,
    "jif_creamy_16oz_051500255162": jif,
    "nutricost_magnesium_oxide_702669934398": nutricost,
    "nutella_fr_3017620422003": nutella,
}
CROSSWALK_PATH = [crosswalk.LINKS]  # tests point this at a fixture crosswalk

HEADS = {
    "careone_ibuprofen_341520314643": ("00341520314643", "Care One Ibuprofen 200 mg softgels"),
    "citrucel_orange_300680418301": ("00300680418301", "CITRUCEL Orange (methylcellulose) powder"),
    "jif_creamy_16oz_051500255162": ("00051500255162", "Jif Creamy Peanut Butter 16 oz"),
    "nutricost_magnesium_oxide_702669934398": (
        "00702669934398",
        "Nutricost Magnesium Oxide 420 mg capsules",
    ),
    "nutella_fr_3017620422003": ("03017620422003", "Nutella 400 g (France)"),
}


def build(store: Path, rules: Path, name: str) -> RecordBuilder:
    gtin, product = HEADS[name]
    b = RecordBuilder(
        store, load_tables(rules), record_id=name, gtin=gtin, product_name=product, variant_note=""
    )
    GOLDEN[name](b)
    add_derivations(b, name)
    return b


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--rules", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("names", nargs="*")
    a = ap.parse_args(argv)
    for name in a.names or sorted(GOLDEN):
        try:
            print(build(a.store, a.rules, name).write(a.out))
        except NeedsSignature as e:
            print(f"skipped {name}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
