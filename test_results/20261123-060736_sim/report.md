# LIO test report: 20261123-060736_sim

**Verdict: NOT FUNCTIONAL**: failure in a critical module: T10.2

- Target: `sim`
- Started 2026-11-23T06:07:36-05:00, finished 2026-11-23T06:07:44-05:00
- Sample: `none-empty-chamber`, operator: unknown
- Firmware 2.5.2 (proto 1, build 2026-11-16)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 e29964e36d34 (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git 130dd7707a (dirty)
- Counts: PASS 1, FAIL 1
- LED duty budget: 176.4 s of cool-down waits, 1 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T10.2 | On-time watchdog | ✕ FAIL |  |
| T02.4 | Robustness to bad input | ✓ PASS |  |

## T10

### T10.2 On-time watchdog: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| '# WDT' received | ✕ FAIL | no '# WDT' event | '# WDT' with on_ms <= 350 |
| '# WDT' received | ✕ FAIL | no '# WDT' event | '# WDT' with on_ms <= 350 |
| Light gone after the watchdog limit | ! WARN | never dark | <= 352 ms: limit 2000 + tolerance 50 + detector settling 2.0 ms |
| Light gone after the watchdog limit | ! WARN | never dark | <= 351 ms: limit 5000 + tolerance 50 + detector settling 0.7 ms |
| CH 3 ON 60000 clamped to RAIL A limit | ✓ PASS | until_ms=2000 clamped=1 | until_ms=2000 clamped=1 |
| Hole 3 lit before the watchdog | ✓ PASS | light seen | light seen |
| CH 13 ON 60000 clamped to RAIL B limit | ✓ PASS | until_ms=5000 clamped=1 | until_ms=5000 clamped=1 |
| Hole 13 lit before the watchdog | ✓ PASS | light seen | light seen |

## T02

### T02.4 Robustness to bad input: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Unknown command | ✓ PASS | @294 ERR FROBNICATE code=1 msg=unknown command | ERR code=1 |
| Bad argument | ✓ PASS | @295 ERR MEAS code=2 msg=usage: MEAS <1-16> [settle_ms] [n] | ERR code=2 |
| Missing argument | ✓ PASS | @296 ERR CH code=2 msg=usage: CH <1-16> ON [ms] | ERR code=2 |
| Line over 64 characters | ✓ PASS | ERR ? code=6 msg=line too long | ERR code=6 |
| Garbage bytes, then PING | ✓ PASS | PING OK | PING still answered |
