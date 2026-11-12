"""Linear constraints over unknown amounts, and exact checks of bound certificates.

Unknowns are record ``variables`` (``V:<name>``, each with a unit). A constraint
compares a linear form of unknowns with the interval of a fact, derivation or
literal (spec §3.3 kinds):

- ``eq_within``: lhs lies in the rhs interval;
- ``le`` / ``ge``: lhs <= the true value of rhs (so <= its upper end) / >= its lower end;
- ``sum_eq``: the ``items`` add up to a value in the rhs interval;
- ``ordered_desc``: ``items`` in non-increasing order (only for weight-ordered lists);
- ``positive``: each of ``items`` is > 0 (a listed ingredient is present).

A constraint without unknowns is a consistency check between data: it is
``entailed`` (always true), ``consistent`` (possible) or ``violated``.

Every constraint becomes atoms ``form op rhs`` with exact Fraction rhs, then LP
rows. Bound certificates are checked in :mod:`lio_verify.cert` with Fraction
arithmetic alone: no solver is trusted.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from lio_verify.expr import Context, ExprError, canonical_unit, evaluate
from lio_verify.interval import Interval, parse_rational


class LpError(ValueError):
    pass


@dataclass(frozen=True)
class Form:
    coeffs: tuple[tuple[str, Fraction], ...]  # sorted by variable
    const: Fraction

    def at(self, x: dict[str, Fraction]) -> Fraction:
        return self.const + sum((c * x[v] for v, c in self.coeffs), Fraction(0))


@dataclass(frozen=True)
class Atom:
    form: Form
    op: str  # "<=", "<", ">=", ">"
    rhs: Fraction
    origin: str

    def holds(self, x: dict[str, Fraction]) -> bool:
        v = self.form.at(x)
        return {
            "<=": v <= self.rhs,
            "<": v < self.rhs,
            ">=": v >= self.rhs,
            ">": v > self.rhs,
        }[self.op]


def _add(a: dict[str, Fraction], b: dict[str, Fraction], k: Fraction) -> dict[str, Fraction]:
    out = dict(a)
    for v, c in b.items():
        out[v] = out.get(v, Fraction(0)) + k * c
    return {v: c for v, c in out.items() if c != 0}


def linear(expr: Any, units: dict[str, str]) -> tuple[dict[str, Fraction], Fraction, str]:
    """A linear form of unknowns: V refs, add/sub/sum/neg, and mul by an N literal."""
    if isinstance(expr, str):
        if expr.startswith("V:"):
            name = expr[2:]
            if name not in units:
                raise LpError(f"unknown variable {expr}")
            return {name: Fraction(1)}, Fraction(0), canonical_unit(units[name])
        if expr.startswith("N:"):
            num, _, unit = expr[2:].partition(":")
            return {}, parse_rational(num), canonical_unit(unit or "1")
        raise LpError(f"{expr!r} is not linear in the unknowns (use it on the right-hand side)")
    if not isinstance(expr, list) or not expr:
        raise LpError(f"bad linear expression {expr!r}")
    op, args = expr[0], expr[1:]
    parts = [linear(a, units) for a in args]
    if op in ("add", "sum", "sub"):
        if op != "sum" and len(parts) != 2:
            raise LpError(f"{op} takes two arguments")
        unit = parts[0][2]
        coeffs, const = dict(parts[0][0]), parts[0][1]
        for i, (c, k, u) in enumerate(parts[1:]):
            if u != unit:
                raise LpError(f"{op}: units differ ({unit}, {u})")
            sign = Fraction(-1) if op == "sub" else Fraction(1)
            coeffs = _add(coeffs, c, sign)
            const += sign * k
            del i
        return coeffs, const, unit
    if op == "neg" and len(parts) == 1:
        c, k, u = parts[0]
        return {v: -x for v, x in c.items()}, -k, u
    if op == "mul" and len(parts) == 2:
        (c1, k1, u1), (c2, k2, u2) = parts
        if c1 and c2:
            raise LpError("a product of two unknowns is not linear")
        if c2:  # literal * form
            (c1, k1, u1), (c2, k2, u2) = (c2, k2, u2), (c1, k1, u1)
        from lio_verify.expr import unit_mul

        return {v: x * k2 for v, x in c1.items()}, k1 * k2, unit_mul(u1, u2)
    raise LpError(f"operator {op!r} is not allowed in a linear form")


def _form(coeffs: dict[str, Fraction], const: Fraction) -> Form:
    return Form(tuple(sorted(coeffs.items())), const)


def _within(form: Form, iv: Interval, origin: str) -> list[Atom]:
    return [
        Atom(form, ">=" if iv.lo_closed else ">", iv.lo, origin),
        Atom(form, "<=" if iv.hi_closed else "<", iv.hi, origin),
    ]


def has_unknowns(c: dict[str, Any]) -> bool:
    def walk(e: Any) -> bool:
        if isinstance(e, str):
            return e.startswith("V:")
        return isinstance(e, list) and any(walk(x) for x in e[1:])

    return bool(c.get("items")) or walk(c.get("lhs"))


def atoms(c: dict[str, Any], units: dict[str, str], ctx: Context) -> list[Atom]:
    """The atoms of one constraint with unknowns."""
    kind, cid = c["kind"], c["id"]
    items = [i[2:] if i.startswith("V:") else i for i in c.get("items", [])]
    for v in items:
        if v not in units:
            raise LpError(f"{cid}: unknown variable {v}")
    if kind == "ordered_desc":
        return [
            Atom(_form({a: Fraction(1), b: Fraction(-1)}, Fraction(0)), ">=", Fraction(0), cid)
            for a, b in itertools.pairwise(items)
        ]
    if kind == "positive":
        return [Atom(_form({v: Fraction(1)}, Fraction(0)), ">", Fraction(0), cid) for v in items]
    try:
        rhs, ru = evaluate(c["rhs"], ctx)
    except ExprError as e:
        raise LpError(f"{cid}: {e}") from e
    if kind == "sum_eq":
        us = {canonical_unit(units[v]) for v in items}
        if us != {ru}:
            raise LpError(f"{cid}: units {us} != {ru}")
        return _within(_form({v: Fraction(1) for v in items}, Fraction(0)), rhs, cid)
    coeffs, const, lu = linear(c["lhs"], units)
    if lu != ru:
        raise LpError(f"{cid}: lhs unit {lu} != rhs unit {ru}")
    form = _form(coeffs, const)
    if kind == "eq_within":
        return _within(form, rhs, cid)
    if kind == "le":
        return [Atom(form, "<=" if rhs.hi_closed else "<", rhs.hi, cid)]
    if kind == "ge":
        return [Atom(form, ">=" if rhs.lo_closed else ">", rhs.lo, cid)]
    raise LpError(f"{cid}: unknown constraint kind {kind!r}")


def data_check(c: dict[str, Any], ctx: Context) -> str:
    """A constraint without unknowns: entailed, consistent or violated."""
    lhs, lu = evaluate(c["lhs"], ctx)
    rhs, ru = evaluate(c["rhs"], ctx)
    if lu != ru:
        raise LpError(f"{c['id']}: units {lu} != {ru}")
    kind = c["kind"]
    if kind == "le":  # x <= y for x in lhs, y in rhs
        if lhs.hi <= rhs.lo:
            return "entailed"
        if lhs.lo > rhs.hi or (lhs.lo == rhs.hi and not (lhs.lo_closed and rhs.hi_closed)):
            return "violated"
        return "consistent"
    if kind == "ge":
        return data_check({**c, "kind": "le", "lhs": c["rhs"], "rhs": c["lhs"]}, ctx)
    if kind == "eq_within":
        if lhs.is_subset(rhs):
            return "entailed"
        return "consistent" if lhs.intersect(rhs) is not None else "violated"
    raise LpError(f"{c['id']}: {kind} needs unknowns")


# -------------------------------------------------------------- LP rows
LpRow = tuple[list[Fraction], Fraction, bool, str]  # a, rhs, strict, origin


def rows_of(all_atoms: list[Atom], names: list[str]) -> list[LpRow]:
    """Atoms ``form op rhs`` as rows ``a . x <= rhs`` (or ``<``) over ``names``, in order."""
    out: list[LpRow] = []
    for at in all_atoms:
        coef = dict(at.form.coeffs)
        a = [coef.get(n, Fraction(0)) for n in names]
        rhs = at.rhs - at.form.const
        if at.op in (">=", ">"):
            a, rhs = [-v for v in a], -rhs
        out.append((a, rhs, at.op in ("<", ">"), at.origin))
    return out


def record_lp(
    constraints: list[dict[str, Any]], units: dict[str, str], ctx: Context
) -> tuple[list[str], list[LpRow]]:
    """The LP implied by a record's constraints on unknowns (variables sorted)."""
    names = sorted(units)
    all_atoms = [a for c in constraints if has_unknowns(c) for a in atoms(c, units, ctx)]
    return names, rows_of(all_atoms, names)


def check_bound(
    bound: dict[str, Any], constraints: list[dict[str, Any]], units: dict[str, str], ctx: Context
) -> list[str]:
    """Problems with a bound's certificate (empty = proven). Fail closed; no solver."""
    from lio_verify import cert
    from lio_verify.interval import IntervalError

    try:
        used = {c["id"] for c in constraints if has_unknowns(c)}
        if sorted(used) != sorted(bound["constraints"]):
            return ["does not use exactly the record's constraints on unknowns"]
        names, rows = record_lp(constraints, units, ctx)
        coeffs, const, unit = linear(bound["objective"], units)
        c = [coeffs.get(n, Fraction(0)) for n in names]
        result, runit = Interval.from_json(bound["result"])
        if runit != unit:
            return [f"result unit {runit} != objective unit {unit}"]
        return cert.check(bound["certificate"], rows, names, c, const, result)
    except (KeyError, TypeError, LpError, ExprError, IntervalError, ValueError) as e:
        return [f"cannot check: {e}"]
