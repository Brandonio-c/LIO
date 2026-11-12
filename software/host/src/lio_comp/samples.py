# ruff: noqa: E501  (statement and method texts are kept whole)
"""Composition records for food-library samples: the photo attestation flow (spec §9).

When the operator saves a Nutrition Facts photo and confirms its rows:

1. the photo bytes go into the evidence store (``data/foods/composition/sources``);
2. an entry is appended to the sample's evidence log (photo hash, the rows as
   confirmed, each row's pixel box from the server's own OCR, signer, time);
3. the sample's record is rebuilt from the log: one ATTESTED fact per row
   (``image_bbox`` locator; the confirmed text re-parsed by ``nfp_row@1`` and
   interpreted with the 21 CFR 101.9(c) rounding rules), per-100 g
   derivations, an attestation per photo, and the library's own (database or
   OCR) values in the unverified layer.

The log is the only input besides the store and the rules, so a rebuild is
byte-identical.
"""

from __future__ import annotations

import io
import json
import threading
from fractions import Fraction
from pathlib import Path
from typing import Any

from lio_comp.derive import derive
from lio_comp.evidence import Retrieval, canonical_json, put
from lio_comp.fetch import now_utc
from lio_comp.record import RecordBuilder
from lio_verify import textrules
from lio_verify.interpret import load_tables
from lio_verify.interval import format_rational
from lio_verify.verify import Verifier

PHOTO_RETRIEVER = "lio.foods.label_photo@1"
MASS_UNITS = {"g", "mg", "kcal"}
LIBRARY_KEYS = {  # food-library nutrition keys -> (quantity, unit)
    "energy_kcal": ("energy", "kcal"), "fat_g": ("total_fat", "g"),
    "saturated_fat_g": ("saturated_fat", "g"), "trans_fat_g": ("trans_fat", "g"),
    "cholesterol_mg": ("cholesterol", "mg"), "sodium_mg": ("sodium", "mg"),
    "carbohydrates_g": ("total_carbohydrate", "g"), "fiber_g": ("dietary_fiber", "g"),
    "sugars_g": ("total_sugars", "g"), "added_sugars_g": ("added_sugars", "g"),
    "protein_g": ("protein", "g"), "salt_g": ("salt", "g"),
}  # fmt: skip


class CompositionError(ValueError):
    """A request the composition layer refuses (shown to the user)."""


def _media_type(photo: bytes) -> str:
    from PIL import Image

    fmt = (Image.open(io.BytesIO(photo)).format or "").lower()
    return {"jpeg": "image/jpeg", "png": "image/png", "heic": "image/heic"}.get(fmt, "image/jpeg")


def _decimal(v: Any) -> str | None:
    """A library number (float from a database or OCR) as an exact rational of its decimal
    spelling. Only used in the unverified layer."""
    try:
        return format_rational(Fraction(repr(float(v))))
    except (TypeError, ValueError):
        return None


class SampleComposition:
    def __init__(self, root: Path, rules: Path, schema: Path | None = None) -> None:
        self.root = root
        self.store = root / "sources"
        self.records = root / "records"
        self.evidence = root / "evidence"
        self.rules = rules
        self.schema = schema or rules.parent / "schema" / "record.schema.json"
        self._lock = threading.Lock()

    def available(self) -> bool:
        return self.rules.is_dir() and self.schema.is_file()

    def record_path(self, code: str) -> Path:
        return self.records / f"sample_{code}.json"

    def log(self, code: str) -> list[dict[str, Any]]:
        p = self.evidence / f"{code}.json"
        return list(json.loads(p.read_text())) if p.exists() else []

    # ----------------------------------------------------------- attestation
    def attest_panel(
        self,
        sample: dict[str, Any],
        product: dict[str, Any],
        photo: bytes,
        image_size: list[int],
        rows: list[dict[str, Any]],
        signer: str,
    ) -> dict[str, Any]:
        """Record a Nutrition Facts photo whose rows the operator confirmed."""
        signer = " ".join(signer.split())
        if not signer:
            raise CompositionError("type your name to attest the values")
        if not rows:
            raise CompositionError("no confirmed rows to attest")
        for r in rows:
            try:
                r["value_raw"] = textrules.apply(r["rule"], r["text"])
            except (textrules.RuleError, KeyError) as e:
                raise CompositionError(f"cannot read {r.get('text')!r}: {e}") from e
        code = sample["sample_code"]
        signed_at = now_utc()
        with self._lock:
            sha = put(
                self.store,
                photo,
                _media_type(photo),
                Retrieval(
                    f"lio://samples/{code}/label-nutrition",
                    signed_at,
                    {"sample_code": code, "gtin14": sample.get("gtin14", "")},
                    PHOTO_RETRIEVER,
                ),
            )
            entry = {
                "kind": "nutrition_panel",
                "photo_sha256": sha,
                "image_size": [int(image_size[0]), int(image_size[1])],
                "rows": [{k: r[k] for k in ("nutrient", "rule", "text", "box")} for r in rows],
                "signer": signer,
                "signed_at": signed_at,
            }
            log = [*self.log(code), entry]
            self.evidence.mkdir(parents=True, exist_ok=True)
            (self.evidence / f"{code}.json").write_bytes(canonical_json(log))
        return self.rebuild(sample, product)

    # ---------------------------------------------------------------- build
    def rebuild(self, sample: dict[str, Any], product: dict[str, Any]) -> dict[str, Any]:
        code = sample["sample_code"]
        log = self.log(code)
        if not log:
            raise CompositionError(f"{code} has no attested label yet")
        b = RecordBuilder(
            self.store,
            load_tables(self.rules),
            record_id=f"sample_{code}",
            gtin=str(sample.get("gtin14") or "0" * 14),
            product_name=str(product.get("name") or "unknown product"),
            variant_note="Facts are the operator's attested transcriptions of label photos of "
            "this physical sample.",
        )
        b.head["physical_sample"]["sample_code"] = code
        b.assume("S1", "sample_identity", f"Every label photo in this record is of sample {code}.")
        b.assume("S2", "label_truth", "The label states the sample's composition.")
        b.assume("S3", "interpretation", "The serving size in grams is taken as printed.")
        for n, entry in enumerate(log, start=1):
            sid = f"P{n}"
            b.source_sha(sid, entry["photo_sha256"], {"sample_code": code})
            b.head["physical_sample"]["photos"].append(entry["photo_sha256"])
            att = f"AT{n}"
            subjects: list[str] = []
            serving = None
            for r in entry["rows"]:
                fid = f"{sid}_{r['nutrient']}"
                loc = {"type": "image_bbox", **r["box"], "text": r["text"], "attestation_id": att}
                if r["nutrient"] == "serving":
                    b.fact(fid, "serving_mass", "per_serving", sid, loc, r["rule"],
                           {"kind": "as_stated", "assumption": "S3"},
                           assumptions=("S2", "S3"), evidence_class="attested")  # fmt: skip
                    serving = fid
                else:
                    b.fact(fid, r["nutrient"], "per_serving", sid, loc, r["rule"],
                           {"kind": "rounded", "rule": f"fda_rounding_101_9@1:{r['nutrient']}"},
                           assumptions=("S2",), evidence_class="attested")  # fmt: skip
                subjects.append(fid)
            b.attestations.append({
                "id": att, "signer": entry["signer"], "signed_at": entry["signed_at"],
                "statement": (f"I compared each value below with the Nutrition Facts panel in photo "
                              f"{entry['photo_sha256'][:12]} of sample {code}; they match the label."),
                "subjects": subjects,
            })  # fmt: skip
            if b.head["physical_sample"]["attestation"] is None:
                b.head["physical_sample"]["attestation"] = att
            if serving:
                for f in [f for f in b.facts if f["source_id"] == sid and f["id"] != serving]:
                    if f["value"]["unit"] in MASS_UNITS:
                        derive(b, f"{f['id']}_per100g", f["quantity"], "per_100g",
                               ["rescale_basis", f["id"], serving, "N:100:g"], ("S3",))  # fmt: skip
        info = product.get("info") or {}
        for key, v in sorted((info.get("nutrition_per_100g") or {}).items()):
            if key in LIBRARY_KEYS and (val := _decimal(v)) is not None:
                q, unit = LIBRARY_KEYS[key]
                b.estimates.append({
                    "quantity": q, "basis": "per_100g", "value": val, "unit": unit,
                    "method": f"food library value (source: {info.get('nutrition_source') or product.get('sources') or 'database'}); not verified",
                    "inputs": [f"product {product.get('gtin14', '')}"],
                })  # fmt: skip
        path = b.write(self.records)
        return {"record": str(path), "report": self.report(code)}

    # --------------------------------------------------------------- verify
    def report(self, code: str) -> dict[str, Any] | None:
        p = self.record_path(code)
        if not p.exists():
            return None
        return Verifier(self.store, self.rules, self.schema).verify(p).to_json()
