// ===== ADS1115 at 0x48: ADS A0 = InGaAs TIA (via 10k), A1 = OPT101, A2/A3 n.c. =====
#pragma once
#include <Arduino.h>
#include "protocol.h"

bool adc_init();             // Wire + ADS1115 at GAIN_ONE, 128 SPS
bool adc_present();
const __FlashStringHelper *adc_gain_name();
uint16_t adc_rate_sps();
float adc_lsb_mv();
uint32_t adc_conv_us();      // nominal single-shot conversion time

// Blocking single-ended read that keeps service() running while it waits.
// Returns 0, or E_ADC on an I2C error / timeout.
uint8_t adc_read(uint8_t ch, int16_t &raw);
// Mean of n reads (integer counts, rounded). Returns 0 or E_ADC.
uint8_t adc_read_mean(uint8_t ch, uint8_t n, int16_t &mean);

void cmd_adc(const Command &c);  // ADC READ | CFG | STREAM
void cmd_i2c(const Command &c);  // I2C SCAN
