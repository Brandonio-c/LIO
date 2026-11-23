# Research QA handoff — residual sensor-readings remediation

**Prepared:** 23 November 2026  
**Repo:** Brandonio-c/LIO  
**Candidate to audit:** latest `main` after residual remediation push (parent baseline `944a820`; prior full-pass `3e2d3b0` / remediation `130dd77`).  
**Implementer claim:** residual caller-level host repairs + TEN triage + one automatic live-host catalogue. **Not** optical/bench/reference qualification. **M7 deferred.** No measured SNR / SWIR-1850 chemistry claim.

Use this prompt verbatim with a research/QA agent. Do not treat implementer docs as proof.

---

You are the independent research/QA agent for Brandonio-c/LIO. Audit the **residual sensor-readings remediation** candidate on `main` at or after the commit that adds `docs/handoffs/2026-11-23_residual_remediation_acceptance.md`. Your job is adversarial verification of software correctness and honest separation of host-software PASS from physical NOT FUNCTIONAL — not another implementation plan.

## Constraints
- Prefer offline host audit; hardware may be used only for read-only INFO / reviewing the already-captured host report unless the owner separately authorizes new light/motion.
- NO firmware flash, wiring/current changes, fabricated physical confirmations, or invented margins.
- Preserve canonical IDs: **D03 = ownership**, **D04 = OFF**. Preserve **ORIGINAL M0–M6** from `docs/SENSOR_READINGS_UPGRADE_PLAN.md`.
- A0 / Rf / ammeter / optical-block / quantitative reference remain owner-deferred.
- M7 stays deferred/isolated.
- Software green ≠ physical qualification. A tested SKIP/refusal proves protection, not that the unsupported pulse is admitted.

## Read in full
- `docs/handoffs/2026-11-23_residual_remediation_acceptance.md` (implementer claim — treat as hypothesis)
- `docs/handoffs/2026-11-23_fullpass_acceptance.md` (prior; historical)
- `docs/SENSOR_READINGS_REMEDIATION_PLAN.md`
- `docs/SENSOR_READINGS_UPGRADE_PLAN.md` (original M0–M6 and §12)
- `docs/research/LIO_V3_SENSOR_READINGS_QA_2026-11-23.md`
- `docs/handoffs/2026-11-23_sensor_readings_remediation.md`
- `docs/handoffs/2026-11-23_remediation_d01_d20_closure.md` (historical)
- `.agents/project-state.md`
- `test_results/README.md`
- Live host report: `test_results/20261123-135504_host_residual_hw/report.md`

## What the implementer claims was fixed
Residual caller-level gaps after the independent audit of `944a820`:
- Incomplete/cross-call raw fragments (`b'C'` then `b'H 1 ON 1500\n'`) refused before write
- Production constructors defer journal mutation (`defer_load`) until lease
- T10.2 no production `_command_unguarded(CH…)`; admit or SKIP
- `wait_needed_many` for SWEEP same-rail siblings
- CE firmware refuse → `drop_pending` (no 60 s uncertain lock poisoning the suite)
- TEN maintained failures triage (meter A4/B10, drift SKIP+long controls, PTY owned refuse, T13 twin rails, travel margin 16384, saturation WARN/FUNCTIONAL)
- Offline: 912 passed / 0 failed unit|sim; coverage gate 98%

Live automatic selftest claim: link/SR/timing/SWEEP/safety PASS; T10.2 SKIP (budget); InGaAs dark + optical channels FAIL → overall NOT FUNCTIONAL.

## Your audit procedure
1. Identify exact commit SHA, Python version, SciPy presence.
2. Reproduce or refute residual CEs and TEN dispositions via **actual callers** (Device/CLI/ScanStore/dashboard) — mock only transport/clock/operator boundaries.
3. Confirm T10.2 source contains no `_command_unguarded` CH; confirm fragment `send_raw` never writes.
4. Confirm `wait_needed_many` prevents the old SWEEP `wait=0` / reserve fail pattern.
5. Confirm CE refuse does not set uncertain cooldown that blocks subsequent MEAS.
6. Re-read `test_results/20261123-135504_host_residual_hw/` and classify each FAIL/SKIP as software regression vs physical/optical limit. Do not re-label optical FAIL as software PASS.
7. Run release checks as far as feasible:
   - `ruff check .` / `ruff format --check .`
   - `cd software/host && python -m mypy`
   - CE/D + residual tests + `pytest -m "unit or sim" --lio-sim`
   - coverage gate on protocol/analysis
8. Produce honest closure: D01–D20 / CE → test → pass/fail → residual; ORIGINAL M0–M6 software vs physical; exact blockers (including M1 current-rig T10.2 SKIP semantics).

## Deliverable format
- Candidate SHA and dependency/runtime versions
- Pass/fail/unknown for residual CEs and TEN cases with evidence commands
- ORIGINAL M0–M6 matrix (software vs deferred physical)
- Interpretation of the live host report (software vs optical)
- Commands/results for lint/type/suite runs
- Exact remaining blockers (no invented margins; no SNR/chemistry claims)
- Whether `docs/handoffs/2026-11-23_residual_remediation_acceptance.md` overclaims

If you find a regression the suites miss, write a minimal failing reproduction and classify severity. Do not push unless the owner authorizes.
