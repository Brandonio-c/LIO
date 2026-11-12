> **Dry run, not a coverage measurement.** The 10 barcodes come from the 2026-11-12 coverage panel, not from store shelves, and the photos are an Open Food Facts image (Jif) and the FDA carton image (Care One). OCR was Tesseract because Apple Vision was down on the lab Mac. This report only shows that `lio bench plan`, `ingest` and `report` work end to end (seed 20261112).

# Coverage benchmark pilot (DRY RUN, 10 items, no store visit)

10 items. Proportions with Wilson 95% confidence intervals.

| Measure | all | foods | supplements | otc |
|---|---|---|---|---|
| Any source found the product | 10/10 = 100% (95% CI 72% to 100%) | 4/4 = 100% (95% CI 51% to 100%) | 3/3 = 100% (95% CI 44% to 100%) | 3/3 = 100% (95% CI 44% to 100%) |
| Source hit: crosswalk | 0/10 = 0% (95% CI 0% to 28%) | 0/4 = 0% (95% CI 0% to 49%) | 0/3 = 0% (95% CI 0% to 56%) | 0/3 = 0% (95% CI 0% to 56%) |
| Source hit: usda | 4/10 = 40% (95% CI 17% to 69%) | 4/4 = 100% (95% CI 51% to 100%) | 0/3 = 0% (95% CI 0% to 56%) | 0/3 = 0% (95% CI 0% to 56%) |
| Source hit: dsld | 3/10 = 30% (95% CI 11% to 60%) | 0/4 = 0% (95% CI 0% to 49%) | 3/3 = 100% (95% CI 44% to 100%) | 0/3 = 0% (95% CI 0% to 56%) |
| Source hit: openfda | 2/10 = 20% (95% CI 6% to 51%) | 0/4 = 0% (95% CI 0% to 49%) | 0/3 = 0% (95% CI 0% to 56%) | 2/3 = 67% (95% CI 21% to 94%) |
| Source hit: ndc | 0/10 = 0% (95% CI 0% to 28%) | 0/4 = 0% (95% CI 0% to 49%) | 0/3 = 0% (95% CI 0% to 56%) | 0/3 = 0% (95% CI 0% to 56%) |
| Source hit: smartlabel | 0/10 = 0% (95% CI 0% to 28%) | 0/4 = 0% (95% CI 0% to 49%) | 0/3 = 0% (95% CI 0% to 56%) | 0/3 = 0% (95% CI 0% to 56%) |
| Source hit: openfoodfacts | 4/10 = 40% (95% CI 17% to 69%) | 3/4 = 75% (95% CI 30% to 95%) | 0/3 = 0% (95% CI 0% to 56%) | 1/3 = 33% (95% CI 6% to 79%) |
| Ingredient list from some source | 9/10 = 90% (95% CI 60% to 98%) | 4/4 = 100% (95% CI 51% to 100%) | 3/3 = 100% (95% CI 44% to 100%) | 2/3 = 67% (95% CI 21% to 94%) |
| List complete vs the facts photo | n/a (0 items) | n/a (0 items) | n/a (0 items) | n/a (0 items) |
| Variant correct (operator) | n/a (0 items) | n/a (0 items) | n/a (0 items) | n/a (0 items) |
| Truncation flag raised | 3/10 = 30% (95% CI 11% to 60%) | 3/4 = 75% (95% CI 30% to 95%) | 0/3 = 0% (95% CI 0% to 56%) | 0/3 = 0% (95% CI 0% to 56%) |
| OTC: needs the printed NDC | 2/3 = 67% (95% CI 21% to 94%) | n/a (0 items) | n/a (0 items) | 2/3 = 67% (95% CI 21% to 94%) |

**Badge mix by source class** (fields from SPL/DSLD/crosswalk: VERIFIED-capable; FDC and Open Food Facts: UNVERIFIED; photo fields: ATTESTED once signed):

- all: VERIFIED 10/20 = 50% (95% CI 30% to 70%), ATTESTED 1/20 = 5% (95% CI 1% to 24%), UNVERIFIED 9/20 = 45% (95% CI 26% to 66%) (fields are not independent: intervals are indicative)
- foods: VERIFIED 0/10 = 0% (95% CI 0% to 28%), ATTESTED 1/10 = 10% (95% CI 2% to 40%), UNVERIFIED 9/10 = 90% (95% CI 60% to 98%) (fields are not independent: intervals are indicative)
- supplements: VERIFIED 6/6 = 100% (95% CI 61% to 100%), ATTESTED 0/6 = 0% (95% CI 0% to 39%), UNVERIFIED 0/6 = 0% (95% CI 0% to 39%) (fields are not independent: intervals are indicative)
- otc: VERIFIED 4/4 = 100% (95% CI 51% to 100%), ATTESTED 0/4 = 0% (95% CI 0% to 49%), UNVERIFIED 0/4 = 0% (95% CI 0% to 49%) (fields are not independent: intervals are indicative)

**Operator time** per item: not recorded. Pipeline time: median 3.9 s.
