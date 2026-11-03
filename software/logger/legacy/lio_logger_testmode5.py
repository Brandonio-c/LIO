# LEGACY (kept unchanged below this header, M0 approval 11): the original
# logger for the TEST_MODE 5 firmware (software/firmware/legacy/
# lio_firmware_testmode). It does not work with firmware v2; use
# software/logger/lio_logger.py (same command line, same CSV/PNG) instead.
#
# LIO V3 sweep logger (LIO-ELEC-001 Rev A)
# Usage:  python lio_logger.py COM3      (Windows)
#         python3 lio_logger.py /dev/tty.usbserial-XXXX   (macOS)
# Needs:  pip install pyserial matplotlib ; firmware TEST_MODE 5
import sys, csv, time
import serial
import matplotlib.pyplot as plt

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
BAUD = 115200
VOLTS_PER_COUNT = 4.096 / 32768      # GAIN_ONE

LABELS = {1: "395", 2: "405", 3: "blue", 4: "green", 5: "yellow", 6: "orange",
          7: "red", 8: "850", 9: "940", 10: "res.", 11: "res.", 12: "1450",
          13: "1550", 14: "1650", 15: "1760", 16: "1850"}

ser = serial.Serial(PORT, BAUD, timeout=5)
time.sleep(2)                          # Nano resets when the port opens

rows, capturing = [], False
while True:
    line = ser.readline().decode(errors="ignore").strip()
    if not line:
        continue
    if line.startswith("hole,"):       # start of a sweep
        rows, capturing = [], True
        continue
    if line == "END" and capturing:
        break
    if capturing:
        try:
            h, di, dop, ig, op = (int(v) for v in line.split(","))
            rows.append((h, di, dop, ig, op))
        except ValueError:
            pass
ser.close()

with open("lio_sweep.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["hole", "label", "dark_ingaas", "dark_opt101", "ingaas", "opt101",
                "net_ingaas_V", "net_opt101_V"])
    for h, di, dop, ig, op in rows:
        w.writerow([h, LABELS.get(h, "?"), di, dop, ig, op,
                    round((ig - di) * VOLTS_PER_COUNT, 5),
                    round((op - dop) * VOLTS_PER_COUNT, 5)])
print("saved lio_sweep.csv")

holes = [r[0] for r in rows]
net_ig = [(r[3] - r[1]) * VOLTS_PER_COUNT for r in rows]
net_op = [(r[4] - r[2]) * VOLTS_PER_COUNT for r in rows]

plt.figure(figsize=(10, 5))
plt.plot(holes, net_op, "o-", label="OPT101 (silicon)")
plt.plot(holes, net_ig, "s-", label="InGaAs (SWIR)")
plt.xticks(holes, [LABELS.get(h, "?") for h in holes], rotation=45)
plt.xlabel("channel / wavelength (nm)")
plt.ylabel("net signal (V, dark-subtracted)")
plt.title("LIO sweep")
plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
plt.savefig("lio_sweep.png", dpi=120)
print("saved lio_sweep.png")
plt.show()
