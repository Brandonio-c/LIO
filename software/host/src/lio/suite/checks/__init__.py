"""The test catalogue (plan §6). Importing this package registers every test."""

from lio.suite.checks import (  # noqa: F401
    interactive,
    t01_t02_link,
    t03_t04_adc_sr,
    t05_channels,
    t06_detectors,
    t07_t08_timing_sweep,
    t09_motors,
    t10_safety,
)
