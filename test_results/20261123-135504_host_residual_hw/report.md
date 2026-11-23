# LIO test report: 20261123-135125_host

**Verdict: NOT FUNCTIONAL**: failure in a critical module: T03.2; 5 failing channels (more than 2): 8, 9, 12, 13, 14

- Target: `/dev/cu.usbmodem101`
- Started 2026-11-23T13:51:25-05:00, finished 2026-11-23T13:54:54-05:00
- Sample: `none-empty-chamber`, operator: residual-remediation
- Firmware 2.5.2 (proto 1, build 2026-11-17)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 e29964e36d34 (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git 944a820d22 (dirty)
- Counts: PASS 28, WARN 1, FAIL 5, SKIP 4
- LED duty budget: 112.4 s of cool-down waits, 0 over-budget on-time(s)

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
| T02.5 | Sequence numbers and interleaved events | ✓ PASS |  |
| T02.6 | RESET restores the boot state | ✓ PASS |  |
| T03.1 | I2C scan finds the ADS1115 | ✓ PASS |  |
| T03.2 | Dark ADC noise, all inputs | ✕ FAIL |  |
| T03.3 | Gain sweep on dark inputs | ✓ PASS |  |
| T03.4 | ADC data rate | ✓ PASS |  |
| T03.5 | Long-term dark stability | ✓ PASS |  |
| T04.1 | Shift-register patterns with CE low | ✓ PASS |  |
| T04.2 | Shift-register loopback (optional jumper) | - SKIP | loopback jumper not fitted (this build has no loop-back input (pins.LOOP), plan §6.3); the shift registers are verified optically by T05.3 |
| T04.3 | Optical address verification | - SKIP | covered by T05.3 (each hole must light only its own expected response) |
| T05.1 | Rail gating by CE1 / CE2 | ✕ FAIL |  |
| T05.2 | Per-channel response | ✕ FAIL |  |
| T05.3 | Channel address and isolation | ✕ FAIL |  |
| T05.4 | Off-state return after each MEAS | ✓ PASS |  |
| T05.5 | Repeatability (interleaved MEAS) | ✓ PASS | not judged (net < 1000 counts or detector unusable): 1/opt101, 2/opt101, 3/opt101, 4/opt101, 5/opt101, 6/opt101, 7/opt101, 8/opt101, 8/ingaas, 9/opt101, 9/ingaas, 10/opt101, 11/opt101, 12/ingaas, 13/ingaas, 14/ingaas, 15/ingaas |
| T06.1 | OPT101 | ✓ PASS |  |
| T06.2 | InGaAs TIA | ✓ PASS |  |
| T06.3 | Cross-calibration on the shared holes | ✕ FAIL |  |
| T07.1 | Step response and settling time | ! WARN |  |
| T07.2 | Recommended settle time | ✓ PASS |  |
| T07.3 | MEAS timing | ✓ PASS |  |
| T08.1 | SWEEP completes with a valid schema | ✓ PASS |  |
| T08.2 | Repeated sweeps | ✓ PASS |  |
| T08.3 | Sweep agrees with MEAS | ✓ PASS |  |
| T08.4 | CSV output format | ✓ PASS |  |
| T10.1 | Power-up dark state | ✓ PASS |  |
| T10.2 | On-time watchdog | - SKIP |  |
| T10.3 | Comms-loss failsafe | ✓ PASS |  |
| T10.4 | Single-channel invariant | ✓ PASS |  |
| T10.5 | Motion disarmed after comms loss | ✓ PASS |  |
| T11.1 | Comparison with the baseline | - SKIP | no baseline given (--baseline <file>); save one with --save-baseline |

### Per-channel response

![Per-channel response](plots/channels.png)

### Response matrix

![Response matrix](plots/crosstalk.png)

### Dark noise

![Dark noise](plots/noise.png)

### Step responses

![Step responses](plots/settling.png)

### Repeated sweeps

![Repeated sweeps](plots/sweeps.png)

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
| Selected port is present | ✓ PASS | /dev/cu.usbmodem101: present | --lio-port names an existing serial port |
| USB-serial chip recognised | ✓ PASS | VID:PID 2341:0074 (Arduino Nano R4 (native USB)) | one of link.usb_ids |

### T01.3 Configuration loads and is self-consistent: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Config validates | ✓ PASS | lio_hw.yaml sha256 e29964e36d34 |  |
| 16 holes | ✓ PASS | 16 entries |  |
| Rails split A = 1-8, B = 9-16 (as built) | ✓ PASS | A=[1, 2, 3, 4, 5, 6, 7, 8] B=[9, 10, 11, 12, 13, 14, 15, 16] |  |

## T02

### T02.1 Port open and boot banner: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Boot banner within the timeout | ✓ PASS | 0.06 s | <= 3 s |
| Banner identifies LIO firmware | ✓ PASS | # BOOT name=lio fw=2.5.2 proto=1 build=2026-11-17 adc_ok=1 hw_wdt=0 | name=lio, fw and proto present |

### T02.2 PING round-trip latency: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Every PING answered | ✓ PASS | 100/100 answered | all |
| p99 round trip | ✓ PASS | median 0.88 ms, p99 0.99 ms, max 1.04 ms | p99 < 50 ms |

### T02.3 INFO fields, versions and safety limits: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| INFO fields present | ✓ PASS | 21 fields | all protocol-1 INFO fields |
| Firmware compatible with this host package | ✓ PASS | fw 2.5.2 proto 1 | >= 2.0.0, proto 1 |
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
| Unknown command | ✓ PASS | @146 ERR FROBNICATE code=1 msg=unknown command | ERR code=1 |
| Bad argument | ✓ PASS | refused before write | OwnershipError refuse (no production light bypass) |
| Missing argument | ✓ PASS | refused before write | OwnershipError refuse (no production light bypass) |
| Line over 64 characters | ✓ PASS | ERR ? code=6 msg=line too long | ERR code=6 |
| Garbage bytes, then PING | ✓ PASS | PING OK | PING still answered |

### T02.5 Sequence numbers and interleaved events: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| @1 echoed | ✓ PASS | @1 OK PING uptime_ms=780347 | @1 OK PING |
| @4242 echoed | ✓ PASS | @4242 OK PING uptime_ms=780348 | @4242 OK PING |
| @99999 echoed | ✓ PASS | @99999 OK PING uptime_ms=780349 | @99999 OK PING |
| No @seq, none echoed | ✓ PASS | OK PING uptime_ms=780349 | OK PING |
| Response found after interleaved events | ✓ PASS | 20 '# S' events then OK | 20 events |
| Asynchronous '# OFF' does not desynchronise | ✓ PASS | 10/10 PINGs matched; 1 timer event(s) seen | all PINGs answered in order, one '# OFF' |

### T02.6 RESET restores the boot state: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Banner after RESET | ✓ PASS | 0.01 s | <= 3 s |
| STATUS shows the safe state | ✓ PASS | ch=0 ce1=0 ce2=0 mask=0x0000 armed=0 | ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle |
| Settings back to defaults | ✓ PASS | wdt_a_ms=2000 (was set to 200) | 2000 |

## T03

### T03.1 I2C scan finds the ADS1115: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| ADS1115 at 0x48 | ✓ PASS | found ['0x48'] | 0x48 acknowledges |
| I2C lines (SDA, SCL) | ✓ PASS | lines idle high with pull-ups, not bridged; 0x48 answers at 166.666 kHz | both idle high, rise on external pull-ups, not joined |
| No unexpected I2C devices | ✓ PASS | none | only the ADS1115 |

### T03.2 Dark ADC noise, all inputs: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| ADS A0 (ingaas) dark noise | ✕ FAIL | mean -331.4, sigma 37.22 counts (n=64) | sigma <= 20 counts |
| ADS A1 (opt101) dark noise | ✓ PASS | mean 59.0, sigma 0.38 counts (n=64) | sigma <= 20 counts |
| ADS A2 (unconnected) | ✓ PASS | recorded only: mean 4491.9, sigma 10.11 | floating input |
| ADS A3 (unconnected) | ✓ PASS | recorded only: mean 2598.6, sigma 1.93 | floating input |

### T03.3 Gain sweep on dark inputs: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| GAIN 2/3 accepted | ✓ PASS | lsb 0.1875 mV | 0.1875 mV |
| GAIN 1 accepted | ✓ PASS | lsb 0.125 mV | 0.125 mV |
| GAIN 2 accepted | ✓ PASS | lsb 0.0625 mV | 0.0625 mV |
| GAIN 4 accepted | ✓ PASS | lsb 0.03125 mV | 0.03125 mV |
| GAIN 8 accepted | ✓ PASS | lsb 0.015625 mV | 0.015625 mV |
| GAIN 16 accepted | ✓ PASS | lsb 0.0078125 mV | 0.0078125 mV |
| ingaas at GAIN 2/3 agrees with GAIN 1 | ✓ PASS | -41.59 mV vs -41.80 mV | within 19.38 mV |
| ingaas at GAIN 1 agrees with GAIN 1 | ✓ PASS | -41.80 mV vs -41.80 mV | within 19.38 mV |
| ingaas at GAIN 2 agrees with GAIN 1 | ✓ PASS | -41.64 mV vs -41.80 mV | within 19.38 mV |
| ingaas at GAIN 4 agrees with GAIN 1 | ✓ PASS | -41.18 mV vs -41.80 mV | within 19.38 mV |
| ingaas at GAIN 8 agrees with GAIN 1 | ✓ PASS | -40.96 mV vs -41.80 mV | within 19.40 mV |
| ingaas at GAIN 16 agrees with GAIN 1 | ✓ PASS | -41.08 mV vs -41.80 mV | within 19.38 mV |
| GAIN 2/3 accepted | ✓ PASS | lsb 0.1875 mV | 0.1875 mV |
| GAIN 1 accepted | ✓ PASS | lsb 0.125 mV | 0.125 mV |
| GAIN 2 accepted | ✓ PASS | lsb 0.0625 mV | 0.0625 mV |
| GAIN 4 accepted | ✓ PASS | lsb 0.03125 mV | 0.03125 mV |
| GAIN 8 accepted | ✓ PASS | lsb 0.015625 mV | 0.015625 mV |
| GAIN 16 accepted | ✓ PASS | lsb 0.0078125 mV | 0.0078125 mV |
| opt101 at GAIN 2/3 agrees with GAIN 1 | ✓ PASS | 7.50 mV vs 7.38 mV | within 5.17 mV |
| opt101 at GAIN 1 agrees with GAIN 1 | ✓ PASS | 7.38 mV vs 7.38 mV | within 5.17 mV |
| opt101 at GAIN 2 agrees with GAIN 1 | ✓ PASS | 7.37 mV vs 7.38 mV | within 5.17 mV |
| opt101 at GAIN 4 agrees with GAIN 1 | ✓ PASS | 7.09 mV vs 7.38 mV | within 5.17 mV |
| opt101 at GAIN 8 agrees with GAIN 1 | ✓ PASS | 7.77 mV vs 7.38 mV | within 5.17 mV |
| opt101 at GAIN 16 agrees with GAIN 1 | ✓ PASS | 7.77 mV vs 7.38 mV | within 5.17 mV |

### T03.4 ADC data rate: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| 8 SPS conversion interval | ✓ PASS | 120.744 ms (nominal 125.000 ms, overhead -4.256 ms) | 106.250-145.250 ms |
| 16 SPS conversion interval | ✓ PASS | 61.184 ms (nominal 62.500 ms, overhead -1.316 ms) | 53.125-73.375 ms |
| 32 SPS conversion interval | ✓ PASS | 31.242 ms (nominal 31.250 ms, overhead -0.008 ms) | 26.562-37.438 ms |
| 64 SPS conversion interval | ✓ PASS | 16.434 ms (nominal 15.625 ms, overhead +0.809 ms) | 13.281-19.469 ms |
| 128 SPS conversion interval | ✓ PASS | 8.863 ms (nominal 7.812 ms, overhead +1.050 ms) | 6.641-10.484 ms |
| 250 SPS conversion interval | ✓ PASS | 5.288 ms (nominal 4.000 ms, overhead +1.288 ms) | 3.400-6.100 ms |
| 475 SPS conversion interval | ✓ PASS | 3.342 ms (nominal 2.105 ms, overhead +1.237 ms) | 1.789-3.921 ms |
| 860 SPS conversion interval | ✓ PASS | 2.536 ms (nominal 1.163 ms, overhead +1.373 ms) | 0.988-2.837 ms |

### T03.5 Long-term dark stability: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| ingaas drift over 60 s | ✓ PASS | +39.9 counts/min (0.122 % FS/min), sigma 37.35 | <= 2 % FS/min |
| opt101 drift over 60 s | ✓ PASS | -0.1 counts/min (0.000 % FS/min), sigma 0.36 | <= 2 % FS/min |

## T04

### T04.1 Shift-register patterns with CE low: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| SR RAW 0x0000 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xFFFF | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x0001 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x0002 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x0004 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x0008 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x0010 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x0020 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x0040 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x0080 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x0100 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x0200 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x0400 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x0800 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x1000 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x2000 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x4000 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x8000 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xFFFE | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xFFFD | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xFFFB | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xFFF7 | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xFFEF | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xFFDF | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xFFBF | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xFF7F | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xFEFF | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xFDFF | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xFBFF | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xF7FF | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xEFFF | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xDFFF | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0xBFFF | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |
| SR RAW 0x7FFF | ✓ PASS | echoed, CE low, detectors dark | mask echoed in reply and STATUS; CE1 = CE2 = 0; detectors at dark |

### T04.2 Shift-register loopback (optional jumper): SKIP

loopback jumper not fitted (this build has no loop-back input (pins.LOOP), plan §6.3); the shift registers are verified optically by T05.3

### T04.3 Optical address verification: SKIP

covered by T05.3 (each hole must light only its own expected response)

## T05

### T05.1 Rail gating by CE1 / CE2: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 12 selected, CE2 high | ✕ FAIL | ingaas -314; no light: RAIL B driver, CE2 or the LED is dead | light above the detection threshold |
| Hole 8 selected, CE1 low | ✓ PASS | opt101 59 (dark 59) | dark |
| Hole 8 selected, CE1 high | ✓ PASS | opt101 215 | light above the detection threshold |
| Hole 8 with CE2 (wrong rail) | ✓ PASS | ERR code=3 needs exactly one selected hole on this rail | refused (code 3) |
| Hole 12 selected, CE2 low | ✓ PASS | ingaas -336 (dark -331) | dark |
| Hole 12 with CE1 (wrong rail) | ✓ PASS | ERR code=3 needs exactly one selected hole on this rail | refused (code 3) |

### T05.2 Per-channel response: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 8 (850) on ingaas | ✕ FAIL | net +22 (none); expected signal, none seen | expect signal: signal >= 263 |
| Hole 9 (940) on ingaas | ✕ FAIL | net +38 (none); expected signal, none seen | expect signal: signal >= 263 |
| Hole 12 (1450) on ingaas | ✕ FAIL | net +8 (none); expected signal, none seen | expect signal: signal >= 263 |
| Hole 13 (1550) on ingaas | ✕ FAIL | net -1 (none); expected signal, none seen | expect signal: signal >= 263 |
| Hole 14 (1650) on ingaas | ✕ FAIL | net -2 (none); expected signal, none seen | expect signal: signal >= 263 |
| Hole 15 (1760) on ingaas | ! WARN | net +0 (none); weak channel below the weak threshold | expect weak: signal >= 263 |
| Hole 1 (395) on opt101 | ✓ PASS | net +35 (signal); signal as expected | expect signal: signal >= 15 |
| Hole 2 (purple) on opt101 | ✓ PASS | net +48 (signal); signal as expected | expect signal: signal >= 15 |
| Hole 3 (blue) on opt101 | ✓ PASS | net +32 (signal); signal as expected | expect signal: signal >= 15 |
| Hole 4 (green) on opt101 | ✓ PASS | net +57 (signal); signal as expected | expect signal: signal >= 15 |
| Hole 5 (yellow) on opt101 | ✓ PASS | net +25 (signal); signal as expected | expect signal: signal >= 15 |
| Hole 6 (orange) on opt101 | ✓ PASS | net +23 (signal); signal as expected | expect signal: signal >= 15 |
| Hole 7 (red) on opt101 | ✓ PASS | net +32 (signal); signal as expected | expect signal: signal >= 15 |
| Hole 8 (850) on opt101 | ✓ PASS | net +172 (signal); signal as expected | expect signal: signal >= 15 |
| Hole 9 (940) on opt101 | ✓ PASS | net +122 (signal); signal as expected | expect signal: signal >= 15 |
| Hole 10 (white) on opt101 | ✓ PASS | net +62 (signal); signal as expected | expect signal: signal >= 15 |
| Hole 11 (pink) on opt101 | ✓ PASS | net +153 (signal); signal as expected | expect signal: signal >= 15 |
| Hole 1 (395) on ingaas | - SKIP | not judged: 395 is outside the ingaas range (judged by opt101); recorded net +4 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 2 (purple) on ingaas | - SKIP | not judged: purple is outside the ingaas range (judged by opt101); recorded net -7 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 3 (blue) on ingaas | - SKIP | not judged: blue is outside the ingaas range (judged by opt101); recorded net -8 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 4 (green) on ingaas | - SKIP | not judged: green is outside the ingaas range (judged by opt101); recorded net +0 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 5 (yellow) on ingaas | - SKIP | not judged: yellow is outside the ingaas range (judged by opt101); recorded net +17 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 6 (orange) on ingaas | - SKIP | not judged: orange is outside the ingaas range (judged by opt101); recorded net +17 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 7 (red) on ingaas | - SKIP | not judged: red is outside the ingaas range (judged by opt101); recorded net +8 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 10 (white) on ingaas | - SKIP | not judged: white is outside the ingaas range (judged by opt101); recorded net +11 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 11 (pink) on ingaas | - SKIP | not judged: pink is outside the ingaas range (judged by opt101); recorded net +5 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 12 (1450) on opt101 | - SKIP | not judged: 1450 is outside the opt101 range (judged by ingaas); recorded net +11 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 13 (1550) on opt101 | - SKIP | not judged: 1550 is outside the opt101 range (judged by ingaas); recorded net +2 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 14 (1650) on opt101 | - SKIP | not judged: 1650 is outside the opt101 range (judged by ingaas); recorded net +0 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 15 (1760) on opt101 | - SKIP | not judged: 1760 is outside the opt101 range (judged by ingaas); recorded net +1 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 16 (1850) on ingaas | - SKIP | not judged: 1850 is outside the ingaas range (judged by no detector); recorded net +24 | out-of-range readings are not judged (channel.judge_out_of_range: false) |
| Hole 16 (1850) on opt101 | - SKIP | not judged: 1850 is outside the opt101 range (judged by no detector); recorded net +199 | out-of-range readings are not judged (channel.judge_out_of_range: false) |

### T05.3 Channel address and isolation: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 8 (850) detector pattern | ✕ FAIL | no response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['ingaas', 'opt101'] |
| Hole 9 (940) detector pattern | ✕ FAIL | no response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['ingaas', 'opt101'] |
| Hole 12 (1450) detector pattern | ✕ FAIL | no response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['ingaas'] |
| Hole 13 (1550) detector pattern | ✕ FAIL | no response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['ingaas'] |
| Hole 14 (1650) detector pattern | ✕ FAIL | no response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['ingaas'] |
| Hole 15 (1760) detector pattern | ! WARN | no response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['ingaas'] |
| Hole 1 (395) detector pattern | ✓ PASS | seen by ['opt101'] as expected (ingaas not judged: outside its range) | expected ['opt101'] |
| Hole 2 (purple) detector pattern | ✓ PASS | seen by ['opt101'] as expected (ingaas not judged: outside its range) | expected ['opt101'] |
| Hole 3 (blue) detector pattern | ✓ PASS | seen by ['opt101'] as expected (ingaas not judged: outside its range) | expected ['opt101'] |
| Hole 4 (green) detector pattern | ✓ PASS | seen by ['opt101'] as expected (ingaas not judged: outside its range) | expected ['opt101'] |
| Hole 5 (yellow) detector pattern | ✓ PASS | seen by ['opt101'] as expected (ingaas not judged: outside its range) | expected ['opt101'] |
| Hole 6 (orange) detector pattern | ✓ PASS | seen by ['opt101'] as expected (ingaas not judged: outside its range) | expected ['opt101'] |
| Hole 7 (red) detector pattern | ✓ PASS | seen by ['opt101'] as expected (ingaas not judged: outside its range) | expected ['opt101'] |
| Hole 10 (white) detector pattern | ✓ PASS | seen by ['opt101'] as expected (ingaas not judged: outside its range) | expected ['opt101'] |
| Hole 11 (pink) detector pattern | ✓ PASS | seen by ['opt101'] as expected (ingaas not judged: outside its range) | expected ['opt101'] |
| Hole 16 (1850) detector pattern | ✓ PASS | seen by nothing as expected (ingaas, opt101 not judged: outside its range) | expected none |
| Signatures unique | ✓ PASS | no two channels look the same | cosine < 0.98 or amplitude differs by more than 1 % |

### T05.4 Off-state return after each MEAS: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 1 ingaas back to dark | ✓ PASS | -335.5 after OFF vs dark -335 | within 5 sigma (131.6 counts) |
| Hole 1 opt101 back to dark | ✓ PASS | 59.2 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 2 ingaas back to dark | ✓ PASS | -333.2 after OFF vs dark -328 | within 5 sigma (131.6 counts) |
| Hole 2 opt101 back to dark | ✓ PASS | 59.2 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 3 ingaas back to dark | ✓ PASS | -329.5 after OFF vs dark -327 | within 5 sigma (131.6 counts) |
| Hole 3 opt101 back to dark | ✓ PASS | 59.5 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 4 ingaas back to dark | ✓ PASS | -326.5 after OFF vs dark -328 | within 5 sigma (131.6 counts) |
| Hole 4 opt101 back to dark | ✓ PASS | 58.8 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 5 ingaas back to dark | ✓ PASS | -334.0 after OFF vs dark -334 | within 5 sigma (131.6 counts) |
| Hole 5 opt101 back to dark | ✓ PASS | 59.2 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 6 ingaas back to dark | ✓ PASS | -328.8 after OFF vs dark -337 | within 5 sigma (131.6 counts) |
| Hole 6 opt101 back to dark | ✓ PASS | 59.5 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 7 ingaas back to dark | ✓ PASS | -336.0 after OFF vs dark -334 | within 5 sigma (131.6 counts) |
| Hole 7 opt101 back to dark | ✓ PASS | 59.2 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 8 ingaas back to dark | ✓ PASS | -333.2 after OFF vs dark -327 | within 5 sigma (131.6 counts) |
| Hole 8 opt101 back to dark | ✓ PASS | 59.5 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 9 ingaas back to dark | ✓ PASS | -331.8 after OFF vs dark -336 | within 5 sigma (131.6 counts) |
| Hole 9 opt101 back to dark | ✓ PASS | 59.5 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 10 ingaas back to dark | ✓ PASS | -330.5 after OFF vs dark -337 | within 5 sigma (131.6 counts) |
| Hole 10 opt101 back to dark | ✓ PASS | 59.2 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 11 ingaas back to dark | ✓ PASS | -328.2 after OFF vs dark -325 | within 5 sigma (131.6 counts) |
| Hole 11 opt101 back to dark | ✓ PASS | 59.2 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 12 ingaas back to dark | ✓ PASS | -327.5 after OFF vs dark -326 | within 5 sigma (131.6 counts) |
| Hole 12 opt101 back to dark | ✓ PASS | 59.2 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 13 ingaas back to dark | ✓ PASS | -326.8 after OFF vs dark -327 | within 5 sigma (131.6 counts) |
| Hole 13 opt101 back to dark | ✓ PASS | 59.0 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 14 ingaas back to dark | ✓ PASS | -327.0 after OFF vs dark -328 | within 5 sigma (131.6 counts) |
| Hole 14 opt101 back to dark | ✓ PASS | 59.2 after OFF vs dark 59 | within 5 sigma (3.5 counts) |
| Hole 15 ingaas back to dark | ✓ PASS | -327.0 after OFF vs dark -326 | within 5 sigma (131.6 counts) |
| Hole 15 opt101 back to dark | ✓ PASS | 59.2 after OFF vs dark 60 | within 5 sigma (3.5 counts) |
| Hole 16 ingaas back to dark | ✓ PASS | -326.5 after OFF vs dark -328 | within 5 sigma (131.6 counts) |
| Hole 16 opt101 back to dark | ✓ PASS | 59.5 after OFF vs dark 59 | within 5 sigma (3.5 counts) |

### T05.5 Repeatability (interleaved MEAS): PASS

not judged (net < 1000 counts or detector unusable): 1/opt101, 2/opt101, 3/opt101, 4/opt101, 5/opt101, 6/opt101, 7/opt101, 8/opt101, 8/ingaas, 9/opt101, 9/ingaas, 10/opt101, 11/opt101, 12/ingaas, 13/ingaas, 14/ingaas, 15/ingaas

## T06

### T06.1 OPT101: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| opt101 dark offset | ✓ PASS | 59.0 counts | 0 to 800 counts |
| Responds to hole 1 (395) | ✓ PASS | net +35 | no zeros where light is expected |
| Responds to hole 2 (purple) | ✓ PASS | net +48 | no zeros where light is expected |
| Responds to hole 3 (blue) | ✓ PASS | net +32 | no zeros where light is expected |
| Responds to hole 4 (green) | ✓ PASS | net +57 | no zeros where light is expected |
| Responds to hole 5 (yellow) | ✓ PASS | net +25 | no zeros where light is expected |
| Responds to hole 6 (orange) | ✓ PASS | net +23 | no zeros where light is expected |
| Responds to hole 7 (red) | ✓ PASS | net +32 | no zeros where light is expected |
| Responds to hole 10 (white) | ✓ PASS | net +62 | no zeros where light is expected |
| Responds to hole 11 (pink) | ✓ PASS | net +153 | no zeros where light is expected |
| Not saturated | ✓ PASS | peak 258 | < 29000 counts |

### T06.2 InGaAs TIA: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Dark signal steady | ✓ PASS | dark mean -331, sigma 37.2 | sigma <= 100 and mean >= -1500 |
| ingaas dark offset | ✓ PASS | -331.4 counts | -400 to 2000 counts |
| Polarity gate (hole 8) | ✓ PASS | net +39 | net >= -5 sigma |
| Hole 9 InGaAs polarity | ✓ PASS | net +38 | net not negative |
| Hole 12 InGaAs polarity | ✓ PASS | net +8 | net not negative |
| Hole 13 InGaAs polarity | ✓ PASS | net -1 | net not negative |
| Hole 14 InGaAs polarity | ✓ PASS | net -2 | net not negative |
| InGaAs not saturated | ✓ PASS | no hole saturates | < 27000 counts |

### T06.3 Cross-calibration on the shared holes: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 8 seen by both detectors | ✕ FAIL | no response on ['ingaas'] | both above the detection threshold |
| Hole 9 seen by both detectors | ✕ FAIL | no response on ['ingaas'] | both above the detection threshold |

## T07

### T07.1 Step response and settling time: WARN

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 13 step response | ! WARN | no step on ingaas (baseline -335, plateau -335) | a step above the detection threshold |
| Hole 3 (opt101) step response | ✓ PASS | settled within one sample: t99 <= 1.29 ms (upper bound, limited by the sample interval) | time to 99 % recorded |
| Hole 8 (opt101) step response | ✓ PASS | settled within one sample: t99 <= 1.29 ms (upper bound, limited by the sample interval) | time to 99 % recorded |

### T07.2 Recommended settle time: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Configured settle_ms is long enough | ✓ PASS | recommended 2 ms (max 1.29 ms x 1.5), configured 8 ms | recommended <= 8 ms |

### T07.3 MEAS timing: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| MEAS 3 8 1 on-time | ✓ PASS | t_on_ms 25 | 21.3-32.0 ms and <= watchdog 2000 ms |
| MEAS 3 20 4 on-time | ✓ PASS | t_on_ms 90 | 73.1-106.9 ms and <= watchdog 2000 ms |

## T08

### T08.1 SWEEP completes with a valid schema: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| 16 records, holes 1-16 in order | ✓ PASS | 16 records: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16] | holes 1..16 |
| Sweep records parse | ✓ PASS | all '# M' fields present and integer |  |
| Sweep duration | ✓ PASS | 833 ms (host 898 ms) | <= 2.5 s |

### T08.2 Repeated sweeps: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| ingaas dark stable between sweeps | ✓ PASS | per-sweep dark means span 2.12 counts | <= 46.52 counts |
| opt101 dark stable between sweeps | ✓ PASS | per-sweep dark means span 0.38 counts | <= 1.25 counts |

### T08.3 Sweep agrees with MEAS: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 4 opt101 sweep vs MEAS | ✓ PASS | sweep 57 vs MEAS 57 (0.7 %) | within 6 counts (max of 10 %, 5 sigma) |
| Hole 8 opt101 sweep vs MEAS | ✓ PASS | sweep 169 vs MEAS 172 (1.5 %) | within 17 counts (max of 10 %, 5 sigma) |
| Hole 9 opt101 sweep vs MEAS | ✓ PASS | sweep 119 vs MEAS 122 (2.6 %) | within 12 counts (max of 10 %, 5 sigma) |
| Hole 10 opt101 sweep vs MEAS | ✓ PASS | sweep 62 vs MEAS 62 (0.6 %) | within 6 counts (max of 10 %, 5 sigma) |
| Hole 11 opt101 sweep vs MEAS | ✓ PASS | sweep 153 vs MEAS 153 (0.1 %) | within 15 counts (max of 10 %, 5 sigma) |

### T08.4 CSV output format: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Header | ✓ PASS | hole,label,dark_ingaas,dark_opt101,ingaas,opt101,net_ingaas_V,net_opt101_V | hole,label,dark_ingaas,dark_opt101,ingaas,opt101,net_ingaas_V,net_opt101_V |
| One CRLF-terminated row per hole | ✓ PASS | 16 rows | 16 rows, CRLF |
| Rows byte-identical to the original logger's format | ✓ PASS | all rows identical | same columns, rounding, labels |

## T10

### T10.1 Power-up dark state: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| STATUS safe after RESET | ✓ PASS | ch=0 ce1=0 ce2=0 mask=0x0000 armed=0 | ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle |
| Detectors dark after RESET | ✓ PASS | ingaas -326, opt101 60 | dark +- k sigma |
| STATUS safe after a port reopen | ✓ PASS | ch=0 ce1=0 ce2=0 mask=0x0000 armed=0 | ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle |
| Detectors dark after a port reopen | ✓ PASS | ingaas -334, opt101 59 | dark +- k sigma |

### T10.2 On-time watchdog: SKIP

| Check | Status | Result | Criterion |
|---|---|---|---|
| RAIL A watchdog clamp pulse | - SKIP | unsupported under approved budgets/capability: refuse before light: conservative bound 2000.0 ms unsupported by budget (request 2000.000 ms exceeds budget 1000.000 ms for hole 3) |  |
| RAIL B watchdog clamp pulse | - SKIP | unsupported under approved budgets/capability: refuse before light: conservative bound 5000.0 ms unsupported by budget (request 5000.000 ms exceeds budget 1000.000 ms for hole 9) |  |

### T10.3 Comms-loss failsafe: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| '# FAILSAFE' after the comms timeout | ✓ PASS | # FAILSAFE reason=comms idle_ms=10000 | idle_ms 10000-10050 |
| Everything off after the failsafe | ✓ PASS | ch=0 ce1=0 ce2=0 mask=0x0000 armed=0 | ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle |
| Failsafe counted | ✓ PASS | failsafe_trips=1 | >= 1 |

### T10.4 Single-channel invariant: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| SR RAW 0x0000 then CE 1 1 | ✓ PASS | host refused before write: CE on refused: no single selected hole to reserve duty against; ce1=0 ce2=0 | refused (code 3 or host gate), CE stays low |
| SR RAW 0x0005 then CE 1 1 | ✓ PASS | host refused before write: CE on refused: no single selected hole to reserve duty against; ce1=0 ce2=0 | refused (code 3 or host gate), CE stays low |
| SR RAW 0x0101 then CE 1 1 | ✓ PASS | host refused before write: CE on refused: no single selected hole to reserve duty against; ce1=0 ce2=0 | refused (code 3 or host gate), CE stays low |
| SR RAW 0x0101 then CE 2 1 | ✓ PASS | host refused before write: CE on refused: no single selected hole to reserve duty against; ce1=0 ce2=0 | refused (code 3 or host gate), CE stays low |
| SR RAW 0x3000 then CE 2 1 | ✓ PASS | host refused before write: CE on refused: no single selected hole to reserve duty against; ce1=0 ce2=0 | refused (code 3 or host gate), CE stays low |
| SR RAW 0x1004 then CE 1 1 | ✓ PASS | host refused before write: CE on refused: no single selected hole to reserve duty against; ce1=0 ce2=0 | refused (code 3 or host gate), CE stays low |
| SR RAW 0x1004 then CE 2 1 | ✓ PASS | host refused before write: CE on refused: no single selected hole to reserve duty against; ce1=0 ce2=0 | refused (code 3 or host gate), CE stays low |

### T10.5 Motion disarmed after comms loss: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Armed before the silence | ✓ PASS | armed=1 | armed=1 |
| Disarmed after the failsafe | ✓ PASS | armed=0 armed_ms=0 | armed=0 |

## T11

### T11.1 Comparison with the baseline: SKIP

no baseline given (--baseline <file>); save one with --save-baseline
