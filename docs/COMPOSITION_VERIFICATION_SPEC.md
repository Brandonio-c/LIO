# LIO — Symbolically Verifiable Composition Records: Specification

**Document:** LIO-SW-COMP-001 Rev B
**Date:** 11 November 2026 (Rev A); 12 November 2026 (Rev B, see the end of this document)
**Scope:** how the LIO project gathers composition data from labels and databases, and stores it so that **every value can be mechanically verified** by an independent checker.

---

## 1. Goal and definition

A composition value is **verified** if and only if an independent checker can confirm, using only stored artefacts and published rules, that it is one of:

1. **Fact:** exactly what a named, hashed source document says at a stated location; or
2. **Derived:** the exact result of a stated expression over verified facts, cited constants and named assumptions; or
3. **Bound:** a minimum or maximum proven by an exact solver from verified facts, derivations, constraints and named assumptions.

Anything else, such as a point estimate, an LLM output or a heuristic, is **unverified**. It lives in a separate layer and is never mixed into the verified store.

**Out of scope for "verified"** (these must be declared as assumptions):
- whether the label is physically true;
- which lot the physical sample came from;
- modelling choices.

## 2. Principles (non-negotiable)

1. **No invented numbers.** Every number in the verified store traces to a fact.
2. **Determinism.** The same inputs give byte-identical outputs, so extraction and derivation must be re-runnable.
3. **Exactness.** No binary floating point in the verified layer. Use `fractions.Fraction` and closed or half-open intervals of `Fraction`.
4. **Rounded values are intervals.** A declared value is converted to the interval implied by the applicable rounding rule.
5. **Everything is cited.** Every constant, rule and assumption has an ID, a citation and a version.
6. **The verifier is separate.** It is a separate module with minimal dependencies and **must not import extractor code**.
7. **LLMs propose, rules decide.** An LLM may suggest candidate spans. Only a deterministic rule can create a fact, and the span must string-match the hashed source.
8. **Fail closed.** If any check fails, the field is UNVERIFIED. It is never "probably fine".

## 3. Architecture

```
sources/      content-addressed snapshots (immutable)
rules/        versioned rule tables: rounding, conversions, constants, salts
records/      one JSON bundle per scanned item
lio_comp/     extractors, deriver, bounder (produce bundles)
lio_verify/   independent verifier (consumes bundles + sources + rules)
```

### 3.1 Evidence store (`sources/`)
- Every fetched document is saved **exactly as received**, at `sources/sha256/<aa>/<hash>`. Examples: DailyMed SPL XML, DSLD JSON, FDC JSON, openFDA JSON, OFF JSON, HTML pages, label photos.
- A manifest entry records:
  - `sha256`, `media_type`, `byte_length`
  - `retrieved_at` (UTC), `retrieval_url`
  - source identifiers: SPL `setid` + `version`, DSLD id, FDC id, GTIN/UPC
  - `retriever_version`
- Files are never modified or deleted. A re-fetch creates a new entry.

### 3.2 Rule tables (`rules/`)
Versioned YAML or JSON. Each entry has `id`, `version`, `citation`, `effective_date` and machine-readable content. Minimum set:

| Rule set | Content | Citation |
|---|---|---|
| `fda_rounding_101_9` | Rounding increments and "0" thresholds per nutrient (calories, fat, sat/trans fat, cholesterol, sodium, potassium, carbohydrate, fibre, sugars, added sugars, protein, vitamins and minerals) | 21 CFR 101.9(c) |
| `fda_tolerance_101_9g` | Class I/II and restricted-nutrient tolerances (optional widening) | 21 CFR 101.9(g) |
| `atwater` | 4 / 4 / 9 kcal/g; label-specific factors where defined | 21 CFR 101.9(c)(1)(i) |
| `atomic_masses` | Standard atomic weights | IUPAC (state the edition) |
| `compounds` | Formula → exact molar mass; element mass fractions | derived from `atomic_masses` |
| `units` | mg, g, kg, µg, IU (per nutrient), kcal, kJ (4.184) | SI / 21 CFR 101.9 |
| `list_ordering` | Food lists in descending weight order (21 CFR 101.4); OTC inactive lists alphabetical (21 CFR 201.66(c)(8)); EU 1169/2011 Art. 18 | regulations |
| `quid` | EU QUID semantics | Reg. 1169/2011 Art. 22, Annex VIII |

**Rounding encoding:** `{nutrient, range_of_true_value, display_rule}`. The inverse map (declared value → true interval) is what derivations use. Write it in code and unit-test it against FDA's own examples.

### 3.3 Record bundle (`records/<record_id>.json`)
JSON, validated by a JSON Schema (`schema/record.schema.json`). Top-level fields:

```
record_id, gtin, product_name, variant_note,
physical_sample: {lot, photos[], attestation}        # attested, not verified
sources[]: {source_id, sha256}
assumptions[]: {id, text, kind, rule_ref?}
facts[], derivations[], constraints[], bounds[],
unverified_layer: {estimates[], notes[]},
toolchain: {extractor_version, deriver_version, rules_versions{}}
```

#### Fact
```
{ "id": "F1",
  "quantity": "methylcellulose", "substance": {"unii": "...", "name_verbatim": "Methylcellulose"},
  "value_raw": "2 g", "basis": "per_serving",            # per_serving | per_unit | per_100g | per_100ml
  "source_id": "S1",
  "locator": { "type": "xpath", "expr": "...", "text": "2" }   # or json_pointer | char_span | image_bbox
  "rule": "spl_active_strength@1",
  "interpretation": { "kind": "exact" }                  # or {"kind":"rounded","rule":"fda_rounding_101_9@1:calories"}
                                                         # or {"kind":"as_stated","assumption":"A2"}
  "value": { "lo": "2", "hi": "2", "lo_closed": true, "hi_closed": true, "unit": "g" } }
```

Locator types:
- `xpath`: XML; must resolve to exactly one node whose text matches `text`.
- `json_pointer`: JSON; the value must equal `text`.
- `char_span`: `{start, end, text}` on the decoded text of the source (encoding declared). `source[start:end] == text`.
- `image_bbox`: `{x, y, w, h, text, attestation_id}`. The text is a **human-attested transcription**. It's verified only as "attested by X at T". The fact is tagged `evidence_class: "attested"`.

#### Derivation
```
{ "id": "D1", "quantity": "sucrose+maltodextrin", "basis": "per_serving",
  "expr": ["div", "F2", "C:atwater.carbohydrate"],      # s-expression over fact/derivation IDs and constants
  "assumptions": ["A3"],
  "value": { "lo": "55/4", "hi": "65/4", "lo_closed": true, "hi_closed": false, "unit": "g" } }
```
Allowed operators: `add, sub, mul, div, neg, min, max, sum, interval_union`, unit conversion, and `rescale_basis` (needs a serving-mass fact). Arithmetic is **interval arithmetic over Fraction**, with correct endpoint openness. Division by an interval containing 0 is an error.

#### Constraint
```
{ "id": "C1", "kind": "le", "lhs": ["add","F1","D1"], "rhs": "F4", "assumptions": [] }
```
Kinds: `le, ge, eq_within, sum_eq` (mass balance), `ordered_desc` (only if `list_ordering` says the list is weight-ordered).

#### Bound
```
{ "id": "B3", "quantity": "sucrose", "basis": "per_serving",
  "solver": "z3@<version>", "variables": [...], "constraints": ["C1","C2",...],
  "assumptions": [...], "result": { "lo": "...", "hi": "...", ... },
  "certificate": { "min_witness": {...}, "max_witness": {...}, "infeasibility_proofs": "..." } }
```
- The bounder computes the min and max of a quantity subject to the constraints, using **exact rational** optimisation (z3 `Optimize` over reals, or an exact LP).
- **Certificate:** a witness assignment achieving each bound, plus proof that nothing beyond it is feasible: z3 `unsat` on "value < lo" and on "value > hi". The verifier re-checks the witnesses by exact substitution and re-runs the unsat checks.

#### Assumption
```
{ "id": "A2", "kind": "interpretation", "text": "OTC 'Other information' mineral amounts are treated as exact as stated (no defined rounding rule)." }
```
Kinds: `interpretation, modelling, rounding, sample_identity, label_truth`. Every assumption is listed in the verifier's report.

#### Unverified layer
Point estimates (OFF `percent_estimate`, Recipe Estimator, LLM suggestions), with method and inputs. **Never read by the verifier as data**, and never shown as verified.

## 4. Extractors (`lio_comp/extract/`)

Each extractor is a pure function `(source_bytes, rule_version) → facts[]` and is versioned.

| Extractor | Source | Facts |
|---|---|---|
| `spl` | DailyMed SPL XML | Product, NDC/packaging, active ingredients (UNII, strength numerator/denominator), inactive ingredients (UNII; strength **only if present in XML**), text sections ("Other information") via `char_span` and grammar |
| `dsld` | DSLD JSON | Dietary ingredients with amount and unit per serving, serving size, other ingredients (identity) |
| `fdc` | FDC Branded JSON | Nutrients per 100 g as provided (interpretation: FDC is a **derived** source, see §7), serving size, ingredient text |
| `openfda` | openFDA label JSON | Active ingredient strings, inactive ingredient text |
| `off` | OFF JSON | Ingredient text and nutrition **as facts about the OFF record**. OFF estimates go to the unverified layer |
| `nfp_photo` | Label photo | Attested transcription of the Nutrition/Supplement/Drug Facts panel, with bounding boxes |

The text grammar (for example `"each heaping tablespoon contains: calcium 80 mg, potassium 105 mg"`) is a formal parser (e.g. `lark`) with tests. It emits `char_span` locators.

**Ingredient identity:** names map to UNII via the GSRS API or a cached GSRS dump. Store `name_verbatim`, the `unii` and the lookup evidence (a hashed GSRS response) as its own fact. If no exact match, the substance stays unresolved; no fuzzy match goes into the verified layer.

## 5. Deriver and bounder (`lio_comp/derive/`, `lio_comp/bound/`)
- **Standard derivations:**
  - per-serving → per-100 g, using a **serving-mass fact** (label-declared, or measured by an attested weighing);
  - energy → carbohydrate mass;
  - element → salt mass over a candidate salt set (the result is the hull over candidates, with the salt set as an assumption);
  - carbohydrate by difference;
  - sums.
- **Standard constraints:**
  - mass balance (components ≤ serving mass);
  - energy consistency with declared macronutrients (interval check);
  - order (food lists only);
  - optional tolerance widening (opt-in assumption `label_truth`).
- **Bounds:** for each ingredient amount without a fact. If unconstrained, the bound is [0, residual].

## 6. Verifier (`lio_verify/`)

**Command:** `lio-verify records/<id>.json --sources sources/ --rules rules/ [--refetch]`

**Checks, in order:**
1. Schema validation.
2. Every cited source exists, its SHA-256 matches, and its manifest is consistent. With `--refetch`, re-download and report whether the upstream copy changed. That is informational only: verification is against the snapshot.
3. Every fact: the locator resolves uniquely, the text matches exactly, the declared rule re-parses to the same raw value and unit, and the interpretation applied with the cited rule version gives the same interval.
4. Every derivation: re-evaluated exactly, and the intervals and units are identical.
5. Every constraint: satisfied (or reported as violated, which flags a data conflict).
6. Every bound: witnesses verified by substitution, and unsat proofs re-run.
7. Every attestation: present, with signer and timestamp. Signature-checked if keys are configured.
8. Report: per field VERIFIED / ATTESTED / UNVERIFIED / FAILED, plus the full list of assumptions and rule versions. Exit code ≠ 0 on any FAILED.

**Dependencies:** standard library, `lxml`, `jsonschema`, `z3-solver`. **No network** unless `--refetch`. **No import of `lio_comp`.**

## 7. Known source caveats (encode as assumptions)
- **FDC Branded** per-100 g values are computed by USDA from label per-serving values. Treat them as derived. Prefer the label or SPL as the primary fact, and record FDC as corroborating.
- **OTC Drug Facts** inactive ingredient lists are alphabetical (21 CFR 201.66(c)(8)), so no `ordered_desc` constraint applies.
- **Supplement "other ingredients"** usually have no amounts.
- **Variants:** one SPL can cover several products (for example Citrucel Orange and Sugar Free). The fact must cite the span belonging to the correct variant, and `variant_note` must explain how it was chosen.

## 8. Tests and acceptance

1. **Golden records:** Citrucel Orange powder (UPC 300680418301), one food with a full Nutrition Facts panel, one supplement from DSLD, one EU product with QUID. The Citrucel record must reproduce:
   - methylcellulose 2 g;
   - energy [55, 65) kcal → sucrose + maltodextrin [55/4, 65/4) g;
   - calcium phosphates [80·136.06/40.08, 80·310.18/(3·40.08)] mg, with exact molar masses from the rule table;
   - consistency constraint with the declared carbohydrate interval.
2. **Property tests (hypothesis):** interval arithmetic soundness; rounding inverse ∘ forward contains the original value.
3. **Mutation tests:** the verifier must FAIL each of:
   - a changed source byte;
   - a shifted span;
   - an altered fact value;
   - an altered derivation result;
   - a removed assumption;
   - a tampered bound witness;
   - a bound narrower than proven.
4. **Determinism test:** running the pipeline twice gives byte-identical bundles (sorted keys, canonical JSON).
5. **No floats** in the verified layer: a schema and lint check rejects JSON numbers in value fields (values are strings of rationals).

## 9. Integration with the existing barcode workflow
- Barcode lookup, the human confirmation screen and source links stay. Every source shown is snapshotted. Confirmation creates attestations (who, when, what was confirmed).
- The UI shows each value with its badge: VERIFIED (fact / derived / bound), ATTESTED (photo), UNVERIFIED (estimate). Point estimates are visually separate.
- Exports for model training carry the interval, the badge and the assumption IDs per value.

## 10. Milestones

| # | Deliverable |
|---|---|
| M0 | Recon of the existing barcode and composition code. Confirm module locations. Questions to the user |
| M1 | Schema, rule tables (rounding, Atwater, atomic masses, units, list ordering), Fraction-interval library with property tests |
| M2 | Evidence store and SPL + DSLD + FDC extractors with locators. Citrucel golden record facts |
| M3 | Deriver + bounder (z3) with certificates |
| M4 | Independent verifier, mutation tests, determinism test |
| M5 | Photo attestation flow, UI badges, training export, docs (`docs/COMPOSITION_VERIFICATION.md`) |

---

## Revision B (12 November 2026): changes from LIO-SW-COMP-002

Rev A above is unchanged. This section amends it; where they differ, Rev B applies.

### B1. Bound certificates are checked without a solver (amends §3.3 Bound, §6 check 6)

- **The verifier has no solver.** `lio_verify` does not depend on z3, and a test runs it with z3 blocked from import. Bounds are computed by an exact `Fraction` simplex (two-phase, Bland's rule) in `lio_comp`.
- **The certificate format:**

```json
"certificate": {
  "lp": {"variables": [...], "rows": [{"a": [...], "sense": "<=" | "<", "rhs": "...", "origin": "C1"}],
         "objective": {"c": [...], "const": "..."}},
  "min": {"value": "...", "bound": "...", "attained": true,  "dual": [...], "witness": {...}},
  "max": {"value": "...", "bound": "...", "attained": false, "dual": [...], "witness": {...},
          "interior": {...}, "motzkin": [...]}
}
```

- **What the verifier checks, with `d = c` for the minimum and `d = −c` for the maximum:**
  1. The LP is exactly the LP rebuilt from the record's constraints.
  2. `dual ≥ 0` and `Σ dual_i a_i = −d`, so `B = −Σ dual_i rhs_i` bounds `d·x`.
  3. If the end is attained, the witness satisfies every row and `d·witness = B`.
  4. If it is not attained:
     - the witness satisfies the closed rows at `B`;
     - the interior point satisfies every row strictly;
     - the Motzkin vector is `≥ 0`, has `Σ z_i a_i + z_obj d = 0`, a positive weight on strict rows, and `Σ z_i rhs_i + z_obj B ≤ 0`.
- **Joint feasibility.** A record with constraints on unknowns carries `feasibility.witness`, a strictly feasible point.

### B2. Identity links (new, amends §3.3)

- **`links[]`, `gtin_ndc_link`.** ATTESTED: the barcode carries this NDC. With `method: "printed_ndc"` it holds the photo source, an `image_bbox` locator and the span (e.g. "NDC 41520-745-18"). The verifier re-parses the span with `printed_ndc@1`, which must give `ndc11`. `method: "name_search_confirmed"` is the fallback when the carton prints no usable NDC.
- **`selections[]`, `spl_product_select`.** VERIFIED relative to its link: an XPath must find exactly one `manufacturedProduct` whose package code is the linked NDC. Every fact read from that SPL must use the selected product. The report shows the chain (`via L1 -> SEL1`).
- **RxNav (ndcstatus, ndcproperties, allhistoricalndcs)** is recorded as concept-level evidence only. It is never proof of which product a barcode is.
- **The crosswalk.** `software/host/data/crosswalk/gtin_links.jsonl` is append-only, and a newer SPL version flags a link for re-confirmation.

### B3. Derived and crowd-sourced database values (amends §4 and §7)

- **FDC `labelNutrients` and per-100 g values** are `corroboration[]` (`kind: derived_corroboration`, with `data_source` and FDC's per-nutrient `derivation`), never facts. The verifier compares each with the label fact under the 21 CFR 101.9(c) rounding rules (`per100 × serving ÷ 100`) and reports *consistent* or *mismatch*.
- **Open Food Facts text** is `candidates[]`, never a fact or an ingredient identity. Open Food Facts **images** may be evidence for ATTESTED facts (CC-BY-SA; attribution recorded).
- **The verifier FAILS** any fact or ingredient identity read from the FDC or Open Food Facts APIs.
- **Truncation flags** are applied to free-text ingredient strings and shown to the operator:
  - it ends mid-word, or its brackets are unbalanced;
  - its length is a suspicious round number;
  - it is shorter than another transcription in the same language.

### B4. Variant-correct identity (amends §4)

- **Ingredient identity** comes from SPL per-product elements (UNII, class, strength) and DSLD rows.
- **SPL text sections** are used only for content with no structured form. Facts from them carry a `text_variant_attribution` assumption.
- **When an SPL record holds both the structured and the text inactive list**, the verifier reports names that do not match as `conflicts` (informational).

### B5. Variable-composition additives (amends §3.2)

- **The rule table `additive_assays@1`** has two entry types:
  - `element_fraction_interval`: e.g. tricalcium phosphate, Ca ∈ [0.340, 0.400] as-is;
  - `assay_times_formula`: e.g. anhydrous dibasic calcium phosphate, 98.0–103.0% × the CIAAW Ca fraction of CaHPO₄.
- **Expression reference:** `A:additive_assays.<entry>`.
- **Sources.** Each entry quotes its monograph (USP 32–NF 27; the Food Chemicals Codex is not freely available). The verifier re-parses the quote (`usp_assay_percent@1`) and fails if the table disagrees.

### B6. Photo panels (amends §4 nfp_photo)

- **Drug Facts** (21 CFR 201.66) and **Supplement Facts** (21 CFR 101.36) panels are parsed into proposed fields with boxes. The operator ticks and corrects them; each ticked field must re-parse with its rule (`drug_active@1`, `otc_contains@1`, `sfp_row@1`, `sfp_serving@1`, `list_item@2`).
- **Drug Facts inactive lists** are alphabetical, so no weight-order constraint is applied to them.
- **A printed NDC is a panel kind** of its own (`printed_ndc@1`).

### B7. New and versioned text rules

- **New rules:**
  - `printed_ndc@1`;
  - `nfp_row@2` and `nfp_serving@2` (label abbreviations);
  - `list_item@2` (a "." inside a list does not end it);
  - `dsld_quantity@1` (refuses IU and "not present");
  - `fdc_per100g@1` (corroboration only);
  - `drug_active@1`, `sfp_row@1` (lark grammar) and `sfp_serving@1`.
- **Unchanged:** existing rule versions keep their meaning.
