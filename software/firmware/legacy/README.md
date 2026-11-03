# Legacy firmware

Kept for reference and rollback. Firmware v2 (`../lio_firmware/`) replaces both.

| Folder | What it is | Flash it? |
|---|---|---|
| `lio_firmware_testmode/` | The LIO-ELEC-001 Rev A test firmware (`#define TEST_MODE 1–5`), as described in §13 and Appendix A of the electronics document. Also tagged `fw-testmode-v1` in git. | Yes, if you need the original bring-up modes. Its `setup()` forces CE1/CE2 low and clears the 595s first. |
| `lio_motor_control/` | The original AccelStepper Z-axis sketch that `software/control/lio_control.py` talks to. | **No.** See the header in the file: on the current wiring it pulls CE2 (D10) up, never clears the 595s, and its jogs are unbounded. |

Compile either with, for example:

```bash
arduino-cli compile --fqbn arduino:avr:nano software/firmware/legacy/lio_firmware_testmode
```
