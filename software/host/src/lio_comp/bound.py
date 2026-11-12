"""Exact bounds on unknown amounts, with solver-independent certificates (plan WP6).

The constraints on unknowns become rows ``G x <= h`` or ``G x < h`` (``>=`` rows are
negated). For a linear objective ``c . x + k`` each end of the range comes with:

- ``dual``: y >= 0 with ``G^T y = -d`` (d = c for the minimum, -c for the maximum):
  then ``d . x >= -h . y`` for every point of the closed system, so the bound holds;
- if the end is reached: ``witness``, a point of the (strict) system at the bound;
- if not: ``witness``, a point of the closed system at the bound, ``interior``, a
  point satisfying every row strictly, which together show the bound is the
  infimum, and ``motzkin``, z >= 0 over the rows plus the objective row with
  ``sum z_i G_i + z_obj d = 0``, ``sum of strict z_i > 0`` and
  ``sum z_i h_i + z_obj B <= 0``, which shows no strict point reaches the bound.

All of it is checked by ``lio_verify.cert`` with Fraction arithmetic alone. The
values are computed by the exact simplex in :mod:`lio_comp.simplex`.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from lio_comp.simplex import solve, solve_free
from lio_verify.interval import Interval, format_rational
from lio_verify.lp import Atom, Form, LpError
from lio_verify.lp import rows_of as lp_rows

SOLVER = "lio_comp.simplex@1 (exact Fraction, Bland's rule)"


@dataclass(frozen=True)
class Row:
    a: tuple[Fraction, ...]
    rhs: Fraction
    strict: bool
    origin: str


def rows_of(atoms: list[Atom], names: list[str]) -> list[Row]:
    """The verifier's own row construction (one definition for both sides)."""
    return [Row(tuple(a), rhs, strict, o) for a, rhs, strict, o in lp_rows(atoms, names)]


def _fmt(v: list[Fraction] | tuple[Fraction, ...]) -> list[str]:
    return [format_rational(x) for x in v]


def _point(names: list[str], x: tuple[Fraction, ...]) -> dict[str, str]:
    return {n: format_rational(v) for n, v in zip(names, x, strict=True)}


def _strict_point(
    rows: list[Row], n: int, eq: tuple[list[Fraction], Fraction] | None
) -> tuple[Fraction, ...] | None:
    """A point satisfying every strict row strictly (and ``eq`` if given), or None.
    Maximise t with strict rows ``a.x + t <= h`` and ``t <= 1``."""
    if not any(r.strict for r in rows):
        g = [list(r.a) for r in rows]
        res = solve_free([Fraction(0)] * n, g, [r.rhs for r in rows],
                         [eq[0]] if eq else None, [eq[1]] if eq else None)  # fmt: skip
        return res.x if res.status == "optimal" else None
    g = [[*r.a, Fraction(1) if r.strict else Fraction(0)] for r in rows]
    h = [r.rhs for r in rows]
    g.append([*([Fraction(0)] * n), Fraction(1)])
    h.append(Fraction(1))
    e = [[*eq[0], Fraction(0)]] if eq else None
    f = [eq[1]] if eq else None
    res = solve_free([Fraction(0)] * n + [Fraction(-1)], g, h, e, f)
    if res.status != "optimal" or res.x[-1] <= 0:
        return None
    return res.x[:-1]


def feasibility_witness(rows: list[Row], names: list[str]) -> dict[str, str]:
    x = _strict_point(rows, len(names), None)
    if x is None:
        raise LpError("the constraints contradict each other (data conflict)")
    return _point(names, x)


def _end(rows: list[Row], names: list[str], d: list[Fraction]) -> dict[str, Any]:
    n = len(names)
    g = [list(r.a) for r in rows]
    h = [r.rhs for r in rows]
    closure = solve_free(d, g, h)
    if closure.status != "optimal":
        raise LpError(f"objective is {closure.status} on the constraints")
    bound = closure.value
    # dual: min h.y  s.t.  G^T y = -d, y >= 0
    gt = [[g[i][j] for i in range(len(rows))] for j in range(n)]
    dual = solve(h, gt, [-v for v in d])
    if dual.status != "optimal" or -dual.value != bound:
        raise LpError("no dual certificate matches the optimum (should not happen)")
    end: dict[str, Any] = {"bound": format_rational(bound), "dual": _fmt(dual.x)}
    reach = _strict_point(rows, n, (d, bound))
    if reach is not None:
        end.update(attained=True, witness=_point(names, reach))
        return end
    # Motzkin: z >= 0 (rows, then the objective row d.x <= bound), [G; d]^T z = 0,
    # sum of strict z = 1, minimise h.z + bound z_obj (must be <= 0)
    m = len(rows)
    cols = [list(r.a) for r in rows] + [list(d)]
    a_eq = [[cols[i][j] for i in range(m + 1)] for j in range(n)]
    a_eq.append([Fraction(int(rows[i].strict)) if i < m else Fraction(0) for i in range(m + 1)])
    b_eq = [Fraction(0)] * n + [Fraction(1)]
    mz = solve([*h, bound], a_eq, b_eq)
    if mz.status != "optimal" or mz.value > 0:
        raise LpError("neither a reaching point nor a Motzkin certificate (should not happen)")
    interior = _strict_point(rows, n, None)
    if interior is None:
        raise LpError("no strictly feasible point")
    end.update(attained=False, witness=_point(names, closure.x), interior=_point(names, interior),
               motzkin=_fmt(mz.x))  # fmt: skip
    return end


def bound(atoms: list[Atom], names: list[str], objective: Form) -> tuple[Interval, dict[str, Any]]:
    rows = rows_of(atoms, names)
    coef = dict(objective.coeffs)
    c = [coef.get(nm, Fraction(0)) for nm in names]
    feasibility_witness(rows, names)
    lo_end = _end(rows, names, c)
    hi_end = _end(rows, names, [-v for v in c])
    k = objective.const
    lo = Fraction(lo_end["bound"]) + k
    hi = -Fraction(hi_end["bound"]) + k
    for e, v in ((lo_end, lo), (hi_end, hi)):
        e["value"] = format_rational(v)
    cert = {
        "lp": {
            "variables": list(names),
            "rows": [
                {
                    "a": _fmt(r.a),
                    "sense": "<" if r.strict else "<=",
                    "rhs": format_rational(r.rhs),
                    "origin": r.origin,
                }
                for r in rows
            ],
            "objective": {"c": _fmt(c), "const": format_rational(k)},
        },
        "min": lo_end,
        "max": hi_end,
    }
    return Interval(lo, hi, lo_end["attained"], hi_end["attained"]), cert


def solver_version() -> str:
    return SOLVER
