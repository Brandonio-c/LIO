"""M2: evidence store, extractors with locators, golden-record facts."""

from __future__ import annotations

import json
from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("lxml")
pytest.importorskip("lark")
jsonschema = pytest.importorskip("jsonschema")

from lio_comp import golden  # noqa: E402
from lio_comp.evidence import EvidenceError, Retrieval, canonical_json, get, put  # noqa: E402
from lio_verify import textrules  # noqa: E402
from lio_verify.interpret import interpret, load_tables  # noqa: E402
from lio_verify.interval import Interval  # noqa: E402
from lio_verify.locate import LocatorError, load_json_exact, resolve  # noqa: E402

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
COMP = REPO / "composition"
STORE = COMP / "sources"
RECORDS = sorted((COMP / "records").glob("*.json"))


def record(name: str) -> dict[str, Any]:
    return dict(json.loads((COMP / "records" / f"{name}.json").read_text()))


def src_bytes(rec: dict[str, Any], source_id: str) -> bytes:
    sha = next(s["sha256"] for s in rec["sources"] if s["source_id"] == source_id)
    return get(STORE, sha)


def value(rec: dict[str, Any], fid: str) -> tuple[Interval, str]:
    f = next(f for f in rec["facts"] if f["id"] == fid)
    return Interval.from_json(f["value"])


# ------------------------------------------------------------ evidence store


def test_store_is_content_addressed_and_immutable(tmp_path: Path) -> None:
    r = Retrieval("https://example.org/a", "2026-11-11T00:00:00Z", {"k": "v"})
    sha = put(tmp_path, b"abc", "text/plain", r)
    assert sha == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert put(tmp_path, b"abc", "text/plain", r) == sha  # same retrieval: no new entry
    r2 = Retrieval("https://example.org/a", "2026-11-12T00:00:00Z", {"k": "v"})
    put(tmp_path, b"abc", "text/plain", r2)
    man = json.loads((tmp_path / "manifest" / f"{sha}.json").read_text())
    assert [x["retrieved_at"] for x in man["retrievals"]] == [
        "2026-11-11T00:00:00Z",
        "2026-11-12T00:00:00Z",
    ]
    blob = tmp_path / "sha256" / sha[:2] / sha
    blob.chmod(0o644)
    blob.write_bytes(b"abd")
    with pytest.raises(EvidenceError):
        get(tmp_path, sha)


def test_no_api_key_in_the_repository_store() -> None:
    for p in (STORE / "manifest").glob("*.json"):
        assert "api_key" not in p.read_text()


# --------------------------------------------------------------- golden facts


@pytest.mark.parametrize("path", RECORDS, ids=lambda p: p.stem)
def test_every_fact_re_derives_from_its_snapshot(path: Path) -> None:
    rec = json.loads(path.read_text())
    tables = load_tables(COMP / "rules")
    # Records built only from corroboration (FDC, Open Food Facts) have no facts (plan WP3).
    for f in rec["facts"]:
        data = src_bytes(rec, f["source_id"])
        text = resolve(f["locator"], data)
        assert textrules.apply(f["rule"], text) == f["value_raw"]
        iv, unit = interpret(f["value_raw"], f["interpretation"], tables)
        assert iv.to_json(unit) == f["value"]
    for ing in rec["ingredients"]:
        text = resolve(ing["name_locator"], src_bytes(rec, ing["source_id"]))
        if "list_rule" in ing:
            text = textrules.apply(ing["list_rule"], text)
        assert text == ing["name_verbatim"]


@pytest.mark.parametrize("path", RECORDS, ids=lambda p: p.stem)
def test_records_match_schema(path: Path) -> None:
    schema = json.loads((COMP / "schema" / "record.schema.json").read_text())
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(json.loads(path.read_text())))
    assert not errors, errors[0].message


def test_golden_records_are_byte_identical_when_rebuilt(tmp_path: Path) -> None:
    for name in golden.GOLDEN:
        try:
            built = golden.build(STORE, COMP / "rules", name).write(tmp_path)
        except golden.NeedsSignature:
            continue  # rests on an operator attestation not yet signed (test_comp_resolution)
        again = golden.build(STORE, COMP / "rules", name).write(tmp_path / "again")
        assert built.read_bytes() == again.read_bytes()
        assert built.read_bytes() == (COMP / "records" / f"{name}.json").read_bytes(), (
            f"{name}: composition/records is stale; rebuild with python -m lio_comp.golden"
        )


def test_citrucel_facts_reproduce_spec_values() -> None:
    rec = record("citrucel_orange_300680418301")
    assert value(rec, "F1") == (Interval.point(2), "g")  # methylcellulose 2 g
    assert value(rec, "F2") == (Interval.point(19), "g")  # SPL strength denominator
    assert value(rec, "F6") == (Interval(F(55), F(65), True, False), "kcal")
    # 21 CFR 201.70(b): calcium is rounded to the nearest 5 mg, so 80 mg is an interval.
    assert value(rec, "F3") == (Interval(F(155, 2), F(165, 2)), "mg")
    uniis = {i["unii"] for i in rec["ingredients"] if "unii" in i}
    assert {"MRJ667KA5E", "L11K75P92J", "K4C08XP666", "C151H8M554", "7CVR7L4A2D"} <= uniis
    formulas = {s["unii"]: s["formula"] for s in rec["substances"]}
    assert formulas == {"L11K75P92J": "Ca.HO4P", "K4C08XP666": "3Ca.2O4P",
                        "EE90ONI6FF": "C6H5O7.3K.H2O"}  # fmt: skip


def test_fdc_values_are_corroboration_only() -> None:
    rec = record("jif_creamy_16oz_051500255162")
    assert not rec["facts"]  # no attested label photo signed in the repository yet
    ids = {c["id"] for c in rec["corroboration"]}
    assert {"CR_label_total_fat", "CR_100g_total_fat", "CR_serving"} <= ids
    fiber = next(c for c in rec["corroboration"] if c["id"] == "CR_label_dietary_fiber")
    assert fiber["value_raw"] == "2.01 g"  # FDC-computed, kept but never a fact


def test_json_numbers_are_kept_as_tokens() -> None:
    doc = load_json_exact(b'{"a": 16.0, "b": 0.502, "c": 140}')
    assert (doc["a"], doc["b"], doc["c"]) == ("16.0", "0.502", "140")


# --------------------------------------------------------------- tampering


def test_tampered_locators_fail() -> None:
    rec = record("citrucel_orange_300680418301")
    f = next(f for f in rec["facts"] if f["id"] == "F1")
    data = src_bytes(rec, "S1")
    bad = dict(f["locator"], text="3 g")
    with pytest.raises(LocatorError):
        resolve(bad, data)
    dose = next(f for f in rec["facts"] if f["id"] == "F2")["locator"]
    bad = dict(dose, expr=dose["expr"].replace("0135-0089", "0135-0090"))
    with pytest.raises(LocatorError):  # the Sugar Free variant: 2 g in 10.2 g
        resolve(bad, data)
    with pytest.raises(LocatorError):  # one changed byte in the snapshot
        resolve(dose, data.replace(b'value="19"', b'value="18"'))


def test_canonical_json_is_stable() -> None:
    assert canonical_json({"b": 1, "a": [2]}) == b'{\n "a": [\n  2\n ],\n "b": 1\n}\n'
