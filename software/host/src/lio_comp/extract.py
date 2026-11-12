"""Locators for each source type (spec §4). Pure functions of identifiers.

Facts are then created by :class:`lio_comp.record.RecordBuilder`, which reads
each locator from the snapshot bytes and applies the named rule.
"""

from __future__ import annotations

from typing import Any

HL7 = {"v": "urn:hl7-org:v3"}


# --------------------------------------------------------------------- SPL XML
def spl_product(ndc_product_code: str) -> str:
    return (
        "/v:document/v:component/v:structuredBody/v:component/v:section/v:subject/"
        "v:manufacturedProduct/v:manufacturedProduct"
        f"[v:code/@code='{ndc_product_code}']"
    )


def spl_active_quantity(code: str, part: str) -> dict[str, Any]:
    """``part`` = numerator (amount of active per dose) or denominator (dose mass)."""
    return {
        "type": "xpath",
        "namespaces": HL7,
        "expr": f"{spl_product(code)}/v:ingredient[@classCode='ACTIB']/v:quantity/v:{part}",
        "fields": ["value", "unit"],
    }


def spl_ingredient(code: str, class_code: str, n: int, what: str) -> dict[str, Any]:
    """The n-th (from 1) ingredient of a class (ACTIB, IACT): its name or UNII."""
    base = f"{spl_product(code)}/v:ingredient[@classCode='{class_code}'][{n}]/v:ingredientSubstance"
    if what == "name":
        return {"type": "xpath", "namespaces": HL7, "expr": f"{base}/v:name"}
    return {"type": "xpath", "namespaces": HL7, "expr": f"{base}/v:code", "fields": ["code"]}


def spl_section_item(title: str, starts_with: str) -> dict[str, Any]:
    """A list item of the section with this exact title, by its opening words."""
    return {
        "type": "xpath",
        "namespaces": HL7,
        "expr": (
            f"//v:section[normalize-space(v:title)='{title}']/v:text/v:list/"
            f"v:item[starts-with(normalize-space(.), '{starts_with}')]"
        ),
    }


def spl_section_paragraph(title: str) -> dict[str, Any]:
    return {
        "type": "xpath",
        "namespaces": HL7,
        "expr": f"//v:section[normalize-space(v:title)='{title}']/v:text/v:paragraph",
    }


# ------------------------------------------------------------------- JSON APIs
def pointer(p: str, fields: list[str] | None = None) -> dict[str, Any]:
    loc: dict[str, Any] = {"type": "json_pointer", "pointer": p}
    if fields:
        loc["fields"] = fields
    return loc


def gsrs_first(field: str) -> dict[str, Any]:
    """GSRS search response, first hit: approvalID (UNII), _name, structure/formula."""
    return pointer(f"/content/0/{field}")


def fdc_label(nutrient: str) -> dict[str, Any]:
    return pointer(f"/labelNutrients/{nutrient}/value")


def dsld_row_quantity(row: int, q: int = 0) -> dict[str, Any]:
    return pointer(f"/ingredientRows/{row}/quantity/{q}", ["quantity", "unit"])


def off_nutrient(key: str) -> dict[str, Any]:
    return pointer("/product/nutriments", [f"{key}_100g", f"{key}_unit"])
