# `lio` — host library, simulator and test suite

Python package for the LIO V3 controller running firmware v2 (`docs/PROTOCOL.md`). Plan: `docs/TEST_SUITE_PLAN.md`.

| Module | What it does |
|---|---|
| `lio.protocol` | Encodes commands and parses `OK` / `ERR` / `#` lines (pure functions) |
| `lio.transport` | `SerialTransport` (pyserial; opening resets the Nano) and `SimTransport` (virtual clock); port discovery by USB VID/PID |
| `lio.device` | `LIODevice`: typed API (`meas`, `sweep`, `adc_read`, `motor_step`, …). Used as a context manager it always sends `OFF` and `MOTOR STOP` on exit. Includes the LED duty-budget tracker |
| `lio.config` | Loads and validates `software/config/lio_hw.yaml`, the only place hardware constants and thresholds live |
| `lio.sim` | `SimulatedLIO`: the firmware protocol plus a simple optical model and injectable faults |
| `lio.analysis` | Statistics, detection levels, settling fits, signature comparison (pure functions) |
| `lio.results` | `TestResult` / `RunRecord` dataclasses, the T11 verdict, `results.json` |
| `lio.suite` | The test catalogue T01–T11 (`lio.suite.checks`), its shared context and runner. Usable from pytest or `lio selftest` |
| `lio.operator` | The person at the bench: `ConsoleOperator` (prompts; `a` aborts) and `SimOperator` (answers from the simulator's truth) |
| `lio.report`, `lio.csvout`, `lio.baseline` | HTML/Markdown reports with plots; logger-format CSV; saved baselines and T11.1 drift |
| `lio.cli` | The `lio` command (`lio --help`) |
| `lio.simserve` | The simulator on a pseudo-terminal, in real time (`lio sim-serve`): exercises the real serial path |
| `lio.dashboard` | `lio dashboard`: a local web page (standard-library HTTP server) that runs the catalogue, shows a digital twin of the instrument coloured by result, and the overall verdict. `twin.py` maps results to parts, `session.py` owns the device and the run thread, `server.py` the HTTP side, `static/index.html` the page |

## Setup

```bash
cd software/host
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Use

```python
from lio.config import load_config
from lio.device import LIODevice
from lio.sim import Faults, SimulatedLIO
from lio.transport import SerialTransport, SimTransport

cfg = load_config()
transport = SimTransport(SimulatedLIO(cfg, Faults.parse("reversed_ingaas")))
# or: transport = SerialTransport("/dev/cu.usbserial-1120")
with LIODevice(transport, cfg) as dev:
    m = dev.meas(13, n=4)
    print(m.net("ingaas"))  # strongly negative: the photodiode is "reversed"
```

Simulator faults: `no_adc`, `stuck_on:<n>`, `dead_channel:<n>`, `swapped:<a>,<b>`, `rail_a_dead`, `rail_b_dead`, `ce_inverted`, `reversed_ingaas`, `no_neg_rail`, `tia_saturated`, `opt101_no_feedback`, `noisy_adc`, `slow_settle`, `chain_break`, `motor_stall`, `comms_drop`.

## Tests

```bash
.venv/bin/pytest -m unit                                   # pure logic + simulator behaviour
.venv/bin/pytest -m "unit or sim" --lio-sim                # + catalogue T01-T10 and fault matrix
.venv/bin/pytest -m sim --lio-sim --lio-fault stuck_on:5   # catalogue against a faulty simulator
```

Hardware (only with the operator's approval; opening the port resets the Nano; T10.3 and T10.5 *arm* motion for 11 s but never send a motor command):

```bash
.venv/bin/pytest -m "hw and not interactive and not motion" --lio-port /dev/cu.usbserial-1120 \
    --lio-sample-id none-empty-chamber --lio-operator <name>
```

Each run writes `test_results/<YYYYmmdd-HHMMSS>_<sim|host>/results.json` at the repository root, or to `--results-dir=PATH` (use the `=` form: pytest otherwise mistakes an existing directory for a test path). FAIL and ERROR fail the pytest test, WARN passes with a warning, and SKIP skips with the reason.

How the catalogue works:

- Each entry is a function in `lio.suite.checks` registered under its plan ID. `tests/system/test_t*.py` maps each ID to one pytest function.
- Shared measurements (dark statistics, the 16-channel matrix, the polarity gate) are taken once per run, on first use, so any test also runs on its own.
- After every test the runner restores the safe state: LEDs off, motors stopped, default gain, rate and watchdogs.
- A detector that is unusable (erratic or pinned output, or a reversed InGaAs on the hole-8 polarity gate) is reported once in T06. Later judgments on it are skipped instead of cascading into misleading failures.
- `tests/system/test_fault_matrix.py` injects every simulator fault, requires its intended test to detect it, and runs the same check on a healthy simulator as a control.

The `lio` command does the same without pytest (`lio selftest`, `lio --sim selftest`); see [docs/TESTING.md](../../docs/TESTING.md) for the catalogue, the report and the hardware checklist.
