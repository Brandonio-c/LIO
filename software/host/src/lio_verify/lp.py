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

Every constraint becomes atoms ``form op rhs`` with exact Fraction rhs. Witnesses
are checked by exact substitution (no solver); the unsat checks use z3 over the
reals, which is exact for linear real arithmetic.
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


# --------------------------------------------------------------------- z3 side
def z3_problem(
    all_atoms: list[Atom], names: list[str], ctx: Any = None
) -> tuple[Any, dict[str, Any]]:
    """z3 constraints in context ``ctx`` (use a fresh ``z3.Context()`` per problem:
    z3's shared default context keeps state between solves, so results would depend on
    what was solved before)."""
    zv = {n: _z3().Real(n, ctx) for n in names}
    out = []
    for a in all_atoms:
        lhs = z3_form(a.form, zv, ctx)
        r = _z3().RealVal(str(a.rhs), ctx)
        out.append({"<=": lhs <= r, "<": lhs < r, ">=": lhs >= r, ">": lhs > r}[a.op])
    return out, zv


def _z3() -> Any:
    import z3

    return z3


def z3_form(form: Form, zv: dict[str, Any], ctx: Any = None) -> Any:
    z3 = _z3()
    out = z3.RealVal(str(form.const), ctx)
    for v, c in form.coeffs:
        out = out + z3.RealVal(str(c), ctx) * zv[v]
    return out


def z3_unsat(constraints: list[Any], extra: Any, ctx: Any = None) -> bool:
    import z3

    s = z3.Solver(ctx=ctx)
    s.add(*constraints, extra)
    r = s.check()
    if r == z3.unknown:
        raise LpError("z3 returned unknown")
    return bool(r == z3.unsat)


def model_value(model: Any, var: Any) -> Fraction:
    v = model.eval(var, model_completion=True)
    return Fraction(v.as_fraction())


def check_bound(
    bound: dict[str, Any], constraints: list[dict[str, Any]], units: dict[str, str], ctx: Context
) -> list[str]:
    """Problems with a bound's certificate (empty = proven). Fail closed."""
    from lio_verify.interval import IntervalError

    problems: list[str] = []
    try:
        used = {c["id"]: c for c in constraints}
        missing = [cid for cid in bound["constraints"] if cid not in used]
        if missing:
            return [f"cites unknown constraints {missing}"]
        all_with = [c for c in constraints if has_unknowns(c)]
        if sorted(c["id"] for c in all_with) != sorted(bound["constraints"]):
            problems.append("does not use exactly the record's constraints on unknowns")
        atoms_all = [a for c in all_with for a in atoms(c, units, ctx)]
        coeffs, const, unit = linear(bound["objective"], units)
        obj = _form(coeffs, const)
        result, runit = Interval.from_json(bound["result"])
        if runit != unit:
            problems.append(f"result unit {runit} != objective unit {unit}")
        cert = bound["certificate"]
        names = sorted(units)
        for end, value, closed in (("min", result.lo, result.lo_closed),
                                   ("max", result.hi, result.hi_closed)):  # fmt: skip
            e = cert[end]
            if parse_rational(e["value"]) != value or e["attained"] != closed:
                problems.append(f"{end}: certificate does not match the result")
                continue
            w = {n: parse_rational(e["witness"][n]) for n in names}
            bad = [a.origin for a in atoms_all if not a.holds(w)]
            if bad:
                problems.append(f"{end} witness violates {sorted(set(bad))}")
            at = obj.at(w)
            if closed and at != value:
                problems.append(f"{end} witness does not reach {value}")
            if not closed:
                gap = parse_rational(e["gap"])
                inside = value < at < value + gap if end == "min" else value - gap < at < value
                if not inside:
                    problems.append(f"{end} witness is not within the stated gap")
        import z3

        zctx = z3.Context()
        zc, zv = z3_problem(atoms_all, names, zctx)
        zo = z3_form(obj, zv, zctx)
        lo, hi = z3.RealVal(str(result.lo), zctx), z3.RealVal(str(result.hi), zctx)
        below = zo < lo if result.lo_closed else zo <= lo
        above = zo > hi if result.hi_closed else zo >= hi
        if not z3_unsat(zc, below, zctx):
            problems.append("a feasible point lies below the stated minimum")
        if not z3_unsat(zc, above, zctx):
            problems.append("a feasible point lies above the stated maximum")
    except (KeyError, TypeError, LpError, ExprError, IntervalError, ValueError) as e:
        problems.append(f"cannot check: {e}")
    return problems
