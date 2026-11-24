# Research handoff: review the practical upgrades and find ways to improve LIO optical performance

**Prepared:** 24 November 2026 · **Repo:** Brandonio-c/LIO, `main` at or after `1416db7`
**For:** an independent research agent. Paste everything below the line as its prompt.

---

You are an independent research agent for LIO V3 (LED-Illuminated Optospectrometer for a
Light-based Ingredient Observer), repository Brandonio-c/LIO, branch `main`. Pull the latest
`main` (at or after `1416db7`) and record the commit you audit.

## Your goal

**Find realistic, evidence-based ways to improve the optical performance of the current LIO
system**: more usable, repeatable signal from the sample on the detectors that matter,
especially the InGaAs SWIR channels (holes 12–15, 1450–1760 nm), and better OPT101
visible/NIR fingerprints. Rank the options by expected benefit, cost, risk and how each would
be verified. You are also reviewing the latest software work (below) so that you know what
the instrument and its tools can now measure and where they still fall short; but the
deliverable is an **optical improvement plan**, not another software audit.

Treat every implementer document as a hypothesis. Use recorded data. Separate what is
established, what is plausible and what is unknown.

## What changed most recently (review, briefly)

Read `docs/handoffs/2026-11-23_sensor_suite_practical_acceptance.md`. In short:
- **S1:** T05.5 now measures fixed-N repeatability at real low signal levels (precision-2;
  noise-aware SD limit or CV for resolved means); T08.2 judges SWEEP net repeatability.
- **S2:** complete reading identities on height scans, exposure-bound/build provenance,
  semantic resume validation; legacy "nA leakage" no longer claimed without verified A0/Rf.
- **S3:** effective integration setting (`mains_periods`) drives the real commands; with mains
  integration a RAIL A height SWEEP only fits the duty budget at 1–2 periods.
- **S5:** paired condition contrasts (e.g. optical-block vs unblocked), scoped shared-control
  contrasts with covariance and familywise intervals are connected through analyse/report.
- **A22:** h16 stays `proxy_unassigned`; explicit opt-in; honest grouped predictive comparison.
- Still open: S4 (settling/integration comparisons), A21 (selection + fresh confirmation),
  browser protocol builder/prompts.

Say briefly whether these tools are adequate to run the optical experiments you propose, and
what (if anything) is missing for them. Software green is not optical PASS.

## Optical facts and evidence to analyse

Start with `docs/research/LIO_V3_FUNCTIONALITY_USABILITY_REPORT_2026-11-23.md` (latest
independent assessment; its per-channel table and InGaAs chronology are the baseline), then
the raw data, not just verdicts:

| Evidence | Where |
|---|---|
| Latest full catalogue (23 Nov), empty chamber | `test_results/20261123-162705_host/` |
| Latest quick height scan, sealed | `test_results/20261123-173108_scan_quick/` (`cube.csv.gz`, `streams/*.npz`) |
| Stationary h8/h12 captures (fixed N) | `test_results/20261123-175731_scan_protocol/`, `20261123-180942_scan_protocol/` |
| Earlier catalogues and scans | `20261118-002742_host`, `20261119-*`, `20261120-*`, `20261123-003133_scan_quick`, `20261123-135504_host_residual_hw` |
| Tray, food and bench records | `test_results/tray_v3/`: empty-tray and Citrucel (`LIO-F-00001`) scans; `HANDHELD_INGAAS_2M_RF.json`, `INGAAS_REMOUNT_DEPTH_CHECK*.json`, `INGAAS_BOOST_INTEGRATION_CHECK.json`, `LED_CONFIRM_SWEEP.json`, `LED_REPLACE_SWEEP.json`, `DRIVE_TUNE_A/B.json` |
| Hardware and optics design | `docs/HARDWARE_INVENTORY.md`, `docs/OPTICAL_CHANNEL_MAP.md`, `docs/LED_SOURCING.md`, `electronics/` (read-only), `CAD/V3/` (optical head, detector plate `LIO_V3_dual_detector_plate_v01.scad`, LED seats/tilt `LIO_V3_R3_Print_Set/LIO_V3_R3_master.scad`, unprinted split light cover `LIO_V3_split_light_cover_v01.scad`) |
| Firmware/ADC behaviour | `software/firmware/lio_firmware/` (`adc.cpp` mains integration, `optics.cpp`) |

Key observations to explain or exploit (verify each against the data):
- InGaAs (MTPD1346D-100, 1 mm active area, TO-46, TL072 TIA) dark σ ≈ 37 counts now vs 2.6–4.8
  on 18–20 Nov; offset ≈ −331 counts (≈ −41 mV ADC-referred) vs ≈ −168 earlier; 60 Hz hum
  ≈ 9.5 mV (Q23) vs 1.3 mV (Q20). Owner-reported changes in between: Rf 1 MΩ → 2 MΩ (config
  still says 1 MΩ), detector remounted deeper after drilling, drilled hole later filled, LED
  tops not fully sealed, both LED rails reduced to ≈ 30 mA (config says B 45 mA).
- Mounted SWIR responses: 18 Nov h12/13/14 ≈ 81/36/35 counts; 23 Nov ≈ 22/8/1; stationary
  h12 mean −8.7 (n=6). Hand-held direct illumination gave h8 7909, h12 4107, h14 1057 counts:
  the detector chain works; light delivery/collection from the sample plane is the suspect.
- h8 InGaAs is weak but repeatable (28.5 ± 0.84, n=6, integrated); OPT101 visible nets are
  ≈ 23–167 counts at ≈ 30 mA with dark σ ≈ 0.5 count (usable, low).
- LEDs sit on a 35 mm ring, tilted toward a nominal sample plane; the detector window in the
  deck was Ø24 vs a recommended ≈ Ø32–34 for the dual-detector plate; the head travels ~420k
  half-steps; scans show height dependence on some channels.
- 60 Hz pickup, earth bond (owner says connected), shielding and the 2 MΩ TIA bandwidth are
  all candidates for the noise; mains-period integration rejects some of it in the average
  but does not remove the pickup.

## Questions to answer

1. **Where are the photons lost?** Using geometry (CAD), datasheets (LED beam angle/radiant
   intensity, InGaAs responsivity and active area, OPT101) and the hand-held vs mounted data,
   estimate the optical budget from LED to sample to detector for h8 and h12–h14. Which term
   dominates: source output at ≈ 30 mA, beam aim/overlap with the detector field of view,
   aperture/window clipping, detector recess depth/acceptance angle, sample-plane distance,
   or stray/ambient light? Give order-of-magnitude numbers with stated assumptions.
2. **Geometry and alignment fixes.** What changes to detector position/recess, window size,
   LED tilt/aim, baffles, a collection lens, diffuser or reflector, or the sample height would
   most increase sample-return signal on the InGaAs? Which can be done with the existing
   printed parts or a small new print (state the dimensions you would change)?
3. **Front-end noise.** Is the InGaAs noise/hum rise explained by Rf 2 MΩ, TIA bandwidth/Cf,
   wiring/shielding, grounding or ambient light? What low-cost changes (Cf value, shielded
   twisted pair, star ground, RC filtering, enclosure/cover, Rf choice) would improve
   signal-to-noise for the *integrated* measurements LIO actually uses, without hiding light?
4. **Source side.** Within the safe current limits (no drive increases beyond LED ratings;
   duty budgets unchanged), would different LEDs (narrower beam, higher radiant intensity,
   different packages), better seating, or pulsed/integrated acquisition timing help? Is the
   ≈ 30 mA operating point leaving much on the table?
5. **Ambient and stray light.** How much can sealing (the split light cover, sealing LED tops)
   plausibly change InGaAs dark noise and offset? Design a quick test to measure it.
6. **Visible/NIR (OPT101).** What would improve OPT101 fingerprints most (signal level,
   repeatability, reference normalization) for food work now?
7. **Experiments.** For your top candidates, propose short, owner-authorised bench experiments
   using the existing tools: fixed-N stationary protocols (`lio scan run --protocol`, paired
   optical-block conditions, `qualified-v2` contrasts), T05.5 precision-2, `lio watch`, and
   one-factor-at-a-time changes. Each needs: change, measurement, success criterion, expected
   effect size and how to tell optical gain from electrical pickup.

## Constraints

- Analysis is offline. Do not open the serial port, light LEDs, move motors, flash firmware or
  change wiring/currents yourself. A dashboard may own the port; do not stop it.
  Physical changes are proposals for the owner.
- Never modify historical runs; work on copies and hash what you rely on.
- Do not raise LED drive above rated limits or relax duty/watchdog limits; do not invent
  physical facts (A0 voltage, Rf, currents, alignment).
- No claim of measured SNR improvement or recovered SWIR/1850 nm chemistry without data; h16
  remains an unassigned proxy, never primary 1850 nm.
- Cite datasheets you use (MTPD1346D-100, OPT101, the LED parts in
  `docs/LED_SOURCING.md` / `docs/HARDWARE_INVENTORY.md`).

## Deliverable

Save `docs/research/LIO_V3_OPTICAL_IMPROVEMENT_PLAN_<date>.md` containing:

1. A one-paragraph bottom line: the most likely reasons optical performance is poor, and the
   single most promising fix.
2. An optical budget table (per hole, per stage, with assumptions and uncertainty).
3. A ranked table of improvement options: change, mechanism, expected gain (range), cost,
   risk, effort, reversibility, and the experiment that would verify it.
4. Front-end noise analysis with recommended component/wiring changes.
5. Concrete geometry proposals (dimensions, which CAD part, print vs buy).
6. A short bench plan (ordered, one factor at a time) with success criteria, using the
   existing software tools, and notes on any software gap that blocks it.
7. A brief review of the latest software upgrades: adequate for these experiments or not,
   and why.
8. What remains unknown and what measurement would resolve it; commit audited and commands run.

Write for the owner, an engineer-researcher, in plain language with the detail in tables.
