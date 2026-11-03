"""Load and validate ``software/config/lio_hw.yaml`` (plan §5.4).

All hardware constants and thresholds come from this file; test logic must not
hard-code them. :func:`load_config` returns an immutable :class:`HwConfig`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DETECTORS = ("opt101", "ingaas")
EXPECT_LEVELS = ("signal", "weak", "none")
N_HOLES = 16


class ConfigError(ValueError):
    """The configuration file is missing, malformed or inconsistent."""


def default_config_path() -> Path:
    """``software/config/lio_hw.yaml`` relative to this source tree."""
    return Path(__file__).resolve().parents[3] / "config" / "lio_hw.yaml"


@dataclass(frozen=True)
class Channel:
    hole: int
    label: str
    wavelength_nm: float | None
    rail: str
    fitted: bool
    expect: dict[str, str]

    def expect_for(self, detector: str) -> str:
        """``signal`` | ``weak`` | ``none`` for this detector."""
        return self.expect.get(detector, "none")

    @property
    def expected_detectors(self) -> tuple[str, ...]:
        return tuple(d for d in DETECTORS if self.expect_for(d) != "none")


@dataclass(frozen=True)
class Detector:
    name: str
    adc_channel: int
    range_nm: tuple[float, float]
    saturation_counts: int


@dataclass(frozen=True)
class Limits:
    """Firmware limits mirrored from config.h (cross-checked against INFO in T02.3)."""

    values: dict[str, int]

    def __getitem__(self, key: str) -> int:
        try:
            return self.values[key]
        except KeyError as e:
            raise ConfigError(f"firmware.limits.{key} missing") from e


class Section:
    """Typed read-only access to a nested mapping by dotted path."""

    def __init__(self, data: dict[str, Any], name: str) -> None:
        self._data = data
        self._name = name

    def raw(self, path: str) -> Any:
        node: Any = self._data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                raise ConfigError(f"{self._name}.{path} missing")
            node = node[part]
        return node

    def num(self, path: str) -> float:
        v = self.raw(path)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ConfigError(f"{self._name}.{path} must be a number, got {v!r}")
        return float(v)

    def integer(self, path: str) -> int:
        v = self.raw(path)
        if isinstance(v, bool) or not isinstance(v, int):
            raise ConfigError(f"{self._name}.{path} must be an integer, got {v!r}")
        return v

    def span(self, path: str) -> tuple[float, float]:
        v = self.raw(path)
        pair = isinstance(v, list) and len(v) == 2
        if not (pair and all(isinstance(x, (int, float)) for x in v)):
            raise ConfigError(f"{self._name}.{path} must be [low, high]")
        lo, hi = float(v[0]), float(v[1])
        if lo > hi:
            raise ConfigError(f"{self._name}.{path}: low > high")
        return lo, hi

    def ints(self, path: str) -> tuple[int, ...]:
        v = self.raw(path)
        if not (isinstance(v, list) and all(isinstance(x, int) for x in v)):
            raise ConfigError(f"{self._name}.{path} must be a list of integers")
        return tuple(v)

    def mapping(self, path: str) -> dict[str, Any]:
        v = self.raw(path)
        if not isinstance(v, dict):
            raise ConfigError(f"{self._name}.{path} must be a mapping")
        return {str(k): val for k, val in v.items()}


@dataclass(frozen=True)
class HwConfig:
    path: Path
    sha256: str
    data: dict[str, Any]
    channels: tuple[Channel, ...]
    detectors: dict[str, Detector]
    limits: Limits

    @property
    def thresholds(self) -> Section:
        return Section(self.data["thresholds"], "thresholds")

    @property
    def sim(self) -> Section:
        return Section(self.data.get("sim", {}), "sim")

    @property
    def section(self) -> Section:
        return Section(self.data, "config")

    @property
    def provisional(self) -> bool:
        return bool(self.data["thresholds"].get("provisional", False))

    def channel(self, hole: int) -> Channel:
        if not 1 <= hole <= N_HOLES:
            raise ConfigError(f"hole {hole} out of range 1-{N_HOLES}")
        return self.channels[hole - 1]

    def rail_holes(self, rail: str) -> tuple[int, ...]:
        return tuple(c.hole for c in self.channels if c.rail == rail)

    def detector_for_adc(self, adc_channel: int) -> str | None:
        for d in self.detectors.values():
            if d.adc_channel == adc_channel:
                return d.name
        return None

    @property
    def fw_name(self) -> str:
        return str(self.data["firmware"]["name"])

    @property
    def fw_proto(self) -> int:
        return int(self.data["firmware"]["proto"])

    @property
    def fw_min_version(self) -> str:
        return str(self.data["firmware"]["min_version"])

    @property
    def lsb_mv(self) -> float:
        adc = self.data["adc"]
        return float(adc["lsb_mv"][str(adc["gain"])])

    def wdt_ms(self, rail: str) -> int:
        return self.limits["wdt_a_ms" if rail == "A" else "wdt_b_ms"]


def _require(data: dict[str, Any], key: str, where: str) -> Any:
    if key not in data:
        raise ConfigError(f"{where}.{key} missing")
    return data[key]


def _parse_channels(raw: Any, rails: dict[str, Any]) -> tuple[Channel, ...]:
    if not isinstance(raw, list) or len(raw) != N_HOLES:
        raise ConfigError(f"channels must list exactly {N_HOLES} holes")
    out: list[Channel] = []
    for i, c in enumerate(raw, start=1):
        if not isinstance(c, dict):
            raise ConfigError(f"channels[{i}] must be a mapping")
        hole = _require(c, "hole", f"channels[{i}]")
        if hole != i:
            raise ConfigError(f"channels must be ordered 1-{N_HOLES}; entry {i} is hole {hole}")
        rail = _require(c, "rail", f"hole {hole}")
        if rail not in rails:
            raise ConfigError(f"hole {hole}: unknown rail {rail!r}")
        if hole not in rails[rail]["holes"]:
            raise ConfigError(f"hole {hole}: rail {rail} does not list it")
        expect = c.get("expect") or {}
        if not isinstance(expect, dict):
            raise ConfigError(f"hole {hole}: expect must be a mapping")
        for det, level in expect.items():
            if det not in DETECTORS:
                raise ConfigError(f"hole {hole}: unknown detector {det!r}")
            if level not in EXPECT_LEVELS:
                raise ConfigError(f"hole {hole}: expect level {level!r} not in {EXPECT_LEVELS}")
        fitted = bool(_require(c, "fitted", f"hole {hole}"))
        if not fitted and any(v != "none" for v in expect.values()):
            raise ConfigError(f"hole {hole}: unfitted holes cannot expect a signal")
        wl = c.get("wavelength_nm")
        out.append(
            Channel(
                hole=hole,
                label=str(_require(c, "label", f"hole {hole}")),
                wavelength_nm=float(wl) if wl is not None else None,
                rail=rail,
                fitted=fitted,
                expect={str(k): str(v) for k, v in expect.items()},
            )
        )
    return tuple(out)


def _check_coverage(channels: tuple[Channel, ...], detectors: dict[str, Detector]) -> None:
    """Expected detectors must cover the emitter wavelength (T01.3)."""
    for ch in channels:
        if ch.wavelength_nm is None:
            continue
        for det in ch.expected_detectors:
            lo, hi = detectors[det].range_nm
            weak = ch.expect_for(det) == "weak"
            if not weak and not lo <= ch.wavelength_nm <= hi:
                raise ConfigError(
                    f"hole {ch.hole}: {det} expected to see {ch.wavelength_nm} nm, "
                    f"outside its range {lo}-{hi} nm"
                )


def parse_config(data: Any, path: Path, sha256: str = "") -> HwConfig:
    if not isinstance(data, dict):
        raise ConfigError("top level must be a mapping")
    if data.get("schema_version") != 1:
        raise ConfigError("schema_version must be 1")
    for key in ("firmware", "link", "adc", "detectors", "rails", "channels", "thresholds"):
        _require(data, key, "config")

    rails = data["rails"]
    if set(rails) != {"A", "B"}:
        raise ConfigError("rails must be exactly A and B")
    all_holes = sorted(h for r in rails.values() for h in r["holes"])
    if all_holes != list(range(1, N_HOLES + 1)):
        raise ConfigError("rails A and B must partition holes 1-16")

    detectors: dict[str, Detector] = {}
    for name in DETECTORS:
        d = _require(data["detectors"], name, "detectors")
        rng = d["range_nm"]
        detectors[name] = Detector(
            name=name,
            adc_channel=int(d["adc_channel"]),
            range_nm=(float(rng[0]), float(rng[1])),
            saturation_counts=int(d["saturation_counts"]),
        )
    if len({d.adc_channel for d in detectors.values()}) != len(detectors):
        raise ConfigError("detectors must use distinct ADC channels")

    channels = _parse_channels(data["channels"], rails)
    _check_coverage(channels, detectors)

    limits_raw = _require(data["firmware"], "limits", "firmware")
    if not all(isinstance(v, int) for v in limits_raw.values()):
        raise ConfigError("firmware.limits values must be integers")
    limits = Limits({str(k): int(v) for k, v in limits_raw.items()})
    for key in ("wdt_a_ms", "wdt_b_ms"):
        if limits[key] > limits[key.replace("_ms", "_cap_ms")]:
            raise ConfigError(f"firmware.limits.{key} exceeds its hard cap")

    gain = str(data["adc"]["gain"])
    if gain not in {str(k) for k in data["adc"]["lsb_mv"]}:
        raise ConfigError(f"adc.gain {gain!r} has no lsb_mv entry")
    data["adc"]["lsb_mv"] = {str(k): v for k, v in data["adc"]["lsb_mv"].items()}

    return HwConfig(path, sha256, data, channels, detectors, limits)


def load_config(path: str | Path | None = None) -> HwConfig:
    p = Path(path) if path is not None else default_config_path()
    try:
        blob = p.read_bytes()
    except OSError as e:
        raise ConfigError(f"cannot read config {p}: {e}") from e
    try:
        data = yaml.safe_load(blob)
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML in {p}: {e}") from e
    return parse_config(data, p, hashlib.sha256(blob).hexdigest())
