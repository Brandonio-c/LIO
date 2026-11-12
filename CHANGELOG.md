# Changelog

## 2026-11-12: Composition coverage M1, solver-independent bound certificates (plan WP6)

### Changed
- **Bounds are computed by an exact simplex** over `Fraction` (`lio_comp.simplex`: two-phase, Bland's rule, size-capped). Each end of a bound carries:
  - the LP it was computed on;
  - an LP dual vector proving the end;
  - a reaching witness, or for an open end a closure-optimal point, a strictly feasible point and a Motzkin certificate that the end is not reached.
- `lio_verify.cert` checks all of it with `Fraction` arithmetic alone. It also checks that the certificate's LP is exactly the LP rebuilt from the record's constraints. Joint feasibility of the constraints is proven by a record-level `feasibility` witness.
- **z3 is gone.** It is no longer used by `lio_verify` or `lio_comp`, and `z3-solver` is no longer a dependency. A test runs `lio-verify` with z3, `lio_comp` and `lio` blocked from import.
- All golden bounds are re-certified; their values and open or closed ends are unchanged.

### Added
- Property tests: simplex optimum equals vertex enumeration on random LPs, and certificates are sound. Mutation tests: perturbed dual, perturbed witness, an LP differing from the record, a bound narrowed by 1/10⁶, an empty Motzkin vector and an infeasible feasibility witness all FAIL.

## 2026-11-12: Ingredient coverage for barcode lookups

### Fixed
- **Barcode forms.** Every source is tried with every barcode form (UPC-A, EAN-13, GTIN-14, UPC-E), sharing one verified check digit. A hit is confirmed against the stored barcode, and the form that matched is logged and kept (`matched_forms`).
  - FDC products stored as 12-digit UPCs were missed (Kraft Mac & Cheese).
  - EAN-13 supplements were skipped by DSLD (SuperSmart: no list before, full label now).
- **Open Food Facts.** The longest ingredient list among the languages present is used, and every language is kept. Nutella France went from "sugar, palm oil" to the full French list with its QUID percentages.

### Added
- **NDC from drug UPCs.** A UPC starting with 3 is decoded to its NDC (4-4-2, 5-3-2 and 5-4-1 readings) and looked up in openFDA (by package, then product NDC) and DailyMed. The match is marked as a lead to confirm.
- **DailyMed in name search.** Citrucel Orange's UPC carries a retired NDC (`0068-0418-30`), so name search is what finds its SPL, set `9d5f2244`, for the user to confirm.
- **`ingredient_parts`.** Ingredient information is kept in order, each part with its origin field:
  - drugs: active, inactive and "Other information", with the variants of a multi-product SPL kept apart;
  - DSLD: dietary and other ingredients;
  - Open Food Facts: every language;
  - FDC: the list, with a possible-truncation flag.
- **Evidence.** Raw database answers and web pages read for ingredients are stored by SHA-256 when the comp extra is installed. API keys are removed from recorded URLs.
- **Find online.**
  - The SmartLabel API is used when a Label Insight key is configured; otherwise SmartLabel is a link.
  - GS1 Digital Link pages.
  - Manufacturer pages are flagged.
  - Retailer searches are links only, never fetched.
- **Ingredients panel photo.** The confirmed list is signed by the operator and becomes ATTESTED ingredients in the sample's composition record: photo hash, bounding box, one ingredient per list item. The verifier marks ingredients read from a photo as ATTESTED.
- `tools/ingredient_coverage.py`: a per-source, per-barcode-form coverage report, with before/after comparison (reports in `docs/reports/`).

## 2026-11-11: Verifiable composition, M5 (attestation, badges, training export, docs)

### Added
- Photo attestation flow for food-library samples (`lio_comp.samples`). When a Nutrition Facts photo is saved, the dashboard and the phone show the rows the Mac read. The operator ticks the rows that match the pack (correcting misreads) and signs with their name. The photo is stored by SHA-256, the confirmation is appended to the sample's evidence log, and the sample's record is rebuilt:
  - one ATTESTED fact per row (`image_bbox`, re-parsed by `nfp_row@1`, interpreted with the 101.9(c) rounding rules);
  - per-100 g derivations;
  - the library's database and OCR values in the unverified layer.
  Row boxes come from the server's own OCR, never from the client.
- `ocr.read_label` returns `panel_rows` (Nutrition Facts rows a row rule can read, with pixel boxes) and `image_size`; split OCR lines on one printed row are joined.
- Dashboard: a **Composition** tab in the inspector, verified by `lio-verify` each time it opens, with VERIFIED / ATTESTED / UNVERIFIED / FAILED badges (always with their word), attestations, assumptions, and the unverified estimates kept apart. Also a **Composition for training** export.
- Training export (`lio_comp.export`, `/foods/export/composition.csv`): one row per value with its exact interval, its badge from the verifier, and every assumption it rests on.
- `docs/COMPOSITION_VERIFICATION.md`: record format, running `lio-verify`, reading its report, the attestation flow, the export, rebuilding, and where the implementation departs from the specification.

## 2026-11-11: Verifiable composition, M4 (independent verifier)

### Added
- `lio-verify` (`lio_verify.verify`, `lio_verify.cli`): checks a record against its snapshots and rules only. In order: schema and no JSON floats; source hashes and manifests; every fact (locator, rule, interpretation, pinned rule version); substances and ingredients; derivations; constraints (data conflicts, weight order only on weight-ordered lists, joint feasibility); bounds (witnesses by exact substitution, z3 soundness checks, carried assumptions); attestations; every assumption cited and stated. Each field is VERIFIED, ATTESTED, UNVERIFIED (an input failed) or FAILED; exit code 1 on any FAILED. No network unless `--refetch`, which only reports whether upstream bytes changed. Imports nothing from `lio` or `lio_comp` (tested in a subprocess).
- Mutation tests: a changed source byte, shifted locators (XPath, JSON pointer, list item), altered fact and derivation values, a removed assumption, a tampered witness, a bound narrower than proven (also with a consistent witness: z3 catches it), a JSON float, weight order on an OTC list, a rules version mismatch, a formula not from its source and a bound dropping an assumption all FAIL.
- All four golden records pass.

### Changed
- Sample-identity assumptions are cited by `physical_sample`, so every stated assumption is used somewhere.

## 2026-11-11: Verifiable composition, M3 (deriver and bounder)

### Added
- `lio_verify.expr`: exact evaluation of derivation expressions with units (add, sub, mul, div, neg, min, max, sum, hull, convert, rescale_basis), cited constants (`C:`), element mass fractions from verified formulas (`M:`), literals (`N:`).
- `lio_verify.lp`: linear constraints over unknown ingredient amounts (`eq_within`, `le`, `ge`, `sum_eq`, `ordered_desc`, `positive`), data-consistency checks, and `check_bound` (witnesses by exact substitution, then z3 "nothing beyond the end" checks).
- `lio_comp.bound`: exact min/max with z3 over the reals; open ends get a near-witness within a stated gap. A fresh z3 context per problem keeps the output deterministic; z3-solver is pinned.
- Golden records now carry derivations, constraints and bounds:
  - Citrucel: sucrose + maltodextrin [55/4, 65/4) g; calcium phosphates [199.9, 280.1] mg; potassium citrate; per-100 g values; other ingredients proven in (0.173, 2.767] g per 19 g dose.
  - Jif: peanuts (27.81, 33) g, sugar (0, 3.5) g, salt (0, 0.369) g per 33 g serving.
  - Nutella: sugar [26.6, 56.3] %, palm oil [13, 30.9] %, whey (0, 6.6] %.
  - Nutricost: magnesium consistent with the stated oxide mass; implied MgO purity at least 92.86 %.

## 2026-11-11: Verifiable composition, M2 (extractors, golden-record facts)

### Added
- Locators resolved against the exact snapshot bytes (`lio_verify.locate`): XPath (one node; attribute `fields`), JSON pointer (numbers kept as their literal token, never floats), character span; image boxes are attested only.
- Versioned text rules (`lio_verify.textrules`): a lark grammar for OTC "each ... contains:" statements, "contributes N calories from", FDC label nutrients and serving size, ingredient-list items and QUID percentages (decimal commas handled).
- `lio_comp.record` builds every fact by reading its locator, applying its rule and interpreting the result with a cited rounding rule; `lio_comp.golden` builds four golden records into `composition/records/`:
  - Citrucel Orange (DailyMed SPL v17, product NDC 0135-0089): methylcellulose 2 g per 19 g dose, calcium/potassium/sodium as OTC-rounded intervals (21 CFR 201.70/72/64), energy [55, 65) kcal; every ingredient with its SPL UNII; phosphate and citrate formulas from GSRS.
  - Jif Creamy 16 oz (FDC 2770309): label nutrients as 101.9 intervals. FDC values that are not valid label declarations (fibre and added sugars 2.01 g) are refused and noted.
  - Nutricost Magnesium Oxide (DSLD 223424): magnesium 420 mg and magnesium oxide 750 mg per capsule.
  - Nutella, France (Open Food Facts): QUID hazelnuts 13 %, cocoa 7.4 %, milk powder 6.6 %, nutrition per 100 g.
- Golden sources snapshotted in `composition/sources/` (the USDA API key is used for the request only and never recorded).

## 2026-11-11: Verifiable composition, M1 (rules, exact intervals, schema)

### Added
- `lio_verify` (the independent verifier's kernel): exact `Fraction` intervals with open/closed ends, canonical rational strings, label rounding rules and their exact inverse, atomic weights and element mass fractions as intervals.
- `lio_comp`: content-addressed evidence store (`composition/sources/`), a fetcher, and the rule-table builder.
- `composition/rules/`: FDA rounding 21 CFR 101.9(c) (ties half-up, per the FDA Food Labeling Guide), OTC mineral rounding 21 CFR 201.64/70/72(b), Atwater factors, CIAAW 2024 standard atomic weights, UNII formulas, units, ingredient-list ordering (101.4, 201.66(c)(8), EU 1169/2011 Art. 18) and QUID. Every rule cites a quote by character span in a hashed snapshot.
- `composition/schema/record.schema.json`: values are rational strings, never JSON numbers.
- Property tests (interval soundness and tightness, rounding inverse contains the original) and FDA's own examples. New `comp` extra (lxml, jsonschema, z3-solver, lark); `hypothesis` in `dev`.

## 2026-11-11: Food library, phone app, firmware 2.3.1

### Added
- **Food library** (`lio.foods`, `docs/FOOD_LIBRARY.md`): a phone app (iPhone and Android, served by `lio dashboard`, reachable through a Cloudflare quick tunnel with the VPN on) scans a product's barcode, looks it up and adds a sample. Sources: USDA FoodData Central, NIH DSLD, openFDA, Open Food Facts, a web search fallback with links, and label photos read on the Mac (Apple Vision). Nothing found online is saved without confirmation.
- Dashboard **Database** tab: admin and exports, add a sample, and a library viewer with search, filters, an inspector (overview, manufacturer data, LIO scans, raw data) and side-by-side comparison of spectra.
- `foods` optional dependencies (zxing-cpp, pillow, segno). Library data lives in `data/foods/` (gitignored, with any API keys).
- `docs/COMPOSITION_VERIFICATION_SPEC.md` (LIO-SW-COMP-001 Rev A): the specification for verifiable composition records.

### Changed
- Firmware 2.3.1: runs on the Arduino Nano R4 (Renesas RA4M1) as well as the ATmega328P Nano. The R4 has no DTR reset, so the firmware re-applies the dark state and prints `# BOOT` when the host opens the port. A repeated same-direction jog renews its bound without restarting the speed ramp (2.2.1).

## 2026-11-04: Software I²C on D11/D12 (firmware 2.2.0)

### Changed
- The ADS1115 now runs over a software I²C bus on **D11 (SDA) and D12 (SCL)**, with 4.7 kΩ pull-ups. The bus is open-drain, never driven high. A minimal ADS1115 driver (`softi2c.cpp`, `adc.cpp`) replaces the Adafruit ADS1X15 library, so the firmware needs no libraries (flash 66 %, SRAM 39 %).
- The pin map changed in `lio_hw.yaml`, `electronics/README.md`, `electronics/WIRING_CHECKLIST.md`, `electronics/data/nano_pinmap.csv`, `docs/PROTOCOL.md` and `software/README.md`. Test hints take the pin names from `lio_hw.yaml`.
- `LOOP TEST` reports `not_fitted` without touching any pin (D11 is now SDA). T04.2 SKIPs.
- T03.4: the I²C overhead allowance is now 1.5 ms (provisional). Measured on the hardware: about 1.4 ms.

### Found on the hardware
- T03.1 failed because the ADS1115 module's VDD had a loose breadboard contact: its supply swung between 1.4 and 2 V, and its pull-ups dragged SDA and SCL low. Reseated, the ADC answers on D11/D12. While diagnosing, A4/A5 also read low; whether they are damaged is unconfirmed (see `docs/OPEN_ITEMS_AND_NEXT_STEPS.md`).

## 2026-11-03: I²C line diagnosis (firmware 2.1.0)

### Added
- `I2C DIAG` (firmware 2.1.0): checks SDA and SCL directly: held low, external pull-ups present, SDA–SCL bridged, and whether 0x48 answers at 100 kHz and 400 kHz (`docs/PROTOCOL.md`).
- T03.1 runs it and reports `T03.1/bus` with a plain-language diagnosis. Simulator faults `i2c_bridged` and `i2c_slow`.

### Changed
- The firmware falls back to a 100 kHz I²C clock when the ADS1115 answers only there (slow lines, no pull-ups). T03.1 then WARNs.

## 2026-11-03: Dashboard

### Added
- `lio dashboard`: a local web page to run the tests and see the instrument's state (`docs/TESTING.md` §3):
  - connect to the Nano or the simulator, run any subsystem or the whole system, answer operator questions in the page, stop safely
  - a digital twin (Nano, shift registers, rails, the 16 holes, detectors, ADC, motors, safety) coloured by result, with the evidence behind each part, and Measure / Flash on each hole
  - the overall verdict over the latest result of every test, with its coverage; earlier runs and their reports
- `dashboard:` settings in `lio_hw.yaml` (local address, port, poll rate, flash time).
- The dashboard's board persists between sessions: it is rebuilt from the saved runs in `test_results/` (hardware and simulator apart; Clear results remembered), and each test shows its source run. A **⚡ Wake bank A** button.
- `environment.yml`: the `lio` conda environment for all LIO software (`conda env create -f environment.yml`).

- `POWER WAKE [ms]` (firmware) and `LIODevice.keep_awake()`: holding both motors' coils for 1 s (no steps, nothing moves) wakes power bank A; the host does it when the port opens, before each test and before Measure/Flash, at most every 20 s (`power:` in `lio_hw.yaml`). Simulator fault `bank_a_asleep`.

### Changed
- Firmware: the ADS1115 is looked for again whenever it is needed (`INFO`, every ADC command) until it answers, so a power bank that switches on after the Nano has booted no longer leaves the ADC "missing" until a reset.
- T03.1's failure message and `docs/TESTING.md` point first at power bank A being asleep.
- When the Nano sends no firmware v2 banner, the error says what it sent instead (or that it sent nothing) and that firmware v2 needs flashing, instead of a bare timeout.
- `LIODevice.request_cancel()`: a stop request ends the running test at its next command or wait (the dashboard's Stop). The command line is unchanged.

## 2026-11-03: System test suite and firmware v2 (LIO-SW-TEST-001, M1–M5)

### Added
- `software/firmware/lio_firmware/`: firmware v2, a command-driven protocol (`docs/PROTOCOL.md`) with the safety rules in firmware:
  - power-up dark state and one channel at a time
  - per-rail on-time watchdog and a comms-loss failsafe
  - armed, bounded motor moves with the coils released afterwards
  - bounded legacy jogs for `lio_motor_control.py`
  - flash 72 %, SRAM 51 % of the ATmega328P
- `software/host/`, the `lio` package and command:
  - device API, protocol parser, a simulator with 16 injectable faults
  - the test catalogue T01–T11 (automatic, interactive and motion tests)
  - HTML/Markdown reports with plots, baselines, and the `lio` CLI
- `software/config/lio_hw.yaml`: the hardware description and all test thresholds (provisional until calibrated)
- `docs/TESTING.md`: how to test, the catalogue, and the first-hardware-session checklist
- `docs/proposals/LIO-ELEC-001_firmware_v2_update.md`: proposed text for LIO-ELEC-001 §13–§15 and the appendices (not applied)
- CI (`.github/workflows/ci.yml`):
  - lint, strict typing
  - unit tests, simulator system tests and the fault-injection matrix
  - firmware compile with an SRAM gate

### Changed
- `software/logger/lio_logger.py`: rewritten on the host package for firmware v2. It keeps the same command line, the same `lio_sweep.csv` (byte-compatible) and `lio_sweep.png`.

- `software/control/lio_control.py` renamed `lio_motor_control.py` (contents unchanged).
- The root README's repository-structure section now matches the actual tree.

### Removed (kept in git)
- The TEST_MODE firmware and the original logger: at tag `fw-testmode-v1`.
- `software/firmware/legacy/` (TEST_MODE firmware copy and the old AccelStepper motor sketch, do-not-flash) and `software/logger/legacy/`: at tag `software-legacy-v1`.
- CI's legacy-firmware build step.
- A stray `CAD/creality_print_files/.DS_Store`.

## 2026-11-02: LIO V3 optical head electronics, Rev A

### Added
- `electronics/`:
  - full schematic (`LIO_full_schematic.svg` / `.html`)
  - technical document LIO-ELEC-001 Rev A (`docs/`, PDF and DOCX)
  - BOM, net list, channel map and Nano pin map CSVs (`data/`)
  - wiring checklist
  - schematic and document generator sources (`source/`)
- `software/firmware/lio_firmware/lio_firmware.ino`: test and sweep firmware (5 modes, dark subtraction)
- `software/logger/lio_logger.py`: serial logger with CSV and plot
- `CAD/V3/LIO_V3_dual_detector_plate_v01.scad`: OPT101 + InGaAs detector plate for the optical deck
- `docs/`: project log, design decisions, hardware inventory, optical channel map, LED sourcing, open items
- `images/lio_v3_electronics_schematic.png`, `images/build_photos/2026-11-02_breadboard_prototype.png`
- `CAD/V2`, `CAD/V3` copied from the project Drive folder (if selected during install)

### Changed (relative to earlier build instructions)
- InGaAs photodiode orientation: cathode → TL072 pin 2, anode → GND
- 10 kΩ protection resistor added before ADS1115 A0
- DRV1 current set to the module minimum (≈30 mA)
- Nano powered from USB only (5V pin not connected)
- Firmware selects the MOSFET before enabling CE; adds a dark reading per channel
- Holes 10–11 reserved (SMD 1200 / 1300 nm emitters removed)

### Requires
- Optical deck central window enlarged from Ø24 to ≈Ø34 (reprint)
