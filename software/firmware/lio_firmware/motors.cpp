#include "motors.h"
#include "config.h"
#include "optics.h"
#include "safety.h"

// Half-step coil patterns, bit0 = IN1 .. bit3 = IN4. Identical to AccelStepper
// HALF4WIRE with pins (IN1, IN3, IN2, IN4) as used by the legacy sketch, so
// increasing phase is the legacy "up" direction.
static const uint8_t PHASES[8] = {0x1, 0x3, 0x2, 0x6, 0x4, 0xC, 0x8, 0x9};

struct Motor {
  long pos;            // half-steps since boot (or POSL0/POSR0)
  uint16_t remaining;  // half-steps left in the current move
  uint16_t done;       // half-steps taken in the current move
  int8_t dir;          // +1 up, -1 down
  uint8_t phase;
  float vmax;          // half-steps/s
  float acc;           // half-steps/s^2
  uint32_t next_us;
  bool jog;            // started by a legacy jog command
};

static Motor mot[2];
static uint16_t va = JOG_VA_DEFAULT, vs = JOG_VS_DEFAULT, acc = JOG_ACC_DEFAULT;

uint16_t jog_va() { return va; }
uint16_t jog_vs() { return vs; }
uint16_t jog_acc() { return acc; }

static void write_coils(uint8_t m, uint8_t pattern) {
  for (uint8_t i = 0; i < 4; i++) digitalWrite(MOTOR_PINS[m][i], (pattern >> i) & 1);
}

static void release(uint8_t m) {
  mot[m].remaining = 0;
  write_coils(m, 0);
}

void motors_init() {
  for (uint8_t m = 0; m < 2; m++) {
    for (uint8_t i = 0; i < 4; i++) {
      digitalWrite(MOTOR_PINS[m][i], LOW);
      pinMode(MOTOR_PINS[m][i], OUTPUT);
    }
    mot[m] = Motor{0, 0, 0, 1, 0, 0, 0, 0, false};
  }
}

bool motors_moving() { return mot[0].remaining || mot[1].remaining; }

void motors_stop_all() { release(0); release(1); }

const __FlashStringHelper *motor_state(uint8_t m) { return mot[m].remaining ? F("run") : F("idle"); }
long motor_pos(uint8_t m) { return mot[m].pos; }

// Trapezoidal profile: v = min(vmax, sqrt(2 a done), sqrt(2 a remaining)).
static uint32_t step_interval_us(const Motor &mo) {
  float up = sqrt(2.0f * mo.acc * (mo.done + 1));
  float down = sqrt(2.0f * mo.acc * (mo.remaining + 1));
  float v = min(mo.vmax, min(up, down));
  if (v < 10.0f) v = 10.0f;
  return (uint32_t)(1000000.0f / v);
}

static void start_move(uint8_t m, long steps, float vmax, float a, bool jog) {
  Motor &mo = mot[m];
  mo.dir = steps >= 0 ? 1 : -1;
  mo.remaining = (uint16_t)(steps >= 0 ? steps : -steps);
  mo.done = 0;
  mo.vmax = vmax;
  mo.acc = a;
  mo.jog = jog;
  mo.next_us = micros();
}

void motors_tick() {
  uint32_t now = micros();
  for (uint8_t m = 0; m < 2; m++) {
    Motor &mo = mot[m];
    if (!mo.remaining || (long)(now - mo.next_us) < 0) continue;
    mo.phase = (mo.phase + mo.dir) & 7;
    write_coils(m, PHASES[mo.phase]);
    mo.pos += mo.dir;
    mo.remaining--;
    mo.done++;
    if (mo.remaining) {
      mo.next_us += step_interval_us(mo);
    } else {
      write_coils(m, 0);  // release coils at the end of every move
      event_begin(F("MOTOR"));
      resp_kv(F("m"), m + 1);
      resp_kv(F("steps"), mo.done);
      resp_kv(F("pos"), mo.pos);
      Serial.print(F(" done"));
      resp_end();
    }
  }
}

static bool motor_arg(const char *t, uint8_t &mask) {
  if (tok_is(t, F("1"))) mask = 1;
  else if (tok_is(t, F("2"))) mask = 2;
  else if (tok_is(t, F("ALL"))) mask = 3;
  else return false;
  return true;
}

// MOTOR ARM <token> | MOTOR <1|2> STEP <+-n> [rpm] | MOTOR <1|2|ALL> RELEASE | MOTOR STOP
void cmd_motor(const Command &c) {
  if (c.ntok < 2) { resp_err(c, E_ARG, F("usage: MOTOR ARM|STOP|<m> STEP|<m> RELEASE")); return; }
  if (tok_is(c.tok[1], F("ARM"))) { cmd_motor_arm(c); return; }
  if (tok_is(c.tok[1], F("STOP"))) {
    motors_stop_all();
    resp_ok(c);
    resp_kv(F("pos1"), mot[0].pos);
    resp_kv(F("pos2"), mot[1].pos);
    resp_end();
    return;
  }
  uint8_t mask;
  if (!motor_arg(c.tok[1], mask) || c.ntok < 3) {
    resp_err(c, E_ARG, F("usage: MOTOR ARM|STOP|<m> STEP|<m> RELEASE"));
    return;
  }
  if (tok_is(c.tok[2], F("RELEASE"))) {
    if (mask & 1) release(0);
    if (mask & 2) release(1);
    resp_ok(c);
    resp_end();
    return;
  }
  long steps, rpm = MOTOR_RPM_DEFAULT;
  if (!tok_is(c.tok[2], F("STEP")) || mask == 3 ||
      !arg_long(c, 3, -(long)MOTOR_STEP_MAX, MOTOR_STEP_MAX, steps) ||
      (c.ntok > 4 && !arg_long(c, 4, 1, MOTOR_RPM_MAX, rpm))) {
    resp_err(c, E_ARG, F("usage: MOTOR <1|2> STEP <+-n<=2048> [rpm<=15]"));
    return;
  }
  uint8_t m = mask - 1;
  if (!motion_armed()) { resp_err(c, E_REFUSED, F("not armed")); return; }
  if (optics_any_ce()) { resp_err(c, E_REFUSED, F("LED on")); return; }
  if (mot[m].remaining) { resp_err(c, E_BUSY, F("motor moving")); return; }
  float v = (float)rpm * HALF_STEPS_PER_REV / 60.0f;
  start_move(m, steps, v, JOG_ACC_DEFAULT, false);
  resp_ok(c);
  resp_kv(F("m"), m + 1);
  resp_kv(F("steps"), steps);
  resp_kv(F("rpm"), rpm);
  resp_end();
}

// ---------------------------------------------------------------------------
// Legacy jog layer for lio_control.py (reviewed exception to the arming rule,
// docs/PROTOCOL.md §7). Each jog ends at whichever comes first: S, the
// JOG_MAX_STEPS bound, or the comms-loss failsafe. Coils release on stop.
// ---------------------------------------------------------------------------

static void jog(const Command &c, uint8_t mask, int8_t dir) {
  if (optics_any_ce()) { resp_err(c, E_REFUSED, F("LED on")); return; }
  long steps = (long)dir * JOG_MAX_STEPS;
  float v = (mask == 3) ? vs : va;
  if (mask & 1) start_move(0, steps, v, acc, true);
  if (mask & 2) start_move(1, steps, v, acc, true);
  resp_ok(c);
  resp_kv(F("steps"), steps);
  resp_kv(F("v"), (long)v);
  resp_end();
}

static uint16_t clamp_u16(long v, uint16_t lo, uint16_t hi, bool &clamped) {
  clamped = v < lo || v > hi;
  return (uint16_t)(v < lo ? lo : (v > hi ? hi : v));
}

bool cmd_legacy(const Command &c) {
  if (c.ntok != 1) return false;
  const char *t = c.tok[0];
  if (tok_is(t, F("S"))) {
    motors_stop_all();
    resp_ok(c);
    resp_end();
    return true;
  }
  if (tok_is(t, F("U"))) { jog(c, 3, +1); return true; }
  if (tok_is(t, F("D"))) { jog(c, 3, -1); return true; }
  if (tok_is(t, F("LU"))) { jog(c, 1, +1); return true; }
  if (tok_is(t, F("LD"))) { jog(c, 1, -1); return true; }
  if (tok_is(t, F("RU"))) { jog(c, 2, +1); return true; }
  if (tok_is(t, F("RD"))) { jog(c, 2, -1); return true; }
  if (tok_is(t, F("POSL0"))) { mot[0].pos = 0; resp_ok(c); resp_end(); return true; }
  if (tok_is(t, F("POSR0"))) { mot[1].pos = 0; resp_ok(c); resp_end(); return true; }
  if (tok_is(t, F("?"))) {
    resp_ok(c);
    Serial.print(F(" legacy=U,D,LU,LD,RU,RD,S,VA<n>,VS<n>,ACC<n>,POSL0,POSR0 see=docs/PROTOCOL.md"));
    resp_end();
    return true;
  }
  // VA<n>, VS<n>, ACC<n>: accepted, clamped to the configured limits.
  uint8_t which = 0, skip = 0;
  if (strncmp_P(t, PSTR("ACC"), 3) == 0) { which = 3; skip = 3; }
  else if (strncmp_P(t, PSTR("VA"), 2) == 0) { which = 1; skip = 2; }
  else if (strncmp_P(t, PSTR("VS"), 2) == 0) { which = 2; skip = 2; }
  if (!which) return false;
  long v;
  if (!parse_long(t + skip, v)) { resp_err(c, E_ARG, F("expects a number")); return true; }
  bool clamped;
  uint16_t value;
  if (which == 3) {
    value = acc = clamp_u16(v, JOG_ACC_MIN, JOG_ACC_MAX, clamped);
    for (uint8_t m = 0; m < 2; m++) if (mot[m].jog) mot[m].acc = acc;
  } else {
    value = clamp_u16(v, JOG_SPEED_MIN, JOG_SPEED_MAX, clamped);
    bool sync = mot[0].jog && mot[1].jog && mot[0].remaining && mot[1].remaining;
    if (which == 1) {
      va = value;
      if (!sync) for (uint8_t m = 0; m < 2; m++) if (mot[m].jog && mot[m].remaining) mot[m].vmax = va;
    } else {
      vs = value;
      if (sync) { mot[0].vmax = vs; mot[1].vmax = vs; }
    }
  }
  resp_ok(c);
  resp_kv(F("value"), value);
  resp_kv(F("clamped"), clamped ? 1 : 0);
  resp_end();
  return true;
}
