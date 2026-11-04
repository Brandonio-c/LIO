#include "adc.h"
#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include "motors.h"
#include "optics.h"
#include "safety.h"

static Adafruit_ADS1115 ads;
static bool present = false;
static uint32_t bus_hz = I2C_CLOCK_HZ;
static uint8_t gain_idx = 1;  // GAIN_ONE
static uint8_t rate_idx = 4;  // 128 SPS

static const adsGain_t GAINS[6] = {GAIN_TWOTHIRDS, GAIN_ONE, GAIN_TWO,
                                   GAIN_FOUR, GAIN_EIGHT, GAIN_SIXTEEN};
static const float LSB_MV[6] = {0.1875f, 0.125f, 0.0625f, 0.03125f, 0.015625f, 0.0078125f};
static const uint16_t RATES[8] = {8, 16, 32, 64, 128, 250, 475, 860};
static const uint16_t RATE_BITS[8] = {
    RATE_ADS1115_8SPS,   RATE_ADS1115_16SPS,  RATE_ADS1115_32SPS,  RATE_ADS1115_64SPS,
    RATE_ADS1115_128SPS, RATE_ADS1115_250SPS, RATE_ADS1115_475SPS, RATE_ADS1115_860SPS};

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
static bool probe() {
  Wire.beginTransmission(ADC_ADDR);
  return Wire.endTransmission() == 0;
}

static bool attach() {
  // Slow, weakly pulled-up lines (no external pull-ups, long breadboard wires)
  // can fail at I2C_CLOCK_HZ yet work at I2C_SLOW_HZ: fall back rather than
  // lose the ADC. ads.begin() resets the bus to 100 kHz, so set the clock after.
  bus_hz = I2C_CLOCK_HZ;
  Wire.setClock(bus_hz);
  if (!probe()) {
    bus_hz = I2C_SLOW_HZ;
    Wire.setClock(bus_hz);
  }
  present = probe() && ads.begin(ADC_ADDR);
  if (!present) bus_hz = I2C_CLOCK_HZ;
  Wire.setClock(bus_hz);
  Wire.setWireTimeout(I2C_TIMEOUT_US, true);
  if (present) {
    ads.setGain(GAINS[gain_idx]);
    ads.setDataRate(RATE_BITS[rate_idx]);
  }
  return present;
}

bool adc_init() {
  Wire.begin();
  Wire.setClock(I2C_CLOCK_HZ);
  Wire.setWireTimeout(I2C_TIMEOUT_US, true);
  if (!attach()) fault_set(F_ADC_MISSING);
  return present;
}

// The ADS1115 is powered from bank A, which may switch on after the Nano
// (USB-powered) has booted: look for it again whenever it is needed.
bool adc_present() { return present || attach(); }

static bool i2c_failed() {
  if (Wire.getWireTimeoutFlag()) { Wire.clearWireTimeoutFlag(); return true; }
  return false;
}

uint8_t adc_read(uint8_t ch, int16_t &raw) {
  if (!adc_present() || !probe()) { fault_set(F_I2C_ERROR); return E_ADC; }
  ads.startADCReading(ADS1X15_REG_CONFIG_MUX_SINGLE_0 + 0x1000 * ch, false);
  // The first conversionComplete() poll may still see the previous result's
  // OS bit; one conversion period of waiting avoids that.
  uint32_t t0 = micros();
  uint32_t limit = 2 * adc_conv_us() + 5000UL;
  while (micros() - t0 < adc_conv_us() / 2) service();
  while (!ads.conversionComplete()) {
    if (i2c_failed() || micros() - t0 > limit) { fault_set(F_I2C_ERROR); return E_ADC; }
    service();
  }
  raw = ads.getLastConversionResults();
  if (i2c_failed()) { fault_set(F_I2C_ERROR); return E_ADC; }
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
        if (present) ads.setGain(GAINS[i]);
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
          if (present) ads.setDataRate(RATE_BITS[i]);
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

// --- I2C DIAG: line-level checks with the TWI peripheral switched off. The pins
// are only ever driven LOW (never HIGH), so nothing on the bus is fought.
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

// Wire.endTransmission() code for an empty write to the ADS1115:
// 0 ack, 2 no ack (address), 4 bus error, 5 timeout.
static uint8_t ack_at(uint32_t hz) {
  Wire.setClock(hz);
  Wire.beginTransmission(ADC_ADDR);
  uint8_t r = Wire.endTransmission();
  i2c_failed();
  return r;
}

static void i2c_diag(const Command &c) {
  Wire.end();
  uint8_t sda = idle_high(SDA), scl = idle_high(SCL);
  uint8_t sda_pu = has_pullup(SDA), scl_pu = has_pullup(SCL);
  // Only meaningful when both lines idle high.
  uint8_t bridge = sda && scl && (follows(SDA, SCL) || follows(SCL, SDA));
  pinMode(SDA, INPUT);
  pinMode(SCL, INPUT);
  Wire.begin();
  Wire.setWireTimeout(I2C_TIMEOUT_US, true);
  uint8_t ack_slow = ack_at(I2C_SLOW_HZ), ack_fast = ack_at(I2C_CLOCK_HZ);
  present = false;
  attach();
  service();
  resp_ok(c);
  resp_kv(F("sda"), sda);
  resp_kv(F("scl"), scl);
  resp_kv(F("sda_pu"), sda_pu);
  resp_kv(F("scl_pu"), scl_pu);
  resp_kv(F("bridge"), bridge);
  resp_kv(F("ack_slow"), ack_slow);
  resp_kv(F("ack_fast"), ack_fast);
  resp_kv_u(F("slow_hz"), I2C_SLOW_HZ);
  resp_kv_u(F("fast_hz"), I2C_CLOCK_HZ);
  resp_kv_u(F("hz"), bus_hz);
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
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0 && nf < sizeof(found)) found[nf++] = a;
    i2c_failed();
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
