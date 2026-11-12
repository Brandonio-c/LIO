# Verifiable composition records

How LIO stores what is in each scanned product so that an independent program can prove every number. The specification is [`COMPOSITION_VERIFICATION_SPEC.md`](COMPOSITION_VERIFICATION_SPEC.md) (LIO-SW-COMP-001 Rev A); this document describes what is built, how to run it, and where it departs from the specification.

## 1. What the badges mean

Every value in a record gets one status from `lio-verify`:

| Status | Meaning |
|---|---|
| **VERIFIED** | Proven from stored documents and published rules only: the exact text at a stated place in a hashed document, an exact calculation from such values, or a bound proven by a solver. |
| **ATTESTED** | Every check passed, but the value rests on a person's statement: a transcription of a label photo that the operator confirmed and signed. |
| **UNVERIFIED** | Not proven: a point estimate (database value, OCR, model), or a value whose input failed. Never use it as a training label. |
| **FAILED** | One of its own checks failed. The record fails as a whole. |

A rounded label value is never a single number. "Calories 60" means the true value is in [55, 65) kcal, because 21 CFR 101.9(c)(1) rounds to the nearest 10 above 50. Every value is an interval of exact fractions, with each end open or closed.

## 2. Where things are

| Path | What |
|---|---|
| `composition/sources/` | Evidence store for the golden records: `sha256/<aa>/<hash>` holds the bytes as received (read-only); `manifest/<hash>.json` holds the media type and every retrieval (URL, UTC time, identifiers); `catalog.json` maps names to hashes. |
| `composition/rules/` | Versioned rule tables. Each rule cites a quote located by character span in a stored copy of the regulation. |
| `composition/schema/record.schema.json` | JSON Schema for records. |
| `composition/records/` | Golden records: Citrucel Orange (DailyMed SPL), Jif Creamy (USDA FDC), Nutricost Magnesium Oxide (NIH DSLD), Nutella France (Open Food Facts, EU QUID). |
| `data/foods/composition/` | The same layout for food-library samples (gitignored), plus `evidence/<sample>.json`, the log of attested label photos each sample record is rebuilt from. |
| `software/host/src/lio_verify/` | The verifier and its exact kernel: intervals, rounding rules, locators, text rules, expressions, linear constraints. Imports nothing from `lio` or `lio_comp`. |
| `software/host/src/lio_comp/` | Builds records: fetcher, evidence store, rule builder, extractors, deriver, bounder, golden records, sample records, export. |

Install with `pip install -e "software/host[comp]"`; `hypothesis` is in the `dev` extra.

## 3. Record format

A record is one canonical JSON file (sorted keys, one-space indent). Numbers that are values are **rational strings** (`"55/4"`), never JSON numbers; the schema and the verifier reject floats. The parts:

- **`sources`**: `{source_id, sha256, media_type, identifiers}`; the bytes are in the store.
- **`assumptions`**: `{id, kind, text, rule_ref?}`, with `kind` one of interpretation, modelling, rounding, sample_identity, label_truth. Every assumption must be cited by something, and everything cited must be stated.
- **`substances`** and **`ingredients`**: identities. A UNII is taken from the source document (the SPL carries one per ingredient) or from a stored GSRS response; formulas come from GSRS. Each identity has a locator.
- **`facts`**: one value read from one source.
  - `locator` says where it is:
    - `xpath`: exactly one node, optionally `fields` = attributes joined by a space;
    - `json_pointer`: numbers compared as their literal token;
    - `char_span`;
    - `image_bbox`: a pixel box on a photo, with the operator's transcription and the attestation that signs it.
  - `rule` (e.g. `otc_contains@1:calcium`) turns the located text into `value_raw` ("80 mg").
  - `interpretation` turns that into the interval:
    - `exact`;
    - `rounded` with a rule-table reference such as `fda_otc_rounding_201@1:calcium` → [77.5, 82.5] mg;
    - `as_stated` with an assumption.
- **`derivations`**: `expr` is an s-expression.
  - Operators: add, sub, mul, div, neg, min, max, sum, hull, convert, rescale_basis.
  - References:
    - fact or derivation ids;
    - `C:<table>.<path>`: cited constants;
    - `M:<element>:<substance>`: element mass fraction from the verified formula and the CIAAW atomic weights, themselves intervals;
    - `N:<rational>[:<unit>]`: literals.
  - Units are checked.
- **`variables`**: unknown ingredient amounts (`V:<name>`).
- **`constraints`**: `eq_within`, `le`, `ge`, `sum_eq`, `ordered_desc`, `positive`. Weight order needs a `list_rule` naming a weight-ordered list; OTC inactive-ingredient lists are alphabetical (21 CFR 201.66(c)(8)) and the verifier refuses weight order on them. A constraint without unknowns is a data check: `entailed`, `consistent` or `violated`.
- **`bounds`**: the minimum and maximum of a linear objective subject to every constraint on unknowns. The certificate gives, for each end:
  - its value;
  - whether it is attained;
  - a witness assignment, or for an open end a witness within the stated `gap`.
- **`attestations`**: `{id, signer, signed_at, statement, subjects}`.
- **`unverified_layer`**: point estimates with their method. The verifier never reads them as data.
- **`toolchain`**: extractor, deriver and bounder versions, and the pinned version of every rule table.

## 4. Running `lio-verify`

```bash
lio-verify composition/records/*.json --sources composition/sources --rules composition/rules
lio-verify data/foods/composition/records/sample_LIO-F-00001.json \
    --sources data/foods/composition/sources --rules composition/rules --json report.json
```

The checks run in this order; any failure makes the field FAILED (fail closed):

1. **Schema and number format.** The schema validates, and there are no JSON floats.
2. **Sources.** Each source's bytes match its SHA-256 and its manifest. `--refetch` downloads again and only reports whether the upstream copy changed; verification is always against the stored copy.
3. **Facts.** For each fact:
   - its locator resolves to exactly one place;
   - the text there equals the stated text;
   - the rule reproduces `value_raw`;
   - the interpretation, with the pinned rule version, reproduces the interval.
4. **Substances and ingredients.** Names, UNIIs and formulas match their sources.
5. **Derivations.** Each is re-evaluated exactly, and the interval and unit must be identical.
6. **Constraints.** Data checks are recomputed; a `violated` one is a data conflict. The constraints on unknowns must be jointly satisfiable: the record's feasibility witness must satisfy all of them strictly, checked with plain fractions.
7. **Bounds.**
   - The certificate's LP must equal the LP rebuilt from the record's constraints.
   - Each end carries an exact LP dual certificate: multipliers y ≥ 0 that combine the constraints into "value ≥ lo" (or ≤ hi). This proves nothing lies beyond the end, with plain fractions and no solver.
   - A closed end's witness satisfies every constraint and reaches it. An open end carries a closure witness, a strictly feasible interior point and a Motzkin (Farkas) vector showing the end itself is infeasible.
   - A bound must carry the assumptions of the constraints it uses.
   - The format is in [the specification, Rev B §B1](COMPOSITION_VERIFICATION_SPEC.md#b1-bound-certificates-are-checked-without-a-solver-amends-33-bound-6-check-6).
8. **Identity links and database values.**
   - A `gtin_ndc_link` must be attested, and its photo span must re-parse to the linked NDC (`printed_ndc@1`).
   - A `spl_product_select` must find exactly one product with that package code, and every fact from that SPL must use it.
   - FDC values are corroboration, compared with the label facts under the rounding rules; Open Food Facts text is candidates. A fact or ingredient identity read from either API fails.
9. **Attestations.** Signer and statement are present. Signatures are optional and not implemented yet; the report says "unsigned".
10. **Assumptions.** Everything cited is stated, and everything stated is cited.

### Reading the report

```
PASS  composition/records/citrucel_orange_300680418301.json
  VERIFIED 36  ATTESTED 0  UNVERIFIED 0  FAILED 0
  VERIFIED   fact        F6  [55, 65) kcal  assumes A2,A3
  VERIFIED   derivation  D1  [55/4, 65/4) g  assumes A3,A4
  VERIFIED   bound       B3  (1802…/1044…, 6636…/2398…] g  assumes A10,A3,…
  Assumptions:
    A3 (rounding) [fda_rounding_101_9@1:calories]: The OTC statement 'contributes 60 calories' is rounded like …
  Rules: atomic_masses@1, atwater@1, …
```

- The first line is PASS or FAIL. The exit code is 0 only when every record passes, 1 when anything FAILED or a record is malformed, and 2 for usage errors.
- Then one line per field: its status, kind, id, exact interval and own assumptions. A FAILED field lists its problems underneath.
- Then every assumption in full, followed by the pinned rule versions. A value is only as good as the assumptions listed for it: read them.

## 5. Label photos: the attestation flow

1. In the phone app or on the dashboard (**Manufacturer data → Nutrition label photo…**), photograph the Nutrition Facts panel.
2. The Mac reads it (Apple Vision, or Tesseract if Vision fails; the engine is recorded) and proposes each row it can parse: "Total Fat 16g 21%". Each row's pixel box comes from the server's own OCR, never from the client.
3. The operator compares each row with the pack, corrects the text if needed, ticks the rows that match, and gives their name. Only ticked rows whose text a row rule (`nfp_row@1`, `nfp_serving@1`) can read are accepted.
4. The photo goes into the sample's evidence store, an entry is appended to `evidence/<sample>.json`, and the record is rebuilt:
   - one ATTESTED fact per row, an interval under the 101.9(c) rounding rules;
   - per-100 g values derived from the printed serving mass;
   - the library's database and OCR numbers in the unverified layer.

The same flow covers **Drug Facts** and **Supplement Facts** photos (**Drug Facts photo…**, **Supplement Facts photo…**, on the dashboard and on the phone). The checklist lists actives with strengths, "each … contains" minerals, amount rows, blend members and the inactive or other-ingredients list. Ticked items become ATTESTED facts and ingredients; the rules are `drug_active@1`, `otc_contains@1`, `sfp_row@1`, `sfp_serving@1` and `list_item@2`.

For an OTC drug whose barcode NDC is in no current label, photograph the printed **NDC** ("NDC 41520-745-18"; the **NDC photo…** button). The signed link resolves the barcode to the DailyMed SPL with that package code. Parser accuracy is in [COMPOSITION_COVERAGE.md](COMPOSITION_COVERAGE.md).

The dashboard's **Composition** tab runs the verifier every time it opens. It shows each value with its badge, the attestations, the assumptions, and, separately, the unverified estimates.

## 6. Training export

**Dashboard → Database → Composition for training** (`/foods/export/composition.csv`), or for any records:

```bash
python -m lio_comp.export composition/records/*.json --sources composition/sources --rules composition/rules
```

One row per value:

| Column | Contents |
|---|---|
| `record_id`, `gtin14`, `sample_code` | Which record and sample the value belongs to. |
| `kind`, `id` | fact, derivation, bound or estimate, and its id. |
| `quantity`, `basis` | What the value is, and per serving, per unit or per 100 g. |
| `lo`, `hi` | The interval's ends, as exact rationals. |
| `lo_closed`, `hi_closed` | Whether each end is included. |
| `unit` | The value's unit. |
| `badge` | From the verifier, never from the record itself. If a record fails as a whole, its values are exported as UNVERIFIED. |
| `assumptions` | Every assumption the value rests on, inherited through its inputs, including sample identity. |
| `method` | For estimates, how they were made. |

## 7. Rebuilding and extending

```bash
cd software/host
python -m lio_comp.catalog --store ../../composition/sources            # re-fetch documents (new retrievals)
python -m lio_comp.rules_build --store ../../composition/sources --out ../../composition/rules
python -m lio_comp.golden --store ../../composition/sources --rules ../../composition/rules --out ../../composition/records
```

- **Determinism.** Building twice gives byte-identical records. The tests rebuild the golden records and compare them byte for byte with the committed files. Bounds come from an exact `Fraction` simplex with Bland's rule, which is deterministic; there is no z3.
- **Changing a rule.** Edit `lio_comp/rules_build.py`, bump the table's `version`, rebuild the rules, then rebuild and re-verify the records. Old records keep citing the old version, and the verifier refuses them against the new table.
- **Changing a rule or text rule's behaviour.** Give it a new version (`nfp_row@2`); never change what an existing version means.
- **API keys.** The USDA key is used for the request only. Recorded URLs never contain it.

## 8. Where this departs from the specification

- **Calcium phosphates (spec §8).** The spec prints the range as [80·136.06/40.08, 80·310.18/(3·40.08)]; the lower end is larger than the upper. Tricalcium phosphate has the higher calcium fraction, so the ends swap.
  - The record also treats "calcium 80 mg" as rounded: 21 CFR 201.70(b) rounds OTC calcium to the nearest 5 mg.
  - It uses the CIAAW 2024 atomic weights with their uncertainty.
  - The result is [199.9, 280.1] mg, which contains the spec's corrected range [206.4, 271.6] (tested).
  - The spec's assumption that OTC mineral amounts have "no defined rounding rule" is wrong for calcium, potassium (201.72(b)) and sodium (201.64(b), nearest whole mg); these are rule tables now. The CFR does not say how halfway values round, so those intervals are closed at both ends.
- **Carbohydrate consistency for Citrucel.** It is an OTC drug with no Nutrition Facts, so there is no declared carbohydrate. The record checks mass balance against the 19 g dose instead; that dose is the SPL strength denominator, "2 g in 19 g".
- **Calories from an OTC statement.** Rounding "contributes 60 calories" with the food rule 101.9(c)(1) is an explicit assumption (A3), as are the 4 kcal/g factor (A4) and the tricalcium phosphate formula (A6). Food-grade "tribasic calcium phosphate" is closer to hydroxyapatite.
- **Potassium and other vitamin/mineral amounts on food labels.** The current 101.9(c)(8) has no increment rule for them; potassium's old sodium-style rule was removed in 2016. They are not in the rounding table and can only be used "as stated" under a named assumption. Supplement Facts mineral amounts likewise (101.36(b)(2)(ii)(B), "levels of significance").
- **FDC label nutrients.** FDC's `labelNutrients` are partly computed from per-100 g data. For Jif, fibre and added sugars are 2.01 g, where the label shows 2 g. A value becomes a fact only if it is a legal 101.9 declaration; the others are refused and noted in the record.
- **Identity.** UNIIs come from the SPL itself or from a stored GSRS response looked up by UNII. A GSRS name search is fuzzy (an exact-name query for "SUCROSE" returned "SUCROSE, 1-OLEATE" first) and is never used for identity. "orange flavors" in the Citrucel SPL text has no structured entry or UNII, so it is part of "other ingredients".
- **The verifier also needs lark.** The spec lists lxml, jsonschema and z3 as dependencies, but the verifier must re-run the OTC statement grammar, which lives in `lio_verify`. Since Rev B the dependencies are lxml, jsonschema and lark; z3 is not used anywhere.
- **Bound certificates.** Superseded by Rev B: exact dual and Motzkin certificates, checked with `Fraction` alone. pycddlib, the plan's suggested backend, did not build here, so the simplex is hand-written (`lio_comp/simplex.py`).
- **Attestation signatures.** These are optional in the spec and not implemented. Attestations record signer, time and statement; the report marks them unsigned.
- **Photo panels.** The attestation flow covers Nutrition Facts, Drug Facts and Supplement Facts panels and printed NDCs. Verified records built from a sample's DailyMed or DSLD sources (as for the golden records) are not yet automatic for library samples.
- **Tricalcium phosphate.** Superseded by Rev B §B5: the calcium fraction comes from the USP assay interval, not the formula Ca₃(PO₄)₂. See the CHANGELOG (M4) for the new Citrucel range.
