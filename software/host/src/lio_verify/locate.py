"""Resolve a fact's locator against the exact bytes of its source (spec §3.3).

- ``xpath``: XML; ``expr`` must select exactly one node. Its text is the node's
  string value, or, with ``fields``, those attributes' values joined by one space.
- ``json_pointer``: JSON (RFC 6901); the value must be a string or number, or,
  with ``fields``, an object whose named members are joined by one space.
  Numbers are compared as their literal token ("16.0"), never as floats.
- ``char_span``: ``text[start:end]`` of the UTF-8 decoded source.
- ``image_bbox``: not machine-checkable; the attested transcription is returned
  and the caller must treat the fact as ATTESTED, not VERIFIED.

Every function raises :class:`LocatorError` on any mismatch (fail closed).
"""

from __future__ import annotations

import json
from typing import Any

from lxml import etree


class LocatorError(ValueError):
    pass


class JsonNumber(str):
    """A JSON number kept as its literal token."""


def load_json_exact(data: bytes) -> Any:
    try:
        return json.loads(
            data.decode("utf-8"),
            parse_float=JsonNumber,
            parse_int=JsonNumber,
            parse_constant=lambda c: (_ for _ in ()).throw(LocatorError(f"JSON constant {c}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise LocatorError(f"not UTF-8 JSON: {e}") from e


def json_pointer(doc: Any, pointer: str) -> Any:
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise LocatorError(f"bad JSON pointer {pointer!r}")
    cur = doc
    for raw in pointer[1:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            if not key.isdigit() or (key != "0" and key.startswith("0")):
                raise LocatorError(f"bad array index {key!r} in {pointer!r}")
            i = int(key)
            if i >= len(cur):
                raise LocatorError(f"index {i} out of range in {pointer!r}")
            cur = cur[i]
        elif isinstance(cur, dict):
            if key not in cur:
                raise LocatorError(f"no member {key!r} in {pointer!r}")
            cur = cur[key]
        else:
            raise LocatorError(f"cannot descend into a scalar at {pointer!r}")
    return cur


def _scalar(v: Any, where: str) -> str:
    if isinstance(v, str):  # includes JsonNumber
        return str(v)
    raise LocatorError(f"{where} is not a string or number")


def _xml(data: bytes) -> Any:
    parser = etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False
    )
    try:
        return etree.fromstring(data, parser)
    except etree.XMLSyntaxError as e:
        raise LocatorError(f"not well-formed XML: {e}") from e


def resolve(locator: dict[str, Any], data: bytes) -> str:
    """The text the locator points at in ``data``; raises unless it matches ``text``."""
    got = read(locator, data)
    if got != locator.get("text"):
        raise LocatorError(f"located text {got!r} != stated {locator.get('text')!r}")
    return got


def read(locator: dict[str, Any], data: bytes) -> str:
    """The text at the locator (no comparison with its ``text``); raises if unresolvable."""
    kind = locator.get("type")
    if kind == "char_span":
        if locator.get("encoding") != "utf-8":
            raise LocatorError("char_span needs encoding utf-8")
        try:
            t = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise LocatorError(f"source is not UTF-8: {e}") from e
        start, end = locator["start"], locator["end"]
        if not (0 <= start <= end <= len(t)):
            raise LocatorError("char_span out of range")
        got = t[start:end]
    elif kind == "xpath":
        root = _xml(data)
        try:
            found = root.xpath(locator["expr"], namespaces=locator.get("namespaces") or {})
        except etree.XPathError as e:
            raise LocatorError(f"bad XPath: {e}") from e
        if not isinstance(found, list) or len(found) != 1:
            n = len(found) if isinstance(found, list) else "a non-node"
            raise LocatorError(f"XPath must select exactly one node, got {n}")
        node = found[0]
        fields = locator.get("fields")
        if fields:
            if not isinstance(node, etree._Element):
                raise LocatorError("fields need an element")
            vals = [node.get(f) for f in fields]
            if any(v is None for v in vals):
                raise LocatorError(f"missing attribute among {fields}")
            got = " ".join(str(v) for v in vals)
        elif isinstance(node, etree._Element):
            got = "".join(node.itertext())
        else:
            got = str(node)
    elif kind == "json_pointer":
        v = json_pointer(load_json_exact(data), locator["pointer"])
        fields = locator.get("fields")
        if fields:
            if not isinstance(v, dict):
                raise LocatorError("fields need a JSON object")
            got = " ".join(_scalar(json_pointer(v, "/" + f), f) for f in fields)
        else:
            got = _scalar(v, locator["pointer"])
    elif kind == "image_bbox":
        return str(locator["text"])
    else:
        raise LocatorError(f"unknown locator type {kind!r}")
    return got
