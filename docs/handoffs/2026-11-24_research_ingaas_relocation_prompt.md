# Research handoff: should the InGaAs detector move to capture reflected SWIR better?

**Prepared:** 24 November 2026 · **Repo:** Brandonio-c/LIO, `main` at or after the commit adding this file
**For:** an independent research agent. Paste everything below the line as its prompt.

---

You are an independent research agent for LIO V3 (LED-Illuminated Optospectrometer for a
Light-based Ingredient Observer), repository Brandonio-c/LIO, branch `main`. Pull the latest
`main` and record the commit you review. This is an **offline analysis and design task**: do not
connect to hardware, change code or push.

## The question

The owner asks: **should the InGaAs photodiode be moved so that it captures light reflected from
the sample more effectively, and if so, where and how?** One idea the owner raised: drill a hole
"down the bottom" and mount the InGaAs at an angle somewhere, aimed at the illuminated spot.
Explore that idea seriously along with the alternatives, and recommend what to do.

Until now the owner's rule has been that neither detector moves without strong evidence. Your job is
to say whether the evidence is now strong enough, for which change, and how to prove it on the bench
before anything permanent (drilling) is done.

## What the evidence says so far (verify against the raw data)

Read first: `docs/research/LIO_V3_ALL16_DUAL_DETECTOR_BENCH_2026-11-24.md` and its evidence folder
`test_results/bench_20261124_all16/` (frozen protocols, sealed runs, `channel_response_32.json`,
`RUN_LABELS.json`, `checkpoint_history.txt`, qualified-v2 products under `derived/`). Then
`docs/research/LIO_V3_STATIONARY_OPTICAL_BENCH_2026-11-24.md` (h8/h12 white paper vs black cup).

Key numbers to check and explain (InGaAs, counts, mains-integrated MEAS, gain 1, N = 12):

| Hole (nm) | Hand-held, pointed straight at the LEDs (21 Nov, `tray_v3/HANDHELD_INGAAS_2M_RF.json`) | Mounted 18 Nov (old depth) | Mounted 24 Nov, white paper (final W1/W2) | Mounted 24 Nov, flat black card (B1/B2) | White − black |
|---|---|---|---|---|---|
| h8 (850) | ≈ 7,900 | — | 143 / 136 | 20 / 32 | +114 |
| h12 (1450) | 4,107 | ≈ 81 | 65 / 76 | 16 / 24 | +51 |
| h13 (1550) | 862 | ≈ 36 | 5.7 / 6.2 | 3.2 / 3.3 | +2.7 |
| h14 (1650) | 1,057 | ≈ 35 | 4.2 / 4.2 | 2.1 / 2.5 | +1.9 |
| h15 (1760) | 679 | — | 36 / 34 | 22 / 20 | +14 (≈ 60 % target-independent) |

So: the detector chain works (thousands of counts direct); mounted, the **reflected** SWIR is
1–2 % of direct for h12 and < 1 % for h13/h14, and h13/h14 fell sharply after the detector was
remounted deeper (`tray_v3/INGAAS_REMOUNT_DEPTH_CHECK*.json`) and the LEDs were reseated. The OPT101
(silicon, centred on the optical axis) sees large target-dependent signals on h1–h11. Black is not
zero: residuals are 10–30 % of white on most channels and ≈ 60 % on h15 InGaAs, and no optical blocker
has yet separated optical return from electrical pickup. Raw InGaAs dark noise is σ ≈ 30–37 counts at
128 SPS, but integrated MEAS repeats are ≈ 1–2 counts. Room light does not change the InGaAs dark level.
Placement disagreement between two placements of the same target is several percent (white) and up to
2.5× (black, OPT101).

## Geometry to work from

- Optical head and deck: `CAD/V3/LIO_V3_R3_Print_Set/06_Optical_Head.scad`, `LIO_V3_R3_master.scad`,
  `CAD/V3/LIO_V3_master.scad` (`optical_deck()`, central window Ø24; the dual-detector README
  recommends ≈ Ø32–34), `CAD/V3/LIO_V3_dual_detector_plate_v01.scad` +
  `README_dual_detector_plate.md` (OPT101 board on axis, InGaAs TO-46 just beyond the board edge,
  i.e. **off axis**), `CAD/V3/LIO_V3_R3_Print_Set/liov3-central_plud_detector.scad`.
- LEDs: 16 on a 35 mm ring, tilted toward a nominal sample plane (`06_Optical_Head.scad` /
  `LIO_V3_R3_master.scad`); the head moves vertically over the sample tray (height scans exist).
- Chamber, tray, door and nest: `03_Chamber_and_Door.scad`, `01_Base_Mount_and_Nest.scad`,
  `10`-series parts in the print list; top cover: `CAD/V3/LIO_V3_split_light_cover_v01.scad`.
- Parts: `docs/HARDWARE_INVENTORY.md`, `docs/OPTICAL_CHANNEL_MAP.md`, `docs/LED_SOURCING.md`;
  InGaAs = MTPD1346D-100 (1 mm active area, TO-46, check its datasheet window/FOV), TIA TL072, Rf
  owner-declared 2 MΩ (unmeasured).
- The owner's phrase "drill a hole down the bottom" is ambiguous: it could mean the bottom face of the
  optical head/deck (beside the LED ring, angled at the spot) or the chamber floor/tray (below or
  beside the sample). Consider both and say which makes physical sense for **reflectance** (a
  detector below an opaque sample sees nothing reflected; a detector below a transparent tray sees
  transmission or the tray's own reflection).

## Questions to answer

1. **Where are the reflected SWIR photons going?** With the CAD geometry, LED beam angles and tilt,
   the sample-plane distance, the InGaAs offset/recess/acceptance cone and the deck window, estimate
   (order of magnitude, stated assumptions) the fraction of a diffuse (Lambertian) return the InGaAs
   collects now, and why h13/h14 are 10× weaker than h12 when hand-held brightness is similar. Is the
   InGaAs field of view even overlapping the spot the SWIR LEDs illuminate? Is the deeper remount
   vignetting it? Is specular geometry involved?
2. **Candidate positions.** Compare, with expected gain ranges and risks:
   (a) current position, unchanged; (b) current position, shallower recess / wider window / chamfered
   aperture; (c) move InGaAs onto the optical axis (swap with or beside the OPT101, or a beamsplitter);
   (d) **angled mount through the bottom of the head/deck**, aimed at the illuminated spot at a chosen
   angle (specify angle, distance, hole diameter and position relative to the LED ring); (e) mount
   in the chamber wall or floor at an angle to the sample plane; (f) a collection lens, light pipe or
   reflector cone in front of the current detector. For each: collection gain, sensitivity to sample
   height (the head moves), specular-glint risk, stray/ambient light, electrical (cable length, shielding,
   hum pickup into a high-impedance TIA), mechanical feasibility and reversibility.
3. **Is drilling justified?** State the evidence threshold for a permanent change and the cheapest
   reversible bench test that would meet it first (e.g. a printed angled clip or temporary bracket that
   holds the TO-46 at the proposed position and angle without drilling, run with the same all-16
   W1/B1/W2/B2 protocol and a blocker pair). Give pass/fail criteria with numbers (e.g. h12 white −
   black ≥ 3× today's +51 counts, h13/h14 ≥ 20 counts, black/white ratio not worse, run-to-run < 3 %).
4. **Angle and geometry specifics** for the most promising option: angle from the normal, distance
   to the spot, spot size vs detector FOV, which LED holes it will favour or shadow, effect on the
   OPT101 and on height scans, and print/drill dimensions against the actual CAD part (name the file
   and module, and the parameters to change).
5. **Interaction with other open problems**: intermittent LED connections (h12, h14, h15, h16 changed
   when wires were moved), h13/h14 aim/seating, placement reproducibility (target holder), the
   unseparated electrical vs optical residual (blocker), and the unreconciled Rf/current metadata.
   Which of these must be fixed first, so that a detector move is judged on a stable baseline?

## Constraints

- Offline only: no serial port, LEDs, motors, firmware, wiring/current changes, code edits,
  dashboard actions or Git push. Physical changes are proposals for the owner.
- Never modify historical runs; hash what you rely on; derived work goes outside source runs.
- Do not raise LED drive or relax duty/watchdog limits; do not invent physical facts (A0, Rf,
  currents, distances you cannot read from CAD or data: state assumptions instead).
- No calibrated reflectance/photocurrent, measured SNR improvement, SWIR chemistry or 1850 nm claim
  without direct evidence. h16 is `proxy_unassigned`; the bench shows a strong silicon response, so it
  is not a primary 1850 nm source.
- Cite datasheets you use (MTPD1346D-100, OPT101, the SWIR LEDs in `docs/LED_SOURCING.md`).

## Deliverable

Save `docs/research/LIO_V3_INGAAS_PLACEMENT_<date>.md` with:

1. A one-paragraph bottom line: move or not, where, and the single next bench test.
2. Your verification of the numbers above from the raw data (any disagreement stated).
3. A collection-geometry estimate for the current mount and each candidate (table; assumptions).
4. A ranked options table: change, expected gain range, risks, cost/effort, reversibility, and the
   test that would confirm it.
5. A concrete design for the recommended option, including the owner's angled-hole idea evaluated
   on its merits: position, angle, hole/clip dimensions, CAD file/module/parameters, and a printable
   no-drill trial fixture if possible.
6. A bench protocol for the trial (JSON-ready fields: holes, N, settle, mains periods, caps,
   checkpoints, targets W/B order, blocker pairs) and pass/fail criteria.
7. Prerequisites to fix first, open unknowns and what would resolve them; commit reviewed and files
   hashed.

Write for the owner, an engineer-researcher, in plain language with detail in tables.
