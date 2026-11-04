#include "softi2c.h"
#include "config.h"

// Direct port access: digitalWrite()/pinMode() take a few microseconds each.
// Only the main loop touches these ports (no interrupt handler writes PORTB/D),
// so the read-modify-write below is safe.
static volatile uint8_t *sda_ddr, *sda_out, *sda_in, *scl_ddr, *scl_out, *scl_in;
static uint8_t sda_bit, scl_bit;

// LOW: output bit cleared first, then the pin made an output.
// Released: the pin made an input first, then the internal pull-up switched on.
// The pin is never an output with its bit set, i.e. never driven HIGH.
static inline void sda_low() { *sda_out &= ~sda_bit; *sda_ddr |= sda_bit; }
static inline void sda_release() { *sda_ddr &= ~sda_bit; *sda_out |= sda_bit; }
static inline void scl_low() { *scl_out &= ~scl_bit; *scl_ddr |= scl_bit; }
static inline void scl_release() { *scl_ddr &= ~scl_bit; *scl_out |= scl_bit; }
bool si2c_sda_high() { return *sda_in & sda_bit; }
bool si2c_scl_high() { return *scl_in & scl_bit; }
static inline void half() { delayMicroseconds(SI2C_HALF_US); }

// Release SCL and wait for it to rise (slow edges, clock stretching).
static bool scl_up() {
  scl_release();
  uint32_t t0 = micros();
  while (!si2c_scl_high()) {
    if (micros() - t0 > SI2C_RISE_MAX_US) return false;
  }
  return true;
}

// Nominal: two half-bit delays plus about 2 us of port access per bit.
uint32_t si2c_hz() { return 1000000UL / (2UL * SI2C_HALF_US + 2UL); }

void si2c_begin() {
  uint8_t p = digitalPinToPort(PIN_SDA);
  sda_ddr = portModeRegister(p);
  sda_out = portOutputRegister(p);
  sda_in = portInputRegister(p);
  sda_bit = digitalPinToBitMask(PIN_SDA);
  p = digitalPinToPort(PIN_SCL);
  scl_ddr = portModeRegister(p);
  scl_out = portOutputRegister(p);
  scl_in = portInputRegister(p);
  scl_bit = digitalPinToBitMask(PIN_SCL);
  sda_release();
  scl_release();
  half();
  si2c_recover();
}

static void stop() {
  sda_low();
  half();
  scl_up();
  half();
  sda_release();
  half();
}

void si2c_recover() {
  sda_release();
  for (uint8_t i = 0; i < 9 && !si2c_sda_high(); i++) {
    scl_low();
    half();
    if (!scl_up()) return;
    half();
  }
  if (si2c_scl_high()) {
    scl_low();
    half();
    stop();
  }
}

static bool start() {
  if (!si2c_sda_high() || !si2c_scl_high()) return false;
  sda_low();
  half();
  scl_low();
  half();
  return true;
}

// Each returns -1 on an SCL timeout.
static int8_t put_bit(bool b) {
  if (b) sda_release(); else sda_low();
  half();
  if (!scl_up()) return -1;
  half();
  scl_low();
  return 0;
}

static int8_t get_bit() {
  sda_release();
  half();
  if (!scl_up()) return -1;
  half();
  int8_t v = si2c_sda_high() ? 1 : 0;
  scl_low();
  return v;
}

// 0 ack, 1 nack, -1 timeout.
static int8_t put_byte(uint8_t b) {
  for (uint8_t m = 0x80; m; m >>= 1) {
    if (put_bit(b & m) < 0) return -1;
  }
  return get_bit();
}

static int16_t get_byte(bool ack) {
  uint8_t v = 0;
  for (uint8_t i = 0; i < 8; i++) {
    int8_t b = get_bit();
    if (b < 0) return -1;
    v = (v << 1) | b;
  }
  if (put_bit(!ack) < 0) return -1;
  return v;
}

static uint8_t fail(uint8_t code) {
  if (code == SI2C_TIMEOUT) si2c_recover();
  else stop();
  return code;
}

uint8_t si2c_write(uint8_t addr, const uint8_t *buf, uint8_t n) {
  if (!start()) { si2c_recover(); return SI2C_BUS_ERROR; }
  int8_t a = put_byte(addr << 1);
  if (a < 0) return fail(SI2C_TIMEOUT);
  if (a) return fail(SI2C_NACK_ADDR);
  for (uint8_t i = 0; i < n; i++) {
    a = put_byte(buf[i]);
    if (a < 0) return fail(SI2C_TIMEOUT);
    if (a) return fail(SI2C_NACK_DATA);
  }
  stop();
  return SI2C_OK;
}

uint8_t si2c_read(uint8_t addr, uint8_t *buf, uint8_t n) {
  if (!start()) { si2c_recover(); return SI2C_BUS_ERROR; }
  int8_t a = put_byte((addr << 1) | 1);
  if (a < 0) return fail(SI2C_TIMEOUT);
  if (a) return fail(SI2C_NACK_ADDR);
  for (uint8_t i = 0; i < n; i++) {
    int16_t v = get_byte(i + 1 < n);
    if (v < 0) return fail(SI2C_TIMEOUT);
    buf[i] = (uint8_t)v;
  }
  stop();
  return SI2C_OK;
}
