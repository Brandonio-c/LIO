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
.venv/bin/pytest -m unit                 # pure logic + simulator behaviour, no hardware
```

The system test catalogue (T01–T11) and the `lio` command line arrive in later milestones.
