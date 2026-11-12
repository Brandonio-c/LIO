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
