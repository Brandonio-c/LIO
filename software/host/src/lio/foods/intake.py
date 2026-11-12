"""Adding a sample in two steps: identify (photo or typed digits), then save.

``identify`` decodes the barcode, looks the product up and keeps the photo as
a short-lived draft; ``commit`` turns the draft into a sample. The phone app
and the dashboard both use this.
"""

from __future__ import annotations

import base64
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .barcode import BarcodeError, Gtin, best_code, decode_image, decoder_available, normalise
from .ocr import OcrError, read_label
from .store import LABEL_KINDS, FoodLibrary, LibraryError

DRAFT_TTL_S = 30 * 60
MAX_DRAFTS = 50


def data_url_bytes(value: Any) -> bytes | None:
    """``data:image/jpeg;base64,...`` (or bare base64) -> bytes; None for empty."""
    if not value:
        return None
    s = str(value)
    if s.startswith("data:"):
        s = s.split(",", 1)[-1]
    try:
        return base64.b64decode(s, validate=False)
    except ValueError as e:
        raise LibraryError(f"bad image data: {e}") from e


@dataclass
class _Draft:
    gtin: Gtin
    scanned_text: str
    fmt: str
    photo: bytes | None
    at: float = field(default_factory=time.monotonic)


class Intake:
    def __init__(self, lib: FoodLibrary, composition: Any = None) -> None:
        self.lib = lib
        # lio_comp.samples.SampleComposition, or None without the composition extra / rules
        self.composition = composition
        self._drafts: dict[str, _Draft] = {}
        # id -> (at, kind, photo, text, OCR result: panel rows with boxes, image size)
        self._labels: dict[str, tuple[float, str, bytes, str, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def _put(self, d: _Draft) -> str:
        key = secrets.token_urlsafe(12)
        with self._lock:
            now = time.monotonic()
            for k in [k for k, v in self._drafts.items() if now - v.at > DRAFT_TTL_S]:
                del self._drafts[k]
            while len(self._drafts) >= MAX_DRAFTS:
                del self._drafts[next(iter(self._drafts))]
            self._drafts[key] = d
        return key

    def identify(self, photo: bytes | None, typed: str = "") -> dict[str, Any]:
        """Decode (or take the typed digits), look the product up, keep a draft."""
        found: list[dict[str, str]] = []
        if typed.strip():
            gtin, text, fmt = normalise(typed), typed.strip(), "typed"
        elif photo:
            decoded = decode_image(photo)
            if best_code(decoded) is None:  # keep the failing photo so it can be inspected
                debug = self.lib.root / "debug"
                debug.mkdir(exist_ok=True)
                (debug / "last_failed_photo.jpg").write_bytes(photo)
            found = [{"text": d.text, "format": d.format} for d in decoded]
            best = best_code(decoded)
            if best is None:
                why = (
                    "no barcode found in the photo"
                    if not decoded
                    else "found "
                    + ", ".join(f"{d.format} {d.text!r}" for d in decoded)
                    + " but no valid retail (EAN/UPC) code"
                )
                raise BarcodeError(f"{why}: retake it closer and flatter, or type the digits")
            gtin, d = best
            text, fmt = d.text, d.format
        else:
            raise BarcodeError("send a photo of the barcode or type its digits")
        product = self.lib.product(gtin)
        existing = [
            {"sample_code": s["sample_code"], "created_at": s["created_at"]}
            for s in self.lib.samples(gtin.gtin14)
            if s["gtin14"] == gtin.gtin14
        ]
        draft = self._put(_Draft(gtin, text, fmt, photo))
        return {
            "draft": draft,
            "gtin14": gtin.gtin14,
            "code": gtin.code,
            "kind": gtin.kind,
            "format": fmt,
            "decoded": found,
            "product": product,
            "existing_samples": existing,
        }

    # ------------------------------------------------------------ label photos

    def read_label(self, photo: bytes | None, kind: str) -> dict[str, Any]:
        """Read an ingredient or nutrition panel; the photo waits as a draft until applied."""
        if kind not in LABEL_KINDS:
            raise LibraryError(f"label kind must be one of {LABEL_KINDS}")
        if not photo:
            raise LibraryError("no photo")
        try:
            res = read_label(photo)
        except OcrError as e:
            raise LibraryError(str(e)) from e
        if not res["lines"]:
            raise LibraryError("no text found: hold the phone closer and flatter, with good light")
        key = secrets.token_urlsafe(12)
        with self._lock:
            now = time.monotonic()
            for k in [k for k, v in self._labels.items() if now - v[0] > DRAFT_TTL_S]:
                del self._labels[k]
            while len(self._labels) >= MAX_DRAFTS:
                del self._labels[next(iter(self._labels))]
            self._labels[key] = (now, kind, photo, res["text"], res)
        rows = [{"index": i, **r} for i, r in enumerate(res.get("panel_rows") or [])]
        can_attest = kind == "nutrition" and self.composition is not None and bool(rows)
        return {"label_draft": key, "kind": kind, **res, "panel_rows": rows,
                "can_attest": can_attest}  # fmt: skip

    def apply_label(self, code: str, label: dict[str, Any]) -> dict[str, Any]:
        """Store a reviewed label photo with its sample and put its data on the product.

        ``label``: {label_draft, ingredients_text?, contains?, nutrition_per_100g?, serving_size?,
        attest?: {signer, rows: [{index, text}]}}. With ``attest``, the confirmed Nutrition
        Facts rows become ATTESTED facts in the sample's composition record; each row's box
        comes from this server's OCR of the photo, only the confirmed text from the client.
        """
        with self._lock:
            d = self._labels.pop(str(label.get("label_draft") or ""), None)
        if d is None:
            raise LibraryError("this label photo expired or was already saved: take it again")
        _, kind, photo, text, res = d
        attest = self._attested_rows(kind, res, label.get("attest"))
        sample = self.lib.add_label_photo(code, kind, photo, text)
        fields: dict[str, Any] = {}
        if kind == "ingredients" and str(label.get("ingredients_text") or "").strip():
            fields["ingredients_text"] = str(label["ingredients_text"])
            if str(label.get("contains") or "").strip():
                fields["contains"] = str(label["contains"])
        if kind == "nutrition":
            per = {
                k: v
                for k, v in (label.get("nutrition_per_100g") or {}).items()
                if v not in (None, "")
            }
            if per:
                fields["nutrition_per_100g"] = per
            if str(label.get("serving_size") or "").strip():
                fields["serving_size"] = str(label["serving_size"])
        if fields:
            self.lib.set_product_info(sample["gtin14"], fields, source="label photo")
        out = self.lib.sample(code)
        if attest is not None:
            signer, rows = attest
            from lio_comp.samples import CompositionError

            product = self.lib.product(normalise(out["gtin14"]))
            try:
                out["composition"] = self.composition.attest_panel(
                    out, product, photo, res["image_size"], rows, signer
                )
            except CompositionError as e:
                raise LibraryError(f"the label was saved, but not attested: {e}") from e
        return out

    def _attested_rows(
        self, kind: str, res: dict[str, Any], attest: Any
    ) -> tuple[str, list[dict[str, Any]]] | None:
        """Validate an attestation request before anything is saved."""
        if not attest:
            return None
        if kind != "nutrition" or self.composition is None:
            raise LibraryError("only Nutrition Facts photos can be attested here")
        signer = " ".join(str(attest.get("signer") or "").split())
        if not signer:
            raise LibraryError("type your name to attest the values")
        ocr_rows = res.get("panel_rows") or []
        rows: list[dict[str, Any]] = []
        for item in attest.get("rows") or []:
            i = int(item.get("index", -1))
            if not 0 <= i < len(ocr_rows):
                raise LibraryError("an attested row is not in this photo")
            rows.append({**ocr_rows[i], "text": " ".join(str(item.get("text") or "").split())})
        if not rows:
            raise LibraryError("tick at least one row that matches the label")
        from lio_verify import textrules

        for r in rows:
            try:
                textrules.apply(r["rule"], r["text"])
            except textrules.RuleError as e:
                raise LibraryError(f"{r['nutrient']}: {e}") from e
        return signer, rows

    def composition_report(self, code: str) -> dict[str, Any]:
        """The sample's composition record, verified now (badges come from the verifier)."""
        if self.composition is None:
            return {"available": False, "record": None, "report": None}
        p = self.composition.record_path(code)
        rec = json.loads(p.read_text()) if p.exists() else None
        return {"available": True, "record": rec, "report": self.composition.report(code)}

    # ------------------------------------------------------ ingredients online

    def find_online(self, gtin14: str, query: str = "") -> dict[str, Any]:
        """Every fallback at once: label databases by name, then the web.

        Nothing is saved: the caller shows each result with its link and the
        user confirms (see :meth:`confirm_ingredients`).
        """
        lib = self.lib
        if lib.lookup is None:
            raise LibraryError("online lookup is off (foods.online_lookup)")
        g = normalise(gtin14)
        p = lib.product(g)
        name = " ".join(x for x in (p["brand"], p["name"]) if x).strip()
        q = query.strip() or name or g.code
        out: dict[str, Any] = {"query": q, "structured": [], "web": None, "errors": []}

        def structured() -> None:
            if q and not q.isdigit():
                try:
                    out["structured"] = lib.lookup.search_by_name(q) if lib.lookup else []
                except ValueError as e:
                    out["errors"].append(str(e))

        def web() -> None:
            if lib.web is not None:
                out["web"] = lib.web.find(f"{q} ingredients", brand_hint=p["brand"] or q)

        threads = [threading.Thread(target=structured), threading.Thread(target=web)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        return out

    def confirm_ingredients(self, gtin14: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Save an ingredient list the user confirmed, with the links it came from."""
        text = str(fields.get("ingredients_text") or "").strip()
        if not text:
            raise LibraryError("the ingredient list is empty")
        refs = fields.get("refs") if isinstance(fields.get("refs"), list) else []
        src = "web" if refs else "manual"
        data: dict[str, Any] = {"ingredients_text": text, "ingredients_refs": refs}
        if str(fields.get("contains") or "").strip():
            data["contains"] = str(fields["contains"])
        return self.lib.set_product_info(gtin14, data, source=src)

    def commit(self, draft: str, fields: dict[str, Any], *, source: str) -> dict[str, Any]:
        with self._lock:
            d = self._drafts.pop(draft, None)
        if d is None:
            raise LibraryError("this scan expired or was already saved: scan again")
        sample = self.lib.create_sample(
            d.gtin,
            scanned_text=d.scanned_text,
            barcode_format=d.fmt,
            barcode_photo=d.photo,
            product_photo=data_url_bytes(fields.get("product_photo")),
            lot=str(fields.get("lot") or ""),
            best_before=str(fields.get("best_before") or ""),
            notes=str(fields.get("notes") or ""),
            entered_by=str(fields.get("entered_by") or ""),
            source=source,
        )
        for label in fields.get("labels") or []:
            if isinstance(label, dict):
                sample = self.apply_label(sample["sample_code"], label)
        found = fields.get("ingredients_found")
        if isinstance(found, dict) and str(found.get("ingredients_text") or "").strip():
            self.confirm_ingredients(sample["gtin14"], found)
            sample = self.lib.sample(sample["sample_code"])
        return sample

    @staticmethod
    def can_decode() -> bool:
        return decoder_available()
