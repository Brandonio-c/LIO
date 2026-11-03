# LIO software

| Folder | Contents |
|---|---|
| `control/` | `lio_control.py`: existing chamber control (unchanged by the electronics update) |
| `firmware/lio_firmware/` | `lio_firmware.ino`: Arduino Nano firmware for the optical head |
| `logger/` | `lio_logger.py`: Python serial logger and plotter, plus `requirements.txt` |

## Firmware: `firmware/lio_firmware/lio_firmware.ino`

You need the Arduino IDE (board: Arduino Nano) and the library **Adafruit ADS1X15**, from the Library Manager.

Set `#define TEST_MODE` before uploading. The Serial Monitor runs at 115200 baud.

| Mode | What it does | Expect |
|---|---|---|
| 1 | I²C scan | `found 0x48` |
| 2 | Live detector readings every 300 ms | Both numbers move with light |
| 3 | Lights holes 1 → 16 for 0.4 s each | Visible LEDs light in order; check IR ones with a phone camera |
| 4 | Hole 8 on 2 s / off 3 s | Use it to set driver current with a meter in series |
| 5 | Sweep: dark reading + lit reading per hole, CSV output | `hole,dark_ingaas,dark_opt101,ingaas,opt101` … `END` |

**Pins:**
- A0 DATA, A1 CLOCK, A2 LATCH (74HC595 chain)
- A3 CE1 (DRV1, RAIL A), D10 CE2 (DRV2, RAIL B)
- A4/A5 I²C to the ADS1115 (A0 = InGaAs, A1 = OPT101)
- D2–D9 are left for the motors

**Switching order:** `lightHole()` turns both drivers off, selects the MOSFET, and only then raises that rail's CE. Keep this order if you modify the code.

**Settings to tune:**
- `SETTLE_MS` (default 8 ms)
- the ADS gain (`GAIN_ONE` = ±4.096 V)
- `isRailB()`: change it to `h >= 11` if white or pink LEDs on RAIL A are fitted in holes 10–11

## Logger: `logger/lio_logger.py`

```bash
pip install -r software/logger/requirements.txt
python software/logger/lio_logger.py /dev/tty.usbserial-XXXX   # macOS
python software/logger/lio_logger.py COM3                        # Windows
```

Close the Arduino Serial Monitor first. The logger captures one sweep and writes:
- `lio_sweep.csv`: raw counts plus dark-subtracted volts
- `lio_sweep.png`: OPT101 and InGaAs response against hole

## To do

The motor control in `control/lio_control.py` hasn't been reviewed against the new pin map. See `docs/OPEN_ITEMS_AND_NEXT_STEPS.md`, section D.
