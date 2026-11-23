# LIO test results (tracked for research)

Historical diagnostic scans, tray_v3 bench artifacts, and related corpora live here so agents and collaborators can analyse them from GitHub without the bench Mac.

**Local-only (gitignored):** `stage_position.json` — chamber-top soft-limit state on the machine.

**Sensor-extraction handoff anchors** (see `docs/handoffs/2026-11-23_research_handoff_sensor_information_extraction.md`):

| Path | Role |
|------|------|
| `20261123-003133_scan_quick/` | Latest empty quick scan (NOT FUNCTIONAL; h12–14 FAIL; h16 OPT WARN) |
| `20261120-012619_scan_quick/` | Strong empty FUNCTIONAL baseline |
| `20261119-152512_scan_quick/` | black_cup FUNCTIONAL (InGaAs 12–14 alive) |
| `tray_v3/LED_CONFIRM_SWEEP.json` | Post visible-LED replace MEAS classify |
| `tray_v3/INGAAS_REMOUNT_DEPTH_CHECK.json` | Handheld vs mounted InGaAs (Rf=2 MΩ) |
| `tray_v3/INGAAS_BOOST_INTEGRATION_CHECK.json` | Longer integration ≠ enough photons |
| `tray_v3/DRIVE_TUNE_A.json` / `DRIVE_TUNE_B.json` | Pot tune logs |
| `tray_v3/LED_REPLACE_SWEEP.json` | Pre-replace dead-LED sweep |

New local runs may be committed when they are needed for a handoff; do not commit secrets or food-library photos here (`data/foods/` stays ignored).
