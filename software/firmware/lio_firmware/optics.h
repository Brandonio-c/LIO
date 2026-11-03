// ===== Optics: 2x 74HC595 channel select, LD06AJSA CE gating, on-time watchdog =====
// Bit (n-1) selects hole n; the U2 byte (holes 9-16) is shifted first, MSB first
// (LIO-ELEC-001 §5.2). Switching order (D-14): select the MOSFET, then raise CE;
// drop CE before changing the selection. At most one channel and one CE high.
#pragma once
#include <Arduino.h>
#include "protocol.h"

void optics_init();   // CE1 = CE2 = LOW, mask = 0. First thing in setup().
void optics_off();    // CE both low, then mask = 0
void optics_tick();   // on-time watchdog; call every loop iteration

uint8_t optics_rail_of(uint8_t hole);   // 1 = RAIL A, 2 = RAIL B
uint16_t optics_wdt_ms(uint8_t rail);
uint16_t optics_mask();
bool optics_ce(uint8_t rail);
bool optics_any_ce();
uint8_t optics_lit_hole();              // hole currently lit, or 0

// CE off -> select hole -> CE on for its rail. ms = 0 means the rail's
// watchdog limit; larger values are clamped to it. Returns 0 or an ErrCode.
uint8_t optics_ch_on(uint8_t hole, uint32_t ms, uint32_t &until_ms);

void cmd_sr(const Command &c);     // SR RAW <hex16>
void cmd_ce(const Command &c);     // CE <1|2> <0|1>
void cmd_ch(const Command &c);     // CH <1-16> ON [ms]
void cmd_off(const Command &c);    // OFF
void cmd_meas(const Command &c);   // MEAS <1-16> [settle_ms] [n]
void cmd_sweep(const Command &c);  // SWEEP [settle_ms] [n]
void cmd_loop(const Command &c);   // LOOP TEST
void cmd_wdt(const Command &c);    // WDT CFG A|B <ms>
