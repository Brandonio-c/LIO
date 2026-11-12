"""Last-resort ingredient search on the web: search, fetch the pages, cut out ingredient lists.

Used when the barcode databases (USDA, DSLD, openFDA, Open Food Facts) have no
ingredient list. Nothing found here is saved on its own: the dashboard and
the phone app show every excerpt with a link to its page, and the user
confirms what is stored (with those links as references).

Search engines, in order:

1. **Brave Search API** when a key is set (``data/foods/brave_api_key.txt`` or
   ``$LIO_BRAVE_API_KEY``; free tier at https://brave.com/search/api/). The
   reliable choice.
2. Without a key: the public results pages of Bing, then Brave. These work
   for occasional, user-initiated searches but can change or rate-limit at
   any time; ``foods.web_search.keyless: false`` turns them off.
"""

from __future__ import annotations

import base64
import contextlib
import html
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
MAX_PAGE_BYTES = 4_000_000
# Pages that sell or describe many products: still useful, ranked after the maker and
# official label sources.
OFFICIAL = ("dailymed.nlm.nih.gov", "fda.gov", "nih.gov", "fdc.nal.usda.gov", "ods.od.nih.gov")
SKIP_DOMAINS = ("youtube.com", "facebook.com", "instagram.com", "tiktok.com", "pinterest.com",
                "reddit.com", "twitter.com", "x.com")  # fmt: skip


@dataclass
class WebSettings:
    brave_api_key: str = ""
    keyless: bool = True
    pages: int = 8
    timeout_s: float = 10.0


def brave_key(foods_dir: Path, configured: str = "") -> str:
    env = os.environ.get("LIO_BRAVE_API_KEY", "").strip()
    if env:
        return env
    try:
        key = (foods_dir / "brave_api_key.txt").read_text().strip()
    except OSError:
        key = ""
    return key or configured


Get = Callable[[str, dict[str, str], float], bytes]


def _http_get(url: str, headers: dict[str, str], timeout: float) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data: bytes = r.read(MAX_PAGE_BYTES)
        return data


# ------------------------------------------------------------------ search


def _clean_url(u: str) -> str:
    u = html.unescape(html.unescape(u))
    if "bing.com/ck/a" in u:  # Bing's click-tracking link: the target is base64 in u=a1...
        q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query).get("u", [""])[0]
        if q.startswith("a1"):
            try:
                u = base64.urlsafe_b64decode(q[2:] + "=" * (-len(q[2:]) % 4)).decode("utf-8")
            except ValueError:
                return ""
    return u if u.startswith(("http://", "https://")) else ""


def _strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_bing(page: str) -> list[dict[str, str]]:
    out = []
    for m in re.finditer(
        r'<li class="b_algo"[^>]*>.*?<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S
    ):
        url = _clean_url(m.group(1))
        if url:
            out.append({"url": url, "title": _strip_tags(m.group(2))})
    return out


def parse_brave_html(page: str) -> list[dict[str, str]]:
    out = []
    for blk in re.split(r'<div class="snippet[^"]*" data-pos="\d+" data-type="web"', page)[1:]:
        a = re.search(r'<a href="(https?://[^"]+)"', blk)
        t = re.search(r'<div class="title[^"]*"[^>]*>(.*?)</div>', blk, re.S)
        if a:
            url = _clean_url(a.group(1))
            if url:
                out.append({"url": url, "title": _strip_tags(t.group(1)) if t else url})
    return out


class WebSearch:
    def __init__(self, settings: WebSettings, get: Get | None = None, evidence: Any = None) -> None:
        self.s = settings
        self._get = get or _http_get
        # (url, bytes, media type) -> SHA-256: every page read for ingredients is stored
        self.evidence = evidence

    def _page(self, url: str, accept: str = "text/html") -> str:
        """A page that is not evidence (search-engine result pages)."""
        headers = {"User-Agent": BROWSER_UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.8"}
        return self._get(url, headers, self.s.timeout_s).decode("utf-8", "replace")

    def _page_bytes(self, url: str, accept: str = "text/html") -> tuple[str, str | None]:
        headers = {"User-Agent": BROWSER_UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.8"}
        data = self._get(url, headers, self.s.timeout_s)
        sha = None
        if self.evidence is not None:
            try:
                sha = self.evidence(url, data, "text/html")
            except OSError:
                sha = None
        return data.decode("utf-8", "replace"), sha

    def search(self, query: str) -> tuple[str, list[dict[str, str]], list[str]]:
        """(engine used, results [{url, title}], errors of the engines tried before it)."""
        errors: list[str] = []
        engines: list[tuple[str, Callable[[], list[dict[str, str]]]]] = []
        q = urllib.parse.quote_plus(query)
        if self.s.brave_api_key:

            def brave_api() -> list[dict[str, str]]:
                raw = self._get(
                    f"https://api.search.brave.com/res/v1/web/search?q={q}&count=15",
                    {"Accept": "application/json", "X-Subscription-Token": self.s.brave_api_key},
                    self.s.timeout_s,
                )
                res = json.loads(raw).get("web", {}).get("results", [])
                return [{"url": r["url"], "title": r.get("title", "")} for r in res if r.get("url")]

            engines.append(("Brave Search API", brave_api))
        if self.s.keyless:
            engines.append(
                (
                    "Bing",
                    lambda: parse_bing(self._page(f"https://www.bing.com/search?q={q}&setlang=en")),
                )
            )
            engines.append(
                (
                    "Brave Search",
                    lambda: parse_brave_html(
                        self._page(f"https://search.brave.com/search?q={q}&source=web")
                    ),
                )
            )
        if not engines:
            return "", [], ["web search is off (no Brave API key, keyless search disabled)"]
        for name, fn in engines:
            try:
                found = fn()
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                errors.append(f"{name}: {e}")
                continue
            if found:
                return name, _dedupe(found), errors
            errors.append(f"{name}: no results (blocked or changed?)")
        return "", [], errors

    # ------------------------------------------------------------ pages

    def page_sections(self, url: str, title: str = "") -> dict[str, Any]:
        """Fetch one page and cut out its ingredient sections."""
        domain = urllib.parse.urlparse(url).netloc.removeprefix("www.")
        out: dict[str, Any] = {
            "url": url,
            "domain": domain,
            "title": title,
            "sections": [],
            "error": "",
        }
        try:
            page, sha = self._page_bytes(url)
            out["sha256"] = sha or ""
        except urllib.error.HTTPError as e:
            out["error"] = f"the site refused automated access ({e.code})"
            return out
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            out["error"] = f"could not load ({e})"
            return out
        if not title:
            m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
            out["title"] = _strip_tags(m.group(1))[:160] if m else domain
        out["sections"] = ingredient_sections(page_lines(page))
        return out

    def find(self, query: str, brand_hint: str = "") -> dict[str, Any]:
        engine, results, errors = self.search(query)
        results = [r for r in results if not any(d in r["url"] for d in SKIP_DOMAINS)]
        results = rank(results, brand_hint)[: self.s.pages]
        pages: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {
                pool.submit(self.page_sections, r["url"], r["title"]): i
                for i, r in enumerate(results)
            }
            done: dict[int, dict[str, Any]] = {}
            for f in as_completed(futs):
                done[futs[f]] = f.result()
        pages = [done[i] for i in sorted(done)]
        pages.sort(key=lambda p: 0 if p["sections"] else 1)  # pages with a list first (stable)
        return {"query": query, "engine": engine, "pages": pages, "errors": errors}


def _dedupe(results: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    per_domain: dict[str, int] = {}
    out = []
    for r in results:
        p = urllib.parse.urlparse(r["url"])
        key = p.netloc + p.path.rstrip("/")
        dom = p.netloc.removeprefix("www.")
        if key in seen or per_domain.get(dom, 0) >= 2:
            continue
        seen.add(key)
        per_domain[dom] = per_domain.get(dom, 0) + 1
        out.append(r)
    return out


def rank(results: list[dict[str, str]], brand_hint: str) -> list[dict[str, str]]:
    """The maker's own site and official label sources first, then the rest in search order."""
    words = [w for w in re.findall(r"[a-z0-9]+", brand_hint.lower()) if len(w) > 3]

    def key(ir: tuple[int, dict[str, str]]) -> tuple[int, int]:
        i, r = ir
        dom = urllib.parse.urlparse(r["url"]).netloc.lower()
        if any(w in dom for w in words):
            return (0, i)
        if any(dom.endswith(o) for o in OFFICIAL):
            return (1, i)
        return (2, i)

    return [r for _, r in sorted(enumerate(results), key=key)]


# ------------------------------------------------------------- extraction

_BLOCK = {"p", "div", "li", "br", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6",
          "section", "article", "dd", "dt", "span", "ul", "ol", "table", "label"}  # fmt: skip
_SKIP = {"script", "style", "noscript", "svg", "template", "head"}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self.skip += 1
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def page_lines(page: str) -> list[str]:
    p = _Text()
    with contextlib.suppress(Exception):  # broken HTML: use what was parsed
        p.feed(page)
    lines = [re.sub(r"\s+", " ", x).strip() for x in "".join(p.parts).split("\n")]
    return [x for x in lines if x]


_HEAD = re.compile(
    r"^\s*((?:active|inactive|other|non[- ]?medicinal|medicinal)?\s*ingredients?"
    r"(?:\s*\([^)]{0,80}\))?(?:\s*\([^)]{0,80}\))?)\s*[:\uff1a.-]?\s*(.*)$",
    re.I,
)
_NOT_A_LIST = re.compile(r"\b(click|learn more|see|view|shop|buy|what are|faq|questions?)\b", re.I)


def _looks_like_list(text: str) -> bool:
    """A list (commas or semicolons) or a short entry such as "Methylcellulose 2 g"."""
    if _NOT_A_LIST.search(text[:40]):
        return False
    return "," in text or ";" in text or len(text.split()) <= 12


def ingredient_sections(lines: list[str], limit: int = 6) -> list[dict[str, str]]:
    """Ingredient lists on a page: a heading ("Inactive ingredients (Orange):") and its list.

    The list is on the heading's line after a colon, or on the next lines.
    """
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        m = _HEAD.match(line)
        if not m or len(m.group(1)) > 100:
            continue
        heading, rest = m.group(1).strip(), m.group(2).strip()
        if re.match(r"(?:and\b|&|/|\|)", rest, re.I):  # "Ingredients and appearance", table headers
            continue
        text = rest
        if len(text) < 40 and "," not in text:  # (the rest of) the list is below the heading
            nxt = [text] if text else []
            for ln in lines[i + 1 : i + 4]:
                if _HEAD.match(ln) or len(ln) < 3:
                    break
                nxt.append(ln)
                if len(" ".join(nxt)) > 40:
                    break
            text = " ".join(nxt)
        text = re.sub(r"\s+", " ", text).strip(" .;:")
        if len(text) < 8 or len(text) > 2500 or not _looks_like_list(text):
            continue
        k = text.lower()[:120]
        if k in seen:
            continue
        seen.add(k)
        out.append({"heading": heading, "text": text})
        if len(out) >= limit:
            break
    return out
