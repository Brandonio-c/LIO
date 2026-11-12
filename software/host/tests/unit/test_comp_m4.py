"""M4: the independent verifier, mutation tests (spec §8), determinism, independence."""

from __future__ import annotations

import copy
import json
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("lxml")
pytest.importorskip("lxml")
pytest.importorskip("jsonschema")

from lio_verify.cli import main as cli_main
from lio_verify.verify import FAILED, Verifier

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
COMP = REPO / "composition"
STORE, RULES = COMP / "sources", COMP / "rules"
NAMES = sorted(p.stem for p in (COMP / "records").glob("*.json"))
CITRUCEL = "citrucel_orange_300680418301"


def rec(name: str) -> dict[str, Any]:
    return dict(json.loads((COMP / "records" / f"{name}.json").read_text()))


def check(r: dict[str, Any], tmp: Path, store: Path = STORE) -> Any:
    p = tmp / f"{r['record_id']}.json"
    p.write_text(json.dumps(r, indent=1, sort_keys=True))
    return Verifier(store, RULES).verify(p)


def by_id(items: list[dict[str, Any]], i: str) -> dict[str, Any]:
    return next(x for x in items if x["id"] == i)


# ----------------------------------------------------------------- passing


@pytest.mark.parametrize("name", NAMES)
def test_golden_records_pass(name: str) -> None:
    rep = Verifier(STORE, RULES).verify(COMP / "records" / f"{name}.json")
    assert rep.ok, (rep.errors, [f.to_json() for f in rep.fields if f.status == FAILED])
    assert rep.counts()["VERIFIED"] + rep.counts()["UNVERIFIED"] > 0


def test_cli_exit_codes(tmp_path: Path) -> None:
    paths = [str(COMP / "records" / f"{n}.json") for n in NAMES]
    out = tmp_path / "report.json"
    assert cli_main([*paths, "--sources", str(STORE), "--rules", str(RULES), "--quiet",
                     "--json", str(out)]) == 0  # fmt: skip
    reports = json.loads(out.read_text())
    assert [r["result"] for r in reports] == ["PASS"] * len(NAMES)
    assert all(r["assumptions"] for r in reports)  # every assumption is listed in the report
    bad = rec(CITRUCEL)
    by_id(bad["facts"], "F1")["value"]["hi"] = "3"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    assert cli_main([str(p), "--sources", str(STORE), "--rules", str(RULES), "--quiet"]) == 1


# ------------------------------------------------------- mutations (spec §8)


def _fact_value(r: dict[str, Any]) -> None:
    by_id(r["facts"], "F1")["value"]["hi"] = "3"


def _derivation_value(r: dict[str, Any]) -> None:
    by_id(r["derivations"], "D1")["value"]["lo"] = "14"


def _removed_assumption(r: dict[str, Any]) -> None:
    r["assumptions"] = [a for a in r["assumptions"] if a["id"] != "A3"]


def _tampered_witness(r: dict[str, Any]) -> None:
    by_id(r["bounds"], "B3")["certificate"]["max"]["witness"]["sucrose"] = "1"


def _narrower_bound(r: dict[str, Any]) -> None:
    b = by_id(r["bounds"], "B1")
    b["result"]["hi"] = "16"  # proven: sucrose < 65/4
    b["certificate"]["max"]["value"] = "16"


def _shifted_xpath(r: dict[str, Any]) -> None:
    loc = by_id(r["facts"], "F3")["locator"]
    loc["expr"] = loc["expr"].replace(
        "each heaping tablespoon contains", "each heaping tablespoon contributes"
    )


def _float_value(r: dict[str, Any]) -> None:
    by_id(r["facts"], "F1")["value"]["lo"] = 2.0


def _otc_weight_order(r: dict[str, Any]) -> None:
    r["constraints"].append({"id": "C99", "kind": "ordered_desc", "items": ["V:sucrose", "V:maltodextrin"],
                             "list_rule": "list_ordering@1:us_otc_inactive_ingredients", "assumptions": []})  # fmt: skip


def _rules_version(r: dict[str, Any]) -> None:
    r["toolchain"]["rules_versions"]["fda_rounding_101_9"] = 2


def _wrong_unii(r: dict[str, Any]) -> None:
    by_id(r["substances"], "SUB_tcp")["formula"] = "5Ca.HO.3O4P"  # hydroxyapatite, not the source


def _dropped_bound_assumption(r: dict[str, Any]) -> None:
    by_id(r["bounds"], "B1")["assumptions"].remove("A6")


MUTATIONS: dict[str, Callable[[dict[str, Any]], None]] = {
    "altered_fact_value": _fact_value,
    "altered_derivation": _derivation_value,
    "removed_assumption": _removed_assumption,
    "tampered_bound_witness": _tampered_witness,
    "bound_narrower_than_proven": _narrower_bound,
    "shifted_locator": _shifted_xpath,
    "float_in_value": _float_value,
    "weight_order_on_otc_list": _otc_weight_order,
    "rules_version_mismatch": _rules_version,
    "formula_not_from_source": _wrong_unii,
    "bound_drops_an_assumption": _dropped_bound_assumption,
}


@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
def test_mutation_fails(mutation: str, tmp_path: Path) -> None:
    r = copy.deepcopy(rec(CITRUCEL))
    MUTATIONS[mutation](r)
    assert not check(r, tmp_path).ok


def test_shifted_list_span_fails(tmp_path: Path) -> None:
    r = rec(CITRUCEL)
    by_id(r["ingredients"], "T3")["list_rule"] = "list_item@2:4"  # the next item in the text list
    assert not check(r, tmp_path).ok


def test_shifted_json_pointer_fails(tmp_path: Path) -> None:
    r = rec("nutricost_magnesium_oxide_702669934398")
    by_id(r["facts"], "F_mg")["locator"]["pointer"] = "/ingredientRows/0/quantity/1"
    assert not check(r, tmp_path).ok


def test_changed_source_byte_fails(tmp_path: Path) -> None:
    store = tmp_path / "store"
    shutil.copytree(STORE, store)
    r = rec(CITRUCEL)
    sha = by_id([{**s, "id": s["source_id"]} for s in r["sources"]], "S1")["sha256"]
    blob = store / "sha256" / sha[:2] / sha
    blob.chmod(0o644)
    data = bytearray(blob.read_bytes())
    data[1000] ^= 1
    blob.write_bytes(bytes(data))
    rep = check(r, tmp_path, store)
    assert not rep.ok
    assert any("SHA-256" in e for e in rep.errors)


def test_dependency_failure_is_unverified_not_verified(tmp_path: Path) -> None:
    r = rec(CITRUCEL)
    by_id(r["facts"], "F6")["value"]["lo"] = "50"
    rep = check(r, tmp_path)
    status = {f.id: f.status for f in rep.fields}
    assert status["F6"] == FAILED
    assert status["D1"] != "VERIFIED"  # derived from a failed fact


# ------------------------------------------------- determinism, independence


def test_reports_are_deterministic() -> None:
    v = Verifier(STORE, RULES)
    for n in NAMES:
        a = v.verify(COMP / "records" / f"{n}.json").to_json()
        b = v.verify(COMP / "records" / f"{n}.json").to_json()
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_verifier_needs_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*a: object, **k: object) -> None:
        raise OSError("network disabled in this test")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    assert Verifier(STORE, RULES).verify(COMP / "records" / f"{CITRUCEL}.json").ok


def test_verifier_does_not_import_the_builder() -> None:
    src = REPO / "software" / "host" / "src" / "lio_verify"
    for p in src.glob("*.py"):
        text = p.read_text()
        assert "lio_comp" not in text.replace("lio_comp.", "") or "import lio_comp" not in text, p
        assert "from lio_comp" not in text and "import lio_comp" not in text, p
        assert (
            "from lio." not in text and "import lio\n" not in text and "from lio import" not in text
        ), p
    code = (
        "import sys, lio_verify.cli as c; "
        f"rc = c.main([{str(COMP / 'records' / f'{CITRUCEL}.json')!r}, '--sources', {str(STORE)!r}, "
        f"'--rules', {str(RULES)!r}, '--quiet']); "
        "bad = sorted(m for m in sys.modules if m == 'lio' or m.startswith(('lio.', 'lio_comp'))); "
        "print(rc, bad); sys.exit(1 if (rc or bad) else 0)"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr


def test_narrower_bound_with_a_consistent_witness_is_caught(tmp_path: Path) -> None:
    """Even with a valid witness inside the narrowed range, the dual certificate no longer
    matches the stated end (no solver is involved)."""
    from fractions import Fraction as F

    r = rec(CITRUCEL)
    b = by_id(r["bounds"], "B1")
    w = b["certificate"]["max"]["witness"]
    new_s = F(16) - F(1, 10**7)
    shift = F(w["sucrose"]) - new_s
    w["sucrose"] = str(new_s)
    w["maltodextrin"] = str(F(w["maltodextrin"]) + shift)  # same total: still feasible
    b["result"]["hi"] = "16"
    b["certificate"]["max"]["value"] = "16"
    rep = check(r, tmp_path)
    problems = [p for f in rep.fields if f.id == "B1" for p in f.problems]
    assert problems, "a narrowed bound must fail"
