# Food library and phone intake app

LIO scans foods whose composition we already know: packaged products, with the
manufacturer's label data. The food library records each item:

- the **identifiers**: a sample code and a UUID;
- the **barcode** and its photo;
- the **manufacturer data**, looked up online from the barcode;
- every **LIO spectral scan** of the item.

## Using it

1. Start the dashboard as usual (`lio dashboard`) and open the **Database** tab.
2. **On the phone (iPhone or Android):**
   1. Scan the QR code on the Database tab with the camera.
   2. Optional: add the page to the home screen. Safari: Share → *Add to Home Screen*. Chrome: ⋮ → *Add to Home screen*. It then opens like an app.
   3. The phone must be on the same Wi-Fi as the Mac.
3. **For each item:**
   1. Tap **Scan barcode** and photograph the barcode.
   2. Check the product details and add notes or the lot number if useful.
   3. Tap **Save**.
   4. **Write the sample code** (`LIO-F-00012`) on the item.
4. **To scan an item:**
   1. Put the item in the chamber.
   2. Open its sample on the Database tab.
   3. Press **Run LIO scan**. Each scan is several sweeps of all 16 holes.

You can also add samples on the dashboard itself, from the barcode digits or a photo.

**VPN and other networks:** the dashboard opens a *secure link*, a Cloudflare quick tunnel (`foods.tunnel: cloudflare`, needs `brew install cloudflared`). The Mac connects out to Cloudflare, and phones reach the app at `https://<words>.trycloudflare.com`. So it works with GlobalProtect connected, on any Wi-Fi, and over cellular. HTTPS also lets the phone show a live camera viewfinder that reads the barcode by itself.

- The link is public, but every request needs the pairing key, and repeated wrong keys are throttled.
- The phone app can only add food samples.
- The link changes each time the dashboard starts: scan the new QR code.
- **Start** and **Stop** for the link are in the Phone app box; `--no-tunnel` starts the dashboard without it.
- Check that your institution allows tunnels like this on a managed laptop.

## What is stored

Everything is stored in `data/foods/` (gitignored):

- the SQLite database `lio_foods.sqlite`;
- the photos, in `files/`;
- `phone_key.txt`, the phone pairing key.

| Table | One row per | Contents |
|---|---|---|
| `products` | barcode (GTIN-14) | normalised label data, the raw API answers, the pack image |
| `samples` | physical item | sample code, UUID, barcode as read, barcode and pack photos, lot, best-before date, notes, who added it, and when |
| `scans` | LIO scan | firmware, config hash, settle time, readings per point, sweeps; the summary per hole (mean net and SD for each detector); every raw dark and lit reading |

Two packs of the same product are two samples of one product.

**Archiving:** archived samples are hidden from the list but never deleted. Photos are never overwritten.

**Exports** (on the Database tab):

- a samples CSV, with nutrition per 100 g;
- a CSV per scan, with every reading;
- the whole library as JSON.

## Where the product data comes from

- **USDA FoodData Central (Branded Foods):**
  - Used first. The data is submitted by the manufacturers, mostly for US products.
  - It needs an api.data.gov key (free at <https://api.data.gov/signup/>). Put it in `data/foods/usda_api_key.txt` (gitignored) or the `LIO_USDA_API_KEY` environment variable, **not** in `lio_hw.yaml`, which is in git. Without it, the rate-limited `DEMO_KEY` is used.
- **Open Food Facts:**
  - Used worldwide; the data is crowd-sourced.
  - It fills the gaps: allergen tags, the pack photo, Nutri-Score and the NOVA group.
- **Both raw answers are kept.**
- **If neither source knows the product:**
  - The sample is still saved.
  - Use **Edit label data** to type in the values from the pack. Edited products are marked "edited by hand".
  - **↻ Look up again** retries the lookup later.

**"Remainder ≈ water + ash"** is calculated from the label: 100 g minus fat, carbohydrate, protein, salt and alcohol. It is an estimate, not a measurement.

## Safety and settings

The phone app runs on its own server, on port 8766 on the local network. It can only add food samples; it has no access to the LEDs, motors or tests. The instrument stays on the dashboard, which is reachable from this Mac only. Every phone request needs the pairing key. **New pairing key** on the Database tab revokes every phone paired before.

The settings are in the `foods:` section of `software/config/lio_hw.yaml`. To turn the phone app off, set `phone_enabled: false` or start the dashboard with `--no-phone`.

To decode barcode photos, install the optional packages:

```
pip install -e software/host[foods]
```

This installs zxing-cpp, Pillow and segno. Without them, type the digits instead.

## Verified composition

Values that can be proven, as exact intervals with VERIFIED / ATTESTED / UNVERIFIED badges, are kept apart from the library's database values. See [COMPOSITION_VERIFICATION.md](COMPOSITION_VERIFICATION.md). To create them for a sample, save a Nutrition Facts photo, tick the rows that match the pack, and sign with your name. The inspector's **Composition** tab shows the result, checked by `lio-verify`.

## Where ingredient lists come from

A scan is looked up in this order. Each source is tried with **every barcode form**: UPC-A, EAN-13, GTIN-14 and, where one exists, UPC-E. One check digit serves all of them, and it is verified first. A hit is confirmed by comparing the source's stored barcode digit for digit. The matching form is logged and kept in the product's `matched_forms`.

1. **USDA FoodData Central.** FDC stores the barcode in the form the brand sent: 12, 13 or 14 digits.
2. **NIH DSLD.** DSLD stores it as printed ("7 02669 93439 8", "5 453003 821090"), so spaced and plain forms are searched. EAN-13 supplements are included.
3. **openFDA drug labels by UPC.**
4. **The NDC in the barcode.** A UPC that starts with 3 can carry a drug's 10-digit NDC. The 4-4-2, 5-3-2 and 5-4-1 readings are all tried: openFDA labels by package NDC, then by product NDC, then DailyMed by NDC. The NDC in a barcode can be out of date, so a match is a lead to confirm. Citrucel Orange's UPC, for example, carries a retired Merrell Dow NDC, `0068-0418-30`.
5. **SmartLabel API.** Used only with a Label Insight key, from `$LIO_SMARTLABEL_KEY` or `data/foods/smartlabel_key.txt`. There is no public access.
6. **Open Food Facts.** The ingredient list in every language present is kept.

Every source's ingredient information is kept as ordered **`ingredient_parts`**, each with the field it came from:

| Product type | Parts kept |
|---|---|
| Drugs | Active and inactive ingredients, and the "Other information" minerals. Each variant an SPL covers is kept apart. |
| Supplements | Dietary ingredients and other ingredients. |
| Open Food Facts | Every `ingredients_text_<language>`. |
| FDC | The ingredient list, flagged `possibly_truncated` when it stops without closing punctuation. |

The summary `ingredients_text` names its origin in `ingredients_text_origin`. When the comp extra is installed, every raw answer and every web page read for ingredients is stored by SHA-256 in `data/foods/composition/sources`.

**Find online**, when the barcode gives no list:
- label databases by name, plus DailyMed SPLs by name (this offers Citrucel's set `9d5f2244`);
- web pages, with the manufacturer's own pages flagged, and each page read kept by hash;
- SmartLabel and GS1 Digital Link pages;
- retailer searches as links you open yourself. Retailer pages are never fetched automatically, under their terms of service.

Nothing found online is saved until you confirm it.

**Ingredients panel photo.** Apple Vision reads the photo in its accurate mode, and the deterministic parser cuts out the list. You correct the text if needed and tick "matches the label word for word" to sign it. The photo's hash, the list's bounding box and your signed confirmation then become ATTESTED ingredients in the sample's verified record ([COMPOSITION_VERIFICATION.md](COMPOSITION_VERIFICATION.md)).

To measure coverage, run `python tools/ingredient_coverage.py --out test_results/coverage/<name> [--compare <earlier>]`. The before and after reports for this change are in [`docs/reports/`](reports/).
