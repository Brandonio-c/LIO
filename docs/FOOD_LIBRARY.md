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
