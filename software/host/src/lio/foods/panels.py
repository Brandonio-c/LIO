"""Drug Facts and Supplement Facts panels, read from OCR lines (plan WP4).

Deterministic parsers: they *propose* fields, each with the text it was read from
and that line's pixel box; the operator confirms each field before it becomes an
ATTESTED fact, and the field's text must re-parse with the versioned rule named
here (``drug_active@1``, ``otc_contains@1``, ``sfp_row@1``, ``sfp_serving@1``,
``list_item@2``).

- **Drug Facts** (21 CFR 201.66(c)): sectioned on the mandated headings, in order:
  Active ingredient(s), Purpose(s), Use(s), Warnings, Directions, Other information,
  Inactive ingredients, Questions?. Actives with strengths; the "each ... contains:"
  mineral statements; the inactive list, which is alphabetical (201.66(c)(8)), so it
  carries no weight order.
- **Supplement Facts** (21 CFR 101.36): serving size, servings per container, the
  dietary-ingredient rows (amount, unit, %DV), proprietary blends (total weight; the
  members that follow have no amounts), and the "Other ingredients" statement.
"""

from __future__ import annotations

import contextlib
import re
from typing import Any

from .ocr import Line, columns, visual_rows

DRUG_HEADINGS = [
    ("active", r"active\s+ingredients?\b"),
    ("purpose", r"purposes?\b"),
    ("uses", r"uses?\b"),
    ("warnings", r"warnings?\b"),
    ("directions", r"directions\b"),
    ("other_information", r"other\s+information\b"),
    ("inactive", r"inactive\s+ingredients?\b"),
    ("questions", r"questions\b"),
]


def _box(ln: Line, size: tuple[int, int]) -> dict[str, int]:
    w, h = size
    return {
        "x": max(0, round(ln.x * w)),
        "y": max(0, round((1 - ln.y - ln.h) * h)),
        "w": max(1, round(ln.w * w)),
        "h": max(1, round(ln.h * h)),
    }


def _union(lines: list[Line], size: tuple[int, int]) -> dict[str, int]:
    x0, x1 = min(ln.x for ln in lines), max(ln.x + ln.w for ln in lines)
    y0, y1 = min(ln.y for ln in lines), max(ln.y + ln.h for ln in lines)
    return _box(Line("", 1.0, x0, y0, x1 - x0, y1 - y0), size)


def _rules() -> Any:
    from lio_verify import textrules  # needs the comp extra

    return textrules


def drug_facts(lines: list[Line], size: tuple[int, int]) -> dict[str, Any]:
    """Sections and proposed fields of a Drug Facts panel."""
    tr = _rules()
    order = [ln for col in columns(lines) for ln in col]
    marks: list[tuple[int, str]] = []
    for i, ln in enumerate(order):
        for key, pat in DRUG_HEADINGS:
            if re.match(pat, ln.text.strip(), re.I) and key not in [k for _, k in marks]:
                marks.append((i, key))
                break
    sections: dict[str, list[Line]] = {}
    for n, (i, key) in enumerate(marks):
        end = marks[n + 1][0] if n + 1 < len(marks) else len(order)
        sections[key] = order[i:end]
    out: dict[str, Any] = {
        "sections": [k for _, k in marks],
        "actives": [],
        "contains": [],
        "inactive": None,
        "complete": len(marks) >= 6,
    }
    for ln in sections.get("active", []):
        body = re.sub(r"(?i)^active\s+ingredients?\s*(\([^)]*\))?\s*", "", ln.text).strip()
        try:
            out["actives"].append(
                {
                    "text": body,
                    "value_raw": tr.apply("drug_active@1", body),
                    "rule": "drug_active@1",
                    "box": _box(ln, size),
                }
            )
        except tr.RuleError:
            continue
    for ln in visual_rows(sections.get("other_information", [])):
        m = re.search(r"(?i)each\b.*?contains\s*:.*", ln.text)
        if not m:
            continue
        try:
            items = tr._otc_items(m.group(0))
        except tr.RuleError:
            continue
        out["contains"].append(
            {"text": m.group(0), "items": items, "rule": "otc_contains@1", "box": _box(ln, size)}
        )
    inact = sections.get("inactive", [])
    if inact:
        text = " ".join(ln.text for ln in inact)
        text = re.sub(r"(?i)^inactive\s+ingredients?\s*(\([^)]*\))?\s*", "", text).strip()
        out["inactive"] = {
            "text": text,
            "items": tr.split_list2(text) if text else [],
            "order": "alphabetical (21 CFR 201.66(c)(8)): no weight order",
            "rule": "list_item@2",
            "box": _union(inact, size),
        }
    return out


def supplement_facts(lines: list[Line], size: tuple[int, int]) -> dict[str, Any]:
    """Proposed fields of a Supplement Facts panel."""
    tr = _rules()
    rows = visual_rows(lines)
    out: dict[str, Any] = {
        "serving": None,
        "servings_per_container": None,
        "rows": [],
        "blends": [],
        "other_ingredients": None,
    }
    blend: dict[str, Any] | None = None
    for i, ln in enumerate(rows):
        t = " ".join(ln.text.split())
        if out["serving"] is None and re.match(r"(?i)serving\s+size\b", t):
            with contextlib.suppress(tr.RuleError):
                out["serving"] = {
                    "text": t,
                    "value_raw": tr.apply("sfp_serving@1", t),
                    "rule": "sfp_serving@1",
                    "box": _box(ln, size),
                }
            continue
        m = re.match(r"(?i)servings\s+per\s+container\s+(?:about\s+)?([0-9]+)", t)
        if m:
            out["servings_per_container"] = {"text": t, "value": m.group(1)}
            continue
        m = re.match(r"(?i)other\s+ingredients?\s*:?\s*(.*)", t)
        if m:
            rest = " ".join([m.group(1), *[r.text for r in rows[i + 1 : i + 4]]]).strip()
            out["other_ingredients"] = {
                "text": rest,
                "items": tr.split_list2(rest) if rest else [],
                "rule": "list_item@2",
                "box": _union(rows[i : i + 4], size),
            }
            break
        if re.match(r"(?i)(amount\s+per\s+serving|%\s*daily\s+value|supplement\s+facts)", t):
            continue
        try:
            name, value_raw, dv = tr.sfp_row(t)
        except tr.RuleError:
            footnote = re.match(r"[†*‡]", t) or re.search(r"(?i)daily\s+value|not\s+established", t)
            if footnote:
                blend = None  # footnotes end the member list
            elif blend is not None and t and not re.search(r"\d", t):
                blend["members"].append({"text": t, "box": _box(ln, size)})  # a member: no amount
            continue
        row = {
            "text": t,
            "name": name,
            "value_raw": value_raw,
            "dv": dv,
            "rule": "sfp_row@1",
            "box": _box(ln, size),
        }
        out["rows"].append(row)
        blend = None
        if re.search(r"(?i)\bblend\b", name):
            blend = {"row": row, "members": []}
            out["blends"].append(blend)
    return out


def parse(kind: str, lines: list[Line], size: tuple[int, int]) -> dict[str, Any] | None:
    try:
        if kind == "drug_facts":
            return drug_facts(lines, size)
        if kind == "supplement_facts":
            return supplement_facts(lines, size)
    except ImportError:
        return None
    return None


def flatten(kind: str, panel: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The proposed fields of a parsed panel as one indexed list (what the operator ticks)."""
    if not panel:
        return []
    out: list[dict[str, Any]] = []
    if kind == "drug_facts":
        for a in panel["actives"]:
            out.append({"field": "active", "rule": a["rule"], "text": a["text"], "box": a["box"]})
        for c in panel["contains"]:
            for el in c["items"]:
                out.append(
                    {
                        "field": "contains",
                        "element": el,
                        "rule": f"otc_contains@1:{el}",
                        "text": c["text"],
                        "box": c["box"],
                    }
                )
        if panel.get("inactive"):
            out.append(
                {
                    "field": "inactive_list",
                    "rule": "list_item@2",
                    "text": panel["inactive"]["text"],
                    "box": panel["inactive"]["box"],
                }
            )
    elif kind == "supplement_facts":
        for r in panel["rows"]:
            out.append(
                {
                    "field": "row",
                    "name": r["name"],
                    "rule": "sfp_row@1",
                    "text": r["text"],
                    "box": r["box"],
                }
            )
        for b in panel["blends"]:
            for m in b["members"]:
                out.append(
                    {
                        "field": "blend_member",
                        "blend": b["row"]["name"],
                        "rule": "",
                        "text": m["text"],
                        "box": m["box"],
                    }
                )
        if panel.get("other_ingredients"):
            o = panel["other_ingredients"]
            out.append(
                {"field": "other_list", "rule": "list_item@2", "text": o["text"], "box": o["box"]}
            )
    return [{"index": i, **f} for i, f in enumerate(out)]
