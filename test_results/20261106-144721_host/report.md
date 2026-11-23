# LIO test report: 20261106-144721_host

**Verdict: NOT FUNCTIONAL**: failure in a critical module: T03.1

- Target: `/dev/cu.usbserial-1120`
- Started 2026-11-06T14:47:21-05:00, finished 2026-11-06T14:47:39-05:00
- Sample: `none-empty-chamber`, operator: unknown, notes: full automated run after charging both power banks
- Firmware 2.2.0 (proto 1, build 2026-11-04)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 39be560ac85d (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git 943774d465
- Counts: PASS 12, FAIL 1, SKIP 25
- LED duty budget: 0.0 s of cool-down waits, 0 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T01.1 | Python and dependency versions | ✓ PASS |  |
| T01.2 | Serial port discovery | ✓ PASS |  |
| T01.3 | Configuration loads and is self-consistent | ✓ PASS |  |
| T02.1 | Port open and boot banner | ✓ PASS |  |
| T02.2 | PING round-trip latency | ✓ PASS |  |
| T02.3 | INFO fields, versions and safety limits | ✓ PASS |  |
| T02.4 | Robustness to bad input | ✓ PASS |  |
| T02.5 | Sequence numbers and interleaved events | - SKIP | the ADS1115 is not responding (see T03.1) |
| T02.6 | RESET restores the boot state | ✓ PASS |  |
| T03.1 | I2C scan finds the ADS1115 | ✕ FAIL |  |
| T03.2 | Dark ADC noise, all inputs | - SKIP | the ADS1115 is not responding (see T03.1) |
| T03.3 | Gain sweep on dark inputs | - SKIP | the ADS1115 is not responding (see T03.1) |
| T03.4 | ADC data rate | - SKIP | the ADS1115 is not responding (see T03.1) |
| T03.5 | Long-term dark stability | - SKIP | the ADS1115 is not responding (see T03.1) |
| T04.1 | Shift-register patterns with CE low | - SKIP | the ADS1115 is not responding (see T03.1) |
| T04.2 | Shift-register loopback (optional jumper) | - SKIP | loopback jumper not fitted (this build has no loop-back input (pins.LOOP), plan §6.3); the shift registers are verified optically by T05.3 |
| T04.3 | Optical address verification | - SKIP | covered by T05.3 (each hole must light only its own expected response) |
| T05.1 | Rail gating by CE1 / CE2 | - SKIP | the ADS1115 is not responding (see T03.1) |
| T05.2 | Per-channel response | - SKIP | the ADS1115 is not responding (see T03.1) |
| T05.3 | Channel address and isolation | - SKIP | the ADS1115 is not responding (see T03.1) |
| T05.4 | Off-state return after each MEAS | - SKIP | the ADS1115 is not responding (see T03.1) |
| T05.5 | Repeatability (interleaved MEAS) | - SKIP | the ADS1115 is not responding (see T03.1) |
| T06.1 | OPT101 | - SKIP | the ADS1115 is not responding (see T03.1) |
| T06.2 | InGaAs TIA | - SKIP | the ADS1115 is not responding (see T03.1) |
| T06.3 | Cross-calibration on the shared holes | - SKIP | the ADS1115 is not responding (see T03.1) |
| T07.1 | Step response and settling time | - SKIP | the ADS1115 is not responding (see T03.1) |
| T07.2 | Recommended settle time | - SKIP | the ADS1115 is not responding (see T03.1) |
| T07.3 | MEAS timing | - SKIP | the ADS1115 is not responding (see T03.1) |
| T08.1 | SWEEP completes with a valid schema | - SKIP | the ADS1115 is not responding (see T03.1) |
| T08.2 | Repeated sweeps | - SKIP | the ADS1115 is not responding (see T03.1) |
| T08.3 | Sweep agrees with MEAS | - SKIP | the ADS1115 is not responding (see T03.1) |
| T08.4 | CSV output format | - SKIP | the ADS1115 is not responding (see T03.1) |
| T10.1 | Power-up dark state | ✓ PASS |  |
| T10.2 | On-time watchdog | - SKIP | the ADS1115 is not responding (see T03.1) |
| T10.3 | Comms-loss failsafe | ✓ PASS |  |
| T10.4 | Single-channel invariant | ✓ PASS |  |
| T10.5 | Motion disarmed after comms loss | ✓ PASS |  |
| T11.1 | Comparison with the baseline | - SKIP | no baseline given (--baseline <file>); save one with --save-baseline |

## T01

### T01.1 Python and dependency versions: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Python version | ✓ PASS | 3.12.11 | >= 3.10 |
| pyserial installed | ✓ PASS | 3.5 | importable |
| pyyaml installed | ✓ PASS | 6.0.3 | importable |
| numpy installed | ✓ PASS | 2.5.4 | importable |
| matplotlib installed | ✓ PASS | 3.11.2 | importable |
| jinja2 installed | ✓ PASS | 3.1.6 | importable |

### T01.2 Serial port discovery: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Selected port is present | ✓ PASS | /dev/cu.usbserial-1120: present | --lio-port names an existing serial port |
| USB-serial chip recognised | ✓ PASS | VID:PID 1A86:7523 (CH340) | one of link.usb_ids |

### T01.3 Configuration loads and is self-consistent: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Config validates | ✓ PASS | lio_hw.yaml sha256 39be560ac85d |  |
| 16 holes | ✓ PASS | 16 entries |  |
| Rails split A = 1-9, B = 10-16 | ✓ PASS | A=[1, 2, 3, 4, 5, 6, 7, 8, 9] B=[10, 11, 12, 13, 14, 15, 16] |  |

## T02

### T02.1 Port open and boot banner: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Boot banner within the timeout | ✓ PASS | 1.63 s | <= 3 s |
| Banner identifies LIO firmware | ✓ PASS | # BOOT name=lio fw=2.2.0 proto=1 build=2026-11-04 adc_ok=0 hw_wdt=0 | name=lio, fw and proto present |

### T02.2 PING round-trip latency: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Every PING answered | ✓ PASS | 100/100 answered | all |
| p99 round trip | ✓ PASS | median 5.79 ms, p99 6.63 ms, max 6.66 ms | p99 < 50 ms |

### T02.3 INFO fields, versions and safety limits: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| INFO fields present | ✓ PASS | 21 fields | all protocol-1 INFO fields |
| Firmware compatible with this host package | ✓ PASS | fw 2.2.0 proto 1 | >= 2.0.0, proto 1 |
| settle_ms matches lio_hw.yaml | ✓ PASS | 8 | 8 |
| wdt_a_ms matches lio_hw.yaml | ✓ PASS | 2000 | 2000 |
| wdt_b_ms matches lio_hw.yaml | ✓ PASS | 5000 | 5000 |
| wdt_a_cap_ms matches lio_hw.yaml | ✓ PASS | 5000 | 5000 |
| wdt_b_cap_ms matches lio_hw.yaml | ✓ PASS | 10000 | 10000 |
| comms_ms matches lio_hw.yaml | ✓ PASS | 10000 | 10000 |
| arm_ms matches lio_hw.yaml | ✓ PASS | 60000 | 60000 |
| step_max matches lio_hw.yaml | ✓ PASS | 2048 | 2048 |
| jog_max matches lio_hw.yaml | ✓ PASS | 2048 | 2048 |
| jog_v_max matches lio_hw.yaml | ✓ PASS | 1000 | 1000 |
| jog_acc_max matches lio_hw.yaml | ✓ PASS | 1000 | 1000 |
| wake_ms_max matches lio_hw.yaml | ✓ PASS | 3000 | 3000 |
| ADC address matches lio_hw.yaml | ✓ PASS | 0x48 | 0x48 |
| ADC gain matches lio_hw.yaml | ✓ PASS | 1 | 1 |
| ADC rate matches lio_hw.yaml | ✓ PASS | 128 | 128 |

### T02.4 Robustness to bad input: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Unknown command | ✓ PASS | @140 ERR FROBNICATE code=1 msg=unknown command | ERR code=1 |
| Bad argument | ✓ PASS | @141 ERR MEAS code=2 msg=usage: MEAS <1-16> [settle_ms] [n] | ERR code=2 |
| Missing argument | ✓ PASS | @142 ERR CH code=2 msg=usage: CH <1-16> ON [ms] | ERR code=2 |
| Line over 64 characters | ✓ PASS | ERR ? code=6 msg=line too long | ERR code=6 |
| Garbage bytes, then PING | ✓ PASS | PING OK | PING still answered |

### T02.5 Sequence numbers and interleaved events: SKIP

the ADS1115 is not responding (see T03.1)

| Check | Status | Result | Criterion |
|---|---|---|---|
| @1 echoed | ✓ PASS | @1 OK PING uptime_ms=3291 | @1 OK PING |
| @4242 echoed | ✓ PASS | @4242 OK PING uptime_ms=3296 | @4242 OK PING |
| @99999 echoed | ✓ PASS | @99999 OK PING uptime_ms=3303 | @99999 OK PING |
| No @seq, none echoed | ✓ PASS | OK PING uptime_ms=3308 | OK PING |

### T02.6 RESET restores the boot state: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Banner after RESET | ✓ PASS | 0.02 s | <= 3 s |
| STATUS shows the safe state | ✓ PASS | ch=0 ce1=0 ce2=0 mask=0x0000 armed=0 | ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle |
| Settings back to defaults | ✓ PASS | wdt_a_ms=2000 (was set to 200) | 2000 |

## T03

### T03.1 I2C scan finds the ADS1115: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| ADS1115 at 0x48 | ✕ FAIL | found nothing; first check that power bank A is on: it alone powers the +5 V bus (ADS1115, LEDs, shift registers), and USB banks switch off when the load is small (measure about 5 V between +5 V and GND); then the ADS1115 wiring: SDA -> D11, SCL -> D12, ADDR -> GND (0x48), VDD 5 V and GND, 4.7 kOhm pull-ups; both lines should idle near 5 V | 0x48 acknowledges |
| I2C lines (SDA, SCL) | ✕ FAIL | SDA and SCL held low even with the Nano's pull-up on: a short to GND, a chip without power clamping the line, a damaged Nano pin, or the wrong pin (SDA = D11, SCL = D12); with power on, measure each line to GND, it should idle near 5 V | both idle high, rise on external pull-ups, not joined |
| No unexpected I2C devices | ✓ PASS | none | only the ADS1115 |

### T03.2 Dark ADC noise, all inputs: SKIP

the ADS1115 is not responding (see T03.1)

### T03.3 Gain sweep on dark inputs: SKIP

the ADS1115 is not responding (see T03.1)

### T03.4 ADC data rate: SKIP

the ADS1115 is not responding (see T03.1)

### T03.5 Long-term dark stability: SKIP

the ADS1115 is not responding (see T03.1)

## T04

### T04.1 Shift-register patterns with CE low: SKIP

the ADS1115 is not responding (see T03.1)

### T04.2 Shift-register loopback (optional jumper): SKIP

loopback jumper not fitted (this build has no loop-back input (pins.LOOP), plan §6.3); the shift registers are verified optically by T05.3

### T04.3 Optical address verification: SKIP

covered by T05.3 (each hole must light only its own expected response)

## T05

### T05.1 Rail gating by CE1 / CE2: SKIP

the ADS1115 is not responding (see T03.1)

### T05.2 Per-channel response: SKIP

the ADS1115 is not responding (see T03.1)

### T05.3 Channel address and isolation: SKIP

the ADS1115 is not responding (see T03.1)

### T05.4 Off-state return after each MEAS: SKIP

the ADS1115 is not responding (see T03.1)

### T05.5 Repeatability (interleaved MEAS): SKIP

the ADS1115 is not responding (see T03.1)

## T06

### T06.1 OPT101: SKIP

the ADS1115 is not responding (see T03.1)

### T06.2 InGaAs TIA: SKIP

the ADS1115 is not responding (see T03.1)

### T06.3 Cross-calibration on the shared holes: SKIP

the ADS1115 is not responding (see T03.1)

## T07

### T07.1 Step response and settling time: SKIP

the ADS1115 is not responding (see T03.1)

### T07.2 Recommended settle time: SKIP

the ADS1115 is not responding (see T03.1)

### T07.3 MEAS timing: SKIP

the ADS1115 is not responding (see T03.1)

## T08

### T08.1 SWEEP completes with a valid schema: SKIP

the ADS1115 is not responding (see T03.1)

### T08.2 Repeated sweeps: SKIP

the ADS1115 is not responding (see T03.1)

### T08.3 Sweep agrees with MEAS: SKIP

the ADS1115 is not responding (see T03.1)

### T08.4 CSV output format: SKIP

the ADS1115 is not responding (see T03.1)

## T10

### T10.1 Power-up dark state: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| STATUS safe after RESET | ✓ PASS | ch=0 ce1=0 ce2=0 mask=0x0000 armed=0 | ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle |
| STATUS safe after a port reopen | ✓ PASS | ch=0 ce1=0 ce2=0 mask=0x0000 armed=0 | ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle |

### T10.2 On-time watchdog: SKIP

the ADS1115 is not responding (see T03.1)

### T10.3 Comms-loss failsafe: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| '# FAILSAFE' after the comms timeout | ✓ PASS | # FAILSAFE reason=comms idle_ms=10000 | idle_ms 10000-10050 |
| Everything off after the failsafe | ✓ PASS | ch=0 ce1=0 ce2=0 mask=0x0000 armed=0 | ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle |
| Failsafe counted | ✓ PASS | failsafe_trips=1 | >= 1 |

### T10.4 Single-channel invariant: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| SR RAW 0x0000 then CE 1 1 | ✓ PASS | ERR code=3 needs exactly one selected hole on this rail; ce1=0 ce2=0 | refused (code 3), CE stays low |
| SR RAW 0x0005 then CE 1 1 | ✓ PASS | ERR code=3 needs exactly one selected hole on this rail; ce1=0 ce2=0 | refused (code 3), CE stays low |
| SR RAW 0x0101 then CE 1 1 | ✓ PASS | ERR code=3 needs exactly one selected hole on this rail; ce1=0 ce2=0 | refused (code 3), CE stays low |
| SR RAW 0x3000 then CE 2 1 | ✓ PASS | ERR code=3 needs exactly one selected hole on this rail; ce1=0 ce2=0 | refused (code 3), CE stays low |
| SR RAW 0x1004 then CE 1 1 | ✓ PASS | ERR code=3 needs exactly one selected hole on this rail; ce1=0 ce2=0 | refused (code 3), CE stays low |
| SR RAW 0x1004 then CE 2 1 | ✓ PASS | ERR code=3 needs exactly one selected hole on this rail; ce1=0 ce2=0 | refused (code 3), CE stays low |

### T10.5 Motion disarmed after comms loss: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Armed before the silence | ✓ PASS | armed=1 | armed=1 |
| Disarmed after the failsafe | ✓ PASS | armed=0 armed_ms=0 | armed=0 |

## T11

### T11.1 Comparison with the baseline: SKIP

no baseline given (--baseline <file>); save one with --save-baseline
