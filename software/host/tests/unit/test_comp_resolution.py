"""M2 (plan WP1): attested barcode -> NDC -> SPL resolution, offline from snapshots."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("lxml")
pytest.importorskip("jsonschema")

from snapweb import STORE, SnapshotWeb

from lio.foods import barcode as bc
from lio.foods.drugid import DrugResolver
from lio.foods.lookup import Lookup, LookupSettings
from lio_comp import crosswalk, golden
from lio_verify import textrules
from lio_verify.verify import Verifier

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
RULES = REPO / "composition" / "rules"
CAREONE_GTIN = "00341520314643"


def resolver(tmp: Path) -> DrugResolver:
    return DrugResolver(
        Lookup(LookupSettings(usda_api_key="k"), fetch=SnapshotWeb()), crosswalk=tmp / "links.jsonl"
    )


# ------------------------------------------------------------------- grammar


def test_printed_ndc_grammar_and_11_digit_form() -> None:
    assert bc.printed_ndcs("Rx only NDC 41520-745-18 180 softgels") == [("41520-745-18", 8, 24)]
    assert bc.ndc11("0135-0089-71") == "00135008971"
    assert bc.ndc11("00680-4183-0") == "00680418300"
    assert textrules.apply("printed_ndc@1", "NDC 41520-745-18") == "41520074518"
    with pytest.raises(textrules.RuleError):
        textrules.apply("printed_ndc@1", "NDC 41520-745-1")  # 5-3-1 is not an NDC pattern
    assert bc.printed_ndcs("NDC 12345-678-901") == []  # too many digits


# ------------------------------------------------------------------ RxNav + DailyMed


def test_citrucel_embedded_ndc_needs_the_printed_one(tmp_path: Path) -> None:
    r = resolver(tmp_path).resolve(bc.normalise("300680418301"))
    first = r["embedded"][0]
    assert (first["ndc"], first["status"], first["rxcui"]) == ("0068-0418-30", "ACTIVE", "1868847")
    assert "concept" in first["note"]
    assert all(not e["spls"] for e in r["embedded"])  # the UPC's NDC is in no current SPL
    assert r["needs_printed_ndc"] and r["spl"] is None


def test_careone_stale_ndc_is_unknown_and_printed_ndc_resolves(tmp_path: Path) -> None:
    rs = resolver(tmp_path)
    r = rs.resolve(bc.normalise("341520314643"))
    assert r["embedded"][1]["ndc"] == "41520-314-64" and r["embedded"][1]["status"] == "UNKNOWN"
    assert r["needs_printed_ndc"]
    hit = rs.resolve_printed("41520-745-18")
    assert (
        hit is not None
        and hit["setid"] == "016299ef-ad40-46fd-acfc-e74ffee3d9b4"
        and hit["version"] == 3
    )
    assert "41520-745-18" in hit["ndcs"]


def test_citrucel_printed_ndc_resolves_without_name_search(tmp_path: Path) -> None:
    web = SnapshotWeb()
    rs = DrugResolver(Lookup(LookupSettings(), fetch=web), crosswalk=tmp_path / "x.jsonl")
    hit = rs.resolve_printed("0135-0089-71")
    assert (
        hit is not None
        and hit["setid"] == "9d5f2244-a610-4d45-b6e8-e79bb17a558f"
        and hit["version"] == 17
    )
    assert not any("drug_name=" in c or "brand_name" in c for c in web.calls)


def test_crosswalk_is_append_only_and_flags_stale_versions(tmp_path: Path) -> None:
    rs = resolver(tmp_path)
    row = {
        "gtin": CAREONE_GTIN,
        "ndc": "41520-745-18",
        "ndc11": "41520074518",
        "setid": "016299ef-ad40-46fd-acfc-e74ffee3d9b4",
        "spl_version": 2,
        "method": "printed_ndc",
        "evidence": {},
        "attestation": {"operator": "test-fixture", "timestamp": "2026-11-12T00:00:00Z"},
    }
    with pytest.raises(ValueError):
        rs.add_link({**row, "attestation": {"operator": " "}})
    rs.add_link(row)
    r = rs.resolve(bc.normalise("341520314643"))
    assert r["crosswalk"]["stale"] is True and r["crosswalk"]["latest_version"] == 3
    assert r["spl"]["via"] == "crosswalk"
    assert len((tmp_path / "links.jsonl").read_text().splitlines()) == 1


# --------------------------------------------------------------- golden records


@pytest.fixture
def signed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A crosswalk with the Care One proposal signed by a clearly synthetic signer."""
    links = tmp_path / "links.jsonl"
    crosswalk.sign(
        CAREONE_GTIN,
        "test-fixture (not an operator attestation)",
        links=links,
        now="2026-11-12T00:00:00Z",
    )
    monkeypatch.setattr(golden, "CROSSWALK_PATH", [links])
    return links


def build_careone(tmp: Path) -> Path:
    return golden.build(STORE, RULES, "careone_ibuprofen_341520314643").write(tmp)


def verify(p: Path) -> Any:
    return Verifier(STORE, RULES).verify(p)


def test_careone_record_passes_via_the_attested_link(signed: Path, tmp_path: Path) -> None:
    p = build_careone(tmp_path)
    rep = verify(p)
    assert rep.ok, (rep.errors, [f.to_json() for f in rep.fields if f.status == "FAILED"])
    st = {f.id: f for f in rep.fields}
    assert st["L1"].status == "ATTESTED" and st["SEL1"].status == "VERIFIED"
    assert st["F1"].status == "VERIFIED" and st["F1"].rests_on == ["L1", "SEL1"]
    rec = json.loads(p.read_text())
    assert rec["selections"][0]["product_code"] == "41520-745"
    assert rec["ingredients"][0]["name_verbatim"] == "IBUPROFEN"


def _mut(p: Path, fn: Any, tmp: Path) -> Any:
    rec = json.loads(p.read_text())
    fn(rec)
    q = tmp / "m.json"
    q.write_text(json.dumps(rec))
    return verify(q)


MUTATIONS = {
    "span_reads_another_ndc": lambda r: r["links"][0]["locator"].__setitem__(
        "text", "NDC 41520-745-80"
    ),
    "ndc11_changed": lambda r: r["links"][0].__setitem__("ndc11", "41520074580"),
    "attestation_removed": lambda r: r.__setitem__("attestations", []),
    "gtin_changed": lambda r: r["links"][0].__setitem__("gtin", "00300680418301"),
    "selection_other_product": lambda r: r["selections"][0].__setitem__(
        "product_code", "41520-746"
    ),
    "selection_other_package": lambda r: r["selections"][0].__setitem__(
        "package_ndc", "41520-745-40"
    ),
    "fact_from_another_product": lambda r: r["facts"][0]["locator"].__setitem__(
        "expr", r["facts"][0]["locator"]["expr"].replace("'41520-745'", "'41520-746'")
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_link_mutations_fail(name: str, signed: Path, tmp_path: Path) -> None:
    p = build_careone(tmp_path)
    assert not _mut(p, MUTATIONS[name], tmp_path).ok, name


def test_unsigned_golden_record_is_not_built() -> None:
    with pytest.raises(golden.NeedsSignature):
        golden.build(STORE, RULES, "careone_ibuprofen_341520314643")


# ------------------------------------------------------------- operator flow


def test_operator_ndc_photo_links_the_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    import lio.foods.drugid as drugid
    import lio.foods.intake as intake_mod
    from lio.foods.intake import Intake
    from lio.foods.store import FoodLibrary
    from lio_comp.samples import SampleComposition

    monkeypatch.setattr(drugid, "CROSSWALK", tmp_path / "gtin_links.jsonl")
    monkeypatch.setattr(intake_mod, "read_label", lambda data: {
        "lines": ["NDC 41520-745-18"], "text": "NDC 41520-745-18", "ingredients": "", "contains": "", "heading": "",
        "nutrition": {"per_100g": {}, "serving": "", "serving_g": None}, "image_size": [800, 600], "panel_rows": [],
        "ingredient_box": None,
        "ndc_candidates": [{"text": "NDC 41520-745-18", "ndc": "41520-745-18", "ndc11": "41520074518", "box": {"x": 10, "y": 20, "w": 200, "h": 30}}]})  # fmt: skip
    web = SnapshotWeb()
    lib = FoodLibrary(tmp_path / "foods", Lookup(LookupSettings(), fetch=web))
    lib._download_image = lambda gtin14, url: ""  # type: ignore[method-assign]
    it = Intake(lib, SampleComposition(tmp_path / "foods" / "composition", RULES))
    # the SPL XML the composition record snapshots
    s = lib.create_sample(bc.normalise("341520314643"))
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buf, "JPEG")
    r = it.read_label(buf.getvalue(), "ndc")
    assert r["can_attest"]
    out = it.apply_label(
        s["sample_code"],
        {"label_draft": r["label_draft"], "attest": {"signer": "test-fixture", "index": 0}},
    )
    assert out["ndc_link"]["setid"] == "016299ef-ad40-46fd-acfc-e74ffee3d9b4"
    rows = (tmp_path / "gtin_links.jsonl").read_text().splitlines()
    assert len(rows) == 1 and json.loads(rows[0])["ndc11"] == "41520074518"
    rep = it.composition_report(s["sample_code"])["report"]
    assert rep["result"] == "PASS", rep
    fields = {f["id"]: f["status"] for f in rep["fields"]}
    assert fields["L1"] == "ATTESTED" and fields["SEL1"] == "VERIFIED"
    lib.close()
