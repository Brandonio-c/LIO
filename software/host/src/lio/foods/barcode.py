"""Retail barcodes: check digits, GTIN-14 normalisation and decoding photos.

Every product is keyed by its GTIN-14 (the 8, 12 or 13 digits on the pack,
zero-padded to 14), so UPC-A ``012345678905`` and EAN-13 ``0012345678905``
are the same product.

Decoding a photo needs the optional ``zxing-cpp`` and ``Pillow`` packages
(``pip install -e software/host[foods]``). Without them the digits can
still be typed in.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

RETAIL_FORMATS = ("EAN13", "UPCA", "EAN8", "UPCE")


class BarcodeError(ValueError):
    """The text is not a valid retail barcode (shown to the user)."""


def check_digit(body: str) -> int:
    """GS1 mod-10 check digit for ``body`` (all digits except the check digit)."""
    total = 0
    for i, ch in enumerate(reversed(body)):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return (10 - total % 10) % 10


def expand_upce(code: str) -> str:
    """UPC-E (8 digits: number system, 6 data, check) to the equivalent UPC-A."""
    if len(code) != 8 or not code.isdigit() or code[0] not in "01":
        raise BarcodeError(f"{code!r} is not a UPC-E code")
    ns, d, chk = code[0], code[1:7], code[7]
    last = d[5]
    if last in "012":
        body = d[0:2] + last + "0000" + d[2:5]
    elif last == "3":
        body = d[0:3] + "00000" + d[3:5]
    elif last == "4":
        body = d[0:4] + "00000" + d[4]
    else:
        body = d[0:5] + "0000" + last
    upca = ns + body + chk
    if check_digit(upca[:-1]) != int(chk):
        raise BarcodeError(f"UPC-E {code}: wrong check digit")
    return upca


@dataclass(frozen=True)
class Gtin:
    gtin14: str  # the key: 14 digits
    code: str  # as printed: 8 (EAN-8), 12 (UPC-A) or 13 (EAN-13) digits, or 14
    kind: str  # EAN-8 | UPC-A | EAN-13 | GTIN-14

    @property
    def lookup_codes(self) -> list[str]:
        """Forms to try against product databases, most likely first."""
        out = [self.code]
        for form in (self.gtin14[1:], self.gtin14):  # EAN-13, GTIN-14
            if form not in out:
                out.append(form)
        return out


def normalise(text: str, fmt: str = "") -> Gtin:
    """Validate a scanned or typed code and return its GTIN forms.

    ``fmt`` is the decoder's symbology (``UPCE`` needs it: an 8-digit UPC-E
    code is otherwise read as EAN-8).
    """
    digits = "".join(ch for ch in text if not ch.isspace() and ch != "-")
    if not digits.isdigit():
        raise BarcodeError(f"{text!r}: a retail barcode has digits only")
    if fmt.upper().replace("-", "") == "UPCE":
        digits = expand_upce(digits)
    if len(digits) not in (8, 12, 13, 14):
        raise BarcodeError(f"{digits}: expected 8, 12, 13 or 14 digits, got {len(digits)}")
    if check_digit(digits[:-1]) != int(digits[-1]):
        raise BarcodeError(f"{digits}: wrong check digit (misread? scan or type it again)")
    g14 = digits.zfill(14)
    if g14.startswith("000000"):
        code, kind = g14[6:], "EAN-8"
    elif g14.startswith("00"):
        code, kind = g14[2:], "UPC-A"
    elif g14.startswith("0"):
        code, kind = g14[1:], "EAN-13"
    else:
        code, kind = g14, "GTIN-14"
    return Gtin(g14, code, kind)


@dataclass(frozen=True)
class Decoded:
    text: str
    format: str


def decoder_available() -> bool:
    try:
        import PIL  # noqa: F401
        import zxingcpp  # noqa: F401
    except ImportError:
        return False
    return True


def _variants(img: Any) -> Iterator[tuple[str, Any]]:
    """The photo, then enhanced versions that recover soft or low-contrast barcodes.

    Phone photos often blur the narrow white gaps between bars until they read
    as bars; sharpening, local contrast normalisation and fixed thresholds
    below the gaps' brightness bring them back. Cheapest first.
    """
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps

    yield "plain", img
    r = max(2.0, max(img.size) / 350.0)  # about one bar module at typical framing
    yield "sharpen", img.filter(ImageFilter.UnsharpMask(radius=r, percent=250, threshold=0))
    a = np.asarray(img, dtype=np.float32)
    bg = np.asarray(img.filter(ImageFilter.GaussianBlur(max(6.0, 3 * r))), dtype=np.float32)
    norm = np.clip((a - bg) * 3.0 + 128.0, 0, 255).astype(np.uint8)
    yield "local-contrast", Image.fromarray(norm)
    lo, hi = np.percentile(a, 2), np.percentile(a, 98)
    for f in (0.25, 0.35, 0.45):
        yield (
            f"threshold {f:.2f}",
            Image.fromarray(((a > lo + f * (hi - lo)) * 255).astype(np.uint8)),
        )
    # Ink spread: printed bars bleed into the narrow gaps. Widening the light areas
    # (a grey-level dilation) reopens them.
    sharp = img.filter(ImageFilter.UnsharpMask(radius=r, percent=250, threshold=0))
    yield "open gaps", sharp.filter(ImageFilter.MaxFilter(3))
    yield "open gaps, contrast", Image.fromarray(norm).filter(ImageFilter.MaxFilter(3))
    yield (
        "equalise + sharpen",
        ImageOps.equalize(img).filter(
            ImageFilter.UnsharpMask(radius=r * 1.5, percent=300, threshold=0)
        ),
    )
    half = img.resize((img.width // 2, img.height // 2))
    yield "half size", half
    yield "half size, sharpened", half.filter(ImageFilter.UnsharpMask(radius=2, percent=250))


def decode_image(data: bytes, *, retail_only: bool = False) -> list[Decoded]:
    """All barcodes found in a photo (JPEG/PNG/HEIC as Pillow reads it).

    Tries the photo as it is, then enhanced versions (see :func:`_variants`),
    and stops at the first that reads. Retail symbologies first.
    ``retail_only`` (live camera frames) looks for EAN/UPC only, which is
    faster. Raises :class:`BarcodeError` when the decoder is not installed or
    the image cannot be read.
    """
    try:
        import zxingcpp
        from PIL import Image, ImageOps
    except ImportError as e:
        raise BarcodeError(
            "barcode decoding is not installed (pip install zxing-cpp pillow); type the digits"
        ) from e
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    except Exception as e:
        raise BarcodeError(f"cannot read the photo: {e}") from e
    img = img.convert("L")
    if max(img.size) > 3200:  # huge photos: decode time grows, detail does not help
        img.thumbnail((3200, 3200))
    kw: dict[str, Any] = {}
    if retail_only:
        kw["formats"] = zxingcpp.BarcodeFormat.EANUPC
    found: list[Decoded] = []
    for name, im in _variants(img):
        for r in zxingcpp.read_barcodes(im, **kw):
            fmt = str(r.format).split(".")[-1].replace("-", "").upper()
            d = Decoded(r.text, fmt)
            if d not in found:
                found.append(d)
        if found:
            log.debug("barcode read from the %s image", name)
            break
    found.sort(key=lambda d: 0 if d.format in RETAIL_FORMATS else 1)
    return found


def best_code(found: list[Decoded]) -> tuple[Gtin, Decoded] | None:
    """The first decoded barcode that is a valid retail GTIN."""
    for d in found:
        try:
            return normalise(d.text, d.format), d
        except BarcodeError:
            continue
    return None
