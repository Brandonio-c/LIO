"""Manufacturer product information from public databases.

Two sources, both free:

- **Open Food Facts** (worldwide, crowd-sourced from the packs: name, brand,
  ingredients, allergens, nutrition per 100 g, front-of-pack photo);
- **USDA FoodData Central, Branded Foods** (US products, from the
  manufacturers' own label data; nutrition per 100 g). Needs an api.data.gov
  key; ``DEMO_KEY`` works but is rate-limited.

Both answers are kept raw, and merged into one normalised record. USDA wins
where it knows the product (its data comes from the manufacturers, while Open
Food Facts names are crowd-sourced and sometimes wrong); Open Food Facts fills
the gaps (allergen tags, pack photo, Nutri-Score, NOVA group).

Also NIH DSLD (supplements), openFDA drug labels (by UPC, and by the NDC a
UPC starting with 3 can carry) and DailyMed. Every source is tried with every
barcode form (UPC-A, EAN-13, GTIN-14, UPC-E) and the matching form is logged
and kept in ``matched_forms``. Ingredient information is kept as ordered
``ingredient_parts``, each with the source field it came from. When an
evidence store is configured, every raw answer is stored by SHA-256.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .barcode import Gtin, Ndc, ndc_candidates

log = logging.getLogger(__name__)

# Normalised nutrition keys, per 100 g (or 100 ml for drinks), and their units.
NUTRIENTS: dict[str, tuple[str, str]] = {
    "energy_kcal": ("Energy", "kcal"),
    "energy_kj": ("Energy", "kJ"),
    "fat_g": ("Fat", "g"),
    "saturated_fat_g": ("  of which saturated", "g"),
    "trans_fat_g": ("  of which trans", "g"),
    "cholesterol_mg": ("Cholesterol", "mg"),
    "carbohydrates_g": ("Carbohydrate", "g"),
    "sugars_g": ("  of which sugars", "g"),
    "added_sugars_g": ("  of which added sugars", "g"),
    "fiber_g": ("Fibre", "g"),
    "protein_g": ("Protein", "g"),
    "salt_g": ("Salt", "g"),
    "sodium_mg": ("Sodium", "mg"),
    "alcohol_g": ("Alcohol", "g"),
}

# Open Food Facts nutriment name -> (our key, factor from OFF's per-100 g unit)
_OFF_NUTRIENTS = {
    "energy-kcal": ("energy_kcal", 1.0),
    "energy-kj": ("energy_kj", 1.0),
    "fat": ("fat_g", 1.0),
    "saturated-fat": ("saturated_fat_g", 1.0),
    "trans-fat": ("trans_fat_g", 1.0),
    "cholesterol": ("cholesterol_mg", 1000.0),  # OFF stores g
    "carbohydrates": ("carbohydrates_g", 1.0),
    "sugars": ("sugars_g", 1.0),
    "added-sugars": ("added_sugars_g", 1.0),
    "fiber": ("fiber_g", 1.0),
    "proteins": ("protein_g", 1.0),
    "salt": ("salt_g", 1.0),
    "sodium": ("sodium_mg", 1000.0),  # OFF stores g
    "alcohol": ("alcohol_g", 1.0),
}

# USDA nutrient number -> our key (Branded Foods values are per 100 g)
_USDA_NUTRIENTS = {
    "208": "energy_kcal",
    "268": "energy_kj",
    "204": "fat_g",
    "606": "saturated_fat_g",
    "605": "trans_fat_g",
    "601": "cholesterol_mg",
    "205": "carbohydrates_g",
    "269": "sugars_g",
    "539": "added_sugars_g",
    "291": "fiber_g",
    "203": "protein_g",
    "307": "sodium_mg",
    "221": "alcohol_g",
}

_OFF_FIELDS = (
    "code,product_name,product_name_en,generic_name,brands,brand_owner,quantity,serving_size,"
    "categories,categories_tags,ingredients_text,ingredients_text_en,allergens_tags,"
    "traces_tags,labels,additives_tags,nutriments,nutrition_data_per,nutriscore_grade,"
    "nova_group,countries,packaging,origins,manufacturing_places,image_front_url,image_url,"
    "product_quantity,product_quantity_unit,lang"
)


@dataclass
class LookupSettings:
    off_url: str = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
    usda_url: str = "https://api.nal.usda.gov/fdc/v1/foods/search"
    usda_api_key: str = "DEMO_KEY"
    dsld_url: str = "https://api.ods.od.nih.gov/dsld/v9"
    openfda_url: str = "https://api.fda.gov/drug/label.json"
    openfda_ndc_url: str = "https://api.fda.gov/drug/ndc.json"
    dailymed_url: str = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
    # SmartLabel (Label Insight) API: needs a key from Label Insight; empty = not used
    smartlabel_url: str = "https://enterprise-li-api.labelinsight.com/api/v4/{key}/data/upc/{upc}"
    smartlabel_key: str = ""
    user_agent: str = "LIO-V3-food-library/0.1"
    timeout_s: float = 10.0


@dataclass
class LookupResult:
    found: bool
    info: dict[str, Any]  # normalised (see :func:`empty_info`)
    raw: dict[str, Any]  # source name -> its raw answer (or error text)
    sources: list[str] = field(default_factory=list)  # sources that knew the product
    errors: dict[str, str] = field(default_factory=dict)  # source -> why it failed

    @property
    def source(self) -> str:
        return self.sources[0] if self.sources else "none"


def empty_info() -> dict[str, Any]:
    return {
        "name": "",
        "brand": "",
        "quantity": "",
        "serving_size": "",
        "categories": [],
        "ingredients_text": "",
        "allergens": [],
        "traces": [],
        "labels": [],
        "additives": [],
        "nutriscore": "",
        "nova_group": None,
        "countries": "",
        "packaging": "",
        "origins": "",
        "image_url": "",
        "nutrition_basis": "100 g",
        "nutrition_per_100g": {},
        "links": {},
        "ingredient_parts": [],
        "matched_forms": {},
    }


Fetch = Callable[[str, dict[str, str], float], Any]
# (url as recorded, bytes as received, media type) -> SHA-256, or None if not stored
Evidence = Callable[[str, bytes, str], "str | None"]


def part(role: str, text: str, source: str, origin: str, **extra: Any) -> dict[str, Any]:
    """One piece of a product's ingredient information, with the field it came from.

    Roles: active, inactive, other_information (drugs); dietary, other (supplements);
    food (a food's ingredient list); contains (allergen statement).
    """
    return {"role": role, "text": " ".join(str(text).split()), "source": source,
            "origin": origin, **extra}  # fmt: skip


def possibly_truncated(text: str) -> bool:
    """A list that stops without closing punctuation (and not on an allergen statement)."""
    t = text.strip()
    if not t:
        return False
    if re.search(r"[.)\]]\s*$", t):
        return False
    return not re.search(r"contains:?\s+[\w ,&/-]+$", t, re.I)


SUSPICIOUS_LENGTHS = (255, 256, 1000, 1024, 2000, 4000, 4096)


def truncation_flags(text: str, others: list[str] | None = None) -> list[str]:
    """Reasons an ingredient string may be cut short (plan WP3); shown to the operator."""
    t = text.strip()
    if not t:
        return []
    flags = []
    if possibly_truncated(t):
        flags.append("ends without closing punctuation (mid-word?)")
    if t.count("(") != t.count(")") or t.count("[") != t.count("]"):
        flags.append("unbalanced brackets")
    if len(text) in SUSPICIOUS_LENGTHS:
        flags.append(f"length is exactly {len(text)} characters (a common field limit)")
    longer = [o for o in others or [] if len(o.strip()) > len(t) * 1.1]
    if longer:
        flags.append(
            f"shorter than another transcription ({len(t)} vs {max(len(o) for o in longer)} characters)"
        )
    return flags


def flag_truncation(info: dict[str, Any]) -> None:
    """Add ``truncation_flags`` to free-text ingredient strings (FDC, Open Food Facts,
    SmartLabel). Structured lists (DSLD rows, SPL sections) are joined or sectioned by
    construction and are not checked. Lengths are compared within one language only."""
    parts = info.get("ingredient_parts") or []

    def lang(p: dict[str, Any]) -> str:
        return str(p.get("lang") or ("en" if p.get("source") in ("usda", "smartlabel") else ""))

    text_parts = [
        p
        for p in parts
        if p.get("role") == "food" and p.get("source") in ("usda", "openfoodfacts", "smartlabel")
    ]
    for p in parts:
        p.pop("truncation_flags", None)
    for p in text_parts:
        others = [x["text"] for x in text_parts if x is not p and lang(x) and lang(x) == lang(p)]
        flags = truncation_flags(p["text"], others)
        if (
            p.get("source") == "openfoodfacts"
        ):  # typed by contributors: an unpunctuated end is normal
            flags = [f for f in flags if not f.startswith("ends without")]
        if flags:
            p["truncation_flags"] = flags
    info["truncation_flags"] = sorted(
        {f"{p['origin']}: {f}" for p in parts for f in p.get("truncation_flags", [])}
    )


def _http_bytes(url: str, headers: dict[str, str], timeout: float) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = (r.headers.get("Content-Type") or "application/json").split(";")[0].strip()
        return r.read(), ctype


def redact(url: str) -> str:
    """The URL without API keys (as recorded in evidence and in the library)."""
    return re.sub(r"(api_key|key|token)=[^&]+", r"\1=REDACTED", url)


def _http_json(url: str, headers: dict[str, str], timeout: float) -> Any:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _tags(values: Any) -> list[str]:
    """``["en:milk", "fr:lait"]`` -> ``["milk", "lait"]``."""
    out = []
    for v in values or []:
        s = str(v).split(":", 1)[-1].replace("-", " ")
        if s and s not in out:
            out.append(s)
    return out


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, 4)


def parse_off(product: dict[str, Any], code: str) -> dict[str, Any]:
    info = empty_info()
    info["name"] = str(product.get("product_name_en") or product.get("product_name") or "")
    info["generic_name"] = str(product.get("generic_name") or "")
    info["brand"] = str(product.get("brands") or product.get("brand_owner") or "")
    info["quantity"] = str(product.get("quantity") or "")
    info["serving_size"] = str(product.get("serving_size") or "")
    cats = str(product.get("categories") or "")
    info["categories"] = [c.strip() for c in cats.split(",") if c.strip()]
    parts: list[dict[str, Any]] = []
    seen: set[str] = set()
    main = str(product.get("ingredients_text") or "").strip()
    if main:
        parts.append(part("food", main, "openfoodfacts", "openfoodfacts.ingredients_text",
                          lang=str(product.get("lang") or "")))  # fmt: skip
        seen.add(" ".join(main.split()).lower())
    for k in sorted(product):
        m = re.fullmatch(r"ingredients_text_([a-z]{2})", k)
        txt = str(product.get(k) or "").strip()
        if m and txt and " ".join(txt.split()).lower() not in seen:
            seen.add(" ".join(txt.split()).lower())
            parts.append(part("food", txt, "openfoodfacts", f"openfoodfacts.{k}", lang=m.group(1)))
    # The longest list: languages are often filled unevenly (one may be only
    # "sugar, palm oil"); the others stay in ingredient_parts with their origin.
    best = max(parts, key=lambda x: len(x["text"]), default=None)
    info["ingredients_text"] = best["text"] if best else ""
    info["ingredients_text_origin"] = best["origin"] if best else ""
    info["ingredient_parts"] = parts
    info["allergens"] = _tags(product.get("allergens_tags"))
    info["traces"] = _tags(product.get("traces_tags"))
    info["labels"] = [s.strip() for s in str(product.get("labels") or "").split(",") if s.strip()]
    info["additives"] = _tags(product.get("additives_tags"))
    info["nutriscore"] = str(product.get("nutriscore_grade") or "")
    nova = product.get("nova_group")
    info["nova_group"] = int(nova) if isinstance(nova, (int, float)) else None
    info["countries"] = str(product.get("countries") or "")
    info["packaging"] = str(product.get("packaging") or "")
    info["origins"] = str(product.get("origins") or product.get("manufacturing_places") or "")
    info["image_url"] = str(product.get("image_front_url") or product.get("image_url") or "")
    if str(product.get("nutrition_data_per") or "100g") not in ("100g", ""):
        info["nutrition_basis"] = "100 g (converted by Open Food Facts)"
    n = product.get("nutriments") or {}
    per: dict[str, float] = {}
    for off_key, (key, factor) in _OFF_NUTRIENTS.items():
        v = _num(n.get(f"{off_key}_100g"))
        if v is not None:
            per[key] = round(v * factor, 4)
    if "energy_kcal" not in per and "energy_kj" in per:
        per["energy_kcal"] = round(per["energy_kj"] / 4.184, 1)
    info["nutrition_per_100g"] = per
    info["links"] = {"openfoodfacts": f"https://world.openfoodfacts.org/product/{code}"}
    return info


def parse_usda(food: dict[str, Any]) -> dict[str, Any]:
    info = empty_info()
    info["name"] = str(food.get("description") or "").strip()
    info["brand"] = str(food.get("brandName") or food.get("brandOwner") or "").strip()
    info["brand_owner"] = str(food.get("brandOwner") or "")
    pkg = food.get("packageWeight")
    info["quantity"] = str(pkg or "")
    ss, unit = food.get("servingSize"), str(food.get("servingSizeUnit") or "")
    hh = str(food.get("householdServingFullText") or "")
    if ss:
        unit_txt = {"GRM": "g", "MLT": "ml"}.get(unit.upper(), unit.lower())
        info["serving_size"] = f"{ss:g} {unit_txt}" + (f" ({hh})" if hh else "")
    cat = str(food.get("brandedFoodCategory") or food.get("foodCategory") or "")
    info["categories"] = [cat] if cat else []
    info["ingredients_text"] = str(food.get("ingredients") or "")
    if info["ingredients_text"].strip():
        info["ingredients_text_origin"] = "usda.ingredients"
        info["ingredient_parts"] = [
            part(
                "food",
                info["ingredients_text"],
                "usda",
                "usda.ingredients",
                possibly_truncated=possibly_truncated(info["ingredients_text"]),
            )
        ]
    info["countries"] = str(food.get("marketCountry") or "")
    per: dict[str, float] = {}
    for nut in food.get("foodNutrients") or []:
        key = _USDA_NUTRIENTS.get(str(nut.get("nutrientNumber") or ""))
        v = _num(nut.get("value"))
        if key and v is not None:
            per[key] = v
    if "sodium_mg" in per:
        per["salt_g"] = round(per["sodium_mg"] * 2.5 / 1000.0, 3)
    info["nutrition_per_100g"] = per
    fdc = food.get("fdcId")
    if fdc:
        info["links"] = {"usda": f"https://fdc.nal.usda.gov/food-details/{fdc}/nutrients"}
    info["usda_fdc_id"] = fdc
    return info


def _dsld_amount(q: list[dict[str, Any]]) -> str:
    if not q:
        return ""
    a = q[0]
    unit = (
        str(a.get("unit") or "").replace("(s)", "").replace("Gram", "g").replace("Milligram", "mg")
    )
    unit = unit.replace("Microgram", "mcg").replace("Calorie", "kcal").strip()
    qty = a.get("quantity")
    return f"{qty:g} {unit}".strip() if isinstance(qty, (int, float)) else ""


def parse_dsld(label: dict[str, Any]) -> dict[str, Any]:
    """A label from the NIH Dietary Supplement Label Database (supplements)."""
    info = empty_info()
    info["name"] = str(label.get("fullName") or "")
    info["brand"] = str(label.get("brandName") or "")
    nc = label.get("netContents") or []
    info["quantity"] = ", ".join(str(n.get("display") or "") for n in nc if n.get("display"))
    ss = label.get("servingSizes") or []
    if ss:
        s0 = ss[0]
        qty = s0.get("minQuantity")
        info["serving_size"] = (
            f"{qty:g} {s0.get('unit', '')}".strip() if isinstance(qty, (int, float)) else ""
        )
    pt = label.get("productType") or {}
    if pt.get("langualCodeDescription"):
        info["categories"] = ["Dietary supplement", str(pt["langualCodeDescription"])]
    facts = []
    for row in label.get("ingredientRows") or []:
        amount = _dsld_amount(row.get("quantity") or [])
        facts.append({"name": str(row.get("name") or ""), "amount": amount})
    other = [
        str(i.get("name") or "")
        for i in (label.get("otheringredients") or {}).get("ingredients") or []
    ]
    other_text = str((label.get("otheringredients") or {}).get("text") or "")
    parts = []
    if facts:
        parts.append(
            ", ".join(f"{f['name']} ({f['amount']})" if f["amount"] else f["name"] for f in facts)
        )
    if other or other_text:
        parts.append("Other ingredients: " + (other_text or ", ".join(o for o in other if o)))
    info["ingredients_text"] = ". ".join(parts)
    info["ingredients_text_origin"] = "dsld.ingredientRows + dsld.otheringredients"
    ip = []
    if parts and facts:
        ip.append(part("dietary", parts[0], "dsld", "dsld.ingredientRows"))
    if other or other_text:
        ip.append(
            part(
                "other",
                other_text or ", ".join(o for o in other if o),
                "dsld",
                "dsld.otheringredients.text" if other_text else "dsld.otheringredients.ingredients",
            )
        )
    info["ingredient_parts"] = ip
    info["supplement_facts"] = facts
    info["other_ingredients"] = other
    info["statements"] = [
        {"type": str(st.get("type") or ""), "text": str(st.get("notes") or "")}
        for st in label.get("statements") or []
    ]
    lid = label.get("id")
    info["dsld_id"] = lid
    if lid:
        info["links"] = {"dsld": f"https://dsld.od.nih.gov/label/{lid}"}
    info["upc_on_label"] = str(label.get("upcSku") or "")
    return info


def parse_usda_detail(food: dict[str, Any]) -> dict[str, Any]:
    """USDA /food/{fdcId} (nested nutrient records) in the search-result shape."""
    flat = dict(food)
    flat["foodNutrients"] = [
        {
            "nutrientNumber": str((n.get("nutrient") or {}).get("number") or ""),
            "value": n.get("amount"),
        }
        for n in food.get("foodNutrients") or []
    ]
    return parse_usda(flat)


def _first(r: dict[str, Any], key: str) -> str:
    v = r.get(key) or []
    return str(v[0]).strip() if isinstance(v, list) and v else str(v or "").strip()


def parse_openfda(r: dict[str, Any]) -> dict[str, Any]:
    """An FDA drug label (over-the-counter products sold as drugs, e.g. fibre laxatives)."""
    info = empty_info()
    o = r.get("openfda") or {}
    brand = ", ".join(o.get("brand_name") or [])
    generic = ", ".join(o.get("generic_name") or [])
    info["name"] = (
        f"{brand} ({generic.lower()})"
        if brand and generic and generic.lower() != brand.lower()
        else brand or generic
    )
    info["brand"] = ", ".join(o.get("manufacturer_name") or [])
    info["categories"] = ["Over-the-counter drug"] + [str(x) for x in o.get("product_type") or []]
    # Every entry of every field is a part (an SPL can cover several variants, e.g.
    # "Inactive ingredients (Citrucel Orange)" and "(Citrucel Sugar Free)"). The summary
    # text uses the first variant only; the rest stay in ingredient_parts to choose from.
    ip: list[dict[str, Any]] = []
    for role, key in (("active", "active_ingredient"), ("inactive", "inactive_ingredient")):
        for i, x in enumerate(r.get(key) or []):
            if str(x).strip():
                ip.append(
                    part(role, str(x), "openfda", f"openfda.{key}[{i}]", variant=_variant(str(x)))
                )
    # "Other information": per-dose minerals ("each tablespoon contains: calcium 80 mg").
    # openFDA files it as other_information or spl_unclassified_section.
    for key in ("other_information", "spl_unclassified_section", "storage_and_handling"):
        for i, x in enumerate(r.get(key) or []):
            if re.search(r"\bcontains?\b|\bcontributes\b", str(x), re.I):
                ip.append(part("other_information", str(x), "openfda", f"openfda.{key}[{i}]",
                               variant=_variant(str(x))))  # fmt: skip
    variants = list(dict.fromkeys(p["variant"] for p in ip if p["variant"]))
    first = variants[0] if variants else ""
    summary = [p for p in ip if not p["variant"] or p["variant"] == first]
    summary = [p for p in summary if p["role"] != "active" or p["origin"].endswith("[0]")]
    info["ingredient_parts"] = ip
    info["ingredients_text"] = " | ".join(p["text"] for p in summary)
    info["ingredients_text_origin"] = " + ".join(p["origin"] for p in summary)
    if len(variants) > 1:
        info["variants"] = variants
    info["drug_facts"] = {
        k: _first(r, k)
        for k in ("active_ingredient", "inactive_ingredient", "purpose", "warnings",
                  "dosage_and_administration", "package_label_principal_display_panel")
        if _first(r, k)
    }  # fmt: skip
    sid = str(r.get("set_id") or "")
    info["openfda_set_id"] = sid
    if sid:
        info["links"] = {
            "dailymed": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={sid}"
        }
    return info


def _variant(text: str) -> str:
    """The product variant a Drug Facts section names, e.g. "Citrucel Orange" in
    "Inactive ingredients (Citrucel Orange) ..." ("" when none is named)."""
    m = re.match(r"\s*(?:active|inactive|other)\s+\w+(?:\s+\w+)?\s*\(([^()]{3,60})\)", text, re.I)
    if m and not re.match(r"in each|per ", m.group(1), re.I):
        return m.group(1).strip()
    return ""


def upc_spaced(gtin: Gtin) -> str:
    """UPC-A as printed under the bars, "3 00680 41830 1" (how DSLD stores it)."""
    c = gtin.gtin14[2:]
    return f"{c[0]} {c[1:6]} {c[6:11]} {c[11]}"


def merge(primary: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    """Fill the empty fields of ``primary`` from ``other`` (nutrients one by one)."""
    out = dict(primary)
    for k, v in other.items():
        if k in ("nutrition_per_100g", "links", "matched_forms"):
            out[k] = {**v, **primary.get(k, {})}
        elif k in ("ingredient_parts", "evidence"):
            have = {(x.get("origin"), x.get("text"), x.get("url")) for x in out.get(k) or []}
            out[k] = list(out.get(k) or []) + [
                x for x in v if (x.get("origin"), x.get("text"), x.get("url")) not in have
            ]
        elif out.get(k) in (None, "", [], {}):
            out[k] = v
    return out


def derived(per: dict[str, float]) -> dict[str, float]:
    """Composition the label implies, per 100 g (an estimate, clearly labelled).

    ``remainder_g`` is 100 g minus fat, carbohydrate, protein, salt and alcohol:
    mostly water, plus ash (and fibre where the label's carbohydrate excludes it).
    """
    parts = ("fat_g", "carbohydrates_g", "protein_g")
    if not all(p in per for p in parts):
        return {}
    solids = sum(per[p] for p in parts) + per.get("salt_g", 0.0) + per.get("alcohol_g", 0.0)
    return {"label_solids_g": round(solids, 2), "remainder_g": round(max(0.0, 100.0 - solids), 2)}


class Lookup:
    def __init__(
        self, settings: LookupSettings, fetch: Fetch | None = None, evidence: Evidence | None = None
    ) -> None:
        self.s = settings
        self._fetch = fetch
        self.evidence = evidence
        self._tl = threading.local()

    def _get(self, url: str) -> Any:
        """GET a JSON answer; with an evidence store, keep its exact bytes by SHA-256."""
        headers = {"User-Agent": self.s.user_agent}
        if self._fetch is not None:
            return self._fetch(url, headers, self.s.timeout_s)
        data, ctype = _http_bytes(url, headers, self.s.timeout_s)
        if self.evidence is not None:
            try:
                sha = self.evidence(redact(url), data, ctype)
            except OSError as e:
                log.warning("evidence store: %s", e)
                sha = None
            if sha:
                ev = getattr(self._tl, "evidence", None)
                if ev is not None:
                    ev.append({"url": redact(url), "sha256": sha, "media_type": ctype})
        return json.loads(data)

    def _matched(self, info: dict[str, Any], source: str, gtin: Gtin, form: str, code: str,
                 stored: str = "") -> None:  # fmt: skip
        info["matched_forms"] = {source: {"form": form, "code": code, "stored": stored}}
        log.info(
            "lookup %s %s: matched as %s %s (stored %r)", source, gtin.gtin14, form, code, stored
        )

    # ------------------------------------------------------------------ sources
    def openfoodfacts(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        last: Any = None
        for code in gtin.lookup_codes:
            url = self.s.off_url.format(code=urllib.parse.quote(code))
            try:
                data = self._get(url)
            except urllib.error.HTTPError as e:
                if e.code != 404:  # 404 = product not found under this code
                    raise
                data = {"status": 0, "code": code, "status_verbose": "product not found"}
            last = data
            if isinstance(data, dict) and data.get("status") == 1 and data.get("product"):
                info = parse_off(data["product"], code)
                self._matched(info, "openfoodfacts", gtin, gtin.form_of(code) or "as scanned",
                              code, str(data.get("code") or ""))  # fmt: skip
                return info, data
        return None, last

    def usda(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        """FDC Branded Foods files gtinUpc in whatever form the brand sent (12, 13 or 14
        digits), and its search matches the text: try every form."""
        if not self.s.usda_api_key:
            return None, "no API key configured"
        tried: dict[str, Any] = {}
        for form in ("GTIN-14", "UPC-A", "EAN-13", "UPC-E", "EAN-8"):
            code = gtin.forms.get(form)
            if not code:
                continue
            q = urllib.parse.urlencode(
                {
                    "query": code,
                    "dataType": "Branded",
                    "pageSize": 10,
                    "api_key": self.s.usda_api_key,
                }
            )
            data = self._get(f"{self.s.usda_url}?{q}")
            foods = data.get("foods") if isinstance(data, dict) else None
            tried[form] = data.get("totalHits") if isinstance(data, dict) else None
            for food in foods or []:
                if gtin.matches(str(food.get("gtinUpc") or "")):
                    info = parse_usda(food)
                    self._matched(info, "usda", gtin, form, code, str(food.get("gtinUpc") or ""))
                    return info, food
        return None, {"totalHits_by_form": tried}

    def dsld(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        """DSLD keeps upcSku as printed ("7 02669 93439 8", "5 453003 821090"): search the
        spaced forms, then the plain digits; confirm each hit by its stored UPC."""
        queries: list[tuple[str, str]] = []
        if "UPC-A" in gtin.forms:
            queries.append(("UPC-A spaced", f'"{upc_spaced(gtin)}"'))
        e = gtin.forms["EAN-13"]
        queries.append(("EAN-13 spaced", f'"{e[0]} {e[1:7]} {e[7:]}"'))
        queries += [(f, gtin.forms[f]) for f in ("UPC-A", "EAN-13") if f in gtin.forms]
        checked: set[str] = set()
        for form, q in queries:
            data = self._get(f"{self.s.dsld_url}/search-filter?q={urllib.parse.quote(q)}&size=5")
            hits = data.get("hits") if isinstance(data, dict) else None
            for h in (hits or [])[:3]:
                lid = str(h.get("_id"))
                if lid in checked:
                    continue
                checked.add(lid)
                label = self._get(f"{self.s.dsld_url}/label/{urllib.parse.quote(lid)}")
                if isinstance(label, dict) and gtin.matches(str(label.get("upcSku") or "")):
                    info = parse_dsld(label)
                    self._matched(
                        info, "dsld", gtin, form, q.strip('"'), str(label.get("upcSku") or "")
                    )
                    return info, label
        return None, {"count": 0, "labels_checked": sorted(checked)}

    def openfda(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        codes = " ".join(f'"{c}"' for c in dict.fromkeys([*gtin.forms.values(), gtin.code]))
        q = urllib.parse.quote(f"openfda.upc:({codes})")
        try:
            data = self._get(f"{self.s.openfda_url}?search={q}&limit=1")
        except urllib.error.HTTPError as e:
            if e.code == 404:  # openFDA answers "no matches" with 404
                return None, {"results": []}
            raise
        res = data.get("results") if isinstance(data, dict) else None
        if not res:
            return None, data
        info = parse_openfda(res[0])
        stored = [u for u in (res[0].get("openfda") or {}).get("upc") or [] if gtin.matches(u)]
        st = stored[0] if stored else ""
        self._matched(info, "openfda", gtin, gtin.form_of(st) or "?", st, st)
        return info, res[0]

    def _openfda_label(self, search: str) -> dict[str, Any] | None:
        try:
            data = self._get(f"{self.s.openfda_url}?search={urllib.parse.quote(search)}&limit=1")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        res = data.get("results") if isinstance(data, dict) else None
        return res[0] if res else None

    def ndc(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        """A UPC starting with 3 can carry the drug's NDC. Try each 10-digit split (4-4-2,
        5-3-2, 5-4-1): an openFDA label by package NDC, then by product NDC, then DailyMed
        by NDC. The NDC in a barcode can be out of date (relabelled products keep their
        UPC), so the result is marked as a lead for the user to confirm."""
        cands = ndc_candidates(gtin)
        if not cands:
            return None, "not an NDC barcode (UPC-A does not start with 3)"
        tried: list[str] = []
        for c in cands:
            for field_, value in (
                ("openfda.package_ndc", c.ndc),
                ("openfda.product_ndc", c.product),
            ):
                tried.append(f"{field_}:{value}")
                r = self._openfda_label(f'{field_}:"{value}"')
                if r is not None:
                    return self._ndc_hit(gtin, c, r, f"openFDA label by {field_}"), r
            tried.append(f"dailymed ndc={c.ndc}")
            try:
                d = self._get(f"{self.s.dailymed_url}/spls.json?ndc={urllib.parse.quote(c.ndc)}")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                raise
            for spl in (d.get("data") if isinstance(d, dict) else None) or []:
                r = self._openfda_label(f'set_id:"{spl.get("setid")}"')
                if r is not None:
                    return self._ndc_hit(gtin, c, r, "DailyMed by NDC"), r
        return None, {"ndc_tried": tried}

    def _ndc_hit(self, gtin: Gtin, c: Ndc, r: dict[str, Any], via: str) -> dict[str, Any]:
        info = parse_openfda(r)
        info["ndc_match"] = {
            "pattern": c.pattern,
            "ndc": c.ndc,
            "ndc11": c.ndc11,
            "via": via,
            "note": "NDC decoded from the barcode; confirm it is this product",
        }
        self._matched(info, "ndc", gtin, f"NDC {c.pattern}", c.ndc, c.ndc)
        return info

    def crosswalk(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        """An operator-attested barcode -> NDC -> SPL link (plan WP1): the exact label."""
        from .drugid import DrugResolver

        link = DrugResolver(self).link_for(gtin.gtin14)
        if link is None:
            return None, "no attested link"
        r = self._openfda_label(f'set_id:"{link["setid"]}"')
        info = parse_openfda(r) if r is not None else empty_info()
        info["drug_link"] = {k: link[k] for k in ("ndc", "ndc11", "setid", "spl_version", "method")}
        info["drug_link"]["operator"] = link["attestation"]["operator"]
        info["links"] = {**info.get("links", {}),
                         "dailymed": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={link['setid']}"}  # fmt: skip
        self._matched(
            info, "crosswalk", gtin, f"printed NDC {link['ndc']}", link["ndc"], link["ndc"]
        )
        return info, link

    def get_bytes(self, url: str) -> bytes:
        """Raw bytes (e.g. an SPL XML), stored as evidence like every JSON answer."""
        headers = {"User-Agent": self.s.user_agent}
        if self._fetch is not None:
            got = self._fetch(url, headers, self.s.timeout_s)
            return got if isinstance(got, bytes) else str(got).encode()
        data, ctype = _http_bytes(url, headers, self.s.timeout_s)
        if self.evidence is not None:
            self.evidence(redact(url), data, ctype)
        return data

    def smartlabel(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        """SmartLabel (Label Insight) API, only with a key (it has no public access)."""
        if not self.s.smartlabel_key:
            return None, "no SmartLabel API key configured"
        upc = gtin.forms.get("UPC-A") or gtin.forms["EAN-13"]
        url = self.s.smartlabel_url.format(key=urllib.parse.quote(self.s.smartlabel_key), upc=upc)
        data = self._get(url)
        content = data.get("content") if isinstance(data, dict) else None
        items = content if isinstance(content, list) else ([data] if isinstance(data, dict) else [])
        for it in items:
            text = str(it.get("ingredients") or it.get("ingredientStatement") or "")
            if text.strip():
                info = empty_info()
                info["name"] = str(it.get("productName") or it.get("name") or "")
                info["brand"] = str(it.get("brandName") or "")
                info["ingredients_text"] = text
                info["ingredients_text_origin"] = "smartlabel.ingredients"
                info["ingredient_parts"] = [
                    part("food", text, "smartlabel", "smartlabel.ingredients")
                ]
                self._matched(
                    info, "smartlabel", gtin, "UPC-A" if "UPC-A" in gtin.forms else "EAN-13", upc
                )
                return info, data
        return None, data

    def gs1_resolver(self, gtin: Gtin) -> list[dict[str, str]]:
        """Pages the brand registered with GS1 Digital Link (id.gs1.org), if any."""
        try:
            data = self._get(f"https://id.gs1.org/01/{gtin.gtin14}?linkType=all")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return []
        links: list[dict[str, str]] = []
        for ls in (data.get("linkset") if isinstance(data, dict) else None) or []:
            for k, v in ls.items():
                if isinstance(v, list):
                    links += [{"url": str(x.get("href")), "title": str(x.get("title") or k)}
                              for x in v if isinstance(x, dict) and x.get("href")]  # fmt: skip
        return links

    def _openfda_by_name(self, query: str, limit: int) -> list[dict[str, Any]]:
        words = sorted(
            {w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 3},
            key=len,
            reverse=True,
        )
        for w in words:  # openFDA ORs spaces: search one distinctive word at a time
            q = urllib.parse.quote(f"openfda.brand_name:{w}")
            try:
                data = self._get(f"{self.s.openfda_url}?search={q}&limit={limit}")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                raise
            res = data.get("results") or []
            if res:
                out = []
                for r in res:
                    info = parse_openfda(r)
                    out.append(
                        {
                            "source": "openfda",
                            "id": info["openfda_set_id"],
                            "name": info["name"],
                            "brand": info["brand"],
                            "detail": _first(r, "package_label_principal_display_panel")[:90],
                            "barcode": "",
                            "ingredients": info["ingredients_text"][:600],
                            "link": info["links"].get("dailymed", ""),
                        }
                    )
                return out
        return []

    def _dailymed_by_name(self, query: str, limit: int, have: set[str]) -> list[dict[str, Any]]:
        """DailyMed SPLs by drug name (e.g. a product whose UPC carries a retired NDC)."""
        words = sorted({w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 3},
                       key=len, reverse=True)  # fmt: skip
        if not words:
            return []
        q = urllib.parse.urlencode({"drug_name": words[0], "pagesize": limit})
        d = self._get(f"{self.s.dailymed_url}/spls.json?{q}")
        out = []
        for spl in (d.get("data") if isinstance(d, dict) else None) or []:
            sid = str(spl.get("setid") or "")
            if not sid or sid in have:
                continue
            out.append({
                "source": "openfda", "id": sid, "name": str(spl.get("title") or ""), "brand": "",
                "detail": f"DailyMed SPL, published {spl.get('published_date', '')}",
                "barcode": "", "ingredients": "",
                "link": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={sid}",
            })  # fmt: skip
        return out

    def search_by_name(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """Candidate labels by name (USDA Branded Foods and DSLD), for the user to pick."""
        out: list[dict[str, Any]] = []
        errors: list[str] = []
        if self.s.usda_api_key:
            q = urllib.parse.urlencode(
                {
                    "query": query,
                    "dataType": "Branded",
                    "pageSize": limit,
                    "api_key": self.s.usda_api_key,
                }
            )
            try:
                data = self._get(f"{self.s.usda_url}?{q}")
                for f in data.get("foods") or []:
                    out.append(
                        {
                            "source": "usda",
                            "id": str(f.get("fdcId")),
                            "name": str(f.get("description") or ""),
                            "brand": str(f.get("brandName") or f.get("brandOwner") or ""),
                            "detail": str(
                                f.get("packageWeight") or f.get("brandedFoodCategory") or ""
                            ),
                            "barcode": str(f.get("gtinUpc") or ""),
                            "ingredients": str(f.get("ingredients") or "")[:600],
                            "link": f"https://fdc.nal.usda.gov/food-details/{f.get('fdcId')}/nutrients",
                        }
                    )
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                errors.append(f"USDA: {e}")
        try:
            data = self._get(
                f"{self.s.dsld_url}/search-filter?q={urllib.parse.quote(query)}&size={limit}"
            )
            for h in data.get("hits") or []:
                src = h.get("_source") or {}
                ingr = ", ".join(str(i.get("name") or "") for i in src.get("allIngredients") or [])
                nc = src.get("netContents") or []
                out.append(
                    {
                        "source": "dsld",
                        "id": str(h.get("_id")),
                        "name": str(src.get("fullName") or ""),
                        "brand": str(src.get("brandName") or ""),
                        "detail": str(nc[0].get("display") if nc else ""),
                        "barcode": "",
                        "ingredients": ingr[:600],
                        "off_market": bool(src.get("offMarket")),
                        "link": f"https://dsld.od.nih.gov/label/{h.get('_id')}",
                    }
                )
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            errors.append(f"DSLD: {e}")
        try:
            out.extend(self._openfda_by_name(query, limit))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            errors.append(f"openFDA: {e}")
        try:
            out.extend(self._dailymed_by_name(query, limit, {c["id"] for c in out}))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            errors.append(f"DailyMed: {e}")
        if not out and errors:
            raise ValueError("; ".join(errors))
        words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 1]

        def score(c: dict[str, Any]) -> float:
            hay = f"{c['name']} {c['brand']}".lower()
            hit = sum(1 for w in words if w in hay)
            return hit / max(1, len(words)) - (0.2 if c.get("off_market") else 0.0)

        out.sort(key=score, reverse=True)
        # Keep only records with the query's most distinctive word (the longest, e.g.
        # "citrucel" in "citrucel orange"): common words like "orange" alone match
        # hundreds of unrelated products.
        if words:
            key = max(words, key=len)
            keep = [c for c in out if key in f"{c['name']} {c['brand']}".lower()]
            if keep:
                out = keep
        return out[: max(limit, 8)]

    def fetch(self, source: str, ident: str) -> tuple[dict[str, Any], Any]:
        """The full record of a candidate picked from :meth:`search_by_name`."""
        if source != "openfda" and not ident.isdigit():
            raise ValueError("bad record id")
        if source == "usda":
            q = urllib.parse.urlencode({"api_key": self.s.usda_api_key})
            food = self._get(f"https://api.nal.usda.gov/fdc/v1/food/{ident}?{q}")
            return parse_usda_detail(food), food
        if source == "dsld":
            label = self._get(f"{self.s.dsld_url}/label/{ident}")
            return parse_dsld(label), label
        if source == "openfda":
            if not re.fullmatch(r"[0-9a-f-]{36}", ident):
                raise ValueError("bad label id")
            data = self._get(f"{self.s.openfda_url}?search=set_id:%22{ident}%22&limit=1")
            r = (data.get("results") or [None])[0]
            if r is None:
                raise ValueError("label not found")
            return parse_openfda(r), r
        raise ValueError(f"unknown source {source!r}")

    def lookup(self, gtin: Gtin) -> LookupResult:
        raw: dict[str, Any] = {}
        errors: dict[str, str] = {}
        infos: list[tuple[str, dict[str, Any]]] = []
        self._tl.evidence = []
        for name, fn in (
            ("crosswalk", self.crosswalk),
            ("usda", self.usda),
            ("dsld", self.dsld),
            ("openfda", self.openfda),
            ("ndc", self.ndc),
            ("smartlabel", self.smartlabel),
            ("openfoodfacts", self.openfoodfacts),
        ):
            if name in ("openfda", "ndc") and any(n == "crosswalk" for n, _ in infos):
                continue  # an operator-attested link already names the exact label
            if name == "ndc" and any(n == "openfda" for n, _ in infos):
                continue  # the drug label was already found by its UPC
            try:
                info, answer = fn(gtin)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                errors[name] = f"{type(e).__name__}: {getattr(e, 'reason', e)}"
                log.warning("lookup %s %s: %s", name, gtin.code, errors[name])
                continue
            raw[name] = answer
            if info is not None:
                infos.append((name, info))
        merged = empty_info()
        if infos:
            merged = infos[0][1]
            for _, info in infos[1:]:
                merged = merge(merged, info)
        if ndc_candidates(gtin) and not any(n == "crosswalk" for n, _ in infos):
            try:
                from .drugid import DrugResolver

                merged["drug_resolution"] = DrugResolver(self).resolve(gtin)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                errors["drug_resolution"] = f"{type(e).__name__}: {e}"
        flag_truncation(merged)
        merged["evidence"] = list(self._tl.evidence)
        self._tl.evidence = None
        merged["derived_per_100g"] = derived(merged.get("nutrition_per_100g", {}))
        merged["looked_up_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        return LookupResult(bool(infos), merged, raw, [n for n, _ in infos], errors)
