# LIO test report: 20261123-060619_sim

**Verdict: NOT FUNCTIONAL**: failure in a critical module: T02.4, T10.2

- Target: `sim`
- Started 2026-11-23T06:06:19-05:00, finished 2026-11-23T06:06:20-05:00
- Sample: `none-empty-chamber`, operator: unknown
- Firmware 2.5.2 (proto 1, build 2026-11-16)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 e29964e36d34 (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git 130dd7707a (dirty)
- Counts: ERROR 2
- LED duty budget: 0.0 s of cool-down waits, 0 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T02.4 | Robustness to bad input | ✕ ERROR | OwnershipError: refusing ungated light-capable command 'MEAS 99': use typed ch_on/ce/meas/sweep/sr_raw (or shell guarded helpers) |
| T10.2 | On-time watchdog | ✕ ERROR | ProtocolError: missing field 'clamped' |

## T02

### T02.4 Robustness to bad input: ERROR

OwnershipError: refusing ungated light-capable command 'MEAS 99': use typed ch_on/ce/meas/sweep/sr_raw (or shell guarded helpers)

| Check | Status | Result | Criterion |
|---|---|---|---|
| Unknown command | ✓ PASS | @3 ERR FROBNICATE code=1 msg=unknown command | ERR code=1 |

## T10

### T10.2 On-time watchdog: ERROR

ProtocolError: missing field 'clamped'
