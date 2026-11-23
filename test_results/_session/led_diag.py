"""LED chain diagnosis: does the firmware select + enable, and does any detector see light?"""
import json, sys, time
from statistics import mean
from lio.config import load_config
from lio.device import LIODevice
from lio.transport import SerialTransport

cfg = load_config(sys.argv[1]); port = sys.argv[2]; out = {}
dev = LIODevice(SerialTransport(port, cfg.section.integer("link.baud")), cfg)
try:
    dev.open()
    info = dev.info(); st = dev.status()
    out["info"] = {k: info.as_str(k) for k in ("fw", "adc_ok", "wdt_a_ms", "wdt_b_ms")}
    out["status_idle"] = {k: st.as_str(k) for k in ("ch", "ce1", "ce2", "mask", "faults")}
    print("INFO", out["info"]); print("STATUS idle", out["status_idle"])
    # 1. firmware side: select + CE during a 500 ms flash
    for hole in (7, 3, 13):
        dev.command(f"CH {hole} ON 500")
        s = dev.status()
        r = {k: s.as_str(k) for k in ("ch", "ce1", "ce2", "mask", "faults")}
        dev.off()
        print(f"STATUS during hole {hole}:", r); out[f"status_h{hole}"] = r
        time.sleep(0.2)
    # 2. every ADC input, dark vs hole 7 lit (samples 10..29 lit, 10 ms apart)
    for hole in (7, 8):
        for ch in range(4):
            s = dev.adc_stream(ch, 40, 10, led=(hole, 10, 30))
            raw = [x.raw for x in s]
            d, l = mean(raw[:10] + raw[32:]), mean(raw[12:30])
            print(f"hole {hole} ADC A{ch}: dark {d*0.125:8.1f} mV  lit {l*0.125:8.1f} mV  diff {(l-d)*0.125:+7.1f} mV")
            out[f"stream_h{hole}_a{ch}"] = raw
            time.sleep(0.1)
    # 3. MEAS sweep, all holes
    print("MEAS  hole  ingaas_net  opt101_net (counts)")
    for h in range(1, 17):
        m = dev.meas(h, 20, 4)
        out[f"meas_{h}"] = {"ingaas": [m.dark("ingaas"), m.lit("ingaas")], "opt101": [m.dark("opt101"), m.lit("opt101")]}
        print(f"      {h:4d}  {m.net('ingaas'):+9d}  {m.net('opt101'):+9d}   (dark {m.dark('ingaas')}/{m.dark('opt101')})")
    print("STATUS end", {k: dev.status().as_str(k) for k in ("ch", "ce1", "ce2", "mask", "faults")})
finally:
    dev.close()
    print("closed: everything off")
stamp = time.strftime("%Y%m%d-%H%M%S")
p = f"{sys.argv[3]}/{stamp}_led_diag.json"; json.dump(out, open(p, "w"), indent=1); print("saved", p)
