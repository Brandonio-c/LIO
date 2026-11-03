"""Sweep and measurement CSV files.

``write_sweep_csv`` produces exactly the format of the original logger
(TEST_MODE 5 logger, ``software/logger/lio_logger.py`` at git tag ``fw-testmode-v1``)::

    hole,label,dark_ingaas,dark_opt101,ingaas,opt101,net_ingaas_V,net_opt101_V
    1,395,40,200,41,1124,0.00012,0.1155

Counts are raw ADS1115 readings; the net columns are (lit - dark) in volts at
the configured gain, rounded to 5 decimals; rows end in CRLF (``csv`` default).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from pathlib import Path

from lio.config import HwConfig
from lio.device import Meas

SWEEP_HEADER = (
    "hole",
    "label",
    "dark_ingaas",
    "dark_opt101",
    "ingaas",
    "opt101",
    "net_ingaas_V",
    "net_opt101_V",
)
MEAS_HEADER = (
    "test",
    "hole",
    "label",
    "dark_ingaas",
    "dark_opt101",
    "ingaas",
    "opt101",
    "net_ingaas",
    "net_opt101",
    "t_on_ms",
)


def sweep_rows(records: Iterable[Meas], cfg: HwConfig) -> list[list[object]]:
    volts_per_count = cfg.lsb_mv / 1000.0
    return [
        [
            m.hole,
            cfg.channel(m.hole).label,
            m.dark0,
            m.dark1,
            m.lit0,
            m.lit1,
            round((m.lit0 - m.dark0) * volts_per_count, 5),
            round((m.lit1 - m.dark1) * volts_per_count, 5),
        ]
        for m in records
    ]


def sweep_csv_text(records: Iterable[Meas], cfg: HwConfig) -> str:
    buf = io.StringIO(newline="")
    w = csv.writer(buf)
    w.writerow(SWEEP_HEADER)
    w.writerows(sweep_rows(records, cfg))
    return buf.getvalue()


def write_sweep_csv(path: Path, records: Iterable[Meas], cfg: HwConfig) -> Path:
    with path.open("w", newline="") as f:
        f.write(sweep_csv_text(records, cfg))
    return path


def write_meas_csv(path: Path, log: Iterable[tuple[str, Meas]], cfg: HwConfig) -> Path:
    """Every MEAS and SWEEP record of a run, with the test that took it."""
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(MEAS_HEADER)
        for test_id, m in log:
            w.writerow(
                [
                    test_id,
                    m.hole,
                    cfg.channel(m.hole).label,
                    m.dark0,
                    m.dark1,
                    m.lit0,
                    m.lit1,
                    m.net("ingaas"),
                    m.net("opt101"),
                    m.t_on_ms,
                ]
            )
    return path
