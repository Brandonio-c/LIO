"""Offline network for tests: answers from the evidence store by recorded URL.

Every URL the code asks for must have been snapshotted in ``composition/sources``
(its manifest records the URL). A few endpoints answer "nothing found" when a URL
was not snapshotted, exactly as the live service does for unknown codes:
RxNav ``ndcstatus`` (status UNKNOWN) and DailyMed ``spls.json?ndc=`` (no SPLs).
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
STORE = REPO / "composition" / "sources"


class SnapshotWeb:
    def __init__(self, store: Path = STORE) -> None:
        self.store = store
        self.by_url: dict[str, tuple[str, str]] = {}
        for m in (store / "manifest").glob("*.json"):
            man = json.loads(m.read_text())
            for r in man["retrievals"]:
                self.by_url[r["retrieval_url"]] = (man["sha256"], man["media_type"])
        self.calls: list[str] = []

    def __call__(self, url: str, headers: dict[str, str], timeout: float) -> Any:
        self.calls.append(url)
        hit = self.by_url.get(url)
        if hit is not None:
            sha, media = hit
            data = (self.store / "sha256" / sha[:2] / sha).read_bytes()
            return json.loads(data) if media.endswith("json") else data
        if "rxnav.nlm.nih.gov/REST/ndcstatus.json" in url:
            ndc = url.split("ndc=")[1].split("&")[0]
            return {
                "ndcStatus": {"ndc11": ndc, "status": "UNKNOWN", "rxcui": "", "conceptName": ""}
            }
        if "dailymed" in url and "spls.json?ndc=" in url:
            return {"data": [], "metadata": {"total_elements": 0}}
        raise urllib.error.HTTPError(url, 404, f"not snapshotted: {url}", {}, None)  # type: ignore[arg-type]
