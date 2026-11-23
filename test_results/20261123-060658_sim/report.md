# LIO test report: 20261123-060658_sim

**Verdict: NOT FUNCTIONAL**: failure in a critical module: T10.2

- Target: `sim`
- Started 2026-11-23T06:06:58-05:00, finished 2026-11-23T06:06:58-05:00
- Sample: `none-empty-chamber`, operator: unknown
- Firmware 2.5.2 (proto 1, build 2026-11-16)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 e29964e36d34 (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git 130dd7707a (dirty)
- Counts: FAIL 1
- LED duty budget: 0.0 s of cool-down waits, 0 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T10.2 | On-time watchdog | ✕ FAIL |  |

## T10

### T10.2 On-time watchdog: FAIL

| Check | Status | Result | Criterion |
|---|---|---|---|
| CH 3 ON 60000 clamped to RAIL A limit | ✕ FAIL | until_ms=90 clamped=1 | until_ms=2000 clamped=1 |
| CH 13 ON 60000 clamped to RAIL B limit | ✕ FAIL | until_ms=90 clamped=1 | until_ms=5000 clamped=1 |
| Hole 3 lit before the watchdog | ✓ PASS | light seen | light seen |
| Light gone after the watchdog limit | ✓ PASS | dark after 311 ms | <= 352 ms: limit 300 + tolerance 50 + detector settling 2.0 ms |
| '# WDT' received | ✓ PASS | # WDT ch=3 on_ms=300 off | '# WDT' with on_ms <= 350 |
| Hole 13 lit before the watchdog | ✓ PASS | light seen | light seen |
| Light gone after the watchdog limit | ✓ PASS | dark after 316 ms | <= 351 ms: limit 300 + tolerance 50 + detector settling 0.7 ms |
| '# WDT' received | ✓ PASS | # WDT ch=13 on_ms=300 off | '# WDT' with on_ms <= 350 |
