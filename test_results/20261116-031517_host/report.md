# LIO test report: 20261116-031517_host

**Verdict: NOT FUNCTIONAL**: failures not tied to a channel: T06.2; 9 failing channels (more than 2): 1, 2, 3, 4, 7, 8, 9, 10, 11

- Target: `/dev/cu.usbmodem101`
- Started 2026-11-16T03:15:17-05:00, finished 2026-11-16T03:16:48-05:00
- Sample: `none-empty-chamber`, operator: claude-code, notes: whole system, automatic tests only; circuit GND earthed via the wall-plug earth pin; OPT101 soldered, cover on
- Firmware 2.3.1 (proto 1, build 2026-11-10)
- Config `test_results/_session/lio_hw_nowake.yaml` sha256 9d912069e7b4 (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git ff62fb7d5e
- Counts: PASS 30, WARN 1, FAIL 4, SKIP 3
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
| T02.5 | Sequence numbers and interleaved events | ✓ PASS |  |
| T02.6 | RESET restores the boot state | ✓ PASS |  |
| T03.1 | I2C scan finds the ADS1115 | ✓ PASS |  |
| T03.2 | Dark ADC noise, all inputs | ✓ PASS |  |
| T03.3 | Gain sweep on dark inputs | ✓ PASS |  |
| T03.4 | ADC data rate | ✓ PASS |  |
| T03.5 | Long-term dark stability | ✓ PASS |  |
| T04.1 | Shift-register patterns with CE low | ✓ PASS |  |
| T04.2 | Shift-register loopback (optional jumper) | - SKIP | loopback jumper not fitted (this build has no loop-back input (pins.LOOP), plan §6.3); the shift registers are verified optically by T05.3 |
| T04.3 | Optical address verification | - SKIP | covered by T05.3 (each hole must light only its own expected response) |
| T05.1 | Rail gating by CE1 / CE2 | ✓ PASS |  |
| T05.2 | Per-channel response | ✕ FAIL |  |
| T05.3 | Channel address and isolation | ✕ FAIL |  |
| T05.4 | Off-state return after each MEAS | ✓ PASS |  |
| T05.5 | Repeatability (interleaved MEAS) | ✓ PASS | not judged (net < 1000 counts or detector unusable): 1/opt101, 2/opt101, 3/opt101, 4/opt101, 5/opt101, 6/opt101, 7/opt101, 8/opt101, 8/ingaas, 9/opt101, 9/ingaas, 10/opt101, 11/opt101, 12/ingaas, 13/ingaas, 14/ingaas, 15/ingaas |
| T06.1 | OPT101 | ✓ PASS |  |
| T06.2 | InGaAs TIA | ✕ FAIL |  |
| T06.3 | Cross-calibration on the shared holes | ✕ FAIL |  |
| T07.1 | Step response and settling time | ✓ PASS |  |
| T07.2 | Recommended settle time | ! WARN |  |
| T07.3 | MEAS timing | ✓ PASS |  |
| T08.1 | SWEEP completes with a valid schema | ✓ PASS |  |
| T08.2 | Repeated sweeps | ✓ PASS |  |
| T08.3 | Sweep agrees with MEAS | ✓ PASS |  |
| T08.4 | CSV output format | ✓ PASS |  |
| T10.1 | Power-up dark state | ✓ PASS |  |
| T10.2 | On-time watchdog | ✓ PASS |  |
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
| Config validates | ✓ PASS | lio_hw_nowake.yaml sha256 9d912069e7b4 |  |
| 16 holes | ✓ PASS | 16 entries |  |
| Rails split A = 1-9, B = 10-16 | ✓ PASS | A=[1, 2, 3, 4, 5, 6, 7, 8, 9] B=[10, 11, 12, 13, 14, 15, 16] |  |

## T02

### T02.1 Port open and boot banner: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Boot banner within the timeout | ✓ PASS | 0.05 s | <= 3 s |
| Banner identifies LIO firmware | ✓ PASS | # BOOT name=lio fw=2.3.1 proto=1 build=2026-11-10 adc_ok=1 hw_wdt=0 | name=lio, fw and proto present |

### T02.2 PING round-trip latency: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Every PING answered | ✓ PASS | 100/100 answered | all |
| p99 round trip | ✓ PASS | median 0.89 ms, p99 1.16 ms, max 1.29 ms | p99 < 50 ms |

### T02.3 INFO fields, versions and safety limits: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| INFO fields present | ✓ PASS | 21 fields | all protocol-1 INFO fields |
| Firmware compatible with this host package | ✓ PASS | fw 2.3.1 proto 1 | >= 2.0.0, proto 1 |
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
| Unknown command | ✓ PASS | @139 ERR FROBNICATE code=1 msg=unknown command | ERR code=1 |
| Bad argument | ✓ PASS | @140 ERR MEAS code=2 msg=usage: MEAS <1-16> [settle_ms] [n] | ERR code=2 |
| Missing argument | ✓ PASS | @141 ERR CH code=2 msg=usage: CH <1-16> ON [ms] | ERR code=2 |
| Line over 64 characters | ✓ PASS | ERR ? code=6 msg=line too long | ERR code=6 |
| Garbage bytes, then PING | ✓ PASS | PING OK | PING still answered |

### T02.5 Sequence numbers and interleaved events: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| @1 echoed | ✓ PASS | @1 OK PING uptime_ms=55160 | @1 OK PING |
| @4242 echoed | ✓ PASS | @4242 OK PING uptime_ms=55160 | @4242 OK PING |
| @99999 echoed | ✓ PASS | @99999 OK PING uptime_ms=55161 | @99999 OK PING |
| No @seq, none echoed | ✓ PASS | OK PING uptime_ms=55162 | OK PING |
| Response found after interleaved events | ✓ PASS | 20 '# S' events then OK | 20 events |
| Asynchronous '# OFF' does not desynchronise | ✓ PASS | 10/10 PINGs matched; 1 timer event(s) seen | all PINGs answered in order, one '# OFF' |

### T02.6 RESET restores the boot state: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Banner after RESET | ✓ PASS | 0.00 s | <= 3 s |
| STATUS shows the safe state | ✓ PASS | ch=0 ce1=0 ce2=0 mask=0x0000 armed=0 | ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle |
| Settings back to defaults | ✓ PASS | wdt_a_ms=2000 (was set to 200) | 2000 |

## T03

### T03.1 I2C scan finds the ADS1115: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| ADS1115 at 0x48 | ✓ PASS | found ['0x48'] | 0x48 acknowledges |
| I2C lines (SDA, SCL) | ✓ PASS | lines idle high with pull-ups, not bridged; 0x48 answers at 166.666 kHz | both idle high, rise on external pull-ups, not joined |
| No unexpected I2C devices | ✓ PASS | none | only the ADS1115 |

### T03.2 Dark ADC noise, all inputs: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| ADS A0 (ingaas) dark noise | ✓ PASS | mean -220.0, sigma 4.74 counts (n=64) | sigma <= 20 counts |
| ADS A1 (opt101) dark noise | ✓ PASS | mean 55.8, sigma 0.42 counts (n=64) | sigma <= 20 counts |
| ADS A2 (unconnected) | ✓ PASS | recorded only: mean 4598.1, sigma 9.23 | floating input |
| ADS A3 (unconnected) | ✓ PASS | recorded only: mean 2813.5, sigma 3.38 | floating input |

### T03.3 Gain sweep on dark inputs: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| GAIN 2/3 accepted | ✓ PASS | lsb 0.1875 mV | 0.1875 mV |
| GAIN 1 accepted | ✓ PASS | lsb 0.125 mV | 0.125 mV |
| GAIN 2 accepted | ✓ PASS | lsb 0.0625 mV | 0.0625 mV |
| GAIN 4 accepted | ✓ PASS | lsb 0.03125 mV | 0.03125 mV |
| GAIN 8 accepted | ✓ PASS | lsb 0.015625 mV | 0.015625 mV |
| GAIN 16 accepted | ✓ PASS | lsb 0.0078125 mV | 0.0078125 mV |
| ingaas at GAIN 2/3 agrees with GAIN 1 | ✓ PASS | -27.55 mV vs -27.48 mV | within 6.87 mV |
| ingaas at GAIN 1 agrees with GAIN 1 | ✓ PASS | -27.48 mV vs -27.48 mV | within 6.85 mV |
| ingaas at GAIN 2 agrees with GAIN 1 | ✓ PASS | -27.42 mV vs -27.48 mV | within 6.85 mV |
| ingaas at GAIN 4 agrees with GAIN 1 | ✓ PASS | -27.49 mV vs -27.48 mV | within 6.85 mV |
| ingaas at GAIN 8 agrees with GAIN 1 | ✓ PASS | -27.53 mV vs -27.48 mV | within 6.93 mV |
| ingaas at GAIN 16 agrees with GAIN 1 | ✓ PASS | -27.48 mV vs -27.48 mV | within 6.85 mV |
| GAIN 2/3 accepted | ✓ PASS | lsb 0.1875 mV | 0.1875 mV |
| GAIN 1 accepted | ✓ PASS | lsb 0.125 mV | 0.125 mV |
| GAIN 2 accepted | ✓ PASS | lsb 0.0625 mV | 0.0625 mV |
| GAIN 4 accepted | ✓ PASS | lsb 0.03125 mV | 0.03125 mV |
| GAIN 8 accepted | ✓ PASS | lsb 0.015625 mV | 0.015625 mV |
| GAIN 16 accepted | ✓ PASS | lsb 0.0078125 mV | 0.0078125 mV |
| opt101 at GAIN 2/3 agrees with GAIN 1 | ✓ PASS | 7.11 mV vs 6.99 mV | within 5.14 mV |
| opt101 at GAIN 1 agrees with GAIN 1 | ✓ PASS | 6.99 mV vs 6.99 mV | within 5.13 mV |
| opt101 at GAIN 2 agrees with GAIN 1 | ✓ PASS | 6.98 mV vs 6.99 mV | within 5.13 mV |
| opt101 at GAIN 4 agrees with GAIN 1 | ✓ PASS | 6.67 mV vs 6.99 mV | within 5.13 mV |
| opt101 at GAIN 8 agrees with GAIN 1 | ✓ PASS | 7.37 mV vs 6.99 mV | within 5.13 mV |
| opt101 at GAIN 16 agrees with GAIN 1 | ✓ PASS | 7.37 mV vs 6.99 mV | within 5.13 mV |

### T03.4 ADC data rate: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| 8 SPS conversion interval | ✓ PASS | 120.746 ms (nominal 125.000 ms, overhead -4.254 ms) | 106.250-145.250 ms |
| 16 SPS conversion interval | ✓ PASS | 61.188 ms (nominal 62.500 ms, overhead -1.312 ms) | 53.125-73.375 ms |
| 32 SPS conversion interval | ✓ PASS | 31.240 ms (nominal 31.250 ms, overhead -0.010 ms) | 26.562-37.438 ms |
| 64 SPS conversion interval | ✓ PASS | 16.435 ms (nominal 15.625 ms, overhead +0.810 ms) | 13.281-19.469 ms |
| 128 SPS conversion interval | ✓ PASS | 8.865 ms (nominal 7.812 ms, overhead +1.053 ms) | 6.641-10.484 ms |
| 250 SPS conversion interval | ✓ PASS | 5.289 ms (nominal 4.000 ms, overhead +1.289 ms) | 3.400-6.100 ms |
| 475 SPS conversion interval | ✓ PASS | 3.343 ms (nominal 2.105 ms, overhead +1.238 ms) | 1.789-3.921 ms |
| 860 SPS conversion interval | ✓ PASS | 2.542 ms (nominal 1.163 ms, overhead +1.379 ms) | 0.988-2.837 ms |

### T03.5 Long-term dark stability: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| ingaas drift over 60 s | ✓ PASS | +9.2 counts/min (0.028 % FS/min), sigma 5.08 | <= 2 % FS/min |
| opt101 drift over 60 s | ✓ PASS | -0.3 counts/min (0.001 % FS/min), sigma 0.50 | <= 2 % FS/min |

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

### T05.1 Rail gating by CE1 / CE2: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 8 selected, CE1 low | ✓ PASS | opt101 56 (dark 56) | dark |
| Hole 8 selected, CE1 high | ✓ PASS | opt101 242 | light above the detection threshold |
| Hole 8 with CE2 (wrong rail) | ✓ PASS | ERR code=3 needs exactly one selected hole on this rail | refused (code 3) |
| Hole 12 selected, CE2 low | ✓ PASS | ingaas -221 (dark -220) | dark |
| Hole 12 selected, CE2 high | ✓ PASS | ingaas -146 | light above the detection threshold |
| Hole 12 with CE1 (wrong rail) | ✓ PASS | ERR code=3 needs exactly one selected hole on this rail | refused (code 3) |

### T05.2 Per-channel response: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 1 (395) on ingaas | ✕ FAIL | net +64 (signal); unexpected signal: possible stuck-on, swapped or misrouted channel | expect none: signal >= 50 |
| Hole 2 (405) on ingaas | ✕ FAIL | net +63 (signal); unexpected signal: possible stuck-on, swapped or misrouted channel | expect none: signal >= 50 |
| Hole 3 (blue) on ingaas | ✕ FAIL | net +73 (signal); unexpected signal: possible stuck-on, swapped or misrouted channel | expect none: signal >= 50 |
| Hole 4 (green) on ingaas | ✕ FAIL | net +73 (signal); unexpected signal: possible stuck-on, swapped or misrouted channel | expect none: signal >= 50 |
| Hole 7 (red) on ingaas | ✕ FAIL | net +59 (signal); unexpected signal: possible stuck-on, swapped or misrouted channel | expect none: signal >= 50 |
| Hole 9 (940) on ingaas | ✕ FAIL | net +0 (none); expected signal, none seen | expect signal: signal >= 50 |
| Hole 9 (940) on opt101 | ✕ FAIL | net +0 (none); expected signal, none seen | expect signal: signal >= 50 |
| Hole 10 (white) on ingaas | ✕ FAIL | net +74 (signal); unexpected signal: possible stuck-on, swapped or misrouted channel | expect none: signal >= 50 |
| Hole 11 (pink) on ingaas | ✕ FAIL | net +81 (signal); unexpected signal: possible stuck-on, swapped or misrouted channel | expect none: signal >= 50 |
| Hole 5 (yellow) on opt101 | ! WARN | net +23 (weak); weaker than expected | expect signal: signal >= 50 |
| Hole 6 (orange) on opt101 | ! WARN | net +24 (weak); weaker than expected | expect signal: signal >= 50 |
| Hole 7 (red) on opt101 | ! WARN | net +32 (weak); weaker than expected | expect signal: signal >= 50 |
| Hole 8 (850) on ingaas | ! WARN | net +35 (weak); weaker than expected | expect signal: signal >= 50 |
| Hole 16 (1850) on ingaas | ! WARN | net +76 (signal); unexpected signal on a channel expected to show none | expect none: signal >= 50 |
| Hole 16 (1850) on opt101 | ! WARN | net +397 (signal); unexpected signal on a channel expected to show none | expect none: signal >= 50 |
| Hole 1 (395) on opt101 | ✓ PASS | net +78 (signal); signal as expected | expect signal: signal >= 50 |
| Hole 2 (405) on opt101 | ✓ PASS | net +67 (signal); signal as expected | expect signal: signal >= 50 |
| Hole 3 (blue) on opt101 | ✓ PASS | net +51 (signal); signal as expected | expect signal: signal >= 50 |
| Hole 4 (green) on opt101 | ✓ PASS | net +60 (signal); signal as expected | expect signal: signal >= 50 |
| Hole 5 (yellow) on ingaas | ✓ PASS | net +43 (none); no signal, as expected | expect none: signal >= 50 |
| Hole 6 (orange) on ingaas | ✓ PASS | net +48 (none); no signal, as expected | expect none: signal >= 50 |
| Hole 8 (850) on opt101 | ✓ PASS | net +197 (signal); signal as expected | expect signal: signal >= 50 |
| Hole 10 (white) on opt101 | ✓ PASS | net +107 (signal); signal as expected | expect signal: signal >= 50 |
| Hole 11 (pink) on opt101 | ✓ PASS | net +212 (signal); signal as expected | expect signal: signal >= 50 |
| Hole 12 (1450) on ingaas | ✓ PASS | net +75 (signal); signal as expected | expect signal: signal >= 50 |
| Hole 12 (1450) on opt101 | ✓ PASS | net +13 (none); no signal, as expected | expect none: signal >= 50 |
| Hole 13 (1550) on ingaas | ✓ PASS | net +74 (signal); signal as expected | expect signal: signal >= 50 |
| Hole 13 (1550) on opt101 | ✓ PASS | net +11 (none); no signal, as expected | expect none: signal >= 50 |
| Hole 14 (1650) on ingaas | ✓ PASS | net +74 (signal); signal as expected | expect signal: signal >= 50 |
| Hole 14 (1650) on opt101 | ✓ PASS | net +10 (none); no signal, as expected | expect none: signal >= 50 |
| Hole 15 (1760) on ingaas | ✓ PASS | net +70 (signal); signal (weak expected) | expect weak: signal >= 50 |
| Hole 15 (1760) on opt101 | ✓ PASS | net +10 (none); no signal, as expected | expect none: signal >= 50 |

### T05.3 Channel address and isolation: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 1 (395) detector pattern | ✕ FAIL | unexpected response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['opt101'] |
| Hole 2 (405) detector pattern | ✕ FAIL | unexpected response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['opt101'] |
| Hole 3 (blue) detector pattern | ✕ FAIL | unexpected response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['opt101'] |
| Hole 4 (green) detector pattern | ✕ FAIL | unexpected response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['opt101'] |
| Hole 7 (red) detector pattern | ✕ FAIL | unexpected response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['opt101'] |
| Hole 9 (940) detector pattern | ✕ FAIL | no response on ['ingaas', 'opt101']: possible swapped, misrouted or stuck-on channel | expected ['ingaas', 'opt101'] |
| Hole 10 (white) detector pattern | ✕ FAIL | unexpected response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['opt101'] |
| Hole 11 (pink) detector pattern | ✕ FAIL | unexpected response on ['ingaas']: possible swapped, misrouted or stuck-on channel | expected ['opt101'] |
| Hole 16 (1850) detector pattern | ! WARN | unexpected response on ['ingaas', 'opt101']: possible swapped, misrouted or stuck-on channel | expected none |
| Hole 5 (yellow) detector pattern | ✓ PASS | seen by ['opt101'] as expected | expected ['opt101'] |
| Hole 6 (orange) detector pattern | ✓ PASS | seen by ['opt101'] as expected | expected ['opt101'] |
| Hole 8 (850) detector pattern | ✓ PASS | seen by ['ingaas', 'opt101'] as expected | expected ['ingaas', 'opt101'] |
| Hole 12 (1450) detector pattern | ✓ PASS | seen by ['ingaas'] as expected | expected ['ingaas'] |
| Hole 13 (1550) detector pattern | ✓ PASS | seen by ['ingaas'] as expected | expected ['ingaas'] |
| Hole 14 (1650) detector pattern | ✓ PASS | seen by ['ingaas'] as expected | expected ['ingaas'] |
| Hole 15 (1760) detector pattern | ✓ PASS | seen by ['ingaas'] as expected | expected ['ingaas'] |
| Signatures unique | ✓ PASS | no two channels look the same | cosine < 0.98 or amplitude differs by more than 1 % |

### T05.4 Off-state return after each MEAS: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 1 ingaas back to dark | ✓ PASS | -219.2 after OFF vs dark -221 | within 5 sigma (16.8 counts) |
| Hole 1 opt101 back to dark | ✓ PASS | 55.8 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 2 ingaas back to dark | ✓ PASS | -220.8 after OFF vs dark -220 | within 5 sigma (16.8 counts) |
| Hole 2 opt101 back to dark | ✓ PASS | 55.8 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 3 ingaas back to dark | ✓ PASS | -220.2 after OFF vs dark -221 | within 5 sigma (16.8 counts) |
| Hole 3 opt101 back to dark | ✓ PASS | 55.5 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 4 ingaas back to dark | ✓ PASS | -220.5 after OFF vs dark -221 | within 5 sigma (16.8 counts) |
| Hole 4 opt101 back to dark | ✓ PASS | 56.0 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 5 ingaas back to dark | ✓ PASS | -220.5 after OFF vs dark -220 | within 5 sigma (16.8 counts) |
| Hole 5 opt101 back to dark | ✓ PASS | 55.8 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 6 ingaas back to dark | ✓ PASS | -221.8 after OFF vs dark -222 | within 5 sigma (16.8 counts) |
| Hole 6 opt101 back to dark | ✓ PASS | 55.8 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 7 ingaas back to dark | ✓ PASS | -220.0 after OFF vs dark -221 | within 5 sigma (16.8 counts) |
| Hole 7 opt101 back to dark | ✓ PASS | 56.2 after OFF vs dark 55 | within 5 sigma (3.5 counts) |
| Hole 8 ingaas back to dark | ✓ PASS | -220.0 after OFF vs dark -221 | within 5 sigma (16.8 counts) |
| Hole 8 opt101 back to dark | ✓ PASS | 55.8 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 9 ingaas back to dark | ✓ PASS | -221.2 after OFF vs dark -220 | within 5 sigma (16.8 counts) |
| Hole 9 opt101 back to dark | ✓ PASS | 56.0 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 10 ingaas back to dark | ✓ PASS | -221.2 after OFF vs dark -220 | within 5 sigma (16.8 counts) |
| Hole 10 opt101 back to dark | ✓ PASS | 56.0 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 11 ingaas back to dark | ✓ PASS | -220.8 after OFF vs dark -221 | within 5 sigma (16.8 counts) |
| Hole 11 opt101 back to dark | ✓ PASS | 56.0 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 12 ingaas back to dark | ✓ PASS | -214.5 after OFF vs dark -222 | within 5 sigma (16.8 counts) |
| Hole 12 opt101 back to dark | ✓ PASS | 56.0 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 13 ingaas back to dark | ✓ PASS | -220.2 after OFF vs dark -221 | within 5 sigma (16.8 counts) |
| Hole 13 opt101 back to dark | ✓ PASS | 56.0 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 14 ingaas back to dark | ✓ PASS | -220.5 after OFF vs dark -220 | within 5 sigma (16.8 counts) |
| Hole 14 opt101 back to dark | ✓ PASS | 55.5 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 15 ingaas back to dark | ✓ PASS | -220.8 after OFF vs dark -220 | within 5 sigma (16.8 counts) |
| Hole 15 opt101 back to dark | ✓ PASS | 55.5 after OFF vs dark 56 | within 5 sigma (3.5 counts) |
| Hole 16 ingaas back to dark | ✓ PASS | -221.0 after OFF vs dark -221 | within 5 sigma (16.8 counts) |
| Hole 16 opt101 back to dark | ✓ PASS | 56.0 after OFF vs dark 56 | within 5 sigma (3.5 counts) |

### T05.5 Repeatability (interleaved MEAS): PASS

not judged (net < 1000 counts or detector unusable): 1/opt101, 2/opt101, 3/opt101, 4/opt101, 5/opt101, 6/opt101, 7/opt101, 8/opt101, 8/ingaas, 9/opt101, 9/ingaas, 10/opt101, 11/opt101, 12/ingaas, 13/ingaas, 14/ingaas, 15/ingaas

## T06

### T06.1 OPT101: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| opt101 dark offset | ✓ PASS | 55.8 counts | 0 to 800 counts |
| Responds to hole 1 (395) | ✓ PASS | net +78 | no zeros where light is expected |
| Responds to hole 2 (405) | ✓ PASS | net +67 | no zeros where light is expected |
| Responds to hole 3 (blue) | ✓ PASS | net +51 | no zeros where light is expected |
| Responds to hole 4 (green) | ✓ PASS | net +60 | no zeros where light is expected |
| Responds to hole 5 (yellow) | ✓ PASS | net +23 | no zeros where light is expected |
| Responds to hole 6 (orange) | ✓ PASS | net +24 | no zeros where light is expected |
| Responds to hole 7 (red) | ✓ PASS | net +32 | no zeros where light is expected |
| Responds to hole 10 (white) | ✓ PASS | net +107 | no zeros where light is expected |
| Responds to hole 11 (pink) | ✓ PASS | net +212 | no zeros where light is expected |
| Not saturated | ✓ PASS | peak 453 | < 29000 counts |

### T06.2 InGaAs TIA: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| ingaas dark offset | ✕ FAIL | -220.0 counts; check the TIA offset | -100 to 2000 counts |
| Dark signal steady | ✓ PASS | dark mean -220, sigma 4.7 | sigma <= 100 and mean >= -1500 |
| Polarity gate (hole 8) | ✓ PASS | net +35 | net >= -5 sigma |
| Hole 9 InGaAs polarity | ✓ PASS | net +0 | net not negative |
| Hole 12 InGaAs polarity | ✓ PASS | net +75 | net not negative |
| Hole 13 InGaAs polarity | ✓ PASS | net +74 | net not negative |
| Hole 14 InGaAs polarity | ✓ PASS | net +74 | net not negative |
| InGaAs not saturated | ✓ PASS | no hole saturates | < 27000 counts |

### T06.3 Cross-calibration on the shared holes: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 8 seen by both detectors | ✕ FAIL | one detector does not respond | both above the detection threshold |
| Hole 9 seen by both detectors | ✕ FAIL | one detector does not respond | both above the detection threshold |

## T07

### T07.1 Step response and settling time: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 3 (opt101) step response | ✓ PASS | t99 = 15.75 ms, tau 3.42 ms | time to 99 % recorded |
| Hole 8 (opt101) step response | ✓ PASS | t99 = 5.30 ms, tau 1.15 ms | time to 99 % recorded |
| Hole 13 (ingaas) step response | ✓ PASS | t99 = 8.01 ms, tau 1.74 ms | time to 99 % recorded |

### T07.2 Recommended settle time: WARN

| Check | Status | Result | Criterion |
|---|---|---|---|
| Configured settle_ms is long enough | ! WARN | recommended 24 ms (max 15.75 ms x 1.5), configured 8 ms: raise firmware.limits.settle_ms to 24 | recommended <= 8 ms |

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
| Sweep duration | ✓ PASS | 833 ms (host 834 ms) | <= 2.5 s |

### T08.2 Repeated sweeps: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| ingaas dark stable between sweeps | ✓ PASS | per-sweep dark means span 0.88 counts | <= 5.93 counts |
| opt101 dark stable between sweeps | ✓ PASS | per-sweep dark means span 0.25 counts | <= 1.25 counts |

### T08.3 Sweep agrees with MEAS: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 1 opt101 sweep vs MEAS | ✓ PASS | sweep 77 vs MEAS 78 (1.3 %) | within 8 counts (max of 10 %, 5 sigma) |
| Hole 2 opt101 sweep vs MEAS | ✓ PASS | sweep 67 vs MEAS 67 (0.0 %) | within 7 counts (max of 10 %, 5 sigma) |
| Hole 3 opt101 sweep vs MEAS | ✓ PASS | sweep 53 vs MEAS 51 (3.1 %) | within 5 counts (max of 10 %, 5 sigma) |
| Hole 4 opt101 sweep vs MEAS | ✓ PASS | sweep 61 vs MEAS 60 (1.3 %) | within 6 counts (max of 10 %, 5 sigma) |
| Hole 8 opt101 sweep vs MEAS | ✓ PASS | sweep 200 vs MEAS 197 (1.3 %) | within 20 counts (max of 10 %, 5 sigma) |
| Hole 10 opt101 sweep vs MEAS | ✓ PASS | sweep 112 vs MEAS 107 (4.7 %) | within 11 counts (max of 10 %, 5 sigma) |
| Hole 11 opt101 sweep vs MEAS | ✓ PASS | sweep 213 vs MEAS 212 (0.7 %) | within 21 counts (max of 10 %, 5 sigma) |
| Hole 12 ingaas sweep vs MEAS | ✓ PASS | sweep 64 vs MEAS 75 (14.9 %) | within 22 counts (max of 10 %, 5 sigma) |
| Hole 13 ingaas sweep vs MEAS | ✓ PASS | sweep 66 vs MEAS 74 (10.8 %) | within 22 counts (max of 10 %, 5 sigma) |
| Hole 14 ingaas sweep vs MEAS | ✓ PASS | sweep 73 vs MEAS 74 (1.1 %) | within 22 counts (max of 10 %, 5 sigma) |
| Hole 15 ingaas sweep vs MEAS | ✓ PASS | sweep 79 vs MEAS 70 (13.1 %) | within 22 counts (max of 10 %, 5 sigma) |

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
| Detectors dark after RESET | ✓ PASS | ingaas -222, opt101 56 | dark +- k sigma |
| STATUS safe after a port reopen | ✓ PASS | ch=0 ce1=0 ce2=0 mask=0x0000 armed=0 | ch=0 ce1=0 ce2=0 mask=0 armed=0, motors idle |
| Detectors dark after a port reopen | ✓ PASS | ingaas -220, opt101 56 | dark +- k sigma |

### T10.2 On-time watchdog: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| CH 3 ON 60000 clamped to RAIL A limit | ✓ PASS | until_ms=2000 clamped=1 | until_ms=2000 clamped=1 |
| Hole 3 lit before the watchdog | ✓ PASS | light seen | light seen |
| Light gone after the watchdog limit | ✓ PASS | dark after 313 ms | <= 366 ms: limit 300 + tolerance 50 + detector settling 15.7 ms |
| '# WDT' received | ✓ PASS | # WDT ch=3 on_ms=300 off | '# WDT' with on_ms <= 350 |
| CH 13 ON 60000 clamped to RAIL B limit | ✓ PASS | until_ms=5000 clamped=1 | until_ms=5000 clamped=1 |
| Hole 13 lit before the watchdog | ✓ PASS | light seen | light seen |
| Light gone after the watchdog limit | ✓ PASS | dark after 315 ms | <= 358 ms: limit 300 + tolerance 50 + detector settling 8.0 ms |
| '# WDT' received | ✓ PASS | # WDT ch=13 on_ms=300 off | '# WDT' with on_ms <= 350 |

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
