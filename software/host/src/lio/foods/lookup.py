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
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .barcode import Gtin

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
    }


Fetch = Callable[[str, dict[str, str], float], Any]


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
    info["ingredients_text"] = str(
        product.get("ingredients_text_en") or product.get("ingredients_text") or ""
    )
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
    active, inactive = _first(r, "active_ingredient"), _first(r, "inactive_ingredient")
    parts = [p for p in (active, inactive) if p]
    info["ingredients_text"] = " | ".join(parts)
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


def upc_spaced(gtin: Gtin) -> str:
    """UPC-A as printed under the bars, "3 00680 41830 1" (how DSLD stores it)."""
    c = gtin.gtin14[2:]
    return f"{c[0]} {c[1:6]} {c[6:11]} {c[11]}"


def merge(primary: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    """Fill the empty fields of ``primary`` from ``other`` (nutrients one by one)."""
    out = dict(primary)
    for k, v in other.items():
        if k in ("nutrition_per_100g", "links"):
            out[k] = {**v, **primary.get(k, {})}
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
    def __init__(self, settings: LookupSettings, fetch: Fetch | None = None) -> None:
        self.s = settings
        self._fetch = fetch or _http_json

    def _get(self, url: str) -> Any:
        return self._fetch(url, {"User-Agent": self.s.user_agent}, self.s.timeout_s)

    def openfoodfacts(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        last: Any = None
        for code in gtin.lookup_codes:
            url = self.s.off_url.format(code=urllib.parse.quote(code)) + "?fields=" + _OFF_FIELDS
            try:
                data = self._get(url)
            except urllib.error.HTTPError as e:
                if e.code != 404:  # 404 = product not found under this code
                    raise
                data = {"status": 0, "code": code, "status_verbose": "product not found"}
            last = data
            if isinstance(data, dict) and data.get("status") == 1 and data.get("product"):
                return parse_off(data["product"], code), data
        return None, last

    def usda(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        if not self.s.usda_api_key:
            return None, "no API key configured"
        q = urllib.parse.urlencode(
            {
                "query": gtin.gtin14,
                "dataType": "Branded",
                "pageSize": 5,
                "api_key": self.s.usda_api_key,
            }
        )
        data = self._get(f"{self.s.usda_url}?{q}")
        foods = data.get("foods") if isinstance(data, dict) else None
        for food in foods or []:
            if str(food.get("gtinUpc") or "").zfill(14) == gtin.gtin14:
                return parse_usda(food), food
        return None, {"totalHits": data.get("totalHits") if isinstance(data, dict) else None}

    def dsld(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        if not gtin.gtin14.startswith("00"):
            return None, "not a US/Canada UPC"
        q = urllib.parse.quote(f'"{upc_spaced(gtin)}"')
        data = self._get(f"{self.s.dsld_url}/search-filter?q={q}&size=5")
        hits = data.get("hits") if isinstance(data, dict) else None
        if not hits:
            return None, {"count": 0}
        label = self._get(f"{self.s.dsld_url}/label/{urllib.parse.quote(str(hits[0]['_id']))}")
        if not isinstance(label, dict):
            return None, label
        return parse_dsld(label), label

    def openfda(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        codes = " ".join(
            f'"{c}"' for c in dict.fromkeys([gtin.code, gtin.gtin14[1:], gtin.gtin14.lstrip("0")])
        )
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
        return parse_openfda(res[0]), res[0]

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
        for name, fn in (
            ("usda", self.usda),
            ("dsld", self.dsld),
            ("openfda", self.openfda),
            ("openfoodfacts", self.openfoodfacts),
        ):
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
        merged["derived_per_100g"] = derived(merged.get("nutrition_per_100g", {}))
        merged["looked_up_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        return LookupResult(bool(infos), merged, raw, [n for n, _ in infos], errors)
