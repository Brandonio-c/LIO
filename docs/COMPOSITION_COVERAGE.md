# Composition coverage

What LIO's composition pipeline can find, verify and read for a retail product, and how accurate the photo-panel parsers are. This is the coverage document called for by [COMPOSITION_COVERAGE_PLAN.md](COMPOSITION_COVERAGE_PLAN.md) (LIO-SW-COMP-002). The recon findings it builds on are in [COMPOSITION_COVERAGE_M0.md](COMPOSITION_COVERAGE_M0.md).

## Photo-panel parsers (WP4)

`lio.foods.panels` turns the OCR lines of a facts-panel photo into proposed fields, each with an image box:

- **Drug Facts** (21 CFR 201.66): active ingredients with strengths, "each … contains" minerals, and the alphabetical inactive list.
- **Supplement Facts** (21 CFR 101.36): serving size, amount rows, blend members, and "Other ingredients".
- **Nutrition Facts**: the existing `nfp_row@2` / `nfp_serving@2` parser.

The parsers only propose fields. In the dashboard or on the phone, the operator ticks each field that matches the label and may correct its text. Every ticked field must re-parse with its versioned rule before it is recorded as an ATTESTED fact, with the photo hash, the box and the operator's name. Fields nobody ticks are never recorded.

### Paired test corpus

`tools/panel_corpus.py` builds a corpus of label images, each paired with structured truth from an independent source:

| Panel | Images | Truth | Notes |
|---|---|---|---|
| Drug Facts | DailyMed package-label images of 100 OTC SPLs (openFDA, seeded random offsets) | the SPL's structured active strengths and its text sections | Carton images often show only the front or a partial panel. |
| Supplement Facts | page 1 of the label PDF of 100 DSLD labels (seeded random IDs) | DSLD rows and "other ingredients" | Many PDFs are multi-panel layouts at low resolution. |
| Nutrition Facts | Open Food Facts nutrition photos of 50 US products in FDC | FDC `labelNutrients` | **Approximate**: FDC label values are partly computed (WP3), so a mismatch may be the reference's fault. |

The seed is 20261112. Images are cached outside the repository (OFF images are CC-BY-SA, and the attribution is recorded per item). Only the summaries are committed, in [`docs/reports/`](reports/).

**OCR engine.** Every number below is from **Tesseract 5**. Apple Vision, the intended engine, failed on this Mac throughout the run: `ANECompilerService` hung, and Vision returned an e5rt error or timed out. The pipeline falls back to Tesseract automatically, and records the engine in every attestation. Vision reads small label type much better than Tesseract, so these numbers are a **lower bound**. Re-run the corpus with Vision once it works (`LIO_OCR_ENGINE` unset).

### Metrics

- **Full panel**: the share of images that show a complete facts panel. The parsers cannot read a panel the image does not show.
- **Recall**: of all truth fields, the share the parser proposed correctly.
- **Precision**: of the fields the parser proposed, the share that were correct. The rest, the "needs correction" share, are what the operator fixes or leaves unticked.

Fields are not independent (one bad image loses all its fields), so field-level shares are given without intervals. Item-level shares carry Wilson 95% intervals.

### Results (Tesseract, 12 November 2026)

| Panel | Items | Full panel | Truth fields | Proposed | Correct | Recall | Precision |
|---|---|---|---|---|---|---|---|
| Drug Facts | 100 | 17% (11–26%) | 1026 | 332 | 125 | 12% | 38% |
| Supplement Facts | 100 | 5% (2–11%) | 937 | 219 | 165 | 18% | 75% |
| Nutrition Facts | 50 | 20% (11–33%) | 453 | 112 | 82 | 18% | 73% |

**Drug Facts**

- On the 17 images that show a full panel:
  - 238 truth fields;
  - 140 proposed, 64 correct (recall 27%, precision 46%).
- **By field type:**
  - actives: 7 of 171 correct, 10 proposed;
  - inactive-list items: 116 of 848 correct, 320 proposed;
  - "contains" minerals: 2 of 7 correct.
- **Image orientation.** 82% (73–88%) of images were upright. The rest were found at 90° (4) or 270° (14) by the rotation search.

**Supplement Facts**

- 61% (51–70%) of label PDFs gave at least one proposed field. On those 61 items, 165 of 561 truth fields were correct.
- **By field type:**
  - amount rows: 121 of 407 correct, 146 proposed;
  - other ingredients: 44 of 530 correct, 73 proposed.
- **Precision is high** because a row must parse as `sfp_row@1` (name, amount and unit) to be proposed.

**Nutrition Facts**

- **Reference values may be wrong.** The reference is FDC `labelNutrients`, which are partly computed, so some "errors" are FDC's.
- **Items with proposals.** 30 of 50 photos gave at least one proposed row.
- **Full panels.** On the 10 photos that show a full panel:
  - 98 reference fields;
  - 62 proposed, 46 correct (recall 47%, precision 74%).
- **By nutrient** (correct of proposed):
  - trans fat 12/12, total sugars 11/13, protein 10/13, total carbohydrate 7/9, total fat 9/12;
  - saturated fat 11/15, calories 9/15, sodium 6/11, dietary fibre 5/9, cholesterol 2/3.

### What this means for the operator

- **Expect to correct or untick fields.** With Tesseract, the checklist proposes about 1 field in 3 (Drug Facts) or 1 in 4 (Supplement and Nutrition Facts), and some of those are wrong.
- **The guarantee holds anyway.** Nothing reaches the verified layer without the operator's tick and a rule re-parse, so parser errors cost operator time, not correctness.
- **Photograph the panel itself, flat and in focus.** Most misses in the corpus are images that do not show the full panel. An operator-taken photo of the panel avoids that.
