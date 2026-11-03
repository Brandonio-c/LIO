const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType,
  ShadingType, AlignmentType, ImageRun, PageOrientation, Header, Footer, PageNumber,
  TableOfContents, LevelFormat, BorderStyle, PageBreak, VerticalAlign
} = require('docx');

const FONT = 'Calibri', MONO = 'Consolas';
const BODY_W = 9360;            // 6.5" portrait text width
const ACCENT = '1F4E79';

// ---------- inline markup: **bold**, `code`, _italic_ ----------
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|_[^_]+_)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith('**')) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else if (t.startsWith('`')) out.push(new TextRun({ text: t.slice(1, -1), font: MONO, size: (base.size || 21) - 2, ...base, }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}
const P = (t, opt = {}) => new Paragraph({ children: runs(t, opt.run || {}), spacing: { after: 120, line: 276 }, alignment: opt.align, ...opt.para });
const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], pageBreakBefore: true });
const H1n = t => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = t => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const Caption = t => new Paragraph({ children: runs(t, { italics: true, size: 18, color: '555555' }), alignment: AlignmentType.CENTER, spacing: { before: 60, after: 200 } });

let stepRef = 0; const stepRefs = [];
function Steps(items) {
  const ref = 'steps' + (stepRef++); stepRefs.push(ref);
  return items.map(t => new Paragraph({ numbering: { reference: ref, level: 0 }, children: runs(t), spacing: { after: 80, line: 276 } }));
}

function Note(t, kind = 'note') {
  const fill = kind === 'warn' ? 'FFF4E0' : 'EAF2FB';
  const border = kind === 'warn' ? 'E3A13B' : '7FA7D3';
  return new Paragraph({
    children: runs(t), spacing: { before: 80, after: 160, line: 276 },
    shading: { type: ShadingType.CLEAR, fill, color: 'auto' },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: border, space: 8 } },
    indent: { left: 160, right: 160 },
  });
}

function Code(src) {
  const lines = src.replace(/\t/g, '  ').split('\n');
  return lines.map((ln, i) => new Paragraph({
    children: [new TextRun({ text: ln.length ? ln : ' ', font: MONO, size: 15 })],
    spacing: { after: 0, line: 228 },
    shading: { type: ShadingType.CLEAR, fill: 'F3F5F8', color: 'auto' },
    indent: { left: 120, right: 120 },
    keepLines: true,
  }));
}

const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: 'BFC5CF' };
const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
function Tbl(headers, rows, widths, opt = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const mk = (txt, w, head) => new TableCell({
    width: { size: w, type: WidthType.DXA }, borders,
    shading: head ? { type: ShadingType.CLEAR, fill: 'DCE6F2', color: 'auto' } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    verticalAlign: VerticalAlign.TOP,
    children: String(txt).split('|').map(part => new Paragraph({ children: runs(part, { size: opt.size || 18, bold: head ? true : undefined }), spacing: { after: 0, line: 252 } })),
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => mk(h, widths[i], true)) }),
      ...rows.map(r => new TableRow({ cantSplit: true, children: r.map((c, i) => mk(c, widths[i], false)) }))],
  });
}
const Gap = () => new Paragraph({ children: [], spacing: { after: 120 } });

function Img(file, wpx, caption) {
  const buf = fs.readFileSync(file);
  // read PNG size
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  const hpx = Math.round(wpx * h / w);
  return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 0 },
    children: [new ImageRun({ type: 'png', data: buf, transformation: { width: wpx, height: hpx } })] }),
  Caption(caption)];
}

// ======================================================================
// CONTENT
// ======================================================================
const title = [
  new Paragraph({ children: [], spacing: { before: 2400 } }),
  new Paragraph({ children: [new TextRun({ text: 'LIO V3 OPTICAL HEAD', bold: true, size: 30, color: '6B7280' })], spacing: { after: 120 } }),
  new Paragraph({ children: [new TextRun({ text: 'Electronics Technical Description', bold: true, size: 52, color: ACCENT })], spacing: { after: 200 } }),
  new Paragraph({ children: [new TextRun({ text: '16-channel multi-wavelength illumination, dual-detector acquisition, and stepper drive', size: 26, color: '333333' })], spacing: { after: 600 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 12 } } }),
  Tbl(['Field', 'Value'], [
    ['Document number', 'LIO-ELEC-001'],
    ['Revision', 'A'],
    ['Date', '2 November 2026'],
    ['Status', 'Development: breadboard prototype as built. Not hardware-qualified.'],
    ['Scope', 'Electronics only: power, control, LED drive, detection, data acquisition, motor drive'],
    ['Companion files', 'LIO_full_schematic.html / .svg (schematic); LIO_V3_master.scad (mechanics)'],
  ], [2600, 6760], { size: 20 }),
];

const contents = [
  new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun('Contents')], pageBreakBefore: true }),
  new TableOfContents('Contents', { hyperlink: true, headingStyleRange: '1-2' }),
  P('_If the table above is empty, right-click it in Word and choose Update Field._', { run: { color: '777777', size: 18 } }),
];

// ---------------- 1 Scope ----------------
const s1 = [
  H1('1  Scope and status'),
  H2('1.1  Purpose'),
  P('This document describes the complete electronics of the LIO V3 optical head as built on the breadboard prototype. The head lights a sample with one of up to sixteen LEDs of different wavelengths at a time. It reads the response with two detectors: a silicon OPT101 for 300–1100 nm and an InGaAs photodiode for about 800–1750 nm. The readings are digitised and sent to a laptop. The existing stepper drive that raises and lowers the chamber is included because it shares the controller and the power supply.'),
  P('The document covers the system architecture, the design rationale and supporting calculations, the full schematic, the net list, the bill of materials, a staged assembly procedure, bring-up tests, troubleshooting, safety, and the firmware and logging software. The mechanical parts (optical deck, LED inserts, dual-detector plate) are covered by the OpenSCAD master file. They appear here only where they affect the electronics.'),
  H2('1.2  Status and open items'),
  P('This is development hardware. The circuit as documented is electrically sound for the components identified, but the items below have not been confirmed on the actual parts. Treat each as a check to perform before relying on the readings.'),
  Tbl(['Item', 'What needs confirming', 'Where it matters'], [
    ['SWIR LED ratings (holes 12–16)', 'Maximum continuous forward current and forward voltage from each part\'s datasheet', 'Driver 2 current setting (§6.2)'],
    ['InGaAs case lead', 'Whether the third lead of the MTPD1346D is isolated, tied to the anode, or tied to the cathode', 'TIA wiring (§7.2)'],
    ['LD06AJSA CE polarity', 'CE high = output on, low = off (inferred from the listing text)', 'Firmware and pull-downs (§6.2)'],
    ['Power bank B behaviour', 'Whether it stays on at a ~3 mA load or auto-sleeps', '−5 V rail (§3.2)'],
    ['TL072 output swing on ±5 V', 'Typically about ±3.5 V; sets the TIA saturation point', 'Rf selection (§7.2)'],
    ['OPT101 module pinout', 'Matches the silkscreen VCC, GND, 1M, OUT, −V, COM', 'Detector 1 wiring (§7.1)'],
  ], [2500, 4060, 2800]),
  H2('1.3  Conventions'),
  P('**Hole n** is LED position n on the optical deck, numbered clockwise from the 12 o\'clock position. **CHn** is the electrical channel that drives hole n; the two numbers always match. Net names are written in capitals (for example +5V, RAIL A, DATA). Chip pin numbers are physical package pins. **GND** always means the common 0 V junction between the two power banks.'),
  P('Calculated values are given with the assumption behind them. Where a datasheet gives a range, the conservative end is used.'),
];

// ---------------- 2 Overview ----------------
const s2 = [
  H1('2  System overview'),
  H2('2.1  Functional chain'),
  P('The Arduino Nano is the controller. It shifts a 16-bit pattern into two daisy-chained 74HC595 shift registers. Each register output drives the gate of one 2N7000 MOSFET through a 220 Ω resistor, and each MOSFET is the low-side switch for one LED. The LED anodes are fed by two LD06AJSA constant-current modules: Driver 1 feeds RAIL A (holes 1–9) and Driver 2 feeds RAIL B (holes 10–16). The Nano enables each driver separately through its CE pin. So the shift registers choose _which_ LED can conduct, and the drivers set _how much_ current flows and _when_.'),
  P('Light leaving the sample reaches the detector plate in the centre of the deck. The OPT101 sits on the optical axis and outputs a voltage proportional to light from about 300 to 1100 nm. The InGaAs photodiode sits just off-axis. Its current is converted to a voltage by a transimpedance amplifier built on one half of a TL072. Both detector voltages go to an ADS1115 16-bit ADC, which the Nano reads over I²C. The Nano sends the readings over USB to the laptop, where a Python script logs and plots them.'),
  Tbl(['Subsystem', 'Parts', 'Function'], [
    ['Power', '2× 5 V USB power banks in series', 'Supplies +5 V, 0 V (GND) and −5 V'],
    ['Controller', 'Arduino Nano', 'Sequencing, I²C master, USB serial to laptop'],
    ['Channel selection', '2× 74HC595 (U1, U2)', '16 select lines from 3 Nano pins'],
    ['Channel switches', '16× 2N7000, 16× 220 Ω, 16× 10 kΩ', 'One low-side switch per LED'],
    ['Current sources', '2× LD06AJSA modules (DRV1, DRV2)', 'Regulated LED current on RAIL A / RAIL B'],
    ['Emitters', 'Up to 16 through-hole LEDs, 395–1850 nm', 'Illumination, one wavelength at a time'],
    ['Detector 1', 'OPT101 module (CJMCU-101)', 'Silicon photodiode with built-in amplifier'],
    ['Detector 2', 'MTPD1346D InGaAs + TL072 (U5)', 'SWIR photodiode with transimpedance amplifier'],
    ['Acquisition', 'ADS1115 breakout (U3)', '16-bit conversion of both detector outputs'],
    ['Motion (existing)', '2× ULN2003 boards + 2× 28BYJ-48', 'Raise and lower the chamber'],
  ], [2100, 3360, 3900]),
  H2('2.2  Operating principle'),
  P('Only one LED is ever lit at a time. That isn\'t a hardware limit; it\'s how the measurement works. The detector reports total light received, so if two wavelengths were lit together their contributions couldn\'t be separated. In addition, two LEDs on one constant-current rail would split the set current unevenly according to their forward voltages.'),
  P('A sweep visits each hole in turn. With all drivers off, the firmware reads both detectors to get a dark (ambient) baseline. It then selects the hole\'s MOSFET, enables the hole\'s driver group, waits for the light and the amplifiers to settle, reads both detectors again, and turns the driver off. Subtracting dark from lit gives the net response at that wavelength. A complete 16-hole sweep takes under a second at the default ADC rate.'),
];

// ---------------- 3 Power ----------------
const s3 = [
  H1('3  Power'),
  H2('3.1  Split supply from two power banks'),
  P('The TL072 needs a supply below ground, because on a single 5 V rail with its input at 0 V it operates outside its common-mode range. A negative rail is made by stacking two 5 V USB power banks in series. Bank A\'s negative terminal is tied to bank B\'s positive terminal, and that junction becomes the system ground. Bank A\'s positive terminal is then +5 V and bank B\'s negative terminal is −5 V with respect to GND.'),
  Tbl(['Net', 'Source', 'Loads'], [
    ['+5V', 'Bank A (+)', 'U1/U2 VCC and /SRCLR, DRV1 V1, DRV2 V1, ADS1115 VDD, OPT101 VCC, TL072 pin 8, both ULN2003 boards'],
    ['GND', 'Bank A (−) joined to bank B (+)', 'Every ground in the system (see net list, §10)'],
    ['−5V', 'Bank B (−)', 'TL072 pin 4 only'],
  ], [1400, 2600, 5360]),
  H2('3.2  Isolation requirement'),
  P('Series stacking only works if the two sources share no internal connection. Two ports on the same bank do share one: a continuity test between the ground pins of the two ports on one bank read about 2 Ω, which is effectively a short. Joining one port\'s + to the other port\'s − would therefore short a port. Two physically separate banks are isolated from each other and are used instead.'),
  ...Steps([
    'With nothing connected, set the meter to continuity and probe bank A ground to bank B ground. It must read open (OL). Any beep or low resistance means stop.',
    'Join bank A (−) to bank B (+). This node is GND.',
    'Measure GND to bank A (+): expect +5.0 V (4.75–5.25 V). Measure GND to bank B (−): expect −5.0 V.',
    'Leave the circuit idle for one minute and measure −5 V again. If it has dropped to 0 V, bank B has gone to sleep (see below).',
  ]),
  Note('Bank B supplies only the TL072, about 3 mA. Many power banks switch off below 50–100 mA. If −5 V disappears, the TIA output becomes meaningless and can swing anywhere. Fixes, in order of preference: use a bank with a low-current or "always on" mode; or put a 220 Ω ¼ W resistor across bank B\'s output as a dummy load (23 mA, 0.11 W). The dummy load drains the bank continuously, so disconnect it after use.', 'warn'),
  P('Do not charge bank B while it is part of the circuit. A charger can reference its output to mains earth and upset the split.'),
  H2('3.3  Current budget'),
  Tbl(['Load', 'Rail', 'Typical current', 'Notes'], [
    ['Active LED channel (one at a time)', '+5V', '30 mA (RAIL A) or ≈45 mA (RAIL B)', 'Only one driver is enabled at a time'],
    ['74HC595 ×2 + gate pull-down', '+5V', '< 1 mA', '0.5 mA through the active channel\'s 10 kΩ'],
    ['ADS1115', '+5V', '0.2 mA', 'Continuous conversion'],
    ['OPT101', '+5V', '0.12 mA', 'Datasheet quiescent current'],
    ['TL072 (both halves)', '+5V / −5V', '≈2.5–3 mA', '≈1.4 mA per amplifier'],
    ['28BYJ-48 via ULN2003, per motor', '+5V', '≈200–240 mA', 'Two coils energised; only while moving'],
    ['Arduino Nano', 'USB', '≈20 mA', 'Powered from the laptop, not from the banks'],
    ['**Bank A peak (both motors moving + LED)**', '+5V', '**≈0.55 A**', 'Well within a typical 2 A bank'],
    ['**Bank A during a sweep (motors idle)**', '+5V', '**≈50 mA**', ''],
    ['**Bank B**', '−5V', '**≈3 mA**', 'Auto-sleep risk, see §3.2'],
  ], [3100, 1100, 2100, 3060]),
  H2('3.4  Powering the Nano'),
  P('The Nano is powered from the laptop over USB, which also carries the serial data the Python logger needs. Its 5V pin is **not** connected to the +5V rail; only its GND is joined to the system ground. If the Nano\'s 5V pin were also tied to bank A, the USB supply and the bank would be connected in parallel and would back-feed each other.'),
  P('Small differences between USB 5 V and bank 5 V are harmless here. A logic high from the Nano (≥ 4.5 V) exceeds the 74HC595\'s 3.5 V input-high threshold, and the ADS1115 board\'s I²C pull-ups to bank 5 V stay within the Nano\'s input tolerance. For standalone use without a laptop, unplug USB first and then feed +5V into the Nano\'s 5V pin.'),
  H2('3.5  Decoupling'),
  P('Each IC has a 100 nF ceramic capacitor across its supply pins, placed as close to the pins as the breadboard allows. These supply the fast current spikes that occur when outputs switch, so the shared rail doesn\'t carry glitches into the detector readings. The power banks provide bulk reservoir capacitance.'),
  Tbl(['Ref', 'Value', 'Placed across', 'Purpose'], [
    ['C1', '100 nF', 'U1 pin 16 to pin 8', 'Shift register switching transients'],
    ['C2', '100 nF', 'U2 pin 16 to pin 8', 'Shift register switching transients'],
    ['C3', '100 nF', 'ADS1115 VDD to GND', 'ADC reference stability'],
    ['C4', '100 nF', 'OPT101 VCC to GND', 'Detector supply noise'],
    ['C5', '100 nF', 'TL072 pin 8 to GND', 'Op-amp stability, +5V side'],
    ['C6', '100 nF', 'TL072 pin 4 to GND', 'Op-amp stability, −5V side'],
  ], [900, 1100, 3200, 4160]),
  H2('3.6  Power-up behaviour'),
  P('When power is applied, the 74HC595 storage registers come up in random states, so several MOSFETs may switch on before the Nano has run its setup code. No LED current flows during this time because each driver\'s CE pin is held low by a 10 kΩ pull-down until the Nano drives it. The first thing the firmware does is clear the registers and hold both CE lines low. This is why the CE pull-downs are required, not optional.'),
];

// ---------------- 4 Controller ----------------
const s4 = [
  H1('4  Controller: Arduino Nano'),
  P('The Nano (ATmega328P, 5 V logic) runs the sequencing firmware in Appendix A. Pins D2–D9 are used by the existing motor drive. The optical head uses three pins for the shift registers, two for the driver enables and two for I²C. A6 and A7 are analog-input-only on the Nano and can\'t be used as outputs.'),
  Tbl(['Pin', 'Net', 'Direction', 'Connects to', 'Notes'], [
    ['A0', 'DATA', 'Out', 'U1 pin 14 (SER)', 'Serial data into the register chain'],
    ['A1', 'CLOCK', 'Out', 'U1 pin 11 and U2 pin 11 (SRCLK)', 'Shared by both chips'],
    ['A2', 'LATCH', 'Out', 'U1 pin 12 and U2 pin 12 (RCLK)', 'Shared by both chips'],
    ['A3', 'CE1', 'Out', 'DRV1 CE', '10 kΩ pull-down to GND'],
    ['D10', 'CE2', 'Out', 'DRV2 CE', '10 kΩ pull-down to GND'],
    ['A4', 'SDA', 'I/O', 'ADS1115 SDA', 'Pull-up on the ADS1115 board'],
    ['A5', 'SCL', 'Out', 'ADS1115 SCL', 'Pull-up on the ADS1115 board'],
    ['D2–D5', 'M1 IN1–IN4', 'Out', 'ULN2003 board #1', 'Existing motor 1'],
    ['D6–D9', 'M2 IN1–IN4', 'Out', 'ULN2003 board #2', 'Existing motor 2'],
    ['GND', 'GND', '—', 'System ground', 'Required'],
    ['5V', '—', '—', 'Not connected', 'Nano is powered from USB'],
    ['D11, D12, A6, A7', '—', '—', 'Spare', 'A6/A7 are analog inputs only'],
  ], [1200, 1300, 1000, 2900, 2960]),
];

// ---------------- 5 Shift registers ----------------
const s5 = [
  H1('5  Channel selection: 74HC595 shift registers'),
  H2('5.1  Configuration'),
  P('Two 74HC595 serial-in, parallel-out registers are chained to form one 16-bit register. CLOCK and LATCH are wired to both chips. DATA enters U1 only, and U1\'s serial overflow output Q7′ (pin 9) feeds U2\'s serial input (pin 14). On every CLOCK edge each bit moves one place along the chain. After sixteen clocks, the first bit sent has reached U2 Q7 and the last bit sent sits in U1 Q0. A rising LATCH edge copies the shift stage to the outputs at the same moment, so outputs never show intermediate patterns while data is being shifted.'),
  P('/OE (pin 13) is tied to GND so the outputs are always enabled, and /SRCLR (pin 10) is tied to +5V so the register is never cleared. Each output only charges a MOSFET gate and holds a 10 kΩ pull-down, about 0.5 mA when high. That is far inside the 74HC595\'s 6 mA recommended and 35 mA absolute-maximum per-pin rating. The registers never carry LED current.'),
  Tbl(['Pin', 'Name', 'U1 connection', 'U2 connection'], [
    ['16', 'VCC', '+5V (C1 to GND)', '+5V (C2 to GND)'],
    ['8', 'GND', 'GND', 'GND'],
    ['14', 'SER', 'Nano A0 (DATA)', 'U1 pin 9 (Q7′)'],
    ['11', 'SRCLK', 'Nano A1 (CLOCK)', 'Nano A1 (CLOCK)'],
    ['12', 'RCLK', 'Nano A2 (LATCH)', 'Nano A2 (LATCH)'],
    ['13', '/OE', 'GND', 'GND'],
    ['10', '/SRCLR', '+5V', '+5V'],
    ['9', 'Q7′', 'U2 pin 14', 'Not connected'],
    ['15', 'Q0', 'CH1 gate resistor', 'CH9 gate resistor'],
    ['1–7', 'Q1–Q7', 'CH2–CH8 gate resistors', 'CH10–CH16 gate resistors'],
  ], [900, 1300, 3580, 3580]),
  Note('Q0 is on pin 15, on the opposite side of the chip from Q1–Q7 (pins 1–7). This is the most common wiring mistake with this part.'),
  H2('5.2  Bit mapping'),
  P('The firmware builds a 16-bit word in which bit (n − 1) selects hole n. It sends the high byte first (holes 9–16, which must end up in U2) and then the low byte (holes 1–8, U1), each most-significant bit first, then pulses LATCH. With this order, bit 0 lands on U1 Q0 = CH1 and bit 15 on U2 Q7 = CH16. Shifting 16 bits with `shiftOut()` takes about 0.2 ms, which is negligible next to the settle time.'),
];

// ---------------- 6 LED drive ----------------
const s6 = [
  H1('6  LED drive'),
  H2('6.1  Architecture and rationale'),
  P('Each LED sits between a current-regulated rail and its own low-side MOSFET switch. Current flows from the driver, along the rail, through the LED and the MOSFET, and to ground, but only for the channel whose MOSFET is on and only while that rail\'s driver is enabled.'),
  P('This arrangement was chosen for three reasons. First, a 74HC595 output can\'t supply LED current, so a switch is needed between the register and the LED. Second, a constant-current source holds the LED current steady as the LED warms and its forward voltage drifts, which a series resistor doesn\'t. That matters most for the weak SWIR emitters. Third, because only one LED conducts at a time, one current source can serve a whole group of LEDs. Sixteen switches are still needed because a single shared switch could only turn every LED on or every LED off; it couldn\'t pick one.'),
  P('The LEDs are split into two groups because their safe currents differ. The visible and near-IR 5 mm LEDs are rated around 20 mA, while the SWIR emitters typically take 50–100 mA. A single shared driver would have to sit at one current for all of them.'),
  H2('6.2  Current sources: LD06AJSA modules'),
  P('Each LD06AJSA module is a linear constant-current regulator, adjustable from 30 to 1500 mA. It takes 2.8–6 V on V1 and sources regulated current from its LED pin when CE is high, with thermal regulation at about 135 °C and an overload limit near 1.9 A. With CE low, the output is off and the module draws under 1 µA.'),
  Tbl(['Pin', 'DRV1', 'DRV2'], [
    ['V1', '+5V', '+5V'],
    ['G', 'GND', 'GND'],
    ['CE', 'Nano A3, plus 10 kΩ to GND', 'Nano D10, plus 10 kΩ to GND'],
    ['LED', 'RAIL A (anodes of holes 1–9)', 'RAIL B (anodes of holes 10–16)'],
    ['Setting', 'Minimum, ≈30 mA', '≈45 mA, or the SWIR LEDs\' rated maximum if lower'],
  ], [1400, 3980, 3980]),
  Note('The module\'s minimum is 30 mA, which is above the 20 mA continuous rating of the 5 mm Chanzon LEDs on RAIL A. In a sweep each LED is lit for about 25 ms per pass, which is acceptable. Do not leave a RAIL A LED on continuously for more than a few seconds of testing. If continuous operation is ever needed, move RAIL A to per-LED series resistors (R = (5 − Vf) / 0.020).', 'warn'),
  P('**Headroom.** A linear regulator needs a few hundred millivolts across itself to regulate. The worst case is the 395 nm LED, with Vf ≈ 3.2–3.4 V at 30 mA. The supply is 5.0 V, less about 0.1 V across the 2N7000, less 3.4 V across the LED, which leaves about 1.5 V for the driver. That is ample. The SWIR emitters (Vf ≈ 0.9–1.3 V) leave about 3.7 V.'),
  P('**Dissipation.** P = (5 − Vf − V_DS) × I. For RAIL B at 45 mA with Vf = 1.2 V, P ≈ (5 − 1.2 − 0.1) × 0.045 ≈ 0.17 W while lit. RAIL A at 30 mA with a 2 V LED gives about 0.09 W. Neither needs a heatsink at these duty cycles.'),
  P('**Open circuit.** When no MOSFET in a group is on, the driver\'s output simply rises toward V1, which is harmless. The module\'s output capacitance would then be charged to about 5 V, and switching a MOSFET on at that moment would dump that charge into the LED. The firmware therefore always selects the MOSFET first and enables CE second, and drops CE before changing channel.'),
  P('**Setting the current.** Enable the driver, select one known-good LED in its group (TEST_MODE 4), put the multimeter in series with the driver\'s LED output on its mA range, and adjust the module until the meter shows the target. Do this once per driver, not once per channel.'),
  H2('6.3  RAIL A and RAIL B'),
  P('RAIL A is the bus strip fed by DRV1\'s LED pin. It carries the anodes of holes 1–9 (395 nm through 940 nm). RAIL B is a separate bus strip fed by DRV2\'s LED pin and carries the anodes of holes 10–16. The two rails must never be joined, because two current regulators connected together will fight. Hole 9 is switched by U2 but belongs to RAIL A: the rail assignment follows wavelength, not chip.'),
  H2('6.4  Channel switch: 2N7000 stage'),
  P('Each channel is identical: register output → 220 Ω → gate (pin 2); gate → 10 kΩ → GND; source (pin 1) → GND; drain (pin 3) → LED cathode; LED anode → rail. Facing the flat side with the legs down, the 2N7000 pins read Source, Gate, Drain from left to right.'),
  Tbl(['Parameter', 'Value', 'Consequence'], [
    ['V_GS(th)', '0.8–3.0 V', 'Fully enhanced by a 5 V gate drive'],
    ['R_DS(on) at V_GS = 4.5–5 V', '≈1.8 Ω typ., 5.3 Ω max', 'At 45 mA, V_DS ≤ 0.24 V, P ≤ 11 mW'],
    ['I_D continuous', '200 mA', 'More than 4× the highest channel current'],
    ['V_DS max', '60 V', 'No concern at 5 V'],
  ], [2800, 2600, 3960]),
  P('**220 Ω gate resistor.** This limits the charging current spike from the register output into the gate capacitance (about 20–50 pF) to under 23 mA, keeping the 74HC595 within ratings and damping ringing on the breadboard wiring. The RC time constant is about 220 Ω × 50 pF ≈ 11 ns, so switching speed is unaffected.'),
  P('**10 kΩ gate pull-down.** This holds the MOSFET off whenever the gate isn\'t actively driven (during reset, or with a loose jumper), so a floating gate can\'t turn an LED on unpredictably. It draws only 0.5 mA from the active output.'),
  H2('6.5  Channel map'),
  Tbl(['CH / Hole', 'LED', 'Register output (pin)', 'Rail', 'Read by'], [
    ['1', '395 nm UV', 'U1 Q0 (15)', 'A', 'OPT101'],
    ['2', '≈405 nm violet', 'U1 Q1 (1)', 'A', 'OPT101'],
    ['3', 'Blue ≈465 nm', 'U1 Q2 (2)', 'A', 'OPT101'],
    ['4', 'Green ≈525 nm', 'U1 Q3 (3)', 'A', 'OPT101'],
    ['5', 'Yellow ≈590 nm', 'U1 Q4 (4)', 'A', 'OPT101'],
    ['6', 'Orange ≈605 nm', 'U1 Q5 (5)', 'A', 'OPT101'],
    ['7', 'Red ≈630 nm', 'U1 Q6 (6)', 'A', 'OPT101'],
    ['8', '850 nm IR', 'U1 Q7 (7)', 'A', 'OPT101 and InGaAs'],
    ['9', '940 nm IR', 'U2 Q0 (15)', 'A', 'OPT101 and InGaAs'],
    ['10', 'Reserved', 'U2 Q1 (1)', 'B*', 'InGaAs'],
    ['11', 'Reserved', 'U2 Q2 (2)', 'B*', 'InGaAs'],
    ['12', '1450 nm', 'U2 Q3 (3)', 'B', 'InGaAs'],
    ['13', '1550 nm', 'U2 Q4 (4)', 'B', 'InGaAs'],
    ['14', '1650 nm', 'U2 Q5 (5)', 'B', 'InGaAs'],
    ['15', '1760 nm', 'U2 Q6 (6)', 'B', 'InGaAs (weak; at cutoff)'],
    ['16', '1850 nm', 'U2 Q7 (7)', 'B', 'Beyond InGaAs range'],
  ], [1200, 2000, 2300, 900, 2960]),
  P('*Holes 10 and 11 originally held surface-mount 1200 nm and 1300 nm emitters, which were removed. Their switches are wired and can be populated later with through-hole SWIR parts on RAIL B. If white or pink LEDs are fitted there instead, their anodes must go to RAIL A, and `isRailB()` in the firmware must change to `return h >= 11;`.', { run: { size: 18 } }),
];

// ---------------- 7 Detection ----------------
const s7 = [
  H1('7  Detection and acquisition'),
  H2('7.1  Detector 1: OPT101 (silicon)'),
  P('The OPT101 combines a 2.29 × 2.29 mm silicon photodiode with a transimpedance amplifier and an internal 1 MΩ feedback resistor on one chip. It runs single-supply here. VCC goes to +5V; GND, −V and COM go to GND; the 1M pin is jumpered to OUT to switch in the internal feedback resistor. OUT goes to ADS1115 input A1.'),
  P('Responsivity is about 0.45 A/W at 650 nm, so with 1 MΩ of gain the output rises by about 0.45 V per microwatt of incident light, starting from near 0 V in the dark. On a 5 V supply the output saturates around VCC − 1.3 V ≈ 3.7 V, which is inside the ADC\'s ±4.096 V range and well below its 5.3 V absolute limit. The bandwidth is about 14 kHz, so it settles in well under a millisecond. Silicon responds from about 300 to 1100 nm, so the OPT101 measures holes 1–9.'),
  Note('If OUT sits pinned near 0 V or near 3.7 V regardless of light, check the 1M-to-OUT jumper first. Without it the amplifier has no feedback.'),
  H2('7.2  Detector 2: InGaAs photodiode and TL072 transimpedance amplifier'),
  P('The MTPD1346D is a bare InGaAs PIN photodiode in a TO-46 can, sensitive from about 800 to 1750 nm. It produces a current proportional to light, typically nanoamps to a few microamps, which side A of a TL072 converts to a voltage.'),
  Tbl(['Connection', 'Wired to'], [
    ['TL072 pin 8 (V+)', '+5V, with C5 to GND'],
    ['TL072 pin 4 (V−)', '−5V, with C6 to GND'],
    ['Photodiode cathode', 'TL072 pin 2 (inverting input, the summing node)'],
    ['Photodiode anode', 'GND'],
    ['Photodiode case lead', 'GND only if continuity tests show it is isolated or tied to the anode; leave unconnected if tied to the cathode'],
    ['Rf = 1 MΩ', 'Pin 1 (output) to pin 2'],
    ['Cf = 10 pF', 'Parallel with Rf, pin 1 to pin 2'],
    ['TL072 pin 3 (+ input)', 'GND'],
    ['TL072 pin 1 (output)', '10 kΩ in series to ADS1115 A0'],
    ['Side B (unused)', 'Pin 6 to pin 7; pin 5 to GND'],
  ], [3000, 6360]),
  P('**Orientation and sign.** The amplifier holds pin 2 at virtual ground. Photocurrent flows out of the summing node into the cathode and through the diode to ground. Since that current is supplied by the output through Rf, the output rises: **Vout = +I_ph × Rf**. The diode sits at zero bias (photovoltaic mode), which minimises dark current and noise for steady illumination. The cost is some speed, and speed isn\'t needed here.'),
  Note('Earlier build instructions wired the cathode to +5V and the anode to pin 2. That makes the output swing negative with light, down to about −3.5 V. The ADS1115\'s inputs are only rated to 0.3 V below ground, so that wiring can damage the ADC. Use the orientation above.', 'warn'),
  P('**Gain and saturation.** On ±5 V the TL072 output swings to roughly ±3.5 V, so with Rf = 1 MΩ it saturates at about 3.5 µA of photocurrent. InGaAs responsivity is about 0.9–1.0 A/W near 1550 nm, which corresponds to about 3.5–4 µW of light on the detector. If the output sits near +3.5 V whenever a SWIR LED is lit, reduce Rf:'),
  Tbl(['Rf', 'Output per µA', 'Saturates at (≈1 A/W)', 'Bandwidth with Cf = 10 pF'], [
    ['1 MΩ (fitted)', '1 V', '≈3.5 µW', '16 kHz'],
    ['100 kΩ', '0.1 V', '≈35 µW', '160 kHz (add Cf ≈ 47–100 pF if it rings)'],
    ['10 kΩ', '0.01 V', '≈350 µW', 'Increase Cf to ≈ 470 pF–1 nF'],
  ], [2000, 2000, 2600, 2760]),
  P('**Bandwidth and settling.** f = 1 / (2π Rf Cf) = 1 / (2π × 1 MΩ × 10 pF) ≈ 16 kHz, a time constant of 10 µs. The 8 ms settle time in the firmware is many hundreds of time constants. Cf also suppresses the oscillation that the photodiode\'s capacitance would otherwise cause at the summing node.'),
  P('**ADC protection.** The 10 kΩ series resistor limits current into the ADS1115\'s input protection diodes to under 0.5 mA if the op-amp output ever goes negative, for example during power-up or if −5V is lost. The ADS1115 allows 10 mA continuous. Its input impedance (megaohms) makes the resistor\'s effect on accuracy a fraction of a percent, which calibration absorbs.'),
  P('**Unused half.** Side B is tied as a grounded voltage follower so it can\'t oscillate and inject noise through the shared supply pins.'),
  H2('7.3  ADS1115 analog-to-digital converter'),
  Tbl(['Board pin', 'Connection', 'Notes'], [
    ['VDD', '+5V', 'C3 to GND'],
    ['GND', 'GND', ''],
    ['SCL', 'Nano A5', 'Board has 10 kΩ pull-ups'],
    ['SDA', 'Nano A4', ''],
    ['ADDR', 'GND', 'I²C address 0x48'],
    ['ALRT', 'Not connected', ''],
    ['A0', 'TIA output via 10 kΩ', 'InGaAs channel'],
    ['A1', 'OPT101 OUT', 'Silicon channel'],
    ['A2, A3', 'Not connected', 'Spare inputs'],
  ], [1600, 3400, 4360]),
  P('Both channels are read single-ended at gain setting GAIN_ONE, a full-scale range of ±4.096 V, so one count is 125 µV. Single-ended readings span 0 to 32767 counts for 0 to 4.096 V. At the default 128 samples/s each conversion takes about 8 ms. Inputs must stay between GND − 0.3 V and VDD + 0.3 V. If the OPT101 readings are small, GAIN_TWO (±2.048 V, 62.5 µV per count) doubles the resolution, as long as no reading exceeds 2.048 V.'),
  H2('7.4  Spectral coverage'),
  Tbl(['Holes', 'Wavelengths', 'Detector', 'Comment'], [
    ['1–7', '395–630 nm', 'OPT101', 'Silicon only'],
    ['8–9', '850, 940 nm', 'Both', 'Overlap channels used to cross-calibrate the two detectors'],
    ['12–14', '1450–1650 nm', 'InGaAs', 'Inside InGaAs range'],
    ['15', '1760 nm', 'InGaAs', 'At the ≈1750 nm cutoff: weak signal'],
    ['16', '1850 nm', 'None at present', 'Needs an extended-InGaAs (2.6 µm) detector'],
  ], [1200, 2000, 1800, 4360]),
];

// ---------------- 8 Motors ----------------
const s8 = [
  H1('8  Motor drive (existing)'),
  P('Two 28BYJ-48 geared steppers raise and lower the chamber. Each is driven by a ULN2003 Darlington board: Nano D2–D5 drive IN1–IN4 of board #1 and D6–D9 drive IN1–IN4 of board #2. Each board\'s + pin goes to +5V and its − pin to GND, and the motor plugs into the board\'s 5-pin connector.'),
  P('At 5 V each motor draws about 200–240 mA with two coils energised. The motors share the +5V rail with the optics, so the coil switching puts noise on the rail. Sweeps should only run with the motors stationary, and firmware that moves the motors should de-energise the coils (all IN pins low) once the chamber is in position. That also stops the motors heating.'),
];

// ---------------- 9 Schematic ----------------
const s9a = [
  H1n('9  Schematic'),
  ...Img('docbuild/full_small.png', 780, 'Figure 1. Full electronics schematic. The same drawing is in LIO_full_schematic.svg, which can be zoomed without losing detail.'),
];
const s9b = [
  H2('9.1  Reading the schematic'),
  P('Every signal wire is drawn from source pin to destination pin. Power connections use labels: every "+5V" label connects to the +5V rail, the "−5V" label to bank B, and every ground symbol to the common GND. A dot marks wires that are joined; where wires cross with a small hop they are **not** connected. Chips are drawn by function, with inputs on the left and outputs on the right, so their pins aren\'t in package order. Wire by the small grey pin numbers. Figures 2–7 enlarge each section.'),
  ...Img('docbuild/ctrl.png', 225, 'Figure 2. Controller: Nano pin assignments, driver-enable and I²C lanes, and the motor drive.'),
  ...Img('docbuild/bank1.png', 624, 'Figure 3. LED bank 1: U1, CH1–CH8 and RAIL A.'),
  ...Img('docbuild/bank2.png', 624, 'Figure 4. LED bank 2: U2, CH9–CH16, RAIL A continuation to CH9, and RAIL B.'),
  ...Img('docbuild/drv.png', 235, 'Figure 5. Power banks and the two LED drivers with CE pull-downs.'),
  ...Img('docbuild/det.png', 624, 'Figure 6. Detectors and ADC: ADS1115, OPT101, and the InGaAs transimpedance amplifier.'),
  ...Img('docbuild/caps.png', 330, 'Figure 7. Decoupling capacitors C1–C6.'),
];

// ---------------- 10 Net list ----------------
const s10 = [
  H1('10  Net list'),
  P('Every electrical connection in the system, grouped by net. Use it as a checklist: tick each connection on the breadboard against this table.'),
  Tbl(['Net', 'Connected points'], [
    ['+5V', 'Bank A (+) · U1 pins 16, 10 · U2 pins 16, 10 · DRV1 V1 · DRV2 V1 · ADS1115 VDD · OPT101 VCC · TL072 pin 8 · ULN2003 #1 (+) · ULN2003 #2 (+) · C1–C5 (+ side)'],
    ['−5V', 'Bank B (−) · TL072 pin 4 · C6'],
    ['GND', 'Bank A (−) / bank B (+) junction · Nano GND · U1 pins 8, 13 · U2 pins 8, 13 · DRV1 G · DRV2 G · Q1–Q16 sources · 16 gate pull-downs · 2 CE pull-downs · ADS1115 GND, ADDR · OPT101 GND, −V, COM · TL072 pins 3, 5 · InGaAs anode (and case if permitted) · ULN2003 #1 (−) · ULN2003 #2 (−) · C1–C6 (ground side)'],
    ['DATA', 'Nano A0 · U1 pin 14'],
    ['CLOCK', 'Nano A1 · U1 pin 11 · U2 pin 11'],
    ['LATCH', 'Nano A2 · U1 pin 12 · U2 pin 12'],
    ['CHAIN', 'U1 pin 9 · U2 pin 14'],
    ['CE1', 'Nano A3 · DRV1 CE · 10 kΩ to GND'],
    ['CE2', 'Nano D10 · DRV2 CE · 10 kΩ to GND'],
    ['RAIL A', 'DRV1 LED · anodes of LEDs in holes 1–9'],
    ['RAIL B', 'DRV2 LED · anodes of LEDs in holes 10–16'],
    ['CHn gate (n = 1–16)', 'Register output for CHn (see §6.5) · 220 Ω · gate (pin 2) of Qn · 10 kΩ to GND'],
    ['LEDn cathode', 'LEDn cathode · drain (pin 3) of Qn'],
    ['SDA', 'Nano A4 · ADS1115 SDA'],
    ['SCL', 'Nano A5 · ADS1115 SCL'],
    ['OPT_OUT', 'OPT101 OUT · OPT101 1M · ADS1115 A1'],
    ['SUM', 'TL072 pin 2 · InGaAs cathode · Rf · Cf'],
    ['TIA_OUT', 'TL072 pin 1 · Rf · Cf · 10 kΩ protection resistor (other end → ADS1115 A0)'],
    ['U5B', 'TL072 pin 6 · TL072 pin 7'],
    ['M1 IN1–IN4', 'Nano D2–D5 · ULN2003 #1 IN1–IN4'],
    ['M2 IN1–IN4', 'Nano D6–D9 · ULN2003 #2 IN1–IN4'],
  ], [2000, 7360]),
];

// ---------------- 11 BOM ----------------
const s11 = [
  H1('11  Bill of materials'),
  Tbl(['Ref', 'Qty', 'Part', 'Specification / notes'], [
    ['—', '1', 'Arduino Nano', 'ATmega328P, 5 V logic, USB to laptop'],
    ['U1, U2', '2', '74HC595', 'SN74HC595N, DIP-16'],
    ['Q1–Q16', '16', '2N7000', 'N-channel MOSFET, TO-92, 60 V / 200 mA'],
    ['R1–R16', '16', 'Resistor 220 Ω', '¼ W, gate resistors'],
    ['R17–R32', '16', 'Resistor 10 kΩ', '¼ W, gate pull-downs'],
    ['R33, R34', '2', 'Resistor 10 kΩ', '¼ W, CE pull-downs'],
    ['R35', '1', 'Resistor 10 kΩ', '¼ W, ADC input protection'],
    ['Rf', '1', 'Resistor 1 MΩ', '¼ W, TIA feedback (100 kΩ alternative if saturating)'],
    ['Cf', '1', 'Capacitor 10 pF', 'Ceramic, TIA feedback'],
    ['C1–C6', '6', 'Capacitor 100 nF', 'Ceramic, decoupling'],
    ['DRV1, DRV2', '2', 'LD06AJSA LED driver module', '2.8–6 V in, 30–1500 mA adjustable, pins V1/CE/G/LED'],
    ['U3', '1', 'ADS1115 breakout', '16-bit I²C ADC with PGA, address 0x48'],
    ['U4', '1', 'OPT101 module (CJMCU-101)', 'Pins VCC, GND, 1M, OUT, −V, COM'],
    ['D1', '1', 'MTPD1346D-100', 'InGaAs PIN photodiode, TO-46, ≈800–1750 nm'],
    ['U5', '1', 'TL072CP', 'Dual JFET op-amp, DIP-8'],
    ['LED1–LED16', 'up to 16', 'Through-hole emitters', '395 nm, ≈405 nm, blue, green, yellow, orange, red, 850 nm, 940 nm, 1450, 1550, 1650, 1760, 1850 nm; holes 10–11 reserved'],
    ['M1, M2', '2 + 2', 'ULN2003 board + 28BYJ-48', 'Existing chamber drive'],
    ['—', '2', '5 V USB power bank', 'Physically separate units; see §3.2'],
    ['—', '—', 'Breadboards, 22 AWG solid wire, Dupont jumpers', 'As used'],
  ], [1300, 900, 2600, 4560]),
];

// ---------------- 12 Assembly ----------------
const s12 = [
  H1('12  Assembly procedure'),
  P('Build and test in stages. Each stage proves one part of the chain before the next depends on it, so a fault can only be in the stage just added. Disconnect both power banks whenever you move wires.'),
  H2('12.1  Stage 1: power and ground'),
  ...Steps([
    'Choose bus strips for +5V, GND and the two LED rails. Label them. Keep RAIL A and RAIL B on separate strips.',
    'Perform the isolation test and split-supply checks in §3.2.',
    'Run bank A (+) to the +5V strip and the bank junction to the GND strip. Jumper the matching strips on both sides of every breadboard.',
    'Join the Nano\'s GND to the GND strip. Leave the Nano\'s 5V pin unconnected.',
  ]),
  H2('12.2  Stage 2: shift registers'),
  ...Steps([
    'Seat U1 and U2 across the centre channel with pin 1 (notch end) in a consistent direction.',
    'Wire pins 16 and 10 to +5V, pins 8 and 13 to GND on both chips. Fit C1 and C2 directly across pins 16 and 8.',
    'Wire Nano A0 to U1 pin 14; A1 to pin 11 of both chips; A2 to pin 12 of both chips; U1 pin 9 to U2 pin 14.',
    'Optional check: put a spare LED with a 1 kΩ resistor from U1 pin 15 to GND and run TEST_MODE 3. It should blink once per sweep. Remove it afterwards.',
  ]),
  H2('12.3  Stage 3: one complete channel (CH8, 850 nm)'),
  ...Steps([
    'Fit DRV1: V1 to +5V, G to GND, CE to Nano A3 with a 10 kΩ resistor from CE to GND, LED pin to the RAIL A strip.',
    'Place a 2N7000 (flat face toward you: Source, Gate, Drain). Source to GND.',
    'U1 pin 7 (Q7) → 220 Ω → gate. Gate → 10 kΩ → GND.',
    'Drain → 850 nm LED cathode (short leg). LED anode (long leg) → RAIL A.',
    'Set DRV1 to its minimum. Run TEST_MODE 4 and look at the LED through a phone\'s front camera: a faint purple-white spot confirms it is lit.',
  ]),
  H2('12.4  Stage 4: remaining channels'),
  ...Steps([
    'Repeat Stage 3 for every channel using the map in §6.5. Holes 1–9 go to RAIL A; holes 10–16 go to RAIL B.',
    'Fit DRV2 exactly like DRV1 but with CE to Nano D10 and LED to RAIL B.',
    'Run TEST_MODE 3. Visible LEDs should light in order 1 → 16; check IR ones with the phone camera. SWIR LEDs (above about 1100 nm) won\'t show on a camera; they are checked with the InGaAs detector in Stage 6.',
    'Set DRV2\'s current as in §6.2.',
  ]),
  H2('12.5  Stage 5: ADS1115 and OPT101'),
  ...Steps([
    'ADS1115: VDD to +5V, GND and ADDR to GND, SDA to Nano A4, SCL to Nano A5. Fit C3.',
    'Run TEST_MODE 1. The serial monitor must report a device at 0x48.',
    'OPT101: VCC to +5V; GND, −V and COM to GND; 1M jumpered to OUT; OUT to ADS1115 A1. Fit C4.',
    'Run TEST_MODE 2. The A1 reading must rise when light falls on the sensor and fall when it is covered.',
  ]),
  H2('12.6  Stage 6: InGaAs amplifier'),
  ...Steps([
    'Test the photodiode\'s three leads with the meter: identify anode and cathode with diode mode, and check whether the case lead is connected to either.',
    'Seat the TL072. Pin 8 to +5V and pin 4 to −5V, with C5 and C6 to GND right at the chip. Confirm about 10 V between pins 8 and 4.',
    'Pin 3 to GND. Rf (1 MΩ) and Cf (10 pF) both from pin 1 to pin 2. Side B: pin 6 to pin 7, pin 5 to GND.',
    'Photodiode cathode to pin 2, anode to GND, case per the continuity result.',
    'Before connecting the ADC, power up and measure pin 1 with the meter: near 0 V in darkness, positive under a lit 850 nm or 940 nm LED. If it goes negative, the diode is reversed.',
    'Connect pin 1 through the 10 kΩ resistor to ADS1115 A0. Run TEST_MODE 2 and confirm A0 responds.',
  ]),
  H2('12.7  Stage 7: final checks'),
  ...Steps([
    'Re-check every connection against the net list (§10).',
    'Confirm both CE lines read 0 V with the Nano held in reset (press and hold its reset button).',
    'Run TEST_MODE 5 with the Python logger and inspect the plot (§13).',
  ]),
];

// ---------------- 13 Bring-up ----------------
const s13 = [
  H1('13  Bring-up and calibration'),
  H2('13.1  Firmware test modes'),
  P('The firmware in Appendix A has five modes, selected by `#define TEST_MODE` at the top of the sketch. Upload, then open the Serial Monitor at 115200 baud.'),
  Tbl(['Mode', 'Purpose', 'Expected result', 'If it fails'], [
    ['1', 'I²C scan', '"found 0x48"', 'Check SDA/SCL (A4/A5), ADS1115 power, ADDR to GND'],
    ['2', 'Live detector readings', 'Both numbers change with light', 'OPT101: 1M jumper, −V/COM grounds. InGaAs: orientation, −5V present'],
    ['3', 'Walk through all 16 channels', 'Each LED lights in turn for 0.4 s', 'See §15'],
    ['4', 'Hole 8 on for 2 s, off for 3 s', 'Steady pulse; use it to set driver current', 'Driver, rail or CH8 wiring'],
    ['5', 'Full sweep with dark subtraction', 'CSV lines, then "END"', 'Run the Python logger to visualise'],
  ], [800, 2400, 2800, 3360]),
  H2('13.2  Calibration steps'),
  ...Steps([
    '**Driver currents.** Set DRV1 to its minimum and DRV2 to the target from §6.2, measuring with the meter in series.',
    '**ADC gain.** In mode 5, if any reading reaches about 32767 counts it is clipping; change to GAIN_TWOTHIRDS. If the largest readings are under 8000 counts, GAIN_TWO doubles the resolution.',
    '**TIA gain.** If InGaAs readings sit at the same high value for all SWIR channels, the amplifier is saturating; fit Rf = 100 kΩ (§7.2).',
    '**Settle time.** Repeat a sweep several times. If the lit readings vary more than a few counts while the dark readings are stable, increase `SETTLE_MS` from 8 to 20.',
    '**Ambient light.** Close the chamber. Dark readings should be small and steady. Large or drifting dark values mean light is leaking in.',
    '**Reference.** Record a sweep with a reference sample (or empty chamber) and divide later sweeps by it to remove LED-to-LED brightness differences.',
  ]),
];

// ---------------- 14 Firmware ----------------
const s14 = [
  H1('14  Firmware and software'),
  H2('14.1  Measurement sequence'),
  P('For each hole the firmware performs the steps below. The order of steps 2 and 3 matters: the MOSFET must be on before the driver is enabled, so the driver never discharges into an LED at switch-on.'),
  ...Steps([
    'Turn both drivers off and clear the registers; wait `SETTLE_MS`; read A0 and A1 as the dark values.',
    'Shift in the pattern with only this hole\'s bit set and latch it (selects the MOSFET).',
    'Raise the CE line for this hole\'s rail.',
    'Wait `SETTLE_MS` (8 ms default).',
    'Read A0 (InGaAs) and A1 (OPT101) as the lit values.',
    'Drop CE and clear the registers.',
    'Print `hole,dark_ingaas,dark_opt101,ingaas,opt101`.',
  ]),
  P('Each LED is lit for about 8 ms of settling plus two 8 ms conversions, roughly 25 ms per pass. A full sweep of 16 holes, including the dark readings, takes about 0.8 s.'),
  H2('14.2  Libraries and tools'),
  P('Arduino: install **Adafruit ADS1X15** from the Library Manager. Python 3: `pip install pyserial matplotlib`. The Python logger (Appendix B) waits for the header line, collects one sweep, saves `lio_sweep.csv` and `lio_sweep.png`, and plots the dark-corrected response of both detectors against hole number. Close the Arduino Serial Monitor before running it, because only one program can hold the port.'),
];

// ---------------- 15 Troubleshooting ----------------
const s15 = [
  H1('15  Troubleshooting'),
  Tbl(['Symptom', 'Likely cause', 'Check / fix'], [
    ['"ADS1115 not found"', 'I²C wiring or power', 'A4 = SDA, A5 = SCL; VDD and GND; ADDR to GND; run mode 1'],
    ['No LED lights in mode 3', 'Drivers not enabled or registers inactive', 'CE wiring to A3/D10; driver V1 and G; rail connected to LED pin; /OE grounded; /SRCLR high'],
    ['Pattern appears on the wrong holes, offset by 8', 'Byte order or chain wiring', 'U1 pin 9 → U2 pin 14; DATA to U1 only'],
    ['U2 copies U1', 'U2 SER wired to DATA', 'U2 pin 14 must come from U1 pin 9'],
    ['Pattern scrambled', 'CLOCK and LATCH swapped', 'Pin 11 = CLOCK (A1), pin 12 = LATCH (A2)'],
    ['One channel dead', 'MOSFET orientation, LED polarity, missing gate resistor', 'S-G-D order; long leg to the rail; meter the gate (≈5 V when selected)'],
    ['One LED never turns off', 'MOSFET damaged or gate floating', 'Check the 10 kΩ pull-down; replace the 2N7000'],
    ['LED dim', 'Driver current low or rail sagging', 'Measure current; check bank A voltage under load'],
    ['OPT101 pinned at 0 V or ≈3.7 V', 'No feedback or no ground reference', '1M jumpered to OUT; −V and COM to GND'],
    ['InGaAs reading ≈0 always', 'Diode reversed, case lead shorting the summing node, or −5V missing', 'Measure pin 1 with a meter under an 850 nm LED; check case lead; check −5V'],
    ['InGaAs reading high and identical for all SWIR channels', 'TIA saturated', 'Fit Rf = 100 kΩ'],
    ['−5V disappears after a minute', 'Bank B auto-sleep', 'Low-current mode or a 220 Ω dummy load (§3.2)'],
    ['Readings jumpy', 'Settling, rail noise, light leaks', 'Raise SETTLE_MS; check decoupling caps; motors stationary; close the chamber'],
    ['Nano resets during motor moves', 'Ground bounce', 'Short, direct GND wiring from ULN2003 boards to the bank junction'],
  ], [2700, 2900, 3760]),
];

// ---------------- 16 Safety ----------------
const s16 = [
  H1('16  Safety and limitations'),
  H2('16.1  Optical safety'),
  P('The 395 nm and 405 nm LEDs emit near-ultraviolet light, which can harm the eyes with prolonged direct viewing and appears dimmer than it is. The 850 nm, 940 nm and SWIR emitters are invisible: the eye\'s blink reflex gives no protection, and you can\'t tell if they are on. Don\'t look into any emitter while it is driven, and run sweeps with the chamber closed. The 300 nm UVC emitter originally planned for hole 1 has been removed. Any future UVC part needs its own boost supply (its forward voltage is about 6.5 V), full enclosure, and a lid interlock that cuts its drive in hardware.'),
  H2('16.2  Electrical safety'),
  P('USB power banks can deliver several amps into a short. Never join the + and − of the same bank, and never stack two ports of the same bank. Disconnect both banks before rewiring. The driver modules can become warm at higher settings; keep them clear of wiring insulation. Don\'t charge either bank while it is wired into the circuit.'),
  H2('16.3  Known limitations'),
  P('Hole 16 (1850 nm) is beyond the InGaAs detector\'s range and hole 15 (1760 nm) is at its edge, so those channels give little or no signal until an extended-range detector is fitted. RAIL A runs the 5 mm LEDs at 30 mA, above their 20 mA continuous rating, which is acceptable only at the low duty cycle of a sweep. The motors and the optics share the +5V rail, so measurements must be taken with the motors stationary. All values in this document are development values; the open items in §1.2 should be resolved before results are relied upon.'),
];

// ---------------- 17 Corrections ----------------
const s17 = [
  H1('17  Changes from earlier build instructions'),
  P('The following corrections were made while consolidating the design. Check an existing breadboard build against each one.'),
  Tbl(['#', 'Item', 'Earlier instruction', 'Corrected design', 'Reason'], [
    ['1', 'InGaAs photodiode orientation', 'Cathode to +5V, anode to TL072 pin 2', 'Cathode to pin 2, anode to GND', 'Earlier wiring drove the output negative, which can damage the ADS1115'],
    ['2', 'ADC input protection', 'TL072 output direct to ADS1115', '10 kΩ series resistor', 'Limits fault current into the ADC'],
    ['3', 'ADS1115 tolerance', 'Stated to tolerate negative input', 'Inputs limited to GND − 0.3 V', 'Datasheet absolute maximum'],
    ['4', 'InGaAs case lead', 'Always grounded', 'Test first; ground only if isolated or tied to the anode', 'Grounding a cathode-tied case shorts the summing node'],
    ['5', 'DRV1 current', '≈20 mA', 'Minimum ≈30 mA, low duty cycle only', 'Module range starts at 30 mA'],
    ['6', 'Nano power', 'Bank A to the 5V pin, unplugged for uploads', 'USB only; 5V pin not connected', 'Logging needs USB; avoids back-feeding'],
    ['7', 'Switching order', 'Enable CE, then select channel', 'Select channel, then enable CE; CE off between channels', 'Avoids discharging the driver output into an LED'],
    ['8', 'Dark reading', 'None', 'Dark reading before each lit reading', 'Removes ambient light and offsets'],
    ['9', 'Holes 10–11', '1200 / 1300 nm', 'Reserved (SMD parts removed)', 'As built'],
  ], [400, 1700, 2200, 2400, 2660], { size: 17 }),
];

// ---------------- Appendix A/B ----------------
const arduino = fs.readFileSync('docbuild/lio_firmware.ino', 'utf8');
const python = fs.readFileSync('docbuild/lio_logger.py', 'utf8');
const appA = [H1('Appendix A  Arduino firmware'), P('File: `lio_firmware.ino`. Requires the Adafruit ADS1X15 library.'), ...Code(arduino)];
const appB = [H1('Appendix B  Python logger'), P('File: `lio_logger.py`. Usage: `python lio_logger.py COM3` (Windows) or `python3 lio_logger.py /dev/tty.usbserial-XXXX` (macOS). Set `TEST_MODE 5` in the firmware first.'), ...Code(python)];

// ======================================================================
const header = new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
  children: [new TextRun({ text: 'LIO-ELEC-001 Rev A · LIO V3 Optical Head Electronics', size: 16, color: '888888' })] })] });
const footer = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
  children: [new TextRun({ children: ['Page ', PageNumber.CURRENT, ' of ', PageNumber.TOTAL_PAGES], size: 16, color: '888888' })] })] });

const portrait = { page: { size: { width: 12240, height: 15840 }, margin: { top: 1300, bottom: 1200, left: 1440, right: 1440, header: 600, footer: 600 } } };
const landscape = { page: { size: { width: 12240, height: 15840, orientation: PageOrientation.LANDSCAPE }, margin: { top: 720, bottom: 720, left: 720, right: 720, header: 360, footer: 360 } } };

const doc = new Document({
  creator: 'LIO project', title: 'LIO V3 Optical Head — Electronics Technical Description',
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 32, bold: true, color: ACCENT, font: FONT }, paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 25, bold: true, color: '2B3445', font: FONT }, paragraph: { spacing: { before: 260, after: 100 }, outlineLevel: 1, keepNext: true } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 22, bold: true, color: '2B3445', font: FONT }, paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: { config: stepRefs.map(ref => ({ reference: ref, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] })) },
  sections: [
    { properties: portrait, children: title },
    { properties: portrait, headers: { default: header }, footers: { default: footer },
      children: [...contents, ...s1, ...s2, ...s3, ...s4, ...s5, ...s6, ...s7, ...s8] },
    { properties: landscape, headers: { default: header }, footers: { default: footer }, children: s9a },
    { properties: portrait, headers: { default: header }, footers: { default: footer },
      children: [...s9b, ...s10, ...s11, ...s12, ...s13, ...s14, ...s15, ...s16, ...s17, ...appA, ...appB] },
  ],
});

Packer.toBuffer(doc).then(b => { fs.writeFileSync('LIO_V3_Electronics_Technical_Document.docx', b); console.log('written', b.length); });
