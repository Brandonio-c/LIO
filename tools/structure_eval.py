"""Accuracy of the structured ingredient tables (``lio.foods.structure``) on real records.

    python tools/structure_eval.py --out test_results/structure_eval --drug 100 --supplement 60 --food 80

Each record is laid out exactly as "Use this" does, then compared with an independent
structured reference:

- **OTC drugs** (openFDA labels, seeded random offsets): the DailyMed SPL XML of the same
  set ID. Active names and strengths come from the SPL's per-product ingredient elements
  (ACTIB/ACTIM numerator), and inactive names from IACT. The table is built from the label
  *text* (openFDA), so this checks the text extraction against the coded data.
- **Supplements** (DSLD labels, seeded random IDs): the DSLD record's own rows. This checks
  that every row, amount, %DV and blend member reaches the table unchanged.
- **Foods** (FDC branded foods, seeded random searches, matched to Open Food Facts by
  barcode): Open Food Facts' own parse of the same text (top-level ingredients and stated
  percentages). This is a second parser, not ground truth, so a disagreement is listed
  for review, not counted as an error by itself.

Every table is also checked for failure signs: empty or very long names, heading words
left in a name, amounts left inside a name, and duplicate rows.

Responses are cached under ``--out/cache`` (by URL hash), so a re-run is offline and
reproducible. Writes ``structure_results.json`` (per item; not ``results.json``, which the
dashboard reads as a test run) and ``summary.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "software" / "host" / "src"))

from lio.foods import structure as S  # noqa: E402
from lio.foods.lookup import parse_dsld, parse_openfda, parse_usda  # noqa: E402

UA = "lio-structure-eval/1 (+https://github.com/Brandonio-c/LIO)"
NS = {"v": "urn:hl7-org:v3"}
NA = S.NA
CACHE: Path = Path()
WORDS = ["bread", "cereal", "cookie", "soup", "sauce", "snack", "yogurt", "cracker", "candy",
         "pasta", "juice", "chips", "bar", "dressing", "frozen", "cheese", "chocolate", "drink"]  # fmt: skip


def get(url: str, *, binary: bool = False, pause: float = 0.3) -> Any:
    """GET with a disk cache (the API key, if any, is not part of the cache key)."""
    key = hashlib.sha256(re.sub(r"api_key=[^&]+", "", url).encode()).hexdigest()
    f = CACHE / key
    if f.exists():
        data = f.read_bytes()
    else:
        time.sleep(pause)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
        f.write_bytes(data)
    if binary:
        return data
    try:
        return json.loads(data)
    except ValueError:
        return None


# Label names and SPL coded (UNII preferred) names for the same substance. Only for
# scoring: a label calling it "BHT" is not an extraction error.
SYNONYMS = [
    (r"\bhc[li]\b", "hydrochloride"), (r"\bhbr\b", "hydrobromide"),
    (r"\bdisodium edta\b|\bedta disodium\b", "edetate disodium"),
    (r"\bbht\b", "butylated hydroxytoluene"), (r"\bbha\b", "butylated hydroxyanisole"),
    (r"\bcellulose gum\b|\bcmc\b", "carboxymethylcellulose"),
    (r"\bpvp\b", "povidone"), (r"\baloe barbadensis\b", "aloe vera"),
    (r"\btocopheryl acetate\b|\bvitamin e acetate\b", "alpha tocopherol acetate"),
    (r"\bsilica\b", "silicon dioxide"), (r"\bpeg\b", "polyethylene glycol"),
    (r"\bpurified water\b|\baqua\b", "water"), (r"\byellow (\d+)\b", r"yellow no \1"),
    (r"\bred (\d+)\b", r"red no \1"), (r"\bblue (\d+)\b", r"blue no \1"),
    (r"\b(unspecified|anhydrous|monohydrate|dihydrate|usp|nf)\b", ""),
]  # fmt: skip


def norm(s: str) -> str:
    s = s.lower().replace("&", " and ")
    s = re.sub(r"\b(no|number)\.?\s*(\d)", r"no \2", s)
    s = " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())
    for pat, rep in SYNONYMS:
        s = re.sub(pat, rep, s)
    return " ".join(s.split())


def same(a: str, b: str) -> bool:
    """Loose name match: equal, one inside the other, or most words shared."""
    x, y = norm(a), norm(b)
    if not x or not y:
        return False
    if x == y or f" {x} " in f" {y} " or f" {y} " in f" {x} ":
        return True
    wx, wy = set(x.split()), set(y.split())
    return len(wx & wy) / max(1, min(len(wx), len(wy))) >= 0.75


MASS = {"g": 1000.0, "mg": 1.0, "mcg": 0.001, "ml": 1000.0, "l": 1e6}


def _q(a: str) -> tuple[float, str] | None:
    m = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zµ%]+)\s*", a.lower())
    if not m:
        return None
    return float(m.group(1)), m.group(2).replace("µg", "mcg").replace("ug", "mcg")


def amount_ok(table: str, num: str, den: str) -> bool:
    """The table's strength equals the SPL's numerator, or, for 'x%', numerator ÷
    denominator * 100 (g per 100 g or mL)."""
    hp = re.fullmatch(r"\s*([0-9.]+)\s*\[(?:hp|kp)_([a-z]+)\]\s*", num, re.I)
    if hp:  # homeopathic potency, e.g. "12 [hp_X]" -> "12X" among the table's potencies
        pot = f"{float(hp.group(1)):g}{hp.group(2).upper()}"
        return pot in [x.strip().upper() for x in table.split(",")]
    un = re.fullmatch(r"\s*([0-9.]+)\s*\[(?:iu|usp'u)\]\s*", num, re.I)
    if un:  # International / USP units
        tu = re.fullmatch(r"\s*([0-9.]+)\s*(?:iu|units?|usp units?)\s*", table, re.I)
        return tu is not None and float(tu.group(1)) == float(un.group(1))
    t, n, d = _q(table), _q(num), _q(den)
    if t is None or n is None:
        return False
    if t[1] == "%":
        if d is None or n[1] not in MASS or d[1] not in MASS:
            return False
        return abs(t[0] - 100 * n[0] * MASS[n[1]] / (d[0] * MASS[d[1]])) < 1e-6
    if t[1] in MASS and n[1] in MASS:
        return abs(t[0] * MASS[t[1]] - n[0] * MASS[n[1]]) < 1e-9
    return t == n


HEAD_WORDS = re.compile(r"\b(inactive ingredients?|active ingredients?|other ingredients?|"
                        r"purpose|directions|warnings?|uses)\b", re.I)  # fmt: skip
AMOUNT_IN_NAME = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|%|iu)\b", re.I)


def failure_signs(st: dict[str, Any]) -> list[str]:
    out = []
    seen: set[tuple[str, str, str]] = set()
    for r in st["ingredients"]:
        n = r["name"]
        if not n or n == NA:
            out.append("empty name")
        if len(n) > 70:
            out.append(f"long name ({len(n)} chars): {n[:60]}…")
        if HEAD_WORDS.search(n):
            out.append(f"heading in name: {n[:60]}")
        if r["amount"] == NA and AMOUNT_IN_NAME.search(n) and r["role"] != "dietary":
            out.append(f"amount left in name: {n[:60]}")
        k = (norm(n), r["role"], r["variant"])
        if k in seen:
            out.append(f"duplicate: {n[:40]}")
        seen.add(k)
    return out


# ------------------------------------------------------------------------ drugs
def spl_products(xml: bytes) -> list[dict[str, Any]]:
    from lxml import etree

    root = etree.fromstring(xml)
    prods = []
    for mp in root.xpath("//v:manufacturedProduct/v:manufacturedProduct", namespaces=NS):
        name = " ".join("".join(mp.xpath("string(v:name)", namespaces=NS)).split())
        act, inact = [], []
        for ing in mp.xpath("v:ingredient", namespaces=NS):
            cls = ing.get("classCode")
            sub = " ".join(ing.xpath("string(v:ingredientSubstance/v:name)", namespaces=NS).split())
            if cls in ("ACTIB", "ACTIM", "ACTIR"):
                num = ing.find("v:quantity/v:numerator", NS)
                den = ing.find("v:quantity/v:denominator", NS)
                amt = f"{num.get('value')} {num.get('unit')}" if num is not None else ""
                per = f"{den.get('value')} {den.get('unit')}" if den is not None else ""
                act.append({"name": sub, "amount": amt, "per": per})
            elif cls == "IACT":
                inact.append(sub)
        if act or inact:
            prods.append({"name": name, "active": act, "inactive": inact})
    return prods


def score_drug(st: dict[str, Any], prods: list[dict[str, Any]]) -> dict[str, Any]:
    acts = [r for r in st["ingredients"] if r["role"] == "active"]
    inacts = [r["name"] for r in st["ingredients"] if r["role"] == "inactive"]

    def fit(p: dict[str, Any]) -> float:
        a = sum(any(same(r["name"], t["name"]) for t in p["active"]) for r in acts)
        i = sum(any(same(n, t) for t in p["inactive"]) for n in inacts)
        return a * 3 + i

    p = max(prods, key=fit)
    a_ok = []
    for t in p["active"]:
        hit = next((r for r in acts if same(r["name"], t["name"])), None)
        a_ok.append({
            "spl": t, "name_found": hit is not None,
            "amount_ok": hit is not None and amount_ok(hit["amount"], t["amount"], t["per"]),
            "table_amount": hit["amount"] if hit else None, "table_basis": hit["basis"] if hit else None,
        })  # fmt: skip
    extra_act = [
        r["name"] for r in acts if not any(same(r["name"], t["name"]) for t in p["active"])
    ]
    i_found = [t for t in p["inactive"] if any(same(n, t) for n in inacts)]
    i_missing = [t for t in p["inactive"] if t not in i_found]
    i_extra = [n for n in inacts if not any(same(n, t) for t in p["inactive"])]
    return {
        "spl_product": p["name"],
        "actives": a_ok,
        "active_extra": extra_act,
        "inactive_spl": len(p["inactive"]),
        "inactive_table": len(inacts),
        "inactive_found": len(i_found),
        "inactive_missing": i_missing,
        "inactive_extra": i_extra,
    }


def drugs(n: int, rng: random.Random) -> list[dict[str, Any]]:
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
        r = d["results"][0]
        setid = r.get("set_id")
        xml = get(
            f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml", binary=True
        )
        if not xml:
            continue
        try:
            prods = spl_products(xml)
        except Exception:
            continue
        if not prods:
            continue
        info = parse_openfda(r)
        both = S.structure_record("openfda", info, r, "", spl_xml=xml)
        coded = [o for o in both["options"] if o["method"] == "spl_coded"]
        cacts = [x for o in coded for x in o["ingredients"] if x["role"] == "active"]
        coded_info = {
            "tables": len(coded),
            "actives": len(cacts),
            "actives_with_amount": sum(1 for x in cacts if x["amount"] != NA),
            "with_purpose": sum(1 for x in cacts if "purpose:" in x["note"]),
            "text_disagrees": sum(1 for x in cacts if "label text says" in x["note"]),
            "not_in_text": sum(1 for x in cacts if "not named in the label text" in x["note"]),
            "default_is_coded": both["options"][both["default"]]["method"] == "spl_coded",
        }
        res = S.structure_record("openfda", info, r, "")
        sc = [score_drug(o, prods) for o in res["options"]]
        best = max(range(len(sc)), key=lambda i: (sum(a["name_found"] for a in sc[i]["actives"]) * 3
                                                    + sc[i]["inactive_found"]))  # fmt: skip
        st = res["options"][best]
        out.append({"kind": "drug", "id": setid, "name": info["name"], "options": len(res["options"]),
                    "has_text": bool(info["ingredients_text"]), "table": st, "score": sc[best],
                    "coded": coded_info,
                    "failures": failure_signs(st)})  # fmt: skip
        print(f"drug {len(out)}/{n} {setid}", flush=True)
    return out


# ------------------------------------------------------------------ supplements
def dsld_expect(label: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []

    def walk(rs: list[dict[str, Any]]) -> None:
        for r in rs:
            q = (r.get("quantity") or [{}])[0]
            amt = ""
            if (
                isinstance(q.get("quantity"), (int, float))
                and str(q.get("unit") or "").upper() != "NP"
            ):
                amt = f"{q['quantity']:g}"
            rows.append((str(r.get("name") or ""), amt))
            walk(r.get("nestedRows") or [])

    walk(label.get("ingredientRows") or [])
    return rows


def supplements(n: int, rng: random.Random) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    tries = 0
    while len(out) < n and tries < n * 6:  # DSLD: 1,000 requests per hour without a key
        tries += 1
        lid = rng.randrange(278000, 345000)
        label = get(f"https://api.ods.od.nih.gov/dsld/v9/label/{lid}", pause=1.0)
        if not isinstance(label, dict) or not label.get("ingredientRows"):
            continue
        (st,) = S.structure_record("dsld", parse_dsld(label), label)["options"]
        exp = dsld_expect(label)
        rows = [r for r in st["ingredients"] if r["role"] == "dietary"]
        found = amt_ok = 0
        missing = []
        for name, amt in exp:
            hit = next((r for r in rows if r["name"] == " ".join(name.split())), None)
            if hit is None:
                missing.append(name)
                continue
            found += 1
            num = re.search(r"[0-9]+(?:\.[0-9]+)?", hit["amount"]) if hit["amount"] != NA else None
            got = num.group(0) if num else ""
            amt_ok += (got == amt) if amt else (hit["amount"] == NA)
        other_exp = len((label.get("otheringredients") or {}).get("ingredients") or [])
        other_got = sum(1 for r in st["ingredients"] if r["role"] == "other")
        out.append({"kind": "supplement", "id": lid, "name": label.get("fullName"), "table": st,
                    "score": {"rows": len(exp), "found": found, "amount_ok": amt_ok,
                              "missing": missing, "other_expected_min": other_exp,
                              "other_table": other_got, "serving": st["serving"]},
                    "failures": failure_signs(st)})  # fmt: skip
        print(f"supplement {len(out)}/{n} {lid}", flush=True)
    return out


# ------------------------------------------------------------------------ foods
def foods(n: int, rng: random.Random, key: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    tries = 0
    while len(out) < n and tries < n * 6:
        tries += 1
        q = urllib.parse.urlencode({"query": rng.choice(WORDS), "dataType": "Branded", "pageSize": 1,
                                    "pageNumber": rng.randrange(1, 60), "api_key": key})  # fmt: skip
        d = get(f"https://api.nal.usda.gov/fdc/v1/foods/search?{q}")
        fl = (d or {}).get("foods") or []
        if not fl or not fl[0].get("ingredients") or not fl[0].get("gtinUpc"):
            continue
        f = fl[0]
        info = parse_usda(f)
        (st,) = S.structure_record("usda", info, f)["options"]
        item: dict[str, Any] = {"kind": "food", "id": f.get("fdcId"), "name": f.get("description"),
                                "table": st, "failures": failure_signs(st)}  # fmt: skip
        code = re.sub(r"\D", "", f["gtinUpc"]).zfill(13)[-13:]
        p = get(f"https://world.openfoodfacts.org/api/v2/product/{code}.json?fields=ingredients_text_en,ingredients_text,ingredients",
                pause=1.2)  # fmt: skip
        prod = (p or {}).get("product") or {}
        text = prod.get("ingredients_text_en") or prod.get("ingredients_text") or ""
        top = [i for i in prod.get("ingredients") or [] if i.get("text")]
        if text and top:
            (ost,) = S.structure_record("openfoodfacts", {"ingredients_text": text}, None)[
                "options"
            ]
            mine = [r for r in ost["ingredients"]]
            theirs = [str(i["text"]) for i in top]
            found = [t for t in theirs if any(same(r["name"], t) for r in mine)]
            pct_theirs = {
                str(i["text"]): i.get("percent") for i in top if i.get("percent") is not None
            }
            pct_ok = []
            for t, v in pct_theirs.items():
                hit = next((r for r in mine if same(r["name"], t)), None)
                got = (
                    hit["amount"].replace("%", "").strip()
                    if hit and hit["amount"].endswith("%")
                    else None
                )
                pct_ok.append({"name": t, "off": v, "table": got,
                               "ok": got is not None and re.fullmatch(r"[0-9.]+", got) is not None
                                     and abs(float(got) - float(v)) < 1e-9})  # fmt: skip
            item["off"] = {"text": text, "off_top": len(theirs), "table_rows": len(mine),
                           "found": len(found), "missing": [t for t in theirs if t not in found],
                           "extra": [r["name"] for r in mine if not any(same(r["name"], t) for t in theirs)],
                           "percents": pct_ok, "failures": failure_signs(ost)}  # fmt: skip
        out.append(item)
        print(f"food {len(out)}/{n} {item['id']}", flush=True)
    return out


def summarise(items: list[dict[str, Any]]) -> dict[str, Any]:
    d = [i for i in items if i["kind"] == "drug"]
    s = [i for i in items if i["kind"] == "supplement"]
    f = [i for i in items if i["kind"] == "food"]
    fo = [i["off"] for i in f if "off" in i]
    acts = [a for i in d for a in i["score"]["actives"]]
    return {
        "drug": {
            "labels": len(d),
            "with_variants": sum(1 for i in d if i["options"] > 1),
            "spl_actives": len(acts),
            "active_name_found": sum(a["name_found"] for a in acts),
            "active_amount_correct": sum(a["amount_ok"] for a in acts),
            "active_basis_stated": sum(1 for a in acts if a["table_basis"] not in (None, NA)),
            "active_extra_rows": sum(len(i["score"]["active_extra"]) for i in d),
            "spl_inactives": sum(i["score"]["inactive_spl"] for i in d),
            "table_inactives": sum(i["score"]["inactive_table"] for i in d),
            "inactive_found": sum(i["score"]["inactive_found"] for i in d),
            "per_dose_rows": sum(len(i["table"]["contains"]) for i in d),
            "labels_with_failure_signs": sum(1 for i in d if i["failures"]),
            "coded_tables_available": sum(1 for i in d if i["coded"]["tables"]),
            "coded_default": sum(1 for i in d if i["coded"]["default_is_coded"]),
            "coded_actives": sum(i["coded"]["actives"] for i in d),
            "coded_actives_with_amount": sum(i["coded"]["actives_with_amount"] for i in d),
            "coded_actives_with_purpose": sum(i["coded"]["with_purpose"] for i in d),
            "coded_actives_text_disagrees": sum(i["coded"]["text_disagrees"] for i in d),
            "coded_actives_not_in_text": sum(i["coded"]["not_in_text"] for i in d),
        },
        "supplement": {
            "labels": len(s),
            "rows": sum(i["score"]["rows"] for i in s),
            "rows_found": sum(i["score"]["found"] for i in s),
            "amount_correct": sum(i["score"]["amount_ok"] for i in s),
            "serving_stated": sum(1 for i in s if i["score"]["serving"] != NA),
            "labels_with_failure_signs": sum(1 for i in s if i["failures"]),
        },
        "food": {
            "lists": len(f),
            "lists_with_failure_signs": sum(1 for i in f if i["failures"]),
            "matched_in_off": len(fo),
            "off_top_level": sum(x["off_top"] for x in fo),
            "off_found": sum(x["found"] for x in fo),
            "table_rows": sum(x["table_rows"] for x in fo),
            "off_percents": sum(len(x["percents"]) for x in fo),
            "off_percents_matched": sum(p["ok"] for x in fo for p in x["percents"]),
        },
    }


def main(argv: list[str] | None = None) -> int:
    global CACHE
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("test_results/structure_eval"))
    ap.add_argument("--drug", type=int, default=100)
    ap.add_argument("--supplement", type=int, default=60)
    ap.add_argument("--food", type=int, default=80)
    ap.add_argument("--seed", type=int, default=20261113)
    ap.add_argument("--usda-key-file", type=Path, default=REPO / "data/foods/usda_api_key.txt")
    a = ap.parse_args(argv)
    CACHE = a.out / "cache"
    CACHE.mkdir(parents=True, exist_ok=True)
    key = a.usda_key_file.read_text().strip() if a.usda_key_file.exists() else "DEMO_KEY"
    items = drugs(a.drug, random.Random(a.seed))
    items += supplements(a.supplement, random.Random(a.seed + 1))
    items += foods(a.food, random.Random(a.seed + 2), key)
    (a.out / "structure_results.json").write_text(json.dumps(items, indent=1, ensure_ascii=False))
    summary = {"seed": a.seed, **summarise(items)}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
