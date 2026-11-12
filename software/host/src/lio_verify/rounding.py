"""Label rounding rules (21 CFR 101.9(c)) as data, and their exact inverse.

A rule table (``composition/rules/fda_rounding_101_9.json``) gives, per nutrient,
*bands* of the true per-serving amount. Each band says how an amount in it is
declared:

- ``nearest``: to the nearest multiple of ``step``. The table's ``ties`` says
  how a value exactly halfway is rounded: ``half_up`` (21 CFR 101.9, per the
  FDA Food Labeling Guide, Appendix H: "2.5 to 2.99 g ... round up (e.g., 3 g)")
  or ``either`` (the regulation is silent, so both neighbours are allowed and
  the interval is closed at both ends);
- ``zero``: declared as 0;
- ``less_than``: declared as "less than ``limit``".

``mode`` says whether the band's display is the ``default``, an alternative the
manufacturer ``may`` use, or the only one allowed (``shall``, which overrides
the others inside its range).

:func:`forward` gives every declaration the rules allow for a true amount;
:func:`inverse` gives the exact set of true amounts that could produce a
declaration. ``x in inverse(d)`` for every ``d in forward(x)`` (tested).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import floor
from typing import Any

from lio_verify.interval import Interval, IntervalError, parse_rational, subtract, union


class RoundingError(ValueError):
    """No rule, or a declaration the rules cannot produce."""


@dataclass(frozen=True)
class Declaration:
    kind: str  # "eq" | "lt"
    value: Fraction

    @classmethod
    def parse(cls, text: str) -> Declaration:
        """``"60"`` -> eq 60, ``"<1"`` -> less than 1 (rational strings)."""
        t = text.strip()
        if t.startswith("<"):
            return cls("lt", parse_rational(t[1:].strip()))
        return cls("eq", parse_rational(t))


@dataclass(frozen=True)
class Band:
    lo: Fraction
    lo_closed: bool
    hi: Fraction | None  # None = no upper limit
    hi_closed: bool
    mode: str  # default | may | shall
    kind: str  # nearest | zero | less_than
    param: Fraction  # step (nearest) or limit (less_than); 0 for zero
    ties: str = "half_up"  # half_up | either

    def contains(self, x: Fraction) -> bool:
        above = x > self.lo or (x == self.lo and self.lo_closed)
        below = self.hi is None or x < self.hi or (x == self.hi and self.hi_closed)
        return above and below

    def bounded(self) -> Interval:
        if self.hi is None:
            raise RoundingError("a zero/less-than band must have an upper limit")
        return Interval(self.lo, self.hi, self.lo_closed, self.hi_closed)

    def clip(self, iv: Interval) -> Interval | None:
        if self.hi is None:  # [lo, infinity): only the lower end can cut
            if iv.hi < self.lo or (iv.hi == self.lo and not (iv.hi_closed and self.lo_closed)):
                return None
            return iv.intersect(Interval(self.lo, iv.hi, self.lo_closed, True))
        return iv.intersect(self.bounded())

    def displays(self, x: Fraction) -> set[Declaration]:
        if self.kind == "nearest":
            up = self.param * floor(x / self.param + Fraction(1, 2))
            out = {Declaration("eq", up)}
            if self.ties == "either" and (x / self.param + Fraction(1, 2)).denominator == 1:
                out.add(Declaration("eq", up - self.param))  # exactly halfway: either way
            return out
        if self.kind == "zero":
            return {Declaration("eq", Fraction(0))}
        return {Declaration("lt", self.param)}

    def preimage(self, d: Declaration) -> Interval | None:
        if self.kind == "nearest":
            if d.kind != "eq" or d.value % self.param != 0:
                return None
            half = self.param / 2
            return self.clip(Interval(d.value - half, d.value + half, True, self.ties == "either"))
        if self.kind == "zero":
            return self.bounded() if d == Declaration("eq", Fraction(0)) else None
        return self.bounded() if d == Declaration("lt", self.param) else None


def _band(d: dict[str, Any], ties: str) -> Band:
    disp = d["display"]
    kind = disp["kind"]
    if kind not in ("nearest", "zero", "less_than"):
        raise RoundingError(f"unknown display kind {kind!r}")
    if d["mode"] not in ("default", "may", "shall"):
        raise RoundingError(f"unknown mode {d['mode']!r}")
    param = parse_rational(disp.get("step") or disp.get("limit") or "0")
    if kind == "nearest" and param <= 0:
        raise RoundingError("nearest needs a positive step")
    return Band(
        lo=parse_rational(d["lo"]),
        lo_closed=bool(d["lo_closed"]),
        hi=None if d["hi"] is None else parse_rational(d["hi"]),
        hi_closed=bool(d["hi_closed"]),
        mode=d["mode"],
        kind=kind,
        param=param,
        ties=ties,
    )


class RoundingRules:
    def __init__(self, table: dict[str, Any]) -> None:
        self.id = f"{table['id']}@{table['version']}"
        ties = table.get("ties")
        if ties not in ("half_up", "either"):
            raise RoundingError(f"unknown tie rule {ties!r}")
        self.units: dict[str, str] = {}
        self.bands: dict[str, list[Band]] = {}
        for name, entry in table["nutrients"].items():
            self.units[name] = entry["unit"]
            self.bands[name] = [_band(b, ties) for b in entry["bands"]]

    def _get(self, nutrient: str) -> list[Band]:
        try:
            return self.bands[nutrient]
        except KeyError:
            raise RoundingError(f"no rounding rule for {nutrient!r} in {self.id}") from None

    def forward(self, nutrient: str, x: Fraction) -> set[Declaration]:
        """Every declaration the rules allow for a true amount ``x`` (>= 0)."""
        if x < 0:
            raise RoundingError("amounts are not negative")
        here = [b for b in self._get(nutrient) if b.contains(x)]
        shall = [b for b in here if b.mode == "shall"]
        return {d for b in (shall or here) for d in b.displays(x)}

    def inverse(self, nutrient: str, d: Declaration) -> Interval:
        """The exact set of true amounts that can be declared as ``d`` (one interval)."""
        bands = self._get(nutrient)
        shall = [b.bounded() for b in bands if b.mode == "shall"]
        parts: list[Interval] = []
        for b in bands:
            pre = b.preimage(d)
            if pre is None:
                continue
            pieces = [pre]
            if b.mode != "shall":
                for cut in shall:
                    pieces = [p for q in pieces for p in subtract(q, cut)]
            parts.extend(pieces)
        merged = union(parts)
        if not merged:
            raise RoundingError(f"{nutrient}: no amount is declared as {d}")
        if len(merged) > 1:
            raise RoundingError(f"{nutrient}: {d} comes from separate ranges {merged}")
        return merged[0]


def interval_for(rules: RoundingRules, nutrient: str, declared: str) -> Interval:
    try:
        return rules.inverse(nutrient, Declaration.parse(declared))
    except IntervalError as e:
        raise RoundingError(str(e)) from e
