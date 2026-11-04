# LIO V3 — Breadboard Wiring Checklist

Tick each connection as you verify it with the meter's continuity mode. Disconnect both power banks before checking. Pin numbers are physical chip pins.

## Power

- [ ] Bank A (−) joined to bank B (+) → GND bus. The banks are separate units, and the bank-to-bank ground check reads open before joining.
- [ ] Bank A (+) → +5V bus
- [ ] Bank B (−) → TL072 pin 4 only
- [ ] GND → +5V reads +5.0 V; GND → −5V reads −5.0 V
- [ ] Nano GND → GND bus; Nano 5V pin **not connected**
- [ ] The +5V and GND buses are jumpered across every breadboard half

## Shift registers (U1, U2)

- [ ] U1 pin 16, U2 pin 16 → +5V; U1 pin 8, U2 pin 8 → GND
- [ ] U1 pin 10, U2 pin 10 (/SRCLR) → +5V
- [ ] U1 pin 13, U2 pin 13 (/OE) → GND
- [ ] Nano A0 → U1 pin 14 (SER)
- [ ] Nano A1 → U1 pin 11 **and** U2 pin 11 (SRCLK)
- [ ] Nano A2 → U1 pin 12 **and** U2 pin 12 (RCLK)
- [ ] U1 pin 9 (Q7′) → U2 pin 14 (SER)
- [ ] C1 100 nF across U1 pins 16–8; C2 100 nF across U2 pins 16–8

## LED drivers

- [ ] DRV1: V1 → +5V, G → GND, CE → Nano A3 + 10 kΩ to GND, LED → RAIL A
- [ ] DRV2: V1 → +5V, G → GND, CE → Nano D10 + 10 kΩ to GND, LED → RAIL B
- [ ] RAIL A and RAIL B are **not** connected to each other

## Channels (repeat for each; 2N7000 flat face toward you: 1 S · 2 G · 3 D)

For every channel, wire four connections:
1. register output → 220 Ω → gate
2. gate → 10 kΩ → GND
3. source → GND
4. drain → LED cathode (short leg); LED anode (long leg) → rail

| CH | Register pin | LED | Rail | Done |
|---|---|---|---|---|
| 1 | U1 pin 15 (Q0) | 395 nm | A | [ ] |
| 2 | U1 pin 1 (Q1) | ≈405 nm | A | [ ] |
| 3 | U1 pin 2 (Q2) | blue | A | [ ] |
| 4 | U1 pin 3 (Q3) | green | A | [ ] |
| 5 | U1 pin 4 (Q4) | yellow | A | [ ] |
| 6 | U1 pin 5 (Q5) | orange | A | [ ] |
| 7 | U1 pin 6 (Q6) | red | A | [ ] |
| 8 | U1 pin 7 (Q7) | 850 nm | A | [ ] |
| 9 | U2 pin 15 (Q0) | 940 nm | A | [ ] |
| 10 | U2 pin 1 (Q1) | reserved | B | [ ] |
| 11 | U2 pin 2 (Q2) | reserved | B | [ ] |
| 12 | U2 pin 3 (Q3) | 1450 nm | B | [ ] |
| 13 | U2 pin 4 (Q4) | 1550 nm | B | [ ] |
| 14 | U2 pin 5 (Q5) | 1650 nm | B | [ ] |
| 15 | U2 pin 6 (Q6) | 1760 nm | B | [ ] |
| 16 | U2 pin 7 (Q7) | 1850 nm | B | [ ] |

## ADS1115 (U3)

- [ ] VDD → +5V; GND → GND; ADDR → GND; ALRT unconnected
- [ ] SDA → Nano **D11**; SCL → Nano **D12** (software I²C; leave A4/A5 unconnected)
- [ ] 4.7 kΩ SDA → +5V; 4.7 kΩ SCL → +5V
- [ ] No loop-back jumper on D11 (it now carries SDA)
- [ ] A0 ← 10 kΩ ← TL072 pin 1
- [ ] A1 ← OPT101 OUT
- [ ] C3 100 nF VDD–GND

## OPT101 (U4)

- [ ] VCC → +5V; GND, −V, COM → GND
- [ ] 1M jumpered to OUT
- [ ] C4 100 nF VCC–GND

## InGaAs + TL072 (D1, U5)

- [ ] Pin 8 → +5V; pin 4 → −5V; C5 and C6 (100 nF) from pins 8 and 4 to GND; about 10 V between pins 8 and 4
- [ ] Photodiode **cathode → pin 2**; **anode → GND**
- [ ] Case lead: GND only if isolated or tied to the anode (tested)
- [ ] Rf 1 MΩ, pin 1 ↔ pin 2; Cf 10 pF, pin 1 ↔ pin 2
- [ ] Pin 3 → GND
- [ ] Side B: pin 6 ↔ pin 7; pin 5 → GND
- [ ] Before connecting the ADC: pin 1 reads ≈0 V in the dark and goes **positive** under an 850 / 940 nm LED

## Motors (existing)

- [ ] Nano D2–D5 → ULN2003 #1 IN1–IN4; D6–D9 → ULN2003 #2 IN1–IN4
- [ ] Both boards: + → +5V, − → GND
