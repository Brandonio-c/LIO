# LIO V3 — System Test Suite: Software Engineering Plan

**Document:** LIO-SW-TEST-001, Rev A, 2 November 2026
**Repository:** `github.com/Brandonio-c/LIO` (local: `/Users/coleloughbc/Documents/VSCode-Local/LIO`)
**Related:**
- `electronics/docs/LIO-ELEC-001_Electronics_Technical_Description.pdf`
- `electronics/data/*.csv`
- `docs/*.md`
- `software/firmware/lio_firmware/lio_firmware.ino`

---

## 1. Goal

Build a software suite that determines, module by module and then end to end, how much of the as-built LIO V3 prototype works. It has to answer, with evidence:

1. Can the host talk to the controller reliably?
2. Do the ADC and both detectors read sensibly (offsets, noise, polarity, saturation)?
3. Does channel selection (2× 74HC595) address all 16 channels correctly, with nothing stuck on or off?
4. Do both LED drivers and rails enable and disable correctly?
5. Does every fitted LED produce a signal on its expected detector, repeatably and in isolation?
6. How fast do the optics settle, and is the sweep timing right?
7. Do the motors move on command without disturbing the measurements?
8. Do the safety behaviours work (power-up dark state, LED on-time watchdog, motion guard)?

The output of every run is a machine-readable result file plus a human-readable report that states PASS / FAIL / WARN / SKIP per test, with measured values against the criteria.

## 2. System under test (facts the software must encode)

| Item | Value |
|---|---|
| Controller | Arduino Nano (ATmega328P, 16 MHz, **2 KB SRAM**, 32 KB flash), USB serial at 115200 baud. Opening the port resets the board (DTR), so the host must wait about 2 s for a banner |
| Shift registers | 2× 74HC595 daisy-chained. A0 = DATA → U1 pin 14; A1 = CLOCK → both pin 11; A2 = LATCH → both pin 12; U1 pin 9 → U2 pin 14. Bit (n−1) selects hole n; send the high byte (U2) first, MSB first |
| Channel switches | 16× 2N7000, one per LED. **Outputs can't be read back** (see §6.3, optional loopback jumper) |
| LED drivers | DRV1 (RAIL A, holes 1–9) enabled by A3 (CE1); DRV2 (RAIL B, holes 10–16) enabled by D10 (CE2). Both CE pins have 10 kΩ pull-downs. DRV1 is at its 30 mA minimum, which **exceeds the 20 mA rating of the 5 mm LEDs**, so RAIL A on-time must be limited |
| Switching order | Select the MOSFET first, then raise CE. Drop CE before changing channel. Only one channel on at a time |
| ADC | ADS1115 at I²C 0x48 (A4 SDA, A5 SCL). ADS A0 = InGaAs TIA output (through 10 kΩ); ADS A1 = OPT101; A2/A3 unconnected. GAIN_ONE = ±4.096 V, 125 µV/count. Default 128 SPS (≈8 ms per conversion) |
| OPT101 | Silicon, ≈300–1100 nm, holes 1–9. Dark ≈ tens of mV. Saturates at ≈3.7 V (≈29,600 counts) |
| InGaAs + TL072 TIA | ≈800–1750 nm, holes 8–15. Rf = 1 MΩ, Cf = 10 pF, ±5 V. Output **should rise** with light; it saturates at ≈+3.5 V (≈28,000 counts). If it falls with light, the photodiode is reversed (a known historical wiring error), which is a **hard fail with a diagnostic**. If −5 V is lost (bank B asleep), the output becomes erratic |
| Emitters | 1 = 395 nm, 2 = ≈405, 3 blue, 4 green, 5 yellow, 6 orange, 7 red, 8 = 850, 9 = 940, 10–11 reserved (empty), 12 = 1450, 13 = 1550, 14 = 1650, 15 = 1760 (weak, at InGaAs cutoff), 16 = 1850 (beyond detector range; expect no signal) |
| Motors | 2× 28BYJ-48 through ULN2003. D2–D5 = motor 1 IN1–IN4, D6–D9 = motor 2. **No limit switches** exist: never home automatically and never move unattended |
| Spare pins | D11, D12 (digital); A6, A7 (analog input only) |
| Existing host code | `software/control/lio_control.py`: purpose and protocol unknown. **It must be read and understood before any firmware change.** Don't break it without the user's agreement |

All hardware constants go in a single config file (§5.4), never hard-coded in test logic.

## 3. Architecture overview

```
┌──────────────────────── Host (Mac, Python ≥3.10) ────────────────────────┐
│  lio CLI  ─┐                                                             │
│  pytest   ─┼─► lio.device (high-level API) ─► lio.protocol ─► transport  │
│  logger   ─┘         ▲                                         │         │
│                      └──── lio.sim (simulated LIO, same protocol) ◄──────┤
│  lio.report ◄── results JSON ◄── test suite (unit | sim | hw | ...)      │
└──────────────────────────────────────────────────────────────────────────┘
                     │ USB serial, line-based command protocol (§4)
┌──────────────────── Firmware (Arduino Nano) ─────────────────────────────┐
│ command parser → optics (595 + CE + watchdog) · adc (ADS1115) · motors   │
│                  safety (power-up dark, on-time limits, motion guard)    │
└──────────────────────────────────────────────────────────────────────────┘
```

Key design choices:

1. **The firmware becomes command-driven.** It replaces the compile-time `TEST_MODE` switch with a serial protocol. The tests then need no re-flashing, and the same firmware serves tests, the logger and future production use.
2. **A simulator speaks the identical protocol.** About 90% of the host code and test logic can then be developed and run in CI without hardware, and faults can be injected (stuck channel, reversed InGaAs, dead rail, missing −5 V, noisy ADC) to prove the tests detect them.
3. **Tests are marked by what they need:** `unit`, `sim`, `hw`, `interactive`, `motion`. Nothing that moves hardware or needs a human runs by default.
4. **Safety is enforced in firmware**, not only in host code: LED on-time limits, power-up dark state, and refusing motion unless it is explicitly armed.

## 4. Firmware: command protocol v1

### 4.1 Framing

- ASCII, one command per line, terminated by `\n`. Case-insensitive command words. At most 64 characters per command line.
- Every command gets exactly **one** response line:
  - `OK <cmd> key=value key=value …`
  - `ERR <cmd> code=<int> msg=<text>`
- Asynchronous event lines start with `#` (for example `# WDT ch=8 off`, `# BOOT`). The host must tolerate them at any time.
- Optional sequence number: if a command starts with `@<n> `, the response echoes `@<n>`. The host uses this to match responses and detect loss.
- Key=value lines rather than JSON, because of the 2 KB SRAM limit. Use `F()` strings, no `String` class, and fixed buffers.
- Boot banner: `# BOOT fw=lio <semver> proto=1 build=<date>`.

### 4.2 Command set (minimum)

| Command | Effect | Response fields |
|---|---|---|
| `PING` | Liveness | `uptime_ms` |
| `INFO` | Identity and configuration | `fw`, `proto`, `adc_addr`, `gain`, `rate`, `settle_ms`, `wdt_a_ms`, `wdt_b_ms`, `motion_armed` |
| `STATUS` | Current state | `ch` (0 = none), `ce1`, `ce2`, `mask` (hex), `motor1`, `motor2`, `faults` |
| `I2C SCAN` | Scan the bus | `addrs=0x48,…` |
| `ADC READ <0-3> [n]` | Single-ended read; mean of n samples | `ch`, `raw`, `mv`, `n`, `std` (if n > 1) |
| `ADC CFG GAIN <2/3,1,2,4,8,16>` / `ADC CFG RATE <8…860>` | Configure the PGA and data rate | echo |
| `ADC STREAM <ch> <n> <interval_ms>` | n lines `# S t_us raw`, then OK | For settling and noise tests |
| `SR RAW <hex16>` | Low-level: shift any 16-bit mask. **CE is forced low first** and stays low | `mask` |
| `CE <1|2> <0|1>` | Low-level driver enable. Refused unless exactly one bit is set in the mask *and* it belongs to that rail (unless `CE … FORCE` in a debug build) | `ce1`, `ce2` |
| `CH <1-16> ON [ms]` | Safe sequence: CE off → select → CE for that hole's rail on. Auto-off after `ms`, or after the rail's watchdog limit if smaller | `ch`, `rail`, `until_ms` |
| `OFF` | CE both off, mask = 0 | |
| `MEAS <1-16> [settle_ms] [n]` | Atomic: dark read (both ADC channels) → CH on → settle → lit read → off | `ch`, `dark0`, `dark1`, `lit0`, `lit1`, `t_on_ms` |
| `SWEEP [settle_ms] [n]` | MEAS for holes 1–16. Streams `# M …` lines, then `OK SWEEP n=16 dur_ms=` | |
| `LOOP TEST` | Optional, needs the jumper in §6.3: shifts patterns and reads U2 Q7′ on D11 | `pass`, `bits_ok`, `bits_bad` |
| `MOTOR ARM <token>` | Arm motion for 60 s (the token is echoed from `INFO`, to prevent accidental arming) | `armed_until` |
| `MOTOR <1|2> STEP <±n> [rpm]` | Half-step moves, limited to ≤ 2048 steps per command. Refused if not armed. De-energises the coils at the end | `pos`, `dur_ms` |
| `MOTOR <1|2|ALL> RELEASE` / `MOTOR STOP` | Coils off; STOP aborts a move immediately (checked between steps) | |
| `WDT CFG A <ms>` / `WDT CFG B <ms>` | Set the rail on-time limits within hard caps. Defaults: RAIL A 2000 ms (hard cap 5000), RAIL B 5000 ms (hard cap 10000) | |
| `RESET` | Software reset (watchdog timer) | `# BOOT` follows |

Error codes are a small fixed enum (1 = unknown command, 2 = bad argument, 3 = refused/safety, 4 = I²C/ADC error, 5 = busy, 6 = overflow). Document them in `docs/PROTOCOL.md`.

### 4.3 Firmware safety requirements (must be met and tested)

1. **Power-up:** the first actions in `setup()` are CE1 = CE2 = LOW and mask = 0. The boot banner comes after.
2. **On-time watchdog:** any lit channel turns off automatically at its deadline, checked every loop iteration. Emit `# WDT ch=n off`.
3. **Comms-loss failsafe:** if no command arrives for 10 s while a channel is on or a motor is armed, turn everything off and disarm.
4. Never more than one channel and one CE high, enforced in the state machine.
5. Motors refuse to move unless armed. Moves are bounded, and the coils are released after each move.
6. Keep the switching order exactly: select, then CE on; CE off before changing selection.

### 4.4 Firmware structure

`software/firmware/lio_firmware/`:
- `lio_firmware.ino`: setup, loop, dispatch only
- `config.h`: pins, limits, version
- `protocol.h/.cpp`: line buffer, tokenizer, response helpers
- `optics.h/.cpp`: 595, CE, watchdog, MEAS/SWEEP
- `adc.h/.cpp`: ADS1115 via Adafruit_ADS1X15
- `motors.h/.cpp`: non-blocking half-step sequencer
- `safety.h/.cpp`

Must compile with `arduino-cli compile --fqbn arduino:avr:nano` and stay under 75% of SRAM. Document both bootloader variants (`cpu=atmega328` and `cpu=atmega328old`) for upload.

**Before changing the firmware,** read `software/control/lio_control.py`.
- If it drives the motors through some existing firmware or protocol, preserve compatibility or provide a documented migration. Ask the user before removing behaviour.
- The current `lio_firmware.ino` (TEST_MODE version) must be kept, as `software/firmware/legacy/lio_firmware_testmode/` or in git history with a tag.

## 5. Host software (Python)

### 5.1 Layout

```
software/host/
├── pyproject.toml          # package "lio", Python ≥3.10, deps: pyserial, pyyaml, numpy, matplotlib, jinja2; dev: pytest, pytest-timeout, ruff, mypy
├── src/lio/
│   ├── __init__.py
│   ├── transport.py        # SerialTransport (pyserial), SimTransport; open/close, DTR reset + banner wait, readline with timeout
│   ├── protocol.py         # encode commands, parse OK/ERR/# lines into typed objects; seq numbers; ProtocolError
│   ├── device.py           # LIODevice: ping(), info(), status(), adc_read(), ch_on(), off(), meas(), sweep(), motor_*(), loop_test(); context manager guarantees OFF on exit
│   ├── sim.py              # SimulatedLIO: full protocol + physics-lite model + fault injection
│   ├── config.py           # load/validate lio_hw.yaml (dataclasses), thresholds, channel map
│   ├── analysis.py         # stats, settling-time fit, CV, crosstalk, saturation, polarity
│   ├── results.py          # TestResult / RunRecord dataclasses; JSON writer
│   ├── report.py           # Markdown + HTML (jinja2) report with plots
│   └── cli.py              # `lio` command: ports, ping, info, ch, off, meas, sweep, motor, selftest, report
├── tests/
│   ├── conftest.py         # options: --lio-port, --lio-sim, --lio-fault, --interactive, --allow-motion, --lio-config, --results-dir
│   ├── unit/               # pure logic: protocol parser, analysis, config validation
│   └── system/             # test catalogue T01–T11 (§6); each works against sim or hardware
└── README.md
software/config/lio_hw.yaml # hardware facts + provisional thresholds (§5.4)
```

`software/logger/lio_logger.py`: rewrite it on top of `lio.device` (keep its CLI and CSV output compatible), or leave it and add a deprecation note pointing to `lio sweep --csv`.

### 5.2 Simulator requirements

- It implements every protocol command with realistic timing (ADC conversion time per rate setting; settle tail as a first-order response with τ about 0.2 ms optical and about 10 µs TIA, plus a configurable extra lag).
- **Model:**
  - per-channel emitter power from the config
  - detector responsivity curves (OPT101 silicon, InGaAs) giving counts
  - Gaussian noise and dark offset
  - saturation at the documented rails
  - ambient light term
- **Faults, injectable by name** (`--lio-fault reversed_ingaas,stuck_on:5`), each needing at least one test that detects it:
  - `no_adc`
  - `stuck_on:<n>`, `dead_channel:<n>`, `swapped:<a>,<b>`
  - `rail_a_dead`, `rail_b_dead`, `ce_inverted`
  - `reversed_ingaas`, `no_neg_rail`, `tia_saturated`, `opt101_no_feedback`
  - `noisy_adc`, `slow_settle`
  - `chain_break` (U2 receives nothing)
  - `motor_stall`, `comms_drop`

### 5.3 Results and reports

- Each run writes `test_results/<YYYYmmdd-HHMMSS>_<host|sim>/`:
  - `results.json`: a run record with:
    - environment: OS, Python, package version, git commit and dirty flag, firmware INFO, config hash, operator, notes
    - per-test results: id, name, module, status, measured values, criteria, duration, artefacts
  - `report.md` and `report.html`, with a summary table and a per-module section
  - `plots/`: per-channel net-signal bars for both detectors, noise histograms, settling curves, sweep overlays, cross-talk matrix
  - raw CSV of every MEAS/SWEEP
- Add `test_results/` to `.gitignore`.
- **Baseline mode:** `lio selftest --save-baseline` stores the measured per-channel values to `software/config/baseline_<date>.yaml`. Later runs compare against it and flag drift beyond tolerance as WARN or FAIL. This is how the provisional thresholds become real ones.

### 5.4 `lio_hw.yaml` (initial content)

Encode:
- the pin map, for documentation and for `INFO` cross-checking
- the channel map (hole → wavelength, rail, expected detector(s), `fitted: true/false`, `expect: signal | weak | none`)
- ADC gain and rate, settle time
- watchdog limits

The thresholds below are **provisional** and must be marked as such:

| Threshold | Provisional value | Notes |
|---|---|---|
| ADC dark noise σ (GAIN_ONE, 128 SPS) | ≤ 20 counts | per channel, n = 64 |
| OPT101 dark offset | 0 – 800 counts | ≈0–100 mV |
| TIA dark offset | −100 – 2000 counts | small positive expected; strongly negative → fault |
| Channel detected | net ≥ max(10 σ, 50 counts) on the expected detector | |
| Weak channel (hole 15) | net ≥ max(3 σ, 15 counts) → PASS, else WARN | |
| Expected-none (hole 16) | report net; never FAIL on absence | |
| Polarity (InGaAs on holes 8–14) | net < −5 σ → **FAIL "InGaAs reversed"** | |
| Saturation | lit ≥ 27,000 counts (TIA) / 29,000 (OPT101) → WARN, with advice (lower Rf / gain) | |
| Off-state return | after OFF + settle, reading within dark ± 5 σ | detects stuck-on |
| Address / isolation | each channel's detector-response pattern matches its expected detector(s); no two channels share a signature | see T05.3 |
| Repeatability | CV ≤ 2% (10 repeats) where net ≥ 1000 counts | |
| Settling | reaches 99% of the step within `settle_ms` (8 ms); else recommend a value | |
| Sweep | completes, 16 records, duration ≤ 2.5 s at defaults | |
| Watchdog | auto-off within limit + 50 ms | |

## 6. Test catalogue

**Types:**
- **A** = automatic (sim and hardware)
- **I** = interactive (asks the operator to observe or measure)
- **M** = motion (requires `--allow-motion`, operator present)

Every test ID maps to one pytest function. Sub-steps are recorded as sub-results (use `pytest-subtests` or a custom recorder).

### T01: Host environment and discovery (A)
- **T01.1** Python and dependency versions recorded.
- **T01.2** Serial port discovery (`lio ports`), selecting a port by VID/PID heuristics (CH340, FTDI, ATmega16U2) or `--lio-port`.
- **T01.3** Config file loads and validates; channel map is self-consistent (16 holes; rails match the A/B split; detectors match the coverage table).

### T02: Link and protocol (A)
- **T02.1** Open the port, then receive `# BOOT` within 3 s.
- **T02.2** `PING` round-trip latency over 100 pings: median and p99 recorded. PASS if all respond and p99 < 50 ms.
- **T02.3** `INFO` fields present; firmware and protocol versions are compatible with the host package; the safety limits match the config.
- **T02.4** Robustness:
  - unknown command → `ERR code=1`
  - bad arguments → `ERR code=2`
  - over-length line → `ERR code=6`
  - garbage bytes → no crash; `PING` still OK
- **T02.5** Sequence numbers are echoed correctly. Interleaved `#` events don't desynchronise the parser.
- **T02.6** `RESET`, then the banner reappears and `STATUS` shows the safe state.

### T03: I²C and ADC (A)
- **T03.1** `I2C SCAN` finds 0x48 (and only expected devices). A FAIL message points to the wiring of SDA A4, SCL A5, ADDR → GND and power.
- **T03.2** With everything off, read ADS A0–A3, n = 64 each. Record mean and σ. Pass if σ ≤ threshold on A0/A1. A2/A3 are floating: record only.
- **T03.3** Gain sweep (2/3 … 16) on dark channels: the reading scales consistently and no errors occur.
- **T03.4** Data-rate check: the measured conversion interval matches the configured rate within ±15%.
- **T03.5** Long-term dark stability: 60 s at 2 Hz. Drift slope and σ are recorded. WARN if drift exceeds 2% of full scale per minute.

### T04: Channel selection, the shift registers (A, optional I)
- **T04.1** `SR RAW` with walking-1 and walking-0 patterns and 0x0000/0xFFFF. `STATUS` echoes the mask. With CE held low, the detectors stay at dark (proves no light without CE).
- **T04.2** *Optional loopback (§6.3):* `LOOP TEST`, where 32 pseudo-random patterns must shift out of U2 Q7′ intact. This proves the clock, latch, data and chain wiring without optics.
- **T04.3** Optical address verification is covered by T05.3 (each hole lights only its own expected response).
- **T04.4 (I)** Walk test: the firmware lights holes 1 → 16 for 0.4 s each. The operator confirms the visible ones (1–7) in order and checks the IR ones with a phone camera (8–9). SWIR holes can't be seen and are marked n/a.

### T05: LED drivers, rails and channels (A)
- **T05.1** Rail gating: select hole 8 with CE1 low → dark; raise CE1 → light. Then try CE2 for hole 8 → refused by the firmware (safety), or dark in a FORCE debug build. Repeat for hole 12 on RAIL B. This detects `rail_*_dead` and `ce_inverted`.
- **T05.2** Per-channel MEAS for every hole with `fitted: true`, n = 4:
  - net on each detector
  - classified against the `expect` field and the thresholds
  - polarity check for the InGaAs
  - saturation check
- **T05.3** Address/isolation: a 16 × 2 response matrix. Each channel's response must match the expected detector pattern (for example hole 3 gives OPT101 ≫ InGaAs; hole 13 gives InGaAs ≫ OPT101). Two channels with near-identical signatures, which is impossible for distinct wavelengths, are flagged as `possible swap`. Detects `swapped`.
- **T05.4** Off-state return: after each MEAS, read again after OFF + settle. It must be within dark ± 5 σ. Detects `stuck_on` (stuck MOSFET or missing pull-down).
- **T05.5** Repeatability: 10 MEAS per channel (interleaved, to spread heating), with CV computed. Respect the RAIL A duty cycle: keep total on-time per channel per minute ≤ 1 s.
- **T05.6 (I, optional)** Driver current: TEST holds hole 8 on for 2 s, repeated up to 5 times while the operator reads the meter in series. The operator enters the mA value, which is recorded and compared to the 30 mA nominal (RAIL A). The same for hole 12 (RAIL B, ≈45 mA nominal).

### T06: Detectors (A)
- **T06.1** OPT101: dark offset within range; responds to holes 1–7; the 7-channel visible signature is monotonic-plausible (no zeros where light is expected); not saturated.
- **T06.2** InGaAs TIA:
  - dark offset within range
  - the polarity test on holes 8, 9 and 12–14 gives a clear **FAIL with instructions** if reversed
  - saturation check, with advice (Rf 1 MΩ → 100 kΩ)
  - an "erratic" check (σ during dark ≫ T03 noise, or a reading pinned at the negative rail) points to a **missing −5 V rail / bank B asleep**
- **T06.3** Cross-calibration: on holes 8 and 9, both detectors respond. Record the ratio InGaAs/OPT101 per hole into the baseline.
- **T06.4** Ambient sensitivity (I, optional): the operator opens the chamber or lid and the dark reading change is recorded. This quantifies light-tightness.

### T07: Timing and settling (A)
- **T07.1** Step response: `ADC STREAM` at 860 SPS around a CH ON / OFF, for holes 3, 8 and 13. Fit a time constant; report the time to 99%.
- **T07.2** Recommend `settle_ms` (max over channels × 1.5, rounded up). WARN if it exceeds the configured value.
- **T07.3** MEAS timing: the reported `t_on_ms` is consistent with settle + conversions, and within the watchdog limit.

### T08: Sweep and data path (A)
- **T08.1** `SWEEP` completes with 16 records within the time limit, and the schema is valid.
- **T08.2** 5 repeated sweeps: per-channel CV, and dark stability between sweeps.
- **T08.3** Results agree with T05.2 within tolerance.
- **T08.4** The logger and CLI CSV output is byte-compatible with the documented format.

### T09: Motors (M; operator present, `--allow-motion`)
- **T09.1** Arming: `MOTOR STEP` without ARM → refused. ARM with the wrong token → refused. ARM expires after 60 s.
- **T09.2** Each motor: the operator confirms the chamber is clear. +64 then −64 half-steps at low rpm; the operator confirms the movement direction. The coils release afterwards (`STATUS`).
- **T09.3** `MOTOR STOP` aborts a 2048-step move in under 50 ms.
- **T09.4** EMI check: run `ADC STREAM` on dark channels during a short move. Report σ during motion against at rest. WARN if more than 3× higher, which justifies "never sweep while moving".
- **T09.5** Integration with `lio_control.py`: only after the user approves the reconciliation (§4.4).

### T10: Safety behaviours (A)
- **T10.1** Power-up dark: after RESET or a port reopen, `STATUS` shows ch = 0, CE low, mask 0, and the detectors read dark.
- **T10.2** On-time watchdog: `CH 3 ON 60000` (asking for longer than allowed) is clamped to the RAIL A limit. Poll ADC A1 and confirm the light disappears within limit + 50 ms; `# WDT` is received.
- **T10.3** Comms-loss failsafe: light a channel, stop sending for 11 s, then reconnect without reset if possible (otherwise check via the event log). The channel must be off.
- **T10.4** Single-channel invariant: `SR RAW` with 2+ bits set, then `CE` → refused.
- **T10.5** Motion is disarmed after a comms loss.

### T11: System acceptance (A + optional I/M)
- Runs T01–T08 and T10, plus T09 if allowed. Produces the full report and an **overall verdict**:
  - **FUNCTIONAL:** no FAILs
  - **DEGRADED:** WARNs only, or FAILs confined to expected-limited channels (15, 16, reserved)
  - **NOT FUNCTIONAL:** any FAIL in T02, T03, T04 or T10, or more than 2 channel FAILs
- Saves a baseline if requested.

### 6.3 Optional hardware test aid (needs the user's approval)

One jumper from **U2 pin 9 (Q7′, currently unconnected) to Nano D11** turns the register chain into a loop that the firmware can read back. This is the only way to verify the shift registers without optics. It is non-invasive and reversible. Implement `LOOP TEST`, which reports `not_fitted` if the line never changes. Never assume the jumper is present.

## 7. Command-line interface

```bash
lio ports
lio --port /dev/tty.usbserial-XXXX info
lio ch 8 on --ms 1000 ; lio off
lio meas 8
lio sweep --csv out.csv --plot
lio motor arm ; lio motor 1 step 64
lio selftest [--sim] [--fault reversed_ingaas] [--interactive] [--allow-motion] [--modules t03,t05] [--save-baseline] [--report]
```

`lio selftest` wraps pytest with the right markers and options, then builds the report. Plain `pytest` must also work:

```bash
pytest -m "unit or sim" --lio-sim                       # no hardware
pytest -m "hw and not interactive and not motion" --lio-port /dev/tty.usbserial-XXXX
```

## 8. Continuous integration

`.github/workflows/ci.yml`, run on push and pull request:
1. Lint and type checks: `ruff`, `mypy` (strict on `src/lio`).
2. `pytest -m "unit or sim"`, including the fault-injection matrix: every fault in §5.2 must be detected by at least one test.
3. `arduino-cli compile --fqbn arduino:avr:nano software/firmware/lio_firmware`, with the Adafruit ADS1X15 library installed. Report flash and SRAM use, and fail if SRAM exceeds 75%.

No hardware tests run in CI.

## 9. Milestones and acceptance

Each milestone is merged through a pull request from a feature branch. Don't push straight to `main`.

| # | Milestone | Done when |
|---|---|---|
| M0 | **Reconnaissance** | Report on `lio_control.py`, the existing firmware, environment and port; deviations from this plan proposed; the user approves |
| M1 | **Protocol spec + firmware v2** | `docs/PROTOCOL.md` written; firmware implements §4 incl. safety; compiles in CI; legacy firmware preserved |
| M2 | **Host library + simulator** | transport, protocol, device, config, sim incl. all faults; unit tests ≥ 90% coverage on protocol and analysis |
| M3 | **Tests T01–T08, T10** | All pass against the healthy simulator; each injected fault is detected by the intended test; hw markers in place |
| M4 | **Motors + interactive** | T09 and the interactive steps implemented with clear operator prompts and abort paths |
| M5 | **Reports, CLI, baseline, CI, docs** | `lio selftest` produces the JSON + HTML report; baseline save/compare; CI green; `docs/TESTING.md` with how-to and the test catalogue; `software/README.md` updated; CHANGELOG entry |
| M6 | **First hardware run (with the user)** | Flash firmware v2 (user-approved); run the non-motion hardware suite; hand the report to the user; calibrate thresholds from real data into the YAML; open issues for every FAIL/WARN |

## 10. Engineering standards

- Python ≥ 3.10, type hints throughout, dataclasses for records, `ruff` formatting and lint, `mypy`.
- Pure logic (parsing, analysis, classification) is separated from I/O so it can be unit-tested.
- Every hardware interaction goes through `LIODevice`, whose context manager **always sends `OFF` and releases the motors on exit or exception** (including Ctrl-C).
- Timeouts everywhere: no infinite blocking reads.
- Logging via `logging`, with a `--verbose` option that also writes the raw serial transcript to the run folder.
- Firmware: no dynamic allocation, `F()` for literals, a non-blocking main loop (watchdog checks every iteration), and comments that cite the pin map.
- No secrets, no large binaries, no `test_results/` in git.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Nano SRAM exhaustion | key=value protocol, fixed buffers, `F()`; CI SRAM gate |
| Port open resets the board | transport waits for `# BOOT`; T02.1 |
| Can't read 595 outputs | optical isolation matrix (T05.3) plus the optional loopback (T04.2) |
| InGaAs still reversed on the bench | T06.2 detects it, with explicit rewiring instructions |
| Bank B auto-sleep (−5 V loss) | T06.2 erratic-signal heuristic + T03.5 long run; the report suggests the fix |
| RAIL A LEDs overdriven (30 mA) | firmware watchdog caps on-time; tests budget duty cycle |
| Unknown `lio_control.py` dependency | M0 recon, user approval before firmware replacement |
| Thresholds unknown before real data | provisional values flagged; M6 calibration + baseline |
| Motors with no limit switches | motion only armed and bounded, operator present, `--allow-motion` |

## 12. Deliverables checklist

- [ ] `docs/TEST_SUITE_PLAN.md` (this document)
- [ ] `docs/PROTOCOL.md`
- [ ] `docs/TESTING.md`
- [ ] Firmware v2 under `software/firmware/lio_firmware/`; legacy firmware preserved
- [ ] `software/host/` package with CLI, simulator, analysis and report
- [ ] `software/host/tests/` unit and system tests T01–T11
- [ ] `software/config/lio_hw.yaml` (+ baselines later)
- [ ] `.github/workflows/ci.yml`
- [ ] `.gitignore` updated (`test_results/`, `__pycache__/`, `.venv/`, `*.egg-info/`)
- [ ] `software/README.md` + `CHANGELOG.md` updated
- [ ] First hardware report (M6) attached to the PR or saved under `docs/test_reports/` (summary only, no raw data)
