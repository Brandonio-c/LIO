# LIO firmware v2 — serial command protocol (protocol 1)

Firmware: `software/firmware/lio_firmware/` (version 2.0.0). Spec: `docs/TEST_SUITE_PLAN.md` §4. The previous TEST_MODE firmware is in `software/firmware/legacy/lio_firmware_testmode/` and under the git tag `fw-testmode-v1`.

## 1. Link

- USB serial, 115200 baud, 8N1.
- **Opening the port resets the Nano** (DTR). Wait for the boot banner (≈2 s) before sending anything.
- Boot banner, always the first non-empty line after a reset:

  ```text
  # BOOT name=lio fw=2.0.0 proto=1 build=2026-11-03 adc_ok=1 hw_wdt=0
  ```

## 2. Framing

- ASCII, one command per line, terminated by `\n`. `\r` is ignored. Empty lines are ignored.
- Command words and arguments are case-insensitive (the firmware upper-cases the line).
- At most **64 characters** per line, excluding `\n`. Longer lines are discarded whole and answered with `ERR ? code=6 msg=line too long`.
- Tokens are separated by spaces or tabs; at most 10 tokens.
- **Optional sequence number:** a line that starts with `@<n> ` gets a response that starts with `@<n> `. Events never carry one.

```text
@17 PING
@17 OK PING uptime_ms=5321
```

## 3. Responses and events

Every command gets **exactly one** final response line:

```text
[@n ]OK <WORD> key=value key=value ...
[@n ]ERR <WORD> code=<int> msg=<text>
```

- `<WORD>` is the first token of the command, upper-cased (`OK ADC ...`, `OK CH ...`, `OK U ...`).
- Values never contain spaces. In `ERR` lines `msg=` is always last and runs to the end of the line, so it may contain spaces.
- Hex values are written `0x` + upper-case digits (`mask=0x0080`, `arm_token=0x3F1C`).
- A few responses end with a bare flag word after the key=value pairs (`# WDT ch=3 on_ms=2000 off`). Parsers should ignore tokens without `=`.

Lines starting with `#` are **events**. They may appear at any time, including between the lines of a streaming command and before its final `OK`. The host must tolerate them everywhere.

| Event | When |
|---|---|
| `# BOOT name=lio fw= proto= build= adc_ok= hw_wdt=` | After power-up, port open, or `RESET` |
| `# S i= t_us= raw=` | One per sample of `ADC STREAM` |
| `# M ch= dark0= dark1= lit0= lit1= t_on_ms=` | One per hole of `SWEEP` |
| `# WDT ch= on_ms= off` | A lit channel reached its rail's watchdog limit and was turned off |
| `# OFF ch= on_ms= off` | A `CH n ON <ms>` timer (shorter than the watchdog) expired normally |
| `# MOTOR m= steps= pos= done` | A move finished; its coils are released |
| `# FAILSAFE reason=comms idle_ms=` | Comms-loss failsafe fired (§6) |

## 4. Error codes

| Code | Meaning | Typical cause |
|---:|---|---|
| 1 | Unknown command | Typo, garbage bytes |
| 2 | Bad argument | Missing or out-of-range argument |
| 3 | Refused (safety) | Not armed, wrong token, LED on during a motor command, CE without exactly one selected hole on that rail, on-time beyond the watchdog |
| 4 | I²C / ADC error | ADS1115 absent, NACK, or I²C timeout |
| 5 | Busy | A motor is moving (LED and measurement commands are refused) |
| 6 | Overflow | Line longer than 64 characters |

## 5. Commands

Channels are holes 1–16. RAIL A = holes 1–9 (DRV1, CE1 = A3 (A4 in firmware 2.2.2 only). Firmware 2.3.0 also runs on the Nano R4: it has no DTR reset, so it re-applies the dark state and prints `# BOOT` when the host opens the port, and RESET does the same without dropping USB); RAIL B = holes 10–16 (DRV2, CE2 = D10). ADC channel 0 = InGaAs TIA, 1 = OPT101, 2–3 unconnected.

### Identity and state

| Command | Response fields |
|---|---|
| `PING` | `uptime_ms` |
| `INFO` | `fw proto build adc_addr adc_ok gain rate settle_ms wdt_a_ms wdt_b_ms wdt_a_cap_ms wdt_b_cap_ms comms_ms arm_ms step_max jog_max jog_v_max jog_acc_max wake_ms_max motion_armed arm_token hw_wdt` (`wake_ms_max` since the POWER WAKE build) |
| `STATUS` | `ch` (lit hole, 0 = none) `ce1 ce2 mask motor1 motor2` (`idle`/`run`) `pos1 pos2 armed armed_ms va vs acc faults wdt_trips failsafe_trips` |
| `RESET` | `OK RESET`, then the device restarts and prints `# BOOT` |

`faults` is a sticky bit mask, cleared only by a reset: `0x01` ADS1115 missing at boot (the firmware keeps looking for it: `adc_ok` in `INFO` and every ADC command probe again until it answers, so a power bank that wakes after the Nano boots is picked up without a reset), `0x02` I²C error seen, `0x04` an LED watchdog fired, `0x08` the comms failsafe fired.

`RESET` turns everything off and jumps to address 0, which re-runs the C runtime and `setup()`. It does not use the hardware watchdog, because the old Nano bootloader loops forever after a watchdog reset.

### ADC

| Command | Effect | Response fields |
|---|---|---|
| `I2C SCAN` | Probe addresses 1–126 | `n addrs` (`addrs=0x48` or `addrs=none`) |
| `I2C DIAG` | Line-level checks of SDA/SCL, then re-attach the ADC (fw ≥ 2.1.0; software bus from 2.2.0) | `sda scl sda_pu scl_pu bridge ack_slow ack_fast slow_hz fast_hz hz present` |
| `ADC READ <0-3> [n]` | Single-ended read; mean of `n` (1–256) | `ch raw mv n` and, if `n > 1`, `mean std` |
| `ADC CFG GAIN <2/3\|1\|2\|4\|8\|16>` | Set the PGA | `gain lsb_mv` |
| `ADC CFG RATE <8\|16\|32\|64\|128\|250\|475\|860>` | Set the data rate | `rate` |
| `ADC STREAM <ch> <n> <interval_ms> [hole on_idx off_idx]` | `n` (1–2000) samples, one `# S` line each, at `interval_ms` (0 = as fast as possible) | `ch n dur_ms` |

**I²C bus (firmware ≥ 2.2.0).** The ADS1115 is driven over a software I²C bus on **D11 (SDA) and D12 (SCL)**, about 170 kHz. It moved off the hardware pins (A4/A5) while a wiring fault was being diagnosed. The lines are open-drain (driven low or released, never driven high) and need 4.7 kΩ pull-ups to +5 V. Firmware 2.0–2.1 used the hardware bus on A4/A5.

**I2C DIAG.** The firmware checks each line, only ever driving it low:
- `sda`/`scl`: the line idles high with the Nano's internal pull-up on. 0 means it is held low (a short to GND, an unpowered chip clamping it, or the wrong pin).
- `sda_pu`/`scl_pu`: the line rises after being pulled low with the internal pull-up off. That needs an external pull-up to a powered VDD. 0 means the module has no pull-ups, or bank A is off.
- `bridge`: pulling one line low also pulls the other low. SDA and SCL are joined.
- `ack_slow`/`ack_fast`: the result for 0x48 at `slow_hz` and `fast_hz`: 0 ack, 2 no answer, 4 bus error, 5 timeout. On the software bus (2.2.0) there is one speed, so both pairs are equal. On the hardware bus (2.1.0) they were 100 kHz and 400 kHz.
- `hz`/`present`: the clock in use, and whether the ADC answers after the checks.

T03.1 runs it every time and reports the result as `T03.1/bus`.

Defaults after boot: gain `1` (±4.096 V, 0.125 mV/count), 128 SPS (≈7.8 ms per conversion).

**STREAM timing.** A stream of up to 48 samples (`STREAM_BUF_N`) is captured into RAM at the full ADC rate and printed when the capture ends, so `t_us` reflects the true conversion interval even at 860 SPS. Longer streams print each sample as it is taken. Each `# S` line takes about 3 ms at 115200 baud, so above about 250 SPS a long stream is limited by the serial line, not by the ADC. While waiting for room in the transmit buffer the firmware keeps servicing the motors and watchdogs.

`raw` is the rounded mean in counts. `mv = mean × lsb`. Single-ended readings can be slightly negative (an input below GND); that is how a reversed InGaAs photodiode shows up.

**STREAM LED schedule (addition to plan §4.2, for T07.1).** With the three optional arguments, the firmware lights `hole` from sample `on_idx` up to, but not including, sample `off_idx`, and turns it off at the end in any case. This is needed because a stream is a blocking command: the host can't send `CH ON` in the middle of one. The schedule is refused (`code=3`) if the LED would be on longer than its rail's watchdog, and with `code=5` while a motor moves. Without the schedule, `ADC STREAM` is allowed while a motor moves (T09.4).

### Channel selection and LEDs

| Command | Effect | Response fields |
|---|---|---|
| `SR RAW <hex16>` | Drives CE1 and CE2 low, then shifts and latches any 16-bit mask. CE stays low | `mask` |
| `CE <1\|2> <0\|1>` | Drives one enable. Raising it requires exactly one selected hole, on that rail; the rail's watchdog starts | `rail on` (+ `until_ms` when on) |
| `CH <1-16> ON [ms]` | Safe sequence: both CE off → select the hole → raise its rail's CE. Auto-off after `ms`, or after the rail's watchdog limit if that is smaller or `ms` is omitted | `ch rail until_ms clamped` |
| `OFF` | Both CE low, then mask = 0 | — |
| `MEAS <1-16> [settle_ms] [n]` | Atomic: off → wait `settle_ms` → read A0 and A1 (mean of `n`) as dark → `CH` on → wait `settle_ms` → read lit → off | `ch dark0 dark1 lit0 lit1 t_on_ms settle_ms n` |
| `SWEEP [settle_ms] [n]` | `MEAS` for holes 1–16, one `# M` line each | `n settle_ms samples dur_ms` |
| `LOOP TEST` | Optional shift-register loopback (§5.1) | `fitted pass bits_ok bits_bad` (+ `status=not_fitted`) |
| `WDT CFG A\|B <ms>` | Set a rail's on-time limit, 50 ms up to the hard cap | `rail ms cap_ms` |

Defaults: `settle_ms` = 8 (0–500), `n` = 1 (1–64). In `MEAS`, `dark0`/`lit0` are ADS A0 (InGaAs) and `dark1`/`lit1` are ADS A1 (OPT101). `t_on_ms` is the time from CE high to CE low: about `settle_ms + 2 × n × conversion time`. `MEAS` and `SWEEP` refuse (`code=3`) any combination whose estimated on-time exceeds the rail's watchdog.

The bit mapping follows LIO-ELEC-001 §5.2: bit (n − 1) selects hole n, the U2 byte (holes 9–16) is shifted first, and each byte goes MSB first.

#### 5.1 LOOP TEST

**Not available from firmware 2.2.0:** D11 now carries I²C SDA, so `LOOP TEST` answers `fitted=0 pass=0 bits_ok=0 bits_bad=0 status=not_fitted` without touching any pin, and the jumper must not be fitted. On earlier builds: this needs the optional jumper from U2 pin 9 (Q7′) to Nano D11 (plan §6.3), which is **not assumed**. The firmware drives both CE low and latches mask 0. It then shifts 32 patterns (0x0000, 0xFFFF, 0xAAAA, 0x5555 and 28 pseudo-random) into the chain **without latching**, so the LEDs never change, and reads each one back bit by bit from D11. D11 has its pull-up enabled, so without the jumper it never reads low, and the result is `fitted=0 pass=0 status=not_fitted`.

### Motors

Motor 1 = left (D2–D5), motor 2 = right (D6–D9), 28BYJ-48 through ULN2003. **+steps = up**: the coil order IN1 → IN1+IN2 → IN2 → … → IN4+IN1, which is the direction the legacy AccelStepper sketch used for `U`. This is still to be confirmed by watching it during T09.2.

| Command | Effect | Response fields |
|---|---|---|
| `MOTOR ARM <token>` | Arm motion for 60 s. `<token>` is `arm_token` from `INFO` (hex), so motion can't be armed by accident | `armed_ms` |
| `MOTOR <1\|2> STEP <±n> [rpm]` | Half-step move, \|n\| ≤ 2048, `rpm` 1–15 (default 5). Needs arming; refused while an LED is on or that motor is moving. Returns at once; `# MOTOR … done` follows | `m steps rpm` |
| `MOTOR <1\|2\|ALL> RELEASE` | Stop and de-energise | — |
| `MOTOR STOP` | Stop both immediately and release the coils | `pos1 pos2` |

Moves use a trapezoidal profile with an acceleration of 250 half-steps/s². The coils are released at the end of every move. An arm that expires during a move does not stop it; the move is bounded anyway.

### Power bank A: `POWER WAKE [ms]`

Power bank A alone supplies the +5 V bus (ADS1115, LEDs, shift registers, motor boards), and a USB power bank switches itself off when the load is small. `POWER WAKE` holds both motors' coils at their current phase for `ms` (default 1000, 1–3000), drawing about 0.5 A from that bus, then releases them: `OK POWER wake_ms=<ms>`. **No step is issued, so nothing moves, and no arming is needed.** It is refused while an LED is on (`code=3`) or a motor is moving (`code=5`). The host sends it when the port opens, before each test and before manual measurements, at most once per `power.interval_s` (`lio_hw.yaml`). Bank B (−5 V, the TL072 only) draws nothing the Nano controls and cannot be woken this way.

## 6. Firmware safety rules

1. **Power-up dark state.** The first statements in `setup()` drive CE1 and CE2 low, make them outputs, and latch mask 0. The banner comes after.
2. **One channel.** At most one bit is selected while a CE is high, and only the CE of that hole's rail can be high. `SR RAW` forces both CE low.
3. **Switching order.** Select the MOSFET, then raise CE. Drop CE before any change of selection.
4. **On-time watchdog.** It is checked on every loop iteration and inside every wait. RAIL A: default 2000 ms, hard cap 5000 ms (its LEDs are driven at 30 mA, above their 20 mA rating). RAIL B: default 5000 ms, cap 10000 ms. When it fires, the channel turns off and `# WDT` is emitted.
5. **Comms-loss failsafe.** If no byte arrives for 10 s while an LED is on, a motor is moving, or motion is armed, everything turns off, the coils are released, motion is disarmed and `# FAILSAFE` is emitted. Any received byte resets the timer. A host that holds a session open while idle and armed should expect to be disarmed.
6. **Motion and light are mutually exclusive.** `CH`, `CE … 1`, `MEAS`, `SWEEP` and a `STREAM` with an LED schedule are refused with `code=5` while a motor moves. Motor commands and jogs are refused with `code=3` while an LED is on.
7. **Bounded motion.** No limit switches exist, so every move is bounded (≤ 2048 half-steps per command), never homes automatically, and always ends with the coils released.

## 7. Legacy jog commands (reviewed exception to the arming rule)

`software/control/lio_motor_control.py` (formerly `lio_control.py`; contents unchanged) sends these commands and never arms. They are accepted **without** `MOTOR ARM`, as an exception approved in the M0 review, because each one is bounded:

| Command | Effect |
|---|---|
| `U` / `D` | Both motors up / down at the synchronized speed `VS` |
| `LU` `LD` `RU` `RD` | One motor at the alignment speed `VA` |
| `S` | Stop both immediately and release the coils |
| `VA<n>` `VS<n>` | Speed in half-steps/s, **clamped** to 50–1000 (`clamped=1` if it was outside). Applied to a running jog of the matching kind |
| `ACC<n>` | Acceleration in half-steps/s², clamped to 25–1000 |
| `POSL0` `POSR0` | Zero a motor's position counter |
| `?` | Lists the legacy commands |

Each jog ends at **whichever comes first**: `S`, **2048 half-steps** (`jog_max`), or the comms-loss failsafe (§6.5). A new jog command replaces the current move of the motors it names, and starts a new 2048-step bound. From firmware 2.2.1, a jog repeated for a motor that is **already jogging in the same direction** renews its bound to 2048 half-steps from that point **without restarting the speed ramp**, so a re-sent or held jog runs smoothly (the dashboard's Run buttons rely on this). A different direction, or a motor that is not jogging, starts a new move with the usual ramp. Jogs are refused while an LED is on; LED and measurement commands are refused while a jog runs.

This bound also fixes `lio_motor_control.py`'s runaway: if its window loses focus while a key is held, the key-release `S` never arrives, but the jog still stops at the bound.

Differences from the legacy AccelStepper sketch (removed from the tree; kept at git tag `software-legacy-v1`):
- Replies are `OK`/`ERR` lines; `lio_motor_control.py` ignores replies.
- `S` stops at once instead of decelerating.
- The coils are released after every move.
- The legacy speed limits (VA 50–1500, VS 100–3000, ACC 25–3000) are clamped to 1000.

Defaults: VA 200, VS 500, ACC 250, as before.

The limits are compile-time constants in `config.h`. They are mirrored in `software/config/lio_hw.yaml` and cross-checked against `INFO` by test T02.3.

## 8. Timing (defaults: 128 SPS, settle 8 ms, n = 1)

| Operation | Approximate time |
|---|---|
| One ADC conversion | 7.8 ms + I²C overhead (≈1 ms on the software bus) |
| `MEAS` | ≈ 8 + 2 × 8 (dark) + 8 + 2 × 8 (lit) ≈ 50 ms; LED on ≈ 25 ms |
| `SWEEP` | ≈ 16 × 50 ms ≈ 0.8 s |
| `ADC STREAM` at 860 SPS | ≈ 1.4 ms per sample |

## 9. Building and flashing

```bash
# New (Optiboot) bootloader, 115200 baud upload:
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328 software/firmware/lio_firmware
arduino-cli upload  --fqbn arduino:avr:nano:cpu=atmega328 -p /dev/cu.usbserial-XXXX software/firmware/lio_firmware
# Old bootloader, 57600 baud upload:
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328old software/firmware/lio_firmware
arduino-cli upload  --fqbn arduino:avr:nano:cpu=atmega328old -p /dev/cu.usbserial-XXXX software/firmware/lio_firmware
```

The optional hardware watchdog (2 s, reset in every service call) is for the **new bootloader only**:

```bash
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328 \
  --build-property "compiler.cpp.extra_flags=-DLIO_HW_WDT=1" software/firmware/lio_firmware
```

`INFO hw_wdt=1` confirms which build is running.

## 10. Example session

```text
# BOOT name=lio fw=2.0.0 proto=1 build=2026-11-03 adc_ok=1 hw_wdt=0
> I2C SCAN
OK I2C n=1 addrs=0x48
> ADC READ 1 16
OK ADC ch=1 raw=212 mv=26.500 n=16 mean=211.94 std=3.12
> MEAS 8
OK MEAS ch=8 dark0=41 dark1=209 lit0=5120 lit1=9874 t_on_ms=24 settle_ms=8 n=1
> CH 3 ON 60000
OK CH ch=3 rail=A until_ms=2000 clamped=1
# WDT ch=3 on_ms=2000 off
> CE 2 1
ERR CE code=3 msg=needs exactly one selected hole on this rail
> MOTOR 1 STEP 64
ERR MOTOR code=3 msg=not armed
```

(Values are illustrative.)
