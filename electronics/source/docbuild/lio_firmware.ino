// ===== LIO V3 optical head — test & sweep firmware (LIO-ELEC-001 Rev A) =====
// Board: Arduino Nano. Library: Adafruit ADS1X15.
// Set TEST_MODE, upload, open Serial Monitor at 115200 baud.
#include <Wire.h>
#include <Adafruit_ADS1X15.h>

Adafruit_ADS1115 ads;

const int DATA  = A0;   // U1 pin 14 (SER)
const int CLOCK = A1;   // U1 + U2 pin 11 (SRCLK)
const int LATCH = A2;   // U1 + U2 pin 12 (RCLK)
const int CE1   = A3;   // DRV1 enable -> RAIL A (holes 1-9)
const int CE2   = 10;   // DRV2 enable -> RAIL B (holes 10-16)

const int SETTLE_MS = 8;   // wait after switching before reading
#define TEST_MODE 5        // 1=I2C scan 2=detectors 3=walk 4=one LED 5=sweep

// hole index 0..15 ; holes 10-16 (index 9..15) are on RAIL B
// If white/pink LEDs are fitted in holes 10-11 on RAIL A, use: return h >= 11;
bool isRailB(int h) { return h >= 9; }

// Select exactly one hole (0..15), or -1 for none.
void setHole(int h) {
  uint16_t bits = (h < 0) ? 0 : (1u << h);
  digitalWrite(LATCH, LOW);
  shiftOut(DATA, CLOCK, MSBFIRST, highByte(bits));  // U2 (holes 9-16) first
  shiftOut(DATA, CLOCK, MSBFIRST, lowByte(bits));   // then U1 (holes 1-8)
  digitalWrite(LATCH, HIGH);
}

void driversOff()        { digitalWrite(CE1, LOW); digitalWrite(CE2, LOW); }
void driverOnFor(int h)  { digitalWrite(isRailB(h) ? CE2 : CE1, HIGH); }

// MOSFET first, then driver enable.
void lightHole(int h) { driversOff(); setHole(h); driverOnFor(h); }
void allOff()         { driversOff(); setHole(-1); }

void readBoth(int16_t &ingaas, int16_t &opt101) {
  ingaas = ads.readADC_SingleEnded(0);   // ADS A0 = TIA output
  opt101 = ads.readADC_SingleEnded(1);   // ADS A1 = OPT101
}

void setup() {
  Serial.begin(115200);
  pinMode(DATA, OUTPUT); pinMode(CLOCK, OUTPUT); pinMode(LATCH, OUTPUT);
  pinMode(CE1, OUTPUT);  pinMode(CE2, OUTPUT);
  allOff();                       // first action: everything dark
  Wire.begin();

#if TEST_MODE == 1
  Serial.println(F("I2C scan:"));
  for (byte a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) { Serial.print(F("found 0x")); Serial.println(a, HEX); }
  }
  Serial.println(F("done"));
#else
  if (!ads.begin(0x48)) { Serial.println(F("ADS1115 not found - check wiring")); while (1); }
  ads.setGain(GAIN_ONE);          // +/-4.096 V full scale, 125 uV per count
  Serial.println(F("ADS1115 ok"));
#endif
}

void loop() {
#if TEST_MODE == 1
  // scan ran once in setup()

#elif TEST_MODE == 2      // live detector readings
  int16_t ig, op; readBoth(ig, op);
  Serial.print(F("InGaAs(A0)=")); Serial.print(ig);
  Serial.print(F("  OPT101(A1)=")); Serial.println(op);
  delay(300);

#elif TEST_MODE == 3      // walk every channel
  for (int h = 0; h < 16; h++) {
    lightHole(h);
    Serial.print(F("hole ")); Serial.println(h + 1);
    delay(400);
  }
  allOff(); delay(400);

#elif TEST_MODE == 4      // hole 8 (850 nm) pulse, for current setting
  lightHole(7); Serial.println(F("hole 8 ON"));  delay(2000);
  allOff();     Serial.println(F("hole 8 OFF")); delay(3000);

#elif TEST_MODE == 5      // full sweep with dark subtraction, CSV output
  Serial.println(F("hole,dark_ingaas,dark_opt101,ingaas,opt101"));
  for (int h = 0; h < 16; h++) {
    int16_t di, dop, ig, op;
    allOff();      delay(SETTLE_MS); readBoth(di, dop);   // dark
    lightHole(h);  delay(SETTLE_MS); readBoth(ig, op);    // lit
    allOff();
    Serial.print(h + 1); Serial.print(',');
    Serial.print(di);    Serial.print(','); Serial.print(dop); Serial.print(',');
    Serial.print(ig);    Serial.print(','); Serial.println(op);
  }
  Serial.println(F("END"));
  delay(2000);
#endif
}
