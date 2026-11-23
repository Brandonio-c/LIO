"""Passive OPT101 check: ADC reads only (no LEDs, no motors, no POWER WAKE)."""
import json, statistics, sys, time
from pathlib import Path
from lio.config import load_config
from lio.device import LIODevice
from lio.transport import SerialTransport

ROOT = Path("/Users/coleloughbc/Documents/VSCode-Local/LIO")
cfg = load_config(ROOT / "test_results/_session/lio_hw_nowake.yaml")
assert not cfg.section.raw("power.wake")
dev = LIODevice(SerialTransport("/dev/cu.usbmodem101"), cfg)
out = {}
banner = dev.open()
try:
    out["banner"] = str(banner)
    out["info"] = dev.info(refresh=True).values
    out["status"] = dev.status().values
    out["i2c_scan"] = dev.command("I2C SCAN", timeout=5).fields.values
    for gain in ("1", "2/3"):
        lsb = dev.adc_gain(gain)
        for ch in range(4):
            r = dev.adc_read(ch, 64)
            out[f"g{gain}_ch{ch}"] = {"mv": round(r.mv, 2), "std_mv": round(r.std * lsb, 3) if r.std is not None else None}
    lsb = dev.adc_gain("1")
    dev.adc_rate(860)  # ~1.2 ms per sample: resolves 60/120 Hz
    for ch in (1, 2):
        s = dev.adc_stream(ch, 48, 0)
        out[f"stream_ch{ch}"] = [[x.t_us, round(x.raw * lsb, 2)] for x in s]
    dev.adc_rate(128)
finally:
    dev.close()
(ROOT / "test_results/opt101_check/passive_probe.json").write_text(json.dumps(out, indent=1, default=str))
print(json.dumps({k: v for k, v in out.items() if not k.startswith("stream")}, indent=1, default=str))
