from __future__ import annotations

import pytest

from lio.protocol import (
    LINE_MAX,
    ErrCode,
    Event,
    Noise,
    ProtocolError,
    Response,
    encode,
    fw_compatible,
    parse_fields,
    parse_line,
    version_tuple,
)

pytestmark = pytest.mark.unit


class TestEncode:
    def test_plain(self) -> None:
        assert encode("PING") == "PING"

    def test_seq_and_whitespace_normalised(self) -> None:
        assert encode("  ADC   READ 1  16 ", seq=7) == "@7 ADC READ 1 16"

    def test_empty_rejected(self) -> None:
        with pytest.raises(ProtocolError, match="empty"):
            encode("   ")

    def test_multiline_rejected(self) -> None:
        with pytest.raises(ProtocolError, match="single line"):
            encode("PING\nOFF")

    def test_too_long_rejected(self) -> None:
        with pytest.raises(ProtocolError, match="longer"):
            encode("X" * (LINE_MAX + 1))

    def test_exactly_max_ok(self) -> None:
        assert len(encode("X" * LINE_MAX)) == LINE_MAX


class TestParseOk:
    def test_ok_with_fields(self) -> None:
        r = parse_line("OK MEAS ch=8 dark0=41 dark1=209 lit0=5120 lit1=9874 t_on_ms=24\r\n")
        assert isinstance(r, Response) and r.ok
        assert r.word == "MEAS" and r.seq is None
        assert r.fields.as_int("lit0") == 5120
        assert r.fields.as_int("ch") == 8

    def test_ok_with_seq(self) -> None:
        r = parse_line("@17 OK PING uptime_ms=5321")
        assert isinstance(r, Response) and r.seq == 17
        assert r.fields.as_int("uptime_ms") == 5321

    def test_ok_without_fields(self) -> None:
        r = parse_line("OK OFF")
        assert isinstance(r, Response) and r.ok and r.fields.values == {}

    def test_hex_and_float_fields(self) -> None:
        r = parse_line("OK STATUS mask=0x0080 faults=0x0C")
        assert isinstance(r, Response)
        assert r.fields.as_int("mask") == 0x80
        assert r.fields.as_int("faults") == 0x0C
        r2 = parse_line("OK ADC ch=1 raw=212 mv=26.500 n=16 mean=211.94 std=3.12")
        assert isinstance(r2, Response)
        assert r2.fields.as_float("std") == pytest.approx(3.12)
        assert r2.fields.opt_float("mean", 0.0) == pytest.approx(211.94)
        assert r2.fields.opt_int("missing", -1) == -1
        assert r2.fields.opt_float("missing", 1.5) == 1.5

    def test_flags_collected(self) -> None:
        e = parse_line("# WDT ch=3 on_ms=2000 off")
        assert isinstance(e, Event)
        assert e.fields.flags == ("off",)


class TestParseErr:
    def test_err_message_with_spaces(self) -> None:
        r = parse_line("ERR CE code=3 msg=needs exactly one selected hole on this rail")
        assert isinstance(r, Response) and not r.ok
        assert r.word == "CE" and r.code == ErrCode.REFUSED
        assert r.msg == "needs exactly one selected hole on this rail"

    def test_err_with_seq(self) -> None:
        r = parse_line("@4 ERR MOTOR code=3 msg=not armed")
        assert isinstance(r, Response) and r.seq == 4 and r.code == 3

    def test_err_word_that_is_a_substring_of_err(self) -> None:
        r = parse_line("ERR R code=1 msg=unknown command")
        assert isinstance(r, Response) and r.word == "R" and r.code == 1

    def test_overflow_err(self) -> None:
        r = parse_line("ERR ? code=6 msg=line too long")
        assert isinstance(r, Response) and r.word == "?" and r.code == ErrCode.OVERFLOW

    def test_err_without_code_is_noise(self) -> None:
        assert isinstance(parse_line("ERR X msg=oops"), Noise)

    def test_err_without_msg(self) -> None:
        r = parse_line("ERR X code=2")
        assert isinstance(r, Response) and r.msg is None and r.code == 2


class TestParseEvents:
    def test_boot_banner(self) -> None:
        e = parse_line("# BOOT name=lio fw=2.0.0 proto=1 build=2026-11-03 adc_ok=1 hw_wdt=0")
        assert isinstance(e, Event) and e.is_boot
        assert e.fields.as_str("fw") == "2.0.0"
        assert e.fields.as_int("adc_ok") == 1

    def test_stream_sample(self) -> None:
        e = parse_line("# S i=3 t_us=4200 raw=-12")
        assert isinstance(e, Event) and not e.is_boot
        assert e.fields.as_int("raw") == -12

    def test_bare_hash_is_noise(self) -> None:
        assert isinstance(parse_line("#"), Noise)


class TestNoise:
    @pytest.mark.parametrize(
        "line",
        [
            "",
            "LIO V3 Z AXIS READY",
            "SYNC UP @ 500.00",
            "@x OK PING",
            "OK",
            "found 0x48",
        ],
    )
    def test_noise(self, line: str) -> None:
        assert isinstance(parse_line(line), Noise)


class TestFields:
    def test_missing_field(self) -> None:
        f = parse_fields(["a=1"])
        with pytest.raises(ProtocolError, match="missing"):
            f.as_int("b")
        assert "a" in f and "b" not in f

    def test_bad_int(self) -> None:
        with pytest.raises(ProtocolError, match="not an integer"):
            parse_fields(["a=1.5"]).as_int("a")

    def test_bad_float(self) -> None:
        with pytest.raises(ProtocolError, match="not a number"):
            parse_fields(["a=x"]).as_float("a")

    def test_value_with_equals(self) -> None:
        assert parse_fields(["k=a=b"]).as_str("k") == "a=b"

    def test_negative_hex(self) -> None:
        assert parse_fields(["k=-0x10"]).as_int("k") == -16


class TestVersions:
    def test_version_tuple(self) -> None:
        assert version_tuple("2.10.3") == (2, 10, 3)

    @pytest.mark.parametrize("bad", ["2.0", "2.x.0", "", "1.2.3.4"])
    def test_version_tuple_bad(self, bad: str) -> None:
        with pytest.raises(ProtocolError):
            version_tuple(bad)

    @pytest.mark.parametrize(
        ("fw", "proto", "ok"),
        [
            ("2.0.0", 1, True),
            ("2.3.1", 1, True),
            ("1.9.9", 1, False),
            ("3.0.0", 1, False),
            ("2.0.0", 2, False),
        ],
    )
    def test_fw_compatible(self, fw: str, proto: int, ok: bool) -> None:
        assert fw_compatible(fw, proto, "2.0.0", 1) is ok
