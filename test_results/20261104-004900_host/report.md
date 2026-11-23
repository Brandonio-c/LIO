# LIO test report: 20261104-004900_host

**Verdict: FUNCTIONAL**: no failures or warnings

- Target: `/dev/cu.usbserial-1120`
- Started 2026-11-04T00:49:00-05:00, finished 2026-11-04T00:49:04-05:00
- Sample: `none-empty-chamber`, operator: unknown
- Firmware 2.2.0 (proto 1, build 2026-11-04)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 446422b3dbd2 (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git ca3168b862 (dirty)
- Counts: PASS 2
- LED duty budget: 0.0 s of cool-down waits, 0 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T03.1 | I2C scan finds the ADS1115 | ✓ PASS |  |
| T03.4 | ADC data rate | ✓ PASS |  |

## T03

### T03.1 I2C scan finds the ADS1115: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| ADS1115 at 0x48 | ✓ PASS | found ['0x48'] | 0x48 acknowledges |
| I2C lines (SDA, SCL) | ✓ PASS | lines idle high with pull-ups, not bridged; 0x48 answers at 166.666 kHz | both idle high, rise on external pull-ups, not joined |
| No unexpected I2C devices | ✓ PASS | none | only the ADS1115 |

### T03.4 ADC data rate: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| 8 SPS conversion interval | ✓ PASS | 121.016 ms (nominal 125.000 ms, overhead -3.984 ms) | 106.250-145.250 ms |
| 16 SPS conversion interval | ✓ PASS | 61.496 ms (nominal 62.500 ms, overhead -1.004 ms) | 53.125-73.375 ms |
| 32 SPS conversion interval | ✓ PASS | 31.564 ms (nominal 31.250 ms, overhead +0.314 ms) | 26.562-37.438 ms |
| 64 SPS conversion interval | ✓ PASS | 16.800 ms (nominal 15.625 ms, overhead +1.175 ms) | 13.281-19.469 ms |
| 128 SPS conversion interval | ✓ PASS | 9.204 ms (nominal 7.812 ms, overhead +1.392 ms) | 6.641-10.484 ms |
| 250 SPS conversion interval | ✓ PASS | 5.652 ms (nominal 4.000 ms, overhead +1.652 ms) | 3.400-6.100 ms |
| 475 SPS conversion interval | ✓ PASS | 3.492 ms (nominal 2.105 ms, overhead +1.387 ms) | 1.789-3.921 ms |
| 860 SPS conversion interval | ✓ PASS | 2.588 ms (nominal 1.163 ms, overhead +1.425 ms) | 0.988-2.837 ms |
