"""Exact evaluation of derivation expressions (spec §3.3), with units.

An expression is a reference or ``[op, arg, ...]``:

- ``F1``, ``D2``: a fact's or derivation's interval and unit;
- ``C:<table>.<path>``: a cited constant from a pinned rule table;
- ``M:<element>:<substance>``: the element's mass fraction in the substance's
  verified formula (unit ``1``), from the pinned atomic weights;
- ``N:<rational>[:<unit>]``: an exact literal (e.g. ``N:100:g``);
- ``U:<unit>``: a unit, only as the target of ``convert``.

Operators: add, sub, mul, div, neg, min, max, sum, hull, convert,
rescale_basis (``[rescale_basis, X, serving_mass, N:100:g]`` = X * 100 g /
serving mass). Arithmetic is interval arithmetic over Fraction; dividing by an
interval that contains 0 is an error.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from lio_verify.interpret import constant, element_fraction, literal, table
from lio_verify.interval import Interval, IntervalError, parse_rational


class ExprError(ValueError):
    pass


# ----------------------------------------------------------------------- units
def _parse_unit(u: str) -> Counter[str]:
    c: Counter[str] = Counter()
    if u in ("", "1"):
        return c
    num, _, den = u.partition("/")
    for t in num.split("*"):
        if t and t != "1":
            c[t] += 1
    for t in den.split("*") if den else []:
        if t:
            c[t] -= 1
    return c


def _format_unit(c: Counter[str]) -> str:
    num = sorted(k for k, v in c.items() for _ in range(v) if v > 0)
    den = sorted(k for k, v in c.items() for _ in range(-v) if v < 0)
    n = "*".join(num) or "1"
    return f"{n}/{'*'.join(den)}" if den else n


def unit_mul(a: str, b: str, sign: int = 1) -> str:
    c = _parse_unit(a)
    for k, v in _parse_unit(b).items():
        c[k] += sign * v
    return _format_unit(Counter({k: v for k, v in c.items() if v}))


def canonical_unit(u: str) -> str:
    return unit_mul(u, "1")


# ----------------------------------------------------------------------- context
@dataclass
class Context:
    values: dict[str, tuple[Interval, str]]
    tables: dict[str, dict[str, Any]]
    versions: dict[str, int]
    formulas: dict[str, str] = field(default_factory=dict)

    def conversion(self, src: str, dst: str) -> Interval:
        units = table(self.tables, "units", self.versions.get("units", -1))
        for group in ("mass_to_g", "energy_to_kcal"):
            g = units[group]
            if src in g and dst in g:
                return Interval.point(parse_rational(g[src]) / parse_rational(g[dst]))
        raise ExprError(f"no conversion from {src} to {dst}")


def _same(op: str, us: list[str]) -> str:
    cu = {canonical_unit(u) for u in us}
    if len(cu) != 1:
        raise ExprError(f"{op}: units differ {us}")
    return cu.pop()


def evaluate(expr: Any, ctx: Context) -> tuple[Interval, str]:
    try:
        return _eval(expr, ctx)
    except IntervalError as e:
        raise ExprError(str(e)) from e


def _ref(ref: str, ctx: Context) -> tuple[Interval, str]:
    if ref.startswith("C:"):
        iv, u = constant(ref, ctx.tables, ctx.versions)
        return iv, canonical_unit(u)
    if ref.startswith("N:"):
        iv, u = literal(ref)
        return iv, canonical_unit(u)
    if ref.startswith("M:"):
        _, el, sub = ref.split(":")
        if sub not in ctx.formulas:
            raise ExprError(f"{ref}: no verified formula for {sub}")
        return element_fraction(el, ctx.formulas[sub], ctx.tables, ctx.versions), "1"
    if ref.startswith(("U:", "V:")):
        raise ExprError(f"{ref} is not a value")
    if ref not in ctx.values:
        raise ExprError(f"unknown reference {ref!r}")
    iv, u = ctx.values[ref]
    return iv, canonical_unit(u)


_BIN: dict[str, Callable[[Interval, Interval], Interval]] = {
    "min": lambda a, b: a.min(b),
    "max": lambda a, b: a.max(b),
    "hull": lambda a, b: a.hull(b),
}


def _eval(expr: Any, ctx: Context) -> tuple[Interval, str]:
    if isinstance(expr, str):
        return _ref(expr, ctx)
    if not isinstance(expr, list) or not expr or not isinstance(expr[0], str):
        raise ExprError(f"bad expression {expr!r}")
    op, args = expr[0], expr[1:]
    if op == "convert":
        if len(args) != 2 or not isinstance(args[1], str) or not args[1].startswith("U:"):
            raise ExprError("convert needs [convert, X, U:<unit>]")
        iv, u = _eval(args[0], ctx)
        dst = args[1][2:]
        return iv * ctx.conversion(u, dst), dst
    if op == "rescale_basis":
        if len(args) != 3:
            raise ExprError("rescale_basis needs [rescale_basis, X, serving_mass, N:<basis>]")
        x, ux = _eval(args[0], ctx)
        m, um = _eval(args[1], ctx)
        n, un = _eval(args[2], ctx)
        _same("rescale_basis", [um, un])
        return x * n / m, ux
    vals = [_eval(a, ctx) for a in args]
    ivs = [v for v, _ in vals]
    us = [u for _, u in vals]
    if op == "neg":
        if len(ivs) != 1:
            raise ExprError("neg takes one argument")
        return -ivs[0], us[0]
    if op in ("add", "sum"):
        if op == "add" and len(ivs) != 2:
            raise ExprError("add takes two arguments")
        total = ivs[0]
        for v in ivs[1:]:
            total = total + v
        return total, _same(op, us)
    if len(ivs) != 2:
        raise ExprError(f"{op} takes two arguments")
    a, b = ivs
    if op == "sub":
        return a - b, _same(op, us)
    if op == "mul":
        return a * b, unit_mul(us[0], us[1])
    if op == "div":
        return a / b, unit_mul(us[0], us[1], -1)
    if op in _BIN:
        return _BIN[op](a, b), _same(op, us)
    raise ExprError(f"unknown operator {op!r}")
