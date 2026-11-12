#include "adc.h"
#include "motors.h"
#include "optics.h"
#include "safety.h"
#include "softi2c.h"

// A minimal ADS1115 driver over the software I2C bus (softi2c.h). Each read is
// a single-shot conversion: write the config register (which also starts it),
// poll its OS bit, then read the conversion register.
static bool present = false;
static uint8_t gain_idx = 1;  // GAIN_ONE (+-4.096 V)
static uint8_t rate_idx = 4;  // 128 SPS

// The ADS1115's PGA and DR codes are the indexes into these tables.
static const float LSB_MV[6] = {0.1875f, 0.125f, 0.0625f, 0.03125f, 0.015625f, 0.0078125f};
static const uint16_t RATES[8] = {8, 16, 32, 64, 128, 250, 475, 860};

const uint8_t REG_CONVERSION = 0x00;
const uint8_t REG_CONFIG = 0x01;
const uint16_t CFG_OS = 0x8000;          // write: start; read: 1 = idle (done)
const uint16_t CFG_MUX_SINGLE_0 = 0x4000;  // AINx vs GND = 0x4000 + x * 0x1000
const uint16_t CFG_MODE_SINGLE = 0x0100;
const uint16_t CFG_COMP_OFF = 0x0003;

const __FlashStringHelper *adc_gain_name() {
  switch (gain_idx) {
    case 0: return F("2/3");
    case 1: return F("1");
    case 2: return F("2");
    case 3: return F("4");
    case 4: return F("8");
    default: return F("16");
  }
}
uint16_t adc_rate_sps() { return RATES[rate_idx]; }
float adc_lsb_mv() { return LSB_MV[gain_idx]; }
uint32_t adc_conv_us() { return 1000000UL / RATES[rate_idx]; }
static uint8_t write_reg(uint8_t reg, uint16_t v) {
  uint8_t b[3] = {reg, (uint8_t)(v >> 8), (uint8_t)(v & 0xFF)};
  return si2c_write(ADC_ADDR, b, 3);
}

// Reads the register the pointer was last set to.
static uint8_t read16(uint16_t &v) {
  uint8_t b[2];
  uint8_t e = si2c_read(ADC_ADDR, b, 2);
  v = ((uint16_t)b[0] << 8) | b[1];
  return e;
}

static bool probe() { return si2c_write(ADC_ADDR, nullptr, 0) == SI2C_OK; }

static bool attach() {
  present = probe();
  return present;
}

void adc_defaults() { gain_idx = 1; rate_idx = 4; present = false; }

bool adc_init() {
  si2c_begin();
  if (!attach()) fault_set(F_ADC_MISSING);
  return present;
}

// The ADS1115 is powered from bank A, which may switch on after the Nano
// (USB-powered) has booted: look for it again whenever it is needed.
bool adc_present() { return present || attach(); }

static uint8_t read_failed() {
  present = false;  // looked for again on the next read
  fault_set(F_I2C_ERROR);
  return E_ADC;
}

uint8_t adc_read(uint8_t ch, int16_t &raw) {
  if (!adc_present()) return read_failed();
  uint16_t cfg = CFG_OS | (CFG_MUX_SINGLE_0 + 0x1000 * ch) | ((uint16_t)gain_idx << 9) |
                 CFG_MODE_SINGLE | ((uint16_t)rate_idx << 5) | CFG_COMP_OFF;
  if (write_reg(REG_CONFIG, cfg)) return read_failed();
  // The first poll may still see the previous conversion's OS bit; half a
  // conversion period of waiting avoids that.
  uint32_t t0 = micros();
  uint32_t limit = 2 * adc_conv_us() + 5000UL;
  while (micros() - t0 < adc_conv_us() / 2) service();
  for (;;) {
    uint16_t v;
    if (read16(v)) return read_failed();  // pointer is still at CONFIG
    if (v & CFG_OS) break;
    if (micros() - t0 > limit) return read_failed();
    service();
  }
  uint8_t ptr = REG_CONVERSION;
  uint16_t v;
  if (si2c_write(ADC_ADDR, &ptr, 1) || read16(v)) return read_failed();
  raw = (int16_t)v;
  return 0;
}

uint8_t adc_read_mean(uint8_t ch, uint8_t n, int16_t &mean) {
  long sum = 0;
  for (uint8_t i = 0; i < n; i++) {
    int16_t r;
    uint8_t e = adc_read(ch, r);
    if (e) return e;
    sum += r;
  }
  mean = (int16_t)((sum + (sum >= 0 ? n / 2 : -(long)(n / 2))) / n);
  return 0;
}

// ADC READ <0-3> [n]
static void adc_cmd_read(const Command &c) {
  long ch, n = 1;
  if (!arg_long(c, 2, 0, 3, ch)) { resp_err(c, E_ARG, F("usage: ADC READ <0-3> [n]")); return; }
  if (c.ntok > 3 && !arg_long(c, 3, 1, ADC_READ_N_MAX, n)) { resp_err(c, E_ARG, F("n out of range")); return; }
  int16_t first = 0;
  float s = 0, ss = 0;
  for (long i = 0; i < n; i++) {
    int16_t r;
    if (adc_read((uint8_t)ch, r)) { resp_err(c, E_ADC, F("adc read failed")); return; }
    if (i == 0) first = r;
    float d = r - first;  // shifted sums keep float precision
    s += d;
    ss += d * d;
  }
  float mean = first + s / n;
  resp_ok(c);
  resp_kv(F("ch"), ch);
  resp_kv(F("raw"), lround(mean));
  resp_kv_f(F("mv"), mean * adc_lsb_mv(), 3);
  resp_kv(F("n"), n);
  if (n > 1) {
    float var = (ss - s * s / n) / (n - 1);
    resp_kv_f(F("mean"), mean, 2);
    resp_kv_f(F("std"), var > 0 ? sqrt(var) : 0.0f, 2);
  }
  resp_end();
}

// ADC CFG GAIN <2/3|1|2|4|8|16> | ADC CFG RATE <8..860>
static void adc_cmd_cfg(const Command &c) {
  if (c.ntok < 4) { resp_err(c, E_ARG, F("usage: ADC CFG GAIN|RATE <v>")); return; }
  if (tok_is(c.tok[2], F("GAIN"))) {
    static const char *const names[6] = {"2/3", "1", "2", "4", "8", "16"};
    for (uint8_t i = 0; i < 6; i++) {
      if (strcmp(c.tok[3], names[i]) == 0) {
        gain_idx = i;
        resp_ok(c);
        resp_kv_P(F("gain"), adc_gain_name());
        resp_kv_f(F("lsb_mv"), adc_lsb_mv(), 7);
        resp_end();
        return;
      }
    }
  } else if (tok_is(c.tok[2], F("RATE"))) {
    long r;
    if (parse_long(c.tok[3], r)) {
      for (uint8_t i = 0; i < 8; i++) {
        if (RATES[i] == r) {
          rate_idx = i;
          resp_ok(c);
          resp_kv(F("rate"), r);
          resp_end();
          return;
        }
      }
    }
  }
  resp_err(c, E_ARG, F("bad gain or rate"));
}

// Longest line: "# S i=1999 t_us=4294967295 raw=-32768\r\n" (39 bytes).
const uint8_t STREAM_LINE_MAX = 40;

static void stream_sample(long i, uint32_t ts, int16_t r) {
  // Wait for room in the TX buffer while servicing (motors keep stepping,
  // watchdogs keep running) instead of blocking inside Serial.print.
  while (Serial.availableForWrite() < STREAM_LINE_MAX) service();
  event_begin(F("S"));
  resp_kv(F("i"), i);
  resp_kv_u(F("t_us"), ts);
  resp_kv(F("raw"), r);
  resp_end();
}

// ADC STREAM <ch> <n> <interval_ms> [hole on_idx off_idx]
// Emits "# S i= t_us= raw=" per sample, then OK. Up to STREAM_BUF_N samples
// are captured first and printed afterwards; longer streams print live. The
// optional LED schedule lights <hole> from sample on_idx up to (not including)
// off_idx, for step-response tests (T07.1). The schedule is checked against
// the watchdog.
static void adc_cmd_stream(const Command &c) {
  long ch, n, iv, hole = 0, on_i = 0, off_i = 0;
  if (!arg_long(c, 2, 0, 3, ch) || !arg_long(c, 3, 1, STREAM_N_MAX, n) || !arg_long(c, 4, 0, 1000, iv)) {
    resp_err(c, E_ARG, F("usage: ADC STREAM <ch> <n> <interval_ms> [hole on off]"));
    return;
  }
  if (c.ntok > 5) {
    if (!arg_long(c, 5, 1, N_HOLES, hole) || !arg_long(c, 6, 0, n - 1, on_i) ||
        !arg_long(c, 7, on_i + 1, n, off_i)) {
      resp_err(c, E_ARG, F("bad LED schedule"));
      return;
    }
    if (motors_moving()) { resp_err(c, E_BUSY, F("motor moving")); return; }
    uint32_t per_us = max((uint32_t)iv * 1000UL, adc_conv_us() + 500UL);
    uint32_t est_ms = (uint32_t)(off_i - on_i) * per_us / 1000UL + 20;
    if (est_ms > optics_wdt_ms(optics_rail_of((uint8_t)hole))) {
      resp_err(c, E_REFUSED, F("LED time exceeds watchdog"));
      return;
    }
  }
  // Short streams are captured first and printed afterwards, so that serial
  // output cannot slow the sampling (T03.4, T07.1 at 860 SPS).
  static int16_t buf_raw[STREAM_BUF_N];
  static uint32_t buf_t[STREAM_BUF_N];
  const bool buffered = n <= STREAM_BUF_N;
  optics_off();
  uint32_t t0 = micros();
  for (long i = 0; i < n; i++) {
    if (iv > 0) { while (micros() - t0 < (uint32_t)i * iv * 1000UL) service(); }
    if (hole && i == on_i) {
      uint32_t until;
      if (optics_ch_on((uint8_t)hole, 0, until)) { optics_off(); resp_err(c, E_REFUSED, F("ch on refused")); return; }
    }
    if (hole && i == off_i) optics_off();
    int16_t r;
    uint32_t ts = micros() - t0;
    if (adc_read((uint8_t)ch, r)) { optics_off(); resp_err(c, E_ADC, F("adc read failed")); return; }
    if (buffered) {
      buf_raw[i] = r;
      buf_t[i] = ts;
    } else {
      stream_sample(i, ts, r);
    }
  }
  optics_off();
  if (buffered) {
    for (long i = 0; i < n; i++) stream_sample(i, buf_t[i], buf_raw[i]);
  }
  resp_ok(c);
  resp_kv(F("ch"), ch);
  resp_kv(F("n"), n);
  resp_kv_u(F("dur_ms"), (micros() - t0) / 1000UL);
  resp_end();
}

void cmd_adc(const Command &c) {
  if (c.ntok < 2) { resp_err(c, E_ARG, F("usage: ADC READ|CFG|STREAM ...")); return; }
  if (tok_is(c.tok[1], F("CFG"))) { adc_cmd_cfg(c); return; }
  if (!adc_present()) { resp_err(c, E_ADC, F("ADS1115 not present")); return; }
  if (tok_is(c.tok[1], F("READ"))) adc_cmd_read(c);
  else if (tok_is(c.tok[1], F("STREAM"))) adc_cmd_stream(c);
  else resp_err(c, E_ARG, F("usage: ADC READ|CFG|STREAM ..."));
}

// --- I2C DIAG: line-level checks of LIO_PIN_SDA/LIO_PIN_SCL. The pins are only ever
// driven LOW (never HIGH), so nothing on the bus is fought.
static uint8_t idle_high(uint8_t pin) {
  pinMode(pin, INPUT_PULLUP);
  delayMicroseconds(DIAG_SETTLE_US);
  return digitalRead(pin);
}

// 1 if the line rises on its own (an external pull-up to a powered VDD):
// pull it low, release it with the internal pull-up off, and read.
static uint8_t has_pullup(uint8_t pin) {
  pinMode(pin, OUTPUT);
  digitalWrite(pin, LOW);
  delayMicroseconds(DIAG_SETTLE_US);
  pinMode(pin, INPUT);
  delayMicroseconds(DIAG_SETTLE_US);
  return digitalRead(pin);
}

// 1 if pulling `drive` low also pulls `sense` (held up internally) low.
static uint8_t follows(uint8_t drive, uint8_t sense) {
  pinMode(sense, INPUT_PULLUP);
  pinMode(drive, OUTPUT);
  digitalWrite(drive, LOW);
  delayMicroseconds(DIAG_SETTLE_US);
  uint8_t low = !digitalRead(sense);
  pinMode(drive, INPUT_PULLUP);
  delayMicroseconds(DIAG_SETTLE_US);
  return low;
}

static void i2c_diag(const Command &c) {
  uint8_t sda = idle_high(LIO_PIN_SDA), scl = idle_high(LIO_PIN_SCL);
  uint8_t sda_pu = has_pullup(LIO_PIN_SDA), scl_pu = has_pullup(LIO_PIN_SCL);
  // Only meaningful when both lines idle high.
  uint8_t bridge = sda && scl && (follows(LIO_PIN_SDA, LIO_PIN_SCL) || follows(LIO_PIN_SCL, LIO_PIN_SDA));
  si2c_begin();  // restores the open-drain idle state and frees a stuck bus
  // The software bus has one speed: the "slow" and "fast" fields are kept for
  // the protocol and carry the same result.
  uint8_t ack = si2c_write(ADC_ADDR, nullptr, 0);
  attach();
  service();
  resp_ok(c);
  resp_kv(F("sda"), sda);
  resp_kv(F("scl"), scl);
  resp_kv(F("sda_pu"), sda_pu);
  resp_kv(F("scl_pu"), scl_pu);
  resp_kv(F("bridge"), bridge);
  resp_kv(F("ack_slow"), ack);
  resp_kv(F("ack_fast"), ack);
  resp_kv_u(F("slow_hz"), si2c_hz());
  resp_kv_u(F("fast_hz"), si2c_hz());
  resp_kv_u(F("hz"), si2c_hz());
  resp_kv(F("present"), present);
  resp_end();
}

// I2C SCAN | I2C DIAG
void cmd_i2c(const Command &c) {
  if (c.ntok >= 2 && tok_is(c.tok[1], F("DIAG"))) { i2c_diag(c); return; }
  if (c.ntok < 2 || !tok_is(c.tok[1], F("SCAN"))) { resp_err(c, E_ARG, F("usage: I2C SCAN|DIAG")); return; }
  // Build the list first so the response line is never interrupted.
  uint8_t found[8];
  uint8_t nf = 0;
  for (uint8_t a = 1; a < 127; a++) {
    if (si2c_write(a, nullptr, 0) == SI2C_OK && nf < sizeof(found)) found[nf++] = a;
    service();
  }
  resp_ok(c);
  Serial.print(F(" n="));
  Serial.print(nf);
  Serial.print(F(" addrs="));
  for (uint8_t i = 0; i < nf; i++) {
    if (i) Serial.print(',');
    Serial.print(F("0x"));
    if (found[i] < 16) Serial.print('0');
    Serial.print(found[i], HEX);
  }
  if (nf == 0) Serial.print(F("none"));
  resp_end();
}
