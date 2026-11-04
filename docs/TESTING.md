# Testing the LIO V3 controller

How to run the system test suite, what each test checks, how to read the report, and the checklist for the first hardware session (M6). Plan: [TEST_SUITE_PLAN.md](TEST_SUITE_PLAN.md). Protocol: [PROTOCOL.md](PROTOCOL.md).

## 1. Set up once

```bash
cd <repo>
conda env create -f environment.yml        # once; after pulling changes: conda env update -f environment.yml
conda activate lio
lio --version
```

Everything (the `lio` command, pytest, the logger, `lio_motor_control.py`) runs in the `lio` conda environment, defined by `environment.yml` at the repo root. The `lio` package is installed in editable mode, so code changes apply without reinstalling. Without conda, `python3 -m venv .venv && .venv/bin/pip install -e "software/host[dev]"` gives the same.

Hardware tests need firmware v2 on the Nano (§7.2). Close the Arduino Serial Monitor and any other program holding the port: only one program can open it.

## 2. Everyday commands

| Command | What it does |
|---|---|
| `lio ports` | Lists serial ports; `*` marks the one chosen when `--port` is omitted (CH340, FTDI or ATmega16U2) |
| `lio info` / `lio status` | Firmware identity and limits / the current state |
| `lio ping` | Round-trip latency |
| `lio ch 8 on --ms 500` | Lights hole 8 for 500 ms, then everything off |
| `lio meas 8` | Dark and lit readings of hole 8 on both detectors |
| `lio sweep --csv s.csv --plot s.png` | All 16 holes; the CSV has the logger's format |
| `lio motor 1 step 64` | Arms, moves motor 1 (left) 64 half-steps up, waits (asks first) |
| `lio shell` | Keeps the port open; type protocol commands (`help` lists them) |
| `lio selftest ...` | Runs tests and writes a report (§3) |
| `lio dashboard` | The web dashboard: run tests, digital twin, overall verdict (§3) |
| `lio report <run>/results.json` | Rebuilds a report |
| `lio sim-serve` | A simulated LIO on a pseudo-terminal, for practice (§6) |

Add `--sim` to any command to use the simulator, and `--fault <name>` to break it (§6). Add `-v` to print the serial transcript.

**Opening the port resets the Nano** (about 2 s). Each one-shot command therefore starts from the safe power-up state, and everything is off when it exits. That includes Ctrl-C and errors.

## 3. Running the tests

### The dashboard (recommended)

```bash
lio dashboard              # opens http://127.0.0.1:8765/ in the browser
lio --sim dashboard        # the same, on the simulator (add --fault dead_channel:5 etc.)
```

A local web page that runs the same catalogue as `lio selftest`:

- **Connect** to the Nano (choose the port; opening it resets the Nano) or to the simulator.
- **Run** one subsystem from its tile, or **Run whole system**. Options: operator steps (walk test, rail current with a meter, ambient light), motor tests (asks you to confirm someone is at the bench), compare with or save a baseline.
- **Digital twin**: the Nano, shift registers, both rails, the 16 holes, both detectors, the ADC, both motors and the safety logic, each coloured by its result (✓ PASS, ! WARN, ✕ FAIL, ⚠ ERROR, – SKIP, ○ not run). Click a part to see every check that concerns it. On a hole, **Measure** takes one MEAS and **Flash** lights it briefly.
- **Overall system evaluation**: the T11 verdict (FUNCTIONAL / DEGRADED / NOT FUNCTIONAL) over the latest result of every test, with how many of the 45 tests it covers. Subsystem runs add up, so you can test one part at a time and watch the verdict build. The board is rebuilt from the saved runs in `test_results/` whenever the dashboard starts or connects, so it **persists between sessions** (hardware and simulator results kept apart); each test shows the run it came from. **Clear results** starts afresh (remembered in `test_results/dashboard_state.json`); the reports themselves are never deleted.
- **⚡ Wake bank A** (header): holds both motors' coils for 3 s (no steps, nothing moves) to wake power bank A, then reports whether the ADC answers.
- **Operator questions** appear as dialogs (Done / Yes / No / a value / Abort).
- **Stop** (or **All off**) stops the current test at its next command or wait, restores the safe state and keeps the results so far. The firmware's watchdogs and failsafe still bound everything if the computer itself fails.
- Every run writes the usual report folder in `test_results/`; **Earlier runs** opens a report or shows an old run on the twin.

How parts are judged: a hole by every check that names it; a rail, motor or detector likewise. Checks that judge a shared part through individual LEDs (the walk test for the shift registers, T06.1/T06.2 for the detectors) count against that part only when more than `verdict.max_channel_fails` holes fail, the same rule as the verdict: one dark LED is that LED, many point at the shared part. Subsystem tiles always show their tests' real results and name the holes when all their failures are on specific holes.

The page is served on 127.0.0.1 only, and every request must carry a token embedded in the page, so other web sites open in the browser cannot drive the instrument. Port and poll rate: `dashboard:` in `lio_hw.yaml`; `--http-port` overrides the port.

### Whole system (command line)

```bash
lio selftest --sample-id none-empty-chamber --operator <name>                    # automatic tests only
lio selftest --interactive --allow-motion --sample-id ... --operator <name>       # everything
lio selftest --interactive --allow-motion --save-baseline --sample-id ...         # and keep it as the reference
lio selftest --baseline latest                                                   # compare with the latest baseline
```

### One subsystem, or single tests

`--modules` takes test IDs, modules or names. The names are `env link adc sr channels detectors timing sweep motors safety baseline`.

```bash
lio selftest --modules adc                  # T03: I2C and ADC
lio selftest --modules sr,safety            # T04 + T10
lio selftest --modules T05.2,T05.3          # two single tests
lio selftest --modules channels --interactive   # T05 incl. the driver-current meter step
lio selftest --modules motors --allow-motion    # T09 (operator present)
```

| Kind | Runs when | On hardware |
|---|---|---|
| A, automatic | always | nothing moves; LEDs light briefly within the duty budget |
| I, interactive | `--interactive` | prompts at the terminal; type `a` at any prompt to abort (everything off) |
| M, motion | `--allow-motion` | asks first that the chamber is clear; every move is small and undone |

**Exit codes:** 0 FUNCTIONAL, 1 DEGRADED, 2 NOT FUNCTIONAL, 3 could not run.

### With pytest

The same tests, for CI and development:

```bash
pytest -m "unit or sim" --lio-sim                                    # no hardware (CI)
pytest -m sim --lio-sim --lio-fault stuck_on:5                       # catalogue on a broken simulator
pytest -m "hw and not interactive and not motion" --lio-port /dev/cu.usbserial-1120
pytest -m "hw and interactive" --lio-port ... --interactive -s
pytest -m "hw and motion" --lio-port ... --allow-motion -s
```

Options: `--lio-sample-id`, `--lio-operator`, `--lio-notes`, `--lio-baseline FILE|latest`, `--results-dir=PATH`. Use the `=` form, otherwise pytest may take an existing directory as a test path.

### Output

Each run writes `test_results/<YYYYmmdd-HHMMSS>_<host|sim>/`. The folder is gitignored.

| File | Contents |
|---|---|
| `report.html` | Verdict, summary table, plots, every check with its result and criterion. Open this first |
| `report.md` | The same as Markdown |
| `results.json` | The run record: environment, git commit, firmware INFO, config hash, metadata, every result and measurement |
| `meas.csv` | Every MEAS and SWEEP record of the run |
| `plots/` | Channel response, response matrix, dark noise, step responses, repeated sweeps |

## 4. The catalogue

Every check compares a measurement with a threshold from `software/config/lio_hw.yaml`. All thresholds are **provisional** until the M6 calibration. Each result is PASS, WARN, FAIL, SKIP (not applicable or not possible, with the reason) or ERROR (the test could not complete).

| ID | Kind | What it checks | Catches |
|---|---|---|---|
| T01.1 | A | Python and dependency versions recorded | broken install |
| T01.2 | A | Port discovery by USB VID/PID | wrong port, unknown adapter |
| T01.3 | A | Config loads; 16 holes; rails A = 1–9, B = 10–16 | edited YAML |
| T02.1 | A | Boot banner within 3 s of opening the port | wrong firmware, dead board |
| T02.2 | A | 100 PINGs all answered, p99 < 50 ms | flaky USB link (`comms_drop`) |
| T02.3 | A | INFO fields; firmware version; safety limits match the YAML | firmware/YAML mismatch |
| T02.4 | A | Unknown command, bad argument, over-long line, garbage bytes | parser bugs |
| T02.5 | A | `@seq` echo; events between responses don't desynchronise | protocol bugs |
| T02.6 | A | RESET: banner returns, safe state, defaults restored | RESET bugs |
| T03.1 | A | I²C scan finds the ADS1115 at 0x48; `T03.1/bus` checks the SDA/SCL lines (`I2C DIAG`): stuck low, no pull-ups, SDA–SCL bridged, answers only at 100 kHz | `no_adc`, `i2c_bridged`, `i2c_slow`, wiring |
| T03.2 | A | Dark noise on A0/A1 (64 samples); A2/A3 recorded | `noisy_adc` |
| T03.3 | A | Every PGA gain accepted; dark mV agrees across gains | gain errors |
| T03.4 | A | Conversion interval at every data rate | ADC timing |
| T03.5 | A | 60 s dark drift (WARN only) | drift, light leaks, bank B sleep |
| T04.1 | A | 34 shift-register patterns: mask echoed, CE stays low, detectors dark | `ce_inverted`, light without CE |
| T04.2 | A | LOOP TEST through U1 → U2 (optional jumper; SKIP if not fitted) | `chain_break`, clock/data wiring |
| T04.3 | A | Points to T05.3 (optical address check) | — |
| T04.4 | I | Walk test: operator confirms 1–7 by eye and 8–9 by phone camera, in order | swaps the detectors cannot see (`swapped:3,4`) |
| T05.1 | A | Hole 8 / 12: dark with CE low, light with CE high, wrong-rail CE refused | `rail_a_dead`, `rail_b_dead`, `ce_inverted` |
| T05.2 | A | Every hole on both detectors against its `expect` (signal / weak / none); saturation | `dead_channel`, misrouting |
| T05.3 | A | Detector pattern per hole; duplicate signatures; unfitted holes dark; U2 chain diagnosis | `stuck_on`, `swapped`, `chain_break` |
| T05.4 | A | Back to dark after each MEAS | `slow_settle`, LED staying on |
| T05.5 | A | 10 interleaved MEAS per channel: CV ≤ 2 % | unstable drivers, noise |
| T05.6 | I | Driver current with a meter in series (holes 8 and 12) | driver set wrong, dead rail |
| T06.1 | A | OPT101: dark in range, every visible hole seen, not saturated | `opt101_no_feedback` |
| T06.2 | A | InGaAs: dark steady (−5 V present), polarity gate on hole 8, saturation | `reversed_ingaas`, `no_neg_rail`, `tia_saturated` |
| T06.3 | A | Holes 8, 9 seen by both detectors; InGaAs/OPT101 ratio recorded | — |
| T06.4 | I | Dark change with the lid open; back to dark when closed | light leaks |
| T07.1 | A | Step response at 860 SPS on holes 3, 8, 13 | `slow_settle` |
| T07.2 | A | Recommended settle time vs the configured 8 ms (WARN) | `slow_settle` |
| T07.3 | A | MEAS on-time consistent with settle + conversions | firmware timing |
| T08.1 | A | SWEEP: 16 records, valid fields, ≤ 2.5 s | data path |
| T08.2 | A | 5 sweeps: CV per channel; dark stable between sweeps | noise, drift |
| T08.3 | A | Sweep agrees with MEAS | data path |
| T08.4 | A | Sweep CSV byte-identical to the logger format | output format |
| T09.1 | M | STEP refused unarmed / wrong token; ARM works; expires after 60 s | arming bugs |
| T09.2 | M | Each motor +64 / −64 half-steps; operator confirms up then down | `motor_stall`, reversed direction, wiring |
| T09.3 | M | MOTOR STOP answers in < 50 ms and freezes the position | stop latency |
| T09.4 | M | Detector noise while moving vs at rest (WARN if > 3×) | motor EMI on the detectors |
| T10.1 | A | Dark and idle after RESET and after reopening the port | power-up state |
| T10.2 | A | `CH n ON 60000` clamped; LED off at the (lowered) watchdog limit; `# WDT` | watchdog |
| T10.3 | A | 11 s of silence with motion armed: `# FAILSAFE`, everything off | comms-loss failsafe |
| T10.4 | A | CE refused with 0 or 2+ holes selected | single-channel invariant |
| T10.5 | A | Motion disarmed by the failsafe | failsafe |
| T11.1 | A | Per-channel drift against a saved baseline (needs `--baseline`) | ageing LEDs, alignment, changes |

**Shared measurements.** The dark statistics (T03.2), the 16-channel matrix (T05.2–T05.4, T06) and the polarity gate are measured once per run, on first use. Any test also runs on its own.

**Unusable detectors.** A detector whose dark output is erratic or pinned at a rail, or an InGaAs that fails the hole-8 polarity gate, is reported once in T06 with the fix. Later judgments on it are skipped, not failed, so one fault does not bury the report in consequences.

**Safe state.** After every test (pass, fail, error or abort) the runner turns the LEDs off, stops the motors, and restores the default ADC gain and rate and the watchdog limits.

**LED duty budget.** RAIL A runs its LEDs above their rating (30 mA vs 20 mA). The host therefore limits each channel to 1 s of on-time per minute (RAIL B: 5 s). It waits before lighting a channel when needed, and the report shows the total wait. On hardware a full run spends some time cooling down; operator steps cool down *before* asking you to watch.

### Verdict (T11)

| Verdict | When |
|---|---|
| FUNCTIONAL | no FAIL, no WARN |
| DEGRADED | only WARNs; or failures only on holes 10, 11, 15, 16; or at most 2 failing channels |
| NOT FUNCTIONAL | a FAIL or ERROR in an automatic T02, T03, T04 or T10 test; a failure not tied to a channel (e.g. InGaAs polarity, a stuck MOSFET); or more than 2 failing channels |

The plan leaves "1–2 failing channels" unclassified; this suite calls that DEGRADED. Operator steps (T04.4) count by the holes the operator names, not by the critical-module rule.

### Deviations from the plan, and why

| Where | Plan | This suite | Why |
|---|---|---|---|
| T03.4 | ±15 % of the nominal interval | ±15 % plus up to 0.8 ms of I²C overhead | a single-shot conversion includes the I²C transactions, which are about 0.4 ms at 400 kHz, 35 % of the 860 SPS period |
| T05.3 | near-identical signatures = possible swap | groups of 3+ identical signatures (±1 %) FAIL; a pair WARNs | visible holes are seen by the OPT101 only, so two healthy LEDs can match by coincidence |
| T05.4 | detects `stuck_on` | detects slow decay and LEDs staying on | with CE low no current can flow, whatever the MOSFET does; T05.3 catches stuck MOSFETs |
| T05.6 | 2 s flashes | RAIL A 1 s, RAIL B 2 s | RAIL A duty budget (1 s per minute) |
| T10.2 | light off within limit + 50 ms | the clamp is checked from the reply, then the cut-off is timed with the watchdog lowered to 300 ms, allowing the detector's settling time | avoids holding a 20 mA LED at 30 mA for 2 s; a slow detector is not a watchdog fault |
| T10.3 | light a channel, go silent 11 s | arm motion (nothing moves), go silent 11 s | the LED watchdog (≤ 5 s on A) always turns the LED off first |
| `lio selftest` | wraps pytest | runs the same catalogue functions directly | the installed tool needs no test dependencies |
| ADC STREAM | — | ≤ 48 samples captured at full rate, then printed | each `# S` line takes ~3 ms at 115200 baud, slower than 860 SPS |

### Known blind spots

- A stuck-on MOSFET on the hole with the highest forward voltage of its rail (e.g. hole 1) never takes the rail's current. It is optically invisible, and harmless.
- Two visible holes swapped with each other look identical to the detectors. The T04.4 walk test and a baseline comparison (T11.1) catch it.
- The loop-back test (T04.2) needs the optional jumper from U2 pin 9 to D11 (plan §6.3). Without it, the shift registers are checked optically (T05.3).

## 5. Reading a failure

Every FAIL message says what was measured, against what, and the likely cause. The most common ones:

| Message | First thing to check |
|---|---|
| T03.1 ADS1115 not found | read **`T03.1/bus`** first: it says whether SDA/SCL are held low, joined, missing pull-ups, or healthy (then the chip's own ADDR, VDD, GND and the Nano GND). Otherwise **power bank A asleep** (it alone powers the +5 V bus: ADS1115, LEDs, shift registers; see §7.1); then SDA → A4, SCL → A5, ADDR → GND, ADS VDD; both lines idle near 5 V |
| T05.1 no light with CE high | the rail's driver supply and CE wire (A3 / D10) |
| T04.1 / T05.1 light with CE low | CE polarity, or a missing CE pull-down |
| T05.3 U2 receives no data | U1 pin 9 → U2 pin 14, U2 power |
| T05.3 unfitted hole gives light | a stuck MOSFET on that rail; the closest-matching hole is named |
| T06.2 polarity gate | the InGaAs photodiode is reversed: swap its two leads at the TIA input |
| T06.2 dark erratic | the −5 V rail (bank B asleep?) |
| T06.1 output pinned high | OPT101 feedback (pins 4–5) open |
| T07.2 recommended settle | raise `firmware.limits.settle_ms` (and `SETTLE_MS_DEFAULT` in config.h) |
| T09.2 operator did not see it move | driver board, coils, the motor's pins in the YAML, the 5 V supply under load |

## 6. Practising without hardware

```bash
lio --sim dashboard                                        # the dashboard on the simulator
lio --sim selftest --interactive --allow-motion            # the whole catalogue in seconds
lio --sim --fault reversed_ingaas selftest --modules detectors
lio sim-serve                                              # prints a port such as /dev/ttys005
lio --port /dev/ttys005 info                               # in another terminal: the real serial path
```

Simulator faults: `no_adc`, `stuck_on:<n>`, `dead_channel:<n>`, `swapped:<a>,<b>`, `rail_a_dead`, `rail_b_dead`, `ce_inverted`, `reversed_ingaas`, `no_neg_rail`, `tia_saturated`, `opt101_no_feedback`, `noisy_adc`, `slow_settle`, `chain_break`, `motor_stall`, `comms_drop`. Combine them with commas. `tests/system/test_fault_matrix.py` proves that each one is detected by its intended test, with a healthy control.

## 7. First hardware session (M6) checklist

Do this with the user present. Motion steps only with someone at the bench.

### 7.1 Bench

- [ ] Chamber **empty and closed**, sample nest in place (baseline sample `none-empty-chamber`)
- [ ] Stages somewhere in mid-travel: nothing can be hit by a small move
- [ ] Power banks charged, **and kept awake**: about +5 V between the +5 V bus and GND (bank A), and about −5 V at TL072 pin 4 (bank B). USB banks switch off when the load is small, and firmware v2 draws almost nothing when idle (it releases the motor coils), so they go to sleep within a minute or so. Use each bank's always-on / low-current mode if it has one (often a double press of its button), or a dummy load across each bank (for example 47 Ω, 1 W: about 100 mA, it gets warm). The old motor sketch kept them awake only because it held the coils energised all the time
- [ ] Bank A is woken by the software (`POWER WAKE`: the motor coils are held for 1 s, nothing moves) when the port opens, before each test and before Measure/Flash. **Bank B cannot be woken from software**: it needs its always-on mode or a dummy load. If bank A still drops out, the firmware finds the ADC again on its next use
- [ ] Nano connected **directly** to the Mac, not through the dock/hub
- [ ] Multimeter with mA range and leads (T05.6); phone camera for holes 8–9 (T04.4)
- [ ] Nothing else holding the port (Arduino IDE Serial Monitor, `lio_motor_control.py`)
- [ ] Optional, only if agreed: the U2 pin 9 → D11 loop-back jumper (T04.2)

### 7.2 Flash firmware v2

M0.5 found the board has the **new (Optiboot) bootloader**.

```bash
cd <repo>
lio ports                                   # note the port, e.g. /dev/cu.usbserial-1120
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328 software/firmware/lio_firmware
arduino-cli upload  --fqbn arduino:avr:nano:cpu=atmega328 -p /dev/cu.usbserial-1120 software/firmware/lio_firmware
```

- Old bootloader instead (the upload fails with `not in sync`): use `cpu=atmega328old` in both commands.
- Optional hardware watchdog (new bootloader only): add `--build-property "compiler.cpp.extra_flags=-DLIO_HW_WDT=1"` to the compile command.
- Check: `lio --port /dev/cu.usbserial-1120 info` shows `fw 2.0.0`, `proto 1` and `adc_ok 1`.
- Roll back: the TEST_MODE firmware is `software/firmware/lio_firmware/` at tag `fw-testmode-v1`. Check it out beside the repo with `git worktree add ../lio-testmode fw-testmode-v1` and flash `../lio-testmode/software/firmware/lio_firmware`. The old AccelStepper motor sketch (tag `software-legacy-v1`, `software/firmware/legacy/lio_motor_control/`) must **not** be flashed on the current wiring: it reads CE2 (D10) as a pressed UP button and starts moving by itself after every reset.

### 7.3 Order of the session

Stop at the first NOT FUNCTIONAL in steps 1–3 and fix the cause before going on. Each step writes its own report.

With the dashboard (`lio dashboard`, §3), connect to the port and run the same steps from the tiles, in the same order: Host environment and USB link, then ADC, then Shift registers and Safety, then LED channels, Detectors, Timing and Sweep, then tick "Include operator steps" and run those tiles again for the operator steps, then Motors, then **Run whole system** with "Save as baseline". The commands below do the same from the terminal.

1. **Link and identity:** `lio selftest --modules env,link`
2. **ADC:** `lio selftest --modules adc`. If T03.1 fails, this is the earlier I²C hang: check SDA/SCL near 5 V idle, and that bank A is awake.
3. **Selection and safety:** `lio selftest --modules sr,safety`. T10.3 and T10.5 arm motion for 11 s but send no motor command.
4. **Optics:** `lio selftest --modules channels,detectors,timing,sweep`. A reversed InGaAs shows up here (T06.2) with the fix.
5. **Operator steps:** `lio selftest --modules T04.4,T05.6,T06.4 --interactive`, with the meter and phone ready.
6. **Motors** (user present, chamber clear): `lio selftest --modules motors --allow-motion`. Watch which way each stage moves: + must be **up** (approved convention). If it is down, stop and tell the developer; do not continue.
7. **Whole system + baseline:**
   `lio selftest --interactive --allow-motion --save-baseline --sample-id none-empty-chamber --operator <name>`
8. **After the session:** calibrate the provisional thresholds in `lio_hw.yaml` from the report (dark ranges, noise, detection levels, CV, settle time), set `provisional: false` where calibrated, and open an issue for every FAIL and WARN.

`software/control/lio_motor_control.py` (the Tkinter jog window) keeps working on firmware v2 through the bounded legacy jog commands (PROTOCOL.md §7).
