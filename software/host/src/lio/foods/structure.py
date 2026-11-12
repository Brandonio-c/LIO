"""Structured ingredient tables from label records and label text.

A record picked in "Find the ingredients online" (an FDA drug label, a DSLD
supplement label, a USDA branded food) or a web-page section is turned into rows:

    name, role, amount, basis, dv, form, sub, variant, note

Whatever the source does not state is ``"N/A"``: an amount is never guessed. The
extraction is deterministic (regular expressions, the ``list_item@2`` splitter and
the DSLD record's own fields), and the result is only a proposal. The operator
reviews and edits the table before it is saved, and nothing here is a verified fact
(see ``docs/COMPOSITION_VERIFICATION.md`` for that path).
"""

from __future__ import annotations

import re
from typing import Any

from lio_verify import textrules

NA = "N/A"
FIELDS = ("name", "role", "amount", "basis", "dv", "form", "sub", "variant", "note")
ROLES = ("active", "inactive", "dietary", "other", "ingredient")
CONTAINS_FIELDS = ("name", "amount", "basis", "variant", "note")
MAX_ROWS = 400
MAX_LEN = 600

_HEAD = re.compile(
    r"^\s*(?:drug\s+facts\s*:?\s*)?(?:(?:section\s+)?)(?:otc[\s-]+)?(?P<h>active\s+ingredients?|inactive\s+ingredients?|other\s+ingredients?|"
    r"ingredients?|other\s+information)\b\s*(?P<paren>\([^()]*\))?\s*[:.\-]?\s*",
    re.I,
)
_UNIT = r"mg|mcg|µg|gr|g|iu|ml|(?:usp\s+)?units?|%"
# Homeopathic potencies (HPUS): 6X, 30C, 200CK, 1LM. A dilution, not an amount.
_POT = re.compile(r"\b(?P<p>\d+(?:\.\d+)?\s?(?:X|C|CK|CH|DH|LM|x))\b(?!\s*(?:mg|g|ml|%))")
_STD = re.compile(r"[,\s]*\b(USP|HPUS|NF)\b\.?", re.I)
_DOSE_FORM = re.compile(
    r"\s+(?:(?:delayed|extended|immediate)[- ]release\s+)?(?:tablets?|caplets?|capsules?|"
    r"softgels?|gelcaps?|lozenges?|chewables?)\s*$",
    re.I,
)
_LEAD_BASIS = re.compile(r"^\s*\(\s*(?:in\s+)?(?:each|per)\s+(?P<d>[^()]{1,40})\)\s*:?\s*", re.I)
_LEAD_CONTAINS = re.compile(
    r"^\s*(?:each\s+(?P<a>[a-z0-9 .()]{1,30}?)|(?P<b>\d+(?:\.\d+)?\s*(?:ml|g)))"
    r"\s+contains?\s*:?\s*",
    re.I,
)
_AMT = re.compile(
    rf"(?P<n>\d+(?:[.,]\d+)?)\s*(?P<u>{_UNIT})(?![a-z])\.?(?P<paren>\s*\([^()]*\))?\*?", re.I
)
_EACH = re.compile(
    r"each\s+(?P<dose>[a-z][a-z ]{1,40}?)\s+contains?\s*:?\s*(?P<items>.*?)"
    r"(?=\s*(?:•|;|\beach\b|\bstore\b|\bkeep\b|\bprotect\b|$)|\.(?:\s|$))",
    re.I,
)
_ITEM = re.compile(r"(?P<name>[a-z][a-z ]*?)\s*(?P<n>\d+(?:\.\d+)?)\s*(?P<u>mg|mcg|g)\b", re.I)
_CAL = re.compile(
    r"each\s+(?P<dose>[a-z][a-z ]{1,40}?)\s+contributes\s+(?P<n>\d+(?:\.\d+)?)\s+calories?"
    r"(?:\s+from\s+(?P<from>[a-z][a-z ,]*?))?(?=\s*(?:•|;|\.|\bstore\b|\bkeep\b|\beach\b|$))",
    re.I,
)
_LESS = re.compile(
    r"^\s*(?:and\s+)?(?:contains\s+)?(?P<pct>less\s+than\s+\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*%\s*or\s+less)"
    r"\s*(?:of)?\s*:?\s*(?:the\s+following\s*:?)?\s*",
    re.I,
)
_PCT_LEAD = re.compile(r"^\s*(?P<n>\d+(?:[.,]\d+)?)\s*%\s+(?=[A-Za-z])")  # "100% blueberries"
_PCT_IN = re.compile(r"\s*\(?\s*(?P<n>\d+(?:[.,]\d+)?)\s*%\s*\)?\s*$")
_UNII = re.compile(r"\(?\s*UNII\s*:\s*(?P<u>[A-Z0-9]{10})\s*\)?", re.I)


def _s(v: Any) -> str:
    return " ".join(str(v if v is not None else "").split())


def row(**kw: Any) -> dict[str, str]:
    out = {k: _s(kw.get(k)) or NA for k in FIELDS}
    out["role"] = kw.get("role") or "ingredient"
    return out


def contains_row(**kw: Any) -> dict[str, str]:
    return {k: _s(kw.get(k)) or NA for k in CONTAINS_FIELDS}


def _basis(paren: str) -> str:
    """'(in each heaping tablespoon)' -> 'per heaping tablespoon'."""
    t = _s(paren).strip("() ")
    m = re.match(r"(?:in\s+)?each\s+(.+)|per\s+(.+)", t, re.I)
    if m:
        return f"per {(m.group(1) or m.group(2)).strip()}"
    return ""


def _split_desc(name: str) -> tuple[str, str]:
    """'Methylcellulose (a fiber)' -> ('Methylcellulose', 'a fiber')."""
    m = re.fullmatch(r"(?P<n>.*?)\s*\((?P<d>[^()]*)\)\s*", name)
    if m and m.group("n").strip():
        return m.group("n").strip(), m.group("d").strip()
    return name.strip(), ""


def _strip_prefix(name: str, prefixes: list[str]) -> str:
    for p in sorted((p for p in prefixes if p), key=len, reverse=True):
        if name.lower().startswith(p.lower() + " ") and len(name) > len(p) + 1:
            return name[len(p) :].strip()
    return name


def _amount(n: str, u: str) -> str:
    n = re.sub(r",(?=\d{3}(?!\d))", "", n)  # "10,000 units": a thousands separator
    u = u.lower().replace("µg", "mcg")
    u = {"iu": "IU", "ml": "mL"}.get(u, u)
    return f"{n.replace(',', '.')}{'' if u == '%' else ' '}{u}"


def heading(text: str) -> tuple[str, str, str, str]:
    """Split a section into (kind, basis, variant, body); kind is '' when unlabelled.

    Drug Facts tables come with dot leaders and a repeated heading ("ACTIVE INGREDIENT
    Active Ingredient ........ Purpose Menthol 5% ........ Topical analgesic"): the
    leaders and the second heading (with its "Purpose" column title) are dropped."""
    text = re.sub(r"\.{3,}|…+", " ", text)
    m = _HEAD.match(text)
    if not m:
        return "", "", "", text.strip()
    rest = text[m.end() :]
    again = _HEAD.match(rest)
    if again and again.group("h").lower().split()[0] == m.group("h").lower().split()[0]:
        paren = m.group("paren") or again.group("paren") or ""
        rest = rest[again.end() :]
    else:
        paren = m.group("paren") or ""
    rest = re.sub(r"^\s*purposes?\b\s*:?\s*", "", rest, flags=re.I)
    # "(in each drop)" or "Each 5 mL contains:" opening an active-ingredient body
    if m.group("h").lower().startswith("active") and not paren:
        mb = _LEAD_BASIS.match(rest)
        mc = None if mb else _LEAD_CONTAINS.match(rest)
        if mb:
            paren, rest = f"(per {mb.group('d')})", rest[mb.end() :]
        elif mc:
            paren, rest = f"(per {mc.group('a') or mc.group('b')})", rest[mc.end() :]
    kind = re.sub(r"\s+", " ", m.group("h").lower()).rstrip("s")
    kind = {
        "active ingredient": "active",
        "inactive ingredient": "inactive",
        "other ingredient": "other",
        "ingredient": "ingredient",
        "other information": "info",
    }.get(kind, kind)
    basis = _basis(paren)
    variant = "" if basis or not paren else _s(paren).strip("() ")
    return kind, basis, variant, rest.strip()


# Purposes from the OTC monographs, for labels whose Purpose section is missing or wrong
# ("Mineral oil 14% ..... Protectant Petrolatum 74.9%").
PURPOSE_WORDS = (
    "protectant", "skin protectant", "analgesic", "topical analgesic", "external analgesic",
    "local anesthetic", "anesthetic", "antiseptic", "astringent", "vasoconstrictor",
    "antihistamine", "nasal decongestant", "decongestant", "expectorant", "cough suppressant",
    "pain reliever", "fever reducer", "pain reliever/fever reducer", "sunscreen",
    "antiperspirant", "antifungal", "antacid", "laxative", "stool softener", "antidiarrheal",
    "anti-itch", "antibacterial", "antimicrobial", "first aid antibiotic", "anticavity",
    "antigingivitis", "antiplaque", "acne treatment", "acne medication", "sleep aid",
    "nighttime sleep aid", "anti-dandruff", "antidandruff", "keratolytic", "hair regrowth",
    "smoking cessation aid", "stop smoking aid", "acid reducer", "antiemetic", "counterirritant",
)  # fmt: skip


def _clean_name(name: str) -> tuple[str, str]:
    """Drop 'USP'/'HPUS' and a trailing dosage form ('delayed-release tablet') from an
    active's name; the standard goes to the note."""
    std = sorted({m.group(1).upper() for m in _STD.finditer(name)})
    n = _STD.sub(" ", name)
    n2 = _DOSE_FORM.sub("", n)
    n = n2 if n2.strip(" ,;:-") else n
    n = re.sub(r"^\s*(?:and|&)\s+", "", n, flags=re.I)
    return _s(n).strip(" ,;:-•*."), ", ".join(std)


def _homeopathic(body: str, basis: str, variant: str) -> list[dict[str, str]]:
    """'Belladonna 12X, Calcarea Carbonica 6X, 30X 8.33%' -> one row per substance, the
    potencies as the amount (an HPUS dilution) and any percentage in the note."""
    items: list[dict[str, Any]] = []
    pos = 0
    for m in _POT.finditer(body):
        seg = body[pos : m.start()]
        pos = m.end()
        pct = re.match(r"^\s*[,;]?\s*(\d+(?:\.\d+)?)\s*%", seg)
        if pct:
            if items:
                items[-1]["pct"] = pct.group(1)
            seg = seg[pct.end() :]
        name, std = _clean_name(re.sub(r"\*+", "", seg))
        pot = m.group("p").replace(" ", "").upper()
        if not name and items:
            items[-1]["pots"].append(pot)
            continue
        items.append({"name": name, "pots": [pot], "pct": "", "std": std})
    tail = re.match(r"^\s*[,;]?\s*(\d+(?:\.\d+)?)\s*%", body[pos:])
    if tail and items:
        items[-1]["pct"] = tail.group(1)
    out = []
    for it in items:
        notes = [x for x in (f"{it['pct']}% of the mixture" if it["pct"] else "", it["std"]) if x]
        out.append(
            row(name=it["name"], role="active", amount=", ".join(it["pots"]),
                basis=basis or "HPUS potency", variant=variant, note="; ".join(notes))
        )  # fmt: skip
    return out


def actives(
    body: str,
    basis: str,
    variant: str,
    prefixes: list[str],
    purposes: list[str] | None = None,
    generic: str = "",
) -> list[dict[str, str]]:
    """Active ingredients with strengths: 'Methylcellulose (a non-allergenic fiber) 500mg'.

    Text between one strength and the next ingredient is that ingredient's purpose when
    it matches the label's Purpose section (or is the only thing after the last one).
    Homeopathic labels (potencies such as 12X, 30C) are read by :func:`_homeopathic`."""
    body = _s(body)
    metric = [m for m in _AMT.finditer(body) if m.group("u") != "%"]
    if _POT.search(body) and not metric:
        return _homeopathic(body, basis, variant)
    ptext = " ".join([*(purposes or []), *PURPOSE_WORDS]).lower()
    gen = generic.lower()
    out: list[dict[str, str]] = []
    pos = 0

    def take_purpose(name: str) -> tuple[str, str]:
        """The longest run of leading words that the Purpose section contains, when an
        ingredient name still follows it (one word only if it is not an ingredient's)."""
        if not ptext or name.lower() in ptext:  # the Purpose section names ingredients
            return name, ""
        words = name.split()
        for k in range(len(words) - 1, 0, -1):
            lead = " ".join(words[:k])
            if lead.lower() in ptext and (k >= 2 or "/" in lead or lead.lower() not in gen):
                return " ".join(words[k:]).strip(" -:"), lead
        return name, ""

    for m in _AMT.finditer(body):
        name = body[pos : m.start()].strip(" ,;:-•*")
        if not name:
            continue
        pos = m.end()
        # "... 3.5 mg of neomycin base Polymyxin B": the lowercase words before the next
        # capitalised name still describe the previous strength
        tail = re.match(
            r"^((?:of|as|from|bacitracin|neomycin|equivalent)\b[^A-Z]*?)\s+(?=[A-Z])", name
        )
        if out and tail:
            t = tail.group(1).strip()
            prev = out[-1]["note"]
            out[-1]["note"] = (
                f"{prev} {t}" if re.search(r"equivalent to [^;]+$", prev) else _join(prev, t)
            )
            name = name[tail.end() :]
        equiv = ""
        e = re.search(r"\s+(equivalent\s+to|equal\s+to|eq\.?\s+to)\s*$", name, re.I)
        if e:
            equiv, name = "equivalent to", name[: e.start()]
        name, purpose = take_purpose(name)
        if purpose and out:
            out[-1]["note"] = _join(out[-1]["note"], f"purpose: {purpose}")
        name = _strip_prefix(name, [variant, *prefixes])
        name, desc = _split_desc(name)
        name, std = _clean_name(name)
        paren = _s(m.group("paren")).strip("() ")
        amount = _amount(m.group("n"), m.group("u"))
        if m.group("u").lower() == "gr":  # apothecary grains: prefer the metric amount given
            metric_in = _AMT.fullmatch(paren) if paren else None
            if metric_in and metric_in.group("u").lower() not in ("gr", "%"):
                amount, paren = _amount(metric_in.group("n"), metric_in.group("u")), amount
        if equiv:
            equiv = f"equivalent to {amount}"
        note = "; ".join(x for x in (desc, paren, std, equiv) if x)
        out.append(
            row(
                name=name,
                role="active",
                amount=amount,
                basis=basis or ("of product" if amount.endswith("%") else ""),
                variant=variant,
                note=note,
            )
        )
    rest = body[pos:].strip(" ,;:-•*")
    rest_clean, rest_std = _clean_name(rest)
    if not out and rest:
        name, desc = _split_desc(_strip_prefix(rest_clean, [variant, *prefixes]))
        note = "; ".join(x for x in (desc, rest_std) if x)
        out.append(row(name=name, role="active", basis=basis, variant=variant, note=note))
    elif out and rest:
        if rest_std:
            out[-1]["note"] = _join(out[-1]["note"], rest_std)
        if re.match(r"(?:of|as|from)\b", rest_clean, re.I):
            out[-1]["note"] = _join(out[-1]["note"], rest_clean)
        elif rest_clean and len(rest_clean) < 80:
            out[-1]["note"] = _join(out[-1]["note"], f"purpose: {rest_clean}")
    return [r for r in out if r["name"] not in ("", NA)] or out


def _join(note: str, extra: str) -> str:
    return extra if note in ("", NA) else f"{note}; {extra}"


def _items(body: str) -> list[str]:
    try:
        return textrules.split_list2(body)
    except textrules.RuleError:
        return [x.strip() for x in re.split(r"[,;]", body) if x.strip()]


# The major food allergens (FALCPA, FASTER Act) and the words labels use for them.
_ALLERGEN_WORDS = (
    "milk", "egg", "eggs", "fish", "shellfish", "crustacean", "crustacean shellfish", "tree nut",
    "tree nuts", "peanut", "peanuts", "wheat", "soy", "soybean", "soybeans", "sesame", "almond",
    "almonds", "cashew", "cashews", "coconut", "hazelnut", "hazelnuts", "pecan", "pecans",
    "walnut", "walnuts", "pistachio", "pistachios", "macadamia", "brazil nut", "pine nut", "shrimp",
    "crab", "lobster", "anchovy", "anchovies", "cod", "salmon", "tuna", "pollock", "gluten",
    "dairy", "nuts",
)  # fmt: skip
_ALLERGEN = re.compile(
    r"(?:^|[.;,]\s*|\s)(?:allergens?\s*:|contains\s*:?)\s*(?P<list>[a-z ,&()/]+?)"
    r"(?:\s+ingredients?)?\s*\.?\s*$",
    re.I,
)


def allergens(text: str) -> tuple[str, list[str]]:
    """Split an allergen statement off the end of an ingredient list:
    'SUGAR, SALT. CONTAINS: WHEAT, MILK' -> ('SUGAR, SALT', ['wheat', 'milk']).
    Only when every word listed is an allergen word (so 'contains 2% or less of' stays)."""
    m = _ALLERGEN.search(text)
    if not m:
        return text, []
    items = [x.strip().lower() for x in re.split(r",|\band\b|&|/", m.group("list")) if x.strip()]
    items = [re.sub(r"\s*\(.*?\)\s*", " ", x).strip() for x in items]
    if not items or not all(
        x in _ALLERGEN_WORDS or any(x.endswith(" " + w) or x == w for w in _ALLERGEN_WORDS)
        for x in items
    ):
        return text, []
    return text[: m.start()].rstrip(" .;,"), items


def ingredient_list(
    body: str, role: str, basis: str = "", variant: str = ""
) -> list[dict[str, str]]:
    """A comma list; sub-ingredients in brackets, 'x%' amounts and '2% or less of' groups."""
    out: list[dict[str, str]] = []
    less = ""
    body = re.sub(
        r"[.;]\s+(?=(?:and\s+)?contains\s+(?:less\s+than\s+)?\d)", ", ", _s(body), flags=re.I
    )
    for item in _items(body.rstrip(". ")):
        it = item.strip(" .:*")
        note = ""
        unii = _UNII.search(it)
        if unii:
            note = f"UNII {unii.group('u').upper()}"
            it = (it[: unii.start()] + it[unii.end() :]).strip()
        m = _LESS.match(it)
        if m:
            less = (
                "≤ "
                + re.sub(r"\s*or\s+less|less\s+than\s*", "", m.group("pct"), flags=re.I).strip()
            )
            if "less than" in m.group("pct").lower():
                less = "< " + less[2:]
            it = it[m.end() :].strip()
            if not it:
                continue
        lead = _PCT_LEAD.match(it)
        lead_pct = ""
        if lead:
            lead_pct, it = _amount(lead.group("n"), "%"), it[lead.end() :]
        depth = sum(it.count(c) for c in "([") - sum(it.count(c) for c in ")]")
        if depth:
            note = _join(note, "brackets do not balance in the source text: check this row")
        name, sub = it, ""
        b = re.search(r"[(\[]", it)
        if b and it.rstrip().endswith((")", "]")):
            name, sub = it[: b.start()].strip(), it[b.start() + 1 : -1].strip()
        amount, basis_i = "", basis
        p = _PCT_IN.search(name)
        if p and p.start() > 0:
            amount, basis_i = _amount(p.group("n"), "%"), "of product"
            name = name[: p.start()].strip()
        elif sub and re.fullmatch(r"\d+(?:[.,]\d+)?\s*%", sub):
            amount, basis_i, sub = _amount(sub.rstrip("% "), "%"), "of product", ""
        elif lead_pct:
            amount, basis_i = lead_pct, "of product"
        elif less:
            amount, basis_i = less, "of product"
        name = re.sub(r"^(?:name\s+strength|name)\s+", "", name, flags=re.I).strip()
        if name:
            out.append(
                row(
                    name=name,
                    role=role,
                    amount=amount,
                    basis=basis_i,
                    sub=sub,
                    variant=variant,
                    note=note,
                )
            )
    return out


def contains(text: str, variant: str = "") -> list[dict[str, str]]:
    """'each caplet contains: calcium 10mg' and 'each tablespoon contributes 60 calories'."""
    t = _s(text)
    out: list[dict[str, str]] = []
    for m in _EACH.finditer(t):
        for it in _ITEM.finditer(m.group("items")):
            out.append(
                contains_row(
                    name=it.group("name").strip().lower(),
                    amount=_amount(it.group("n"), it.group("u")),
                    basis=f"per {m.group('dose').strip()}",
                    variant=variant,
                )
            )
    for m in _CAL.finditer(t):
        src = _s(m.group("from"))
        out.append(
            contains_row(
                name="calories",
                amount=f"{m.group('n')} kcal",
                basis=f"per {m.group('dose').strip()}",
                variant=variant,
                note=f"from {src}" if src else "",
            )
        )
    return out


def section(
    text: str,
    *,
    heading_text: str = "",
    prefixes: list[str] | None = None,
    default: str = "ingredient",
    purposes: list[str] | None = None,
    generic: str = "",
) -> dict[str, Any]:
    """One label section (with or without its heading) -> rows and contains-statements."""
    full = f"{heading_text}: {text}" if heading_text else text
    kind, basis, variant, body = heading(full)
    kind = kind or default
    rows: list[dict[str, str]] = []
    cont: list[dict[str, str]] = []
    if kind == "active":
        rows = actives(body, basis, variant, prefixes or [], purposes, generic)
    elif kind == "info":
        cont = contains(body, variant)
    elif kind in ("inactive", "other", "ingredient"):
        body, alg = allergens(body)
        rows = ingredient_list(body, kind, basis, variant)
        cont = contains(body, variant)
        return {"ingredients": rows, "contains": cont, "allergens": alg}
    return {"ingredients": rows, "contains": cont, "allergens": []}


# --------------------------------------------------------------------- records


def _empty(source: str, name: str) -> dict[str, Any]:
    return {
        "source": source,
        "product": name or NA,
        "variant": NA,
        "serving": NA,
        "ingredients": [],
        "contains": [],
        "allergens": [],
    }


def _openfda(info: dict[str, Any], raw: Any) -> list[dict[str, Any]]:
    parts = info.get("ingredient_parts") or []
    variants = [v for v in (info.get("variants") or []) if v]
    brand = generic = ""
    listed: list[str] = []
    if isinstance(raw, dict):
        o = raw.get("openfda") or {}
        brand = ", ".join(o.get("brand_name") or [])
        listed = [str(x) for x in o.get("substance_name") or []] or [
            x.strip() for x in ", ".join(o.get("generic_name") or []).split(",") if x.strip()
        ]
        generic = " ".join([*(o.get("generic_name") or []), *listed])
    # a brand that is also the ingredient ("Loratadine") must not be stripped from names
    keep_brand = brand and brand.lower() not in generic.lower()
    prefixes = [*variants, brand] if keep_brand else list(variants)

    def variant_of(p: dict[str, Any]) -> str:
        v = str(p.get("variant") or "")
        if v:
            return v
        low = str(p.get("text") or "").lower()
        hits = [x for x in variants if x.lower() in low]
        return max(hits, key=len) if hits else ""

    purpose_text = ""
    if isinstance(raw, dict) and raw.get("purpose"):
        purpose_text = _s(" ".join(str(x) for x in raw["purpose"]))
    purposes = [re.sub(r"^\s*(?:purposes?\b\s*:?\s*)+", "", purpose_text, flags=re.I)]
    options = variants or [""]
    out = []
    for v in options:
        s = _empty("openfda", str(info.get("name") or ""))
        s["variant"] = v or NA
        for p in parts:
            pv = variant_of(p)
            if pv and v and pv != v:
                continue
            role = {"other_information": "info"}.get(p["role"], p["role"])
            sec = section(
                str(p["text"]), prefixes=prefixes, default=role, purposes=purposes, generic=generic
            )
            for r in sec["ingredients"]:
                if v and r["variant"] == NA:
                    r["variant"] = v
            s["ingredients"].extend(sec["ingredients"])
            s["contains"].extend(sec["contains"])
        acts = [r for r in s["ingredients"] if r["role"] == "active"]
        if len(acts) == 1 and acts[0]["name"] in ("", NA) and len(listed) == 1:
            acts[0]["name"] = listed[0].title()
            acts[0]["note"] = _join(acts[0]["note"], "name from the FDA product listing")
        if not acts and listed:
            # The label text gives no active ingredient: the FDA listing names them.
            acts = [
                row(name=x.title(), role="active", variant=v,
                    note="from the FDA product listing; the label text gives no strength")
                for x in listed
            ]  # fmt: skip
            s["ingredients"] = acts + s["ingredients"]
        _attach_purposes(acts, purpose_text)
        bases = {r["basis"] for r in s["ingredients"] if r["role"] == "active" and r["basis"] != NA}
        if len(bases) == 1:
            s["serving"] = "1 " + bases.pop().removeprefix("per ")
        out.append(s)
    return out


def _attach_purposes(acts: list[dict[str, str]], text: str) -> None:
    """Fill each active's purpose from the label's Purpose section: the words after the
    ingredient's name, up to the next ingredient ("Glycerin-Protectant Lidocaine-Local
    anesthetic"), or the whole section when there is one active and no name in it."""
    t = re.sub(r"\.{3,}|…+", " ", text)
    t = re.sub(r"^\s*(?:purposes?\b\s*:?\s*)+", "", t, flags=re.I).strip()
    todo = [r for r in acts if "purpose:" not in r["note"]]
    if not t or not todo:
        return
    low = t.lower()
    hits = []
    for r in acts:
        key = re.sub(r"\s*\b(hcl|hydrochloride)\b", "", r["name"].lower()).strip()
        i = low.find(key) if key else -1
        if i >= 0:
            hits.append((i, i + len(key), r))
    hits.sort(key=lambda h: h[0])
    for k, (_, end, r) in enumerate(hits):
        stop = hits[k + 1][0] if k + 1 < len(hits) else len(t)
        phrase = re.sub(r"^\s*(?:hcl|hydrochloride)\b", "", t[end:stop], flags=re.I)
        phrase = phrase.strip(" -:\u2013,;.*")
        if phrase and r in todo and len(phrase) < 80:
            r["note"] = _join(r["note"], f"purpose: {phrase}")
    if not hits and len(acts) == 1 and len(t) < 80:
        acts[0]["note"] = _join(acts[0]["note"], f"purpose: {t.strip(' .')}")


def _dsld_unit(u: Any) -> str:
    t = _s(u).replace("(s)", "").strip()
    return {
        "gram": "g",
        "milligram": "mg",
        "microgram": "mcg",
        "calorie": "kcal",
        "kilocalorie": "kcal",
    }.get(t.lower(), t)


def _dsld_qty(q: list[dict[str, Any]]) -> tuple[str, str]:
    """(amount, %DV) of a DSLD row's first serving; 'NP' (not present) -> N/A."""
    if not q:
        return "", ""
    a = q[0]
    unit = _dsld_unit(a.get("unit"))
    qty = a.get("quantity")
    amount = ""
    if isinstance(qty, (int, float)) and unit and unit.upper() != "NP":
        op = _s(a.get("operator"))
        amount = f"{'' if op in ('', '=') else op + ' '}{qty:g} {unit}"
    dv = ""
    for g in a.get("dailyValueTargetGroup") or []:
        if isinstance(g.get("percent"), (int, float)):
            dv = f"{g['percent']:g}%"
            break
        if g.get("footnote"):
            dv = _s(g["footnote"])
    return amount, dv


def _forms(x: dict[str, Any]) -> str:
    return ", ".join(_s(f.get("name")) for f in x.get("forms") or [] if f.get("name"))


def _dsld(raw: dict[str, Any], info: dict[str, Any]) -> dict[str, Any]:
    s = _empty("dsld", str(info.get("name") or raw.get("fullName") or ""))
    ss = (raw.get("servingSizes") or [{}])[0]
    if isinstance(ss.get("minQuantity"), (int, float)):
        unit = _s(ss.get("unit")).replace("(s)", "")
        size = f"{ss['minQuantity']:g} {unit}".strip()
        s["serving"] = size
        if isinstance(ss.get("maxDailyServings"), (int, float)):
            s["serving"] += f", up to {ss['maxDailyServings']:g} a day"
        basis = f"per {size}"
    else:
        basis = ""

    def walk(rows: list[dict[str, Any]], parent: str) -> None:
        for r in rows:
            amount, dv = _dsld_qty(r.get("quantity") or [])
            notes = []
            if parent:
                notes.append(f"in {parent}")
            if r.get("category"):
                notes.append(f"category: {_s(r['category'])}")
            if r.get("uniiCode"):
                notes.append(f"UNII {r['uniiCode']}")
            if r.get("notes"):
                notes.append(_s(r["notes"]))
            s["ingredients"].append(
                row(
                    name=r.get("name"),
                    role="dietary",
                    amount=amount,
                    basis=basis if amount else "",
                    dv=dv,
                    form=_forms(r),
                    note="; ".join(notes),
                )
            )
            walk(r.get("nestedRows") or [], _s(r.get("name")))

    walk(raw.get("ingredientRows") or [], "")
    oi = raw.get("otheringredients") or {}
    names = oi.get("ingredients") or []
    if names:
        for x in names:
            if _s(x.get("ingredientGroup")).lower() == "header" and x.get("forms"):
                for f in x["forms"]:
                    s["ingredients"].append(
                        row(name=f.get("name"), role="other", note=_s(x.get("name")))
                    )
            else:
                s["ingredients"].append(row(name=x.get("name"), role="other", form=_forms(x)))
    elif oi.get("text"):
        s["ingredients"].extend(ingredient_list(str(oi["text"]), "other"))
    return s


def _food(source: str, info: dict[str, Any]) -> dict[str, Any]:
    s = _empty(source, str(info.get("name") or ""))
    if info.get("serving_size"):
        s["serving"] = _s(info["serving_size"])
    text = str(info.get("ingredients_text") or "")
    if text.strip():
        sec = section(text, default="ingredient")
        s["ingredients"], s["contains"] = sec["ingredients"], sec["contains"]
        s["allergens"] = sec["allergens"]
    return s


def structure_record(
    source: str, info: dict[str, Any], raw: Any, query: str = ""
) -> dict[str, Any]:
    """Every variant's table for a picked record, and the one that best matches ``query``."""
    if source == "openfda":
        options = _openfda(info, raw)
    elif source == "dsld" and isinstance(raw, dict):
        options = [_dsld(raw, info)]
    else:
        options = [_food(source, info)]
    words = set(re.findall(r"[a-z0-9]+", query.lower()))

    def score(o: dict[str, Any]) -> int:
        return len(words & set(re.findall(r"[a-z0-9]+", str(o["variant"]).lower())))

    best = max(range(len(options)), key=lambda i: (score(options[i]), -i))
    return {"options": options, "default": best}


def structure_sections(sections: list[dict[str, Any]]) -> dict[str, Any]:
    """Web-page sections the user ticked ({heading, text}) -> one table."""
    s = _empty("web", "")
    for sc in sections[:50]:
        sec = section(str(sc.get("text") or ""), heading_text=str(sc.get("heading") or ""))
        s["ingredients"].extend(sec["ingredients"])
        s["contains"].extend(sec["contains"])
        s["allergens"] += [a for a in sec["allergens"] if a not in s["allergens"]]
    return s


# ------------------------------------------------------------------- saving


def clean(s: Any) -> dict[str, Any]:
    """Validate a (possibly edited) table sent back by a client."""
    if not isinstance(s, dict):
        raise ValueError("structured ingredients must be an object")

    def txt(v: Any) -> str:
        t = _s(v)[:MAX_LEN]
        return t or NA

    rows = s.get("ingredients") or []
    cont = s.get("contains") or []
    if not isinstance(rows, list) or not isinstance(cont, list):
        raise ValueError("structured ingredients: rows must be lists")
    if len(rows) + len(cont) > MAX_ROWS:
        raise ValueError("structured ingredients: too many rows")
    out_rows = []
    for r in rows:
        if not isinstance(r, dict):
            raise ValueError("structured ingredients: a row is not an object")
        d = {k: txt(r.get(k)) for k in FIELDS}
        if d["role"] not in ROLES:
            raise ValueError(f"unknown ingredient role {d['role']!r}")
        if d["name"] != NA:
            out_rows.append(d)
    out_cont = []
    for r in cont:
        if not isinstance(r, dict):
            raise ValueError("structured ingredients: a row is not an object")
        d = {k: txt(r.get(k)) for k in CONTAINS_FIELDS}
        if d["name"] != NA:
            out_cont.append(d)
    return {
        "source": txt(s.get("source")),
        "product": txt(s.get("product")),
        "variant": txt(s.get("variant")),
        "serving": txt(s.get("serving")),
        "ingredients": out_rows,
        "contains": out_cont,
        "allergens": [
            a
            for a in (
                _s(x)[:60].lower()
                for x in (s["allergens"] if isinstance(s.get("allergens"), list) else [])[:30]
            )
            if a and a != "n/a"
        ],
    }


def to_text(s: dict[str, Any]) -> str:
    """A label-style ingredient statement from a table (for the plain-text field)."""

    def v(x: str) -> str:
        return "" if x == NA else x

    def item(r: dict[str, str]) -> str:
        t = r["name"]
        if v(r.get("sub", NA)):
            t += f" ({r['sub']})"
        extra = [x for x in (v(r["amount"]), v(r.get("dv", NA)) and f"{r['dv']} DV") if x]
        return t + (f" {' '.join(extra)}" if extra else "")

    parts = []
    groups = (
        ("active", "Active ingredients"),
        ("dietary", "Supplement Facts"),
        ("ingredient", "Ingredients"),
        ("inactive", "Inactive ingredients"),
        ("other", "Other ingredients"),
    )
    for role, title in groups:
        rows = [r for r in s.get("ingredients") or [] if r["role"] == role]
        if not rows:
            continue
        bases = {r["basis"] for r in rows if r["basis"] not in (NA, "of product")}
        head = f"{title} ({bases.pop()})" if len(bases) == 1 else title
        parts.append(f"{head}: " + ", ".join(item(r) for r in rows))
    if s.get("allergens"):
        parts.append("Allergens: " + ", ".join(s["allergens"]))
    cont = s.get("contains") or []
    if cont:
        parts.append(
            "Per dose: "
            + ", ".join(
                f"{r['name']} {r['amount']}" + (f" {r['basis']}" if v(r["basis"]) else "")
                for r in cont
            )
        )
    return " | ".join(parts)
