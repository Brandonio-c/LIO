# Coding-agent handoff: LIO V3 sensor-readings upgrade

Copy the prompt below into the implementation agent working on the local LIO repository. The [implementation plan](../SENSOR_READINGS_UPGRADE_PLAN.md) is the specification; the [research assessment](../research/LIO_V3_SENSOR_INFORMATION_ASSESSMENT_2026-11-23.md) is its evidence base.

---

You are implementing the host-software sensor-readings upgrade in `Brandonio-c/LIO`.

**Implement and test milestones M0–M6 of `docs/SENSOR_READINGS_UPGRADE_PLAN.md` in dependency order. Do not return another research report or stop at a plan. M7 is explicitly deferred; do not expand into firmware, auto-ranging or a new classifier project.**

## Repository and authorization

- Read applicable `AGENTS.md` instructions and `.agents/README.md`, `preferences.md`, `project-state.md`, `baselines.md` and `workflows.md` first.
- Inspect status/history and work from current `main`; fast-forward from origin only when it preserves local work. No side branches, destructive reset/clean, force push or Git-config changes.
- Offline host implementation, simulator work and tests are authorized. **No real device connection, LED exposure, motor motion, firmware flash, current/wiring change, operator auto-confirmation, physical stage-state modification or live-dashboard restart is authorized.** Current connections can energize coils through POWER WAKE; even a planning command must not open a real device.
- The documentation publication is already authorized separately. Implementation commits/pushes must follow the owner's instructions in this implementation session; do not treat the earlier docs-only push as blanket authorization to push code. Complete the implementation, verification and reviewable result without waiting for a bench session or push decision.

## Read in full

1. `docs/SENSOR_READINGS_UPGRADE_PLAN.md` — architecture, contracts, milestones, interfaces and acceptance tests.
2. `docs/research/LIO_V3_SENSOR_INFORMATION_ASSESSMENT_2026-11-23.md`.
3. `docs/handoffs/2026-11-23_research_handoff_sensor_information_extraction.md` and `test_results/README.md`.

Then inspect the current configuration, `lio.device`, `lio.scan`, dashboard acquisition/jobs, `lio.food_profiles` adapters/schema/features, tests, packaging and CI. The plan is grounded in `138a9635df7538748b5dda1fddee88db5067b8fb`; reconcile newer changes rather than overwriting them. The historical results are tracked on main; only `test_results/stage_position.json` remains local/ignored.

Use the Nov 19, Nov 20 and Nov 23 quick scans and all tray-v3 anchors specified in the plan. Preserve their raw and historical derived bytes. Real records establish regression/provenance facts; labelled synthetic fixtures establish numerical truth and failure behavior.

## Required implementation

- M0: frozen acquisition/calibration facts, terminal source identity, quantity-specific validity, immutable derived analyses and shared compatibility gates. Repair the string-versus-callable config-hash bug and weak saved-analysis identity checks in `food_profiles/runs.py`.
- M1: exclusive device ownership and crash-durable strict exposure reservations across CLI/dashboard/restarts. Bound actual possible pulse duration before transmission; do not rely on post-hoc accounting or let raw shell/`budget=False` bypass the gate. Preserve safe stop when accounting fails.
- M2: independent primary/control/proxy roles and versioned legacy, validated-control and unidentified coupling models. Unknown C is not zero. H16 remains spectrally unassigned and cannot enter a primary-1850 feature namespace.
- M3: signed fixed-N block estimates, paired control contrasts, covariance-aware uncertainty, explicit assumptions and unresolved results. No noise-selected peak qualification or stop-when-positive inference.
- M4: working targeted stationary protocols, offline preview, fixed allocation and separate-pilot/frozen-production allocation under identical hard budgets. Implement the proposed commands in the plan; do not merely register parsers or return synthetic placeholders.
- M5: one shared target-specific scout/held-out-confirm objective for planning, fine placement, reporting and UI. No automatic travel extension or silent fallback to blind/noisy channels.
- M6: usable CLI/dashboard/report/profile flows, semantic masks, baseline compatibility, migration, packaging and regression checks. Keep heavy analysis off acquisition/control threads and preserve offline `--no-food-library` use.

Keep implementations within the existing scan/device/profile boundaries. Proposed new modules are not permission to build an unrelated workflow framework. Finish each slice with actual outputs and documentation before adding the next acquisition feature.

## Scientific and hardware contracts

- More counts or a healthier verdict is not proof of more optical information. Do not tune thresholds to make the latest failed run pass.
- OPT101 h16 is not 1850 nm chemistry. Manufacturer lower-range uncertainty means red/broadband sources are not guaranteed electrical blinds; it does not automatically qualify them as new spectral channels.
- Record actual gain/LSB, integration, Rf/current provenance and geometry. Preserve unknown/conflicting facts; never apply today's nominal configuration retrospectively.
- Mains-rejected scans use `mains_periods`, not `sweep_n`; current firmware samples the detector inputs sequentially and returns rounded means. Do not invent exact conversion timestamps, simultaneous readings or fractional telemetry.
- Preserve signed data and raw/processed layers. A selected maximum, raw hum residual or firmware N is not an independent measurement uncertainty.
- Keep fixed-N inference first. A separate pilot may set a frozen production budget; ordinary repeatedly inspected intervals are not anytime-valid.
- Actual A0 operating range and optical-path validation remain bench qualification tasks. Unknown/out-of-range A0 does not qualify InGaAs physical current or optical/reference quantities; narrow statistical intervals cannot repair transfer validity. Keep raw/labelled ADC-referred observations and independently valid OPT101 results available. Implement and test valid-input and unqualified paths without fabricating measurements.
- Core acquisition keeps the existing owner-approved fixed gain (gain 1 at the evidence snapshot) and rejects unexpected gain requests/readback. Physical PGA experiments belong to deferred M7; different-gain offline fixtures are not bench authorization.
- Current firmware supports one contiguous scheduled STREAM pulse. Do not implement periodic-lock-in or independent-detector-gain claims through flags the hardware cannot honor.

## Verification and completion

Follow the plan's real-record numerical assertions, synthetic bias/coverage/null/missingness tests, ownership/duty crash/clock/alias fault tests and offline transport guards. Test actual estimator outputs, persisted provenance and usable workflows, not only key names or successful returns.

Run relevant Ruff/format, strict mypy, unit/simulator and fault-matrix checks; maintain Python 3.10/3.12 and the existing coverage gate. Exercise core installs, precision/profile extras, installed-wheel/offline operation, dashboard smoke flows, cancellation/resume and analysis/acquisition concurrency. Use isolated simulator state and outputs. Do not pass hardware/motion test flags or discover a bench port automatically.

An unavailable bench limits physical qualification, not offline implementation completeness. Report M0–M6 completion, checks actually run, changed files and any authorized commits, example working commands, intentional migration behavior, unresolved scientific limits and the separately pending bench qualification. Update usage docs and agent context to match the final implementation. Never claim the upgrade improved measured LIO SNR or recovered primary SWIR/1850 information without the required later measurements.
