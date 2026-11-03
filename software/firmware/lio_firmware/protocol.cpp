#include "protocol.h"

static char line[LINE_MAX + 1];
static uint8_t line_len = 0;
static bool line_overflow = false;
static uint32_t last_rx_ms = 0;

uint32_t proto_last_rx_ms() { return last_rx_ms; }

static void tokenize(Command &cmd) {
  cmd.ntok = 0;
  cmd.seq = -1;
  char *p = line;
  while (*p && cmd.ntok < TOK_MAX) {
    while (*p == ' ' || *p == '\t') *p++ = '\0';
    if (!*p) break;
    cmd.tok[cmd.ntok++] = p;
    while (*p && *p != ' ' && *p != '\t') p++;
  }
  if (cmd.ntok > 0 && cmd.tok[0][0] == '@') {
    long s;
    if (parse_long(cmd.tok[0] + 1, s) && s >= 0) cmd.seq = s;
    for (uint8_t i = 1; i < cmd.ntok; i++) cmd.tok[i - 1] = cmd.tok[i];
    cmd.ntok--;
  }
}

bool proto_poll(Command &cmd) {
  while (Serial.available() > 0) {
    char ch = (char)Serial.read();
    last_rx_ms = millis();
    if (ch == '\r') continue;
    if (ch == '\n') {
      if (line_overflow) {
        line_overflow = false;
        line_len = 0;
        Serial.print(F("ERR ? code="));
        Serial.print((int)E_OVERFLOW);
        Serial.println(F(" msg=line too long"));
        continue;
      }
      if (line_len == 0) continue;
      line[line_len] = '\0';
      line_len = 0;
      tokenize(cmd);
      if (cmd.ntok == 0) continue;  // "@5" alone
      return true;
    }
    if (line_overflow) continue;
    if (line_len >= LINE_MAX) { line_overflow = true; continue; }
    if (ch == '\0') ch = '?';
    if (ch >= 'a' && ch <= 'z') ch -= 'a' - 'A';
    line[line_len++] = ch;
  }
  return false;
}

static void print_seq(const Command &c) {
  if (c.seq >= 0) { Serial.print('@'); Serial.print(c.seq); Serial.print(' '); }
}

void resp_ok(const Command &c) {
  print_seq(c);
  Serial.print(F("OK "));
  Serial.print(c.tok[0]);
}

void resp_err(const Command &c, ErrCode code, const __FlashStringHelper *msg) {
  print_seq(c);
  Serial.print(F("ERR "));
  Serial.print(c.ntok ? c.tok[0] : "?");
  Serial.print(F(" code="));
  Serial.print((int)code);
  Serial.print(F(" msg="));  // msg is always last; it may contain spaces
  Serial.println(msg);
}

void resp_end() { Serial.println(); }

void event_begin(const __FlashStringHelper *name) {
  Serial.print(F("# "));
  Serial.print(name);
}

static void key(const __FlashStringHelper *k) {
  Serial.print(' ');
  Serial.print(k);
  Serial.print('=');
}

void resp_kv(const __FlashStringHelper *k, long v) { key(k); Serial.print(v); }
void resp_kv_u(const __FlashStringHelper *k, unsigned long v) { key(k); Serial.print(v); }
void resp_kv_f(const __FlashStringHelper *k, float v, uint8_t d) { key(k); Serial.print(v, d); }
void resp_kv_s(const __FlashStringHelper *k, const char *v) { key(k); Serial.print(v); }
void resp_kv_P(const __FlashStringHelper *k, const __FlashStringHelper *v) { key(k); Serial.print(v); }

static void hex_digits(uint16_t v, uint8_t n) {
  for (int8_t i = n - 1; i >= 0; i--) Serial.print((v >> (4 * i)) & 0xF, HEX);
}

void resp_kv_hex16(const __FlashStringHelper *k, uint16_t v) {
  key(k); Serial.print(F("0x")); hex_digits(v, 4);
}

void resp_kv_hex8(const __FlashStringHelper *k, uint8_t v) {
  key(k); Serial.print(F("0x")); hex_digits(v, 2);
}

bool tok_is(const char *t, const __FlashStringHelper *s) {
  return strcmp_P(t, (const char *)s) == 0;
}

bool parse_long(const char *s, long &out) {
  if (!s || !*s) return false;
  bool neg = false;
  if (*s == '+' || *s == '-') { neg = (*s == '-'); s++; }
  if (!*s) return false;
  long v = 0;
  for (; *s; s++) {
    if (*s < '0' || *s > '9') return false;
    if (v > 100000000L) return false;  // keep well inside int32
    v = v * 10 + (*s - '0');
  }
  out = neg ? -v : v;
  return true;
}

bool parse_hex16(const char *s, uint16_t &out) {
  if (!s || !*s) return false;
  if (s[0] == '0' && s[1] == 'X') s += 2;
  uint8_t n = 0;
  uint16_t v = 0;
  for (; *s; s++, n++) {
    char ch = *s;
    uint8_t d;
    if (ch >= '0' && ch <= '9') d = ch - '0';
    else if (ch >= 'A' && ch <= 'F') d = ch - 'A' + 10;
    else return false;
    if (n >= 4) return false;
    v = (v << 4) | d;
  }
  if (n == 0) return false;
  out = v;
  return true;
}

bool arg_long(const Command &c, uint8_t i, long lo, long hi, long &out) {
  long v;
  if (i >= c.ntok || !parse_long(c.tok[i], v) || v < lo || v > hi) return false;
  out = v;
  return true;
}
