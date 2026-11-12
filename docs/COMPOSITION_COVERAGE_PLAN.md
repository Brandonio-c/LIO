# LIO — Composition Data Coverage & Verifiability: Software Engineering Plan

**Document:** LIO-SW-COMP-002 Rev A, 12 November 2026
**Repo:** github.com/Brandonio-c/LIO (`main` at `ef45dc9` or later)
**Builds on:** LIO-SW-COMP-001 (verifiable composition records, `docs/COMPOSITION_VERIFICATION_SPEC.md`), and the research report on barcode-to-composition coverage dated 12 November 2026.

---

## 1. Goals

1. **Resolve every scanned product to its correct label source,** including OTC drugs whose UPC carries a retired or stale NDC. Do it without relying on name search alone.
2. **Use only true label values as facts.** Database values that are back-computed (FDC `labelNutrients`) or crowd-sourced (OFF text) become corroboration or candidates, never facts.
3. **Take variant-correct ingredient identity from structured data** (SPL per-product elements, DSLD rows) wherever it exists.
4. **Extend photo attestation** to Drug Facts and Supplement Facts panels, with rule-based parsers and a measured accuracy.
5. **Correct the chemistry rules** for food-grade calcium phosphates.
6. **Make bound certificates solver-independent:** the verifier checks exact LP dual and Farkas certificates using `Fraction` alone. Remove z3 from `lio_verify`.
7. **Measure real coverage** on an unbiased sample of about 200 US retail products, and report it with confidence intervals.

**Non-goals:** paid data licences (GS1, GDSN pools, Nutritionix, Label Insight) are not integrated. Only optional adapter stubs are allowed, disabled by default. Lab-measurement integration is out of scope.

## 2. Invariants (unchanged from COMP-001; restated because every work package must keep them)

- No invented numbers. No floats in the verified layer.
- Every source is snapshotted byte-for-byte and stored by SHA-256.
- Every fact has a locator that string-matches its snapshot, or is ATTESTED (photo hash + bbox + operator signature).
- ML/LLM output may only *propose*. A deterministic rule or a human confirms.
- `lio_verify` never imports `lio_comp` or `lio.foods`, runs with no network unless `--refetch`, and fails closed.
- Respect terms of service: no scraping of retailers or smartlabel.org. Those are links only. Rate limits are honoured (RxNav ≈20 req/s; DSLD 1,000/h without a key).
- The human confirmation step stays.

## 3. Work packages

### WP1 — Attested GTIN → NDC → SPL resolution (highest priority)

**Problem.** UPC-embedded NDCs can be retired (Citrucel: `0068-0418-30`, current Haleon `0135-0089`) or stale (Care One ibuprofen: UPC `41520-314-64`, label `41520-745-xx`). No free, authoritative GTIN → NDC or set-id mapping exists.

**Design.**
1. **NDC status check.** `foods/lookup.py` adds an RxNav client (snapshotted responses):
   - `ndcstatus.json?ndc=<11-digit>&history=1`
   - `ndcproperties.json?id=<ndc>&ndcstatus=ALL`
   - `rxcui/{rxcui}/allhistoricalndcs.json`

   Outcome per embedded NDC: `ACTIVE | OBSOLETE | ALIEN | UNKNOWN`, with history. RxNav establishes **drug-concept** equivalence only. It must never be used as proof of product identity.
2. **Printed-NDC capture.** If the embedded NDC is not ACTIVE, or doesn't appear in the matched SPL, the app prompts: "Photograph the NDC on the carton".
   - `foods/barcode.py` gains an NDC text grammar (`NDC\s*(\d{4}-\d{4}-\d{2}|\d{5}-\d{3}-\d{2}|\d{5}-\d{4}-\d{1})`) with 11-digit normalisation.
   - Apple Vision supplies candidates; the operator confirms the span.
3. **Exact SPL resolution.** The printed NDC goes to DailyMed:
   - `services/v2/spls.json?ndc=…`
   - `services/v2/spls/{setid}/ndcs.json`
   - `services/v2/spls/{setid}/history.json`

   Snapshot all responses and the SPL XML.
4. **Crosswalk store.** `software/host/data/crosswalk/gtin_links.jsonl`. Each row is an attested record:
   - `{gtin, ndc11, setid, spl_version, evidence: {photo_sha256, bbox, ndc_text}, attestation: {operator, timestamp, signature}, method: "printed_ndc"|"name_search_confirmed"}`

   Re-scans resolve from the crosswalk with no prompt. Stale entries (the SPL version changed) are flagged for re-confirmation.
5. **Record model (`lio_comp`).**
   - New fact kind `gtin_ndc_link` (ATTESTED).
   - New derivation `spl_product_select`: picks the unique `manufacturedProduct` whose product/package code equals the linked NDC.
6. **Verifier (`lio_verify`).**
   - Checks attestation integrity and the photo hash.
   - Re-parses the NDC span with its own copy of the grammar.
   - XPath-asserts that the hashed SPL contains that NDC under exactly one `manufacturedProduct`.
   - Downstream facts are VERIFIED relative to an ATTESTED link, and the report shows that chain.

**Acceptance.**
- Citrucel Orange (UPC 300680418301) resolves to set `9d5f2244-…` via the printed NDC with no name search, and passes `lio-verify`.
- Care One ibuprofen resolves to `41520-745-xx`.
- RxNav results for both are recorded. Expected for Citrucel: UNKNOWN or OBSOLETE (to be confirmed; record whatever is returned).

### WP2 — Variant-correct structured ingredients from SPL and DSLD

1. **SPL:** extract ingredient identity **per `manufacturedProduct`** (UNII, name, class active/inactive, strength numerator/denominator if present). These become VERIFIED facts with XPath locators.
   - Text sections ("Other information", "Inactive ingredients") are used **only** for content that doesn't exist in structured form (mineral amounts, calorie statements).
   - Their variant attribution is an explicit assumption or attestation: `text_variant_attribution`.
2. **DSLD:** use `ingredientRows` (order, quantity per serving, unit, forms) and other-ingredient rows as VERIFIED facts (JSON pointer locators). Use `upcSku` for GTIN matching, normalised to every barcode form.
3. **Cross-check:** if both the SPL structured list and the text list exist, the verifier reports any identity mismatch as a data conflict.

**Acceptance.**
- For a multi-variant SPL (Citrucel Orange vs Sugar Free), the record lists only the Orange product's structured ingredients.
- The "Other information" mineral facts carry a `text_variant_attribution` assumption or attestation.

### WP3 — Demote derived and crowd-sourced database values

1. **FDC:**
   - Store `data_source` (GDSN/LI) and, where present, the per-nutrient derivation method.
   - `labelNutrients` and per-100 g nutrients become **`derived_corroboration`**, never facts.
   - Add a consistency check: `per100 × servingSize / 100`, rounded by the 21 CFR 101.9(c) rule, must fall in the label value's interval when a label fact exists. Mismatches are reported, not "fixed".
2. **OFF:**
   - Text fields are candidates only.
   - Download the **selected ingredients and nutrition images** (image id + revision, SHA-256) as evidence, under CC-BY-SA with attribution recorded.
   - Re-transcription by the operator turns them into ATTESTED facts.
3. **Truncation heuristics** on any ingredient string; each flag is surfaced to the operator:
   - ends mid-word, or brackets/parentheses unbalanced;
   - length at a suspicious round number (255/256/1000/1024/2000/4000/4096);
   - shorter than the best photo or OFF transcription.

**Acceptance.** No FDC or OFF number appears as a VERIFIED fact in any golden record. Corroboration checks run and report.

### WP4 — Photo attestation for Drug Facts and Supplement Facts panels

1. **Parsers** (deterministic, `lark` grammars):
   - **Drug Facts** (21 CFR 201.66): sectioning on the mandated headings in order (Active ingredient(s) / Purpose(s) / Use(s) / Warnings / Directions / Other information / Inactive ingredients / Questions?). Extract actives with strengths, the "each X contains" mineral statements, and the inactive list. Mark the list **alphabetical** (no ordering constraint).
   - **Supplement Facts** (21 CFR 101.36): serving size, servings per container, nutrient/dietary-ingredient rows (amount, unit, %DV, footnote markers), proprietary blends (total weight, members without amounts), and the "Other ingredients" statement.
2. **Capture UX:** a panel-type selector (Nutrition / Supplement / Drug / Ingredients / NDC). Apple Vision at the accurate level gives line boxes. The parser proposes; the operator confirms each field. Store bboxes and the attestation.
3. **Test corpus (free, paired):**
   - DailyMed SPL package-label images paired with their SPL text;
   - DSLD label PDFs paired with DSLD rows;
   - OFF images (CC-BY-SA) paired with operator transcriptions.

   Build about 100 Drug Facts, 100 Supplement Facts and 100 Nutrition Facts examples. Record coverage of full panels (some images show only the principal display panel).
4. **Metrics:** field-level exact-match accuracy after parsing, and the share of fields needing operator correction. These are reported, not gating.

**Acceptance.**
- Both parsers pass unit tests on regulation-conforming synthetic panels.
- Corpus accuracy is reported in `docs/COMPOSITION_COVERAGE.md`.

### WP5 — Chemistry rule corrections

1. **Tricalcium phosphate:** replace the formula with a **Ca mass-fraction interval [0.340, 0.400]** (FCC monograph assay; cite the edition used).
   - Confirm the assay basis (as-is vs ignited/dried). If not as-is, widen by the loss-on-ignition limit (≤10%) and cite it.
   - Rule id `fcc_tcp_assay@<edition>`.
2. **Dibasic calcium phosphate** (anhydrous and dihydrate): an assay interval per FCC (97.0–105.0% as CaHPO₄ / CaHPO₄·2H₂O), giving a Ca fraction interval.
3. A generic rule type `element_fraction_interval` for any variable-composition additive. Formula-based fractions remain for well-defined compounds (UNII formula from GSRS, CIAAW masses).
4. Update the Citrucel golden record: if all calcium is from TCP, TCP is [200, 235.3] mg as-is before any LOI widening. The record reports the hull over the candidate salts.

**Acceptance.** The verifier reproduces the new intervals exactly from the cited rules. Old formula-based TCP bounds are removed.

### WP6 — Solver-independent bound certificates

1. **Builder (`lio_comp/bound`):** an **exact simplex over `fractions.Fraction`** (dense, Bland's rule; the problems have tens of variables). For each bound it emits:
   - a primal witness x\*;
   - dual multipliers for every constraint and variable bound;
   - for infeasible systems, a Farkas vector.

   pycddlib is an optional backend behind the same interface. z3 may remain as an optional cross-check in the builder only.
2. **Certificate format** (in the bundle):
   - `{lp: {A, b, senses, bounds, c (all rational strings)}, primal: x*, dual: {y_rows, y_lo, y_hi}, objective: rational}`
   - or `{farkas: y}`.
3. **Verifier (`lio_verify/cert.py`):** pure `Fraction` checks:
   - primal feasibility;
   - dual feasibility (sign conditions; Aᵀy + bound multipliers = c);
   - strong duality (cᵀx\* = bᵀy + bound terms);
   - Farkas: y ≥ 0 where required, yᵀA = 0, yᵀb < 0.
4. Also check that the LP in the certificate is exactly the LP implied by the record's constraints: rebuild it from the facts, derivations and constraints, and compare.
5. **Remove `z3-solver` from `lio_verify` dependencies.**

**Acceptance.**
- All existing bounds are re-certified.
- Mutation tests FAIL for: one perturbed dual entry; a perturbed witness; an LP in the certificate differing from the record's constraints; a bound narrowed by 1/10⁶.
- `lio_verify` has no z3 import (CI check).

### WP7 — Unbiased coverage benchmark

1. **Protocol** (`docs/COVERAGE_BENCHMARK_PROTOCOL.md`):
   - Stratified store-shelf sampling of about 200 items: foods, dietary supplements, OTC drugs (equal thirds by default; configurable).
   - 3–4 store formats in at least 2 locations.
   - Random (aisle, shelf, facing) triples are generated **before** each visit by `lio bench plan` (seeded; the seed is stored). Nearest-right rule if a slot is empty. Substitutions are logged.
   - For each item, photograph the barcode, front panel, facts panel and NDC (if OTC).
2. **Tooling:**
   - `lio bench plan`: produces the per-store sampling sheet.
   - `lio bench ingest`: imports photos and barcodes, runs the full pipeline, records the operator time per item.
   - `lio bench report`: computes the metrics below with **Wilson 95% intervals**, broken down by stratum and source.
3. **Metrics:**
   - source hit rate per source;
   - any-source hit rate;
   - ingredient-list completeness (active + inactive; vs the attested photo transcription);
   - variant correctness;
   - share of VERIFIED / ATTESTED / UNVERIFIED fields;
   - truncation flags;
   - operator time.
4. Optional, documented only: a sales-weighted variant using an academic scanner-data UPC universe (for example NielsenIQ via the Kilts Center), if the university has access.

**Acceptance.** Tooling runs end-to-end on a 10-item pilot. Protocol document written. The full 200-item collection is a separate, human-run activity.

### WP8 — Documentation and housekeeping

- `docs/COMPOSITION_COVERAGE.md`: sources and their status (free, paid, link-only, terms), resolution flow, rule changes, benchmark results.
- Update `docs/COMPOSITION_VERIFICATION_SPEC.md` (new fact kinds, certificate format, rule types) via a reviewed PR.
- CHANGELOG entry; README links.
- Optional paid-source adapters (GS1 Data Hub, Label Insight) as disabled stubs that only document the interface.

## 4. Sequencing and milestones

| # | Milestone | Contents | Done when |
|---|---|---|---|
| M0 | Recon | Read the code and specs; run the RxNav and DailyMed calls for Citrucel and Care One; confirm the TCP assay basis source; check pycddlib/macOS | Report to the user (RxNav results verbatim, plan deviations, questions). **Stop for approval** |
| M1 | WP6 certificates | Exact simplex + certificate format + verifier checks; z3 removed from the verifier | Mutation tests green; all bounds re-certified |
| M2 | WP1 resolution | RxNav client, printed-NDC capture, DailyMed exact resolution, crosswalk, `gtin_ndc_link` | Citrucel and Care One golden records pass |
| M3 | WP2 + WP3 | Per-product SPL ingredients, DSLD rows, FDC/OFF demotion, truncation flags | No derived values in verified layers; corroboration reported |
| M4 | WP5 chemistry | FCC interval rules | Citrucel bounds updated and verified |
| M5 | WP4 photo panels | Drug/Supplement Facts parsers, capture UX, paired corpus, accuracy report | Parsers tested; corpus metrics in docs |
| M6 | WP7 benchmark | plan / ingest / report tooling, protocol, 10-item pilot | Pilot report with Wilson intervals |
| M7 | WP8 docs | Coverage doc, spec update, CHANGELOG | Reviewed and merged |

(M1 comes first because it's self-contained and strengthens every later milestone's verifier output.)

## 5. Testing strategy

- **Unit:** grammars (NDC, Drug Facts, Supplement Facts); barcode/NDC normalisation; rule tables; exact simplex.
- **Property (hypothesis):** simplex optimum = brute-force vertex enumeration on small random LPs; certificate soundness; interval arithmetic.
- **Golden records:**
  - Citrucel Orange
  - Care One ibuprofen
  - one DSLD supplement with a proprietary blend
  - one Nutrition Facts food
  - one EU QUID product
- **Mutation:** every verifier check has at least one tamper test that must FAIL.
- **Offline:** all tests run from snapshots. Network calls happen only in explicit `--live` integration tests.
- **CI:** ruff, mypy (strict for `lio_comp`, `lio_verify`), pytest incl. hypothesis and mutation suites, an import-boundary check (`lio_verify` must not import `lio_comp`/`lio.foods` or z3).

## 6. Risks

| Risk | Mitigation |
|---|---|
| The carton has no printed NDC, or it's illegible | Fall back to name search + confirmation (`method: name_search_confirmed`), flagged in the report |
| RxNav or DailyMed API changes | Snapshots plus version-pinned clients; integration tests behind `--live` |
| The FCC edition text isn't freely available | Cite the 1996 revised monograph (free) plus whatever edition is accessible; record the assay-basis uncertainty as an assumption that widens the interval |
| Exact simplex performance | Problems are small; cap the size and fail loudly if it's exceeded |
| Photo corpus has only principal display panels | Report coverage; supplement with operator-captured panels |
| Licence obligations (OFF CC-BY-SA, FDC attribution) | Attribution fields in records; docs note the obligations |

## 7. Deliverables checklist

- [ ] RxNav and DailyMed results for Citrucel and Care One (M0 report)
- [ ] `lio_comp/bound` exact simplex + certificates; `lio_verify/cert.py`; z3 removed from the verifier
- [ ] NDC grammar, printed-NDC capture, crosswalk store, `gtin_ndc_link`, `spl_product_select`
- [ ] Per-product SPL ingredients; DSLD rows; FDC/OFF demotion; truncation flags
- [ ] FCC interval rules (TCP, DCP); `element_fraction_interval`
- [ ] Drug Facts and Supplement Facts parsers; capture UX; paired corpus + accuracy report
- [ ] Benchmark tooling + protocol + pilot
- [ ] Docs: COMPOSITION_COVERAGE.md, spec update, protocol, CHANGELOG
