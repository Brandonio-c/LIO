"""Food library: barcodes, product lookup, the database, scans, dashboard and phone APIs."""

from __future__ import annotations

import base64
import io
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from lio.config import HwConfig
from lio.dashboard.server import DashboardServer, Foods
from lio.dashboard.session import Session
from lio.foods import barcode as bc
from lio.foods.intake import Intake
from lio.foods.lookup import Lookup, LookupSettings, derived
from lio.foods.phone import PhoneKey, PhoneServer
from lio.foods.scans import build_scan
from lio.foods.store import FoodLibrary, LibraryError

pytestmark = pytest.mark.unit

UPC = "016000275287"  # Cheerios (UPC-A)
EAN = "3017624010701"  # Nutella (EAN-13)

OFF_PRODUCT = {
    "product_name": "Nutella",
    "brands": "Ferrero",
    "quantity": "400 g",
    "categories": "Spreads, Sweet spreads, Hazelnut spreads",
    "ingredients_text_en": "Sugar, palm oil, hazelnuts 13%, skimmed milk powder 8.7%, cocoa",
    "allergens_tags": ["en:milk", "en:nuts", "en:soybeans"],
    "nutriscore_grade": "e",
    "nova_group": 4,
    "nutriments": {
        "energy-kcal_100g": 539,
        "fat_100g": 30.9,
        "saturated-fat_100g": 10.6,
        "carbohydrates_100g": 57.5,
        "sugars_100g": 56.3,
        "proteins_100g": 6.3,
        "salt_100g": 0.107,
        "sodium_100g": 0.0428,
    },
}
USDA_FOOD = {
    "fdcId": 2517161,
    "description": "Cheerios Cereal",
    "brandOwner": "General Mills",
    "gtinUpc": "00016000275287",
    "servingSize": 39.0,
    "servingSizeUnit": "GRM",
    "householdServingFullText": "1 1/2 cup",
    "brandedFoodCategory": "Cereal",
    "ingredients": "WHOLE GRAIN OATS, CORN STARCH, SUGAR, SALT",
    "foodNutrients": [
        {"nutrientNumber": "203", "value": 12.8},
        {"nutrientNumber": "204", "value": 6.41},
        {"nutrientNumber": "205", "value": 74.4},
        {"nutrientNumber": "208", "value": 359},
        {"nutrientNumber": "307", "value": 487},
    ],
}


DSLD_LABEL = {
    "id": 64567,
    "fullName": "Fish Oil",
    "brandName": "Nature Made",
    "upcSku": "7 80994 81213 0",
    "netContents": [{"display": "100 Softgel(s)"}],
    "servingSizes": [{"minQuantity": 1, "unit": "Softgel(s)"}],
    "ingredientRows": [
        {"name": "Calories", "quantity": [{"quantity": 10, "unit": "Calorie(s)"}]},
        {"name": "EPA", "quantity": [{"quantity": 425, "unit": "Milligram(s)"}]},
    ],
    "otheringredients": {"text": None, "ingredients": [{"name": "Gelatin"}, {"name": "Glycerin"}]},
    "statements": [{"type": "Precautions", "notes": "Keep out of reach of children."}],
}


class FakeWeb:
    """Answers like Open Food Facts (Nutella only) and USDA (Cheerios only)."""

    def __init__(self, offline: bool = False) -> None:
        self.offline = offline
        self.calls: list[str] = []

    def __call__(self, url: str, headers: dict[str, str], timeout: float) -> Any:
        self.calls.append(url)
        assert "User-Agent" in headers
        if self.offline:
            raise urllib.error.URLError("no network")
        if "openfoodfacts" in url:
            if f"/{EAN}.json" in url:
                return {"status": 1, "code": EAN, "product": OFF_PRODUCT}
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)  # type: ignore[arg-type]
        if "api.fda.gov" in url or "dailymed.nlm.nih.gov" in url or "id.gs1.org" in url:
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)  # type: ignore[arg-type]
        if "ods.od.nih.gov" in url:
            if "search-filter" in url and "780994812130" not in url and "7%2080994" in url:
                return {"hits": [{"_id": "64567", "_source": {"fullName": "Fish Oil"}}]}
            if "/label/64567" in url:
                return DSLD_LABEL
            return {"hits": [], "stats": {"count": 0}}
        if "nal.usda.gov" in url:
            hit = "00016000275287" in url
            return {"totalHits": int(hit), "foods": [USDA_FOOD] if hit else []}
        raise AssertionError(url)


def png_barcode(code: str) -> bytes:
    zxingcpp = pytest.importorskip("zxingcpp")
    pytest.importorskip("PIL")
    import numpy as np
    from PIL import Image

    fmt = zxingcpp.BarcodeFormat.EAN13 if len(code) == 13 else zxingcpp.BarcodeFormat.UPCA
    img = zxingcpp.write_barcode_to_image(zxingcpp.create_barcode(code, fmt), scale=3)
    buf = io.BytesIO()
    Image.fromarray(np.array(img)).save(buf, "PNG")
    return buf.getvalue()


def jpeg_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 120, 40)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def web() -> FakeWeb:
    return FakeWeb()


@pytest.fixture
def lib(tmp_path: Path, web: FakeWeb) -> Iterator[FoodLibrary]:
    lb = FoodLibrary(tmp_path / "foods", Lookup(LookupSettings(), fetch=web))
    lb._download_image = lambda gtin14, url: ""  # type: ignore[method-assign]
    yield lb
    lb.close()


# ------------------------------------------------------------------ barcodes


class TestBarcode:
    def test_check_digits(self) -> None:
        assert bc.check_digit(UPC[:-1]) == int(UPC[-1])
        assert bc.check_digit(EAN[:-1]) == int(EAN[-1])
        assert bc.check_digit("9638507") == 4  # EAN-8 96385074

    def test_forms_of_one_product_share_a_gtin14(self) -> None:
        a, b = bc.normalise(UPC), bc.normalise("0" + UPC)
        assert a.gtin14 == b.gtin14 == "00016000275287"
        assert a.code == b.code == UPC and a.kind == "UPC-A"
        assert bc.normalise(EAN).kind == "EAN-13"
        e8 = bc.normalise("96385074")
        assert e8.kind == "EAN-8" and e8.code == "96385074"
        assert bc.normalise("0 16000 27528 7").code == UPC

    def test_upce_expands(self) -> None:
        assert bc.expand_upce("04252614") == "042100005264"
        assert bc.normalise("04252614", "UPCE").code == "042100005264"

    def test_bad_codes_are_refused(self) -> None:
        for bad in ("016000275288", "12345", "abc", ""):
            with pytest.raises(bc.BarcodeError):
                bc.normalise(bad)

    def test_lookup_forms(self) -> None:
        assert bc.normalise(UPC).lookup_codes == [UPC, "0" + UPC, "00" + UPC]

    def test_decodes_a_photo(self) -> None:
        found = bc.decode_image(png_barcode(EAN))
        best = bc.best_code(found)
        assert best is not None and best[0].code == EAN

    def test_reads_blurred_ink_spread_photos(self) -> None:
        """Narrow gaps blurred shut (as in a real phone frame) are reopened."""
        zxingcpp = pytest.importorskip("zxingcpp")
        import numpy as np
        from PIL import Image, ImageFilter

        code = "300680418301"
        raw = zxingcpp.write_barcode_to_image(
            zxingcpp.create_barcode(code, zxingcpp.BarcodeFormat.UPCA), scale=4
        )
        im = Image.fromarray(np.array(raw)).convert("L").filter(ImageFilter.MinFilter(3))
        canvas = Image.new("L", (1100, 800), 230)
        canvas.paste(im, ((1100 - im.width) // 2, (800 - im.height) // 2))
        canvas = canvas.filter(ImageFilter.GaussianBlur(1.2))
        buf = io.BytesIO()
        canvas.save(buf, "JPEG", quality=80)
        best = bc.best_code(bc.decode_image(buf.getvalue(), retail_only=True))
        assert best is not None and best[0].code == code

    def test_blank_photo_finds_nothing(self) -> None:
        pytest.importorskip("zxingcpp")
        assert bc.best_code(bc.decode_image(jpeg_bytes())) is None


# -------------------------------------------------------------------- lookup


class TestLookup:
    def test_open_food_facts(self, web: FakeWeb) -> None:
        r = Lookup(LookupSettings(), fetch=web).lookup(bc.normalise(EAN))
        assert r.found and r.sources == ["openfoodfacts"]
        assert r.info["name"] == "Nutella" and r.info["brand"] == "Ferrero"
        per = r.info["nutrition_per_100g"]
        assert per["fat_g"] == 30.9 and per["sodium_mg"] == pytest.approx(42.8)
        assert r.info["allergens"] == ["milk", "nuts", "soybeans"]
        assert r.info["derived_per_100g"]["remainder_g"] == pytest.approx(100 - 94.807, abs=0.01)

    def test_usda_when_open_food_facts_has_nothing(self, web: FakeWeb) -> None:
        r = Lookup(LookupSettings(), fetch=web).lookup(bc.normalise(UPC))
        assert r.found and r.sources == ["usda"]
        assert r.info["name"] == "Cheerios Cereal" and r.info["serving_size"].startswith("39 g")
        assert r.info["nutrition_per_100g"]["salt_g"] == pytest.approx(1.218, abs=0.001)
        assert len([u for u in web.calls if "openfoodfacts" in u]) == 3  # every code form
        assert r.errors == {}

    def test_usda_wins_and_open_food_facts_fills_gaps(self) -> None:
        def both(url: str, headers: dict[str, str], timeout: float) -> Any:
            if "openfoodfacts" in url:
                return {"status": 1, "product": {**OFF_PRODUCT, "product_name": "My Bff"}}
            return {"foods": [USDA_FOOD]}

        r = Lookup(LookupSettings(), fetch=both).lookup(bc.normalise(UPC))
        assert r.sources == ["usda", "openfoodfacts"]
        assert r.info["name"] == "Cheerios Cereal"  # manufacturer data, not the crowd's name
        assert r.info["allergens"] == ["milk", "nuts", "soybeans"]  # filled from OFF
        assert r.info["nutrition_per_100g"]["protein_g"] == 12.8  # USDA's value kept
        assert r.info["nutrition_per_100g"]["sugars_g"] == 56.3  # gap filled from OFF
        assert set(r.info["links"]) == {"usda", "openfoodfacts"}

    def test_offline(self) -> None:
        r = Lookup(LookupSettings(), fetch=FakeWeb(offline=True)).lookup(bc.normalise(UPC))
        assert not r.found and set(r.errors) == {"openfoodfacts", "usda", "dsld", "openfda"}

    def test_derived_needs_the_macros(self) -> None:
        assert derived({"fat_g": 1.0}) == {}


# --------------------------------------------------------------------- store


class TestStore:
    def test_samples_get_codes_and_products_are_shared(self, lib: FoodLibrary) -> None:
        a = lib.create_sample(bc.normalise(EAN), notes="jar 1", barcode_photo=jpeg_bytes())
        b = lib.create_sample(bc.normalise(EAN), notes="jar 2")
        assert (a["sample_code"], b["sample_code"]) == ("LIO-F-00001", "LIO-F-00002")
        assert a["uuid"] != b["uuid"] and a["product"]["name"] == "Nutella"
        assert lib.counts() == {"samples": 2, "products": 1, "scans": 0, "archived": 0}
        photo = lib.file_path(a["barcode_photo"])
        assert photo is not None and photo.read_bytes()[:3] == b"\xff\xd8\xff"
        assert lib.file_path("../lio_foods.sqlite") is None

    def test_search_update_archive(self, lib: FoodLibrary) -> None:
        lib.create_sample(bc.normalise(EAN))
        s = lib.create_sample(bc.normalise(UPC))
        assert [x["name"] for x in lib.samples("cheerios")] == ["Cheerios Cereal"]
        lib.update_sample(s["sample_code"], {"lot": "L42", "notes": "opened"})
        assert lib.samples("L42")[0]["sample_code"] == s["sample_code"]
        lib.update_sample(s["sample_code"], {"archived": True})
        assert [x["sample_code"] for x in lib.samples()] == ["LIO-F-00001"]
        assert [x["sample_code"] for x in lib.samples(archived=True)] == [s["sample_code"]]

    def test_unknown_product_then_manual_label_data(self, lib: FoodLibrary) -> None:
        s = lib.create_sample(bc.normalise("96385074"))
        assert not s["product"]["found"]
        p = lib.set_product_info(
            s["gtin14"],
            {
                "name": "Test bar",
                "nutrition_per_100g": {"fat_g": 10, "carbohydrates_g": 50, "protein_g": 20},
            },
        )
        assert p["name"] == "Test bar" and p["sources"] == ["manual"]
        assert p["info"]["derived_per_100g"]["remainder_g"] == 20.0
        with pytest.raises(LibraryError):
            lib.set_product_info(s["gtin14"], {"nutrition_per_100g": {"vitamin_q": 1}})

    def test_failed_refresh_keeps_the_data(self, lib: FoodLibrary, web: FakeWeb) -> None:
        g = bc.normalise(EAN)
        lib.product(g)
        web.offline = True
        p = lib.product(g, refresh=True)
        assert p["name"] == "Nutella" and "openfoodfacts" in p["errors"]

    def test_photos_never_overwrite(self, lib: FoodLibrary) -> None:
        s = lib.create_sample(bc.normalise(EAN), barcode_photo=jpeg_bytes())
        s2 = lib.set_photo(s["sample_code"], "barcode", jpeg_bytes())
        assert s2["barcode_photo"] != s["barcode_photo"]
        assert lib.file_path(s["barcode_photo"]) is not None
        with pytest.raises(LibraryError):
            lib.set_photo(s["sample_code"], "selfie", jpeg_bytes())

    def test_intake_two_steps(self, lib: FoodLibrary) -> None:
        it = Intake(lib)
        r = it.identify(png_barcode(EAN))
        assert r["code"] == EAN and r["product"]["name"] == "Nutella" and r["format"] == "EAN13"
        s = it.commit(r["draft"], {"notes": "from photo"}, source="phone")
        assert s["barcode_photo"] and s["source"] == "phone" and s["barcode_format"] == "EAN13"
        with pytest.raises(LibraryError):
            it.commit(r["draft"], {}, source="phone")  # one save per draft
        r2 = it.identify(None, UPC)
        assert r2["format"] == "typed" and r2["existing_samples"] == []
        assert it.identify(None, EAN)["existing_samples"][0]["sample_code"] == s["sample_code"]
        with pytest.raises(bc.BarcodeError):
            it.identify(jpeg_bytes())


# --------------------------------------------------------------------- scans


@pytest.fixture
def session(cfg: HwConfig, tmp_path: Path) -> Iterator[Session]:
    s = Session(cfg, tmp_path / "results")
    s.connect("sim")
    yield s
    s.shutdown(timeout_s=30)


class TestScans:
    def test_sim_scan_is_stored_with_every_reading(
        self, session: Session, lib: FoodLibrary, cfg: HwConfig
    ) -> None:
        s = lib.create_sample(bc.normalise(EAN))
        sweeps, meta = session.sample_sweeps(2)
        assert meta["kind"] == "sim" and meta["n"] == cfg.thresholds.integer("channel.meas_n")
        scan = lib.add_scan(s["sample_code"], build_scan(cfg, sweeps, **meta))
        assert scan["repeats"] == 2 and len(scan["spectrum"]) == 16
        nms = [r["nm"] for r in scan["spectrum"]]
        assert nms == sorted(nms)
        visible = next(r for r in scan["spectrum"] if r["hole"] == 3)
        assert visible["opt101"]["net"] > 100 and visible["n_sweeps"] == 2
        csv_text = lib.scan_csv(scan["uuid"])
        assert len(csv_text.strip().splitlines()) == 4 + 2 * 16 * 2
        assert lib.sample(s["sample_code"])["scans"][0]["uuid"] == scan["uuid"]
        full = lib.export()["samples"][0]["scans"][0]
        assert len(full["sweeps"]) == 2

    def test_scan_refused_while_the_ring_runs(self, session: Session) -> None:
        from lio.dashboard.session import Busy

        session._ring = {"state": "running"}
        try:
            with pytest.raises(Busy):
                session.sample_sweeps(1)
        finally:
            session._ring = None


# ------------------------------------------------------------------- servers


def http(
    url: str, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None
) -> tuple[int, Any]:
    req = urllib.request.Request(url, method="GET" if body is None else "POST")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if body is not None:
        req.data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw, status, ctype = r.read(), r.status, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raw, status, ctype = e.read(), e.code, e.headers.get("Content-Type", "")
    return status, json.loads(raw) if "json" in ctype else raw


def data_url(blob: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(blob).decode()


@pytest.fixture
def dash(session: Session, lib: FoodLibrary) -> Iterator[DashboardServer]:
    srv = DashboardServer(session, "127.0.0.1", 0, Foods(lib, Intake(lib)))
    srv.serve_in_thread()
    yield srv
    srv.shutdown()
    srv.server_close()


@pytest.fixture
def phone(lib: FoodLibrary, tmp_path: Path) -> Iterator[PhoneServer]:
    srv = PhoneServer(lib, Intake(lib), PhoneKey(tmp_path / "key.txt"), "127.0.0.1", 0)
    srv.serve_in_thread()
    yield srv
    srv.shutdown()
    srv.server_close()


class TestDashboardApi:
    def test_add_scan_and_browse(self, dash: DashboardServer) -> None:
        base, tok = dash.url.rstrip("/"), {"X-LIO-Token": dash.token}
        assert http(base + "/api/foods/status")[0] == 403  # token needed
        st, status = http(base + "/api/foods/status", headers=tok)
        assert st == 200 and status["counts"]["samples"] == 0 and not status["phone"]["enabled"]
        st, r = http(base + "/api/foods/identify", {"code": UPC}, tok)
        assert st == 200 and r["product"]["name"] == "Cheerios Cereal"
        st, s = http(base + "/api/foods/save", {"draft": r["draft"], "notes": "box"}, tok)
        assert st == 200 and s["source"] == "dashboard"
        st, sc = http(
            base + "/api/foods/scan", {"sample_code": s["sample_code"], "repeats": 1}, tok
        )
        assert st == 200 and sc["kind"] == "sim"
        st, _ = http(base + "/api/foods/scan", {"sample_code": "LIO-F-99999"}, tok)
        assert st == 400
        st, lst = http(base + "/api/foods/samples?q=cheer", headers=tok)
        assert [x["n_scans"] for x in lst["samples"]] == [1]
        st, csv_body = http(base + f"/foods/export/scan/{sc['uuid']}.csv")
        assert st == 200 and b"repeat,hole" in csv_body
        assert http(base + "/foods/export/samples.csv")[0] == 200
        assert http(base + "/foods/files/../lio_foods.sqlite")[0] == 404
        st, bad = http(base + "/api/foods/identify", {"code": "123"}, tok)
        assert st == 400 and "digits" in bad["error"]


class TestPhone:
    def test_needs_the_key_and_saves_a_photo_scan(self, phone: PhoneServer) -> None:
        base = f"http://127.0.0.1:{phone.port}"
        st, page = http(base + "/")
        assert st == 200 and b"LIO food intake" in page
        assert http(base + "/icon-192.png")[0] == 200
        assert http(base + "/api/status")[0] == 403
        assert http(base + "/api/status", headers={"X-LIO-Phone-Key": "wrong"})[0] == 403
        key = {"X-LIO-Phone-Key": phone.key.value}
        st, r = http(base + "/api/identify", {"photo": data_url(png_barcode(EAN))}, key)
        assert st == 200 and r["product"]["name"] == "Nutella"
        st, s = http(base + "/api/save", {"draft": r["draft"], "entered_by": "BC"}, key)
        assert st == 200 and s["sample_code"] == "LIO-F-00001" and s["entered_by"] == "BC"
        st, photo = http(f"{base}/files/{s['barcode_photo']}?k={phone.key.value}")
        assert st == 200 and photo[:3] == b"\xff\xd8\xff"
        st, man = http(f"{base}/manifest.webmanifest?k={phone.key.value}")
        assert st == 200 and phone.key.value in man["start_url"]
        assert http(base + "/api/recent", headers=key)[1]["samples"][0]["sample_code"] == (
            "LIO-F-00001"
        )
        old = phone.key.value
        phone.key.renew()
        assert http(base + "/api/status", headers={"X-LIO-Phone-Key": old})[0] == 403

    def test_live_frames_decode_without_lookup(self, phone: PhoneServer, web: FakeWeb) -> None:
        base, key = f"http://127.0.0.1:{phone.port}", {"X-LIO-Phone-Key": phone.key.value}
        n_calls = len(web.calls)
        st, r = http(base + "/api/decode", {"photo": data_url(png_barcode(EAN))}, key)
        assert st == 200 and r["found"] and r["code"] == EAN and r["kind"] == "EAN-13"
        assert len(web.calls) == n_calls  # no online lookup for a live frame
        st, r = http(base + "/api/decode", {"photo": data_url(jpeg_bytes())}, key)
        assert st == 200 and r == {"found": False, "ms": r["ms"]}
        assert (phone.lib.root / "debug" / "last_live_frame.jpg").is_file()

    def test_key_survives_a_restart(self, tmp_path: Path) -> None:
        a = PhoneKey(tmp_path / "k.txt")
        assert PhoneKey(tmp_path / "k.txt").value == a.value
        assert (tmp_path / "k.txt").stat().st_mode & 0o077 == 0


# -------------------------------------------------------------------- tunnel

FAKE_CLOUDFLARED = """#!/bin/sh
echo "INF Requesting new quick Tunnel on trycloudflare.com..." >&2
echo "INF |  https://brave-test-words.trycloudflare.com  |" >&2
echo "INF Registered tunnel connection connIndex=0 protocol=quic" >&2
sleep 30
"""


class TestTunnel:
    def test_reports_the_public_address_and_stops(self, tmp_path: Path) -> None:
        import time as _time

        from lio.foods.tunnel import CloudflareTunnel

        exe = tmp_path / "cloudflared"
        exe.write_text(FAKE_CLOUDFLARED)
        exe.chmod(0o755)
        t = CloudflareTunnel(8766, str(exe))
        t.start()
        for _ in range(100):
            if t.status()["state"] == "up":
                break
            _time.sleep(0.05)
        assert t.status() == {
            "state": "up",
            "url": "https://brave-test-words.trycloudflare.com",
            "error": "",
        }
        t.stop()
        assert t.status()["state"] == "off"

    def test_missing_binary(self, tmp_path: Path) -> None:
        from lio.foods.tunnel import CloudflareTunnel

        t = CloudflareTunnel(8766, str(tmp_path / "nope"))
        t.start()
        assert t.status()["state"] == "error" and "not installed" in str(t.status()["error"])

    def test_tunnel_link_comes_first(self, phone: PhoneServer) -> None:
        from lio.foods.tunnel import CloudflareTunnel

        phone.tunnel = CloudflareTunnel(phone.port)
        phone.tunnel.state, phone.tunnel.url = "up", "https://x-y.trycloudflare.com"
        assert phone.urls()[0] == f"https://x-y.trycloudflare.com/?k={phone.key.value}"

    def test_wrong_keys_are_throttled(self, phone: PhoneServer) -> None:
        base = f"http://127.0.0.1:{phone.port}"
        codes = [
            http(base + "/api/status", headers={"X-LIO-Phone-Key": f"guess{i}"})[0]
            for i in range(35)
        ]
        assert codes[0] == 403 and codes[-1] == 429
        key = {"X-LIO-Phone-Key": phone.key.value}
        assert http(base + "/api/status", headers=key)[0] == 200  # the real key still works


# ------------------------------------------------------------- label reading

COLD_LABEL = [
    "Nutrition Facts",
    "8 servings per container",
    "Serving size 1 cup (55g)",
    "Amount per serving",
    "Calories 230",
    "% Daily Value*",
    "Total Fat 8g 10%",
    "Saturated Fat 1g 5%",
    "Trans Fat 0g",
    "Cholesterol 0mg 0%",
    "Sodium 160mg 7%",
    "Total Carbohydrate 37g 13%",
    "Dietary Fiber 4g 14%",
    "Total Sugars 12g",
    "Includes 10g Added Sugars 20%",
    "Protein 3g",
    "INGREDIENTS: WHOLE GRAIN OATS,",
    "SUGAR, CORN STARCH, VITAMIN E (MIXED TOCO-",
    "PHEROLS) ADDED TO PRESERVE FRESHNESS.",
    "CONTAINS: WHEAT INGREDIENTS.",
    "DISTRIBUTED BY GENERAL MILLS",
]


class TestLabelText:
    def test_ingredients_between_the_heading_and_the_next_section(self) -> None:
        from lio.foods.ocr import extract_ingredients

        r = extract_ingredients(COLD_LABEL)
        assert r["ingredients"] == (
            "WHOLE GRAIN OATS, SUGAR, CORN STARCH, VITAMIN E (MIXED TOCOPHEROLS) "
            "ADDED TO PRESERVE FRESHNESS"
        )
        assert r["contains"] == "WHEAT INGREDIENTS"
        other = extract_ingredients(["Other ingredients: gelatin, glycerin. Warning: keep cool"])
        assert (
            other["ingredients"] == "gelatin, glycerin" and other["heading"] == "Other ingredients"
        )
        assert extract_ingredients(["no list here"])["ingredients"] == ""

    def test_nutrition_facts_per_serving_and_per_100g(self) -> None:
        from lio.foods.ocr import parse_nutrition

        n = parse_nutrition(COLD_LABEL)
        assert n["serving_g"] == 55.0 and n["serving"] == "1 cup (55g)"
        ps = n["per_serving"]
        assert ps == {
            "energy_kcal": 230.0, "fat_g": 8.0, "saturated_fat_g": 1.0, "trans_fat_g": 0.0,
            "cholesterol_mg": 0.0, "sodium_mg": 160.0, "carbohydrates_g": 37.0, "fiber_g": 4.0,
            "sugars_g": 12.0, "added_sugars_g": 10.0, "protein_g": 3.0,
        }  # fmt: skip
        assert n["per_100g"]["fat_g"] == pytest.approx(14.545, abs=0.001)
        assert n["per_100g"]["salt_g"] == pytest.approx(0.727, abs=0.001)
        assert parse_nutrition(["Calories 90"])["per_100g"] == {}  # no grams: no conversion

    def test_two_columns_are_not_interleaved(self) -> None:
        from lio.foods.ocr import Line, reading_order

        lines = [
            Line("Nutrition Facts", 1, 0.05, 0.9, 0.4, 0.05),
            Line("INGREDIENTS: OATS,", 1, 0.55, 0.9, 0.4, 0.05),
            Line("Calories 230", 1, 0.05, 0.8, 0.3, 0.05),
            Line("SUGAR, SALT.", 1, 0.55, 0.8, 0.4, 0.05),
        ]
        assert reading_order(lines) == [
            "Nutrition Facts", "Calories 230", "INGREDIENTS: OATS,", "SUGAR, SALT.",
        ]  # fmt: skip

    @pytest.mark.skipif(sys.platform != "darwin", reason="Apple Vision")
    def test_apple_vision_reads_a_label(self) -> None:
        from lio.foods import ocr

        if not ocr.available():
            pytest.skip("Xcode command line tools not installed")
        from PIL import Image, ImageDraw, ImageFont

        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 34)
        except OSError:
            pytest.skip("no system font")
        img = Image.new("RGB", (1400, 300), "white")
        d = ImageDraw.Draw(img)
        d.text((30, 30), "INGREDIENTS: METHYLCELLULOSE, SUCROSE,", fill="black", font=font)
        d.text((30, 80), "CITRIC ACID. CONTAINS: NO ALLERGENS.", fill="black", font=font)
        buf = io.BytesIO()
        img.save(buf, "JPEG")
        try:
            r = ocr.read_label(buf.getvalue())
        except ocr.OcrError as e:
            pytest.skip(f"Vision unavailable here: {e}")
        assert r["ingredients"].upper() == "METHYLCELLULOSE, SUCROSE, CITRIC ACID"


class TestSupplementsAndPicking:
    def test_dsld_by_barcode(self, web: FakeWeb) -> None:
        r = Lookup(LookupSettings(), fetch=web).lookup(bc.normalise("780994812130"))
        assert r.sources == ["dsld"] and r.info["name"] == "Fish Oil"
        assert r.info["ingredients_text"] == (
            "Calories (10 kcal), EPA (425 mg). Other ingredients: Gelatin, Glycerin"
        )
        assert r.info["links"]["dsld"].endswith("/64567")

    def test_name_search_ranks_by_words(self) -> None:
        def fetch(url: str, headers: dict[str, str], timeout: float) -> Any:
            if "nal.usda.gov" in url:
                return {"foods": [{"fdcId": 1, "description": "ORANGE SODA", "brandOwner": "X"}]}
            return {
                "hits": [
                    {"_id": "26748", "_source": {"fullName": "Citrucel Orange", "brandName": "GSK"}}
                ]
            }

        c = Lookup(LookupSettings(), fetch=fetch).search_by_name("citrucel orange")
        assert [x["id"] for x in c] == ["26748"]  # "orange soda" lacks the distinctive word

    def test_picked_label_and_locked_fields_survive_a_refresh(
        self, lib: FoodLibrary, web: FakeWeb
    ) -> None:
        from lio.foods.lookup import parse_dsld

        s = lib.create_sample(bc.normalise("96385074"))  # unknown everywhere
        p = lib.adopt(s["gtin14"], parse_dsld(DSLD_LABEL), DSLD_LABEL, source="dsld", query="fish")
        assert p["info"]["ingredients_source"] == "dsld (picked)" and p["found"]
        lib.set_product_info(
            s["gtin14"], {"ingredients_text": "fish oil, gelatin"}, source="label photo"
        )
        p = lib.product(bc.normalise("96385074"), refresh=True)
        assert p["info"]["ingredients_text"] == "fish oil, gelatin"
        assert p["info"]["ingredients_source"] == "label photo"
        assert [x["sample_code"] for x in lib.samples(ingredients="yes")] == [s["sample_code"]]

    def test_label_photo_is_kept_and_applied(
        self, lib: FoodLibrary, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import lio.foods.intake as intake_mod

        monkeypatch.setattr(
            intake_mod,
            "read_label",
            lambda data, kind="": {
                "lines": ["INGREDIENTS: OATS, SALT."], "text": "INGREDIENTS: OATS, SALT.",
                "ingredients": "OATS, SALT", "contains": "", "heading": "INGREDIENTS",
                "nutrition": {"per_100g": {}, "serving": "", "serving_g": None},
            },
        )  # fmt: skip
        it = Intake(lib)
        s = lib.create_sample(bc.normalise("96385074"))
        assert lib.samples(ingredients="no")[0]["sample_code"] == s["sample_code"]
        r = it.read_label(jpeg_bytes(), "ingredients")
        assert r["ingredients"] == "OATS, SALT"
        out = it.apply_label(
            s["sample_code"], {"label_draft": r["label_draft"], "ingredients_text": "Oats, salt"}
        )
        assert out["label_photos"][0]["kind"] == "ingredients"
        assert out["product"]["info"]["ingredients_text"] == "Oats, salt"
        assert out["product"]["info"]["ingredients_source"] == "label photo"
        with pytest.raises(LibraryError):
            it.apply_label(s["sample_code"], {"label_draft": r["label_draft"]})


# ------------------------------------------------------------ web fallback

DAILYMED_PAGE = """<html><head><title>DailyMed - CITRUCEL</title>
<script>var x="Ingredients: no";</script></head><body>
<h2>Active ingredient (in each heaping tablespoon)</h2><p>CITRUCEL Orange</p>
<p>Methylcellulose (a non-allergenic fiber) 2 g</p>
<h2>Inactive ingredients (Citrucel Orange)</h2><p>citric acid, maltodextrin, sucrose, riboflavin</p>
<h2>Purpose</h2><p>Bulk-forming fiber laxative</p>
<div>Ingredients: click here to learn more</div>
<h3>INGREDIENTS AND APPEARANCE</h3><p>CITRUCEL methylcellulose powder</p>
<td>Active Ingredient/Active Moiety</td></body></html>"""
BING_PAGE = (
    '<ol><li class="b_algo"><h2><a href="https://www.bing.com/ck/a?!&amp;u=a1aHR0cHM6Ly9kYWls'
    'eW1lZC5ubG0ubmloLmdvdi9sYWJlbA&amp;ntb=1">DailyMed - <strong>CITRUCEL</strong></a></h2></li>'
    '<li class="b_algo"><h2><a href="https://www.citrucel.com/products/orange">'
    "Orange | Citrucel</a></h2></li></ol>"
)


class TestWebFallback:
    def test_ingredient_sections_from_a_page(self) -> None:
        from lio.foods.websearch import ingredient_sections, page_lines

        secs = ingredient_sections(page_lines(DAILYMED_PAGE))
        assert secs == [
            {
                "heading": "Active ingredient (in each heaping tablespoon)",
                "text": "CITRUCEL Orange Methylcellulose (a non-allergenic fiber) 2 g",
            },
            {
                "heading": "Inactive ingredients (Citrucel Orange)",
                "text": "citric acid, maltodextrin, sucrose, riboflavin",
            },
        ]

    def test_search_results_pages(self) -> None:
        from lio.foods.websearch import parse_bing, rank

        res = parse_bing(BING_PAGE)
        assert res == [
            {"url": "https://dailymed.nlm.nih.gov/label", "title": "DailyMed - CITRUCEL"},
            {"url": "https://www.citrucel.com/products/orange", "title": "Orange | Citrucel"},
        ]
        assert rank(res, "Citrucel")[0]["url"].startswith("https://www.citrucel.com")

    def test_find_shows_links_and_saves_only_on_confirm(self, lib: FoodLibrary) -> None:
        from lio.foods.websearch import WebSearch, WebSettings

        def get(url: str, headers: dict[str, str], timeout: float) -> bytes:
            if "bing.com/search" in url:
                return BING_PAGE.encode()
            if "dailymed" in url:
                return DAILYMED_PAGE.encode()
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)  # type: ignore[arg-type]

        lib.web = WebSearch(WebSettings(), get=get)
        it = Intake(lib)
        s = lib.create_sample(bc.normalise(EAN))
        r = it.find_online(s["gtin14"])
        pages = r["web"]["pages"]
        assert r["web"]["engine"] == "Bing" and pages[0]["domain"] == "dailymed.nlm.nih.gov"
        assert pages[0]["sections"][1]["text"].startswith("citric acid")
        assert "refused" in pages[1]["error"]
        assert lib.sample(s["sample_code"])["product"]["info"]["ingredients_text"].startswith(
            "Sugar"
        )  # nothing saved by searching
        refs = [{"url": pages[0]["url"], "title": pages[0]["title"]}]
        p = it.confirm_ingredients(
            s["gtin14"], {"ingredients_text": "citric acid, sucrose", "refs": refs}
        )
        info = p["info"]
        assert (
            info["ingredients_text"] == "citric acid, sucrose"
            and info["ingredients_source"] == "web"
        )
        assert info["ingredients_refs"] == refs and info["ingredients_confirmed_at"]
        with pytest.raises(LibraryError):
            it.confirm_ingredients(s["gtin14"], {"ingredients_text": "  "})

    def test_openfda_label(self) -> None:
        from lio.foods.lookup import parse_openfda

        info = parse_openfda(
            {
                "set_id": "9d5f2244-a610-4d45-b6e8-e79bb17a558f",
                "openfda": {"brand_name": ["CITRUCEL"], "generic_name": ["METHYLCELLULOSE"],
                            "manufacturer_name": ["Foundation Consumer Healthcare"]},
                "active_ingredient": ["Active ingredient Methylcellulose 2 g"],
                "inactive_ingredient": ["Inactive ingredients citric acid, sucrose"],
            }
        )  # fmt: skip
        assert info["name"] == "CITRUCEL (methylcellulose)"
        assert info["ingredients_text"] == (
            "Active ingredient Methylcellulose 2 g | Inactive ingredients citric acid, sucrose"
        )
        assert info["links"]["dailymed"].endswith("setid=9d5f2244-a610-4d45-b6e8-e79bb17a558f")
