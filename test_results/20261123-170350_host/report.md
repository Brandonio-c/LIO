# LIO test report: 20261123-170350_host

**Verdict: NOT FUNCTIONAL**: failures not tied to a channel: T13.1

- Target: `/dev/cu.usbmodem101`
- Started 2026-11-23T17:03:50-05:00, finished 2026-11-23T17:29:22-05:00
- Sample: `empty`, operator: owner (answers via Claude session 2026-11-23), notes: T13.1 rerun after closing-check fix f78c6b6; owner answers: chamber empty+clear, lid closed, earth bond connected
- Firmware 2.5.2 (proto 1, build 2026-11-17)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 493718927528 (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git f78c6b6877 (dirty)
- Counts: ERROR 1
- LED duty budget: 524.5 s of cool-down waits, 0 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T13.1 | Diagnostic height sweep | ✕ ERROR | OwnershipError: CE on refused: no single selected hole to reserve duty against |

## T13

### T13.1 Diagnostic height sweep: ERROR

OwnershipError: CE on refused: no single selected hole to reserve duty against
