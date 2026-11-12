"""Derivations, constraints and bounds for the golden records (spec §5).

Each derivation is evaluated exactly with :mod:`lio_verify.expr`; each bound is
solved with :mod:`lio_comp.bound`. The verifier recomputes all of it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lio_comp import bound as B
from lio_comp.record import RecordBuilder, RecordError
from lio_verify.expr import Context, evaluate
from lio_verify.interval import Interval
from lio_verify.lp import Form, LpError, atoms, data_check, has_unknowns, linear


def context(b: RecordBuilder) -> Context:
    values: dict[str, tuple[Interval, str]] = {}
    for f in b.facts:
        values[f["id"]] = Interval.from_json(f["value"])
    for d in b.derivations:
        values[d["id"]] = Interval.from_json(d["value"])
    formulas = {s["id"]: s["formula"] for s in b.substances if "formula" in s}
    versions = {t: b.tables[t]["version"] for t in b.tables}
    return Context(values, b.tables, versions, formulas)


def derive(b: RecordBuilder, did: str, quantity: str, basis: str, expr: Any,
           assumptions: tuple[str, ...] = ()) -> dict[str, Any]:  # fmt: skip
    for a in assumptions:
        if a not in b.assumptions:
            raise RecordError(f"{did}: assumption {a} not stated")
    iv, unit = evaluate(expr, context(b))
    d = {"id": did, "quantity": quantity, "basis": basis, "expr": expr,
         "assumptions": list(assumptions), "value": iv.to_json(unit)}  # fmt: skip
    b.derivations.append(d)
    return d


def variable(b: RecordBuilder, name: str, unit: str, ingredient: str | None = None) -> str:
    v: dict[str, Any] = {"name": name, "unit": unit}
    if ingredient:
        v["ingredient"] = ingredient
    b.head["variables"].append(v)
    return f"V:{name}"


def constrain(b: RecordBuilder, cid: str, kind: str, *, lhs: Any = None, rhs: Any = None,
              items: list[str] | None = None, list_rule: str | None = None,
              assumptions: tuple[str, ...] = ()) -> dict[str, Any]:  # fmt: skip
    c: dict[str, Any] = {"id": cid, "kind": kind, "assumptions": list(assumptions)}
    if lhs is not None:
        c["lhs"] = lhs
    if rhs is not None:
        c["rhs"] = rhs
    if items is not None:
        c["items"] = items
    if list_rule:
        c["list_rule"] = list_rule
    if not has_unknowns(c):
        c["status"] = data_check(c, context(b))
    b.constraints.append(c)
    return c


def units(b: RecordBuilder) -> dict[str, str]:
    return {v["name"]: v["unit"] for v in b.head.get("variables", [])}


def bound_of(b: RecordBuilder, bid: str, quantity: str, basis: str, objective: Any,
             assumptions: tuple[str, ...] = ()) -> dict[str, Any]:  # fmt: skip
    u = units(b)
    ctx = context(b)
    used = [c for c in b.constraints if has_unknowns(c)]
    all_atoms = [a for c in used for a in atoms(c, u, ctx)]
    coeffs, const, unit = linear(objective, u)
    form = Form(tuple(sorted(coeffs.items())), const)
    iv, cert = B.bound(all_atoms, sorted(u), form)
    b.head["feasibility"] = {
        "witness": B.feasibility_witness(B.rows_of(all_atoms, sorted(u)), sorted(u)),
        "method": B.SOLVER,
    }
    cert_assumptions = sorted({a for c in used for a in c["assumptions"]} | set(assumptions))
    out = {
        "id": bid, "quantity": quantity, "basis": basis, "solver": B.solver_version(),
        "objective": objective, "variables": sorted(u), "constraints": [c["id"] for c in used],
        "assumptions": cert_assumptions, "result": iv.to_json(unit), "certificate": cert,
    }  # fmt: skip
    b.bounds.append(out)
    return out


# ------------------------------------------------------------------- records
def citrucel(b: RecordBuilder) -> None:
    b.assume("A9", "modelling", "Every listed ingredient is present (amount > 0).")
    b.assume(
        "A10",
        "modelling",
        "The dose consists only of the listed ingredients and the flavors named in the SPL text (mass balance).",
    )
    derive(
        b,
        "D1",
        "sucrose_plus_maltodextrin",
        "per_serving",
        ["div", "F6", "C:atwater.constants.carbohydrate"],
        ("A3", "A4"),
    )
    derive(
        b,
        "D2",
        "calcium_phosphates",
        "per_serving",
        ["hull", ["div", "F3", "M:Ca:SUB_dcp"], ["div", "F3", "M:Ca:SUB_tcp"]],
        ("A5", "A6"),
    )
    derive(
        b,
        "D3",
        "potassium_citrate_monohydrate",
        "per_serving",
        ["div", "F4", "M:K:SUB_kcit"],
        ("A7",),
    )
    derive(
        b, "D4", "methylcellulose", "per_100g", ["rescale_basis", "F1", "F2", "N:100:g"], ("A8",)
    )
    derive(
        b,
        "D5",
        "sucrose_plus_maltodextrin",
        "per_100g",
        ["rescale_basis", "D1", "F2", "N:100:g"],
        ("A8",),
    )
    derive(b, "D6", "calcium_phosphates_g", "per_serving", ["convert", "D2", "U:g"])
    derive(b, "D7", "potassium_citrate_monohydrate_g", "per_serving", ["convert", "D3", "U:g"])

    mc = variable(b, "methylcellulose", "g", "I_active_1")
    su = variable(b, "sucrose", "g", "I_sucrose")
    md = variable(b, "maltodextrin", "g", "I_maltodextrin")
    ph = variable(b, "calcium_phosphates", "g")
    kc = variable(b, "potassium_citrate", "g", "I_potassium_citrate")
    ot = variable(b, "other_ingredients", "g")
    names = [mc, su, md, ph, kc, ot]
    constrain(b, "C1", "sum_eq", items=names, rhs="F2", assumptions=("A10",))
    constrain(b, "C2", "eq_within", lhs=mc, rhs="F1")
    constrain(b, "C3", "eq_within", lhs=["add", su, md], rhs="D1", assumptions=("A3", "A4"))
    constrain(b, "C4", "eq_within", lhs=ph, rhs="D6", assumptions=("A5", "A6"))
    constrain(b, "C5", "eq_within", lhs=kc, rhs="D7", assumptions=("A7",))
    constrain(b, "C6", "positive", items=names, assumptions=("A9",))
    bound_of(b, "B1", "sucrose", "per_serving", su)
    bound_of(b, "B2", "maltodextrin", "per_serving", md)
    bound_of(b, "B3", "other_ingredients", "per_serving", ot)
    b.note(
        "OTC inactive ingredients are listed alphabetically (21 CFR 201.66(c)(8)): no weight-order constraint is used."
    )


def jif(b: RecordBuilder) -> None:
    b.assume("J7", "modelling", "Every listed ingredient is present (amount > 0).")
    b.assume(
        "J8", "modelling", "The serving consists only of the listed ingredients (mass balance)."
    )
    b.assume(
        "J9",
        "interpretation",
        "Ingredients after 'Contains 2% Or Less Of:' are each at most 2 % of the food by weight (21 CFR 101.4(a)(2)); the ones before it are in descending order of weight.",
        "list_ordering@1",
    )
    derive(
        b,
        "D1",
        "salt_upper",
        "per_serving",
        ["convert", ["div", "F_sodium", "M:Na:SUB_nacl"], "U:g"],
        ("J5",),
    )
    derive(
        b, "D2", "two_percent_of_serving", "per_serving", ["mul", "F_serving", "N:1/50"], ("J9",)
    )
    pn = variable(b, "roasted_peanuts", "g", "I1")
    su = variable(b, "sugar", "g", "I2")
    hv = variable(b, "hydrogenated_vegetable_oils", "g", "I3")
    sa = variable(b, "salt", "g", "I4")
    mo = variable(b, "molasses", "g", "I5")
    names = [pn, su, hv, sa, mo]
    constrain(b, "C1", "sum_eq", items=names, rhs="F_serving", assumptions=("J8",))
    constrain(
        b,
        "C2",
        "ordered_desc",
        items=[pn, su],
        list_rule="list_ordering@1:us_food_ingredients",
        assumptions=("J9",),
    )
    for i, v in enumerate((hv, sa, mo), start=3):
        constrain(b, f"C{i}", "le", lhs=v, rhs="D2", assumptions=("J9",))
    constrain(b, "C6", "le", lhs=su, rhs="F_total_sugars", assumptions=("J6",))
    constrain(b, "C7", "le", lhs=sa, rhs="D1", assumptions=("J5",))
    constrain(b, "C8", "positive", items=names, assumptions=("J7",))
    bound_of(b, "B1", "roasted_peanuts", "per_serving", pn)
    bound_of(b, "B2", "sugar", "per_serving", su)
    bound_of(b, "B3", "salt", "per_serving", sa)


def nutricost(b: RecordBuilder) -> None:
    derive(
        b, "D1", "magnesium_in_stated_oxide_if_pure", "per_unit", ["mul", "F_mgo", "M:Mg:SUB_mgo"]
    )
    derive(b, "D2", "magnesium_oxide_purity_implied", "per_unit", ["div", "F_mg", "D1"], ("N4",))
    constrain(b, "C1", "le", lhs="F_mg", rhs="D1", assumptions=("N4",))


def nutella(b: RecordBuilder) -> None:
    b.assume("E5", "modelling", "'Sucre' is sucrose (all sugars); 'huile de palme' is all fat.")
    b.assume(
        "E6",
        "modelling",
        "Every listed ingredient is present (amount > 0) and they make up the whole product (no moisture loss in manufacture).",
    )
    b.assume(
        "E7",
        "interpretation",
        "Ingredients are in descending order of weight (Reg. 1169/2011 Art. 18), except that ingredients under 2 % may follow in any order (Annex VII Part A); so every ingredient after milk powder (6.6 %) is at most 6.6 %.",
        "list_ordering@1",
    )
    names = [
        variable(b, n, "%", f"I{i}")
        for i, n in enumerate(
            [
                "sugar",
                "palm_oil",
                "hazelnuts",
                "fat_reduced_cocoa",
                "skimmed_milk_powder",
                "whey_powder",
                "lecithins",
                "vanillin",
            ],
            start=1,
        )
    ]
    s, p, h, c, m, w, le, v = names
    constrain(b, "C1", "sum_eq", items=names, rhs="N:100:%", assumptions=("E6",))
    constrain(b, "C2", "eq_within", lhs=h, rhs="F_quid_hazelnuts", assumptions=("E3",))
    constrain(b, "C3", "eq_within", lhs=c, rhs="F_quid_fat_reduced_cocoa", assumptions=("E3",))
    constrain(b, "C4", "eq_within", lhs=m, rhs="F_quid_skimmed_milk_powder", assumptions=("E3",))
    constrain(
        b,
        "C5",
        "ordered_desc",
        items=[s, p, h, c, m],
        list_rule="list_ordering@1:eu_food_ingredients",
        assumptions=("E7",),
    )
    for i, x in enumerate((w, le, v), start=6):
        constrain(b, f"C{i}", "le", lhs=x, rhs="F_quid_skimmed_milk_powder", assumptions=("E7",))
    constrain(
        b, "C9", "le", lhs=s, rhs=["mul", "F_total_sugars", "N:1:%/g"], assumptions=("E4", "E5")
    )
    constrain(
        b, "C10", "le", lhs=p, rhs=["mul", "F_total_fat", "N:1:%/g"], assumptions=("E4", "E5")
    )
    constrain(b, "C11", "positive", items=names, assumptions=("E6",))
    for i, (x, q) in enumerate(((s, "sugar"), (p, "palm_oil"), (w, "whey_powder")), start=1):
        bound_of(b, f"B{i}", q, "per_100g", x)


def swanson(b: RecordBuilder) -> None:
    b.assume(
        "W4",
        "modelling",
        "Each named member of the blend is present (amount > 0) and the members make up the whole blend.",
    )
    blend = next(f for f in b.facts if f["quantity"] == "row_1")
    members = [i for i in b.ingredients if i["list_id"] == "dsld_dietary" and i["position"] > 1]
    names = [variable(b, f"member_{i['position']}", "mg", i["id"]) for i in members]
    constrain(b, "C1", "sum_eq", items=names, rhs=blend["id"], assumptions=("W2", "W3", "W4"))
    constrain(b, "C2", "positive", items=names, assumptions=("W4",))
    for n, v in enumerate(names, start=1):
        bound_of(b, f"B{n}", v[2:], "per_unit", v)


DERIVE: dict[str, Callable[[RecordBuilder], None]] = {
    "swanson_lowat_blend_087614040622": swanson,
    "careone_ibuprofen_341520314643": lambda b: None,
    "citrucel_orange_300680418301": citrucel,
    "jif_creamy_16oz_051500255162": lambda b: None,  # no label serving mass: no mass balance
    "nutricost_magnesium_oxide_702669934398": nutricost,
    "nutella_fr_3017620422003": lambda b: None,  # no facts until a label photo is attested
}


def add_derivations(b: RecordBuilder, name: str) -> None:
    try:
        DERIVE[name](b)
    except LpError as e:
        raise RecordError(f"{name}: {e}") from e
