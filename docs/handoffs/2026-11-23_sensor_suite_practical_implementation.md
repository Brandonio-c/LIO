# Coding-agent handoff: complete the practical LIO sensor-suite upgrades

**Date:** 23 November 2026. Repository Brandonio-c/LIO, branch `main`.  
**Code/evidence baseline:** `92bee4a2b3f702b3ba6c294e5ef4d9af716729e4` plus the documentation commits publishing this handoff, its plan and the functionality report.

## Copy-paste task

You are the coding agent for LIO V3: LED-Illuminated Optospectrometer for a Light-based Ingredient Observer.

Pull latest `main`, record the exact starting SHA/dirty state, read applicable AGENTS/.agents instructions, and implement **ALL S1–S7** in `docs/SENSOR_SUITE_PRACTICAL_UPGRADE_PLAN.md`. Deliver the working implementation and full offline verification, not another plan, helper-only changes or unsupported completion language. Preserve newer compatible work and local owner changes; do not reset/clean destructively, force-push, change Git configuration or edit historical acquisitions.

### Read in full before implementation

1. `docs/SENSOR_SUITE_PRACTICAL_UPGRADE_PLAN.md` — controlling new scope and acceptance gates.
2. `docs/research/LIO_V3_FUNCTIONALITY_USABILITY_REPORT_2026-11-23.md` — independent evidence and reproduced gaps.
3. `docs/SENSOR_READINGS_UPGRADE_PLAN.md` — ORIGINAL M0–M6 and section12; M7 stays deferred.
4. `docs/SENSOR_READINGS_CALLER_REMEDIATION_PLAN.md`.
5. `docs/research/LIO_V3_CALLER_REGRESSION_CASES_2026-11-23.md`.
6. `docs/handoffs/2026-11-23_caller_remediation_acceptance.md` — implementer claims to verify, not blanket acceptance.
7. `.agents/project-state.md`, `test_results/README.md`, current README/TESTING/DIAGNOSTIC_SWEEP usage and the relevant config/code.

Keep D03=ownership and D04=OFF. Preserve CE/D/A regressions and original milestones; do not redefine them as narrower software/helper milestones.

### Authorization and limits

You are authorized to implement host source/tests/current docs and perform full OFFLINE tests using simulator, fake transports, copied archives and test-created local servers. Proceed through the whole software scope without asking permission for ordinary edits/tests. Finish independent work while reporting unavailable platforms or bench-only evidence honestly.

This handoff **does not authorize** real Device/serial open, port enumeration that contacts hardware, POWER WAKE, LEDs, motors, live-dashboard restart/port takeover, firmware edit/flash, wiring/current/pot changes, physical stage-state edits or invented operator confirmations. The board being connected and permissions quoted in historical handoffs do not supply authorization under this task. Bench experiments need explicit owner authorization and actual prerequisites. Code push follows the coding session's instruction; publication of these docs is not code-push permission. Do not stop implementation to ask about a later push.

Core gain remains1, original duty/travel/current limits remain intact, M7 deferred. The NanoR4 reports `hw_wdt=0`; preserve the owner-acknowledged cooperative admission mode and its **unproven firmware-hang bound**. Do not invent timing margins or use synthetic capability on real ports. A0/Rf/ammeter/optical/reference checks stay owner-deferred. No automatic homing/rebasing or catch-up based on unequal bottom marks.

Historical `test_results/` bytes are immutable and tracked; only physical `stage_position.json` stays local/ignored. New derived products go outside source runs under `--derived-out`. Isolate ALL test stage/journal paths before full simulator tests; `LIO_STATE_ROOT` alone does not currently guarantee stage isolation.

### Implement these seven packages

**S1 — Realistic repeatability.** Fix T05.5's first-reading/1000count prefilter and T08.2's missing net-repeatability judgment. Collect predeclared fixed N within existing gates for low-count signals; persist signed repeats, identities and missingness; show N/mean/SD/interval/drift/dropouts and unavailable reasons. CV cannot qualify a near-zero denominator. Zero judged channels is not precision PASS. Stable low-count, unstable, negative, missing and saturated fixtures need meaningful distinct results.

**S2 — Integrity before qualification.** Populate NEW height-scan identity fields and full frozen facts, including per-fact provenance and exposure-bound label. Correct all physical-current consumers, including legacy height reports. Do not certify unverified A0 or silently substitute today's Rf/current into old runs. Before resume validate exact detector-row multiplicity, conditions/settings/blocks/identities/pairs, schedule and sources/any existing seal. Reproduce the report's corrupted completed-prefix INCOMPLETE cases. Preserve legal unsealed crash recovery using durable checkpoints and explicit source revision, not blanket refusal or blind resealing. Preserve segments, chronology, abort history and charges.

**S3 — Working owner workflow.** Deliver a stationary Scan UI using the same validated protocol as CLI, including an exploratory OPT101 preset and explicitly diagnostic SWIR mode. Fix browser protocol Resume routing and real CLI height Resume's missing `sample` handling. Render fresh manual checkpoint occurrences and strict answers. Ordinary suite/height/unblocked capture keeps one truthful start confirmation and no in-run popups; manual interventions remain separately confirmed. Expose effective mains periods versus ordinary N and prove settings change actual MEAS arguments. Test a real headless browser through persisted records, not only HTTP handlers.

**S4 — Finite acquisition comparisons.** Expose settling/integration comparisons with measured target-contrast pilot variance/cost and separate frozen production allocation. Fair optimized/equal comparators obey the same exposure AND wall/cycle caps, including unequal costs/cooldowns. Persist pilot source IDs, priors/unknowns, weights, feasible comparator and exact schedule. Never stop when positive or treat technical conversions as independent blocks. Do not promise SNR gain from longer averaging.

**S5 — Connected uncertainty.** Wire paired optical/control contrasts, target/control and shared-control covariance, and frozen-family inference through actual qualified analyse/report/dashboard/profile consumers. Introduce explicit experimental pairing/group identity where existing condition-specific block IDs cannot pair. Unknown C stays null. Test saved-record truth, including paired `[10,12,14]−[1,2,3]` giving mean10 and variance of mean1/3. Missing pairs, drift/unsupported assumptions and absent SciPy have explicit limits; eligible labelled fixtures produce useful numbers. Synthetic evidence never becomes rig qualification. Remove unconditional outcome stubs without replacing them with unconditional PASS.

**S6 — References, A21 and A22.** Match reference/baseline/profile eligibility to actual assembly/source/acquisition/calibration/control epochs. Implement shared source-bound selection through planner/fine placement/CLI/UI/report and genuinely new disjoint confirmation. No noisy-max, blind/h16 contamination or travel extension. Preserve h16 extraction and wire explicit proxy opt-in through batch/CLI/UI with `proxy_unassigned` namespace. Existing grouped distance helpers are not predictive validation: audit/reuse genuine train/test group facilities with training-only transforms, matched folds/support and honest estimands, or report predictive value unavailable. Do not build a new classifier project to manufacture a positive result.

**S7 — Status and release discipline.** Separate COMPLETE from optical/quantitative eligibility; fix vacuous PASS and misleading diagnostic messages, expose actual cooldown/progress costs, and identify each dashboard twin tile's source run/epoch. Record loaded startup build/dirty-content identity/PID; disk HEAD and Session.version are not loaded-code identity. Test controlled restart semantics only on fake servers. Isolate all simulator stage paths with write guards. Diagnose the intermittent golden HTTP failure with captured evidence. Update current docs/help/agent state to implemented behavior.

### Required evidence and verification

Use genuine dependencies. Run full Ruff/format, strict mypy, maintained CE/D/caller/new regressions and `pytest -m "unit or sim" --lio-sim` with coverage and the existing90% protocol/analysis gate. See the plan for exact commands. Run Python3.10/3.12 and optional core/precision/profiles absent/present environments; SciPy numerical tests must actually execute where claimed. Test installed wheel/CLI/assets outside checkout and browser actions. If an environment cannot be supplied, report the precise missing check rather than PASS.

Retain >=2000-family numerical checks with predeclared tolerances AND integrated saved-record numerical truth. Prove offline planning/audit/analysis/views perform zero Device/serial/WAKE/ARM, static acquisition no motion, and data/reuse/settings/selection conclusions through actual callers. Preserve historical byte hashes before/after complete tests. Do not weaken assertions, tune thresholds to current data, add blanket exclusions/xfails or count missing optional tests as passes.

Baseline context: original final archived suite971passed/1failed/6skipped; intermittent `test_golden_dashboard_http_plan_numerical_answer` remains unexplained. Earlier969/0/6 and Python3.10's960/0/15 are different scopes; the latter lacked SciPy. Independent focused audit was63passed (59caller+3protocolCLI+1golden), not a whole-release pass. Another isolated golden pass is not diagnosis.

### Finish with a concrete acceptance record

Deliver changed source/tests/docs, exact tested SHA/versions/commands/results and retained logs; S1–S7 and A21/A22 caller-level evidence; ORIGINAL M0–M6 software-versus-physical matrix; browser/CLI working examples; numerical truth and source immutability/test-isolation evidence; migration/legacy behavior; precise remaining gaps and separate proposed owner-authorized bench comparisons.

Do all software work needed to make the result reviewable before asking about later publication or physical tests. Do not claim full completion from inherited test counts or undocumented helpers. **Software green is not optical PASS. No measured SNR improvement or recovered SWIR/1850nm chemistry is justified by software alone.**
