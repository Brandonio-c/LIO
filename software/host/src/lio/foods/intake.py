"""Adding a sample in two steps: identify (photo or typed digits), then save.

``identify`` decodes the barcode, looks the product up and keeps the photo as
a short-lived draft; ``commit`` turns the draft into a sample. The phone app
and the dashboard both use this.
"""

from __future__ import annotations

import base64
import json
import re
import secrets
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from . import structure
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


def retailer_links(code: str, query: str) -> list[dict[str, str]]:
    """Retailer searches for the user to open themselves. They are never fetched by
    this program (retailers' terms forbid automated access)."""
    q = urllib.parse.quote_plus(code)
    return [
        {"name": "Walmart", "url": f"https://www.walmart.com/search?q={q}"},
        {"name": "Target", "url": f"https://www.target.com/s?searchTerm={q}"},
        {"name": "Amazon", "url": f"https://www.amazon.com/s?k={q}"},
        {"name": "Kroger", "url": f"https://www.kroger.com/search?query={q}"},
        {
            "name": "Google Shopping",
            "url": f"https://www.google.com/search?tbm=shop&q={urllib.parse.quote_plus(query)}",
        },
    ]


def _search_words(text: str) -> set[str]:
    """Words for matching a search to a product name ("caplets" ~ "tablet")."""
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        w = {"caplet": "tablet", "caplets": "tablet", "tablets": "tablet", "sf": "sugar"}.get(w, w)
        out.add(w[:-1] if len(w) > 4 and w.endswith("s") else w)
    return out


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
            res = read_label(photo, kind)
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
        if kind == "ndc":
            return {
                "label_draft": key,
                "kind": kind,
                **res,
                "can_attest": bool(res.get("ndc_candidates")),
            }
        if kind in ("drug_facts", "supplement_facts"):
            from .panels import flatten

            fields = flatten(kind, res.get("panel"))
            res["panel_fields"] = fields
            return {
                "label_draft": key,
                "kind": kind,
                **res,
                "can_attest": self.composition is not None and bool(fields),
            }
        can_attest = self.composition is not None and (
            (kind == "nutrition" and bool(rows))
            or (kind == "ingredients" and res.get("ingredient_box") is not None)
        )
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
        if kind == "ndc":
            return self._apply_ndc(code, photo, res, label)
        if kind in ("drug_facts", "supplement_facts"):
            return self._apply_panel(code, kind, photo, text, res, label)
        attest = None
        if kind == "ingredients" and label.get("attest"):
            attest_ingr = self._attested_list(res, label)
        else:
            attest_ingr = None
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
        if attest_ingr is not None:
            from lio_comp.samples import CompositionError

            signer, list_text = attest_ingr
            product = self.lib.product(normalise(out["gtin14"]))
            try:
                out["composition"] = self.composition.attest_ingredients(
                    out, product, photo, res["image_size"], res["ingredient_box"], list_text, signer
                )
            except CompositionError as e:
                raise LibraryError(f"the label was saved, but not attested: {e}") from e
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

    def _apply_panel(
        self,
        code: str,
        kind: str,
        photo: bytes,
        text: str,
        res: dict[str, Any],
        label: dict[str, Any],
    ) -> dict[str, Any]:
        """Drug Facts / Supplement Facts fields the operator ticked (texts may be corrected;
        boxes are this server's) become ATTESTED facts in the sample's record."""
        att = label.get("attest") or {}
        signer = " ".join(str(att.get("signer") or "").split())
        fields = res.get("panel_fields") or []
        picked = []
        for item in att.get("fields") or []:
            i = int(item.get("index", -1))
            if not 0 <= i < len(fields):
                raise LibraryError("a ticked field is not in this photo")
            corrected = " ".join(str(item.get("text") or fields[i]["text"]).split())
            picked.append({**fields[i], "text": corrected})
        if picked and (self.composition is None or not signer):
            raise LibraryError("type your name to attest the ticked fields")
        from lio_verify import textrules

        for f in picked:
            try:
                if f["rule"] == "list_item@2":
                    if not textrules.split_list2(f["text"]):
                        raise textrules.RuleError("the list is empty")
                elif f["rule"]:
                    textrules.apply(f["rule"], f["text"])
            except textrules.RuleError as e:
                raise LibraryError(f"{f['field']}: {e}") from e
        sample = self.lib.add_label_photo(code, kind, photo, text)
        out = self.lib.sample(code)
        if picked and self.composition is not None:
            product = self.lib.product(normalise(sample["gtin14"]))
            out["composition"] = self.composition.attest_fields(
                out,
                product,
                photo,
                res["image_size"],
                kind,
                picked,
                signer,
                res.get("ocr_engine", ""),
            )
        return out

    def _apply_ndc(
        self, code: str, photo: bytes, res: dict[str, Any], label: dict[str, Any]
    ) -> dict[str, Any]:
        """The operator picked the printed NDC on the carton: resolve it to exactly one SPL,
        record the attested link, and append it to the crosswalk."""
        from .drugid import DrugResolver

        if self.lib.lookup is None:
            raise LibraryError("online lookup is off: the NDC cannot be resolved")
        cands = res.get("ndc_candidates") or []
        att = label.get("attest") or {}
        i = int(att.get("index", -1))
        if not 0 <= i < len(cands):
            raise LibraryError("pick the NDC printed on the carton")
        signer = " ".join(str(att.get("signer") or "").split())
        if not signer:
            raise LibraryError("type your name to attest the NDC")
        cand = cands[i]
        resolver = DrugResolver(self.lib.lookup)
        spl = resolver.resolve_printed(cand["ndc"])
        if spl is None:
            raise LibraryError(
                f"NDC {cand['ndc']} is not listed in exactly one current DailyMed label; "
                "use Find online and confirm the label by name instead"
            )
        sample = self.lib.add_label_photo(code, "ndc", photo, cand["text"])
        product = self.lib.product(normalise(sample["gtin14"]))
        row: dict[str, Any]
        if self.composition is not None:
            xml = self.lib.lookup.get_bytes(
                f"{self.lib.lookup.s.dailymed_url}/spls/{spl['setid']}.xml"
            )
            row = self.composition.link_ndc(
                sample, product, photo, res["image_size"], cand, signer, spl, xml
            )
        else:
            import datetime as _dt
            import hashlib

            now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
            row = {
                "gtin": sample["gtin14"],
                "ndc": cand["ndc"],
                "ndc11": cand["ndc11"],
                "setid": spl["setid"],
                "spl_version": spl["version"],
                "method": "printed_ndc",
                "evidence": {
                    "photo_sha256": hashlib.sha256(photo).hexdigest(),
                    "bbox": cand["box"],
                    "ndc_text": cand["text"],
                    "sample_code": code,
                },
                "attestation": {"operator": signer, "signature": "", "timestamp": now},
            }
        resolver.add_link(row)
        self.lib.product(
            normalise(sample["gtin14"]), refresh=True
        )  # re-resolve through the crosswalk
        out = self.lib.sample(code)
        out["ndc_link"] = {"ndc": cand["ndc"], "setid": spl["setid"], "spl_version": spl["version"]}
        return out

    def _attested_list(self, res: dict[str, Any], label: dict[str, Any]) -> tuple[str, str]:
        """An ingredient list the operator confirmed word for word (checked before saving)."""
        if self.composition is None or res.get("ingredient_box") is None:
            raise LibraryError("this photo's ingredient list cannot be attested (no list found)")
        signer = " ".join(str((label.get("attest") or {}).get("signer") or "").split())
        text = " ".join(str(label.get("ingredients_text") or "").split())
        if not signer:
            raise LibraryError("type your name to attest the ingredient list")
        if not text:
            raise LibraryError("the ingredient list is empty")
        from lio_verify import textrules

        try:
            textrules.split_list(text)
        except textrules.RuleError as e:
            raise LibraryError(str(e)) from e
        return signer, text

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
                brand = [
                    w for w in re.findall(r"[a-z0-9]+", (p["brand"] or "").lower()) if len(w) > 2
                ]
                for page in out["web"].get("pages") or []:
                    dom = str(page.get("domain") or "").replace("-", "")
                    page["manufacturer"] = bool(brand) and any(w in dom for w in brand)

        def smartlabel() -> None:
            lk = lib.lookup
            assert lk is not None
            sl: dict[str, Any] = {
                "configured": bool(lk.s.smartlabel_key),
                "result": None,
                "link": "https://www.smartlabel.org/",
                "gs1_links": [],
            }
            try:
                info, _ = lk.smartlabel(g)
                if info is not None:
                    sl["result"] = {"ingredients_text": info["ingredients_text"],
                                    "name": info["name"], "brand": info["brand"]}  # fmt: skip
                sl["gs1_links"] = lk.gs1_resolver(g)
            except (OSError, ValueError) as e:
                out["errors"].append(f"SmartLabel: {e}")
            out["smartlabel"] = sl

        threads = [threading.Thread(target=f) for f in (structured, web, smartlabel)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        out["retailers"] = retailer_links(g.code, q)
        return out

    def preview_record(self, source: str, ident: str, query: str = "") -> dict[str, Any]:
        """A record picked by name, fetched in full and laid out as ingredient tables
        (one per product variant). Nothing is saved."""
        lk = self.lib.lookup
        if lk is None:
            raise LibraryError("online lookup is off (foods.online_lookup)")
        try:
            info, raw = lk.fetch(source, ident)
        except (OSError, ValueError) as e:
            raise LibraryError(f"could not fetch the record: {e}") from e
        xml = None
        setid = str(info.get("openfda_set_id") or "")
        if source == "openfda" and re.fullmatch(r"[0-9a-f-]{36}", setid):
            try:  # the coded product data of the same label (DailyMed)
                xml = lk.get_bytes(f"{lk.s.dailymed_url}/spls/{setid}.xml")
            except (OSError, ValueError):
                xml = None
        out = structure.structure_record(source, info, raw, query, spl_xml=xml)
        out["ingredients_text"] = str(info.get("ingredients_text") or "")
        return out

    def fuse_sources(
        self, records: Any, sections: Any, query: str = "", *, all_variants: bool = False
    ) -> dict[str, Any]:
        """Several picked sources (database records and web-page sections) combined.

        The readings are first grouped by product (an Orange powder, a Sugar Free powder
        and a caplet are three products), and each group is combined into one table.
        The options are the combined tables, then each source's own table; the default
        is the group that best matches ``query``. With ``all_variants`` every product
        variant of every record takes part ("combine all"). Nothing is saved."""
        recs = [r for r in records if isinstance(r, dict)][:10] if isinstance(records, list) else []
        secs = [x for x in sections if isinstance(x, dict)] if isinstance(sections, list) else []
        if not recs and not secs:
            raise LibraryError("pick the sources to combine")
        tables: list[dict[str, Any]] = []
        skipped: list[str] = []
        for r in recs:
            try:
                pv = self.preview_record(str(r.get("source") or ""), str(r.get("id") or ""), query)
            except LibraryError as e:  # one source down must not stop the others
                skipped.append(f"{r.get('name') or r.get('id')}: {e}")
                continue
            opts = pv["options"]
            pick = opts[pv["default"]]
            if all_variants:
                parts = [o for o in opts if o.get("method") != "combined"]
            else:
                parts = [opts[i] for i in pick.get("parts", [])] or [pick]
            rname = " ".join(str(r.get("name") or "").split())[:40]
            for t in parts:
                v = str(t.get("variant") or structure.NA)
                name = v.split(" · ")[0] if v != structure.NA else rname
                base = structure.METHODS.get(t.get("method", ""), "")
                kind = {"spl_coded": "FDA coded", "label_text": "FDA label text"}.get(
                    t.get("method", ""),
                    {"dsld": "DSLD", "usda": "USDA"}.get(t["source"], t["source"]),
                )
                t["label"] = kind or base
                t["_name"] = name
                tables.append(t)
        tables += structure.structure_pages(secs)
        if not tables:
            raise LibraryError("none of the sources could be read: " + "; ".join(skipped))
        count: dict[str, int] = {}
        for t in tables:
            count[t["label"]] = count.get(t["label"], 0) + 1
        seen: dict[str, int] = {}
        for t in tables:  # short labels for the Sources column; the name only if needed
            name = t.pop("_name", "")
            if count[t["label"]] > 1:
                n = seen[t["label"]] = seen.get(t["label"], 0) + 1
                t["label"] = f"{t['label']}: {name}" if name else f"{t['label']} ({n})"
        groups = structure.group_tables(tables)
        words = _search_words(query)
        fused_all = []
        for g in groups:
            f = structure.fuse(g)
            f["method_label"] = structure.METHODS["combined"]
            desc = next(
                (
                    str(t["variant"]).split(" · ")[0]
                    for t in g
                    if t.get("variant") not in (None, "", structure.NA)
                ),
                str(g[0].get("product") or "product"),
            )
            f["variant"] = f"{desc} ({len(g)} source{'s' if len(g) > 1 else ''})"
            # match the search against the group's product (its most trusted reading's name)
            f["_score"] = (len(words & _search_words(desc)), len(g))
            fused_all.append(f)
        best = max(range(len(fused_all)), key=lambda i: fused_all[i]["_score"])
        for f in fused_all:
            f.pop("_score")
        for t in tables:
            t["method_label"] = t["label"]
            t.setdefault("method", "record")
            t.pop("parts", None)
        return {
            "options": [*fused_all, *tables],
            "default": best,
            "groups": len(groups),
            "skipped": skipped,
        }

    @staticmethod
    def structure_sections(sections: Any) -> dict[str, Any]:
        """Web-page sections the user ticked, laid out as one ingredient table."""
        if not isinstance(sections, list):
            raise LibraryError("sections must be a list")
        return structure.structure_sections([x for x in sections if isinstance(x, dict)])

    def confirm_ingredients(self, gtin14: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Save an ingredient list the user confirmed, with the links it came from,
        and the reviewed ingredient table when there is one."""
        table = None
        if fields.get("ingredients_structured"):
            try:
                table = structure.clean(fields["ingredients_structured"])
            except ValueError as e:
                raise LibraryError(str(e)) from e
        text = str(fields.get("ingredients_text") or "").strip()
        if not text and table is not None:
            text = structure.to_text(table)
        if not text:
            raise LibraryError("the ingredient list is empty")
        refs = fields.get("refs") if isinstance(fields.get("refs"), list) else []
        src = "web" if refs else "manual"
        data: dict[str, Any] = {"ingredients_text": text, "ingredients_refs": refs}
        if table is not None:
            data["ingredients_structured"] = table
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
