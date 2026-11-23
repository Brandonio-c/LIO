# LIO test results (tracked for research)

Historical diagnostic scans, tray_v3 bench artifacts, and related corpora live here so agents and collaborators can analyse them from GitHub without the bench Mac.

**Local-only (gitignored):** `stage_position.json` — chamber-top soft-limit state on the machine.

**Sensor-extraction handoff anchors** (see `docs/handoffs/2026-11-23_research_handoff_sensor_information_extraction.md`):

| Path | Role |
|------|------|
| `20261123-135504_host_residual_hw/` | Live automatic host suite after residual remediation (NOT FUNCTIONAL; InGaAs dark/optical FAIL; T10.2 SKIP; SWEEP/safety PASS) |
| `20261123-003133_scan_quick/` | Latest empty quick scan (NOT FUNCTIONAL; h12–14 FAIL; h16 OPT WARN) |
| `20261120-012619_scan_quick/` | Strong empty FUNCTIONAL baseline |
| `20261119-152512_scan_quick/` | black_cup FUNCTIONAL (InGaAs 12–14 alive) |
| `tray_v3/LED_CONFIRM_SWEEP.json` | Post visible-LED replace MEAS classify |
| `tray_v3/INGAAS_REMOUNT_DEPTH_CHECK.json` | Handheld vs mounted InGaAs (Rf=2 MΩ) |
| `tray_v3/INGAAS_BOOST_INTEGRATION_CHECK.json` | Longer integration ≠ enough photons |
| `tray_v3/DRIVE_TUNE_A.json` / `DRIVE_TUNE_B.json` | Pot tune logs |
| `tray_v3/LED_REPLACE_SWEEP.json` | Pre-replace dead-LED sweep |

New local runs may be committed when they are needed for a handoff; do not commit secrets or food-library photos here (`data/foods/` stays ignored).

**Current independent QA (2026-11-23):** `a0935fb` passes the maintained Python 3.12 checks (918 full unit/simulator passes, 0 failures, 12 skips; 98% protocol/analysis gate), but twelve separate audit-only actual-caller tests fail and further connected contracts remain incomplete. Python 3.10 CI mypy fails. Original M0–M6 are not accepted as complete. See the [independent audit](../docs/research/LIO_V3_RESIDUAL_REMEDIATION_QA_a0935fb_2026-11-23.md), [regression catalogue](../docs/research/LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md), [current remediation plan](../docs/SENSOR_READINGS_CALLER_REMEDIATION_PLAN.md) and [coding handoff](../docs/handoffs/2026-11-23_caller_remediation_implementation.md).

The archived automatic live run remains NOT FUNCTIONAL; historical scans are not re-qualified as optical PASS. The [residual acceptance handoff](../docs/handoffs/2026-11-23_residual_remediation_acceptance.md) and [D01–D20 closure](../docs/handoffs/2026-11-23_remediation_d01_d20_closure.md) are historical claims. The owner has now authorized implementation and supported live full tests under the new handoff; this documentation publication itself performs none. New evidence must use fresh run paths, preserve existing bytes and keep physical stage state local. No measured SNR or SWIR/1850 chemistry claim follows from software completion.
