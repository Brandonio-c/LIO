# LIO test report: 20261120-003105_host

**Verdict: NOT FUNCTIONAL**: failure in a critical module: T02.1, T02.2, T02.3, T02.4, T02.5, T02.6, T03.1, T03.2, T03.3, T03.4, T03.5, T04.1, T04.2, T04.3, T10.1, T10.2, T10.3, T10.4, T10.5; failures not tied to a channel: T01.1, T01.2, T01.3, T05.1, T05.2, T05.3, T05.4, T05.5, T06.1, T06.2, T06.3, T07.1, T07.2, T07.3, T08.1, T08.2, T08.3, T08.4, T09.1, T09.2, T09.3, T09.4, T09.6, T09.7, T11.1, T13.1

- Target: `/dev/cu.usbmodem101`
- Started 2026-11-20T00:31:05-05:00, finished 2026-11-20T00:31:05-05:00
- Sample: `empty`, operator: unknown
- Firmware ? (proto ?, build ?)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 ed3b4ba8e185 (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git 226efcf6de (dirty)
- Counts: ERROR 45
- LED duty budget: 0.0 s of cool-down waits, 0 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T01.1 | Python and dependency versions | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T01.2 | Serial port discovery | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T01.3 | Configuration loads and is self-consistent | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T02.1 | Port open and boot banner | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T02.2 | PING round-trip latency | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T02.3 | INFO fields, versions and safety limits | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T02.4 | Robustness to bad input | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T02.5 | Sequence numbers and interleaved events | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T02.6 | RESET restores the boot state | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T03.1 | I2C scan finds the ADS1115 | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T03.2 | Dark ADC noise, all inputs | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T03.3 | Gain sweep on dark inputs | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T03.4 | ADC data rate | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T03.5 | Long-term dark stability | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T04.1 | Shift-register patterns with CE low | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T04.2 | Shift-register loopback (optional jumper) | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T04.3 | Optical address verification | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T05.1 | Rail gating by CE1 / CE2 | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T05.2 | Per-channel response | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T05.3 | Channel address and isolation | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T05.4 | Off-state return after each MEAS | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T05.5 | Repeatability (interleaved MEAS) | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T06.1 | OPT101 | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T06.2 | InGaAs TIA | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T06.3 | Cross-calibration on the shared holes | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T07.1 | Step response and settling time | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T07.2 | Recommended settle time | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T07.3 | MEAS timing | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T08.1 | SWEEP completes with a valid schema | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T08.2 | Repeated sweeps | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T08.3 | Sweep agrees with MEAS | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T08.4 | CSV output format | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T09.1 | Motion arming | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T09.2 | Each motor moves both ways | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T09.3 | MOTOR STOP latency | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T09.4 | Detector noise while a motor moves | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T09.6 | Full travel, both motors in lockstep | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T09.7 | Detectors while the chamber moves | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T10.1 | Power-up dark state | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T10.2 | On-time watchdog | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T10.3 | Comms-loss failsafe | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T10.4 | Single-channel invariant | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T10.5 | Motion disarmed after comms loss | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T11.1 | Comparison with the baseline | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |
| T13.1 | Diagnostic height sweep | ✕ ERROR | TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured |

## T01

### T01.1 Python and dependency versions: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T01.2 Serial port discovery: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T01.3 Configuration loads and is self-consistent: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

## T02

### T02.1 Port open and boot banner: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T02.2 PING round-trip latency: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T02.3 INFO fields, versions and safety limits: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T02.4 Robustness to bad input: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T02.5 Sequence numbers and interleaved events: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T02.6 RESET restores the boot state: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

## T03

### T03.1 I2C scan finds the ADS1115: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T03.2 Dark ADC noise, all inputs: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T03.3 Gain sweep on dark inputs: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T03.4 ADC data rate: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T03.5 Long-term dark stability: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

## T04

### T04.1 Shift-register patterns with CE low: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T04.2 Shift-register loopback (optional jumper): ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T04.3 Optical address verification: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

## T05

### T05.1 Rail gating by CE1 / CE2: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T05.2 Per-channel response: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T05.3 Channel address and isolation: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T05.4 Off-state return after each MEAS: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T05.5 Repeatability (interleaved MEAS): ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

## T06

### T06.1 OPT101: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T06.2 InGaAs TIA: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T06.3 Cross-calibration on the shared holes: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

## T07

### T07.1 Step response and settling time: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T07.2 Recommended settle time: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T07.3 MEAS timing: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

## T08

### T08.1 SWEEP completes with a valid schema: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T08.2 Repeated sweeps: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T08.3 Sweep agrees with MEAS: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T08.4 CSV output format: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

## T09

### T09.1 Motion arming: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T09.2 Each motor moves both ways: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T09.3 MOTOR STOP latency: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T09.4 Detector noise while a motor moves: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T09.6 Full travel, both motors in lockstep: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T09.7 Detectors while the chamber moves: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

## T10

### T10.1 Power-up dark state: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T10.2 On-time watchdog: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T10.3 Comms-loss failsafe: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T10.4 Single-channel invariant: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

### T10.5 Motion disarmed after comms loss: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

## T11

### T11.1 Comparison with the baseline: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured

## T13

### T13.1 Diagnostic height sweep: ERROR

TransportError: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured; could not restore the safe state afterwards: write failed on /dev/cu.usbmodem101: write failed: [Errno 6] Device not configured
