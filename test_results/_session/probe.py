"""Use the ADS1115's spare inputs A2/A3 as probes: light one hole for 200 ms and
report each probe's voltage before / during / after. Usage: probe.py cfg port hole [label2] [label3]"""
import sys, time
from statistics import mean
from lio.config import load_config
from lio.device import LIODevice
from lio.transport import SerialTransport

cfg = load_config(sys.argv[1]); port = sys.argv[2]; hole = int(sys.argv[3])
labels = {2: sys.argv[4] if len(sys.argv) > 4 else "A2", 3: sys.argv[5] if len(sys.argv) > 5 else "A3"}
dev = LIODevice(SerialTransport(port, cfg.section.integer("link.baud")), cfg)
log = open(f"{sys.argv[6] if len(sys.argv) > 6 else 'test_results'}/probe_log.txt", "a")
try:
    dev.open()
    for ch in (2, 3):
        raw = [x.raw for x in dev.adc_stream(ch, 40, 10, led=(hole, 10, 30))]
        before, lit, after = mean(raw[2:10]), mean(raw[13:29]), mean(raw[32:])
        v = lambda c: c * 0.125 / 1000
        clip = " (≥4.1 V: reads as 4.1, the ADC's ceiling)" if max(raw) >= 32700 else ""
        line = (f"hole {hole:2d}  {labels[ch]:<22s} before {v(before):6.3f} V   "
                f"LIT {v(lit):6.3f} V   after {v(after):6.3f} V   change {v(lit-before):+6.3f} V{clip}")
        print(line); log.write(time.strftime("%H:%M:%S ") + line + "\n")
        time.sleep(0.2)
finally:
    dev.close(); log.close()
    print("everything off")
