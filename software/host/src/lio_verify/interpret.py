"""Rule tables, cited constants, and turning a fact's raw value into an interval."""

from __future__ import annotations

import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

from lio_verify.chem import mass_fraction, parse_mf
from lio_verify.interval import Interval, IntervalError, parse_rational
from lio_verify.rounding import Declaration, RoundingError, RoundingRules
from lio_verify.textrules import parse_raw


class InterpretError(ValueError):
    pass


def load_tables(rules_dir: Path) -> dict[str, dict[str, Any]]:
    tables: dict[str, dict[str, Any]] = {}
    for p in sorted(rules_dir.glob("*.json")):
        t = json.loads(p.read_text(encoding="utf-8"))
        tables[t["id"]] = t
    return tables


def split_ref(ref: str) -> tuple[str, int, str]:
    """``"fda_rounding_101_9@1:calories"`` -> (table id, version, selector)."""
    head, _, sel = ref.partition(":")
    tid, _, ver = head.partition("@")
    if not tid or not ver.isdigit():
        raise InterpretError(f"bad rule reference {ref!r}")
    return tid, int(ver), sel


def table(tables: dict[str, dict[str, Any]], tid: str, version: int) -> dict[str, Any]:
    t = tables.get(tid)
    if t is None:
        raise InterpretError(f"no rule table {tid!r}")
    if t["version"] != version:
        raise InterpretError(f"{tid} is version {t['version']}, the record cites {version}")
    return t


def interpret(
    value_raw: str, interpretation: dict[str, Any], tables: dict[str, dict[str, Any]]
) -> tuple[Interval, str]:
    """The exact set of true values a raw value stands for, and its unit."""
    lt = value_raw.startswith("<")
    raw = parse_raw(value_raw[1:].strip() if lt else value_raw)
    kind = interpretation.get("kind")
    if kind in ("exact", "as_stated"):
        if lt:
            raise InterpretError("a 'less than' value needs a rounding rule")
        return Interval.point(raw.value), raw.unit
    if kind == "rounded":
        tid, ver, nutrient = split_ref(interpretation["rule"])
        rr = RoundingRules(table(tables, tid, ver))
        if rr.units.get(nutrient) != raw.unit:
            raise InterpretError(
                f"{nutrient}: unit {raw.unit} != rule unit {rr.units.get(nutrient)}"
            )
        try:
            return rr.inverse(nutrient, Declaration("lt" if lt else "eq", raw.value)), raw.unit
        except RoundingError as e:
            raise InterpretError(str(e)) from e
    raise InterpretError(f"unknown interpretation {kind!r}")


def constant(
    ref: str, tables: dict[str, dict[str, Any]], versions: dict[str, int]
) -> tuple[Interval, str]:
    """``C:<table>.<path>`` -> a cited constant (``{"value": rational, "unit": ...}``)."""
    path = ref[2:].split(".")
    tid = path[0]
    if tid not in versions:
        raise InterpretError(f"{ref}: the record does not pin a version of {tid}")
    node: Any = table(tables, tid, versions[tid])
    for key in path[1:]:
        if not isinstance(node, dict) or key not in node:
            raise InterpretError(f"no constant {ref}")
        node = node[key]
    if not isinstance(node, dict) or "value" not in node or "unit" not in node:
        raise InterpretError(f"{ref} is not a constant")
    return Interval.point(parse_rational(node["value"])), str(node["unit"])


def element_fraction(
    element: str, formula: str, tables: dict[str, dict[str, Any]], versions: dict[str, int]
) -> Interval:
    """Mass fraction of ``element`` in a UNII formula, from the pinned atomic weights."""
    t = table(tables, "atomic_masses", versions.get("atomic_masses", -1))
    weights: dict[str, Interval] = {}
    for el, e in t["elements"].items():
        weights[el] = Interval.from_json(e["weight"])[0]
    counts = parse_mf(formula)
    missing = [el for el in counts if el not in weights]
    if missing or element not in counts:
        raise InterpretError(f"cannot weigh {formula} for {element} (missing {missing})")
    try:
        return mass_fraction(element, counts, weights)
    except IntervalError as e:
        raise InterpretError(str(e)) from e


_ASSAY = re.compile(
    r".*?not less than (?P<lo>[0-9]+(?:\.[0-9]+)?) percent"
    r" and not more than (?P<hi>[0-9]+(?:\.[0-9]+)?) percent.*"
)


def assay_percent(quote: str) -> Interval:
    """``usp_assay_percent@1``: "not less than 98.0 percent and not more than 103.0 percent"
    -> [0.98, 1.03] (closed)."""
    m = _ASSAY.fullmatch(" ".join(quote.split()))
    if not m:
        raise InterpretError(f"not a USP assay range: {quote!r}")
    return Interval(Fraction(m.group("lo")) / 100, Fraction(m.group("hi")) / 100)


def additive_fraction(
    name: str, tables: dict[str, dict[str, Any]], versions: dict[str, int]
) -> Interval:
    """``A:additive_assays.<entry>``: the element mass fraction of a variable-composition
    additive, re-derived from the quoted assay (which must match the table)."""
    t = table(tables, "additive_assays", versions.get("additive_assays", -1))
    e = t["entries"].get(name)
    if e is None:
        raise InterpretError(f"no additive assay {name!r}")
    if e.get("rule") != "usp_assay_percent@1":
        raise InterpretError(f"{name}: unknown assay rule {e.get('rule')!r}")
    quoted = assay_percent(e["citations"][0]["locator"]["text"])
    if e["type"] == "element_fraction_interval":
        iv, _ = Interval.from_json(e["interval"])
        if iv != quoted:
            raise InterpretError(f"{name}: table interval {iv} is not the quoted {quoted}")
        return iv
    if e["type"] == "assay_times_formula":
        assay, _ = Interval.from_json(e["assay"])
        if assay != quoted:
            raise InterpretError(f"{name}: table assay {assay} is not the quoted {quoted}")
        return assay * element_fraction(e["element"], e["formula"], tables, versions)
    raise InterpretError(f"{name}: unknown rule type {e['type']!r}")


def literal(ref: str) -> tuple[Interval, str]:
    """``N:<rational>[:<unit>]`` -> an exact literal (e.g. 100 for per-100 g)."""
    body = ref[2:]
    num, _, unit = body.partition(":")
    return Interval.point(parse_rational(num)), unit or "1"


__all__ = [
    "Fraction",
    "InterpretError",
    "constant",
    "element_fraction",
    "interpret",
    "literal",
    "load_tables",
    "split_ref",
    "table",
]
