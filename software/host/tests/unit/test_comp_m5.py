# ruff: noqa: E501  (fixtures and one-line calls are kept whole)
"""M5: photo attestation flow, badges, training export."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from fractions import Fraction as F
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("z3")
pytest.importorskip("lxml")
pytest.importorskip("jsonschema")
pytest.importorskip("PIL")

from lio.foods import barcode as bc
from lio.foods.intake import Intake
from lio.foods.lookup import Lookup, LookupSettings
from lio.foods.ocr import Line, panel_rows, visual_rows
from lio.foods.store import FoodLibrary, LibraryError
from lio_comp.export import rows, to_csv
from lio_comp.samples import CompositionError, SampleComposition
from lio_verify.interval import Interval
from lio_verify.verify import Verifier

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
RULES = REPO / "composition" / "rules"


def photo() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (600, 900), (250, 250, 245)).save(buf, "JPEG")
    return buf.getvalue()


def box(i: int) -> dict[str, int]:
    return {"x": 40, "y": 100 + 40 * i, "w": 400, "h": 30}


PANEL = [  # what ocr.panel_rows gives for a Nutrition Facts photo
    ("serving", "nfp_serving@1", "Serving size 2 Tbsp (33g)"),
    ("calories", "nfp_row@1:calories", "Calories 190"),
    ("total_fat", "nfp_row@1:total_fat", "Total Fat 16g 21%"),
    ("sodium", "nfp_row@1:sodium", "Sodium 140mg 6%"),
    ("dietary_fiber", "nfp_row@1:dietary_fiber", "Dietary Fiber 2g 7%"),
    ("protein", "nfp_row@1:protein", "Protein 7g"),
]


def ocr_result() -> dict[str, Any]:
    return {
        "lines": [t for _, _, t in PANEL], "text": "\n".join(t for _, _, t in PANEL),
        "ingredients": "", "contains": "", "heading": "",
        "nutrition": {"per_100g": {"fat_g": 48.48}, "serving": "2 Tbsp (33g)", "serving_g": 33.0},
        "image_size": [600, 900],
        "panel_rows": [{"nutrient": n, "rule": r, "text": t, "value_raw": "", "box": box(i)}
                       for i, (n, r, t) in enumerate(PANEL)],
    }  # fmt: skip


class _NoWeb:
    def __call__(self, *a: Any, **k: Any) -> Any:
        raise OSError("offline")


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[FoodLibrary, Intake]]:
    import lio.foods.intake as intake_mod

    monkeypatch.setattr(intake_mod, "read_label", lambda data: ocr_result())
    lib = FoodLibrary(tmp_path / "foods", Lookup(LookupSettings(), fetch=_NoWeb()))
    lib._download_image = lambda gtin14, url: ""  # type: ignore[method-assign]
    comp = SampleComposition(tmp_path / "foods" / "composition", RULES)
    yield lib, Intake(lib, comp)
    lib.close()


def attest_all(
    it: Intake, code: str, signer: str = "B. Colelough", edit: dict[int, str] | None = None
) -> dict[str, Any]:
    r = it.read_label(photo(), "nutrition")
    assert r["can_attest"]
    picked = [
        {"index": x["index"], "text": (edit or {}).get(x["index"], x["text"])}
        for x in r["panel_rows"]
    ]
    return it.apply_label(code, {"label_draft": r["label_draft"], "nutrition_per_100g": {"fat_g": 48.48},
                                 "attest": {"signer": signer, "rows": picked}})  # fmt: skip


# --------------------------------------------------------------- the flow


def test_attested_panel_becomes_a_verified_record(setup: tuple[FoodLibrary, Intake]) -> None:
    lib, it = setup
    s = lib.create_sample(bc.normalise("96385074"))
    out = attest_all(it, s["sample_code"])
    rep = out["composition"]["report"]
    assert rep["result"] == "PASS", rep
    status = {f["id"]: f["status"] for f in rep["fields"]}
    assert status["P1_total_fat"] == "ATTESTED"  # a photo, attested by a person: not VERIFIED
    assert status["P1_total_fat_per100g"] == "ATTESTED"  # derived from attested facts
    assert "VERIFIED" not in {status[k] for k in status if k.startswith("P1_")}
    rec = it.composition_report(s["sample_code"])["record"]
    fat = next(f for f in rec["facts"] if f["id"] == "P1_total_fat")
    assert Interval.from_json(fat["value"]) == (Interval(F(31, 2), F(33, 2), True, False), "g")
    assert fat["locator"]["type"] == "image_bbox" and fat["evidence_class"] == "attested"
    assert rec["attestations"][0]["signer"] == "B. Colelough"
    assert rec["unverified_layer"]["estimates"][0]["quantity"] == "total_fat"
    per100, _ = Interval.from_json(
        next(d for d in rec["derivations"] if d["id"] == "P1_total_fat_per100g")["value"]
    )
    assert per100 == Interval(F(31, 2) * 100 / 33, F(33, 2) * 100 / 33, True, False)


def test_boxes_come_from_the_server_and_text_from_the_operator(
    setup: tuple[FoodLibrary, Intake],
) -> None:
    lib, it = setup
    s = lib.create_sample(bc.normalise("96385074"))
    attest_all(it, s["sample_code"], edit={2: "Total Fat 15g 19%"})  # operator corrects a misread
    rec = it.composition_report(s["sample_code"])["record"]
    fat = next(f for f in rec["facts"] if f["id"] == "P1_total_fat")
    assert fat["locator"]["text"] == "Total Fat 15g 19%"
    assert {k: fat["locator"][k] for k in ("x", "y", "w", "h")} == box(2)


def test_attestation_needs_a_name_and_readable_rows(setup: tuple[FoodLibrary, Intake]) -> None:
    lib, it = setup
    s = lib.create_sample(bc.normalise("96385074"))
    with pytest.raises(LibraryError):
        attest_all(it, s["sample_code"], signer="  ")
    with pytest.raises(LibraryError):
        attest_all(it, s["sample_code"], edit={2: "Total Fat sixteen grams"})
    assert it.composition_report(s["sample_code"])["record"] is None  # nothing half-saved
    r = it.read_label(photo(), "nutrition")
    with pytest.raises(LibraryError):  # rows can only be the server's own OCR rows
        it.apply_label(s["sample_code"], {"label_draft": r["label_draft"],
                                          "attest": {"signer": "x", "rows": [{"index": 99, "text": "Protein 7g"}]}})  # fmt: skip


def test_tampered_photo_or_value_fails(setup: tuple[FoodLibrary, Intake], tmp_path: Path) -> None:
    lib, it = setup
    s = lib.create_sample(bc.normalise("96385074"))
    attest_all(it, s["sample_code"])
    comp = it.composition
    assert comp is not None
    path = comp.record_path(s["sample_code"])
    rec = json.loads(path.read_text())
    sha = rec["sources"][0]["sha256"]
    blob = comp.store / "sha256" / sha[:2] / sha
    blob.chmod(0o644)
    good = blob.read_bytes()
    blob.write_bytes(good[:-1] + bytes([good[-1] ^ 1]))
    assert Verifier(comp.store, RULES).verify(path).ok is False
    blob.write_bytes(good)
    next(f for f in rec["facts"] if f["id"] == "P1_sodium")["value"]["hi"] = "150"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(rec))
    assert Verifier(comp.store, RULES).verify(bad).ok is False


def test_rebuild_is_byte_identical(setup: tuple[FoodLibrary, Intake]) -> None:
    lib, it = setup
    s = lib.create_sample(bc.normalise("96385074"))
    attest_all(it, s["sample_code"])
    comp = it.composition
    assert comp is not None
    first = comp.record_path(s["sample_code"]).read_bytes()
    comp.rebuild(lib.sample(s["sample_code"]), lib.product(bc.normalise("96385074")))
    assert comp.record_path(s["sample_code"]).read_bytes() == first


def test_signer_is_required_by_the_service(tmp_path: Path) -> None:
    comp = SampleComposition(tmp_path / "c", RULES)
    with pytest.raises(CompositionError):
        comp.attest_panel({"sample_code": "X"}, {}, photo(), [600, 900], [], "")


# ------------------------------------------------------------------ export


def test_training_export_carries_interval_badge_and_assumptions(
    setup: tuple[FoodLibrary, Intake],
) -> None:
    lib, it = setup
    s = lib.create_sample(bc.normalise("96385074"))
    attest_all(it, s["sample_code"])
    comp = it.composition
    assert comp is not None
    table = rows(sorted(comp.records.glob("*.json")), Verifier(comp.store, RULES))
    fat = next(r for r in table if r["id"] == "P1_total_fat")
    assert (fat["lo"], fat["hi"], fat["lo_closed"], fat["hi_closed"], fat["unit"]) == (
        "31/2",
        "33/2",
        True,
        False,
        "g",
    )
    assert fat["badge"] == "ATTESTED" and fat["assumptions"] == "S1;S2"
    est = [r for r in table if r["kind"] == "estimate"]
    assert est and all(r["badge"] == "UNVERIFIED" for r in est)
    head = to_csv(table).splitlines()[0]
    assert head.startswith("record_id,gtin14,sample_code,kind,id,quantity,basis,lo,hi")


def test_golden_export_is_all_verified() -> None:
    comp_dir = REPO / "composition"
    table = rows(
        sorted((comp_dir / "records").glob("*.json")), Verifier(comp_dir / "sources", RULES)
    )
    assert table and {r["badge"] for r in table if r["kind"] != "estimate"} == {"VERIFIED"}


# -------------------------------------------------------------- OCR rows


def L(text: str, x: float, y: float, w: float = 0.2, h: float = 0.02) -> Line:
    return Line(text, 1.0, x, y, w, h)


def test_split_ocr_lines_are_joined_into_panel_rows() -> None:
    lines = [
        L("Serving size", 0.05, 0.80, 0.25), L("2 Tbsp (32g)", 0.40, 0.801, 0.25),
        L("Total Fat", 0.05, 0.70), L("16g", 0.30, 0.702, 0.06), L("21%", 0.80, 0.70, 0.08),
        L("Sodium 140mg", 0.05, 0.65, 0.3), L("6%", 0.80, 0.65, 0.05),
        L("Protein 7g", 0.05, 0.60, 0.3),
    ]  # fmt: skip
    joined = [ln.text for ln in visual_rows(lines)]
    assert "Total Fat 16g" in " | ".join(joined)
    found = {r["nutrient"]: r for r in panel_rows(lines, (1000, 2000))}
    assert found["serving"]["value_raw"] == "32 g"
    assert found["total_fat"]["value_raw"] == "16 g"
    assert found["sodium"]["value_raw"] == "140 mg"
    b = found["protein"]["box"]
    assert b["x"] == 50 and b["y"] == round((1 - 0.60 - 0.02) * 2000)
