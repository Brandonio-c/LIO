// LIO port C self-test: reports each A0–A5 pin's voltage in 4 states
const uint8_t pins[6] = {A0, A1, A2, A3, A4, A5};
float vcc;
float readVcc() {                         // AVCC measured against the internal 1.1 V bandgap
  ADMUX = _BV(REFS0) | 0x0E; delay(3);
  ADCSRA |= _BV(ADSC); while (ADCSRA & _BV(ADSC));
  return 1.1 * 1023.0 / ADC;
}
float vpin(uint8_t p) { analogRead(p); return analogRead(p) * vcc / 1023.0; }
void setup() {
  pinMode(10, OUTPUT); digitalWrite(10, LOW);       // CE2 held off
  Serial.begin(115200); delay(500);
  vcc = readVcc(); analogRead(A0);
  Serial.print(F("AVCC/Vcc = ")); Serial.print(vcc, 3); Serial.println(F(" V"));
  Serial.println(F("pin float_V pullup_V high_V low_V estR_to_GND verdict"));
  for (uint8_t i = 0; i < 6; i++) {
    uint8_t p = pins[i];
    pinMode(p, INPUT);        delay(5); float vf = vpin(p);
    pinMode(p, INPUT_PULLUP); delay(5); float vu = vpin(p);
    pinMode(p, OUTPUT); digitalWrite(p, HIGH); float vh = vpin(p);   // HIGH for <1 ms
    digitalWrite(p, LOW);                     float vl = vpin(p);
    pinMode(p, INPUT);
    float r = (vu < vcc - 0.05) ? 35000.0 * vu / (vcc - vu) : 1e9;  // rough: pull-up ≈35 kΩ
    const char* v = (vh > 0.9 * vcc) ? "DRIVES OK"
                  : (vu > 0.5 * vcc) ? "DRIVER DAMAGED"
                  : "STRONG LOAD/SHORT TO GND";
    Serial.print('A'); Serial.print(i); Serial.print(' ');
    Serial.print(vf, 2); Serial.print(' '); Serial.print(vu, 2); Serial.print(' ');
    Serial.print(vh, 2); Serial.print(' '); Serial.print(vl, 2); Serial.print(' ');
    if (r > 1e8) Serial.print(F(">1M")); else { Serial.print(r / 1000, 1); Serial.print('k'); }
    Serial.print(' '); Serial.println(v);
  }
}
void loop() {}
