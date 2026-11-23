# LIO test report: 20261116-124222_sim

**Verdict: FUNCTIONAL**: no failures or warnings

- Target: `sim`
- Started 2026-11-16T12:42:22-05:00, finished 2026-11-16T12:42:23-05:00
- Sample: `none-empty-chamber`, operator: unknown
- Firmware 2.4.0 (proto 1, build 2026-11-03)
- Config `/Users/coleloughbc/Documents/VSCode-Local/LIO/software/config/lio_hw.yaml` sha256 c3d525e8d31a (thresholds provisional)
- Host: macOS-27.0.1-x86_64-i386-64bit, Python 3.12.11, lio 0.2.0, git d6cf0b7dff (dirty)
- Counts: PASS 4, SKIP 2
- LED duty budget: 0.0 s of cool-down waits, 0 over-budget on-time(s)

## Summary

| Test | Name | Status | Note |
|---|---|---|---|
| T09.1 | Motion arming | ✓ PASS |  |
| T09.2 | Each motor moves both ways | ✓ PASS |  |
| T09.3 | MOTOR STOP latency | ✓ PASS |  |
| T09.4 | Detector noise while a motor moves | ✓ PASS |  |
| T09.6 | Full travel, both motors in lockstep | - SKIP | travel not measured: mark the top and bottom (Motors tab, or lio stage set-top / mark-bottom), or set thresholds.motion.travel.range_steps |
| T09.7 | Detectors while the chamber moves | - SKIP | travel not measured: mark the top and bottom (Motors tab, or lio stage set-top / mark-bottom), or set thresholds.motion.travel.range_steps |

## T09

### T09.1 Motion arming: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| MOTOR STEP without ARM is refused | ✓ PASS | @4 ERR MOTOR code=3 msg=not armed | ERR code=3 (not armed) |
| ARM with the wrong token is refused | ✓ PASS | @6 ERR MOTOR code=3 msg=wrong token | ERR code=3 |
| ARM with the INFO token | ✓ PASS | armed=1 armed_ms=59996 | armed=1, armed_ms <= 60000 |
| Arming expires after 60 s | ✓ PASS | armed=0 failsafe_trips=0 | armed=0 without a failsafe |
| MOTOR STEP after expiry is refused | ✓ PASS | @42 ERR MOTOR code=3 msg=not armed | ERR code=3 (not armed) |

### T09.2 Each motor moves both ways: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Motor 1 +64 half-steps completes | ✓ PASS | # MOTOR m=1 steps=64 pos=64 done | '# MOTOR m=1 steps=64 ... done' |
| Operator saw motor 1 (LEFT) move up | ✓ PASS | confirmed | +steps = up (legacy U direction) |
| Motor 1 -64 half-steps completes | ✓ PASS | # MOTOR m=1 steps=64 pos=0 done | '# MOTOR m=1 steps=64 ... done' |
| Operator saw motor 1 (LEFT) move back down | ✓ PASS | confirmed | returned |
| Motor 1 idle, coils released, back at start | ✓ PASS | motor1=idle pos1=0 | idle, pos1=0 |
| Motor 2 +64 half-steps completes | ✓ PASS | # MOTOR m=2 steps=64 pos=64 done | '# MOTOR m=2 steps=64 ... done' |
| Operator saw motor 2 (RIGHT) move up | ✓ PASS | confirmed | +steps = up (legacy U direction) |
| Motor 2 -64 half-steps completes | ✓ PASS | # MOTOR m=2 steps=64 pos=0 done | '# MOTOR m=2 steps=64 ... done' |
| Operator saw motor 2 (RIGHT) move back down | ✓ PASS | confirmed | returned |
| Motor 2 idle, coils released, back at start | ✓ PASS | motor2=idle pos2=0 | idle, pos2=0 |

### T09.3 MOTOR STOP latency: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| MOTOR STOP answered | ✓ PASS | 4.9 ms | < 50 ms |
| Motor stopped and stays stopped | ✓ PASS | moved 32 of 2048 half-steps; motor1=idle | idle, position frozen, move cut short |
| Motor 1 returned to the start | ✓ PASS | # MOTOR m=1 steps=32 pos=0 done | pos1=0 |

### T09.4 Detector noise while a motor moves: PASS

| Check | Status | Result | Criterion |
|---|---|---|---|
| Streams taken while the motor was moving | ✓ PASS | motor still running after both streams | motor1=run |
| ingaas noise during motion | ✓ PASS | sigma 4.34 moving vs 3.46 at rest (x1.25) | ratio <= 3 |
| opt101 noise during motion | ✓ PASS | sigma 3.04 moving vs 2.98 at rest (x1.02) | ratio <= 3 |

### T09.6 Full travel, both motors in lockstep: SKIP

travel not measured: mark the top and bottom (Motors tab, or lio stage set-top / mark-bottom), or set thresholds.motion.travel.range_steps

### T09.7 Detectors while the chamber moves: SKIP

travel not measured: mark the top and bottom (Motors tab, or lio stage set-top / mark-bottom), or set thresholds.motion.travel.range_steps
