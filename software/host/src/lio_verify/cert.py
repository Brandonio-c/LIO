"""Check LP bound certificates with Fraction arithmetic alone (no solver).

A bound's certificate holds the LP it was computed on (rows ``a . x <= rhs`` or
``a . x < rhs``, objective ``c . x + const``) and, for each end, the proof that
the end is right. The LP is first rebuilt from the record's own constraints and
must match the certificate exactly; then, with ``d = c`` for the minimum and
``d = -c`` for the maximum and ``B`` the end's bound on ``d . x``:

1. dual: ``y >= 0`` and ``sum y_i a_i = -d``. For every point of the closed
   system ``d . x = -sum y_i (a_i . x) >= -sum y_i rhs_i``; that must equal B.
2. attained end: the witness satisfies every row (strict rows strictly) and
   ``d . witness = B``.
3. open end: the witness satisfies the closed rows with ``d . witness = B``; the
   interior point satisfies every row strictly (so points between them come
   arbitrarily close to B: B is the infimum); and the Motzkin vector ``z >= 0``
   (rows, then the objective row) has ``sum z_i a_i + z_obj d = 0``,
   ``sum of strict z_i > 0`` and ``sum z_i rhs_i + z_obj B <= 0``, so no point of
   the strict system has ``d . x <= B``.

Then the stated result must be ``[B + const`` (min) and ``-B + const]`` (max) with
each end closed exactly when attained.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from lio_verify.interval import Interval, IntervalError, parse_rational


class CertError(ValueError):
    pass


def _vec(xs: Any, n: int, what: str) -> list[Fraction]:
    if not isinstance(xs, list) or len(xs) != n:
        raise CertError(f"{what}: expected {n} rationals")
    return [parse_rational(x) for x in xs]


def _point(p: Any, names: list[str], what: str) -> list[Fraction]:
    if not isinstance(p, dict) or sorted(p) != sorted(names):
        raise CertError(f"{what}: must give exactly the variables {names}")
    return [parse_rational(p[n]) for n in names]


def _dot(a: list[Fraction], x: list[Fraction]) -> Fraction:
    return sum((u * v for u, v in zip(a, x, strict=True)), Fraction(0))


Row = tuple[list[Fraction], Fraction, bool]  # a, rhs, strict


def _check_end(
    end: dict[str, Any], rows: list[Row], names: list[str], d: list[Fraction]
) -> tuple[Fraction, bool]:
    n = len(names)
    b = parse_rational(end["bound"])
    y = _vec(end["dual"], len(rows), "dual")
    if any(v < 0 for v in y):
        raise CertError("dual has a negative entry")
    comb = [sum((y[i] * rows[i][0][j] for i in range(len(rows))), Fraction(0)) for j in range(n)]
    if comb != [-v for v in d]:
        raise CertError("dual does not reproduce the objective (G^T y != -d)")
    if -sum((y[i] * rows[i][1] for i in range(len(rows))), Fraction(0)) != b:
        raise CertError("dual bound does not equal the stated bound")
    w = _point(end["witness"], names, "witness")
    if _dot(d, w) != b:
        raise CertError("witness does not reach the bound")
    attained = end["attained"]
    if attained is True:
        if any(_dot(a, w) > rhs or (strict and _dot(a, w) == rhs) for a, rhs, strict in rows):
            raise CertError("witness violates a constraint")
        return b, True
    if attained is not False:
        raise CertError("attained must be true or false")
    if any(_dot(a, w) > rhs for a, rhs, _ in rows):
        raise CertError("witness violates a closed constraint")
    xi = _point(end["interior"], names, "interior")
    if any(_dot(a, xi) >= rhs if strict else _dot(a, xi) > rhs for a, rhs, strict in rows):
        raise CertError("interior point is not strictly feasible")
    z = _vec(end["motzkin"], len(rows) + 1, "motzkin")
    if any(v < 0 for v in z):
        raise CertError("Motzkin vector has a negative entry")
    zsum = [
        sum((z[i] * rows[i][0][j] for i in range(len(rows))), Fraction(0)) + z[-1] * d[j]
        for j in range(n)
    ]
    if any(v != 0 for v in zsum):
        raise CertError("Motzkin combination is not zero")
    if sum((z[i] for i in range(len(rows)) if rows[i][2]), Fraction(0)) <= 0:
        raise CertError("Motzkin vector puts no weight on a strict row")
    if sum((z[i] * rows[i][1] for i in range(len(rows))), Fraction(0)) + z[-1] * b > 0:
        raise CertError("Motzkin right-hand side is positive")
    return b, False


def check(
    cert: dict[str, Any],
    expected_rows: list[tuple[list[Fraction], Fraction, bool, str]],
    names: list[str],
    c: list[Fraction],
    const: Fraction,
    result: Interval,
) -> list[str]:
    """Problems with a bound certificate (empty: the stated interval is proven)."""
    try:
        lp = cert["lp"]
        if lp["variables"] != names:
            return ["certificate LP has different variables from the record"]
        rows: list[Row] = []
        got = []
        for r in lp["rows"]:
            if r["sense"] not in ("<=", "<"):
                return [f"bad row sense {r['sense']!r}"]
            a = _vec(r["a"], len(names), "row")
            rows.append((a, parse_rational(r["rhs"]), r["sense"] == "<"))
            got.append((a, parse_rational(r["rhs"]), r["sense"] == "<", r["origin"]))
        if got != expected_rows:
            return ["the certificate's LP is not the LP of the record's constraints"]
        if (
            _vec(lp["objective"]["c"], len(names), "objective") != c
            or parse_rational(lp["objective"]["const"]) != const
        ):
            return ["the certificate's objective is not the bound's objective"]
        lo_b, lo_att = _check_end(cert["min"], rows, names, c)
        hi_b, hi_att = _check_end(cert["max"], rows, names, [-v for v in c])
        lo, hi = lo_b + const, -hi_b + const
        if parse_rational(cert["min"]["value"]) != lo or parse_rational(cert["max"]["value"]) != hi:
            return ["end values do not follow from the bounds"]
        proven = Interval(lo, hi, lo_att, hi_att)
        if proven != result:
            return [f"result {result} is not the proven {proven}"]
    except (CertError, IntervalError, KeyError, TypeError) as e:
        return [str(e)]
    return []


def check_feasible(rows: list[Row], names: list[str], witness: Any) -> list[str]:
    """A point that satisfies every row (strict ones strictly): the constraints agree."""
    try:
        x = _point(witness, names, "feasibility witness")
    except (CertError, IntervalError) as e:
        return [str(e)]
    bad = [
        i
        for i, (a, rhs, strict) in enumerate(rows)
        if (_dot(a, x) >= rhs if strict else _dot(a, x) > rhs)
    ]
    return [f"feasibility witness violates rows {bad}"] if bad else []
