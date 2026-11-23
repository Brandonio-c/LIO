# LIO test report: 20261116-052003_host

**Verdict: FUNCTIONAL**: no failures or warnings

- Target: `/dev/cu.usbmodem101`
- Started 2026-11-16T05:20:03-05:00, finished 2026-11-16T05:24:12-05:00
- Sample: `none-empty-chamber`, operator: claude-code, notes: full chamber travel (tracked limits) and detectors while moving; fw 2.4.0; 7 rpm; top margin 4096
- Firmware 2.4.0 (proto 1, build 2026-11-16)
- Config `test_results/_session/lio_hw_nowake.yaml` sha256 f13b7380bdf4 (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git d41f99e4ed (dirty)
- Counts: SKIP 1
- LED duty budget: 0.0 s of cool-down waits, 0 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T09.6 | Full travel, both motors in lockstep | - SKIP | stopped by the operator |

## T09

### T09.6 Full travel, both motors in lockstep: SKIP

stopped by the operator
