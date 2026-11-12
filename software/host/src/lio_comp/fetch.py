"""Download a document and put it in the evidence store (the only network code here)."""

from __future__ import annotations

import datetime as dt
import gzip
import urllib.request
import zlib
from pathlib import Path

from lio_comp.evidence import Retrieval, put

USER_AGENT = "lio-composition/1 (+https://github.com/Brandonio-c/LIO)"


def download(url: str, *, timeout: float = 120.0) -> tuple[bytes, str]:
    """The entity body (Content-Encoding removed) and its media type."""
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # https URLs only (snapshot)
        body = resp.read()
        enc = (resp.headers.get("Content-Encoding") or "").lower()
        ctype = (resp.headers.get("Content-Type") or "application/octet-stream").split(";")[0]
    if enc == "gzip":
        body = gzip.decompress(body)
    elif enc == "deflate":
        body = zlib.decompress(body)
    return body, ctype.strip().lower()


def now_utc() -> str:
    return (
        dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def snapshot(
    root: Path, url: str, identifiers: dict[str, str], *, media_type: str | None = None
) -> str:
    """Fetch ``url`` into the store at ``root``; returns the SHA-256."""
    if not url.startswith("https://"):
        raise ValueError("only https sources are snapshotted")
    body, ctype = download(url)
    return put(root, body, media_type or ctype, Retrieval(url, now_utc(), identifiers))
