// Nano R4 pin check: hold A0-A5 high and light the onboard L LED (D13).
void setup() {
  const uint8_t p[] = {A0, A1, A2, A3, A4, A5, 13};
  for (uint8_t i = 0; i < sizeof p; i++) { pinMode(p[i], OUTPUT); digitalWrite(p[i], HIGH); }
}
void loop() {}
