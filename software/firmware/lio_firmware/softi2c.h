// ===== Software (bit-banged) I2C master on any two digital pins =====
// The Nano's hardware I2C pins (A4/A5) may be unusable (see config.h), so the
// ADS1115 is driven from PIN_SDA/PIN_SCL. The lines are open-drain: a pin is
// either driven LOW or released (input, internal pull-up on), never driven
// HIGH, so nothing on the bus is fought. External 4.7k pull-ups are expected.
#pragma once
#include <Arduino.h>

// Results, numbered like Wire.endTransmission() so that I2C DIAG reads the same:
const uint8_t SI2C_OK = 0;
const uint8_t SI2C_NACK_ADDR = 2;   // no device answered its address
const uint8_t SI2C_NACK_DATA = 3;   // the device refused a data byte
const uint8_t SI2C_BUS_ERROR = 4;   // a line was low when the bus should be free
const uint8_t SI2C_TIMEOUT = 5;     // SCL never rose (held low, or no pull-up)

void si2c_begin();                  // release both lines, then free a stuck bus
void si2c_recover();                // up to 9 clocks until SDA is released, then STOP
bool si2c_sda_high();
bool si2c_scl_high();
// Write n bytes (n may be 0: an address probe) / read n bytes (n >= 1).
uint8_t si2c_write(uint8_t addr, const uint8_t *buf, uint8_t n);
uint8_t si2c_read(uint8_t addr, uint8_t *buf, uint8_t n);
uint32_t si2c_hz();                 // nominal clock from SI2C_HALF_US
