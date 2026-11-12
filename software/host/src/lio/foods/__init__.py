"""Food library: barcode intake (phone app), manufacturer data, LIO spectral scans."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lio.config import HwConfig

from .lookup import Lookup, LookupSettings
from .store import FoodLibrary
from .websearch import WebSearch, WebSettings, brave_key


@dataclass
class FoodSettings:
    dir: Path
    phone_enabled: bool
    phone_host: str
    phone_port: int
    scan_repeats: int
    scan_repeats_max: int
    photo_max_px: int
    online_lookup: bool
    tunnel: str
    cloudflared: str
    lookup: LookupSettings
    web: WebSettings


def settings(cfg: HwConfig, repo_root: Path) -> FoodSettings:
    """The ``foods:`` section of lio_hw.yaml (defaults for any key left out)."""
    f: dict[str, Any] = dict(cfg.data.get("foods") or {})
    d = Path(str(f.get("dir", "data/foods")))
    d = d if d.is_absolute() else repo_root / d
    ls = LookupSettings()
    return FoodSettings(
        dir=d,
        phone_enabled=bool(f.get("phone_enabled", True)),
        phone_host=str(f.get("phone_host", "0.0.0.0")),
        phone_port=int(f.get("phone_port", 8766)),
        scan_repeats=int(f.get("scan_repeats", 3)),
        scan_repeats_max=int(f.get("scan_repeats_max", 10)),
        photo_max_px=int(f.get("photo_max_px", 2000)),
        online_lookup=bool(f.get("online_lookup", True)),
        tunnel=str(f.get("tunnel", "none") or "none"),
        cloudflared=str(f.get("cloudflared_path", "") or ""),
        web=WebSettings(
            brave_api_key=brave_key(d, str((f.get("web_search") or {}).get("brave_api_key") or "")),
            keyless=bool((f.get("web_search") or {}).get("keyless", True)),
            pages=int((f.get("web_search") or {}).get("pages", 8)),
            timeout_s=float((f.get("web_search") or {}).get("timeout_s", 10)),
        ),
        lookup=LookupSettings(
            off_url=str(f.get("openfoodfacts_url", ls.off_url)),
            usda_url=str(f.get("usda_url", ls.usda_url)),
            usda_api_key=usda_key(d, str(f.get("usda_api_key", ls.usda_api_key) or "")),
            user_agent=str(f.get("user_agent", ls.user_agent)),
            timeout_s=float(f.get("lookup_timeout_s", ls.timeout_s)),
            smartlabel_key=secret_key(d, "LIO_SMARTLABEL_KEY", "smartlabel_key.txt"),
        ),
    )


def usda_key(foods_dir: Path, configured: str) -> str:
    """The api.data.gov key: $LIO_USDA_API_KEY, else <foods dir>/usda_api_key.txt
    (gitignored, so a personal key never reaches git), else lio_hw.yaml."""
    env = os.environ.get("LIO_USDA_API_KEY", "").strip()
    if env:
        return env
    try:
        key = (foods_dir / "usda_api_key.txt").read_text().strip()
    except OSError:
        key = ""
    return key or configured


def secret_key(foods_dir: Path, env: str, filename: str) -> str:
    """A key from $<env>, else <foods dir>/<filename> (gitignored). Never from lio_hw.yaml."""
    v = os.environ.get(env, "").strip()
    if v:
        return v
    try:
        return (foods_dir / filename).read_text().strip()
    except OSError:
        return ""


def evidence_store(foods_dir: Path) -> Any:
    """Store every raw answer from the product databases and web pages by SHA-256 in
    <foods dir>/composition/sources (needs the ``comp`` extra; otherwise nothing is
    stored and lookups work as before)."""
    try:
        from lio_comp.evidence import Retrieval, put
        from lio_comp.fetch import now_utc
    except ImportError:
        return None
    root = foods_dir / "composition" / "sources"

    def store(url: str, data: bytes, media_type: str) -> str:
        return put(root, data, media_type or "application/octet-stream",
                   Retrieval(url, now_utc(), {}, "lio.foods.lookup@2"))  # fmt: skip

    return store


def open_library(s: FoodSettings) -> FoodLibrary:
    ev = evidence_store(s.dir)
    lib = FoodLibrary(
        s.dir,
        Lookup(s.lookup, evidence=ev) if s.online_lookup else None,
        photo_max_px=s.photo_max_px,
    )
    if s.online_lookup:
        lib.web = WebSearch(s.web, evidence=ev)
    return lib


__all__ = ["FoodLibrary", "FoodSettings", "Lookup", "LookupSettings", "open_library", "settings"]
