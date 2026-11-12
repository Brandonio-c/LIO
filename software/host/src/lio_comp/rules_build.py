# ruff: noqa: E501  (regulatory quotes are kept whole)
"""Build the versioned rule tables in ``composition/rules/`` (spec §3.2).

Every rule cites the regulation or reference it encodes: a quote located by
character span in a snapshot from the evidence store (``char_span`` on the
UTF-8 text). The verifier re-checks each quote against the snapshot. Run:

    python -m lio_comp.rules_build --store composition/sources --out composition/rules

The tables are data; this script only finds the quotes and writes the files,
so changing a rule means editing it here, bumping its version, and rebuilding.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from lio_comp import catalog
from lio_comp.evidence import canonical_json, get
from lio_verify.chem import parse_mf, parse_row

ATOMIC_ELEMENTS = (
    "H", "C", "N", "O", "Na", "Mg", "Al", "P", "S", "Cl", "K", "Ca", "Ti", "Mn", "Fe", "Cu",
    "Zn", "Se", "I",
)  # fmt: skip


class Cite:
    def __init__(self, store: Path) -> None:
        self.store = store
        self.cat = catalog.load(store)
        self._text: dict[str, str] = {}

    def text(self, doc: str) -> str:
        if doc not in self._text:
            self._text[doc] = get(self.store, self.cat[doc]).decode("utf-8")
        return self._text[doc]

    def __call__(self, doc: str, quote: str, *, after: str | None = None) -> dict[str, Any]:
        t = self.text(doc)
        start = 0
        if after is not None:
            start = t.find(after)
            if start < 0:
                raise LookupError(f"{doc}: anchor not found: {after!r}")
        i = t.find(quote, start)
        if i < 0:
            raise LookupError(f"{doc}: quote not found: {quote!r}")
        return {
            "source": doc,
            "sha256": self.cat[doc],
            "locator": {
                "type": "char_span",
                "encoding": "utf-8",
                "start": i,
                "end": i + len(quote),
                "text": quote,
            },
        }


def _band(lo: str, hi: str | None, lo_c: bool, hi_c: bool, mode: str, kind: str,
          param: str | None = None) -> dict[str, Any]:  # fmt: skip
    disp: dict[str, Any] = {"kind": kind}
    if kind == "nearest":
        disp["step"] = param
    elif kind == "less_than":
        disp["limit"] = param
    return {"lo": lo, "hi": hi, "lo_closed": lo_c, "hi_closed": hi_c, "mode": mode,
            "display": disp}  # fmt: skip


def _fats() -> list[dict[str, Any]]:
    return [
        _band("0", "1/2", True, False, "shall", "zero"),
        _band("1/2", "5", True, False, "default", "nearest", "1/2"),
        _band("5", None, True, False, "default", "nearest", "1"),
    ]


def _grams_lt1() -> list[dict[str, Any]]:
    return [
        _band("0", None, True, False, "default", "nearest", "1"),
        _band("0", "1", True, False, "may", "less_than", "1"),
        _band("0", "1/2", True, False, "may", "zero"),
    ]


def _calories() -> list[dict[str, Any]]:
    return [
        _band("0", "50", True, True, "default", "nearest", "5"),
        _band("50", None, False, False, "default", "nearest", "10"),
        _band("0", "5", True, False, "may", "zero"),
    ]


def fda_rounding(c: Cite) -> dict[str, Any]:
    d = "ecfr_21cfr101_9"
    lt1 = (
        "expressed to the nearest gram, except that if a serving contains less than 1 gram, "
        "the statement “Contains less than 1 gram” or “less than 1 gram” may be used as an "
        "alternative, and if the serving contains less than 0.5 gram, the content may be "
        "expressed as zero"
    )
    fat_q = (
        "gram increment below 5 grams and to the nearest gram increment above 5 grams. "
        "If the serving contains less than 0.5 gram, the content"
    )
    nutrients: dict[str, Any] = {
        "calories": (
            "kcal",
            "21 CFR 101.9(c)(1)",
            _calories(),
            [
                c(
                    d,
                    "expressed to the nearest 5-calorie increment up to and including 50 calories, and "
                    "10-calorie increment above 50 calories, except that amounts less than 5 calories "
                    "may be expressed as zero",
                    after="(1) “Calories, total,”",
                )
            ],
        ),
        "calories_from_saturated_fat": (
            "kcal",
            "21 CFR 101.9(c)(1)(ii)",
            _calories(),
            [
                c(
                    d,
                    "expressed to the nearest 5-calorie increment, up to and including 50 calories, and "
                    "the nearest 10-calorie increment above 50 calories, except that amounts less than "
                    "5 calories may be expressed as zero",
                    after="Calories from saturated fat",
                )
            ],
        ),
        "total_fat": (
            "g",
            "21 CFR 101.9(c)(2)",
            _fats(),
            [
                c(d, "Amounts shall be expressed to the nearest 0.5", after="(2) “Fat, total”"),
                c(d, fat_q + " shall be expressed as zero", after="(2) “Fat, total”"),
            ],
        ),
        "saturated_fat": (
            "g",
            "21 CFR 101.9(c)(2)(i)",
            _fats(),
            [c(d, fat_q + " shall be expressed as zero", after="Saturated fat content")],
        ),
        "trans_fat": (
            "g",
            "21 CFR 101.9(c)(2)(ii)",
            _fats(),
            [
                c(
                    d,
                    fat_q + ", when declared, shall be expressed as zero",
                    after="Trans fat content shall be",
                )
            ],
        ),
        "polyunsaturated_fat": (
            "g",
            "21 CFR 101.9(c)(2)(iii)",
            _fats(),
            [c(d, fat_q + " shall be expressed as zero", after="Polyunsaturated fat content")],
        ),
        "monounsaturated_fat": (
            "g",
            "21 CFR 101.9(c)(2)(iv)",
            _fats(),
            [c(d, fat_q + " shall be expressed as zero", after="Monounsaturated fat content")],
        ),
        "cholesterol": (
            "mg",
            "21 CFR 101.9(c)(3)",
            [
                _band("0", None, True, False, "default", "nearest", "5"),
                _band("0", "2", True, False, "may", "zero"),
                _band("2", "5", True, True, "may", "less_than", "5"),
            ],
            [
                c(
                    d,
                    "expressed in milligrams to the nearest 5-milligram increment",
                    after="(3) “Cholesterol”",
                ),
                c(d, "may state the cholesterol content as zero", after="(3) “Cholesterol”"),
                c(
                    d,
                    "If the food contains 2 to 5 milligrams of cholesterol per serving, the content "
                    "may be stated as “less than 5 milligrams.”",
                ),
            ],
        ),
        "sodium": (
            "mg",
            "21 CFR 101.9(c)(4)",
            [
                _band("0", "5", True, False, "shall", "zero"),
                _band("5", "140", True, True, "default", "nearest", "5"),
                _band("140", None, False, False, "default", "nearest", "10"),
            ],
            [
                c(
                    d,
                    "expressed as zero when the serving contains less than 5 milligrams of sodium, "
                    "to the nearest 5-milligram increment when the serving contains 5 to 140 "
                    "milligrams of sodium, and to the nearest 10-milligram increment when the "
                    "serving contains greater than 140 milligrams",
                    after="(4) “Sodium”",
                )
            ],
        ),
        "fluoride": (
            "mg",
            "21 CFR 101.9(c)(5)",
            [
                _band("0", "1/10", True, False, "shall", "zero"),
                _band("1/10", "4/5", True, True, "default", "nearest", "1/10"),
                _band("4/5", None, False, False, "default", "nearest", "1/5"),
            ],
            [
                c(
                    d,
                    "Fluoride content shall be expressed as zero when the serving contains less "
                    "than 0.1 milligrams of fluoride, to the nearest 0.1-milligram increment when "
                    "the serving contains less than or equal to 0.8 milligrams of fluoride, and "
                    "the nearest 0.2 milligram-increment when a serving contains more than 0.8 "
                    "milligrams of fluoride",
                )
            ],
        ),
        "total_carbohydrate": (
            "g",
            "21 CFR 101.9(c)(6)",
            _grams_lt1(),
            [
                c(
                    d,
                    "expressed to the nearest gram, except that if a serving contains less than 1 gram, "
                    "the statement “Contains less than 1 gram” or “less than 1 gram” may be used as an "
                    "alternative, or if the serving contains less than 0.5 gram, the content may be "
                    "expressed as zero",
                    after="(6) “Carbohydrate, total”",
                )
            ],
        ),
        "dietary_fiber": (
            "g",
            "21 CFR 101.9(c)(6)(i)",
            _grams_lt1(),
            [
                c(
                    d,
                    "expressed to the nearest gram, except that if a serving contains less than 1 gram, "
                    "declaration of dietary fiber is not required or, alternatively, the statement "
                    "“Contains less than 1 gram” or “less than 1 gram” may be used, and if the serving "
                    "contains less than 0.5 gram, the content may be expressed as zero",
                    after="(i) “Dietary fiber”",
                )
            ],
        ),
        "soluble_fiber": (
            "g",
            "21 CFR 101.9(c)(6)(i)(A)",
            _grams_lt1(),
            [c(d, lt1, after="Soluble fiber content")],
        ),
        "insoluble_fiber": (
            "g",
            "21 CFR 101.9(c)(6)(i)(B)",
            _grams_lt1(),
            [c(d, lt1, after="Insoluble fiber content")],
        ),
        "total_sugars": (
            "g",
            "21 CFR 101.9(c)(6)(ii)",
            _grams_lt1(),
            [c(d, lt1, after="Total sugars content shall")],
        ),
        "added_sugars": (
            "g",
            "21 CFR 101.9(c)(6)(iii)",
            _grams_lt1(),
            [c(d, "It shall be " + lt1, after="(iii) “Added Sugars”")],
        ),
        "sugar_alcohol": (
            "g",
            "21 CFR 101.9(c)(6)(iv)",
            _grams_lt1(),
            [c(d, lt1, after="Sugar alcohol content shall")],
        ),
        "protein": ("g", "21 CFR 101.9(c)(7)", _grams_lt1(), [c(d, lt1, after="(7) “Protein”")]),
        "vitamin_mineral_percent_dv": (
            "percent_dv",
            "21 CFR 101.9(c)(8)(iii)",
            [
                _band("0", "10", True, True, "default", "nearest", "2"),
                _band("10", "50", False, True, "default", "nearest", "5"),
                _band("50", None, False, False, "default", "nearest", "10"),
            ],
            [
                c(
                    d,
                    "percentages for vitamins and minerals shall be expressed to the nearest "
                    "2-percent increment up to and including the 10-percent level, the nearest "
                    "5-percent increment above 10 percent and up to and including the 50-percent "
                    "level, and the nearest 10-percent increment above the 50-percent level",
                )
            ],
        ),
    }
    return {
        "id": "fda_rounding_101_9",
        "version": 1,
        "citation": "21 CFR 101.9(c), eCFR text as of 2026-11-01",
        "effective_date": "2026-11-01",
        "basis": "per_serving",
        "ties": "half_up",
        "ties_citation": {
            "source": "fda_food_labeling_guide_2013",
            "sha256": c.cat["fda_food_labeling_guide_2013"],
            "locator": {
                "type": "pdf_text",
                "page_label": "130",
                "text": "To express nutrient values to the nearest 1 g increment, for amounts "
                "falling exactly halfway between two whole numbers or higher (e.g., 2.5 to "
                "2.99 g), round up (e.g., 3 g).",
            },
        },
        "notes": [
            "Quantitative amounts of vitamins and minerals (mg, mcg), including potassium, have "
            "no increment rule in 21 CFR 101.9(c)(8); they are not in this table and are "
            "interpreted only through a named assumption.",
            "Where a band's display is 'may', the label can use it or the default; 'shall' "
            "overrides every other display inside its range.",
        ],
        "nutrients": {
            k: {"unit": u, "paragraph": para, "bands": bands, "citations": cites}
            for k, (u, para, bands, cites) in nutrients.items()
        },
    }


def fda_otc_rounding(c: Cite) -> dict[str, Any]:
    def mineral(doc: str, el: str) -> dict[str, Any]:
        return {
            "unit": "mg",
            "paragraph": f"21 CFR {doc[10:].replace('_', '.')}(b)",
            "bands": [
                _band("0", "1000", True, False, "default", "nearest", "5"),
                _band("1000", None, True, False, "default", "nearest", "100"),
            ],
            "citations": [
                c(
                    doc,
                    f"The {el} content{' per dosage unit' if el == 'calcium' else ''}"
                    " shall be rounded-off to the nearest 5 milligrams (or nearest "
                    "tenth of a gram if over 1 gram)",
                )
            ],
        }

    return {
        "id": "fda_otc_rounding_201",
        "version": 1,
        "citation": "21 CFR 201.64(b), 201.70(b), 201.72(b), eCFR text as of 2026-11-01",
        "effective_date": "2026-11-01",
        "basis": "per_dosage_unit",
        "ties": "either",
        "notes": [
            "The regulations do not say how a value exactly halfway is rounded, so both "
            "neighbours are allowed (intervals closed at both ends).",
            "Amounts are per dosage unit, as stated under 'Other information' (21 CFR "
            "201.66(c)(7)).",
        ],
        "nutrients": {
            "sodium": {
                "unit": "mg",
                "paragraph": "21 CFR 201.64(b)",
                "bands": [_band("0", None, True, False, "default", "nearest", "1")],
                "citations": [
                    c(
                        "ecfr_21cfr201_64",
                        "The sodium content shall be rounded-off to the nearest whole number",
                    )
                ],
            },
            "calcium": mineral("ecfr_21cfr201_70", "calcium"),
            "potassium": mineral("ecfr_21cfr201_72", "potassium"),
        },
    }


def atwater(c: Cite) -> dict[str, Any]:
    return {
        "id": "atwater",
        "version": 1,
        "citation": "21 CFR 101.9(c)(1)(i)(B)",
        "effective_date": "2026-11-01",
        "constants": {
            "protein": {"value": "4", "unit": "kcal/g"},
            "carbohydrate": {"value": "4", "unit": "kcal/g"},
            "fat": {"value": "9", "unit": "kcal/g"},
        },
        "citations": [
            c(
                "ecfr_21cfr101_9",
                "(B) Using the general factors of 4, 4, and 9 calories per gram for "
                "protein, total carbohydrate, and total fat, respectively",
            )
        ],
        "notes": [
            "101.9(c)(1)(i) allows other methods (specific Atwater factors, bomb calorimetry, "
            "...). Using the general factors for a given label is an assumption.",
        ],
    }


def atomic_masses(c: Cite) -> dict[str, Any]:
    doc = "ciaaw_standard_atomic_weights"
    t = c.text(doc)
    elements: dict[str, Any] = {}
    for el in ATOMIC_ELEMENTS:
        m = re.search(rf"<td>{el}</td><td><a [^>]*>[a-z]+</a></td><td>[^<]*</td>", t)
        if not m:
            raise LookupError(f"CIAAW row for {el} not found")
        cite = c(doc, m.group(0))
        sym, w = parse_row(m.group(0))
        assert sym == el
        elements[el] = {"weight": w.to_json("1"), "citation": cite, "rule": "ciaaw_row@1"}
    return {
        "id": "atomic_masses",
        "version": 1,
        "citation": "IUPAC CIAAW, Standard Atomic Weights 2024 (Atomic Weights 2021 report "
        "with the 2024 revisions), ciaaw.org/atomic-weights.htm",
        "effective_date": "2024-01-01",
        "notes": [
            "Weights are intervals: CIAAW's interval, or the value plus/minus its standard "
            "uncertainty. Only ratios are used (mass fractions), so the molar mass constant "
            "cancels.",
            "Elements marked 'g' by CIAAW (e.g. Ca) can fall outside the range in exceptional "
            "geological samples; using the standard weight is an assumption.",
        ],
        "elements": elements,
    }


# Formulas copied from the FDA UNII records (MF column of UNII_Records_4Aug2026.txt);
# element counts are parsed from them (unii_mf@1), never typed.
COMPOUNDS: dict[str, tuple[str, str]] = {
    "L11K75P92J": ("ANHYDROUS DIBASIC CALCIUM PHOSPHATE", "Ca.HO4P"),
    "K4C08XP666": ("TRICALCIUM PHOSPHATE", "3Ca.2O4P"),
    "EE90ONI6FF": ("POTASSIUM CITRATE", "C6H5O7.3K.H2O"),
    "2968PHW8QP": ("CITRIC ACID MONOHYDRATE", "C6H8O7.H2O"),
    "C151H8M554": ("SUCROSE", "C12H22O11"),
}


def compounds() -> dict[str, Any]:
    return {
        "id": "compounds",
        "version": 1,
        "citation": "FDA UNII records (UNII_Records_4Aug2026.txt), molecular formula column",
        "effective_date": "2026-08-04",
        "notes": [
            "Molar masses and element mass fractions are not stored: the verifier computes "
            "them from these formulas and the atomic_masses table.",
            "TRICALCIUM PHOSPHATE: the UNII formula is Ca3(PO4)2. The food/USP material "
            "('tribasic calcium phosphate') is a variable mixture close to hydroxyapatite; "
            "using Ca3(PO4)2 is an assumption.",
        ],
        "compounds": {
            unii: {"name": name, "unii_mf": mf, "counts": parse_mf(mf), "rule": "unii_mf@1"}
            for unii, (name, mf) in COMPOUNDS.items()
        },
    }


def units() -> dict[str, Any]:
    return {
        "id": "units",
        "version": 1,
        "citation": "SI; thermochemical calorie (1 cal = 4.184 J exactly)",
        "effective_date": "2019-05-20",
        "mass_to_g": {"kg": "1000", "g": "1", "mg": "1/1000", "mcg": "1/1000000",
                      "µg": "1/1000000"},
        "energy_to_kcal": {"kcal": "1", "kJ": "125/523"},
        "notes": [
            "International Units depend on the vitamin and its form; they are not converted.",
        ],
    }  # fmt: skip


def list_ordering(c: Cite) -> dict[str, Any]:
    return {
        "id": "list_ordering",
        "version": 1,
        "effective_date": "2026-11-01",
        "lists": {
            "us_food_ingredients": {
                "order": "descending_weight",
                "exception": "ingredients at <= 2 % (or the stated threshold) may follow a "
                "quantifying statement in any order",
                "citations": [
                    c(
                        "ecfr_21cfr101_4",
                        "shall be listed by common or usual name in descending "
                        "order of predominance by weight",
                    ),
                    c(
                        "ecfr_21cfr101_4",
                        "do not apply to ingredients present in amounts of 2 "
                        "percent or less by weight when a listing of these ingredients is placed at "
                        "the end of the ingredient statement following an appropriate quantifying "
                        "statement",
                    ),
                ],
            },
            "us_otc_inactive_ingredients": {
                "order": "alphabetical",
                "citations": [
                    c(
                        "ecfr_21cfr201_66",
                        "If the product is an OTC drug product that "
                        "is not also a cosmetic product, then the inactive ingredients "
                        "shall be listed in alphabetical order",
                    )
                ],
            },
            "eu_food_ingredients": {
                "order": "descending_weight",
                "exception": "Annex VII Part A: e.g. ingredients under 2 % may be listed in a "
                "different order after the others",
                "citations": [
                    c(
                        "eu_reg_1169_2011_consolidated_20180101",
                        "descending order of weight, as recorded at the time of their "
                        "use in the manufacture of the food",
                    )
                ],
            },
        },
    }


def quid(c: Cite) -> dict[str, Any]:
    eu = "eu_reg_1169_2011_consolidated_20180101"
    return {
        "id": "quid",
        "version": 1,
        "citation": "Regulation (EU) No 1169/2011, Art. 22 and Annex VIII (consolidated "
        "2018-01-01)",
        "effective_date": "2018-01-01",
        "semantics": {
            "unit": "percent",
            "basis": "ingredient mass at the time of use, per mass of the finished product "
            "(Annex VIII 3); exceptions in Annex VIII 4 (moisture loss, volatile ingredients)",
            "rounding": "none defined; a declared percentage is interpreted through a named "
            "assumption",
        },
        "citations": [
            c(eu, "Quantitative indication of ingredients", after="Article 22"),
            c(eu, "QUANTITATIVE INDICATION OF INGREDIENTS", after="ANNEX VIII"),
        ],
    }


def build(store: Path) -> dict[str, dict[str, Any]]:
    c = Cite(store)
    tables = [
        fda_rounding(c),
        fda_otc_rounding(c),
        atwater(c),
        atomic_masses(c),
        compounds(),
        units(),
        list_ordering(c),
        quid(c),
    ]
    return {t["id"]: t for t in tables}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    for name, table in build(a.store).items():
        (a.out / f"{name}.json").write_bytes(canonical_json(table))
        print(f"{name}@{table['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
