// ===== LIO V3 firmware v2 — pins, limits, version =====
// Pin map: electronics/data/nano_pinmap.csv (LIO-ELEC-001 Rev A, §4).
// Every limit below is mirrored in software/config/lio_hw.yaml; the host
// cross-checks them against INFO (test T02.3). Change both together.
#pragma once
#include <Arduino.h>

#define LIO_FW_VERSION "2.2.0"
#define LIO_PROTO 1

// Build with -DLIO_HW_WDT=1 only for the new (Optiboot) bootloader,
// FQBN arduino:avr:nano:cpu=atmega328. The old bootloader loops forever
// after a watchdog reset.
#ifndef LIO_HW_WDT
#define LIO_HW_WDT 0
#endif

// ---- Optics: 2x 74HC595 chain + LD06AJSA enables ----
const uint8_t PIN_DATA  = A0;  // U1 pin 14 (SER)
const uint8_t PIN_CLOCK = A1;  // U1 + U2 pin 11 (SRCLK)
const uint8_t PIN_LATCH = A2;  // U1 + U2 pin 12 (RCLK)
const uint8_t PIN_CE1   = A3;  // DRV1 CE -> RAIL A (holes 1-9), 10k pull-down
const uint8_t PIN_CE2   = 10;  // DRV2 CE -> RAIL B (holes 10-16), 10k pull-down
// The optional loop-back jumper (U2 pin 9 Q7' -> D11, plan §6.3) is not
// available: D11 now carries I2C SDA. 0 = no loop-back input; LOOP TEST then
// reports not_fitted without touching any pin.
const uint8_t PIN_LOOP  = 0;

const uint8_t N_HOLES = 16;
const uint8_t RAIL_B_FIRST_HOLE = 10;  // holes 10-16 on RAIL B

// ---- ADS1115 over software I2C (softi2c.h) ----
// This board's Nano has damaged hardware I2C pins (A4/A5 read low with nothing
// attached), so the bus runs on two spare digital pins instead. External 4.7k
// pull-ups to +5 V on both lines.
const uint8_t ADC_ADDR = 0x48;
const uint8_t PIN_SDA = 11;             // ADS1115 SDA
const uint8_t PIN_SCL = 12;             // ADS1115 SCL
const uint8_t SI2C_HALF_US = 2;         // half bit time: about 100 kHz with overheads
const uint16_t SI2C_RISE_MAX_US = 1000; // SCL must rise within this after release
const uint16_t DIAG_SETTLE_US = 50;     // I2C DIAG: line settle time per step

// ---- Motors: 28BYJ-48 via ULN2003, IN1..IN4 ----
const uint8_t MOTOR_PINS[2][4] = {
  {2, 3, 4, 5},  // motor 1 = left  (D2-D5)
  {6, 7, 8, 9},  // motor 2 = right (D6-D9)
};

// ---- Safety limits ----
const uint16_t SETTLE_MS_DEFAULT = 8;
const uint16_t SETTLE_MS_MAX     = 500;
const uint8_t  MEAS_N_MAX        = 64;
const uint16_t ADC_READ_N_MAX    = 256;
const uint16_t STREAM_N_MAX      = 2000;
// Streams of up to STREAM_BUF_N samples are captured into RAM at the full ADC
// rate and printed afterwards; longer streams print live, so above ~250 SPS
// their rate is limited by the serial line (~3 ms per "# S" line at 115200).
const uint8_t  STREAM_BUF_N      = 48;

const uint16_t WDT_A_DEFAULT_MS = 2000;   // RAIL A LEDs overdriven at 30 mA
const uint16_t WDT_A_CAP_MS     = 5000;
const uint16_t WDT_B_DEFAULT_MS = 5000;
const uint16_t WDT_B_CAP_MS     = 10000;
const uint16_t WDT_MIN_MS       = 50;

const uint32_t COMMS_TIMEOUT_MS = 10000UL;  // failsafe when lit/armed/moving
const uint32_t ARM_DURATION_MS  = 60000UL;

const uint16_t MOTOR_STEP_MAX     = 2048;  // half-steps per MOTOR STEP command
const uint16_t MOTOR_RPM_DEFAULT  = 5;
const uint16_t MOTOR_RPM_MAX      = 15;
const uint16_t HALF_STEPS_PER_REV = 4096;

// POWER WAKE: hold both motors' coils (no steps) to draw ~0.5 A from bank A,
// which wakes a USB power bank that switched itself off at low load.
const uint16_t WAKE_MS_DEFAULT = 1000;
const uint16_t WAKE_MS_MAX     = 3000;

// Legacy jog (lio_motor_control.py compatibility, reviewed exception — PROTOCOL.md §7)
const uint16_t JOG_MAX_STEPS   = 2048;  // per U/D/LU/LD/RU/RD command
const uint16_t JOG_SPEED_MIN   = 50;    // half-steps/s
const uint16_t JOG_SPEED_MAX   = 1000;
const uint16_t JOG_ACC_MIN     = 25;    // half-steps/s^2
const uint16_t JOG_ACC_MAX     = 1000;
const uint16_t JOG_VA_DEFAULT  = 200;   // alignment (single motor) speed
const uint16_t JOG_VS_DEFAULT  = 500;   // synchronized speed
const uint16_t JOG_ACC_DEFAULT = 250;

// ---- Protocol ----
const uint8_t LINE_MAX = 64;  // characters per command line, excluding '\n'
const uint8_t TOK_MAX  = 10;
