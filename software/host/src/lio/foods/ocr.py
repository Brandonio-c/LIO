"""Read ingredient and nutrition labels from photos (Apple Vision, on this Mac).

The text is recognised by a small Swift program (``swift/lio_ocr.swift``),
built with ``xcrun swiftc`` the first time it is needed and cached in
``~/Library/Caches/lio``. Nothing is sent off the Mac.

- :func:`read_label` returns the text in reading order.
- :func:`extract_ingredients` cuts the ingredient list out of it.
- :func:`parse_nutrition` reads a US Nutrition Facts or Supplement Facts
  panel (values per serving) and converts them to per 100 g when the serving
  size is in grams.

Everything here is a proposal: the phone app and the dashboard show it for
review before it is saved.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

CACHE = Path.home() / "Library" / "Caches" / "lio"
_build_lock = threading.Lock()


class OcrError(RuntimeError):
    """Text recognition is not available or failed (shown to the user)."""


@dataclass(frozen=True)
class Line:
    text: str
    conf: float
    x: float
    y: float  # Vision's box: normalised, origin bottom-left
    w: float
    h: float


def available() -> bool:
    return sys.platform == "darwin" and (
        (CACHE / "lio_ocr").is_file() or shutil.which("xcrun") is not None
    )


def _binary() -> Path:
    exe = CACHE / "lio_ocr"
    src = resources.files("lio.foods").joinpath("swift/lio_ocr.swift")
    with _build_lock:
        source = src.read_bytes()
        stamp = CACHE / "lio_ocr.src"
        if exe.is_file() and stamp.is_file() and stamp.read_bytes() == source:
            return exe
        if sys.platform != "darwin" or shutil.which("xcrun") is None:
            raise OcrError("label reading needs macOS with the Xcode command line tools")
        CACHE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            swift = Path(tmp) / "lio_ocr.swift"
            swift.write_bytes(source)
            r = subprocess.run(
                ["xcrun", "swiftc", "-O", str(swift), "-o", str(exe)],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        if r.returncode != 0:
            raise OcrError(f"cannot build the label reader: {r.stderr.strip()[-400:]}")
        stamp.write_bytes(source)
        return exe


def _upright_jpeg(data: bytes) -> bytes:
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((3500, 3500))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()


def recognise(data: bytes) -> list[Line]:
    """Every line of text Vision finds in the photo."""
    exe = _binary()
    with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
        f.write(_upright_jpeg(data))
        f.flush()
        # Vision sometimes fails the first run after a build while it prepares its
        # model (an "e5rt" error); a second try works.
        for attempt in range(3):
            r = subprocess.run(
                [str(exe), f.name], capture_output=True, text=True, timeout=90, check=False
            )
            if r.returncode == 0:
                break
            time.sleep(0.5 * (attempt + 1))
    if r.returncode != 0:
        raise OcrError(f"label reading failed: {r.stderr.strip()[-300:]}")
    return [
        Line(**{k: d[k] for k in ("text", "conf", "x", "y", "w", "h")})
        for d in json.loads(r.stdout)
    ]


def columns(lines: list[Line]) -> list[list[Line]]:
    """Group lines into text columns (overlapping horizontally), each top to bottom.

    Labels often put the nutrition panel and the ingredient list side by side;
    reading straight across the page would interleave them.
    """
    cols: list[list[Line]] = []
    for ln in sorted(lines, key=lambda ln: ln.x):
        for col in cols:
            x0 = min(c.x for c in col)
            x1 = max(c.x + c.w for c in col)
            overlap = min(x1, ln.x + ln.w) - max(x0, ln.x)
            if overlap > 0.3 * min(ln.w, x1 - x0):
                col.append(ln)
                break
        else:
            cols.append([ln])
    for col in cols:
        col.sort(key=lambda ln: -(ln.y + ln.h))
    cols.sort(key=lambda col: min(c.x for c in col))
    return cols


def reading_order(lines: list[Line]) -> list[str]:
    """Column by column (left to right), each top to bottom."""
    return [ln.text for col in columns(lines) for ln in col]


# ------------------------------------------------------------------ ingredients

_START = re.compile(
    r"\b((?:other|inactive|non[- ]?medicinal)\s+ingredients?|ingredients?|ingr[eé]dients?)\s*[:.;]",
    re.I,
)
_STOP = re.compile(
    r"\b(contains\s*:|allergen|may contain|manufactured|distributed|made (?:in|by|for)|"
    r"packed (?:in|by|for)|nutrition facts|supplement facts|directions|suggested use|warning|"
    r"keep (?:out|refrigerated|frozen)|store (?:in|at)|storage|questions|best (?:by|before)|"
    r"net (?:wt|weight|contents)|www\.|https?://|\bdist\.? by)",
    re.I,
)


def _tidy(text: str) -> str:
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)  # words hyphenated across lines
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:)\]])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    return text.strip(" .;,")


def extract_ingredients(lines: list[str]) -> dict[str, str]:
    """The ingredient list (and a "Contains:" allergen statement) from label text.

    ``lines`` in reading order (see :func:`reading_order`): the list runs from
    the "Ingredients:" heading to the next section of the label.
    """
    text = " ".join(lines)
    out: dict[str, str] = {"ingredients": "", "contains": "", "heading": ""}
    m = _START.search(text)
    if m:
        out["heading"] = m.group(1)
        rest = text[m.end() :]
        stop = _STOP.search(rest)
        out["ingredients"] = _tidy(rest[: stop.start()] if stop else rest)
    c = re.search(r"\bcontains\s*:\s*([^.]{2,200})", text, re.I)
    if c:
        out["contains"] = _tidy(c.group(1))
    return out


# -------------------------------------------------------------------- nutrition

_NUM = r"(<\s*)?(\d+(?:[.,]\d+)?)"
# label words -> (our key, unit the key is stored in)
_ROWS: list[tuple[str, str, str]] = [
    (r"calories|energy", "energy_kcal", "kcal"),
    (r"total\s+fat|fat,?\s+total|^fat", "fat_g", "g"),
    (r"saturated\s+fat|sat\.?\s+fat", "saturated_fat_g", "g"),
    (r"trans\s+fat", "trans_fat_g", "g"),
    (r"cholesterol", "cholesterol_mg", "mg"),
    (r"sodium", "sodium_mg", "mg"),
    (r"total\s+carbohydrate|total\s+carb\.?|carbohydrate", "carbohydrates_g", "g"),
    (r"dietary\s+fiber|fibre|fiber", "fiber_g", "g"),
    (r"incl\.?\s+added\s+sugars|includes\s+\d+\s*g\s+added|added\s+sugars", "added_sugars_g", "g"),
    (r"total\s+sugars|sugars", "sugars_g", "g"),
    (r"protein", "protein_g", "g"),
]
_UNIT_FACTOR = {("g", "g"): 1.0, ("mg", "g"): 0.001, ("mcg", "g"): 1e-6, ("g", "mg"): 1000.0,
                ("mg", "mg"): 1.0, ("mcg", "mg"): 0.001}  # fmt: skip


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def parse_nutrition(lines: list[str]) -> dict[str, Any]:
    """Per-serving values from a Nutrition/Supplement Facts panel, and per 100 g.

    Returns ``{"serving": "...", "serving_g": float|None, "per_serving": {...},
    "per_100g": {...}, "rows": [label lines used]}``.
    """
    out: dict[str, Any] = {
        "serving": "",
        "serving_g": None,
        "per_serving": {},
        "per_100g": {},
        "rows": [],
    }
    for ln in lines:
        m = re.search(r"serving\s+size\s*:?\s*(.+)", ln, re.I)
        if m and not out["serving"]:
            out["serving"] = m.group(1).strip()
            g = re.search(r"(\d+(?:[.,]\d+)?)\s*(g|ml)\b", m.group(1), re.I)
            if g:
                out["serving_g"] = _num(g.group(1))
    if out["serving"] and out["serving_g"] is None:  # "Serving size" alone, grams on the next line
        for ln in lines:
            g = re.fullmatch(r"\s*[(]?\s*(\d+(?:[.,]\d+)?)\s*g\s*[)]?\s*", ln, re.I)
            if g:
                out["serving_g"] = _num(g.group(1))
                break
    per: dict[str, float] = {}
    for ln in lines:
        low = ln.lower()
        header = "daily value" in low or "% dv" in low or low.startswith("amount per")
        if header and "calories" not in low:
            continue
        for pat, key, unit in _ROWS:
            if key in per or not re.search(pat, low):
                continue
            if key == "energy_kcal":
                m = re.search(r"(?:calories|energy)\D{0,12}?" + _NUM + r"(?!\s*%)", ln, re.I)
                if m:
                    per[key] = _num(m.group(2))
                    out["rows"].append(ln)
            else:
                m = re.search(_NUM + r"\s*(mcg|µg|mg|g)\b", ln, re.I)
                if m:
                    u = m.group(3).lower().replace("µg", "mcg")
                    per[key] = round(_num(m.group(2)) * _UNIT_FACTOR[(u, unit)], 4)
                    out["rows"].append(ln)
            break
    out["per_serving"] = per
    sg = out["serving_g"]
    if sg:
        out["per_100g"] = {k: round(v * 100.0 / sg, 3) for k, v in per.items()}
        if "sodium_mg" in out["per_100g"]:
            out["per_100g"]["salt_g"] = round(out["per_100g"]["sodium_mg"] * 2.5 / 1000.0, 3)
    return out


def read_label(data: bytes) -> dict[str, Any]:
    """Everything the phone app and the dashboard need from one label photo."""
    found = recognise(data)
    cols = columns(found)
    lines = [ln.text for col in cols for ln in col]
    ingr = extract_ingredients(lines)
    # Nutrition rows: Vision's own lines, each column on its own (values sit on their row).
    nutrition = parse_nutrition(lines)
    return {
        "lines": lines,
        "text": "\n\n".join("\n".join(ln.text for ln in col) for col in cols),
        **ingr,
        "nutrition": nutrition,
    }
