# LIO V3 sweep logger, rewritten on lio.device for firmware v2 (docs/PROTOCOL.md).
# Same command line and the same outputs as the original
# (git tag fw-testmode-v1, which needed the TEST_MODE 5 firmware):
#
#   python lio_logger.py /dev/cu.usbserial-XXXX     (macOS)
#   python lio_logger.py COM3                       (Windows)
#
# Writes lio_sweep.csv (raw counts + dark-subtracted volts) and lio_sweep.png.
# Needs the host package:  pip install -e software/host
# Equivalent:  lio --port <PORT> sweep --csv lio_sweep.csv --plot lio_sweep.png
from __future__ import annotations

import sys
from pathlib import Path

try:
    import lio  # noqa: F401
except ImportError:  # running from a checkout without installing the package
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host" / "src"))

from lio.config import load_config
from lio.csvout import write_sweep_csv
from lio.device import LIODevice
from lio.report import plot_sweep
from lio.transport import SerialTransport


def main(argv: list[str]) -> int:
    port = argv[1] if len(argv) > 1 else "COM3"
    cfg = load_config()
    with LIODevice(SerialTransport(port, cfg.section.integer("link.baud")), cfg) as dev:
        dev.check_compatible()
        sweep = dev.sweep()
    write_sweep_csv(Path("lio_sweep.csv"), sweep.records, cfg)
    print("saved lio_sweep.csv")
    plot_sweep(Path("lio_sweep.png"), sweep.records, cfg)
    print("saved lio_sweep.png")
    if "--no-show" not in argv:
        import matplotlib.pyplot as plt

        img = plt.imread("lio_sweep.png")
        plt.figure(figsize=(10, 5))
        plt.imshow(img)
        plt.axis("off")
        plt.show()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
