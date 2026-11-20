# Research handoff: LIO V3 diagnostic suite and hardware dashboard

**Date:** 16 November 2026
**From:** the engineering session that built and ran the current suite.
**Repository:** https://github.com/Brandonio-c/LIO. Local clone: `/Users/coleloughbc/Documents/VSCode-Local/LIO`.

## 1. Your task

You are the research agent for this phase. Produce two plans.

1. **An assessment of the diagnostic suite, and an engineering plan to make it a full diagnostic suite.** The suite should find, localise and explain every fault this instrument can plausibly have: electrical, optical, mechanical, firmware, and host-to-firmware.
2. **A plan to upgrade the dashboard** so it explains the physical device as well as testing it:
   - every component and every wire, with its role and its electrical values;
   - **symbolic circuit diagrams** that the user can click to open each component's details: part number, pins, nets, datasheet values, expected voltages, and which tests check it, with their latest results.

**Research only.** Read the code, documents and data files, and research the external material you need: datasheets, diagnostic methods for photodiode amplifiers, schematic-rendering options, and so on. Do **not** run anything that talks to the hardware, flash firmware, change wiring instructions, or push to git. The hardware owner decides those.

## 2. What the instrument is

LIO V3 is an open-hardware, 3D-printed **multispectral diffuse-reflectance scanner for powdered food samples**. Sixteen LEDs (395 nm to 1850 nm) sit in a ring around a sample chamber and are lit one at a time. Two detectors measure the reflected light:
- **OPT101**, silicon, for the visible and near-IR holes;
- **InGaAs photodiode with a TL072 transimpedance amplifier**, for the short-wave IR holes.

A motorised top moves vertically, to change the measurement geometry and so the amount of light returned.

The goal is repeatable, calibrated spectral signatures for closed-world classification. Measurement integrity comes first: the instrument has to be proven trustworthy before it is used.

## 3. Hardware: the sources of truth in the repository

| What | Where |
|---|---|
| Net list | `electronics/data/netlist.csv` (net → connected points; 22 nets) |
| Bill of materials | `electronics/data/bom.csv` (ref, qty, part, spec, notes) |
| Microcontroller pin map | `electronics/data/nano_pinmap.csv` (pin, net, direction, connects_to, notes) |
| Channel map | `electronics/data/channel_map.csv` (hole → LED, wavelength, shift-register output, rail, driver, detector, MOSFET, gate resistor, pull-down) |
| Full schematic (generated) | `electronics/LIO_full_schematic.svg` and `.html`, drawn by `electronics/source/gen_full.py`: hand-placed SVG primitives, **not** interactive |
| Technical description | `electronics/docs/LIO-ELEC-001_Electronics_Technical_Description.pdf/.docx` (Rev A) |
| Wiring checklist | `electronics/WIRING_CHECKLIST.md` |
| Overview and warnings | `electronics/README.md` |
| Hardware configuration for software and tests | `software/config/lio_hw.yaml`: every hardware constant and test threshold; all thresholds are marked *provisional* |
| Design history | `docs/PROJECT_LOG.md`, `docs/DESIGN_DECISIONS.md`, `docs/OPTICAL_CHANNEL_MAP.md`, `docs/HARDWARE_INVENTORY.md`, `docs/LED_SOURCING.md`, `docs/OPEN_ITEMS_AND_NEXT_STEPS.md` |
| CAD | `CAD/`, `CAD/V3/` (OpenSCAD; the V3 master and the dual-detector plate) |

### The circuit in brief (check against the files)

- **Controller: an Arduino Nano R4** (Renesas RA4M1, board ID `arduino:renesas_uno:nanor4`), on USB to a Mac.
  - The BOM and some documents still say an ATmega328P Nano. That's a known inconsistency for the plan to resolve.
  - The firmware also builds for the classic Nano.
- **LED selection:**
  - Two 74HC595 shift registers (U1: holes 1–8, U2: holes 9–16) choose one LED through 2N7000 MOSFETs. Each has a 220 Ω gate resistor and a 10 kΩ pull-down.
  - Two constant-current LED drivers (DRV1, rail A, holes 1–9, enabled by CE1; DRV2, rail B, holes 10–16, enabled by CE2) supply the current.
  - The rule: exactly one hole, and only its rail enabled.
- **ADC:** an ADS1115 at I²C address 0x48.
  - The I²C bus is a **software bus on D11 (SDA) and D12 (SCL)**, with 4.7 kΩ pull-ups. It moved from A4/A5 during an earlier fault.
  - **A0 = InGaAs amplifier output, through a 10 kΩ series resistor. A1 = OPT101 output. A2 and A3 are unconnected** (used as the "floating input" reference).
- **OPT101 (U4), a CJMCU-101 module:** pin 4 (1 MΩ) jumpered to OUT; output to A1. Now soldered in; the dark reading is about 7 mV and very quiet.
- **InGaAs amplifier:**
  - photodiode **D1**, MTPD1346D-100 in a TO-46 can, about 800–1750 nm, with three leads: anode, cathode and case;
  - op-amp **U5**, a TL072 on ±5 V; Rf = 1 MΩ; Cf, pins 1–2, **now 100 pF** (was 10 pF); the unused half is tied off.
- **Power:**
  - **+5 V and −5 V come from two separate supplies in series.** They were USB power banks; now two two-prong USB wall chargers. Their junction is circuit GND.
  - **Circuit GND is now earthed** through the earth pin of a wall plug. This cut the InGaAs 60 Hz hum from 8.5 mV to about 1 mV.
  - −5 V feeds only the TL072 (pin 4).
- **Motors:** two 28BYJ-48 steppers driven by ULN2003 boards, motor 1 (left) on D2–D5 and motor 2 (right) on D6–D9.
  - They lift **one chamber top** together, so they must always move in lockstep.
  - 4,096 half-steps per output turn.
  - **There are no limit switches.** The measured travel is **420,017 half-steps**, about 102.5 turns, top to bottom.

### The 16 holes (from `lio_hw.yaml`; `channel_map.csv` is older for holes 10–11)

| Holes | Light | Detector meant to see it |
|---|---|---|
| 1–7 | 395 nm, 405 nm, blue, green, yellow, orange, red | OPT101 |
| 8, 9 | 850 nm, 940 nm | both (cross-calibration holes) |
| 10, 11 | white, pink | OPT101; `channel_map.csv` still says "reserved" |
| 12–14 | 1450, 1550, 1650 nm | InGaAs |
| 15 | 1760 nm | InGaAs, weak, at its cut-off |
| 16 | 1850 nm | beyond both detectors; an extended InGaAs is a future item |

Rail A (DRV1) serves holes 1–9 and rail B (DRV2) holes 10–16.

## 4. Firmware

- **Source:** `software/firmware/lio_firmware/`: `lio_firmware.ino`, `optics.*`, `adc.*`, `motors.*`, `safety.*`, `softi2c.*`, `protocol.*`, `config.h`.
- **Version:** **2.4.0 is flashed** as of 16 Nov. It added `MOTOR LIGHT <0|1>`, below.
- **Protocol:** `docs/PROTOCOL.md`. Line-based commands and replies (`OK …` / `ERR … code=`), plus `# EVENT` lines.
  - Commands: `INFO`, `STATUS`, `PING`, `RESET`, `I2C SCAN|DIAG`, `ADC READ|CFG|STREAM`, `SR RAW`, `CE`, `CH`, `OFF`, `MEAS`, `SWEEP`, `WDT CFG`, `MOTOR ARM|STEP|STOP|RELEASE|LIGHT`, `POWER WAKE`, `LOOP TEST`.
  - The legacy jog commands are also accepted: `U D LU LD RU RD S VA VS ACC POSL0 POSR0`.
- **Safety, enforced in firmware:**
  - a power-up dark state;
  - per-rail LED on-time watchdogs;
  - only one LED at a time;
  - a comms-loss failsafe (10 s);
  - motion needs a token-armed 60 s window;
  - moves are bounded (≤ 2,048 half-steps per command);
  - coils are released after every move;
  - **motion and light are mutually exclusive, unless `MOTOR LIGHT 1` is set** (armed only; it lapses with the arm).
- **Position counters** (`pos1`, `pos2`) restart at 0 whenever the port is opened or the board resets. The host keeps the true position (§6).

## 5. Host software and the current diagnostic suite

**Package:** `software/host/src/lio/` (Python 3.12, conda environment `lio`; ruff and mypy strict; about 690 pytest tests, which run against a full simulator).

| Module | Role |
|---|---|
| `device.py` | Typed, safe device API: duty budget, arming, stage tracking hooks |
| `transport.py` | Serial and simulator transports |
| `sim.py` | **Simulator** of the firmware and physics, with fault injection: `--fault dead_channel:5`, `stuck_on:8`, `swapped:3,8`, `no_adc`, `i2c_bridged`, `rail_a_dead`, … |
| `stage.py` | Position tracking across sessions (new 16 Nov) |
| `suite/core.py`, `suite/runner.py`, `suite/judge.py`, `suite/checks/t*.py` | Test registry, runner, channel judging, checks |
| `analysis.py`, `report.py`, `results.py`, `baseline.py`, `csvout.py` | Statistics, HTML/Markdown reports, result model, baselines, CSV |
| `dashboard/server.py`, `dashboard/session.py`, `dashboard/twin.py`, `dashboard/static/index.html` | Local web dashboard (one file, about 2,200 lines of HTML and JavaScript) |
| `cli.py` | `lio` command: `info`, `status`, `meas`, `sweep`, `motor`, `stage`, `selftest`, `report`, `shell`, `dashboard`, … |

**Documents:** `docs/TESTING.md` (how to run, the catalogue table, first-hardware checklist), `docs/TEST_SUITE_PLAN.md` (the original plan, LIO-SW-TEST-001 Rev A).

### Catalogue (47 tests; kinds: A automatic, I interactive operator, M motion)

| Module | Tests |
|---|---|
| **T01** environment | T01.1 Python and dependency versions; T01.2 serial port discovery; T01.3 config consistency |
| **T02** link | T02.1 boot banner; T02.2 PING latency; T02.3 INFO fields and safety limits; T02.4 bad input; T02.5 sequence numbers; T02.6 RESET |
| **T03** ADC | T03.1 I²C scan (+ `I2C DIAG` line checks); T03.2 dark noise on all inputs; T03.3 gain sweep; T03.4 data rate; T03.5 long-term dark stability |
| **T04** shift registers | T04.1 patterns with CE low; T04.2 loop-back (jumper not fitted: SKIP); T04.3 optical address (covered by T05.3); T04.4 **I** walk test |
| **T05** channels | T05.1 rail gating by CE1/CE2; T05.2 per-channel response; T05.3 address and isolation (signatures, duplicates); T05.4 off-state return; T05.5 repeatability; T05.6 **I** driver current with a meter |
| **T06** detectors | T06.1 OPT101; T06.2 InGaAs amplifier; T06.3 cross-calibration on holes 8 and 9; T06.4 **I** ambient light |
| **T07** timing | T07.1 step response and settling; T07.2 recommended settle time; T07.3 MEAS timing |
| **T08** sweep | T08.1 schema; T08.2 repeated sweeps; T08.3 sweep vs MEAS; T08.4 CSV format |
| **T09** motion (**M**) | T09.1 arming; T09.2 each motor both ways (±64 half-steps); T09.3 STOP latency; T09.4 detector noise while moving; **T09.6 full travel in lockstep (new)**; **T09.7 detectors while the chamber moves (new, firmware 2.4.0)**. T09.5 is reserved for `lio_motor_control.py` integration |
| **T10** safety | T10.1 power-up dark; T10.2 on-time watchdog; T10.3 comms-loss failsafe; T10.4 single-channel invariant; T10.5 motion disarmed after comms loss |
| **T11** | T11.1 comparison with a saved baseline (none saved yet) |

**Verdict logic.** T11 gives FUNCTIONAL, DEGRADED or NOT FUNCTIONAL from critical modules, failures not tied to a channel, and the number of failing channels (`verdict.max_channel_fails` = 2). The dashboard's "digital twin" (`twin.py`) colours each part by the worst sub-result that concerns it.

**Recent rule change.** Each hole is now judged only by the detector(s) its `expect` names, via the setting `channel.judge_out_of_range: false`. A reading on the other detector is recorded as "not judged". Strict mode (`true`) also catches electrical crosstalk, but flagged every visible hole on the InGaAs.

## 6. Position tracking and motion (new, 16 Nov)

- **`lio.stage`** keeps the absolute position of both motors in `test_results/stage_position.json`, in half-steps from the top (top = 0, bottom = −420,017).
  - `LIODevice` rebases it at every firmware `# BOOT` and updates it from every reported position.
  - Limits are marked from the dashboard Motors tab ("Set top here" / "Mark bottom here") or with `lio stage set-top|mark-bottom|show|forget`.
  - **Soft limits:** step moves beyond the range are refused, continuous jogs stop short of a limit, and the top keeps a margin of **4,096 half-steps**, one turn, until the count over the full travel is proven.
  - A move made by hand or by `lio_motor_control.py` isn't seen.
- **T09.6 and T09.7** use the tracked limits.
  - Long moves are now **one continuous jog of both motors** at 500 half-steps/s. It is renewed every 1,024 half-steps without a new ramp, stopped just before the target, and finished with an exact step move per motor.
  - The first rig attempt used 1,024-step pulses, and the user stopped it: too slow, and not continuous. The continuous version is tested on the simulator only; **it has not run on the rig yet**.
  - T09.7 stores a response-vs-height scan in `results.json`.
- **Code status:** firmware 2.4.0, stage tracking and the motion rewrite are committed **locally** on branch `feature/motion-travel-tests` (three commits). Not pushed.
- **Other branches:**
  - `fix/judge-by-detector-range` is pushed, with a pull request link pending;
  - `feature/structured-ingredients` is pushed (food-library work, unrelated to this task).

## 7. Bench findings (15–16 Nov): what the current suite caught and missed

Read these closely: they show where the suite needs depth.

1. **OPT101 output wasn't reaching A1:** a loose module. After soldering it in, the dark reading is 7 mV, noise σ 0.05 mV, and T06.1 passes. Open air: 4.3 V under a phone torch, 200 mV covered.
2. **InGaAs hum.** 60 Hz pickup of 8.5 mV and noise σ 58 counts (one count = 0.125 mV) made every InGaAs channel "fail". Cause: the floating wall chargers' Y-capacitor leakage. Fixed by earthing circuit GND through a resistor. The suite reported "noise too high", but nothing in it identified *mains hum* specifically (60/180 Hz components).
3. **The InGaAs photodiode was never connected to the amplifier.** The white wire on TL072 pin 2 was the **can (case) lead**. Then the anode and case were briefly on the wrong rail. This showed up as hum, a −22 mV offset, and an LED-current-correlated "signal" of about 70 counts on every hole regardless of wavelength. A hole-to-hole comparison (visible holes vs IR holes on the same rail) exposed it. The suite had no check that the InGaAs response depends on wavelength, or that its "signal" isn't simply LED current coupling in.
4. **A ground-reference shift.** While an LED is on, its return current shifted the amplifier's reference by about 10 mV through the shared breadboard ground. It went away once the photodiode anode and case went to TL072 pin 3 and pin 3 went straight to the ADS1115 GND.
5. **A steady −21 mV InGaAs dark offset remains.** About 21 nA leaks into the pin 2 junction (the inputs are balanced; pin 2 = pin 3 on a meter).
   - Ruled out: two TL072s, the Cf change, the photodiode, grounding, ADC gain (identical in mV at gains 2/3–4), drift.
   - Suspected: breadboard leakage at the pin 2 row.
   - It fails T06.2 (dark limit −100 counts).
   - Options: bias pin 3 to about +50 mV, move or solder the pin 2 junction, or widen the limit. The user doesn't want to move the op-amp.
6. **InGaAs light response is weak:** 20–50 counts (a few nA). 1650 nm is the strongest (+50), and 850 nm gives +24, although the OPT101 sees that LED at +185. Probably the optical path: the deck's Ø24 window needs to be about Ø34 for the off-axis InGaAs (open item B). Holes 12–15 "passing" at about 70–75 counts earlier was the ground shift, not light.
7. **Hole 9 (940 nm) is dead on both detectors.** Suspect the LED or its MOSFET Q9.
8. **The OPT101 sees hole 16 (1850 nm) at about 390–400 counts,** which silicon cannot. Unexplained: wrong LED fitted, or electrical. It's a WARN.
9. **Empty-chamber OPT101 signals are small** (17–75 counts). Thresholds are provisional; there's no sample and no baseline yet.
10. **The dashboard showed stale results.** It rebuilds the board only on start or connect, so a CLI run didn't appear until a restart.
11. **A results-file name clash crashed the dashboard at startup:** a non-run `results.json` in `test_results/`. Fixed: such files are skipped.

The raw data for these findings is in `test_results/opt101_check/` (`hum_log.jsonl`, `diag.json`, `allmeas_*.json`, `tia_probe.json`) and in the run folders `test_results/2026111*_host/`.

## 8. Constraints and conventions

- **Safety and process**, set by the hardware owner:
  - no firmware flashing without approval;
  - no motor motion without an explicit "go";
  - interactive steps need an operator;
  - never touch `software/control/lio_motor_control.py`, the CAD files or the electronics documents without asking;
  - never delete files;
  - commit and push only when asked.
- **Code:** Python ≥ 3.10, typed (mypy strict), ruff, pytest. Every test must also run against the simulator (`--lio-sim`), with fault-injection rows in `tests/system/test_fault_matrix.py`. Thresholds live only in `lio_hw.yaml`.
- **Dashboard:**
  - served on 127.0.0.1 only, with a per-session token;
  - one static page (`index.html`) plus a JSON API in `server.py`;
  - no external CDNs today: assess whether a library is acceptable, and vendor it if so;
  - dark theme;
  - views: System (twin and verdict), Motors, LEDs, Database (food library).
- **The user's style:** plain, direct explanations; numbers with units; and the "why".

## 9. Deliverables

### A. Diagnostic suite assessment and engineering plan

1. **A gap analysis** of the catalogue against a fault model. For every plausible fault, say whether it's detected, localised to a part, and explained to the user.
   - Electrical: opens and shorts per net, a wrong pin, supply sag, ground shift, hum and EMI, leakage, amplifier offset, oscillation, saturation, reversed or disconnected photodiode, wrong LED fitted, dead LED or MOSFET, driver current.
   - Optical: light leaks, misalignment, a blocked window, stray light.
   - Mechanical: lost steps, binding, the two sides out of level, limits, backlash.
   - Firmware and protocol, host and software, and supplies (sleep, sag, charger leakage, earthing).
2. **Research-backed diagnostic methods,** with how this hardware can do them (or a minimal add-on). Among others:
   - **spectral noise analysis:** 60/120/180 Hz and charger switching frequencies, with mains-synchronous averaging;
   - **LED-current coupling detection:** correlating the response with LED current or wavelength, and dark-vs-lit signatures on the out-of-band detector;
   - **wavelength-plausibility checks** using the detector responsivity curves in `lio_hw.yaml`;
   - **amplifier health:** offset vs gain, step response, and estimating leakage current from the offset;
   - **supply monitoring:** could a spare ADC input (A2/A3) read the ±5 V rails through dividers?
   - **position verification without switches:** stall or step-loss detection, optical height signatures from the T09.7 scan, and repeatability of the T09.6 return;
   - **an end-to-end standard:** a reference tile, or a baseline sweep with drift tracking;
   - **operator-guided fault isolation:** "measure pin X to Y; expect Z" as interactive steps with recorded answers.
3. **An engineering plan:** milestones (each a pull request), new tests with IDs and kinds, firmware changes (if any, flagged for approval), simulator fault models to add for each new check, acceptance criteria, and effort estimates.
4. **Explicit recommendations** on the open items in §7: items 5, 6, 7 and 8, plus the provisional thresholds and baseline strategy.

### B. Dashboard upgrade plan, with interactive circuit diagrams

1. **A device model:** one machine-readable source for components, pins, nets, wires (colours where known), connectors, power domains and the expected voltage at each test point. Recommend extending `electronics/data/*.csv` or adding a YAML/JSON model. Reconcile the inconsistencies (Nano R4 vs ATmega328P; holes 10–11; the InGaAs wiring as now built).
2. **Clickable symbolic schematics** generated from that model: whole system, LED chain, detector front ends, power and grounding, motors. A click on a component opens a panel with:
   - part number and datasheet link, pinout and role;
   - nets on each pin;
   - expected and measured values (live where the ADC allows);
   - the tests that cover it, with their latest results and evidence;
   - known faults and how to check them by hand.
   Evaluate the options and recommend one with reasons: extending `gen_full.py` to emit SVG with `data-` IDs; KiCad schematic plus `kicad-cli` SVG export with component IDs; netlistsvg/Yosys-style auto-layout; elkjs/d3 auto-layout; Schemdraw; WireViz for wiring harnesses; others you find. Criteria: offline, no CDN, generated from the model, readable symbols, maintainable by one person.
3. **Wiring views:** breadboard and harness level (which wire goes where, colour, and the checklist items from `WIRING_CHECKLIST.md`), linked to the schematic.
4. **Live data on the diagrams:** the digital-twin status per part, the last ADC values per detector, the stage position and limits, and supply status if measurable.
5. **UX:** layout within the existing single-page dashboard, performance, keyboard and accessibility, and the dark theme.
6. **An implementation plan** with milestones, file structure, tests (pure-Python generation tests, plus a browser smoke test), and effort.

## 10. Open questions to raise with the owner

- Can spare ADC inputs (A2/A3) be used for supply and ground monitoring? This needs a small wiring change and approval.
- Should the T06.2 dark limit be widened, or should pin 3 be biased (+50 mV)?
- Should the classic-Nano build target be kept?
- Is it acceptable to add third-party JavaScript or Python libraries for the diagrams? Vendored only, or none at all?
- Is a reference reflectance standard available or planned, for end-to-end checks?
