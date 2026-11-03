// ===== Line protocol: framing, tokenizer, response helpers (docs/PROTOCOL.md) =====
#pragma once
#include <Arduino.h>
#include "config.h"

enum ErrCode : uint8_t {
  E_UNKNOWN  = 1,  // unknown command
  E_ARG      = 2,  // bad argument
  E_REFUSED  = 3,  // refused by a safety rule
  E_ADC      = 4,  // I2C / ADC error
  E_BUSY     = 5,  // busy (motor moving)
  E_OVERFLOW = 6,  // line longer than LINE_MAX
};

struct Command {
  char *tok[TOK_MAX];  // upper-cased tokens; tok[0] is the command word
  uint8_t ntok;
  long seq;            // value of a leading "@<n>", or -1
};

// Reads available serial bytes. Returns true when a complete command line
// is in cmd. Over-length lines are answered with ERR code=6 here.
bool proto_poll(Command &cmd);
uint32_t proto_last_rx_ms();

// Responses: exactly one OK or ERR line per command.
//   resp_ok(c); resp_kv(F("ch"), 3); ...; resp_end();
void resp_ok(const Command &c);
void resp_err(const Command &c, ErrCode code, const __FlashStringHelper *msg);
void resp_end();

// Asynchronous / streamed lines: "# <NAME> k=v ...", terminated by resp_end().
void event_begin(const __FlashStringHelper *name);

void resp_kv(const __FlashStringHelper *k, long v);
void resp_kv_u(const __FlashStringHelper *k, unsigned long v);
void resp_kv_hex16(const __FlashStringHelper *k, uint16_t v);
void resp_kv_hex8(const __FlashStringHelper *k, uint8_t v);
void resp_kv_f(const __FlashStringHelper *k, float v, uint8_t digits);
void resp_kv_s(const __FlashStringHelper *k, const char *v);
void resp_kv_P(const __FlashStringHelper *k, const __FlashStringHelper *v);

// Argument helpers. tok_is() compares an (upper-cased) token to a flash string.
bool tok_is(const char *t, const __FlashStringHelper *s);
bool parse_long(const char *s, long &out);
bool parse_hex16(const char *s, uint16_t &out);
// Parses c.tok[i] as an integer in [lo, hi]. Missing -> false.
bool arg_long(const Command &c, uint8_t i, long lo, long hi, long &out);
