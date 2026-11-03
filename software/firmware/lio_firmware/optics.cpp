#include "optics.h"
#include "adc.h"
#include "config.h"
#include "motors.h"
#include "safety.h"

static uint16_t mask = 0;
static bool ce[3] = {false, false, false};  // index by rail (1, 2)
static uint32_t lit_at = 0;
static uint32_t lit_for = 0;
static bool lit_by_wdt = false;   // true when the deadline is the watchdog limit
static uint16_t wdt_ms[3] = {0, WDT_A_DEFAULT_MS, WDT_B_DEFAULT_MS};

static const uint8_t CE_PIN[3] = {0, PIN_CE1, PIN_CE2};

static void set_ce(uint8_t rail, bool on) {
  digitalWrite(CE_PIN[rail], on ? HIGH : LOW);
  ce[rail] = on;
}

static void ce_all_off() { set_ce(1, false); set_ce(2, false); }

// Shift 16 bits: U2 byte (holes 9-16) first, then U1 (holes 1-8), MSB first.
static void shift_raw(uint16_t bits) {
  shiftOut(PIN_DATA, PIN_CLOCK, MSBFIRST, highByte(bits));
  shiftOut(PIN_DATA, PIN_CLOCK, MSBFIRST, lowByte(bits));
}

static void latch(uint16_t bits) {
  digitalWrite(PIN_LATCH, LOW);
  shift_raw(bits);
  digitalWrite(PIN_LATCH, HIGH);
  mask = bits;
}

static uint8_t bit_count(uint16_t v) {
  uint8_t n = 0;
  for (; v; v &= v - 1) n++;
  return n;
}

static uint8_t single_hole(uint16_t v) {
  if (bit_count(v) != 1) return 0;
  uint8_t h = 1;
  while (!(v & 1)) { v >>= 1; h++; }
  return h;
}

uint8_t optics_rail_of(uint8_t hole) { return hole >= RAIL_B_FIRST_HOLE ? 2 : 1; }
uint16_t optics_wdt_ms(uint8_t rail) { return wdt_ms[rail]; }
uint16_t optics_mask() { return mask; }
bool optics_ce(uint8_t rail) { return ce[rail]; }
bool optics_any_ce() { return ce[1] || ce[2]; }

uint8_t optics_lit_hole() {
  uint8_t h = single_hole(mask);
  return (h && ce[optics_rail_of(h)]) ? h : 0;
}

void optics_init() {
  // Power-up dark state (LIO-ELEC-001 §3.6): the 595s come up random, so the
  // CE lines are driven low before the registers are cleared.
  digitalWrite(PIN_CE1, LOW);
  digitalWrite(PIN_CE2, LOW);
  pinMode(PIN_CE1, OUTPUT);
  pinMode(PIN_CE2, OUTPUT);
  ce[1] = ce[2] = false;
  pinMode(PIN_DATA, OUTPUT);
  pinMode(PIN_CLOCK, OUTPUT);
  pinMode(PIN_LATCH, OUTPUT);
  latch(0);
  pinMode(PIN_LOOP, INPUT_PULLUP);  // reads HIGH unless the §6.3 jumper drives it
}

void optics_off() {
  ce_all_off();
  latch(0);
}

static void start_timer(uint32_t req_ms, uint8_t rail) {
  uint32_t lim = wdt_ms[rail];
  lit_by_wdt = (req_ms == 0 || req_ms >= lim);
  lit_for = lit_by_wdt ? lim : req_ms;
  lit_at = millis();
}

uint8_t optics_ch_on(uint8_t hole, uint32_t ms, uint32_t &until_ms) {
  if (hole < 1 || hole > N_HOLES) return E_ARG;
  if (motors_moving()) return E_BUSY;
  uint8_t rail = optics_rail_of(hole);
  ce_all_off();                         // drop CE before changing the selection
  latch((uint16_t)1 << (hole - 1));     // select the MOSFET ...
  start_timer(ms, rail);
  set_ce(rail, true);                   // ... then enable the driver
  until_ms = lit_for;
  return 0;
}

void optics_tick() {
  if (!optics_any_ce() || millis() - lit_at < lit_for) return;
  uint8_t h = single_hole(mask);
  uint32_t on_ms = millis() - lit_at;
  optics_off();
  if (lit_by_wdt) {
    wdt_trip_count();
    event_begin(F("WDT"));
  } else {
    event_begin(F("OFF"));
  }
  resp_kv(F("ch"), h);
  resp_kv_u(F("on_ms"), on_ms);
  Serial.print(F(" off"));
  resp_end();
}

// SR RAW <hex16>: CE is forced low first and stays low.
void cmd_sr(const Command &c) {
  uint16_t m;
  if (c.ntok < 3 || !tok_is(c.tok[1], F("RAW")) || !parse_hex16(c.tok[2], m)) {
    resp_err(c, E_ARG, F("usage: SR RAW <hex16>"));
    return;
  }
  ce_all_off();
  latch(m);
  resp_ok(c);
  resp_kv_hex16(F("mask"), mask);
  resp_end();
}

// CE <1|2> <0|1>: raising CE needs exactly one selected hole on that rail.
void cmd_ce(const Command &c) {
  long rail, on;
  if (!arg_long(c, 1, 1, 2, rail) || !arg_long(c, 2, 0, 1, on)) {
    resp_err(c, E_ARG, F("usage: CE <1|2> <0|1>"));
    return;
  }
  if (on) {
    uint8_t h = single_hole(mask);
    if (motors_moving()) { resp_err(c, E_BUSY, F("motor moving")); return; }
    if (!h || optics_rail_of(h) != rail) {
      resp_err(c, E_REFUSED, F("needs exactly one selected hole on this rail"));
      return;
    }
    start_timer(0, (uint8_t)rail);
    set_ce((uint8_t)rail, true);
  } else {
    set_ce((uint8_t)rail, false);
  }
  resp_ok(c);
  resp_kv(F("rail"), rail);
  resp_kv(F("on"), on);
  if (on) resp_kv_u(F("until_ms"), lit_for);
  resp_end();
}

// CH <1-16> ON [ms]
void cmd_ch(const Command &c) {
  long hole, ms = 0;
  if (!arg_long(c, 1, 1, N_HOLES, hole) || c.ntok < 3 || !tok_is(c.tok[2], F("ON")) ||
      (c.ntok > 3 && !arg_long(c, 3, 1, 600000L, ms))) {
    resp_err(c, E_ARG, F("usage: CH <1-16> ON [ms]"));
    return;
  }
  uint32_t until;
  uint8_t e = optics_ch_on((uint8_t)hole, (uint32_t)ms, until);
  if (e == E_BUSY) { resp_err(c, E_BUSY, F("motor moving")); return; }
  if (e) { resp_err(c, (ErrCode)e, F("refused")); return; }
  resp_ok(c);
  resp_kv(F("ch"), hole);
  resp_kv_P(F("rail"), optics_rail_of((uint8_t)hole) == 1 ? F("A") : F("B"));
  resp_kv_u(F("until_ms"), until);
  resp_kv(F("clamped"), ms > 0 && (uint32_t)ms > until ? 1 : 0);
  resp_end();
}

void cmd_off(const Command &c) {
  optics_off();
  resp_ok(c);
  resp_end();
}

struct MeasRec {
  int16_t dark0, dark1, lit0, lit1;
  uint16_t t_on_ms;
};

static const __FlashStringHelper *meas_err_msg = nullptr;

// Atomic measurement (LIO-ELEC-001 §14.1): dark read -> CH on -> settle ->
// lit read -> off. ADS A0 = InGaAs TIA, A1 = OPT101.
static uint8_t do_meas(uint8_t hole, uint16_t settle, uint8_t n, MeasRec &r) {
  if (motors_moving()) { meas_err_msg = F("motor moving"); return E_BUSY; }
  uint32_t est = settle + 2UL * n * (adc_conv_us() / 1000UL + 2) + 10;
  if (est > wdt_ms[optics_rail_of(hole)]) { meas_err_msg = F("on-time exceeds watchdog"); return E_REFUSED; }
  optics_off();
  service_delay(settle);
  meas_err_msg = F("adc read failed");
  if (adc_read_mean(0, n, r.dark0) || adc_read_mean(1, n, r.dark1)) { optics_off(); return E_ADC; }
  uint32_t until;
  uint8_t e = optics_ch_on(hole, 0, until);
  if (e) { meas_err_msg = F("ch on refused"); return e; }
  uint32_t t0 = millis();
  service_delay(settle);
  e = adc_read_mean(0, n, r.lit0) || adc_read_mean(1, n, r.lit1);
  bool still_lit = optics_lit_hole() == hole;
  r.t_on_ms = (uint16_t)(millis() - t0);
  optics_off();
  if (e) return E_ADC;
  if (!still_lit) { meas_err_msg = F("watchdog fired during measurement"); return E_REFUSED; }
  return 0;
}

static bool meas_args(const Command &c, uint8_t first, long &settle, long &n) {
  settle = SETTLE_MS_DEFAULT;
  n = 1;
  if (c.ntok > first && !arg_long(c, first, 0, SETTLE_MS_MAX, settle)) return false;
  if (c.ntok > first + 1 && !arg_long(c, first + 1, 1, MEAS_N_MAX, n)) return false;
  return true;
}

static void print_meas(uint8_t hole, const MeasRec &r) {
  resp_kv(F("ch"), hole);
  resp_kv(F("dark0"), r.dark0);
  resp_kv(F("dark1"), r.dark1);
  resp_kv(F("lit0"), r.lit0);
  resp_kv(F("lit1"), r.lit1);
  resp_kv(F("t_on_ms"), r.t_on_ms);
}

// MEAS <1-16> [settle_ms] [n]
void cmd_meas(const Command &c) {
  long hole, settle, n;
  if (!arg_long(c, 1, 1, N_HOLES, hole) || !meas_args(c, 2, settle, n)) {
    resp_err(c, E_ARG, F("usage: MEAS <1-16> [settle_ms] [n]"));
    return;
  }
  MeasRec r;
  uint8_t e = do_meas((uint8_t)hole, (uint16_t)settle, (uint8_t)n, r);
  if (e) { resp_err(c, (ErrCode)e, meas_err_msg); return; }
  resp_ok(c);
  print_meas((uint8_t)hole, r);
  resp_kv(F("settle_ms"), settle);
  resp_kv(F("n"), n);
  resp_end();
}

// SWEEP [settle_ms] [n]: "# M ..." per hole 1-16, then OK.
void cmd_sweep(const Command &c) {
  long settle, n;
  if (!meas_args(c, 1, settle, n)) { resp_err(c, E_ARG, F("usage: SWEEP [settle_ms] [n]")); return; }
  uint32_t t0 = millis();
  for (uint8_t h = 1; h <= N_HOLES; h++) {
    MeasRec r;
    uint8_t e = do_meas(h, (uint16_t)settle, (uint8_t)n, r);
    if (e) { optics_off(); resp_err(c, (ErrCode)e, meas_err_msg); return; }
    event_begin(F("M"));
    print_meas(h, r);
    resp_end();
  }
  resp_ok(c);
  resp_kv(F("n"), N_HOLES);
  resp_kv(F("settle_ms"), settle);
  resp_kv(F("samples"), n);
  resp_kv_u(F("dur_ms"), millis() - t0);
  resp_end();
}

// LOOP TEST (§6.3, optional jumper U2 pin 9 -> D11). Patterns are shifted in
// but never latched, so the outputs stay dark; CE is held low throughout.
void cmd_loop(const Command &c) {
  if (c.ntok < 2 || !tok_is(c.tok[1], F("TEST"))) { resp_err(c, E_ARG, F("usage: LOOP TEST")); return; }
  optics_off();
  uint16_t ok = 0, bad = 0;
  bool saw_low = false;
  uint16_t lfsr = 0xACE1;
  for (uint8_t p = 0; p < 32; p++) {
    uint16_t pat;
    if (p == 0) pat = 0x0000;
    else if (p == 1) pat = 0xFFFF;
    else if (p == 2) pat = 0xAAAA;
    else if (p == 3) pat = 0x5555;
    else { lfsr = (lfsr >> 1) ^ (-(lfsr & 1u) & 0xB400u); pat = lfsr; }
    shift_raw(pat);
    for (int8_t b = 15; b >= 0; b--) {
      bool v = digitalRead(PIN_LOOP);
      if (!v) saw_low = true;
      if (v == (bool)((pat >> b) & 1)) ok++; else bad++;
      digitalWrite(PIN_DATA, LOW);   // clock the next bit out of U2 Q7'
      digitalWrite(PIN_CLOCK, HIGH);
      digitalWrite(PIN_CLOCK, LOW);
    }
    service();
  }
  latch(0);
  resp_ok(c);
  resp_kv(F("fitted"), saw_low ? 1 : 0);
  resp_kv(F("pass"), saw_low && bad == 0 ? 1 : 0);
  resp_kv(F("bits_ok"), ok);
  resp_kv(F("bits_bad"), bad);
  if (!saw_low) resp_kv_P(F("status"), F("not_fitted"));
  resp_end();
}

// WDT CFG A|B <ms>
void cmd_wdt(const Command &c) {
  long ms;
  uint8_t rail = 0;
  if (c.ntok >= 4 && tok_is(c.tok[1], F("CFG"))) {
    if (tok_is(c.tok[2], F("A"))) rail = 1;
    else if (tok_is(c.tok[2], F("B"))) rail = 2;
  }
  uint16_t cap = rail == 1 ? WDT_A_CAP_MS : WDT_B_CAP_MS;
  if (!rail || !arg_long(c, 3, WDT_MIN_MS, cap, ms)) {
    resp_err(c, E_ARG, F("usage: WDT CFG A|B <ms> within the hard cap"));
    return;
  }
  wdt_ms[rail] = (uint16_t)ms;
  resp_ok(c);
  resp_kv_P(F("rail"), rail == 1 ? F("A") : F("B"));
  resp_kv(F("ms"), ms);
  resp_kv(F("cap_ms"), cap);
  resp_end();
}
