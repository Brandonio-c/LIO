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

    def attest_ingredients(
        self,
        sample: dict[str, Any],
        product: dict[str, Any],
        photo: bytes,
        image_size: list[int],
        box: dict[str, int],
        text: str,
        signer: str,
    ) -> dict[str, Any]:
        """Record an ingredient-panel photo whose list the operator confirmed word for word."""
        signer = " ".join(signer.split())
        text = " ".join(text.split())
        if not signer:
            raise CompositionError("type your name to attest the ingredient list")
        try:
            items = textrules.split_list(text)
        except textrules.RuleError as e:
            raise CompositionError(str(e)) from e
        if not items:
            raise CompositionError("the ingredient list is empty")
        code = sample["sample_code"]
        signed_at = now_utc()
        with self._lock:
            sha = put(
                self.store,
                photo,
                _media_type(photo),
                Retrieval(
                    f"lio://samples/{code}/label-ingredients",
                    signed_at,
                    {"sample_code": code, "gtin14": sample.get("gtin14", "")},
                    PHOTO_RETRIEVER,
                ),
            )
            entry = {
                "kind": "ingredients_panel",
                "photo_sha256": sha,
                "image_size": [int(image_size[0]), int(image_size[1])],
                "box": {k: int(box[k]) for k in ("x", "y", "w", "h")},
                "text": text,
                "signer": signer,
                "signed_at": signed_at,
            }
            log = [*self.log(code), entry]
            self.evidence.mkdir(parents=True, exist_ok=True)
            (self.evidence / f"{code}.json").write_bytes(canonical_json(log))
        return self.rebuild(sample, product)

    def attest_fields(
        self,
        sample: dict[str, Any],
        product: dict[str, Any],
        photo: bytes,
        image_size: list[int],
        kind: str,
        fields: list[dict[str, Any]],
        signer: str,
        engine: str,
    ) -> dict[str, Any]:
        """Record confirmed Drug Facts / Supplement Facts fields of a panel photo."""
        signer = " ".join(signer.split())
        if not signer:
            raise CompositionError("type your name to attest the fields")
        code = sample["sample_code"]
        signed_at = now_utc()
        keep = ("field", "rule", "text", "box", "element", "name")
        with self._lock:
            sha = put(
                self.store,
                photo,
                _media_type(photo),
                Retrieval(
                    f"lio://samples/{code}/label-{kind}",
                    signed_at,
                    {"sample_code": code, "gtin14": sample.get("gtin14", "")},
                    PHOTO_RETRIEVER,
                ),
            )
            entry = {
                "kind": f"{kind}_panel",
                "photo_sha256": sha,
                "image_size": [int(v) for v in image_size],
                "fields": [{k: f[k] for k in keep if k in f} for f in fields],
                "ocr_engine": engine,
                "signer": signer,
                "signed_at": signed_at,
            }
            log = [*self.log(code), entry]
            self.evidence.mkdir(parents=True, exist_ok=True)
            (self.evidence / f"{code}.json").write_bytes(canonical_json(log))
        return self.rebuild(sample, product)

    def link_ndc(
        self,
        sample: dict[str, Any],
        product: dict[str, Any],
        photo: bytes,
        image_size: list[int],
        candidate: dict[str, Any],
        signer: str,
        spl: dict[str, Any],
        spl_xml: bytes,
    ) -> dict[str, Any]:
        """Record the operator-confirmed printed NDC (photo, box, span) and the exact SPL it
        resolves to; returns the crosswalk row to append."""
        signer = " ".join(signer.split())
        if not signer:
            raise CompositionError("type your name to attest the NDC")
        if textrules.apply("printed_ndc@1", candidate["text"]) != candidate["ndc11"]:
            raise CompositionError(f"{candidate['text']!r} is not a printed NDC")
        code = sample["sample_code"]
        signed_at = now_utc()
        with self._lock:
            sha = put(self.store, photo, _media_type(photo),
                      Retrieval(f"lio://samples/{code}/label-ndc", signed_at,
                                {"sample_code": code, "gtin14": sample.get("gtin14", "")}, PHOTO_RETRIEVER))  # fmt: skip
            spl_sha = put(self.store, spl_xml, "application/xml",
                          Retrieval(f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{spl['setid']}.xml",
                                    signed_at, {"spl_setid": spl["setid"], "spl_version": str(spl["version"])}))  # fmt: skip
            entry = {
                "kind": "ndc_link", "photo_sha256": sha, "image_size": [int(image_size[0]), int(image_size[1])],
                "box": {k: int(candidate["box"][k]) for k in ("x", "y", "w", "h")},
                "text": candidate["text"], "ndc": candidate["ndc"], "ndc11": candidate["ndc11"],
                "setid": spl["setid"], "spl_version": spl["version"], "spl_sha256": spl_sha,
                "signer": signer, "signed_at": signed_at,
            }  # fmt: skip
            log = [*self.log(code), entry]
            self.evidence.mkdir(parents=True, exist_ok=True)
            (self.evidence / f"{code}.json").write_bytes(canonical_json(log))
        self.rebuild(sample, product)
        return {
            "gtin": sample["gtin14"], "ndc": candidate["ndc"], "ndc11": candidate["ndc11"],
            "setid": spl["setid"], "spl_version": spl["version"], "method": "printed_ndc",
            "evidence": {"photo_sha256": sha, "bbox": entry["box"], "ndc_text": candidate["text"],
                         "sample_code": code},
            "attestation": {"operator": signer, "timestamp": signed_at, "signature": "",
                            "statement": f"I confirmed that {candidate['text']} is printed on the carton of sample {code}."},
        }  # fmt: skip

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
        if any(e.get("kind", "nutrition_panel") == "nutrition_panel" for e in log):
            # only cited by Nutrition Facts values (the verifier refuses uncited assumptions)
            b.assume("S2", "label_truth", "The label states the sample's composition.")
            b.assume("S3", "interpretation", "The serving size in grams is taken as printed.")
        for n, entry in enumerate(log, start=1):
            sid = f"P{n}"
            b.source_sha(sid, entry["photo_sha256"], {"sample_code": code})
            b.head["physical_sample"]["photos"].append(entry["photo_sha256"])
            att = f"AT{n}"
            if entry.get("kind") in ("drug_facts_panel", "supplement_facts_panel"):
                self._panel_entry(b, n, sid, att, entry, code)
                continue
            if entry.get("kind") == "ndc_link":
                b.attestations.append({
                    "id": att, "signer": entry["signer"], "signed_at": entry["signed_at"],
                    "statement": f"I confirmed that {entry['text']} is printed on the carton of sample {code} (photo {entry['photo_sha256'][:12]}).",
                    "subjects": [f"L{n}"],
                })  # fmt: skip
                b.link(f"L{n}", method="printed_ndc", ndc11=entry["ndc11"], attestation_id=att,
                       source_id=sid, box=entry["box"], span=entry["text"])  # fmt: skip
                b.source_sha(f"S_spl{n}", entry["spl_sha256"], {"spl_setid": entry["setid"]})
                b.select(f"SEL{n}", f"L{n}", f"S_spl{n}", entry["ndc"], None,
                         {"v": "urn:hl7-org:v3"})  # fmt: skip
                if b.head["physical_sample"]["attestation"] is None:
                    b.head["physical_sample"]["attestation"] = att
                continue
            if entry.get("kind") == "ingredients_panel":
                loc = {
                    "type": "image_bbox",
                    **entry["box"],
                    "text": entry["text"],
                    "attestation_id": att,
                }
                ids = []
                for k in range(1, len(textrules.split_list(entry["text"])) + 1):
                    ing = b.ingredient(f"{sid}_I{k}", f"label_photo_{n}", k, "food", sid, loc,
                                       list_rule=f"list_item@1:{k}")  # fmt: skip
                    ids.append(ing["id"])
                b.attestations.append({
                    "id": att, "signer": entry["signer"], "signed_at": entry["signed_at"],
                    "statement": (f"I compared the ingredient list below, word for word, with the "
                                  f"ingredient panel in photo {entry['photo_sha256'][:12]} of "
                                  f"sample {code}; it matches the label."),
                    "subjects": ids,
                })  # fmt: skip
                if b.head["physical_sample"]["attestation"] is None:
                    b.head["physical_sample"]["attestation"] = att
                continue
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

    def _panel_entry(
        self, b: RecordBuilder, n: int, sid: str, att: str, entry: dict[str, Any], code: str
    ) -> None:
        drug = entry["kind"] == "drug_facts_panel"
        lt = b.assume("S2", "label_truth", "The label states the sample's composition.")
        otc = {"sodium", "calcium", "potassium"}
        needs_as_stated = any(
            f["field"] in ("active", "row")
            or (f["field"] == "contains" and f.get("element") not in otc)
            for f in entry["fields"]
        )
        st = ""
        if needs_as_stated:
            st = b.assume(
                "S6",
                "interpretation",
                "Drug Facts strengths and Supplement Facts amounts are taken as stated "
                "(no rounding rule applies).",
            )
        subjects: list[str] = []
        for k, f in enumerate(entry["fields"], start=1):
            loc = {"type": "image_bbox", **f["box"], "text": f["text"], "attestation_id": att}
            fid = f"{sid}_{k}"
            if f["field"] in ("active", "row"):
                b.fact(
                    fid,
                    f.get("name") or "active_ingredient",
                    "per_unit",
                    sid,
                    loc,
                    f["rule"],
                    {"kind": "as_stated", "assumption": st},
                    assumptions=(lt, st),
                    evidence_class="attested",
                )
            elif f["field"] == "contains":
                el = f["element"]
                if el in otc:
                    interp: dict[str, Any] = {
                        "kind": "rounded",
                        "rule": f"fda_otc_rounding_201@1:{el}",
                    }
                    asm: tuple[str, ...] = (lt,)
                else:
                    interp, asm = {"kind": "as_stated", "assumption": st}, (lt, st)
                b.fact(
                    fid,
                    el,
                    "per_unit",
                    sid,
                    loc,
                    f["rule"],
                    interp,
                    assumptions=asm,
                    evidence_class="attested",
                )
            elif f["field"] in ("inactive_list", "other_list"):
                items = textrules.split_list2(f["text"])
                role = "inactive" if drug else "other"
                for j in range(1, len(items) + 1):
                    b.ingredient(
                        f"{fid}_{j}",
                        f"{entry['kind']}_{f['field']}_{n}",
                        j,
                        role,
                        sid,
                        loc,
                        list_rule=f"list_item@2:{j}",
                    )
                    subjects.append(f"{fid}_{j}")
                continue
            elif f["field"] == "blend_member":
                b.ingredient(fid, f"blend_{n}", k, "dietary", sid, loc)
            else:
                continue
            subjects.append(fid)
        panel = "Drug" if drug else "Supplement"
        b.attestations.append(
            {
                "id": att,
                "signer": entry["signer"],
                "signed_at": entry["signed_at"],
                "statement": (
                    f"I compared each field below with the {panel} Facts panel in photo "
                    f"{entry['photo_sha256'][:12]} of sample {code}; they match "
                    f"(text read by {entry.get('ocr_engine') or 'OCR'})."
                ),
                "subjects": subjects,
            }
        )
        if b.head["physical_sample"]["attestation"] is None:
            b.head["physical_sample"]["attestation"] = att

    # --------------------------------------------------------------- verify
    def report(self, code: str) -> dict[str, Any] | None:
        p = self.record_path(code)
        if not p.exists():
            return None
        return Verifier(self.store, self.rules, self.schema).verify(p).to_json()
