"""Exact intervals over :class:`fractions.Fraction` (the verified layer's arithmetic).

No binary floating point anywhere in this module. Values are serialised as
canonical rational strings ("2", "-3/4", "55/4"): lowest terms, no "+", no
leading zeros, no "-0", denominator > 1 only when needed. A non-canonical string
is rejected, so every value has exactly one spelling and bundles are
byte-identical across runs.

An :class:`Interval` is non-empty and bounded, with each end open or closed.
Arithmetic is sound and tight: the result is exactly the set
``{x op y : x in A, y in B}`` (for the operators here that set is an interval),
including which ends are attained.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

_RATIONAL = re.compile(r"-?(0|[1-9][0-9]*)(/[1-9][0-9]*)?")
_DECIMAL = re.compile(r"(0|[1-9][0-9]*)(\.[0-9]+)?")


class IntervalError(ValueError):
    """An invalid interval, rational string or operation (e.g. dividing by 0)."""


def format_rational(v: Fraction) -> str:
    return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"


def parse_rational(s: object) -> Fraction:
    """A canonical rational string -> Fraction. Anything else raises."""
    if not isinstance(s, str) or not _RATIONAL.fullmatch(s):
        raise IntervalError(f"not a rational string: {s!r}")
    v = Fraction(s)
    if format_rational(v) != s:
        raise IntervalError(f"not in canonical form: {s!r} (expected {format_rational(v)!r})")
    return v


def parse_decimal(s: str) -> Fraction:
    """A plain non-negative decimal as printed on a label ("0.5", "60", "10.2")."""
    if not _DECIMAL.fullmatch(s):
        raise IntervalError(f"not a plain decimal: {s!r}")
    return Fraction(s)


def _attained_mul(
    v: Fraction, corners: list[tuple[Fraction, bool]], a: Interval, b: Interval
) -> bool:
    if any(c == v and closed for c, closed in corners):
        return True
    # A product of 0 is also attained when either factor can be exactly 0.
    return v == 0 and (a.contains(Fraction(0)) or b.contains(Fraction(0)))


@dataclass(frozen=True, order=False)
class Interval:
    lo: Fraction
    hi: Fraction
    lo_closed: bool = True
    hi_closed: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.lo, Fraction) or not isinstance(self.hi, Fraction):
            raise IntervalError("interval ends must be Fractions")
        if self.lo > self.hi or (self.lo == self.hi and not (self.lo_closed and self.hi_closed)):
            raise IntervalError(f"empty interval: {self}")

    # ------------------------------------------------------------ construction
    @classmethod
    def point(cls, v: Fraction | int) -> Interval:
        f = Fraction(v)
        return cls(f, f)

    @classmethod
    def of(cls, v: Interval | Fraction | int) -> Interval:
        return v if isinstance(v, Interval) else cls.point(v)

    def __str__(self) -> str:
        left = "[" if self.lo_closed else "("
        right = "]" if self.hi_closed else ")"
        return f"{left}{format_rational(self.lo)}, {format_rational(self.hi)}{right}"

    # -------------------------------------------------------------- predicates
    @property
    def is_point(self) -> bool:
        return self.lo == self.hi

    def contains(self, x: Fraction) -> bool:
        above = x > self.lo or (x == self.lo and self.lo_closed)
        below = x < self.hi or (x == self.hi and self.hi_closed)
        return above and below

    def is_subset(self, other: Interval) -> bool:
        lo_ok = self.lo > other.lo or (
            self.lo == other.lo and (other.lo_closed or not self.lo_closed)
        )
        hi_ok = self.hi < other.hi or (
            self.hi == other.hi and (other.hi_closed or not self.hi_closed)
        )
        return lo_ok and hi_ok

    # --------------------------------------------------------------- arithmetic
    def __neg__(self) -> Interval:
        return Interval(-self.hi, -self.lo, self.hi_closed, self.lo_closed)

    def __add__(self, other: Interval | Fraction | int) -> Interval:
        o = Interval.of(other)
        return Interval(
            self.lo + o.lo,
            self.hi + o.hi,
            self.lo_closed and o.lo_closed,
            self.hi_closed and o.hi_closed,
        )

    __radd__ = __add__

    def __sub__(self, other: Interval | Fraction | int) -> Interval:
        return self + (-Interval.of(other))

    def __rsub__(self, other: Interval | Fraction | int) -> Interval:
        return Interval.of(other) - self

    def __mul__(self, other: Interval | Fraction | int) -> Interval:
        o = Interval.of(other)
        corners = [
            (x * y, cx and cy)
            for x, cx in ((self.lo, self.lo_closed), (self.hi, self.hi_closed))
            for y, cy in ((o.lo, o.lo_closed), (o.hi, o.hi_closed))
        ]
        lo = min(c for c, _ in corners)
        hi = max(c for c, _ in corners)
        return Interval(
            lo, hi, _attained_mul(lo, corners, self, o), _attained_mul(hi, corners, self, o)
        )

    __rmul__ = __mul__

    def reciprocal(self) -> Interval:
        if self.lo <= 0 <= self.hi:
            raise IntervalError(f"division by an interval that contains or touches 0: {self}")
        return Interval(1 / self.hi, 1 / self.lo, self.hi_closed, self.lo_closed)

    def __truediv__(self, other: Interval | Fraction | int) -> Interval:
        return self * Interval.of(other).reciprocal()

    def __rtruediv__(self, other: Interval | Fraction | int) -> Interval:
        return Interval.of(other) * self.reciprocal()

    # ------------------------------------------------------------ order, sets
    def min(self, other: Interval) -> Interval:
        """``{min(x, y)}`` over x in self, y in other."""
        lo, lo_c = _lower_end(self, other)
        if self.hi != other.hi:
            hi, hi_c = (
                (self.hi, self.hi_closed) if self.hi < other.hi else (other.hi, other.hi_closed)
            )
        else:  # min(x, y) = h needs x = y = h
            hi, hi_c = self.hi, self.hi_closed and other.hi_closed
        return Interval(lo, hi, lo_c, hi_c)

    def max(self, other: Interval) -> Interval:
        """``{max(x, y)}`` over x in self, y in other."""
        return -((-self).min(-other))

    def hull(self, other: Interval) -> Interval:
        lo, lo_c = _lower_end(self, other)
        if self.hi != other.hi:
            hi, hi_c = (
                (self.hi, self.hi_closed) if self.hi > other.hi else (other.hi, other.hi_closed)
            )
        else:
            hi, hi_c = self.hi, self.hi_closed or other.hi_closed
        return Interval(lo, hi, lo_c, hi_c)

    def intersect(self, other: Interval) -> Interval | None:
        if self.lo != other.lo:
            lo, lo_c = (
                (self.lo, self.lo_closed) if self.lo > other.lo else (other.lo, other.lo_closed)
            )
        else:
            lo, lo_c = self.lo, self.lo_closed and other.lo_closed
        if self.hi != other.hi:
            hi, hi_c = (
                (self.hi, self.hi_closed) if self.hi < other.hi else (other.hi, other.hi_closed)
            )
        else:
            hi, hi_c = self.hi, self.hi_closed and other.hi_closed
        if lo > hi or (lo == hi and not (lo_c and hi_c)):
            return None
        return Interval(lo, hi, lo_c, hi_c)

    def touches(self, other: Interval) -> bool:
        """True when the union of the two is one interval (overlap or shared end)."""
        if self.intersect(other) is not None:
            return True
        a, b = (self, other) if self.hi <= other.lo else (other, self)
        return a.hi == b.lo and (a.hi_closed or b.lo_closed)

    # ------------------------------------------------------------ serialising
    def to_json(self, unit: str) -> dict[str, Any]:
        return {
            "lo": format_rational(self.lo),
            "hi": format_rational(self.hi),
            "lo_closed": self.lo_closed,
            "hi_closed": self.hi_closed,
            "unit": unit,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> tuple[Interval, str]:
        if not isinstance(d.get("lo_closed"), bool) or not isinstance(d.get("hi_closed"), bool):
            raise IntervalError("lo_closed and hi_closed must be booleans")
        unit = d.get("unit")
        if not isinstance(unit, str):
            raise IntervalError("unit must be a string")
        return (
            cls(parse_rational(d["lo"]), parse_rational(d["hi"]), d["lo_closed"], d["hi_closed"]),
            unit,
        )


def _lower_end(a: Interval, b: Interval) -> tuple[Fraction, bool]:
    if a.lo != b.lo:
        return (a.lo, a.lo_closed) if a.lo < b.lo else (b.lo, b.lo_closed)
    return a.lo, a.lo_closed or b.lo_closed


def union(parts: Iterable[Interval]) -> list[Interval]:
    """Disjoint, sorted, merged intervals covering exactly the given parts."""
    items = sorted(parts, key=lambda i: (i.lo, not i.lo_closed))
    out: list[Interval] = []
    for it in items:
        if out and out[-1].touches(it):
            out[-1] = out[-1].hull(it)
        else:
            out.append(it)
    return out


def subtract(a: Interval, cut: Interval) -> list[Interval]:
    """``a`` minus ``cut``: zero, one or two intervals."""
    if a.intersect(cut) is None:
        return [a]
    out: list[Interval] = []
    # the part of a below cut
    if a.lo < cut.lo or (a.lo == cut.lo and a.lo_closed and not cut.lo_closed):
        left = Interval(a.lo, cut.lo, a.lo_closed, not cut.lo_closed) if a.lo < cut.lo else None
        if left is None:
            left = Interval.point(a.lo)
        out.append(left)
    # the part of a above cut
    if a.hi > cut.hi or (a.hi == cut.hi and a.hi_closed and not cut.hi_closed):
        right = Interval(cut.hi, a.hi, not cut.hi_closed, a.hi_closed) if a.hi > cut.hi else None
        if right is None:
            right = Interval.point(a.hi)
        out.append(right)
    return out
