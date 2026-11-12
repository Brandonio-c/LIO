"""Content-addressed evidence store (spec §3.1).

Layout under a store root (``composition/sources`` for golden records,
``data/foods/composition/sources`` for samples):

- ``sha256/<aa>/<hash>``: the document bytes as received (the HTTP entity body
  after any Content-Encoding is removed). Never modified or deleted.
- ``manifest/<hash>.json``: media type, length, and every retrieval of those
  bytes (URL, UTC time, source identifiers, retriever version). A re-fetch of
  identical bytes adds a retrieval; changed bytes are a new document.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RETRIEVER_VERSION = "lio_comp.fetch@1"


class EvidenceError(RuntimeError):
    pass


def blob_path(root: Path, sha256: str) -> Path:
    return root / "sha256" / sha256[:2] / sha256


def manifest_path(root: Path, sha256: str) -> Path:
    return root / "manifest" / f"{sha256}.json"


def canonical_json(obj: Any) -> bytes:
    """The one serialisation used for every JSON file this package writes."""
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=1) + "\n").encode()


@dataclass(frozen=True)
class Retrieval:
    retrieval_url: str
    retrieved_at: str  # UTC, ISO 8601, "Z"
    identifiers: dict[str, str]
    retriever_version: str = RETRIEVER_VERSION

    def to_json(self) -> dict[str, Any]:
        return {
            "retrieval_url": self.retrieval_url,
            "retrieved_at": self.retrieved_at,
            "identifiers": dict(sorted(self.identifiers.items())),
            "retriever_version": self.retriever_version,
        }


def put(root: Path, data: bytes, media_type: str, retrieval: Retrieval) -> str:
    """Store ``data`` (if new) and record the retrieval; returns the SHA-256."""
    sha = hashlib.sha256(data).hexdigest()
    blob = blob_path(root, sha)
    if blob.exists():
        if hashlib.sha256(blob.read_bytes()).hexdigest() != sha:
            raise EvidenceError(f"stored blob {sha} is corrupt")
    else:
        blob.parent.mkdir(parents=True, exist_ok=True)
        tmp = blob.with_suffix(".part")
        tmp.write_bytes(data)
        os.replace(tmp, blob)
        os.chmod(blob, 0o444)
    mpath = manifest_path(root, sha)
    if mpath.exists():
        man = json.loads(mpath.read_text())
        if man["media_type"] != media_type:
            raise EvidenceError(f"{sha}: media type {media_type} != {man['media_type']}")
    else:
        man = {"sha256": sha, "byte_length": len(data), "media_type": media_type, "retrievals": []}
    entry = retrieval.to_json()
    if entry not in man["retrievals"]:
        man["retrievals"].append(entry)
        man["retrievals"].sort(key=lambda r: (r["retrieved_at"], r["retrieval_url"]))
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_bytes(canonical_json(man))
    return sha


def get(root: Path, sha256: str) -> bytes:
    data = blob_path(root, sha256).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise EvidenceError(f"stored blob {sha256} does not match its hash")
    return data
