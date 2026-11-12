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

## Sources and their status

| Source | Cost and terms | Used for | In a verified record |
|---|---|---|---|
| DailyMed SPL (NLM) | free, public | OTC drug labels by set ID and package NDC | **Facts**: structured per-product actives and inactives (UNII, strength), and text sections with a `text_variant_attribution` assumption |
| openFDA (drug label, NDC) | free, public; rate-limited | finding an OTC label by UPC, NDC lookups | not used directly; facts come from the DailyMed SPL XML |
| RxNav (NLM) | free; about 20 requests/s | NDC status, properties, history | **Concept-level evidence only**, never proof that a barcode is a product |
| DSLD (NIH ODS) | free; 1,000 requests/h without a key | supplement labels by UPC | **Facts**: label rows (`dsld_quantity@1`) and other ingredients |
| FoodData Central (USDA) | free; API key (kept out of the repository) | branded-food lookups | **Corroboration only**: `labelNutrients` and per-100 g values are partly computed |
| Open Food Facts | free; database ODbL, images CC-BY-SA | lookups and label photos | text is **candidates only**; images may be evidence for ATTESTED facts, with attribution recorded |
| GSRS (FDA) | free, public | UNII to name and formula | identity by UNII only; name searches are fuzzy and never used |
| USP–NF (USP 32–NF 27 via a public mirror) | the current edition is paid; the old edition is read from a mirror | additive assay intervals (`additive_assays@1`) | rule-table source, quoted and re-checked |
| SmartLabel (smartlabel.org) | pages are public, but scraping is not allowed | — | **link only**; the Label Insight API adapter is off unless a key is configured |
| Retailer sites | terms forbid scraping | — | **link only**, for the operator to look at |
| GS1 Data Hub, GDSN pools, Nutritionix, Label Insight | paid | — | not integrated; `lio.foods.paid_sources` has disabled stubs that document the interface |
| Operator photos | — | facts panels, printed NDCs | **ATTESTED** facts and identity links (photo hash, box, signer) |

## Resolving an OTC drug barcode to its label

1. **Read the barcode.** Every form is tried: UPC-A, EAN-13, GTIN-14, and the NDC candidates a UPC-A starting with 3 encodes (10-digit NDCs in all three segment layouts).
2. **Check the crosswalk.** An operator-signed `gtin_ndc_link` in `data/crosswalk/gtin_links.jsonl` names the package NDC directly. A newer SPL version flags the link for re-confirmation.
3. **Look the barcode up.** openFDA by UPC, then DailyMed `spls?ndc=` for each candidate NDC. RxNav `ndcstatus` is recorded, but only as concept-level evidence.
4. **If no current label lists the barcode's NDC**, as for Citrucel (00068041830 is ACTIVE in RxNav, but no DailyMed label lists it) and Care One ibuprofen (41520-314-64 is UNKNOWN):
   - the operator photographs the **printed NDC** on the carton (**NDC photo…**);
   - `printed_ndc@1` reads it, DailyMed finds the SPL with that package code, and the operator signs the proposed link.
5. **The record** holds the link (ATTESTED) and the product selection (VERIFIED: exactly one product has that package code). Every SPL fact must come from that product.

There is no name search anywhere in this path. A name-search match can become a link only as `name_search_confirmed`, when the carton prints no usable NDC.

## Rule changes (LIO-SW-COMP-001 Rev B)

The full list is in [COMPOSITION_VERIFICATION_SPEC.md, Revision B](COMPOSITION_VERIFICATION_SPEC.md#revision-b-12-november-2026-changes-from-lio-sw-comp-002).

- **Bounds** carry exact LP dual and Motzkin certificates, checked with `Fraction`. z3 is gone.
- **Identity links and product selections** are new record sections.
- **FDC values** are corroboration, and **Open Food Facts text** is candidates.
- **Tricalcium phosphate and the dibasic calcium phosphates** use USP assay intervals (`additive_assays@1`), not formulas. Citrucel's calcium phosphates are now [775/4, ≈285.81] mg.
- **New text rules:**
  - `printed_ndc@1`, `drug_active@1`, `sfp_row@1`, `sfp_serving@1`, `dsld_quantity@1`, `fdc_per100g@1`;
  - new versions `list_item@2`, `nfp_row@2`, `nfp_serving@2`.

## Golden records (12 November 2026)

| Record | `lio-verify` | Fields | Waiting on |
|---|---|---|---|
| Citrucel Orange (300680418301) | PASS | 47 VERIFIED | Photo of the tub's printed NDC. Its UPC NDC is in no DailyMed label, so today product 0135-0089 of set 9d5f2244 rests on assumption A1 (name and size on the tub). A signed printed-NDC link replaces A1. |
| Care One ibuprofen (341520314643) | not built | — | The operator signing the printed-NDC proposal (NDC 41520-745-18, from the FDA carton image). |
| Jif Creamy (051500255162) | PASS | 5 VERIFIED, 23 UNVERIFIED | Signing the Open Food Facts nutrition-photo proposal `jif_nutrition_en_209`. |
| Nutella (3017620422003) | PASS | 8 UNVERIFIED | An operator photo of the ingredient panel. The image Open Food Facts selects as "ingredients" shows the front. |
| Nutricost magnesium oxide (702669934398) | PASS | 12 VERIFIED | — |
| Swanson Lowat blend (087614040622) | PASS | 10 VERIFIED | — |

The operator commands are:

```bash
cd software/host
python -m lio_comp.crosswalk list
python -m lio_comp.crosswalk sign 00341520314643 --operator "NAME"   # Care One
python -m lio_comp.attest list
python -m lio_comp.attest sign jif_nutrition_en_209 --operator "NAME"  # Jif
```

After signing, rebuild with `python -m lio_comp.golden …` (see [COMPOSITION_VERIFICATION.md §7](COMPOSITION_VERIFICATION.md)).

## Coverage benchmark

The protocol is [COVERAGE_BENCHMARK_PROTOCOL.md](COVERAGE_BENCHMARK_PROTOCOL.md): random shelf slots in 3–4 store formats, three strata, and Wilson 95% intervals. The tools are `lio bench plan`, `ingest` and `report`.

The 10-item **dry run** ([report](reports/bench_pilot_dryrun_2026-11-12.md)) uses coverage-panel barcodes, not shelf samples, so its numbers are not a coverage estimate. It found:

- every item in some source (10/10);
- an ingredient list for 9 of 10;
- a truncation flag on 3 of 10;
- 2 of 3 OTC items that need the printed NDC;
- a median pipeline time of 3.9 s per item.

The real pilot, about 200 items over 3–4 store visits, is still to be collected.
