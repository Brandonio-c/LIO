"""Atomic weights and element mass fractions as exact intervals.

Standard atomic weights come from the IUPAC CIAAW table, either as an interval
``[a, b]`` or as a value with a standard uncertainty in its last digits,
``40.078(4)`` = [40.074, 40.082]. Mass fractions only use ratios of atomic
weights, so the molar mass constant cancels.
"""

from __future__ import annotations

import html
import re
from fractions import Fraction

from lio_verify.interval import Interval, IntervalError

_CELL = re.compile(
    r"<td>(?P<sym>[A-Z][a-z]?)</td><td><a [^>]*>[a-z]+</a></td><td>(?P<w>[^<]*)</td>"
)
_RANGE = re.compile(r"\[(\d+\.\d+),(\d+\.\d+)\]")
_UNC = re.compile(r"(\d+)(?:\.(\d+))?\((\d+)\)")


def parse_weight(text: str) -> Interval:
    """A CIAAW standard atomic weight cell ("[1.007 84, 1.008 11]", "40.078(4)")."""
    t = re.sub(r"\s+", "", html.unescape(text)).replace("\u00a0", "")
    m = _RANGE.fullmatch(t)
    if m:
        return Interval(Fraction(m.group(1)), Fraction(m.group(2)))
    m = _UNC.fullmatch(t)
    if m:
        whole, frac, unc = m.group(1), m.group(2) or "", m.group(3)
        value = Fraction(f"{whole}.{frac}" if frac else whole)
        u = Fraction(int(unc), 10 ** len(frac))
        return Interval(value - u, value + u)
    raise IntervalError(f"not a standard atomic weight: {text!r}")


def parse_row(span_text: str) -> tuple[str, Interval]:
    """``ciaaw_row@1``: one table row's symbol and weight, from the cited span."""
    m = _CELL.fullmatch(span_text)
    if not m:
        raise IntervalError(f"not a CIAAW table row: {span_text!r}")
    return m.group("sym"), parse_weight(m.group("w"))


_PART = re.compile(r"(\d*)((?:[A-Z][a-z]?\d*)+)")
_ATOM = re.compile(r"([A-Z][a-z]?)(\d*)")


def parse_mf(mf: str) -> dict[str, int]:
    """FDA UNII molecular formula ("C6H5O7.3K.H2O") -> element counts.

    Parts are separated by "."; a leading number multiplies its part.
    """
    counts: dict[str, int] = {}
    for part in mf.split("."):
        m = _PART.fullmatch(part)
        if not m:
            raise IntervalError(f"not a UNII molecular formula: {mf!r}")
        mult = int(m.group(1) or "1")
        for el, n in _ATOM.findall(m.group(2)):
            counts[el] = counts.get(el, 0) + mult * int(n or "1")
    return dict(sorted(counts.items()))


def formula_weight(counts: dict[str, int], weights: dict[str, Interval]) -> Interval:
    total = Interval.point(0)
    for el, n in counts.items():
        total = total + weights[el] * n
    return total


def mass_fraction(element: str, counts: dict[str, int], weights: dict[str, Interval]) -> Interval:
    """Tight bounds on n*A(el) / sum(n_i*A_i): increasing in A(el), decreasing in the rest."""
    n = counts[element]
    a = weights[element]
    rest = formula_weight({k: v for k, v in counts.items() if k != element}, weights)
    lo = n * a.lo / (n * a.lo + rest.hi)
    hi = n * a.hi / (n * a.hi + rest.lo)
    return Interval(lo, hi)
