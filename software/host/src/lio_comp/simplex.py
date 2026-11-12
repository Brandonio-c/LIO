"""An exact linear-programming solver over :class:`fractions.Fraction`.

Two-phase dense tableau simplex with Bland's rule (no cycling), for problems in
standard form::

    minimise  c . x   subject to   A x = b,   x >= 0.

The bound problems in composition records have tens of variables, so a dense
tableau is fine; :data:`MAX_SIZE` makes larger problems fail loudly. Every
number stays a Fraction: the answers are exact, and the certificates built from
them are checked by the verifier with Fraction arithmetic alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

MAX_SIZE = 400  # rows + columns


class SimplexError(RuntimeError):
    pass


@dataclass(frozen=True)
class Result:
    status: str  # "optimal" | "infeasible" | "unbounded"
    x: tuple[Fraction, ...] = ()
    value: Fraction = Fraction(0)


def _pivot(t: list[list[Fraction]], r: int, c: int) -> None:
    piv = t[r][c]
    t[r] = [v / piv for v in t[r]]
    for i in range(len(t)):
        if i != r and t[i][c] != 0:
            f = t[i][c]
            t[i] = [a - f * b for a, b in zip(t[i], t[r], strict=True)]


def _run(t: list[list[Fraction]], basis: list[int], ncols: int, allowed: list[bool]) -> str:
    """Minimise the objective in the last row of ``t`` (reduced costs; value in the last
    column, negated). Bland's rule: entering = lowest index with negative reduced cost;
    leaving = lowest basis index among the ratio-test ties."""
    m = len(t) - 1
    while True:
        enter = next((j for j in range(ncols) if allowed[j] and t[m][j] < 0), None)
        if enter is None:
            return "optimal"
        best: tuple[Fraction, int, int] | None = None
        for i in range(m):
            a = t[i][enter]
            if a > 0:
                ratio = t[i][-1] / a
                key = (ratio, basis[i], i)
                if best is None or key < best:
                    best = key
        if best is None:
            return "unbounded"
        _pivot(t, best[2], enter)
        basis[best[2]] = enter


def solve(c: list[Fraction], a: list[list[Fraction]], b: list[Fraction]) -> Result:
    """Minimise c.x subject to A x = b, x >= 0 (exact)."""
    m, n = len(a), len(c)
    if any(len(row) != n for row in a) or len(b) != m:
        raise SimplexError("inconsistent LP dimensions")
    if m + n > MAX_SIZE:
        raise SimplexError(f"LP too large for the exact dense simplex ({m} rows, {n} columns)")
    rows = [list(r) for r in a]
    rhs = list(b)
    for i in range(m):  # b >= 0
        if rhs[i] < 0:
            rows[i] = [-v for v in rows[i]]
            rhs[i] = -rhs[i]
    # Phase 1: artificial variables n .. n+m-1
    total = n + m
    t = [rows[i] + [Fraction(int(j == i)) for j in range(m)] + [rhs[i]] for i in range(m)]
    obj = [Fraction(0)] * n + [Fraction(1)] * m + [Fraction(0)]
    for i in range(m):  # make artificials basic: subtract their rows from the cost row
        obj = [o - v for o, v in zip(obj, t[i], strict=True)]
    t.append(obj)
    basis = list(range(n, n + m))
    _run(t, basis, total, [True] * total)
    if t[m][-1] != 0:  # phase-1 optimum is -sum(artificials)
        return Result("infeasible")
    # Drive remaining artificials out of the basis (degenerate rows)
    for i in range(m):
        if basis[i] >= n:
            col = next((j for j in range(n) if t[i][j] != 0), None)
            if col is not None:
                _pivot(t, i, col)
                basis[i] = col
    # Phase 2: original costs, artificial columns barred
    cost = list(c) + [Fraction(0)] * m + [Fraction(0)]
    for i in range(m):
        if basis[i] < total and cost[basis[i]] != 0:
            f = cost[basis[i]]
            cost = [cv - f * tv for cv, tv in zip(cost, t[i], strict=True)]
    t[m] = cost
    status = _run(t, basis, total, [j < n for j in range(total)])
    if status != "optimal":
        return Result(status)
    x = [Fraction(0)] * n
    for i in range(m):
        if basis[i] < n:
            x[basis[i]] = t[i][-1]
    value = sum((ci * xi for ci, xi in zip(c, x, strict=True)), Fraction(0))
    return Result("optimal", tuple(x), value)


def solve_free(
    c: list[Fraction], g: list[list[Fraction]], h: list[Fraction],
    e: list[list[Fraction]] | None = None, f: list[Fraction] | None = None,
) -> Result:  # fmt: skip
    """Minimise c.x subject to G x <= h (and E x = f), x free. Returns x in the original
    variables. Free variables are split x = u - v; inequalities get slack columns."""
    n, m = len(c), len(g)
    e, f = e or [], f or []
    cols = 2 * n + m
    a: list[list[Fraction]] = []
    b: list[Fraction] = []
    for i, row in enumerate(g):
        a.append(list(row) + [-v for v in row] + [Fraction(int(j == i)) for j in range(m)])
        b.append(h[i])
    for row, rv in zip(e, f, strict=True):
        a.append(list(row) + [-v for v in row] + [Fraction(0)] * m)
        b.append(rv)
    cost = list(c) + [-v for v in c] + [Fraction(0)] * m
    if not a:
        if any(v != 0 for v in c):
            return Result("unbounded")
        return Result("optimal", tuple([Fraction(0)] * n), Fraction(0))
    r = solve(cost, a, b)
    if r.status != "optimal":
        return Result(r.status)
    x = tuple(r.x[j] - r.x[n + j] for j in range(n))
    del cols
    return Result("optimal", x, r.value)
