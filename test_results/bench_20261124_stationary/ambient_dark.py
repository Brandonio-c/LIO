"""Source-off ambient check (bench 2026-11-24). Reads ADC only: no LED, no motion.

Frozen design: room-light states ON, OFF, ON; 3 records per state; each record is a
64-sample raw ADC stream per detector at the configured rate, with STATUS verified
dark (CE1=CE2=0, no motor running) before every record. The owner's answer for each
room-light state is read from stdin (one line per state, given by the owner for that
occurrence). Output: ambient_dark.json next to this script.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

from lio.buildinfo import loaded_build_identity
from lio.config import load_config
from lio.device import LIODevice
from lio.transport import SerialTransport

PORT = sys.argv[1]
STATES = ["ON", "OFF", "ON"]
RECORDS, N = 3, 64
ADC = {"ingaas": 0, "opt101": 1}

cfg = load_config()
out: dict = {"design": {"states": STATES, "records_per_state": RECORDS, "samples": N,
                        "adc": ADC, "light": "none (source-off)"},
             "build": loaded_build_identity(), "port": PORT, "states": []}
dev = LIODevice(SerialTransport(PORT, cfg.section.integer("link.baud")), cfg)
with dev:
    info = dev.info(refresh=True)
    out["info"] = dict(info.values)
    for k, state in enumerate(STATES):
        print(f"\n[LIO] Ambient state {k + 1}/3: set the ROOM LIGHTS {state} and keep the "
              f"chamber closed. Confirm lights are {state} [y/n, a = abort]: ", flush=True)
        ans = sys.stdin.readline().strip().lower()
        rec = {"state": state, "owner_answer": ans, "answered_at": time.strftime("%H:%M:%S"),
               "records": []}
        if ans not in ("y", "yes"):
            rec["skipped"] = "owner did not confirm"
            out["states"].append(rec)
            break
        for r in range(RECORDS):
            st = dev.status()
            assert st.as_int("ce1") == 0 and st.as_int("ce2") == 0, "not dark"
            one = {"t": time.strftime("%H:%M:%S"), "status": {"ce1": st.as_int("ce1"),
                   "ce2": st.as_int("ce2"), "ch": st.as_int("ch")}}
            for det, ch in ADC.items():
                s = dev.adc_stream(ch, N)
                raw = [x.raw for x in s]
                one[det] = {"raw": raw, "t_us": [x.t_us for x in s],
                            "mean": statistics.fmean(raw), "sd": statistics.stdev(raw)}
            rec["records"].append(one)
            print(f"  record {r}: ingaas mean {one['ingaas']['mean']:.1f} sd "
                  f"{one['ingaas']['sd']:.2f} | opt101 mean {one['opt101']['mean']:.1f} sd "
                  f"{one['opt101']['sd']:.2f}", flush=True)
        out["states"].append(rec)
Path(__file__).with_name("ambient_dark.json").write_text(json.dumps(out, indent=1))
print("saved ambient_dark.json", flush=True)
