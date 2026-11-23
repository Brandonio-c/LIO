# LIO test report: 20261103-183129_host

**Verdict: NOT FUNCTIONAL**: failure in a critical module: T03.1

- Target: `/dev/cu.usbserial-1120`
- Started 2026-11-03T18:31:29-05:00, finished 2026-11-03T18:31:32-05:00
- Sample: `none-empty-chamber`, operator: unknown
- Firmware 2.0.0 (proto 1, build 2026-11-03)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 9afb79318e92 (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git 14bc7163f0
- Counts: FAIL 1, SKIP 4
- LED duty budget: 0.0 s of cool-down waits, 0 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T03.1 | I2C scan finds the ADS1115 | ✕ FAIL |  |
| T03.2 | Dark ADC noise, all inputs | - SKIP | the ADS1115 is not responding (see T03.1) |
| T03.3 | Gain sweep on dark inputs | - SKIP | the ADS1115 is not responding (see T03.1) |
| T03.4 | ADC data rate | - SKIP | the ADS1115 is not responding (see T03.1) |
| T03.5 | Long-term dark stability | - SKIP | the ADS1115 is not responding (see T03.1) |

## T03

### T03.1 I2C scan finds the ADS1115: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| ADS1115 at 0x48 | ✕ FAIL | found nothing; first check that power bank A is on: it alone powers the +5 V bus (ADS1115, LEDs, shift registers), and USB banks switch off when the load is small (measure about 5 V between +5 V and GND); then the ADS1115 wiring: SDA -> A4, SCL -> A5, ADDR -> GND (0x48), VDD 5 V and GND; both lines should idle near 5 V | 0x48 acknowledges |
| No unexpected I2C devices | ✓ PASS | none | only the ADS1115 |

### T03.2 Dark ADC noise, all inputs: SKIP

the ADS1115 is not responding (see T03.1)

### T03.3 Gain sweep on dark inputs: SKIP

the ADS1115 is not responding (see T03.1)

### T03.4 ADC data rate: SKIP

the ADS1115 is not responding (see T03.1)

### T03.5 Long-term dark stability: SKIP

the ADS1115 is not responding (see T03.1)
