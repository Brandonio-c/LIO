# LIO software

| Folder | Contents |
|---|---|
| `firmware/lio_firmware/` | **Firmware v2** for the Arduino Nano: command protocol, safety rules in firmware ([docs/PROTOCOL.md](../docs/PROTOCOL.md)) |
| `host/` | The `lio` Python package and command: device API, simulator, test suite, reports ([host/README.md](host/README.md)) |
| `config/lio_hw.yaml` | Hardware description and every test threshold (provisional until calibrated); saved baselines go here too |
| `logger/lio_logger.py` | Sweep logger: same command line and CSV/PNG as before, now on firmware v2 |
| `control/lio_motor_control.py` | The Tkinter Z-axis jog window (formerly `lio_control.py`, contents unchanged); works on firmware v2 through the bounded legacy jog commands. Close it before running `lio`: only one program can hold the port |

Older code is no longer in the tree but stays in git: the TEST_MODE firmware and the original logger at tag `fw-testmode-v1`, and the old AccelStepper motor sketch (**do not flash** on the current wiring) at tag `software-legacy-v1`.

## Quick start

```bash
cd software/host && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/lio --sim selftest            # try everything against the simulator
.venv/bin/lio ports                     # find the Nano
.venv/bin/lio info                      # talk to it (firmware v2 must be flashed)
.venv/bin/lio selftest                  # automatic hardware tests and a report
```

How to test, the full catalogue and the first-hardware-session checklist: [docs/TESTING.md](../docs/TESTING.md).

## Firmware

Build and flash with `arduino-cli`. The board has the new (Optiboot) bootloader; use `cpu=atmega328old` for an old one.

```bash
arduino-cli lib install "Adafruit ADS1X15" "Adafruit BusIO"
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328 software/firmware/lio_firmware
arduino-cli upload  --fqbn arduino:avr:nano:cpu=atmega328 -p /dev/cu.usbserial-XXXX software/firmware/lio_firmware
```

The Arduino IDE works too: board Arduino Nano, processor ATmega328P, and the same two libraries.

**Pins (unchanged):**
- A0 DATA, A1 CLOCK, A2 LATCH (74HC595 chain)
- A3 CE1 (DRV1, RAIL A), D10 CE2 (DRV2, RAIL B)
- A4/A5 I²C to the ADS1115 (A0 = InGaAs, A1 = OPT101)
- D2–D5 motor 1 (left), D6–D9 motor 2 (right)
- D11 the optional loop-back input

**Switching order:** both drivers off, select the MOSFET, then raise that rail's CE. The firmware enforces this, along with one channel at a time and a per-rail on-time watchdog.

## Motor control

```bash
pip install pyserial
python software/control/lio_motor_control.py
```

## Logger

```bash
pip install -e software/host
python software/logger/lio_logger.py /dev/cu.usbserial-XXXX   # macOS
python software/logger/lio_logger.py COM3                       # Windows
```

It writes `lio_sweep.csv` (raw counts plus dark-subtracted volts, the same columns as before) and `lio_sweep.png`. `lio sweep --csv … --plot …` does the same.
