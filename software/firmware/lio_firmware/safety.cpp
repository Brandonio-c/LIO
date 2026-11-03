#include "safety.h"
#include <avr/wdt.h>
#include "motors.h"
#include "optics.h"

static uint8_t fault_bits = 0;
static uint16_t n_wdt_trips = 0;
static uint16_t n_failsafe = 0;
static uint16_t token = 0;
static bool armed = false;
static uint32_t armed_at = 0;

void fault_set(uint8_t bits) { fault_bits |= bits; }
uint8_t faults() { return fault_bits; }
uint16_t wdt_trips() { return n_wdt_trips; }
void wdt_trip_count() { n_wdt_trips++; fault_set(F_WDT_TRIP); }
uint16_t failsafe_trips() { return n_failsafe; }

uint16_t arm_token() { return token; }
void disarm() { armed = false; }

bool motion_armed() {
  if (armed && millis() - armed_at >= ARM_DURATION_MS) armed = false;
  return armed;
}

uint32_t armed_remaining_ms() {
  return motion_armed() ? ARM_DURATION_MS - (millis() - armed_at) : 0;
}

void safety_init() {
  // Token: mixes floating-input noise (A6/A7 are unconnected) with boot timing.
  uint16_t t = (uint16_t)micros();
  for (uint8_t i = 0; i < 8; i++) {
    t = (t << 3) ^ (t >> 5) ^ (uint16_t)analogRead(i & 1 ? A7 : A6);
  }
  token = t ? t : 0x5A5A;
#if LIO_HW_WDT
  wdt_enable(WDTO_2S);
#endif
}

static void comms_failsafe() {
  bool active = optics_any_ce() || motors_moving() || motion_armed();
  if (!active || millis() - proto_last_rx_ms() < COMMS_TIMEOUT_MS) return;
  optics_off();
  motors_stop_all();
  armed = false;
  n_failsafe++;
  fault_set(F_FAILSAFE);
  event_begin(F("FAILSAFE"));
  resp_kv_P(F("reason"), F("comms"));
  resp_kv_u(F("idle_ms"), millis() - proto_last_rx_ms());
  resp_end();
}

void service() {
  motors_tick();
  optics_tick();
  comms_failsafe();
#if LIO_HW_WDT
  wdt_reset();
#endif
}

void service_delay(uint32_t ms) {
  uint32_t t0 = millis();
  while (millis() - t0 < ms) service();
}

void cmd_motor_arm(const Command &c) {
  uint16_t t;
  if (c.ntok < 3 || !parse_hex16(c.tok[2], t)) { resp_err(c, E_ARG, F("usage: MOTOR ARM <token>")); return; }
  if (t != token) { resp_err(c, E_REFUSED, F("wrong token")); return; }
  armed = true;
  armed_at = millis();
  resp_ok(c);
  resp_kv_u(F("armed_ms"), ARM_DURATION_MS);
  resp_end();
}

void cmd_reset(const Command &c) {
  optics_off();
  motors_stop_all();
  resp_ok(c);
  resp_end();
  Serial.flush();
  // Re-run the C runtime and setup() from address 0. This works with both
  // bootloaders; a watchdog reset would hang the old one. setup() re-applies
  // the power-up dark state before anything else.
  cli();
#if LIO_HW_WDT
  wdt_disable();
#endif
  UCSR0B = 0;  // UART off
  TWCR = 0;    // TWI off
  TIMSK0 = 0; TIMSK1 = 0; TIMSK2 = 0;
  asm volatile("jmp 0");
}
