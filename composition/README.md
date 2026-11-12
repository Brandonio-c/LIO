# Verifiable composition records

Data for the verified composition layer (spec: [`docs/COMPOSITION_VERIFICATION_SPEC.md`](../docs/COMPOSITION_VERIFICATION_SPEC.md)).

| Folder | What | Written by |
|---|---|---|
| `sources/` | Content-addressed snapshots of every cited document: `sha256/<aa>/<hash>` (bytes as received, read-only), `manifest/<hash>.json` (retrievals), `catalog.json` (name to hash) | `python -m lio_comp.catalog --store composition/sources` |
| `rules/` | Versioned rule tables (rounding, Atwater, atomic masses, compounds, units, list ordering, QUID). Every rule cites a quote located by character span in a snapshot | `python -m lio_comp.rules_build --store composition/sources --out composition/rules` |
| `schema/` | JSON Schema for record bundles | by hand |
| `records/` | One bundle per golden record (from M2) | `lio_comp` |

Snapshots for real samples live in `data/foods/composition/` (gitignored), not here.

One blob is not in git: the FDA Food Labeling Guide PDF (8.9 MB, cited for the half-up tie rule). Run `python -m lio_comp.catalog --store composition/sources fda_food_labeling_guide_2013` to fetch it; its hash is in `catalog.json`.
