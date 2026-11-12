"""Paired test corpus for the panel parsers (plan WP4): label images + structured truth.

    python tools/panel_corpus.py --out test_results/corpus --drug 100 --supplement 100 --nutrition 50

- **Drug Facts**: OTC labels sampled from openFDA (seeded random offsets); each
  label's DailyMed SPL package-label images, paired with the SPL's structured
  active strengths and its text sections (inactive list, "each ... contains").
- **Supplement Facts**: DSLD labels with a label PDF (seeded random ids), page 1
  rendered to an image, paired with the DSLD rows and other ingredients.
- **Nutrition Facts**: Open Food Facts nutrition photos of US products in FDC,
  paired with FDC labelNutrients. FDC values are partly computed (plan WP3), so this
  reference is approximate and reported as such.

OCR is Apple Vision, or Tesseract when Vision fails (recorded). Images are cached
under ``--out`` (not committed: OFF images are CC-BY-SA, recorded per item).
Writes ``corpus.json`` (items, hashes, per-field results) and ``summary.json``.
Metrics are field-level exact match after parsing, the share of proposed fields an
operator would have to correct, and how many images show a full panel. Reported,
not gating.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "software" / "host" / "src"))

from lio.foods import ocr, panels  # noqa: E402
from lio_verify import textrules  # noqa: E402

UA = "lio-panel-corpus/1 (+https://github.com/Brandonio-c/LIO)"
NS = {"v": "urn:hl7-org:v3"}


def get(url: str, *, binary: bool = False, pause: float = 0.3) -> Any:
    time.sleep(pause)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    return data if binary else json.loads(data)


class Ocr:
    def __init__(self) -> None:
        self.engine = "apple-vision"
        try:
            import io

            from PIL import Image

            im = Image.new("RGB", (400, 100), "white")
            buf = io.BytesIO()
            im.save(buf, "JPEG")
            ocr.recognise(buf.getvalue())
        except ocr.OcrError:
            self.engine = "tesseract"

    def lines(self, data: bytes) -> list[ocr.Line]:
        if self.engine == "apple-vision":
            return ocr.recognise(data)
        return ocr.recognise_tesseract(data)

    def best_rotation(self, data: bytes, score: Any) -> tuple[bytes, list[ocr.Line], int]:
        """Cartons often print the facts panel sideways: try 0, 270 and 90 degrees and keep
        the orientation the parser scores highest (Tesseract's own guess is unreliable)."""
        import io

        from PIL import Image

        best: tuple[bytes, list[ocr.Line], int] | None = None
        best_score = -1
        for rot in (0, 270, 90):
            if rot:
                im = Image.open(io.BytesIO(data)).convert("RGB").rotate(rot, expand=True)
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=95)
                d = buf.getvalue()
            else:
                d = data
            ls = self.lines(d)
            sc = score(ls, size_of(d))
            if sc > best_score:
                best, best_score = (d, ls, rot), sc
            if sc >= 5:
                break
        assert best is not None
        return best


def size_of(data: bytes) -> tuple[int, int]:
    return ocr.upright_size(data)


def norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9.%& ]", " ", s.lower()).split())


# ------------------------------------------------------------------- drug facts
def spl_truth(xml: bytes) -> dict[str, Any]:
    from lxml import etree

    root = etree.fromstring(xml)
    actives = sorted({f"{n.get('value')} {n.get('unit')}".lower()
                      for n in root.xpath("//v:ingredient[@classCode='ACTIB' or @classCode='ACTIM']/v:quantity/v:numerator", namespaces=NS)})  # fmt: skip
    texts = {}
    for sec in root.xpath("//v:section[v:title]", namespaces=NS):
        title = " ".join("".join(sec.find("v:title", NS).itertext()).split()).lower()
        body = sec.find("v:text", NS)
        if body is None:
            continue
        txt = " ".join("".join(body.itertext()).split())
        if title.startswith("inactive ingredient") and "inactive" not in texts:
            texts["inactive"] = txt
        if title.startswith("other information") and "other" not in texts:
            texts["other"] = txt
    contains: dict[str, str] = {}
    m = re.search(
        r"(?i)each\b[^.]*?contains\s*:[^.]*?(?=\s+(?:store|keep|read|do not|protect|see|tamper)|$)",
        texts.get("other", ""),
    )
    if m:
        try:
            contains = textrules._otc_items(m.group(0))
        except textrules.RuleError:
            contains = {}
    inactive = textrules.split_list2(texts["inactive"]) if texts.get("inactive") else []
    images = [
        str(x) for x in root.xpath("//v:observationMedia/v:value/v:reference/@value", namespaces=NS)
    ]
    return {"actives": actives, "contains": contains, "inactive": inactive, "images": images}


def score_drug(parsed: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    got_act = {a["value_raw"] for a in parsed["actives"]}
    for a in truth["actives"]:
        a2 = a.replace(" 1", "")
        fields.append(
            {"field": f"active {a}", "ok": a2 in got_act or a in got_act, "proposed": bool(got_act)}
        )
    got_c: dict[str, str] = {}
    for c in parsed["contains"]:
        got_c.update(c["items"])
    for el, amt in truth["contains"].items():
        fields.append(
            {"field": f"contains {el}", "ok": got_c.get(el) == amt, "proposed": el in got_c}
        )
    got_i = {norm(x) for x in (parsed["inactive"] or {}).get("items", [])}
    for item in truth["inactive"]:
        fields.append(
            {"field": f"inactive {item}", "ok": norm(item) in got_i, "proposed": bool(got_i)}
        )
    return {"fields": fields, "complete_panel": parsed["complete"], "sections": parsed["sections"]}


def drug_corpus(n: int, rng: random.Random, cache: Path, eng: Ocr) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    tries = 0
    while len(out) < n and tries < n * 3:
        tries += 1
        skip = rng.randrange(0, 25000)
        d = get(
            f'https://api.fda.gov/drug/label.json?search=openfda.product_type:"HUMAN+OTC+DRUG"&limit=1&skip={skip}'
        )
        if not d or not d.get("results"):
            continue
        setid = d["results"][0].get("set_id")
        xml = get(
            f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml", binary=True
        )
        if not xml:
            continue
        try:
            truth = spl_truth(xml)
        except Exception:
            continue
        if not truth["images"]:
            out.append({"kind": "drug_facts", "id": setid, "skip": "SPL has no label images"})
            continue
        best: dict[str, Any] | None = None
        for name in truth["images"][:3]:
            img = get(
                f"https://dailymed.nlm.nih.gov/dailymed/image.cfm?setid={setid}&name={urllib.parse.quote(name)}",
                binary=True,
            )
            if not img:
                continue
            (cache / f"drug_{setid}_{hashlib.sha256(img).hexdigest()[:12]}.jpg").write_bytes(img)
            try:
                d, ls, rot = eng.best_rotation(
                    img, lambda ls, sz: len(panels.drug_facts(ls, sz)["sections"])
                )
                parsed = panels.drug_facts(ls, size_of(d))
            except Exception as e:
                rot = 0
                parsed = {
                    "actives": [],
                    "contains": [],
                    "inactive": None,
                    "complete": False,
                    "sections": [],
                    "error": str(e),
                }
            res = {
                "image": name,
                "sha256": hashlib.sha256(img).hexdigest(),
                "rotation": rot,
                **score_drug(parsed, truth),
            }
            if best is None or len(res["sections"]) > len(best["sections"]):
                best = res
        if best is None:
            continue
        out.append(
            {"kind": "drug_facts", "id": setid, "license": "public domain (DailyMed/FDA)", **best}
        )
        print(f"drug {len(out)}/{n} {setid} sections={len(best['sections'])}", file=sys.stderr)
    return out


# ------------------------------------------------------------- supplement facts
DSLD_UNITS = {
    "mg": "mg",
    "mcg": "mcg",
    "gram(s)": "g",
    "g": "g",
    "milligram(s)": "mg",
    "microgram(s)": "mcg",
}


def dsld_truth(label: dict[str, Any]) -> dict[str, Any]:
    rows = []

    def walk(rs: list[dict[str, Any]]) -> None:
        for r in rs:
            q = (r.get("quantity") or [{}])[0]
            u = DSLD_UNITS.get(str(q.get("unit") or "").lower())
            if u and isinstance(q.get("quantity"), (int, float)) and q["quantity"] > 0:
                amt = q["quantity"]
                rows.append({"name": str(r.get("name") or ""), "value_raw": f"{amt:g} {u}"})
            walk(r.get("nestedRows") or [])

    walk(label.get("ingredientRows") or [])
    other = [
        str(i.get("name") or "")
        for i in (label.get("otheringredients") or {}).get("ingredients") or []
    ]
    return {"rows": rows, "other": other}


def score_supplement(parsed: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    prow = [
        (set(norm(r["name"]).split()), r["value_raw"].replace(".0 ", " ")) for r in parsed["rows"]
    ]
    for t in truth["rows"]:
        tw = set(norm(t["name"]).split())
        cand = [v for w, v in prow if tw and len(tw & w) / len(tw) >= 0.5]
        fields.append(
            {"field": f"row {t['name']}", "ok": t["value_raw"] in cand, "proposed": bool(cand)}
        )
    got_o = {norm(x) for x in (parsed["other_ingredients"] or {}).get("items", [])}
    for o in truth["other"]:
        fields.append(
            {
                "field": f"other {o}",
                "ok": any(norm(o) in g or g in norm(o) for g in got_o if g),
                "proposed": bool(got_o),
            }
        )
    return {
        "fields": fields,
        "complete_panel": bool(parsed["rows"]) and parsed["serving"] is not None,
    }


def pdf_page1(pdf: bytes) -> bytes | None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "l.pdf"
        p.write_bytes(pdf)
        r = subprocess.run(["/opt/homebrew/bin/pdftoppm", "-r", "200", "-f", "1", "-l", "1", "-jpeg", str(p), str(Path(tmp) / "pg")],
                           capture_output=True, timeout=120, check=False)  # fmt: skip
        if r.returncode != 0:
            return None
        pages = sorted(Path(tmp).glob("pg*.jpg"))
        return pages[0].read_bytes() if pages else None


def supplement_corpus(n: int, rng: random.Random, cache: Path, eng: Ocr) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    tries = 0
    while len(out) < n and tries < n * 6:  # DSLD: 1,000 requests per hour without a key
        tries += 1
        lid = rng.randrange(278000, 345000)
        label = get(f"https://api.ods.od.nih.gov/dsld/v9/label/{lid}", pause=1.0)
        if not isinstance(label, dict) or not label.get("pdf") or label.get("offMarket"):
            continue
        pdf = get(f"https://api.ods.od.nih.gov/dsld/s3/pdf/{lid}.pdf", binary=True, pause=1.0)
        img = pdf_page1(pdf) if pdf else None
        if not img:
            continue
        (cache / f"supp_{lid}.jpg").write_bytes(img)
        truth = dsld_truth(label)
        try:
            parsed = panels.supplement_facts(eng.lines(img), size_of(img))
        except Exception as e:
            parsed = {
                "rows": [],
                "serving": None,
                "other_ingredients": None,
                "blends": [],
                "error": str(e),
            }
        out.append({"kind": "supplement_facts", "id": lid, "license": "public domain (NIH DSLD)",
                    "sha256": hashlib.sha256(img).hexdigest(), **score_supplement(parsed, truth)})  # fmt: skip
        print(f"supplement {len(out)}/{n} {lid}", file=sys.stderr)
    return out


# -------------------------------------------------------------- nutrition facts
FDC_KEYS = {"calories": "calories", "fat": "total_fat", "saturatedFat": "saturated_fat", "transFat": "trans_fat",
            "cholesterol": "cholesterol", "sodium": "sodium", "carbohydrates": "total_carbohydrate",
            "fiber": "dietary_fiber", "sugars": "total_sugars", "protein": "protein"}  # fmt: skip
WORDS = ["cereal", "soup", "cookies", "crackers", "pasta", "yogurt", "chips", "bread", "sauce", "juice",
         "granola", "peanut", "cheese", "candy", "beans", "rice", "salsa", "dressing", "bar", "tea"]  # fmt: skip


def nutrition_corpus(
    n: int, rng: random.Random, cache: Path, eng: Ocr, key: str
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    tries = 0
    while len(out) < n and tries < n * 6:
        tries += 1
        q = urllib.parse.urlencode({"query": rng.choice(WORDS), "dataType": "Branded", "pageSize": 1,
                                    "pageNumber": rng.randrange(1, 50), "api_key": key})  # fmt: skip
        d = get(f"https://api.nal.usda.gov/fdc/v1/foods/search?{q}")
        foods = (d or {}).get("foods") or []
        if not foods or not foods[0].get("gtinUpc"):
            continue
        f = foods[0]
        code = re.sub(r"\D", "", f["gtinUpc"]).zfill(13)[-13:]
        p = get(
            f"https://world.openfoodfacts.org/api/v2/product/{code}.json?fields=selected_images",
            pause=1.2,
        )
        url = (
            (
                (((p or {}).get("product") or {}).get("selected_images") or {}).get("nutrition")
                or {}
            ).get("display")
            or {}
        ).get("en")
        if not url:
            continue
        img = get(url.replace(".400.jpg", ".full.jpg"), binary=True, pause=1.0)
        if not img:
            continue
        detail = get(f"https://api.nal.usda.gov/fdc/v1/food/{f['fdcId']}?api_key={key}")
        ln = (detail or {}).get("labelNutrients") or {}
        truth = {
            FDC_KEYS[k]: str(v.get("value"))
            for k, v in ln.items()
            if k in FDC_KEYS and isinstance(v, dict)
        }
        (cache / f"nut_{code}.jpg").write_bytes(img)
        try:
            rows = ocr.panel_rows(eng.lines(img), size_of(img))
        except Exception:
            rows = []
        got = {r["nutrient"]: r["value_raw"].split()[0].lstrip("<") for r in rows}
        fields = []
        for k, v in truth.items():
            try:
                same = k in got and textrules.parse_decimal(got[k]) == textrules.parse_decimal(
                    v.rstrip("0").rstrip(".") or "0"
                )
            except Exception:
                same = False
            fields.append({"field": k, "ok": same, "proposed": k in got})
        out.append({"kind": "nutrition_facts", "id": code, "fdc_id": f["fdcId"], "image_url": url,
                    "license": "CC-BY-SA 3.0, Open Food Facts contributors", "sha256": hashlib.sha256(img).hexdigest(),
                    "reference": "FDC labelNutrients (approximate: partly computed)", "fields": fields,
                    "complete_panel": len(rows) >= 6})  # fmt: skip
        print(f"nutrition {len(out)}/{n} {code}", file=sys.stderr)
    return out


# ------------------------------------------------------------------- summary
def summarise(items: list[dict[str, Any]]) -> dict[str, Any]:
    by: dict[str, Any] = {}
    for kind in ("drug_facts", "supplement_facts", "nutrition_facts"):
        its = [i for i in items if i["kind"] == kind and "fields" in i]
        fs = [f for i in its for f in i["fields"]]
        prop = [f for f in fs if f["proposed"]]
        by[kind] = {
            "items": len([i for i in items if i["kind"] == kind]),
            "scored": len(its),
            "full_panel": sum(1 for i in its if i.get("complete_panel")),
            "fields": len(fs),
            "exact_match": sum(1 for f in fs if f["ok"]),
            "proposed": len(prop),
            "needs_correction": sum(1 for f in prop if not f["ok"]),
        }
    return by


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--drug", type=int, default=100)
    ap.add_argument("--supplement", type=int, default=100)
    ap.add_argument("--nutrition", type=int, default=50)
    a = ap.parse_args(argv)
    cache = a.out / "images"
    cache.mkdir(parents=True, exist_ok=True)
    eng = Ocr()
    print(f"OCR engine: {eng.engine}", file=sys.stderr)
    key = (
        (REPO / "data" / "foods" / "usda_api_key.txt").read_text().strip()
        if (REPO / "data" / "foods" / "usda_api_key.txt").exists()
        else "DEMO_KEY"
    )
    items = (drug_corpus(a.drug, random.Random(a.seed), cache, eng)
             + supplement_corpus(a.supplement, random.Random(a.seed + 1), cache, eng)
             + nutrition_corpus(a.nutrition, random.Random(a.seed + 2), cache, eng, key))  # fmt: skip
    (a.out / "corpus.json").write_text(
        json.dumps({"seed": a.seed, "ocr_engine": eng.engine, "items": items}, indent=1)
    )
    summary = {"seed": a.seed, "ocr_engine": eng.engine, "by_kind": summarise(items)}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
