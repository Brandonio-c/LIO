"""Deterministic, versioned rules that turn located text into a raw value.

A fact names a rule ``name@version`` (optionally ``:selector``). The verifier
re-runs the rule on the located text and requires the same ``value_raw``; then
:func:`parse_raw` turns ``value_raw`` into an exact number and a unit.

Rules (all pure functions of the located text):

- ``quantity@1``: the text is "<decimal> <unit>" ("2 g", "420 mg").
- ``otc_contains@1:<name>``: an OTC "Other information" statement,
  "each <dose> contains: calcium 80 mg, potassium 105 mg, ..." (21 CFR
  201.66(c)(7)(i)); selects the named ingredient's amount.
- ``otc_calories_from@1``: "each <dose> contributes 60 calories from ...".
- ``fdc_label_nutrient@1:<nutrient>``: a bare number from FoodData Central
  ``labelNutrients``; the unit is fixed per nutrient (assumption A-FDC-UNITS).
- ``nfp_row@1:<nutrient>``: a row of a US Nutrition Facts panel ("Total Fat 16g 21%").
- ``nfp_serving@1``: the panel's serving size in grams ("Serving size 2 Tbsp (32g)").
- ``fdc_serving@1``: FoodData Central ``servingSize servingSizeUnit`` ("33.0 GRM").
- ``line_amount@1:<n>``: the amount opening line ``n`` (from 1) of a multi-line
  statement ("750 mg per serving" -> "750 mg").
- ``list_item@1:<index>``: the ``index``-th top-level item (from 1) of a
  comma-separated ingredient list, verbatim (used for ingredient identity).
- ``ingredient_list@1:<index>``: that item's stated percentage ("13%").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from lark import Lark, LarkError, Token, Tree

from lio_verify.interval import parse_decimal


class RuleError(ValueError):
    pass


UNITS = {"g", "mg", "mcg", "kcal", "ml", "%"}

_OTC = Lark(
    r"""
    start: "each"i dose "contains"i ":" item ("," item)* "."?
    dose: WORD+
    item: name NUMBER UNIT
    name: WORD+
    NUMBER: /[0-9]+(\.[0-9]+)?/
    UNIT: /(mg|g|mcg)\b/
    WORD: /(?!(mg|g|mcg)\b)(?!contains\b)[A-Za-z][A-Za-z-]*/
    %import common.WS
    %ignore WS
    """,
    parser="lalr",
)

_CAL = re.compile(
    r"each (?P<dose>[a-z ]+?) contributes (?P<n>[0-9]+(?:\.[0-9]+)?) calories from "
    r"(?P<from>[a-z ,]+?)\.?",
    re.I,
)
_QTY = re.compile(r"(?P<n>[0-9]+(?:\.[0-9]+)?) (?P<u>[A-Za-z%]+)")
_PCT = re.compile(r"(?P<n>[0-9]+(?:[.,][0-9]+)?)\s?%")

_AMT = r"(?P<lt><\s*|less than\s+)?(?P<n>[0-9]+(?:\.[0-9]+)?)\s*(?P<u>{u})\b"
NFP_ROWS: dict[str, tuple[str, str]] = {  # 21 CFR 101.9(c) nutrient -> (row label, unit)
    "total_fat": (r"total\s+fat", "g"),
    "saturated_fat": (r"sat(?:urated|\.)?\s+fat", "g"),
    "trans_fat": (r"trans\s+fat", "g"),
    "polyunsaturated_fat": (r"polyunsat(?:urated|\.)?\s+fat", "g"),
    "monounsaturated_fat": (r"monounsat(?:urated|\.)?\s+fat", "g"),
    "cholesterol": (r"cholest(?:erol|\.)?", "mg"),
    "sodium": (r"sodium", "mg"),
    "total_carbohydrate": (r"total\s+carb(?:ohydrate|s|\.)?", "g"),
    "dietary_fiber": (r"dietary\s+fib(?:er|re)", "g"),
    "total_sugars": (r"total\s+sugars", "g"),
    "protein": (r"protein", "g"),
}


def nfp_row(nutrient: str, text: str) -> str:
    """``nfp_row@1``: one row of a US Nutrition Facts panel -> its declared amount."""
    t = " ".join(text.split())
    if nutrient == "calories":
        m = re.fullmatch(r"calories\s+(?P<n>[0-9]+)(\s.*)?", t, re.I)
        if not m:
            raise RuleError(f"not a Calories row: {text!r}")
        return f"{m.group('n')} kcal"
    if nutrient == "added_sugars":
        m = re.fullmatch(
            r"incl(?:udes|\.)?\s+" + _AMT.format(u="g") + r"\s+added\s+sugars(\s.*)?", t, re.I
        )
    elif nutrient in NFP_ROWS:
        label, unit = NFP_ROWS[nutrient]
        m = re.fullmatch(label + r"\s+" + _AMT.format(u=unit) + r"(\s.*)?", t, re.I)
    else:
        raise RuleError(f"no Nutrition Facts row rule for {nutrient!r}")
    if not m:
        raise RuleError(f"not a {nutrient} row: {text!r}")
    return f"{'<' if m.group('lt') else ''}{m.group('n')} {m.group('u').lower()}"


def nfp_serving(text: str) -> str:
    """``nfp_serving@1``: "Serving size 2 Tbsp (32g)" -> "32 g"."""
    t = " ".join(text.split())
    m = re.fullmatch(r"serving\s+size\b.*?(?P<n>[0-9]+(?:\.[0-9]+)?)\s*(?P<u>g|ml)\s*\)?", t, re.I)
    if not m:
        raise RuleError(f"not a serving-size row with grams: {text!r}")
    return f"{m.group('n')} {m.group('u').lower()}"


FDC_LABEL_UNITS = {
    "calories": "kcal",
    "fat": "g",
    "saturatedFat": "g",
    "transFat": "g",
    "carbohydrates": "g",
    "fiber": "g",
    "sugars": "g",
    "addedSugar": "g",
    "protein": "g",
    "cholesterol": "mg",
    "sodium": "mg",
    "potassium": "mg",
    "calcium": "mg",
    "iron": "mg",
}


@dataclass(frozen=True)
class Raw:
    value: Fraction
    unit: str


def parse_raw(value_raw: str) -> Raw:
    """``value_raw`` ("2 g", "13%", "7,4%", "16.0 g") -> exact value and unit."""
    m = _QTY.fullmatch(value_raw)
    if m and m.group("u") in UNITS:
        return Raw(parse_decimal(m.group("n")), m.group("u"))
    m = _PCT.fullmatch(value_raw)
    if m:
        return Raw(parse_decimal(m.group("n").replace(",", ".")), "%")
    raise RuleError(f"not a raw value: {value_raw!r}")


def _otc_items(text: str) -> dict[str, str]:
    try:
        tree = _OTC.parse(" ".join(text.split()))
    except LarkError as e:
        raise RuleError(f"not an OTC 'contains' statement: {e}") from e
    out: dict[str, str] = {}
    for item in tree.find_data("item"):
        name_tree, num, unit = item.children
        assert isinstance(name_tree, Tree) and isinstance(num, Token) and isinstance(unit, Token)
        name = " ".join(str(t) for t in name_tree.children).lower()
        if name in out:
            raise RuleError(f"{name} stated twice")
        out[name] = f"{num} {unit}"
    return out


def split_list(text: str) -> list[str]:
    """Top-level comma-separated items; any of ([{ opens and )]} closes a group.

    A trailing sentence after the list ("... vanilline. Sans gluten.") is dropped.
    """
    t = " ".join(text.split())
    depth = 0
    items: list[str] = []
    cur: list[str] = []
    for i, ch in enumerate(t):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        decimal_comma = 0 < i < len(t) - 1 and t[i - 1].isdigit() and t[i + 1].isdigit()
        if depth == 0 and ch == "," and not decimal_comma:
            items.append("".join(cur).strip())
            cur = []
            continue
        if depth == 0 and ch == "." and (i + 1 == len(t) or t[i + 1] == " "):
            break  # end of the list sentence
        cur.append(ch)
    if "".join(cur).strip():
        items.append("".join(cur).strip())
    if any(not it for it in items):
        raise RuleError("empty item in ingredient list")
    return items


def _list_item(text: str, sel: str) -> str:
    parts = split_list(text)
    if not sel.isdigit() or not 1 <= int(sel) <= len(parts):
        raise RuleError(f"no item {sel!r} in a list of {len(parts)}")
    return parts[int(sel) - 1]


def apply(rule: str, text: str) -> str:
    """The ``value_raw`` that ``rule`` (``name@version[:selector]``) reads from ``text``."""
    base, _, sel = rule.partition(":")
    if base == "quantity@1":
        t = " ".join(text.split())
        parse_raw(t)
        return t
    if base == "otc_contains@1":
        items = _otc_items(text)
        if sel not in items:
            raise RuleError(f"{sel!r} not stated (found {sorted(items)})")
        return items[sel]
    if base == "otc_calories_from@1":
        m = _CAL.fullmatch(" ".join(text.split()))
        if not m:
            raise RuleError("not an OTC 'contributes ... calories from' statement")
        return f"{m.group('n')} kcal"
    if base == "fdc_label_nutrient@1":
        if sel not in FDC_LABEL_UNITS:
            raise RuleError(f"no unit known for FDC label nutrient {sel!r}")
        parse_decimal(text)
        return f"{text} {FDC_LABEL_UNITS[sel]}"
    if base == "nfp_row@1":
        return nfp_row(sel, text)
    if base == "nfp_serving@1":
        return nfp_serving(text)
    if base == "fdc_serving@1":
        m = re.fullmatch(r"(?P<n>[0-9]+(?:\.[0-9]+)?) (?P<u>GRM|MLT)", text)
        if not m:
            raise RuleError(f"not an FDC serving size: {text!r}")
        return f"{m.group('n')} {'g' if m.group('u') == 'GRM' else 'ml'}"
    if base == "line_amount@1":
        lines = text.split("\n")
        if not sel.isdigit() or not 1 <= int(sel) <= len(lines):
            raise RuleError(f"no line {sel!r}")
        m = re.match(r"(?P<n>[0-9]+(?:\.[0-9]+)?) (?P<u>mg|g|mcg)\b", lines[int(sel) - 1])
        if not m:
            raise RuleError(f"line {sel} does not start with an amount")
        return f"{m.group('n')} {m.group('u')}"
    if base == "list_item@1":
        return _list_item(text, sel)
    if base == "ingredient_list@1":
        found = _PCT.findall(_list_item(text, sel))
        if len(found) != 1:
            raise RuleError(f"item {sel} states {len(found)} percentages")
        return f"{found[0]}%"
    raise RuleError(f"unknown rule {rule!r}")


def calories_from(text: str) -> list[str]:
    """The ingredients named in an ``otc_calories_from@1`` statement."""
    m = _CAL.fullmatch(" ".join(text.split()))
    if not m:
        raise RuleError("not an OTC 'contributes ... calories from' statement")
    return [p.strip() for p in re.split(r",|\band\b", m.group("from")) if p.strip()]
