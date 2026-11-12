# ruff: noqa: RUF059, RUF001  (a report tool: long report strings)
"""Ingredient-list coverage report for barcode lookups.

For every barcode in the panel (the food library's recent scans, plus a fixed
panel of real retail products), query each source *directly* with each barcode
form and record what came back, then run the food library's own lookup
pipeline on it. The direct queries do not use ``lio.foods.lookup``, so the
same report can be compared before and after changes to that code.

    python tools/ingredient_coverage.py --out test_results/coverage/before
    python tools/ingredient_coverage.py --out test_results/coverage/after --compare test_results/coverage/before

Writes ``report.json`` and ``report.md``. Needs network access; reads the USDA
key from ``$LIO_USDA_API_KEY`` or ``data/foods/usda_api_key.txt`` (never written
to the report).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "software" / "host" / "src"))

UA = "lio-coverage/1 (+https://github.com/Brandonio-c/LIO)"

# A fixed panel of real products, chosen from each source by fixed searches
# (2026-11-12). Each item says where its barcode came from: hit rates for that
# source are biased upwards for the items it supplied.
PANEL: list[tuple[str, str, str]] = [
    ("051500255162", "FDC (golden record)", "Jif Creamy Peanut Butter 16 oz"),
    ("702669934398", "DSLD (golden record)", "Nutricost Magnesium Oxide"),
    ("3017620422003", "OFF (golden record)", "Nutella 400 g (France)"),
    ("016000275287", "FDC search 'cheerios cereal'", "Cheerios"),
    ("051000273482", "FDC search 'campbell tomato soup'", "Campbell's Tomato Soup"),
    ("818290019790", "FDC search 'chobani greek yogurt'", "Chobani Honey Vanilla Greek"),
    ("021000037377", "FDC search 'kraft macaroni cheese'", "Kraft Macaroni & Cheese"),
    ("842379108549", "DSLD label 239571", "Solimo Melatonin 3 mg"),
    ("766298017891", "DSLD label 277770", "Pure Encapsulations Melatonin-SR"),
    ("5453003821090", "DSLD label 332395", "SuperSmart Melatonin 2 mg"),
    ("070038610953", "openFDA label (openfda.upc)", "Valu Pain Reliever Extra Strength"),
    ("341520314643", "openFDA label (openfda.upc)", "Care One Ibuprofen"),
    ("032251921049", "openFDA label (openfda.upc)", "Family Wellness Daytime Cold and Flu"),
    ("070038599760", "openFDA label (openfda.upc)", "Valu Allergy Relief"),
    ("5449000000996", "OFF", "Coca-Cola Original (EU)"),
    ("8000500310427", "OFF", "Nutella Biscuits"),
    ("3228857000166", "OFF", "Harrys 100% mie complet"),
    ("049000028911", "OFF", "Diet Coke (US)"),
    ("04963406", "OFF (UPC-E)", "Coca-Cola can, UPC-E"),
]


# ------------------------------------------------------------------- barcodes
def check_digit(body: str) -> int:
    s = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - s % 10) % 10


def expand_upce(code: str) -> str:
    ns, d, chk = code[0], code[1:7], code[7]
    last = d[5]
    if last in "012":
        body = d[0:2] + last + "0000" + d[2:5]
    elif last == "3":
        body = d[0:3] + "00000" + d[3:5]
    elif last == "4":
        body = d[0:4] + "00000" + d[4]
    else:
        body = d[0:5] + "0000" + last
    return ns + body + chk


def forms(code: str) -> dict[str, Any]:
    digits = re.sub(r"\D", "", code)
    out: dict[str, Any] = {"as_given": digits}
    if len(digits) == 8 and digits[0] in "01":
        up = expand_upce(digits)
        out["upce"] = digits
        if check_digit(up[:-1]) == int(up[-1]):
            digits = up
    out["check_digit_ok"] = check_digit(digits[:-1]) == int(digits[-1])
    g14 = digits.zfill(14)
    out["gtin14"] = g14
    out["ean13"] = g14[1:]
    if g14.startswith("00"):
        out["upca"] = g14[2:]
    return out


def ndc_candidates(upca: str) -> list[str]:
    """UPC-A 3 + 10-digit NDC + check -> NDC in the 4-4-2, 5-3-2 and 5-4-1 patterns."""
    if not upca.startswith("3") or len(upca) != 12:
        return []
    n = upca[1:11]
    return [f"{n[:4]}-{n[4:8]}-{n[8:]}", f"{n[:5]}-{n[5:8]}-{n[8:]}", f"{n[:5]}-{n[5:9]}-{n[9:]}"]


# ----------------------------------------------------------------------- http
def get(url: str) -> tuple[int, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, None
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            return e.code, None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if attempt < 2:
                time.sleep(2)
                continue
            return -1, str(e)
    return -1, None


def usda_key() -> str:
    k = os.environ.get("LIO_USDA_API_KEY", "")
    f = REPO / "data" / "foods" / "usda_api_key.txt"
    return k or (f.read_text().strip() if f.exists() else "DEMO_KEY")


# ------------------------------------------------------------- source probes
def probe_off(fm: dict[str, Any]) -> dict[str, Any]:
    tried, hit = [], None
    for name in ("as_given", "upca", "ean13", "gtin14", "upce"):
        code = fm.get(name)
        if not code or code in [t["code"] for t in tried]:
            continue
        time.sleep(1.5)  # OFF asks for at most ~1 product request per second
        st, d = get(f"https://world.openfoodfacts.org/api/v2/product/{code}.json")
        ok = isinstance(d, dict) and d.get("status") == 1
        tried.append({"form": name, "code": code, "hit": ok})
        if ok and hit is None:
            p = d["product"]
            langs = sorted(
                k[len("ingredients_text_") :]
                for k, v in p.items()
                if k.startswith("ingredients_text_") and isinstance(v, str) and v.strip()
                and re.fullmatch(r"ingredients_text_[a-z]{2}", k)
            )  # fmt: skip
            hit = {
                "form": name,
                "fields": {
                    "ingredients_text": bool((p.get("ingredients_text") or "").strip()),
                    "ingredients_text_languages": langs,
                    "ingredients_parsed": len(p.get("ingredients") or []),
                    "nutriments": bool(p.get("nutriments")),
                },
                "lang": p.get("lang"),
            }
    return {"tried": tried, "hit": hit}


def probe_fdc(fm: dict[str, Any], key: str) -> dict[str, Any]:
    tried, hit = [], None
    for name in ("gtin14", "ean13", "upca", "as_given"):
        code = fm.get(name)
        if not code or code in [t["code"] for t in tried]:
            continue
        q = urllib.parse.urlencode(
            {"query": code, "dataType": "Branded", "pageSize": 10, "api_key": key}
        )
        st, d = get(f"https://api.nal.usda.gov/fdc/v1/foods/search?{q}")
        foods = (d or {}).get("foods") or [] if isinstance(d, dict) else []
        match = [
            f
            for f in foods
            if re.sub(r"\D", "", str(f.get("gtinUpc") or "")).zfill(14) == fm["gtin14"]
        ]
        tried.append({"form": name, "code": code, "hit": bool(match), "results": len(foods)})
        if match and hit is None:
            f = match[0]
            ing = str(f.get("ingredients") or "")
            hit = {
                "form": name,
                "stored_gtinUpc": f.get("gtinUpc"),
                "fdc_id": f.get("fdcId"),
                "fields": {
                    "ingredients": bool(ing.strip()),
                    "ingredients_chars": len(ing),
                    "ingredients_ends_cleanly": bool(
                        re.search(r"[.)\]]\s*$", ing)
                        or re.search(r"contains:?\s+[\w ,&/-]+$", ing, re.I)  # allergen statement
                    ),
                    "servingSize": f.get("servingSize") is not None,
                },
            }
        time.sleep(0.3)
    return {"tried": tried, "hit": hit}


def _dsld_spaced(fm: dict[str, Any]) -> list[str]:
    out = []
    u = fm.get("upca")
    if u:
        out.append(f"{u[0]} {u[1:6]} {u[6:11]} {u[11]}")
    e = fm["ean13"]
    out.append(f"{e[0]} {e[1:7]} {e[7:13]}")
    return out


def probe_dsld(fm: dict[str, Any]) -> dict[str, Any]:
    tried, hit = [], None
    queries = [(f"spaced:{s}", f'"{s}"') for s in _dsld_spaced(fm)]
    queries += [("upca", fm.get("upca")), ("ean13", fm["ean13"])]
    for name, q in queries:
        if not q:
            continue
        st, d = get(
            f"https://api.ods.od.nih.gov/dsld/v9/search-filter?q={urllib.parse.quote(q)}&size=5"
        )
        hits = (d or {}).get("hits") or [] if isinstance(d, dict) else []
        found = None
        for h in hits[:3]:
            st2, lab = get(f"https://api.ods.od.nih.gov/dsld/v9/label/{h['_id']}")
            if (
                isinstance(lab, dict)
                and re.sub(r"\D", "", str(lab.get("upcSku") or "")).zfill(14) == fm["gtin14"]
            ):
                found = lab
                break
        tried.append({"form": name, "code": q, "hit": found is not None, "results": len(hits)})
        if found is not None and hit is None:
            other = (found.get("otheringredients") or {}).get("ingredients") or []
            hit = {
                "form": name,
                "dsld_id": found.get("id"),
                "stored_upcSku": found.get("upcSku"),
                "fields": {
                    "dietary_ingredients": len(found.get("ingredientRows") or []),
                    "other_ingredients": len(other),
                },
            }
            break
    return {"tried": tried, "hit": hit}


def probe_openfda_label(fm: dict[str, Any]) -> dict[str, Any]:
    tried, hit = [], None
    for name in ("ean13", "upca", "gtin14"):
        code = fm.get(name)
        if not code:
            continue
        st, d = get(f"https://api.fda.gov/drug/label.json?search=openfda.upc:%22{code}%22&limit=1")
        res = (d or {}).get("results") or [] if isinstance(d, dict) else []
        tried.append({"form": name, "code": code, "hit": bool(res)})
        if res and hit is None:
            r = res[0]
            hit = {"form": name, "set_id": r.get("set_id"), "fields": _drug_fields(r)}
    return {"tried": tried, "hit": hit}


def _drug_fields(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "active_ingredient": bool(r.get("active_ingredient")),
        "inactive_ingredient": bool(r.get("inactive_ingredient")),
        "other_information": bool(r.get("storage_and_handling") or r.get("other_safety_information")
                                  or any("other information" in str(x).lower() for x in r.get("package_label_principal_display_panel") or [])),
    }  # fmt: skip


def probe_ndc(fm: dict[str, Any]) -> dict[str, Any]:
    """NDC decoded from a UPC that starts with 3: openFDA NDC directory (package, then
    product NDC) and DailyMed SPLs by NDC."""
    cands = ndc_candidates(fm.get("upca") or "")
    tried, hit = [], None
    for ndc in cands:
        product = ndc.rsplit("-", 1)[0]
        for kind, q in (("package", f"packaging.package_ndc:%22{ndc}%22"),
                        ("product", f"product_ndc:%22{product}%22")):  # fmt: skip
            st, d = get(f"https://api.fda.gov/drug/ndc.json?search={q}&limit=1")
            res = (d or {}).get("results") or [] if isinstance(d, dict) else []
            tried.append(
                {
                    "form": f"openfda {kind} {ndc if kind == 'package' else product}",
                    "code": ndc,
                    "hit": bool(res),
                }
            )
            if res and hit is None:
                r = res[0]
                hit = {"form": f"{kind} {ndc}", "product_ndc": r.get("product_ndc"),
                       "fields": {"active_ingredients": len(r.get("active_ingredients") or [])}}  # fmt: skip
        st, d = get(f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?ndc={ndc}")
        n = (
            int(((d or {}).get("metadata") or {}).get("total_elements") or 0)
            if isinstance(d, dict)
            else 0
        )
        tried.append({"form": f"dailymed {ndc}", "code": ndc, "hit": n > 0})
        if n and hit is None:
            hit = {"form": f"dailymed {ndc}", "fields": {"spls": n}}
    return {"tried": tried, "hit": hit, "applicable": bool(cands)}


# ---------------------------------------------------------------- pipeline
def run_pipeline(code: str) -> dict[str, Any]:
    from lio.foods import barcode as bc
    from lio.foods.lookup import Lookup, LookupSettings

    g = bc.normalise(code, "UPCE" if len(code) == 8 and code[0] in "01" else "")
    lk = Lookup(LookupSettings(usda_api_key=usda_key()))
    try:
        res = lk.lookup(g)
    except Exception as e:  # report, do not stop the run
        return {"error": f"{type(e).__name__}: {e}"}
    info = res.info
    ingr = str(info.get("ingredients_text") or "")
    parts = info.get("ingredient_parts") or []
    return {
        "found": res.found,
        "sources": res.sources,
        "errors": res.errors,
        "ingredients_text": bool(ingr.strip()),
        "ingredients_chars": len(ingr),
        "ingredients_source": info.get("ingredients_text_origin")
        or info.get("ingredients_source", ""),
        "parts": [
            {
                "origin": p.get("origin"),
                "role": p.get("role"),
                "flags": {
                    k: v
                    for k, v in p.items()
                    if k in ("possibly_truncated", "variant", "lang") and v
                },
            }
            for p in parts
        ],
        "matched_forms": info.get("matched_forms") or {},
    }


# ----------------------------------------------------------------- report
def recent_scans(limit: int) -> list[tuple[str, str, str]]:
    db = REPO / "data" / "foods" / "lio_foods.sqlite"
    if not db.exists():
        return []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(
        """SELECT s.scanned_text, s.sample_code, p.name FROM samples s
           JOIN products p ON p.gtin14 = s.gtin14 ORDER BY s.id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    con.close()
    return [(r[0], f"library scan {r[1]}", r[2] or "") for r in rows]


def assess(item: dict[str, Any]) -> dict[str, Any]:
    """Where the list is empty or partial."""
    p = item["probes"]
    issues: list[str] = []
    have_list = False
    off = p["off"]["hit"]
    if off:
        f = off["fields"]
        have_list |= f["ingredients_text"] or bool(f["ingredients_text_languages"])
        kept = sum(
            1
            for x in item["pipeline"].get("parts") or []
            if str(x.get("origin", "")).startswith("openfoodfacts.")
        )
        if len(f["ingredients_text_languages"]) > 1 and kept < 2:
            issues.append(
                f"OFF: lists in {len(f['ingredients_text_languages'])} languages; only one is used"
            )
    fdc = p["fdc"]["hit"]
    if fdc:
        f = fdc["fields"]
        have_list |= f["ingredients"]
        if f["ingredients"] and not f["ingredients_ends_cleanly"]:
            issues.append(
                f"FDC: ingredients may be truncated ({f['ingredients_chars']} chars, no closing punctuation)"
            )
    dsld = p["dsld"]["hit"]
    if dsld:
        have_list |= dsld["fields"]["dietary_ingredients"] > 0
        if not dsld["fields"]["other_ingredients"]:
            issues.append("DSLD: no other ingredients")
    lab = p["openfda_label"]["hit"]
    if lab:
        have_list |= lab["fields"]["active_ingredient"]
        if not lab["fields"]["inactive_ingredient"]:
            issues.append("openFDA label: no inactive ingredients")
    if p["ndc"]["applicable"] and p["ndc"]["hit"] and not lab:
        issues.append("drug found only through its NDC (the pipeline does not try NDC)")
    pipe = item["pipeline"]
    if have_list and not pipe.get("ingredients_text"):
        issues.append("a source has a list, but the pipeline returned none")
    if not have_list and not (p["ndc"]["hit"]):
        issues.append("no source has an ingredient list for any barcode form")
    return {"any_source_has_list": have_list, "issues": issues}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--recent", type=int, default=20, help="library scans to include")
    ap.add_argument("--compare", type=Path, default=None, help="an earlier --out directory")
    ap.add_argument("--rerender", action="store_true", help="rebuild report.md from report.json")
    a = ap.parse_args(argv)
    if a.rerender:
        out = json.loads((a.out / "report.json").read_text())
        for it in out:
            it["assessment"] = assess(it)
        before = json.loads((a.compare / "report.json").read_text()) if a.compare else None
        (a.out / "report.md").write_text(render(out, before))
        return 0
    key = usda_key()
    items = recent_scans(a.recent)
    seen = {re.sub(r"\D", "", c).zfill(14)[-12:] for c, _, _ in items}
    items += [x for x in PANEL if forms(x[0])["gtin14"][-12:] not in seen]
    out: list[dict[str, Any]] = []
    for code, origin, name in items:
        fm = forms(code)
        print(f"{code:>14}  {name}", file=sys.stderr)
        item = {"code": code, "origin": origin, "name": name, "forms": fm, "probes": {
            "off": probe_off(fm), "fdc": probe_fdc(fm, key), "dsld": probe_dsld(fm),
            "openfda_label": probe_openfda_label(fm), "ndc": probe_ndc(fm)}}  # fmt: skip
        time.sleep(3)  # let the OFF rate limit recover before the pipeline's own requests
        item["pipeline"] = run_pipeline(code)
        item["assessment"] = assess(item)
        out.append(item)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "report.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    before = json.loads((a.compare / "report.json").read_text()) if a.compare else None
    (a.out / "report.md").write_text(render(out, before))
    print(a.out / "report.md")
    return 0


def _rate(items: list[dict[str, Any]], pred: Any) -> str:
    n = sum(1 for i in items if pred(i))
    return f"{n}/{len(items)}"


def summary(items: list[dict[str, Any]]) -> dict[str, str]:
    P = lambda s: lambda i: i["probes"][s]["hit"] is not None  # noqa: E731
    return {
        "Open Food Facts": _rate(items, P("off")),
        "USDA FDC Branded": _rate(items, P("fdc")),
        "NIH DSLD": _rate(items, P("dsld")),
        "openFDA label (by UPC)": _rate(items, P("openfda_label")),
        "openFDA NDC (UPC 3 + NDC)": _rate(items, P("ndc")),
        "Pipeline: product found": _rate(items, lambda i: i["pipeline"].get("found")),
        "Pipeline: ingredient list": _rate(items, lambda i: i["pipeline"].get("ingredients_text")),
        "Pipeline: list of 50+ characters": _rate(
            items, lambda i: (i["pipeline"].get("ingredients_chars") or 0) >= 50
        ),
        "Pipeline: parts with their origin field": _rate(
            items, lambda i: bool(i["pipeline"].get("parts"))
        ),
        "Pipeline used FDC": _rate(items, lambda i: "usda" in (i["pipeline"].get("sources") or [])),
        "Pipeline used DSLD": _rate(
            items, lambda i: "dsld" in (i["pipeline"].get("sources") or [])
        ),
        "Pipeline used openFDA (UPC)": _rate(
            items, lambda i: "openfda" in (i["pipeline"].get("sources") or [])
        ),
        "Pipeline used openFDA/DailyMed (NDC)": _rate(
            items, lambda i: "ndc" in (i["pipeline"].get("sources") or [])
        ),
        "Pipeline used OFF": _rate(
            items, lambda i: "openfoodfacts" in (i["pipeline"].get("sources") or [])
        ),
        "Any source has a list": _rate(items, lambda i: i["assessment"]["any_source_has_list"]),
    }


def render(items: list[dict[str, Any]], before: list[dict[str, Any]] | None) -> str:
    L: list[str] = ["# Ingredient coverage report", ""]
    now = summary(items)
    if before:
        was = summary(before)
        L += ["| Measure | Before | After |", "|---|---|---|"]
        L += [f"| {k} | {was.get(k, '–')} | {v} |" for k, v in now.items()]
    else:
        L += ["| Measure | Hits |", "|---|---|"] + [f"| {k} | {v} |" for k, v in now.items()]
    L += ["", "## Per barcode", ""]
    for it in items:
        fm = it["forms"]
        L.append(f"### {it['code']}: {it['name']}")
        L.append(f"- From: {it['origin']}. Check digit {'OK' if fm['check_digit_ok'] else 'WRONG'}; "
                 f"GTIN-14 {fm['gtin14']}{'; UPC-E ' + fm['upce'] if fm.get('upce') else ''}.")  # fmt: skip
        for src, label in (("off", "OFF"), ("fdc", "FDC"), ("dsld", "DSLD"),
                           ("openfda_label", "openFDA label"), ("ndc", "openFDA NDC")):  # fmt: skip
            pr = it["probes"][src]
            if src == "ndc" and not pr.get("applicable"):
                continue
            tried = ", ".join(f"{t['form']}{'+' if t['hit'] else '-'}" for t in pr["tried"])
            hit = pr["hit"]
            got = (
                "no match"
                if not hit
                else f"matched with {hit['form']}: "
                + ", ".join(f"{k}={v}" for k, v in hit["fields"].items())
            )
            extra = ""
            if hit and hit.get("stored_gtinUpc"):
                extra = f" (stored as {hit['stored_gtinUpc']!r})"
            if hit and hit.get("stored_upcSku"):
                extra = f" (stored as {hit['stored_upcSku']!r})"
            L.append(f"- {label}: tried [{tried}]; {got}{extra}")
        pipe = it["pipeline"]
        L.append(f"- Pipeline: found={pipe.get('found')}, sources={pipe.get('sources')}, "
                 f"list={'yes (' + str(pipe.get('ingredients_chars')) + ' chars, ' + str(pipe.get('ingredients_source')) + ')' if pipe.get('ingredients_text') else 'NO'}"
                 f"{', errors=' + str(pipe['errors']) if pipe.get('errors') else ''}")  # fmt: skip
        if pipe.get("matched_forms"):
            L.append(
                "- Matched forms: "
                + ", ".join(
                    f"{k}={v.get('form')} {v.get('code')}" for k, v in pipe["matched_forms"].items()
                )
            )
        if pipe.get("parts"):
            L.append("- Parts: " + ", ".join(f"{p['role']}<{p['origin']}>" for p in pipe["parts"]))
        for issue in it["assessment"]["issues"]:
            L.append(f"- **Issue:** {issue}")
        L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
