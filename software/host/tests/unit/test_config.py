from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from lio.config import ConfigError, HwConfig, default_config_path, load_config, parse_config

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def raw() -> dict[str, Any]:
    return yaml.safe_load(default_config_path().read_text())


def _parse(data: dict[str, Any]) -> HwConfig:
    return parse_config(copy.deepcopy(data), Path("x.yaml"))


class TestShippedConfig:
    def test_loads(self, cfg: HwConfig) -> None:
        assert len(cfg.channels) == 16
        assert len(cfg.sha256) == 64
        assert cfg.provisional

    def test_rails_match_hardware(self, cfg: HwConfig) -> None:
        assert cfg.rail_holes("A") == tuple(range(1, 10))
        assert cfg.rail_holes("B") == tuple(range(10, 17))

    def test_detector_coverage(self, cfg: HwConfig) -> None:
        assert cfg.channel(3).expected_detectors == ("opt101",)
        assert cfg.channel(8).expected_detectors == ("opt101", "ingaas")
        assert cfg.channel(13).expected_detectors == ("ingaas",)
        assert cfg.channel(15).expect_for("ingaas") == "weak"
        assert cfg.channel(16).expected_detectors == ()
        assert not cfg.channel(10).fitted and not cfg.channel(11).fitted

    def test_adc_mapping(self, cfg: HwConfig) -> None:
        assert cfg.detector_for_adc(0) == "ingaas"
        assert cfg.detector_for_adc(1) == "opt101"
        assert cfg.detector_for_adc(2) is None
        assert cfg.lsb_mv == 0.125

    def test_limits_mirror_firmware(self, cfg: HwConfig) -> None:
        assert cfg.wdt_ms("A") == 2000 and cfg.wdt_ms("B") == 5000
        assert cfg.limits["step_max"] == 2048
        assert cfg.fw_name == "lio" and cfg.fw_proto == 1 and cfg.fw_min_version == "2.0.0"

    def test_config_h_and_yaml_agree(self, cfg: HwConfig) -> None:
        """The firmware constants and the YAML mirror must not drift apart."""
        src = (
            Path(__file__).resolve().parents[3] / "firmware" / "lio_firmware" / "config.h"
        ).read_text()
        pairs = {
            "WDT_A_DEFAULT_MS": "wdt_a_ms",
            "WDT_A_CAP_MS": "wdt_a_cap_ms",
            "WDT_B_DEFAULT_MS": "wdt_b_ms",
            "WDT_B_CAP_MS": "wdt_b_cap_ms",
            "WDT_MIN_MS": "wdt_min_ms",
            "COMMS_TIMEOUT_MS": "comms_ms",
            "ARM_DURATION_MS": "arm_ms",
            "MOTOR_STEP_MAX": "step_max",
            "MOTOR_RPM_DEFAULT": "rpm_default",
            "MOTOR_RPM_MAX": "rpm_max",
            "HALF_STEPS_PER_REV": "half_steps_per_rev",
            "JOG_MAX_STEPS": "jog_max",
            "JOG_SPEED_MIN": "jog_v_min",
            "JOG_SPEED_MAX": "jog_v_max",
            "JOG_ACC_MIN": "jog_acc_min",
            "JOG_ACC_MAX": "jog_acc_max",
            "JOG_VA_DEFAULT": "jog_va_default",
            "JOG_VS_DEFAULT": "jog_vs_default",
            "JOG_ACC_DEFAULT": "jog_acc_default",
            "SETTLE_MS_DEFAULT": "settle_ms",
            "SETTLE_MS_MAX": "settle_ms_max",
            "MEAS_N_MAX": "meas_n_max",
            "LINE_MAX": "line_max",
            "STREAM_BUF_N": "stream_buf_n",
        }
        import re

        for const, key in pairs.items():
            m = re.search(rf"\b{const}\s*=\s*(\d+)", src)
            assert m, f"{const} not found in config.h"
            assert int(m.group(1)) == cfg.limits[key], f"{const} != limits.{key}"

    def test_sections(self, cfg: HwConfig) -> None:
        th = cfg.thresholds
        assert th.num("channel.detect_sigma") == 10
        assert th.integer("repeatability.repeats") == 10
        assert th.span("dark.opt101_counts") == (0, 800)
        assert th.ints("settling.holes") == (3, 8, 13)
        assert "A" in cfg.section.mapping("rails")
        with pytest.raises(ConfigError, match="missing"):
            th.num("nope.nothing")
        with pytest.raises(ConfigError, match="number"):
            cfg.section.num("firmware.name")
        with pytest.raises(ConfigError, match="integer"):
            th.integer("repeatability.cv_max")
        with pytest.raises(ConfigError, match="low, high"):
            th.span("channel.detect_sigma")
        with pytest.raises(ConfigError, match="integers"):
            th.ints("channel")
        with pytest.raises(ConfigError, match="mapping"):
            cfg.section.mapping("schema_version")

    def test_integer_keys(self, cfg: HwConfig) -> None:
        assert cfg.section.raw("motors.1.name") == "left"
        assert cfg.section.raw("motors.2.name") == "right"

    def test_channel_range(self, cfg: HwConfig) -> None:
        with pytest.raises(ConfigError):
            cfg.channel(17)


class TestValidation:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="cannot read"):
            load_config(tmp_path / "nope.yaml")

    def test_bad_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("a: [1, 2\n")
        with pytest.raises(ConfigError, match="invalid YAML"):
            load_config(p)

    def test_not_mapping(self) -> None:
        with pytest.raises(ConfigError, match="mapping"):
            parse_config([1, 2], Path("x"))

    def test_schema(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["schema_version"] = 2
        with pytest.raises(ConfigError, match="schema_version"):
            _parse(d)

    def test_missing_section(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        del d["thresholds"]
        with pytest.raises(ConfigError, match="thresholds missing"):
            _parse(d)

    def test_rails_partition(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["rails"]["A"]["holes"] = [1, 2, 3]
        with pytest.raises(ConfigError, match="partition"):
            _parse(d)

    def test_rails_names(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["rails"]["C"] = d["rails"].pop("B")
        with pytest.raises(ConfigError, match="exactly A and B"):
            _parse(d)

    def test_channel_count(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["channels"] = d["channels"][:15]
        with pytest.raises(ConfigError, match="exactly 16"):
            _parse(d)

    def test_channel_order(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["channels"][0], d["channels"][1] = d["channels"][1], d["channels"][0]
        with pytest.raises(ConfigError, match="ordered"):
            _parse(d)

    def test_channel_wrong_rail(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["channels"][8]["rail"] = "B"  # hole 9 is on RAIL A
        with pytest.raises(ConfigError, match="does not list"):
            _parse(d)

    def test_channel_unknown_rail(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["channels"][0]["rail"] = "Z"
        with pytest.raises(ConfigError, match="unknown rail"):
            _parse(d)

    def test_unknown_detector(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["channels"][0]["expect"] = {"ccd": "signal"}
        with pytest.raises(ConfigError, match="unknown detector"):
            _parse(d)

    def test_bad_level(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["channels"][0]["expect"] = {"opt101": "lots"}
        with pytest.raises(ConfigError, match="expect level"):
            _parse(d)

    def test_expect_not_mapping(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["channels"][0]["expect"] = ["opt101"]
        with pytest.raises(ConfigError, match="expect must be"):
            _parse(d)

    def test_unfitted_cannot_expect(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["channels"][9]["expect"] = {"ingaas": "signal"}
        with pytest.raises(ConfigError, match="unfitted"):
            _parse(d)

    def test_coverage_mismatch(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["channels"][2]["expect"] = {"ingaas": "signal"}  # blue on InGaAs: impossible
        with pytest.raises(ConfigError, match="outside its range"):
            _parse(d)

    def test_detector_channels_distinct(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["detectors"]["opt101"]["adc_channel"] = 0
        with pytest.raises(ConfigError, match="distinct"):
            _parse(d)

    def test_limits_integers(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["firmware"]["limits"]["wdt_a_ms"] = 2.5
        with pytest.raises(ConfigError, match="integers"):
            _parse(d)

    def test_wdt_over_cap(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["firmware"]["limits"]["wdt_a_ms"] = 9000
        with pytest.raises(ConfigError, match="hard cap"):
            _parse(d)

    def test_missing_limit_key(self, cfg: HwConfig) -> None:
        with pytest.raises(ConfigError, match=r"limits\.nope"):
            cfg.limits["nope"]

    def test_gain_without_lsb(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["adc"]["gain"] = "32"
        with pytest.raises(ConfigError, match="lsb_mv"):
            _parse(d)

    def test_entry_not_mapping(self, raw: dict[str, Any]) -> None:
        d = copy.deepcopy(raw)
        d["channels"][0] = "hole 1"
        with pytest.raises(ConfigError, match="must be a mapping"):
            _parse(d)
