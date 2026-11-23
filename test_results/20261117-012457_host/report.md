# LIO test report: 20261117-012457_host

**Verdict: DEGRADED**: failing channels: 8, 9

- Target: `/dev/cu.usbmodem1101`
- Started 2026-11-17T01:24:57-05:00, finished 2026-11-17T01:25:04-05:00
- Sample: `none-empty-chamber`, operator: unknown
- Firmware 2.5.1 (proto 1, build 2026-11-16)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 795e6bf0787d (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.4, lio 0.2.0, git 33dbb29085 (dirty)
- Counts: PASS 2, FAIL 1
- LED duty budget: 0.0 s of cool-down waits, 0 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T06.1 | OPT101 | ✓ PASS |  |
| T06.2 | InGaAs TIA | ✓ PASS |  |
| T06.3 | Cross-calibration on the shared holes | ✕ FAIL |  |

## T06

### T06.1 OPT101: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| opt101 dark offset | ✓ PASS | 56.9 counts | 0 to 800 counts |
| Responds to hole 1 (395) | ✓ PASS | net +76 | no zeros where light is expected |
| Responds to hole 2 (405) | ✓ PASS | net +59 | no zeros where light is expected |
| Responds to hole 3 (blue) | ✓ PASS | net +41 | no zeros where light is expected |
| Responds to hole 4 (green) | ✓ PASS | net +43 | no zeros where light is expected |
| Responds to hole 5 (yellow) | ✓ PASS | net +20 | no zeros where light is expected |
| Responds to hole 6 (orange) | ✓ PASS | net +21 | no zeros where light is expected |
| Responds to hole 7 (red) | ✓ PASS | net +27 | no zeros where light is expected |
| Responds to hole 10 (white) | ✓ PASS | net +68 | no zeros where light is expected |
| Responds to hole 11 (pink) | ✓ PASS | net +136 | no zeros where light is expected |
| Not saturated | ✓ PASS | peak 359 | < 29000 counts |

### T06.2 InGaAs TIA: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Dark signal steady | ✓ PASS | dark mean -168, sigma 6.9 | sigma <= 100 and mean >= -1500 |
| ingaas dark offset | ✓ PASS | -168.0 counts | -400 to 2000 counts |
| Polarity gate (hole 8) | ✓ PASS | net +16 | net >= -5 sigma |
| Hole 9 InGaAs polarity | ✓ PASS | net -1 | net not negative |
| Hole 12 InGaAs polarity | ✓ PASS | net +11 | net not negative |
| Hole 13 InGaAs polarity | ✓ PASS | net +17 | net not negative |
| Hole 14 InGaAs polarity | ✓ PASS | net +108 | net not negative |
| InGaAs not saturated | ✓ PASS | no hole saturates | < 27000 counts |

### T06.3 Cross-calibration on the shared holes: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| Hole 8 seen by both detectors | ✕ FAIL | one detector does not respond | both above the detection threshold |
| Hole 9 seen by both detectors | ✕ FAIL | one detector does not respond | both above the detection threshold |
