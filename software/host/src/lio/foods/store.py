"""The food library: a SQLite database plus a folder of photos.

Three tables:

- ``products``: one row per GTIN (the barcode), with the manufacturer
  information from :mod:`lio.foods.lookup`, normalised and raw;
- ``samples``: one row per physical item brought to the instrument. Each has
  its own sample code (``LIO-F-00001``, written on the item) and UUID, the
  barcode photo, an optional product photo, and notes. Two packs of the same
  product are two samples of one product;
- ``scans``: LIO spectral scans of a sample: every sweep's raw readings and a
  per-hole summary (mean net signal per detector).

Photos live under ``<root>/files``; the database stores paths relative to it.
"""

from __future__ import annotations

import contextlib
import csv
import datetime as dt
import io
import json
import logging
import sqlite3
import threading
import urllib.request
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar

from .barcode import Gtin, normalise
from .lookup import NUTRIENTS, Lookup, derived, empty_info, merge
from .websearch import WebSearch

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
CODE_PREFIX = "LIO-F-"
PHOTO_KINDS = ("barcode", "product")
LABEL_KINDS = ("ingredients", "nutrition")
# Fields set by hand, from a label photo or from a picked record survive "look up again".
META_KEYS = (
    "locked",
    "ingredients_source",
    "nutrition_source",
    "matched",
    "edited_fields",
    "ingredients_refs",
    "ingredients_confirmed_at",
)
MAX_PHOTO_BYTES = 15 * 1024 * 1024

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS products (
  gtin14        TEXT PRIMARY KEY,
  code          TEXT NOT NULL,
  kind          TEXT NOT NULL,
  name          TEXT NOT NULL DEFAULT '',
  brand         TEXT NOT NULL DEFAULT '',
  quantity      TEXT NOT NULL DEFAULT '',
  found         INTEGER NOT NULL DEFAULT 0,
  sources       TEXT NOT NULL DEFAULT '',
  info_json     TEXT NOT NULL DEFAULT '{}',
  raw_json      TEXT NOT NULL DEFAULT '{}',
  errors_json   TEXT NOT NULL DEFAULT '{}',
  image_file    TEXT NOT NULL DEFAULT '',
  looked_up_at  TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS samples (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  sample_code    TEXT NOT NULL UNIQUE,
  uuid           TEXT NOT NULL UNIQUE,
  gtin14         TEXT NOT NULL REFERENCES products(gtin14),
  scanned_text   TEXT NOT NULL DEFAULT '',
  barcode_format TEXT NOT NULL DEFAULT '',
  barcode_photo  TEXT NOT NULL DEFAULT '',
  product_photo  TEXT NOT NULL DEFAULT '',
  lot            TEXT NOT NULL DEFAULT '',
  best_before    TEXT NOT NULL DEFAULT '',
  notes          TEXT NOT NULL DEFAULT '',
  entered_by     TEXT NOT NULL DEFAULT '',
  source         TEXT NOT NULL DEFAULT '',
  archived       INTEGER NOT NULL DEFAULT 0,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS samples_gtin ON samples(gtin14);
CREATE TABLE IF NOT EXISTS scans (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  uuid           TEXT NOT NULL UNIQUE,
  sample_id      INTEGER NOT NULL REFERENCES samples(id),
  created_at     TEXT NOT NULL,
  target         TEXT NOT NULL,
  kind           TEXT NOT NULL,
  firmware       TEXT NOT NULL DEFAULT '',
  config_sha256  TEXT NOT NULL DEFAULT '',
  settle_ms      INTEGER NOT NULL,
  n              INTEGER NOT NULL,
  repeats        INTEGER NOT NULL,
  lsb_mv         REAL NOT NULL,
  duration_s     REAL NOT NULL DEFAULT 0,
  notes          TEXT NOT NULL DEFAULT '',
  spectrum_json  TEXT NOT NULL,
  raw_json       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS scans_sample ON scans(sample_id);
CREATE TABLE IF NOT EXISTS label_photos (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  sample_id   INTEGER NOT NULL REFERENCES samples(id),
  kind        TEXT NOT NULL,
  file        TEXT NOT NULL,
  text        TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS label_photos_sample ON label_photos(sample_id);
"""


class LibraryError(ValueError):
    """A request the library refuses (shown to the user)."""


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def image_bytes(data: bytes, max_px: int) -> tuple[bytes, str]:
    """Normalise a photo to an upright JPEG no larger than ``max_px`` (needs Pillow).

    Without Pillow, JPEG and PNG are stored as they are.
    """
    if len(data) > MAX_PHOTO_BYTES:
        raise LibraryError("photo too large (15 MB max)")
    try:
        from PIL import Image, ImageOps
    except ImportError:
        if data[:3] == b"\xff\xd8\xff":
            return data, ".jpg"
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return data, ".png"
        raise LibraryError("only JPEG or PNG photos can be stored without Pillow") from None
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    except Exception as e:
        raise LibraryError(f"cannot read the photo: {e}") from e
    img = img.convert("RGB")
    img.thumbnail((max_px, max_px))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    return out.getvalue(), ".jpg"


class FoodLibrary:
    def __init__(self, root: Path, lookup: Lookup | None = None, photo_max_px: int = 2000) -> None:
        self.root = root
        self.files = root / "files"
        self.files.mkdir(parents=True, exist_ok=True)
        self.lookup = lookup
        self.web: WebSearch | None = None  # last-resort ingredient search (set by open_library)
        self.photo_max_px = photo_max_px
        self.db_path = root / "lio_foods.sqlite"
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA journal_mode = WAL")
        self._db.executescript(SCHEMA)
        self._db.execute(
            "INSERT OR IGNORE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
        )
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    @contextlib.contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._db
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise

    # ------------------------------------------------------------ files

    def file_path(self, rel: str) -> Path | None:
        """The file for a stored relative path, or None if it escapes the folder."""
        root = self.files.resolve()
        p = (root / rel).resolve()
        return p if root in p.parents and p.is_file() else None

    def _save_file(self, folder: str, stem: str, data: bytes) -> str:
        blob, ext = image_bytes(data, self.photo_max_px)
        d = self.files / folder
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{stem}{ext}"
        n = 1
        while path.exists():  # never overwrite: keep every photo
            n += 1
            path = d / f"{stem}-{n}{ext}"
        path.write_bytes(blob)
        return str(path.relative_to(self.files))

    def _download_image(self, gtin14: str, url: str) -> str:
        if not url.startswith("https://"):
            return ""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LIO-V3-food-library/0.1"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read(MAX_PHOTO_BYTES + 1)
            return self._save_file("products", gtin14, data)
        except Exception as e:  # the picture is a nicety; the record stands without it
            log.warning("product image %s: %s", url, e)
            return ""

    # --------------------------------------------------------- products

    def product(self, gtin: Gtin, *, refresh: bool = False) -> dict[str, Any]:
        """The product record, looked up online the first time (or on ``refresh``)."""
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM products WHERE gtin14 = ?", (gtin.gtin14,)
            ).fetchone()
        if row is not None and not refresh:
            return self._product_dict(row)
        info, raw, errors, sources, found = empty_info(), {}, {}, [], False
        if self.lookup is not None:
            res = self.lookup.lookup(gtin)
            info, raw, errors, sources, found = (
                res.info,
                res.raw,
                res.errors,
                res.sources,
                res.found,
            )
        else:
            errors = {"lookup": "online lookup is off"}
        if row is not None:
            old = json.loads(row["info_json"])
            for k in old.get("locked", []):
                if k in old:
                    info[k] = old[k]
            for k in META_KEYS:
                if k in old:
                    info[k] = old[k]
            if old.get("locked"):
                info["derived_per_100g"] = derived(info.get("nutrition_per_100g") or {})
        image = row["image_file"] if row is not None else ""
        if found and info.get("image_url") and (refresh or not image):
            image = self._download_image(gtin.gtin14, str(info["image_url"])) or image
        if row is not None and not found and json.loads(row["info_json"]).get("name"):
            # A failed refresh (offline, rate limit) keeps what we had.
            with self._tx() as db:
                db.execute(
                    "UPDATE products SET errors_json = ? WHERE gtin14 = ?",
                    (json.dumps(errors), gtin.gtin14),
                )
            return self.product(gtin)
        with self._tx() as db:
            db.execute(
                """INSERT INTO products (gtin14, code, kind, name, brand, quantity, found,
                       sources, info_json, raw_json, errors_json, image_file, looked_up_at,
                       created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(gtin14) DO UPDATE SET name=excluded.name, brand=excluded.brand,
                       quantity=excluded.quantity, found=excluded.found,
                       sources=excluded.sources, info_json=excluded.info_json,
                       raw_json=excluded.raw_json, errors_json=excluded.errors_json,
                       image_file=excluded.image_file, looked_up_at=excluded.looked_up_at""",
                (
                    gtin.gtin14,
                    gtin.code,
                    gtin.kind,
                    str(info.get("name") or ""),
                    str(info.get("brand") or ""),
                    str(info.get("quantity") or ""),
                    int(found),
                    ",".join(sources),
                    json.dumps(info),
                    json.dumps(raw),
                    json.dumps(errors),
                    image,
                    str(info.get("looked_up_at") or now_iso()),
                    now_iso(),
                ),
            )
        return self.product(gtin)

    def _product_row(self, gtin14: str) -> sqlite3.Row:
        with self._lock:
            row: sqlite3.Row | None = self._db.execute(
                "SELECT * FROM products WHERE gtin14 = ?", (gtin14,)
            ).fetchone()
        if row is None:
            raise LibraryError(f"no product {gtin14}")
        return row

    def _save_info(
        self, gtin14: str, info: dict[str, Any], source: str, raw: tuple[str, Any] | None = None
    ) -> dict[str, Any]:
        row = self._product_row(gtin14)
        sources = [x for x in row["sources"].split(",") if x]
        if source not in sources:
            sources.append(source)
        raws = json.loads(row["raw_json"])
        if raw is not None:
            raws[raw[0]] = raw[1]
        found = bool(row["found"]) or bool(info.get("ingredients_text") or info.get("name"))
        with self._tx() as db:
            db.execute(
                """UPDATE products SET name=?, brand=?, quantity=?, info_json=?, sources=?,
                   raw_json=?, found=? WHERE gtin14=?""",
                (
                    str(info.get("name") or ""),
                    str(info.get("brand") or ""),
                    str(info.get("quantity") or ""),
                    json.dumps(info),
                    ",".join(sources),
                    json.dumps(raws),
                    int(found),
                    gtin14,
                ),
            )
        return self.product(normalise(gtin14))

    def set_product_info(
        self, gtin14: str, fields: dict[str, Any], *, source: str = "manual"
    ) -> dict[str, Any]:
        """Corrections (name, brand, quantity, serving, ingredients, nutrition per 100 g).

        ``source`` says where they came from: "manual" (typed in) or "label photo".
        The fields are locked: looking the product up again keeps them.
        """
        info = json.loads(self._product_row(gtin14)["info_json"])
        locked = set(info.get("locked", []))
        for k in ("name", "brand", "quantity", "serving_size", "ingredients_text", "contains"):
            if k in fields:
                info[k] = str(fields[k]).strip()
                locked.add(k)
        if "ingredients_text" in fields:
            info["ingredients_source"] = source
            # Where a confirmed list was found (web pages, label records): [{url, title}]
            refs = fields.get("ingredients_refs")
            info["ingredients_refs"] = [
                {"url": str(r.get("url") or ""), "title": str(r.get("title") or "")}
                for r in (refs if isinstance(refs, list) else [])
                if isinstance(r, dict)
                and str(r.get("url") or "").startswith(("http://", "https://"))
            ]
            info["ingredients_confirmed_at"] = now_iso()
        if isinstance(fields.get("nutrition_per_100g"), dict):
            per = dict(info.get("nutrition_per_100g") or {})
            for k, v in fields["nutrition_per_100g"].items():
                if k not in NUTRIENTS:
                    raise LibraryError(f"unknown nutrient {k!r}")
                if v in (None, ""):
                    per.pop(k, None)
                else:
                    per[k] = float(v)
            info["nutrition_per_100g"] = per
            info["derived_per_100g"] = derived(per)
            info["nutrition_source"] = source
            locked.add("nutrition_per_100g")
        info["locked"] = sorted(locked)
        info["edited_fields"] = sorted(set(info.get("edited_fields", [])) | set(fields))
        return self._save_info(gtin14, info, source)

    def adopt(
        self, gtin14: str, picked: dict[str, Any], raw: Any, *, source: str, query: str
    ) -> dict[str, Any]:
        """Use a record the user picked by name (e.g. a DSLD label) for this product.

        The picked record wins over looked-up data; fields set by hand or read
        from a label photo are kept.
        """
        old = json.loads(self._product_row(gtin14)["info_json"])
        info = merge(picked, old)
        for k in old.get("locked", []):
            if k in old:
                info[k] = old[k]
        tag = f"{source} (picked)"
        if picked.get("ingredients_text") and "ingredients_text" not in old.get("locked", []):
            info["ingredients_source"] = tag
            info["ingredients_refs"] = [
                {"url": u, "title": k} for k, u in (picked.get("links") or {}).items()
            ]
            info["ingredients_confirmed_at"] = now_iso()
        if picked.get("nutrition_per_100g") and "nutrition_per_100g" not in old.get("locked", []):
            info["nutrition_source"] = tag
        info["derived_per_100g"] = derived(info.get("nutrition_per_100g") or {})
        rid = picked.get("dsld_id") or picked.get("usda_fdc_id")
        info["matched"] = {"source": source, "id": rid, "query": query, "at": now_iso()}
        info["locked"] = sorted(set(old.get("locked", [])))
        for k in META_KEYS:
            if k in old and k not in info:
                info[k] = old[k]
        return self._save_info(gtin14, info, tag, (f"{source}_picked", raw))

    def _product_dict(self, row: sqlite3.Row, *, raw: bool = False) -> dict[str, Any]:
        out = {
            "gtin14": row["gtin14"],
            "code": row["code"],
            "kind": row["kind"],
            "name": row["name"],
            "brand": row["brand"],
            "quantity": row["quantity"],
            "found": bool(row["found"]),
            "sources": [s for s in row["sources"].split(",") if s],
            "info": json.loads(row["info_json"]),
            "errors": json.loads(row["errors_json"]),
            "image_file": row["image_file"],
            "looked_up_at": row["looked_up_at"],
        }
        if raw:
            out["raw"] = json.loads(row["raw_json"])
        return out

    # ---------------------------------------------------------- samples

    def create_sample(
        self,
        gtin: Gtin,
        *,
        scanned_text: str = "",
        barcode_format: str = "",
        barcode_photo: bytes | None = None,
        product_photo: bytes | None = None,
        lot: str = "",
        best_before: str = "",
        notes: str = "",
        entered_by: str = "",
        source: str = "dashboard",
    ) -> dict[str, Any]:
        self.product(gtin)  # make sure the product row exists (looked up if new)
        uid = str(uuid.uuid4())
        bphoto = self._save_file(uid, "barcode", barcode_photo) if barcode_photo else ""
        pphoto = self._save_file(uid, "product", product_photo) if product_photo else ""
        t = now_iso()
        with self._tx() as db:
            cur = db.execute(
                """INSERT INTO samples (sample_code, uuid, gtin14, scanned_text, barcode_format,
                       barcode_photo, product_photo, lot, best_before, notes, entered_by,
                       source, created_at, updated_at)
                   VALUES ('pending',?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    uid,
                    gtin.gtin14,
                    scanned_text or gtin.code,
                    barcode_format,
                    bphoto,
                    pphoto,
                    lot.strip(),
                    best_before.strip(),
                    notes.strip(),
                    entered_by.strip(),
                    source,
                    t,
                    t,
                ),
            )
            code = f"{CODE_PREFIX}{cur.lastrowid:05d}"
            db.execute("UPDATE samples SET sample_code = ? WHERE id = ?", (code, cur.lastrowid))
        return self.sample(code)

    def _sample_row(self, code: str) -> sqlite3.Row:
        with self._lock:
            row: sqlite3.Row | None = self._db.execute(
                "SELECT * FROM samples WHERE sample_code = ? OR uuid = ?", (code, code)
            ).fetchone()
        if row is None:
            raise LibraryError(f"no sample {code!r}")
        return row

    def _sample_summary(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "sample_code": row["sample_code"],
            "uuid": row["uuid"],
            "gtin14": row["gtin14"],
            "scanned_text": row["scanned_text"],
            "barcode_format": row["barcode_format"],
            "barcode_photo": row["barcode_photo"],
            "product_photo": row["product_photo"],
            "lot": row["lot"],
            "best_before": row["best_before"],
            "notes": row["notes"],
            "entered_by": row["entered_by"],
            "source": row["source"],
            "archived": bool(row["archived"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def sample(self, code: str, *, raw: bool = False) -> dict[str, Any]:
        """One sample with its product and the list of its scans (``raw``: API answers too)."""
        row = self._sample_row(code)
        with self._lock:
            prod = self._db.execute(
                "SELECT * FROM products WHERE gtin14 = ?", (row["gtin14"],)
            ).fetchone()
            scans = self._db.execute(
                "SELECT * FROM scans WHERE sample_id = ? ORDER BY id DESC", (row["id"],)
            ).fetchall()
        out = self._sample_summary(row)
        out["product"] = self._product_dict(prod, raw=raw) if prod is not None else None
        out["scans"] = [self._scan_summary(s, row["sample_code"]) for s in scans]
        with self._lock:
            labels = self._db.execute(
                "SELECT * FROM label_photos WHERE sample_id = ? ORDER BY id", (row["id"],)
            ).fetchall()
        out["label_photos"] = [
            {"kind": r["kind"], "file": r["file"], "text": r["text"], "created_at": r["created_at"]}
            for r in labels
        ]
        return out

    SORTS: ClassVar[dict[str, str]] = {
        "newest": "s.id DESC",
        "oldest": "s.id ASC",
        "name": "lower(p.name) ASC, s.id ASC",
        "scans": "n_scans DESC, s.id DESC",
        "last_scan": "last_scan IS NULL, last_scan DESC, s.id DESC",
    }

    def samples(
        self,
        query: str = "",
        *,
        archived: bool = False,
        scanned: str = "",
        found: str = "",
        ingredients: str = "",
        source: str = "",
        sort: str = "newest",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Search and filter. ``scanned``/``found``: "yes", "no" or "" (any);
        ``source``: "phone", "dashboard" or ""; ``sort``: a key of :attr:`SORTS`."""
        sql = """SELECT s.*, p.name AS p_name, p.brand AS p_brand, p.quantity AS p_quantity,
                        p.found AS p_found, p.image_file AS p_image,
                        COALESCE(json_extract(p.info_json, '$.ingredients_text'), '') != ''
                            AS p_has_ingr,
                        (SELECT COUNT(*) FROM scans c WHERE c.sample_id = s.id) AS n_scans,
                        (SELECT MAX(created_at) FROM scans c WHERE c.sample_id = s.id) AS last_scan
                 FROM samples s JOIN products p ON p.gtin14 = s.gtin14
                 WHERE s.archived = ?"""
        args: list[Any] = [int(archived)]
        q = query.strip()
        if q:
            sql += """ AND (s.sample_code LIKE ? OR s.gtin14 LIKE ? OR s.scanned_text LIKE ?
                       OR p.name LIKE ? OR p.brand LIKE ? OR s.notes LIKE ? OR s.lot LIKE ?)"""
            args += [f"%{q}%"] * 7
        if scanned in ("yes", "no"):
            has = "EXISTS (SELECT 1 FROM scans c WHERE c.sample_id = s.id)"
            sql += f" AND {has}" if scanned == "yes" else f" AND NOT {has}"
        if found in ("yes", "no"):
            sql += " AND p.found = ?"
            args.append(int(found == "yes"))
        if ingredients in ("yes", "no"):
            sql += " AND p_has_ingr = ?"
            args.append(int(ingredients == "yes"))
        if source:
            sql += " AND s.source = ?"
            args.append(source)
        sql += f" ORDER BY {self.SORTS.get(sort, self.SORTS['newest'])} LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
        out = []
        for r in rows:
            d = self._sample_summary(r)
            d.update(
                name=r["p_name"],
                brand=r["p_brand"],
                quantity=r["p_quantity"],
                found=bool(r["p_found"]),
                has_ingredients=bool(r["p_has_ingr"]),
                product_image=r["p_image"],
                n_scans=r["n_scans"],
                last_scan=r["last_scan"] or "",
            )
            out.append(d)
        return out

    def counts(self) -> dict[str, int]:
        with self._lock:
            one = self._db.execute(
                """SELECT (SELECT COUNT(*) FROM samples WHERE archived = 0),
                          (SELECT COUNT(*) FROM products),
                          (SELECT COUNT(*) FROM scans),
                          (SELECT COUNT(*) FROM samples WHERE archived = 1)"""
            ).fetchone()
        return {"samples": one[0], "products": one[1], "scans": one[2], "archived": one[3]}

    def update_sample(self, code: str, fields: dict[str, Any]) -> dict[str, Any]:
        row = self._sample_row(code)
        allowed = ("lot", "best_before", "notes", "entered_by")
        sets = {k: str(fields[k]).strip() for k in allowed if k in fields}
        if "archived" in fields:
            sets["archived"] = str(int(bool(fields["archived"])))
        if not sets:
            return self.sample(code)
        cols = ", ".join(f"{k} = ?" for k in sets)
        with self._tx() as db:
            db.execute(
                f"UPDATE samples SET {cols}, updated_at = ? WHERE id = ?",
                [*sets.values(), now_iso(), row["id"]],
            )
        return self.sample(code)

    def set_photo(self, code: str, kind: str, data: bytes) -> dict[str, Any]:
        if kind not in PHOTO_KINDS:
            raise LibraryError(f"photo kind must be one of {PHOTO_KINDS}")
        row = self._sample_row(code)
        rel = self._save_file(row["uuid"], kind, data)
        with self._tx() as db:
            db.execute(
                f"UPDATE samples SET {kind}_photo = ?, updated_at = ? WHERE id = ?",
                (rel, now_iso(), row["id"]),
            )
        return self.sample(code)

    def add_label_photo(self, code: str, kind: str, data: bytes, text: str = "") -> dict[str, Any]:
        """Keep a photo of the ingredient or nutrition panel, with the text read from it."""
        if kind not in LABEL_KINDS:
            raise LibraryError(f"label kind must be one of {LABEL_KINDS}")
        row = self._sample_row(code)
        rel = self._save_file(row["uuid"], f"label-{kind}", data)
        with self._tx() as db:
            db.execute(
                """INSERT INTO label_photos (sample_id, kind, file, text, created_at)
                   VALUES (?,?,?,?,?)""",
                (row["id"], kind, rel, text, now_iso()),
            )
            db.execute("UPDATE samples SET updated_at = ? WHERE id = ?", (now_iso(), row["id"]))
        return self.sample(code)

    # ------------------------------------------------------------ scans

    def add_scan(self, code: str, scan: dict[str, Any]) -> dict[str, Any]:
        """Store a scan built by :func:`lio.foods.scans.build_scan`."""
        row = self._sample_row(code)
        uid = str(uuid.uuid4())
        with self._tx() as db:
            db.execute(
                """INSERT INTO scans (uuid, sample_id, created_at, target, kind, firmware,
                       config_sha256, settle_ms, n, repeats, lsb_mv, duration_s, notes,
                       spectrum_json, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    uid,
                    row["id"],
                    now_iso(),
                    scan["target"],
                    scan["kind"],
                    scan.get("firmware", ""),
                    scan.get("config_sha256", ""),
                    int(scan["settle_ms"]),
                    int(scan["n"]),
                    int(scan["repeats"]),
                    float(scan["lsb_mv"]),
                    float(scan.get("duration_s", 0.0)),
                    str(scan.get("notes", "")),
                    json.dumps(scan["spectrum"]),
                    json.dumps(scan["sweeps"]),
                ),
            )
        return self.scan(uid)

    def _scan_summary(self, r: sqlite3.Row, sample_code: str) -> dict[str, Any]:
        return {
            "uuid": r["uuid"],
            "sample_code": sample_code,
            "created_at": r["created_at"],
            "target": r["target"],
            "kind": r["kind"],
            "firmware": r["firmware"],
            "config_sha256": r["config_sha256"],
            "settle_ms": r["settle_ms"],
            "n": r["n"],
            "repeats": r["repeats"],
            "lsb_mv": r["lsb_mv"],
            "duration_s": r["duration_s"],
            "notes": r["notes"],
        }

    def scan(self, uid: str) -> dict[str, Any]:
        with self._lock:
            r = self._db.execute(
                """SELECT c.*, s.sample_code FROM scans c JOIN samples s ON s.id = c.sample_id
                   WHERE c.uuid = ?""",
                (uid,),
            ).fetchone()
        if r is None:
            raise LibraryError(f"no scan {uid!r}")
        out = self._scan_summary(r, r["sample_code"])
        out["spectrum"] = json.loads(r["spectrum_json"])
        out["sweeps"] = json.loads(r["raw_json"])
        return out

    # ----------------------------------------------------------- export

    def scan_csv(self, uid: str) -> str:
        sc = self.scan(uid)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["# sample", sc["sample_code"], "scan", sc["uuid"], sc["created_at"]])
        w.writerow(["# target", sc["target"], "kind", sc["kind"], "firmware", sc["firmware"]])
        w.writerow(["# settle_ms", sc["settle_ms"], "n", sc["n"], "lsb_mv", sc["lsb_mv"]])
        w.writerow(
            ["repeat", "hole", "label", "wavelength_nm", "detector", "dark", "lit", "net",
             "t_on_ms"]
        )  # fmt: skip
        for i, sweep in enumerate(sc["sweeps"], 1):
            for m in sweep["records"]:
                for det in ("opt101", "ingaas"):
                    w.writerow(
                        [i, m["hole"], m["label"], m["nm"], det, m["dark"][det], m["lit"][det],
                         m["net"][det], m["t_on_ms"]]
                    )  # fmt: skip
        return buf.getvalue()

    def samples_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        nkeys = list(NUTRIENTS)
        w.writerow(
            ["sample_code", "uuid", "gtin14", "barcode", "name", "brand", "quantity",
             "lot", "best_before", "notes", "entered_by", "created_at", "n_scans",
             "product_sources", *[f"{k}_per_100g" for k in nkeys], "ingredients"]
        )  # fmt: skip
        for s in self.samples(limit=100000):
            prod = self.sample(s["sample_code"])["product"] or {}
            info = prod.get("info", {})
            per = info.get("nutrition_per_100g", {})
            w.writerow(
                [s["sample_code"], s["uuid"], s["gtin14"], s["scanned_text"], s["name"],
                 s["brand"], s["quantity"], s["lot"], s["best_before"], s["notes"],
                 s["entered_by"], s["created_at"], s["n_scans"], ",".join(prod.get("sources", [])),
                 *[per.get(k, "") for k in nkeys], info.get("ingredients_text", "")]
            )  # fmt: skip
        return buf.getvalue()

    def export(self) -> dict[str, Any]:
        """Everything (except photo bytes): samples with products and full scans."""
        out = []
        for s in self.samples(limit=100000) + self.samples(archived=True, limit=100000):
            d = self.sample(s["sample_code"])
            d["scans"] = [self.scan(c["uuid"]) for c in d["scans"]]
            out.append(d)
        return {"schema_version": SCHEMA_VERSION, "exported_at": now_iso(), "samples": out}
