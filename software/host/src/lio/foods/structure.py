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
    r"^\s*(?P<h>active\s+ingredients?|inactive\s+ingredients?|other\s+ingredients?|"
    r"ingredients?|other\s+information)\b\s*(?P<paren>\([^()]*\))?\s*[:.\-]?\s*",
    re.I,
)
_UNIT = r"mg|mcg|µg|g|iu|ml|%"
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
    r"^\s*(?:and\s+)?(?:contains\s+)?(?P<pct>(?:less\s+than\s+)?\d+(?:\.\d+)?\s*%\s*(?:or\s+less)?)"
    r"\s*(?:of)?\s*:?\s*(?:the\s+following\s*:?)?\s*",
    re.I,
)
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
    u = u.lower().replace("µg", "mcg")
    u = {"iu": "IU", "ml": "mL"}.get(u, u)
    return f"{n.replace(',', '.')}{'' if u == '%' else ' '}{u}"


def heading(text: str) -> tuple[str, str, str, str]:
    """Split a section into (kind, basis, variant, body); kind is '' when unlabelled."""
    m = _HEAD.match(text)
    if not m:
        return "", "", "", text.strip()
    kind = re.sub(r"\s+", " ", m.group("h").lower()).rstrip("s")
    kind = {
        "active ingredient": "active",
        "inactive ingredient": "inactive",
        "other ingredient": "other",
        "ingredient": "ingredient",
        "other information": "info",
    }.get(kind, kind)
    paren = m.group("paren") or ""
    basis = _basis(paren)
    variant = "" if basis or not paren else _s(paren).strip("() ")
    return kind, basis, variant, text[m.end() :].strip()


def actives(body: str, basis: str, variant: str, prefixes: list[str]) -> list[dict[str, str]]:
    """Active ingredients with strengths: 'Methylcellulose (a non-allergenic fiber) 500mg'."""
    body = _s(body)
    out: list[dict[str, str]] = []
    pos = 0
    for m in _AMT.finditer(body):
        name = body[pos : m.start()].strip(" ,;:-•*")
        if not name:
            continue
        pos = m.end()
        name = _strip_prefix(name, [variant, *prefixes])
        name, desc = _split_desc(name)
        note = " ".join(x for x in (desc, _s(m.group("paren")).strip("() ")) if x)
        out.append(
            row(
                name=name,
                role="active",
                amount=_amount(m.group("n"), m.group("u")),
                basis=basis,
                variant=variant,
                note=note,
            )
        )
    rest = body[pos:].strip(" ,;:-•*")
    if not out and rest:
        name, desc = _split_desc(_strip_prefix(rest, [variant, *prefixes]))
        out.append(row(name=name, role="active", basis=basis, variant=variant, note=desc))
    elif out and rest and len(rest) < 80:
        last = out[-1]
        last["note"] = " ".join(x for x in (last["note"], rest) if x != NA)
    return out


def _items(body: str) -> list[str]:
    try:
        return textrules.split_list2(body)
    except textrules.RuleError:
        return [x.strip() for x in re.split(r"[,;]", body) if x.strip()]


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
        if m and re.search(r"%", m.group("pct")):
            less = (
                "≤ "
                + re.sub(r"\s*or\s+less|less\s+than\s*", "", m.group("pct"), flags=re.I).strip()
            )
            if "less than" in m.group("pct").lower():
                less = "< " + less[2:]
            it = it[m.end() :].strip()
            if not it:
                continue
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
) -> dict[str, Any]:
    """One label section (with or without its heading) -> rows and contains-statements."""
    full = f"{heading_text}: {text}" if heading_text else text
    kind, basis, variant, body = heading(full)
    kind = kind or default
    rows: list[dict[str, str]] = []
    cont: list[dict[str, str]] = []
    if kind == "active":
        rows = actives(body, basis, variant, prefixes or [])
    elif kind == "info":
        cont = contains(body, variant)
    elif kind in ("inactive", "other", "ingredient"):
        rows = ingredient_list(body, kind, basis, variant)
        cont = contains(body, variant)
    return {"ingredients": rows, "contains": cont}


# --------------------------------------------------------------------- records


def _empty(source: str, name: str) -> dict[str, Any]:
    return {
        "source": source,
        "product": name or NA,
        "variant": NA,
        "serving": NA,
        "ingredients": [],
        "contains": [],
    }


def _openfda(info: dict[str, Any], raw: Any) -> list[dict[str, Any]]:
    parts = info.get("ingredient_parts") or []
    variants = [v for v in (info.get("variants") or []) if v]
    brand = ""
    if isinstance(raw, dict):
        brand = ", ".join((raw.get("openfda") or {}).get("brand_name") or [])
    prefixes = [*variants, brand] if brand else list(variants)

    def variant_of(p: dict[str, Any]) -> str:
        v = str(p.get("variant") or "")
        if v:
            return v
        low = str(p.get("text") or "").lower()
        hits = [x for x in variants if x.lower() in low]
        return max(hits, key=len) if hits else ""

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
            sec = section(str(p["text"]), prefixes=prefixes, default=role)
            for r in sec["ingredients"]:
                if v and r["variant"] == NA:
                    r["variant"] = v
            s["ingredients"].extend(sec["ingredients"])
            s["contains"].extend(sec["contains"])
        bases = {r["basis"] for r in s["ingredients"] if r["role"] == "active" and r["basis"] != NA}
        if len(bases) == 1:
            s["serving"] = "1 " + bases.pop().removeprefix("per ")
        out.append(s)
    return out


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
    cont = s.get("contains") or []
    if cont:
        parts.append(
            "Contains: "
            + ", ".join(
                f"{r['name']} {r['amount']}" + (f" {r['basis']}" if v(r["basis"]) else "")
                for r in cont
            )
        )
    return " | ".join(parts)
