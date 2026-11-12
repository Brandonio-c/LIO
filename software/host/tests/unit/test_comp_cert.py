"""M1 (plan WP6): exact simplex, LP dual / Motzkin certificates, no solver in lio_verify."""

from __future__ import annotations

import copy
import itertools
import json
import subprocess
import sys
from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from lio_comp import bound as B  # noqa: E402
from lio_comp.simplex import solve_free  # noqa: E402
from lio_verify import cert  # noqa: E402
from lio_verify.interval import Interval  # noqa: E402
from lio_verify.lp import Atom, Form  # noqa: E402
from lio_verify.verify import Verifier  # noqa: E402

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
COMP = REPO / "composition"
CITRUCEL = "citrucel_orange_300680418301"


def rec(name: str) -> dict[str, Any]:
    return dict(json.loads((COMP / "records" / f"{name}.json").read_text()))


def check(r: dict[str, Any], tmp: Path) -> Any:
    p = tmp / "r.json"
    p.write_text(json.dumps(r))
    return Verifier(COMP / "sources", COMP / "rules").verify(p)


def bound(r: dict[str, Any], bid: str) -> dict[str, Any]:
    return next(b for b in r["bounds"] if b["id"] == bid)


# ------------------------------------------------------------ simplex vs brute force

small = st.fractions(min_value=-5, max_value=5, max_denominator=4)


@st.composite
def lp2(draw: st.DrawFn) -> tuple[list[list[F]], list[F], list[F]]:
    """A bounded 2-variable LP: a box plus a few random rows."""
    g = [[F(1), F(0)], [F(-1), F(0)], [F(0), F(1)], [F(0), F(-1)]]
    h = [F(10)] * 4
    for _ in range(draw(st.integers(0, 4))):
        g.append([draw(small), draw(small)])
        h.append(draw(st.fractions(min_value=-3, max_value=8, max_denominator=4)))
    return g, h, [draw(small), draw(small)]


def brute(g: list[list[F]], h: list[F], c: list[F]) -> F | None:
    """Minimum over the vertices (pairwise intersections that are feasible)."""
    best = None
    for i, j in itertools.combinations(range(len(g)), 2):
        (a, b), (cc, d) = g[i], g[j]
        det = a * d - b * cc
        if det == 0:
            continue
        x = (h[i] * d - b * h[j]) / det
        y = (a * h[j] - cc * h[i]) / det
        if all(r[0] * x + r[1] * y <= hv for r, hv in zip(g, h, strict=True)):
            v = c[0] * x + c[1] * y
            best = v if best is None or v < best else best
    return best


@settings(max_examples=300, deadline=None)
@given(lp2())
def test_simplex_matches_vertex_enumeration(lp: tuple[list[list[F]], list[F], list[F]]) -> None:
    g, h, c = lp
    res = solve_free(c, g, h)
    want = brute(g, h, c)
    if want is None:
        assert res.status == "infeasible"
    else:
        assert res.status == "optimal" and res.value == want


@settings(max_examples=150, deadline=None)
@given(lp2(), st.lists(st.booleans(), min_size=8, max_size=8))
def test_certificates_are_sound_and_check(
    lp: tuple[list[list[F]], list[F], list[F]], strict: list[bool]
) -> None:
    g, h, c = lp
    names = ["x", "y"]
    atoms = [Atom(Form((("x", r[0]), ("y", r[1])), F(0)), "<" if strict[i % 8] else "<=", hv, f"R{i}")
             for i, (r, hv) in enumerate(zip(g, h, strict=True))]  # fmt: skip
    try:
        iv, cer = B.bound(atoms, names, Form((("x", c[0]), ("y", c[1])), F(0)))
    except B.LpError:
        return  # infeasible or empty strict system: no bound to certify
    rows = [(list(a), rhs, s, o) for a, rhs, s, o in B.lp_rows(atoms, names)]
    assert cert.check(cer, rows, names, c, F(0), iv) == []
    # every vertex of the closed system lies within the closure of the interval
    for i, j in itertools.combinations(range(len(g)), 2):
        (a, b), (cc, d) = g[i], g[j]
        det = a * d - b * cc
        if det:
            x, y = (h[i] * d - b * h[j]) / det, (a * h[j] - cc * h[i]) / det
            if all(r[0] * x + r[1] * y <= hv for r, hv in zip(g, h, strict=True)):
                assert iv.lo <= c[0] * x + c[1] * y <= iv.hi


# ----------------------------------------------------------------- mutations (WP6)


def _perturb_dual(r: dict[str, Any]) -> None:
    e = bound(r, "B3")["certificate"]["min"]
    i = next(k for k, v in enumerate(e["dual"]) if v != "0")
    e["dual"][i] = str(F(e["dual"][i]) + F(1, 10**6))


def _perturb_witness(r: dict[str, Any]) -> None:
    w = bound(r, "B3")["certificate"]["max"]["witness"]
    w["sucrose"] = str(F(w["sucrose"]) + F(1, 10**6))


def _lp_differs(r: dict[str, Any]) -> None:
    row = bound(r, "B3")["certificate"]["lp"]["rows"][0]
    row["rhs"] = str(F(row["rhs"]) + 1)


def _narrow(r: dict[str, Any]) -> None:
    b = bound(r, "B3")
    hi = F(b["result"]["hi"]) - F(1, 10**6)
    b["result"]["hi"] = f"{hi.numerator}/{hi.denominator}"
    b["certificate"]["max"]["value"] = b["result"]["hi"]


def _motzkin(r: dict[str, Any]) -> None:
    e = bound(r, "B1")["certificate"]["min"]
    e["motzkin"] = ["0"] * len(e["motzkin"])


def _feasibility(r: dict[str, Any]) -> None:
    r["feasibility"]["witness"]["sucrose"] = "100"


MUTATIONS = {"perturbed_dual": _perturb_dual, "perturbed_witness": _perturb_witness,
             "lp_differs_from_record": _lp_differs, "narrowed_by_1e-6": _narrow,
             "empty_motzkin": _motzkin, "infeasible_feasibility_witness": _feasibility}  # fmt: skip


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_certificate_mutations_fail(name: str, tmp_path: Path) -> None:
    r = copy.deepcopy(rec(CITRUCEL))
    MUTATIONS[name](r)
    rep = check(r, tmp_path)
    assert not rep.ok, name


def test_all_golden_bounds_are_recertified() -> None:
    for p in (COMP / "records").glob("*.json"):
        r = json.loads(p.read_text())
        for b in r["bounds"]:
            assert b["solver"].startswith("lio_comp.simplex")
            assert {"lp", "min", "max"} <= set(b["certificate"])
            for end in ("min", "max"):
                e = b["certificate"][end]
                assert "dual" in e and (e["attained"] or {"interior", "motzkin"} <= set(e))
        assert Verifier(COMP / "sources", COMP / "rules").verify(p).ok


def test_open_and_closed_ends_match_the_old_z3_results() -> None:
    r = rec(CITRUCEL)
    assert Interval.from_json(bound(r, "B1")["result"]) == (
        Interval(F(0), F(65, 4), False, False),
        "g",
    )
    n = rec("nutella_fr_3017620422003")
    assert Interval.from_json(bound(n, "B1")["result"]) == (Interval(F(133, 5), F(563, 10)), "%")


# -------------------------------------------------------------- import boundary


def test_lio_verify_never_imports_a_solver_or_the_builder() -> None:
    src = REPO / "software" / "host" / "src" / "lio_verify"
    for p in src.glob("*.py"):
        text = p.read_text()
        for bad in (
            "import z3",
            "from z3",
            "import lio_comp",
            "from lio_comp",
            "from lio.",
            "import lio.foods",
        ):
            assert bad not in text, (p.name, bad)
    code = (
        "import sys, importlib.abc\n"
        "class Block(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, name, path, target=None):\n"
        "        if name == 'z3' or name.startswith(('z3.', 'lio_comp', 'lio.')) or name == 'lio':\n"
        "            raise ImportError('blocked: ' + name)\n"
        "sys.meta_path.insert(0, Block())\n"
        "import pkgutil, lio_verify\n"
        "for m in pkgutil.iter_modules(lio_verify.__path__): __import__('lio_verify.' + m.name)\n"
        "from lio_verify.cli import main\n"
        f"rc = main([{str(COMP / 'records' / (CITRUCEL + '.json'))!r}, '--sources', {str(COMP / 'sources')!r}, '--rules', {str(COMP / 'rules')!r}, '--quiet'])\n"
        "sys.exit(rc)\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
