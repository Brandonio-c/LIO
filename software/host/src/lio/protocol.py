"""Line protocol (docs/PROTOCOL.md): command encoding and response/event parsing.

Pure functions only; no I/O. Every line from the device parses into exactly one of
:class:`Response` (``OK``/``ERR``), :class:`Event` (``# ...``, including the boot
banner) or :class:`Noise` (anything else, e.g. output from an older firmware).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

LINE_MAX = 64


class ErrCode(IntEnum):
    UNKNOWN = 1
    BAD_ARG = 2
    REFUSED = 3
    ADC = 4
    BUSY = 5
    OVERFLOW = 6


class ProtocolError(Exception):
    """A line could not be encoded, or a response was malformed or missing."""


def _parse_int(text: str) -> int:
    t = text.strip()
    return int(t, 16) if t.lower().startswith(("0x", "-0x")) else int(t)


@dataclass(frozen=True)
class Fields:
    """``key=value`` pairs plus bare flag words, with typed accessors."""

    values: dict[str, str] = field(default_factory=dict)
    flags: tuple[str, ...] = ()

    def __contains__(self, key: object) -> bool:
        return key in self.values

    def as_str(self, key: str) -> str:
        try:
            return self.values[key]
        except KeyError as e:
            raise ProtocolError(f"missing field {key!r}") from e

    def as_int(self, key: str) -> int:
        v = self.as_str(key)
        try:
            return _parse_int(v)
        except ValueError as e:
            raise ProtocolError(f"field {key}={v!r} is not an integer") from e

    def as_float(self, key: str) -> float:
        v = self.as_str(key)
        try:
            return float(v)
        except ValueError as e:
            raise ProtocolError(f"field {key}={v!r} is not a number") from e

    def opt_int(self, key: str, default: int) -> int:
        return self.as_int(key) if key in self.values else default

    def opt_float(self, key: str, default: float) -> float:
        return self.as_float(key) if key in self.values else default


def parse_fields(tokens: list[str]) -> Fields:
    values: dict[str, str] = {}
    flags: list[str] = []
    for tok in tokens:
        if "=" in tok:
            k, _, v = tok.partition("=")
            values[k] = v
        else:
            flags.append(tok)
    return Fields(values, tuple(flags))


@dataclass(frozen=True)
class Response:
    ok: bool
    word: str
    fields: Fields
    seq: int | None
    code: int | None = None
    msg: str | None = None
    raw: str = ""


@dataclass(frozen=True)
class Event:
    name: str
    fields: Fields
    raw: str = ""

    @property
    def is_boot(self) -> bool:
        return self.name == "BOOT"


@dataclass(frozen=True)
class Noise:
    raw: str


Line = Response | Event | Noise


def encode(command: str, seq: int | None = None) -> str:
    """Return the wire form of a command (without the trailing newline)."""
    cmd = " ".join(command.split())
    if not cmd:
        raise ProtocolError("empty command")
    if "\n" in command or "\r" in command:
        raise ProtocolError("command must be a single line")
    line = f"@{seq} {cmd}" if seq is not None else cmd
    if len(line) > LINE_MAX:
        raise ProtocolError(f"command longer than {LINE_MAX} characters: {line!r}")
    return line


def parse_line(raw: str) -> Line:
    line = raw.strip()
    if line.startswith("#"):
        tokens = line[1:].split()
        if not tokens:
            return Noise(raw)
        return Event(tokens[0], parse_fields(tokens[1:]), raw)

    seq: int | None = None
    rest = line
    if rest.startswith("@"):
        head, _, rest = rest.partition(" ")
        try:
            seq = int(head[1:])
        except ValueError:
            return Noise(raw)

    tokens = rest.split()
    if len(tokens) < 2 or tokens[0] not in ("OK", "ERR"):
        return Noise(raw)
    word = tokens[1]
    if tokens[0] == "OK":
        return Response(True, word, parse_fields(tokens[2:]), seq, raw=raw)

    # ERR <word> code=<n> msg=<text to end of line>
    parts = rest.split(None, 2)
    after_word = parts[2] if len(parts) > 2 else ""
    msg = None
    head = after_word
    if "msg=" in after_word:
        head, _, msg = after_word.partition("msg=")
    fields = parse_fields(head.split())
    try:
        code = fields.as_int("code")
    except ProtocolError:
        return Noise(raw)
    return Response(False, word, fields, seq, code=code, msg=msg, raw=raw)


def version_tuple(v: str) -> tuple[int, int, int]:
    parts = v.strip().split(".")
    if len(parts) != 3:
        raise ProtocolError(f"not a semantic version: {v!r}")
    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError as e:
        raise ProtocolError(f"not a semantic version: {v!r}") from e
    return major, minor, patch


def fw_compatible(fw: str, proto: int, min_version: str, expected_proto: int) -> bool:
    """True if firmware ``fw`` speaks ``expected_proto`` and is >= min, < next major."""
    have, need = version_tuple(fw), version_tuple(min_version)
    return proto == expected_proto and have >= need and have[0] == need[0]
