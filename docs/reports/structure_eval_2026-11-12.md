# Structured ingredient tables: accuracy on real records (12 November 2026)

**What was tested.** The table that "Use this" shows in "Find the ingredients online" (`lio.foods.structure`). Each record was laid out exactly as the dashboard does it, then compared with independent structured data for the same product.

**How to reproduce.** Run `python tools/structure_eval.py --out test_results/structure_eval --drug 100 --supplement 60 --food 80` (seed 20261113). Responses are cached, so a re-run is offline.

## Results

| Records | Reference | Result |
|---|---|---|
| 86 conventional OTC drug labels (openFDA, random) | DailyMed SPL coded ingredients of the same set ID | **136 of 139** active ingredients found (98%)<br>**117 of 139** strengths match the SPL exactly (84%) |
| 14 homeopathic OTC labels | same | 22 of 133 substances matched by name. The label uses Latin names ("Calcarea Carbonica"), the SPL uses substance names ("oyster shell calcium carbonate"). |
| OTC inactive ingredients (86 labels) | SPL coded inactive list | 844 of 1,091 SPL names found (77%)<br>844 of 1,012 table rows matched (83%) |
| 60 DSLD supplement labels (random) | the DSLD record's rows | **533 of 533** rows, with every amount correct<br>serving size on all 60 labels |
| 63 FDC branded foods also in Open Food Facts | Open Food Facts' own parse of the same list | 654 of 700 top-level ingredients agree (93%) |

## Two readings of a drug label (added after this evaluation)

For an FDA drug label, "Use this" now offers two readings, and the operator picks one. The coded reading is preselected.

1. **FDA coded product data** (the DailyMed SPL of the same set ID):
   - one table per product;
   - substance names, ingredient codes (UNII) and strengths exactly as the manufacturer filed them;
   - purposes, per-dose amounts and allergens copied from the label text.
2. **The label-text reading** described above.

On the same 100 labels:

- **Coverage.** A coded table was available for all 100. All **273 of 273** coded actives have a strength, against 84% from the label text.
- **Disagreements.** For 9 actives the label text states a different strength, and the row says so ("label text says …"). For example, "5 mg" against a coded "3.5 mg" neomycin base, or a "10%" coded as 0.1 g per 100 g.
  - The comparison treats equivalent forms as the same: "5%" equals 5 g per 100 g, "500 units" equals 500 IU.
- **Unmatched names.**
  - On regular labels, 5 of 140 coded actives could not be matched to a label-text name; the cause is synonyms or typos.
  - On homeopathic labels, 107 of 133 could not. The label uses Latin names, the coded data uses substance names, and the row notes this.

## Combined reading (several sources fused)

A third option combines several readings into one table:

- **Automatically**, for an FDA label: the coded data plus the label text of the same product. This reading is preselected.
- **On demand** in the dashboard: tick "combine" on any database records (FDA, DSLD, USDA) and any web-page sections, then press "Combine N sources".

How the table is built:

- **Matching rows.** Rows naming the same ingredient are merged: same UNII, or the same words after removing synonyms ("HCl" means hydrochloride, "soy" means soybean).
- **Choosing values.** Each field takes the value of the most trusted source that states it: FDA coded, then DSLD, then label text, then USDA, then web pages and Open Food Facts. Gaps are filled from the other sources.
- **Showing the evidence.**
  - A Sources column lists the sources that name each ingredient.
  - A strength that two sources state differently is highlighted, and the row says "conflict: …".
  - An ingredient only one source lists is marked "only in: …".
- **Supplement facts and per-dose amounts.** A DSLD supplement-facts row that matches a drug label's "each … contains" amount confirms that amount.

On the 100 OTC labels (coded data combined with label text):

| | Conventional (86 labels) | Homeopathic (14) |
|---|---|---|
| Combined rows | 1,492 | 216 |
| Named by both sources | 990 (66%) | 49 |
| Only one source names it | 502 | 167 |
| Strength conflicts flagged | 8 | 1 |
| Actives with a strength | 144 of 144 | 176 of 176 |

Homeopathic labels give duplicate rows, because the Latin and substance names cannot be matched; the operator removes the duplicates. On conventional labels, most "only one source" rows are inactive ingredients the label text names differently ("fragrance", "Cyclopentasiloxane") or does not list.

### Why the 22 conventional strengths differ

- **11: the label text gives no strength.** For example, MEDCLOT says only "CarboxymethylCellulose", and a sunscreen has an empty active-ingredient field. N/A is the correct answer here.
- **About 8: the SPL's coded data disagrees with its own label text.**
  - A "10%" active is coded as 0.1 g per 100 g.
  - "Neomycin sulfate 5 mg" is coded as the 3.5 mg base.
  - A "1.6%" coal tar is coded as 5.39 g per 250 mL.
- **The rest: label typos.** For example, "Salicilic acid".

### Why inactive names differ

The label and the SPL code often name the same substance differently: "Cyclopentasiloxane" against "CYCLOMETHICONE 5", or "fragrance" with no coded entry. Three labels print their inactive list without commas, so it becomes one long row.

### Fixed during this evaluation (each has a unit test)

- Dot-leader tables and repeated headings ("Active Ingredient ……… Purpose").
- "Drug Facts" or "OTC-" before a heading.
- The Purpose column: captured per ingredient, from the Purpose section or from the OTC monograph purpose words.
- "x%" strengths: basis "of product".
- Homeopathic potencies (12X, 30C, 200CK): the amount is the potency and the basis is "HPUS potency".
- "units" and "10,000" (a thousands separator, previously read as 10.000).
- Grains: the metric amount in the brackets is used.
- "Equivalent to … of … base" phrases.
- A brand that is the drug name ("Loratadine") was stripped from the name.
- "USP" and dosage-form words are no longer part of names.
- Labels with no active-ingredient text: names come from the FDA product listing, with the amount N/A.
- "100% blueberries" was read as "≤ 100%".
- Food lists whose brackets do not balance get a warning note.
- Allergen statements ("CONTAINS: WHEAT, MILK") were turned into ingredients. They are now a separate allergen field.
