// ===== Motors: 2x 28BYJ-48 via ULN2003, non-blocking half-step sequencer =====
// Motor 1 = left (D2-D5), motor 2 = right (D6-D9). +steps is the direction the
// legacy AccelStepper sketch used for "U" (up). No limit switches exist:
// every move is bounded and the coils are released when it ends.
#pragma once
#include <Arduino.h>
#include "protocol.h"

void motors_init();          // all IN pins low (coils released)
void motors_tick();          // advance any move whose next step is due
bool motors_moving();
void motors_stop_all();      // immediate stop + release, both motors

const __FlashStringHelper *motor_state(uint8_t m);  // "idle" | "run"
long motor_pos(uint8_t m);
uint16_t jog_va();
uint16_t jog_vs();
uint16_t jog_acc();

void cmd_motor(const Command &c);  // MOTOR ARM | <1|2> STEP | <1|2|ALL> RELEASE | STOP
// Legacy lio_control.py commands: U D LU LD RU RD S VA<n> VS<n> ACC<n> POSL0 POSR0 ?
// Returns false if c is not a legacy command.
bool cmd_legacy(const Command &c);
