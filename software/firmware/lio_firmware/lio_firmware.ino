// ===== LIO V3 firmware v2 — command-driven optics + motors (protocol 1) =====
// Board: Arduino Nano (ATmega328P). Libraries: Adafruit ADS1X15, Adafruit BusIO.
// Protocol: docs/PROTOCOL.md. Pin map: electronics/data/nano_pinmap.csv.
// The previous TEST_MODE firmware is in ../legacy/lio_firmware_testmode/
// (git tag fw-testmode-v1).
#include "config.h"
#include "adc.h"
#include "motors.h"
#include "optics.h"
#include "protocol.h"
#include "safety.h"

static Command cmd;

// __DATE__ is "Mmm dd yyyy"; print it as yyyy-mm-dd.
static void print_build_date() {
  static const char months[] PROGMEM = "JanFebMarAprMayJunJulAugSepOctNovDec";
  const char *d = __DATE__;
  uint8_t mon = 1;
  for (uint8_t i = 0; i < 12; i++) {
    if (strncmp_P(d, months + 3 * i, 3) == 0) { mon = i + 1; break; }
  }
  Serial.print(d + 7);
  Serial.print('-');
  if (mon < 10) Serial.print('0');
  Serial.print(mon);
  Serial.print('-');
  Serial.print(d[4] == ' ' ? '0' : d[4]);
  Serial.print(d[5]);
}

static void cmd_ping(const Command &c) {
  resp_ok(c);
  resp_kv_u(F("uptime_ms"), millis());
  resp_end();
}

static void cmd_info(const Command &c) {
  resp_ok(c);
  resp_kv_P(F("fw"), F(LIO_FW_VERSION));
  resp_kv(F("proto"), LIO_PROTO);
  Serial.print(F(" build="));
  print_build_date();
  resp_kv_hex8(F("adc_addr"), ADC_ADDR);
  resp_kv(F("adc_ok"), adc_present() ? 1 : 0);
  resp_kv_P(F("gain"), adc_gain_name());
  resp_kv(F("rate"), adc_rate_sps());
  resp_kv(F("settle_ms"), SETTLE_MS_DEFAULT);
  resp_kv(F("wdt_a_ms"), optics_wdt_ms(1));
  resp_kv(F("wdt_b_ms"), optics_wdt_ms(2));
  resp_kv(F("wdt_a_cap_ms"), WDT_A_CAP_MS);
  resp_kv(F("wdt_b_cap_ms"), WDT_B_CAP_MS);
  resp_kv_u(F("comms_ms"), COMMS_TIMEOUT_MS);
  resp_kv_u(F("arm_ms"), ARM_DURATION_MS);
  resp_kv(F("step_max"), MOTOR_STEP_MAX);
  resp_kv(F("jog_max"), JOG_MAX_STEPS);
  resp_kv(F("jog_v_max"), JOG_SPEED_MAX);
  resp_kv(F("jog_acc_max"), JOG_ACC_MAX);
  resp_kv(F("motion_armed"), motion_armed() ? 1 : 0);
  resp_kv_hex16(F("arm_token"), arm_token());
  resp_kv(F("hw_wdt"), LIO_HW_WDT);
  resp_end();
}

static void cmd_status(const Command &c) {
  resp_ok(c);
  resp_kv(F("ch"), optics_lit_hole());
  resp_kv(F("ce1"), optics_ce(1) ? 1 : 0);
  resp_kv(F("ce2"), optics_ce(2) ? 1 : 0);
  resp_kv_hex16(F("mask"), optics_mask());
  resp_kv_P(F("motor1"), motor_state(0));
  resp_kv_P(F("motor2"), motor_state(1));
  resp_kv(F("pos1"), motor_pos(0));
  resp_kv(F("pos2"), motor_pos(1));
  resp_kv(F("armed"), motion_armed() ? 1 : 0);
  resp_kv_u(F("armed_ms"), armed_remaining_ms());
  resp_kv(F("va"), jog_va());
  resp_kv(F("vs"), jog_vs());
  resp_kv(F("acc"), jog_acc());
  resp_kv_hex8(F("faults"), faults());
  resp_kv(F("wdt_trips"), wdt_trips());
  resp_kv(F("failsafe_trips"), failsafe_trips());
  resp_end();
}

static void dispatch(const Command &c) {
  const char *t = c.tok[0];
  if (tok_is(t, F("PING"))) cmd_ping(c);
  else if (tok_is(t, F("INFO"))) cmd_info(c);
  else if (tok_is(t, F("STATUS"))) cmd_status(c);
  else if (tok_is(t, F("I2C"))) cmd_i2c(c);
  else if (tok_is(t, F("ADC"))) cmd_adc(c);
  else if (tok_is(t, F("SR"))) cmd_sr(c);
  else if (tok_is(t, F("CE"))) cmd_ce(c);
  else if (tok_is(t, F("CH"))) cmd_ch(c);
  else if (tok_is(t, F("OFF"))) cmd_off(c);
  else if (tok_is(t, F("MEAS"))) cmd_meas(c);
  else if (tok_is(t, F("SWEEP"))) cmd_sweep(c);
  else if (tok_is(t, F("LOOP"))) cmd_loop(c);
  else if (tok_is(t, F("MOTOR"))) cmd_motor(c);
  else if (tok_is(t, F("WDT"))) cmd_wdt(c);
  else if (tok_is(t, F("RESET"))) cmd_reset(c);
  else if (!cmd_legacy(c)) resp_err(c, E_UNKNOWN, F("unknown command"));
}

void setup() {
  optics_init();   // first: CE1 = CE2 = LOW, 595s cleared (§4.3)
  motors_init();   // coils released
  Serial.begin(115200);
  adc_init();
  safety_init();
  Serial.println();
  Serial.print(F("# BOOT name=lio fw=" LIO_FW_VERSION));
  resp_kv(F("proto"), LIO_PROTO);
  Serial.print(F(" build="));
  print_build_date();
  resp_kv(F("adc_ok"), adc_present() ? 1 : 0);
  resp_kv(F("hw_wdt"), LIO_HW_WDT);
  resp_end();
}

void loop() {
  if (proto_poll(cmd)) dispatch(cmd);
  service();
}
