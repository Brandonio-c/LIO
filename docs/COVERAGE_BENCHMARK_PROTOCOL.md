# Coverage benchmark protocol

How to measure, without bias, how well LIO's barcode-to-composition pipeline covers real retail products. This is plan WP7 of [COMPOSITION_COVERAGE_PLAN.md](COMPOSITION_COVERAGE_PLAN.md). Collecting the full sample of about 200 products is a human activity; the tools below plan it, process it and report it.

## Why shelf sampling

Barcodes taken from a database are biased toward that database: a product found by searching FDC is, by construction, in FDC. Coverage can only be measured on products chosen independently of every source. Randomly chosen shelf positions in real stores are a practical way to do that.

## Design

| Setting | Default | Notes |
|---|---|---|
| Size | about 200 items | Any size works; ±7 percentage points at 95% for a proportion near 50% needs about 200 per estimate. |
| Strata | foods, dietary supplements, OTC drugs, in equal thirds | Use `--n` and the stratum aisle ranges; shares can be changed in code (`bench.plan(..., shares)`). |
| Stores | 3–4 formats (grocery, pharmacy, club or discount, natural foods), at least 2 locations | One sheet per visit. |
| Slots | random (aisle, shelf, facing) per stratum, drawn **before** the visit | `lio bench plan` (seeded; the seed and parameters are written to `<sheet>.plan.json`). |
| Empty slot | the nearest product to the right | Write the substitution in the `substituted` column. |

## Steps

1. **Before the visit**, map the store's aisles for each stratum (foods, supplements, OTC), its shelf count and the facings per shelf, then plan:

   ```bash
   lio bench plan --store "Kroger, Bethesda MD" --format grocery --n 40 --seed 20261201 \
       --aisles-foods 1-18 --aisles-supplements 19-20 --aisles-otc 21-22 \
       --shelves 1-6 --facings 1-30 --out bench/kroger_bethesda.csv
   ```

   Use a new seed for every visit and keep the `.plan.json` file.
2. **In the store**, go to each slot in the sheet's order and take the product (nearest-right rule). For each product:
   - photograph the barcode, the front, and the facts panel (Nutrition, Supplement or Drug Facts);
   - for OTC drugs, also photograph the printed NDC ("NDC 12345-678-90"), if the carton shows one.

   Put the photo file names in the sheet. Also fill in:
   - `barcode` (typed, or left blank to decode it from the photo);
   - `seconds` (your handling time for the item);
   - `notes`.
3. **After the visit**, ingest, then report over one or more visits:

   ```bash
   lio bench ingest --sheet bench/kroger_bethesda.csv --photos bench/photos --out bench/kroger.jsonl
   lio bench report --ingest bench/*.jsonl --title "Coverage benchmark, December 2026" --out bench/report.md
   ```

   Ingest runs the full pipeline: every source, every barcode form, the drug label path, and the facts photo. Then compare each product's resolved label with the item in hand and set `variant_correct` (yes or no) in the sheet. Re-run ingest and report.
4. **For the verified records**, attest the photographed panels in the dashboard as usual. These are separate from the benchmark numbers.

## Metrics (all with Wilson 95% intervals, by stratum)

| Metric | Definition |
|---|---|
| Source hit rate | Share of items each source matched (crosswalk, FDC, DSLD, openFDA by UPC, NDC path, SmartLabel, Open Food Facts). |
| Any-source hit rate | Share of items at least one source matched. |
| Ingredient list | Share of items with an ingredient list from some source. |
| Completeness | Share of items whose database list names every ingredient read from the facts photo (active and inactive for drugs). |
| Variant correctness | Share of items whose resolved label is the operator-confirmed variant. |
| Badge mix | Share of fields by source class: SPL, DSLD and crosswalk fields are VERIFIED-capable; FDC and Open Food Facts are UNVERIFIED; photo fields are ATTESTED once signed. Fields are not independent, so these intervals are indicative. |
| Truncation flags | Share of items with a flagged free-text list. |
| NDC needed | Share of OTC items whose barcode NDC is in no current label. |
| Operator time | Median seconds per item, and pipeline time. |

## Optional: sales weighting

A shelf sample weights every facing equally. A sales-weighted estimate would need a universe of UPCs with sales, for example NielsenIQ scanner data through the Kilts Center (University of Chicago), if the university has access. That is documented here only; it is not implemented.

## Pilot

A 10-item **dry run** checks the tooling end to end. It is in [`docs/reports/bench_pilot_dryrun_2026-11-12.md`](reports/bench_pilot_dryrun_2026-11-12.md). Its barcodes come from the coverage panel, not from a store shelf, and its photos are FDA and Open Food Facts images, so its numbers say nothing about coverage. The real pilot is the first store visit.
