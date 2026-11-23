# Research QA handoff — sensor-readings full-pass (software)

**Prepared:** 23 November 2026  
**Repo:** Brandonio-c/LIO  
**Candidate to audit:** `3e2d3b0` (on `main`; parent remediation `130dd77`)  
**Implementer claim:** offline host software full-pass repairs for remaining sensor-readings acceptance gaps. **Not** bench/optical/reference qualification. **M7 deferred.** No measured SNR / SWIR-1850 chemistry claim.

Use this prompt verbatim with a research/QA agent. Do not treat implementer docs as proof.

---

You are the independent research/QA agent for Brandonio-c/LIO. Audit the sensor-readings **full-pass** candidate on `main` at or after `3e2d3b0`. Your job is adversarial verification of software correctness claims—not another implementation plan.

## Constraints
- Offline host audit only unless the owner separately authorizes hardware.
- NO real serial, POWER WAKE, LEDs, motors, firmware flash, wiring/current changes, fabricated physical confirmations, or live-dashboard restart.
- Preserve canonical IDs: **D03 = ownership**, **D04 = OFF**. Preserve **ORIGINAL M0–M6** definitions from `docs/SENSOR_READINGS_UPGRADE_PLAN.md` (do not rename or swap).
- A0 / Rf / ammeter / optical-block / quantitative reference remain owner-deferred unknowns.
- M7 stays deferred/isolated.
- Software green ≠ physical qualification. A tested refusal proves protection, not that an unsupported physical feature works.

## Read in full
- `docs/SENSOR_READINGS_REMEDIATION_PLAN.md`
- `docs/SENSOR_READINGS_UPGRADE_PLAN.md` (original M0–M6 and §12)
- `docs/research/LIO_V3_SENSOR_READINGS_QA_2026-11-23.md` (describes earlier `38eb8e6` audit)
- `docs/handoffs/2026-11-23_sensor_readings_remediation.md`
- `docs/handoffs/2026-11-23_remediation_d01_d20_closure.md` (historical; not acceptance)
- `docs/handoffs/2026-11-23_fullpass_acceptance.md` (implementer claim — treat as hypothesis)
- `.agents/project-state.md`
- `test_results/README.md`

## What the implementer claims was fixed
Connected repairs across ownership/exposure gateway, authoritative ScanStore records, shared preflight/provenance, protocol lifecycle with real CLI/dashboard operator answers, quantity/compatibility gates, fixed-N + Bonferroni/FWER (≥2000), pilot freeze / shared TargetSelection, and release lint/type checks.

Mandatory counterexamples turned into regressions (`software/host/tests/unit/test_fullpass_counterexamples.py`), including:
- raw `b'PING\nCH 1 ON 1500\n'` and `b'@123 CH 1 ON 1500\n'` without reservations
- constructor mutating live owner journal
- 50 ms reservation vs active 2000 ms WDT
- failed OFF while CE high
- height resume at gain 2 under gain-1 snapshot
- saved analysis remaining verified after NPZ mutation
- pilot 100 + production 0,1,2 → mean must be 1 not 25.75
- invented physical confirmations / `--allow-light` as confirmation
- timeout charged zero; expired deadlines reset on resume
- frozen `{12:1,13:5}` executing swapped schedule
- incompatible Rf/assembly/A0 baseline accepted
- H16 opt-in extracting nothing
- grouped ablation evaluating training rows
- fine/report selecting different targets

Also claim: `lio scan plan --protocol` constructs no Device/serial and sends no WAKE; golden CLI + dashboard HTTP paths with fake physical boundaries.

## Your audit procedure
1. Check out / identify exact commit SHA, Python version, and whether SciPy/sklearn extras are present.
2. Reproduce or refute each CE01–CE14 and D01–D20 required proof by running **actual** callers (CLI routing, dashboard server/HTTP, ScanStore readers)—not only helpers. Prefer failing the audited old behavior over import-only tests.
3. Search for vacuous assertions (`or True`), unused spies, tests that never enter claimed state, hardcoded `control_evidence=False`, always-UNRESOLVED substitutes, and ungated envelope paths.
4. Verify fail-closed timing: cooperative WDT is not treated as a zero-overshoot wall-clock ceiling; no invented margin; ordinary n=2 and mains 2/8/8/2 semantics; wrong-rail bounds use energized rail.
5. Verify historical byte invariance on a real acquisition under audit/analyse/report/view.
6. Run release checks as far as feasible offline:
   - `ruff check .` and `ruff format --check .`
   - `cd software/host && python -m mypy`
   - targeted CE/D suites + `pytest -m "unit or sim" --lio-sim` with isolated `--results-dir`
   - FWER test when SciPy present
   - Note any remaining failures; do not hide them.
7. Produce an honest closure table: D01–D20 / CE → test → pass/fail → residual. Separate ORIGINAL M0–M6 software verdict from bench/optical/quantitative.
8. Explicitly list blockers that prevent (a) full software acceptance and (b) current-rig M1 acquisition acceptance.

## Deliverable format
- Candidate SHA and dependency/runtime versions
- Pass/fail/unknown for each CE and D01–D20 with evidence commands
- ORIGINAL M0–M6 matrix (software vs deferred physical)
- Commands/results for lint/type/suite runs
- Historical byte-invariance evidence
- Exact remaining blockers (no invented margins; no SNR/chemistry claims)
- Whether implementer `docs/handoffs/2026-11-23_fullpass_acceptance.md` overclaims

If you find a regression that the suites miss, write a minimal failing reproduction and classify severity. Do not push unless the owner authorizes.
