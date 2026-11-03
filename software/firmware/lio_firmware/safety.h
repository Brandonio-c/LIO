// ===== Safety: background service, comms-loss failsafe, motion arming, reset =====
#pragma once
#include <Arduino.h>
#include "protocol.h"

// Sticky fault flags reported in STATUS faults= (cleared only by RESET).
enum FaultBit : uint8_t {
  F_ADC_MISSING = 0x01,  // ADS1115 did not answer at boot
  F_I2C_ERROR   = 0x02,  // an I2C transfer failed or timed out
  F_WDT_TRIP    = 0x04,  // an LED on-time watchdog fired
  F_FAILSAFE    = 0x08,  // the comms-loss failsafe fired
};

void safety_init();      // arm token, optional hardware watchdog
void service();          // call every loop iteration and inside every wait
void service_delay(uint32_t ms);  // delay() that keeps service() running

void fault_set(uint8_t bits);
uint8_t faults();
uint16_t wdt_trips();
void wdt_trip_count();
uint16_t failsafe_trips();

bool motion_armed();
uint32_t armed_remaining_ms();
uint16_t arm_token();
void disarm();

void cmd_motor_arm(const Command &c);   // MOTOR ARM <token>
void cmd_reset(const Command &c);       // RESET
