# Processing and visualizing LIO food scans: literature review and recommended experiments

**Research date:** 20 November 2026. **Evidence base:** 50 unique original research, methods, author-preprint and primary software records, with duplicate ASCA records merged. The UMAP methods preprint and software paper are two records about one method, not independent validation studies. Abstract-only and full-text access are distinguished in the accompanying evidence matrix. This is a targeted narrative literature search, not a systematic review or a meta-analysis.

**Direct conclusion:** LIO should begin with **matched-geometry, quality-controlled food fingerprints; amplitude-preserving and shape-emphasizing processing in parallel; PCA linked to loadings and original measurements; and within-food versus between-food distance comparisons**. Its distinctive height dimension should then be assessed with curve features and multivariate functional PCA. UMAP, supervised discriminant maps and tensor decompositions are optional research comparisons, not the initial evidence that foods differ.

**What remains unknown:** no actual LIO food-run cubes were available. No literature search can determine which preprocessing separates these particular foods most reliably without independent preparation/day data. This report recommends the strongest starting experiment and the evidence needed to choose a winner.

## 1. What the literature question really is

The useful question is not “which graph produces distinct colored clusters?” It is:

> Which measured food differences remain larger than instrumental, packing, geometry and day-to-day variation, and which display lets us inspect those differences without hiding their origin?

There are three legitimate targets, and they need different processing:

| Target | Information to preserve | Main competing explanation |
|---|---|---|
| Recognize a food as presented | Color, brightness, texture/scattering and spectral response | Cup fill, packing, surface, instrument drift |
| Find spectral-pattern differences less dependent on brightness | Relative response across qualified channels | Normalization artifacts, weak-channel noise |
| Identify composition or ingredients | Features related to independently measured composition | Correlated color/texture, formulation, reference bias |

LIO can start investigating the first two immediately after collecting appropriate controls. The third requires external composition labels, standards and task-specific validation. Neither a separated PCA map nor an apparent “water-sensitive” channel proves a specific ingredient.

### The actual LIO constraints

The reviewed code records signed dark-subtracted counts for 16 LEDs × 2 detectors over height, direction and repeats. But 32 measured cells are not 32 independent spectral bands. The current expectation map is:

| Detector | Signal pairs | Weak pair | Blind pairs |
|---|---|---|---|
| OPT101 | Holes 1–11 | None | 12–16 |
| InGaAs | 8, 9, 12–14 | 15 | 1–7, 10, 11, 16 |

Holes 8/9 measure the same 850/940 nm emitters with two different detectors. Holes 10/11 are broadband white/pink sources, not two narrow 450 nm samples. Hole 16 is blind on both expected detector responses. Keep an optical feature axis of **valid detector–hole pairs**, with diagnostic blind readings available separately.

The height axis changes illumination/collection geometry. It is not a second wavelength axis, not a spatial image, and not a source of independent food observations. A general explanatory model is that a channel integrates emitter output × detector sensitivity × sample/geometry response over wavelength, plus residual artifacts. A broadband source therefore cannot be interpreted as a point reflectance measurement at its nominal peak.

Source of these project facts: [hardware configuration](https://github.com/Brandonio-c/LIO/blob/main/software/config/lio_hw.yaml#L112-L134), [cube/stream schema](https://github.com/Brandonio-c/LIO/blob/main/software/host/src/lio/scan/store.py), [curve processing](https://github.com/Brandonio-c/LIO/blob/main/software/host/src/lio/scan/analysis/data.py), and [optics analysis](https://github.com/Brandonio-c/LIO/blob/main/software/host/src/lio/scan/analysis/optics.py). This review extends the earlier repository review; it does not replace those data-integrity requirements.

## 2. The most relevant experimental evidence

These papers are more useful than generic advice to “use PCA for spectroscopy.” They either use compact food sensors or experimentally test the geometry/preprocessing problems LIO faces.

| Study | What was actually tested | Result relevant to LIO | Transfer limit |
|---|---|---|---|
| **Rady et al., 2020** [S38] | 53 powdered/flake/seed food materials; six sensor heights, seven light levels; 401 wavelengths, 1550–1950 nm | Height changed PCA separation and classifier behavior; SNV/MSC helped some settings. White/dark references were collected by height. | Dense spectra and scan repetitions differ from LIO. Group classification is not trace-allergen detection. |
| **Heydarov et al., 2023** [S02] | Nine food powders/flakes; AS7265x, 18 channels, 410–940 nm; 150 readings/type | Mean channel profiles with variability and multivariate models can reveal sparse-sensor differences. | Independent preparation/day/lot generalization was not established by the reported random measurement split. |
| **Sagita et al., 2025** [S37] | AS7265X coffee species/origins; 18/24/30 configured features | Tested pretreatments did not improve classification in the original abstract. Keep a minimally processed benchmark. | Full sample-independence and validation details were not accessible; reported accuracy is not a LIO forecast. |
| **Rodriguez-Macadaeg et al., 2024** [S01] | Actual nine-LED/InGaAs rice instrument plus simulations using laboratory spectra; held-out rice varieties | Actual milled-rice discrimination was 55.6–61.1%, versus 90.7–100% for the simulated band subset. Simple centering performed comparably to more elaborate pretreatments. | Pesticide screening differs from food identity. Simulated narrow-band success does not establish hardware performance. |
| **Pakuła et al., 2022** [S39] | Six sequential LEDs and photodetector; distance/collimator experiments | A 2 mm distance increase reduced uncollimated signal by 33–47% in that apparatus. Geometry can dwarf subtle material differences. | Fiber-coupled eggshell geometry and numerical effects do not transfer directly. |
| **Huang et al., 2016** [S10] | Eight milk-powder products; 152 plates; controlled powder thickness/backing | Fill thickness changed spectra and underlying-material detectability. | Dense imaging; do not borrow its specific thickness recommendation. |
| **Herath et al., 2023** [S06] | Nine-LED oil transmission fingerprints; separate new-batch validation mixtures | Band-profile overlays are useful, and validation on new physical batches is feasible. | Transmission and image pixels differ from LIO reflectance; pixels are not independent foods. |
| **Delatour et al., 2022** [S03] | Eight miniature spectral sensors; adulterated skimmed-milk powders | Important negative evidence: compact sensors often lacked the sensitivity/specificity needed for the tested fraud tasks. | Do not turn its task-specific fraud levels into a general mass-fraction detection limit. |
| **Ryckewaert et al., 2020** [S46] | Repeated NIR coffee measurements and REP-ASCA | Physical repeatability variation could obscure factor interpretation; a dedicated repeatability-control set was useful. | Do not automatically remove all height/packing variation; it may be part of the intended food phenotype. |

Additional food evidence in the matrix covers apples, fermenting musts, date-fruit trajectories, flour fixtures, LED linearity experiments, and repeated milk measurements. These extend coverage; they are not treated as interchangeable validation of LIO. [S04] [S05] [S07] [S08] [S09] [S47]

**Synthesis:** sparse-channel food discrimination is plausible. Its repeatability, geometry and validation determine whether it is useful. The literature supports neither a universal preprocessing winner nor a universal expectation of clean clusters.

## 3. Recommended processing: preserve three representations

### 3.1 First preserve and qualify the measurements

Keep immutable raw rows and saved analysis. Start with primary down-pass optical visits; inspect up passes and mechanical repetitions separately. Never turn heights/reps into extra food samples.

Preserve signed counts. Flag saturation, dropouts, incompleteness, untrusted geometry, blind cells and weak/noisy channels. Select the common usable feature set using hardware/reference/repeatability evidence, not whichever channels produce the best separation of food labels. Weak InGaAs/h15 data may remain inspectable while being excluded from the initial joint model.

Do not confuse the existing diagnostic 100-count baseline ratio floor with a scientifically validated food-feature threshold. A food feature needs its own repeatability/reference qualification.

For LIO, `net_counts` already subtracts dark. Saved `C` estimates an additional LED-induced electrical component. Do not subtract dark again or assume C removes every artifact.

### 3.2 Representation A: amplitude at common physical geometry

Construct one vector per independently prepared scan:

`X[preparation/run, valid detector–hole pair] = response at a common height`.

Use common measured heights first. If interpolation is needed, label it, restrict it to overlapping support, preserve raw points and validate sensitivity. Match physical surface/optics geometry as well as stage coordinates: a thin PTFE tile and a deeply filled cup can have different effective sample distances at the same `height_hs`.

**Before a trustworthy physical reference exists:** use minimally corrected counts within consistent hardware settings, with detector blocks separate and geometry prominently recorded. This is an instrument-dependent fingerprint.

**High-priority correction experiment:** collect a stable white/PTFE reference through the relevant height range. For qualified sample/reference channels, compare the relative response:

`q_sample,j(h) = [net_sample,j(h) − C_sample,j] / [net_white,j(h) − C_white,j]`.

This is a proposed LIO processing branch, not an already validated radiometric conversion. Evaluate C reliability, compatible gain/timing, denominator strength, reference drift and matching surface geometry. Label the result **reference-relative band response** unless traceable reflectance and the required optical assumptions have been established. Reference calibration experiments and related sequential-LED hardware support investigating this before elaborate chemometrics. [S05] [S35] [S36]

Do not use empty cup as a 100% reflector, black cup as a perfect zero, or peak O/white O measured at different optima as a substitute for same-height calibration. Do not clip negative or >1 ratios merely to create attractive graphs. Invalid ratios need a reason and an available raw view.

### 3.3 Representation B: spectral shape, with amplitude retained

Compare a small prespecified set of challengers:

1. Minimally corrected/reference-relative features with mean centering.
2. Vector-normalized qualified profiles.
3. SNV within a scientifically defensible, consistent feature block.
4. Restrained MSC, only after the simpler alternatives have been assessed.

SNV subtracts each profile's own mean and divides by its own standard deviation. It deliberately removes offset/scale information. It does not calibrate LED power, fix detector response, or distinguish chemical from physical variation.

The original MSC meat work found scatter coefficients related to fat; subsequent gluten/starch work found standard MSC could discard useful analyte information. Therefore brightness/scattering cannot automatically be classified as unwanted variation. Retain an amplitude feature block and correction parameters when investigating normalization. [S29] [S30] [S32]

A seven-channel sparse-IR study found that corrections appropriate to dense spectra did not transfer automatically; additional EMSC terms could degrade the result. Its cartilage modality is different, but its limited-information warning is directly relevant to LIO's handful of SWIR channels. [S34]

### 3.4 Representation C: height-response phenotype

Keep `O, h_opt, modulation, FWHM` and the full curves distinct:

| Feature | Use | Main limitation |
|---|---|---|
| Common-height amplitude | Fixed-geometry comparison | Requires shared, trusted geometry |
| O envelope | Each channel's strongest estimated response | Different channels/foods can contribute different heights |
| Peak height | Reproducible geometric/shape difference | Fill level, datum and mechanics can shift it |
| Width/modulation | Broad vs localized height response | Boundary peaks and low signals undermine interpretation |
| Curve shape | Distinguish responses with similar peak amplitude | Needs common domain, weighting and repeatability |
| Down/up difference | Detect changes during scan/approach effects | Can reflect time, settling or mechanics rather than food chemistry |

Do not label the O envelope a spectrum acquired at one height. Boundary optima and incomplete widths must retain their warnings.

For a compact first model, use only a few reproducible summaries. For a richer next model, use **multivariate functional PCA**, treating each valid channel as a function over height. It can summarize coordinated curve variation, with interpretable loading/eigenfunction curves. Its published method supports multivariate curves and measurement error; its success on LIO remains an experimental question. [S13]

Weight functional comparisons by physical height spacing. Equal weight per recorded point would give densely sampled fine-mode regions extra influence. Use a common supported domain or an explicit missing-domain method; no default endpoint extrapolation.

**Do not automatically align every peak.** Curve registration separates horizontal from vertical variation, but removing a height shift assumes it is nuisance. Preserve original coordinates and estimated shifts; compare any justified alignment as a sensitivity analysis. [S14]

### 3.5 Methods to avoid as defaults

| Method | Why it is a poor default here |
|---|---|
| Wavelength Savitzky–Golay derivatives across hole order | Hole order is not a uniform wavelength sequence; there are large gaps, broadband LEDs and detector changes. Numerical differentiation is possible on irregular grids, but meaningful chemical derivatives are not thereby established. |
| High-order wavelength detrending / elaborate EMSC | Too few independent spectral measurements to justify many nuisance terms; useful food variation can be removed. [S31] [S33] [S34] |
| `log(1/raw_counts)` | Counts are not reflectance; negatives/zeros do not support the transform. Adding epsilon changes weak signals arbitrarily. |
| Automatic full-spectrum reconstruction | No observation supplies the missing wavelengths. Interpolation cannot recover absent absorption bands. |
| Blind-channel imputation | Structurally blind optical pairs are not missing food spectra to reconstruct. |
| Arbitrary nonnegative NMF/tensor preprocessing | Signed measurement noise is real; clipping/offsetting to fit a chosen model can create artifacts. |
| Aggressive outlier removal | A new food, a packing change or a failing channel can all look unusual. Flag, investigate and retain an audit trail. |

Height-axis smoothing is a separate issue from wavelength smoothing. LIO's existing `Cube.curve()` already aggregates duplicates and despikes; saved `smooth` adds another processing layer. Raw marker access is essential.

## 4. The best visual system for seeing food differences

### Rank 1: food × feature heatmap with an exact difference fingerprint

**Best early view, even with a small collection.**

Rows are runs carrying parent preparation and lot IDs, grouped by food with day/lot annotations. Same-cup repeated runs remain visibly linked and do not count as independent preparations. Columns are qualified channel–detector features at the chosen physical height. Separate detector blocks. Show both amplitude and shape representations; state the units/normalization.

Allow ordering by physical channel or similarity. When selecting foods A/B, show their individual preparation profiles, a group summary, and signed B−A channel differences. Visible preparation spread matters more than a smooth mean line.

This builds on established measurement-preserving clustered displays rather than compressing everything into two coordinates. Correlation/shape and amplitude-based ordering must remain separate choices. [S22]

### Rank 2: PCA food map linked to loadings and source curves

**Best initial overview of multiple food profiles.**

- One point per run, carrying parent preparation/lot IDs; color by food and symbol/facet by day/lot. Link technical repeats. Use independent preparations, or independent lots for lot-level claims, as the summary/resampling unit.
- PC1–PC2 plus access to other informative component pairs.
- Explained variance, channel loadings, detector contributions and residuals.
- Recolor the exact same map by day, order, fill and reference drift.
- Select a point/pair to inspect the original fingerprint and height curves.
- Show individuals; do not hide tiny groups behind confident-looking ellipses.

The loadings explain what creates a score difference; a biplot is a low-rank representation, not a complete chemical explanation. [S19]

Run separate detector PCAs before presenting a fused map. Reference correction can reduce numerical scale discrepancies, but autoscaling weak channels can inflate noise. Different centering/scaling choices change the scientific question and feature importance. [S18]

For fusion, state feature scaling and block weights. Equalizing OPT101/InGaAs variance does not establish equal information quality. Some multiblock PCA formulations are equivalent to appropriately normalized concatenated PCA; the label “multiblock” is not an improvement by itself. MFA/consensus approaches become useful when their block contributions are actually inspected. [S20] [S21]

A frozen/versioned PCA model should project future runs into the same coordinate system. Refitting whenever a food is added can rotate/change the map and make visual movement ambiguous.

### Rank 3: original-feature distance matrix and repeatability comparison

**Best check that apparent separation survives outside the scatter plot.**

Show a symmetric run × run distance heatmap with food/day/lot boundaries. Beside it, show distributions or individual distances for:

- Same untouched cup.
- Reload/repack of the same material.
- Same food across day/lot.
- Different foods, including deliberately difficult pairs.

The pairs are dependent; do not count every pair as a new replicate for inference.

| Distance | What it emphasizes | Caveat |
|---|---|---|
| Euclidean on qualified reference-relative amplitudes | Magnitude plus channel pattern | Large-variance features dominate |
| Euclidean after stated variable scaling | Relative standardized departures | Weak/noisy channels may be amplified |
| Correlation | Pattern after offset/scale removal | Bright/dark foods can look similar; near-flat vectors are unstable |
| Cosine/spectral angle | Direction rather than total vector magnitude | Does not correct channel-specific response/gain or offsets |
| Functional distance over height | Entire response shape/amplitude | Needs domain/height weighting and explicit channel weights |

Do not default to an unrestricted Mahalanobis covariance estimate with few independent preparations and hundreds of correlated height features.

### Rank 4: channel × height difference maps and functional-PC displays

For a selected food pair, plot B−A versus height for each qualified channel, with individual preparations available. Facet detectors and use consistent scales within the comparison. This can show that two foods differ only over part of travel even when their peak envelopes overlap.

After functional PCA, plot the mean curve plus/minus component perturbations and channel × height loadings. This answers “which channels and heights drive this food axis?” more directly than a 3D surface. [S13]

### Rank 5: UMAP; t-SNE only as an additional sensitivity view

UMAP/t-SNE are legitimate neighborhood visualizers, but their islands are not independent evidence of distinct foods. Original methods and controlled embedding experiments show how objective, neighborhood scale, attraction/repulsion and initialization change appearance. [S23] [S24] [S25] [S26] [S27] [S28]

If offered:

- Use the already qualified representation and stated metric.
- Show sensitivity to neighborhood parameters and seeds.
- Compare neighborhoods with the original-feature distance matrix.
- Preserve the same food/day/lot annotation controls.
- Do not interpret island area as food variability or island spacing as chemical distance.
- Do not select the preprocessing because this map looks most separated.

There is no defensible universal minimum sample count for “UMAP works” in this dataset. With only a few independent preparations, the original fingerprints and PCA are easier to audit.

### Supervised visualizations: a different question

PLS-DA/LDA may later help test classification. Their fitted score plots must not be the headline evidence that foods are naturally distinct: a classic empirical study obtained visually separated PLS-DA groups from arbitrary labels. [S42]

If classification is desired, present grouped held-out predictions/confusion, with the entire tuned preprocessing/height/feature-selection procedure inside validation. A supervised projection can then be labeled as such. [S43] [S44] [S45]

## 5. How to determine which pipeline is actually best

### A staged, cost-aware collection experiment

The following is a proposed engineering pilot, not a statistically powered sample-size prescription.

**Pilot:** choose four powder foods: two plausible near-neighbors and two contrasting references. For each food, independently refill/repack twice on each of two days, with every food represented on every day and acquisition order interleaved. This is 16 full food scans, plus hardware/reference controls.

At a planning assumption near 40 minutes per full scan, the food scans alone require roughly 11 instrument-hours. Actual duration and control overhead must be checked on the rig. If constrained, reduce the number of foods before replacing independent preparations with many untouched-cup repeats.

Include a small controlled nuisance set: immediate same-cup repeat, unload/reload/repack, and repeated stable reference. These estimate different errors. Independent lots/packages come next; a new preparation from one package does not establish new-lot robustness.

Record material identity, package/lot, preparation ID, day/order, cup/nest, fill depth or mass, packing treatment, lid/datum, reference IDs, settings and interventions. Same stage coordinate does not guarantee the same surface distance. Proposed analysis metadata such as food_label/product_id, lot_id, parent_sample_id and preparation_id should remain separate from run_id and the existing sample_id; define whether the target is a particular item, product or general food class.

Powder-replacement/tapping work, controlled-depth food experiments and coffee repeatability analysis support this emphasis on physical sampling. Their exact experimental settings are not copied. [S10] [S41] [S46]

### Compare a small set of defined pipelines

| Pipeline | Representation | Purpose |
|---|---|---|
| A0 | Minimally corrected common-height features | Honest low-processing benchmark |
| A1 | Qualified same-height reference-relative features | Test whether physical referencing improves stability |
| B1 | A1 plus vector normalization or restrained SNV | Test shape discrimination while retaining amplitude separately |
| C1 | A1 plus a small reproducible curve-summary block | Test whether the height sweep adds information |
| C2, later | Weighted multivariate functional PCA | Test coordinated full-curve information |

Compare detector-specific results with a documented joint representation. Do not explore dozens of transformations and retain only the prettiest picture.

Ask whether the selected pipeline:

1. Keeps same-food independent preparations closer than relevant different foods across days.
2. Distinguishes difficult pairs in source features, not only an embedding.
3. Remains stable to reasonable scaling, channel exclusions and processing choices.
4. Avoids organizing chiefly by day/order/fill or a failing detector.
5. Uses reproducible heights/features and preserves honest quality limitations.
6. Projects a new day/preparation into a frozen map consistently.

The result may be that amplitude works for some foods, shape for others, and height adds little for a particular task. Do not force one global winner.

### Validation boundary

For descriptive exploration, fitting PCA to the full pilot collection is legitimate if labeled exploratory. For a claim about new scans, fit centering/scaling, MSC references, supervised feature/height selection and learned projections using training material only, then apply them to held-out independent groups.

Keep all related measurements of a preparation together; test new days/lots when those are the intended deployment conditions. Random row splitting is especially misleading when a scan supplies hundreds of correlated readings.

A recent 2026 AS7265x milk study used physically diluted samples and averaged consecutive readings, but reported shuffled cross-validation/leave-one-prepared-sample-out rather than demonstrated new-parent-milk/day/field validation. This is a useful example of why “LOO” alone does not establish deployment robustness. Related-material leakage is a concern to resolve, not something this review claims to have proven in that study. [S50]

Once enough independent replicated data exist, quantify food-group center and spread separately. Large preparation spread can create misleading distance/cluster interpretations. Any permutation/bootstrap must respect experimental grouping; ADC counts are voltage encodings, not automatically Poisson event counts. [S48] [S49]

### Designed-effects analysis later

Use ASCA or an appropriate repeated/nested extension to ask how much variation belongs to food, day, preparation and their interactions. Original ASCA decomposes designed effects, and a cheddar Raman/MIR study provides a food-data-fusion precedent. It cannot disentangle food from day if those factors were never crossed. [S11] [S12]

REP-ASCA or other nuisance projection is worth investigating after controlled repeatability experiments. Projecting away “unwanted” directions learned from a mixture of food identities could erase the food signal itself.

## 6. Why tensor models and automatic alignment are later work

A sample × valid-channel × height array is a useful organization. It does not establish a trilinear physical mixture model.

CP/PARAFAC assumes particular shared factor structure; food-dependent scattering/peak shifts may violate it. Tucker is more flexible but introduces additional parameters and interpretation choices. Structural diagnostics, rank stability, repeated initializations, residual maps and held-out-run reconstruction are necessary comparisons. Latent components cannot simply be named ingredients. [S15] [S16]

Incomplete-tensor methods can fit observed entries without zero-filling ordinary missing measurements. That does not make a detector-blind LED pair a recoverable spectrum. Removing structural blind optical pairs is usually the more defensible starting point. [S17]

Compared with those models, a few curve summaries and functional PCA expose their relation to physical height more directly. This is a LIO-specific recommendation by inference, not a published head-to-head benchmark on this apparatus.

## 7. Additional optical caveats worth testing

- **UV/violet fluorescence:** food-oil experiments produce visible fluorescence under 405 nm excitation. Because OPT101 is broadband, an LIO UV/violet measurement could contain fluorescence as well as reflected excitation. Its magnitude in LIO is unknown. Treat it as a testable interpretation caveat, not a proven fault or an established fluorescence feature. [S40]
- **Sample mode:** powders, opaque solids, clear oils and translucent liquids have different optical paths. Do not assume one reference or preprocessing recipe makes them directly comparable.
- **Illumination and collection footprints:** LED positions/beam shapes can make channel differences geometry-dependent. White reference ratios reduce some effects; they do not reconstruct a continuous spectrum or guarantee chemical specificity.
- **Reference records:** retain full reference-run identity and provenance. Compact scan baselines keep O and smoothed curves, not the raw cube, C, all repetitions or streams; they are insufficient to recreate every proposed normalization.
- **Hardware changes:** channel replacements, LED spectra, detector gain changes and stage re-zeroing define instrument versions. Keep maps/reference models versioned and test transfer rather than silently merging incompatible scans.
- **No assumed composition:** a spectral separation can reflect color or texture; failure to separate can reflect weak hardware, noise, insufficient bands or genuinely similar foods. Neither outcome alone establishes composition equality/difference.

## 8. Concrete recommendation for an implementation agent

Build these capabilities in this order:

1. A run-level feature exporter that preserves raw/corrected/shape/curve-summary provenance, independent-preparation metadata and availability masks.
2. A food × channel heatmap and linked A/B difference fingerprint at shared physical height.
3. A frozen/versioned PCA view with loadings, individual preparations, food/day/lot controls and detector contributions.
4. An original-space distance matrix comparing within-food variability to between-food differences.
5. Selected-pair channel × height differences, followed by functional PCA if full curves provide repeatable additional information.
6. UMAP and advanced nuisance/tensor methods as documented comparisons.

Keep the existing single-run diagnostic heatmaps, raw traces and saved findings as the route back to instrument health. They explain whether a food-map outlier is a material difference or an acquisition problem.

**Best defensible starting pipeline:** qualified primary-pass nets → matched-height reference-relative response where valid → parallel amplitude/shape representations → PCA/loadings + feature/distance heatmaps → independent preparation/day checks → full-curve functional analysis if warranted.

## 9. Search scope and evidence limits

Searches covered scholarly web results, PubMed/PMC, original publisher records, JMLR/JSS, author manuscripts and method repositories. We searched compact/discrete-LED food instruments, food powder height/packing effects, white/dark calibration, SNV/MSC/EMSC, sparse-spectrum preprocessing, PCA/scaling/biplots/multiblock methods, curve/functional/tensor methods, ASCA/repeatability and validation of visual separation.

Representative exact search strings included:

- “The Effect of Light Intensity Sensor Height Spectral Pre-Processing powdered foods”
- “food LED multispectral spectrometer classification low cost reflectance”
- “AS7265x food classification spectroscopy study”
- “2026 multispectral food sensor low cost PCA AS7265x AS7341”
- “Preprocessing Strategies for Sparse Infrared Spectroscopy”
- “normalization spectroscopy removes chemical information SNV MSC”
- “Westerhuis Assessment of PLSDA cross validation”
- “REP-ASCA NIR coffee repeatability”
- “Multivariate Functional Principal Component Analysis for Data Observed on Different”
- “ASCA cheese spectroscopy”
- “Attraction-Repulsion Spectrum in Neighbor Embeddings”

We followed references to foundational original methods and checked newer compact-sensor work through the search date. Reviews and commercial summaries served only as discovery aids; secondary reviews and one remote-domain phase example were excluded from the core 50-record matrix. Publisher failures, abstracts, indexed original passages and inspected author versions are identified explicitly. The source count measures documentary coverage, not 50 independent food-device validations or 50 papers read in full.

No PRISMA flow count, exhaustive database export, meta-analytic pooling, universal optimum preprocessing, LIO classification accuracy or empirical LIO separation is claimed. The supplied GitHub full-run example was not tracked/available, and no measured LIO food data were fabricated.

## 10. Annotated bibliography

The accompanying CSV has one row per retained record, including experimental setting, result, LIO applicability, limitations and access level. Below are the citation keys used in this report.


- **S01. Fatima Rodriguez-Macadaeg; Paul R. Armstrong; Elizabeth B. Maghirang; Erin D. Scully; Daniel L. Brabec; Frank H. Arthur; Arlene D. Adviento-Borbe; Kevin F. Yaptenco; Delfin C. Suministrado (2024). [Developing a Multi-Spectral NIR LED-Based Instrument for the Detection of Pesticide Residues Containing Chlorpyrifos-Methyl in Rough, Brown, and Milled Rice](https://www.mdpi.com/1424-8220/24/13/4055).** DOI: 10.3390/s24134055. Access: Full publisher text retrieved; PMC intermittently blocked..

- **S02. Saddam Heydarov; Musa Aydin; Cagri Faydaci; Suha Tuna; Sadullah Ozturk (2023). [Low-cost VIS/NIR range hand-held and portable photospectrometer and evaluation of machine learning algorithms for classification performance](https://doi.org/10.1016/j.jestch.2022.101302).** DOI: 10.1016/j.jestch.2022.101302. Access: Publisher returned 403; complete author-uploaded original PDF read on ResearchGate; publication metadata verified..

- **S03. Thierry Delatour; Florian Becker; Julius Krause; Roman Romero; Robin Gruna; Thomas Längle; Alexandre Panchaud (2022). [Handheld Spectral Sensing Devices Should Not Mislead Consumers as Far as Non-Authentic Food Is Concerned: A Case Study with Adulteration of Milk Powder](https://pmc.ncbi.nlm.nih.gov/articles/PMC8750415/).** DOI: 10.3390/foods11010075. Access: PubMed abstract and primary indexed fragments retrieved; direct full text blocked by 429/PMC challenge. Online 2021; volume 11 (2022)..

- **S04. Nhut-Thanh Tran; Masayuki Fukuzawa (2020). [A Portable Spectrometric System for Quantitative Prediction of the Soluble Solids Content of Apples with a Pre-calibrated Multispectral Sensor Chipset](https://pmc.ncbi.nlm.nih.gov/articles/PMC7589226/).** DOI: 10.3390/s20205883. Access: Primary indexed methods and abstract retrieved; direct PMC challenge and publisher PDF content-type failure..

- **S05. Raffaele Civelli; Valentina Giovenzana; Ezio Naldi; Riccardo Guidetti; Roberto Oberti (2015). [A Simplified, Light Emitting Diode (LED) Based, Modular System to be Used for the Rapid Evaluation of Fruit and Vegetable Quality: Development and Validation on Dye Solutions](https://pmc.ncbi.nlm.nih.gov/articles/PMC4610431/).** DOI: 10.3390/s150922705. Access: Extensive primary indexed passages retrieved; direct PMC challenge and publisher timeout..

- **S06. Sanjaya Herath; Hashan Kavinga Weerasooriya; Don Yasiru Lakshan Ranasinghe; Wele Gedara Chaminda Bandara; Vijitha Rohana Herath; Roshan Indika Godaliyadda; Mervyn Parakrama Bandara Ekanayake; Terrence Madhujith (2023). [Quantitative assessment of adulteration of coconut oil using transmittance multispectral imaging](https://pmc.ncbi.nlm.nih.gov/articles/PMC10076459/).** DOI: 10.1007/s13197-023-05697-0. Access: Full PMC text retrieved..

- **S07. Gianmarco Alfieri; Margherita Modesti; Andrea Bellincontro; Francesco Renzi; Jose Luis Aleixandre-Tudo (2025). [Feasibility assessment of a low-cost visible spectroscopy-based prototype for monitoring polyphenol extraction in fermenting musts](https://pmc.ncbi.nlm.nih.gov/articles/PMC11726600/).** DOI: 10.1002/jsfa.13274. Access: Full PMC text retrieved. Online 2024; issue 2025..

- **S08. Oscar Jossa-Bastidas; Ainhoa Osa-Sanchez; Leire Bravo-Lamas; Begonya García-Zapirain (2023). [IoT System for Gluten Prediction in Flour Samples Using NIRS Technology, Deep and Machine Learning Techniques](https://www.mdpi.com/2079-9292/12/8/1916).** DOI: 10.3390/electronics12081916. Access: Primary indexed PDF methods and abstract retrieved; direct publisher access blocked..

- **S09. Ramasamy Srinivasagan; Maged Mohammed; Ali Alzahrani (2023). [TinyML-Sensor for Shelf Life Estimation of Fresh Date Fruits](https://www.mdpi.com/1424-8220/23/16/7081).** DOI: 10.3390/s23167081. Access: Full publisher text retrieved..

- **S10. Min Huang; Moon S. Kim; Kuanglin Chao; Jianwei Qin; Changyeun Mo; Carlos Esquerre; Stephen Delwiche; Qibing Zhu (2016). [Penetration Depth Measurement of Near-Infrared Hyperspectral Imaging Light for Milk Powder](https://pmc.ncbi.nlm.nih.gov/articles/PMC4850955/).** DOI: 10.3390/s16040441. Access: Full PMC text retrieved..

- **S11. Age K. Smilde; Jeroen J. Jansen; Huub C. J. Hoefsloot; Robert-Jan A. N. Lamers; Jan van der Greef; Marieke E. Timmerman (2005). [ANOVA-simultaneous component analysis (ASCA): a new tool for analyzing designed metabolomics data](https://pubmed.ncbi.nlm.nih.gov/15890747/).** DOI: 10.1093/bioinformatics/bti476. Access: Primary abstract; publisher full text inaccessible.

- **S12. P. Firmani; R. Vitale; C. Ruckebusch; F. Marini (2020). [ANOVA-Simultaneous Component analysis modelling of low-level-fused spectroscopic data: A food chemistry case-study](https://pubmed.ncbi.nlm.nih.gov/32674778/).** DOI: 10.1016/j.aca.2020.05.059. Access: Primary abstract and author-manuscript metadata; full publisher text inaccessible.

- **S13. Clara Happ; Sonja Greven (2018). [Multivariate Functional Principal Component Analysis for Data Observed on Different (Dimensional) Domains](https://arxiv.org/abs/1509.02029).** DOI: 10.1080/01621459.2016.1273115. Access: Full author preprint retrieved https://arxiv.org/pdf/1509.02029.

- **S14. J. O. Ramsay; Xiaochun Li (1998). [Curve Registration](https://academic.oup.com/jrsssb/article-abstract/60/2/351/7083122).** DOI: 10.1111/1467-9868.00129. Access: Publisher-indexed summary; full article endpoint failed.

- **S15. Ledyard R. Tucker (1966). [Some Mathematical Notes on Three-Mode Factor Analysis](https://doi.org/10.1007/BF02289464).** DOI: 10.1007/BF02289464. Access: Publisher abstract and metadata, not full article.

- **S16. Rasmus Bro; Henk A. L. Kiers (2003). [A new efficient method for determining the number of components in PARAFAC models](https://analyticalsciencejournals.onlinelibrary.wiley.com/doi/10.1002/cem.801).** DOI: 10.1002/cem.801. Access: Publisher abstract.

- **S17. Evrim Acar; Daniel M. Dunlavy; Tamara G. Kolda; Morten Mørup (2011). [Scalable tensor factorizations for incomplete data](https://arxiv.org/abs/1005.2197).** DOI: 10.1016/j.chemolab.2010.08.004. Access: Full author preprint https://arxiv.org/pdf/1005.2197.

- **S18. Robert A. van den Berg; Huub C. J. Hoefsloot; Johan A. Westerhuis; Age K. Smilde; Mariët J. van der Werf (2006). [Centering, scaling, and transformations: improving the biological information content of metabolomics data](https://pmc.ncbi.nlm.nih.gov/articles/PMC1534033/).** DOI: 10.1186/1471-2164-7-142. Access: Full primary text retrieved via indexed PMC result..

- **S19. K. R. Gabriel (1971). [The biplot graphic display of matrices with application to principal component analysis](https://doi.org/10.1093/biomet/58.3.453).** DOI: 10.1093/biomet/58.3.453. Access: Publisher abstract; full article paywalled..

- **S20. Sébastien Lê; Julie Josse; François Husson (2008). [FactoMineR: An R Package for Multivariate Analysis](https://www.jstatsoft.org/article/view/v025i01).** DOI: 10.18637/jss.v025.i01. Access: Primary journal landing page retrieved; PDF route attempted..

- **S21. Bradley Worley; Robert Powers (2015). [A Sequential Algorithm for Multiblock Orthogonal Projections to Latent Structures](https://pmc.ncbi.nlm.nih.gov/articles/PMC4668594/).** DOI: 10.1016/j.chemolab.2015.10.018. Access: Full primary author manuscript retrieved..

- **S22. Michael B. Eisen; Paul T. Spellman; Patrick O. Brown; David Botstein (1998). [Cluster analysis and display of genome-wide expression patterns](https://pmc.ncbi.nlm.nih.gov/articles/PMC24541/).** DOI: 10.1073/pnas.95.25.14863. Access: Full primary indexed text retrieved; later direct open hit CAPTCHA..

- **S23. Laurens van der Maaten; Geoffrey Hinton (2008). [Visualizing Data using t-SNE](https://www.jmlr.org/papers/v9/vandermaaten08a.html).** No DOI verified in the inspected record. Access: Full canonical journal PDF retrieved..

- **S24. Leland McInnes; John Healy; James Melville (2018). [UMAP: Uniform Manifold Approximation and Projection for Dimension Reduction](https://arxiv.org/abs/1802.03426).** DOI: 10.48550/arXiv.1802.03426. Access: Author preprint abstract retrieved; version revised 2020..

- **S25. Leland McInnes; John Healy; Nathaniel Saul; Lukas Großberger (2018). [UMAP: Uniform Manifold Approximation and Projection](https://joss.theoj.org/papers/10.21105/joss.00861).** DOI: 10.21105/joss.00861. Access: Primary JOSS record retrieved..

- **S26. Jan Niklas Böhm; Philipp Berens; Dmitry Kobak (2022). [Attraction-Repulsion Spectrum in Neighbor Embeddings](https://www.jmlr.org/papers/v23/21-0055.html).** No DOI verified in the inspected record. Access: Primary JMLR and author-arXiv abstracts retrieved..

- **S27. Martin Wattenberg; Fernanda Viégas; Ian Johnson (2016). [How to Use t-SNE Effectively](https://distill.pub/2016/misread-tsne/).** DOI: 10.23915/distill.00002. Access: Full primary interactive article retrieved..

- **S28. Dmitry Kobak; George C. Linderman (2021). [Initialization is critical for preserving global data structure in both t-SNE and UMAP](https://pubmed.ncbi.nlm.nih.gov/33526945/).** DOI: 10.1038/s41587-020-00809-z. Access: Final metadata verified in PubMed; experimental content read in 2019 author preprint DOI10.1101/2019.12.19.877522..

- **S29. P. Geladi; D. MacDougall; H. Martens (1985). [Linearization and Scatter-Correction for Near-Infrared Reflectance Spectra of Meat](https://opg.optica.org/as/abstract.cfm?uri=as-39-3-491).** DOI: 10.1366/0003702854248656. Access: abstract.

- **S30. R. J. Barnes; M. S. Dhanoa; S. J. Lister (1989). [Standard Normal Variate Transformation and De-trending of Near-Infrared Diffuse Reflectance Spectra](https://opg.optica.org/as/abstract.cfm?uri=as-43-5-772).** DOI: 10.1366/0003702894202201. Access: abstract.

- **S31. H. Martens; E. Stark (1991). [Extended multiplicative signal correction and spectral interference subtraction: New preprocessing methods for near infrared spectroscopy](https://pubmed.ncbi.nlm.nih.gov/1790182/).** DOI: 10.1016/0731-7085(91)80188-F. Access: abstract.

- **S32. H. Martens; J. P. Nielsen; S. B. Engelsen (2003). [Light scattering and light absorbance separated by extended multiplicative signal correction. Application to near-infrared transmission analysis of powder mixtures](https://pubmed.ncbi.nlm.nih.gov/12585463/).** DOI: 10.1021/ac020194w. Access: abstract.

- **S33. J. H. Solheim; B. Zimmermann; V. Tafintseva; S. Dzurendová; V. Shapaval; A. Kohler (2022). [The Use of Constituent Spectra and Weighting in Extended Multiplicative Signal Correction in Infrared Spectroscopy](https://pmc.ncbi.nlm.nih.gov/articles/PMC8948808/).** DOI: 10.3390/molecules27061900. Access: fulltext.

- **S34. V. Tafintseva; T. A. Lintvedt; J. H. Solheim; B. Zimmermann; H. U. Rehman; V. Virtanen; R. Shaikh; E. Nippolainen; I. Afara; S. Saarakkala; L. Rieppo; P. Krebs; P. Fomina; B. Mizaikoff; A. Kohler (2022). [Preprocessing Strategies for Sparse Infrared Spectroscopy: A Case Study on Cartilage Diagnostics](https://pmc.ncbi.nlm.nih.gov/articles/PMC8839829/).** DOI: 10.3390/molecules27030873. Access: fulltext.

- **S35. M. S. Shaikh; K. Jaferzadeh; B. Thörnberg; J. Casselgren (2021). [Calibration of a Hyper-Spectral Imaging System Using a Low-Cost Reference](https://pmc.ncbi.nlm.nih.gov/articles/PMC8199474/).** DOI: 10.3390/s21113738. Access: fulltext.

- **S36. N. Modir; M. Shahedi; J. Dormer; L. Ma; B. Fei (2025). [LED-based, real-time, hyperspectral imaging device](https://pmc.ncbi.nlm.nih.gov/articles/PMC12162177/).** DOI: 10.1117/1.JMI.12.3.035002. Access: fulltext.

- **S37. D. Sagita; S. Widodo; S. S. Mardjan; P. B. Purwandoko; Suparlan; H. Hariadi; S. Darniadi (2025). [Rapid identification of coffee species and origin using affordable multi-channel spectral sensor combined with machine learning](https://pubmed.ncbi.nlm.nih.gov/40356157/).** DOI: 10.1016/j.foodres.2025.116501. Access: abstract.

- **S38. Ahmed Rady; Joel Fischer; Stuart Reeves; Brian Logan; Nicholas James Watson (2020). [The Effect of Light Intensity, Sensor Height, and Spectral Pre-Processing Methods When Using NIR Spectroscopy to Identify Different Allergen-Containing Powdered Foods](https://pmc.ncbi.nlm.nih.gov/articles/PMC6982964/).** DOI: 10.3390/s20010230. Access: Full original text; online 2019, issue 2020.

- **S39. Anna Pakuła; Wojciech Żołnowski; Sławomir Paśko; Olimpia Kursa; Paweł Marć; Leszek R. Jaroszewicz (2022). [Multispectral Portable Fibre-Optic Reflectometer for the Classification of the Origin of Chicken Eggshells in the Case of Mycoplasma synoviae Infections](https://pmc.ncbi.nlm.nih.gov/articles/PMC9692302/).** DOI: 10.3390/s22228690. Access: Full original text.

- **S40. Carla Regina Borges Lopes et al. (2023). [Evaluation of Steady-State and Time-Resolved Fluorescence Spectroscopy as a Method for Assessing the Impact of Photo-Oxidation on Refined Soybean Oils](https://pubmed.ncbi.nlm.nih.gov/37174400/).** DOI: 10.3390/foods12091862. Access: Original abstract and figure captions.

- **S41. T. Sakamoto; Y. Fujimaki; Y. Hiyama (2007). [Studies on the influence of uniformity of particle size of powder, tapping and sample replacement for diffusion reflectance quantitative NIR spectrometric analysis](https://pubmed.ncbi.nlm.nih.gov/18065100/).** No DOI verified in the inspected record. Access: Original abstract.

- **S42. J. A. Westerhuis; H. C. J. Hoefsloot; S. Smit; D. J. Vis; A. K. Smilde; E. J. J. van Velzen; J. P. M. van Duijnhoven; F. A. van Dorsten (2008). [Assessment of PLSDA cross validation](https://link.springer.com/article/10.1007/s11306-007-0099-6).** DOI: 10.1007/s11306-007-0099-6. Access: Full text.

- **S43. E. Szymańska; E. Saccenti; A. K. Smilde; J. A. Westerhuis (2012). [Double-check: validation of diagnostic statistics for PLS-DA models in metabolomics studies](https://pmc.ncbi.nlm.nih.gov/articles/PMC3337399/).** DOI: 10.1007/s11306-011-0330-3. Access: Full text; online 2011.

- **S44. S. Varma; R. Simon (2006). [Bias in error estimation when using cross-validation for model selection](https://pmc.ncbi.nlm.nih.gov/articles/PMC1397873/).** DOI: 10.1186/1471-2105-7-91. Access: Primary text retrieved; subsequent anti-bot challenge.

- **S45. R. Bro; K. Kjeldahl; A. K. Smilde; H. A. L. Kiers (2008). [Cross-validation of component models: a critical look at current methods](https://pubmed.ncbi.nlm.nih.gov/18214448/).** DOI: 10.1007/s00216-007-1790-1. Access: Primary abstract.

- **S46. M. Ryckewaert; N. Gorretta; F. Henriot; F. Marini; J.-M. Roger (2020). [Reduction of repeatability error for analysis of variance–Simultaneous Component Analysis (REP-ASCA): Application to NIR spectroscopy on coffee sample](https://pubmed.ncbi.nlm.nih.gov/32029115/).** DOI: 10.1016/j.aca.2019.12.024. Access: Primary abstract.

- **S47. M. Majadi; A. Barkó; A. Varga-Tóth; Z. S. Maukenovna; D. Z. Batirkhanovna; S. Dilora; M. Lukacs; T. Kaszab; Z. Mednyánszky; Z. Kovacs (2024). [Quality Assessment of Reconstructed Cow, Camel and Mare Milk Powders by Near-Infrared Spectroscopy and Chemometrics](https://www.mdpi.com/1420-3049/29/17/3989).** DOI: 10.3390/molecules29173989. Access: Full text.

- **S48. M. J. Anderson (2006). [Distance-Based Tests for Homogeneity of Multivariate Dispersions](https://academic.oup.com/biometrics/article-abstract/62/1/245/7306369).** DOI: 10.1111/j.1541-0420.2005.00440.x. Access: Primary abstract.

- **S49. D. I. Warton; S. T. Wright; Y. Wang (2012). [Distance-based multivariate analyses confound location and dispersion effects](https://besjournals.onlinelibrary.wiley.com/doi/10.1111/j.2041-210X.2011.00127.x).** DOI: 10.1111/j.2041-210X.2011.00127.x. Access: Full text; online 2011.

- **S50. A. Ç. Seçkin; M. Ekici; T. Akcan; F. Soygazi; H. Gürsoy Demir (2026). [XAI-Supported Electronic Tongue for Estimating Milk Composition and Adulteration Indicators](https://pmc.ncbi.nlm.nih.gov/articles/PMC13204219/).** DOI: 10.3390/bios16050245. Access: Full text.

[S01]: https://www.mdpi.com/1424-8220/24/13/4055
[S02]: https://doi.org/10.1016/j.jestch.2022.101302
[S03]: https://pmc.ncbi.nlm.nih.gov/articles/PMC8750415/
[S04]: https://pmc.ncbi.nlm.nih.gov/articles/PMC7589226/
[S05]: https://pmc.ncbi.nlm.nih.gov/articles/PMC4610431/
[S06]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10076459/
[S07]: https://pmc.ncbi.nlm.nih.gov/articles/PMC11726600/
[S08]: https://www.mdpi.com/2079-9292/12/8/1916
[S09]: https://www.mdpi.com/1424-8220/23/16/7081
[S10]: https://pmc.ncbi.nlm.nih.gov/articles/PMC4850955/
[S11]: https://pubmed.ncbi.nlm.nih.gov/15890747/
[S12]: https://pubmed.ncbi.nlm.nih.gov/32674778/
[S13]: https://arxiv.org/abs/1509.02029
[S14]: https://academic.oup.com/jrsssb/article-abstract/60/2/351/7083122
[S15]: https://doi.org/10.1007/BF02289464
[S16]: https://analyticalsciencejournals.onlinelibrary.wiley.com/doi/10.1002/cem.801
[S17]: https://arxiv.org/abs/1005.2197
[S18]: https://pmc.ncbi.nlm.nih.gov/articles/PMC1534033/
[S19]: https://doi.org/10.1093/biomet/58.3.453
[S20]: https://www.jstatsoft.org/article/view/v025i01
[S21]: https://pmc.ncbi.nlm.nih.gov/articles/PMC4668594/
[S22]: https://pmc.ncbi.nlm.nih.gov/articles/PMC24541/
[S23]: https://www.jmlr.org/papers/v9/vandermaaten08a.html
[S24]: https://arxiv.org/abs/1802.03426
[S25]: https://joss.theoj.org/papers/10.21105/joss.00861
[S26]: https://www.jmlr.org/papers/v23/21-0055.html
[S27]: https://distill.pub/2016/misread-tsne/
[S28]: https://pubmed.ncbi.nlm.nih.gov/33526945/
[S29]: https://opg.optica.org/as/abstract.cfm?uri=as-39-3-491
[S30]: https://opg.optica.org/as/abstract.cfm?uri=as-43-5-772
[S31]: https://pubmed.ncbi.nlm.nih.gov/1790182/
[S32]: https://pubmed.ncbi.nlm.nih.gov/12585463/
[S33]: https://pmc.ncbi.nlm.nih.gov/articles/PMC8948808/
[S34]: https://pmc.ncbi.nlm.nih.gov/articles/PMC8839829/
[S35]: https://pmc.ncbi.nlm.nih.gov/articles/PMC8199474/
[S36]: https://pmc.ncbi.nlm.nih.gov/articles/PMC12162177/
[S37]: https://pubmed.ncbi.nlm.nih.gov/40356157/
[S38]: https://pmc.ncbi.nlm.nih.gov/articles/PMC6982964/
[S39]: https://pmc.ncbi.nlm.nih.gov/articles/PMC9692302/
[S40]: https://pubmed.ncbi.nlm.nih.gov/37174400/
[S41]: https://pubmed.ncbi.nlm.nih.gov/18065100/
[S42]: https://link.springer.com/article/10.1007/s11306-007-0099-6
[S43]: https://pmc.ncbi.nlm.nih.gov/articles/PMC3337399/
[S44]: https://pmc.ncbi.nlm.nih.gov/articles/PMC1397873/
[S45]: https://pubmed.ncbi.nlm.nih.gov/18214448/
[S46]: https://pubmed.ncbi.nlm.nih.gov/32029115/
[S47]: https://www.mdpi.com/1420-3049/29/17/3989
[S48]: https://academic.oup.com/biometrics/article-abstract/62/1/245/7306369
[S49]: https://besjournals.onlinelibrary.wiley.com/doi/10.1111/j.2041-210X.2011.00127.x
[S50]: https://pmc.ncbi.nlm.nih.gov/articles/PMC13204219/
