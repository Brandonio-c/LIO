"""Exact bounds on unknown ingredient amounts, with certificates (spec §5, §3.3).

For a linear objective over the record's unknowns:

1. minimise and maximise it over the closure of the constraints (non-strict
   inequalities) with z3's exact rational optimiser;
2. if the strict system reaches that value, the end is closed and the model is
   the witness; otherwise the end is open and the certificate gives a witness
   within a stated gap of it (for a non-empty polyhedron the closure of the
   strict set is the closed set, so the closure optimum is the infimum);
3. the verifier re-checks each witness by exact substitution and re-runs z3 on
   "objective beyond the end" (must be unsat).
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Any

from lio_verify.interval import Interval, format_rational
from lio_verify.lp import Atom, Form, LpError, model_value, z3_form, z3_problem

GAP = Fraction(1, 10**6)


def _closure(a: Atom) -> Atom:
    return replace(a, op={"<": "<=", ">": ">="}.get(a.op, a.op))


def _witness(model: Any, zv: dict[str, Any]) -> dict[str, str]:
    return {n: format_rational(model_value(model, v)) for n, v in sorted(zv.items())}


def solver_version() -> str:
    import z3

    return f"z3@{z3.get_version_string()}"


def bound(atoms: list[Atom], names: list[str], objective: Form) -> tuple[Interval, dict[str, Any]]:
    import z3

    zctx = z3.Context()  # fresh per bound: results must not depend on earlier solves
    strict, zv = z3_problem(atoms, names, zctx)
    closed, _ = z3_problem([_closure(a) for a in atoms], names, zctx)
    obj = z3_form(objective, zv, zctx)
    s = z3.Solver(ctx=zctx)
    s.add(*strict)
    if s.check() != z3.sat:
        raise LpError("the constraints contradict each other (data conflict)")
    ends: dict[str, dict[str, Any]] = {}
    values: dict[str, Fraction] = {}
    for end in ("lo", "hi"):
        opt = z3.Optimize(ctx=zctx)
        opt.add(*closed)
        h = opt.minimize(obj) if end == "lo" else opt.maximize(obj)
        if opt.check() != z3.sat:
            raise LpError("optimiser failed")
        bound_val = opt.lower(h) if end == "lo" else opt.upper(h)
        if "oo" in str(bound_val) or "epsilon" in str(bound_val):
            raise LpError(f"{end}: unbounded objective ({bound_val})")
        v = model_value(opt.model(), obj)  # the closure optimum is attained by the model
        values[end] = v
        exact = z3.Solver(ctx=zctx)
        exact.add(*strict, obj == z3.RealVal(str(v), zctx))
        if exact.check() == z3.sat:
            ends[end] = {"value": format_rational(v), "attained": True,
                         "witness": _witness(exact.model(), zv)}  # fmt: skip
            continue
        near = z3.Solver(ctx=zctx)
        target = v + GAP if end == "lo" else v - GAP
        near.add(
            *strict,
            obj < z3.RealVal(str(target), zctx)
            if end == "lo"
            else obj > z3.RealVal(str(target), zctx),
        )
        if near.check() != z3.sat:
            raise LpError(f"{end}: no point near the closure optimum")
        ends[end] = {"value": format_rational(v), "attained": False, "gap": format_rational(GAP),
                     "witness": _witness(near.model(), zv)}  # fmt: skip
    iv = Interval(values["lo"], values["hi"], ends["lo"]["attained"], ends["hi"]["attained"])
    cert = {
        "min": ends["lo"],
        "max": ends["hi"],
        "infeasibility_proofs": {
            "method": "z3 over the reals: constraints and (objective beyond the end) is unsat",
            "below_min": "objective < min" if ends["lo"]["attained"] else "objective <= min",
            "above_max": "objective > max" if ends["hi"]["attained"] else "objective >= max",
        },
    }
    return iv, cert
