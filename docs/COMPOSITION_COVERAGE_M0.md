# M0 report: composition coverage recon (LIO-SW-COMP-002)

Recon for [COMPOSITION_COVERAGE_PLAN.md](COMPOSITION_COVERAGE_PLAN.md). Every response below is stored byte-for-byte in `composition/sources` (SHA-256 given), retrieved 12 November 2026.

## 1. RxNav and DailyMed results, and what they mean

| Call | Result | Meaning (concept level only) |
|---|---|---|
| `ndcstatus` 00068041830 (Citrucel UPC NDC) | **ACTIVE**, RxCUI 1868847 "methylcellulose 2000 MG Powder for Oral Suspension [Citrucel]", sources GS, MMSL, MMX, RXNORM, VANDF; history 2017-03 to 2026-11 | Not retired. The NDC is live in the drug compendia (Gold Standard, Multum, Micromedex) though absent from the FDA NDC directory and DailyMed. The plan expected UNKNOWN or OBSOLETE. |
| `ndcproperties` 0135-0089, all statuses | 0135-0089-69 (454 g) under RxCUIs 1006675, 1868847, 204597, 209712; SPL set `9d5f2244…` | The current Orange product, linked to the same concepts. The 850 g pack 0135-0089-71 is not in this answer. |
| `allhistoricalndcs` 1868847 / 1006675 | Both list 00068041830 **and** 00135008969/71 (Orange) **and** 00135009070/74/75 (Sugar Free) | RxNav puts the retired-labeler NDC, Orange and Sugar Free in one concept. It cannot say which product a barcode is, so it is concept-level evidence only (invariant 5 confirmed). |
| `allhistoricalndcs` 204597 / 209712 | Older concepts (2007–2010) for 0135 and 0766 NDCs | History only. |
| DailyMed `spls.json?ndc=0068-0418-30` | 0 SPLs | The UPC's NDC is not in any current FDA label. |
| DailyMed `9d5f2244…/ndcs.json` | 0135-0089-69, 0135-0089-71, 0135-0090-70/74/75 (v17) | The set covers Orange (0089) and Sugar Free (0090). |
| DailyMed `9d5f2244…/history.json` | 17 versions, 2010-10-15 to 2026-03-20 | Version pinning for the crosswalk. |
| `ndcstatus` 41520031464 (Care One UPC NDC) | **UNKNOWN** | The UPC's NDC is unknown to RxNorm. |
| `ndcstatus` 41520074540 (label NDC) | ACTIVE, RxCUI 310964 "ibuprofen 200 MG Oral Capsule" | The label's NDC is live. |

**Does any call link the retired NDC to the current product?** Only at concept level. RxNav's history puts 00068041830 in the same RxCUI as the Orange NDCs, but also as the Sugar Free NDCs. Nothing links it to set `9d5f2244` as a specific product or variant, and nothing in DailyMed knows 0068-0418-30. For Care One, nothing links 41520-314-64 to anything.

## 2. Citrucel SPL structure

SPL v17 (set `9d5f2244`, document `4d50ac6b-…`) has **separate `manufacturedProduct` elements**:
- **Orange, 0135-0089:** active methylcellulose 2 g in 19 g, plus 10 inactive ingredients with UNIIs.
- **Sugar Free, 0135-0090:** 2 g in 10.2 g, plus 8 inactive ingredients.

**No inactive ingredient carries a `<quantity>` (strength).** The text sections name the variant only in their titles ("Inactive ingredients (Citrucel Orange)"). The text list has one item with no structured entry: "orange flavors (natural and artificial)".

## 3. Calcium phosphate specifications (the FCC is not free)

The Food Chemicals Codex is sold by USP and could not be read. Free, citable sources, all stored in `composition/sources`:

| Material | Source | Assay | Basis | Loss limit |
|---|---|---|---|---|
| Tribasic calcium phosphate | USP 32–NF 27 monograph | "not less than 34.0 percent and not more than 40.0 percent of calcium (Ca)" | **as-is** (no dried or ignited qualifier) | ignition ≤ 8.0% (800 °C, 30 min) |
| Tricalcium phosphate (INS 341(iii)) | JECFA monograph (FAO) | ≥ 90% as Ca₃(PO₄)₂ | **ignited** | ignition ≤ 10% (825 °C) |
| Anhydrous dibasic calcium phosphate | USP 32–NF 27 | 98.0–103.0% CaHPO₄ | **as-is** | n/a |
| Dibasic calcium phosphate dihydrate | USP 32–NF 27 | 98.0–105.0% CaHPO₄·2H₂O | as-is | n/a |

**Effect on the intervals.**
- **Tricalcium phosphate.** The USP as-is range gives a Ca mass fraction of [0.340, 0.400] with no widening needed. JECFA alone would give only a lower bound, 0.9 × 3Ca/Ca₃(PO₄)₂ ≈ 0.349 ignited, or ≥ 0.314 as-is after a 10% ignition loss, and no upper bound. So the rule uses USP–NF, under an assumption that Citrucel's TCP meets the NF monograph. For an OTC drug ingredient the compendial standard is the legal one (FD&C Act §501(b)).
- **Anhydrous DCP.** The plan's 97.0–105.0% is not what USP says: it's 98.0–103.0% as-is, so Ca ∈ [0.980, 1.030] × Ca/CaHPO₄ (CIAAW interval).
- **The mirror.** The USP text is read from a public mirror of USP 32 (drugfuture.com). That this mirror matches the official text is a recorded assumption.

## 4. Exact LP backend

`pycddlib` does not build on this Mac: it needs the cddlib and GMP C libraries, and pip has no wheel. So **the hand-rolled dense `Fraction` simplex (Bland's rule)** is used, as the plan defaults. pycddlib stays an optional backend behind the same interface, not installed.

## 5. Deviations from the plan, and questions answered by default

1. **The Citrucel NDC is ACTIVE in RxNav (compendia), not retired.** The resolver records whatever status comes back. ACTIVE-but-absent-from-the-SPL is treated like OBSOLETE, i.e. it triggers the printed-NDC prompt.
2. **The printed NDC may not resolve Citrucel.** If the tub prints an NDC at all (OTC labels need not), it likely matches the UPC, 0068-0418-30, which is absent from the SPL. In that case the record uses `method: "name_search_confirmed"` with the operator's variant choice, which the plan allows as the fallback.
3. **The operator must sign the golden-record attestations.** The software cannot attest for the operator. Golden records that need a link attestation are generated by the `lio comp link-ndc` command once the operator photographs and signs. CI uses clearly marked test fixtures (signer `test-fixture`), never golden data.
4. **FCC → USP–NF + JECFA** (section 3). The rule ids are `usp_nf_tcp_assay@32` and `usp_nf_dcp_anhydrous_assay@32`, not `fcc_tcp_assay@…`.
5. **Branches.** `gh` is not logged in on this Mac, so I can't open PRs. Each milestone is a stacked branch, `feature/composition-coverage-mN`, pushed with a PR link. `feature/composition-coverage` is the final one.
6. **Benchmark pilot.** It needs store photos. The tooling is run end to end on a labelled dry run; the real 10-item pilot is the operator's.
7. **The paired corpus** is built from free sources where ground truth is structured: DailyMed label images paired with SPL text, and DSLD label images paired with DSLD rows. Its size is whatever those sources yield, and is reported.

## Verbatim responses

### `https://rxnav.nlm.nih.gov/REST/ndcstatus.json?ndc=00068041830&history=1`

SHA-256 `2332b7a6cd8bff8eaf6d3ee8a87f75bbcda804564fa8d730a3c94385099fb4f5`, retrieved 2026-11-12T18:11:13Z

```json
{"ndcStatus":{"ndc11":"00068041830","status":"ACTIVE","active":"YES","rxnormNdc":"YES","rxcui":"1868847","conceptName":"methylcellulose 2000 MG Powder for Oral Suspension [Citrucel]","conceptStatus":"ACTIVE","sourceList":{"sourceName":["GS","MMSL","MMX","RXNORM","VANDF"]},"altNdc":"N","comment":null,"ndcHistory":[{"activeRxcui":"1868847","originalRxcui":"1868847","startDate":"201703","endDate":"202611"}]}}
```

### `https://rxnav.nlm.nih.gov/REST/ndcproperties.json?id=0135-0089&ndcstatus=ALL`

SHA-256 `d6c9c1d825f96e30a6003d5047d1d9e645adbd2682a6c6f741204295b43ed3d8`, retrieved 2026-11-12T18:11:13Z

```json
{"ndcPropertyList":{"ndcProperty":[{"ndcItem":"00135008969","ndc9":"0135-0089","ndc10":"0135-0089-69","rxcui":"1006675","splSetIdItem":"9d5f2244-a610-4d45-b6e8-e79bb17a558f","packagingList":{"packaging":["454 g in 1 BOTTLE (0135-0089-69)"]},"propertyConceptList":{"propertyConcept":[{"propName":"COLORTEXT","propValue":"ORANGE"},{"propName":"COLOR","propValue":"C48331"},{"propName":"LABELER","propValue":"Haleon US Holdings LLC"},{"propName":"LABEL_TYPE","propValue":"HUMAN OTC DRUG"},{"propName":"MARKETING_CATEGORY","propValue":"OTC MONOGRAPH DRUG"},{"propName":"MARKETING_EFFECTIVE_TIME_LOW","propValue":"20100916"},{"propName":"MARKETING_STATUS","propValue":"ACTIVE"},{"propName":"OTC_MONOGRAPH_DRUG","propValue":"M007"},{"propName":"OTC_MONOGRAPH_NOT_FINAL","propValue":"part334"}]},"source":"Hybrid"},{"ndcItem":"00135008969","ndc9":"0135-0089","ndc10":"0135-0089-69","rxcui":"1868847","splSetIdItem":"9d5f2244-a610-4d45-b6e8-e79bb17a558f","packagingList":{"packaging":["454 g in 1 BOTTLE (0135-0089-69)"]},"propertyConceptList":{"propertyConcept":[{"propName":"COLORTEXT","propValue":"orange"},{"propName":"COLOR","propValue":"C48331"},{"propName":"LABELER","propValue":"Haleon US Holdings LLC"},{"propName":"LABEL_TYPE","propValue":"HUMAN OTC DRUG"},{"propName":"MARKETING_CATEGORY","propValue":"OTC MONOGRAPH DRUG"},{"propName":"MARKETING_EFFECTIVE_TIME_LOW","propValue":"20100916"},{"propName":"MARKETING_STATUS","propValue":"ACTIVE"},{"propName":"OTC_MONOGRAPH_DRUG","propValue":"M007"}]},"source":"Hybrid"},{"ndcItem":"00135008969","ndc9":"0135-0089","ndc10":"0135-0089-69","rxcui":"204597","splSetIdItem":"","packagingList":{"packaging":["454 g in 1 BOTTLE (0135-0089-69)"]},"propertyConceptList":{"propertyConcept":[{"propName":"LABELER","propValue":"Haleon US Holdings LLC"},{"propName":"LABEL_TYPE","propValue":"HUMAN OTC DRUG"},{"propName":"MARKETING_CATEGORY","propValue":"OTC MONOGRAPH DRUG"},{"propName":"MARKETING_EFFECTIVE_TIME_LOW","propValue":"20100916"},{"propName":"MARKETING_STATUS","propValue":"ACTIVE"},{"propName":"OTC_MONOGRAPH_DRUG","propValue":"M007"}]},"source":"FDA"},{"ndcItem":"00135008969","ndc9":"0135-0089","ndc10":"0135-0089-69","rxcui":"209712","splSetIdItem":"","packagingList":{"packaging":["454 g in 1 BOTTLE (0135-0089-69)"]},"propertyConceptList":{"propertyConcept":[{"propName":"LABELER","propValue":"Haleon US Holdings LLC"},{"propName":"LABEL_TYPE","propValue":"HUMAN OTC DRUG"},{"propName":"MARKETING_CATEGORY","propValue":"OTC MONOGRAPH DRUG"},{"propName":"MARKETING_EFFECTIVE_TIME_LOW","propValue":"20100916"},{"propName":"MARKETING_STATUS","propValue":"ACTIVE"},{"propName":"OTC_MONOGRAPH_DRUG","propValue":"M007"}]},"source":"FDA"},{"ndcItem":"00135008971","ndc9":"0135-0089","ndc10":"0135-0089-71","rxcui":"1006675","splSetIdItem":"9d5f2244-a610-4d45-b6e8-e79bb17a558f","packagingList":{"packaging":["850 g in 1 BOTTLE (0135-0089-71)"]},"propertyConceptList":{"propertyConcept":[{"propName":"COLORTEXT","propValue":"ORANGE"},{"propName":"COLOR","propValue":"C48331"},{"propName":"LABELER","propValue":"Haleon US Holdings LLC"},{"propName":"LABEL_TYPE","propValue":"HUMAN OTC DRUG"},{"propName":"MARKETING_CATEGORY","propValue":"OTC MONOGRAPH DRUG"},{"propName":"MARKETING_EFFECTIVE_TIME_LOW","propValue":"20100916"},{"propName":"MARKETING_STATUS","propValue":"ACTIVE"},{"propName":"OTC_MONOGRAPH_DRUG","propValue":"M007"},{"propName":"OTC_MONOGRAPH_NOT_FINAL","propValue":"part334"}]},"source":"Hybrid"},{"ndcItem":"00135008971","ndc9":"0135-0089","ndc10":"0135-0089-71","rxcui":"1868847","splSetIdItem":"9d5f2244-a610-4d45-b6e8-e79bb17a558f","packagingList":{"packaging":["850 g in 1 BOTTLE (0135-0089-71)"]},"propertyConceptList":{"propertyConcept":[{"propName":"COLORTEXT","propValue":"orange"},{"propName":"COLOR","propValue":"C48331"},{"propName":"LABELER","propValue":"Haleon US Holdings LLC"},{"propName":"LABEL_TYPE","propValue":"HUMAN OTC DRUG"},{"propName":"MARKETING_CATEGORY","propValue":"OTC MONOGRAPH DRUG"},{"propName":"MARKETING_EFFECTIVE_TIME_LOW","propValue":"20100916"},{"propName":"MARKETING_STATUS","propValue":"ACTIVE"},{"propName":"OTC_MONOGRAPH_DRUG","propValue":"M007"}]},"source":"Hybrid"},{"ndcItem":"00135008971","ndc9":"0135-0089","ndc10":"0135-0089-71","rxcui":"204597","splSetIdItem":"","packagingList":{"packaging":["850 g in 1 BOTTLE (0135-0089-71)"]},"propertyConceptList":{"propertyConcept":[{"propName":"LABELER","propValue":"Haleon US Holdings LLC"},{"propName":"LABEL_TYPE","propValue":"HUMAN OTC DRUG"},{"propName":"MARKETING_CATEGORY","propValue":"OTC MONOGRAPH DRUG"},{"propName":"MARKETING_EFFECTIVE_TIME_LOW","propValue":"20100916"},{"propName":"MARKETING_STATUS","propValue":"ACTIVE"},{"propName":"OTC_MONOGRAPH_DRUG","propValue":"M007"}]},"source":"FDA"},{"ndcItem":"00135008971","ndc9":"0135-0089","ndc10":"0135-0089-71","rxcui":"209712","splSetIdItem":"","packagingList":{"packaging":["850 g in 1 BOTTLE (0135-0089-71)"]},"propertyConceptList":{"propertyConcept":[{"propName":"LABELER","propValue":"Haleon US Holdings LLC"},{"propName":"LABEL_TYPE","propValue":"HUMAN OTC DRUG"},{"propName":"MARKETING_CATEGORY","propValue":"OTC MONOGRAPH DRUG"},{"propName":"MARKETING_EFFECTIVE_TIME_LOW","propValue":"20100916"},{"propName":"MARKETING_STATUS","propValue":"ACTIVE"},{"propName":"OTC_MONOGRAPH_DRUG","propValue":"M007"}]},"source":"FDA"},{"ndcItem":"00135008975","ndc9":"0135-0089","ndc10":"0135-0089-75","rxcui":"1006675","splSetIdItem":"","propertyConceptList":{"propertyConcept":[{"propName":"COLORTEXT","propValue":"ORANGE"},{"propName":"COLOR","propValue":"C48331"},{"propName":"LABELER","propValue":"Haleon US Holdings LLC"},{"propName":"LABEL_TYPE","propValue":"HUMAN OTC DRUG"},{"propName":"MARKETING_CATEGORY","propValue":"OTC MONOGRAPH DRUG"},{"propName":"MARKETING_EFFECTIVE_TIME_LOW","propValue":"20100916"},{"propName":"MARKETING_STATUS","propValue":"ACTIVE"},{"propName":"OTC_MONOGRAPH_DRUG","propValue":"M007"},{"propName":"OTC_MONOGRAPH_NOT_FINAL","propValue":"part334"}]},"source":"Hybrid"},{"ndcItem":"00135008975","ndc9":"0135-0089","ndc10":"0135-0089-75","rxcui":"204597","splSetIdItem":"","propertyConceptList":{"propertyConcept":[{"propName":"LABELER","propValue":"Haleon US Holdings LLC"},{"propName":"LABEL_TYPE","propValue":"HUMAN OTC DRUG"},{"propName":"MARKETING_CATEGORY","propValue":"OTC MONOGRAPH DRUG"},{"propName":"MARKETING_EFFECTIVE_TIME_LOW","propValue":"20100916"},{"propName":"MARKETING_STATUS","propValue":"ACTIVE"},{"propName":"OTC_MONOGRAPH_DRUG","propValue":"M007"}]},"source":"FDA"},{"ndcItem":"00135008975","ndc9":"0135-0089","ndc10":"0135-0089-75","rxcui":"209712","splSetIdItem":"","propertyConceptList":{"propertyConcept":[{"propName":"LABELER","propValue":"Haleon US Holdings LLC"},{"propName":"LABEL_TYPE","propValue":"HUMAN OTC DRUG"},{"propName":"MARKETING_CATEGORY","propValue":"OTC MONOGRAPH DRUG"},{"propName":"MARKETING_EFFECTIVE_TIME_LOW","propValue":"20100916"},{"propName":"MARKETING_STATUS","propValue":"ACTIVE"},{"propName":"OTC_MONOGRAPH_DRUG","propValue":"M007"}]},"source":"FDA"}]}}
```

### `https://rxnav.nlm.nih.gov/REST/rxcui/1006675/allhistoricalndcs.json`

SHA-256 `da8cd2b12603e462ba04409e0ac9527b70d3023a4e961788ef518235c3760b3e`, retrieved 2026-11-12T18:11:14Z

```json
{"historicalNdcConcept":{"historicalNdcTime":[{"status":"direct","rxcui":"1006675","ndcTime":[{"ndc":["00068041830"],"startDate":"201311","endDate":"201702"},{"ndc":["00068042017"],"startDate":"201102","endDate":"201702"},{"ndc":["00135008969"],"startDate":"201011","endDate":"201702"},{"ndc":["00135008971"],"startDate":"201011","endDate":"201702"},{"ndc":["00135008975"],"startDate":"201102","endDate":"201601"},{"ndc":["00135009068"],"startDate":"201009","endDate":"201601"},{"ndc":["00135009070"],"startDate":"201011","endDate":"201702"},{"ndc":["00135009074"],"startDate":"201011","endDate":"201702"},{"ndc":["00135009075"],"startDate":"201011","endDate":"201702"},{"ndc":["00135010556"],"startDate":"201009","endDate":"201101"},{"ndc":["00135010557"],"startDate":"201102","endDate":"201601"},{"ndc":["00135023802"],"startDate":"201102","endDate":"201112"},{"ndc":["00680042017"],"startDate":"201309","endDate":"201702"},{"ndc":["00766041850"],"startDate":"201009","endDate":"201404"},{"ndc":["00766042025"],"startDate":"201009","endDate":"201702"},{"ndc":["00766042050"],"startDate":"201009","endDate":"201702"},{"ndc":["00766287589"],"startDate":"201112","endDate":"201702"}]},{"status":"indirect","rxcui":"209712","ndcTime":[{"ndc":["00135008969"],"startDate":"200706","endDate":"201002"},{"ndc":["00135008971"],"startDate":"200706","endDate":"201002"},{"ndc":["00135008975"],"startDate":"200706","endDate":"201002"},{"ndc":["00135009068"],"startDate":"200706","endDate":"201008"},{"ndc":["00135009070"],"startDate":"200706","endDate":"201002"},{"ndc":["00135010556"],"startDate":"200706","endDate":"201008"},{"ndc":["00135010557"],"startDate":"200706","endDate":"201002"},{"ndc":["00766041850"],"startDate":"200706","endDate":"201008"},{"ndc":["00766042025"],"startDate":"200706","endDate":"201008"},{"ndc":["00766042050"],"startDate":"200706","endDate":"201008"}]}]}}
```

### `https://rxnav.nlm.nih.gov/REST/rxcui/1868847/allhistoricalndcs.json`

SHA-256 `260627fd02f87a32f34a5edb12ec8e8126be52ff6f6777f735f0cd3cf6ebdfb1`, retrieved 2026-11-12T18:11:14Z

```json
{"historicalNdcConcept":{"historicalNdcTime":[{"status":"indirect","rxcui":"1006675","ndcTime":[{"ndc":["00068041830"],"startDate":"201311","endDate":"201702"},{"ndc":["00068042017"],"startDate":"201102","endDate":"201702"},{"ndc":["00135008969"],"startDate":"201011","endDate":"201702"},{"ndc":["00135008971"],"startDate":"201011","endDate":"201702"},{"ndc":["00135008975"],"startDate":"201102","endDate":"201601"},{"ndc":["00135009068"],"startDate":"201009","endDate":"201601"},{"ndc":["00135009070"],"startDate":"201011","endDate":"201702"},{"ndc":["00135009074"],"startDate":"201011","endDate":"201702"},{"ndc":["00135009075"],"startDate":"201011","endDate":"201702"},{"ndc":["00135010556"],"startDate":"201009","endDate":"201101"},{"ndc":["00135010557"],"startDate":"201102","endDate":"201601"},{"ndc":["00135023802"],"startDate":"201102","endDate":"201112"},{"ndc":["00680042017"],"startDate":"201309","endDate":"201702"},{"ndc":["00766041850"],"startDate":"201009","endDate":"201404"},{"ndc":["00766042025"],"startDate":"201009","endDate":"201702"},{"ndc":["00766042050"],"startDate":"201009","endDate":"201702"},{"ndc":["00766287589"],"startDate":"201112","endDate":"201702"}]},{"status":"direct","rxcui":"1868847","ndcTime":[{"ndc":["00068041830"],"startDate":"201703","endDate":"202611"},{"ndc":["00068042017"],"startDate":"201703","endDate":"202611"},{"ndc":["00135008969"],"startDate":"201703","endDate":"202611"},{"ndc":["00135008971"],"startDate":"201703","endDate":"202611"},{"ndc":["00135009070"],"startDate":"201703","endDate":"202611"},{"ndc":["00135009074"],"startDate":"201703","endDate":"202611"},{"ndc":["00135009075"],"startDate":"201703","endDate":"202611"},{"ndc":["00680042017"],"startDate":"201703","endDate":"202611"},{"ndc":["00766042025"],"startDate":"201703","endDate":"202611"},{"ndc":["00766042050"],"startDate":"201703","endDate":"202611"},{"ndc":["00766287589"],"startDate":"201703","endDate":"202207"}]},{"status":"indirect","rxcui":"209712","ndcTime":[{"ndc":["00135008969"],"startDate":"200706","endDate":"201002"},{"ndc":["00135008971"],"startDate":"200706","endDate":"201002"},{"ndc":["00135008975"],"startDate":"200706","endDate":"201002"},{"ndc":["00135009068"],"startDate":"200706","endDate":"201008"},{"ndc":["00135009070"],"startDate":"200706","endDate":"201002"},{"ndc":["00135010556"],"startDate":"200706","endDate":"201008"},{"ndc":["00135010557"],"startDate":"200706","endDate":"201002"},{"ndc":["00766041850"],"startDate":"200706","endDate":"201008"},{"ndc":["00766042025"],"startDate":"200706","endDate":"201008"},{"ndc":["00766042050"],"startDate":"200706","endDate":"201008"}]}]}}
```

### `https://rxnav.nlm.nih.gov/REST/rxcui/204597/allhistoricalndcs.json`

SHA-256 `e37abe7f9ebc351b13737841cff0d05ac4cd6150b8f912ef6b0d5141fe605388`, retrieved 2026-11-12T18:11:14Z

```json
{"historicalNdcConcept":{"historicalNdcTime":[{"status":"direct","rxcui":"204597","ndcTime":[{"ndc":["00135008969"],"startDate":"200801","endDate":"200901"},{"ndc":["00135008971"],"startDate":"200801","endDate":"200901"},{"ndc":["00135008975"],"startDate":"200801","endDate":"200901"},{"ndc":["00135009068"],"startDate":"200801","endDate":"200901"},{"ndc":["00135009070"],"startDate":"200801","endDate":"200901"},{"ndc":["00135010556"],"startDate":"200801","endDate":"200901"},{"ndc":["00135010557"],"startDate":"200801","endDate":"200901"},{"ndc":["00766041850"],"startDate":"200801","endDate":"200901"},{"ndc":["00766042025"],"startDate":"200801","endDate":"200901"},{"ndc":["00766042050"],"startDate":"200801","endDate":"200901"},{"ndc":["00904567516"],"startDate":"200706","endDate":"201002"},{"ndc":["49348051879"],"startDate":"200706","endDate":"201008"}]}]}}
```

### `https://rxnav.nlm.nih.gov/REST/rxcui/209712/allhistoricalndcs.json`

SHA-256 `129c929efab3ad2f1f9167507dd24e37462ea287e5ded9c8fccfa8d38d89e048`, retrieved 2026-11-12T18:11:15Z

```json
{"historicalNdcConcept":{"historicalNdcTime":[{"status":"direct","rxcui":"209712","ndcTime":[{"ndc":["00135008969"],"startDate":"200706","endDate":"201002"},{"ndc":["00135008971"],"startDate":"200706","endDate":"201002"},{"ndc":["00135008975"],"startDate":"200706","endDate":"201002"},{"ndc":["00135009068"],"startDate":"200706","endDate":"201008"},{"ndc":["00135009070"],"startDate":"200706","endDate":"201002"},{"ndc":["00135010556"],"startDate":"200706","endDate":"201008"},{"ndc":["00135010557"],"startDate":"200706","endDate":"201002"},{"ndc":["00766041850"],"startDate":"200706","endDate":"201008"},{"ndc":["00766042025"],"startDate":"200706","endDate":"201008"},{"ndc":["00766042050"],"startDate":"200706","endDate":"201008"}]}]}}
```

### `https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?ndc=0068-0418-30`

SHA-256 `913b56488c264930f11e445e6c4256ad0246133954a953ed7d6f17a624e8aeaf`, retrieved 2026-11-12T18:11:15Z

```json
{"data": [], "metadata": {"db_published_date": "Nov 11, 2026 08:02:44PM EST", "elements_per_page": 100, "current_url": "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json?ndc=0068-0418-30", "next_page_url": "null", "total_elements": 0, "total_pages": 0, "current_page": 1, "previous_page": "null", "previous_page_url": "null", "next_page": "null"}}
```

### `https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/9d5f2244-a610-4d45-b6e8-e79bb17a558f/ndcs.json`

SHA-256 `062808938556fac3311aca78562fa0430e8f467d5d513af127c00ad17c47bcd0`, retrieved 2026-11-12T18:11:15Z

```json
{"data": {"spl_version": 17, "ndcs": [{"ndc": "0135-0089-69"}, {"ndc": "0135-0089-71"}, {"ndc": "0135-0090-70"}, {"ndc": "0135-0090-74"}, {"ndc": "0135-0090-75"}], "published_date": "Mar 20, 2026", "title": "CITRUCEL (METHYLCELLULOSE) POWDER, FOR SOLUTION [HALEON US HOLDINGS LLC]", "setid": "9d5f2244-a610-4d45-b6e8-e79bb17a558f"}, "metadata": {"db_published_date": "Nov 11, 2026 08:02:44PM EST", "elements_per_page": 100, "current_url": "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/9d5f2244-a610-4d45-b6e8-e79bb17a558f/ndcs.json", "next_page_url": "null", "total_elements": 5, "total_pages": 1, "current_page": 1, "previous_page": "null", "previous_page_url": "null", "next_page": "null"}}
```

### `https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/9d5f2244-a610-4d45-b6e8-e79bb17a558f/history.json`

SHA-256 `a22438b764c7b6eaaac31cdb0fd841190a7f3e10b32e33f3f12aaacde381f03a`, retrieved 2026-11-12T18:11:16Z

```json
{"data": {"spl": {"title": "CITRUCEL (METHYLCELLULOSE) POWDER, FOR SOLUTION [HALEON US HOLDINGS LLC]", "setid": "9d5f2244-a610-4d45-b6e8-e79bb17a558f"}, "history": [{"spl_version": 17, "published_date": "Mar 20, 2026"}, {"spl_version": 16, "published_date": "Jun 12, 2024"}, {"spl_version": 15, "published_date": "Mar 08, 2024"}, {"spl_version": 14, "published_date": "Oct 02, 2023"}, {"spl_version": 13, "published_date": "Dec 19, 2022"}, {"spl_version": 12, "published_date": "May 25, 2021"}, {"spl_version": 11, "published_date": "Apr 28, 2021"}, {"spl_version": 10, "published_date": "Nov 18, 2020"}, {"spl_version": 9, "published_date": "Oct 11, 2018"}, {"spl_version": 8, "published_date": "Feb 09, 2018"}, {"spl_version": 7, "published_date": "Dec 06, 2016"}, {"spl_version": 6, "published_date": "Sep 16, 2015"}, {"spl_version": 5, "published_date": "Sep 16, 2014"}, {"spl_version": 4, "published_date": "Sep 17, 2013"}, {"spl_version": 3, "published_date": "Dec 11, 2012"}, {"spl_version": 2, "published_date": "Nov 10, 2011"}, {"spl_version": 1, "published_date": "Oct 15, 2010"}]}, "metadata": {"db_published_date": "Nov 11, 2026 08:02:44PM EST", "elements_per_page": 100, "current_url": "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/9d5f2244-a610-4d45-b6e8-e79bb17a558f/history.json", "next_page_url": "null", "total_elements": 17, "total_pages": 1, "current_page": 1, "previous_page": "null", "previous_page_url": "null", "next_page": "null"}}
```

### `https://rxnav.nlm.nih.gov/REST/ndcstatus.json?ndc=41520031464&history=1`

SHA-256 `368d28931a5b5e80cd631d3a00ba84044789dd9b0f756d751cf9f0962a422dd3`, retrieved 2026-11-12T18:11:16Z

```json
{"ndcStatus":{"ndc11":"41520031464","status":"UNKNOWN","active":"","rxnormNdc":"","rxcui":"","conceptName":"","conceptStatus":"","sourceList":{},"altNdc":"N","comment":null}}
```

### `https://rxnav.nlm.nih.gov/REST/ndcstatus.json?ndc=41520074540&history=1`

SHA-256 `59f9509b868db22db924f3c2ed6c322a02c6df1ae47aa1b26ce183ae5172ae00`, retrieved 2026-11-12T18:11:16Z

```json
{"ndcStatus":{"ndc11":"41520074540","status":"ACTIVE","active":"YES","rxnormNdc":"YES","rxcui":"310964","conceptName":"ibuprofen 200 MG Oral Capsule","conceptStatus":"ACTIVE","sourceList":{"sourceName":["MTHSPL","RXNORM"]},"altNdc":"N","comment":null,"ndcHistory":[{"activeRxcui":"310964","originalRxcui":"310964","startDate":"201807","endDate":"202611"}]}}
```
